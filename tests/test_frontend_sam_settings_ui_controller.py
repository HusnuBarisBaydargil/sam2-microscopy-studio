import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = REPO_ROOT / "static"


SAM_SETTINGS_UI_CALLS = [
    "samSettingsUiController.openModal(",
    "samSettingsUiController.closeModal(",
    "samSettingsUiController.renderSettingsPanel(",
    "samSettingsUiController.renderDevicePanel(",
    "samSettingsUiController.readSamSettingsFromInputs(",
    "samSettingsUiController.currentSamSettingsPayload(",
    "samSettingsUiController.samDeviceLabel(",
]


def test_sam_settings_ui_controller_loads_after_settings_controller_and_before_main_script():
    index_html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    project_settings_tag = '<script src="static/projectSettingsClient.js"></script>'
    settings_controller_tag = '<script src="static/settingsController.js"></script>'
    sam_ui_tag = '<script src="static/samSettingsUiController.js"></script>'
    script_tag = '<script src="static/script.js"></script>'

    assert project_settings_tag in index_html
    assert settings_controller_tag in index_html
    assert sam_ui_tag in index_html
    assert script_tag in index_html
    assert index_html.index(project_settings_tag) < index_html.index(sam_ui_tag)
    assert index_html.index(settings_controller_tag) < index_html.index(sam_ui_tag)
    assert index_html.index(sam_ui_tag) < index_html.index(script_tag)


def test_main_script_delegates_sam_settings_ui_helpers():
    script_js = (STATIC_DIR / "script.js").read_text(encoding="utf-8")

    assert "const samSettingsUiController = window.SAM2SamSettingsUiController;" in script_js
    for delegated_call in SAM_SETTINGS_UI_CALLS:
        assert delegated_call in script_js

    assert "function renderSamPresetOptions(" not in script_js
    assert "settingsController.syncSamSettingsInputs(" not in script_js
    assert "settingsController.readSamSettingsFromInputs(" not in script_js
    assert "settingsController.currentSamSettingsPayload(" not in script_js
    assert "samDeviceStatus.classList.toggle(" not in script_js
    assert "samRiskText.textContent" not in script_js


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


def test_sam_settings_ui_controller_exports_expected_dom_behavior():
    node = _node_executable()
    if node is None:
        pytest.skip("Node.js is not available to execute samSettingsUiController.js")

    js_test = textwrap.dedent(
        r"""
        const assert = require('assert');
        const fs = require('fs');
        const vm = require('vm');

        class FakeElement {
            constructor(tagName = 'div') {
                this.tagName = tagName;
                this.children = [];
                this.value = '';
                this.textContent = '';
                this.title = '';
                this.checked = false;
                this.focused = false;
                this.classes = new Set();
                this.classList = {
                    remove: className => this.classes.delete(className),
                    add: className => this.classes.add(className),
                    toggle: (className, enabled) => {
                        if (enabled) this.classes.add(className);
                        else this.classes.delete(className);
                    },
                    contains: className => this.classes.has(className)
                };
            }

            set innerHTML(value) {
                this.children = [];
                this._innerHTML = value;
            }

            get innerHTML() {
                return this._innerHTML || '';
            }

            appendChild(child) {
                this.children.push(child);
                return child;
            }

            focus() {
                this.focused = true;
            }
        }

        const activeElement = new FakeElement('button');
        const context = {
            console,
            document: {
                activeElement,
                createElement(tagName) {
                    return new FakeElement(tagName);
                }
            },
            window: {}
        };
        vm.createContext(context);
        [
            'static/frontendConfig.js',
            'static/annotationCodecs.js',
            'static/projectSettingsClient.js',
            'static/settingsController.js',
            'static/samSettingsUiController.js'
        ].forEach(path => vm.runInContext(fs.readFileSync(path, 'utf8'), context));

        const samUi = context.window.SAM2SamSettingsUiController;
        assert.ok(samUi);

        const refs = {
            samSettingsModal: new FakeElement(),
            closeSamSettingsBtn: new FakeElement('button'),
            samPresetSummary: new FakeElement(),
            samDeviceSelect: new FakeElement('select'),
            samDeviceStatus: new FakeElement(),
            samPresetSelect: new FakeElement('select'),
            samAreaModeSelect: new FakeElement('select'),
            samPointsPerSideInput: new FakeElement('input'),
            samCropLayersInput: new FakeElement('input'),
            samCropOverlapInput: new FakeElement('input'),
            samCropDownscaleInput: new FakeElement('input'),
            samPointsPerBatchInput: new FakeElement('input'),
            samMinMaskRegionAreaInput: new FakeElement('input'),
            samMinObjectAreaInput: new FakeElement('input'),
            samMaxObjectAreaInput: new FakeElement('input'),
            samPredIouInput: new FakeElement('input'),
            samStabilityInput: new FakeElement('input'),
            samStabilityOffsetInput: new FakeElement('input'),
            samBoxNmsInput: new FakeElement('input'),
            samCropNmsInput: new FakeElement('input'),
            samUseM2mInput: new FakeElement('input'),
            samRiskText: new FakeElement()
        };
        refs.samSettingsModal.classes.add('hidden');

        const state = {
            samPresets: [
                {
                    key: 'balanced',
                    label: 'Balanced',
                    params: {
                        points_per_side: 32,
                        crop_n_layers: 1,
                        min_mask_region_area: 20,
                        crop_overlap_ratio: 0.25,
                        crop_n_points_downscale_factor: 2,
                        points_per_batch: 32,
                        pred_iou_thresh: 0.9,
                        stability_score_thresh: 0.91,
                        stability_score_offset: 1,
                        box_nms_thresh: 0.5,
                        crop_nms_thresh: 0.5,
                        use_m2m: true,
                        area_mode: 'percent',
                        min_overall_area: 1,
                        max_overall_area: 50
                    }
                }
            ],
            projectSettings: {
                samSettings: {
                    preset: 'balanced',
                    params: {
                        points_per_side: 32,
                        crop_n_layers: 1,
                        min_mask_region_area: 20,
                        crop_overlap_ratio: 0.25,
                        crop_n_points_downscale_factor: 2,
                        points_per_batch: 32,
                        pred_iou_thresh: 0.9,
                        stability_score_thresh: 0.91,
                        stability_score_offset: 1,
                        box_nms_thresh: 0.5,
                        crop_nms_thresh: 0.5,
                        use_m2m: true,
                        area_mode: 'percent',
                        min_overall_area: 1,
                        max_overall_area: 50
                    },
                    warnings: ['Server warning.']
                },
                samDevice: {
                    mode: 'auto',
                    active: 'cpu',
                    ready: false,
                    error: '',
                    modelLoadSkipped: false
                }
            }
        };

        let rendered = false;
        const returnFocus = samUi.openModal(refs, () => {
            rendered = true;
        }, context.document);
        assert.strictEqual(returnFocus, activeElement);
        assert.strictEqual(rendered, true);
        assert.strictEqual(refs.samSettingsModal.classList.contains('hidden'), false);
        assert.strictEqual(refs.closeSamSettingsBtn.focused, true);
        assert.strictEqual(samUi.closeModal(refs, returnFocus), null);
        assert.strictEqual(refs.samSettingsModal.classList.contains('hidden'), true);
        assert.strictEqual(activeElement.focused, true);

        samUi.renderSettingsPanel(refs, state, { keepInputs: false, currentImage: { originalImage: { width: 10, height: 10 } } });
        assert.strictEqual(refs.samPresetSelect.children.length, 2);
        assert.strictEqual(refs.samPresetSelect.children[0].textContent, 'Balanced');
        assert.strictEqual(refs.samPresetSelect.children[1].value, 'custom');
        assert.strictEqual(refs.samPresetSelect.value, 'balanced');
        assert.strictEqual(refs.samPointsPerSideInput.value, 32);
        assert.strictEqual(refs.samAreaModeSelect.value, 'percent');
        assert.strictEqual(refs.samMinObjectAreaInput.title, '% image area');
        assert.strictEqual(refs.samPresetSummary.textContent, 'Balanced');
        assert.strictEqual(refs.samDeviceStatus.textContent, 'Auto -> CPU');
        assert.strictEqual(refs.samDeviceStatus.classList.contains('warning'), true);
        assert.strictEqual(refs.samRiskText.classList.contains('warning'), true);

        refs.samPointsPerSideInput.value = '48';
        const nextSettings = samUi.readSamSettingsFromInputs(refs);
        assert.strictEqual(nextSettings.params.points_per_side, 48);
        const payload = samUi.currentSamSettingsPayload(state, refs);
        assert.strictEqual(payload.params.points_per_side, 48);
        assert.strictEqual(state.projectSettings.samSettings.warnings[0], 'Server warning.');
        assert.strictEqual(samUi.samDeviceLabel({ ready: true, mode: 'cuda', active: 'cuda' }), 'CUDA');
        """
    )

    subprocess.run([node, "-e", js_test], cwd=REPO_ROOT, check=True)
