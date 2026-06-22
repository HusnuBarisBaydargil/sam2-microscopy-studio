import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


DELEGATED_GEOMETRY_CALLS = [
    "canvasGeometry.arrowKeyDelta(",
    "canvasGeometry.resizeBbox(",
    "canvasGeometry.normalizeBboxFromPoints(",
    "canvasGeometry.normalizeRawBbox(",
    "canvasGeometry.clampBboxToImage(",
    "canvasGeometry.clampMovedBboxToImage(",
    "canvasGeometry.getResizeHandleAtPoint(",
    "canvasGeometry.annotationHandles(",
    "canvasGeometry.pointInsideCandidate(",
    "canvasGeometry.pointInsideBbox(",
    "canvasGeometry.pointInsidePolygon(",
    "canvasGeometry.cursorForHandle(",
    "canvasGeometry.bboxesEqual(",
    "canvasGeometry.fitImageToView(",
    "canvasGeometry.screenPoint(",
    "canvasGeometry.worldPoint(",
    "canvasGeometry.pointInsideRect(",
]


def test_canvas_geometry_loads_after_config_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    config_tag = '<script src="static/frontendConfig.js"></script>'
    geometry_tag = '<script src="static/canvasGeometry.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert config_tag in index_html
    assert geometry_tag in index_html
    assert script_tag in index_html
    assert index_html.index(config_tag) < index_html.index(geometry_tag)
    assert index_html.index(geometry_tag) < index_html.index(script_tag)


def test_main_script_delegates_canvas_geometry_helpers():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const canvasGeometry = window.SAM2CanvasGeometry;" in script_js
    for delegated_call in DELEGATED_GEOMETRY_CALLS:
        assert delegated_call in script_js


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


def test_canvas_geometry_exports_expected_math_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute canvasGeometry.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        function plain(value) {
            return JSON.parse(JSON.stringify(value));
        }

        function assertClose(actual, expected, tolerance = 0.0001) {
            assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);
        }

        const context = { window: {} };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync('static/frontendConfig.js', 'utf8'), context);
        vm.runInContext(fs.readFileSync('static/canvasGeometry.js', 'utf8'), context);

        const geometry = context.window.SAM2CanvasGeometry;
        assert.ok(geometry);

        assert.deepStrictEqual(plain(geometry.arrowKeyDelta('ArrowLeft')), { dx: -1, dy: 0 });
        assert.strictEqual(geometry.arrowKeyDelta('KeyA'), null);
        assert.deepStrictEqual(plain(geometry.normalizeBboxFromPoints(10, 20, 2, 5)), [2, 5, 8, 15]);
        assert.deepStrictEqual(plain(geometry.normalizeBboxFromPoints(1, 1, 1.5, 1.5)), [1, 1, 2, 2]);
        assert.deepStrictEqual(plain(geometry.normalizeRawBbox([10, 10, -5, -4])), [5, 6, 5, 4]);
        assert.strictEqual(geometry.normalizeRawBbox([1, 2, 0, 3]), null);

        assert.deepStrictEqual(
            plain(geometry.clampBboxToImage([-5, 10, 20, 20], { width: 100, height: 30 })),
            [0, 10, 15, 20]
        );
        assert.strictEqual(geometry.clampBboxToImage([120, 10, 20, 20], { width: 100, height: 30 }), null);
        assert.deepStrictEqual(
            plain(geometry.clampMovedBboxToImage([95, 25, 20, 10], { width: 100, height: 30 })),
            [80, 20, 20, 10]
        );
        assert.strictEqual(geometry.clampNumber(12, 0, 10), 10);

        const annotation = { bbox: [10, 20, 40, 20] };
        assert.deepStrictEqual(plain(geometry.annotationHandles(annotation).se), { x: 50, y: 40 });
        assert.strictEqual(geometry.getResizeHandleAtPoint(annotation, { x: 50, y: 40 }, 1), 'se');
        assert.strictEqual(geometry.getResizeHandleAtPoint(annotation, { x: 30, y: 20 }, 1), 'n');
        assert.strictEqual(geometry.getResizeHandleAtPoint(annotation, { x: 30, y: 30 }, 1), null);

        assert.strictEqual(geometry.pointInsideBbox({ x: 15, y: 25 }, [10, 20, 40, 20]), true);
        assert.strictEqual(geometry.pointInsideBbox({ x: 5, y: 25 }, [10, 20, 40, 20]), false);
        const polygon = [[0, 0], [10, 0], [10, 10], [0, 10]];
        assert.strictEqual(geometry.pointInsidePolygon({ x: 5, y: 5 }, polygon), true);
        assert.strictEqual(geometry.pointInsidePolygon({ x: 15, y: 5 }, polygon), false);
        assert.strictEqual(
            geometry.pointInsideCandidate(
                { x: 5, y: 5 },
                { contour: polygon, bbox: [100, 100, 10, 10] },
                contour => contour
            ),
            true
        );

        assert.strictEqual(geometry.cursorForHandle('ne'), 'nesw-resize');
        assert.strictEqual(geometry.cursorForHandle('bad'), 'default');
        assert.strictEqual(geometry.bboxesEqual([1, 2, 3, 4], [1, 2.0005, 3, 4]), true);
        assert.strictEqual(geometry.bboxesEqual([1, 2, 3, 4], [1, 2.01, 3, 4]), false);

        const fitted = geometry.fitImageToView({ width: 1000, height: 500 }, { width: 200, height: 100 });
        assertClose(fitted.zoom, 4.75);
        assertClose(fitted.offset.x, 25);
        assertClose(fitted.offset.y, 12.5);
        assert.strictEqual(geometry.fitImageToView({ width: 0, height: 500 }, { width: 200, height: 100 }), null);

        assert.deepStrictEqual(plain(geometry.screenPoint(150, 90, { left: 100, top: 50 })), { x: 50, y: 40 });
        assert.deepStrictEqual(plain(geometry.worldPoint(50, 40, { x: 10, y: 20 }, 2)), { x: 20, y: 10 });
        assert.strictEqual(geometry.pointInsideRect({ x: 5, y: 6 }, { x: 0, y: 0, w: 10, h: 10 }), true);
        assert.strictEqual(geometry.pointInsideRect({ x: 11, y: 6 }, { x: 0, y: 0, w: 10, h: 10 }), false);

        const zoomed = geometry.zoomState(4, { x: 100, y: 80 }, { x: 10, y: 20 }, 2);
        assertClose(zoomed.zoom, 4);
        assertClose(zoomed.offset.x, -80);
        assertClose(zoomed.offset.y, -40);
        assert.strictEqual(geometry.screenUnits(10, 2), 5);
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
