import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


CANVAS_INTERACTION_CALLS = [
    "canvasInteractionController.toggleManualMode(",
    "canvasInteractionController.beginManualDrawing(",
    "canvasInteractionController.updateManualBox(",
    "canvasInteractionController.finishManualDrawing(",
    "canvasInteractionController.beginPanning(",
    "canvasInteractionController.updatePanning(",
    "canvasInteractionController.finishPanning(",
    "canvasInteractionController.startBoxEdit(",
    "canvasInteractionController.updateBoxEdit(",
    "canvasInteractionController.commitBoxEdit(",
    "canvasInteractionController.cancelBoxEdit(",
    "canvasInteractionController.nudgeSelectedAnnotations(",
    "canvasInteractionController.zoomState(",
    "canvasInteractionController.setupChoiceButtons(",
    "canvasInteractionController.buildManualAnnotation(",
    "canvasInteractionController.closeManualChoice(",
]


def test_canvas_interaction_controller_loads_after_geometry_and_before_renderer():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    geometry_tag = '<script src="static/canvasGeometry.js"></script>'
    interaction_tag = '<script src="static/canvasInteractionController.js"></script>'
    renderer_tag = '<script src="static/canvasRenderer.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert geometry_tag in index_html
    assert interaction_tag in index_html
    assert renderer_tag in index_html
    assert script_tag in index_html
    assert index_html.index(geometry_tag) < index_html.index(interaction_tag)
    assert index_html.index(interaction_tag) < index_html.index(renderer_tag)
    assert index_html.index(interaction_tag) < index_html.index(script_tag)


def test_main_script_delegates_canvas_interaction_state_logic():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const canvasInteractionController = window.SAM2CanvasInteractionController;" in script_js
    for delegated_call in CANVAS_INTERACTION_CALLS:
        assert delegated_call in script_js

    assert "appState.cameraOffset.x += event.clientX - appState.lastPanPoint.x;" not in script_js
    assert "appState.boxEditOriginalBboxes = new Map();" not in script_js
    assert "const buttonWidth = 96;" not in script_js
    assert "const normalizedRect = {" not in script_js


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


def test_canvas_interaction_controller_exports_expected_state_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute canvasInteractionController.js")

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
        vm.runInContext(fs.readFileSync('static/canvasInteractionController.js', 'utf8'), context);

        const controller = context.window.SAM2CanvasInteractionController;
        assert.ok(controller);

        const state = {
            isManualMode: false,
            isPanning: false,
            isDrawing: false,
            isAwaitingChoice: false,
            manualBoxStart: { x: 0, y: 0 },
            currentManualBox: null,
            choiceInfo: null,
            lastPanPoint: { x: 0, y: 0 },
            cameraOffset: { x: 10, y: 20 },
            cameraZoom: 2,
            boxEditMode: null,
            boxEditHandle: null,
            boxEditStartWorld: null,
            boxEditOriginalBboxes: new Map(),
            annotationCounter: 0
        };

        assert.deepStrictEqual(plain(controller.toggleManualMode(state)), {
            enabled: true,
            cursor: 'crosshair',
            status: 'Manual Box mode enabled. Click and drag.'
        });
        assert.strictEqual(state.isManualMode, true);
        assert.strictEqual(state.isPanning, false);

        controller.beginManualDrawing(state, { x: 5, y: 6 });
        controller.updateManualBox(state, { x: 25, y: 36 });
        assert.deepStrictEqual(plain(state.currentManualBox), { x: 5, y: 6, w: 20, h: 30 });
        assert.strictEqual(controller.finishManualDrawing(state), true);
        assert.strictEqual(state.isDrawing, false);
        assert.strictEqual(state.isAwaitingChoice, true);

        state.isDrawing = true;
        state.currentManualBox = { x: 1, y: 1, w: 2, h: 2 };
        assert.strictEqual(controller.finishManualDrawing(state), false);
        assert.strictEqual(state.currentManualBox, null);

        controller.beginPanning(state, { x: 10, y: 10 });
        controller.updatePanning(state, { x: 13, y: 18 });
        assert.deepStrictEqual(plain(state.cameraOffset), { x: 13, y: 28 });
        assert.deepStrictEqual(plain(state.lastPanPoint), { x: 13, y: 18 });
        assert.strictEqual(controller.finishPanning(state), 'crosshair');
        assert.strictEqual(state.isPanning, false);

        const annotations = new Map([
            [1, { id: 1, bbox: [10, 10, 20, 20] }],
            [2, { id: 2, bbox: [50, 50, 10, 10] }]
        ]);
        const findAnnotationById = id => annotations.get(id);
        const geometry = {
            clampMovedBboxToImage(bbox) { return bbox; },
            resizeBbox(bbox, handle, dx, dy) {
                assert.strictEqual(handle, 'se');
                return [bbox[0], bbox[1], bbox[2] + dx, bbox[3] + dy];
            },
            clampBboxToImage(bbox) { return bbox; },
            bboxesEqual(a, b) {
                return a.length === b.length && a.every((value, index) => value === b[index]);
            }
        };

        controller.startBoxEdit(state, 'move', { x: 10, y: 10 }, [1], findAnnotationById);
        controller.updateBoxEdit(state, { x: 15, y: 17 }, findAnnotationById, geometry);
        assert.deepStrictEqual(plain(annotations.get(1).bbox), [15, 17, 20, 20]);
        let changes = controller.commitBoxEdit(state, findAnnotationById, geometry.bboxesEqual);
        assert.deepStrictEqual(plain(changes), [{ id: 1, oldBbox: [10, 10, 20, 20], newBbox: [15, 17, 20, 20] }]);
        assert.strictEqual(state.boxEditMode, null);

        controller.startBoxEdit(state, 'resize', { x: 0, y: 0 }, [2], findAnnotationById, 'se');
        controller.updateBoxEdit(state, { x: 5, y: 6 }, findAnnotationById, geometry);
        assert.deepStrictEqual(plain(annotations.get(2).bbox), [50, 50, 15, 16]);
        assert.strictEqual(controller.cancelBoxEdit(state, findAnnotationById), 'crosshair');
        assert.deepStrictEqual(plain(annotations.get(2).bbox), [50, 50, 10, 10]);

        const nudgeAnnotations = [
            { id: 1, bbox: [0, 0, 5, 5] },
            { id: 2, bbox: [10, 10, 5, 5] }
        ];
        changes = controller.nudgeSelectedAnnotations(
            nudgeAnnotations,
            new Set([2]),
            3,
            -2,
            geometry
        );
        assert.deepStrictEqual(plain(changes), [{ id: 2, oldBbox: [10, 10, 5, 5], newBbox: [13, 8, 5, 5] }]);
        assert.deepStrictEqual(plain(nudgeAnnotations[1].bbox), [13, 8, 5, 5]);

        controller.zoomState(
            state,
            4,
            { x: 100, y: 80 },
            (newZoom, mousePos, cameraOffset, cameraZoom) => {
                assert.strictEqual(newZoom, 4);
                assert.deepStrictEqual(plain(mousePos), { x: 100, y: 80 });
                assert.strictEqual(cameraZoom, 2);
                return { zoom: 4, offset: { x: -80, y: -40 } };
            }
        );
        assert.strictEqual(state.cameraZoom, 4);
        assert.deepStrictEqual(plain(state.cameraOffset), { x: -80, y: -40 });

        state.currentManualBox = { x: 20, y: 20, w: 50, h: 40 };
        const choiceInfo = controller.setupChoiceButtons(
            state,
            { width: 240, height: 160 },
            [
                { name: 'Nucleus', color: '#111111' },
                { name: 'Membrane', color: '#222222' }
            ],
            '__new_class__'
        );
        assert.deepStrictEqual(plain(choiceInfo.rect), { x: 20, y: 20, w: 50, h: 40 });
        assert.deepStrictEqual(plain(choiceInfo.buttons.map(button => button.action)), [
            'Nucleus',
            'Membrane',
            '__new_class__',
            'Cancel'
        ]);
        assert.strictEqual(state.currentManualBox, null);

        state.choiceInfo = { rect: { x: 20, y: 20, w: 40, h: 20 } };
        const manual = controller.buildManualAnnotation(
            state,
            'Nucleus',
            (x, y) => ({ x: x / 2, y: y / 2 }),
            bbox => bbox
        );
        assert.deepStrictEqual(plain(manual), {
            annotation: { id: 1, bbox: [10, 10, 20, 10], class: 'Nucleus', type: 'manual' },
            error: null
        });

        state.choiceInfo = { rect: { x: 20, y: 20, w: 0, h: 0 } };
        const invalidManual = controller.buildManualAnnotation(
            state,
            'Nucleus',
            (x, y) => ({ x, y }),
            bbox => bbox
        );
        assert.strictEqual(invalidManual.annotation, null);
        assert.strictEqual(invalidManual.error, 'Invalid box dimensions.');

        state.isAwaitingChoice = true;
        state.choiceInfo = { rect: {} };
        controller.closeManualChoice(state);
        assert.strictEqual(state.isAwaitingChoice, false);
        assert.strictEqual(state.choiceInfo, null);
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
