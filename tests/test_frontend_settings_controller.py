import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


SETTINGS_CONTROLLER_CALLS = [
    "settingsController.selectedPreprocessMethod(",
    "settingsController.currentPreprocessParams(",
    "settingsController.samPreprocessPayload(",
    "settingsController.readPreprocessSettingsFromInputs(",
    "settingsController.syncPreprocessSettingsInputs(",
    "settingsController.defaultPreprocessParams(",
    "settingsController.readSamSettingsFromInputs(",
    "settingsController.syncSamSettingsInputs(",
    "settingsController.samSettingsForPresetChange(",
    "settingsController.samSettingsForInputChange(",
    "settingsController.currentSamSettingsPayload(",
    "settingsController.normalizeAndStoreSamSettings(",
    "settingsController.currentSamParams(",
    "settingsController.samRiskState(",
    "settingsController.currentSamPresetLabel(",
    "settingsController.findSamPreset(",
    "settingsController.normalizeAndStoreProjectSettings(",
    "settingsController.currentAnnotationFormat(",
]


def test_settings_controller_loads_after_project_settings_client_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    project_settings_tag = '<script src="static/projectSettingsClient.js"></script>'
    settings_controller_tag = '<script src="static/settingsController.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert project_settings_tag in index_html
    assert settings_controller_tag in index_html
    assert script_tag in index_html
    assert index_html.index(project_settings_tag) < index_html.index(settings_controller_tag)
    assert index_html.index(settings_controller_tag) < index_html.index(script_tag)


def test_main_script_delegates_settings_form_and_state_logic():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")
    sam_ui_js = (STATIC_DIR / "samSettingsUiController.js").read_text(encoding="utf-8")
    settings_callers_js = script_js + sam_ui_js

    assert "const settingsController = window.SAM2SettingsController;" in script_js
    for delegated_call in SETTINGS_CONTROLLER_CALLS:
        assert delegated_call in settings_callers_js

    assert "DEFAULT_PREPROCESS_PARAMS" not in script_js
    assert "samParamsEqual" not in script_js
    assert "normalizeSamSettingsForClient" not in script_js
    assert "samRiskWarnings(" not in script_js
    assert "normalizeProjectSettingsForClient" not in script_js


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


def test_settings_controller_exports_expected_settings_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute settingsController.js")

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
        vm.runInContext(fs.readFileSync('static/settingsController.js', 'utf8'), context);

        const settings = context.window.SAM2SettingsController;
        assert.ok(settings);

        assert.strictEqual(settings.selectedPreprocessMethod({ value: '' }), 'original');
        assert.strictEqual(settings.selectedPreprocessMethod({ value: 'clahe' }), 'clahe');
        assert.strictEqual(settings.numberFromInput({ value: '2.5' }, 1), 2.5);
        assert.strictEqual(settings.numberFromInput({ value: 'bad' }, 1), 1);

        const preprocessRefs = {
            preprocessClaheClipInput: { value: '3.5' },
            preprocessClaheTileInput: { value: '12' },
            preprocessGammaInput: { value: '1.8' },
            preprocessUnsharpAmountInput: { value: '2.1' },
            preprocessUnsharpRadiusInput: { value: '1.4' },
            preprocessUnsharpThresholdInput: { value: 'bad' },
            preprocessRetinexStrengthInput: { value: '0.7' }
        };
        assert.deepStrictEqual(plain(settings.readPreprocessSettingsFromInputs(preprocessRefs)), {
            clahe_clip_limit: 3.5,
            clahe_tile_grid_size: 12,
            gamma: 1.8,
            unsharp_amount: 2.1,
            unsharp_radius: 1.4,
            unsharp_threshold: 3,
            retinex_strength: 0.7
        });
        settings.syncPreprocessSettingsInputs(preprocessRefs, settings.defaultPreprocessParams());
        assert.strictEqual(preprocessRefs.preprocessGammaInput.value, 1.2);

        const projectSettings = { preprocessParams: { gamma: 1.6 } };
        assert.strictEqual(settings.currentPreprocessParams(projectSettings).gamma, 1.6);
        assert.deepStrictEqual(
            plain(settings.samPreprocessPayload(
                { preprocessMethod: 'gamma', preprocessParams: { gamma: 1.6 }, processedImage: {} },
                settings.currentPreprocessParams(projectSettings)
            )),
            { method: 'gamma', params: { gamma: 1.6 } }
        );

        const samRefs = {
            samPresetSelect: { value: 'cell_1920x1440' },
            samPointsPerSideInput: { value: '80' },
            samCropLayersInput: { value: '3' },
            samMinMaskRegionAreaInput: { value: '4' },
            samCropOverlapInput: { value: '0.5' },
            samCropDownscaleInput: { value: '2' },
            samPointsPerBatchInput: { value: '128' },
            samPredIouInput: { value: '0.91' },
            samStabilityInput: { value: '0.95' },
            samStabilityOffsetInput: { value: '1.1' },
            samBoxNmsInput: { value: '0.6' },
            samCropNmsInput: { value: '0.7' },
            samUseM2mInput: { checked: true },
            samAreaModeSelect: { value: 'percent' },
            samMinObjectAreaInput: { value: '0.2' },
            samMaxObjectAreaInput: { value: '80' }
        };
        const samSettings = settings.readSamSettingsFromInputs(samRefs);
        assert.strictEqual(samSettings.preset, 'cell_1920x1440');
        assert.strictEqual(samSettings.params.points_per_side, 80);
        assert.strictEqual(samSettings.params.area_mode, 'percent');
        assert.strictEqual(samSettings.params.use_m2m, true);

        settings.syncSamSettingsInputs(samRefs, {
            points_per_side: 64,
            crop_n_layers: 2,
            crop_overlap_ratio: 0.34,
            crop_n_points_downscale_factor: 1,
            points_per_batch: 96,
            min_mask_region_area: 16,
            min_overall_area: 20,
            max_overall_area: 50000,
            pred_iou_thresh: 0.88,
            stability_score_thresh: 0.9,
            stability_score_offset: 1,
            box_nms_thresh: 0.7,
            crop_nms_thresh: 0.7,
            use_m2m: false,
            area_mode: 'pixels'
        });
        assert.strictEqual(samRefs.samPointsPerSideInput.value, 64);
        assert.strictEqual(samRefs.samUseM2mInput.checked, false);
        assert.strictEqual(samRefs.samAreaModeSelect.value, 'pixels');

        const state = {
            samPresets: [
                { key: 'cell_1920x1440', label: 'Balanced', params: { points_per_side: 64, crop_n_layers: 2 } },
                { key: 'fast', label: 'Fast', params: { points_per_side: 32, crop_n_layers: 1 } }
            ],
            projectSettings: {
                annotationFormat: 'csv',
                samSettings: {
                    preset: 'cell_1920x1440',
                    params: { points_per_side: 64, crop_n_layers: 2 },
                    warnings: ['server warning']
                }
            }
        };
        assert.strictEqual(settings.findSamPreset(state.samPresets, 'fast').label, 'Fast');
        assert.deepStrictEqual(
            plain(settings.samSettingsForPresetChange(state, 'fast', () => ({ preset: 'custom', params: {} }))),
            { preset: 'fast', params: { points_per_side: 32, crop_n_layers: 1 }, warnings: [] }
        );
        assert.deepStrictEqual(
            plain(settings.samSettingsForPresetChange(state, 'custom', () => ({ preset: 'fast', params: { points_per_side: 1 } }))),
            { preset: 'custom', params: { points_per_side: 1 }, warnings: [] }
        );
        assert.strictEqual(
            settings.samSettingsForInputChange(
                state,
                { params: { points_per_side: 32, crop_n_layers: 1 } },
                'fast'
            ).preset,
            'fast'
        );
        assert.strictEqual(
            settings.samSettingsForInputChange(
                state,
                { params: { points_per_side: 33, crop_n_layers: 1 } },
                'fast'
            ).preset,
            'custom'
        );

        assert.deepStrictEqual(
            plain(settings.currentSamSettingsPayload(state, { preset: 'fast', params: { points_per_side: 32 } })),
            { preset: 'fast', params: { points_per_side: 32 } }
        );
        assert.deepStrictEqual(plain(state.projectSettings.samSettings.warnings), ['server warning']);
        assert.strictEqual(settings.normalizeAndStoreSamSettings(state, { params: { points_per_side: 48 } }).params.points_per_side, 48);
        assert.strictEqual(settings.currentSamParams(state).points_per_side, 48);
        assert.strictEqual(settings.currentSamPresetLabel(state), 'Balanced');

        const risk = settings.samRiskState(
            { points_per_side: 128, crop_n_layers: 3, points_per_batch: 256, pred_iou_thresh: 0.7, stability_score_thresh: 0.7 },
            { originalImage: { width: 2200, height: 1600 } },
            ['server warning']
        );
        assert.strictEqual(risk.warning, true);
        assert.ok(risk.text.includes('Large image'));
        assert.ok(risk.text.includes('server warning'));
        assert.deepStrictEqual(
            plain(settings.samRiskState({ points_per_side: 32, crop_n_layers: 1 }, null, [])),
            { text: 'Current settings are within normal limits.', warning: false }
        );

        settings.normalizeAndStoreProjectSettings(state, {
            annotation_output_dir: 'labels',
            annotation_dir_display: 'labels',
            annotation_format: 'coco',
            sam_presets: [{ key: 'fast', label: 'Fast', params: { points_per_side: 32 } }]
        });
        assert.strictEqual(state.projectSettings.annotationOutputDir, 'labels');
        assert.strictEqual(state.projectSettings.annotationFormat, 'coco');
        assert.strictEqual(state.samPresets[0].key, 'fast');
        assert.strictEqual(settings.currentAnnotationFormat('', state.projectSettings.annotationFormat, value => value), 'coco');
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
