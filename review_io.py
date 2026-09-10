"""Conservative, format-independent persistence of explicit image review decisions."""

import hashlib
import json
import math

from atomic_io import atomic_write_file

REVIEW_STATUSES = {"unreviewed", "in_progress", "reviewed", "confirmed_empty"}
COMPLETED_REVIEW_STATUSES = {"reviewed", "confirmed_empty"}


def default_review_status(annotations):
    return "in_progress" if annotations else "unreviewed"


def validate_review_status(status, annotations, image_identity, image_size):
    if status is None:
        return default_review_status(annotations)
    if not isinstance(status, str) or status not in REVIEW_STATUSES:
        raise ValueError("Invalid review_status")
    if status == "reviewed" and not annotations:
        raise ValueError("Reviewed images must contain annotations; use confirmed_empty for an empty image")
    if status == "confirmed_empty" and annotations:
        raise ValueError("Confirmed empty images cannot contain annotations")
    if status in COMPLETED_REVIEW_STATUSES:
        if not isinstance(image_identity, str) or not image_identity.strip():
            raise ValueError("image_identity is required to complete review")
        if not image_size or any(
            value is None or not math.isfinite(float(value)) or float(value) <= 0
            for value in image_size
        ):
            raise ValueError("Positive image dimensions are required to complete review")
    return status


def _context(project_id, image_identity, image_size, classes):
    return {
        "project_id": project_id,
        "image_identity_sha256": hashlib.sha256(image_identity.encode("utf-8")).hexdigest()
        if isinstance(image_identity, str) else None,
        "image_size": [float(value) if value is not None else None for value in (image_size or (None, None))],
        "classes": sorted(
            [{"id": item.get("id"), "name": item.get("name")} for item in classes],
            key=lambda item: (str(item["id"]), str(item["name"])),
        ),
    }


def _file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path, payload):
    def writer(temporary_path):
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, allow_nan=False)

    # Review decisions must never recover from an older backup.
    atomic_write_file(f"{path}.review.json", writer, keep_backup=False)


def invalidate_review(path):
    _write(path, {"schema_version": 1, "review_status": "unreviewed"})


def save_review(path, status, *, project_id, image_identity, image_size, classes):
    _write(path, {
        "schema_version": 1,
        "review_status": status,
        "annotation_sha256": _file_hash(path),
        **_context(project_id, image_identity, image_size, classes),
    })


def load_review(path, annotations, *, project_id, image_identity, image_size, classes):
    fallback = default_review_status(annotations)
    try:
        with open(f"{path}.review.json", encoding="utf-8") as file:
            stored = json.load(file)
        if stored.get("schema_version") != 1 or stored.get("annotation_sha256") != _file_hash(path):
            return fallback
        context = _context(project_id, image_identity, image_size, classes)
        if any(stored.get(key) != value for key, value in context.items()):
            return fallback
        return validate_review_status(stored.get("review_status"), annotations, image_identity, image_size)
    except (OSError, ValueError, TypeError, AttributeError, OverflowError):
        return fallback
