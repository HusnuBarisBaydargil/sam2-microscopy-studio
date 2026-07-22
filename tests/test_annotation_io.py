import io
import json

from annotation_io import (
    _clamp_annotations_to_image,
    _normalize_annotation_payload,
    _read_annotation_file,
    _write_annotation_coco,
    _write_annotation_file,
)


def _sam_annotation(**overrides):
    annotation = {
        "id": 1,
        "bbox": [10, 5, 40, 20],
        "class": "nucleus",
        "type": "sam_final",
        "contour": [[10, 5], [50, 5], [50, 25]],
        "mask_area": 750,
        "source": "sam2",
        "predicted_iou": 0.91,
        "stability_score": 0.87,
    }
    annotation.update(overrides)
    return annotation


def test_normalize_annotation_preserves_consistent_mask_geometry():
    normalized = _normalize_annotation_payload(_sam_annotation(), 0)

    assert normalized["contour"] == [[10.0, 5.0], [50.0, 5.0], [50.0, 25.0]]
    assert normalized["mask_area"] == 750.0


def test_normalize_annotation_discards_mask_geometry_that_does_not_match_bbox():
    normalized = _normalize_annotation_payload(_sam_annotation(bbox=[60, 5, 40, 20]), 0)

    assert "contour" not in normalized
    assert "mask_area" not in normalized
    assert normalized["source"] == "sam2"
    assert normalized["predicted_iou"] == 0.91
    assert normalized["stability_score"] == 0.87


def test_clamping_bbox_discards_mask_geometry():
    annotations, changed_count = _clamp_annotations_to_image(
        [_sam_annotation(bbox=[-5, 5, 40, 20])],
        (100, 80),
    )

    assert changed_count == 1
    assert annotations[0]["bbox"] == [0.0, 5.0, 35.0, 20.0]
    assert "contour" not in annotations[0]
    assert "mask_area" not in annotations[0]


def test_coco_writer_does_not_export_inconsistent_mask_geometry(monkeypatch):
    class OutputBuffer(io.StringIO):
        def close(self):
            pass

    output = OutputBuffer()
    monkeypatch.setattr("annotation_io.os.makedirs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: output)
    _write_annotation_coco(
        "annotations/cells.json",
        "cells.png",
        [_sam_annotation(bbox=[60, 5, 40, 20])],
        (200, 100),
        [{"name": "nucleus", "color": "#39d353", "hotkey": "n"}],
    )

    annotation = json.loads(output.getvalue())["annotations"][0]
    assert "segmentation" not in annotation
    assert "mask_area" not in annotation
    assert annotation["area"] == 800.0
    assert annotation["source"] == "sam2"


def test_yolo_and_coco_use_stable_manifest_class_ids(tmp_path):
    classes = [
        {"id": 9, "name": "nucleus", "color": "#39d353", "hotkey": "n"},
        {"id": 4, "name": "membrane", "color": "#58a6ff", "hotkey": "m"},
    ]
    annotations = [
        _sam_annotation(),
        _sam_annotation(
            id=2,
            bbox=[80, 20, 10, 10],
            contour=None,
            mask_area=None,
            **{"class": "membrane"},
        ),
    ]

    yolo_path = tmp_path / "cells.txt"
    _write_annotation_file(yolo_path, "cells.png", annotations, "yolo", (200, 100), classes)
    assert [line.split()[0] for line in yolo_path.read_text(encoding="utf-8").splitlines()] == ["8", "3"]
    loaded_yolo = _read_annotation_file(yolo_path, "yolo", "cells.png", (200, 100), classes)
    assert [annotation["class"] for annotation in loaded_yolo] == ["nucleus", "membrane"]

    coco_path = tmp_path / "cells.json"
    _write_annotation_file(coco_path, "cells.png", annotations, "coco", (200, 100), classes)
    coco = json.loads(coco_path.read_text(encoding="utf-8"))
    assert [category["id"] for category in coco["categories"]] == [9, 4]
    assert [annotation["category_id"] for annotation in coco["annotations"]] == [9, 4]
