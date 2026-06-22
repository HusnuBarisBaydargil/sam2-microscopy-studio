import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


EXTRACTED_CLASS_FUNCTIONS = [
    "normalizeClassName",
    "normalizeHotkey",
    "getUniqueClassName",
    "getFirstAvailableHotkey",
    "classExists",
    "normalizeClassList",
]


def test_class_manager_loads_after_config_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    config_tag = '<script src="static/frontendConfig.js"></script>'
    class_manager_tag = '<script src="static/classManager.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert config_tag in index_html
    assert class_manager_tag in index_html
    assert script_tag in index_html
    assert index_html.index(config_tag) < index_html.index(class_manager_tag)
    assert index_html.index(class_manager_tag) < index_html.index(script_tag)


def test_main_script_uses_class_manager_without_duplicate_pure_helpers():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const classManagerLogic = window.SAM2ClassManager;" in script_js
    for function_name in EXTRACTED_CLASS_FUNCTIONS:
        assert f"function {function_name}(" not in script_js


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


def test_class_manager_exports_expected_class_logic():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute classManager.js")

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
        vm.runInContext(fs.readFileSync('static/classManager.js', 'utf8'), context);

        const manager = context.window.SAM2ClassManager;
        assert.ok(manager);

        assert.strictEqual(manager.normalizeClassName('  cell    nucleus  '), 'cell nucleus');
        assert.strictEqual(manager.normalizeClassName('   '), '');
        assert.strictEqual(manager.normalizeHotkey(' SHIFT+N '), 's');
        assert.strictEqual(manager.normalizeHotkey(' !9 '), '9');
        assert.strictEqual(manager.normalizeHotkey('***'), '');

        const classes = [
            { name: 'Class 1', color: '#39d353', hotkey: 'c' },
            { name: 'nucleus', color: '#58a6ff', hotkey: 'n' }
        ];
        assert.strictEqual(manager.getUniqueClassName(classes), 'Class 3');
        assert.strictEqual(manager.classExists(classes, 'nucleus'), true);
        assert.strictEqual(manager.classExists(classes, 'cytoplasm'), false);
        assert.strictEqual(manager.getFirstAvailableHotkey('nucleus', classes), 'u');

        const newClass = manager.buildNewClass('cytoplasm', classes);
        assert.deepStrictEqual(plain(newClass), {
            name: 'cytoplasm',
            color: '#58a6ff',
            hotkey: 'y'
        });

        const normalized = manager.normalizeClassList([
            { name: ' nucleus ', color: '#ABCDEF', hotkey: 'N' },
            { name: 'nucleus', color: '#000000', hotkey: 'x' },
            { name: 'membrane', color: 'bad', hotkey: 'n' },
            { name: 'cytoplasm', color: '#123456', hotkey: 'C' },
            { name: '', color: '#ffffff', hotkey: 'z' }
        ]);
        assert.deepStrictEqual(plain(normalized), [
            { name: 'nucleus', color: '#ABCDEF', hotkey: 'n' },
            { name: 'membrane', color: '#58a6ff', hotkey: '' },
            { name: 'cytoplasm', color: '#123456', hotkey: 'c' }
        ]);

        const annotations = [
            { class: ' nucleus ' },
            { class: 'membrane' },
            { class: '' },
            { class: 'membrane' }
        ];
        const ensured = manager.ensureClassesForAnnotations(
            [{ name: 'nucleus', color: '#39d353', hotkey: 'n' }],
            annotations
        );
        assert.strictEqual(ensured.addedCount, 2);
        assert.deepStrictEqual(annotations.map(annotation => annotation.class), [
            'nucleus',
            'membrane',
            'Unlabeled',
            'membrane'
        ]);
        assert.deepStrictEqual(plain(ensured.classes), [
            { name: 'nucleus', color: '#39d353', hotkey: 'n' },
            { name: 'membrane', color: '#9ca3af', hotkey: 'm' },
            { name: 'Unlabeled', color: '#58a6ff', hotkey: 'u' }
        ]);
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
