import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


EXPECTED_DOM_REFS = [
    "loadImageInput",
    "runSamBtn",
    "samSettingsModal",
    "preprocessSettingsModal",
    "annotationLogBody",
    "annotationLogHint",
    "canvas",
    "ctx",
    "canvasContainer",
    "canvasEmptyState",
    "toastContainer",
    "classManager",
    "classManagerFeedback",
    "imageQueueProgress",
    "imageQueueFilters",
    "unsavedStateIndicator",
    "selectionSummary",
    "nextActionText",
    "oneClickModeBadge",
    "undoBtn",
    "redoBtn",
    "validateProjectDatasetBtn",
    "exportProjectDatasetBtn",
    "samReadinessText",
    "helpModal",
]


def test_dom_refs_loads_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    state_store_tag = '<script src="static/stateStore.js"></script>'
    dom_refs_tag = '<script src="static/domRefs.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert state_store_tag in index_html
    assert dom_refs_tag in index_html
    assert script_tag in index_html
    assert index_html.index(state_store_tag) < index_html.index(dom_refs_tag)
    assert index_html.index(dom_refs_tag) < index_html.index(script_tag)


def test_main_script_uses_dom_refs_without_direct_id_lookups():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const domRefs = window.SAM2DomRefs;" in script_js
    assert "} = domRefs.getDomRefs(document);" in script_js
    assert "document.getElementById(" not in script_js
    for ref_name in EXPECTED_DOM_REFS:
        assert ref_name in script_js


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


def test_dom_refs_exports_expected_element_mapping():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute domRefs.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        const context = { window: {} };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync('static/domRefs.js', 'utf8'), context);

        const domRefs = context.window.SAM2DomRefs;
        assert.ok(domRefs);
        assert.strictEqual(domRefs.DOM_REF_IDS.loadImageInput, 'loadImageInput');
        assert.strictEqual(domRefs.DOM_REF_IDS.canvas, 'mainCanvas');
        assert.strictEqual(domRefs.DOM_REF_IDS.canvasContainer, 'canvas-container');
        assert.strictEqual(domRefs.DOM_REF_IDS.canvasEmptyState, 'canvasEmptyState');
        assert.strictEqual(domRefs.DOM_REF_IDS.toastContainer, 'toast-container');
        assert.strictEqual(domRefs.DOM_REF_IDS.imageQueueProgress, 'imageQueueProgress');
        assert.strictEqual(domRefs.DOM_REF_IDS.imageQueueFilters, 'imageQueueFilters');
        assert.strictEqual(domRefs.DOM_REF_IDS.unsavedStateIndicator, 'unsavedStateIndicator');
        assert.strictEqual(domRefs.DOM_REF_IDS.selectionSummary, 'selectionSummary');
        assert.strictEqual(domRefs.DOM_REF_IDS.nextActionText, 'nextActionText');
        assert.strictEqual(domRefs.DOM_REF_IDS.oneClickModeBadge, 'oneClickModeBadge');
        assert.strictEqual(domRefs.DOM_REF_IDS.annotationLogHint, 'annotationLogHint');
        assert.strictEqual(domRefs.DOM_REF_IDS.undoBtn, 'undoBtn');
        assert.strictEqual(domRefs.DOM_REF_IDS.redoBtn, 'redoBtn');
        assert.strictEqual(domRefs.DOM_REF_IDS.validateProjectDatasetBtn, 'validateProjectDatasetBtn');
        assert.strictEqual(domRefs.DOM_REF_IDS.exportProjectDatasetBtn, 'exportProjectDatasetBtn');
        assert.strictEqual(domRefs.DOM_REF_IDS.classManagerFeedback, 'classManagerFeedback');
        assert.strictEqual(domRefs.DOM_REF_IDS.samReadinessText, 'samReadinessText');

        const requestedIds = [];
        const canvasContext = { kind: '2d-context' };
        const elementsById = new Map(
            Object.values(domRefs.DOM_REF_IDS).map(id => [
                id,
                id === 'mainCanvas'
                    ? { id, getContext: kind => (kind === '2d' ? canvasContext : null) }
                    : { id }
            ])
        );
        const fakeDocument = {
            getElementById(id) {
                requestedIds.push(id);
                return elementsById.get(id);
            }
        };

        const refs = domRefs.getDomRefs(fakeDocument);
        assert.strictEqual(refs.loadImageInput.id, 'loadImageInput');
        assert.strictEqual(refs.runSamBtn.id, 'runSamBtn');
        assert.strictEqual(refs.canvas.id, 'mainCanvas');
        assert.strictEqual(refs.canvasContainer.id, 'canvas-container');
        assert.strictEqual(refs.canvasEmptyState.id, 'canvasEmptyState');
        assert.strictEqual(refs.toastContainer.id, 'toast-container');
        assert.strictEqual(refs.imageQueueProgress.id, 'imageQueueProgress');
        assert.strictEqual(refs.imageQueueFilters.id, 'imageQueueFilters');
        assert.strictEqual(refs.unsavedStateIndicator.id, 'unsavedStateIndicator');
        assert.strictEqual(refs.selectionSummary.id, 'selectionSummary');
        assert.strictEqual(refs.nextActionText.id, 'nextActionText');
        assert.strictEqual(refs.oneClickModeBadge.id, 'oneClickModeBadge');
        assert.strictEqual(refs.annotationLogHint.id, 'annotationLogHint');
        assert.strictEqual(refs.classManagerFeedback.id, 'classManagerFeedback');
        assert.strictEqual(refs.samReadinessText.id, 'samReadinessText');
        assert.strictEqual(refs.ctx, canvasContext);
        assert.strictEqual(requestedIds.length, Object.keys(domRefs.DOM_REF_IDS).length);
        assert.ok(requestedIds.includes('helpModal'));
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
