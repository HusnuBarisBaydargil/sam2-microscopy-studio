(() => {
    const frontendConfig = window.SAM2FrontendConfig;
    const annotationCodecs = window.SAM2AnnotationCodecs;
    if (!frontendConfig) {
        throw new Error('SAM2FrontendConfig must be loaded before projectSettingsClient.js.');
    }
    if (!annotationCodecs) {
        throw new Error('SAM2AnnotationCodecs must be loaded before projectSettingsClient.js.');
    }

    const {
        DEFAULT_SAM_PRESET,
        DEFAULT_SAM_PARAMS,
        DEFAULT_PREPROCESS_PARAMS,
        PREPROCESS_METHODS
    } = frontendConfig;

    const { normalizeAnnotationFormat } = annotationCodecs;

    function preprocessLabel(method) {
        return PREPROCESS_METHODS[method]?.label || 'Preprocessing';
    }

    function preprocessBadgeLabel(method) {
        return PREPROCESS_METHODS[method]?.badge || preprocessLabel(method);
    }

    function normalizePreprocessParams(params = {}) {
        return {
            ...DEFAULT_PREPROCESS_PARAMS,
            ...(params || {})
        };
    }

    function samPreprocessPayload(imageRecord, fallbackParams = DEFAULT_PREPROCESS_PARAMS) {
        if (!hasActivePreprocess(imageRecord)) {
            return { method: 'original', params: {} };
        }
        return {
            method: imageRecord.preprocessMethod || 'original',
            params: imageRecord.preprocessParams || normalizePreprocessParams(fallbackParams)
        };
    }

    function hasActivePreprocess(imageRecord) {
        return !!(imageRecord && imageRecord.processedImage && imageRecord.preprocessMethod && imageRecord.preprocessMethod !== 'original');
    }

    function numberFromValue(value, fallback) {
        const number = Number.parseFloat(value);
        return Number.isFinite(number) ? number : fallback;
    }

    function normalizeSamSettingsForClient(samSettings) {
        const rawParams = samSettings && typeof samSettings.params === 'object'
            ? samSettings.params
            : {};
        return {
            preset: samSettings?.preset || DEFAULT_SAM_PRESET,
            params: {
                ...DEFAULT_SAM_PARAMS,
                ...rawParams,
                area_mode: rawParams.area_mode === 'percent' ? 'percent' : 'pixels'
            },
            warnings: Array.isArray(samSettings?.warnings) ? samSettings.warnings : []
        };
    }

    function normalizeSamDeviceForClient(samDevice = {}) {
        const mode = ['auto', 'cuda', 'cpu'].includes(samDevice.mode) ? samDevice.mode : 'auto';
        return {
            mode,
            active: String(samDevice.active || 'unknown'),
            cudaAvailable: Boolean(samDevice.cuda_available ?? samDevice.cudaAvailable),
            ready: Boolean(samDevice.ready),
            modelLoadSkipped: Boolean(samDevice.model_load_skipped ?? samDevice.modelLoadSkipped),
            error: String(samDevice.error || '')
        };
    }

    function samDeviceLabel(device) {
        if (device.error) return 'Needs attention';
        if (device.modelLoadSkipped) return 'SAM2 unavailable';
        if (device.mode === 'auto' && device.active === 'cuda') return 'Auto -> CUDA';
        if (device.mode === 'auto' && device.active === 'cpu') return 'Auto -> CPU';
        if (device.active === 'cuda') return 'CUDA';
        if (device.active === 'cpu') return 'CPU';
        return device.mode.toUpperCase();
    }

    function samDeviceTitle(device) {
        if (device.error) return device.error;
        if (device.modelLoadSkipped) return 'SAM2 model loading is disabled with SKIP_SAM_MODEL_LOAD=1.';
        if (device.active === 'cpu') return 'SAM2 is running on CPU; inference may be slow.';
        if (device.active === 'cuda') return 'SAM2 is running with CUDA acceleration.';
        return device.cudaAvailable ? 'CUDA is available.' : 'CUDA is not available.';
    }

    function samDeviceReadiness(device) {
        const normalizedDevice = normalizeSamDeviceForClient(device);
        if (normalizedDevice.error) {
            return {
                level: 'error',
                text: `SAM2 needs attention: ${normalizedDevice.error}`
            };
        }
        if (normalizedDevice.modelLoadSkipped) {
            return {
                level: 'error',
                text: 'SAM2 candidate generation is unavailable in this session.'
            };
        }
        if (!normalizedDevice.ready) {
            return {
                level: 'error',
                text: 'SAM2 model not ready. Candidate generation is unavailable.'
            };
        }
        if (normalizedDevice.active === 'cpu') {
            return {
                level: 'warning',
                text: 'SAM2 is ready but running on CPU. Candidate generation may be slow.'
            };
        }
        if (normalizedDevice.active === 'cuda') {
            return {
                level: 'ready',
                text: 'SAM2 is ready with CUDA acceleration.'
            };
        }
        return {
            level: 'warning',
            text: 'SAM2 readiness is unknown. Check the selected device before generating candidates.'
        };
    }

    function samRiskWarnings(params, imageRecord = null) {
        const warnings = [];
        if (params.points_per_side > 96) warnings.push('High point density can be slow and memory intensive.');
        if (params.crop_n_layers > 2) warnings.push('More than 2 crop layers can greatly increase runtime.');
        if (params.points_per_batch > 128) warnings.push('Large point batches can trigger GPU out-of-memory errors.');
        if (params.pred_iou_thresh < 0.75) warnings.push('Low IoU threshold can produce many noisy masks.');
        if (params.stability_score_thresh < 0.75) warnings.push('Low stability threshold can produce unstable masks.');
        if (imageRecord?.originalImage) {
            const pixels = imageRecord.originalImage.width * imageRecord.originalImage.height;
            if (pixels > 3000000 && params.points_per_side >= 96 && params.crop_n_layers >= 2) {
                warnings.push('Large image plus dense crop settings can be very GPU intensive.');
            }
        }
        return warnings;
    }

    function samParamsEqual(leftParams, rightParams) {
        return Object.keys(DEFAULT_SAM_PARAMS).every(key => {
            const leftValue = leftParams[key];
            const rightValue = rightParams[key];
            if (typeof leftValue === 'number' || typeof rightValue === 'number') {
                return Math.abs(Number(leftValue) - Number(rightValue)) < 0.0001;
            }
            return leftValue === rightValue;
        });
    }

    function normalizeSamPresets(samPresets) {
        if (!Array.isArray(samPresets) || samPresets.length === 0) return null;
        return samPresets.map(preset => ({
            ...preset,
            params: { ...DEFAULT_SAM_PARAMS, ...(preset.params || {}) }
        }));
    }

    function normalizeProjectSettingsForClient(data, currentSettings = {}) {
        const nextSettings = {
            schemaVersion: Number(data.schema_version) || currentSettings.schemaVersion || 1,
            projectId: String(data.project_id || currentSettings.projectId || ''),
            taskType: String(data.task_type || currentSettings.taskType || 'bounding_box'),
            manifestPath: String(data.manifest_path || currentSettings.manifestPath || 'project_manifest.json'),
            annotationOutputDir: data.annotation_output_dir || 'annotations',
            annotationDirDisplay: data.annotation_dir_display || data.annotation_output_dir || 'annotations',
            annotationFormat: normalizeAnnotationFormat(data.annotation_format || currentSettings.annotationFormat),
            privacy: {
                phiSafeMode: Boolean(data.privacy?.phi_safe_mode),
                saltConfigured: Boolean(data.privacy?.salt_configured)
            }
        };
        if (data.sam_settings) {
            nextSettings.samSettings = normalizeSamSettingsForClient(data.sam_settings);
        }
        if (data.sam_device) {
            nextSettings.samDevice = normalizeSamDeviceForClient(data.sam_device);
        }
        return nextSettings;
    }

    window.SAM2ProjectSettingsClient = {
        preprocessLabel,
        preprocessBadgeLabel,
        normalizePreprocessParams,
        samPreprocessPayload,
        hasActivePreprocess,
        numberFromValue,
        normalizeSamSettingsForClient,
        normalizeSamDeviceForClient,
        samDeviceLabel,
        samDeviceTitle,
        samDeviceReadiness,
        samRiskWarnings,
        samParamsEqual,
        normalizeSamPresets,
        normalizeProjectSettingsForClient
    };
})();
