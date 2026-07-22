(() => {
    const frontendConfig = window.SAM2FrontendConfig;
    if (!frontendConfig) {
        throw new Error('SAM2FrontendConfig must be loaded before stateStore.js.');
    }

    const {
        DEFAULT_CLASSES,
        DEFAULT_SAM_PRESET,
        DEFAULT_SAM_PARAMS,
        DEFAULT_SAM_PRESETS,
        DEFAULT_PREPROCESS_PARAMS
    } = frontendConfig;

    function createAppState() {
        return {
            classes: DEFAULT_CLASSES.map(cls => ({ ...cls })),
            images: [],
            currentImage: null,
            annotationsByImage: new Map(),
            candidateAnnotationsByImage: new Map(),
            annotationHistoryByImage: new Map(),
            annotationRedoByImage: new Map(),
            annotationMatchesByImage: new Map(),
            selectedCandidateIds: new Set(),
            selectedAnnotationIds: new Set(),
            dirtyImages: new Set(),
            projectSettings: {
                annotationOutputDir: 'annotations',
                annotationDirDisplay: 'annotations',
                annotationFormat: 'csv',
                privacy: {
                    phiSafeMode: false,
                    saltConfigured: false
                },
                samSettings: {
                    preset: DEFAULT_SAM_PRESET,
                    params: { ...DEFAULT_SAM_PARAMS },
                    warnings: []
                },
                samDevice: {
                    mode: 'auto',
                    active: 'unknown',
                    cudaAvailable: false,
                    ready: false,
                    modelLoadSkipped: false,
                    error: ''
                },
                preprocessParams: { ...DEFAULT_PREPROCESS_PARAMS }
            },
            samPresets: DEFAULT_SAM_PRESETS.map(preset => ({
                ...preset,
                params: { ...preset.params }
            })),
            matchSummary: null,
            imageQueueFilter: 'all',
            annotationSource: {
                mode: 'server',
                files: [],
                fileMap: new Map(),
                displayName: 'Server folder source active.'
            },
            annotationCounter: 0,
            candidateCounter: 0,
            logItemToModify: null,
            isPanning: false,
            lastPanPoint: { x: 0, y: 0 },
            cameraOffset: { x: 0, y: 0 },
            cameraZoom: 1,
            isManualMode: false,
            isDrawing: false,
            manualBoxStart: { x: 0, y: 0 },
            currentManualBox: null,
            isAwaitingChoice: false,
            choiceInfo: null,
            boxEditMode: null,
            boxEditHandle: null,
            boxEditStartWorld: null,
            boxEditOriginalBboxes: new Map()
        };
    }

    function initializeImageState(state, imageId) {
        if (!state.annotationsByImage.has(imageId)) state.annotationsByImage.set(imageId, []);
        if (!state.candidateAnnotationsByImage.has(imageId)) state.candidateAnnotationsByImage.set(imageId, []);
        if (!state.annotationHistoryByImage.has(imageId)) state.annotationHistoryByImage.set(imageId, []);
        if (!state.annotationRedoByImage.has(imageId)) state.annotationRedoByImage.set(imageId, []);
    }

    function currentImageId(state) {
        return state.currentImage ? state.currentImage.id : null;
    }

    function currentImageIndex(state) {
        if (!state.currentImage) return -1;
        return state.images.findIndex(imageRecord => imageRecord.id === state.currentImage.id);
    }

    function currentAnnotations(state) {
        const imageId = currentImageId(state);
        if (!imageId) return [];
        if (!state.annotationsByImage.has(imageId)) state.annotationsByImage.set(imageId, []);
        return state.annotationsByImage.get(imageId);
    }

    function setCurrentAnnotations(state, annotations) {
        const imageId = currentImageId(state);
        if (!imageId) return;
        state.annotationsByImage.set(imageId, annotations);
    }

    function currentCandidates(state) {
        const imageId = currentImageId(state);
        if (!imageId) return [];
        if (!state.candidateAnnotationsByImage.has(imageId)) state.candidateAnnotationsByImage.set(imageId, []);
        return state.candidateAnnotationsByImage.get(imageId);
    }

    function setCurrentCandidates(state, candidates) {
        const imageId = currentImageId(state);
        if (!imageId) return;
        state.candidateAnnotationsByImage.set(imageId, candidates);
    }

    function currentHistory(state) {
        const imageId = currentImageId(state);
        if (!imageId) return [];
        if (!state.annotationHistoryByImage.has(imageId)) state.annotationHistoryByImage.set(imageId, []);
        return state.annotationHistoryByImage.get(imageId);
    }

    function setCurrentHistory(state, history) {
        const imageId = currentImageId(state);
        if (!imageId) return;
        state.annotationHistoryByImage.set(imageId, history);
    }

    function currentRedoHistory(state) {
        const imageId = currentImageId(state);
        if (!imageId) return [];
        if (!state.annotationRedoByImage.has(imageId)) state.annotationRedoByImage.set(imageId, []);
        return state.annotationRedoByImage.get(imageId);
    }

    function setCurrentRedoHistory(state, history) {
        const imageId = currentImageId(state);
        if (!imageId) return;
        state.annotationRedoByImage.set(imageId, history);
    }

    function currentDisplayImage(state, hasActivePreprocess) {
        const imageRecord = state.currentImage;
        if (!imageRecord) return null;
        return hasActivePreprocess(imageRecord) ? imageRecord.processedImage : imageRecord.originalImage;
    }

    function markCurrentImageDirty(state) {
        const imageId = currentImageId(state);
        if (imageId) state.dirtyImages.add(imageId);
    }

    function resetInteractionState(state) {
        state.selectedCandidateIds.clear();
        state.selectedAnnotationIds.clear();
        state.logItemToModify = null;
        state.isDrawing = false;
        state.isPanning = false;
        state.isAwaitingChoice = false;
        state.choiceInfo = null;
        state.currentManualBox = null;
        state.boxEditMode = null;
        state.boxEditHandle = null;
        state.boxEditStartWorld = null;
        state.boxEditOriginalBboxes = new Map();
    }

    function resetProjectState(state) {
        state.images = [];
        state.currentImage = null;
        state.annotationsByImage.clear();
        state.candidateAnnotationsByImage.clear();
        state.annotationHistoryByImage.clear();
        state.annotationRedoByImage.clear();
        state.annotationMatchesByImage.clear();
        state.selectedCandidateIds.clear();
        state.selectedAnnotationIds.clear();
        state.dirtyImages.clear();
        state.matchSummary = null;
        state.imageQueueFilter = 'all';
        state.annotationCounter = 0;
        state.candidateCounter = 0;
        state.logItemToModify = null;
        state.isDrawing = false;
        state.isPanning = false;
        state.isAwaitingChoice = false;
        state.choiceInfo = null;
        state.currentManualBox = null;
        state.boxEditMode = null;
        state.boxEditHandle = null;
        state.boxEditStartWorld = null;
        state.boxEditOriginalBboxes = new Map();
        state.cameraOffset = { x: 0, y: 0 };
        state.cameraZoom = 1;
    }

    window.SAM2StateStore = {
        createAppState,
        initializeImageState,
        currentImageId,
        currentImageIndex,
        currentAnnotations,
        setCurrentAnnotations,
        currentCandidates,
        setCurrentCandidates,
        currentHistory,
        setCurrentHistory,
        currentRedoHistory,
        setCurrentRedoHistory,
        currentDisplayImage,
        markCurrentImageDirty,
        resetInteractionState,
        resetProjectState
    };
})();
