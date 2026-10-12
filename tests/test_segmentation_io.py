import copy
import json

import pytest

import atomic_io
from segmentation_io import (
    load_segmentation_document,
    normalize_segmentation_document,
    save_segmentation_document,
)

PROJECT_ID = "556c5503-90bf-4319-9d08-06d56e1e69cd"
CONTEXT = {"project_id": PROJECT_ID, "image_identity": "field-01", "image_size": (100, 80), "class_ids": [3, 8]}


def document():
    return {
        "schema_version": 1, "task_type": "instance_segmentation", "project_id": PROJECT_ID,
        "image": {"identity": "field-01", "width": 100, "height": 80}, "next_object_id": 12,
        "annotations": [{"id": 7, "class_id": 3, "geometry": {
            "type": "polygon", "points": [[10.25, 10], [30.25, 10], [30.25, 20], [10.25, 20]],
        }, "source": "imported", "edited": True}],
    }


def test_round_trip_preserves_vertices_ids_and_provenance_and_derives_metrics(tmp_path):
    original = document()
    untouched = copy.deepcopy(original)
    original["annotations"][0].update(bbox=[0, 0, 1, 1], area=1)
    path = tmp_path / "field.studio.json"
    saved = save_segmentation_document(path, original, **CONTEXT)
    loaded = load_segmentation_document(path, **CONTEXT)
    assert loaded == saved
    assert loaded["annotations"][0]["geometry"] == untouched["annotations"][0]["geometry"]
    assert loaded["annotations"][0]["bbox"] == [10.25, 10, 20, 10]
    assert loaded["annotations"][0]["area"] == 200
    assert loaded["annotations"][0]["source"] == "imported"
    assert loaded["annotations"][0]["edited"] is True
    assert loaded["annotations"][0]["id"] == 7
    assert loaded["annotations"][0]["class_id"] == 3
    assert loaded["next_object_id"] == 12
    assert original["annotations"][0]["area"] == 1  # No mutation of caller state.


@pytest.mark.parametrize("points", [
    [[0, 0], [10, 10]],
    [[0, 0], [10, 10], [20, 20]],
    [[0, 0], [20, 20], [0, 20], [20, 0]],
    [[0, 0], [20, 0], [10, 0], [10, 10]],
    [[0, 0], [20, 0], [20, 20], [10, 0], [0, 20]],
    [[0, 0], [10, 0], [10, 10], [0, 0]],
    [[-1, 0], [10, 0], [10, 10]],
    [[0, 0], [101, 0], [10, 10]],
    [[0, 0], [10, 0], [10, float("nan")]],
    [[0, 0], [10, 0], [10, float("inf")]],
    [[0, 0], [10, 0], [10, 10**400]],
    [[False, 0], [10, 0], [10, 10]],
    [["0", 0], [10, 0], [10, 10]],
])
def test_rejects_invalid_polygons_without_overwriting_valid_file(tmp_path, points):
    path = tmp_path / "field.studio.json"
    save_segmentation_document(path, document(), **CONTEXT)
    before = path.read_bytes()
    invalid = document()
    invalid["annotations"][0]["geometry"]["points"] = points
    with pytest.raises(ValueError):
        save_segmentation_document(path, invalid, **CONTEXT)
    assert path.read_bytes() == before


def test_concave_and_clockwise_polygons_and_image_edges_are_preserved():
    data = document()
    points = [[0, 0], [100, 0], [100, 80], [50, 40], [0, 80]]
    for ring in (points, points[::-1]):
        data["annotations"][0]["geometry"]["points"] = ring
        annotation = normalize_segmentation_document(data, **CONTEXT)["annotations"][0]
        assert annotation["geometry"]["points"] == ring
        assert annotation["area"] == 6000


@pytest.mark.parametrize("field,value", [
    ("schema_version", 2), ("schema_version", True),
    ("task_type", "bounding_box"), ("project_id", "wrong"), ("next_object_id", 7),
])
def test_rejects_wrong_document_contract(field, value):
    data = document()
    data[field] = value
    with pytest.raises(ValueError):
        normalize_segmentation_document(data, **CONTEXT)


def test_rejects_wrong_image_unknown_class_duplicate_ids_and_future_geometry():
    for mutate in (
        lambda d: d["image"].update(identity="another-image"),
        lambda d: d["image"].update(width=99),
        lambda d: d["annotations"][0].update(class_id=99),
        lambda d: d["annotations"].append(copy.deepcopy(d["annotations"][0])),
        lambda d: d["annotations"][0]["geometry"].update(type="mask"),
        lambda d: d["annotations"][0]["geometry"].update(holes=[]),
    ):
        data = document()
        mutate(data)
        with pytest.raises(ValueError):
            normalize_segmentation_document(data, **CONTEXT)


def test_empty_document_keeps_id_counter_and_needs_no_classes(tmp_path):
    data = document()
    data["annotations"] = []
    path = tmp_path / "empty.studio.json"
    save_segmentation_document(path, data, **{**CONTEXT, "class_ids": []})
    assert load_segmentation_document(path, **CONTEXT)["next_object_id"] == 12


def test_interrupted_replacement_keeps_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "field.studio.json"
    save_segmentation_document(path, document(), **CONTEXT)
    before = path.read_bytes()
    replace = atomic_io.os.replace

    def fail_final(source, destination):
        if str(destination) == str(path):
            raise OSError("simulated disk failure")
        return replace(source, destination)

    monkeypatch.setattr(atomic_io.os, "replace", fail_final)
    changed = document()
    changed["annotations"][0]["class_id"] = 8
    with pytest.raises(OSError, match="simulated"):
        save_segmentation_document(path, changed, **CONTEXT)
    assert path.read_bytes() == before


def test_corrupt_primary_recovers_valid_backup(tmp_path):
    path = tmp_path / "field.studio.json"
    first = save_segmentation_document(path, document(), **CONTEXT)
    second = document()
    second["annotations"][0]["class_id"] = 8
    save_segmentation_document(path, second, **CONTEXT)
    path.write_text("{", encoding="utf-8")
    assert load_segmentation_document(path, **CONTEXT) == first
    assert json.loads((tmp_path / "field.studio.json.bak").read_text())["annotations"][0]["class_id"] == 3


def test_duplicate_points_error_identifies_overlapping_point_numbers():
    value = document()
    points = value['annotations'][0]['geometry']['points']
    points.append(points[0].copy())
    with pytest.raises(ValueError, match='Points 1, 5 overlap at the same location'):
        normalize_segmentation_document(value, **CONTEXT)
