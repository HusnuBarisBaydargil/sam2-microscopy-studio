import json
import uuid

import pytest

from project_manifest import (
    PROJECT_MANIFEST_SCHEMA_VERSION,
    create_project_manifest,
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


def test_segmentation_project_round_trip_and_detection_default(tmp_path):
    options = manifest_options(tmp_path)
    assert create_project_manifest(**options)["task_type"] == "bounding_box"
    manifest = create_project_manifest(task_type="instance_segmentation", **options)
    assert manifest["classes"] == []
    path = tmp_path / "segmentation.json"
    save_project_manifest(manifest, path, **options)
    assert load_or_create_project_manifest(path, **options) == manifest
    with pytest.raises(ValueError, match="task_type"):
        create_project_manifest(task_type="unknown", **options)


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


@pytest.mark.parametrize('task_type', ['bounding_box', 'instance_segmentation'])
def test_retired_classes_with_reused_names_survive_save_and_reload(tmp_path, task_type):
    options = manifest_options(tmp_path)
    path = tmp_path / 'project_manifest.json'
    manifest = create_project_manifest(classes=[
        {'name': 'A', 'color': '#39d353', 'hotkey': 'a'},
        {'name': 'B', 'color': '#58a6ff', 'hotkey': 'b'},
    ], task_type=task_type, **options)
    first, second = manifest['classes']
    manifest = save_project_manifest(update_manifest_classes(manifest, [second]), path, **options)
    renamed = {**second, 'name': 'A'}
    manifest = save_project_manifest(update_manifest_classes(manifest, [renamed]), path, **options)
    manifest = save_project_manifest(update_manifest_classes(manifest, []), path, **options)
    expected = [first, renamed]
    assert manifest['classes'] == []
    assert manifest['retired_classes'] == expected
    assert load_or_create_project_manifest(path, **options)['retired_classes'] == expected
    assert json.loads(path.read_text(encoding='utf-8'))['retired_classes'] == expected
    # A subsequent class still receives a fresh ID; neither archived ID is recycled.
    added = save_project_manifest(update_manifest_classes(manifest, [{'name': 'C'}]), path, **options)
    assert added['classes'][0]['id'] > max(first['id'], second['id'])
    assert added['retired_classes'] == expected


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


def test_new_project_has_no_sample_classes_and_saved_empty_list_stays_empty(tmp_path):
    path = tmp_path / "project_manifest.json"
    options = manifest_options(tmp_path)
    manifest = load_or_create_project_manifest(path, **options)
    assert manifest["classes"] == []
    assert manifest["next_class_id"] == 1
    reloaded = load_or_create_project_manifest(
        path, legacy_classes=[{"name": "old label"}], **options,
    )
    assert reloaded["classes"] == []
    assert reloaded["project_id"] == manifest["project_id"]
