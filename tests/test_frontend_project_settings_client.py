import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


EXTRACTED_SETTINGS_FUNCTIONS = [
    "preprocessLabel",
    "preprocessBadgeLabel",
    "hasActivePreprocess",
    "normalizeSamSettingsForClient",
    "normalizeSamDeviceForClient",
    "samDeviceLabel",
    "samDeviceTitle",
    "samRiskWarnings",
    "samParamsEqual",
]


def test_project_settings_client_loads_after_codecs_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    config_tag = '<script src="static/frontendConfig.js"></script>'
    codecs_tag = '<script src="static/annotationCodecs.js"></script>'
    settings_tag = '<script src="static/projectSettingsClient.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert config_tag in index_html
    assert codecs_tag in index_html
    assert settings_tag in index_html
    assert script_tag in index_html
    assert index_html.index(config_tag) < index_html.index(settings_tag)
    assert index_html.index(codecs_tag) < index_html.index(settings_tag)
    assert index_html.index(settings_tag) < index_html.index(script_tag)


def test_main_script_uses_project_settings_client_without_duplicate_bodies():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const projectSettingsClient = window.SAM2ProjectSettingsClient;" in script_js
    for function_name in EXTRACTED_SETTINGS_FUNCTIONS:
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


def test_project_settings_client_exports_expected_normalization_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute projectSettingsClient.js")

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
        vm.runInContext(fs.readFileSync('static/projectSettingsClient.js', 'utf8'), context);

        const settings = context.window.SAM2ProjectSettingsClient;
        assert.ok(settings);

        assert.strictEqual(settings.preprocessLabel('clahe'), 'CLAHE');
        assert.strictEqual(settings.preprocessLabel('missing'), 'Preprocessing');
        assert.strictEqual(settings.preprocessBadgeLabel('clahe_unsharp'), 'CLAHE+USM');
        assert.strictEqual(settings.normalizePreprocessParams({ gamma: 2 }).gamma, 2);
        assert.strictEqual(settings.normalizePreprocessParams({ gamma: 2 }).retinex_strength, 0.55);
        assert.strictEqual(settings.numberFromValue('2.5', 1), 2.5);
        assert.strictEqual(settings.numberFromValue('bad', 1), 1);

        const inactiveImage = { preprocessMethod: 'original', processedImage: { width: 10 } };
        const activeImage = {
            preprocessMethod: 'gamma',
            preprocessParams: { gamma: 1.7 },
            processedImage: { width: 10 }
        };
        assert.strictEqual(settings.hasActivePreprocess(inactiveImage), false);
        assert.strictEqual(settings.hasActivePreprocess(activeImage), true);
        assert.deepStrictEqual(
            plain(settings.samPreprocessPayload(inactiveImage, { gamma: 1.2 })),
            { method: 'original', params: {} }
        );
        assert.deepStrictEqual(
            plain(settings.samPreprocessPayload(activeImage, { gamma: 1.2 })),
            { method: 'gamma', params: { gamma: 1.7 } }
        );

        const samSettings = settings.normalizeSamSettingsForClient({
            preset: 'custom',
            params: { points_per_side: 80, area_mode: 'percent' },
            warnings: ['server warning']
        });
        assert.strictEqual(samSettings.preset, 'custom');
        assert.strictEqual(samSettings.params.points_per_side, 80);
        assert.strictEqual(samSettings.params.crop_n_layers, 2);
        assert.strictEqual(samSettings.params.area_mode, 'percent');
        assert.deepStrictEqual(plain(samSettings.warnings), ['server warning']);

        const device = settings.normalizeSamDeviceForClient({
            mode: 'auto',
            active: 'cuda',
            cuda_available: true,
            ready: true,
            model_load_skipped: false
        });
        assert.deepStrictEqual(plain(device), {
            mode: 'auto',
            active: 'cuda',
            cudaAvailable: true,
            ready: true,
            modelLoadSkipped: false,
            error: ''
        });
        assert.strictEqual(settings.samDeviceLabel(device), 'Auto -> CUDA');
        assert.strictEqual(settings.samDeviceTitle(device), 'SAM2 is running with CUDA acceleration.');
        assert.deepStrictEqual(plain(settings.samDeviceReadiness(device)), {
            level: 'ready',
            text: 'SAM2 is ready with CUDA acceleration.'
        });
        assert.strictEqual(settings.samDeviceLabel({ ...device, error: 'boom' }), 'Needs attention');
        assert.strictEqual(settings.samDeviceTitle({ ...device, error: 'boom' }), 'boom');
        assert.deepStrictEqual(plain(settings.samDeviceReadiness({ ...device, error: 'boom' })), {
            level: 'error',
            text: 'SAM2 needs attention: boom'
        });
        assert.deepStrictEqual(plain(settings.samDeviceReadiness({ ...device, active: 'cpu', ready: true })), {
            level: 'warning',
            text: 'SAM2 is ready but running on CPU. Candidate generation may be slow.'
        });
        assert.deepStrictEqual(plain(settings.samDeviceReadiness({ ...device, modelLoadSkipped: true, ready: false })), {
            level: 'error',
            text: 'SAM2 candidate generation is unavailable in this session.'
        });

        const riskWarnings = settings.samRiskWarnings(
            {
                points_per_side: 128,
                crop_n_layers: 3,
                points_per_batch: 256,
                pred_iou_thresh: 0.7,
                stability_score_thresh: 0.7
            },
            { originalImage: { width: 2200, height: 1600 } }
        );
        assert.strictEqual(riskWarnings.length, 6);
        assert.ok(riskWarnings.some(message => message.includes('Large image')));

        assert.strictEqual(
            settings.samParamsEqual({ points_per_side: 64.00001 }, { points_per_side: 64 }),
            true
        );
        assert.strictEqual(
            settings.samParamsEqual({ points_per_side: 65 }, { points_per_side: 64 }),
            false
        );

        const presets = settings.normalizeSamPresets([{ key: 'fast', params: { points_per_side: 32 } }]);
        assert.strictEqual(presets[0].params.points_per_side, 32);
        assert.strictEqual(presets[0].params.crop_n_layers, 2);
        assert.strictEqual(settings.normalizeSamPresets([]), null);

        const normalizedProjectSettings = settings.normalizeProjectSettingsForClient(
            {
                annotation_output_dir: 'labels',
                annotation_dir_display: 'labels',
                annotation_format: 'coco',
                privacy: { phi_safe_mode: true, salt_configured: true },
                sam_settings: { params: { points_per_side: 48 } },
                sam_device: { mode: 'cpu', active: 'cpu', ready: true }
            },
            { annotationFormat: 'csv' }
        );
        assert.strictEqual(normalizedProjectSettings.annotationOutputDir, 'labels');
        assert.strictEqual(normalizedProjectSettings.annotationFormat, 'coco');
        assert.strictEqual(normalizedProjectSettings.privacy.phiSafeMode, true);
        assert.strictEqual(normalizedProjectSettings.samSettings.params.points_per_side, 48);
        assert.strictEqual(normalizedProjectSettings.samDevice.mode, 'cpu');
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
