from pathlib import Path


def identity(client):
    data = client.get("/api/project/manifest").get_json()
    data.pop("manifest_path", None)
    return data


def header(project):
    return {"X-Project-ID": project["project_id"]}


def test_new_project_is_empty_and_reopening_restores_saved_project(client, app_module):
    old = identity(client)
    client.post("/api/classes", json={"classes": [{"name": "User label"}]})
    old = identity(client)
    output = Path(app_module._annotation_dir())
    output.mkdir(parents=True, exist_ok=True)
    saved = output / "untouched.csv"
    saved.write_bytes(b"preserve existing annotation bytes")
    result = client.post("/api/project/projects", headers=header(old), json={"action": "new", "name": "Second"})
    assert result.status_code == 200
    new = result.get_json()
    assert new["classes"] == []
    assert new["name"] == "Second"
    assert new["project_id"] != old["project_id"]
    assert new["settings"]["annotation_output_dir"] != old["settings"]["annotation_output_dir"]
    assert not (Path(app_module._annotation_dir()) / "untouched.csv").exists()
    assert saved.read_bytes() == b"preserve existing annotation bytes"
    client.post("/api/classes", headers=header(new), json={"classes": [{"name": "Second label"}]})
    reopened = client.post("/api/project/projects", headers=header(new), json={"action": "open", "project_id": old["project_id"]})
    assert reopened.status_code == 200
    assert reopened.get_json() == old
    listing = client.get("/api/project/projects", headers=header(old)).get_json()
    assert len(listing["projects"]) == 2
    again = client.post("/api/project/projects", headers=header(old), json={"action": "open", "project_id": new["project_id"]}).get_json()
    assert [c["name"] for c in again["classes"]] == ["Second label"]
    app_module.PROJECT_MANIFEST = None
    app_module.PROJECT_SETTINGS = None
    assert identity(client) == again


def test_reuse_is_explicit_and_old_tabs_cannot_write(client):
    old = identity(client)
    client.post("/api/classes", json={"classes": [{"name": "Explicit label"}]})
    new = client.post("/api/project/projects", headers=header(old), json={"action": "new", "name": "Reuse", "reuse_classes": True}).get_json()
    assert [c["name"] for c in new["classes"]] == ["Explicit label"]
    for path in ["/api/classes", "/api/project/settings", "/api/annotations/save", "/api/project/projects"]:
        assert client.post(path, headers=header(old), json={}).status_code == 409
        assert client.post(path, json={}).status_code == 409
    assert identity(client) == new


def test_chooser_creates_lists_and_reopens_segmentation_without_detection_writes(client, app_module):
    detection = identity(client)
    response = client.post("/api/project/projects", headers=header(detection), json={
        "action": "new", "name": "Cell outlines", "task_type": "instance_segmentation",
    })
    assert response.status_code == 200
    segmentation = response.get_json()
    assert segmentation["task_type"] == "instance_segmentation"
    assert segmentation["classes"] == []
    listing = client.get("/api/project/projects", headers=header(segmentation)).get_json()
    assert {p["task_type"] for p in listing["projects"]} == {"bounding_box", "instance_segmentation"}
    output = Path(app_module._annotation_dir())
    before = list(output.glob("*")) if output.exists() else []
    blocked = client.post("/api/annotations/save", headers=header(segmentation), json={
        "image_name": "field.png", "annotations": [{"bbox": [0, 0, 10, 10], "class": "cell"}],
    })
    assert blocked.status_code == 409
    assert "Detection annotation routes" in blocked.get_json()["error"]
    assert (list(output.glob("*")) if output.exists() else []) == before
    assert client.post("/api/project/projects", headers=header(segmentation), json={
        "action": "open", "project_id": detection["project_id"],
    }).get_json()["task_type"] == "bounding_box"
    assert client.post("/api/project/projects", headers=header(detection), json={
        "action": "open", "project_id": segmentation["project_id"],
    }).get_json() == segmentation


def test_chooser_rejects_unknown_task_without_switching(client):
    current = identity(client)
    for task in (None, "", "semantic", 1, []):
        result = client.post("/api/project/projects", headers=header(current), json={
            "action": "new", "name": "Invalid", "task_type": task,
        })
        assert result.status_code == 400
        assert identity(client) == current


def test_invalid_switches_and_failed_persistence_preserve_active_project(client, app_module, monkeypatch):
    old = identity(client)
    for payload in [{"action": "new", "name": " "}, {"action": "open", "project_id": "../../bad"}, {"action": "new", "name": "valid", "reuse_classes": "yes"}]:
        assert client.post("/api/project/projects", headers=header(old), json=payload).status_code == 400
        assert identity(client) == old
    def fail(*args, **kwargs):
        raise OSError("simulated disk error")
    monkeypatch.setattr(app_module, "_save_manifest", fail)
    response = client.post("/api/project/projects", headers=header(old), json={"action": "new", "name": "Failed"})
    assert response.status_code == 500
    assert identity(client) == old


def test_restart_restores_active_project_and_leaves_annotations_untouched(client, app_module):
    client.post("/api/classes", json={"classes": [{"name": "Saved label"}]})
    previous = identity(client)
    output = Path(app_module._annotation_dir())
    output.mkdir(parents=True, exist_ok=True)
    annotation = output / "preserved.csv"
    annotation.write_bytes(b"existing annotations")
    app_module.PROJECT_MANIFEST = None
    app_module.PROJECT_SETTINGS = None
    assert app_module._project_manifest() == previous
    assert annotation.read_bytes() == b"existing annotations"
    assert identity(client) == previous
    assert identity(client) == previous


def test_restart_restores_segmentation_project_settings_and_classes(client, app_module):
    current = identity(client)
    project = client.post("/api/project/projects", headers=header(current), json={
        "action": "new", "name": "Resume outlines", "task_type": "instance_segmentation",
    }).get_json()
    client.post("/api/classes", headers=header(project), json={"classes": [{"name": "Cell"}]})
    previous = identity(client)
    app_module.PROJECT_MANIFEST = None
    app_module.PROJECT_SETTINGS = None
    assert app_module._project_manifest() == previous
    assert identity(client) == previous
