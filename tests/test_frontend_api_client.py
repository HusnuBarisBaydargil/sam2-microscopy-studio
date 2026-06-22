import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


def test_api_client_loads_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    api_client_tag = '<script src="static/apiClient.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert api_client_tag in index_html
    assert script_tag in index_html
    assert index_html.index(api_client_tag) < index_html.index(script_tag)


def test_main_script_uses_extracted_api_client_without_duplicate_helpers():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const apiWorkflows = window.SAM2ApiWorkflows;" in script_js
    assert "function apiPath(" not in script_js
    assert "function apiFetch(" not in script_js
    assert "withApiAuthHeaders" not in script_js
    assert "fetchWithApiAuth" not in script_js
    assert "API_TOKEN_STORAGE_KEY" not in script_js
    assert "apiAuthToken" not in script_js


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


def test_api_client_auth_fetch_behavior_matches_existing_contract():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute apiClient.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        class TestHeaders {
            constructor(init = {}) {
                this.values = new Map();
                if (init instanceof TestHeaders) {
                    for (const [key, value] of init.entries()) this.set(key, value);
                } else if (Array.isArray(init)) {
                    for (const [key, value] of init) this.set(key, value);
                } else {
                    for (const [key, value] of Object.entries(init)) this.set(key, value);
                }
            }

            set(key, value) {
                this.values.set(key.toLowerCase(), String(value));
            }

            get(key) {
                return this.values.get(key.toLowerCase()) || null;
            }

            entries() {
                return this.values.entries();
            }
        }

        function response(status, body) {
            return {
                status,
                clone() {
                    return response(status, body);
                },
                async json() {
                    if (body instanceof Error) throw body;
                    return body;
                }
            };
        }

        function loadClient(initialToken = '') {
            const source = fs.readFileSync('static/apiClient.js', 'utf8');
            const sessionStorage = {
                store: new Map(initialToken ? [['sam2AnnotatorApiToken', initialToken]] : []),
                getItem(key) {
                    return this.store.has(key) ? this.store.get(key) : null;
                },
                setItem(key, value) {
                    this.store.set(key, String(value));
                },
                removeItem(key) {
                    this.store.delete(key);
                }
            };
            const context = {
                Headers: TestHeaders,
                sessionStorage,
                window: {
                    prompt() {
                        throw new Error('prompt was not configured');
                    }
                },
                fetch() {
                    throw new Error('fetch was not configured');
                }
            };
            vm.createContext(context);
            vm.runInContext(source, context);
            return context;
        }

        async function main() {
            let context = loadClient();
            assert.strictEqual(context.window.SAM2ApiClient.apiPath('/api/classes'), 'api/classes');
            assert.strictEqual(context.window.SAM2ApiClient.apiPath('api/classes'), 'api/classes');

            let calls = [];
            context.fetch = async (url, init) => {
                calls.push({ url, headers: init.headers });
                return response(200, { ok: true });
            };
            let fetchResponse = await context.window.SAM2ApiClient.apiFetch('/api/classes');
            assert.strictEqual(fetchResponse.status, 200);
            assert.strictEqual(calls.length, 1);
            assert.strictEqual(calls[0].url, 'api/classes');
            assert.strictEqual(calls[0].headers.get('Authorization'), null);
            assert.strictEqual(calls[0].headers.get('X-API-Token'), null);

            context = loadClient('stored-token');
            calls = [];
            context.fetch = async (url, init) => {
                calls.push({ url, headers: init.headers });
                return response(200, { ok: true });
            };
            await context.window.SAM2ApiClient.apiFetch('/api/project/settings');
            assert.strictEqual(calls[0].headers.get('Authorization'), 'Bearer stored-token');
            assert.strictEqual(calls[0].headers.get('X-API-Token'), 'stored-token');

            context = loadClient();
            const prompts = [' entered-token '];
            calls = [];
            context.window.prompt = () => prompts.shift();
            context.fetch = async (url, init) => {
                calls.push({ url, headers: init.headers });
                if (calls.length === 1) return response(401, { auth_required: true });
                return response(200, { ok: true });
            };
            await context.window.SAM2ApiClient.apiFetch('/api/project/settings');
            assert.strictEqual(calls.length, 2);
            assert.strictEqual(calls[0].headers.get('Authorization'), null);
            assert.strictEqual(calls[1].headers.get('Authorization'), 'Bearer entered-token');
            assert.strictEqual(
                context.sessionStorage.getItem('sam2AnnotatorApiToken'),
                'entered-token'
            );

            context = loadClient();
            calls = [];
            context.window.prompt = () => 'bad-token';
            context.fetch = async (url, init) => {
                calls.push({ url, headers: init.headers });
                return response(401, { auth_required: true });
            };
            await assert.rejects(
                () => context.window.SAM2ApiClient.apiFetch('/api/project/settings'),
                /Invalid API token/
            );
            assert.strictEqual(context.sessionStorage.getItem('sam2AnnotatorApiToken'), null);
        }

        main().catch((error) => {
            console.error(error);
            process.exit(1);
        });
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
