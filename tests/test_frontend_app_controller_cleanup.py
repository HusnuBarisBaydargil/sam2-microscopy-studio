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


def test_manual_choice_class_hotkeys_are_checked_before_manual_mode_return():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    class_match_index = script_js.index(
        "const classMatch = appState.classes.find(cls => cls.hotkey === event.key.toLowerCase());"
    )
    manual_choice_index = script_js.index(
        "if (appState.isAwaitingChoice && appState.choiceInfo && classMatch) {"
    )
    finalize_index = script_js.index("finalizeAnnotation(classMatch.name);")
    manual_mode_return_index = script_js.index("if (appState.isManualMode) return;")
    process_selection_index = script_js.index("processSelection(classMatch.name);")

    assert class_match_index < manual_choice_index
    assert manual_choice_index < finalize_index
    assert finalize_index < manual_mode_return_index
    assert manual_mode_return_index < process_selection_index
