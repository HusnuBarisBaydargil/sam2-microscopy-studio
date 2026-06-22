import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


def test_modal_keyboard_controller_loads_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    modal_keyboard_tag = '<script src="static/modalKeyboardController.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert modal_keyboard_tag in index_html
    assert script_tag in index_html
    assert index_html.index(modal_keyboard_tag) < index_html.index(script_tag)


def test_main_script_delegates_modal_keyboard_helpers():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const modalKeyboardController = window.SAM2ModalKeyboardController;" in script_js
    assert "modalKeyboardController.visibleModal(" in script_js
    assert "modalKeyboardController.closeVisibleModal(" in script_js
    assert "modalKeyboardController.trapModalFocus(" in script_js

    assert "function visibleModal(" not in script_js
    assert "function closeVisibleModal(" not in script_js
    assert "function focusableElementsIn(" not in script_js
    assert "function trapModalFocus(" not in script_js
    assert "modal.querySelectorAll(" not in script_js


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


def test_modal_keyboard_controller_exports_expected_focus_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute modalKeyboardController.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        class FakeClassList {
            constructor(classes = []) {
                this.classes = new Set(classes);
            }

            add(className) {
                this.classes.add(className);
            }

            remove(className) {
                this.classes.delete(className);
            }

            contains(className) {
                return this.classes.has(className);
            }
        }

        class FakeElement {
            constructor({ hidden = false, disabled = false, visible = true } = {}) {
                this.classList = new FakeClassList(hidden ? ['hidden'] : []);
                this.disabled = disabled;
                this.visible = visible;
                this.focused = false;
                this.focusables = [];
            }

            querySelectorAll() {
                return this.focusables;
            }

            getClientRects() {
                return this.visible ? [{}] : [];
            }

            focus() {
                this.focused = true;
            }
        }

        const context = {
            window: {},
            document: { activeElement: null }
        };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync('static/modalKeyboardController.js', 'utf8'), context);

        const modalKeyboard = context.window.SAM2ModalKeyboardController;
        assert.ok(modalKeyboard);

        const hiddenModal = new FakeElement({ hidden: true });
        const visibleModal = new FakeElement();
        assert.strictEqual(modalKeyboard.visibleModal([hiddenModal, null, visibleModal]), visibleModal);
        assert.strictEqual(modalKeyboard.visibleModal([hiddenModal]), null);

        let closed = '';
        assert.strictEqual(modalKeyboard.closeVisibleModal(visibleModal, [
            { modal: hiddenModal, close: () => { closed = 'hidden'; } },
            { modal: visibleModal, close: () => { closed = 'visible'; } }
        ]), true);
        assert.strictEqual(closed, 'visible');
        assert.strictEqual(modalKeyboard.closeVisibleModal(visibleModal, []), false);

        const first = new FakeElement();
        const disabled = new FakeElement({ disabled: true });
        const invisible = new FakeElement({ visible: false });
        const last = new FakeElement();
        visibleModal.focusables = [first, disabled, invisible, last];
        const focusable = modalKeyboard.focusableElementsIn(visibleModal);
        assert.strictEqual(focusable.length, 2);
        assert.strictEqual(focusable[0], first);
        assert.strictEqual(focusable[1], last);

        let prevented = 0;
        const tabEvent = {
            key: 'Tab',
            shiftKey: false,
            preventDefault() {
                prevented++;
            }
        };

        context.document.activeElement = last;
        assert.strictEqual(modalKeyboard.trapModalFocus(tabEvent, visibleModal, context.document), true);
        assert.strictEqual(prevented, 1);
        assert.strictEqual(first.focused, true);

        first.focused = false;
        last.focused = false;
        context.document.activeElement = first;
        assert.strictEqual(modalKeyboard.trapModalFocus({
            key: 'Tab',
            shiftKey: true,
            preventDefault() {
                prevented++;
            }
        }, visibleModal, context.document), true);
        assert.strictEqual(prevented, 2);
        assert.strictEqual(last.focused, true);

        const emptyModal = new FakeElement();
        emptyModal.focusables = [];
        assert.strictEqual(modalKeyboard.trapModalFocus({
            key: 'Tab',
            shiftKey: false,
            preventDefault() {
                prevented++;
            }
        }, emptyModal, context.document), true);
        assert.strictEqual(prevented, 3);
        assert.strictEqual(emptyModal.focused, true);

        assert.strictEqual(modalKeyboard.trapModalFocus({ key: 'Escape' }, visibleModal, context.document), false);
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
