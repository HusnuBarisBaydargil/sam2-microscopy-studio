import base64
import hashlib
import hmac
import io
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError

import cv2
import torch
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from annotation_io import (
    SUPPORTED_ANNOTATION_FORMATS,
    _clamp_annotations_to_image,
    _classes_with_annotation_labels,
    _count_annotation_file,
    _image_size_from_values,
    _normalize_annotation_format,
    _normalize_annotations_payload,
    _normalize_classes,
    _parse_float,
    _read_annotation_file,
    _write_annotation_file,
)
from image_io import (
    ALLOWED_IMAGE_EXTENSIONS,
    _decode_cv2_bgr_image,
    _decode_pil_rgb_image,
    _validate_uploaded_image_file,
)
from preprocessing import (
    PREPROCESS_METHODS,
    _apply_optional_preprocessing_for_sam,
    _normalize_preprocess_method,
    _preprocess_bgr_image,
)
from project_config import (
    load_project_settings,
    normalize_annotation_output_dir,
    normalize_project_settings,
    project_settings_path,
    resolve_annotation_dir,
    save_project_settings,
)
from sam_service import (
    SamInferenceBusyError,
    SamInferenceTimeoutError,
    SAMModelHandler,
    normalize_sam_device,
    normalize_sam_settings,
    sam_presets_response,
)
from security import apply_security_headers, is_authorized_api_request


def _truthy_env(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _positive_int_env(name, default):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _positive_float_env(name, default):
    try:
        value = float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _csv_env(name, default):
    raw_value = os.environ.get(name)
    if not raw_value:
        return default
    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    return values or default


app = Flask(__name__, static_folder='static')
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
MAX_UPLOAD_MB = _positive_int_env("MAX_UPLOAD_MB", 64)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
SAM_MAX_CONCURRENT_REQUESTS = _positive_int_env("SAM_MAX_CONCURRENT_REQUESTS", 1)
SAM_QUEUE_TIMEOUT_SECONDS = _positive_float_env("SAM_QUEUE_TIMEOUT_SECONDS", 5.0)
SAM_INFERENCE_TIMEOUT_SECONDS = _positive_float_env("SAM_INFERENCE_TIMEOUT_SECONDS", 300.0)
ALLOWED_CORS_ORIGINS = _csv_env(
    "ALLOWED_CORS_ORIGINS",
    ["http://127.0.0.1:5000", "http://localhost:5000"],
)
CORS(app, resources={r"/api/*": {"origins": ALLOWED_CORS_ORIGINS}})

SAM_CHECKPOINT_PATH = os.path.join(PROJECT_ROOT, "models", "sam2.1_hiera_large.pt")
SAM_CONFIG_PATH = os.path.join(PROJECT_ROOT, "models", "sam2.1_hiera_l.yaml")
DEFAULT_ANNOTATION_OUTPUT_DIR = os.environ.get("ANNOTATION_OUTPUT_DIR", "annotations")
PROJECT_SETTINGS_FILE = os.environ.get("PROJECT_SETTINGS_FILE", "project_settings.json")
PROJECT_CLASSES_FILE = "project_classes.json"
API_AUTH_TOKEN = (os.environ.get("APP_API_TOKEN") or os.environ.get("API_TOKEN") or "").strip()
PHI_SAFE_MODE = _truthy_env("PHI_SAFE_MODE", False)
PHI_HASH_SALT = os.environ.get("PHI_HASH_SALT", "")
ALLOW_ABSOLUTE_ANNOTATION_DIR = _truthy_env("ALLOW_ABSOLUTE_ANNOTATION_DIR", False)
SKIP_SAM_MODEL_LOAD = _truthy_env("SKIP_SAM_MODEL_LOAD", False)
DEFAULT_ANNOTATION_FORMAT = os.environ.get("ANNOTATION_FORMAT", "csv").strip().lower()
PROJECT_SETTINGS = None
SAM_INFERENCE_SEMAPHORE = threading.BoundedSemaphore(SAM_MAX_CONCURRENT_REQUESTS)
SAM_INFERENCE_EXECUTOR = ThreadPoolExecutor(max_workers=SAM_MAX_CONCURRENT_REQUESTS)


def _run_sam_inference_with_limits(rgb_image, sam_settings):
    if not SAM_INFERENCE_SEMAPHORE.acquire(timeout=SAM_QUEUE_TIMEOUT_SECONDS):
        raise SamInferenceBusyError(
            "SAM2 inference is already running. Try again after the current request finishes."
        )

    def _generate_masks():
        try:
            return sam_model_handler.generate_masks(rgb_image, sam_settings)
        finally:
            SAM_INFERENCE_SEMAPHORE.release()

    future = SAM_INFERENCE_EXECUTOR.submit(_generate_masks)
    try:
        return future.result(timeout=SAM_INFERENCE_TIMEOUT_SECONDS)
    except TimeoutError:
        raise SamInferenceTimeoutError(
            f"SAM2 inference exceeded the {SAM_INFERENCE_TIMEOUT_SECONDS:g} second timeout."
        )

def _resolve_annotation_dir(configured_dir):
    return resolve_annotation_dir(
        configured_dir,
        PROJECT_ROOT,
        DEFAULT_ANNOTATION_OUTPUT_DIR,
        ALLOW_ABSOLUTE_ANNOTATION_DIR,
    )

def _normalize_annotation_output_dir(value):
    return normalize_annotation_output_dir(
        value,
        PROJECT_ROOT,
        DEFAULT_ANNOTATION_OUTPUT_DIR,
        ALLOW_ABSOLUTE_ANNOTATION_DIR,
    )

def _annotation_dir():
    settings = _project_settings()
    configured_dir = settings.get("annotation_output_dir") or DEFAULT_ANNOTATION_OUTPUT_DIR
    return _resolve_annotation_dir(configured_dir)

def _project_settings_path():
    return project_settings_path(PROJECT_ROOT, PROJECT_SETTINGS_FILE)

def _normalize_project_settings(raw_settings=None):
    return normalize_project_settings(
        raw_settings,
        project_root=PROJECT_ROOT,
        default_annotation_output_dir=DEFAULT_ANNOTATION_OUTPUT_DIR,
        allow_absolute_annotation_dir=ALLOW_ABSOLUTE_ANNOTATION_DIR,
    )

def _load_project_settings():
    return load_project_settings(
        _project_settings_path(),
        project_root=PROJECT_ROOT,
        default_annotation_output_dir=DEFAULT_ANNOTATION_OUTPUT_DIR,
        allow_absolute_annotation_dir=ALLOW_ABSOLUTE_ANNOTATION_DIR,
    )

def _save_project_settings(settings):
    return save_project_settings(
        settings,
        _project_settings_path(),
        project_root=PROJECT_ROOT,
        default_annotation_output_dir=DEFAULT_ANNOTATION_OUTPUT_DIR,
        allow_absolute_annotation_dir=ALLOW_ABSOLUTE_ANNOTATION_DIR,
    )

def _project_settings():
    global PROJECT_SETTINGS
    if PROJECT_SETTINGS is None:
        PROJECT_SETTINGS = _load_project_settings()
    return PROJECT_SETTINGS

def _project_settings_response():
    annotation_dir = _annotation_dir()
    sam_settings = normalize_sam_settings(_project_settings().get("sam_settings"))
    return {
        "annotation_output_dir": _project_settings().get("annotation_output_dir"),
        "annotation_dir": None if PHI_SAFE_MODE else annotation_dir,
        "annotation_dir_display": _public_annotation_dir_display(annotation_dir),
        "settings_path": _public_settings_path(_project_settings_path()),
        "annotation_format": _project_settings().get("annotation_format", "csv"),
        "annotation_formats": [
            {"key": key, **metadata}
            for key, metadata in SUPPORTED_ANNOTATION_FORMATS.items()
        ],
        "sam_device": sam_model_handler.status(),
        "sam_settings": sam_settings,
        "sam_presets": sam_presets_response(),
        "privacy": {
            "phi_safe_mode": PHI_SAFE_MODE,
            "salt_configured": bool(PHI_HASH_SALT),
        },
    }

def _safe_image_stem(image_name):
    safe_name = secure_filename(os.path.basename(image_name or "image"))
    stem, _ = os.path.splitext(safe_name)
    return stem or "image"

def _safe_path_stem(image_path):
    normalized_path = str(image_path or "").replace("\\", "/")
    parts = [secure_filename(part) for part in normalized_path.split("/") if part]
    if not parts:
        return _safe_image_stem(image_path)

    stem_parts = []
    for index, part in enumerate(parts):
        stem = os.path.splitext(part)[0] if index == len(parts) - 1 else part
        if stem:
            stem_parts.append(stem)

    return "__".join(stem_parts) or _safe_image_stem(image_path)


def _anonymized_image_stem(image_name, image_path=None):
    identity = str(image_path or image_name or "image").replace("\\", "/").strip().lower()
    key = PHI_HASH_SALT.encode("utf-8")
    digest_source = identity.encode("utf-8")
    if key:
        digest = hmac.new(key, digest_source, hashlib.sha256).hexdigest()
    else:
        digest = hashlib.sha256(digest_source).hexdigest()
    return f"image_{digest[:16]}"


def _public_image_name(image_name, image_path=None):
    if not PHI_SAFE_MODE:
        return image_name
    extension = os.path.splitext(secure_filename(os.path.basename(image_name or "")))[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        extension = ""
    return f"{_anonymized_image_stem(image_name, image_path)}{extension}"


def _public_annotation_path(path):
    if not PHI_SAFE_MODE:
        return _display_path(path)
    return os.path.basename(path).replace(os.sep, "/")


def _public_annotation_dir_display(path):
    if not PHI_SAFE_MODE:
        return _display_path(path)
    return "annotation_dir"


def _public_settings_path(path):
    if not PHI_SAFE_MODE:
        return _display_path(path)
    return "project_settings"


def _annotation_file_names(image_name, image_path=None, match_mode="basename", annotation_format="csv"):
    annotation_format = _normalize_annotation_format(annotation_format)
    if PHI_SAFE_MODE:
        stem = _anonymized_image_stem(image_name, image_path if match_mode == "path" else image_name)
    elif match_mode == "path" and image_path:
        stem = _safe_path_stem(image_path)
    else:
        stem = _safe_image_stem(image_name)

    if annotation_format == "csv":
        return [f"{stem}_annotations.csv"]
    if annotation_format == "csv_rich":
        return [f"{stem}_annotations_rich.csv", f"{stem}_annotations.csv"]
    if annotation_format == "yolo":
        return [f"{stem}.txt", f"{stem}_annotations.txt"]
    if annotation_format == "coco":
        return [f"{stem}_annotations.json", f"{stem}.json"]
    if annotation_format == "voc":
        return [f"{stem}.xml", f"{stem}_annotations.xml"]
    return [f"{stem}_annotations.csv"]

def _annotation_file_name(image_name, image_path=None, match_mode="basename", annotation_format="csv"):
    return _annotation_file_names(image_name, image_path, match_mode, annotation_format)[0]

def _annotation_path_for_image(image_name, image_path=None, match_mode="basename", annotation_format="csv"):
    file_name = _annotation_file_name(image_name, image_path, match_mode, annotation_format)
    return os.path.join(_annotation_dir(), file_name)

def _annotation_candidate_paths(image_name, image_path=None, annotation_format="csv"):
    candidates = []
    if image_path and str(image_path) != str(image_name):
        for file_name in _annotation_file_names(image_name, image_path, "path", annotation_format):
            candidates.append({
                "match_mode": "path",
                "format": annotation_format,
                "path": os.path.join(_annotation_dir(), file_name),
            })
    for file_name in _annotation_file_names(image_name, image_path, "basename", annotation_format):
        candidates.append({
            "match_mode": "basename",
            "format": annotation_format,
            "path": os.path.join(_annotation_dir(), file_name),
        })

    unique = []
    seen_paths = set()
    for candidate in candidates:
        normalized_path = os.path.abspath(candidate["path"])
        if normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)
        unique.append(candidate)
    return unique

def _project_classes_path():
    return os.path.join(_annotation_dir(), PROJECT_CLASSES_FILE)

def _display_path(path):
    try:
        return os.path.relpath(path, PROJECT_ROOT).replace(os.sep, "/")
    except ValueError:
        return os.path.abspath(path).replace(os.sep, "/")

def _image_info_from_payload(raw_image):
    raw_image = raw_image if isinstance(raw_image, dict) else {}
    name = str(raw_image.get("name", "")).strip()
    display_path = str(raw_image.get("display_path") or name).strip()
    width = _parse_float(raw_image.get("width"))
    height = _parse_float(raw_image.get("height"))
    return {
        "id": str(raw_image.get("id") or display_path or name).strip(),
        "name": name,
        "display_path": display_path,
        "width": width,
        "height": height,
    }

def _duplicate_stems_for_images(images):
    counts = {}
    for image in images:
        stem = _safe_image_stem(image.get("name"))
        counts[stem] = counts.get(stem, 0) + 1
    return {stem for stem, count in counts.items() if count > 1}

def _count_annotations_safe(path, annotation_format="csv"):
    try:
        return _count_annotation_file(path, annotation_format)
    except Exception:
        return None

def _first_candidate(candidates, match_mode, must_exist=False):
    for candidate in candidates:
        if candidate["match_mode"] != match_mode:
            continue
        if must_exist and not os.path.exists(candidate["path"]):
            continue
        return candidate
    return None

def _resolve_annotation_match(image_info, duplicate_stems=None, annotation_format=None):
    annotation_format = _normalize_annotation_format(annotation_format or _project_settings().get("annotation_format"))
    duplicate_stems = duplicate_stems or set()
    image_name = image_info.get("name", "")
    image_path = image_info.get("display_path") or image_name
    image_stem = _safe_image_stem(image_name)
    is_duplicate_name = image_stem in duplicate_stems
    candidates = _annotation_candidate_paths(image_name, image_path, annotation_format)
    path_candidate = _first_candidate(candidates, "path")
    base_candidate = _first_candidate(candidates, "basename")
    path_match = _first_candidate(candidates, "path", must_exist=True)
    base_match = _first_candidate(candidates, "basename", must_exist=True)

    if is_duplicate_name:
        if path_match:
            chosen = path_match
            status = "matched"
            message = "Matched by image folder path."
        elif base_match:
            chosen = base_match
            status = "ambiguous"
            message = "Duplicate image name; basename annotation file could match more than one image."
        else:
            chosen = path_candidate or base_candidate
            status = "missing"
            message = "No matching annotation file found."
    elif base_match:
        chosen = base_match
        status = "matched"
        message = "Matched by image name."
    elif path_match:
        chosen = path_match
        status = "matched"
        message = "Matched by image folder path."
    else:
        chosen = base_candidate or path_candidate
        status = "missing"
        message = "No matching annotation file found."

    path = chosen["path"] if chosen else _annotation_path_for_image(image_name, image_path, annotation_format=annotation_format)
    return {
        "id": image_info.get("id"),
        "name": _public_image_name(image_name, image_path),
        "display_path": _public_image_name(image_name, image_path),
        "format": annotation_format,
        "status": status,
        "exists": status == "matched",
        "ambiguous": status == "ambiguous",
        "match_mode": chosen["match_mode"] if chosen else "basename",
        "path": _public_annotation_path(path),
        "annotation_count": _count_annotations_safe(path, annotation_format) if status == "matched" else 0,
        "message": message,
    }

def _save_project_classes(classes):
    os.makedirs(_annotation_dir(), exist_ok=True)
    with open(_project_classes_path(), "w", encoding="utf-8") as file:
        json.dump({"classes": _normalize_classes(classes)}, file, indent=2)

def _load_project_classes():
    path = _project_classes_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return _normalize_classes(data.get("classes"))
    except Exception:
        return []

sam_model_handler = SAMModelHandler(
    SAM_CONFIG_PATH,
    SAM_CHECKPOINT_PATH,
    requested_device=_project_settings().get("sam_device"),
    skip_model_load=SKIP_SAM_MODEL_LOAD,
    display_path=_display_path,
)

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


@app.after_request
def add_security_headers(response):
    return apply_security_headers(response)


@app.before_request
def require_api_token():
    if is_authorized_api_request(request, API_AUTH_TOKEN):
        return None

    return jsonify({
        "error": "API token required.",
        "auth_required": True,
    }), 401


@app.route("/api/auth/status", methods=["GET"])
def auth_status_endpoint():
    return jsonify({"auth_required": bool(API_AUTH_TOKEN)})


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(error):
    return jsonify({"error": f"Request body is too large. Limit is {MAX_UPLOAD_MB} MB."}), 413

@app.route("/api/load_image", methods=["POST"])
def load_image_endpoint():
    if 'image' not in request.files: return jsonify({"error": "No image file provided"}), 400
    file = request.files['image']
    try:
        _validate_uploaded_image_file(file)
        image_stream = file.read()
        image = _decode_pil_rgb_image(image_stream, context="image")
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        encoded_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return jsonify({ "image_url": f"data:image/png;base64,{encoded_image}" })
    except Exception as e:
        return jsonify({"error": f"Failed to decode image file: {e}"}), 400

@app.route("/api/clahe", methods=["POST"])
def apply_clahe_endpoint():
    return _preprocess_endpoint_response("clahe", {})

@app.route("/api/preprocess", methods=["POST"])
def apply_preprocess_endpoint():
    raw_params = {}
    if request.form.get("params"):
        try:
            raw_params = json.loads(request.form.get("params"))
        except json.JSONDecodeError:
            return jsonify({"error": "params must be valid JSON"}), 400
    try:
        method = _normalize_preprocess_method(request.form.get("method"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return _preprocess_endpoint_response(method, raw_params)

def _preprocess_endpoint_response(method, raw_params):
    if 'image' not in request.files: return jsonify({"error": "No image file provided"}), 400
    file = request.files['image']
    try:
        _validate_uploaded_image_file(file)
        image_stream = file.read()
        bgr_image = _decode_cv2_bgr_image(image_stream, context="image")
        processed_bgr, params = _preprocess_bgr_image(bgr_image, method, raw_params)
        is_success, buffer_np = cv2.imencode('.png', processed_bgr)
        if not is_success: raise RuntimeError("Failed to encode image to PNG format.")
        encoded_image = base64.b64encode(buffer_np.tobytes()).decode('utf-8')
        return jsonify({
            "image": f"data:image/png;base64,{encoded_image}",
            "method": method,
            "label": PREPROCESS_METHODS[method],
            "params": params,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Failed to process image"}), 500

@app.route("/api/classes", methods=["GET", "POST"])
def load_classes_endpoint():
    if request.method == "GET":
        return jsonify({
            "classes": _load_project_classes(),
            "classes_path": _public_annotation_path(_project_classes_path()),
        })

    data = request.get_json(silent=True) or {}
    try:
        classes = _normalize_classes(data.get("classes", []))
        _save_project_classes(classes)
        return jsonify({
            "classes": classes,
            "classes_path": _public_annotation_path(_project_classes_path()),
        })
    except Exception as e:
        return jsonify({"error": f"Failed to save project classes: {e}"}), 500

@app.route("/api/project/settings", methods=["GET", "POST"])
def project_settings_endpoint():
    global PROJECT_SETTINGS

    if request.method == "GET":
        return jsonify(_project_settings_response())

    data = request.get_json(silent=True) or {}
    next_settings = dict(_project_settings())

    if "annotation_output_dir" in data:
        annotation_output_dir = str(data.get("annotation_output_dir", "")).strip()
        if not annotation_output_dir:
            return jsonify({"error": "annotation_output_dir cannot be empty"}), 400
        try:
            _normalize_annotation_output_dir(annotation_output_dir)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        next_settings["annotation_output_dir"] = annotation_output_dir

    if "annotation_format" in data:
        try:
            next_settings["annotation_format"] = _normalize_annotation_format(data.get("annotation_format"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    device_changed = False
    if "sam_device" in data:
        try:
            sam_device = normalize_sam_device(data.get("sam_device"))
            if sam_device == "cuda" and not torch.cuda.is_available():
                return jsonify({"error": "CUDA was requested for SAM2, but CUDA is not available."}), 400
            device_changed = sam_device != normalize_sam_device(next_settings.get("sam_device"))
            next_settings["sam_device"] = sam_device
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    if "sam_settings" in data:
        try:
            sam_settings = normalize_sam_settings(data.get("sam_settings"))
            next_settings["sam_settings"] = {
                "preset": sam_settings["preset"],
                "params": sam_settings["params"],
            }
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    try:
        PROJECT_SETTINGS = _save_project_settings(next_settings)
        if device_changed:
            sam_model_handler.set_requested_device(PROJECT_SETTINGS["sam_device"])
        os.makedirs(_annotation_dir(), exist_ok=True)
        return jsonify(_project_settings_response())
    except Exception as e:
        return jsonify({"error": f"Failed to update project settings: {e}"}), 500

@app.route("/api/annotations/match", methods=["POST"])
def match_annotations_endpoint():
    data = request.get_json(silent=True) or {}
    try:
        annotation_format = _normalize_annotation_format(
            data.get("format") or data.get("annotation_format") or _project_settings().get("annotation_format")
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    images = [_image_info_from_payload(image) for image in data.get("images", [])]
    images = [image for image in images if image["name"]]
    duplicate_stems = _duplicate_stems_for_images(images)
    results = [_resolve_annotation_match(image, duplicate_stems, annotation_format) for image in images]
    summary = {
        "total": len(results),
        "matched": sum(1 for result in results if result["status"] == "matched"),
        "missing": sum(1 for result in results if result["status"] == "missing"),
        "ambiguous": sum(1 for result in results if result["status"] == "ambiguous"),
    }
    return jsonify({
        "annotation_dir": None if PHI_SAFE_MODE else _annotation_dir(),
        "annotation_dir_display": _public_annotation_dir_display(_annotation_dir()),
        "format": annotation_format,
        "results": results,
        "summary": summary,
    })

@app.route("/api/annotations/bulk_load", methods=["POST"])
def bulk_load_annotations_endpoint():
    data = request.get_json(silent=True) or {}
    try:
        annotation_format = _normalize_annotation_format(
            data.get("format") or data.get("annotation_format") or _project_settings().get("annotation_format")
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    images = [_image_info_from_payload(image) for image in data.get("images", [])]
    images = [image for image in images if image["name"]]
    duplicate_stems = _duplicate_stems_for_images(images)
    results = []

    for image in images:
        match = _resolve_annotation_match(image, duplicate_stems, annotation_format)
        if match["status"] != "matched":
            results.append({**match, "annotations": []})
            continue

        try:
            path = _annotation_path_for_image(
                image["name"],
                image["display_path"],
                match["match_mode"],
                annotation_format,
            )
            if match.get("path"):
                for candidate in _annotation_candidate_paths(image["name"], image["display_path"], annotation_format):
                    if match["path"] in (_display_path(candidate["path"]), _public_annotation_path(candidate["path"])):
                        path = candidate["path"]
                        break
            results.append({
                **match,
                "annotations": _read_annotation_file(
                    path,
                    annotation_format,
                    image_name=image["name"],
                    image_size=(image.get("width"), image.get("height")),
                    classes=_load_project_classes(),
                ),
            })
        except Exception as e:
            results.append({
                **match,
                "status": "error",
                "exists": False,
                "annotations": [],
                "message": f"Failed to load annotations: {e}",
            })

    summary = {
        "total": len(results),
        "loaded": sum(1 for result in results if result["status"] == "matched"),
        "missing": sum(1 for result in results if result["status"] == "missing"),
        "ambiguous": sum(1 for result in results if result["status"] == "ambiguous"),
        "errors": sum(1 for result in results if result["status"] == "error"),
    }
    return jsonify({
        "classes": _load_project_classes(),
        "format": annotation_format,
        "results": results,
        "summary": summary,
    })

@app.route("/api/annotations/load", methods=["GET"])
def load_annotations_endpoint():
    image_name = request.args.get("image_name", "").strip()
    image_path = request.args.get("image_path", "").strip()
    match_mode = request.args.get("match_mode", "auto").strip()
    try:
        annotation_format = _normalize_annotation_format(
            request.args.get("format") or request.args.get("annotation_format") or _project_settings().get("annotation_format")
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not image_name:
        return jsonify({"error": "image_name is required"}), 400
    image_size = (
        request.args.get("image_width") or request.args.get("width"),
        request.args.get("image_height") or request.args.get("height"),
    )

    if match_mode in ("basename", "path"):
        candidates = _annotation_candidate_paths(image_name, image_path, annotation_format)
        path = None
        for candidate in candidates:
            if candidate["match_mode"] == match_mode and os.path.exists(candidate["path"]):
                path = candidate["path"]
                break
        if path is None:
            path = _annotation_path_for_image(image_name, image_path, match_mode, annotation_format)
        path_exists = os.path.exists(path)
        match = {
            "exists": path_exists,
            "format": annotation_format,
            "match_mode": match_mode,
            "path": _public_annotation_path(path),
            "status": "matched" if path_exists else "missing",
            "annotation_count": _count_annotations_safe(path, annotation_format) if path_exists else 0,
            "message": "Matched annotation file." if path_exists else "No matching annotation file found.",
        }
    else:
        image_info = {"id": image_path or image_name, "name": image_name, "display_path": image_path or image_name}
        match = _resolve_annotation_match(image_info, annotation_format=annotation_format)
        path = None
        for candidate in _annotation_candidate_paths(image_name, image_path, annotation_format):
            if match.get("path") in (_display_path(candidate["path"]), _public_annotation_path(candidate["path"])):
                path = candidate["path"]
                break
        if path is None:
            path = _annotation_path_for_image(image_name, image_path, match["match_mode"], annotation_format)

    if not os.path.exists(path):
        return jsonify({
            "exists": False,
            "annotations": [],
            "classes": _load_project_classes(),
            "format": annotation_format,
            "path": _public_annotation_path(path),
            "match": match,
        })

    try:
        if annotation_format == "yolo":
            _image_size_from_values(*image_size, required=True, context="YOLO annotations")
        annotations = _read_annotation_file(
            path,
            annotation_format,
            image_name=image_name,
            image_size=image_size,
            classes=_load_project_classes(),
        )
        return jsonify({
            "exists": True,
            "annotations": annotations,
            "classes": _load_project_classes(),
            "format": annotation_format,
            "path": _public_annotation_path(path),
            "match": match,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to load annotations: {e}"}), 500

@app.route("/api/annotations/save", methods=["POST"])
def save_annotations_endpoint():
    data = request.get_json(silent=True) or {}
    image_name = str(data.get("image_name", "")).strip()
    image_path = str(data.get("image_path") or image_name).strip()
    match_mode = str(data.get("match_mode") or "basename").strip()
    overwrite = bool(data.get("overwrite", True))
    annotations = data.get("annotations", [])
    classes = data.get("classes", [])
    image_size = (data.get("image_width") or data.get("width"), data.get("image_height") or data.get("height"))

    if not image_name:
        return jsonify({"error": "image_name is required"}), 400
    if match_mode not in ("basename", "path"):
        return jsonify({"error": "match_mode must be basename or path"}), 400
    try:
        annotation_format = _normalize_annotation_format(
            data.get("format") or data.get("annotation_format") or _project_settings().get("annotation_format")
        )
        annotations = _normalize_annotations_payload(annotations)
        classes = _classes_with_annotation_labels(classes, annotations)
        normalized_image_size = _image_size_from_values(
            *image_size,
            required=annotation_format == "yolo",
            context="YOLO annotations" if annotation_format == "yolo" else "annotations",
        )
        annotations, clamped_count = _clamp_annotations_to_image(annotations, normalized_image_size)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        path = _annotation_path_for_image(image_name, image_path, match_mode, annotation_format)
        if os.path.exists(path) and not overwrite:
            return jsonify({
                "error": "Annotation file already exists.",
                "exists": True,
                "path": _public_annotation_path(path),
                "format": annotation_format,
            }), 409

        _save_project_classes(classes)
        _write_annotation_file(
            path,
            _public_image_name(image_name, image_path),
            annotations,
            annotation_format,
            image_size=normalized_image_size,
            classes=classes,
        )
        return jsonify({
            "saved": True,
            "count": len(annotations),
            "clamped_count": clamped_count,
            "path": _public_annotation_path(path),
            "format": annotation_format,
            "match_mode": match_mode,
            "classes_path": _public_annotation_path(_project_classes_path()),
        })
    except Exception as e:
        return jsonify({"error": f"Failed to save annotations: {e}"}), 500

@app.route("/api/run_sam", methods=["POST"])
def run_sam_endpoint():
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400
    if not sam_model_handler.is_ready():
        return jsonify({"error": "SAM2 model is not available on the server."}), 503
    file = request.files['image']
    try:
        _validate_uploaded_image_file(file)
        raw_sam_settings = {}
        if request.form.get("sam_settings"):
            try:
                raw_sam_settings = json.loads(request.form.get("sam_settings"))
            except json.JSONDecodeError:
                return jsonify({"error": "sam_settings must be valid JSON"}), 400

        image_stream = file.read()
        bgr_image = _decode_cv2_bgr_image(image_stream, context="image")
        bgr_image, preprocess_info = _apply_optional_preprocessing_for_sam(bgr_image, request.form)
        rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        sam_settings = normalize_sam_settings(raw_sam_settings or _project_settings().get("sam_settings"))
        filtered_masks = _run_sam_inference_with_limits(rgb_image, sam_settings)
        return jsonify({
            "masks": filtered_masks,
            "sam_settings": sam_settings,
            "preprocess": preprocess_info,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except SamInferenceBusyError as e:
        return jsonify({"error": str(e)}), 429
    except SamInferenceTimeoutError as e:
        return jsonify({"error": str(e)}), 504
    except Exception as e:
        print(f"Error during SAM processing: {e}")
        return jsonify({"error": f"Failed to run SAM model: {e}"}), 500

if __name__ == "__main__":
    app.run(
        host=os.environ.get("APP_HOST", "127.0.0.1"),
        port=_positive_int_env("APP_PORT", 5000),
        debug=False,
    )
