import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


REMOVED_RENDERING_WRAPPERS = [
    "function screenUnits(",
    "function strokeCandidateShape(",
    "function drawCandidateOverlay(",
    "function drawAnnotationOverlay(",
    "function drawAnnotationLabel(",
    "function strokeScreenRect(",
    "function drawAnnotationHandles(",
]


def test_canvas_renderer_loads_after_geometry_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    config_tag = '<script src="static/frontendConfig.js"></script>'
    geometry_tag = '<script src="static/canvasGeometry.js"></script>'
    renderer_tag = '<script src="static/canvasRenderer.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert config_tag in index_html
    assert geometry_tag in index_html
    assert renderer_tag in index_html
    assert script_tag in index_html
    assert index_html.index(config_tag) < index_html.index(renderer_tag)
    assert index_html.index(geometry_tag) < index_html.index(renderer_tag)
    assert index_html.index(renderer_tag) < index_html.index(script_tag)


def test_main_script_delegates_canvas_rendering_helpers():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const canvasRenderer = window.SAM2CanvasRenderer;" in script_js
    assert "canvasRenderer.drawScene(" in script_js
    for wrapper_signature in REMOVED_RENDERING_WRAPPERS:
        assert wrapper_signature not in script_js

    assert "const imageToDraw = currentDisplayImage();" not in script_js
    assert "ctx.drawImage(imageToDraw, 0, 0);" not in script_js
    assert "appState.choiceInfo.buttons.forEach(button => {" not in script_js


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


def test_canvas_renderer_exports_expected_drawing_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute canvasRenderer.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        const context = { window: {} };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync('static/frontendConfig.js', 'utf8'), context);
        vm.runInContext(fs.readFileSync('static/canvasGeometry.js', 'utf8'), context);
        vm.runInContext(fs.readFileSync('static/canvasRenderer.js', 'utf8'), context);

        const renderer = context.window.SAM2CanvasRenderer;
        assert.ok(renderer);

        function makeContext() {
            const calls = [];
            return {
                calls,
                save() { calls.push(['save']); },
                restore() { calls.push(['restore']); },
                translate(x, y) { calls.push(['translate', x, y]); },
                scale(x, y) { calls.push(['scale', x, y]); },
                drawImage(image, x, y) { calls.push(['drawImage', image.id, x, y]); },
                fillRect(x, y, w, h) { calls.push(['fillRect', x, y, w, h]); },
                strokeRect(x, y, w, h) { calls.push(['strokeRect', x, y, w, h]); },
                setLineDash(dash) { calls.push(['setLineDash', dash]); },
                beginPath() { calls.push(['beginPath']); },
                moveTo(x, y) { calls.push(['moveTo', x, y]); },
                lineTo(x, y) { calls.push(['lineTo', x, y]); },
                closePath() { calls.push(['closePath']); },
                stroke() { calls.push(['stroke']); },
                measureText(text) {
                    calls.push(['measureText', text]);
                    return { width: text.length * 6 };
                },
                fillText(text, x, y) { calls.push(['fillText', text, x, y]); }
            };
        }

        const contourCtx = makeContext();
        renderer.strokeCandidateShape(contourCtx, {
            contour: [[1, 2], [5, 2], [5, 8]]
        });
        assert.deepStrictEqual(contourCtx.calls.slice(0, 5), [
            ['beginPath'],
            ['moveTo', 1, 2],
            ['lineTo', 5, 2],
            ['lineTo', 5, 8],
            ['closePath']
        ]);
        assert.deepStrictEqual(contourCtx.calls[5], ['stroke']);

        const bboxCtx = makeContext();
        renderer.strokeCandidateShape(bboxCtx, { bbox: [10, 20, 30, 40] });
        assert.deepStrictEqual(bboxCtx.calls, [['strokeRect', 10, 20, 30, 40]]);

        const sceneCtx = makeContext();
        const zoomLevelDisplay = { textContent: '' };
        renderer.drawScene(sceneCtx, { width: 200, height: 100 }, {
            imageToDraw: { id: 'image' },
            cameraOffset: { x: 11, y: 12 },
            cameraZoom: 2,
            candidates: [{ id: 7, bbox: [1, 2, 30, 40] }],
            selectedCandidateIds: new Set([7]),
            annotations: [{ id: 3, bbox: [10, 20, 50, 40], class: 'Nucleus' }],
            selectedAnnotationIds: new Set([3]),
            isDrawing: true,
            currentManualBox: { x: 4, y: 5, w: 60, h: 70 },
            isAwaitingChoice: true,
            choiceInfo: {
                rect: { x: 6, y: 7, w: 80, h: 90 },
                buttons: [{ x: 10, y: 12, w: 20, h: 14, color: '#123456', label: 'Keep' }]
            },
            zoomLevelDisplay,
            getClassColor(className) {
                assert.strictEqual(className, 'Nucleus');
                return '#abcdef';
            }
        });

        assert.ok(sceneCtx.calls.some(call => call[0] === 'fillRect' && call[1] === 0 && call[2] === 0));
        assert.ok(sceneCtx.calls.some(call => call[0] === 'translate' && call[1] === 11 && call[2] === 12));
        assert.ok(sceneCtx.calls.some(call => call[0] === 'scale' && call[1] === 2 && call[2] === 2));
        assert.ok(sceneCtx.calls.some(call => call[0] === 'drawImage' && call[1] === 'image'));
        assert.ok(sceneCtx.calls.some(call => call[0] === 'strokeRect' && call[1] === 1 && call[2] === 2));
        assert.ok(sceneCtx.calls.some(call => call[0] === 'measureText' && call[1] === '#3'));
        assert.ok(sceneCtx.calls.some(call => call[0] === 'fillText' && call[1] === 'Keep'));
        assert.strictEqual(zoomLevelDisplay.textContent, '200%');
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
