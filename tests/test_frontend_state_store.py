import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


STATE_STORE_CALLS = [
    "stateStore.createAppState(",
    "stateStore.initializeImageState(",
    "stateStore.currentImageId(",
    "stateStore.currentImageIndex(",
    "stateStore.currentAnnotations(",
    "stateStore.setCurrentAnnotations(",
    "stateStore.currentCandidates(",
    "stateStore.setCurrentCandidates(",
    "stateStore.currentHistory(",
    "stateStore.setCurrentHistory(",
    "stateStore.currentRedoHistory(",
    "stateStore.setCurrentRedoHistory(",
    "stateStore.currentDisplayImage(",
    "stateStore.markCurrentImageDirty(",
    "stateStore.resetInteractionState(",
    "stateStore.resetProjectState(",
]


def test_state_store_loads_after_config_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    config_tag = '<script src="static/frontendConfig.js"></script>'
    state_store_tag = '<script src="static/stateStore.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert config_tag in index_html
    assert state_store_tag in index_html
    assert script_tag in index_html
    assert index_html.index(config_tag) < index_html.index(state_store_tag)
    assert index_html.index(state_store_tag) < index_html.index(script_tag)


def test_main_script_uses_state_store_without_duplicate_state_shape():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const stateStore = window.SAM2StateStore;" in script_js
    for delegated_call in STATE_STORE_CALLS:
        assert delegated_call in script_js

    assert "annotationsByImage: new Map()" not in script_js
    assert "candidateAnnotationsByImage: new Map()" not in script_js
    assert "projectSettings: {" not in script_js
    assert "DEFAULT_CLASSES," not in script_js
    assert "DEFAULT_SAM_PRESETS," not in script_js


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


def test_state_store_exports_expected_state_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute stateStore.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        function plain(value) {
            return JSON.parse(JSON.stringify(value));
        }

        const context = { window: {} };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync('static/frontendConfig.js', 'utf8'), context);
        vm.runInContext(fs.readFileSync('static/stateStore.js', 'utf8'), context);

        const store = context.window.SAM2StateStore;
        assert.ok(store);

        const state = store.createAppState();
        assert.strictEqual(state.nextClassId, 1);
        assert.strictEqual(state.projectSettings.schemaVersion, 1);
        assert.strictEqual(state.projectSettings.taskType, 'bounding_box');
        assert.strictEqual(state.projectSettings.annotationOutputDir, 'annotations');
        assert.strictEqual(state.projectSettings.annotationFormat, 'csv');
        assert.strictEqual(state.projectSettings.samSettings.preset, 'cell_1920x1440');
        assert.strictEqual(state.annotationSource.mode, 'server');
        assert.strictEqual(state.imageQueueFilter, 'all');
        assert.strictEqual(state.cameraZoom, 1);
        assert.strictEqual(store.currentImageId(state), null);
        assert.strictEqual(store.currentImageIndex(state), -1);
        assert.deepStrictEqual(plain(store.currentAnnotations(state)), []);
        assert.deepStrictEqual(plain(store.currentCandidates(state)), []);
        assert.deepStrictEqual(plain(store.currentHistory(state)), []);
        assert.deepStrictEqual(plain(store.currentRedoHistory(state)), []);

        const otherState = store.createAppState();
        state.projectSettings.samSettings.params.points_per_side = 123;
        assert.notStrictEqual(otherState.projectSettings.samSettings.params.points_per_side, 123);

        const originalImage = { id: 'original' };
        const processedImage = { id: 'processed' };
        state.images = [
            { id: 'image-1', originalImage, processedImage, preprocessMethod: 'clahe' }
        ];
        state.currentImage = state.images[0];
        store.initializeImageState(state, 'image-1');
        assert.strictEqual(store.currentImageId(state), 'image-1');
        assert.strictEqual(store.currentImageIndex(state), 0);

        store.setCurrentAnnotations(state, [{ id: 1 }]);
        store.setCurrentCandidates(state, [{ id: 'cand_1' }]);
        store.setCurrentHistory(state, [{ type: 'batch' }]);
        store.setCurrentRedoHistory(state, [{ type: 'redo' }]);
        assert.deepStrictEqual(plain(store.currentAnnotations(state)), [{ id: 1 }]);
        assert.deepStrictEqual(plain(store.currentCandidates(state)), [{ id: 'cand_1' }]);
        assert.deepStrictEqual(plain(store.currentHistory(state)), [{ type: 'batch' }]);
        assert.deepStrictEqual(plain(store.currentRedoHistory(state)), [{ type: 'redo' }]);
        assert.strictEqual(store.currentDisplayImage(state, () => true), processedImage);
        assert.strictEqual(store.currentDisplayImage(state, () => false), originalImage);

        store.markCurrentImageDirty(state);
        assert.strictEqual(state.dirtyImages.has('image-1'), true);

        state.selectedCandidateIds.add('cand_1');
        state.selectedAnnotationIds.add(1);
        state.isManualMode = true;
        state.isDrawing = true;
        state.isPanning = true;
        state.choiceInfo = { rect: {} };
        state.boxEditOriginalBboxes.set(1, [1, 2, 3, 4]);
        store.resetInteractionState(state);
        assert.strictEqual(state.selectedCandidateIds.size, 0);
        assert.strictEqual(state.selectedAnnotationIds.size, 0);
        assert.strictEqual(state.isDrawing, false);
        assert.strictEqual(state.isPanning, false);
        assert.strictEqual(state.choiceInfo, null);
        assert.strictEqual(state.boxEditOriginalBboxes.size, 0);
        assert.strictEqual(state.isManualMode, true);

        state.images = [{ id: 'image-1' }];
        state.currentImage = state.images[0];
        state.matchSummary = { matched: 1 };
        state.imageQueueFilter = 'unsaved';
        state.annotationCounter = 7;
        state.candidateCounter = 9;
        state.cameraOffset = { x: 10, y: 11 };
        state.cameraZoom = 3;
        store.initializeImageState(state, 'image-1');
        store.markCurrentImageDirty(state);
        store.resetProjectState(state);
        assert.strictEqual(state.images.length, 0);
        assert.strictEqual(state.currentImage, null);
        assert.strictEqual(state.annotationsByImage.size, 0);
        assert.strictEqual(state.annotationRedoByImage.size, 0);
        assert.strictEqual(state.dirtyImages.size, 0);
        assert.strictEqual(state.matchSummary, null);
        assert.strictEqual(state.imageQueueFilter, 'all');
        assert.strictEqual(state.annotationCounter, 0);
        assert.strictEqual(state.candidateCounter, 0);
        assert.deepStrictEqual(plain(state.cameraOffset), { x: 0, y: 0 });
        assert.strictEqual(state.cameraZoom, 1);
        assert.strictEqual(state.projectSettings.annotationOutputDir, 'annotations');
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
