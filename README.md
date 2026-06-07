# SAM2 Annotation Web App

A local Flask web application for SAM2-assisted image annotation. The app is designed for cell, microscopy, and medical-image review workflows where a user loads images, generates SAM2 candidate masks, converts selected candidates into final annotations, edits boxes, manages classes, and exports annotations in common dataset formats.

The project runs as a local browser UI backed by a Python server. SAM2 inference happens on the server; annotation review and editing happen in the browser.

## Features

- Load a single image or a browser-selected image folder.
- Generate SAM2 candidate masks with presets and expert settings.
- Review SAM candidates with contour-based hit testing.
- Convert SAM candidates to final annotations with batch apply or one-click active-class accept.
- Preserve SAM metadata including contour, mask area, source, predicted IoU, and stability score.
- Draw manual boxes, edit boxes, nudge boxes, undo geometry/class changes, and clamp boxes to image bounds.
- Manage class names, colors, and hotkeys.
- Save/load annotations on the server with duplicate filename handling.
- Import/export CSV, YOLO TXT, COCO JSON, and Pascal VOC XML.
- Apply preprocessing for display and SAM inference.
- Optional API token protection for shared/local-network deployments.
- Optional PHI-safe mode that hides image filenames and paths behind generated IDs.

## Repository Layout

```text
app.py                         Flask API, SAM2 loading, preprocessing, annotation IO
static/index.html              Browser UI
static/script.js               Frontend state, canvas interaction, API calls, import/export
static/style.css               UI styling
scripts/check_setup.py         Environment/model sanity check
tests/                         Unit, API, and static UI contract tests
requirements.txt               Runtime dependencies
requirements-dev.txt           Test/dev dependencies
project_settings.example.json  Example runtime settings shape
Dockerfile                     Optional container runtime
```

## Requirements

- Python 3.12.
- A SAM2 checkpoint at `models/sam2.1_hiera_large.pt`.
- A SAM2 config at `models/sam2.1_hiera_l.yaml`.
- CUDA-capable GPU recommended for practical SAM2 inference.

The app can start without loading SAM2 when `SKIP_SAM_MODEL_LOAD=1`, which is useful for tests and API work.

## Local Setup

Create an environment and install runtime dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Place the SAM2 model files under `models/`:

```text
models/
  sam2.1_hiera_l.yaml
  sam2.1_hiera_large.pt
```

Validate the setup:

```powershell
python scripts/check_setup.py
```

Run the app:

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Running Tests

Install dev dependencies:

```powershell
pip install -r requirements-dev.txt
```

Run tests without loading the SAM2 checkpoint:

```powershell
$env:SKIP_SAM_MODEL_LOAD = "1"
$env:ALLOW_ABSOLUTE_ANNOTATION_DIR = "1"
pytest
```

On Windows, if pytest cannot access the default temp directory, use a workspace-local temp directory:

```powershell
pytest --basetemp pytest_workspace_tmp\run -p no:cacheprovider
```

## Docker

The Docker image intentionally excludes model checkpoints and runtime annotation data. Mount those directories at runtime:

```powershell
docker build -t sam2-annotator .
docker run --rm -p 5000:5000 `
  -v ${PWD}\models:/app/models `
  -v ${PWD}\annotations:/app/annotations `
  sam2-annotator
```

Open:

```text
http://127.0.0.1:5000
```

## Configuration

Environment variables:

- `APP_HOST`: Flask bind host. Defaults to `127.0.0.1`; Docker sets `0.0.0.0`.
- `APP_PORT`: Flask port. Defaults to `5000`.
- `APP_API_TOKEN` or `API_TOKEN`: optional bearer token for `/api/*` endpoints.
- `PHI_SAFE_MODE`: set to `1` to hide image filenames, folder paths, annotation paths, and saved export image names behind generated IDs.
- `PHI_HASH_SALT`: optional secret salt for stable PHI-safe image IDs.
- `ANNOTATION_OUTPUT_DIR`: default annotation folder. Defaults to `annotations`.
- `ANNOTATION_FORMAT`: default annotation format: `csv`, `yolo`, `coco`, or `voc`.
- `PROJECT_SETTINGS_FILE`: runtime project settings file. Defaults to `project_settings.json`.
- `ALLOWED_CORS_ORIGINS`: comma-separated allowed origins.
- `MAX_UPLOAD_MB`: request size limit in MB.
- `MAX_DECODED_IMAGE_PIXELS`: decoded image pixel limit for load, preprocessing, and SAM requests. Defaults to `25000000`.
- `SAM_MAX_CONCURRENT_REQUESTS`: maximum concurrent SAM2 inference jobs. Defaults to `1`.
- `SAM_QUEUE_TIMEOUT_SECONDS`: seconds a SAM2 request can wait for an inference slot. Defaults to `5`.
- `SAM_INFERENCE_TIMEOUT_SECONDS`: seconds a SAM2 request can wait for inference to finish before timeout. Defaults to `300`.
- `MAX_ANNOTATIONS_PER_SAVE`: maximum annotations accepted in one save request.
- `MAX_CLASSES_PER_PROJECT`: maximum project classes.
- `ALLOW_ABSOLUTE_ANNOTATION_DIR`: set to `1` only if absolute annotation paths are required.
- `SKIP_SAM_MODEL_LOAD`: set to `1` for tests or API work that should not load the SAM2 checkpoint.

`project_settings.json` is local runtime state and is ignored by git. Use `project_settings.example.json` as the checked-in reference.

## Security And Privacy

The app is safe for trusted localhost use by default. For shared workstations, lab servers, or any non-localhost deployment, set an API token:

```powershell
$env:APP_API_TOKEN = "replace-with-a-long-random-token"
```

When token protection is enabled, API requests require either:

```text
Authorization: Bearer <token>
```

or:

```text
X-API-Token: <token>
```

For privacy-sensitive datasets, enable PHI-safe mode:

```powershell
$env:PHI_SAFE_MODE = "1"
$env:PHI_HASH_SALT = "replace-with-a-secret-salt"
```

In PHI-safe mode, original filenames and folder paths remain internal for matching, but the UI, API response paths, annotation filenames, and CSV/COCO/VOC image-name fields use generated image IDs.

## Annotation Formats

CSV saves one file per image as `*_annotations.csv`. CSV export neutralizes spreadsheet formulas in text fields.

YOLO saves one `.txt` file per image using normalized `class_id x_center y_center width height` rows. Class IDs follow the current project class order.

COCO saves one JSON dataset file per image with `images`, `categories`, and `annotations`. SAM contours are exported as polygon `segmentation` when present.

Pascal VOC saves one XML file per image with `object/bndbox` entries.

YOLO and Pascal VOC are box-only formats. CSV and COCO preserve SAM-derived contour and metadata fields where possible.

## Preprocessing And SAM

The browser can apply preprocessing for display. When preprocessing is active, SAM2 runs from the original uploaded image plus the selected preprocessing method and parameters. The server applies preprocessing immediately before SAM inference, avoiding a second upload of the processed PNG.

Supported preprocessing methods include CLAHE, gamma, CLAHE plus unsharp, gamma plus unsharp, and mild Retinex.

## Troubleshooting

- If SAM2 is unavailable, confirm both model files exist and run `python scripts/check_setup.py`.
- If Docker starts but SAM2 cannot run, confirm the `models` volume is mounted.
- If YOLO import fails, load the image first so the browser can provide image width and height.
- If duplicate image names are used in a folder, use path-specific saves or keep filenames unique.
- If pytest fails on Windows temp permissions, run with `--basetemp` pointed at a writable workspace folder.
