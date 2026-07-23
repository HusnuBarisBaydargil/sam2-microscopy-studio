import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


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
    return str(bundled_node) if bundled_node.exists() else None


def test_project_dataset_controller_loads_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")
    codecs_tag = '<script src="static/annotationCodecs.js"></script>'
    controller_tag = '<script src="static/projectDatasetController.js"></script>'
    script_tag = '<script src="static/script.js"></script>'
    assert codecs_tag in index_html
    assert controller_tag in index_html
    assert index_html.index(codecs_tag) < index_html.index(controller_tag) < index_html.index(script_tag)
    assert "const projectDatasetController = window.SAM2ProjectDatasetController;" in script_js
    assert "projectDatasetController.buildProjectCocoExport(" in script_js
    assert "validateProjectDatasetBtn.addEventListener('click', handleValidateProjectDataset);" in script_js
    assert "exportProjectDatasetBtn.addEventListener('click', handleExportProjectDataset);" in script_js


def test_project_dataset_export_is_deterministic_and_validates_failures():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute projectDatasetController.js")

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
        vm.runInContext(fs.readFileSync('static/annotationCodecs.js', 'utf8'), context);
        vm.runInContext(fs.readFileSync('static/projectDatasetController.js', 'utf8'), context);
        const controller = context.window.SAM2ProjectDatasetController;

        const images = [
            { id: 'b', displayPath: 'plate/b.png', width: 100, height: 80 },
            { id: 'a', displayPath: 'plate/a.png', originalImage: { width: 200, height: 120 } }
        ];
        const annotationsByImage = new Map([
            ['a', [{ id: 4, bbox: [10, 10, 20, 30], class: 'nucleus', type: 'manual' }]],
            ['b', []]
        ]);
        const result = controller.buildProjectCocoExport({
            projectId: '617abb01-cea9-48d1-9a8c-660850cd309a',
            schemaVersion: 1,
            taskType: 'bounding_box',
            images,
            annotationsByImage,
            annotationMatchesByImage: new Map(),
            candidateAnnotationsByImage: new Map([['a', [{ id: 'candidate-1' }]]]),
            dirtyImageIds: new Set(['a']),
            classes: [{ id: 9, name: 'nucleus', color: '#39d353', hotkey: 'n' }],
            imageName: image => image.displayPath.split('/').at(-1),
            imagePath: image => image.displayPath,
            normalizeAnnotation: annotation => annotation,
            generatedAt: '2026-07-22T10:00:00.000Z'
        });

        assert.strictEqual(result.validation.valid, true);
        assert.deepStrictEqual(plain(result.dataset.images.map(image => image.file_name)), [
            'plate/a.png',
            'plate/b.png'
        ]);
        assert.deepStrictEqual(plain(result.dataset.categories), [{ id: 9, name: 'nucleus' }]);
        assert.strictEqual(result.dataset.annotations[0].image_id, 1);
        assert.strictEqual(result.dataset.annotations[0].category_id, 9);
        assert.strictEqual(result.dataset.annotations[0].source_annotation_id, 4);
        assert.strictEqual(result.dataset.info.project_id, '617abb01-cea9-48d1-9a8c-660850cd309a');
        assert.strictEqual(result.validation.stats.images, 2);
        assert.strictEqual(result.validation.stats.annotations, 1);
        assert.deepStrictEqual(plain(result.validation.warnings.map(item => item.code)), [
            'unsaved_annotations',
            'unaccepted_candidates',
            'empty_images'
        ]);
        assert.strictEqual(result.fileName, 'sam2_project_617abb01_coco.json');
        assert.ok(controller.validationSummary(result.validation).startsWith('Project dataset valid:'));

        const invalid = controller.buildProjectCocoExport({
            projectId: '',
            schemaVersion: 2,
            taskType: 'segmentation',
            images: [
                { id: 'x', displayPath: 'same.png', originalImage: { width: 10, height: 10 } },
                { id: 'y', displayPath: 'same.png', originalImage: { width: 0, height: 10 } }
            ],
            annotationsByImage: new Map([
                ['x', [
                    { id: 1, bbox: [9, 9, 5, 5], class: 'unknown' },
                    { id: 1, bbox: [1, 1, 2, 2], class: 'unknown' }
                ]]
            ]),
            annotationMatchesByImage: new Map([['x', { status: 'matched' }]]),
            candidateAnnotationsByImage: new Map(),
            dirtyImageIds: new Set(),
            classes: [{ id: 1, name: 'known' }, { id: 1, name: 'duplicate' }],
            imageName: image => image.displayPath,
            imagePath: image => image.displayPath,
            normalizeAnnotation: annotation => annotation,
            generatedAt: '2026-07-22T10:00:00.000Z'
        });
        assert.strictEqual(invalid.validation.valid, false);
        const errorCodes = new Set(invalid.validation.errors.map(item => item.code));
        [
            'project_id',
            'schema_version',
            'task_type',
            'manifest_class_id',
            'source_image_name',
            'source_image_dimensions',
            'source_annotation_id',
            'source_annotation_class',
            'matched_annotations_not_loaded',
            'annotation_bounds'
        ].forEach(code => assert.ok(errorCodes.has(code), code));
        assert.ok(controller.validationSummary(invalid.validation).startsWith('Project validation failed'));

        const malformed = controller.validateCocoDataset({ images: [], categories: [], annotations: [
            { id: 1, image_id: 99, category_id: 99, bbox: [0, 0, -1, 2], area: 0 }
        ] });
        assert.strictEqual(malformed.valid, false);
        assert.ok(malformed.errors.some(item => item.code === 'annotation_image'));
        assert.ok(malformed.errors.some(item => item.code === 'annotation_category'));
        assert.ok(malformed.errors.some(item => item.code === 'annotation_bbox'));

        const polygonOutside = controller.validateCocoDataset({
            images: [{ id: 1, file_name: 'one.png', width: 10, height: 10 }],
            categories: [{ id: 1, name: 'cell' }],
            annotations: [{
                id: 1,
                image_id: 1,
                category_id: 1,
                bbox: [0, 0, 10, 10],
                area: 50,
                segmentation: [[0, 0, 12, 0, 5, 5]]
            }]
        });
        assert.ok(polygonOutside.errors.some(item => item.code === 'annotation_segmentation_bounds'));
        """
    )
    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
