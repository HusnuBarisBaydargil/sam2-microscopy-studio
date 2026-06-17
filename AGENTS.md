# Repository Agent Instructions

## Scope
These instructions apply to the entire repository.

## Project overview
- `app.py` contains the Flask API, SAM2 model wiring, preprocessing, annotation I/O, project settings, and authentication checks.
- `static/` contains the browser UI.
- `sam2/` is vendored upstream SAM2 code. Do not edit it unless the user explicitly asks or a repository bug cannot be fixed elsewhere.
- Runtime files such as `annotations/`, `project_settings.json`, and model checkpoints are local artifacts and should not be committed.

## Environment and tests
- Set `SKIP_SAM_MODEL_LOAD=1` for tests and API-only development to avoid loading SAM2 checkpoints.
- Prefer a temp `PROJECT_SETTINGS_FILE` and temp annotation directory in tests so local runtime settings are not modified.
- Run `pytest` for focused API and annotation behavior checks.
- Run `ruff check .` when available. Avoid broad formatting churn in vendored `sam2/` unless specifically requested.

## Coding guidance
- Keep endpoint validation explicit and return JSON errors with appropriate HTTP status codes.
- Do not put `try`/`except` blocks around imports.
- Keep annotation format changes covered for save/load when possible.
- Avoid committing generated caches, local notebooks, annotations, checkpoints, and local settings files.
