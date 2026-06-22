import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


EXTRACTED_FILE_UTILITY_FUNCTIONS = [
    "basename",
    "imageExtension",
    "safeImageStem",
    "safePathStem",
    "safeFilePart",
    "stripExtension",
    "annotationFileNames",
    "isSupportedImageFile",
    "imageSortName",
]


def test_file_utils_load_after_config_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    config_tag = '<script src="static/frontendConfig.js"></script>'
    file_utils_tag = '<script src="static/fileUtils.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert config_tag in index_html
    assert file_utils_tag in index_html
    assert script_tag in index_html
    assert index_html.index(config_tag) < index_html.index(file_utils_tag)
    assert index_html.index(file_utils_tag) < index_html.index(script_tag)


def test_main_script_uses_extracted_file_utils_without_duplicate_bodies():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const fileUtils = window.SAM2FileUtils;" in script_js
    for function_name in EXTRACTED_FILE_UTILITY_FUNCTIONS:
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


def test_file_utils_exports_expected_values_and_validation_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute fileUtils.js")

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
        vm.runInContext(fs.readFileSync('static/fileUtils.js', 'utf8'), context);

        const utils = context.window.SAM2FileUtils;
        assert.ok(utils);

        assert.strictEqual(utils.basename('plate/a/cells.TIF'), 'cells.TIF');
        assert.strictEqual(utils.basename('plate\\a\\cells.TIF'), 'cells.TIF');
        assert.strictEqual(utils.imageExtension('cells.TIFF'), '.tiff');
        assert.strictEqual(utils.imageExtension('cells'), '');
        assert.strictEqual(utils.safeFilePart('  plate A / field #1  '), 'plate_A_field_1');
        assert.strictEqual(utils.stripExtension('cells.annotations.csv'), 'cells.annotations');
        assert.strictEqual(utils.safeImageStem('weird cells #1.tif'), 'weird_cells_1');
        assert.strictEqual(utils.safeImageStem('###'), 'image');
        assert.strictEqual(utils.safePathStem('Plate A/Field 01/cells #1.tif'), 'Plate_A__Field_01__cells_1');

        assert.deepStrictEqual(
            plain(utils.annotationFileNames('cells.tif', 'Plate A/cells.tif', 'basename', 'csv')),
            ['cells_annotations.csv']
        );
        assert.deepStrictEqual(
            plain(utils.annotationFileNames('cells.tif', 'Plate A/cells.tif', 'path', 'csv_rich')),
            ['Plate_A__cells_annotations_rich.csv', 'Plate_A__cells_annotations.csv']
        );
        assert.deepStrictEqual(
            plain(utils.annotationFileNames('cells.tif', 'Plate A/cells.tif', 'path', 'yolo')),
            ['Plate_A__cells.txt', 'Plate_A__cells_annotations.txt']
        );
        assert.deepStrictEqual(
            plain(utils.annotationFileNames('cells.tif', 'Plate A/cells.tif', 'path', 'coco')),
            ['Plate_A__cells_annotations.json', 'Plate_A__cells.json']
        );
        assert.deepStrictEqual(
            plain(utils.annotationFileNames('cells.tif', 'Plate A/cells.tif', 'path', 'voc')),
            ['Plate_A__cells.xml', 'Plate_A__cells_annotations.xml']
        );

        const imageRecord = {
            name: 'patient_cells.tif',
            displayPath: 'private/patient_cells.tif',
            publicName: 'image_001.tif',
            publicDisplayPath: 'image_001.tif'
        };
        assert.strictEqual(utils.publicImageName(imageRecord, false), 'patient_cells.tif');
        assert.strictEqual(utils.publicImageName(imageRecord, true), 'image_001.tif');
        assert.strictEqual(utils.publicImagePath(imageRecord, false), 'private/patient_cells.tif');
        assert.strictEqual(utils.publicImagePath(imageRecord, true), 'image_001.tif');
        assert.strictEqual(utils.publicAnnotationPath('annotations/cells.csv', false), 'annotations/cells.csv');
        assert.strictEqual(utils.publicAnnotationPath('annotations/cells.csv', true), 'annotation file');

        assert.strictEqual(utils.isSupportedImageFile({ name: 'cells.tif', type: 'image/tiff' }), true);
        assert.strictEqual(utils.isSupportedImageFile({ name: 'cells.TIFF', type: '' }), true);
        assert.strictEqual(utils.isSupportedImageFile({ name: 'cells.txt', type: 'image/tiff' }), false);
        assert.strictEqual(utils.isSupportedImageFile({ name: 'cells.tif', type: 'text/plain' }), false);
        assert.strictEqual(utils.imageSortName({ name: 'cells.tif', webkitRelativePath: 'Plate B/cells.tif' }), 'Plate B/cells.tif');
        assert.strictEqual(utils.imageSortName({ name: 'cells.tif' }), 'cells.tif');
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
