import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


CLASS_UI_CONTROLLER_CALLS = [
    "classUiController.renderClassControls(",
    "classUiController.getClassRowIndex(",
]


def test_class_ui_controller_loads_after_class_manager_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    class_manager_tag = '<script src="static/classManager.js"></script>'
    class_ui_tag = '<script src="static/classUiController.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert class_manager_tag in index_html
    assert class_ui_tag in index_html
    assert script_tag in index_html
    assert index_html.index(class_manager_tag) < index_html.index(class_ui_tag)
    assert index_html.index(class_ui_tag) < index_html.index(script_tag)


def test_main_script_delegates_class_ui_helpers():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const classUiController = window.SAM2ClassUiController;" in script_js
    for delegated_call in CLASS_UI_CONTROLLER_CALLS:
        assert delegated_call in script_js

    controls_js = (STATIC_DIR / "controlsUiController.js").read_text(encoding="utf-8")
    assert "classUiController.syncClassControlStates(" in controls_js

    assert "function renderClassOptions(" not in script_js
    assert "function getClassRowIndex(" not in script_js
    assert "class-empty-state" not in script_js
    assert "Create a class first" not in script_js
    assert "Optional keyboard shortcut" not in script_js


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


def test_class_ui_controller_exports_expected_dom_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute classUiController.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        class FakeElement {
            constructor(tagName) {
                this.tagName = tagName;
                this.children = [];
                this.dataset = {};
                this._className = '';
                this.value = '';
                this.textContent = '';
                this.disabled = false;
                this.checked = false;
            }

            set className(value) {
                this._className = value;
                this.classList = {
                    contains: className => String(value).split(/\s+/).includes(className)
                };
            }

            get className() {
                return this._className;
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
                if (selector !== '.class-row') return null;
                let element = this;
                while (element) {
                    if (element.classList?.contains('class-row')) return element;
                    element = element.parentElement;
                }
                return null;
            }
        }

        const context = {
            window: {},
            document: {
                createElement(tagName) {
                    return new FakeElement(tagName);
                }
            }
        };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync('static/classUiController.js', 'utf8'), context);

        const classUi = context.window.SAM2ClassUiController;
        assert.ok(classUi);

        const classes = [
            { name: 'nucleus', color: '#39d353', hotkey: 'n' },
            { name: 'membrane', color: '#58a6ff', hotkey: '' }
        ];
        assert.strictEqual(classUi.selectedClassName(classes, 'membrane'), 'membrane');
        assert.strictEqual(classUi.selectedClassName(classes, 'missing'), 'nucleus');

        const classManager = new FakeElement('div');
        const classificationSelect = new FakeElement('select');
        classUi.renderClassControls({ classManager, classificationSelect }, classes, 'membrane');

        assert.strictEqual(classManager.children.length, 2);
        assert.strictEqual(classManager.children[0].className, 'class-row');
        assert.strictEqual(classManager.children[0].dataset.classIndex, '0');
        assert.strictEqual(classManager.children[0].children[0].className, 'class-color-input');
        assert.strictEqual(classManager.children[0].children[0].value, '#39d353');
        assert.strictEqual(classManager.children[0].children[1].className, 'class-name-input');
        assert.strictEqual(classManager.children[0].children[1].value, 'nucleus');
        assert.strictEqual(classManager.children[0].children[2].className, 'class-hotkey-input');
        assert.strictEqual(classManager.children[0].children[2].value, 'N');
        assert.strictEqual(classManager.children[0].children[3].className, 'btn btn-secondary class-delete-btn');
        assert.strictEqual(classificationSelect.children.length, 2);
        assert.strictEqual(classificationSelect.children[1].value, 'membrane');
        assert.strictEqual(classificationSelect.value, 'membrane');
        assert.strictEqual(classUi.getClassRowIndex(classManager.children[1].children[3]), 1);
        assert.strictEqual(classUi.getClassRowIndex(new FakeElement('button')), null);

        const emptyClassManager = new FakeElement('div');
        const emptySelect = new FakeElement('select');
        classUi.renderClassControls({ classManager: emptyClassManager, classificationSelect: emptySelect }, [], '');
        assert.strictEqual(emptyClassManager.children.length, 1);
        assert.strictEqual(emptyClassManager.children[0].className, 'class-empty-state');
        assert.strictEqual(emptySelect.children[0].textContent, 'Create a class first');
        assert.strictEqual(emptySelect.value, '');

        const refs = {
            classificationSelect: new FakeElement('select'),
            applyClassificationBtn: new FakeElement('button'),
            oneClickAcceptInput: new FakeElement('input'),
            quickClassInput: new FakeElement('input'),
            quickAddClassBtn: new FakeElement('button')
        };
        refs.oneClickAcceptInput.checked = true;
        classUi.syncClassControlStates(refs, {
            imageLoaded: false,
            selectionExists: true,
            classesExist: false,
            candidatesExist: true
        });
        assert.strictEqual(refs.classificationSelect.disabled, true);
        assert.strictEqual(refs.applyClassificationBtn.disabled, true);
        assert.strictEqual(refs.oneClickAcceptInput.disabled, true);
        assert.strictEqual(refs.oneClickAcceptInput.checked, false);
        assert.strictEqual(refs.quickClassInput.disabled, false);
        assert.strictEqual(refs.quickAddClassBtn.disabled, false);
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
