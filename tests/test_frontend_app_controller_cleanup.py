from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


REMOVED_CONTROLLER_LEFTOVERS = [
    "const apiClient = window.SAM2ApiClient;",
    "OVERLAY_COLORS,",
    "BOX_HANDLE_SCREEN_SIZE,",
    "function screenUnits(",
    "function strokeCandidateShape(",
    "function drawCandidateOverlay(",
    "function drawAnnotationOverlay(",
    "function drawAnnotationLabel(",
    "function strokeScreenRect(",
    "function drawAnnotationHandles(",
]


def test_main_script_has_no_transitional_controller_leftovers():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const apiWorkflows = window.SAM2ApiWorkflows;" in script_js
    assert "const canvasRenderer = window.SAM2CanvasRenderer;" in script_js
    assert "canvasRenderer.drawScene(" in script_js

    for leftover in REMOVED_CONTROLLER_LEFTOVERS:
        assert leftover not in script_js
