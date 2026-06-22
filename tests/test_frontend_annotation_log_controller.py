import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


ANNOTATION_LOG_CALLS = [
    "annotationLogController.applyLogSelection(",
    "annotationLogController.openContextMenu(",
    "annotationLogController.hideContextMenu(",
    "annotationLogController.renderAnnotationLog(",
    "annotationLogController.renderAnnotationInspector(",
    "annotationLogController.readInspectorBboxInputs(",
]


def test_annotation_log_controller_loads_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    log_controller_tag = '<script src="static/annotationLogController.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert log_controller_tag in index_html
    assert script_tag in index_html
    assert index_html.index(log_controller_tag) < index_html.index(script_tag)


def test_main_script_delegates_annotation_log_ui_helpers():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const annotationLogController = window.SAM2AnnotationLogController;" in script_js
    for delegated_call in ANNOTATION_LOG_CALLS:
        assert delegated_call in script_js

    assert "annotationLogBody.innerHTML" not in script_js
    assert "selectedAnnotationSummary.textContent" not in script_js
    assert "logContextMenu.style.left" not in script_js
    assert "logContextMenu.classList.add('hidden')" not in script_js
    assert "document.createElement('tr')" not in script_js


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


def test_annotation_log_controller_exports_expected_dom_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute annotationLogController.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        class FakeElement {
            constructor(tagName = 'div') {
                this.tagName = tagName;
                this.children = [];
                this.dataset = {};
                this.style = {};
                this.value = '';
                this.textContent = '';
                this.disabled = false;
                this.classes = new Set();
                this.classList = {
                    add: className => this.classes.add(className),
                    remove: className => this.classes.delete(className),
                    contains: className => this.classes.has(className)
                };
            }

            set innerHTML(value) {
                this.children = [];
                this._innerHTML = value;
            }

            get innerHTML() {
                return this._innerHTML || '';
            }

            appendChild(child) {
                child.parentElement = this;
                this.children.push(child);
                return child;
            }

            closest(selector) {
                if (selector !== 'tr') return null;
                let element = this;
                while (element) {
                    if (element.tagName === 'tr') return element;
                    element = element.parentElement;
                }
                return null;
            }
        }

        const context = {
            document: {
                createElement(tagName) {
                    return new FakeElement(tagName);
                }
            },
            window: {}
        };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync('static/annotationLogController.js', 'utf8'), context);

        const log = context.window.SAM2AnnotationLogController;
        assert.ok(log);

        const refs = {
            annotationLogBody: new FakeElement('tbody'),
            selectedAnnotationSummary: new FakeElement('div'),
            bboxXInput: new FakeElement('input'),
            bboxYInput: new FakeElement('input'),
            bboxWInput: new FakeElement('input'),
            bboxHInput: new FakeElement('input'),
            applyBoxEditBtn: new FakeElement('button'),
            logContextMenu: new FakeElement('div')
        };

        const annotations = [
            { id: 2, class: 'membrane', bbox: [1.2, 2.6, 3.1, 4.8] },
            { id: 1, class: 'nucleus', bbox: [5, 6, 7, 8] }
        ];
        log.renderAnnotationLog(refs, annotations, new Set([2]));
        assert.strictEqual(refs.annotationLogBody.children.length, 2);
        assert.strictEqual(refs.annotationLogBody.children[0].dataset.annotationId, 1);
        assert.strictEqual(refs.annotationLogBody.children[1].classList.contains('highlighted'), true);
        assert.strictEqual(refs.annotationLogBody.children[1].children[2].textContent, '(1, 3, 3, 5)');

        const state = {
            selectedAnnotationIds: new Set(),
            selectedCandidateIds: new Set([99]),
            logItemToModify: null
        };
        const row = refs.annotationLogBody.children[1];
        assert.strictEqual(log.annotationIdFromRowEvent({ target: row }), 2);
        assert.strictEqual(log.applyLogSelection(state, { target: row }), true);
        assert.strictEqual(state.selectedAnnotationIds.has(2), true);
        assert.strictEqual(state.selectedCandidateIds.size, 0);
        assert.strictEqual(log.applyLogSelection(state, { target: row, ctrlKey: true }), true);
        assert.strictEqual(state.selectedAnnotationIds.has(2), false);

        const prevented = { value: false };
        assert.strictEqual(log.openContextMenu(refs, state, {
            target: row,
            clientX: 11,
            clientY: 22,
            preventDefault() {
                prevented.value = true;
            }
        }), true);
        assert.strictEqual(prevented.value, true);
        assert.strictEqual(state.logItemToModify, 2);
        assert.strictEqual(refs.logContextMenu.style.left, '11px');
        assert.strictEqual(refs.logContextMenu.style.top, '22px');
        assert.strictEqual(refs.logContextMenu.classList.contains('hidden'), false);
        log.hideContextMenu(refs);
        assert.strictEqual(refs.logContextMenu.classList.contains('hidden'), true);

        log.renderAnnotationInspector(refs, [annotations[0]]);
        assert.strictEqual(refs.selectedAnnotationSummary.textContent, '#2 (membrane)');
        assert.strictEqual(refs.applyBoxEditBtn.disabled, false);
        assert.strictEqual(refs.bboxXInput.value, 1);
        assert.strictEqual(refs.bboxYInput.value, 3);
        refs.bboxXInput.value = '10';
        refs.bboxYInput.value = '20';
        refs.bboxWInput.value = '30';
        refs.bboxHInput.value = '40';
        const readBbox = log.readInspectorBboxInputs(refs);
        assert.strictEqual(readBbox.rawValues.join(','), '10,20,30,40');
        assert.strictEqual(readBbox.parsedValues.join(','), '10,20,30,40');
        assert.strictEqual(readBbox.valid, true);

        log.renderAnnotationInspector(refs, []);
        assert.strictEqual(refs.selectedAnnotationSummary.textContent, 'None');
        assert.strictEqual(refs.applyBoxEditBtn.disabled, true);
        assert.strictEqual(refs.bboxXInput.value, '');
        log.renderAnnotationInspector(refs, annotations);
        assert.strictEqual(refs.selectedAnnotationSummary.textContent, '2 selected');
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
