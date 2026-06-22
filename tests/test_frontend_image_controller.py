import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


IMAGE_CONTROLLER_CALLS = [
    "imageController.createImageRecord(",
    "imageController.loadImageElement(",
    "imageController.getImageBadges(",
    "imageController.imageStateSummary(",
    "imageController.imageDimensions(",
]


def test_image_controller_loads_after_file_utils_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    file_utils_tag = '<script src="static/fileUtils.js"></script>'
    image_controller_tag = '<script src="static/imageController.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert file_utils_tag in index_html
    assert image_controller_tag in index_html
    assert script_tag in index_html
    assert index_html.index(file_utils_tag) < index_html.index(image_controller_tag)
    assert index_html.index(image_controller_tag) < index_html.index(script_tag)


def test_main_script_delegates_image_helpers_without_duplicate_bodies():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")
    workflow_js = (STATIC_DIR / "annotationWorkflowController.js").read_text(encoding="utf-8")

    assert "const imageController = window.SAM2ImageController;" in script_js
    for delegated_call in IMAGE_CONTROLLER_CALLS:
        assert delegated_call in script_js
    assert "imageController.imagePayloads(" in workflow_js

    assert "const publicBaseName = `image_${String(index + 1).padStart(5, '0')}`;" not in script_js
    assert "display_path: imageRecord.displayPath" not in script_js
    assert "SAM has run but no candidates are currently shown" not in script_js
    assert "display/server SAM preprocessing" not in script_js


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


def test_image_controller_exports_expected_image_logic():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute imageController.js")

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
        vm.runInContext(fs.readFileSync('static/imageController.js', 'utf8'), context);

        const controller = context.window.SAM2ImageController;
        assert.ok(controller);

        const file = {
            name: 'cells.TIF',
            webkitRelativePath: 'Plate A/cells.TIF',
            size: 42,
            lastModified: 7
        };
        const imageElement = { width: 100, height: 80 };
        const imageRecord = controller.createImageRecord(file, imageElement, 4);
        assert.deepStrictEqual(plain(imageRecord), {
            id: 'Plate A/cells.TIF:42:7',
            name: 'cells.TIF',
            displayPath: 'Plate A/cells.TIF',
            publicName: 'image_00005.tif',
            publicDisplayPath: 'image_00005.tif',
            file,
            originalImage: imageElement,
            processedImage: null,
            preprocessMethod: 'original',
            preprocessLabel: '',
            preprocessParams: null,
            claheApplied: false,
            samHasRun: false,
            serverAnnotationsChecked: false
        });

        class TestImage {
            set src(value) {
                this._src = value;
                this.onload();
            }

            get src() {
                return this._src;
            }
        }

        async function main() {
            const loadedImage = await controller.loadImageElement('data:image/png;base64,abc', TestImage);
            assert.strictEqual(loadedImage.src, 'data:image/png;base64,abc');

            const context = {
                annotations: [{ id: 1 }, { id: 2 }],
                candidates: [],
                isDirty: true,
                match: { status: 'matched', format: 'csv', path: 'ann/cells.csv', annotation_count: 2 },
                currentAnnotationFormat: () => 'csv',
                formatLabel: format => format.toUpperCase(),
                hasActivePreprocess: () => true,
                preprocessBadgeLabel: method => method.toUpperCase(),
                preprocessLabel: method => method.toUpperCase(),
                publicAnnotationPath: path => `public:${path}`
            };
            const preprocessedRecord = {
                id: 'image-1',
                preprocessMethod: 'clahe',
                samHasRun: true
            };
            const badges = controller.getImageBadges(preprocessedRecord, context);
            assert.deepStrictEqual(plain(badges), [
                { type: 'annotated', label: 'Ann 2', title: '2 annotations' },
                { type: 'dirty', label: 'Unsaved', title: 'Unsaved changes' },
                {
                    type: 'preprocess',
                    label: 'CLAHE',
                    title: 'CLAHE is active for display; SAM applies the same preprocessing on the server'
                },
                { type: 'sam', label: 'SAM 0', title: 'SAM has run but no candidates are currently shown' },
                {
                    type: 'matched',
                    label: 'Matched',
                    title: 'Matched CSV: public:ann/cells.csv (2 annotations)'
                }
            ]);

            assert.strictEqual(
                controller.imageStateSummary(preprocessedRecord, context),
                '2 annotations | 0 candidates | unsaved | CLAHE display/server SAM preprocessing | CSV matched'
            );
            assert.strictEqual(
                controller.imageStateSummary(
                    preprocessedRecord,
                    { ...context, match: { status: 'missing' }, isDirty: false }
                ),
                '2 annotations | 0 candidates | CLAHE display/server SAM preprocessing | CSV missing'
            );

            assert.deepStrictEqual(
                plain(controller.imageDimensions({ originalImage: { width: 10, height: 20 } })),
                { width: 10, height: 20 }
            );
            assert.deepStrictEqual(
                plain(controller.imageDimensions({ processedImage: { width: 30, height: 40 } })),
                { width: 30, height: 40 }
            );
            assert.strictEqual(controller.imageDimensions({ originalImage: { width: 0, height: 20 } }), null);

            assert.deepStrictEqual(
                plain(controller.imagePayloads([
                    { id: 'a', name: 'a.tif', displayPath: 'folder/a.tif', originalImage: { width: 10, height: 20 } },
                    { id: 'b', name: 'b.tif', displayPath: 'folder/b.tif' }
                ])),
                [
                    { id: 'a', name: 'a.tif', display_path: 'folder/a.tif', width: 10, height: 20 },
                    { id: 'b', name: 'b.tif', display_path: 'folder/b.tif', width: null, height: null }
                ]
            );
        }

        main().catch((error) => {
            console.error(error);
            process.exit(1);
        });
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
