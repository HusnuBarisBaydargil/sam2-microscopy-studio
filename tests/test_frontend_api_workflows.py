import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


WORKFLOW_CALLS = [
    "apiWorkflows.loadImage(",
    "apiWorkflows.loadImageInfo(",
    "apiWorkflows.preprocessImage(",
    "apiWorkflows.runSam(",
    "apiWorkflows.saveProjectSettings(",
    "apiWorkflows.loadProjectSettings(",
    "apiWorkflows.matchAnnotations(",
    "apiWorkflows.bulkLoadAnnotations(",
    "apiWorkflows.loadAnnotations(",
    "apiWorkflows.saveAnnotations(",
    "apiWorkflows.loadClasses(",
    "apiWorkflows.saveClasses(",
]


def test_api_workflows_loads_after_api_client_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    api_client_tag = '<script src="static/apiClient.js"></script>'
    api_workflows_tag = '<script src="static/apiWorkflows.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert api_client_tag in index_html
    assert api_workflows_tag in index_html
    assert script_tag in index_html
    assert index_html.index(api_client_tag) < index_html.index(api_workflows_tag)
    assert index_html.index(api_workflows_tag) < index_html.index(script_tag)


def test_main_script_delegates_endpoint_requests_to_api_workflows():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")
    workflow_js = (STATIC_DIR / "annotationWorkflowController.js").read_text(encoding="utf-8")
    frontend_controller_js = script_js + workflow_js

    assert "const apiWorkflows = window.SAM2ApiWorkflows;" in script_js
    for workflow_call in WORKFLOW_CALLS:
        assert workflow_call in frontend_controller_js

    assert "apiFetch(" not in frontend_controller_js
    assert "apiPath(" not in frontend_controller_js


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


def test_api_workflows_build_expected_requests():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute apiWorkflows.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        class TestFormData {
            constructor() {
                this.fields = [];
            }

            append(name, value, filename) {
                this.fields.push([name, value, filename]);
            }
        }

        const calls = [];
        const context = {
            FormData: TestFormData,
            URLSearchParams,
            window: {
                SAM2ApiClient: {
                    apiPath(path) {
                        return path.replace(/^\//, '');
                    },
                    apiFetch(url, init = {}) {
                        calls.push({ url, init });
                        return Promise.resolve({ ok: true });
                    }
                }
            }
        };
        vm.createContext(context);
        vm.runInContext(fs.readFileSync('static/apiWorkflows.js', 'utf8'), context);

        const workflows = context.window.SAM2ApiWorkflows;
        assert.ok(workflows);

        async function main() {
            await workflows.loadImage('image-file');
            assert.strictEqual(calls.at(-1).url, 'api/load_image');
            assert.strictEqual(calls.at(-1).init.method, 'POST');
            assert.deepStrictEqual(calls.at(-1).init.body.fields, [['image', 'image-file', undefined]]);

            await workflows.loadImageInfo('image-file');
            assert.strictEqual(calls.at(-1).url, 'api/image_info');
            assert.strictEqual(calls.at(-1).init.method, 'POST');
            assert.deepStrictEqual(calls.at(-1).init.body.fields, [['image', 'image-file', undefined]]);

            await workflows.preprocessImage({
                file: 'image-file',
                method: 'clahe',
                params: { gamma: 1.2 }
            });
            assert.strictEqual(calls.at(-1).url, 'api/preprocess');
            assert.deepStrictEqual(calls.at(-1).init.body.fields, [
                ['image', 'image-file', undefined],
                ['method', 'clahe', undefined],
                ['params', '{"gamma":1.2}', undefined]
            ]);

            await workflows.runSam({
                file: 'image-file',
                imageName: 'sample.tif',
                samSettings: { preset: 'custom' },
                preprocessMethod: 'gamma',
                preprocessParams: { gamma: 1.1 }
            });
            assert.strictEqual(calls.at(-1).url, 'api/run_sam');
            assert.deepStrictEqual(calls.at(-1).init.body.fields, [
                ['image', 'image-file', 'sample.tif'],
                ['sam_settings', '{"preset":"custom"}', undefined],
                ['preprocess_method', 'gamma', undefined],
                ['preprocess_params', '{"gamma":1.1}', undefined]
            ]);

            await workflows.saveProjectSettings({ annotation_format: 'coco' });
            assert.strictEqual(calls.at(-1).url, 'api/project/settings');
            assert.strictEqual(calls.at(-1).init.method, 'POST');
            assert.strictEqual(calls.at(-1).init.headers['Content-Type'], 'application/json');
            assert.strictEqual(calls.at(-1).init.body, '{"annotation_format":"coco"}');

            await workflows.loadProjectSettings();
            assert.strictEqual(calls.at(-1).url, 'api/project/settings');
            assert.deepStrictEqual(calls.at(-1).init, {});

            await workflows.matchAnnotations({ images: [{ id: 'one' }], format: 'csv' });
            assert.strictEqual(calls.at(-1).url, 'api/annotations/match');
            assert.strictEqual(calls.at(-1).init.body, '{"images":[{"id":"one"}],"format":"csv"}');

            await workflows.bulkLoadAnnotations({ images: [{ id: 'one' }], format: 'coco' });
            assert.strictEqual(calls.at(-1).url, 'api/annotations/bulk_load');
            assert.strictEqual(calls.at(-1).init.body, '{"images":[{"id":"one"}],"format":"coco"}');

            await workflows.loadAnnotations({
                image_name: 'sample.tif',
                image_path: 'folder/sample.tif',
                format: 'csv'
            });
            assert.strictEqual(
                calls.at(-1).url,
                'api/annotations/load?image_name=sample.tif&image_path=folder%2Fsample.tif&format=csv'
            );

            await workflows.saveAnnotations({ image_name: 'sample.tif', annotations: [] });
            assert.strictEqual(calls.at(-1).url, 'api/annotations/save');
            assert.strictEqual(calls.at(-1).init.body, '{"image_name":"sample.tif","annotations":[]}');

            await workflows.loadClasses();
            assert.strictEqual(calls.at(-1).url, 'api/classes');
            assert.deepStrictEqual(calls.at(-1).init, {});

            await workflows.saveClasses([{ name: 'Nucleus' }]);
            assert.strictEqual(calls.at(-1).url, 'api/classes');
            assert.strictEqual(calls.at(-1).init.body, '{"classes":[{"name":"Nucleus"}]}');
        }

        main().catch((error) => {
            console.error(error);
            process.exit(1);
        });
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
