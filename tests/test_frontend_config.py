import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


EXTRACTED_CONSTANTS = [
    "DEFAULT_CLASSES",
    "ANNOTATION_FORMATS",
    "CLASS_COLOR_PALETTE",
    "ALLOWED_IMAGE_EXTENSIONS",
    "ALLOWED_IMAGE_MIME_TYPES",
    "OVERLAY_COLORS",
    "MAX_ZOOM",
    "MIN_ZOOM",
    "SCROLL_SENSITIVITY",
    "ZOOM_STEP",
    "BOX_HANDLE_SCREEN_SIZE",
    "MIN_BOX_SIZE",
    "NEW_CLASS_ACTION",
    "DEFAULT_SAM_PRESET",
    "DEFAULT_SAM_PARAMS",
    "DEFAULT_SAM_PRESETS",
    "PREPROCESS_METHODS",
    "DEFAULT_PREPROCESS_PARAMS",
]


def test_frontend_config_loads_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    api_client_tag = '<script src="static/apiClient.js"></script>'
    config_tag = '<script src="static/frontendConfig.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert api_client_tag in index_html
    assert config_tag in index_html
    assert script_tag in index_html
    assert index_html.index(api_client_tag) < index_html.index(script_tag)
    assert index_html.index(config_tag) < index_html.index(script_tag)


def test_main_script_uses_extracted_frontend_config_without_duplicate_constants():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const frontendConfig = window.SAM2FrontendConfig;" in script_js
    assert "} = frontendConfig;" in script_js
    for constant_name in EXTRACTED_CONSTANTS:
        assert f"const {constant_name} =" not in script_js


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


def test_frontend_config_exports_expected_values():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute frontendConfig.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        const source = fs.readFileSync('static/frontendConfig.js', 'utf8');
        const context = { window: {} };
        vm.createContext(context);
        vm.runInContext(source, context);

        const config = context.window.SAM2FrontendConfig;
        assert.ok(config);
        assert.ok(Array.isArray(config.DEFAULT_CLASSES));
        assert.strictEqual(config.DEFAULT_CLASSES.length, 0);
        assert.strictEqual(config.ANNOTATION_FORMATS.csv.label, 'Simple CSV');
        assert.strictEqual(config.ANNOTATION_FORMATS.coco.mime, 'application/json');
        assert.strictEqual(config.CLASS_COLOR_PALETTE[0], '#39d353');
        assert.ok(config.ALLOWED_IMAGE_EXTENSIONS.includes('.tiff'));
        assert.ok(config.ALLOWED_IMAGE_MIME_TYPES.has('image/x-tiff'));
        assert.strictEqual(config.OVERLAY_COLORS.manualBox, '#d97706');
        assert.strictEqual(config.MAX_ZOOM, 10);
        assert.strictEqual(config.MIN_ZOOM, 0.1);
        assert.strictEqual(config.SCROLL_SENSITIVITY, 0.001);
        assert.strictEqual(config.ZOOM_STEP, 1.2);
        assert.strictEqual(config.BOX_HANDLE_SCREEN_SIZE, 9);
        assert.strictEqual(config.MIN_BOX_SIZE, 2);
        assert.strictEqual(config.NEW_CLASS_ACTION, '__new_class__');
        assert.strictEqual(config.DEFAULT_SAM_PRESET, 'cell_1920x1440');
        assert.strictEqual(config.DEFAULT_SAM_PARAMS.points_per_side, 64);
        assert.strictEqual(config.DEFAULT_SAM_PRESETS[0].key, 'cell_1920x1440');
        assert.strictEqual(config.DEFAULT_SAM_PRESETS[0].params.points_per_side, 64);
        assert.strictEqual(config.PREPROCESS_METHODS.clahe.badge, 'CLAHE');
        assert.strictEqual(config.DEFAULT_PREPROCESS_PARAMS.gamma, 1.2);
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
