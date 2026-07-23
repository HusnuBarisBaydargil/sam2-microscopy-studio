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
    "annotationController.recordHistoryCommand(",
    "annotationController.groupHistoryCommands(",
    "annotationController.undoLastAction(",
    "annotationController.redoLastAction(",
    "annotationController.deleteAnnotationsByIds(",
    "annotationController.selectedAnnotations(",
    "annotationController.countAnnotationsWithClass(",
    "annotationController.countOtherImageAnnotationsWithClass(",
    "annotationController.renameAnnotationClass(",
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
        const redoHistory = [];
        const clamp = bbox => bbox.slice();

        const converted = controller.convertSelectedCandidates(
            state,
            candidates,
            annotations,
            history,
            redoHistory,
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
            redoHistory,
            'Membrane'
        );
        assert.strictEqual(relabeledCount, 1);
        assert.strictEqual(annotations[0].class, 'Membrane');
        assert.strictEqual(history.at(-1).type, 'relabel_annotations');

        let undoMessage = controller.undoLastAction(annotations, converted.remainingCandidates, history, redoHistory);
        assert.strictEqual(undoMessage, 'Undid relabeling 1 annotation.');
        assert.strictEqual(annotations[0].class, 'Old');

        undoMessage = controller.undoLastAction(annotations, converted.remainingCandidates, history, redoHistory);
        assert.strictEqual(undoMessage, 'Undid acceptance of 1 annotation.');
        assert.deepStrictEqual(plain(annotations), [{ id: 2, bbox: [5, 6, 7, 8], class: 'Old', type: 'loaded' }]);
        assert.strictEqual(converted.remainingCandidates.length, 2);

        let redoMessage = controller.redoLastAction(annotations, converted.remainingCandidates, history, redoHistory);
        assert.strictEqual(redoMessage, 'Redid acceptance of 1 annotation.');
        assert.strictEqual(annotations.length, 2);
        assert.strictEqual(converted.remainingCandidates.length, 1);
        redoMessage = controller.redoLastAction(annotations, converted.remainingCandidates, history, redoHistory);
        assert.strictEqual(redoMessage, 'Redid relabeling 1 annotation.');
        assert.strictEqual(annotations[0].class, 'Membrane');

        controller.recordHistoryCommand(history, redoHistory, {
            type: 'geometry_edit',
            changes: [{ id: 2, oldBbox: [1, 1, 2, 2], newBbox: [9, 9, 9, 9] }]
        });
        annotations[0].bbox = [9, 9, 9, 9];
        undoMessage = controller.undoLastAction(annotations, converted.remainingCandidates, history, redoHistory);
        assert.strictEqual(undoMessage, 'Undid box edit for 1 annotation.');
        assert.deepStrictEqual(plain(annotations[0].bbox), [1, 1, 2, 2]);
        redoMessage = controller.redoLastAction(annotations, converted.remainingCandidates, history, redoHistory);
        assert.strictEqual(redoMessage, 'Redid box edit for 1 annotation.');
        assert.deepStrictEqual(plain(annotations[0].bbox), [9, 9, 9, 9]);

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
        const geometryRedo = [];
        undoMessage = controller.undoLastAction([samAnnotation], [], geometryHistory, geometryRedo);
        assert.strictEqual(undoMessage, 'Undid box edit for 1 annotation.');
        assert.deepStrictEqual(plain(samAnnotation.bbox), [10, 10, 20, 20]);
        assert.deepStrictEqual(plain(samAnnotation.contour), [[10, 10], [30, 10], [30, 30]]);
        assert.strictEqual(samAnnotation.mask_area, 275);
        redoMessage = controller.redoLastAction([samAnnotation], [], geometryHistory, geometryRedo);
        assert.strictEqual(redoMessage, 'Redid box edit for 1 annotation.');
        assert.deepStrictEqual(plain(samAnnotation.bbox), [15, 12, 20, 20]);
        assert.strictEqual(samAnnotation.contour, undefined);
        assert.strictEqual(samAnnotation.mask_area, undefined);

        const deleteHistory = [{
            type: 'convert_candidates',
            candidateRecords: [{ item: { id: 'cand_3', bbox: [7, 7, 7, 7] }, index: 0 }],
            annotationRecords: [{ item: { id: 3 }, index: 0 }]
        }];
        const deleteAnnotations = [
            { id: 3, bbox: [7, 7, 7, 7], class: 'Nucleus', type: 'sam_final', originalCandidateId: 'cand_3' }
        ];
        const deleteCandidates = [];
        const deleteRedo = [];
        const selectedIds = new Set([3]);
        const deleted = controller.deleteAnnotationsByIds(
            deleteAnnotations,
            deleteCandidates,
            deleteHistory,
            deleteRedo,
            selectedIds,
            [3]
        );
        assert.strictEqual(deleted[0].id, 3);
        assert.strictEqual(deleteAnnotations.length, 0);
        assert.deepStrictEqual(plain(deleteCandidates), [{ id: 'cand_3', bbox: [7, 7, 7, 7] }]);
        assert.strictEqual(selectedIds.has(3), false);
        undoMessage = controller.undoLastAction(deleteAnnotations, deleteCandidates, deleteHistory, deleteRedo);
        assert.strictEqual(undoMessage, 'Undid deletion of 1 annotation.');
        assert.strictEqual(deleteAnnotations[0].id, 3);
        assert.strictEqual(deleteCandidates.length, 0);
        redoMessage = controller.redoLastAction(deleteAnnotations, deleteCandidates, deleteHistory, deleteRedo);
        assert.strictEqual(redoMessage, 'Redid deletion of 1 annotation.');
        assert.strictEqual(deleteAnnotations.length, 0);
        assert.strictEqual(deleteCandidates.length, 1);

        const creationHistory = [];
        const creationRedo = [{ type: 'obsolete' }];
        const manualAnnotation = { id: 8, bbox: [1, 1, 5, 5], class: 'Nucleus', type: 'manual' };
        const manualAnnotations = [manualAnnotation];
        controller.recordHistoryCommand(creationHistory, creationRedo, {
            type: 'create_annotations',
            annotationRecords: [{ item: manualAnnotation, index: 0 }]
        });
        assert.strictEqual(creationRedo.length, 0);
        controller.undoLastAction(manualAnnotations, [], creationHistory, creationRedo);
        assert.strictEqual(manualAnnotations.length, 0);
        controller.redoLastAction(manualAnnotations, [], creationHistory, creationRedo);
        assert.strictEqual(manualAnnotations[0].id, 8);

        const importedAnnotation = { id: 12, bbox: [9, 9, 3, 3], class: 'Imported' };
        const replacedAnnotations = [importedAnnotation];
        const replacementHistory = [{
            type: 'replace_annotations',
            beforeRecords: [{ item: manualAnnotation, index: 0 }],
            afterRecords: [{ item: importedAnnotation, index: 0 }]
        }];
        const replacementRedo = [];
        undoMessage = controller.undoLastAction(
            replacedAnnotations,
            [],
            replacementHistory,
            replacementRedo
        );
        assert.strictEqual(undoMessage, 'Undid annotation import.');
        assert.deepStrictEqual(plain(replacedAnnotations), [plain(manualAnnotation)]);
        redoMessage = controller.redoLastAction(
            replacedAnnotations,
            [],
            replacementHistory,
            replacementRedo
        );
        assert.strictEqual(redoMessage, 'Redid annotation import.');
        assert.deepStrictEqual(plain(replacedAnnotations), [plain(importedAnnotation)]);

        const compoundAnnotation = { id: 9, bbox: [5, 5, 8, 8], class: 'New' };
        const compoundHistory = [
            {
                type: 'relabel_annotations',
                changes: [{ id: 9, oldClass: 'Old', newClass: 'New' }]
            },
            {
                type: 'geometry_edit',
                changes: [{ id: 9, oldBbox: [1, 1, 4, 4], newBbox: [5, 5, 8, 8] }]
            }
        ];
        const compoundRedo = [];
        controller.groupHistoryCommands(compoundHistory, 0, 'combined edit');
        assert.strictEqual(compoundHistory.length, 1);
        assert.strictEqual(compoundHistory[0].type, 'compound');
        undoMessage = controller.undoLastAction([compoundAnnotation], [], compoundHistory, compoundRedo);
        assert.strictEqual(undoMessage, 'Undid combined edit.');
        assert.strictEqual(compoundAnnotation.class, 'Old');
        assert.deepStrictEqual(plain(compoundAnnotation.bbox), [1, 1, 4, 4]);
        redoMessage = controller.redoLastAction([compoundAnnotation], [], compoundHistory, compoundRedo);
        assert.strictEqual(redoMessage, 'Redid combined edit.');
        assert.strictEqual(compoundAnnotation.class, 'New');
        assert.deepStrictEqual(plain(compoundAnnotation.bbox), [5, 5, 8, 8]);

        const classHistory = [{
            type: 'remove_class',
            classRecord: { item: { name: 'Nucleus', color: '#ffffff', hotkey: 'n' }, index: 0 }
        }];
        const classRedo = [];
        const projectClasses = [];
        controller.undoLastAction([], [], classHistory, classRedo, projectClasses);
        assert.deepStrictEqual(plain(projectClasses), [{ name: 'Nucleus', color: '#ffffff', hotkey: 'n' }]);
        controller.redoLastAction([], [], classHistory, classRedo, projectClasses);
        assert.deepStrictEqual(plain(projectClasses), []);

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
