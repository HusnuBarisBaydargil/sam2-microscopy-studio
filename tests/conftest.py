import importlib
import os
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.fixture(scope="session")
def app_module():
    os.environ.setdefault("SKIP_SAM_MODEL_LOAD", "1")
    os.environ.setdefault("ALLOW_ABSOLUTE_ANNOTATION_DIR", "1")
    os.environ.setdefault("PROJECT_SETTINGS_FILE", os.path.abspath("pytest_project_settings.json"))
    if "app" in sys.modules:
        return sys.modules["app"]
    return importlib.import_module("app")


@pytest.fixture()
def client(app_module, tmp_path, monkeypatch):
    settings_path = tmp_path / "project_settings.json"
    annotation_dir = tmp_path / "annotations"
    monkeypatch.setattr(app_module, "PROJECT_SETTINGS_FILE", str(settings_path))
    monkeypatch.setattr(app_module, "DEFAULT_ANNOTATION_OUTPUT_DIR", str(annotation_dir))
    monkeypatch.setattr(app_module, "PROJECT_SETTINGS", None)
    monkeypatch.setattr(app_module, "API_AUTH_TOKEN", "")
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()
