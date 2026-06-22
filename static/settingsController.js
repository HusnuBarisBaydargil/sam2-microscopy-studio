(() => {
    const frontendConfig = window.SAM2FrontendConfig;
    const projectSettingsClient = window.SAM2ProjectSettingsClient;
    if (!frontendConfig) {
        throw new Error('SAM2FrontendConfig must be loaded before settingsController.js.');
    }
    if (!projectSettingsClient) {
        throw new Error('SAM2ProjectSettingsClient must be loaded before settingsController.js.');
    }

    const {
        DEFAULT_PREPROCESS_PARAMS,
        DEFAULT_SAM_PRESET,
        DEFAULT_SAM_PARAMS
    } = frontendConfig;

    function selectedPreprocessMethod(preprocessMethodSelect) {
        return preprocessMethodSelect.value || 'original';
    }

    function currentPreprocessParams(projectSettings) {
        return projectSettingsClient.normalizePreprocessParams(projectSettings.preprocessParams);
    }

    function samPreprocessPayload(imageRecord, preprocessParams) {
        return projectSettingsClient.samPreprocessPayload(imageRecord, preprocessParams);
    }

    function numberFromInput(input, fallback) {
        return projectSettingsClient.numberFromValue(input.value, fallback);
    }

    function readPreprocessSettingsFromInputs(refs) {
        return {
            clahe_clip_limit: numberFromInput(refs.preprocessClaheClipInput, DEFAULT_PREPROCESS_PARAMS.clahe_clip_limit),
            clahe_tile_grid_size: numberFromInput(refs.preprocessClaheTileInput, DEFAULT_PREPROCESS_PARAMS.clahe_tile_grid_size),
            gamma: numberFromInput(refs.preprocessGammaInput, DEFAULT_PREPROCESS_PARAMS.gamma),
            unsharp_amount: numberFromInput(refs.preprocessUnsharpAmountInput, DEFAULT_PREPROCESS_PARAMS.unsharp_amount),
            unsharp_radius: numberFromInput(refs.preprocessUnsharpRadiusInput, DEFAULT_PREPROCESS_PARAMS.unsharp_radius),
            unsharp_threshold: numberFromInput(refs.preprocessUnsharpThresholdInput, DEFAULT_PREPROCESS_PARAMS.unsharp_threshold),
            retinex_strength: numberFromInput(refs.preprocessRetinexStrengthInput, DEFAULT_PREPROCESS_PARAMS.retinex_strength)
        };
    }

    function syncPreprocessSettingsInputs(refs, params) {
        refs.preprocessGammaInput.value = params.gamma;
        refs.preprocessClaheClipInput.value = params.clahe_clip_limit;
        refs.preprocessClaheTileInput.value = params.clahe_tile_grid_size;
        refs.preprocessUnsharpAmountInput.value = params.unsharp_amount;
        refs.preprocessUnsharpRadiusInput.value = params.unsharp_radius;
        refs.preprocessUnsharpThresholdInput.value = params.unsharp_threshold;
        refs.preprocessRetinexStrengthInput.value = params.retinex_strength;
    }

    function defaultPreprocessParams() {
        return { ...DEFAULT_PREPROCESS_PARAMS };
    }

    function readNumericInput(input, fallback) {
        const value = Number(input.value);
        return Number.isFinite(value) ? value : fallback;
    }

    function readSamSettingsFromInputs(refs) {
        return {
            preset: refs.samPresetSelect.value || DEFAULT_SAM_PRESET,
            params: {
                points_per_side: readNumericInput(refs.samPointsPerSideInput, DEFAULT_SAM_PARAMS.points_per_side),
                crop_n_layers: readNumericInput(refs.samCropLayersInput, DEFAULT_SAM_PARAMS.crop_n_layers),
                min_mask_region_area: readNumericInput(refs.samMinMaskRegionAreaInput, DEFAULT_SAM_PARAMS.min_mask_region_area),
                crop_overlap_ratio: readNumericInput(refs.samCropOverlapInput, DEFAULT_SAM_PARAMS.crop_overlap_ratio),
                crop_n_points_downscale_factor: readNumericInput(refs.samCropDownscaleInput, DEFAULT_SAM_PARAMS.crop_n_points_downscale_factor),
                points_per_batch: readNumericInput(refs.samPointsPerBatchInput, DEFAULT_SAM_PARAMS.points_per_batch),
                pred_iou_thresh: readNumericInput(refs.samPredIouInput, DEFAULT_SAM_PARAMS.pred_iou_thresh),
                stability_score_thresh: readNumericInput(refs.samStabilityInput, DEFAULT_SAM_PARAMS.stability_score_thresh),
                stability_score_offset: readNumericInput(refs.samStabilityOffsetInput, DEFAULT_SAM_PARAMS.stability_score_offset),
                box_nms_thresh: readNumericInput(refs.samBoxNmsInput, DEFAULT_SAM_PARAMS.box_nms_thresh),
                crop_nms_thresh: readNumericInput(refs.samCropNmsInput, DEFAULT_SAM_PARAMS.crop_nms_thresh),
                use_m2m: refs.samUseM2mInput.checked,
                area_mode: refs.samAreaModeSelect.value === 'percent' ? 'percent' : 'pixels',
                min_overall_area: readNumericInput(refs.samMinObjectAreaInput, DEFAULT_SAM_PARAMS.min_overall_area),
                max_overall_area: readNumericInput(refs.samMaxObjectAreaInput, DEFAULT_SAM_PARAMS.max_overall_area)
            }
        };
    }

    function syncSamSettingsInputs(refs, params) {
        refs.samAreaModeSelect.value = params.area_mode || 'pixels';
        refs.samPointsPerSideInput.value = params.points_per_side;
        refs.samCropLayersInput.value = params.crop_n_layers;
        refs.samCropOverlapInput.value = params.crop_overlap_ratio;
        refs.samCropDownscaleInput.value = params.crop_n_points_downscale_factor;
        refs.samPointsPerBatchInput.value = params.points_per_batch;
        refs.samMinMaskRegionAreaInput.value = params.min_mask_region_area;
        refs.samMinObjectAreaInput.value = params.min_overall_area;
        refs.samMaxObjectAreaInput.value = params.max_overall_area;
        refs.samPredIouInput.value = params.pred_iou_thresh;
        refs.samStabilityInput.value = params.stability_score_thresh;
        refs.samStabilityOffsetInput.value = params.stability_score_offset;
        refs.samBoxNmsInput.value = params.box_nms_thresh;
        refs.samCropNmsInput.value = params.crop_nms_thresh;
        refs.samUseM2mInput.checked = Boolean(params.use_m2m);
    }

    function findSamPreset(samPresets, key) {
        return samPresets.find(preset => preset.key === key);
    }

    function samSettingsForPresetChange(state, selectedPresetValue, readCurrentInputs) {
        if (selectedPresetValue === 'custom') {
            return {
                ...readCurrentInputs(),
                preset: 'custom',
                warnings: []
            };
        }

        const preset = findSamPreset(state.samPresets, selectedPresetValue)
            || findSamPreset(state.samPresets, DEFAULT_SAM_PRESET);
        if (!preset) return null;

        return {
            preset: preset.key,
            params: { ...preset.params },
            warnings: []
        };
    }

    function samSettingsForInputChange(state, nextSettings, selectedPresetValue) {
        const selectedPreset = findSamPreset(state.samPresets, selectedPresetValue);
        const stillMatchesPreset = selectedPreset
            && projectSettingsClient.samParamsEqual(nextSettings.params, selectedPreset.params);
        return {
            ...nextSettings,
            preset: stillMatchesPreset ? selectedPreset.key : 'custom',
            warnings: []
        };
    }

    function currentSamSettingsPayload(state, currentSettings) {
        state.projectSettings.samSettings = {
            ...currentSettings,
            warnings: state.projectSettings.samSettings.warnings || []
        };
        return currentSettings;
    }

    function normalizeAndStoreSamSettings(state, samSettings) {
        const normalizedSettings = projectSettingsClient.normalizeSamSettingsForClient(samSettings);
        state.projectSettings.samSettings = normalizedSettings;
        return normalizedSettings;
    }

    function currentSamParams(state) {
        return state.projectSettings.samSettings.params || DEFAULT_SAM_PARAMS;
    }

    function samRiskState(currentParams, currentImage, settingsWarnings = []) {
        const warnings = [
            ...projectSettingsClient.samRiskWarnings(currentParams, currentImage),
            ...settingsWarnings
        ];
        const uniqueWarnings = [...new Set(warnings)];
        return {
            text: uniqueWarnings.length === 0
                ? 'Current settings are within normal limits.'
                : uniqueWarnings.join(' '),
            warning: uniqueWarnings.length > 0
        };
    }

    function currentSamPresetLabel(state) {
        if (state.projectSettings.samSettings.preset === 'custom') return 'Custom';
        const preset = findSamPreset(state.samPresets, state.projectSettings.samSettings.preset);
        return preset ? preset.label : 'Custom';
    }

    function normalizeAndStoreProjectSettings(state, data) {
        const normalizedSettings = projectSettingsClient.normalizeProjectSettingsForClient(data, state.projectSettings);
        state.projectSettings = {
            ...state.projectSettings,
            ...normalizedSettings
        };
        const normalizedSamPresets = projectSettingsClient.normalizeSamPresets(data.sam_presets);
        if (normalizedSamPresets) state.samPresets = normalizedSamPresets;
        return state.projectSettings;
    }

    function currentAnnotationFormat(value, projectSettingsAnnotationFormat, normalizeAnnotationFormat) {
        return normalizeAnnotationFormat(value || projectSettingsAnnotationFormat);
    }

    window.SAM2SettingsController = {
        selectedPreprocessMethod,
        currentPreprocessParams,
        samPreprocessPayload,
        numberFromInput,
        readPreprocessSettingsFromInputs,
        syncPreprocessSettingsInputs,
        defaultPreprocessParams,
        readNumericInput,
        readSamSettingsFromInputs,
        syncSamSettingsInputs,
        findSamPreset,
        samSettingsForPresetChange,
        samSettingsForInputChange,
        currentSamSettingsPayload,
        normalizeAndStoreSamSettings,
        currentSamParams,
        samRiskState,
        currentSamPresetLabel,
        normalizeAndStoreProjectSettings,
        currentAnnotationFormat
    };
})();
