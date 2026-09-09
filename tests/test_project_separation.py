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


def test_fresh_start_archives_classes_and_leaves_annotations_untouched(client, app_module):
    client.post("/api/classes", json={"classes": [{"name": "Saved label"}]})
    previous = identity(client)
    output = Path(app_module._annotation_dir())
    output.mkdir(parents=True, exist_ok=True)
    annotation = output / "preserved.csv"
    annotation.write_bytes(b"existing annotations")
    fresh = app_module._start_fresh_project()
    assert fresh["classes"] == []
    assert fresh["project_id"] != previous["project_id"]
    assert fresh["settings"]["annotation_output_dir"] != previous["settings"]["annotation_output_dir"]
    assert annotation.read_bytes() == b"existing annotations"
    # Browser refresh/API reads must not create yet another project.
    assert identity(client) == fresh
    assert identity(client) == fresh
    restored = client.post("/api/project/projects", headers=header(fresh), json={
        "action": "open", "project_id": previous["project_id"],
    })
    assert restored.status_code == 200
    assert restored.get_json() == previous


def test_fresh_start_archive_failure_keeps_active_project(client, app_module, monkeypatch):
    previous = identity(client)
    def fail(*args, **kwargs):
        raise OSError("simulated archive failure")
    monkeypatch.setattr(app_module, "save_project_manifest", fail)
    import pytest
    with pytest.raises(OSError, match="simulated archive failure"):
        app_module._start_fresh_project()
    assert identity(client) == previous
