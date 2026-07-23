import json
import uuid

import pytest

from project_manifest import (
    PROJECT_MANIFEST_SCHEMA_VERSION,
    load_or_create_project_manifest,
    save_project_manifest,
    update_manifest_classes,
)


def manifest_options(tmp_path):
    return {
        "project_root": str(tmp_path),
        "default_annotation_output_dir": "annotations",
        "allow_absolute_annotation_dir": False,
    }


def test_manifest_migrates_legacy_state_and_preserves_identity(tmp_path):
    path = tmp_path / "project_manifest.json"
    options = manifest_options(tmp_path)
    manifest = load_or_create_project_manifest(
        path,
        legacy_settings={"annotation_output_dir": "labels", "annotation_format": "coco"},
        legacy_classes=[
            {"name": "nucleus", "color": "#39d353", "hotkey": "n"},
            {"name": "membrane", "color": "#58a6ff", "hotkey": "m"},
        ],
        **options,
    )

    assert manifest["schema_version"] == PROJECT_MANIFEST_SCHEMA_VERSION
    assert str(uuid.UUID(manifest["project_id"])) == manifest["project_id"]
    assert manifest["task_type"] == "bounding_box"
    assert manifest["settings"]["annotation_output_dir"] == "labels"
    assert manifest["settings"]["annotation_format"] == "coco"
    assert [class_info["id"] for class_info in manifest["classes"]] == [1, 2]
    assert manifest["next_class_id"] == 3

    reloaded = load_or_create_project_manifest(path, **options)
    assert reloaded == manifest


def test_class_ids_survive_reorder_and_rename_and_are_never_reused(tmp_path):
    path = tmp_path / "project_manifest.json"
    options = manifest_options(tmp_path)
    manifest = load_or_create_project_manifest(
        path,
        legacy_classes=[{"name": "first"}, {"name": "second"}],
        **options,
    )
    first_id, second_id = [class_info["id"] for class_info in manifest["classes"]]

    manifest = update_manifest_classes(
        manifest,
        [
            {"id": second_id, "name": "renamed second", "color": "#58a6ff"},
            {"id": first_id, "name": "first", "color": "#39d353"},
        ],
    )
    assert [(item["id"], item["name"]) for item in manifest["classes"]] == [
        (second_id, "renamed second"),
        (first_id, "first"),
    ]

    manifest = update_manifest_classes(manifest, [{"id": first_id, "name": "first"}])
    manifest = update_manifest_classes(
        manifest,
        [{"id": first_id, "name": "first"}, {"id": second_id, "name": "third"}],
    )
    assert manifest["classes"][1]["id"] > second_id


def test_manifest_uses_valid_backup_and_rejects_future_schema(tmp_path):
    path = tmp_path / "project_manifest.json"
    options = manifest_options(tmp_path)
    first = load_or_create_project_manifest(path, legacy_classes=[{"name": "first"}], **options)
    second = save_project_manifest(
        update_manifest_classes(first, [{"id": 1, "name": "second"}]),
        path,
        **options,
    )
    assert second["classes"][0]["id"] == 1

    path.write_text("{", encoding="utf-8")
    recovered = load_or_create_project_manifest(path, **options)
    assert recovered == first

    future = {**recovered, "schema_version": PROJECT_MANIFEST_SCHEMA_VERSION + 1}
    path.write_text(json.dumps(future), encoding="utf-8")
    (tmp_path / "project_manifest.json.bak").unlink(missing_ok=True)
    with pytest.raises(ValueError, match="schema_version"):
        load_or_create_project_manifest(path, **options)
