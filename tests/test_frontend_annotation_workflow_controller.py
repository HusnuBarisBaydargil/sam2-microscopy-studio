import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


ANNOTATION_WORKFLOW_CALLS = [
    "annotationWorkflowController.refreshServerAnnotationMatches(",
    "annotationWorkflowController.loadServerMatchedAnnotations(",
    "annotationWorkflowController.refreshLocalAnnotationMatches(",
    "annotationWorkflowController.loadLocalMatchedAnnotations(",
    "annotationWorkflowController.importAnnotationFile(",
    "annotationWorkflowController.loadServerAnnotationsForImage(",
    "annotationWorkflowController.saveImageAnnotationsToServer(",
    "annotationWorkflowController.setAnnotationsForImage(",
]


def test_annotation_workflow_controller_loads_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    api_workflows_tag = '<script src="static/apiWorkflows.js"></script>'
    matching_tag = '<script src="static/annotationMatching.js"></script>'
    codecs_tag = '<script src="static/annotationCodecs.js"></script>'
    annotation_controller_tag = '<script src="static/annotationController.js"></script>'
    workflow_tag = '<script src="static/annotationWorkflowController.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert api_workflows_tag in index_html
    assert matching_tag in index_html
    assert codecs_tag in index_html
    assert annotation_controller_tag in index_html
    assert workflow_tag in index_html
    assert script_tag in index_html
    assert index_html.index(api_workflows_tag) < index_html.index(workflow_tag)
    assert index_html.index(matching_tag) < index_html.index(workflow_tag)
    assert index_html.index(codecs_tag) < index_html.index(workflow_tag)
    assert index_html.index(annotation_controller_tag) < index_html.index(workflow_tag)
    assert index_html.index(workflow_tag) < index_html.index(script_tag)


def test_main_script_delegates_annotation_workflows():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const annotationWorkflowController = window.SAM2AnnotationWorkflowController;" in script_js
    for delegated_call in ANNOTATION_WORKFLOW_CALLS:
        assert delegated_call in script_js

    assert "apiWorkflows.matchAnnotations(" not in script_js
    assert "apiWorkflows.bulkLoadAnnotations(" not in script_js
    assert "apiWorkflows.loadAnnotations(" not in script_js
    assert "apiWorkflows.saveAnnotations(" not in script_js
    assert "annotationCodecs.buildAnnotationExport(" not in script_js
    assert "annotationCodecs.parseAnnotationFile(" not in script_js
    assert "annotationController.normalizeAnnotation(" not in script_js
    assert "function resolveLocalAnnotationMatch(" not in script_js
    assert "function countLocalAnnotationFile(" not in script_js
    assert "function updateAnnotationMatchAfterSave(" not in script_js


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


def test_annotation_workflow_controller_updates_state_and_api_payloads():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute annotationWorkflowController.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        function response(data, extra = {}) {
            return {
                ok: extra.ok ?? true,
                status: extra.status ?? 200,
                statusText: extra.statusText ?? 'OK',
                async json() {
                    return data;
                }
            };
        }

        function plain(value) {
            return JSON.parse(JSON.stringify(value));
        }

        const apiCalls = [];
        const apiResponses = {
            matchAnnotations: response({
                results: [{ id: 'img-1', status: 'matched', annotation_count: 2 }],
                summary: { matched: 1, missing: 0, ambiguous: 0 },
                annotation_dir_display: 'annotations'
            }),
            bulkLoadAnnotations: response({
                classes: [{ name: 'nucleus', color: '#39d353', hotkey: 'n' }],
                results: [
                    {
                        id: 'img-1',
                        status: 'matched',
                        annotations: [{ id: 4, bbox: [1, 2, 3, 4], class: 'nucleus' }]
                    }
                ],
                summary: { matched: 1, missing: 0, ambiguous: 0, errors: 0 }
            }),
            loadAnnotations: response({
                exists: true,
                match: { id: 'img-1', status: 'matched', match_mode: 'basename' },
                annotations: [{ id: 5, bbox: [2, 3, 4, 5], class: 'nucleus' }]
            }),
            saveAnnotations: response({
                path: 'annotations/img-1.csv',
                count: 1,
                format: 'csv',
                match_mode: 'basename'
            })
        };

        const context = {
            console,
            URLSearchParams,
            window: {
                SAM2ApiWorkflows: {
                    matchAnnotations(payload) {
                        apiCalls.push(['matchAnnotations', payload]);
                        return Promise.resolve(apiResponses.matchAnnotations);
                    },
                    bulkLoadAnnotations(payload) {
                        apiCalls.push(['bulkLoadAnnotations', payload]);
                        return Promise.resolve(apiResponses.bulkLoadAnnotations);
                    },
                    loadAnnotations(params) {
                        apiCalls.push(['loadAnnotations', Object.fromEntries(params.entries())]);
                        return Promise.resolve(apiResponses.loadAnnotations);
                    },
                    saveAnnotations(payload) {
                        apiCalls.push(['saveAnnotations', payload]);
                        return Promise.resolve(apiResponses.saveAnnotations);
                    }
                }
            }
        };
        vm.createContext(context);
        [
            'static/frontendConfig.js',
            'static/fileUtils.js',
            'static/imageController.js',
            'static/annotationMatching.js',
            'static/annotationCodecs.js',
            'static/annotationController.js',
            'static/annotationWorkflowController.js'
        ].forEach(path => vm.runInContext(fs.readFileSync(path, 'utf8'), context));

        const workflow = context.window.SAM2AnnotationWorkflowController;
        assert.ok(workflow);

        const imageRecord = {
            id: 'img-1',
            name: 'sample.tif',
            displayPath: 'plate/sample.tif',
            originalImage: { width: 100, height: 80 }
        };
        const state = {
            images: [imageRecord],
            projectSettings: {},
            annotationSource: workflow.serverAnnotationSource(),
            annotationMatchesByImage: new Map(),
            matchSummary: null,
            annotationsByImage: new Map(),
            annotationHistoryByImage: new Map(),
            annotationCounter: 0,
            dirtyImages: new Set(),
            selectedAnnotationIds: new Set([9]),
            selectedCandidateIds: new Set([8])
        };

        async function main() {
            assert.strictEqual(workflow.localAnnotationSourceActive(state.annotationSource), false);
            assert.strictEqual(workflow.matchSummaryText(state), 'Annotation matches not checked.');

            const matchData = await workflow.refreshServerAnnotationMatches(state, { format: 'csv' });
            assert.strictEqual(matchData.annotation_dir_display, 'annotations');
            assert.strictEqual(state.annotationMatchesByImage.get('img-1').status, 'matched');
            assert.deepStrictEqual(plain(state.matchSummary), { matched: 1, missing: 0, ambiguous: 0 });
            assert.strictEqual(state.projectSettings.annotationDirDisplay, 'annotations');
            assert.deepStrictEqual(plain(apiCalls[0][1].images[0]), {
                id: 'img-1',
                name: 'sample.tif',
                display_path: 'plate/sample.tif',
                width: 100,
                height: 80
            });

            let appliedClasses = null;
            const loaded = await workflow.loadServerMatchedAnnotations(state, {
                format: 'csv',
                setAnnotationsForImage(record, annotations, options) {
                    assert.strictEqual(record.id, 'img-1');
                    assert.strictEqual(options.markDirty, false);
                    state.annotationsByImage.set(record.id, annotations);
                    return annotations;
                },
                applyLoadedClasses(classes) {
                    appliedClasses = classes;
                }
            });
            assert.strictEqual(loaded.loadedCount, 1);
            assert.strictEqual(loaded.annotationCount, 1);
            assert.strictEqual(imageRecord.serverAnnotationsChecked, true);
            assert.strictEqual(state.dirtyImages.has('img-1'), false);
            assert.strictEqual(appliedClasses[0].name, 'nucleus');

            const loadedSingle = await workflow.loadServerAnnotationsForImage(state, {
                imageRecord,
                imageId: imageRecord.id,
                format: 'csv',
                matchMode: 'basename',
                imageSize: { width: 100, height: 80 }
            });
            assert.strictEqual(loadedSingle.exists, true);
            assert.strictEqual(apiCalls.at(-1)[1].image_width, '100');
            assert.strictEqual(state.annotationMatchesByImage.get('img-1').match_mode, 'basename');

            const saved = await workflow.saveImageAnnotationsToServer(state, {
                imageRecord,
                annotations: [{ id: 4, bbox: [1, 2, 3, 4], class: 'nucleus' }],
                classes: [{ name: 'nucleus' }],
                format: 'csv',
                matchMode: 'basename',
                imageSize: { width: 100, height: 80 },
                display: {
                    name: 'public-sample.tif',
                    displayPath: 'public/sample.tif',
                    annotationPath: path => `public:${path}`
                },
                confirmConflict() {
                    throw new Error('should not ask');
                }
            });
            assert.strictEqual(saved.count, 1);
            assert.strictEqual(apiCalls.at(-1)[0], 'saveAnnotations');
            assert.strictEqual(apiCalls.at(-1)[1].overwrite, true);
            assert.strictEqual(state.annotationMatchesByImage.get('img-1').path, 'public:annotations/img-1.csv');
            assert.strictEqual(state.annotationMatchesByImage.get('img-1').name, 'public-sample.tif');

            const ensured = [];
            const normalized = workflow.setAnnotationsForImage(
                state,
                imageRecord,
                [{ id: 7, bbox: [0, 0, 1, 1], class: 'membrane' }],
                {
                    markDirty: true,
                    normalizeAnnotation(annotation) {
                        return annotation;
                    },
                    ensureClassesForAnnotations(annotations) {
                        ensured.push(...annotations);
                        return 1;
                    },
                    scheduleProjectClassesSave() {
                        state.savedClasses = true;
                    },
                    currentImageId() {
                        return 'img-1';
                    }
                }
            );
            assert.strictEqual(normalized.length, 1);
            assert.strictEqual(state.annotationCounter, 7);
            assert.strictEqual(state.dirtyImages.has('img-1'), true);
            assert.strictEqual(state.selectedAnnotationIds.size, 0);
            assert.strictEqual(state.selectedCandidateIds.size, 0);
            assert.strictEqual(state.savedClasses, true);
            assert.strictEqual(ensured[0].class, 'membrane');
        }

        main().catch(error => {
            console.error(error);
            process.exit(1);
        });
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
