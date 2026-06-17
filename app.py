import base64
import csv
import hashlib
import hmac
import io
import json
import os
import re
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from xml.sax.saxutils import escape as xml_escape

import cv2
import numpy as np
import torch
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from hydra.utils import instantiate
from omegaconf import OmegaConf
from PIL import Image
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator


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
MAX_DECODED_IMAGE_PIXELS = _positive_int_env("MAX_DECODED_IMAGE_PIXELS", 25_000_000)
SAM_MAX_CONCURRENT_REQUESTS = _positive_int_env("SAM_MAX_CONCURRENT_REQUESTS", 1)
SAM_QUEUE_TIMEOUT_SECONDS = _positive_float_env("SAM_QUEUE_TIMEOUT_SECONDS", 5.0)
SAM_INFERENCE_TIMEOUT_SECONDS = _positive_float_env("SAM_INFERENCE_TIMEOUT_SECONDS", 300.0)
ALLOWED_CORS_ORIGINS = _csv_env(
    "ALLOWED_CORS_ORIGINS",
    ["http://127.0.0.1:5000", "http://localhost:5000"],
)
CORS(app, resources={r"/api/*": {"origins": ALLOWED_CORS_ORIGINS}})
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/bmp", "image/x-ms-bmp", "image/tiff", "image/x-tiff"}
ALLOWED_PIL_IMAGE_FORMATS = {"JPEG", "PNG", "BMP", "TIFF"}

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
DEFAULT_SAM_DEVICE = os.environ.get("SAM_DEVICE", "auto").strip().lower() or "auto"
SUPPORTED_SAM_DEVICES = {"auto", "cuda", "cpu"}
DEFAULT_ANNOTATION_FORMAT = os.environ.get("ANNOTATION_FORMAT", "csv").strip().lower()
SUPPORTED_ANNOTATION_FORMATS = {
    "csv": {"label": "Simple CSV", "extension": "csv"},
    "csv_rich": {"label": "Rich CSV", "extension": "csv"},
    "yolo": {"label": "YOLO TXT", "extension": "txt"},
    "coco": {"label": "COCO JSON", "extension": "json"},
    "voc": {"label": "Pascal VOC XML", "extension": "xml"},
}
MAX_ANNOTATIONS_PER_SAVE = _positive_int_env("MAX_ANNOTATIONS_PER_SAVE", 100000)
MAX_CLASSES_PER_PROJECT = _positive_int_env("MAX_CLASSES_PER_PROJECT", 500)
MAX_CLASS_NAME_LENGTH = _positive_int_env("MAX_CLASS_NAME_LENGTH", 128)
MAX_BBOX_ABS_VALUE = float(_positive_int_env("MAX_BBOX_ABS_VALUE", 1000000000))

DEFAULT_SAM_PRESET = "cell_1920x1440"
SAM_PRESETS = {
    "cell_1920x1440": {
        "label": "Cell 1920x1440",
        "description": "Current default tuned for the original cell workflow.",
        "params": {
            "points_per_side": 64,
            "crop_n_layers": 2,
            "min_mask_region_area": 400,
            "crop_overlap_ratio": 0.4,
            "crop_n_points_downscale_factor": 2,
            "points_per_batch": 64,
            "pred_iou_thresh": 0.92,
            "stability_score_thresh": 0.92,
            "stability_score_offset": 1.0,
            "box_nms_thresh": 0.5,
            "crop_nms_thresh": 0.5,
            "use_m2m": True,
            "area_mode": "pixels",
            "min_overall_area": 300,
            "max_overall_area": 30000,
        },
    },
    "general_balanced": {
        "label": "General balanced",
        "description": "Moderate density for varied image types.",
        "params": {
            "points_per_side": 32,
            "crop_n_layers": 1,
            "min_mask_region_area": 100,
            "crop_overlap_ratio": 0.35,
            "crop_n_points_downscale_factor": 2,
            "points_per_batch": 64,
            "pred_iou_thresh": 0.88,
            "stability_score_thresh": 0.90,
            "stability_score_offset": 1.0,
            "box_nms_thresh": 0.5,
            "crop_nms_thresh": 0.5,
            "use_m2m": True,
            "area_mode": "percent",
            "min_overall_area": 0.02,
            "max_overall_area": 5.0,
        },
    },
    "small_image_512": {
        "label": "Small image 512",
        "description": "Lower area filters and moderate density for small images.",
        "params": {
            "points_per_side": 32,
            "crop_n_layers": 1,
            "min_mask_region_area": 20,
            "crop_overlap_ratio": 0.35,
            "crop_n_points_downscale_factor": 2,
            "points_per_batch": 64,
            "pred_iou_thresh": 0.88,
            "stability_score_thresh": 0.88,
            "stability_score_offset": 1.0,
            "box_nms_thresh": 0.5,
            "crop_nms_thresh": 0.5,
            "use_m2m": True,
            "area_mode": "pixels",
            "min_overall_area": 20,
            "max_overall_area": 6000,
        },
    },
    "high_recall": {
        "label": "High recall",
        "description": "More permissive filtering; can be slower and noisier.",
        "params": {
            "points_per_side": 64,
            "crop_n_layers": 2,
            "min_mask_region_area": 50,
            "crop_overlap_ratio": 0.45,
            "crop_n_points_downscale_factor": 2,
            "points_per_batch": 64,
            "pred_iou_thresh": 0.82,
            "stability_score_thresh": 0.86,
            "stability_score_offset": 1.0,
            "box_nms_thresh": 0.45,
            "crop_nms_thresh": 0.45,
            "use_m2m": True,
            "area_mode": "percent",
            "min_overall_area": 0.005,
            "max_overall_area": 8.0,
        },
    },
    "fast_preview": {
        "label": "Fast preview",
        "description": "Lower density and no crop layers for quick first pass.",
        "params": {
            "points_per_side": 24,
            "crop_n_layers": 0,
            "min_mask_region_area": 100,
            "crop_overlap_ratio": 0.3,
            "crop_n_points_downscale_factor": 2,
            "points_per_batch": 64,
            "pred_iou_thresh": 0.90,
            "stability_score_thresh": 0.92,
            "stability_score_offset": 1.0,
            "box_nms_thresh": 0.5,
            "crop_nms_thresh": 0.5,
            "use_m2m": True,
            "area_mode": "percent",
            "min_overall_area": 0.02,
            "max_overall_area": 5.0,
        },
    },
}
SAM_NUMERIC_LIMITS = {
    "points_per_side": ("int", 8, 128),
    "crop_n_layers": ("int", 0, 3),
    "min_mask_region_area": ("int", 0, 1000000),
    "crop_overlap_ratio": ("float", 0.0, 0.9),
    "crop_n_points_downscale_factor": ("int", 1, 8),
    "points_per_batch": ("int", 16, 256),
    "pred_iou_thresh": ("float", 0.0, 1.0),
    "stability_score_thresh": ("float", 0.0, 1.0),
    "stability_score_offset": ("float", 0.0, 2.0),
    "box_nms_thresh": ("float", 0.0, 1.0),
    "crop_nms_thresh": ("float", 0.0, 1.0),
}
DEFAULT_CLASSES = []
DEFAULT_CLASS_COLORS = [
    "#39d353",
    "#9ca3af",
    "#58a6ff",
    "#f2cc60",
    "#ff7b72",
    "#d2a8ff",
    "#56d4dd",
    "#ffa657",
]
PROJECT_SETTINGS = None
SAM_INFERENCE_SEMAPHORE = threading.BoundedSemaphore(SAM_MAX_CONCURRENT_REQUESTS)
SAM_INFERENCE_EXECUTOR = ThreadPoolExecutor(max_workers=SAM_MAX_CONCURRENT_REQUESTS)


class SamInferenceBusyError(RuntimeError):
    pass


class SamInferenceTimeoutError(RuntimeError):
    pass


def _uploaded_image_extension(file_storage):
    filename = secure_filename(file_storage.filename or "")
    return os.path.splitext(filename)[1].lower()


def _spreadsheet_safe_cell(value):
    text = str(value if value is not None else "")
    return f"'{text}" if re.match(r"^\s*[=+\-@]", text) else text


def _validate_uploaded_image_file(file_storage):
    extension = _uploaded_image_extension(file_storage)
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        raise ValueError(f"unsupported image extension; allowed extensions are: {allowed}")

    mimetype = (file_storage.mimetype or "").lower()
    if mimetype and mimetype != "application/octet-stream" and mimetype not in ALLOWED_IMAGE_MIME_TYPES:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_MIME_TYPES))
        raise ValueError(f"unsupported image MIME type; allowed MIME types are: {allowed}")


def _decoded_pixel_count(width, height):
    try:
        width = int(width)
        height = int(height)
    except (TypeError, ValueError):
        raise ValueError("image dimensions must be numeric")
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
    return width * height


def _validate_decoded_image_size(width, height, context="image"):
    pixel_count = _decoded_pixel_count(width, height)
    if pixel_count > MAX_DECODED_IMAGE_PIXELS:
        raise ValueError(
            f"{context} has {pixel_count} decoded pixels; limit is {MAX_DECODED_IMAGE_PIXELS}."
        )


def _inspect_encoded_image_size(image_bytes, context="image"):
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.format not in ALLOWED_PIL_IMAGE_FORMATS:
                allowed = ", ".join(sorted(ALLOWED_PIL_IMAGE_FORMATS))
                raise ValueError(f"{context} format must be one of: {allowed}")
            _validate_decoded_image_size(image.width, image.height, context=context)
    except ValueError:
        raise
    except Exception:
        return


def _decode_cv2_bgr_image(image_bytes, context="image"):
    _inspect_encoded_image_size(image_bytes, context=context)
    image_array = np.frombuffer(image_bytes, np.uint8)
    bgr_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if bgr_image is None:
        raise ValueError("Failed to decode image")
    height, width = bgr_image.shape[:2]
    _validate_decoded_image_size(width, height, context=context)
    return bgr_image


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

def _path_within(base_path, candidate_path):
    base = os.path.normcase(os.path.abspath(base_path))
    candidate = os.path.normcase(os.path.abspath(candidate_path))
    try:
        return os.path.commonpath([base, candidate]) == base
    except ValueError:
        return False

def _resolve_annotation_dir(configured_dir):
    raw_dir = str(configured_dir or DEFAULT_ANNOTATION_OUTPUT_DIR).strip()
    if not raw_dir:
        raise ValueError("annotation_output_dir cannot be empty")

    expanded_dir = os.path.expanduser(raw_dir)
    if os.path.splitdrive(expanded_dir)[0] and not os.path.isabs(expanded_dir):
        raise ValueError("annotation_output_dir must be relative to the project folder or an absolute path explicitly enabled by the server")
    if os.path.isabs(expanded_dir):
        if not ALLOW_ABSOLUTE_ANNOTATION_DIR:
            raise ValueError(
                "Absolute annotation folders are disabled. Use a relative folder under the project root "
                "or set ALLOW_ABSOLUTE_ANNOTATION_DIR=1."
            )
        return os.path.abspath(expanded_dir)

    resolved_dir = os.path.abspath(os.path.join(PROJECT_ROOT, expanded_dir))
    if not _path_within(PROJECT_ROOT, resolved_dir):
        raise ValueError("annotation_output_dir must stay inside the project folder")
    return resolved_dir

def _normalize_annotation_output_dir(value):
    raw_dir = str(value or DEFAULT_ANNOTATION_OUTPUT_DIR).strip()
    _resolve_annotation_dir(raw_dir)
    return raw_dir

def _annotation_dir():
    settings = _project_settings()
    configured_dir = settings.get("annotation_output_dir") or DEFAULT_ANNOTATION_OUTPUT_DIR
    return _resolve_annotation_dir(configured_dir)

def _project_settings_path():
    if os.path.isabs(PROJECT_SETTINGS_FILE):
        return os.path.abspath(PROJECT_SETTINGS_FILE)
    return os.path.join(PROJECT_ROOT, PROJECT_SETTINGS_FILE)

def _default_sam_settings():
    return {
        "preset": DEFAULT_SAM_PRESET,
        "params": dict(SAM_PRESETS[DEFAULT_SAM_PRESET]["params"]),
    }

def _sam_presets_response():
    return [
        {
            "key": key,
            "label": preset["label"],
            "description": preset["description"],
            "params": dict(preset["params"]),
        }
        for key, preset in SAM_PRESETS.items()
    ]

def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)

def _coerce_number(value, key, value_type):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be a number")
    return int(round(number)) if value_type == "int" else number

def _normalize_bounded_number(value, key, value_type, minimum, maximum, warnings):
    number = _coerce_number(value, key, value_type)
    original = number
    if number < minimum:
        number = minimum
    if number > maximum:
        number = maximum
    if number != original:
        warnings.append(f"{key} was clamped to {number}.")
    return number

def _normalize_sam_settings(raw_settings=None):
    raw_settings = raw_settings if isinstance(raw_settings, dict) else {}
    preset = str(raw_settings.get("preset") or DEFAULT_SAM_PRESET).strip()
    if preset not in SAM_PRESETS and preset != "custom":
        preset = DEFAULT_SAM_PRESET

    base_preset = DEFAULT_SAM_PRESET if preset == "custom" else preset
    base_params = dict(SAM_PRESETS[base_preset]["params"])
    raw_params = raw_settings.get("params")
    if not isinstance(raw_params, dict):
        raw_params = {}

    params = {}
    warnings = []
    for key, (value_type, minimum, maximum) in SAM_NUMERIC_LIMITS.items():
        value = raw_params.get(key, base_params.get(key))
        params[key] = _normalize_bounded_number(value, key, value_type, minimum, maximum, warnings)

    params["use_m2m"] = _coerce_bool(raw_params.get("use_m2m", base_params.get("use_m2m", True)))
    area_mode = str(raw_params.get("area_mode", base_params.get("area_mode", "pixels"))).strip().lower()
    params["area_mode"] = "percent" if area_mode == "percent" else "pixels"

    area_minimum = 0.0
    area_maximum = 100.0 if params["area_mode"] == "percent" else 100000000.0
    params["min_overall_area"] = _normalize_bounded_number(
        raw_params.get("min_overall_area", base_params.get("min_overall_area", 0)),
        "min_overall_area",
        "float",
        area_minimum,
        area_maximum,
        warnings,
    )
    params["max_overall_area"] = _normalize_bounded_number(
        raw_params.get("max_overall_area", base_params.get("max_overall_area", area_maximum)),
        "max_overall_area",
        "float",
        area_minimum,
        area_maximum,
        warnings,
    )
    if params["min_overall_area"] > params["max_overall_area"]:
        raise ValueError("min_overall_area cannot be greater than max_overall_area")

    warnings.extend(_sam_risk_warnings(params))
    return {"preset": preset, "params": params, "warnings": warnings}

def _sam_risk_warnings(params):
    warnings = []
    if params["points_per_side"] > 96:
        warnings.append("points_per_side above 96 can be slow and memory intensive.")
    if params["crop_n_layers"] > 2:
        warnings.append("crop_n_layers above 2 can greatly increase runtime and GPU memory usage.")
    if params["points_per_batch"] > 128:
        warnings.append("points_per_batch above 128 can trigger GPU out-of-memory errors.")
    if params["pred_iou_thresh"] < 0.75:
        warnings.append("low pred_iou_thresh can produce many noisy masks.")
    if params["stability_score_thresh"] < 0.75:
        warnings.append("low stability_score_thresh can produce unstable masks.")
    return warnings

def _effective_filter_areas(image_np, params):
    if params["area_mode"] == "percent":
        image_area = float(image_np.shape[0] * image_np.shape[1])
        min_area = int(round(image_area * params["min_overall_area"] / 100.0))
        max_area = int(round(image_area * params["max_overall_area"] / 100.0))
    else:
        min_area = int(round(params["min_overall_area"]))
        max_area = int(round(params["max_overall_area"]))
    return max(0, min_area), max(0, max_area)

def _normalize_annotation_format(value):
    annotation_format = str(value or DEFAULT_ANNOTATION_FORMAT or "csv").strip().lower()
    if annotation_format not in SUPPORTED_ANNOTATION_FORMATS:
        supported = ", ".join(SUPPORTED_ANNOTATION_FORMATS.keys())
        raise ValueError(f"annotation format must be one of: {supported}")
    return annotation_format

def _normalize_sam_device(value=None):
    default_device = DEFAULT_SAM_DEVICE if DEFAULT_SAM_DEVICE in SUPPORTED_SAM_DEVICES else "auto"
    device = str(value or default_device).strip().lower()
    if device not in SUPPORTED_SAM_DEVICES:
        supported = ", ".join(sorted(SUPPORTED_SAM_DEVICES))
        raise ValueError(f"sam_device must be one of: {supported}")
    return device

def _normalize_project_settings(raw_settings=None):
    raw_settings = raw_settings if isinstance(raw_settings, dict) else {}
    try:
        annotation_output_dir = _normalize_annotation_output_dir(
            raw_settings.get("annotation_output_dir") or DEFAULT_ANNOTATION_OUTPUT_DIR
        )
    except ValueError:
        annotation_output_dir = "annotations"
    try:
        sam_settings = _normalize_sam_settings(raw_settings.get("sam_settings"))
    except ValueError:
        sam_settings = _default_sam_settings()
    try:
        annotation_format = _normalize_annotation_format(raw_settings.get("annotation_format"))
    except ValueError:
        annotation_format = "csv"
    try:
        sam_device = _normalize_sam_device(raw_settings.get("sam_device"))
    except ValueError:
        sam_device = _normalize_sam_device()
    return {
        "annotation_output_dir": annotation_output_dir,
        "annotation_format": annotation_format,
        "sam_device": sam_device,
        "sam_settings": {
            "preset": sam_settings["preset"],
            "params": sam_settings["params"],
        },
    }

def _load_project_settings():
    path = _project_settings_path()
    if not os.path.exists(path):
        return _normalize_project_settings()
    try:
        with open(path, "r", encoding="utf-8") as file:
            return _normalize_project_settings(json.load(file))
    except Exception:
        return _normalize_project_settings()

def _save_project_settings(settings):
    normalized = _normalize_project_settings(settings)
    with open(_project_settings_path(), "w", encoding="utf-8") as file:
        json.dump(normalized, file, indent=2)
    return normalized

def _project_settings():
    global PROJECT_SETTINGS
    if PROJECT_SETTINGS is None:
        PROJECT_SETTINGS = _load_project_settings()
    return PROJECT_SETTINGS

def _project_settings_response():
    annotation_dir = _annotation_dir()
    sam_settings = _normalize_sam_settings(_project_settings().get("sam_settings"))
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
        "sam_presets": _sam_presets_response(),
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

def _is_clean_text(value):
    return all(ord(char) >= 32 and ord(char) != 127 for char in value)

def _normalize_class_name(value, fallback="Unlabeled"):
    class_name = str(value or fallback).strip() or fallback
    if len(class_name) > MAX_CLASS_NAME_LENGTH:
        raise ValueError(f"class name cannot exceed {MAX_CLASS_NAME_LENGTH} characters")
    if not _is_clean_text(class_name):
        raise ValueError("class name cannot contain control characters")
    return class_name

def _normalize_class_color(value):
    color = str(value or "#9ca3af").strip()
    if len(color) > 32 or not color.startswith("#") or not _is_clean_text(color):
        return "#9ca3af"
    return color

def _normalize_hotkey(value):
    hotkey = str(value or "").strip().lower()[:1]
    return hotkey if _is_clean_text(hotkey) else ""

def _normalize_classes(raw_classes):
    if not isinstance(raw_classes, list):
        return []

    normalized_classes = []
    seen_names = set()
    for item in raw_classes[:MAX_CLASSES_PER_PROJECT]:
        if not isinstance(item, dict):
            continue
        try:
            name = _normalize_class_name(item.get("name"), fallback="")
        except ValueError:
            continue
        if not name or name in seen_names:
            continue
        color = _normalize_class_color(item.get("color"))
        hotkey = _normalize_hotkey(item.get("hotkey"))
        normalized_classes.append({"name": name, "color": color, "hotkey": hotkey})
        seen_names.add(name)

    return normalized_classes

def _classes_with_annotation_labels(raw_classes, annotations):
    classes = _normalize_classes(raw_classes)
    seen_names = {class_info["name"] for class_info in classes}
    used_hotkeys = {class_info["hotkey"] for class_info in classes if class_info.get("hotkey")}

    for annotation in annotations:
        if len(classes) >= MAX_CLASSES_PER_PROJECT:
            break
        try:
            class_name = _normalize_class_name(annotation.get("class"))
        except ValueError:
            continue
        if class_name in seen_names:
            continue

        hotkey = ""
        for candidate in (class_name.lower().replace(" ", "") + "abcdefghijklmnopqrstuvwxyz0123456789"):
            if candidate.isalnum() and candidate not in used_hotkeys:
                hotkey = candidate
                break

        if hotkey:
            used_hotkeys.add(hotkey)
        classes.append({
            "name": class_name,
            "color": DEFAULT_CLASS_COLORS[len(classes) % len(DEFAULT_CLASS_COLORS)],
            "hotkey": hotkey,
        })
        seen_names.add(class_name)

    return classes

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

def _parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _is_finite_number(value):
    return isinstance(value, (int, float)) and np.isfinite(value)

def _normalize_bbox(raw_bbox, field_name="bbox", allow_flip=False):
    if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
        raise ValueError(f"{field_name} must contain four numeric values")

    try:
        bbox = [float(value) for value in raw_bbox]
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must contain only numeric values")

    if not all(_is_finite_number(value) for value in bbox):
        raise ValueError(f"{field_name} values must be finite numbers")

    if allow_flip:
        if bbox[2] < 0:
            bbox[0] += bbox[2]
            bbox[2] = abs(bbox[2])
        if bbox[3] < 0:
            bbox[1] += bbox[3]
            bbox[3] = abs(bbox[3])

    if bbox[2] <= 0 or bbox[3] <= 0:
        raise ValueError(f"{field_name} width and height must be greater than zero")

    if any(abs(value) > MAX_BBOX_ABS_VALUE for value in bbox):
        raise ValueError(f"{field_name} values are too large")

    return bbox


def _clamp_bbox_to_image(raw_bbox, image_size, field_name="bbox"):
    bbox = _normalize_bbox(raw_bbox, field_name=field_name, allow_flip=True)
    dimensions = _image_size_from_values(
        *(image_size or (None, None)),
        required=False,
        context=field_name,
    )
    if not dimensions:
        return bbox

    image_width, image_height = dimensions
    x, y, w, h = bbox
    x_min = max(0.0, min(float(image_width), x))
    y_min = max(0.0, min(float(image_height), y))
    x_max = max(0.0, min(float(image_width), x + w))
    y_max = max(0.0, min(float(image_height), y + h))

    if x_max <= x_min or y_max <= y_min:
        raise ValueError(f"{field_name} is outside the image bounds")

    return [x_min, y_min, x_max - x_min, y_max - y_min]


def _clamp_annotations_to_image(annotations, image_size):
    dimensions = _image_size_from_values(
        *(image_size or (None, None)),
        required=False,
        context="annotations",
    )
    if not dimensions:
        return annotations, 0

    clamped_annotations = []
    changed_count = 0
    for index, annotation in enumerate(annotations):
        original_bbox = annotation.get("bbox")
        clamped_bbox = _clamp_bbox_to_image(
            original_bbox,
            dimensions,
            field_name=f"annotations[{index}].bbox",
        )
        normalized_bbox = _normalize_bbox(
            original_bbox,
            field_name=f"annotations[{index}].bbox",
            allow_flip=True,
        )
        if any(abs(normalized_bbox[item] - clamped_bbox[item]) > 1e-9 for item in range(4)):
            changed_count += 1
        clamped_annotations.append({**annotation, "bbox": clamped_bbox})

    return clamped_annotations, changed_count


def _normalize_contour(raw_contour, field_name="contour"):
    if raw_contour in (None, ""):
        return None
    if isinstance(raw_contour, str):
        try:
            raw_contour = json.loads(raw_contour)
        except json.JSONDecodeError:
            raise ValueError(f"{field_name} must be valid JSON")
    if not isinstance(raw_contour, list):
        raise ValueError(f"{field_name} must be a list of points")

    contour = []
    for point_index, point in enumerate(raw_contour):
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            raise ValueError(f"{field_name}[{point_index}] must contain x and y")
        try:
            x = float(point[0])
            y = float(point[1])
        except (TypeError, ValueError):
            raise ValueError(f"{field_name}[{point_index}] must contain numeric x and y")
        if not _is_finite_number(x) or not _is_finite_number(y):
            raise ValueError(f"{field_name}[{point_index}] values must be finite")
        if abs(x) > MAX_BBOX_ABS_VALUE or abs(y) > MAX_BBOX_ABS_VALUE:
            raise ValueError(f"{field_name}[{point_index}] values are too large")
        contour.append([x, y])

    if len(contour) < 3:
        return None
    return contour


def _optional_finite_number(value):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if _is_finite_number(number) else None


def _segmentation_from_contour(contour):
    normalized = _normalize_contour(contour)
    if not normalized:
        return None
    return [[coordinate for point in normalized for coordinate in point]]


def _contour_from_coco_segmentation(segmentation):
    if not isinstance(segmentation, list) or not segmentation:
        return None
    polygon = segmentation[0] if isinstance(segmentation[0], list) else segmentation
    if not isinstance(polygon, list) or len(polygon) < 6:
        return None
    points = []
    for index in range(0, len(polygon) - 1, 2):
        points.append([polygon[index], polygon[index + 1]])
    return _normalize_contour(points)


def _annotation_mask_metadata(annotation):
    metadata = {}

    try:
        contour = _normalize_contour(annotation.get("contour"))
    except ValueError:
        contour = None
    if contour:
        metadata["contour"] = contour

    for source_key, target_key in (
        ("mask_area", "mask_area"),
        ("predicted_iou", "predicted_iou"),
        ("stability_score", "stability_score"),
    ):
        number = _optional_finite_number(annotation.get(source_key))
        if number is not None:
            metadata[target_key] = number

    source = str(annotation.get("source") or "").strip()[:64]
    if source and _is_clean_text(source):
        metadata["source"] = source

    return metadata


def _normalize_annotation_payload(annotation, index):
    if not isinstance(annotation, dict):
        raise ValueError(f"annotations[{index}] must be an object")

    bbox = _normalize_bbox(annotation.get("bbox"), field_name=f"annotations[{index}].bbox")
    class_name = _normalize_class_name(annotation.get("class"))
    annotation_id = annotation.get("id", index + 1)
    try:
        annotation_id_number = float(annotation_id)
    except (TypeError, ValueError):
        raise ValueError(f"annotations[{index}].id must be a positive integer")
    if (
        not _is_finite_number(annotation_id_number)
        or annotation_id_number <= 0
        or not annotation_id_number.is_integer()
    ):
        raise ValueError(f"annotations[{index}].id must be a positive integer")
    annotation_id = int(annotation_id_number)

    annotation_type = str(annotation.get("type") or "manual").strip()[:64]
    if not _is_clean_text(annotation_type):
        annotation_type = "manual"

    normalized = {
        "id": annotation_id,
        "bbox": bbox,
        "class": class_name,
        "type": annotation_type,
    }
    normalized.update(_annotation_mask_metadata(annotation))
    return normalized

def _normalize_annotations_payload(annotations):
    if not isinstance(annotations, list):
        raise ValueError("annotations must be a list")
    if len(annotations) > MAX_ANNOTATIONS_PER_SAVE:
        raise ValueError(f"annotations cannot contain more than {MAX_ANNOTATIONS_PER_SAVE} items")
    return [
        _normalize_annotation_payload(annotation, index)
        for index, annotation in enumerate(annotations)
    ]

def _annotation_from_csv_row(row, fallback_id):
    normalized = {str(key).strip().lower(): value for key, value in row.items() if key is not None}
    class_name = (
        normalized.get("class_label")
        or normalized.get("class")
        or normalized.get("label")
        or normalized.get("category")
        or ""
    ).strip()

    if {"x_min", "y_min", "x_max", "y_max"}.issubset(normalized):
        x_min = _parse_float(normalized.get("x_min"))
        y_min = _parse_float(normalized.get("y_min"))
        x_max = _parse_float(normalized.get("x_max"))
        y_max = _parse_float(normalized.get("y_max"))
        if None in (x_min, y_min, x_max, y_max):
            return None
        bbox = [x_min, y_min, x_max - x_min, y_max - y_min]
    elif {"x", "y", "w", "h"}.issubset(normalized):
        x = _parse_float(normalized.get("x"))
        y = _parse_float(normalized.get("y"))
        w = _parse_float(normalized.get("w"))
        h = _parse_float(normalized.get("h"))
        if None in (x, y, w, h):
            return None
        bbox = [x, y, w, h]
    else:
        return None

    try:
        bbox = _normalize_bbox(bbox, field_name="CSV bbox", allow_flip=True)
        class_name = _normalize_class_name(class_name)
    except ValueError:
        return None

    parsed_id = _parse_float(normalized.get("id"))
    annotation_id = int(parsed_id) if _is_finite_number(parsed_id) and parsed_id > 0 else fallback_id
    annotation = {
        "id": annotation_id,
        "bbox": bbox,
        "class": class_name or "Unlabeled",
        "type": "loaded",
    }
    metadata_input = {
        "contour": normalized.get("contour") or normalized.get("segmentation"),
        "mask_area": normalized.get("mask_area"),
        "source": normalized.get("source"),
        "predicted_iou": normalized.get("predicted_iou"),
        "stability_score": normalized.get("stability_score"),
    }
    annotation.update(_annotation_mask_metadata(metadata_input))
    return annotation

def _read_annotation_csv(path):
    annotations = []
    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for index, row in enumerate(reader, start=1):
            annotation = _annotation_from_csv_row(row, index)
            if annotation:
                annotations.append(annotation)
    return annotations

def _write_annotation_csv(path, image_name, annotations, include_metadata=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        header = [
            "source_image",
            "x_min",
            "y_min",
            "x_max",
            "y_max",
            "class_label",
        ]
        if include_metadata:
            header.extend([
                "contour",
                "mask_area",
                "source",
                "predicted_iou",
                "stability_score",
            ])
        writer.writerow(header)
        for annotation in annotations:
            x, y, w, h = _normalize_bbox(annotation.get("bbox"))
            row = [
                _spreadsheet_safe_cell(image_name),
                round(x),
                round(y),
                round(x + w),
                round(y + h),
                _spreadsheet_safe_cell(_normalize_class_name(annotation.get("class"))),
            ]
            if include_metadata:
                metadata = _annotation_mask_metadata(annotation)
                row.extend([
                    json.dumps(metadata.get("contour", []), separators=(",", ":")) if metadata.get("contour") else "",
                    _format_number(metadata["mask_area"]) if "mask_area" in metadata else "",
                    _spreadsheet_safe_cell(metadata.get("source", "")),
                    _format_number(metadata["predicted_iou"]) if "predicted_iou" in metadata else "",
                    _format_number(metadata["stability_score"]) if "stability_score" in metadata else "",
                ])
            writer.writerow(row)

def _image_size_from_values(width, height, required=False, context="annotations"):
    image_width = _parse_float(width)
    image_height = _parse_float(height)
    if (
        _is_finite_number(image_width)
        and _is_finite_number(image_height)
        and image_width > 0
        and image_height > 0
    ):
        return int(round(image_width)), int(round(image_height))
    if required:
        raise ValueError(f"image width and height are required for {context}")
    return None

def _class_name_for_index(classes, class_index):
    if 0 <= class_index < len(classes):
        return classes[class_index]["name"]
    return f"class_{class_index}"

def _class_index_map(classes):
    return {class_info["name"]: index for index, class_info in enumerate(classes)}

def _format_number(value):
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return text or "0"

def _count_annotation_file(path, annotation_format="csv"):
    annotation_format = _normalize_annotation_format(annotation_format)
    if annotation_format in ("csv", "csv_rich"):
        return len(_read_annotation_csv(path))
    if annotation_format == "yolo":
        with open(path, "r", encoding="utf-8-sig") as file:
            return sum(
                1 for line in file
                if line.strip() and not line.lstrip().startswith("#") and len(line.split()) >= 5
            )
    if annotation_format == "coco":
        with open(path, "r", encoding="utf-8-sig") as file:
            data = json.load(file)
        annotations = data.get("annotations", []) if isinstance(data, dict) else []
        return len(annotations) if isinstance(annotations, list) else 0
    if annotation_format == "voc":
        root = ET.parse(path).getroot()
        return len(root.findall(".//object"))
    return 0

def _read_annotation_yolo(path, image_size, classes):
    image_width, image_height = _image_size_from_values(
        *(image_size or (None, None)),
        required=True,
        context="YOLO annotations",
    )
    annotations = []
    with open(path, "r", encoding="utf-8-sig") as file:
        for index, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                class_index = int(float(parts[0]))
                x_center = float(parts[1]) * image_width
                y_center = float(parts[2]) * image_height
                box_width = float(parts[3]) * image_width
                box_height = float(parts[4]) * image_height
                bbox = _normalize_bbox(
                    [
                        x_center - box_width / 2.0,
                        y_center - box_height / 2.0,
                        box_width,
                        box_height,
                    ],
                    field_name="YOLO bbox",
                )
                class_name = _normalize_class_name(_class_name_for_index(classes, class_index))
            except (TypeError, ValueError):
                continue
            annotations.append({
                "id": index,
                "bbox": bbox,
                "class": class_name,
                "type": "loaded",
            })
    return annotations

def _write_annotation_yolo(path, annotations, image_size, classes):
    image_width, image_height = _image_size_from_values(
        *(image_size or (None, None)),
        required=True,
        context="YOLO annotations",
    )
    annotations, _ = _clamp_annotations_to_image(annotations, (image_width, image_height))
    class_indices = _class_index_map(classes)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        for annotation in annotations:
            x, y, w, h = _normalize_bbox(annotation.get("bbox"))
            class_name = _normalize_class_name(annotation.get("class"))
            class_index = class_indices.get(class_name, 0)
            x_center = (x + w / 2.0) / image_width
            y_center = (y + h / 2.0) / image_height
            norm_width = w / image_width
            norm_height = h / image_height
            file.write(
                f"{class_index} {_format_number(x_center)} {_format_number(y_center)} "
                f"{_format_number(norm_width)} {_format_number(norm_height)}\n"
            )

def _matching_coco_image_ids(data, image_name):
    images = data.get("images", []) if isinstance(data, dict) else []
    if not isinstance(images, list):
        return set()
    if not images:
        return set()

    target = os.path.basename(image_name or "").lower()
    matched_ids = {
        image.get("id")
        for image in images
        if os.path.basename(str(image.get("file_name", ""))).lower() == target
    }
    if matched_ids:
        return matched_ids
    if len(images) == 1:
        return {images[0].get("id")}
    return set()

def _read_annotation_coco(path, image_name):
    with open(path, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        return []

    category_map = {}
    categories = data.get("categories", [])
    if isinstance(categories, list):
        for category in categories:
            if not isinstance(category, dict):
                continue
            category_id = category.get("id")
            name = str(category.get("name") or f"category_{category_id}").strip()
            category_map[category_id] = name

    image_ids = _matching_coco_image_ids(data, image_name)
    annotations = []
    raw_annotations = data.get("annotations", [])
    if not isinstance(raw_annotations, list):
        return annotations

    for index, raw_annotation in enumerate(raw_annotations, start=1):
        if not isinstance(raw_annotation, dict):
            continue
        if image_ids and raw_annotation.get("image_id") not in image_ids:
            continue
        try:
            bbox = _normalize_bbox(raw_annotation.get("bbox"), field_name="COCO bbox")
            category_id = raw_annotation.get("category_id")
            class_name = _normalize_class_name(category_map.get(category_id, f"category_{category_id}"))
        except ValueError:
            continue
        annotation_id = raw_annotation.get("id")
        if not isinstance(annotation_id, int) or annotation_id <= 0:
            annotation_id = index
        annotation = {
            "id": annotation_id,
            "bbox": bbox,
            "class": class_name,
            "type": "loaded",
        }
        try:
            contour = _contour_from_coco_segmentation(raw_annotation.get("segmentation"))
        except ValueError:
            contour = None
        metadata_input = {
            "contour": contour,
            "mask_area": raw_annotation.get("mask_area") or (raw_annotation.get("area") if contour else None),
            "source": raw_annotation.get("source"),
            "predicted_iou": raw_annotation.get("predicted_iou"),
            "stability_score": raw_annotation.get("stability_score"),
        }
        annotation.update(_annotation_mask_metadata(metadata_input))
        annotations.append(annotation)
    return annotations

def _write_annotation_coco(path, image_name, annotations, image_size, classes):
    image_size = _image_size_from_values(
        *(image_size or (None, None)),
        required=False,
        context="COCO annotations",
    )
    if image_size:
        annotations, _ = _clamp_annotations_to_image(annotations, image_size)
    image_width, image_height = image_size or (0, 0)
    class_indices = _class_index_map(classes)
    categories = [
        {"id": index + 1, "name": class_info["name"]}
        for index, class_info in enumerate(classes)
    ]
    coco_annotations = []
    for index, annotation in enumerate(annotations, start=1):
        x, y, w, h = _normalize_bbox(annotation.get("bbox"))
        class_name = _normalize_class_name(annotation.get("class"))
        category_id = class_indices.get(class_name, 0) + 1
        metadata = _annotation_mask_metadata(annotation)
        segmentation = _segmentation_from_contour(metadata.get("contour"))
        area = metadata.get("mask_area", w * h)
        coco_annotation = {
            "id": index,
            "image_id": 1,
            "category_id": category_id,
            "bbox": [x, y, w, h],
            "area": area,
            "iscrowd": 0,
        }
        if segmentation:
            coco_annotation["segmentation"] = segmentation
        for key in ("source", "mask_area", "predicted_iou", "stability_score"):
            if key in metadata:
                coco_annotation[key] = metadata[key]
        coco_annotations.append(coco_annotation)
    payload = {
        "images": [{
            "id": 1,
            "file_name": image_name,
            "width": image_width,
            "height": image_height,
        }],
        "categories": categories,
        "annotations": coco_annotations,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

def _read_annotation_voc(path):
    root = ET.parse(path).getroot()
    annotations = []
    for index, obj in enumerate(root.findall(".//object"), start=1):
        bndbox = obj.find("bndbox")
        if bndbox is None:
            continue
        try:
            x_min = _parse_float(bndbox.findtext("xmin"))
            y_min = _parse_float(bndbox.findtext("ymin"))
            x_max = _parse_float(bndbox.findtext("xmax"))
            y_max = _parse_float(bndbox.findtext("ymax"))
            if None in (x_min, y_min, x_max, y_max):
                continue
            bbox = _normalize_bbox([x_min, y_min, x_max - x_min, y_max - y_min], field_name="VOC bbox")
            class_name = _normalize_class_name(obj.findtext("name") or "Unlabeled")
        except ValueError:
            continue
        annotations.append({
            "id": index,
            "bbox": bbox,
            "class": class_name,
            "type": "loaded",
        })
    return annotations

def _write_annotation_voc(path, image_name, annotations, image_size):
    image_size = _image_size_from_values(
        *(image_size or (None, None)),
        required=False,
        context="VOC annotations",
    )
    if image_size:
        annotations, _ = _clamp_annotations_to_image(annotations, image_size)
    image_width, image_height = image_size or (0, 0)
    lines = [
        "<annotation>",
        f"  <filename>{xml_escape(image_name)}</filename>",
        "  <size>",
        f"    <width>{image_width}</width>",
        f"    <height>{image_height}</height>",
        "    <depth>3</depth>",
        "  </size>",
    ]
    for annotation in annotations:
        x, y, w, h = _normalize_bbox(annotation.get("bbox"))
        class_name = _normalize_class_name(annotation.get("class"))
        lines.extend([
            "  <object>",
            f"    <name>{xml_escape(class_name)}</name>",
            "    <pose>Unspecified</pose>",
            "    <truncated>0</truncated>",
            "    <difficult>0</difficult>",
            "    <bndbox>",
            f"      <xmin>{round(x)}</xmin>",
            f"      <ymin>{round(y)}</ymin>",
            f"      <xmax>{round(x + w)}</xmax>",
            f"      <ymax>{round(y + h)}</ymax>",
            "    </bndbox>",
            "  </object>",
        ])
    lines.append("</annotation>")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as file:
        file.write("\n".join(lines) + "\n")

def _read_annotation_file(path, annotation_format="csv", image_name="", image_size=None, classes=None):
    annotation_format = _normalize_annotation_format(annotation_format)
    classes = _normalize_classes(classes if classes is not None else _load_project_classes())
    if annotation_format in ("csv", "csv_rich"):
        return _read_annotation_csv(path)
    if annotation_format == "yolo":
        return _read_annotation_yolo(path, image_size, classes)
    if annotation_format == "coco":
        return _read_annotation_coco(path, image_name)
    if annotation_format == "voc":
        return _read_annotation_voc(path)
    return []

def _write_annotation_file(path, image_name, annotations, annotation_format="csv", image_size=None, classes=None):
    annotation_format = _normalize_annotation_format(annotation_format)
    classes = _normalize_classes(classes if classes is not None else _load_project_classes())
    normalized_image_size = _image_size_from_values(
        *(image_size or (None, None)),
        required=annotation_format == "yolo",
        context="YOLO annotations" if annotation_format == "yolo" else "annotations",
    )
    if normalized_image_size:
        annotations, _ = _clamp_annotations_to_image(annotations, normalized_image_size)
    if annotation_format == "csv":
        _write_annotation_csv(path, image_name, annotations, include_metadata=False)
    elif annotation_format == "csv_rich":
        _write_annotation_csv(path, image_name, annotations, include_metadata=True)
    elif annotation_format == "yolo":
        _write_annotation_yolo(path, annotations, normalized_image_size, classes)
    elif annotation_format == "coco":
        _write_annotation_coco(path, image_name, annotations, normalized_image_size, classes)
    elif annotation_format == "voc":
        _write_annotation_voc(path, image_name, annotations, normalized_image_size)
    else:
        raise ValueError("unsupported annotation format")


PREPROCESS_METHODS = {
    "clahe": "CLAHE",
    "gamma": "Gamma",
    "clahe_unsharp": "CLAHE + Unsharp",
    "gamma_unsharp": "Gamma + Unsharp",
    "retinex_mild": "Retinex mild",
}

PREPROCESS_DEFAULT_PARAMS = {
    "clahe_clip_limit": 2.0,
    "clahe_tile_grid_size": 8,
    "gamma": 1.2,
    "unsharp_amount": 0.8,
    "unsharp_radius": 1.2,
    "unsharp_threshold": 3,
    "retinex_strength": 0.55,
}

def _bounded_float(value, fallback, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if not np.isfinite(number):
        return fallback
    return min(max(number, minimum), maximum)

def _bounded_int(value, fallback, minimum, maximum):
    return int(round(_bounded_float(value, fallback, minimum, maximum)))

def _normalize_preprocess_method(value):
    method = str(value or "clahe").strip().lower()
    if method not in PREPROCESS_METHODS:
        raise ValueError(f"preprocess method must be one of: {', '.join(PREPROCESS_METHODS.keys())}")
    return method

def _normalize_preprocess_params(raw_params=None):
    raw_params = raw_params if isinstance(raw_params, dict) else {}
    params = dict(PREPROCESS_DEFAULT_PARAMS)
    params["clahe_clip_limit"] = _bounded_float(raw_params.get("clahe_clip_limit"), params["clahe_clip_limit"], 0.5, 8.0)
    params["clahe_tile_grid_size"] = _bounded_int(raw_params.get("clahe_tile_grid_size"), params["clahe_tile_grid_size"], 2, 32)
    params["gamma"] = _bounded_float(raw_params.get("gamma"), params["gamma"], 0.2, 3.0)
    params["unsharp_amount"] = _bounded_float(raw_params.get("unsharp_amount"), params["unsharp_amount"], 0.0, 3.0)
    params["unsharp_radius"] = _bounded_float(raw_params.get("unsharp_radius"), params["unsharp_radius"], 0.3, 6.0)
    params["unsharp_threshold"] = _bounded_int(raw_params.get("unsharp_threshold"), params["unsharp_threshold"], 0, 255)
    params["retinex_strength"] = _bounded_float(raw_params.get("retinex_strength"), params["retinex_strength"], 0.1, 1.0)
    return params

def _apply_clahe_bgr(bgr_image, params):
    lab_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab_image)
    tile_size = params["clahe_tile_grid_size"]
    clahe = cv2.createCLAHE(
        clipLimit=params["clahe_clip_limit"],
        tileGridSize=(tile_size, tile_size),
    )
    enhanced_l = clahe.apply(l_channel)
    merged_lab = cv2.merge([enhanced_l, a_channel, b_channel])
    return cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)

def _apply_gamma_bgr(bgr_image, params):
    gamma = max(params["gamma"], 0.01)
    lookup = ((np.arange(256, dtype=np.float32) / 255.0) ** (1.0 / gamma) * 255.0)
    return cv2.LUT(bgr_image, np.clip(lookup, 0, 255).astype(np.uint8))

def _apply_unsharp_bgr(bgr_image, params):
    amount = params["unsharp_amount"]
    if amount <= 0:
        return bgr_image
    blurred = cv2.GaussianBlur(bgr_image, (0, 0), sigmaX=params["unsharp_radius"])
    sharpened = cv2.addWeighted(bgr_image, 1.0 + amount, blurred, -amount, 0)
    threshold = params["unsharp_threshold"]
    if threshold <= 0:
        return sharpened
    delta = cv2.absdiff(bgr_image, blurred)
    mask = cv2.cvtColor(delta, cv2.COLOR_BGR2GRAY) > threshold
    return np.where(mask[:, :, None], sharpened, bgr_image)

def _apply_retinex_mild_bgr(bgr_image, params):
    image = bgr_image.astype(np.float32) + 1.0
    retinex = np.zeros_like(image)
    for sigma in (15, 80, 250):
        blur = cv2.GaussianBlur(image, (0, 0), sigmaX=sigma, sigmaY=sigma)
        retinex += np.log(image) - np.log(blur + 1.0)
    retinex /= 3.0

    normalized_channels = []
    for channel_index in range(3):
        channel = retinex[:, :, channel_index]
        normalized = cv2.normalize(channel, None, 0, 255, cv2.NORM_MINMAX)
        normalized_channels.append(normalized)
    retinex_bgr = cv2.merge(normalized_channels).astype(np.uint8)
    strength = params["retinex_strength"]
    return cv2.addWeighted(bgr_image, 1.0 - strength, retinex_bgr, strength, 0)

def _preprocess_bgr_image(bgr_image, method, params):
    method = _normalize_preprocess_method(method)
    params = _normalize_preprocess_params(params)

    if method == "clahe":
        processed = _apply_clahe_bgr(bgr_image, params)
    elif method == "gamma":
        processed = _apply_gamma_bgr(bgr_image, params)
    elif method == "clahe_unsharp":
        processed = _apply_unsharp_bgr(_apply_clahe_bgr(bgr_image, params), params)
    elif method == "gamma_unsharp":
        processed = _apply_unsharp_bgr(_apply_gamma_bgr(bgr_image, params), params)
    elif method == "retinex_mild":
        processed = _apply_retinex_mild_bgr(bgr_image, params)
    else:
        raise ValueError("unsupported preprocess method")

    return np.clip(processed, 0, 255).astype(np.uint8), params


def _preprocess_request_from_form(form):
    method = str(form.get("preprocess_method") or form.get("method") or "original").strip().lower()
    if method in ("", "original", "none"):
        return "original", {}

    raw_params = {}
    if form.get("preprocess_params"):
        try:
            raw_params = json.loads(form.get("preprocess_params"))
        except json.JSONDecodeError:
            raise ValueError("preprocess_params must be valid JSON")
    elif form.get("params"):
        try:
            raw_params = json.loads(form.get("params"))
        except json.JSONDecodeError:
            raise ValueError("params must be valid JSON")

    return _normalize_preprocess_method(method), raw_params


def _apply_optional_preprocessing_for_sam(bgr_image, form):
    method, raw_params = _preprocess_request_from_form(form)
    if method == "original":
        return bgr_image, {"method": "original", "label": "Original", "params": {}}

    processed_bgr, params = _preprocess_bgr_image(bgr_image, method, raw_params)
    return processed_bgr, {
        "method": method,
        "label": PREPROCESS_METHODS[method],
        "params": params,
    }

class SAMModelHandler:
    def __init__(self, cfg_path, checkpoint_path):
        self.model = None
        self.cfg_path = cfg_path
        self.checkpoint_path = checkpoint_path
        self.requested_device = _normalize_sam_device(_project_settings().get("sam_device"))
        self.device = torch.device("cpu")
        self.last_error = None
        self._lock = threading.RLock()
        if SKIP_SAM_MODEL_LOAD:
            try:
                self.device = self._resolve_device(self.requested_device)
            except Exception as e:
                self.last_error = str(e)
                print(f"FATAL: {self.last_error}")
            print("INFO: SKIP_SAM_MODEL_LOAD=1; SAM2 model initialization skipped.")
        else:
            self._initialize_model()

    def _resolve_device(self, requested_device):
        if requested_device == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if requested_device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested for SAM2, but CUDA is not available.")
        return torch.device(requested_device)

    def _initialize_model(self):
        with self._lock:
            self.model = None
            self.last_error = None
            try:
                self.device = self._resolve_device(self.requested_device)
            except Exception as e:
                self.last_error = str(e)
                print(f"FATAL: {self.last_error}")
                return

        if not os.path.exists(self.cfg_path):
            self.last_error = f"SAM2 config not found: {_display_path(self.cfg_path)}"
            print(f"FATAL: {self.last_error}")
            print("FATAL: Place sam2.1_hiera_l.yaml under models/ or update SAM_CONFIG_PATH.")
            return
        if not os.path.exists(self.checkpoint_path):
            self.last_error = f"SAM2 checkpoint not found: {_display_path(self.checkpoint_path)}"
            print(f"FATAL: {self.last_error}")
            print("FATAL: Place sam2.1_hiera_large.pt under models/ or update SAM_CHECKPOINT_PATH.")
            return

        try:
            cfg = OmegaConf.load(self.cfg_path)
            model = instantiate(cfg.model, _recursive_=True)
            
            state_dict = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)["model"]
            model.load_state_dict(state_dict)
            
            model = model.to(self.device)
            model.eval()
            with self._lock:
                self.model = model
            
            print(f"INFO: SUCCESS: SAM2 model loaded successfully on {self.device}.")
        except Exception as e:
            self.last_error = f"Could not load SAM2 model. Error: {e}"
            print(f"FATAL: {self.last_error}")
            with self._lock:
                self.model = None

    def set_requested_device(self, requested_device):
        requested_device = _normalize_sam_device(requested_device)
        if requested_device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested for SAM2, but CUDA is not available.")
        with self._lock:
            if requested_device == self.requested_device and self.device == self._resolve_device(requested_device):
                return
            self.requested_device = requested_device
        if SKIP_SAM_MODEL_LOAD:
            with self._lock:
                self.device = self._resolve_device(self.requested_device)
            return
        self._initialize_model()

    def status(self):
        with self._lock:
            return {
                "mode": self.requested_device,
                "active": str(self.device),
                "cuda_available": torch.cuda.is_available(),
                "ready": self.is_ready(),
                "model_load_skipped": SKIP_SAM_MODEL_LOAD,
                "error": self.last_error,
            }

    def is_ready(self):
        return self.model is not None

    def generate_masks(self, image_np, sam_settings):
        with self._lock:
            if not self.is_ready(): raise RuntimeError("SAM2 model is not initialized.")
            params = sam_settings["params"]
            mask_generator = SAM2AutomaticMaskGenerator(
                model=self.model,
                points_per_side=params["points_per_side"],
                crop_n_layers=params["crop_n_layers"],
                min_mask_region_area=params["min_mask_region_area"],
                points_per_batch=params["points_per_batch"],
                pred_iou_thresh=params["pred_iou_thresh"],
                stability_score_thresh=params["stability_score_thresh"],
                stability_score_offset=params["stability_score_offset"],
                box_nms_thresh=params["box_nms_thresh"],
                crop_nms_thresh=params["crop_nms_thresh"],
                crop_overlap_ratio=params["crop_overlap_ratio"],
                crop_n_points_downscale_factor=params["crop_n_points_downscale_factor"],
                use_m2m=params["use_m2m"],
            )
            raw_masks = mask_generator.generate(image_np)
        filtered_masks = []
        min_area, max_area = _effective_filter_areas(image_np, params)
        for mask_data in raw_masks:
            if not (min_area <= mask_data["area"] <= max_area): continue
            contours, _ = cv2.findContours(mask_data["segmentation"].astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours: continue
            largest_contour = max(contours, key=cv2.contourArea)
            contour_points = largest_contour.reshape(-1, 2).tolist()
            bounding_box = cv2.boundingRect(largest_contour)
            filtered_masks.append({
                "contour": contour_points,
                "bbox": list(bounding_box),
                "mask_area": int(mask_data.get("area", 0)),
                "source": "sam2",
                "predicted_iou": float(mask_data["predicted_iou"]) if "predicted_iou" in mask_data else None,
                "stability_score": float(mask_data["stability_score"]) if "stability_score" in mask_data else None,
            })
        return filtered_masks

sam_model_handler = SAMModelHandler(SAM_CONFIG_PATH, SAM_CHECKPOINT_PATH)

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "base-uri 'self'; "
        "frame-ancestors 'self'"
    )
    return response


def _request_api_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return request.headers.get("X-API-Token", "").strip()


@app.before_request
def require_api_token():
    if not API_AUTH_TOKEN:
        return None
    if request.method == "OPTIONS":
        return None
    if not request.path.startswith("/api/"):
        return None
    if request.path == "/api/auth/status":
        return None

    supplied_token = _request_api_token()
    if supplied_token and hmac.compare_digest(supplied_token, API_AUTH_TOKEN):
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
        with Image.open(io.BytesIO(image_stream)) as source_image:
            if source_image.format not in ALLOWED_PIL_IMAGE_FORMATS:
                allowed = ", ".join(sorted(ALLOWED_PIL_IMAGE_FORMATS))
                raise ValueError(f"image format must be one of: {allowed}")
            _validate_decoded_image_size(source_image.width, source_image.height, context="image")
            image = source_image.convert("RGB")
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
            sam_device = _normalize_sam_device(data.get("sam_device"))
            if sam_device == "cuda" and not torch.cuda.is_available():
                return jsonify({"error": "CUDA was requested for SAM2, but CUDA is not available."}), 400
            device_changed = sam_device != _normalize_sam_device(next_settings.get("sam_device"))
            next_settings["sam_device"] = sam_device
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    if "sam_settings" in data:
        try:
            sam_settings = _normalize_sam_settings(data.get("sam_settings"))
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
        sam_settings = _normalize_sam_settings(raw_sam_settings or _project_settings().get("sam_settings"))
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
