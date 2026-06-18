import json
import os

from annotation_io import _normalize_annotation_format
from sam_service import (
    default_sam_settings,
    normalize_sam_device,
    normalize_sam_settings,
)


def path_within(base_path, candidate_path):
    base = os.path.normcase(os.path.abspath(base_path))
    candidate = os.path.normcase(os.path.abspath(candidate_path))
    try:
        return os.path.commonpath([base, candidate]) == base
    except ValueError:
        return False


def resolve_annotation_dir(
    configured_dir,
    project_root,
    default_annotation_output_dir,
    allow_absolute_annotation_dir,
):
    raw_dir = str(configured_dir or default_annotation_output_dir).strip()
    if not raw_dir:
        raise ValueError("annotation_output_dir cannot be empty")

    expanded_dir = os.path.expanduser(raw_dir)
    if os.path.splitdrive(expanded_dir)[0] and not os.path.isabs(expanded_dir):
        raise ValueError(
            "annotation_output_dir must be relative to the project folder or an absolute path explicitly enabled by the server"
        )
    if os.path.isabs(expanded_dir):
        if not allow_absolute_annotation_dir:
            raise ValueError(
                "Absolute annotation folders are disabled. Use a relative folder under the project root "
                "or set ALLOW_ABSOLUTE_ANNOTATION_DIR=1."
            )
        return os.path.abspath(expanded_dir)

    resolved_dir = os.path.abspath(os.path.join(project_root, expanded_dir))
    if not path_within(project_root, resolved_dir):
        raise ValueError("annotation_output_dir must stay inside the project folder")
    return resolved_dir


def normalize_annotation_output_dir(
    value,
    project_root,
    default_annotation_output_dir,
    allow_absolute_annotation_dir,
):
    raw_dir = str(value or default_annotation_output_dir).strip()
    resolve_annotation_dir(
        raw_dir,
        project_root,
        default_annotation_output_dir,
        allow_absolute_annotation_dir,
    )
    return raw_dir


def project_settings_path(project_root, project_settings_file):
    if os.path.isabs(project_settings_file):
        return os.path.abspath(project_settings_file)
    return os.path.join(project_root, project_settings_file)


def normalize_project_settings(
    raw_settings=None,
    *,
    project_root,
    default_annotation_output_dir,
    allow_absolute_annotation_dir,
):
    raw_settings = raw_settings if isinstance(raw_settings, dict) else {}
    try:
        annotation_output_dir = normalize_annotation_output_dir(
            raw_settings.get("annotation_output_dir") or default_annotation_output_dir,
            project_root,
            default_annotation_output_dir,
            allow_absolute_annotation_dir,
        )
    except ValueError:
        annotation_output_dir = "annotations"
    try:
        sam_settings = normalize_sam_settings(raw_settings.get("sam_settings"))
    except ValueError:
        sam_settings = default_sam_settings()
    try:
        annotation_format = _normalize_annotation_format(raw_settings.get("annotation_format"))
    except ValueError:
        annotation_format = "csv"
    try:
        sam_device = normalize_sam_device(raw_settings.get("sam_device"))
    except ValueError:
        sam_device = normalize_sam_device()
    return {
        "annotation_output_dir": annotation_output_dir,
        "annotation_format": annotation_format,
        "sam_device": sam_device,
        "sam_settings": {
            "preset": sam_settings["preset"],
            "params": sam_settings["params"],
        },
    }


def load_project_settings(
    settings_path,
    *,
    project_root,
    default_annotation_output_dir,
    allow_absolute_annotation_dir,
):
    if not os.path.exists(settings_path):
        return normalize_project_settings(
            project_root=project_root,
            default_annotation_output_dir=default_annotation_output_dir,
            allow_absolute_annotation_dir=allow_absolute_annotation_dir,
        )
    try:
        with open(settings_path, "r", encoding="utf-8") as file:
            return normalize_project_settings(
                json.load(file),
                project_root=project_root,
                default_annotation_output_dir=default_annotation_output_dir,
                allow_absolute_annotation_dir=allow_absolute_annotation_dir,
            )
    except Exception:
        return normalize_project_settings(
            project_root=project_root,
            default_annotation_output_dir=default_annotation_output_dir,
            allow_absolute_annotation_dir=allow_absolute_annotation_dir,
        )


def save_project_settings(
    settings,
    settings_path,
    *,
    project_root,
    default_annotation_output_dir,
    allow_absolute_annotation_dir,
):
    normalized = normalize_project_settings(
        settings,
        project_root=project_root,
        default_annotation_output_dir=default_annotation_output_dir,
        allow_absolute_annotation_dir=allow_absolute_annotation_dir,
    )
    with open(settings_path, "w", encoding="utf-8") as file:
        json.dump(normalized, file, indent=2)
    return normalized
