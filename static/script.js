document.addEventListener('DOMContentLoaded', () => {
    // --- CONSTANTS ---
    const DEFAULT_CLASSES = [];
    const ANNOTATION_FORMATS = {
        csv: {
            label: 'CSV',
            extension: 'csv',
            mime: 'text/csv',
            accept: '.csv,text/csv'
        },
        yolo: {
            label: 'YOLO TXT',
            extension: 'txt',
            mime: 'text/plain',
            accept: '.txt,text/plain'
        },
        coco: {
            label: 'COCO JSON',
            extension: 'json',
            mime: 'application/json',
            accept: '.json,application/json'
        },
        voc: {
            label: 'Pascal VOC XML',
            extension: 'xml',
            mime: 'application/xml',
            accept: '.xml,application/xml,text/xml'
        }
    };
    const CLASS_COLOR_PALETTE = [
        '#39d353',
        '#9ca3af',
        '#58a6ff',
        '#f2cc60',
        '#ff7b72',
        '#d2a8ff',
        '#56d4dd',
        '#ffa657'
    ];
    const ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'];
    const ALLOWED_IMAGE_MIME_TYPES = new Set([
        'image/jpeg',
        'image/png',
        'image/bmp',
        'image/x-ms-bmp',
        'image/tiff',
        'image/x-tiff'
    ]);
    const OVERLAY_COLORS = {
        candidate: '#38bdf8',
        contrastStroke: 'rgba(0, 0, 0, 0.82)',
        labelBackground: 'rgba(0, 0, 0, 0.78)',
        labelBorder: 'rgba(255, 255, 255, 0.55)',
        labelText: '#ffffff',
        selectedHalo: '#ffffff',
        manualBox: '#d97706'
    };
    const MAX_ZOOM = 10;
    const MIN_ZOOM = 0.1;
    const SCROLL_SENSITIVITY = 0.001;
    const ZOOM_STEP = 1.2;
    const BOX_HANDLE_SCREEN_SIZE = 9;
    const MIN_BOX_SIZE = 2;
    const NEW_CLASS_ACTION = '__new_class__';
    const DEFAULT_SAM_PRESET = 'cell_1920x1440';
    const DEFAULT_SAM_PARAMS = {
        points_per_side: 64,
        crop_n_layers: 2,
        min_mask_region_area: 400,
        crop_overlap_ratio: 0.4,
        crop_n_points_downscale_factor: 2,
        points_per_batch: 64,
        pred_iou_thresh: 0.92,
        stability_score_thresh: 0.92,
        stability_score_offset: 1.0,
        box_nms_thresh: 0.5,
        crop_nms_thresh: 0.5,
        use_m2m: true,
        area_mode: 'pixels',
        min_overall_area: 300,
        max_overall_area: 30000
    };
    const DEFAULT_SAM_PRESETS = [
        {
            key: DEFAULT_SAM_PRESET,
            label: 'Cell 1920x1440',
            description: 'Current default tuned for the original cell workflow.',
            params: { ...DEFAULT_SAM_PARAMS }
        }
    ];
    const PREPROCESS_METHODS = {
        original: { label: 'Original', badge: '' },
        clahe: { label: 'CLAHE', badge: 'CLAHE' },
        gamma: { label: 'Gamma', badge: 'Gamma' },
        clahe_unsharp: { label: 'CLAHE + Unsharp', badge: 'CLAHE+USM' },
        gamma_unsharp: { label: 'Gamma + Unsharp', badge: 'Gamma+USM' },
        retinex_mild: { label: 'Retinex mild', badge: 'Retinex' }
    };
    const DEFAULT_PREPROCESS_PARAMS = {
        clahe_clip_limit: 2.0,
        clahe_tile_grid_size: 8,
        gamma: 1.2,
        unsharp_amount: 0.8,
        unsharp_radius: 1.2,
        unsharp_threshold: 3,
        retinex_strength: 0.55
    };

    function apiPath(path) {
        return path.replace(/^\/+/, '');
    }

    const API_TOKEN_STORAGE_KEY = 'sam2AnnotatorApiToken';
    let apiAuthToken = sessionStorage.getItem(API_TOKEN_STORAGE_KEY) || '';

    function withApiAuthHeaders(init = {}, token = apiAuthToken) {
        const nextInit = { ...init };
        const headers = new Headers(init.headers || {});
        if (token) {
            headers.set('Authorization', `Bearer ${token}`);
            headers.set('X-API-Token', token);
        }
        nextInit.headers = headers;
        return nextInit;
    }

    async function fetchWithApiAuth(path, init = {}, token = apiAuthToken) {
        return fetch(apiPath(path), withApiAuthHeaders(init, token));
    }

    async function apiFetch(path, init = {}) {
        let response = await fetchWithApiAuth(path, init);
        if (response.status !== 401) return response;

        let authRequired = false;
        try {
            const data = await response.clone().json();
            authRequired = Boolean(data && data.auth_required);
        } catch (error) {
            authRequired = false;
        }
        if (!authRequired) return response;

        const token = window.prompt('Enter the API token for this annotator server:');
        if (!token || !token.trim()) {
            throw new Error('API token required.');
        }

        apiAuthToken = token.trim();
        sessionStorage.setItem(API_TOKEN_STORAGE_KEY, apiAuthToken);
        response = await fetchWithApiAuth(path, init, apiAuthToken);
        if (response.status === 401) {
            apiAuthToken = '';
            sessionStorage.removeItem(API_TOKEN_STORAGE_KEY);
            throw new Error('Invalid API token.');
        }
        return response;
    }

    // --- ELEMENT SELECTION ---
    const loadImageInput = document.getElementById('loadImageInput');
    const openFolderInput = document.getElementById('openFolderInput');
    const runSamBtn = document.getElementById('runSamBtn');
    const clearCandidatesBtn = document.getElementById('clearCandidatesBtn');
    const keepAnnotationsInput = document.getElementById('keepAnnotationsInput');
    const openSamSettingsBtn = document.getElementById('openSamSettingsBtn');
    const samSettingsModal = document.getElementById('samSettingsModal');
    const closeSamSettingsBtn = document.getElementById('closeSamSettingsBtn');
    const samPresetSummary = document.getElementById('samPresetSummary');
    const samPresetSelect = document.getElementById('samPresetSelect');
    const samAreaModeSelect = document.getElementById('samAreaModeSelect');
    const samPointsPerSideInput = document.getElementById('samPointsPerSideInput');
    const samCropLayersInput = document.getElementById('samCropLayersInput');
    const samCropOverlapInput = document.getElementById('samCropOverlapInput');
    const samCropDownscaleInput = document.getElementById('samCropDownscaleInput');
    const samPointsPerBatchInput = document.getElementById('samPointsPerBatchInput');
    const samMinMaskRegionAreaInput = document.getElementById('samMinMaskRegionAreaInput');
    const samMinObjectAreaInput = document.getElementById('samMinObjectAreaInput');
    const samMaxObjectAreaInput = document.getElementById('samMaxObjectAreaInput');
    const samPredIouInput = document.getElementById('samPredIouInput');
    const samStabilityInput = document.getElementById('samStabilityInput');
    const samStabilityOffsetInput = document.getElementById('samStabilityOffsetInput');
    const samBoxNmsInput = document.getElementById('samBoxNmsInput');
    const samCropNmsInput = document.getElementById('samCropNmsInput');
    const samUseM2mInput = document.getElementById('samUseM2mInput');
    const samRiskText = document.getElementById('samRiskText');
    const applySamSettingsBtn = document.getElementById('applySamSettingsBtn');
    const resetSamPresetBtn = document.getElementById('resetSamPresetBtn');
    const preprocessMethodSelect = document.getElementById('preprocessMethodSelect');
    const applyPreprocessBtn = document.getElementById('applyPreprocessBtn');
    const openPreprocessSettingsBtn = document.getElementById('openPreprocessSettingsBtn');
    const restoreOriginalBtn = document.getElementById('restoreOriginalBtn');
    const preprocessSummary = document.getElementById('preprocessSummary');
    const preprocessSettingsModal = document.getElementById('preprocessSettingsModal');
    const closePreprocessSettingsBtn = document.getElementById('closePreprocessSettingsBtn');
    const preprocessGammaInput = document.getElementById('preprocessGammaInput');
    const preprocessClaheClipInput = document.getElementById('preprocessClaheClipInput');
    const preprocessClaheTileInput = document.getElementById('preprocessClaheTileInput');
    const preprocessUnsharpAmountInput = document.getElementById('preprocessUnsharpAmountInput');
    const preprocessUnsharpRadiusInput = document.getElementById('preprocessUnsharpRadiusInput');
    const preprocessUnsharpThresholdInput = document.getElementById('preprocessUnsharpThresholdInput');
    const preprocessRetinexStrengthInput = document.getElementById('preprocessRetinexStrengthInput');
    const applyPreprocessSettingsBtn = document.getElementById('applyPreprocessSettingsBtn');
    const resetPreprocessSettingsBtn = document.getElementById('resetPreprocessSettingsBtn');
    const manualAnnotationBtn = document.getElementById('manualAnnotationBtn');
    const undoBtn = document.getElementById('undoBtn');
    const exportAnnotationFileBtn = document.getElementById('exportAnnotationFileBtn');
    const loadAnnotationFileBtn = document.getElementById('loadAnnotationFileBtn');
    const loadAnnotationFileInput = document.getElementById('loadAnnotationFileInput');
    const loadServerAnnotationsBtn = document.getElementById('loadServerAnnotationsBtn');
    const saveServerBtn = document.getElementById('saveServerBtn');
    const saveAllServerBtn = document.getElementById('saveAllServerBtn');
    const currentImageName = document.getElementById('currentImageName');
    const currentPreprocessBadge = document.getElementById('currentPreprocessBadge');
    const imagePosition = document.getElementById('imagePosition');
    const currentImageState = document.getElementById('currentImageState');
    const prevImageBtn = document.getElementById('prevImageBtn');
    const nextImageBtn = document.getElementById('nextImageBtn');
    const imageList = document.getElementById('imageList');
    const annotationDirInput = document.getElementById('annotationDirInput');
    const setAnnotationDirBtn = document.getElementById('setAnnotationDirBtn');
    const annotationDirDisplay = document.getElementById('annotationDirDisplay');
    const loadAnnotationSourceFilesBtn = document.getElementById('loadAnnotationSourceFilesBtn');
    const loadAnnotationSourceFolderBtn = document.getElementById('loadAnnotationSourceFolderBtn');
    const useServerAnnotationSourceBtn = document.getElementById('useServerAnnotationSourceBtn');
    const annotationSourceFilesInput = document.getElementById('annotationSourceFilesInput');
    const annotationSourceFolderInput = document.getElementById('annotationSourceFolderInput');
    const annotationSourceDisplay = document.getElementById('annotationSourceDisplay');
    const annotationFormatSelect = document.getElementById('annotationFormatSelect');
    const refreshMatchesBtn = document.getElementById('refreshMatchesBtn');
    const loadMatchedBtn = document.getElementById('loadMatchedBtn');
    const matchSummary = document.getElementById('matchSummary');
    const statusText = document.getElementById('statusText');
    const annotationLogBody = document.getElementById('annotationLogBody');
    const loader = document.getElementById('loader');
    const loaderText = document.getElementById('loaderText');
    const canvas = document.getElementById('mainCanvas');
    const ctx = canvas.getContext('2d');
    const preprocessOverlay = document.getElementById('preprocessOverlay');
    const preprocessOverlayTitle = document.getElementById('preprocessOverlayTitle');
    const preprocessOverlayDetail = document.getElementById('preprocessOverlayDetail');
    const classManager = document.getElementById('classManager');
    const addClassBtn = document.getElementById('addClassBtn');
    const quickClassInput = document.getElementById('quickClassInput');
    const quickAddClassBtn = document.getElementById('quickAddClassBtn');
    const classificationSelect = document.getElementById('classificationSelect');
    const applyClassificationBtn = document.getElementById('applyClassificationBtn');
    const oneClickAcceptInput = document.getElementById('oneClickAcceptInput');
    const selectedAnnotationSummary = document.getElementById('selectedAnnotationSummary');
    const bboxXInput = document.getElementById('bboxXInput');
    const bboxYInput = document.getElementById('bboxYInput');
    const bboxWInput = document.getElementById('bboxWInput');
    const bboxHInput = document.getElementById('bboxHInput');
    const applyBoxEditBtn = document.getElementById('applyBoxEditBtn');
    const logContextMenu = document.getElementById('logContextMenu');
    const logDeleteBtn = document.getElementById('logDeleteBtn');
    const logCancelBtn = document.getElementById('logCancelBtn');
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const resetViewBtn = document.getElementById('resetViewBtn');
    const zoomLevelDisplay = document.getElementById('zoomLevelDisplay');
    const helpBtn = document.getElementById('helpBtn');
    const helpModal = document.getElementById('helpModal');
    const closeHelpBtn = document.getElementById('closeHelpBtn');

    // --- APPLICATION STATE ---
    const appState = {
        classes: DEFAULT_CLASSES.map(cls => ({ ...cls })),
        images: [],
        currentImage: null,
        annotationsByImage: new Map(),
        candidateAnnotationsByImage: new Map(),
        annotationHistoryByImage: new Map(),
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
            preprocessParams: { ...DEFAULT_PREPROCESS_PARAMS }
        },
        samPresets: DEFAULT_SAM_PRESETS.map(preset => ({
            ...preset,
            params: { ...preset.params }
        })),
        matchSummary: null,
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
    let classSaveTimer = null;
    let samSettingsReturnFocus = null;
    let preprocessSettingsReturnFocus = null;
    let helpReturnFocus = null;

    // --- EVENT LISTENERS ---
    loadImageInput.addEventListener('change', handleImageLoad);
    openFolderInput.addEventListener('change', handleFolderLoad);
    runSamBtn.addEventListener('click', handleRunSam);
    clearCandidatesBtn.addEventListener('click', handleClearCandidates);
    openSamSettingsBtn.addEventListener('click', openSamSettingsModal);
    closeSamSettingsBtn.addEventListener('click', closeSamSettingsModal);
    samSettingsModal.addEventListener('click', event => {
        if (event.target === samSettingsModal) {
            closeSamSettingsModal();
        }
    });
    samPresetSelect.addEventListener('change', handleSamPresetChange);
    samAreaModeSelect.addEventListener('change', handleSamSettingsInput);
    [
        samPointsPerSideInput,
        samCropLayersInput,
        samCropOverlapInput,
        samCropDownscaleInput,
        samPointsPerBatchInput,
        samMinMaskRegionAreaInput,
        samMinObjectAreaInput,
        samMaxObjectAreaInput,
        samPredIouInput,
        samStabilityInput,
        samStabilityOffsetInput,
        samBoxNmsInput,
        samCropNmsInput,
        samUseM2mInput
    ].forEach(input => input.addEventListener('input', handleSamSettingsInput));
    samUseM2mInput.addEventListener('change', handleSamSettingsInput);
    applySamSettingsBtn.addEventListener('click', handleApplySamSettings);
    resetSamPresetBtn.addEventListener('click', handleResetSamPreset);
    preprocessMethodSelect.addEventListener('change', handlePreprocessMethodChange);
    applyPreprocessBtn.addEventListener('click', handleApplyPreprocess);
    restoreOriginalBtn.addEventListener('click', handleRestoreOriginal);
    openPreprocessSettingsBtn.addEventListener('click', openPreprocessSettingsModal);
    closePreprocessSettingsBtn.addEventListener('click', closePreprocessSettingsModal);
    preprocessSettingsModal.addEventListener('click', event => {
        if (event.target === preprocessSettingsModal) {
            closePreprocessSettingsModal();
        }
    });
    [
        preprocessGammaInput,
        preprocessClaheClipInput,
        preprocessClaheTileInput,
        preprocessUnsharpAmountInput,
        preprocessUnsharpRadiusInput,
        preprocessUnsharpThresholdInput,
        preprocessRetinexStrengthInput
    ].forEach(input => input.addEventListener('input', handlePreprocessSettingsInput));
    applyPreprocessSettingsBtn.addEventListener('click', handleApplyPreprocessSettings);
    resetPreprocessSettingsBtn.addEventListener('click', handleResetPreprocessSettings);
    manualAnnotationBtn.addEventListener('click', toggleManualMode);
    addClassBtn.addEventListener('click', handleAddClass);
    quickAddClassBtn.addEventListener('click', () => handleQuickAddClass());
    quickClassInput.addEventListener('keydown', event => {
        if (event.key !== 'Enter') return;
        event.preventDefault();
        const className = handleQuickAddClass();
        if (className && (appState.selectedCandidateIds.size > 0 || appState.selectedAnnotationIds.size > 0)) {
            processSelection(className);
        }
    });
    classManager.addEventListener('input', handleClassManagerInput);
    classManager.addEventListener('change', handleClassManagerChange);
    classManager.addEventListener('click', handleClassManagerClick);
    applyClassificationBtn.addEventListener('click', () => {
        processSelection(classificationSelect.value);
    });
    oneClickAcceptInput.addEventListener('change', updateButtonStates);
    applyBoxEditBtn.addEventListener('click', applyInspectorBoxEdit);
    [bboxXInput, bboxYInput, bboxWInput, bboxHInput].forEach(input => {
        input.addEventListener('keydown', event => {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            applyInspectorBoxEdit();
        });
    });
    undoBtn.addEventListener('click', handleUndoBatch);
    exportAnnotationFileBtn.addEventListener('click', handleExportAnnotationFile);
    loadAnnotationFileBtn.addEventListener('click', () => {
        if (appState.currentImage) loadAnnotationFileInput.click();
    });
    loadAnnotationFileInput.addEventListener('change', handleLoadAnnotationFile);
    loadServerAnnotationsBtn.addEventListener('click', handleLoadServerAnnotations);
    saveServerBtn.addEventListener('click', handleSaveServerAnnotations);
    saveAllServerBtn.addEventListener('click', handleSaveAllServerAnnotations);
    setAnnotationDirBtn.addEventListener('click', handleSetAnnotationDir);
    loadAnnotationSourceFilesBtn.addEventListener('click', () => annotationSourceFilesInput.click());
    loadAnnotationSourceFolderBtn.addEventListener('click', () => annotationSourceFolderInput.click());
    useServerAnnotationSourceBtn.addEventListener('click', useServerAnnotationSource);
    annotationSourceFilesInput.addEventListener('change', handleAnnotationSourceInput);
    annotationSourceFolderInput.addEventListener('change', handleAnnotationSourceInput);
    annotationFormatSelect.addEventListener('change', handleAnnotationFormatChange);
    refreshMatchesBtn.addEventListener('click', () => refreshAnnotationMatches({ showFeedback: true }));
    loadMatchedBtn.addEventListener('click', handleLoadMatchedAnnotations);
    prevImageBtn.addEventListener('click', () => selectImageByOffset(-1));
    nextImageBtn.addEventListener('click', () => selectImageByOffset(1));
    imageList.addEventListener('click', handleImageListClick);
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('wheel', handleWheel);
    window.addEventListener('keydown', handleKeyDown);
    annotationLogBody.addEventListener('click', handleLogClick);
    annotationLogBody.addEventListener('contextmenu', handleLogRightClick);
    logDeleteBtn.addEventListener('click', () => {
        if (appState.logItemToModify !== null) {
            deleteAnnotationById(appState.logItemToModify);
        }
    });
    logCancelBtn.addEventListener('click', () => logContextMenu.classList.add('hidden'));
    zoomInBtn.addEventListener('click', zoomIn);
    zoomOutBtn.addEventListener('click', zoomOut);
    resetViewBtn.addEventListener('click', () => {
        fitImageToView();
        draw();
    });
    helpBtn.addEventListener('click', openHelpModal);
    closeHelpBtn.addEventListener('click', closeHelpModal);
    helpModal.addEventListener('click', event => {
        if (event.target === helpModal) {
            closeHelpModal();
        }
    });
    window.addEventListener('click', event => {
        if (logContextMenu && !logContextMenu.contains(event.target)) {
            logContextMenu.classList.add('hidden');
        }
    });
    window.addEventListener('resize', () => {
        if (resizeCanvasToContainer()) {
            draw();
        }
    });
    window.addEventListener('beforeunload', handleBeforeUnload);

    // --- MAIN WORKFLOW ---
    async function handleImageLoad(event) {
        const file = event.target.files[0];
        event.target.value = '';
        if (!file) return;
        if (!confirmDiscardUnsavedChanges('Loading a new image will clear the current project state.')) return;

        resetState();
        const imageRecord = createImageRecord(file);
        appState.images = [imageRecord];
        initializeImageState(imageRecord.id);
        renderImageBrowser();
        await refreshAnnotationMatches({ showFeedback: false });
        await selectImageByIndex(0, { autoLoadAnnotations: true });
    }

    async function handleFolderLoad(event) {
        const files = Array.from(event.target.files || [])
            .filter(isSupportedImageFile)
            .sort((a, b) => imageSortName(a).localeCompare(imageSortName(b), undefined, { numeric: true }));
        event.target.value = '';
        if (files.length > 0 && !confirmDiscardUnsavedChanges('Opening a folder will clear the current project state.')) return;

        if (files.length === 0) {
            const msg = 'No supported images found in that folder.';
            updateStatus(msg);
            showToast(msg, 'error');
            return;
        }

        resetState();
        appState.images = files.map((file, index) => createImageRecord(file, null, index));
        appState.images.forEach(imageRecord => initializeImageState(imageRecord.id));
        renderImageBrowser();
        await refreshAnnotationMatches({ showFeedback: false });

        await selectImageByIndex(0, { autoLoadAnnotations: true });

        const msg = `Opened folder with ${files.length} images.`;
        updateStatus(msg);
        showToast(msg, 'success');
    }

    async function loadImageRecord(imageRecord) {
        if (!imageRecord) return false;
        if (imageRecord.originalImage) return true;

        setLoader(true, `Loading '${publicImageName(imageRecord)}'...`);

        try {
            const formData = new FormData();
            formData.append('image', imageRecord.file);

            const response = await apiFetch(apiPath('/api/load_image'), { method: 'POST', body: formData });
            if (!response.ok) {
                throw new Error(`Server error: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            imageRecord.originalImage = await loadImageElement(data.image_url);
            return true;
        } catch (error) {
            console.error('Image Load Error:', error);
            const errorMsg = `Error loading image: ${error.message}`;
            updateStatus(errorMsg);
            showToast(errorMsg, 'error');
            return false;
        } finally {
            setLoader(false);
        }
    }

    function loadImageElement(src) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error('Failed to load the image returned by the server.'));
            img.src = src;
        });
    }

    async function selectImageByOffset(offset) {
        const index = currentImageIndex();
        if (index === -1) return;
        await selectImageByIndex(index + offset, { autoLoadAnnotations: true });
    }

    async function selectImageByIndex(index, { autoLoadAnnotations = true } = {}) {
        if (index < 0 || index >= appState.images.length) return;

        const imageRecord = appState.images[index];
        const loaded = await loadImageRecord(imageRecord);
        if (!loaded) return;

        appState.currentImage = imageRecord;
        initializeImageState(imageRecord.id);
        resetInteractionState();

        updateCurrentImageDisplay();
        renderImageBrowser();
        resizeCanvasToContainer();
        fitImageToView();
        updateAnnotationLog();
        draw();
        updateButtonStates();

        const loadedAnnotationCount = currentAnnotations().length;
        let autoLoadedAnnotations = false;
        if (autoLoadAnnotations && !imageRecord.serverAnnotationsChecked && loadedAnnotationCount === 0) {
            autoLoadedAnnotations = await loadServerAnnotationsForCurrentImage({ silentWhenMissing: true });
        }

        if (!autoLoadedAnnotations) {
            const msg = `Loaded '${publicImageName(imageRecord)}'. Ready to process.`;
            updateStatus(msg);
        }
    }

    function handleImageListClick(event) {
        const item = event.target.closest('.image-list-item');
        if (!item) return;

        const index = parseInt(item.dataset.imageIndex, 10);
        if (Number.isInteger(index)) {
            selectImageByIndex(index, { autoLoadAnnotations: true });
        }
    }

    function renderImageBrowser() {
        imageList.innerHTML = '';

        if (appState.images.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'image-list-empty';
            empty.textContent = 'No folder loaded.';
            imageList.appendChild(empty);
            updateCurrentImageDisplay();
            return;
        }

        const currentIndex = currentImageIndex();
        appState.images.forEach((imageRecord, index) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'image-list-item';
            item.dataset.imageIndex = String(index);
            if (index === currentIndex) item.classList.add('active');
            if (appState.dirtyImages.has(imageRecord.id)) item.classList.add('dirty-image');
            const match = appState.annotationMatchesByImage.get(imageRecord.id);
            if (match?.status === 'missing') item.classList.add('match-missing');
            if (match?.status === 'ambiguous') item.classList.add('match-ambiguous');
            item.title = publicImagePath(imageRecord);

            const name = document.createElement('span');
            name.className = 'image-list-name';
            name.textContent = publicImageName(imageRecord);

            const badges = document.createElement('span');
            badges.className = 'image-list-badges';
            getImageBadges(imageRecord).forEach(badgeInfo => {
                const badge = document.createElement('span');
                badge.className = `image-badge ${badgeInfo.type}`;
                badge.textContent = badgeInfo.label;
                badge.title = badgeInfo.title;
                badges.appendChild(badge);
            });

            item.appendChild(name);
            item.appendChild(badges);
            imageList.appendChild(item);
        });
        updateCurrentImageDisplay();
    }

    function getImageBadges(imageRecord) {
        const badges = [];
        const annotations = appState.annotationsByImage.get(imageRecord.id) || [];
        const candidates = appState.candidateAnnotationsByImage.get(imageRecord.id) || [];

        if (annotations.length > 0) {
            badges.push({ type: 'annotated', label: `Ann ${annotations.length}`, title: `${annotations.length} annotations` });
        }
        if (appState.dirtyImages.has(imageRecord.id)) {
            badges.push({ type: 'dirty', label: 'Unsaved', title: 'Unsaved changes' });
        }
        if (candidates.length > 0) {
            badges.push({ type: 'candidates', label: `Cand ${candidates.length}`, title: `${candidates.length} SAM candidates` });
        }
        if (hasActivePreprocess(imageRecord)) {
            badges.push({
                type: 'preprocess',
                label: preprocessBadgeLabel(imageRecord.preprocessMethod),
                title: `${preprocessLabel(imageRecord.preprocessMethod)} is active for display; SAM applies the same preprocessing on the server`
            });
        }
        if (imageRecord.samHasRun && candidates.length === 0) {
            badges.push({ type: 'sam', label: 'SAM 0', title: 'SAM has run but no candidates are currently shown' });
        }

        const match = appState.annotationMatchesByImage.get(imageRecord.id);
        if (match) {
            if (match.status === 'matched') {
                const matchFormat = formatLabel(match.format || currentAnnotationFormat());
                badges.push({
                    type: 'matched',
                    label: 'Matched',
                    title: `Matched ${matchFormat}: ${publicAnnotationPath(match.path)}${match.annotation_count ? ` (${match.annotation_count} annotations)` : ''}`
                });
            } else if (match.status === 'ambiguous') {
                badges.push({ type: 'ambiguous', label: 'Ambiguous', title: match.message || 'Ambiguous annotation match' });
            } else if (match.status === 'missing') {
                badges.push({ type: 'missing', label: 'Missing', title: 'No matching annotation file found' });
            }
        }

        return badges;
    }

    function imageStateSummary(imageRecord) {
        const annotations = appState.annotationsByImage.get(imageRecord.id) || [];
        const candidates = appState.candidateAnnotationsByImage.get(imageRecord.id) || [];
        const parts = [
            `${annotations.length} annotations`,
            `${candidates.length} candidates`,
        ];

        if (appState.dirtyImages.has(imageRecord.id)) {
            parts.push('unsaved');
        }
        if (hasActivePreprocess(imageRecord)) {
            parts.push(`${preprocessLabel(imageRecord.preprocessMethod)} display/server SAM preprocessing`);
        }

        const match = appState.annotationMatchesByImage.get(imageRecord.id);
        if (match?.status) {
            parts.push(`${formatLabel(match.format || currentAnnotationFormat())} ${match.status}`);
        }

        return parts.join(' | ');
    }

    function preprocessLabel(method) {
        return PREPROCESS_METHODS[method]?.label || 'Preprocessing';
    }

    function preprocessBadgeLabel(method) {
        return PREPROCESS_METHODS[method]?.badge || preprocessLabel(method);
    }

    function selectedPreprocessMethod() {
        return preprocessMethodSelect.value || 'original';
    }

    function hasActivePreprocess(imageRecord = appState.currentImage) {
        return !!(imageRecord && imageRecord.processedImage && imageRecord.preprocessMethod && imageRecord.preprocessMethod !== 'original');
    }

    function currentPreprocessParams() {
        return {
            ...DEFAULT_PREPROCESS_PARAMS,
            ...(appState.projectSettings.preprocessParams || {})
        };
    }

    function samPreprocessPayload(imageRecord = appState.currentImage) {
        if (!hasActivePreprocess(imageRecord)) {
            return { method: 'original', params: {} };
        }
        return {
            method: imageRecord.preprocessMethod || 'original',
            params: imageRecord.preprocessParams || currentPreprocessParams()
        };
    }

    function numberFromInput(input, fallback) {
        const value = Number.parseFloat(input.value);
        return Number.isFinite(value) ? value : fallback;
    }

    function readPreprocessSettingsFromInputs() {
        const defaults = DEFAULT_PREPROCESS_PARAMS;
        return {
            clahe_clip_limit: numberFromInput(preprocessClaheClipInput, defaults.clahe_clip_limit),
            clahe_tile_grid_size: numberFromInput(preprocessClaheTileInput, defaults.clahe_tile_grid_size),
            gamma: numberFromInput(preprocessGammaInput, defaults.gamma),
            unsharp_amount: numberFromInput(preprocessUnsharpAmountInput, defaults.unsharp_amount),
            unsharp_radius: numberFromInput(preprocessUnsharpRadiusInput, defaults.unsharp_radius),
            unsharp_threshold: numberFromInput(preprocessUnsharpThresholdInput, defaults.unsharp_threshold),
            retinex_strength: numberFromInput(preprocessRetinexStrengthInput, defaults.retinex_strength)
        };
    }

    function syncPreprocessSettingsInputs(params = currentPreprocessParams()) {
        preprocessGammaInput.value = params.gamma;
        preprocessClaheClipInput.value = params.clahe_clip_limit;
        preprocessClaheTileInput.value = params.clahe_tile_grid_size;
        preprocessUnsharpAmountInput.value = params.unsharp_amount;
        preprocessUnsharpRadiusInput.value = params.unsharp_radius;
        preprocessUnsharpThresholdInput.value = params.unsharp_threshold;
        preprocessRetinexStrengthInput.value = params.retinex_strength;
    }

    function handlePreprocessMethodChange() {
        updateButtonStates();
    }

    function handlePreprocessSettingsInput() {
        appState.projectSettings.preprocessParams = readPreprocessSettingsFromInputs();
        updateButtonStates();
    }

    function handleApplyPreprocessSettings() {
        appState.projectSettings.preprocessParams = readPreprocessSettingsFromInputs();
        closePreprocessSettingsModal();
        const msg = 'Preprocessing expert settings updated.';
        updateStatus(msg);
        showToast(msg, 'success');
    }

    function handleResetPreprocessSettings() {
        appState.projectSettings.preprocessParams = { ...DEFAULT_PREPROCESS_PARAMS };
        syncPreprocessSettingsInputs();
        updateButtonStates();
        const msg = 'Preprocessing settings reset to defaults.';
        updateStatus(msg);
        showToast(msg, 'info');
    }

    function openPreprocessSettingsModal() {
        preprocessSettingsReturnFocus = document.activeElement;
        syncPreprocessSettingsInputs();
        preprocessSettingsModal.classList.remove('hidden');
        preprocessGammaInput.focus();
    }

    function closePreprocessSettingsModal() {
        preprocessSettingsModal.classList.add('hidden');
        if (preprocessSettingsReturnFocus && typeof preprocessSettingsReturnFocus.focus === 'function') {
            preprocessSettingsReturnFocus.focus();
        }
        preprocessSettingsReturnFocus = null;
    }

    function openHelpModal() {
        helpReturnFocus = document.activeElement;
        helpModal.classList.remove('hidden');
        closeHelpBtn.focus();
    }

    function closeHelpModal() {
        helpModal.classList.add('hidden');
        if (helpReturnFocus && typeof helpReturnFocus.focus === 'function') {
            helpReturnFocus.focus();
        }
        helpReturnFocus = null;
    }

    async function handleApplyPreprocess() {
        const imageRecord = appState.currentImage;
        if (!imageRecord) return;
        const method = selectedPreprocessMethod();
        if (method === 'original') {
            handleRestoreOriginal();
            return;
        }

        const methodLabel = preprocessLabel(method);
        setLoader(true, `Applying ${methodLabel} on server...`);

        try {
            const formData = new FormData();
            formData.append('image', imageRecord.file);
            formData.append('method', method);
            formData.append('params', JSON.stringify(currentPreprocessParams()));

            const response = await apiFetch(apiPath('/api/preprocess'), { method: 'POST', body: formData });
            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            const processedImg = new Image();
            processedImg.onload = () => {
                imageRecord.processedImage = processedImg;
                imageRecord.preprocessMethod = data.method || method;
                imageRecord.preprocessLabel = data.label || methodLabel;
                imageRecord.preprocessParams = data.params || currentPreprocessParams();
                imageRecord.claheApplied = imageRecord.preprocessMethod === 'clahe';
                updateCurrentImageDisplay();
                renderImageBrowser();
                draw();

                const successMsg = `${imageRecord.preprocessLabel} active: display uses the processed image; SAM will apply the same preprocessing on the server.`;
                updateStatus(successMsg);
                showToast(successMsg, 'success');
                updateButtonStates();
            };
            processedImg.onerror = () => {
                const errorMsg = `Failed to load the ${methodLabel} image returned by the server.`;
                updateStatus(errorMsg);
                showToast(errorMsg, 'error');
            };
            processedImg.src = data.image;
        } catch (error) {
            console.error('Preprocessing Error:', error);
            const errorMsg = `Failed to apply ${methodLabel}.`;
            updateStatus(errorMsg);
            showToast(errorMsg, 'error');
        } finally {
            setLoader(false);
        }
    }

    function handleRestoreOriginal() {
        const imageRecord = appState.currentImage;
        if (!imageRecord || !hasActivePreprocess(imageRecord)) return;

        const previousLabel = preprocessLabel(imageRecord.preprocessMethod);

        imageRecord.processedImage = null;
        imageRecord.preprocessMethod = 'original';
        imageRecord.preprocessLabel = '';
        imageRecord.preprocessParams = null;
        imageRecord.claheApplied = false;
        updateCurrentImageDisplay();
        renderImageBrowser();
        draw();

        const msg = `${previousLabel} inactive: display and SAM input restored to the original image.`;
        updateStatus(msg);
        showToast(msg, 'info');
        updateButtonStates();
    }

    async function handleRunSam() {
        const imageRecord = appState.currentImage;
        if (!imageRecord) return;

        const existingCandidateCount = currentCandidates().length;
        const existingAnnotationCount = currentAnnotations().length;
        const keepExistingAnnotations = keepAnnotationsInput.checked;

        if (
            existingCandidateCount > 0
            && !window.confirm(`Re-run SAM2 and replace ${existingCandidateCount} current candidates? Existing annotations will be ${keepExistingAnnotations ? 'kept' : 'cleared'}.`)
        ) {
            return;
        }

        if (
            !keepExistingAnnotations
            && existingAnnotationCount > 0
            && !window.confirm(`Re-running with "Keep existing annotations" off will clear ${existingAnnotationCount} final annotations after SAM succeeds. Continue?`)
        ) {
            return;
        }

        setLoader(true, 'Running SAM2 & filtering on server...');

        try {
            const formData = new FormData();
            formData.append('image', imageRecord.file, imageRecord.name);
            formData.append('sam_settings', JSON.stringify(currentSamSettingsPayload()));
            const samPreprocess = samPreprocessPayload(imageRecord);
            formData.append('preprocess_method', samPreprocess.method);
            formData.append('preprocess_params', JSON.stringify(samPreprocess.params));

            const response = await apiFetch(apiPath('/api/run_sam'), { method: 'POST', body: formData });
            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            if (data.error) throw new Error(data.error);
            if (data.sam_settings) {
                applySamSettings(data.sam_settings);
            }
            if (data.preprocess?.method && data.preprocess.method !== 'original') {
                imageRecord.preprocessMethod = data.preprocess.method;
                imageRecord.preprocessLabel = data.preprocess.label || preprocessLabel(data.preprocess.method);
                imageRecord.preprocessParams = data.preprocess.params || imageRecord.preprocessParams;
            }

            const candidateAnnotations = data.masks.map(mask => ({
                id: `cand_${appState.candidateCounter++}`,
                bbox: mask.bbox,
                type: 'sam_candidate',
                ...annotationMaskMetadata({
                    contour: mask.contour,
                    mask_area: mask.mask_area,
                    source: mask.source || 'sam2',
                    predicted_iou: mask.predicted_iou,
                    stability_score: mask.stability_score
                })
            }));

            setCurrentCandidates(candidateAnnotations);
            appState.selectedCandidateIds.clear();
            if (!keepExistingAnnotations) {
                setCurrentAnnotations([]);
                setCurrentHistory([]);
                appState.selectedAnnotationIds.clear();
                if (existingAnnotationCount > 0) markCurrentImageDirty();
            }
            imageRecord.samHasRun = true;

            const actionText = existingCandidateCount > 0 ? 'Replaced candidates' : 'Found candidate masks';
            const annotationText = keepExistingAnnotations
                ? `Kept ${existingAnnotationCount} existing annotations.`
                : `Cleared ${existingAnnotationCount} existing annotations.`;
            const successMsg = `${actionText}: ${candidateAnnotations.length} with ${currentSamPresetLabel()}. ${annotationText}`;
            updateStatus(successMsg);
            showToast(successMsg, 'success');
            renderImageBrowser();
            updateAnnotationLog();
            draw();
        } catch (error) {
            console.error('SAM Error:', error);
            const errorMsg = `Failed to run SAM: ${error.message}`;
            updateStatus(errorMsg);
            showToast(errorMsg, 'error');
        } finally {
            setLoader(false);
            updateButtonStates();
        }
    }

    function handleClearCandidates() {
        const imageRecord = appState.currentImage;
        if (!imageRecord) return;

        const candidateCount = currentCandidates().length;
        if (candidateCount === 0) return;

        if (!window.confirm(`Clear ${candidateCount} current SAM candidates? Existing annotations will be kept.`)) {
            return;
        }

        setCurrentCandidates([]);
        appState.selectedCandidateIds.clear();
        imageRecord.samHasRun = false;

        const msg = `Cleared ${candidateCount} SAM candidates.`;
        updateStatus(msg);
        showToast(msg, 'info');
        renderImageBrowser();
        updateAnnotationLog();
        draw();
        updateButtonStates();
    }

    function processSelection(className) {
        if (!classExists(className)) {
            const msg = appState.classes.length === 0
                ? 'Create a class before applying annotations.'
                : 'Please choose a valid class before applying annotations.';
            updateStatus(msg);
            showToast(msg, 'error');
            quickClassInput.focus();
            return;
        }

        const relabeledCount = relabelSelectedAnnotations(className);
        const convertedCount = convertSelectedCandidates(className);
        const totalCount = relabeledCount + convertedCount;

        if (totalCount === 0) return;

        markCurrentImageDirty();
        updateAnnotationLog();
        renderImageBrowser();

        const msgParts = [];
        if (convertedCount > 0) msgParts.push(`processed ${convertedCount} masks`);
        if (relabeledCount > 0) msgParts.push(`relabeled ${relabeledCount} annotations`);
        const msg = `${capitalizeFirst(msgParts.join(' and '))} as "${className}".`;
        updateStatus(msg);
        showToast(msg, 'info');
        draw();
        updateButtonStates();
    }

    function convertSelectedCandidates(className) {
        if (appState.selectedCandidateIds.size === 0) return 0;

        const batch = { type: 'convert_candidates', convertedAnnotations: [], originalCandidates: [] };
        const newAnnotations = [];
        const remainingCandidates = [];
        const selectedIds = new Set(appState.selectedCandidateIds);

        currentCandidates().forEach(candidate => {
            if (selectedIds.has(candidate.id)) {
                const newAnnotation = annotationFromCandidate(candidate, className);
                if (!newAnnotation) return;
                newAnnotations.push(newAnnotation);
                batch.convertedAnnotations.push(newAnnotation);
                batch.originalCandidates.push(candidate);
            } else {
                remainingCandidates.push(candidate);
            }
        });

        if (batch.convertedAnnotations.length > 0) {
            currentHistory().push(batch);
        }

        currentAnnotations().push(...newAnnotations);
        setCurrentCandidates(remainingCandidates);
        appState.selectedCandidateIds.clear();

        return newAnnotations.length;
    }

    function annotationFromCandidate(candidate, className) {
        const bbox = clampBboxToImage(candidate.bbox);
        if (!bbox) return null;

        appState.annotationCounter++;
        return {
            id: appState.annotationCounter,
            bbox,
            class: className,
            type: 'sam_final',
            originalCandidateId: candidate.id,
            ...annotationMaskMetadata({
                ...candidate,
                source: candidate.source || 'sam2'
            })
        };
    }

    function acceptSingleCandidate(candidate, className) {
        if (!classExists(className)) {
            const msg = appState.classes.length === 0
                ? 'Create a class before accepting candidates.'
                : 'Choose a valid class before accepting candidates.';
            updateStatus(msg);
            showToast(msg, 'error');
            updateButtonStates();
            return false;
        }

        const newAnnotation = annotationFromCandidate(candidate, className);
        if (!newAnnotation) {
            const msg = 'Candidate box is outside the image bounds.';
            updateStatus(msg);
            showToast(msg, 'error');
            return false;
        }
        currentAnnotations().push(newAnnotation);
        setCurrentCandidates(currentCandidates().filter(item => item.id !== candidate.id));
        appState.selectedCandidateIds.delete(candidate.id);
        appState.selectedAnnotationIds.clear();
        currentHistory().push({
            type: 'convert_candidates',
            convertedAnnotations: [newAnnotation],
            originalCandidates: [candidate]
        });
        markCurrentImageDirty();
        updateAnnotationLog();
        renderImageBrowser();
        draw();
        updateButtonStates();

        const msg = `Accepted candidate #${newAnnotation.id} as "${className}".`;
        updateStatus(msg);
        showToast(msg, 'success');
        return true;
    }

    function relabelSelectedAnnotations(className) {
        if (appState.selectedAnnotationIds.size === 0) return 0;

        const changes = [];
        currentAnnotations().forEach(annotation => {
            if (!appState.selectedAnnotationIds.has(annotation.id) || annotation.class === className) return;

            changes.push({
                id: annotation.id,
                oldClass: annotation.class,
                newClass: className
            });
            annotation.class = className;
        });

        if (changes.length > 0) {
            currentHistory().push({ type: 'relabel_annotations', changes });
        }

        return changes.length;
    }

    function handleUndoBatch() {
        const history = currentHistory();
        if (history.length === 0) return;

        const lastBatch = history.pop();
        let msg = '';

        if (lastBatch.type === 'relabel_annotations') {
            const changesById = new Map(lastBatch.changes.map(change => [change.id, change]));
            currentAnnotations().forEach(annotation => {
                const change = changesById.get(annotation.id);
                if (change) annotation.class = change.oldClass;
            });
            msg = `Reverted relabeling for ${lastBatch.changes.length} annotations.`;
        } else if (lastBatch.type === 'geometry_edit') {
            const changesById = new Map(lastBatch.changes.map(change => [change.id, change]));
            currentAnnotations().forEach(annotation => {
                const change = changesById.get(annotation.id);
                if (change) annotation.bbox = change.oldBbox.slice();
            });
            msg = `Reverted box edit for ${lastBatch.changes.length} annotations.`;
        } else {
            const idsToRevert = new Set(lastBatch.convertedAnnotations.map(annotation => annotation.id));
            setCurrentAnnotations(currentAnnotations().filter(annotation => !idsToRevert.has(annotation.id)));
            currentCandidates().push(...lastBatch.originalCandidates);
            msg = `Reverted last batch of ${lastBatch.originalCandidates.length} annotations.`;
        }

        updateAnnotationLog();
        markCurrentImageDirty();
        renderImageBrowser();
        updateAnnotationInspector();
        updateStatus(msg);
        showToast(msg, 'info');
        draw();
        updateButtonStates();
    }

    // --- CLASS MANAGEMENT ---
    function handleAddClass() {
        createClassFromName(getUniqueClassName(), { select: true });
    }

    function handleQuickAddClass() {
        return createClassFromName(quickClassInput.value, { select: true });
    }

    function createClassFromName(rawName, { select = true } = {}) {
        const className = normalizeClassName(String(rawName || ''));
        if (!className) {
            const msg = 'Enter a class name first.';
            updateStatus(msg);
            showToast(msg, 'error');
            quickClassInput.focus();
            return null;
        }

        const existingClass = appState.classes.find(cls => cls.name === className);
        if (existingClass) {
            if (select) renderClassControls(existingClass.name);
            quickClassInput.value = '';
            const msg = `Class "${className}" already exists.`;
            updateStatus(msg);
            showToast(msg, 'info');
            return existingClass.name;
        }

        const newClass = {
            name: className,
            color: CLASS_COLOR_PALETTE[appState.classes.length % CLASS_COLOR_PALETTE.length],
            hotkey: getFirstAvailableHotkey(className)
        };

        appState.classes.push(newClass);
        scheduleProjectClassesSave();
        renderClassControls(select ? newClass.name : classificationSelect.value);
        quickClassInput.value = '';

        const msg = `Added class "${newClass.name}".`;
        updateStatus(msg);
        showToast(msg, 'success');
        return newClass.name;
    }

    function handleClassManagerInput(event) {
        if (event.target.classList.contains('class-hotkey-input')) {
            event.target.value = normalizeHotkey(event.target.value).toUpperCase();
            return;
        }

        if (event.target.classList.contains('class-color-input')) {
            const index = getClassRowIndex(event.target);
            if (index === null) return;
            appState.classes[index].color = event.target.value;
            scheduleProjectClassesSave();
            draw();
        }
    }

    function handleClassManagerChange(event) {
        const index = getClassRowIndex(event.target);
        if (index === null) return;

        if (event.target.classList.contains('class-name-input')) {
            commitClassRename(index, event.target.value);
            return;
        }

        if (event.target.classList.contains('class-hotkey-input')) {
            commitClassHotkey(index, event.target.value);
            return;
        }

        if (event.target.classList.contains('class-color-input')) {
            appState.classes[index].color = event.target.value;
            scheduleProjectClassesSave();
            renderClassControls(classificationSelect.value);
            draw();
        }
    }

    function handleClassManagerClick(event) {
        const deleteButton = event.target.closest('.class-delete-btn');
        if (!deleteButton) return;

        const index = getClassRowIndex(deleteButton);
        if (index === null) return;
        deleteClass(index);
    }

    function commitClassRename(index, rawName) {
        const classInfo = appState.classes[index];
        if (!classInfo) return;

        const oldName = classInfo.name;
        const newName = normalizeClassName(rawName);

        if (!newName) {
            showToast('Class name cannot be empty.', 'error');
            renderClassControls(oldName);
            return;
        }

        if (appState.classes.some((cls, clsIndex) => clsIndex !== index && cls.name === newName)) {
            showToast(`Class "${newName}" already exists.`, 'error');
            renderClassControls(oldName);
            return;
        }

        if (newName === oldName) {
            renderClassControls(oldName);
            return;
        }

        const affectedCount = countAnnotationsWithClass(oldName);
        if (
            affectedCount > 0
            && !window.confirm(`Rename "${oldName}" to "${newName}" and update ${affectedCount} existing annotations?`)
        ) {
            renderClassControls(oldName);
            return;
        }

        classInfo.name = newName;
        const changedCount = renameAnnotationClass(oldName, newName);
        scheduleProjectClassesSave();
        renderClassControls(newName);
        updateAnnotationLog();
        draw();

        const msg = changedCount > 0
            ? `Renamed "${oldName}" to "${newName}" and updated ${changedCount} annotations.`
            : `Renamed "${oldName}" to "${newName}".`;
        updateStatus(msg);
        showToast(msg, 'success');
    }

    function commitClassHotkey(index, rawHotkey) {
        const classInfo = appState.classes[index];
        if (!classInfo) return;

        const hotkey = normalizeHotkey(rawHotkey);
        if (hotkey && appState.classes.some((cls, clsIndex) => clsIndex !== index && cls.hotkey === hotkey)) {
            showToast(`Hotkey "${hotkey.toUpperCase()}" is already assigned.`, 'error');
            renderClassControls(classificationSelect.value);
            return;
        }

        classInfo.hotkey = hotkey;
        scheduleProjectClassesSave();
        renderClassControls(classificationSelect.value);
    }

    function deleteClass(index) {
        const classToDelete = appState.classes[index];
        if (!classToDelete) return;

        const affectedCount = countAnnotationsWithClass(classToDelete.name);

        if (affectedCount > 0) {
            const confirmed = window.confirm(
                `Are you sure you want to delete the class "${classToDelete.name}" and ${affectedCount} annotation${affectedCount === 1 ? '' : 's'}?`
            );
            if (!confirmed) return;
        }

        appState.classes.splice(index, 1);
        scheduleProjectClassesSave();

        const deletedCount = deleteAnnotationsWithClass(classToDelete.name);

        const preferredClass = classificationSelect.value === classToDelete.name
            ? ''
            : classificationSelect.value;
        renderClassControls(preferredClass);
        updateAnnotationLog();
        updateAnnotationInspector();
        renderImageBrowser();
        draw();

        const msg = deletedCount > 0
            ? `Deleted "${classToDelete.name}" and ${deletedCount} annotations.`
            : `Deleted class "${classToDelete.name}".`;
        updateStatus(msg);
        showToast(msg, 'info');
        updateButtonStates();
    }

    // --- CANVAS INTERACTION ---
    function toggleManualMode() {
        appState.isManualMode = !appState.isManualMode;

        if (appState.isManualMode) {
            appState.isPanning = false;
        } else {
            appState.isAwaitingChoice = false;
            appState.choiceInfo = null;
        }

        manualAnnotationBtn.classList.toggle('active', appState.isManualMode);
        canvas.style.cursor = appState.isManualMode ? 'crosshair' : 'grab';
        updateStatus(appState.isManualMode ? 'Manual Box mode enabled. Click and drag.' : 'Manual Box mode disabled.');
        updateButtonStates();
        draw();
    }

    function handleMouseDown(event) {
        if (event.button !== 0) return;

        logContextMenu.classList.add('hidden');

        if (appState.isAwaitingChoice && appState.choiceInfo) {
            const screenPoint = getScreenPoint(event.clientX, event.clientY);
            for (const button of appState.choiceInfo.buttons) {
                if (pointInsideRect(screenPoint, button)) {
                    if (button.action === 'Cancel') {
                        cancelManualAnnotation();
                    } else if (button.action === NEW_CLASS_ACTION) {
                        promptCreateClassForManualAnnotation();
                    } else {
                        finalizeAnnotation(button.action);
                    }
                    return;
                }
            }
        }

        if (appState.isManualMode) {
            appState.isDrawing = true;
            appState.isAwaitingChoice = false;
            appState.manualBoxStart = getScreenPoint(event.clientX, event.clientY);
            return;
        }

        const rect = canvas.getBoundingClientRect();
        const worldPoint = getWorldPoint(event.clientX - rect.left, event.clientY - rect.top);

        const resizeHit = getSelectedResizeHandleAtPoint(worldPoint);
        if (resizeHit) {
            startBoxEdit('resize', worldPoint, [resizeHit.annotation.id], resizeHit.handle);
            canvas.style.cursor = cursorForHandle(resizeHit.handle);
            return;
        }

        const selectedMoveAnnotation = findAnnotationAtPoint(worldPoint, annotation => (
            appState.selectedAnnotationIds.has(annotation.id)
        ));
        if (selectedMoveAnnotation && !event.shiftKey && !event.ctrlKey && !event.metaKey) {
            startBoxEdit('move', worldPoint, Array.from(appState.selectedAnnotationIds));
            canvas.style.cursor = 'move';
            return;
        }

        const clickedAnnotation = findAnnotationAtPoint(worldPoint);
        if (clickedAnnotation) {
            if (event.shiftKey || event.ctrlKey || event.metaKey) {
                if (appState.selectedAnnotationIds.has(clickedAnnotation.id)) {
                    appState.selectedAnnotationIds.delete(clickedAnnotation.id);
                } else {
                    appState.selectedAnnotationIds.add(clickedAnnotation.id);
                }
            } else {
                appState.selectedAnnotationIds.clear();
                appState.selectedAnnotationIds.add(clickedAnnotation.id);
            }
            appState.selectedCandidateIds.clear();
            updateAnnotationLog();
            updateAnnotationInspector();
            draw();
            updateButtonStates();
            return;
        }

        const clickedCandidate = findCandidateAtPoint(worldPoint);
        if (clickedCandidate) {
            if (
                oneClickAcceptInput.checked
                && !event.shiftKey
                && !event.ctrlKey
                && !event.metaKey
            ) {
                acceptSingleCandidate(clickedCandidate, classificationSelect.value);
                return;
            }

            if (appState.selectedCandidateIds.has(clickedCandidate.id)) {
                appState.selectedCandidateIds.delete(clickedCandidate.id);
            } else {
                appState.selectedCandidateIds.add(clickedCandidate.id);
            }
            appState.selectedAnnotationIds.clear();
            updateAnnotationLog();
            updateAnnotationInspector();
            draw();
            updateButtonStates();
            return;
        }

        appState.isPanning = true;
        appState.lastPanPoint = { x: event.clientX, y: event.clientY };
        canvas.style.cursor = 'grabbing';
    }

    function handleMouseMove(event) {
        if (appState.boxEditMode) {
            const rect = canvas.getBoundingClientRect();
            const worldPoint = getWorldPoint(event.clientX - rect.left, event.clientY - rect.top);
            updateBoxEdit(worldPoint);
            draw();
            updateAnnotationInspector();
            return;
        }

        if (appState.isPanning) {
            appState.cameraOffset.x += event.clientX - appState.lastPanPoint.x;
            appState.cameraOffset.y += event.clientY - appState.lastPanPoint.y;
            appState.lastPanPoint = { x: event.clientX, y: event.clientY };
            draw();
            return;
        }

        if (appState.isDrawing) {
            const currentPoint = getScreenPoint(event.clientX, event.clientY);
            appState.currentManualBox = {
                x: appState.manualBoxStart.x,
                y: appState.manualBoxStart.y,
                w: currentPoint.x - appState.manualBoxStart.x,
                h: currentPoint.y - appState.manualBoxStart.y
            };
            draw();
            return;
        }

        updateCanvasEditCursor(event);
    }

    function handleMouseUp() {
        if (appState.boxEditMode) {
            commitBoxEdit();
            canvas.style.cursor = appState.isManualMode ? 'crosshair' : 'grab';
            return;
        }

        if (appState.isPanning) {
            appState.isPanning = false;
            canvas.style.cursor = appState.isManualMode ? 'crosshair' : 'grab';
            return;
        }

        if (appState.isDrawing && appState.isManualMode && appState.currentManualBox) {
            appState.isDrawing = false;
            if (Math.abs(appState.currentManualBox.w) > 5 && Math.abs(appState.currentManualBox.h) > 5) {
                appState.isAwaitingChoice = true;
                setupChoiceButtons();
            } else {
                appState.currentManualBox = null;
            }
            draw();
        }
    }

    function startBoxEdit(mode, worldPoint, annotationIds, handle = null) {
        appState.boxEditMode = mode;
        appState.boxEditHandle = handle;
        appState.boxEditStartWorld = { ...worldPoint };
        appState.boxEditOriginalBboxes = new Map();

        annotationIds.forEach(id => {
            const annotation = findAnnotationById(id);
            if (annotation) {
                appState.boxEditOriginalBboxes.set(id, annotation.bbox.slice());
            }
        });
    }

    function updateBoxEdit(worldPoint) {
        const dx = worldPoint.x - appState.boxEditStartWorld.x;
        const dy = worldPoint.y - appState.boxEditStartWorld.y;

        for (const [id, originalBbox] of appState.boxEditOriginalBboxes.entries()) {
            const annotation = findAnnotationById(id);
            if (!annotation) continue;

            if (appState.boxEditMode === 'move') {
                annotation.bbox = clampMovedBboxToImage([
                    originalBbox[0] + dx,
                    originalBbox[1] + dy,
                    originalBbox[2],
                    originalBbox[3]
                ]) || annotation.bbox;
            } else if (appState.boxEditMode === 'resize') {
                annotation.bbox = clampBboxToImage(
                    resizeBbox(originalBbox, appState.boxEditHandle, dx, dy)
                ) || annotation.bbox;
            }
        }
    }

    function commitBoxEdit() {
        const changes = [];

        for (const [id, oldBbox] of appState.boxEditOriginalBboxes.entries()) {
            const annotation = findAnnotationById(id);
            if (!annotation) continue;

            const newBbox = annotation.bbox.slice();
            if (!bboxesEqual(oldBbox, newBbox)) {
                changes.push({ id, oldBbox, newBbox });
            }
        }

        appState.boxEditMode = null;
        appState.boxEditHandle = null;
        appState.boxEditStartWorld = null;
        appState.boxEditOriginalBboxes = new Map();

        if (changes.length > 0) {
            currentHistory().push({ type: 'geometry_edit', changes });
            markCurrentImageDirty();
            renderImageBrowser();
            updateAnnotationLog();
            updateAnnotationInspector();
            updateStatus(`Updated ${changes.length} annotation boxes.`);
            updateButtonStates();
        }
    }

    function cancelBoxEdit() {
        for (const [id, oldBbox] of appState.boxEditOriginalBboxes.entries()) {
            const annotation = findAnnotationById(id);
            if (annotation) annotation.bbox = oldBbox.slice();
        }

        appState.boxEditMode = null;
        appState.boxEditHandle = null;
        appState.boxEditStartWorld = null;
        appState.boxEditOriginalBboxes = new Map();
        canvas.style.cursor = appState.isManualMode ? 'crosshair' : 'grab';
        updateAnnotationInspector();
        draw();
    }

    function arrowKeyDelta(key) {
        if (key === 'ArrowLeft') return { dx: -1, dy: 0 };
        if (key === 'ArrowRight') return { dx: 1, dy: 0 };
        if (key === 'ArrowUp') return { dx: 0, dy: -1 };
        if (key === 'ArrowDown') return { dx: 0, dy: 1 };
        return null;
    }

    function nudgeSelectedAnnotations(dx, dy) {
        const changes = [];
        currentAnnotations().forEach(annotation => {
            if (!appState.selectedAnnotationIds.has(annotation.id)) return;

            const oldBbox = annotation.bbox.slice();
            const newBbox = clampMovedBboxToImage([
                oldBbox[0] + dx,
                oldBbox[1] + dy,
                oldBbox[2],
                oldBbox[3]
            ]) || oldBbox.slice();
            if (bboxesEqual(oldBbox, newBbox)) return;
            annotation.bbox = newBbox;
            changes.push({ id: annotation.id, oldBbox, newBbox: newBbox.slice() });
        });

        if (changes.length === 0) return;

        currentHistory().push({ type: 'geometry_edit', changes });
        markCurrentImageDirty();
        renderImageBrowser();
        updateAnnotationLog();
        updateAnnotationInspector();
        draw();
        updateStatus(`Moved ${changes.length} selected box${changes.length === 1 ? '' : 'es'} by ${dx}, ${dy}.`);
        updateButtonStates();
    }

    function resizeBbox(bbox, handle, dx, dy) {
        const x1 = bbox[0];
        const y1 = bbox[1];
        const x2 = bbox[0] + bbox[2];
        const y2 = bbox[1] + bbox[3];

        const movedX1 = handle.includes('w') ? x1 + dx : x1;
        const movedX2 = handle.includes('e') ? x2 + dx : x2;
        const movedY1 = handle.includes('n') ? y1 + dy : y1;
        const movedY2 = handle.includes('s') ? y2 + dy : y2;

        return normalizeBboxFromPoints(movedX1, movedY1, movedX2, movedY2);
    }

    function normalizeBboxFromPoints(x1, y1, x2, y2) {
        return [
            Math.min(x1, x2),
            Math.min(y1, y2),
            Math.max(MIN_BOX_SIZE, Math.abs(x2 - x1)),
            Math.max(MIN_BOX_SIZE, Math.abs(y2 - y1))
        ];
    }

    function normalizeRawBbox(bbox) {
        if (!Array.isArray(bbox) || bbox.length !== 4) return null;
        const values = bbox.map(Number);
        if (values.some(value => !Number.isFinite(value))) return null;
        if (values[2] < 0) {
            values[0] += values[2];
            values[2] = Math.abs(values[2]);
        }
        if (values[3] < 0) {
            values[1] += values[3];
            values[3] = Math.abs(values[3]);
        }
        if (values[2] <= 0 || values[3] <= 0) return null;
        return values;
    }

    function clampBboxToImage(bbox, imageRecord = appState.currentImage) {
        const normalized = normalizeRawBbox(bbox);
        if (!normalized) return null;

        const size = imageDimensions(imageRecord);
        if (!size) return normalized;

        const [x, y, w, h] = normalized;
        const x1 = clampNumber(x, 0, size.width);
        const y1 = clampNumber(y, 0, size.height);
        const x2 = clampNumber(x + w, 0, size.width);
        const y2 = clampNumber(y + h, 0, size.height);

        if (x2 <= x1 || y2 <= y1) return null;
        return [x1, y1, x2 - x1, y2 - y1];
    }

    function clampMovedBboxToImage(bbox, imageRecord = appState.currentImage) {
        const normalized = normalizeRawBbox(bbox);
        if (!normalized) return null;

        const size = imageDimensions(imageRecord);
        if (!size) return normalized;

        const width = Math.min(normalized[2], size.width);
        const height = Math.min(normalized[3], size.height);
        return [
            clampNumber(normalized[0], 0, Math.max(0, size.width - width)),
            clampNumber(normalized[1], 0, Math.max(0, size.height - height)),
            width,
            height
        ];
    }

    function clampNumber(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }


    function getSelectedResizeHandleAtPoint(worldPoint) {
        for (let i = currentAnnotations().length - 1; i >= 0; i--) {
            const annotation = currentAnnotations()[i];
            if (!appState.selectedAnnotationIds.has(annotation.id)) continue;

            const handle = getResizeHandleAtPoint(annotation, worldPoint);
            if (handle) return { annotation, handle };
        }
        return null;
    }

    function getResizeHandleAtPoint(annotation, worldPoint) {
        const handleSize = BOX_HANDLE_SCREEN_SIZE / appState.cameraZoom;
        const half = handleSize / 2;
        const handles = annotationHandles(annotation);

        for (const handle of ['nw', 'ne', 'se', 'sw', 'n', 'e', 's', 'w']) {
            const point = handles[handle];
            if (
                worldPoint.x >= point.x - half
                && worldPoint.x <= point.x + half
                && worldPoint.y >= point.y - half
                && worldPoint.y <= point.y + half
            ) {
                return handle;
            }
        }

        return null;
    }

    function annotationHandles(annotation) {
        const [x, y, w, h] = annotation.bbox;
        const x2 = x + w;
        const y2 = y + h;

        return {
            nw: { x, y },
            n: { x: x + w / 2, y },
            ne: { x: x2, y },
            e: { x: x2, y: y + h / 2 },
            se: { x: x2, y: y2 },
            s: { x: x + w / 2, y: y2 },
            sw: { x, y: y2 },
            w: { x, y: y + h / 2 }
        };
    }

    function findAnnotationAtPoint(worldPoint, predicate = null) {
        for (let i = currentAnnotations().length - 1; i >= 0; i--) {
            const annotation = currentAnnotations()[i];
            if (predicate && !predicate(annotation)) continue;
            if (pointInsideBbox(worldPoint, annotation.bbox)) return annotation;
        }
        return null;
    }

    function findCandidateAtPoint(worldPoint) {
        for (let i = currentCandidates().length - 1; i >= 0; i--) {
            const candidate = currentCandidates()[i];
            if (pointInsideCandidate(worldPoint, candidate)) return candidate;
        }
        return null;
    }

    function pointInsideCandidate(point, candidate) {
        const contour = normalizeContour(candidate.contour);
        if (contour) return pointInsidePolygon(point, contour);
        if (!Array.isArray(candidate.bbox) || candidate.bbox.length !== 4) return false;
        return pointInsideBbox(point, candidate.bbox);
    }

    function pointInsideBbox(point, bbox) {
        const [x, y, w, h] = bbox;
        return point.x >= x && point.x <= x + w && point.y >= y && point.y <= y + h;
    }

    function pointInsidePolygon(point, polygon) {
        let inside = false;
        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const xi = polygon[i][0];
            const yi = polygon[i][1];
            const xj = polygon[j][0];
            const yj = polygon[j][1];
            const intersects = ((yi > point.y) !== (yj > point.y))
                && (point.x < ((xj - xi) * (point.y - yi)) / ((yj - yi) || Number.EPSILON) + xi);
            if (intersects) inside = !inside;
        }
        return inside;
    }

    function findAnnotationById(id) {
        return currentAnnotations().find(annotation => annotation.id === id);
    }

    function updateCanvasEditCursor(event) {
        if (appState.isManualMode || appState.isAwaitingChoice || !appState.currentImage) return;

        const rect = canvas.getBoundingClientRect();
        const worldPoint = getWorldPoint(event.clientX - rect.left, event.clientY - rect.top);
        const resizeHit = getSelectedResizeHandleAtPoint(worldPoint);
        if (resizeHit) {
            canvas.style.cursor = cursorForHandle(resizeHit.handle);
            return;
        }

        const selectedAnnotation = findAnnotationAtPoint(worldPoint, annotation => (
            appState.selectedAnnotationIds.has(annotation.id)
        ));
        if (selectedAnnotation) {
            canvas.style.cursor = 'move';
            return;
        }

        const annotation = findAnnotationAtPoint(worldPoint);
        if (annotation) {
            canvas.style.cursor = 'pointer';
            return;
        }

        canvas.style.cursor = findCandidateAtPoint(worldPoint) ? 'pointer' : 'grab';
    }

    function cursorForHandle(handle) {
        const cursors = {
            n: 'ns-resize',
            s: 'ns-resize',
            e: 'ew-resize',
            w: 'ew-resize',
            ne: 'nesw-resize',
            sw: 'nesw-resize',
            nw: 'nwse-resize',
            se: 'nwse-resize'
        };
        return cursors[handle] || 'default';
    }

    function bboxesEqual(a, b) {
        return a.length === b.length && a.every((value, index) => Math.abs(value - b[index]) < 0.001);
    }

    function handleWheel(event) {
        event.preventDefault();
        const zoomAmount = event.deltaY * SCROLL_SENSITIVITY;
        const newZoom = appState.cameraZoom * (1 - zoomAmount);
        setZoom(newZoom, { x: event.clientX, y: event.clientY });
    }

    function setZoom(newZoom, zoomCenter = null) {
        let center = zoomCenter;
        if (!center) {
            const rect = canvas.getBoundingClientRect();
            center = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
        }

        const mousePos = getScreenPoint(center.x, center.y);
        const worldPosBeforeZoom = getWorldPoint(mousePos.x, mousePos.y);
        appState.cameraZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, newZoom));
        appState.cameraOffset.x = mousePos.x - worldPosBeforeZoom.x * appState.cameraZoom;
        appState.cameraOffset.y = mousePos.y - worldPosBeforeZoom.y * appState.cameraZoom;
        draw();
    }

    function zoomIn() {
        setZoom(appState.cameraZoom * ZOOM_STEP);
    }

    function zoomOut() {
        setZoom(appState.cameraZoom / ZOOM_STEP);
    }

    function setupChoiceButtons() {
        const box = appState.currentManualBox;
        const buttonWidth = 96;
        const buttonHeight = 30;
        const padding = 8;
        const choices = [
            ...appState.classes.map(cls => ({
                label: cls.name,
                action: cls.name,
                color: cls.color
            })),
            { label: '+ Class', action: NEW_CLASS_ACTION, color: '#2563eb' },
            { label: 'Cancel', action: 'Cancel', color: '#4a4a4a' }
        ];
        const maxColumns = Math.max(1, Math.floor((canvas.width + padding) / (buttonWidth + padding)));
        const columns = Math.min(choices.length, maxColumns);
        const rows = Math.ceil(choices.length / columns);
        const totalWidth = columns * buttonWidth + (columns - 1) * padding;
        const totalHeight = rows * buttonHeight + (rows - 1) * padding;
        const startX = Math.max(0, Math.min(box.x, canvas.width - totalWidth));
        const preferredY = box.h >= 0 ? box.y + box.h + padding : box.y + padding;
        const fallbackY = box.h >= 0 ? box.y - totalHeight - padding : box.y + box.h - totalHeight - padding;
        const startY = Math.max(
            0,
            Math.min(
                preferredY + totalHeight <= canvas.height ? preferredY : fallbackY,
                canvas.height - totalHeight
            )
        );

        appState.choiceInfo = {
            rect: { ...box },
            buttons: choices.map((choice, index) => ({
                ...choice,
                x: startX + (index % columns) * (buttonWidth + padding),
                y: startY + Math.floor(index / columns) * (buttonHeight + padding),
                w: buttonWidth,
                h: buttonHeight
            }))
        };
        appState.currentManualBox = null;
    }

    function promptCreateClassForManualAnnotation() {
        const rawName = window.prompt('New class name');
        if (rawName === null) return;

        const className = createClassFromName(rawName, { select: true });
        if (className) {
            finalizeAnnotation(className);
        }
    }

    function finalizeAnnotation(className) {
        if (!appState.choiceInfo) return;
        if (!classExists(className)) {
            const msg = 'Please choose a valid class before creating an annotation.';
            updateStatus(msg);
            showToast(msg, 'error');
            appState.isAwaitingChoice = false;
            appState.choiceInfo = null;
            draw();
            return;
        }

        try {
            const screenBox = appState.choiceInfo.rect;
            const normalizedRect = {
                x: screenBox.w > 0 ? screenBox.x : screenBox.x + screenBox.w,
                y: screenBox.h > 0 ? screenBox.y : screenBox.y + screenBox.h,
                w: Math.abs(screenBox.w),
                h: Math.abs(screenBox.h)
            };
            const boxStart = getWorldPoint(normalizedRect.x, normalizedRect.y);
            const boxEnd = getWorldPoint(normalizedRect.x + normalizedRect.w, normalizedRect.y + normalizedRect.h);
            const worldBox = {
                x: boxStart.x,
                y: boxStart.y,
                w: boxEnd.x - boxStart.x,
                h: boxEnd.y - boxStart.y
            };

            if (isNaN(worldBox.w) || isNaN(worldBox.h) || worldBox.w < 1 || worldBox.h < 1) {
                throw new Error('Invalid box dimensions.');
            }
            const clampedBbox = clampBboxToImage([worldBox.x, worldBox.y, worldBox.w, worldBox.h]);
            if (!clampedBbox) {
                throw new Error('Box is outside the image bounds.');
            }

            appState.annotationCounter++;
            const newAnnotation = {
                id: appState.annotationCounter,
                bbox: clampedBbox,
                class: className,
                type: 'manual'
            };

            currentAnnotations().push(newAnnotation);
            markCurrentImageDirty();

            const msg = `Added manual annotation #${newAnnotation.id} as '${className}'.`;
            updateStatus(msg);
            showToast(msg, 'success');
            updateAnnotationLog();
            renderImageBrowser();
        } catch (error) {
            console.error('Failed to finalize manual annotation:', error);
            const errorMsg = 'Error: Could not create manual annotation.';
            updateStatus(errorMsg);
            showToast(errorMsg, 'error');
        } finally {
            appState.isAwaitingChoice = false;
            appState.choiceInfo = null;
            draw();
            updateButtonStates();
        }
    }

    function cancelManualAnnotation() {
        appState.isAwaitingChoice = false;
        appState.choiceInfo = null;
        updateStatus('Manual box cancelled.');
        draw();
    }

    // --- ANNOTATION LOG AND ACTIONS ---
    function handleLogClick(event) {
        const row = event.target.closest('tr');
        if (!row) return;

        const id = parseInt(row.dataset.annotationId, 10);
        if (event.shiftKey || event.ctrlKey || event.metaKey) {
            if (appState.selectedAnnotationIds.has(id)) {
                appState.selectedAnnotationIds.delete(id);
            } else {
                appState.selectedAnnotationIds.add(id);
            }
            appState.selectedCandidateIds.clear();
        } else if (appState.selectedAnnotationIds.has(id)) {
            appState.selectedAnnotationIds.clear();
        } else {
            appState.selectedAnnotationIds.clear();
            appState.selectedAnnotationIds.add(id);
            appState.selectedCandidateIds.clear();
        }

        updateAnnotationLog();
        draw();
        updateButtonStates();
    }

    function handleLogRightClick(event) {
        event.preventDefault();
        const row = event.target.closest('tr');
        if (!row) return;

        appState.logItemToModify = parseInt(row.dataset.annotationId, 10);
        logContextMenu.style.left = `${event.clientX}px`;
        logContextMenu.style.top = `${event.clientY}px`;
        logContextMenu.classList.remove('hidden');
    }

    function deleteAnnotationById(idToDelete) {
        logContextMenu.classList.add('hidden');
        if (idToDelete === null) return;

        const annotations = currentAnnotations();
        const annotationIndex = annotations.findIndex(annotation => annotation.id === idToDelete);
        if (annotationIndex === -1) return;

        const deletedAnnotation = annotations[annotationIndex];
        annotations.splice(annotationIndex, 1);

        if (deletedAnnotation.type === 'sam_final') {
            for (const batch of currentHistory()) {
                if (batch.type !== 'convert_candidates' || !Array.isArray(batch.originalCandidates)) continue;

                const originalCandidate = batch.originalCandidates.find(candidate => (
                    candidate.id === deletedAnnotation.originalCandidateId
                ));

                if (originalCandidate) {
                    currentCandidates().push(originalCandidate);
                    batch.originalCandidates = batch.originalCandidates.filter(candidate => (
                        candidate.id !== deletedAnnotation.originalCandidateId
                    ));
                    batch.convertedAnnotations = batch.convertedAnnotations.filter(annotation => (
                        annotation.id !== deletedAnnotation.id
                    ));
                    break;
                }
            }
        }

        appState.selectedAnnotationIds.delete(idToDelete);
        appState.logItemToModify = null;
        markCurrentImageDirty();

        const msg = `Deleted annotation #${deletedAnnotation.id}.`;
        updateStatus(msg);
        showToast(msg, 'info');
        updateAnnotationLog();
        renderImageBrowser();
        draw();
        updateButtonStates();
    }

    function visibleModal() {
        return [samSettingsModal, preprocessSettingsModal, helpModal]
            .find(modal => modal && !modal.classList.contains('hidden'));
    }

    function closeVisibleModal(modal) {
        if (modal === samSettingsModal) {
            closeSamSettingsModal();
        } else if (modal === preprocessSettingsModal) {
            closePreprocessSettingsModal();
        } else if (modal === helpModal) {
            closeHelpModal();
        }
    }

    function focusableElementsIn(modal) {
        return Array.from(modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )).filter(element => !element.disabled && element.getClientRects().length > 0);
    }

    function trapModalFocus(event, modal) {
        if (event.key !== 'Tab') return false;
        const focusable = focusableElementsIn(modal);
        if (focusable.length === 0) {
            event.preventDefault();
            modal.focus();
            return true;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
            return true;
        }
        if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
            return true;
        }
        return false;
    }

    function handleKeyDown(event) {
        const modal = visibleModal();
        if (event.key === 'Escape') {
            event.preventDefault();
            if (modal) {
                closeVisibleModal(modal);
            } else if (appState.boxEditMode) {
                cancelBoxEdit();
                updateStatus('Box edit cancelled.');
            } else if (appState.isDrawing) {
                appState.isDrawing = false;
                appState.currentManualBox = null;
                draw();
                updateStatus('Manual box drawing cancelled.');
            } else if (appState.isAwaitingChoice) {
                cancelManualAnnotation();
            } else if (appState.isManualMode) {
                toggleManualMode();
            }
            return;
        }

        if (modal) {
            trapModalFocus(event, modal);
            return;
        }

        const tagName = document.activeElement ? document.activeElement.tagName : '';
        if (['INPUT', 'SELECT', 'TEXTAREA'].includes(tagName)) return;

        if (event.key.toLowerCase() === 'b') {
            event.preventDefault();
            if (appState.currentImage) toggleManualMode();
            return;
        }

        if (event.key === 'Delete') {
            event.preventDefault();
            const selectedIds = Array.from(appState.selectedAnnotationIds);
            selectedIds.forEach(id => deleteAnnotationById(id));
            return;
        }

        if (appState.isManualMode) return;

        const arrowDelta = arrowKeyDelta(event.key);
        if (arrowDelta && appState.selectedAnnotationIds.size > 0) {
            event.preventDefault();
            const step = event.shiftKey ? 10 : 1;
            nudgeSelectedAnnotations(arrowDelta.dx * step, arrowDelta.dy * step);
            return;
        }

        if (event.key.toLowerCase() === 'u') {
            event.preventDefault();
            handleUndoBatch();
            return;
        }

        const classMatch = appState.classes.find(cls => cls.hotkey === event.key.toLowerCase());
        if (classMatch) {
            event.preventDefault();
            processSelection(classMatch.name);
        }
    }

    async function handleSetAnnotationDir() {
        const annotationOutputDir = annotationDirInput.value.trim();
        if (!annotationOutputDir) {
            const msg = 'Annotation folder cannot be empty.';
            updateStatus(msg);
            showToast(msg, 'error');
            return;
        }
        const isChangingAnnotationDir = annotationOutputDir !== appState.projectSettings.annotationOutputDir;
        if (
            isChangingAnnotationDir
            && !confirmProceedWithUnsavedChanges('Changing the annotation folder changes where annotations are loaded from and saved to.')
        ) {
            return;
        }

        setLoader(true, 'Updating annotation folder...');

        try {
            const response = await apiFetch(apiPath('/api/project/settings'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ annotation_output_dir: annotationOutputDir })
            });
            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            applyProjectSettings(data);
            appState.annotationSource = {
                mode: 'server',
                files: [],
                fileMap: new Map(),
                displayName: 'Server folder source active.'
            };
            updateAnnotationSourceDisplay();
            await loadProjectClasses();
            clearAnnotationMatches();
            appState.images.forEach(imageRecord => {
                imageRecord.serverAnnotationsChecked = false;
            });

            if (appState.images.length > 0) {
                await refreshAnnotationMatches({ showFeedback: false });
            }

            const msg = `Annotation folder set to ${data.annotation_dir_display}.`;
            updateStatus(msg);
            showToast(msg, 'success');
        } catch (error) {
            console.error('Project Settings Error:', error);
            const msg = `Failed to update annotation folder: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        } finally {
            setLoader(false);
            updateButtonStates();
        }
    }

    function openSamSettingsModal() {
        samSettingsReturnFocus = document.activeElement;
        renderSamSettingsPanel({ keepInputs: true });
        samSettingsModal.classList.remove('hidden');
        closeSamSettingsBtn.focus();
    }

    function closeSamSettingsModal() {
        samSettingsModal.classList.add('hidden');
        if (samSettingsReturnFocus && typeof samSettingsReturnFocus.focus === 'function') {
            samSettingsReturnFocus.focus();
        }
        samSettingsReturnFocus = null;
    }

    function handleSamPresetChange() {
        if (samPresetSelect.value === 'custom') {
            const customSettings = readSamSettingsFromInputs();
            appState.projectSettings.samSettings = {
                ...customSettings,
                preset: 'custom',
                warnings: []
            };
            renderSamSettingsPanel({ keepInputs: true });
            return;
        }

        const preset = findSamPreset(samPresetSelect.value) || findSamPreset(DEFAULT_SAM_PRESET);
        if (!preset) return;

        appState.projectSettings.samSettings = {
            preset: preset.key,
            params: { ...preset.params },
            warnings: []
        };
        renderSamSettingsPanel();
    }

    function handleSamSettingsInput() {
        const nextSettings = readSamSettingsFromInputs();
        const selectedPreset = findSamPreset(samPresetSelect.value);
        const stillMatchesPreset = selectedPreset
            && samParamsEqual(nextSettings.params, selectedPreset.params);
        appState.projectSettings.samSettings = {
            ...nextSettings,
            preset: stillMatchesPreset ? selectedPreset.key : 'custom',
            warnings: []
        };
        renderSamSettingsPanel({ keepInputs: true });
    }

    async function handleApplySamSettings() {
        const samSettings = readSamSettingsFromInputs();
        if (samSettings.params.min_overall_area > samSettings.params.max_overall_area) {
            const msg = 'SAM min object area cannot be greater than max object area.';
            updateStatus(msg);
            showToast(msg, 'error');
            return;
        }

        setLoader(true, 'Saving SAM settings...');

        try {
            const response = await apiFetch(apiPath('/api/project/settings'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sam_settings: samSettings })
            });
            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            applyProjectSettings(data);
            closeSamSettingsModal();
            const msg = `SAM settings saved: ${currentSamPresetLabel()}.`;
            updateStatus(msg);
            showToast(msg, 'success');
        } catch (error) {
            console.error('SAM Settings Error:', error);
            const msg = `Failed to save SAM settings: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        } finally {
            setLoader(false);
        }
    }

    function handleResetSamPreset() {
        const selectedPreset = samPresetSelect.value === 'custom' ? DEFAULT_SAM_PRESET : samPresetSelect.value;
        const preset = findSamPreset(selectedPreset) || findSamPreset(DEFAULT_SAM_PRESET);
        if (!preset) return;

        appState.projectSettings.samSettings = {
            preset: preset.key,
            params: { ...preset.params },
            warnings: []
        };
        renderSamSettingsPanel();
        const msg = `Reset SAM fields to ${preset.label}.`;
        updateStatus(msg);
        showToast(msg, 'info');
    }

    function renderSamPresetOptions() {
        const selectedPreset = appState.projectSettings.samSettings.preset || DEFAULT_SAM_PRESET;
        samPresetSelect.innerHTML = '';

        appState.samPresets.forEach(preset => {
            const option = document.createElement('option');
            option.value = preset.key;
            option.textContent = preset.label;
            samPresetSelect.appendChild(option);
        });

        const customOption = document.createElement('option');
        customOption.value = 'custom';
        customOption.textContent = 'Custom';
        samPresetSelect.appendChild(customOption);
        samPresetSelect.value = findSamPreset(selectedPreset) ? selectedPreset : 'custom';
    }

    function renderSamSettingsPanel({ keepInputs = false } = {}) {
        if (!keepInputs) {
            renderSamPresetOptions();
            const params = appState.projectSettings.samSettings.params || DEFAULT_SAM_PARAMS;
            samAreaModeSelect.value = params.area_mode || 'pixels';
            samPointsPerSideInput.value = params.points_per_side;
            samCropLayersInput.value = params.crop_n_layers;
            samCropOverlapInput.value = params.crop_overlap_ratio;
            samCropDownscaleInput.value = params.crop_n_points_downscale_factor;
            samPointsPerBatchInput.value = params.points_per_batch;
            samMinMaskRegionAreaInput.value = params.min_mask_region_area;
            samMinObjectAreaInput.value = params.min_overall_area;
            samMaxObjectAreaInput.value = params.max_overall_area;
            samPredIouInput.value = params.pred_iou_thresh;
            samStabilityInput.value = params.stability_score_thresh;
            samStabilityOffsetInput.value = params.stability_score_offset;
            samBoxNmsInput.value = params.box_nms_thresh;
            samCropNmsInput.value = params.crop_nms_thresh;
            samUseM2mInput.checked = !!params.use_m2m;
        } else {
            samPresetSelect.value = appState.projectSettings.samSettings.preset === 'custom'
                ? 'custom'
                : appState.projectSettings.samSettings.preset;
        }

        const params = appState.projectSettings.samSettings.params || DEFAULT_SAM_PARAMS;
        const areaSuffix = params.area_mode === 'percent' ? '% image area' : 'px';
        samMinObjectAreaInput.title = areaSuffix;
        samMaxObjectAreaInput.title = areaSuffix;
        samPresetSummary.textContent = currentSamPresetLabel();
        updateSamRiskText();
    }

    function readSamSettingsFromInputs() {
        return {
            preset: samPresetSelect.value || DEFAULT_SAM_PRESET,
            params: {
                points_per_side: readNumericInput(samPointsPerSideInput, DEFAULT_SAM_PARAMS.points_per_side),
                crop_n_layers: readNumericInput(samCropLayersInput, DEFAULT_SAM_PARAMS.crop_n_layers),
                min_mask_region_area: readNumericInput(samMinMaskRegionAreaInput, DEFAULT_SAM_PARAMS.min_mask_region_area),
                crop_overlap_ratio: readNumericInput(samCropOverlapInput, DEFAULT_SAM_PARAMS.crop_overlap_ratio),
                crop_n_points_downscale_factor: readNumericInput(samCropDownscaleInput, DEFAULT_SAM_PARAMS.crop_n_points_downscale_factor),
                points_per_batch: readNumericInput(samPointsPerBatchInput, DEFAULT_SAM_PARAMS.points_per_batch),
                pred_iou_thresh: readNumericInput(samPredIouInput, DEFAULT_SAM_PARAMS.pred_iou_thresh),
                stability_score_thresh: readNumericInput(samStabilityInput, DEFAULT_SAM_PARAMS.stability_score_thresh),
                stability_score_offset: readNumericInput(samStabilityOffsetInput, DEFAULT_SAM_PARAMS.stability_score_offset),
                box_nms_thresh: readNumericInput(samBoxNmsInput, DEFAULT_SAM_PARAMS.box_nms_thresh),
                crop_nms_thresh: readNumericInput(samCropNmsInput, DEFAULT_SAM_PARAMS.crop_nms_thresh),
                use_m2m: samUseM2mInput.checked,
                area_mode: samAreaModeSelect.value === 'percent' ? 'percent' : 'pixels',
                min_overall_area: readNumericInput(samMinObjectAreaInput, DEFAULT_SAM_PARAMS.min_overall_area),
                max_overall_area: readNumericInput(samMaxObjectAreaInput, DEFAULT_SAM_PARAMS.max_overall_area)
            }
        };
    }

    function currentSamSettingsPayload() {
        const currentSettings = readSamSettingsFromInputs();
        appState.projectSettings.samSettings = {
            ...currentSettings,
            warnings: appState.projectSettings.samSettings.warnings || []
        };
        return currentSettings;
    }

    function applySamSettings(samSettings) {
        const normalizedSettings = normalizeSamSettingsForClient(samSettings);
        appState.projectSettings.samSettings = normalizedSettings;
        renderSamSettingsPanel();
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

    function currentSamParams() {
        return appState.projectSettings.samSettings.params || DEFAULT_SAM_PARAMS;
    }

    function readNumericInput(input, fallback) {
        const value = Number(input.value);
        return Number.isFinite(value) ? value : fallback;
    }

    function updateSamRiskText() {
        const warnings = [
            ...samRiskWarnings(currentSamParams()),
            ...(appState.projectSettings.samSettings.warnings || [])
        ];
        const uniqueWarnings = [...new Set(warnings)];
        if (uniqueWarnings.length === 0) {
            samRiskText.textContent = 'Current settings are within normal limits.';
            samRiskText.classList.remove('warning');
            return;
        }

        samRiskText.textContent = uniqueWarnings.join(' ');
        samRiskText.classList.add('warning');
    }

    function samRiskWarnings(params) {
        const warnings = [];
        if (params.points_per_side > 96) warnings.push('High point density can be slow and memory intensive.');
        if (params.crop_n_layers > 2) warnings.push('More than 2 crop layers can greatly increase runtime.');
        if (params.points_per_batch > 128) warnings.push('Large point batches can trigger GPU out-of-memory errors.');
        if (params.pred_iou_thresh < 0.75) warnings.push('Low IoU threshold can produce many noisy masks.');
        if (params.stability_score_thresh < 0.75) warnings.push('Low stability threshold can produce unstable masks.');
        if (appState.currentImage?.originalImage) {
            const pixels = appState.currentImage.originalImage.width * appState.currentImage.originalImage.height;
            if (pixels > 3000000 && params.points_per_side >= 96 && params.crop_n_layers >= 2) {
                warnings.push('Large image plus dense crop settings can be very GPU intensive.');
            }
        }
        return warnings;
    }

    function currentSamPresetLabel() {
        if (appState.projectSettings.samSettings.preset === 'custom') return 'Custom';
        const preset = findSamPreset(appState.projectSettings.samSettings.preset);
        return preset ? preset.label : 'Custom';
    }

    function findSamPreset(key) {
        return appState.samPresets.find(preset => preset.key === key);
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

    async function refreshAnnotationMatches({ showFeedback = false } = {}) {
        if (appState.annotationSource.mode === 'local') {
            await refreshLocalAnnotationMatches({ showFeedback });
            return;
        }

        if (appState.images.length === 0) {
            clearAnnotationMatches();
            updateMatchSummaryDisplay();
            updateButtonStates();
            return;
        }

        setLoader(true, 'Checking annotation matches...');

        try {
            const response = await apiFetch(apiPath('/api/annotations/match'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    images: imagePayloads(),
                    format: currentAnnotationFormat()
                })
            });
            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            appState.annotationMatchesByImage.clear();
            (data.results || []).forEach(match => {
                appState.annotationMatchesByImage.set(match.id, match);
            });
            appState.matchSummary = data.summary || null;
            if (data.annotation_dir_display) {
                appState.projectSettings.annotationDirDisplay = data.annotation_dir_display;
                annotationDirDisplay.textContent = data.annotation_dir_display;
                annotationDirDisplay.title = phiSafeMode()
                    ? 'PHI-safe mode hides annotation folder paths.'
                    : (data.annotation_dir || data.annotation_dir_display);
            }

            renderImageBrowser();
            updateMatchSummaryDisplay();
            updateButtonStates();

            if (showFeedback) {
                const summary = appState.matchSummary;
                const msg = summary
                    ? `Annotation matches: ${summary.matched} matched, ${summary.missing} missing, ${summary.ambiguous} ambiguous.`
                    : 'Annotation matches checked.';
                updateStatus(msg);
                showToast(msg, 'info');
            }
        } catch (error) {
            console.error('Annotation Match Error:', error);
            const msg = `Failed to check annotation matches: ${error.message}`;
            updateStatus(msg);
            if (showFeedback) showToast(msg, 'error');
        } finally {
            setLoader(false);
        }
    }

    async function handleLoadMatchedAnnotations() {
        if (appState.annotationSource.mode === 'local') {
            await handleLoadLocalMatchedAnnotations();
            return;
        }

        if (appState.images.length === 0) return;

        const dirtyMatchedImages = appState.images.filter(imageRecord => (
            appState.dirtyImages.has(imageRecord.id)
            && appState.annotationMatchesByImage.get(imageRecord.id)?.status === 'matched'
        ));
        if (
            dirtyMatchedImages.length > 0
            && !confirmReplaceUnsavedAnnotations(
                'Loading matched annotation files will overwrite those modified images.',
                dirtyMatchedImages.length
            )
        ) {
            return;
        }

        setLoader(true, 'Loading matched annotations...');

        try {
            const response = await apiFetch(apiPath('/api/annotations/bulk_load'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    images: imagePayloads(),
                    format: currentAnnotationFormat()
                })
            });
            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            if (Array.isArray(data.classes)) {
                applyLoadedClasses(data.classes);
            }

            let loadedCount = 0;
            let annotationCount = 0;
            const imageById = new Map(appState.images.map(imageRecord => [imageRecord.id, imageRecord]));

            (data.results || []).forEach(result => {
                appState.annotationMatchesByImage.set(result.id, result);
                const imageRecord = imageById.get(result.id);
                if (!imageRecord) return;

                imageRecord.serverAnnotationsChecked = true;

                if (result.status !== 'matched') return;

                const normalizedAnnotations = setAnnotationsForImage(
                    imageRecord,
                    result.annotations || [],
                    { markDirty: false }
                );
                annotationCount += normalizedAnnotations.length;
                loadedCount++;
                appState.dirtyImages.delete(imageRecord.id);
            });

            appState.matchSummary = data.summary || appState.matchSummary;
            renderClassControls(classificationSelect.value);
            updateAnnotationLog();
            renderImageBrowser();
            updateMatchSummaryDisplay();
            draw();
            updateButtonStates();

            const summary = data.summary || {};
            const msg = `Loaded ${annotationCount} annotations from ${loadedCount} matched ${formatLabel(currentAnnotationFormat())} files. ${summary.ambiguous || 0} ambiguous, ${summary.missing || 0} missing, ${summary.errors || 0} errors.`;
            updateStatus(msg);
            showToast(msg, loadedCount > 0 ? 'success' : 'info');
        } catch (error) {
            console.error('Bulk Annotation Load Error:', error);
            const msg = `Failed to load matched annotations: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        } finally {
            setLoader(false);
        }
    }

    function localAnnotationSourceActive() {
        return appState.annotationSource.mode === 'local' && appState.annotationSource.files.length > 0;
    }

    async function handleAnnotationSourceInput(event) {
        const selectedFiles = Array.from(event.target.files || []);
        event.target.value = '';
        const annotationFiles = selectedFiles.filter(file => formatFromFileName(file.name));

        if (annotationFiles.length === 0) {
            const msg = 'No supported annotation files were selected.';
            updateStatus(msg);
            showToast(msg, 'error');
            return;
        }

        const fileMap = new Map();
        annotationFiles.forEach(file => {
            const key = basename(file.name).toLowerCase();
            if (!fileMap.has(key)) fileMap.set(key, []);
            fileMap.get(key).push(file);
        });

        const folderNames = new Set(annotationFiles
            .map(file => file.webkitRelativePath ? file.webkitRelativePath.split('/')[0] : '')
            .filter(Boolean));
        const displayName = phiSafeMode()
            ? `${annotationFiles.length} local annotation files`
            : folderNames.size === 1
            ? `${annotationFiles.length} files from ${Array.from(folderNames)[0]}`
            : `${annotationFiles.length} local annotation files`;

        appState.annotationSource = {
            mode: 'local',
            files: annotationFiles,
            fileMap,
            displayName
        };
        updateAnnotationSourceDisplay();
        await refreshAnnotationMatches({ showFeedback: true });
    }

    async function useServerAnnotationSource() {
        appState.annotationSource = {
            mode: 'server',
            files: [],
            fileMap: new Map(),
            displayName: 'Server folder source active.'
        };
        updateAnnotationSourceDisplay();
        await refreshAnnotationMatches({ showFeedback: true });
    }

    function updateAnnotationSourceDisplay() {
        if (localAnnotationSourceActive()) {
            annotationSourceDisplay.textContent = appState.annotationSource.displayName;
            annotationSourceDisplay.title = phiSafeMode()
                ? 'PHI-safe mode hides local annotation source paths.'
                : appState.annotationSource.files
                .slice(0, 20)
                .map(file => file.webkitRelativePath || file.name)
                .join('\n');
            useServerAnnotationSourceBtn.disabled = false;
            return;
        }

        annotationSourceDisplay.textContent = 'Server folder source active.';
        annotationSourceDisplay.title = annotationDirDisplay.title || annotationDirDisplay.textContent;
        useServerAnnotationSourceBtn.disabled = true;
    }

    async function refreshLocalAnnotationMatches({ showFeedback = false } = {}) {
        if (appState.images.length === 0 || !localAnnotationSourceActive()) {
            clearAnnotationMatches();
            updateMatchSummaryDisplay();
            updateButtonStates();
            return;
        }

        setLoader(true, 'Checking local annotation matches...');

        try {
            const annotationFormat = currentAnnotationFormat();
            const duplicateStems = duplicateImageStems();
            const results = [];

            for (const imageRecord of appState.images) {
                const match = resolveLocalAnnotationMatch(imageRecord, duplicateStems, annotationFormat);
                if (match.status === 'matched') {
                    match.annotation_count = await countLocalAnnotationFile(match.sourceFile, annotationFormat, imageRecord);
                }
                results.push(match);
            }

            appState.annotationMatchesByImage.clear();
            results.forEach(match => appState.annotationMatchesByImage.set(match.id, match));
            appState.matchSummary = {
                total: results.length,
                matched: results.filter(result => result.status === 'matched').length,
                missing: results.filter(result => result.status === 'missing').length,
                ambiguous: results.filter(result => result.status === 'ambiguous').length,
            };

            renderImageBrowser();
            updateMatchSummaryDisplay();
            updateButtonStates();

            if (showFeedback) {
                const summary = appState.matchSummary;
                const msg = `Local annotation matches: ${summary.matched} matched, ${summary.missing} missing, ${summary.ambiguous} ambiguous.`;
                updateStatus(msg);
                showToast(msg, 'info');
            }
        } catch (error) {
            console.error('Local Annotation Match Error:', error);
            const msg = `Failed to check local annotation matches: ${error.message}`;
            updateStatus(msg);
            if (showFeedback) showToast(msg, 'error');
        } finally {
            setLoader(false);
        }
    }

    async function handleLoadLocalMatchedAnnotations() {
        if (appState.images.length === 0 || !localAnnotationSourceActive()) return;

        const dirtyMatchedImages = appState.images.filter(imageRecord => (
            appState.dirtyImages.has(imageRecord.id)
            && appState.annotationMatchesByImage.get(imageRecord.id)?.status === 'matched'
        ));
        if (
            dirtyMatchedImages.length > 0
            && !confirmReplaceUnsavedAnnotations(
                'Loading matched local annotation files will overwrite those modified images.',
                dirtyMatchedImages.length
            )
        ) {
            return;
        }

        setLoader(true, 'Loading local matched annotations...');

        try {
            const annotationFormat = currentAnnotationFormat();
            let loadedCount = 0;
            let annotationCount = 0;
            let errorCount = 0;

            for (const imageRecord of appState.images) {
                const match = appState.annotationMatchesByImage.get(imageRecord.id);
                if (match?.status !== 'matched' || !match.sourceFile) continue;

                try {
                    const text = await match.sourceFile.text();
                    const result = parseAnnotationFile(text, annotationFormat, imageRecord);
                    const normalizedAnnotations = setAnnotationsForImage(
                        imageRecord,
                        result.annotations || [],
                        { markDirty: false }
                    );
                    annotationCount += normalizedAnnotations.length;
                    loadedCount++;
                    imageRecord.serverAnnotationsChecked = true;
                    appState.dirtyImages.delete(imageRecord.id);
                } catch (error) {
                    errorCount++;
                    appState.annotationMatchesByImage.set(imageRecord.id, {
                        ...match,
                        status: 'error',
                        exists: false,
                        annotations: [],
                        message: `Failed to load local annotations: ${error.message}`
                    });
                }
            }

            recomputeMatchSummaryFromMatches();
            renderClassControls(classificationSelect.value);
            updateAnnotationLog();
            renderImageBrowser();
            updateMatchSummaryDisplay();
            draw();
            updateButtonStates();

            const summary = appState.matchSummary || {};
            const msg = `Loaded ${annotationCount} annotations from ${loadedCount} matched local ${formatLabel(annotationFormat)} files. ${summary.ambiguous || 0} ambiguous, ${summary.missing || 0} missing, ${errorCount} errors.`;
            updateStatus(msg);
            showToast(msg, loadedCount > 0 ? 'success' : 'info');
        } catch (error) {
            console.error('Local Bulk Annotation Load Error:', error);
            const msg = `Failed to load local matched annotations: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        } finally {
            setLoader(false);
        }
    }

    function handleExportAnnotationFile() {
        const annotations = currentAnnotations();
        if (annotations.length === 0) {
            const msg = 'No annotations to save.';
            updateStatus(msg);
            showToast(msg, 'error');
            return;
        }

        try {
            const sourceImageName = appState.currentImage ? publicImageName(appState.currentImage) : 'unknown_image';
            const format = currentAnnotationFormat();
            const exportData = buildAnnotationExport(sourceImageName, annotations, format, appState.currentImage);
            const blob = new Blob([exportData.content], { type: `${exportData.mime};charset=utf-8` });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = annotationDownloadName(sourceImageName, format);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);

            const msg = `Exported ${annotations.length} annotations as ${formatLabel(format)}.`;
            updateStatus(msg);
            showToast(msg, 'success');
        } catch (error) {
            const msg = `Failed to export annotations: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        }
    }

    async function handleLoadAnnotationFile(event) {
        const file = event.target.files[0];
        event.target.value = '';

        if (!file || !appState.currentImage) return;
        if (
            appState.dirtyImages.has(currentImageId())
            && !confirmReplaceUnsavedAnnotations('Importing this file will replace the current image annotations.', 1)
        ) {
            return;
        }

        try {
            const text = await file.text();
            const format = formatFromFileName(file.name) || currentAnnotationFormat();
            const result = parseAnnotationFile(text, format, appState.currentImage);
            if (result.annotations.length === 0) {
                throw new Error('No valid annotations were found in this file.');
            }

            applyLoadedAnnotations(result.annotations, { markDirty: true });

            const matchText = result.usedMatchedRows
                ? `matched to ${publicImageName(appState.currentImage)}`
                : 'imported without image-name filtering';
            const msg = `Loaded ${result.annotations.length} ${formatLabel(format)} annotations from ${phiSafeMode() ? 'annotation file' : file.name} (${matchText}).`;
            updateStatus(msg);
            showToast(msg, 'success');
        } catch (error) {
            console.error('Annotation Import Error:', error);
            const msg = `Failed to import annotations: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        }
    }

    async function handleLoadServerAnnotations() {
        if (!appState.currentImage) return;

        await loadServerAnnotationsForCurrentImage({ silentWhenMissing: false });
    }

    async function loadServerAnnotationsForCurrentImage({ silentWhenMissing }) {
        if (!appState.currentImage) return false;

        const currentMatch = appState.annotationMatchesByImage.get(currentImageId());
        if (currentMatch?.status === 'ambiguous') {
            if (!silentWhenMissing) {
                const msg = `Ambiguous saved annotation file for ${publicImageName(appState.currentImage)}. Duplicate image names need path-specific annotation files.`;
                updateStatus(msg);
                showToast(msg, 'error');
            }
            return false;
        }

        if (
            !silentWhenMissing
            && appState.dirtyImages.has(currentImageId())
            && !confirmReplaceUnsavedAnnotations('Loading the saved annotation file will replace the current image annotations.', 1)
        ) {
            return false;
        }

        setLoader(true, 'Loading saved annotations...');

        try {
            const params = new URLSearchParams({
                image_name: appState.currentImage.name,
                image_path: appState.currentImage.displayPath,
                match_mode: annotationMatchModeForImage(appState.currentImage),
                format: currentAnnotationFormat()
            });
            const imageSize = imageDimensions(appState.currentImage);
            if (imageSize) {
                params.set('image_width', String(imageSize.width));
                params.set('image_height', String(imageSize.height));
            }
            const url = `${apiPath('/api/annotations/load')}?${params.toString()}`;
            const response = await apiFetch(url);
            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            appState.currentImage.serverAnnotationsChecked = true;
            if (data.match) {
                appState.annotationMatchesByImage.set(currentImageId(), data.match);
                recomputeMatchSummaryFromMatches();
            }

            if (!data.exists) {
                if (!silentWhenMissing) {
                    const msg = `No saved ${formatLabel(currentAnnotationFormat())} file found for ${publicImageName(appState.currentImage)}.`;
                    updateStatus(msg);
                    showToast(msg, 'info');
                }
                renderImageBrowser();
                return false;
            }

            if (Array.isArray(data.classes)) {
                applyLoadedClasses(data.classes);
            }
            applyLoadedAnnotations(data.annotations || [], { markDirty: false });
            appState.dirtyImages.delete(currentImageId());

            const msg = `Loaded ${currentAnnotations().length} annotations from ${publicAnnotationPath(data.path)}.`;
            updateStatus(msg);
            if (!silentWhenMissing) showToast(msg, 'success');
            renderImageBrowser();
            return true;
        } catch (error) {
            console.error('Server Annotation Load Error:', error);
            const msg = `Failed to load saved annotations: ${error.message}`;
            updateStatus(msg);
            if (!silentWhenMissing) showToast(msg, 'error');
            return false;
        } finally {
            setLoader(false);
        }
    }

    async function handleSaveServerAnnotations() {
        if (!appState.currentImage) return;

        setLoader(true, 'Saving annotations to server...');

        try {
            const data = await saveImageAnnotationsToServer(appState.currentImage, { confirmOverwrite: true });
            appState.dirtyImages.delete(currentImageId());
            renderImageBrowser();
            const msg = `Saved ${data.count} annotations to ${publicAnnotationPath(data.path)}.`;
            updateStatus(msg);
            showToast(msg, 'success');
        } catch (error) {
            console.error('Server Annotation Save Error:', error);
            const msg = `Failed to save annotations: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        } finally {
            setLoader(false);
        }
    }

    async function handleSaveAllServerAnnotations() {
        const dirtyImageRecords = appState.images.filter(imageRecord => appState.dirtyImages.has(imageRecord.id));
        if (dirtyImageRecords.length === 0) return;

        setLoader(true, `Saving ${dirtyImageRecords.length} modified images...`);

        const failures = [];
        let savedCount = 0;

        for (const imageRecord of dirtyImageRecords) {
            try {
                await saveImageAnnotationsToServer(imageRecord);
                appState.dirtyImages.delete(imageRecord.id);
                savedCount++;
            } catch (error) {
                failures.push(`${publicImageName(imageRecord)}: ${error.message}`);
            }
        }

        renderImageBrowser();
        updateButtonStates();
        setLoader(false);

        if (failures.length > 0) {
            const msg = `Saved ${savedCount} images; ${failures.length} failed.`;
            updateStatus(msg);
            showToast(msg, 'error');
            console.error('Save All failures:', failures);
            return;
        }

        const msg = `Saved annotations for ${savedCount} modified images.`;
        updateStatus(msg);
        showToast(msg, 'success');
    }

    async function saveImageAnnotationsToServer(imageRecord, { confirmOverwrite = false } = {}) {
        const imageSize = imageDimensions(imageRecord);
        const annotations = (appState.annotationsByImage.get(imageRecord.id) || [])
            .map(annotation => normalizeAnnotation(annotation, imageRecord))
            .filter(Boolean);
        appState.annotationsByImage.set(imageRecord.id, annotations);
        const payload = {
            image_name: imageRecord.name,
            image_path: imageRecord.displayPath,
            match_mode: annotationMatchModeForImage(imageRecord),
            format: currentAnnotationFormat(),
            overwrite: !confirmOverwrite,
            annotations,
            classes: appState.classes,
            image_width: imageSize ? imageSize.width : null,
            image_height: imageSize ? imageSize.height : null
        };

        const response = await apiFetch(apiPath('/api/annotations/save'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.status === 409 && confirmOverwrite) {
            const conflictData = await response.json();
            const shouldOverwrite = confirm(`Overwrite existing annotation file?\n\n${publicAnnotationPath(conflictData.path) || publicImageName(imageRecord)}`);
            if (!shouldOverwrite) throw new Error('Save cancelled.');

            const overwriteResponse = await apiFetch(apiPath('/api/annotations/save'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...payload, overwrite: true })
            });
            if (!overwriteResponse.ok) throw new Error(`Server error: ${overwriteResponse.statusText}`);
            const overwriteData = await overwriteResponse.json();
            if (overwriteData.error) throw new Error(overwriteData.error);
            updateAnnotationMatchAfterSave(imageRecord, overwriteData);
            return overwriteData;
        }

        if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

        const data = await response.json();
        if (data.error) throw new Error(data.error);
        updateAnnotationMatchAfterSave(imageRecord, data);
        return data;
    }

    async function loadProjectSettings() {
        try {
            const response = await apiFetch(apiPath('/api/project/settings'));
            if (!response.ok) return;

            const data = await response.json();
            if (data.error) throw new Error(data.error);
            applyProjectSettings(data);
        } catch (error) {
            console.warn('Project settings could not be loaded.', error);
        }
    }

    function normalizeAnnotationFormat(format) {
        const key = String(format || 'csv').trim().toLowerCase();
        return ANNOTATION_FORMATS[key] ? key : 'csv';
    }

    function currentAnnotationFormat() {
        return normalizeAnnotationFormat(annotationFormatSelect.value || appState.projectSettings.annotationFormat);
    }

    function formatLabel(format) {
        return ANNOTATION_FORMATS[normalizeAnnotationFormat(format)].label;
    }

    function updateAnnotationFormatUi() {
        const format = currentAnnotationFormat();
        const metadata = ANNOTATION_FORMATS[format];
        annotationFormatSelect.value = format;
        loadAnnotationFileInput.accept = Object.values(ANNOTATION_FORMATS)
            .map(item => item.accept)
            .join(',');
        annotationSourceFilesInput.accept = loadAnnotationFileInput.accept;
        annotationSourceFolderInput.accept = loadAnnotationFileInput.accept;
        exportAnnotationFileBtn.textContent = `Export ${metadata.label}`;
        loadAnnotationFileBtn.textContent = `Import ${metadata.label}`;
        loadServerAnnotationsBtn.textContent = `Load Saved ${metadata.label}`;
    }

    function annotationDownloadName(sourceImageName, format) {
        const stem = sourceImageName.replace(/\.[^/.]+$/, '') || 'annotations';
        const normalizedFormat = normalizeAnnotationFormat(format);
        if (normalizedFormat === 'yolo') return `${stem}.txt`;
        if (normalizedFormat === 'voc') return `${stem}.xml`;
        if (normalizedFormat === 'coco') return `${stem}_annotations.json`;
        return `${stem}_annotations.csv`;
    }

    function formatFromFileName(fileName) {
        const lowerName = String(fileName || '').toLowerCase();
        if (lowerName.endsWith('.csv')) return 'csv';
        if (lowerName.endsWith('.txt')) return 'yolo';
        if (lowerName.endsWith('.json')) return 'coco';
        if (lowerName.endsWith('.xml')) return 'voc';
        return null;
    }

    function imageDimensions(imageRecord) {
        const image = imageRecord?.originalImage || imageRecord?.processedImage;
        if (!image || !image.width || !image.height) return null;
        return { width: image.width, height: image.height };
    }

    async function handleAnnotationFormatChange() {
        const annotationFormat = currentAnnotationFormat();
        appState.projectSettings.annotationFormat = annotationFormat;
        updateAnnotationFormatUi();
        clearAnnotationMatches();

        try {
            const response = await apiFetch(apiPath('/api/project/settings'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ annotation_format: annotationFormat })
            });
            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            if (data.error) throw new Error(data.error);
            applyProjectSettings(data);

            if (appState.images.length > 0) {
                await refreshAnnotationMatches({ showFeedback: false });
            }

            const msg = `Annotation format set to ${formatLabel(annotationFormat)}.`;
            updateStatus(msg);
            showToast(msg, 'success');
        } catch (error) {
            const msg = `Failed to update annotation format: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        }
    }

    function applyProjectSettings(data) {
        appState.projectSettings.annotationOutputDir = data.annotation_output_dir || 'annotations';
        appState.projectSettings.annotationDirDisplay = data.annotation_dir_display || appState.projectSettings.annotationOutputDir;
        appState.projectSettings.annotationFormat = normalizeAnnotationFormat(data.annotation_format || appState.projectSettings.annotationFormat);
        appState.projectSettings.privacy = {
            phiSafeMode: Boolean(data.privacy?.phi_safe_mode),
            saltConfigured: Boolean(data.privacy?.salt_configured)
        };
        if (Array.isArray(data.sam_presets) && data.sam_presets.length > 0) {
            appState.samPresets = data.sam_presets.map(preset => ({
                ...preset,
                params: { ...DEFAULT_SAM_PARAMS, ...(preset.params || {}) }
            }));
        }
        if (data.sam_settings) {
            appState.projectSettings.samSettings = normalizeSamSettingsForClient(data.sam_settings);
        }
        annotationDirInput.value = appState.projectSettings.annotationOutputDir;
        annotationDirDisplay.textContent = appState.projectSettings.annotationDirDisplay;
        annotationDirDisplay.title = phiSafeMode()
            ? 'PHI-safe mode hides annotation folder paths.'
            : (data.annotation_dir || appState.projectSettings.annotationDirDisplay);
        annotationFormatSelect.value = appState.projectSettings.annotationFormat;
        updateAnnotationFormatUi();
        renderSamSettingsPanel();
        syncPreprocessSettingsInputs();
        updateAnnotationSourceDisplay();
    }

    function imagePayloads(images = appState.images) {
        return images.map(imageRecord => {
            const size = imageDimensions(imageRecord);
            return {
                id: imageRecord.id,
                name: imageRecord.name,
                display_path: imageRecord.displayPath,
                width: size ? size.width : null,
                height: size ? size.height : null
            };
        });
    }

    function clearAnnotationMatches() {
        appState.annotationMatchesByImage.clear();
        appState.matchSummary = null;
        updateMatchSummaryDisplay();
        renderImageBrowser();
    }

    function updateMatchSummaryDisplay() {
        if (appState.images.length === 0) {
            matchSummary.textContent = 'No image folder checked.';
            return;
        }

        const summary = appState.matchSummary;
        if (!summary) {
            matchSummary.textContent = localAnnotationSourceActive()
                ? 'Local annotation matches not checked.'
                : 'Annotation matches not checked.';
            return;
        }

        const prefix = localAnnotationSourceActive() ? 'Local source: ' : '';
        matchSummary.textContent = `${prefix}${summary.matched || summary.loaded || 0} matched, ${summary.missing || 0} missing, ${summary.ambiguous || 0} ambiguous.`;
    }

    function annotationMatchModeForImage(imageRecord) {
        const match = appState.annotationMatchesByImage.get(imageRecord.id);
        if (match?.status === 'matched' && match.match_mode) {
            return match.match_mode;
        }
        return hasDuplicateImageName(imageRecord) ? 'path' : 'basename';
    }

    function hasDuplicateImageName(imageRecord) {
        const normalizedName = imageRecord.name.toLowerCase();
        return appState.images.filter(otherRecord => otherRecord.name.toLowerCase() === normalizedName).length > 1;
    }

    function duplicateImageStems() {
        const counts = new Map();
        appState.images.forEach(imageRecord => {
            const stem = safeImageStem(imageRecord.name);
            counts.set(stem, (counts.get(stem) || 0) + 1);
        });
        return new Set(Array.from(counts.entries())
            .filter(([, count]) => count > 1)
            .map(([stem]) => stem));
    }

    function resolveLocalAnnotationMatch(imageRecord, duplicateStems, annotationFormat) {
        const candidates = localAnnotationCandidates(imageRecord, annotationFormat);
        const pathCandidate = candidates.find(candidate => candidate.match_mode === 'path');
        const baseCandidate = candidates.find(candidate => candidate.match_mode === 'basename');
        const pathMatch = candidates.find(candidate => candidate.match_mode === 'path' && candidate.sourceFile);
        const baseMatch = candidates.find(candidate => candidate.match_mode === 'basename' && candidate.sourceFile);
        const pathDuplicate = candidates.find(candidate => candidate.match_mode === 'path' && candidate.duplicateFileCount > 1);
        const baseDuplicate = candidates.find(candidate => candidate.match_mode === 'basename' && candidate.duplicateFileCount > 1);
        const isDuplicateName = duplicateStems.has(safeImageStem(imageRecord.name));

        let chosen = null;
        let status = 'missing';
        let message = 'No matching local annotation file found.';

        if (isDuplicateName) {
            if (pathMatch) {
                chosen = pathMatch;
                status = 'matched';
                message = 'Matched local annotation by image folder path.';
            } else if (pathDuplicate) {
                chosen = pathDuplicate;
                status = 'ambiguous';
                message = 'Multiple local annotation files have the same path-specific filename.';
            } else if (baseMatch) {
                chosen = baseMatch;
                status = 'ambiguous';
                message = 'Duplicate image name; local basename annotation file could match more than one image.';
            } else if (baseDuplicate) {
                chosen = baseDuplicate;
                status = 'ambiguous';
                message = 'Multiple local annotation files have the same basename annotation filename.';
            } else {
                chosen = pathCandidate || baseCandidate;
            }
        } else if (baseMatch) {
            chosen = baseMatch;
            status = 'matched';
            message = 'Matched local annotation by image name.';
        } else if (baseDuplicate) {
            chosen = baseDuplicate;
            status = 'ambiguous';
            message = 'Multiple local annotation files have the same basename annotation filename.';
        } else if (pathMatch) {
            chosen = pathMatch;
            status = 'matched';
            message = 'Matched local annotation by image folder path.';
        } else if (pathDuplicate) {
            chosen = pathDuplicate;
            status = 'ambiguous';
            message = 'Multiple local annotation files have the same path-specific filename.';
        } else {
            chosen = baseCandidate || pathCandidate;
        }

        const path = chosen?.sourceFile
            ? (chosen.sourceFile.webkitRelativePath || chosen.sourceFile.name)
            : (chosen?.fileName || annotationFileNames(imageRecord.name, imageRecord.displayPath, 'basename', annotationFormat)[0]);

        return {
            id: imageRecord.id,
            name: publicImageName(imageRecord),
            display_path: publicImagePath(imageRecord),
            format: annotationFormat,
            status,
            exists: status === 'matched',
            ambiguous: status === 'ambiguous',
            match_mode: chosen?.match_mode || 'basename',
            path: publicAnnotationPath(path),
            source: 'local',
            sourceFile: chosen?.sourceFile || null,
            annotation_count: 0,
            message,
        };
    }

    function localAnnotationCandidates(imageRecord, annotationFormat) {
        const candidates = [];
        if (imageRecord.displayPath && imageRecord.displayPath !== imageRecord.name) {
            annotationFileNames(imageRecord.name, imageRecord.displayPath, 'path', annotationFormat)
                .forEach(fileName => candidates.push(localAnnotationCandidate(fileName, 'path', annotationFormat)));
        }
        annotationFileNames(imageRecord.name, imageRecord.displayPath, 'basename', annotationFormat)
            .forEach(fileName => candidates.push(localAnnotationCandidate(fileName, 'basename', annotationFormat)));
        return candidates;
    }

    function localAnnotationCandidate(fileName, matchMode, annotationFormat) {
        const files = appState.annotationSource.fileMap.get(fileName.toLowerCase()) || [];
        return {
            fileName,
            match_mode: matchMode,
            format: annotationFormat,
            sourceFile: files.length === 1 ? files[0] : null,
            duplicateFileCount: files.length,
        };
    }

    function annotationFileNames(imageName, imagePath, matchMode, annotationFormat) {
        const stem = matchMode === 'path' && imagePath
            ? safePathStem(imagePath)
            : safeImageStem(imageName);

        if (annotationFormat === 'yolo') return [`${stem}.txt`, `${stem}_annotations.txt`];
        if (annotationFormat === 'coco') return [`${stem}_annotations.json`, `${stem}.json`];
        if (annotationFormat === 'voc') return [`${stem}.xml`, `${stem}_annotations.xml`];
        return [`${stem}_annotations.csv`];
    }

    function safeImageStem(imageName) {
        return stripExtension(safeFilePart(basename(imageName || 'image'))) || 'image';
    }

    function safePathStem(imagePath) {
        const parts = String(imagePath || '')
            .replace(/\\/g, '/')
            .split('/')
            .map(part => safeFilePart(part))
            .filter(Boolean);
        if (parts.length === 0) return safeImageStem(imagePath);
        return parts
            .map((part, index) => index === parts.length - 1 ? stripExtension(part) : part)
            .filter(Boolean)
            .join('__') || safeImageStem(imagePath);
    }

    function safeFilePart(value) {
        return String(value || '')
            .trim()
            .replace(/[^A-Za-z0-9_.-]+/g, '_')
            .replace(/^_+|_+$/g, '');
    }

    function stripExtension(fileName) {
        return String(fileName || '').replace(/\.[^/.]+$/, '');
    }

    async function countLocalAnnotationFile(file, annotationFormat, imageRecord) {
        if (!file) return 0;
        try {
            const text = await file.text();
            return parseAnnotationFile(text, annotationFormat, imageRecord).annotations.length;
        } catch {
            return null;
        }
    }

    function updateAnnotationMatchAfterSave(imageRecord, data) {
        appState.annotationMatchesByImage.set(imageRecord.id, {
            id: imageRecord.id,
            name: publicImageName(imageRecord),
            display_path: publicImagePath(imageRecord),
            status: 'matched',
            exists: true,
            ambiguous: false,
            match_mode: data.match_mode || annotationMatchModeForImage(imageRecord),
            path: publicAnnotationPath(data.path),
            annotation_count: data.count,
            format: data.format || currentAnnotationFormat(),
            message: 'Saved annotation file.'
        });
        recomputeMatchSummaryFromMatches();
    }

    function recomputeMatchSummaryFromMatches() {
        if (appState.images.length === 0 || appState.annotationMatchesByImage.size === 0) {
            appState.matchSummary = null;
            updateMatchSummaryDisplay();
            return;
        }

        const matches = appState.images
            .map(imageRecord => appState.annotationMatchesByImage.get(imageRecord.id))
            .filter(Boolean);
        appState.matchSummary = {
            total: appState.images.length,
            matched: matches.filter(match => match.status === 'matched').length,
            missing: matches.filter(match => match.status === 'missing').length,
            ambiguous: matches.filter(match => match.status === 'ambiguous').length,
        };
        updateMatchSummaryDisplay();
    }

    async function loadProjectClasses() {
        try {
            const response = await apiFetch(apiPath('/api/classes'));
            if (!response.ok) return;

            const data = await response.json();
            if (Array.isArray(data.classes)) {
                applyLoadedClasses(data.classes);
            }
        } catch (error) {
            console.warn('Project classes could not be loaded.', error);
        }
    }

    function scheduleProjectClassesSave() {
        if (classSaveTimer) clearTimeout(classSaveTimer);
        classSaveTimer = setTimeout(() => {
            classSaveTimer = null;
            saveProjectClasses({ silent: true });
        }, 500);
    }

    async function saveProjectClasses({ silent = false } = {}) {
        try {
            const response = await apiFetch(apiPath('/api/classes'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ classes: appState.classes })
            });
            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            if (data.error) throw new Error(data.error);
            if (!silent) {
                const msg = `Saved ${appState.classes.length} project classes.`;
                updateStatus(msg);
                showToast(msg, 'success');
            }
            return true;
        } catch (error) {
            console.warn('Project classes could not be saved.', error);
            if (!silent) {
                const msg = `Failed to save project classes: ${error.message}`;
                updateStatus(msg);
                showToast(msg, 'error');
            }
            return false;
        }
    }

    function applyLoadedAnnotations(annotations, { markDirty }) {
        const normalizedAnnotations = setAnnotationsForImage(
            appState.currentImage,
            annotations,
            { markDirty }
        );
        renderClassControls(normalizedAnnotations[0] ? normalizedAnnotations[0].class : classificationSelect.value);

        updateAnnotationLog();
        renderImageBrowser();
        draw();
        updateButtonStates();
    }

    function setAnnotationsForImage(imageRecord, annotations, { markDirty }) {
        if (!imageRecord) return [];

        const normalizedAnnotations = annotations
            .map(annotation => normalizeAnnotation(annotation, imageRecord))
            .filter(Boolean);

        appState.annotationsByImage.set(imageRecord.id, normalizedAnnotations);
        appState.annotationHistoryByImage.set(imageRecord.id, []);
        appState.annotationCounter = Math.max(
            appState.annotationCounter,
            ...normalizedAnnotations.map(annotation => annotation.id),
            0
        );

        const addedClassCount = ensureClassesForAnnotations(normalizedAnnotations);
        if (addedClassCount > 0) scheduleProjectClassesSave();

        if (markDirty) {
            appState.dirtyImages.add(imageRecord.id);
        }

        if (currentImageId() === imageRecord.id) {
            appState.selectedAnnotationIds.clear();
            appState.selectedCandidateIds.clear();
        }

        return normalizedAnnotations;
    }

    function applyLoadedClasses(classes) {
        const normalizedClasses = normalizeClassList(classes);
        appState.classes = normalizedClasses;
        const addedClassCount = ensureClassesForAnnotations(currentAnnotations());
        if (addedClassCount > 0) scheduleProjectClassesSave();
        renderClassControls(classificationSelect.value);
        draw();
        updateButtonStates();
    }

    function buildAnnotationExport(sourceImageName, annotations, format, imageRecord) {
        const normalizedFormat = normalizeAnnotationFormat(format);
        const exportAnnotations = annotations
            .map(annotation => normalizeAnnotation(annotation, imageRecord))
            .filter(Boolean);
        if (normalizedFormat === 'csv') {
            return {
                content: buildAnnotationCsv(sourceImageName, exportAnnotations),
                mime: ANNOTATION_FORMATS.csv.mime
            };
        }
        if (normalizedFormat === 'yolo') {
            return {
                content: buildAnnotationYolo(exportAnnotations, imageRecord),
                mime: ANNOTATION_FORMATS.yolo.mime
            };
        }
        if (normalizedFormat === 'coco') {
            return {
                content: buildAnnotationCoco(sourceImageName, exportAnnotations, imageRecord),
                mime: ANNOTATION_FORMATS.coco.mime
            };
        }
        if (normalizedFormat === 'voc') {
            return {
                content: buildAnnotationVoc(sourceImageName, exportAnnotations, imageRecord),
                mime: ANNOTATION_FORMATS.voc.mime
            };
        }
        throw new Error('Unsupported annotation format.');
    }

    function classesForExport(annotations) {
        const classes = normalizeClassList(appState.classes);
        const names = new Set(classes.map(cls => cls.name));
        annotations.forEach(annotation => {
            const name = normalizeClassName(String(annotation.class || 'Unlabeled')) || 'Unlabeled';
            if (names.has(name)) return;
            classes.push({
                name,
                color: CLASS_COLOR_PALETTE[classes.length % CLASS_COLOR_PALETTE.length],
                hotkey: ''
            });
            names.add(name);
        });
        return classes;
    }

    function classIndexByName(classes) {
        const indexByName = new Map();
        classes.forEach((cls, index) => indexByName.set(cls.name, index));
        return indexByName;
    }

    function normalizeContour(contour) {
        if (typeof contour === 'string' && contour.trim()) {
            try {
                contour = JSON.parse(contour);
            } catch (_error) {
                return null;
            }
        }
        if (!Array.isArray(contour)) return null;

        const points = [];
        contour.forEach(point => {
            if (!Array.isArray(point) || point.length < 2) return;
            const x = Number(point[0]);
            const y = Number(point[1]);
            if (!Number.isFinite(x) || !Number.isFinite(y)) return;
            points.push([x, y]);
        });

        return points.length >= 3 ? points : null;
    }

    function optionalFiniteNumber(value) {
        if (value === null || value === undefined || value === '') return null;
        const number = Number(value);
        return Number.isFinite(number) ? number : null;
    }

    function annotationMaskMetadata(annotation) {
        const metadata = {};
        const contour = normalizeContour(annotation?.contour);
        if (contour) metadata.contour = contour;

        [
            ['mask_area', 'mask_area'],
            ['predicted_iou', 'predicted_iou'],
            ['stability_score', 'stability_score']
        ].forEach(([sourceKey, targetKey]) => {
            const value = optionalFiniteNumber(annotation?.[sourceKey]);
            if (value !== null) metadata[targetKey] = value;
        });

        const source = String(annotation?.source || '').trim();
        if (source) metadata.source = source.slice(0, 64);
        return metadata;
    }

    function cocoSegmentationFromContour(contour) {
        const normalized = normalizeContour(contour);
        if (!normalized) return null;
        return [normalized.flatMap(point => point)];
    }

    function contourFromCocoSegmentation(segmentation) {
        if (!Array.isArray(segmentation) || segmentation.length === 0) return null;
        const polygon = Array.isArray(segmentation[0]) ? segmentation[0] : segmentation;
        if (!Array.isArray(polygon) || polygon.length < 6) return null;
        const contour = [];
        for (let index = 0; index < polygon.length - 1; index += 2) {
            contour.push([polygon[index], polygon[index + 1]]);
        }
        return normalizeContour(contour);
    }

    function buildAnnotationCsv(sourceImageName, annotations) {
        const rows = [[
            'source_image',
            'x_min',
            'y_min',
            'x_max',
            'y_max',
            'class_label',
            'contour',
            'mask_area',
            'source',
            'predicted_iou',
            'stability_score'
        ]];

        annotations.forEach(annotation => {
            const [x, y, w, h] = annotation.bbox.map(Math.round);
            const metadata = annotationMaskMetadata(annotation);
            rows.push([
                spreadsheetSafe(sourceImageName),
                x,
                y,
                x + w,
                y + h,
                spreadsheetSafe(annotation.class),
                metadata.contour ? JSON.stringify(metadata.contour) : '',
                metadata.mask_area ?? '',
                spreadsheetSafe(metadata.source || ''),
                metadata.predicted_iou ?? '',
                metadata.stability_score ?? ''
            ]);
        });

        return rows.map(row => row.map(csvEscape).join(',')).join('\n') + '\n';
    }

    function buildAnnotationYolo(annotations, imageRecord) {
        const size = imageDimensions(imageRecord);
        if (!size) throw new Error('YOLO export requires the loaded image dimensions.');

        const classes = classesForExport(annotations);
        const indexByName = classIndexByName(classes);
        return annotations.map(annotation => {
            const [x, y, w, h] = annotation.bbox;
            const className = normalizeClassName(String(annotation.class || 'Unlabeled')) || 'Unlabeled';
            const classIndex = indexByName.has(className) ? indexByName.get(className) : 0;
            const xCenter = (x + w / 2) / size.width;
            const yCenter = (y + h / 2) / size.height;
            return [
                classIndex,
                formatDecimal(xCenter),
                formatDecimal(yCenter),
                formatDecimal(w / size.width),
                formatDecimal(h / size.height)
            ].join(' ');
        }).join('\n') + '\n';
    }

    function buildAnnotationCoco(sourceImageName, annotations, imageRecord) {
        const size = imageDimensions(imageRecord) || { width: 0, height: 0 };
        const classes = classesForExport(annotations);
        const indexByName = classIndexByName(classes);
        const payload = {
            images: [{
                id: 1,
                file_name: sourceImageName,
                width: size.width,
                height: size.height
            }],
            categories: classes.map((cls, index) => ({ id: index + 1, name: cls.name })),
            annotations: annotations.map((annotation, index) => {
                const [x, y, w, h] = annotation.bbox;
                const className = normalizeClassName(String(annotation.class || 'Unlabeled')) || 'Unlabeled';
                const categoryId = (indexByName.has(className) ? indexByName.get(className) : 0) + 1;
                const metadata = annotationMaskMetadata(annotation);
                const segmentation = cocoSegmentationFromContour(metadata.contour);
                const cocoAnnotation = {
                    id: index + 1,
                    image_id: 1,
                    category_id: categoryId,
                    bbox: [x, y, w, h],
                    area: metadata.mask_area ?? w * h,
                    iscrowd: 0
                };
                if (segmentation) cocoAnnotation.segmentation = segmentation;
                ['source', 'mask_area', 'predicted_iou', 'stability_score'].forEach(key => {
                    if (metadata[key] !== undefined) cocoAnnotation[key] = metadata[key];
                });
                return cocoAnnotation;
            })
        };
        return JSON.stringify(payload, null, 2) + '\n';
    }

    function buildAnnotationVoc(sourceImageName, annotations, imageRecord) {
        const size = imageDimensions(imageRecord) || { width: 0, height: 0 };
        const lines = [
            '<annotation>',
            `  <filename>${xmlEscape(sourceImageName)}</filename>`,
            '  <size>',
            `    <width>${Math.round(size.width)}</width>`,
            `    <height>${Math.round(size.height)}</height>`,
            '    <depth>3</depth>',
            '  </size>'
        ];

        annotations.forEach(annotation => {
            const [x, y, w, h] = annotation.bbox;
            const className = normalizeClassName(String(annotation.class || 'Unlabeled')) || 'Unlabeled';
            lines.push(
                '  <object>',
                `    <name>${xmlEscape(className)}</name>`,
                '    <pose>Unspecified</pose>',
                '    <truncated>0</truncated>',
                '    <difficult>0</difficult>',
                '    <bndbox>',
                `      <xmin>${Math.round(x)}</xmin>`,
                `      <ymin>${Math.round(y)}</ymin>`,
                `      <xmax>${Math.round(x + w)}</xmax>`,
                `      <ymax>${Math.round(y + h)}</ymax>`,
                '    </bndbox>',
                '  </object>'
            );
        });

        lines.push('</annotation>');
        return lines.join('\n') + '\n';
    }

    function formatDecimal(value) {
        return Number(value).toFixed(6).replace(/0+$/, '').replace(/\.$/, '') || '0';
    }

    function xmlEscape(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&apos;');
    }

    function csvEscape(value) {
        const text = String(value ?? '');
        if (/[",\r\n]/.test(text)) {
            return `"${text.replace(/"/g, '""')}"`;
        }
        return text;
    }

    function spreadsheetSafe(value) {
        const text = String(value ?? '');
        return /^\s*[=+\-@]/.test(text) ? `'${text}` : text;
    }

    function parseAnnotationFile(text, format, imageRecord) {
        const normalizedFormat = normalizeAnnotationFormat(format);
        if (normalizedFormat === 'csv') return parseAnnotationCsv(text, imageNameAliases(imageRecord));
        if (normalizedFormat === 'yolo') return parseAnnotationYolo(text, imageRecord);
        if (normalizedFormat === 'coco') return parseAnnotationCoco(text, imageNameAliases(imageRecord));
        if (normalizedFormat === 'voc') return parseAnnotationVoc(text);
        throw new Error('Unsupported annotation format.');
    }

    function imageNameAliases(imageRecord) {
        return [
            imageRecord?.name,
            imageRecord?.displayPath,
            publicImageName(imageRecord),
            publicImagePath(imageRecord)
        ].filter(Boolean);
    }

    function normalizedBasenameSet(names) {
        return new Set(names.map(name => basename(name).toLowerCase()));
    }

    function parseAnnotationCsv(csvText, currentImageNames) {
        const rows = parseCsvRows(csvText).filter(row => row.some(field => field.trim() !== ''));
        if (rows.length < 2) {
            return { annotations: [], usedMatchedRows: false };
        }

        const headers = rows[0].map(normalizeCsvHeader);
        const records = rows.slice(1).map(row => {
            const record = {};
            headers.forEach((header, index) => {
                record[header] = row[index] || '';
            });
            return record;
        });

        const imageNames = normalizedBasenameSet(Array.isArray(currentImageNames) ? currentImageNames : [currentImageNames]);
        const rowsWithSourceImage = records.filter(record => record.source_image);
        const matchedRecords = records.filter(record => (
            record.source_image && imageNames.has(basename(record.source_image).toLowerCase())
        ));
        const selectedRecords = matchedRecords.length > 0 ? matchedRecords : records;

        const annotations = selectedRecords
            .map((record, index) => annotationFromRecord(record, index + 1))
            .filter(Boolean);

        return {
            annotations,
            usedMatchedRows: rowsWithSourceImage.length > 0 && matchedRecords.length > 0
        };
    }

    function parseAnnotationYolo(text, imageRecord) {
        const size = imageDimensions(imageRecord);
        if (!size) throw new Error('YOLO import requires the loaded image dimensions.');

        const annotations = [];
        text.split(/\r?\n/).forEach((rawLine, index) => {
            const line = rawLine.trim();
            if (!line || line.startsWith('#')) return;

            const parts = line.split(/\s+/);
            if (parts.length < 5) return;

            const classIndex = Number(parts[0]);
            const xCenter = Number(parts[1]) * size.width;
            const yCenter = Number(parts[2]) * size.height;
            const boxWidth = Number(parts[3]) * size.width;
            const boxHeight = Number(parts[4]) * size.height;
            const bbox = normalizeImportedBbox([
                xCenter - boxWidth / 2,
                yCenter - boxHeight / 2,
                boxWidth,
                boxHeight
            ]);
            if (!Number.isInteger(classIndex) || !bbox) return;

            const className = appState.classes[classIndex]?.name || `class_${classIndex}`;
            annotations.push({
                id: index + 1,
                bbox,
                class: className,
                type: 'loaded'
            });
        });

        return { annotations, usedMatchedRows: false };
    }

    function parseAnnotationCoco(text, currentImageNames) {
        const data = JSON.parse(text);
        if (!data || typeof data !== 'object') return { annotations: [], usedMatchedRows: false };

        const categories = new Map();
        (Array.isArray(data.categories) ? data.categories : []).forEach(category => {
            categories.set(category.id, String(category.name || `category_${category.id}`));
        });

        const images = Array.isArray(data.images) ? data.images : [];
        const targetNames = normalizedBasenameSet(Array.isArray(currentImageNames) ? currentImageNames : [currentImageNames]);
        let imageIds = new Set(images
            .filter(image => targetNames.has(basename(String(image.file_name || '')).toLowerCase()))
            .map(image => image.id));
        if (imageIds.size === 0 && images.length === 1) {
            imageIds = new Set([images[0].id]);
        }

        const rawAnnotations = Array.isArray(data.annotations) ? data.annotations : [];
        const annotations = rawAnnotations
            .filter(annotation => imageIds.size === 0 || imageIds.has(annotation.image_id))
            .map((annotation, index) => {
                const bbox = normalizeImportedBbox(annotation.bbox);
                if (!bbox) return null;

                const categoryName = categories.get(annotation.category_id) || `category_${annotation.category_id}`;
                const contour = contourFromCocoSegmentation(annotation.segmentation);
                return {
                    id: Number.isInteger(annotation.id) && annotation.id > 0 ? annotation.id : index + 1,
                    bbox,
                    class: categoryName,
                    type: 'loaded',
                    ...annotationMaskMetadata({
                        contour,
                        mask_area: annotation.mask_area ?? (contour ? annotation.area : null),
                        source: annotation.source,
                        predicted_iou: annotation.predicted_iou,
                        stability_score: annotation.stability_score
                    })
                };
            })
            .filter(Boolean);

        return {
            annotations,
            usedMatchedRows: imageIds.size > 0
        };
    }

    function parseAnnotationVoc(text) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(text, 'application/xml');
        if (doc.querySelector('parsererror')) {
            throw new Error('Invalid VOC XML.');
        }

        const annotations = Array.from(doc.querySelectorAll('object'))
            .map((objectNode, index) => {
                const boxNode = objectNode.querySelector('bndbox');
                if (!boxNode) return null;

                const xMin = Number(boxNode.querySelector('xmin')?.textContent);
                const yMin = Number(boxNode.querySelector('ymin')?.textContent);
                const xMax = Number(boxNode.querySelector('xmax')?.textContent);
                const yMax = Number(boxNode.querySelector('ymax')?.textContent);
                const bbox = normalizeImportedBbox([xMin, yMin, xMax - xMin, yMax - yMin]);
                if (!bbox) return null;

                const className = objectNode.querySelector('name')?.textContent?.trim() || 'Unlabeled';
                return {
                    id: index + 1,
                    bbox,
                    class: className,
                    type: 'loaded'
                };
            })
            .filter(Boolean);

        return { annotations, usedMatchedRows: false };
    }

    function parseCsvRows(text) {
        const rows = [];
        let row = [];
        let field = '';
        let inQuotes = false;

        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            const nextChar = text[i + 1];

            if (char === '"') {
                if (inQuotes && nextChar === '"') {
                    field += '"';
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }
                continue;
            }

            if (char === ',' && !inQuotes) {
                row.push(field);
                field = '';
                continue;
            }

            if ((char === '\n' || char === '\r') && !inQuotes) {
                if (char === '\r' && nextChar === '\n') i++;
                row.push(field);
                rows.push(row);
                row = [];
                field = '';
                continue;
            }

            field += char;
        }

        row.push(field);
        rows.push(row);
        return rows;
    }

    function normalizeCsvHeader(header) {
        return header.trim().toLowerCase().replace(/\s+/g, '_');
    }

    function annotationFromRecord(record, fallbackId) {
        const className = (
            record.class_label
            || record.class
            || record.label
            || record.category
            || 'Unlabeled'
        ).trim();

        let bbox = null;
        if (hasCsvFields(record, ['x_min', 'y_min', 'x_max', 'y_max'])) {
            const xMin = Number(record.x_min);
            const yMin = Number(record.y_min);
            const xMax = Number(record.x_max);
            const yMax = Number(record.y_max);
            bbox = [xMin, yMin, xMax - xMin, yMax - yMin];
        } else if (hasCsvFields(record, ['x', 'y', 'w', 'h'])) {
            bbox = [Number(record.x), Number(record.y), Number(record.w), Number(record.h)];
        }

        bbox = normalizeImportedBbox(bbox);
        if (!bbox) return null;

        const existingId = Number(record.id);
        return {
            id: Number.isInteger(existingId) && existingId > 0 ? existingId : fallbackId,
            bbox,
            class: className || 'Unlabeled',
            type: 'loaded',
            ...annotationMaskMetadata({
                contour: record.contour || record.segmentation,
                mask_area: record.mask_area,
                source: record.source,
                predicted_iou: record.predicted_iou,
                stability_score: record.stability_score
            })
        };
    }

    function normalizeImportedBbox(rawBbox) {
        if (!Array.isArray(rawBbox) || rawBbox.length !== 4) return null;
        const bbox = rawBbox.map(Number);
        if (bbox.some(value => !Number.isFinite(value))) return null;

        if (bbox[2] < 0) {
            bbox[0] += bbox[2];
            bbox[2] = Math.abs(bbox[2]);
        }
        if (bbox[3] < 0) {
            bbox[1] += bbox[3];
            bbox[3] = Math.abs(bbox[3]);
        }
        if (bbox[2] <= 0 || bbox[3] <= 0) return null;
        return bbox;
    }

    function hasCsvFields(record, fields) {
        return fields.every(field => record[field] !== undefined && record[field] !== '');
    }

    function basename(path) {
        return path.split(/[\\/]/).pop();
    }

    function normalizeAnnotation(annotation, imageRecord = appState.currentImage) {
        if (!annotation || !Array.isArray(annotation.bbox) || annotation.bbox.length !== 4) return null;

        const bbox = clampBboxToImage(annotation.bbox, imageRecord);
        if (!bbox) return null;

        const existingId = Number(annotation.id);
        return {
            id: Number.isInteger(existingId) && existingId > 0 ? existingId : ++appState.annotationCounter,
            bbox,
            class: String(annotation.class || 'Unlabeled').trim() || 'Unlabeled',
            type: annotation.type || 'loaded',
            ...annotationMaskMetadata(annotation)
        };
    }

    function screenUnits(value) {
        return value / appState.cameraZoom;
    }

    function strokeCandidateShape(candidate) {
        if (candidate.contour && candidate.contour.length > 2 && Array.isArray(candidate.contour[0])) {
            ctx.beginPath();
            ctx.moveTo(candidate.contour[0][0], candidate.contour[0][1]);
            for (let i = 1; i < candidate.contour.length; i++) {
                ctx.lineTo(candidate.contour[i][0], candidate.contour[i][1]);
            }
            ctx.closePath();
            ctx.stroke();
            return;
        }

        if (Array.isArray(candidate.bbox) && candidate.bbox.length === 4) {
            const [x, y, w, h] = candidate.bbox;
            ctx.strokeRect(x, y, w, h);
        }
    }

    function drawCandidateOverlay(candidate, isSelected) {
        const lineWidth = screenUnits(isSelected ? 2.5 : 1.75);
        const dash = [screenUnits(7), screenUnits(5)];

        ctx.save();
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.setLineDash(dash);

        ctx.strokeStyle = isSelected ? OVERLAY_COLORS.selectedHalo : OVERLAY_COLORS.contrastStroke;
        ctx.lineWidth = lineWidth + screenUnits(isSelected ? 4 : 2.5);
        ctx.globalAlpha = isSelected ? 0.95 : 0.72;
        strokeCandidateShape(candidate);

        ctx.strokeStyle = OVERLAY_COLORS.candidate;
        ctx.lineWidth = lineWidth;
        ctx.globalAlpha = isSelected ? 1 : 0.9;
        strokeCandidateShape(candidate);

        ctx.restore();
    }

    function drawAnnotationOverlay(annotation, isHighlighted) {
        const [x, y, w, h] = annotation.bbox;
        const classColor = getClassColor(annotation.class);

        ctx.save();
        ctx.setLineDash([]);
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';

        ctx.strokeStyle = isHighlighted ? OVERLAY_COLORS.selectedHalo : OVERLAY_COLORS.contrastStroke;
        ctx.lineWidth = screenUnits(isHighlighted ? 6 : 5);
        ctx.globalAlpha = isHighlighted ? 0.98 : 0.68;
        ctx.strokeRect(x, y, w, h);

        ctx.strokeStyle = classColor;
        ctx.lineWidth = screenUnits(isHighlighted ? 3 : 2.75);
        ctx.globalAlpha = 1;
        ctx.strokeRect(x, y, w, h);

        drawAnnotationLabel(annotation, x, y, classColor);
        ctx.restore();

        if (isHighlighted) {
            drawAnnotationHandles(ctx, annotation);
        }
    }

    function drawAnnotationLabel(annotation, x, y, classColor) {
        const label = `#${annotation.id}`;
        const fontSize = screenUnits(13);
        const paddingX = screenUnits(5);
        const paddingY = screenUnits(3);
        const gap = screenUnits(4);

        ctx.font = `600 ${fontSize}px system-ui, sans-serif`;
        ctx.textBaseline = 'middle';
        const labelWidth = ctx.measureText(label).width + paddingX * 2;
        const labelHeight = fontSize + paddingY * 2;
        const labelX = x;
        const labelY = y > labelHeight + gap ? y - labelHeight - gap : y + gap;

        ctx.fillStyle = OVERLAY_COLORS.labelBackground;
        ctx.fillRect(labelX, labelY, labelWidth, labelHeight);
        ctx.strokeStyle = OVERLAY_COLORS.labelBorder;
        ctx.lineWidth = screenUnits(1);
        ctx.strokeRect(labelX, labelY, labelWidth, labelHeight);
        ctx.fillStyle = classColor;
        ctx.fillRect(labelX, labelY, screenUnits(3), labelHeight);
        ctx.fillStyle = OVERLAY_COLORS.labelText;
        ctx.fillText(label, labelX + paddingX + screenUnits(2), labelY + labelHeight / 2);
    }

    function strokeScreenRect(rect, color, width, dash = []) {
        ctx.save();
        ctx.setLineDash(dash);
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);
        ctx.restore();
    }

    // --- RENDERING ---
    function draw() {
        resizeCanvasToContainer();

        const imageToDraw = currentDisplayImage();
        ctx.fillStyle = '#111';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        if (!imageToDraw) return;

        ctx.save();
        ctx.translate(appState.cameraOffset.x, appState.cameraOffset.y);
        ctx.scale(appState.cameraZoom, appState.cameraZoom);
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(imageToDraw, 0, 0);

        currentCandidates().forEach(candidate => {
            const isSelected = appState.selectedCandidateIds.has(candidate.id);
            drawCandidateOverlay(candidate, isSelected);
        });

        currentAnnotations().forEach(annotation => {
            const isHighlighted = appState.selectedAnnotationIds.has(annotation.id);
            drawAnnotationOverlay(annotation, isHighlighted);
        });

        ctx.restore();

        if (appState.isDrawing && appState.currentManualBox) {
            strokeScreenRect(appState.currentManualBox, OVERLAY_COLORS.contrastStroke, 4, [7, 5]);
            strokeScreenRect(appState.currentManualBox, OVERLAY_COLORS.manualBox, 2, [7, 5]);
        }

        if (appState.isAwaitingChoice && appState.choiceInfo) {
            strokeScreenRect(appState.choiceInfo.rect, OVERLAY_COLORS.selectedHalo, 4);
            strokeScreenRect(appState.choiceInfo.rect, OVERLAY_COLORS.manualBox, 2);

            appState.choiceInfo.buttons.forEach(button => {
                ctx.fillStyle = button.color;
                ctx.fillRect(button.x, button.y, button.w, button.h);
                ctx.fillStyle = 'white';
                ctx.font = 'bold 14px system-ui, sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(button.label, button.x + button.w / 2, button.y + button.h / 2);
            });
            ctx.textAlign = 'left';
            ctx.textBaseline = 'alphabetic';
        }

        if (zoomLevelDisplay) {
            zoomLevelDisplay.textContent = `${Math.round(appState.cameraZoom * 100)}%`;
        }
    }

    function drawAnnotationHandles(context, annotation) {
        const handleSize = BOX_HANDLE_SCREEN_SIZE / appState.cameraZoom;
        const half = handleSize / 2;
        const handles = annotationHandles(annotation);

        context.save();
        context.fillStyle = '#ffffff';
        context.strokeStyle = '#111111';
        context.lineWidth = 1 / appState.cameraZoom;

        Object.values(handles).forEach(point => {
            context.fillRect(point.x - half, point.y - half, handleSize, handleSize);
            context.strokeRect(point.x - half, point.y - half, handleSize, handleSize);
        });

        context.restore();
    }

    function updateAnnotationLog() {
        annotationLogBody.innerHTML = '';

        currentAnnotations()
            .slice()
            .sort((a, b) => a.id - b.id)
            .forEach(annotation => {
                const row = document.createElement('tr');
                row.dataset.annotationId = annotation.id;
                if (appState.selectedAnnotationIds.has(annotation.id)) {
                    row.classList.add('highlighted');
                }

                const bboxString = `(${annotation.bbox.map(value => Math.round(value)).join(', ')})`;
                [annotation.id, annotation.class, bboxString].forEach(value => {
                    const cell = document.createElement('td');
                    cell.textContent = String(value);
                    row.appendChild(cell);
                });
                annotationLogBody.appendChild(row);
            });

        updateAnnotationInspector();
        updateButtonStates();
    }

    function updateAnnotationInspector() {
        const selectedAnnotations = getSelectedAnnotations();
        const hasSingleSelection = selectedAnnotations.length === 1;

        if (selectedAnnotations.length === 0) {
            selectedAnnotationSummary.textContent = 'None';
        } else if (hasSingleSelection) {
            selectedAnnotationSummary.textContent = `#${selectedAnnotations[0].id} (${selectedAnnotations[0].class})`;
        } else {
            selectedAnnotationSummary.textContent = `${selectedAnnotations.length} selected`;
        }

        [bboxXInput, bboxYInput, bboxWInput, bboxHInput, applyBoxEditBtn].forEach(control => {
            control.disabled = !hasSingleSelection;
        });

        if (!hasSingleSelection) {
            bboxXInput.value = '';
            bboxYInput.value = '';
            bboxWInput.value = '';
            bboxHInput.value = '';
            return;
        }

        const [x, y, w, h] = selectedAnnotations[0].bbox;
        bboxXInput.value = Math.round(x);
        bboxYInput.value = Math.round(y);
        bboxWInput.value = Math.round(w);
        bboxHInput.value = Math.round(h);
    }

    function applyInspectorBoxEdit() {
        const selectedAnnotations = getSelectedAnnotations();
        if (selectedAnnotations.length !== 1) return;

        const annotation = selectedAnnotations[0];
        const rawValues = [bboxXInput.value, bboxYInput.value, bboxWInput.value, bboxHInput.value]
            .map(value => value.trim());
        const parsedValues = rawValues.map(Number);

        if (rawValues.some(value => value === '') || !parsedValues.every(Number.isFinite)) {
            const msg = 'Box coordinates must be valid numbers.';
            updateStatus(msg);
            showToast(msg, 'error');
            updateAnnotationInspector();
            return;
        }

        const newBbox = clampBboxToImage([
            parsedValues[0],
            parsedValues[1],
            Math.max(MIN_BOX_SIZE, parsedValues[2]),
            Math.max(MIN_BOX_SIZE, parsedValues[3])
        ]);
        if (!newBbox) {
            const msg = 'Box is outside the image bounds.';
            updateStatus(msg);
            showToast(msg, 'error');
            updateAnnotationInspector();
            return;
        }

        const oldBbox = annotation.bbox.slice();
        if (bboxesEqual(oldBbox, newBbox)) return;

        annotation.bbox = newBbox;
        currentHistory().push({
            type: 'geometry_edit',
            changes: [{ id: annotation.id, oldBbox, newBbox: newBbox.slice() }]
        });
        markCurrentImageDirty();
        renderImageBrowser();
        updateAnnotationLog();
        draw();

        const msg = `Updated annotation #${annotation.id}.`;
        updateStatus(msg);
        showToast(msg, 'success');
    }

    function getSelectedAnnotations() {
        return currentAnnotations().filter(annotation => appState.selectedAnnotationIds.has(annotation.id));
    }

    function renderClassControls(preferredClassName = classificationSelect.value) {
        classManager.innerHTML = '';

        if (appState.classes.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'class-empty-state';
            empty.textContent = 'No classes yet. Add a class or import annotations with class labels.';
            classManager.appendChild(empty);
        }

        appState.classes.forEach((cls, index) => {
            const row = document.createElement('div');
            row.className = 'class-row';
            row.dataset.classIndex = String(index);

            const colorInput = document.createElement('input');
            colorInput.type = 'color';
            colorInput.className = 'class-color-input';
            colorInput.value = cls.color;
            colorInput.title = `Color for ${cls.name}`;

            const nameInput = document.createElement('input');
            nameInput.type = 'text';
            nameInput.className = 'class-name-input';
            nameInput.value = cls.name;
            nameInput.placeholder = 'Class name';
            nameInput.title = 'Class name';

            const hotkeyInput = document.createElement('input');
            hotkeyInput.type = 'text';
            hotkeyInput.className = 'class-hotkey-input';
            hotkeyInput.value = cls.hotkey ? cls.hotkey.toUpperCase() : '';
            hotkeyInput.placeholder = '-';
            hotkeyInput.maxLength = 1;
            hotkeyInput.title = 'Optional keyboard shortcut';

            const deleteButton = document.createElement('button');
            deleteButton.type = 'button';
            deleteButton.className = 'btn btn-secondary class-delete-btn';
            deleteButton.textContent = 'X';
            deleteButton.title = `Delete ${cls.name}`;

            row.appendChild(colorInput);
            row.appendChild(nameInput);
            row.appendChild(hotkeyInput);
            row.appendChild(deleteButton);
            classManager.appendChild(row);
        });

        renderClassOptions(preferredClassName);
    }

    function renderClassOptions(preferredClassName = classificationSelect.value) {
        classificationSelect.innerHTML = '';
        if (appState.classes.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'Create a class first';
            classificationSelect.appendChild(option);
            classificationSelect.value = '';
            return;
        }

        appState.classes.forEach(cls => {
            const option = document.createElement('option');
            option.value = cls.name;
            option.textContent = cls.name;
            classificationSelect.appendChild(option);
        });

        const selectedClass = appState.classes.find(cls => cls.name === preferredClassName)
            ? preferredClassName
            : appState.classes[0]?.name || '';
        classificationSelect.value = selectedClass;
    }

    function updateButtonStates() {
        const imageLoaded = !!appState.currentImage;
        const selectionExists = appState.selectedCandidateIds.size > 0 || appState.selectedAnnotationIds.size > 0;
        const historyExists = currentHistory().length > 0;
        const annotationsExist = currentAnnotations().length > 0;
        const candidatesExist = currentCandidates().length > 0;
        const classesExist = appState.classes.length > 0;
        const index = currentImageIndex();

        runSamBtn.disabled = !imageLoaded;
        runSamBtn.textContent = imageLoaded && appState.currentImage.samHasRun ? 'Re-run SAM2' : 'Run SAM2 & Filter';
        clearCandidatesBtn.disabled = !imageLoaded || !candidatesExist;
        keepAnnotationsInput.disabled = !imageLoaded;
        manualAnnotationBtn.disabled = !imageLoaded;
        manualAnnotationBtn.textContent = appState.isManualMode ? 'Exit Manual Box (B)' : 'Manual Box (B)';
        const selectedPreprocess = selectedPreprocessMethod();
        const activePreprocess = hasActivePreprocess(appState.currentImage);
        const activePreprocessMethod = appState.currentImage?.preprocessMethod || 'original';
        const preprocessSelectedOriginal = selectedPreprocess === 'original';
        applyPreprocessBtn.disabled = !imageLoaded || preprocessSelectedOriginal;
        applyPreprocessBtn.textContent = preprocessSelectedOriginal
            ? 'Original Active'
            : activePreprocess && activePreprocessMethod === selectedPreprocess
                ? `${preprocessLabel(selectedPreprocess)} Active`
                : `Apply ${preprocessLabel(selectedPreprocess)}`;
        applyPreprocessBtn.title = 'Apply the selected preprocessing to the displayed image; future SAM runs apply the same preprocessing on the server.';
        restoreOriginalBtn.disabled = !imageLoaded || !activePreprocess;
        restoreOriginalBtn.title = 'Restore the original display and use the original image for future SAM runs.';
        openPreprocessSettingsBtn.disabled = false;
        preprocessSummary.textContent = activePreprocess
            ? `${preprocessLabel(activePreprocessMethod)} active. Original image is preserved.`
            : 'Original image is preserved.';
        classificationSelect.disabled = !classesExist;
        applyClassificationBtn.disabled = !selectionExists || !classesExist;
        oneClickAcceptInput.disabled = !imageLoaded || !classesExist || !candidatesExist;
        if (!classesExist || !imageLoaded) oneClickAcceptInput.checked = false;
        quickClassInput.disabled = false;
        quickAddClassBtn.disabled = false;
        undoBtn.disabled = !historyExists;
        exportAnnotationFileBtn.disabled = !annotationsExist;
        loadAnnotationFileBtn.disabled = !imageLoaded;
        loadAnnotationFileInput.disabled = !imageLoaded;
        loadServerAnnotationsBtn.disabled = !imageLoaded;
        refreshMatchesBtn.textContent = localAnnotationSourceActive() ? 'Check Local Matches' : 'Check Matches';
        loadMatchedBtn.textContent = localAnnotationSourceActive() ? 'Load Local Matched' : 'Load Matched';
        useServerAnnotationSourceBtn.disabled = !localAnnotationSourceActive();
        saveServerBtn.disabled = !imageLoaded;
        saveAllServerBtn.disabled = appState.dirtyImages.size === 0;
        refreshMatchesBtn.disabled = appState.images.length === 0;
        loadMatchedBtn.disabled = !appState.matchSummary || ((appState.matchSummary.matched || appState.matchSummary.loaded || 0) === 0);
        prevImageBtn.disabled = index <= 0;
        nextImageBtn.disabled = index === -1 || index >= appState.images.length - 1;
    }

    function getClassRowIndex(element) {
        const row = element.closest('.class-row');
        if (!row) return null;

        const index = parseInt(row.dataset.classIndex, 10);
        return Number.isInteger(index) ? index : null;
    }

    function normalizeClassName(value) {
        return value.trim().replace(/\s+/g, ' ');
    }

    function normalizeHotkey(value) {
        const match = value.trim().toLowerCase().match(/[a-z0-9]/);
        return match ? match[0] : '';
    }

    function getUniqueClassName() {
        let index = appState.classes.length + 1;
        let name = `Class ${index}`;

        while (appState.classes.some(cls => cls.name === name)) {
            index++;
            name = `Class ${index}`;
        }

        return name;
    }

    function getFirstAvailableHotkey(className) {
        const usedHotkeys = new Set(appState.classes.map(cls => cls.hotkey).filter(Boolean));
        const candidates = [
            ...className.toLowerCase().replace(/[^a-z0-9]/g, ''),
            ...'abcdefghijklmnopqrstuvwxyz0123456789'
        ];

        return candidates.find(candidate => !usedHotkeys.has(candidate)) || '';
    }

    function classExists(className) {
        return appState.classes.some(cls => cls.name === className);
    }

    function normalizeClassList(classes) {
        const seenNames = new Set();
        const seenHotkeys = new Set();
        const normalizedClasses = [];

        if (!Array.isArray(classes)) return [];

        classes.forEach((cls, index) => {
            const name = normalizeClassName(String(cls.name || ''));
            if (!name || seenNames.has(name)) return;

            const hotkey = normalizeHotkey(String(cls.hotkey || ''));
            const safeHotkey = hotkey && !seenHotkeys.has(hotkey) ? hotkey : '';
            const color = /^#[0-9a-f]{6}$/i.test(String(cls.color || ''))
                ? cls.color
                : CLASS_COLOR_PALETTE[index % CLASS_COLOR_PALETTE.length];

            normalizedClasses.push({ name, color, hotkey: safeHotkey });
            seenNames.add(name);
            if (safeHotkey) seenHotkeys.add(safeHotkey);
        });

        return normalizedClasses;
    }

    function ensureClassesForAnnotations(annotations) {
        const existingNames = new Set(appState.classes.map(cls => cls.name));
        let addedCount = 0;

        annotations.forEach(annotation => {
            const className = normalizeClassName(String(annotation.class || 'Unlabeled')) || 'Unlabeled';
            annotation.class = className;

            if (existingNames.has(className)) return;

            appState.classes.push({
                name: className,
                color: CLASS_COLOR_PALETTE[appState.classes.length % CLASS_COLOR_PALETTE.length],
                hotkey: getFirstAvailableHotkey(className)
            });
            existingNames.add(className);
            addedCount++;
        });

        return addedCount;
    }

    function countAnnotationsWithClass(className) {
        let count = 0;
        for (const annotations of appState.annotationsByImage.values()) {
            count += annotations.filter(annotation => annotation.class === className).length;
        }
        return count;
    }

    function renameAnnotationClass(oldName, newName) {
        let changedCount = 0;

        for (const [imageId, annotations] of appState.annotationsByImage.entries()) {
            let imageChanged = false;
            annotations.forEach(annotation => {
                if (annotation.class === oldName) {
                    annotation.class = newName;
                    changedCount++;
                    imageChanged = true;
                }
            });

            if (imageChanged) {
                appState.dirtyImages.add(imageId);
            }
        }

        return changedCount;
    }

    function deleteAnnotationsWithClass(className) {
        let deletedCount = 0;

        for (const [imageId, annotations] of appState.annotationsByImage.entries()) {
            const remainingAnnotations = annotations.filter(annotation => annotation.class !== className);
            const removedCount = annotations.length - remainingAnnotations.length;
            if (removedCount === 0) continue;

            appState.annotationsByImage.set(imageId, remainingAnnotations);
            appState.annotationHistoryByImage.set(imageId, []);
            appState.dirtyImages.add(imageId);
            deletedCount += removedCount;
        }

        appState.selectedAnnotationIds.clear();
        appState.logItemToModify = null;
        return deletedCount;
    }

    // --- STATE HELPERS ---
    function createImageRecord(file, imageElement = null, index = appState.images.length) {
        const displayPath = file.webkitRelativePath || file.name;
        const publicBaseName = `image_${String(index + 1).padStart(5, '0')}`;
        const extension = imageExtension(file.name);
        return {
            id: `${displayPath}:${file.size}:${file.lastModified}`,
            name: file.name,
            displayPath,
            publicName: `${publicBaseName}${extension}`,
            publicDisplayPath: `${publicBaseName}${extension}`,
            file,
            originalImage: imageElement,
            processedImage: null,
            preprocessMethod: 'original',
            preprocessLabel: '',
            preprocessParams: null,
            claheApplied: false,
            samHasRun: false,
            serverAnnotationsChecked: false
        };
    }

    function phiSafeMode() {
        return Boolean(appState.projectSettings.privacy?.phiSafeMode);
    }

    function imageExtension(fileName) {
        const match = String(fileName || '').match(/\.[^.\\/]+$/);
        return match ? match[0].toLowerCase() : '';
    }

    function publicImageName(imageRecord) {
        if (!imageRecord) return 'unknown_image';
        return phiSafeMode() ? imageRecord.publicName : imageRecord.name;
    }

    function publicImagePath(imageRecord) {
        if (!imageRecord) return '';
        return phiSafeMode() ? imageRecord.publicDisplayPath : imageRecord.displayPath;
    }

    function publicAnnotationPath(path) {
        if (!path) return '';
        return phiSafeMode() ? 'annotation file' : path;
    }

    function initializeImageState(imageId) {
        if (!appState.annotationsByImage.has(imageId)) appState.annotationsByImage.set(imageId, []);
        if (!appState.candidateAnnotationsByImage.has(imageId)) appState.candidateAnnotationsByImage.set(imageId, []);
        if (!appState.annotationHistoryByImage.has(imageId)) appState.annotationHistoryByImage.set(imageId, []);
    }

    function currentImageId() {
        return appState.currentImage ? appState.currentImage.id : null;
    }

    function currentImageIndex() {
        if (!appState.currentImage) return -1;
        return appState.images.findIndex(imageRecord => imageRecord.id === appState.currentImage.id);
    }

    function currentAnnotations() {
        const imageId = currentImageId();
        if (!imageId) return [];
        if (!appState.annotationsByImage.has(imageId)) appState.annotationsByImage.set(imageId, []);
        return appState.annotationsByImage.get(imageId);
    }

    function setCurrentAnnotations(annotations) {
        const imageId = currentImageId();
        if (!imageId) return;
        const normalizedAnnotations = annotations
            .map(annotation => normalizeAnnotation(annotation, appState.currentImage))
            .filter(Boolean);
        appState.annotationsByImage.set(imageId, normalizedAnnotations);
    }

    function currentCandidates() {
        const imageId = currentImageId();
        if (!imageId) return [];
        if (!appState.candidateAnnotationsByImage.has(imageId)) appState.candidateAnnotationsByImage.set(imageId, []);
        return appState.candidateAnnotationsByImage.get(imageId);
    }

    function setCurrentCandidates(candidates) {
        const imageId = currentImageId();
        if (!imageId) return;
        appState.candidateAnnotationsByImage.set(imageId, candidates);
    }

    function currentHistory() {
        const imageId = currentImageId();
        if (!imageId) return [];
        if (!appState.annotationHistoryByImage.has(imageId)) appState.annotationHistoryByImage.set(imageId, []);
        return appState.annotationHistoryByImage.get(imageId);
    }

    function setCurrentHistory(history) {
        const imageId = currentImageId();
        if (!imageId) return;
        appState.annotationHistoryByImage.set(imageId, history);
    }

    function currentDisplayImage() {
        const imageRecord = appState.currentImage;
        if (!imageRecord) return null;
        return hasActivePreprocess(imageRecord) ? imageRecord.processedImage : imageRecord.originalImage;
    }

    function markCurrentImageDirty() {
        const imageId = currentImageId();
        if (imageId) appState.dirtyImages.add(imageId);
    }

    function resetInteractionState() {
        appState.selectedCandidateIds.clear();
        appState.selectedAnnotationIds.clear();
        appState.logItemToModify = null;
        appState.isDrawing = false;
        appState.isPanning = false;
        appState.isAwaitingChoice = false;
        appState.choiceInfo = null;
        appState.currentManualBox = null;
        appState.boxEditMode = null;
        appState.boxEditHandle = null;
        appState.boxEditStartWorld = null;
        appState.boxEditOriginalBboxes = new Map();
        logContextMenu.classList.add('hidden');

        if (appState.isManualMode) {
            manualAnnotationBtn.classList.remove('active');
            appState.isManualMode = false;
        }

        canvas.style.cursor = 'grab';
    }

    function resetState() {
        appState.images = [];
        appState.currentImage = null;
        appState.annotationsByImage.clear();
        appState.candidateAnnotationsByImage.clear();
        appState.annotationHistoryByImage.clear();
        appState.annotationMatchesByImage.clear();
        appState.selectedCandidateIds.clear();
        appState.selectedAnnotationIds.clear();
        appState.dirtyImages.clear();
        appState.matchSummary = null;
        appState.annotationCounter = 0;
        appState.candidateCounter = 0;
        appState.logItemToModify = null;
        appState.isDrawing = false;
        appState.isPanning = false;
        appState.isAwaitingChoice = false;
        appState.choiceInfo = null;
        appState.currentManualBox = null;
        appState.boxEditMode = null;
        appState.boxEditHandle = null;
        appState.boxEditStartWorld = null;
        appState.boxEditOriginalBboxes = new Map();
        appState.cameraOffset = { x: 0, y: 0 };
        appState.cameraZoom = 1;

        if (appState.isManualMode) {
            manualAnnotationBtn.classList.remove('active');
            appState.isManualMode = false;
        }

        canvas.style.cursor = 'grab';
        updateCurrentImageDisplay();
        renderImageBrowser();
        updateMatchSummaryDisplay();
        updateAnnotationLog();
        fitImageToView();
        draw();
        updateStatus('Please load an image.');
        updateButtonStates();
    }

    // --- GENERAL HELPERS ---
    function unsavedImageCount() {
        return appState.dirtyImages.size;
    }

    function unsavedImageSummary(count = unsavedImageCount()) {
        return `${count} image${count === 1 ? '' : 's'}`;
    }

    function confirmDiscardUnsavedChanges(actionText) {
        const count = unsavedImageCount();
        if (count === 0) return true;
        return window.confirm(
            `You have unsaved annotation changes for ${unsavedImageSummary(count)}. ${actionText}\n\nContinue and discard those changes?`
        );
    }

    function confirmProceedWithUnsavedChanges(actionText) {
        const count = unsavedImageCount();
        if (count === 0) return true;
        return window.confirm(
            `You have unsaved annotation changes for ${unsavedImageSummary(count)}. ${actionText}\n\nContinue?`
        );
    }

    function confirmReplaceUnsavedAnnotations(actionText, count = 1) {
        return window.confirm(
            `This will replace unsaved annotations for ${unsavedImageSummary(count)}. ${actionText}\n\nContinue?`
        );
    }

    function handleBeforeUnload(event) {
        if (unsavedImageCount() === 0) return;
        event.preventDefault();
        event.returnValue = '';
    }

    function resizeCanvasToContainer() {
        const container = document.getElementById('canvas-container');
        if (container.clientWidth !== canvas.width || container.clientHeight !== canvas.height) {
            canvas.width = container.clientWidth;
            canvas.height = container.clientHeight;
            return true;
        }
        return false;
    }

    function fitImageToView() {
        const imageRecord = appState.currentImage;
        if (!imageRecord || canvas.width < 1) return;

        const padding = 0.95;
        const canvasAspect = canvas.width / canvas.height;
        const imageAspect = imageRecord.originalImage.width / imageRecord.originalImage.height;
        appState.cameraZoom = canvasAspect > imageAspect
            ? (canvas.height / imageRecord.originalImage.height) * padding
            : (canvas.width / imageRecord.originalImage.width) * padding;
        appState.cameraOffset.x = (canvas.width - imageRecord.originalImage.width * appState.cameraZoom) / 2;
        appState.cameraOffset.y = (canvas.height - imageRecord.originalImage.height * appState.cameraZoom) / 2;
    }

    function getScreenPoint(clientX, clientY) {
        const rect = canvas.getBoundingClientRect();
        return { x: clientX - rect.left, y: clientY - rect.top };
    }

    function getWorldPoint(screenX, screenY) {
        return {
            x: (screenX - appState.cameraOffset.x) / appState.cameraZoom,
            y: (screenY - appState.cameraOffset.y) / appState.cameraZoom
        };
    }

    function pointInsideRect(point, rect) {
        return point.x >= rect.x
            && point.x <= rect.x + rect.w
            && point.y >= rect.y
            && point.y <= rect.y + rect.h;
    }

    function getClassColor(className) {
        const classInfo = appState.classes.find(cls => cls.name === className);
        return classInfo ? classInfo.color : '#9ca3af';
    }

    function updateCurrentImageDisplay() {
        const index = currentImageIndex();
        const activePreprocess = hasActivePreprocess(appState.currentImage);
        const activePreprocessLabel = activePreprocess
            ? preprocessLabel(appState.currentImage.preprocessMethod)
            : '';
        currentImageName.textContent = appState.currentImage ? publicImagePath(appState.currentImage) : 'None';
        currentImageName.title = appState.currentImage ? publicImagePath(appState.currentImage) : '';
        imagePosition.textContent = index >= 0 ? `${index + 1} / ${appState.images.length}` : '0 / 0';
        currentImageState.textContent = appState.currentImage
            ? imageStateSummary(appState.currentImage)
            : 'No image loaded.';
        currentPreprocessBadge.textContent = activePreprocess
            ? `${activePreprocessLabel} view + server SAM`
            : 'Processed view + server SAM';
        currentPreprocessBadge.title = activePreprocess
            ? `Original image is preserved; display uses ${activePreprocessLabel}, and SAM applies it server-side.`
            : 'Original image is preserved; display uses the selected preprocessing while active, and SAM applies it server-side.';
        preprocessOverlayTitle.textContent = activePreprocess
            ? `${activePreprocessLabel} active`
            : 'Preprocessing active';
        preprocessOverlayDetail.textContent = activePreprocess
            ? 'Display uses the processed image; SAM applies it server-side'
            : 'Display uses the processed image; SAM applies it server-side';
        currentPreprocessBadge.classList.toggle('hidden', !activePreprocess);
        preprocessOverlay.classList.toggle('hidden', !activePreprocess);
    }

    function capitalizeFirst(value) {
        return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
    }

    function isSupportedImageFile(file) {
        const lowerName = String(file.name || '').toLowerCase();
        const hasAllowedExtension = ALLOWED_IMAGE_EXTENSIONS.some(extension => lowerName.endsWith(extension));
        if (!hasAllowedExtension) return false;
        if (!file.type) return true;
        return ALLOWED_IMAGE_MIME_TYPES.has(file.type.toLowerCase());
    }

    function imageSortName(file) {
        return file.webkitRelativePath || file.name;
    }

    function setLoader(visible, text = 'Processing...') {
        loaderText.textContent = text;
        loader.classList.toggle('hidden', !visible);
    }

    function updateStatus(message) {
        statusText.textContent = message;
    }

    function showToast(message, type = 'info', duration = 3000) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.animationDuration = '0.3s, 0.5s';
        toast.style.animationDelay = `0s, ${duration / 1000 - 0.5}s`;
        container.appendChild(toast);
        setTimeout(() => {
            toast.remove();
        }, duration);
    }

    async function initializeApp() {
        renderSamSettingsPanel();
        syncPreprocessSettingsInputs();
        resetState();
        renderClassControls();
        await loadProjectSettings();
        await loadProjectClasses();
        resizeCanvasToContainer();
        draw();
        updateButtonStates();
    }

    initializeApp();
});
