import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


ANNOTATION_CONTROLLER_CALLS = [
    "annotationController.annotationFromCandidate(",
    "annotationController.convertSelectedCandidates(",
    "annotationController.relabelSelectedAnnotations(",
    "annotationController.invalidateMaskGeometryForChanges(",
    "annotationController.undoLastBatch(",
    "annotationController.deleteAnnotationById(",
    "annotationController.selectedAnnotations(",
    "annotationController.countAnnotationsWithClass(",
    "annotationController.countOtherImageAnnotationsWithClass(",
    "annotationController.renameAnnotationClass(",
    "annotationController.deleteAnnotationsWithClass(",
]


def test_annotation_controller_loads_after_codecs_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    codecs_tag = '<script src="static/annotationCodecs.js"></script>'
    controller_tag = '<script src="static/annotationController.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert codecs_tag in index_html
    assert controller_tag in index_html
    assert script_tag in index_html
    assert index_html.index(codecs_tag) < index_html.index(controller_tag)
    assert index_html.index(controller_tag) < index_html.index(script_tag)


def test_main_script_delegates_annotation_mutations_without_duplicate_bodies():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")
    workflow_js = (STATIC_DIR / "annotationWorkflowController.js").read_text(encoding="utf-8")

    assert "const annotationController = window.SAM2AnnotationController;" in script_js
    assert "annotationWorkflowController.normalizeAnnotation(" in script_js
    assert "annotationController.normalizeAnnotation(" in workflow_js
    for delegated_call in ANNOTATION_CONTROLLER_CALLS:
        assert delegated_call in script_js

    assert "convertedAnnotations: [], originalCandidates: []" not in script_js
    assert "const changesById = new Map(lastBatch.changes.map" not in script_js
    assert "const idsToRevert = new Set(lastBatch.convertedAnnotations.map" not in script_js
    assert "annotation.class = newName;" not in script_js


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


def test_annotation_controller_exports_expected_mutation_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute annotationController.js")

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
        vm.runInContext(fs.readFileSync('static/annotationController.js', 'utf8'), context);

        const controller = context.window.SAM2AnnotationController;
        assert.ok(controller);

        const state = {
            annotationCounter: 0,
            selectedCandidateIds: new Set(['cand_1']),
            selectedAnnotationIds: new Set([2])
        };
        const candidates = [
            { id: 'cand_1', bbox: [1, 2, 3, 4], contour: [[1, 2], [4, 2], [4, 6]], mask_area: 12 },
            { id: 'cand_2', bbox: [10, 20, 30, 40] }
        ];
        const annotations = [{ id: 2, bbox: [5, 6, 7, 8], class: 'Old', type: 'loaded' }];
        const history = [];
        const clamp = bbox => bbox.slice();

        const converted = controller.convertSelectedCandidates(
            state,
            candidates,
            annotations,
            history,
            'Nucleus',
            clamp
        );
        assert.strictEqual(converted.count, 1);
        assert.deepStrictEqual(plain(converted.remainingCandidates), [{ id: 'cand_2', bbox: [10, 20, 30, 40] }]);
        assert.strictEqual(state.annotationCounter, 1);
        assert.strictEqual(state.selectedCandidateIds.size, 0);
        assert.strictEqual(history.length, 1);
        assert.deepStrictEqual(plain(annotations.map(annotation => ({
            id: annotation.id,
            bbox: annotation.bbox,
            class: annotation.class,
            type: annotation.type,
            originalCandidateId: annotation.originalCandidateId,
            source: annotation.source
        }))), [
            { id: 2, bbox: [5, 6, 7, 8], class: 'Old', type: 'loaded' },
            {
                id: 1,
                bbox: [1, 2, 3, 4],
                class: 'Nucleus',
                type: 'sam_final',
                originalCandidateId: 'cand_1',
                source: 'sam2'
            }
        ]);

        const relabeledCount = controller.relabelSelectedAnnotations(
            annotations,
            state.selectedAnnotationIds,
            history,
            'Membrane'
        );
        assert.strictEqual(relabeledCount, 1);
        assert.strictEqual(annotations[0].class, 'Membrane');
        assert.strictEqual(history.at(-1).type, 'relabel_annotations');

        let undoMessage = controller.undoLastBatch(annotations, converted.remainingCandidates, history);
        assert.strictEqual(undoMessage, 'Reverted relabeling for 1 annotations.');
        assert.strictEqual(annotations[0].class, 'Old');

        undoMessage = controller.undoLastBatch(annotations, converted.remainingCandidates, history);
        assert.strictEqual(undoMessage, 'Reverted last batch of 1 annotations.');
        assert.deepStrictEqual(plain(annotations), [{ id: 2, bbox: [5, 6, 7, 8], class: 'Old', type: 'loaded' }]);
        assert.strictEqual(converted.remainingCandidates.length, 2);

        history.push({
            type: 'geometry_edit',
            changes: [{ id: 2, oldBbox: [1, 1, 2, 2] }]
        });
        annotations[0].bbox = [9, 9, 9, 9];
        undoMessage = controller.undoLastBatch(annotations, converted.remainingCandidates, history);
        assert.strictEqual(undoMessage, 'Reverted box edit for 1 annotations.');
        assert.deepStrictEqual(plain(annotations[0].bbox), [1, 1, 2, 2]);
        assert.strictEqual(controller.undoLastBatch(annotations, converted.remainingCandidates, history), null);

        const samAnnotation = {
            id: 4,
            bbox: [10, 10, 20, 20],
            class: 'Nucleus',
            type: 'sam_final',
            contour: [[10, 10], [30, 10], [30, 30]],
            mask_area: 275,
            source: 'sam2',
            predicted_iou: 0.93,
            stability_score: 0.97
        };
        const geometryChanges = [{ id: 4, oldBbox: [10, 10, 20, 20], newBbox: [15, 12, 20, 20] }];
        samAnnotation.bbox = geometryChanges[0].newBbox.slice();
        controller.invalidateMaskGeometryForChanges([samAnnotation], geometryChanges);
        assert.strictEqual(samAnnotation.contour, undefined);
        assert.strictEqual(samAnnotation.mask_area, undefined);
        assert.strictEqual(samAnnotation.source, 'sam2');
        assert.strictEqual(samAnnotation.predicted_iou, 0.93);
        assert.deepStrictEqual(plain(geometryChanges[0].oldMaskGeometry), {
            contour: [[10, 10], [30, 10], [30, 30]],
            mask_area: 275
        });

        const geometryHistory = [{ type: 'geometry_edit', changes: geometryChanges }];
        undoMessage = controller.undoLastBatch([samAnnotation], [], geometryHistory);
        assert.strictEqual(undoMessage, 'Reverted box edit for 1 annotations.');
        assert.deepStrictEqual(plain(samAnnotation.bbox), [10, 10, 20, 20]);
        assert.deepStrictEqual(plain(samAnnotation.contour), [[10, 10], [30, 10], [30, 30]]);
        assert.strictEqual(samAnnotation.mask_area, 275);

        const deleteHistory = [{
            type: 'convert_candidates',
            originalCandidates: [{ id: 'cand_3', bbox: [7, 7, 7, 7] }],
            convertedAnnotations: [{ id: 3 }]
        }];
        const deleteAnnotations = [
            { id: 3, bbox: [7, 7, 7, 7], class: 'Nucleus', type: 'sam_final', originalCandidateId: 'cand_3' }
        ];
        const deleteCandidates = [];
        const selectedIds = new Set([3]);
        const deleted = controller.deleteAnnotationById(
            deleteAnnotations,
            deleteCandidates,
            deleteHistory,
            selectedIds,
            3
        );
        assert.strictEqual(deleted.id, 3);
        assert.strictEqual(deleteAnnotations.length, 0);
        assert.deepStrictEqual(plain(deleteCandidates), [{ id: 'cand_3', bbox: [7, 7, 7, 7] }]);
        assert.strictEqual(selectedIds.has(3), false);

        const normalized = controller.normalizeAnnotation(
            state,
            { bbox: [2, 3, 4, 5], class: '  ', contour: [[2, 3], [6, 3], [6, 8]] },
            { width: 100, height: 100 },
            bbox => bbox
        );
        assert.strictEqual(normalized.id, 2);
        assert.strictEqual(normalized.class, 'Unlabeled');
        assert.strictEqual(normalized.type, 'loaded');
        assert.strictEqual(controller.normalizeAnnotation(state, { bbox: [1, 2, 3] }, null, bbox => bbox), null);

        assert.deepStrictEqual(
            plain(controller.selectedAnnotations(
                [{ id: 1 }, { id: 2 }, { id: 3 }],
                new Set([1, 3])
            )),
            [{ id: 1 }, { id: 3 }]
        );

        const annotationsByImage = new Map([
            ['a', [{ class: 'Old' }, { class: 'Other' }]],
            ['b', [{ class: 'Old' }]]
        ]);
        const dirtyImages = new Set();
        assert.strictEqual(controller.countAnnotationsWithClass(annotationsByImage, 'Old'), 2);
        assert.strictEqual(controller.countOtherImageAnnotationsWithClass(annotationsByImage, 'a', 'Old'), 1);
        assert.strictEqual(controller.renameAnnotationClass(annotationsByImage, dirtyImages, 'Old', 'New'), 2);
        assert.deepStrictEqual([...dirtyImages].sort(), ['a', 'b']);
        assert.deepStrictEqual(plain(annotationsByImage.get('a')), [{ class: 'New' }, { class: 'Other' }]);
        assert.deepStrictEqual(
            plain(controller.deleteAnnotationsWithClass(annotationsByImage.get('a'), 'New')),
            { deletedCount: 1, remainingAnnotations: [{ class: 'Other' }] }
        );
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
