import base64
import io

from PIL import Image


def png_bytes(size=(4, 3), color=(10, 20, 30)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def test_app_import_skips_sam_model_load(app_module):
    assert app_module.SKIP_SAM_MODEL_LOAD is True
    status = app_module.sam_model_handler.status()
    assert status["model_load_skipped"] is True
    assert status["ready"] is False


def test_auth_status_and_token_gate(client, app_module, monkeypatch):
    assert client.get("/api/auth/status").get_json() == {"auth_required": False}

    monkeypatch.setattr(app_module, "API_AUTH_TOKEN", "secret-token")
    assert client.get("/api/auth/status").get_json() == {"auth_required": True}

    blocked = client.get("/api/project/settings")
    assert blocked.status_code == 401
    assert blocked.get_json()["auth_required"] is True

    allowed = client.get("/api/project/settings", headers={"Authorization": "Bearer secret-token"})
    assert allowed.status_code == 200


def test_load_image_rejects_bad_extension_and_accepts_png(client):
    bad = client.post(
        "/api/load_image",
        data={"image": (io.BytesIO(b"not an image"), "sample.txt")},
        content_type="multipart/form-data",
    )
    assert bad.status_code == 400
    assert "unsupported image extension" in bad.get_json()["error"]

    good = client.post(
        "/api/load_image",
        data={"image": (png_bytes(), "sample.png")},
        content_type="multipart/form-data",
    )
    assert good.status_code == 200
    image_url = good.get_json()["image_url"]
    assert image_url.startswith("data:image/png;base64,")
    base64.b64decode(image_url.split(",", 1)[1])


def test_annotation_save_and_load_round_trip_csv(client):
    payload = {
        "image_name": "cells.png",
        "image_width": 100,
        "image_height": 80,
        "format": "csv_rich",
        "classes": [{"name": "nucleus", "color": "#39d353", "hotkey": "n"}],
        "annotations": [
            {
                "id": 1,
                "bbox": [10.2, 5.8, 20, 15],
                "class": "nucleus",
                "type": "manual",
                "contour": [[10, 6], [30, 6], [30, 21]],
                "mask_area": 220,
                "source": "test",
                "predicted_iou": 0.95,
                "stability_score": 0.96,
            }
        ],
    }
    saved = client.post("/api/annotations/save", json=payload)
    assert saved.status_code == 200
    assert saved.get_json()["count"] == 1

    loaded = client.get(
        "/api/annotations/load",
        query_string={"image_name": "cells.png", "format": "csv_rich", "image_width": 100, "image_height": 80},
    )
    assert loaded.status_code == 200
    data = loaded.get_json()
    assert data["exists"] is True
    assert data["annotations"][0]["class"] == "nucleus"
    assert data["annotations"][0]["bbox"] == [10.0, 6.0, 20.0, 15.0]
    assert data["classes"][0]["name"] == "nucleus"


def test_project_settings_validation_and_persistence(client):
    invalid = client.post("/api/project/settings", json={"annotation_output_dir": "../outside"})
    assert invalid.status_code == 400

    response = client.post(
        "/api/project/settings",
        json={
            "annotation_output_dir": "annotations/reviewed",
            "annotation_format": "voc",
            "sam_device": "cpu",
            "sam_settings": {
                "preset": "custom",
                "params": {"points_per_side": 999, "min_overall_area": 1, "max_overall_area": 10},
            },
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["annotation_output_dir"] == "annotations/reviewed"
    assert data["annotation_format"] == "voc"
    assert data["sam_device"]["mode"] == "cpu"
    assert data["sam_settings"]["params"]["points_per_side"] == 128
