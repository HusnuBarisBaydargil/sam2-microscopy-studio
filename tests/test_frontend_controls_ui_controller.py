import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


def test_controls_ui_controller_loads_after_class_ui_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    class_ui_tag = '<script src="static/classUiController.js"></script>'
    controls_ui_tag = '<script src="static/controlsUiController.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert class_ui_tag in index_html
    assert controls_ui_tag in index_html
    assert script_tag in index_html
    assert index_html.index(class_ui_tag) < index_html.index(controls_ui_tag)
    assert index_html.index(controls_ui_tag) < index_html.index(script_tag)


def test_main_script_delegates_control_state_updates():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const controlsUiController = window.SAM2ControlsUiController;" in script_js
    assert "controlsUiController.updateButtonStates(" in script_js

    assert "runSamBtn.disabled =" not in script_js
    assert "applyPreprocessBtn.textContent =" not in script_js
    assert "refreshMatchesBtn.textContent =" not in script_js
    assert "saveAllServerBtn.disabled =" not in script_js
    assert "classUiController.syncClassControlStates(" not in script_js


def _node_executable():
    node = shutil.which("node")
    if node:
        return node

    bundled_node = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "bin"
        / "node.exe"
    )
    if bundled_node.exists():
        return str(bundled_node)

    return None


def test_controls_ui_controller_exports_expected_button_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute controlsUiController.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        function element() {
            const classes = new Set();
            return {
                disabled: false,
                textContent: '',
                title: '',
                checked: true,
                classList: {
                    toggle(className, force) {
                        if (force) {
                            classes.add(className);
                        } else {
                            classes.delete(className);
                        }
                    },
                    contains(className) {
                        return classes.has(className);
                    }
                }
            };
        }

        function refs() {
            return {
                runSamBtn: element(),
                clearCandidatesBtn: element(),
                keepAnnotationsInput: element(),
                manualAnnotationBtn: element(),
                applyPreprocessBtn: element(),
                restoreOriginalBtn: element(),
                openPreprocessSettingsBtn: element(),
                preprocessSummary: element(),
                classificationSelect: element(),
                applyClassificationBtn: element(),
                oneClickAcceptInput: element(),
                quickClassInput: element(),
                quickAddClassBtn: element(),
                undoBtn: element(),
                redoBtn: element(),
                exportAnnotationFileBtn: element(),
                loadAnnotationFileBtn: element(),
                loadAnnotationFileInput: element(),
                loadServerAnnotationsBtn: element(),
                refreshMatchesBtn: element(),
                loadMatchedBtn: element(),
                useServerAnnotationSourceBtn: element(),
                saveServerBtn: element(),
                saveAllServerBtn: element(),
                unsavedStateIndicator: element(),
                selectionSummary: element(),
                nextActionText: element(),
                canvasEmptyState: element(),
                oneClickModeBadge: element(),
                prevImageBtn: element(),
                nextImageBtn: element()
            };
        }

        let classState = null;
        const helpers = {
            preprocessLabel(method) {
                return {
                    original: 'Original',
                    clahe: 'CLAHE',
                    gamma: 'Gamma'
                }[method] || method;
            },
            classUiController: {
                syncClassControlStates(classRefs, state) {
                    classState = { classRefs, state };
                    classRefs.classificationSelect.disabled = !state.classesExist;
                    classRefs.applyClassificationBtn.disabled = !state.selectionExists || !state.classesExist;
                    classRefs.oneClickAcceptInput.disabled = !state.imageLoaded || !state.classesExist || !state.candidatesExist || !state.activeClassName;
                    if (classRefs.oneClickAcceptInput.disabled) classRefs.oneClickAcceptInput.checked = false;
                }
            }
        };

        const context = { window: {} };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync('static/controlsUiController.js', 'utf8'), context);

        const controls = context.window.SAM2ControlsUiController;
        assert.ok(controls);

        const activeRefs = refs();
        activeRefs.oneClickAcceptInput.checked = true;
        controls.updateButtonStates(activeRefs, {
            imageLoaded: true,
            samHasRun: true,
            selectionExists: true,
            historyExists: true,
            redoExists: true,
            annotationsExist: true,
            candidatesExist: true,
            classesExist: true,
            isManualMode: true,
            selectedPreprocess: 'clahe',
            activePreprocess: true,
            activePreprocessMethod: 'clahe',
            localAnnotationSourceActive: true,
            dirtyImageCount: 2,
            currentImageDirty: true,
            imageCount: 3,
            matchSummary: { matched: 1 },
            currentImageIndex: 1,
            selectedCandidateCount: 2,
            selectedAnnotationCount: 1,
            activeClassName: 'WBC'
        }, helpers);

        assert.strictEqual(activeRefs.runSamBtn.disabled, false);
        assert.strictEqual(activeRefs.canvasEmptyState.classList.contains('hidden'), true);
        assert.strictEqual(activeRefs.oneClickModeBadge.textContent, 'One-click accept: WBC');
        assert.strictEqual(activeRefs.oneClickModeBadge.classList.contains('hidden'), false);
        assert.strictEqual(activeRefs.runSamBtn.textContent, 'Re-generate SAM2 candidates');
        assert.strictEqual(activeRefs.clearCandidatesBtn.disabled, false);
        assert.strictEqual(activeRefs.manualAnnotationBtn.textContent, 'Exit Manual Box (B)');
        assert.strictEqual(activeRefs.applyPreprocessBtn.disabled, false);
        assert.strictEqual(activeRefs.applyPreprocessBtn.textContent, 'CLAHE active');
        assert.strictEqual(activeRefs.restoreOriginalBtn.disabled, false);
        assert.strictEqual(activeRefs.preprocessSummary.textContent, 'CLAHE active. Original image is preserved.');
        assert.strictEqual(activeRefs.selectionSummary.textContent, 'Selected: 2 candidates, 1 annotation');
        assert.strictEqual(activeRefs.nextActionText.textContent, 'Apply active class or press a class hotkey.');
        assert.strictEqual(activeRefs.undoBtn.disabled, false);
        assert.strictEqual(activeRefs.redoBtn.disabled, false);
        assert.strictEqual(activeRefs.exportAnnotationFileBtn.disabled, false);
        assert.strictEqual(activeRefs.refreshMatchesBtn.textContent, 'Check Local Matches');
        assert.strictEqual(activeRefs.loadMatchedBtn.textContent, 'Import Local Matched');
        assert.strictEqual(activeRefs.useServerAnnotationSourceBtn.disabled, false);
        assert.strictEqual(activeRefs.saveAllServerBtn.disabled, false);
        assert.strictEqual(activeRefs.unsavedStateIndicator.textContent, 'Unsaved changes: current + 1 other');
        assert.strictEqual(activeRefs.unsavedStateIndicator.title, 'There are unsaved annotation changes.');
        assert.strictEqual(activeRefs.unsavedStateIndicator.classList.contains('dirty'), true);
        assert.strictEqual(activeRefs.unsavedStateIndicator.classList.contains('saved'), false);
        assert.strictEqual(activeRefs.refreshMatchesBtn.disabled, false);
        assert.strictEqual(activeRefs.loadMatchedBtn.disabled, false);
        assert.strictEqual(activeRefs.prevImageBtn.disabled, false);
        assert.strictEqual(activeRefs.nextImageBtn.disabled, false);
        assert.strictEqual(classState.state.imageLoaded, true);
        assert.strictEqual(classState.state.selectionExists, true);
        assert.strictEqual(classState.state.classesExist, true);
        assert.strictEqual(classState.state.candidatesExist, true);
        assert.strictEqual(classState.state.activeClassName, 'WBC');

        const inactiveRefs = refs();
        controls.updateButtonStates(inactiveRefs, {
            imageLoaded: false,
            samHasRun: false,
            selectionExists: false,
            historyExists: false,
            redoExists: false,
            annotationsExist: false,
            candidatesExist: false,
            classesExist: false,
            isManualMode: false,
            selectedPreprocess: 'original',
            activePreprocess: false,
            activePreprocessMethod: 'original',
            localAnnotationSourceActive: false,
            dirtyImageCount: 0,
            currentImageDirty: false,
            imageCount: 0,
            matchSummary: null,
            currentImageIndex: -1,
            selectedCandidateCount: 0,
            selectedAnnotationCount: 0,
            activeClassName: ''
        }, helpers);

        assert.strictEqual(inactiveRefs.runSamBtn.disabled, true);
        assert.strictEqual(inactiveRefs.canvasEmptyState.classList.contains('hidden'), false);
        assert.strictEqual(inactiveRefs.oneClickModeBadge.textContent, '');
        assert.strictEqual(inactiveRefs.oneClickModeBadge.classList.contains('hidden'), true);
        assert.strictEqual(inactiveRefs.runSamBtn.textContent, 'Generate SAM2 candidates');
        assert.strictEqual(inactiveRefs.clearCandidatesBtn.disabled, true);
        assert.strictEqual(inactiveRefs.keepAnnotationsInput.disabled, true);
        assert.strictEqual(inactiveRefs.manualAnnotationBtn.disabled, true);
        assert.strictEqual(inactiveRefs.manualAnnotationBtn.textContent, 'Manual Box (B)');
        assert.strictEqual(inactiveRefs.undoBtn.disabled, true);
        assert.strictEqual(inactiveRefs.redoBtn.disabled, true);
        assert.strictEqual(inactiveRefs.applyPreprocessBtn.disabled, true);
        assert.strictEqual(inactiveRefs.applyPreprocessBtn.textContent, 'Original image active');
        assert.strictEqual(inactiveRefs.restoreOriginalBtn.disabled, true);
        assert.strictEqual(inactiveRefs.openPreprocessSettingsBtn.disabled, false);
        assert.strictEqual(inactiveRefs.preprocessSummary.textContent, 'Original image is preserved.');
        assert.strictEqual(inactiveRefs.selectionSummary.textContent, 'Selected: 0 candidates, 0 annotations');
        assert.strictEqual(inactiveRefs.nextActionText.textContent, 'Load an image or folder.');
        assert.strictEqual(inactiveRefs.loadAnnotationFileBtn.disabled, true);
        assert.strictEqual(inactiveRefs.loadAnnotationFileInput.disabled, true);
        assert.strictEqual(inactiveRefs.loadServerAnnotationsBtn.disabled, true);
        assert.strictEqual(inactiveRefs.refreshMatchesBtn.textContent, 'Check Matches');
        assert.strictEqual(inactiveRefs.loadMatchedBtn.textContent, 'Import Matched');
        assert.strictEqual(inactiveRefs.useServerAnnotationSourceBtn.disabled, true);
        assert.strictEqual(inactiveRefs.saveServerBtn.disabled, true);
        assert.strictEqual(inactiveRefs.saveAllServerBtn.disabled, true);
        assert.strictEqual(inactiveRefs.unsavedStateIndicator.textContent, 'All changes saved');
        assert.strictEqual(inactiveRefs.unsavedStateIndicator.title, 'No unsaved annotation changes.');
        assert.strictEqual(inactiveRefs.unsavedStateIndicator.classList.contains('dirty'), false);
        assert.strictEqual(inactiveRefs.unsavedStateIndicator.classList.contains('saved'), true);
        assert.strictEqual(inactiveRefs.refreshMatchesBtn.disabled, true);
        assert.strictEqual(inactiveRefs.loadMatchedBtn.disabled, true);
        assert.strictEqual(inactiveRefs.prevImageBtn.disabled, true);
        assert.strictEqual(inactiveRefs.nextImageBtn.disabled, true);
        assert.strictEqual(controls.unsavedStateText(1, true), 'Unsaved changes: current image');
        assert.strictEqual(controls.unsavedStateText(1, false), 'Unsaved changes: 1 image');
        assert.strictEqual(controls.nextActionText({ imageLoaded: true, selectionExists: false, candidatesExist: false, annotationsExist: false }), 'Generate SAM2 candidates or draw manual boxes.');
        assert.strictEqual(controls.nextActionText({ imageLoaded: true, selectionExists: false, candidatesExist: true, annotationsExist: false }), 'Select candidate boxes.');
        assert.strictEqual(controls.nextActionText({ imageLoaded: true, selectionExists: false, candidatesExist: false, annotationsExist: true }), 'Review, edit, save, or export annotations.');
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
