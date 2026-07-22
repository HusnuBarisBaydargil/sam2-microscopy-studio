import json
import os
import uuid

from annotation_io import _normalize_classes
from atomic_io import atomic_write_file, read_with_backup, recoverable_file_exists
from project_config import normalize_project_settings

PROJECT_MANIFEST_SCHEMA_VERSION = 1
PROJECT_TASK_BOUNDING_BOX = "bounding_box"
SUPPORTED_PROJECT_TASKS = {PROJECT_TASK_BOUNDING_BOX}


def project_manifest_path(project_root, project_manifest_file):
    if os.path.isabs(project_manifest_file):
        return os.path.abspath(project_manifest_file)
    return os.path.join(project_root, project_manifest_file)


def _valid_project_id(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def _valid_class_id(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _next_available_class_id(used_ids, next_class_id):
    candidate = max(1, next_class_id)
    while candidate in used_ids:
        candidate += 1
    return candidate


def normalize_manifest_classes(raw_classes, next_class_id=1):
    normalized = _normalize_classes(raw_classes)
    used_ids = set()
    next_id = _valid_class_id(next_class_id) or 1
    classes = []

    for class_info in normalized:
        class_id = _valid_class_id(class_info.get("id"))
        if class_id is None or class_id in used_ids:
            class_id = _next_available_class_id(used_ids, next_id)
        used_ids.add(class_id)
        next_id = max(next_id, class_id + 1)
        classes.append({"id": class_id, **{key: value for key, value in class_info.items() if key != "id"}})

    return classes, next_id


def normalize_project_manifest(
    raw_manifest,
    *,
    project_root,
    default_annotation_output_dir,
    allow_absolute_annotation_dir,
    allow_missing_identity=False,
):
    raw_manifest = raw_manifest if isinstance(raw_manifest, dict) else {}
    schema_version = raw_manifest.get("schema_version")
    if schema_version is None and allow_missing_identity:
        schema_version = PROJECT_MANIFEST_SCHEMA_VERSION
    if schema_version != PROJECT_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported project manifest schema_version {schema_version!r}; "
            f"expected {PROJECT_MANIFEST_SCHEMA_VERSION}"
        )

    project_id = _valid_project_id(raw_manifest.get("project_id"))
    if project_id is None:
        if not allow_missing_identity:
            raise ValueError("project manifest project_id must be a valid UUID")
        project_id = str(uuid.uuid4())

    task_type = str(raw_manifest.get("task_type") or PROJECT_TASK_BOUNDING_BOX).strip()
    if task_type not in SUPPORTED_PROJECT_TASKS:
        raise ValueError(f"Unsupported project task_type: {task_type}")

    settings = normalize_project_settings(
        raw_manifest.get("settings"),
        project_root=project_root,
        default_annotation_output_dir=default_annotation_output_dir,
        allow_absolute_annotation_dir=allow_absolute_annotation_dir,
    )
    classes, next_class_id = normalize_manifest_classes(
        raw_manifest.get("classes"),
        raw_manifest.get("next_class_id", 1),
    )
    return {
        "schema_version": PROJECT_MANIFEST_SCHEMA_VERSION,
        "project_id": project_id,
        "task_type": task_type,
        "next_class_id": next_class_id,
        "settings": settings,
        "classes": classes,
    }


def create_project_manifest(
    settings=None,
    classes=None,
    *,
    project_root,
    default_annotation_output_dir,
    allow_absolute_annotation_dir,
):
    return normalize_project_manifest(
        {
            "schema_version": PROJECT_MANIFEST_SCHEMA_VERSION,
            "project_id": str(uuid.uuid4()),
            "task_type": PROJECT_TASK_BOUNDING_BOX,
            "settings": settings or {},
            "classes": classes or [],
        },
        project_root=project_root,
        default_annotation_output_dir=default_annotation_output_dir,
        allow_absolute_annotation_dir=allow_absolute_annotation_dir,
    )


def _read_project_manifest_json(path):
    with open(path, "r", encoding="utf-8") as file:
        manifest = json.load(file)
    if not isinstance(manifest, dict):
        raise ValueError("project manifest must be a JSON object")
    if manifest.get("schema_version") != PROJECT_MANIFEST_SCHEMA_VERSION:
        raise ValueError("project manifest has an unsupported schema_version")
    if _valid_project_id(manifest.get("project_id")) is None:
        raise ValueError("project manifest project_id must be a valid UUID")
    if not isinstance(manifest.get("settings"), dict):
        raise ValueError("project manifest must contain a settings object")
    if not isinstance(manifest.get("classes"), list):
        raise ValueError("project manifest must contain a classes list")
    return manifest


def save_project_manifest(
    manifest,
    manifest_path,
    *,
    project_root,
    default_annotation_output_dir,
    allow_absolute_annotation_dir,
):
    normalized = normalize_project_manifest(
        manifest,
        project_root=project_root,
        default_annotation_output_dir=default_annotation_output_dir,
        allow_absolute_annotation_dir=allow_absolute_annotation_dir,
    )

    def write_manifest(path):
        with open(path, "w", encoding="utf-8") as file:
            json.dump(normalized, file, indent=2)

    atomic_write_file(manifest_path, write_manifest, validator=_read_project_manifest_json)
    return normalized


def load_or_create_project_manifest(
    manifest_path,
    *,
    legacy_settings=None,
    legacy_classes=None,
    project_root,
    default_annotation_output_dir,
    allow_absolute_annotation_dir,
):
    if recoverable_file_exists(manifest_path):
        raw_manifest = read_with_backup(manifest_path, _read_project_manifest_json)
        normalized = normalize_project_manifest(
            raw_manifest,
            project_root=project_root,
            default_annotation_output_dir=default_annotation_output_dir,
            allow_absolute_annotation_dir=allow_absolute_annotation_dir,
        )
        if normalized != raw_manifest:
            normalized = save_project_manifest(
                normalized,
                manifest_path,
                project_root=project_root,
                default_annotation_output_dir=default_annotation_output_dir,
                allow_absolute_annotation_dir=allow_absolute_annotation_dir,
            )
        return normalized

    manifest = create_project_manifest(
        legacy_settings,
        legacy_classes,
        project_root=project_root,
        default_annotation_output_dir=default_annotation_output_dir,
        allow_absolute_annotation_dir=allow_absolute_annotation_dir,
    )
    return save_project_manifest(
        manifest,
        manifest_path,
        project_root=project_root,
        default_annotation_output_dir=default_annotation_output_dir,
        allow_absolute_annotation_dir=allow_absolute_annotation_dir,
    )


def update_manifest_settings(
    manifest,
    settings,
    *,
    project_root,
    default_annotation_output_dir,
    allow_absolute_annotation_dir,
):
    return normalize_project_manifest(
        {**manifest, "settings": settings},
        project_root=project_root,
        default_annotation_output_dir=default_annotation_output_dir,
        allow_absolute_annotation_dir=allow_absolute_annotation_dir,
    )


def update_manifest_classes(manifest, raw_classes):
    current_classes = manifest.get("classes", [])
    current_by_id = {class_info["id"]: class_info for class_info in current_classes}
    current_by_name = {class_info["name"]: class_info for class_info in current_classes}
    normalized_input = _normalize_classes(raw_classes)
    used_ids = set()
    next_class_id = _valid_class_id(manifest.get("next_class_id")) or 1
    classes = []

    for class_info in normalized_input:
        requested_id = _valid_class_id(class_info.get("id"))
        existing = current_by_id.get(requested_id) or current_by_name.get(class_info["name"])
        if existing and existing["id"] not in used_ids:
            class_id = existing["id"]
        else:
            class_id = _next_available_class_id(used_ids | set(current_by_id), next_class_id)
            next_class_id = class_id + 1
        used_ids.add(class_id)
        next_class_id = max(next_class_id, class_id + 1)
        classes.append({"id": class_id, **{key: value for key, value in class_info.items() if key != "id"}})

    return {
        **manifest,
        "next_class_id": next_class_id,
        "classes": classes,
    }
