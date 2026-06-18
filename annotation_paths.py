import hashlib
import hmac
import json
import os

from werkzeug.utils import secure_filename

from annotation_io import (
    _count_annotation_file,
    _normalize_annotation_format,
    _normalize_classes,
    _parse_float,
)


def safe_image_stem(image_name):
    safe_name = secure_filename(os.path.basename(image_name or "image"))
    stem, _ = os.path.splitext(safe_name)
    return stem or "image"


def safe_path_stem(image_path):
    normalized_path = str(image_path or "").replace("\\", "/")
    parts = [secure_filename(part) for part in normalized_path.split("/") if part]
    if not parts:
        return safe_image_stem(image_path)

    stem_parts = []
    for index, part in enumerate(parts):
        stem = os.path.splitext(part)[0] if index == len(parts) - 1 else part
        if stem:
            stem_parts.append(stem)

    return "__".join(stem_parts) or safe_image_stem(image_path)


def anonymized_image_stem(image_name, image_path=None, phi_hash_salt=""):
    identity = str(image_path or image_name or "image").replace("\\", "/").strip().lower()
    key = phi_hash_salt.encode("utf-8")
    digest_source = identity.encode("utf-8")
    if key:
        digest = hmac.new(key, digest_source, hashlib.sha256).hexdigest()
    else:
        digest = hashlib.sha256(digest_source).hexdigest()
    return f"image_{digest[:16]}"


def public_image_name(
    image_name,
    image_path=None,
    *,
    phi_safe_mode=False,
    phi_hash_salt="",
    allowed_image_extensions=None,
):
    if not phi_safe_mode:
        return image_name
    allowed_image_extensions = allowed_image_extensions or set()
    extension = os.path.splitext(secure_filename(os.path.basename(image_name or "")))[1].lower()
    if extension not in allowed_image_extensions:
        extension = ""
    return f"{anonymized_image_stem(image_name, image_path, phi_hash_salt)}{extension}"


def public_annotation_path(path, *, phi_safe_mode=False, display_path=str):
    if not phi_safe_mode:
        return display_path(path)
    return os.path.basename(path).replace(os.sep, "/")


def annotation_file_names(
    image_name,
    image_path=None,
    match_mode="basename",
    annotation_format="csv",
    *,
    phi_safe_mode=False,
    phi_hash_salt="",
):
    annotation_format = _normalize_annotation_format(annotation_format)
    if phi_safe_mode:
        stem = anonymized_image_stem(
            image_name,
            image_path if match_mode == "path" else image_name,
            phi_hash_salt,
        )
    elif match_mode == "path" and image_path:
        stem = safe_path_stem(image_path)
    else:
        stem = safe_image_stem(image_name)

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


def annotation_file_name(
    image_name,
    image_path=None,
    match_mode="basename",
    annotation_format="csv",
    *,
    phi_safe_mode=False,
    phi_hash_salt="",
):
    return annotation_file_names(
        image_name,
        image_path,
        match_mode,
        annotation_format,
        phi_safe_mode=phi_safe_mode,
        phi_hash_salt=phi_hash_salt,
    )[0]


def annotation_path_for_image(
    image_name,
    image_path=None,
    match_mode="basename",
    annotation_format="csv",
    *,
    annotation_dir,
    phi_safe_mode=False,
    phi_hash_salt="",
):
    file_name = annotation_file_name(
        image_name,
        image_path,
        match_mode,
        annotation_format,
        phi_safe_mode=phi_safe_mode,
        phi_hash_salt=phi_hash_salt,
    )
    return os.path.join(annotation_dir, file_name)


def annotation_candidate_paths(
    image_name,
    image_path=None,
    annotation_format="csv",
    *,
    annotation_dir,
    phi_safe_mode=False,
    phi_hash_salt="",
):
    candidates = []
    if image_path and str(image_path) != str(image_name):
        for file_name in annotation_file_names(
            image_name,
            image_path,
            "path",
            annotation_format,
            phi_safe_mode=phi_safe_mode,
            phi_hash_salt=phi_hash_salt,
        ):
            candidates.append({
                "match_mode": "path",
                "format": annotation_format,
                "path": os.path.join(annotation_dir, file_name),
            })
    for file_name in annotation_file_names(
        image_name,
        image_path,
        "basename",
        annotation_format,
        phi_safe_mode=phi_safe_mode,
        phi_hash_salt=phi_hash_salt,
    ):
        candidates.append({
            "match_mode": "basename",
            "format": annotation_format,
            "path": os.path.join(annotation_dir, file_name),
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


def project_classes_path(annotation_dir, project_classes_file):
    return os.path.join(annotation_dir, project_classes_file)


def image_info_from_payload(raw_image):
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


def duplicate_stems_for_images(images):
    counts = {}
    for image in images:
        stem = safe_image_stem(image.get("name"))
        counts[stem] = counts.get(stem, 0) + 1
    return {stem for stem, count in counts.items() if count > 1}


def count_annotations_safe(path, annotation_format="csv"):
    try:
        return _count_annotation_file(path, annotation_format)
    except Exception:
        return None


def first_candidate(candidates, match_mode, must_exist=False):
    for candidate in candidates:
        if candidate["match_mode"] != match_mode:
            continue
        if must_exist and not os.path.exists(candidate["path"]):
            continue
        return candidate
    return None


def resolve_annotation_match(
    image_info,
    duplicate_stems=None,
    annotation_format=None,
    *,
    default_annotation_format,
    annotation_dir,
    phi_safe_mode=False,
    phi_hash_salt="",
    allowed_image_extensions=None,
    display_path=str,
):
    annotation_format = _normalize_annotation_format(annotation_format or default_annotation_format)
    duplicate_stems = duplicate_stems or set()
    image_name = image_info.get("name", "")
    image_path = image_info.get("display_path") or image_name
    image_stem = safe_image_stem(image_name)
    is_duplicate_name = image_stem in duplicate_stems
    candidates = annotation_candidate_paths(
        image_name,
        image_path,
        annotation_format,
        annotation_dir=annotation_dir,
        phi_safe_mode=phi_safe_mode,
        phi_hash_salt=phi_hash_salt,
    )
    path_candidate = first_candidate(candidates, "path")
    base_candidate = first_candidate(candidates, "basename")
    path_match = first_candidate(candidates, "path", must_exist=True)
    base_match = first_candidate(candidates, "basename", must_exist=True)

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

    path = chosen["path"] if chosen else annotation_path_for_image(
        image_name,
        image_path,
        annotation_format=annotation_format,
        annotation_dir=annotation_dir,
        phi_safe_mode=phi_safe_mode,
        phi_hash_salt=phi_hash_salt,
    )
    public_name = public_image_name(
        image_name,
        image_path,
        phi_safe_mode=phi_safe_mode,
        phi_hash_salt=phi_hash_salt,
        allowed_image_extensions=allowed_image_extensions,
    )
    return {
        "id": image_info.get("id"),
        "name": public_name,
        "display_path": public_name,
        "format": annotation_format,
        "status": status,
        "exists": status == "matched",
        "ambiguous": status == "ambiguous",
        "match_mode": chosen["match_mode"] if chosen else "basename",
        "path": public_annotation_path(path, phi_safe_mode=phi_safe_mode, display_path=display_path),
        "annotation_count": count_annotations_safe(path, annotation_format) if status == "matched" else 0,
        "message": message,
    }


def save_project_classes(classes, classes_path):
    os.makedirs(os.path.dirname(classes_path), exist_ok=True)
    with open(classes_path, "w", encoding="utf-8") as file:
        json.dump({"classes": _normalize_classes(classes)}, file, indent=2)


def load_project_classes(classes_path):
    if not os.path.exists(classes_path):
        return []
    try:
        with open(classes_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return _normalize_classes(data.get("classes"))
    except Exception:
        return []
