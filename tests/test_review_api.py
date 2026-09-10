import pytest


def _payload(status="reviewed", annotations=None, annotation_format="csv"):
    return {
        "image_name": "cell.bmp", "image_identity": "cell.bmp:123:456", "image_width": 100,
        "image_height": 80, "format": annotation_format, "review_status": status,
        "classes": [{"id": 1, "name": "cell", "color": "#ff0000"}],
        "annotations": annotations if annotations is not None else [{"bbox": [1, 2, 20, 30], "label": "cell"}],
    }


@pytest.mark.parametrize("annotation_format", ["csv", "csv_rich", "coco", "yolo", "voc"])
@pytest.mark.parametrize("status", ["reviewed", "confirmed_empty"])
def test_save_and_reload_review(client, annotation_format, status):
    payload = _payload(status, [] if status == "confirmed_empty" else None, annotation_format)
    saved = client.post("/api/annotations/save", json=payload)
    assert saved.status_code == 200, saved.json
    assert saved.json["review_status"] == status
    loaded = client.get("/api/annotations/load", query_string={
        key: payload[key] for key in ["image_name", "image_identity", "image_width", "image_height", "format"]
    })
    assert loaded.status_code == 200, loaded.json
    assert loaded.json["review_status"] == status
    bulk = client.post("/api/annotations/bulk_load", json={"format": annotation_format, "images": [{
        "id": "image", "name": payload["image_name"], "image_identity": payload["image_identity"],
        "width": 100, "height": 80,
    }]})
    assert bulk.json["results"][0]["review_status"] == status


def test_legacy_save_and_identity_change_require_review(client):
    payload = _payload()
    assert client.post("/api/annotations/save", json=payload).status_code == 200
    query = {"image_name": "cell.bmp", "image_width": 100, "image_height": 80, "image_identity": "new image"}
    assert client.get("/api/annotations/load", query_string=query).json["review_status"] == "in_progress"
    payload.pop("review_status")
    assert client.post("/api/annotations/save", json=payload).json["review_status"] == "in_progress"


@pytest.mark.parametrize("change", [
    {"annotations": []}, {"image_identity": None}, {"image_width": None},
    {"review_status": "confirmed_empty"}, {"review_status": "bogus"},
])
def test_invalid_review_save_rejected(client, change):
    payload = {**_payload(), **change}
    assert client.post("/api/annotations/save", json=payload).status_code == 400


def test_failed_overwrite_cannot_retain_completed_review(client, app_module, monkeypatch):
    payload = _payload()
    assert client.post("/api/annotations/save", json=payload).status_code == 200

    def fail(*args, **kwargs):
        raise OSError("simulated write failure")

    monkeypatch.setattr(app_module, "_write_annotation_file", fail)
    assert client.post("/api/annotations/save", json=payload).status_code == 500
    loaded = client.get("/api/annotations/load", query_string={
        key: payload[key] for key in ["image_name", "image_identity", "image_width", "image_height", "format"]
    })
    assert loaded.json["review_status"] == "in_progress"
