document.addEventListener('DOMContentLoaded', () => {
    // --- CONSTANTS ---
    const frontendConfig = window.SAM2FrontendConfig;
    if (!frontendConfig) {
        throw new Error('SAM2FrontendConfig must be loaded before script.js.');
    }
    const {
        ANNOTATION_FORMATS,
        CLASS_COLOR_PALETTE,
        MAX_ZOOM,
        MIN_ZOOM,
        SCROLL_SENSITIVITY,
        ZOOM_STEP,
        MIN_BOX_SIZE,
        NEW_CLASS_ACTION,
        DEFAULT_SAM_PRESET
    } = frontendConfig;

    const apiWorkflows = window.SAM2ApiWorkflows;
    if (!apiWorkflows) {
        throw new Error('SAM2ApiWorkflows must be loaded before script.js.');
    }

    const stateStore = window.SAM2StateStore;
    if (!stateStore) {
        throw new Error('SAM2StateStore must be loaded before script.js.');
    }

    const domRefs = window.SAM2DomRefs;
    if (!domRefs) {
        throw new Error('SAM2DomRefs must be loaded before script.js.');
    }

    const annotationCodecs = window.SAM2AnnotationCodecs;
    if (!annotationCodecs) {
        throw new Error('SAM2AnnotationCodecs must be loaded before script.js.');
    }
    const {
        normalizeAnnotationFormat,
        formatLabel,
        annotationDownloadName,
        formatFromFileName,
        annotationMaskMetadata,
        normalizeContour
    } = annotationCodecs;

    const annotationController = window.SAM2AnnotationController;
    if (!annotationController) {
        throw new Error('SAM2AnnotationController must be loaded before script.js.');
    }
    const projectDatasetController = window.SAM2ProjectDatasetController;
    if (!projectDatasetController) {
        throw new Error('SAM2ProjectDatasetController must be loaded before script.js.');
    }
    const annotationWorkflowController = window.SAM2AnnotationWorkflowController;
    if (!annotationWorkflowController) {
        throw new Error('SAM2AnnotationWorkflowController must be loaded before script.js.');
    }

    const fileUtils = window.SAM2FileUtils;
    if (!fileUtils) {
        throw new Error('SAM2FileUtils must be loaded before script.js.');
    }
    const {
        isSupportedImageFile,
        imageSortName
    } = fileUtils;

    const imageController = window.SAM2ImageController;
    if (!imageController) {
        throw new Error('SAM2ImageController must be loaded before script.js.');
    }

    const annotationMatching = window.SAM2AnnotationMatching;
    if (!annotationMatching) {
        throw new Error('SAM2AnnotationMatching must be loaded before script.js.');
    }

    const projectSettingsClient = window.SAM2ProjectSettingsClient;
    if (!projectSettingsClient) {
        throw new Error('SAM2ProjectSettingsClient must be loaded before script.js.');
    }
    const {
        preprocessLabel,
        preprocessBadgeLabel,
        hasActivePreprocess
    } = projectSettingsClient;

    const settingsController = window.SAM2SettingsController;
    if (!settingsController) {
        throw new Error('SAM2SettingsController must be loaded before script.js.');
    }
    const samSettingsUiController = window.SAM2SamSettingsUiController;
    if (!samSettingsUiController) {
        throw new Error('SAM2SamSettingsUiController must be loaded before script.js.');
    }

    const classManagerLogic = window.SAM2ClassManager;
    if (!classManagerLogic) {
        throw new Error('SAM2ClassManager must be loaded before script.js.');
    }
    const classUiController = window.SAM2ClassUiController;
    if (!classUiController) {
        throw new Error('SAM2ClassUiController must be loaded before script.js.');
    }
    const controlsUiController = window.SAM2ControlsUiController;
    if (!controlsUiController) {
        throw new Error('SAM2ControlsUiController must be loaded before script.js.');
    }
    const annotationLogController = window.SAM2AnnotationLogController;
    if (!annotationLogController) {
        throw new Error('SAM2AnnotationLogController must be loaded before script.js.');
    }
    const modalKeyboardController = window.SAM2ModalKeyboardController;
    if (!modalKeyboardController) {
        throw new Error('SAM2ModalKeyboardController must be loaded before script.js.');
    }
    const {
        normalizeClassName,
        normalizeHotkey,
        classExists,
        normalizeClassList
    } = classManagerLogic;

    const canvasGeometry = window.SAM2CanvasGeometry;
    if (!canvasGeometry) {
        throw new Error('SAM2CanvasGeometry must be loaded before script.js.');
    }

    const canvasInteractionController = window.SAM2CanvasInteractionController;
    if (!canvasInteractionController) {
        throw new Error('SAM2CanvasInteractionController must be loaded before script.js.');
    }

    const canvasRenderer = window.SAM2CanvasRenderer;
    if (!canvasRenderer) {
        throw new Error('SAM2CanvasRenderer must be loaded before script.js.');
    }

    // --- ELEMENT SELECTION ---
    const {
        loadImageInput,
        openFolderInput,
        runSamBtn,
        clearCandidatesBtn,
        keepAnnotationsInput,
        openSamSettingsBtn,
        samSettingsModal,
        closeSamSettingsBtn,
        samPresetSummary,
        samDeviceSelect,
        samDeviceStatus,
        samReadinessText,
        samPresetSelect,
        samAreaModeSelect,
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
        samUseM2mInput,
        samRiskText,
        applySamSettingsBtn,
        resetSamPresetBtn,
        preprocessMethodSelect,
        applyPreprocessBtn,
        openPreprocessSettingsBtn,
        restoreOriginalBtn,
        preprocessSummary,
        preprocessSettingsModal,
        closePreprocessSettingsBtn,
        preprocessGammaInput,
        preprocessClaheClipInput,
        preprocessClaheTileInput,
        preprocessUnsharpAmountInput,
        preprocessUnsharpRadiusInput,
        preprocessUnsharpThresholdInput,
        preprocessRetinexStrengthInput,
        applyPreprocessSettingsBtn,
        resetPreprocessSettingsBtn,
        manualAnnotationBtn,
        undoBtn,
        redoBtn,
        exportAnnotationFileBtn,
        validateProjectDatasetBtn,
        exportProjectDatasetBtn,
        loadAnnotationFileBtn,
        loadAnnotationFileInput,
        loadServerAnnotationsBtn,
        saveServerBtn,
        saveAllServerBtn,
        reviewAndNextBtn,
        confirmEmptyBtn,
        reopenReviewBtn,
        unsavedStateIndicator,
        currentImageName,
        currentPreprocessBadge,
        imagePosition,
        currentImageState,
        prevImageBtn,
        nextImageBtn,
        imageQueueProgress,
        imageQueueFilters,
        imageList,
        annotationDirInput,
        setAnnotationDirBtn,
        annotationDirDisplay,
        loadAnnotationSourceFilesBtn,
        loadAnnotationSourceFolderBtn,
        useServerAnnotationSourceBtn,
        annotationSourceFilesInput,
        annotationSourceFolderInput,
        annotationSourceDisplay,
        annotationFormatSelect,
        refreshMatchesBtn,
        loadMatchedBtn,
        matchSummary,
        statusText,
        annotationLogBody,
        annotationLogHint,
        loader,
        loaderText,
        canvas,
        ctx,
        canvasContainer,
        canvasEmptyState,
        toastContainer,
        preprocessOverlay,
        preprocessOverlayTitle,
        preprocessOverlayDetail,
        oneClickModeBadge,
        classManager,
        classManagerFeedback,
        addClassBtn,
        quickClassInput,
        quickAddClassBtn,
        classificationSelect,
        applyClassificationBtn,
        oneClickAcceptInput,
        selectionSummary,
        nextActionText,
        selectedAnnotationSummary,
        bboxXInput,
        bboxYInput,
        bboxWInput,
        bboxHInput,
        applyBoxEditBtn,
        logContextMenu,
        logDeleteBtn,
        logCancelBtn,
        zoomInBtn,
        zoomOutBtn,
        resetViewBtn,
        zoomLevelDisplay,
        helpBtn,
        helpModal,
        closeHelpBtn
    } = domRefs.getDomRefs(document);

    // --- APPLICATION STATE ---
    const appState = stateStore.createAppState();
    let annotationSavePending = false;
    let annotationDirectoryChangePending = false;
    let classSaveTimer = null;
    let classChangesPending = false;
    let classSaveQueue = Promise.resolve();
    let samSettingsReturnFocus = null;
    let preprocessSettingsReturnFocus = null;
    let helpReturnFocus = null;

    const projectDialog = document.getElementById('projectDialog');
    const projectStatus = document.getElementById('projectDialogStatus');
    const projectSelect = document.getElementById('savedProjectSelect');
    let projectSwitchPending = false;
    async function projectRequest(payload) {
        const response = await window.SAM2ApiClient.apiFetch('api/project/projects', payload ? {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
        } : {});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Could not access projects');
        return data;
    }
    document.getElementById('manageProjectsBtn').addEventListener('click', async () => {
        projectStatus.textContent = 'Loading projects…';
        projectDialog.showModal();
        document.getElementById('reuseProjectClasses').checked = false;
        try {
            const data = await projectRequest();
            projectSelect.replaceChildren();
            data.projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project.project_id;
                option.textContent = `${project.name} (${project.class_count} classes) · ${project.project_id.slice(0, 8)}`;
                option.selected = project.project_id === data.active_project_id;
                projectSelect.appendChild(option);
            });
            projectStatus.textContent = '';
        } catch (error) { projectStatus.textContent = error.message; }
    });
    document.getElementById('closeProjectDialogBtn').addEventListener('click', () => {
        if (!projectSwitchPending) projectDialog.close();
    });
    projectDialog.addEventListener('cancel', event => { if (projectSwitchPending) event.preventDefault(); });
    async function switchProject(payload) {
        if (projectSwitchPending) return;
        if (annotationSavePending || annotationDirectoryChangePending) {
            projectStatus.textContent = 'Wait for the current save or folder change to finish.';
            return;
        }
        if (!confirmDiscardUnsavedChanges('Switching projects clears the image queue.')) return;
        projectSwitchPending = true;
        projectStatus.textContent = 'Saving classes and opening project…';
        try {
            if (classSaveTimer) { clearTimeout(classSaveTimer); classSaveTimer = null; }
            if (!await saveProjectClasses()) throw new Error('Classes could not be saved; project switch cancelled.');
            await projectRequest(payload);
            window.removeEventListener('beforeunload', handleBeforeUnload);
            window.location.reload();
        } catch (error) {
            projectStatus.textContent = error.message;
            projectSwitchPending = false;
        }
    }
    document.getElementById('createProjectBtn').addEventListener('click', () => {
        const name = document.getElementById('newProjectName').value.trim();
        if (!name) { projectStatus.textContent = 'Enter a project name.'; return; }
        switchProject({ action: 'new', name, reuse_classes: document.getElementById('reuseProjectClasses').checked });
    });
    document.getElementById('openProjectBtn').addEventListener('click', () => {
        if (projectSelect.value) switchProject({ action: 'open', project_id: projectSelect.value });
    });

    const overlayVisibility = { candidates: true, annotations: true, labels: true, imageOnly: false };
    const visibilityInputs = {
        candidates: document.getElementById('showCandidatesInput'),
        annotations: document.getElementById('showAnnotationsInput'),
        labels: document.getElementById('showLabelsInput'),
        imageOnly: document.getElementById('imageOnlyInput')
    };
    Object.entries(visibilityInputs).forEach(([key, input]) => {
        input.addEventListener('change', () => {
            overlayVisibility[key] = input.checked;
            if (overlayVisibility.imageOnly || !overlayVisibility.candidates) appState.selectedCandidateIds.clear();
            if (overlayVisibility.imageOnly || !overlayVisibility.annotations) appState.selectedAnnotationIds.clear();
            if (overlayVisibility.imageOnly && appState.isManualMode) toggleManualMode();
            updateAnnotationLog();
            draw();
        });
    });

    const imageQueueSearch = document.getElementById('imageQueueSearch');
    const classListSearch = document.getElementById('classListSearch');
    imageQueueSearch.addEventListener('input', renderImageBrowser);
    classListSearch.addEventListener('input', filterClassList);
    function filterClassList() {
        const query = classListSearch.value.trim().toLocaleLowerCase();
        const rows = Array.from(classManager.querySelectorAll('.class-row'));
        rows.forEach(row => {
            row.hidden = !row.querySelector('.class-select-btn').dataset.className.toLocaleLowerCase().includes(query);
        });
        document.getElementById('classSearchEmpty').hidden = !query || rows.some(row => !row.hidden);
    }

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
    samDeviceSelect.addEventListener('change', handleSamDeviceChange);
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
    classificationSelect.addEventListener('change', () => {
        updateButtonStates();
        draw();
    });
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
    undoBtn.addEventListener('click', handleUndoAction);
    redoBtn.addEventListener('click', handleRedoAction);
    exportAnnotationFileBtn.addEventListener('click', handleExportAnnotationFile);
    validateProjectDatasetBtn.addEventListener('click', handleValidateProjectDataset);
    exportProjectDatasetBtn.addEventListener('click', handleExportProjectDataset);
    loadAnnotationFileBtn.addEventListener('click', () => {
        if (appState.currentImage) loadAnnotationFileInput.click();
    });
    loadAnnotationFileInput.addEventListener('change', handleLoadAnnotationFile);
    loadServerAnnotationsBtn.addEventListener('click', handleLoadServerAnnotations);
    saveServerBtn.addEventListener('click', handleSaveServerAnnotations);
    saveAllServerBtn.addEventListener('click', handleSaveAllServerAnnotations);
    reviewAndNextBtn.addEventListener('click', () => handleReviewImage('reviewed'));
    confirmEmptyBtn.addEventListener('click', () => handleReviewImage('confirmed_empty'));
    reopenReviewBtn.addEventListener('click', () => handleReviewImage('in_progress', false));
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
    imageQueueFilters.addEventListener('click', handleImageQueueFilterClick);
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
    logCancelBtn.addEventListener('click', () => annotationLogController.hideContextMenu(annotationLogRefs()));
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
            annotationLogController.hideContextMenu(annotationLogRefs());
        }
    });
    window.addEventListener('resize', () => {
        if (resizeCanvasToContainer()) {
            draw();
        }
    });
    window.addEventListener('workspace-panels-changed', () => {
        resizeCanvasToContainer();
        fitImageToView();
        draw();
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
        const isCurrent = stateStore.beginOperation(appState, 'open-project');
        renderImageBrowser();
        await refreshAnnotationMatches({ showFeedback: false });
        if (!isCurrent()) return;
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
        const isCurrent = stateStore.beginOperation(appState, 'open-project');
        renderImageBrowser();
        await refreshAnnotationMatches({ showFeedback: false });

        if (!isCurrent()) return;
        await selectImageByIndex(0, { autoLoadAnnotations: true });

        const msg = `Opened folder with ${files.length} images.`;
        updateStatus(msg);
        showToast(msg, 'success');
    }

    async function loadImageRecord(imageRecord) {
        if (!imageRecord) return false;
        if (imageRecord.originalImage) return true;

        const isCurrent = stateStore.beginOperation(appState, 'decode', { imageRecord });
        const stopLoading = setLoader(true, `Loading '${publicImageName(imageRecord)}'...`);

        try {
            const response = await apiWorkflows.loadImage(imageRecord.file);
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.error || `Server error: ${response.status} ${response.statusText}`);
            }
            if (data.error) throw new Error(data.error);

            const image = await loadImageElement(data.image_url);
            if (!isCurrent()) return false;
            imageRecord.originalImage = image;
            imageRecord.width = Number(data.width) || imageRecord.originalImage.width;
            imageRecord.height = Number(data.height) || imageRecord.originalImage.height;
            return true;
        } catch (error) {
            if (!isCurrent()) return false;
            console.error('Image Load Error:', error);
            const errorMsg = `Error loading image: ${error.message}`;
            updateStatus(errorMsg);
            showToast(errorMsg, 'error');
            return false;
        } finally {
            stopLoading();
        }
    }

    function loadImageElement(src) {
        return imageController.loadImageElement(src);
    }

    async function selectImageByOffset(offset) {
        const index = currentImageIndex();
        if (index === -1) return;
        await selectImageByIndex(index + offset, { autoLoadAnnotations: true });
    }

    async function selectImageByIndex(index, { autoLoadAnnotations = true } = {}) {
        if (index < 0 || index >= appState.images.length) return;

        const imageRecord = appState.images[index];
        const isCurrent = stateStore.beginOperation(appState, 'navigate');
        const loaded = await loadImageRecord(imageRecord);
        if (!loaded || !isCurrent()) return;

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

        if (!isCurrent()) return;
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

    function handleImageQueueFilterClick(event) {
        const filterButton = event.target.closest('[data-filter]');
        if (!filterButton) return;

        const nextFilter = imageController.normalizeQueueFilter(filterButton.dataset.filter);
        if (appState.imageQueueFilter === nextFilter) return;

        appState.imageQueueFilter = nextFilter;
        renderImageBrowser();
    }

    function renderImageBrowser() {
        stateStore.invalidateReviewsForClassChanges(appState);
        const focusedIndex = document.activeElement?.closest('.image-list-item')?.dataset.imageIndex;
        imageList.innerHTML = '';

        if (appState.images.length === 0) {
            updateImageQueueProgress({ total: 0, annotated: 0, unsaved: 0, candidates: 0 });
            renderImageQueueFilters();
            const empty = document.createElement('div');
            empty.className = 'image-list-empty';
            empty.textContent = 'No folder loaded.';
            imageList.appendChild(empty);
            updateCurrentImageDisplay();
            return;
        }

        const currentIndex = currentImageIndex();
        const queueItems = appState.images.map((imageRecord, index) => ({
            imageRecord,
            index,
            queueState: getImageQueueState(imageRecord)
        }));
        updateImageQueueProgress(imageController.imageQueueProgressSummary(queueItems.map(item => item.queueState)));
        renderImageQueueFilters();

        const activeFilter = imageController.normalizeQueueFilter(appState.imageQueueFilter);
        const visibleQueueItems = queueItems.filter(item => (
            imageController.imageMatchesQueueFilter(item.queueState, activeFilter)
            && publicImageName(item.imageRecord).toLocaleLowerCase().includes(imageQueueSearch.value.trim().toLocaleLowerCase())
        ));

        if (visibleQueueItems.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'image-list-empty';
            empty.textContent = 'No images match this filter.';
            imageList.appendChild(empty);
            updateCurrentImageDisplay();
            return;
        }

        visibleQueueItems.forEach(({ imageRecord, index }) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'image-list-item';
            item.dataset.imageIndex = String(index);
            if (index === currentIndex) item.classList.add('active');
            if (appState.dirtyImages.has(imageRecord.id)) item.classList.add('dirty-image');
            item.setAttribute('aria-current', String(index === currentIndex));
            item.title = publicImagePath(imageRecord);

            const name = document.createElement('span');
            name.className = 'image-list-name';
            name.textContent = publicImageName(imageRecord);

            const badges = document.createElement('span');
            badges.className = 'image-list-badges';
            getImageBadges(imageRecord).forEach(badgeInfo => {
                if (!['unreviewed', 'in_progress', 'reviewed', 'confirmed_empty', 'dirty'].includes(badgeInfo.type)) {
                    item.title += `
${badgeInfo.title}`;
                    return;
                }
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
        if (focusedIndex !== undefined) {
            imageList.querySelector(`[data-image-index="${Number(focusedIndex)}"]`)?.focus({ preventScroll: true });
        }
        updateCurrentImageDisplay();
    }

    function updateImageQueueProgress(summary) {
        imageQueueProgress.textContent = `${summary.reviewed || 0} of ${summary.total} reviewed`;
        imageQueueProgress.title = `${summary.confirmedEmpty || 0} confirmed empty · ${summary.unsaved || 0} unsaved`;
    }

    function renderImageQueueFilters() {
        const activeFilter = imageController.normalizeQueueFilter(appState.imageQueueFilter);
        appState.imageQueueFilter = activeFilter;
        imageQueueFilters.querySelectorAll('[data-filter]').forEach(button => {
            button.classList.toggle('active', button.dataset.filter === activeFilter);
        });
    }

    function getImageQueueState(imageRecord) {
        return imageController.imageQueueState({
            annotations: appState.annotationsByImage.get(imageRecord.id) || [],
            candidates: appState.candidateAnnotationsByImage.get(imageRecord.id) || [],
            reviewStatus: imageRecord.reviewStatus,
            isDirty: appState.dirtyImages.has(imageRecord.id),
            match: appState.annotationMatchesByImage.get(imageRecord.id)
        });
    }

    function getImageBadges(imageRecord) {
        return imageController.getImageBadges(imageRecord, {
            annotations: appState.annotationsByImage.get(imageRecord.id) || [],
            candidates: appState.candidateAnnotationsByImage.get(imageRecord.id) || [],
            reviewStatus: imageRecord.reviewStatus,
            isDirty: appState.dirtyImages.has(imageRecord.id),
            match: appState.annotationMatchesByImage.get(imageRecord.id),
            currentAnnotationFormat,
            formatLabel,
            hasActivePreprocess,
            preprocessBadgeLabel,
            preprocessLabel,
            publicAnnotationPath
        });
    }

    function imageStateSummary(imageRecord) {
        return imageController.imageStateSummary(imageRecord, {
            annotations: appState.annotationsByImage.get(imageRecord.id) || [],
            candidates: appState.candidateAnnotationsByImage.get(imageRecord.id) || [],
            reviewStatus: imageRecord.reviewStatus,
            isDirty: appState.dirtyImages.has(imageRecord.id),
            match: appState.annotationMatchesByImage.get(imageRecord.id),
            currentAnnotationFormat,
            formatLabel,
            hasActivePreprocess,
            preprocessLabel
        });
    }

    function selectedPreprocessMethod() {
        return settingsController.selectedPreprocessMethod(preprocessMethodSelect);
    }

    function currentPreprocessParams() {
        return settingsController.currentPreprocessParams(appState.projectSettings);
    }

    function samPreprocessPayload(imageRecord = appState.currentImage) {
        return settingsController.samPreprocessPayload(imageRecord, currentPreprocessParams());
    }

    function readPreprocessSettingsFromInputs() {
        return settingsController.readPreprocessSettingsFromInputs({
            preprocessClaheClipInput,
            preprocessClaheTileInput,
            preprocessGammaInput,
            preprocessUnsharpAmountInput,
            preprocessUnsharpRadiusInput,
            preprocessUnsharpThresholdInput,
            preprocessRetinexStrengthInput
        });
    }

    function syncPreprocessSettingsInputs(params = currentPreprocessParams()) {
        settingsController.syncPreprocessSettingsInputs(
            {
                preprocessGammaInput,
                preprocessClaheClipInput,
                preprocessClaheTileInput,
                preprocessUnsharpAmountInput,
                preprocessUnsharpRadiusInput,
                preprocessUnsharpThresholdInput,
                preprocessRetinexStrengthInput
            },
            params
        );
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
        appState.projectSettings.preprocessParams = settingsController.defaultPreprocessParams();
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

        const isCurrent = stateStore.beginOperation(appState, 'preprocess', { imageRecord });
        const methodLabel = preprocessLabel(method);
        const stopLoading = setLoader(true, `Applying ${methodLabel} on server...`);

        try {
            const response = await apiWorkflows.preprocessImage({
                file: imageRecord.file,
                method,
                params: currentPreprocessParams()
            });
            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            const processedImg = await loadImageElement(data.image);
            if (!isCurrent()) return;
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
        } catch (error) {
            if (!isCurrent()) return;
            console.error('Preprocessing Error:', error);
            const errorMsg = `Failed to apply ${methodLabel}.`;
            updateStatus(errorMsg);
            showToast(errorMsg, 'error');
        } finally {
            stopLoading();
        }
    }

    function handleRestoreOriginal() {
        const imageRecord = appState.currentImage;
        if (!imageRecord || !hasActivePreprocess(imageRecord)) return;

        stateStore.beginOperation(appState, 'preprocess', { imageRecord });
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

    function beginAnnotationOperation(key, imageRecord = null, trackAnnotations = true) {
        const source = appState.annotationSource;
        const directory = appState.projectSettings.annotationOutputDir;
        const format = currentAnnotationFormat();
        const classes = JSON.stringify(appState.classes);
        const isCurrent = stateStore.beginOperation(appState, key, {
            imageRecord,
            trackAnnotations: Boolean(imageRecord && trackAnnotations)
        });
        return () => isCurrent()
            && !annotationDirectoryChangePending
            && appState.annotationSource === source
            && appState.projectSettings.annotationOutputDir === directory
            && currentAnnotationFormat() === format
            && JSON.stringify(appState.classes) === classes;
    }

    async function handleRunSam() {
        const imageRecord = appState.currentImage;
        if (!imageRecord) return;

        const existingCandidateCount = currentCandidates().length;
        const existingAnnotationCount = currentAnnotations().length;
        const keepExistingAnnotations = keepAnnotationsInput.checked;

        if (
            existingCandidateCount > 0
            && !window.confirm(`Re-generate SAM2 candidates and replace ${existingCandidateCount} current candidates? Existing annotations will be ${keepExistingAnnotations ? 'kept' : 'cleared'}.`)
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

        const isCurrent = beginAnnotationOperation('annotations', imageRecord);
        const samSettings = currentSamSettingsPayload();
        const settingsSnapshot = JSON.stringify(samSettings);
        const stopLoading = setLoader(true, 'Running SAM2 & filtering on server...');

        try {
            const samPreprocess = samPreprocessPayload(imageRecord);
            const response = await apiWorkflows.runSam({
                file: imageRecord.file,
                imageName: imageRecord.name,
                samSettings,
                preprocessMethod: samPreprocess.method,
                preprocessParams: samPreprocess.params
            });
            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            if (!isCurrent()) return;
            if (data.error) throw new Error(data.error);
            if (data.sam_settings && JSON.stringify(currentSamSettingsPayload()) === settingsSnapshot) {
                applySamSettings(data.sam_settings);
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

            appState.candidateAnnotationsByImage.set(imageRecord.id, candidateAnnotations);
            appState.annotationRedoByImage.set(imageRecord.id, []);
            if (appState.currentImage === imageRecord) appState.selectedCandidateIds.clear();
            if (!keepExistingAnnotations) {
                appState.annotationsByImage.set(imageRecord.id, []);
                appState.annotationHistoryByImage.set(imageRecord.id, []);
                if (appState.currentImage === imageRecord) appState.selectedAnnotationIds.clear();
                if (existingAnnotationCount > 0) appState.dirtyImages.add(imageRecord.id);
            }
            imageRecord.samHasRun = true;
            stateStore.markImageDirty(appState, imageRecord);

            const actionText = existingCandidateCount > 0 ? 'Replaced candidates' : 'Found candidate masks';
            const annotationText = keepExistingAnnotations
                ? `Kept ${existingAnnotationCount} existing annotations.`
                : `Cleared ${existingAnnotationCount} existing annotations.`;
            const successMsg = `${actionText}: ${candidateAnnotations.length} with ${currentSamPresetLabel()}. ${annotationText}`;
            if (appState.currentImage === imageRecord) updateStatus(successMsg);
            showToast(successMsg, 'success');
            renderImageBrowser();
            updateAnnotationLog();
            draw();
        } catch (error) {
            if (!isCurrent()) return;
            console.error('SAM Error:', error);
            const errorMsg = `Failed to run SAM: ${error.message}`;
            updateStatus(errorMsg);
            showToast(errorMsg, 'error');
        } finally {
            stopLoading();
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
        setCurrentRedoHistory([]);
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
        if (!classExists(appState.classes, className)) {
            const msg = appState.classes.length === 0
                ? 'Create a class before applying annotations.'
                : 'Please choose a valid class before applying annotations.';
            updateStatus(msg);
            showToast(msg, 'error');
            quickClassInput.focus();
            return;
        }

        const historyStart = currentHistory().length;
        const relabeledCount = relabelSelectedAnnotations(className);
        const convertedCount = convertSelectedCandidates(className);
        const totalCount = relabeledCount + convertedCount;

        if (totalCount === 0) return;

        annotationController.groupHistoryCommands(currentHistory(), historyStart, 'class application');

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
        const result = annotationController.convertSelectedCandidates(
            appState,
            currentCandidates(),
            currentAnnotations(),
            currentHistory(),
            currentRedoHistory(),
            className,
            clampBboxToImage
        );
        setCurrentCandidates(result.remainingCandidates);
        return result.count;
    }

    function annotationFromCandidate(candidate, className) {
        return annotationController.annotationFromCandidate(appState, candidate, className, clampBboxToImage);
    }

    function acceptSingleCandidate(candidate, className) {
        if (!classExists(appState.classes, className)) {
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
        const annotationIndex = currentAnnotations().length;
        const candidateIndex = currentCandidates().findIndex(item => item.id === candidate.id);
        currentAnnotations().push(newAnnotation);
        setCurrentCandidates(currentCandidates().filter(item => item.id !== candidate.id));
        appState.selectedCandidateIds.delete(candidate.id);
        appState.selectedAnnotationIds.clear();
        annotationController.recordHistoryCommand(currentHistory(), currentRedoHistory(), {
            type: 'convert_candidates',
            annotationRecords: [{ item: newAnnotation, index: annotationIndex }],
            candidateRecords: [{ item: candidate, index: candidateIndex }]
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
        return annotationController.relabelSelectedAnnotations(
            currentAnnotations(),
            appState.selectedAnnotationIds,
            currentHistory(),
            currentRedoHistory(),
            className
        );
    }

    function handleUndoAction() {
        const classNamesBefore = appState.classes.map(classInfo => classInfo.name).join('\u0000');
        const msg = annotationController.undoLastAction(
            currentAnnotations(),
            currentCandidates(),
            currentHistory(),
            currentRedoHistory(),
            appState.classes
        );
        if (!msg) return;

        if (classNamesBefore !== appState.classes.map(classInfo => classInfo.name).join('\u0000')) {
            scheduleProjectClassesSave();
            renderClassControls(classificationSelect.value);
        }

        appState.selectedAnnotationIds.clear();
        appState.selectedCandidateIds.clear();

        updateAnnotationLog();
        markCurrentImageDirty();
        renderImageBrowser();
        updateAnnotationInspector();
        updateStatus(msg);
        showToast(msg, 'info');
        draw();
        updateButtonStates();
    }

    function handleRedoAction() {
        const classNamesBefore = appState.classes.map(classInfo => classInfo.name).join('\u0000');
        const msg = annotationController.redoLastAction(
            currentAnnotations(),
            currentCandidates(),
            currentHistory(),
            currentRedoHistory(),
            appState.classes
        );
        if (!msg) return;

        if (classNamesBefore !== appState.classes.map(classInfo => classInfo.name).join('\u0000')) {
            scheduleProjectClassesSave();
            renderClassControls(classificationSelect.value);
        }

        appState.selectedAnnotationIds.clear();
        appState.selectedCandidateIds.clear();
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
        quickClassInput.closest('.quick-class-row').hidden = false;
        quickClassInput.focus();
        quickClassInput.scrollIntoView({ block: 'nearest' });
        updateStatus('Enter a meaningful class name, then choose Create class.');
    }

    function handleQuickAddClass() {
        const created = createClassFromName(quickClassInput.value, { select: true });
        if (created) quickClassInput.closest('.quick-class-row').hidden = true;
        return created;
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

        const newClass = classManagerLogic.buildNewClass(className, appState.classes, appState.nextClassId);

        appState.classes.push(newClass);
        appState.nextClassId = Math.max(appState.nextClassId, newClass.id + 1);
        scheduleProjectClassesSave();
        classListSearch.value = '';
        renderClassControls(select ? newClass.name : classificationSelect.value);
        classManager.scrollTop = classManager.scrollHeight;
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
            const index = classUiController.getClassRowIndex(event.target);
            if (index === null) return;
            appState.classes[index].color = event.target.value;
            scheduleProjectClassesSave();
            draw();
        }
    }

    function handleClassManagerChange(event) {
        const index = classUiController.getClassRowIndex(event.target);
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
        const selectButton = event.target.closest('.class-select-btn');
        if (selectButton) {
            classificationSelect.value = selectButton.dataset.className;
            classificationSelect.dispatchEvent(new Event('change'));
            updateButtonStates();
            draw();
            return;
        }
        const deleteButton = event.target.closest('.class-delete-btn');
        if (!deleteButton) return;

        const index = classUiController.getClassRowIndex(deleteButton);
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
            const msg = `Class "${newName}" already exists. Select annotations and use Apply class to selection to reassign them.`;
            updateStatus(msg);
            showToast(msg, 'info');
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
        if (changedCount > 0) clearAllAnnotationHistory();
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
        if (classManagerLogic.isReservedHotkey(hotkey)) {
            const msg = `${hotkey.toUpperCase()} is reserved for ${hotkey === 'b' ? 'Manual Box' : 'Undo'}. Choose another shortcut or clear the field.`;
            showClassManagerFeedback(msg);
            showToast(msg, 'info');
            renderClassControls(classificationSelect.value);
            return;
        }

        if (hotkey && appState.classes.some((cls, clsIndex) => clsIndex !== index && cls.hotkey === hotkey)) {
            const msg = `Hotkey ${hotkey.toUpperCase()} is already assigned.`;
            showClassManagerFeedback(msg);
            showToast(msg, 'error');
            renderClassControls(classificationSelect.value);
            return;
        }

        clearClassManagerFeedback();
        classInfo.hotkey = hotkey;
        scheduleProjectClassesSave();
        renderClassControls(classificationSelect.value);
    }

    function deleteClass(index) {
        const classToDelete = appState.classes[index];
        if (!classToDelete) return;
        const affectedCount = countAnnotationsWithClass(classToDelete.name);
        if (affectedCount > 0) {
            const msg = `"${classToDelete.name}" is used by ${affectedCount} loaded annotations. Reassign them before removing the class.`;
            showClassManagerFeedback(msg);
            showToast(msg, 'info');
            return;
        }
        if (!window.confirm(`Remove "${classToDelete.name}" from the project class list? Saved annotation files are unchanged. Loading a file that uses this class will restore it.`)) return;
        appState.classes.splice(index, 1);
        clearAllAnnotationHistory();
        clearClassManagerFeedback();
        scheduleProjectClassesSave();
        renderClassControls(classificationSelect.value);
        draw();
        updateButtonStates();
        const msg = `Removed class "${classToDelete.name}". Annotations were preserved.`;
        updateStatus(msg);
        showToast(msg, 'info');
    }

    // --- CANVAS INTERACTION ---
    function toggleManualMode() {
        if (!appState.isManualMode) {
            overlayVisibility.imageOnly = false;
            overlayVisibility.annotations = true;
        }
        const nextManualMode = canvasInteractionController.toggleManualMode(appState);
        manualAnnotationBtn.classList.toggle('active', nextManualMode.enabled);
        canvas.style.cursor = nextManualMode.cursor;
        updateStatus(nextManualMode.status);
        updateButtonStates();
        draw();
    }

    function handleMouseDown(event) {
        if (event.button !== 0) return;

        annotationLogController.hideContextMenu(annotationLogRefs());

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
            canvasInteractionController.beginManualDrawing(appState, getScreenPoint(event.clientX, event.clientY));
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

        canvasInteractionController.beginPanning(appState, { x: event.clientX, y: event.clientY });
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
            canvasInteractionController.updatePanning(appState, { x: event.clientX, y: event.clientY });
            draw();
            return;
        }

        if (appState.isDrawing) {
            canvasInteractionController.updateManualBox(appState, getScreenPoint(event.clientX, event.clientY));
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
            canvas.style.cursor = canvasInteractionController.finishPanning(appState);
            return;
        }

        if (appState.isDrawing && appState.isManualMode && appState.currentManualBox) {
            if (canvasInteractionController.finishManualDrawing(appState)) {
                setupChoiceButtons();
            }
            draw();
        }
    }

    function startBoxEdit(mode, worldPoint, annotationIds, handle = null) {
        canvasInteractionController.startBoxEdit(appState, mode, worldPoint, annotationIds, findAnnotationById, handle);
    }

    function updateBoxEdit(worldPoint) {
        canvasInteractionController.updateBoxEdit(appState, worldPoint, findAnnotationById, {
            clampMovedBboxToImage,
            clampBboxToImage,
            resizeBbox
        });
    }

    function commitBoxEdit() {
        const changes = canvasInteractionController.commitBoxEdit(appState, findAnnotationById, bboxesEqual);

        if (changes.length > 0) {
            annotationController.invalidateMaskGeometryForChanges(currentAnnotations(), changes);
            annotationController.recordHistoryCommand(
                currentHistory(),
                currentRedoHistory(),
                { type: 'geometry_edit', changes }
            );
            markCurrentImageDirty();
            renderImageBrowser();
            updateAnnotationLog();
            updateAnnotationInspector();
            updateStatus(`Updated ${changes.length} annotation boxes.`);
            updateButtonStates();
        }
    }

    function cancelBoxEdit() {
        canvas.style.cursor = canvasInteractionController.cancelBoxEdit(appState, findAnnotationById);
        updateAnnotationInspector();
        draw();
    }

    function arrowKeyDelta(key) {
        return canvasGeometry.arrowKeyDelta(key);
    }

    function nudgeSelectedAnnotations(dx, dy) {
        const changes = canvasInteractionController.nudgeSelectedAnnotations(
            currentAnnotations(),
            appState.selectedAnnotationIds,
            dx,
            dy,
            {
                clampMovedBboxToImage,
                bboxesEqual
            }
        );

        if (changes.length === 0) return;

        annotationController.invalidateMaskGeometryForChanges(currentAnnotations(), changes);
        annotationController.recordHistoryCommand(
            currentHistory(),
            currentRedoHistory(),
            { type: 'geometry_edit', changes }
        );
        markCurrentImageDirty();
        renderImageBrowser();
        updateAnnotationLog();
        updateAnnotationInspector();
        draw();
        updateStatus(`Moved ${changes.length} selected box${changes.length === 1 ? '' : 'es'} by ${dx}, ${dy}.`);
        updateButtonStates();
    }

    function resizeBbox(bbox, handle, dx, dy) {
        return canvasGeometry.resizeBbox(bbox, handle, dx, dy);
    }

    function normalizeBboxFromPoints(x1, y1, x2, y2) {
        return canvasGeometry.normalizeBboxFromPoints(x1, y1, x2, y2);
    }

    function normalizeRawBbox(bbox) {
        return canvasGeometry.normalizeRawBbox(bbox);
    }

    function clampBboxToImage(bbox, imageRecord = appState.currentImage) {
        return canvasGeometry.clampBboxToImage(bbox, imageDimensions(imageRecord));
    }

    function clampMovedBboxToImage(bbox, imageRecord = appState.currentImage) {
        return canvasGeometry.clampMovedBboxToImage(bbox, imageDimensions(imageRecord));
    }

    function clampNumber(value, min, max) {
        return canvasGeometry.clampNumber(value, min, max);
    }


    function getSelectedResizeHandleAtPoint(worldPoint) {
        if (overlayVisibility.imageOnly || !overlayVisibility.annotations) return null;
        for (let i = currentAnnotations().length - 1; i >= 0; i--) {
            const annotation = currentAnnotations()[i];
            if (!appState.selectedAnnotationIds.has(annotation.id)) continue;

            const handle = getResizeHandleAtPoint(annotation, worldPoint);
            if (handle) return { annotation, handle };
        }
        return null;
    }

    function getResizeHandleAtPoint(annotation, worldPoint) {
        return canvasGeometry.getResizeHandleAtPoint(annotation, worldPoint, appState.cameraZoom);
    }

    function annotationHandles(annotation) {
        return canvasGeometry.annotationHandles(annotation);
    }

    function findAnnotationAtPoint(worldPoint, predicate = null) {
        if (overlayVisibility.imageOnly || !overlayVisibility.annotations) return null;
        for (let i = currentAnnotations().length - 1; i >= 0; i--) {
            const annotation = currentAnnotations()[i];
            if (predicate && !predicate(annotation)) continue;
            if (pointInsideBbox(worldPoint, annotation.bbox)) return annotation;
        }
        return null;
    }

    function findCandidateAtPoint(worldPoint) {
        if (overlayVisibility.imageOnly || !overlayVisibility.candidates) return null;
        for (let i = currentCandidates().length - 1; i >= 0; i--) {
            const candidate = currentCandidates()[i];
            if (pointInsideCandidate(worldPoint, candidate)) return candidate;
        }
        return null;
    }

    function pointInsideCandidate(point, candidate) {
        return canvasGeometry.pointInsideCandidate(point, candidate, normalizeContour);
    }

    function pointInsideBbox(point, bbox) {
        return canvasGeometry.pointInsideBbox(point, bbox);
    }

    function pointInsidePolygon(point, polygon) {
        return canvasGeometry.pointInsidePolygon(point, polygon);
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
        return canvasGeometry.cursorForHandle(handle);
    }

    function bboxesEqual(a, b) {
        return canvasGeometry.bboxesEqual(a, b);
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
        canvasInteractionController.zoomState(
            appState,
            newZoom,
            mousePos,
            canvasGeometry.zoomState
        );
        draw();
    }

    function zoomIn() {
        setZoom(appState.cameraZoom * ZOOM_STEP);
    }

    function zoomOut() {
        setZoom(appState.cameraZoom / ZOOM_STEP);
    }

    function setupChoiceButtons() {
        canvasInteractionController.setupChoiceButtons(
            appState,
            { width: canvas.width, height: canvas.height },
            appState.classes,
            NEW_CLASS_ACTION
        );
        // The refined UI uses native controls rather than canvas-drawn buttons.
        appState.choiceInfo.buttons = [];
    }

    function promptCreateClassForManualAnnotation() {
        const rawName = window.prompt('Class name');
        if (rawName === null) return;

        const className = createClassFromName(rawName, { select: true });
        if (className) {
            finalizeAnnotation(className);
        }
    }

    function finalizeAnnotation(className) {
        if (!appState.choiceInfo) return;
        if (!classExists(appState.classes, className)) {
            const msg = 'Please choose a valid class before creating an annotation.';
            updateStatus(msg);
            showToast(msg, 'error');
            appState.isAwaitingChoice = false;
            appState.choiceInfo = null;
            draw();
            return;
        }

        try {
            const { annotation: newAnnotation, error } = canvasInteractionController.buildManualAnnotation(
                appState,
                className,
                getWorldPoint,
                clampBboxToImage
            );
            if (error) throw new Error(error);
            if (!newAnnotation) return;

            const annotationIndex = currentAnnotations().length;
            currentAnnotations().push(newAnnotation);
            annotationController.recordHistoryCommand(currentHistory(), currentRedoHistory(), {
                type: 'create_annotations',
                annotationRecords: [{ item: newAnnotation, index: annotationIndex }]
            });
            markCurrentImageDirty();

            updateAnnotationLog();
            renderImageBrowser();
        } catch (error) {
            console.error('Failed to finalize manual annotation:', error);
            const errorMsg = 'Error: Could not create manual annotation.';
            updateStatus(errorMsg);
            showToast(errorMsg, 'error');
        } finally {
            canvasInteractionController.closeManualChoice(appState);
            draw();
            updateButtonStates();
        }
    }

    function cancelManualAnnotation() {
        canvasInteractionController.closeManualChoice(appState);
        updateStatus('Manual box cancelled.');
        draw();
    }

    // --- ANNOTATION LOG AND ACTIONS ---
    function handleLogClick(event) {
        if (!annotationLogController.applyLogSelection(appState, event)) return;

        updateAnnotationLog();
        draw();
        updateButtonStates();
    }

    function handleLogRightClick(event) {
        annotationLogController.openContextMenu(annotationLogRefs(), appState, event);
    }

    function deleteAnnotationById(idToDelete) {
        annotationLogController.hideContextMenu(annotationLogRefs());
        const deletedAnnotations = annotationController.deleteAnnotationsByIds(
            currentAnnotations(),
            currentCandidates(),
            currentHistory(),
            currentRedoHistory(),
            appState.selectedAnnotationIds,
            [idToDelete]
        );
        if (deletedAnnotations.length === 0) return;

        appState.logItemToModify = null;
        markCurrentImageDirty();

        const msg = `Deleted annotation #${deletedAnnotations[0].id}.`;
        updateStatus(msg);
        showToast(msg, 'info');
        updateAnnotationLog();
        renderImageBrowser();
        draw();
        updateButtonStates();
    }

    function handleKeyDown(event) {
        // Native dialog handles focus, text editing, and Escape. Workspace
        // shortcuts must not reach the annotations behind it.
        if (projectDialog.open) return;
        const modal = modalKeyboardController.visibleModal([samSettingsModal, preprocessSettingsModal, helpModal]);
        if (event.key === 'Escape') {
            event.preventDefault();
            if (modal) {
                modalKeyboardController.closeVisibleModal(modal, [
                    { modal: samSettingsModal, close: closeSamSettingsModal },
                    { modal: preprocessSettingsModal, close: closePreprocessSettingsModal },
                    { modal: helpModal, close: closeHelpModal }
                ]);
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
            modalKeyboardController.trapModalFocus(event, modal, document);
            return;
        }

        const tagName = document.activeElement ? document.activeElement.tagName : '';
        if (['INPUT', 'SELECT', 'TEXTAREA'].includes(tagName)) return;

        const plainKey = !event.ctrlKey && !event.metaKey && !event.altKey;
        const classMatch = plainKey && !classManagerLogic.isReservedHotkey(event.key)
            && appState.classes.find(cls => cls.hotkey === event.key.toLowerCase());
        if (appState.isAwaitingChoice && appState.choiceInfo && classMatch) {
            event.preventDefault();
            finalizeAnnotation(classMatch.name);
            return;
        }

        if (plainKey && event.key.toLowerCase() === 'b') {
            event.preventDefault();
            if (appState.currentImage) toggleManualMode();
            return;
        }

        if (event.key === 'Delete') {
            event.preventDefault();
            const selectedIds = Array.from(appState.selectedAnnotationIds);
            const deletedAnnotations = annotationController.deleteAnnotationsByIds(
                currentAnnotations(),
                currentCandidates(),
                currentHistory(),
                currentRedoHistory(),
                appState.selectedAnnotationIds,
                selectedIds
            );
            if (deletedAnnotations.length > 0) {
                markCurrentImageDirty();
                appState.logItemToModify = null;
                updateStatus(`Deleted ${deletedAnnotations.length} selected annotation${deletedAnnotations.length === 1 ? '' : 's'}.`);
                updateAnnotationLog();
                renderImageBrowser();
                draw();
                updateButtonStates();
            }
            return;
        }

        const undoShortcut = (plainKey && event.key.toLowerCase() === 'u')
            || (event.ctrlKey && !event.shiftKey && event.key.toLowerCase() === 'z');
        const redoShortcut = event.ctrlKey
            && (event.key.toLowerCase() === 'y' || (event.shiftKey && event.key.toLowerCase() === 'z'));
        if (redoShortcut) {
            event.preventDefault();
            handleRedoAction();
            return;
        }
        if (undoShortcut) {
            event.preventDefault();
            handleUndoAction();
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

        if (classMatch) {
            event.preventDefault();
            processSelection(classMatch.name);
        }
    }

    async function handleSetAnnotationDir() {
        if (annotationSavePending || annotationDirectoryChangePending) {
            const msg = 'Wait for the current annotation save or folder change to finish.';
            updateStatus(msg);
            showToast(msg, 'info');
            return;
        }
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

        let refreshMatches = false;
        annotationDirectoryChangePending = true;
        const stopLoading = setLoader(true, 'Updating annotation folder...');

        try {
            const response = await apiWorkflows.saveProjectSettings({ annotation_output_dir: annotationOutputDir });
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

            refreshMatches = true;

            const msg = `Annotation folder set to ${data.annotation_dir_display}.`;
            updateStatus(msg);
            showToast(msg, 'success');
        } catch (error) {
            console.error('Project Settings Error:', error);
            const msg = `Failed to update annotation folder: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        } finally {
            annotationDirectoryChangePending = false;
            stopLoading();
            updateButtonStates();
        }
        if (refreshMatches && appState.images.length > 0) {
            await refreshAnnotationMatches({ showFeedback: false });
        }
    }

    function samSettingsModalRefs() {
        return {
            samSettingsModal,
            closeSamSettingsBtn
        };
    }

    function samSettingsRefs() {
        return {
            ...samSettingsModalRefs(),
            samPresetSummary,
            samDeviceSelect,
            samDeviceStatus,
            samReadinessText,
            samPresetSelect,
            samAreaModeSelect,
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
            samUseM2mInput,
            samRiskText
        };
    }

    function openSamSettingsModal() {
        samSettingsReturnFocus = samSettingsUiController.openModal(
            samSettingsModalRefs(),
            renderSamSettingsPanel,
            document
        );
    }

    function closeSamSettingsModal() {
        samSettingsReturnFocus = samSettingsUiController.closeModal(
            samSettingsModalRefs(),
            samSettingsReturnFocus
        );
    }

    function handleSamPresetChange() {
        const nextSettings = settingsController.samSettingsForPresetChange(
            appState,
            samPresetSelect.value,
            readSamSettingsFromInputs
        );
        if (!nextSettings) return;

        appState.projectSettings.samSettings = nextSettings;
        renderSamSettingsPanel();
    }

    function handleSamSettingsInput() {
        const nextSettings = readSamSettingsFromInputs();
        appState.projectSettings.samSettings = settingsController.samSettingsForInputChange(
            appState,
            nextSettings,
            samPresetSelect.value
        );
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

        const stopLoading = setLoader(true, 'Saving SAM settings...');

        try {
            const response = await apiWorkflows.saveProjectSettings({ sam_settings: samSettings });
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
            stopLoading();
        }
    }

    async function handleSamDeviceChange() {
        const samDevice = samDeviceSelect.value || 'auto';
        const stopLoading = setLoader(true, 'Updating SAM2 device...');

        try {
            const response = await apiWorkflows.saveProjectSettings({ sam_device: samDevice });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.error || `Server error: ${response.statusText}`);
            if (data.error) throw new Error(data.error);

            applyProjectSettings(data);
            const device = appState.projectSettings.samDevice;
            const msg = `SAM2 device set to ${samSettingsUiController.samDeviceLabel(device)}.`;
            updateStatus(msg);
            showToast(msg, device.ready || device.modelLoadSkipped ? 'success' : 'info');
        } catch (error) {
            renderSamDevicePanel();
            const msg = `Failed to update SAM2 device: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        } finally {
            stopLoading();
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

    function renderSamSettingsPanel({ keepInputs = false } = {}) {
        samSettingsUiController.renderSettingsPanel(
            samSettingsRefs(),
            appState,
            { keepInputs, currentImage: appState.currentImage }
        );
    }

    function renderSamDevicePanel() {
        samSettingsUiController.renderDevicePanel(samSettingsRefs(), appState.projectSettings.samDevice);
    }

    function readSamSettingsFromInputs() {
        return samSettingsUiController.readSamSettingsFromInputs(samSettingsRefs());
    }

    function currentSamSettingsPayload() {
        return samSettingsUiController.currentSamSettingsPayload(appState, samSettingsRefs());
    }

    function applySamSettings(samSettings) {
        settingsController.normalizeAndStoreSamSettings(appState, samSettings);
        renderSamSettingsPanel();
    }

    function currentSamPresetLabel() {
        return settingsController.currentSamPresetLabel(appState);
    }

    function findSamPreset(key) {
        return settingsController.findSamPreset(appState.samPresets, key);
    }

    async function refreshAnnotationMatches({ showFeedback = false } = {}) {
        if (appState.annotationSource.mode === 'local') {
            await refreshLocalAnnotationMatches({ showFeedback });
            return;
        }

        if (appState.images.length === 0) {
            clearAnnotationMatches();
            refreshAnnotationMatchViews();
            return;
        }

        const isCurrent = beginAnnotationOperation('matches');
        const stopLoading = setLoader(true, 'Checking annotation matches...');

        try {
            const data = await annotationWorkflowController.refreshServerAnnotationMatches(
                appState,
                { format: currentAnnotationFormat(), isCurrent }
            );
            if (data.stale) return;
            if (data.annotation_dir_display) {
                annotationDirDisplay.textContent = data.annotation_dir_display;
                annotationDirDisplay.title = phiSafeMode()
                    ? 'PHI-safe mode hides annotation folder paths.'
                    : (data.annotation_dir || data.annotation_dir_display);
            }

            refreshAnnotationMatchViews();

            if (showFeedback) {
                const summary = appState.matchSummary;
                const msg = summary
                    ? `Annotation matches: ${summary.matched} matched, ${summary.missing} missing, ${summary.ambiguous} ambiguous.`
                    : 'Annotation matches checked.';
                updateStatus(msg);
                showToast(msg, 'info');
            }
        } catch (error) {
            if (!isCurrent()) return;
            console.error('Annotation Match Error:', error);
            const msg = `Failed to check annotation matches: ${error.message}`;
            updateStatus(msg);
            if (showFeedback) showToast(msg, 'error');
        } finally {
            stopLoading();
        }
    }

    function beginBulkAnnotationOperation() {
        const isCurrent = beginAnnotationOperation('bulk-annotations');
        const imageGuards = appState.images.map(imageRecord => (
            beginAnnotationOperation('annotations', imageRecord)
        ));
        return () => isCurrent() && imageGuards.every(check => check());
    }

    async function handleLoadMatchedAnnotations() {
        if (appState.annotationSource.mode === 'local') {
            await handleLoadLocalMatchedAnnotations();
            return;
        }

        if (appState.images.length === 0) return;

        const preflightIsCurrent = beginAnnotationOperation('bulk-preflight');
        if (!await ensureProjectImageDimensions() || !preflightIsCurrent()) return;
        const dirtyMatchedImages = annotationWorkflowController.dirtyMatchedImages(appState);
        if (
            dirtyMatchedImages.length > 0
            && !confirmReplaceUnsavedAnnotations(
                'Loading matched annotation files will overwrite those modified images.',
                dirtyMatchedImages.length
            )
        ) {
            return;
        }

        const isCurrent = beginBulkAnnotationOperation();
        const stopLoading = setLoader(true, 'Loading matched annotations...');

        try {
            const result = await annotationWorkflowController.loadServerMatchedAnnotations(
                appState,
                {
                    isCurrent,
                    format: currentAnnotationFormat(),
                    setAnnotationsForImage,
                    applyLoadedClasses
                }
            );
            if (result.stale) return;
            refreshAnnotationLoadViews();

            const summary = result.summary || {};
            const msg = `Loaded ${result.annotationCount} annotations from ${result.loadedCount} matched ${formatLabel(currentAnnotationFormat())} files. ${summary.ambiguous || 0} ambiguous, ${summary.missing || 0} missing, ${summary.errors || 0} errors.`;
            updateStatus(msg);
            showToast(msg, result.loadedCount > 0 ? 'success' : 'info');
        } catch (error) {
            if (!isCurrent()) return;
            console.error('Bulk Annotation Load Error:', error);
            const msg = `Failed to load matched annotations: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        } finally {
            stopLoading();
        }
    }

    function localAnnotationSourceActive() {
        return annotationWorkflowController.localAnnotationSourceActive(appState.annotationSource);
    }

    async function handleAnnotationSourceInput(event) {
        const selectedFiles = Array.from(event.target.files || []);
        event.target.value = '';
        const { annotationFiles, annotationSource } = annotationWorkflowController.localAnnotationSourceFromFiles(
            selectedFiles,
            { formatFromFileName, phiSafeMode: phiSafeMode() }
        );

        if (annotationFiles.length === 0) {
            const msg = 'No supported annotation files were selected.';
            updateStatus(msg);
            showToast(msg, 'error');
            return;
        }

        appState.annotationSource = annotationSource;
        updateAnnotationSourceDisplay();
        await refreshAnnotationMatches({ showFeedback: true });
    }

    async function useServerAnnotationSource() {
        appState.annotationSource = annotationWorkflowController.serverAnnotationSource();
        updateAnnotationSourceDisplay();
        await refreshAnnotationMatches({ showFeedback: true });
    }

    function updateAnnotationSourceDisplay() {
        if (localAnnotationSourceActive()) {
            annotationSourceDisplay.textContent = appState.annotationSource.displayName;
            annotationSourceDisplay.title = annotationMatching.annotationSourceTitle(
                appState.annotationSource,
                { phiSafeMode: phiSafeMode() }
            );
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
            refreshAnnotationMatchViews();
            return;
        }

        const isCurrent = beginAnnotationOperation('matches');
        const stopLoading = setLoader(true, 'Checking local annotation matches...');

        try {
            const annotationFormat = currentAnnotationFormat();
            const data = await annotationWorkflowController.refreshLocalAnnotationMatches(
                appState,
                {
                    isCurrent,
                    format: annotationFormat,
                    parseAnnotationFile,
                    displayForImage: localAnnotationMatchDisplay
                }
            );
            if (data.stale) return;
            refreshAnnotationMatchViews();

            if (showFeedback) {
                const summary = appState.matchSummary;
                const msg = `Local annotation matches: ${summary.matched} matched, ${summary.missing} missing, ${summary.ambiguous} ambiguous.`;
                updateStatus(msg);
                showToast(msg, 'info');
            }
        } catch (error) {
            if (!isCurrent()) return;
            console.error('Local Annotation Match Error:', error);
            const msg = `Failed to check local annotation matches: ${error.message}`;
            updateStatus(msg);
            if (showFeedback) showToast(msg, 'error');
        } finally {
            stopLoading();
        }
    }

    async function handleLoadLocalMatchedAnnotations() {
        if (appState.images.length === 0 || !localAnnotationSourceActive()) return;

        const preflightIsCurrent = beginAnnotationOperation('bulk-preflight');
        if (!await ensureProjectImageDimensions() || !preflightIsCurrent()) return;
        const dirtyMatchedImages = annotationWorkflowController.dirtyMatchedImages(appState);
        if (
            dirtyMatchedImages.length > 0
            && !confirmReplaceUnsavedAnnotations(
                'Loading matched local annotation files will overwrite those modified images.',
                dirtyMatchedImages.length
            )
        ) {
            return;
        }

        const isCurrent = beginBulkAnnotationOperation();
        const stopLoading = setLoader(true, 'Loading local matched annotations...');

        try {
            const annotationFormat = currentAnnotationFormat();
            const result = await annotationWorkflowController.loadLocalMatchedAnnotations(
                appState,
                {
                    isCurrent,
                    format: annotationFormat,
                    parseAnnotationFile,
                    setAnnotationsForImage
                }
            );
            if (result.stale) return;
            refreshAnnotationLoadViews();

            const summary = appState.matchSummary || {};
            const msg = `Loaded ${result.annotationCount} annotations from ${result.loadedCount} matched local ${formatLabel(annotationFormat)} files. ${summary.ambiguous || 0} ambiguous, ${summary.missing || 0} missing, ${result.errorCount} errors.`;
            updateStatus(msg);
            showToast(msg, result.loadedCount > 0 ? 'success' : 'info');
        } catch (error) {
            if (!isCurrent()) return;
            console.error('Local Bulk Annotation Load Error:', error);
            const msg = `Failed to load local matched annotations: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        } finally {
            stopLoading();
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
            const format = document.getElementById('exportFormatSelect').value;
            const exportData = annotationWorkflowController.buildAnnotationExport(
                sourceImageName,
                annotations,
                format,
                appState.currentImage,
                { classes: appState.classes, normalizeAnnotation }
            );
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

    function buildProjectDatasetExport() {
        stateStore.invalidateReviewsForClassChanges(appState);
        return projectDatasetController.buildProjectCocoExport({
            projectId: appState.projectSettings.projectId,
            schemaVersion: appState.projectSettings.schemaVersion,
            taskType: appState.projectSettings.taskType,
            images: appState.images,
            annotationsByImage: appState.annotationsByImage,
            annotationMatchesByImage: appState.annotationMatchesByImage,
            candidateAnnotationsByImage: appState.candidateAnnotationsByImage,
            dirtyImageIds: appState.dirtyImages,
            classes: appState.classes,
            imageName: publicImageName,
            imagePath: publicImagePath,
            normalizeAnnotation
        });
    }

    function reportProjectValidation(validation) {
        const msg = projectDatasetController.validationSummary(validation);
        updateStatus(msg);
        showToast(msg, validation.valid ? (validation.warnings.length > 0 ? 'info' : 'success') : 'error');
        if (!validation.valid) console.warn('Project dataset validation errors:', validation.errors);
        if (validation.warnings.length > 0) {
            console.info('Project dataset validation warnings:', validation.warnings);
        }
        return msg;
    }

    async function ensureProjectImageDimensions() {
        const missingDimensions = appState.images.filter(imageRecord => !imageController.imageDimensions(imageRecord));
        if (missingDimensions.length === 0) return true;

        const isCurrent = stateStore.beginOperation(appState, 'dimensions');
        const stopLoading = setLoader(true, `Inspecting ${missingDimensions.length} project image${missingDimensions.length === 1 ? '' : 's'}...`);
        try {
            for (const imageRecord of missingDimensions) {
                const response = await apiWorkflows.loadImageInfo(imageRecord.file);
                if (!response.ok) throw new Error(`Server error for ${publicImageName(imageRecord)}: ${response.statusText}`);
                const data = await response.json();
                if (!isCurrent()) return false;
                if (data.error) throw new Error(`${publicImageName(imageRecord)}: ${data.error}`);
                imageRecord.width = Number(data.width);
                imageRecord.height = Number(data.height);
                if (!imageController.imageDimensions(imageRecord)) {
                    throw new Error(`${publicImageName(imageRecord)} returned invalid dimensions.`);
                }
            }
            return true;
        } catch (error) {
            if (!isCurrent()) return false;
            const msg = `Could not inspect project images: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
            return false;
        } finally {
            stopLoading();
        }
    }

    async function handleValidateProjectDataset() {
        if (!await ensureProjectImageDimensions()) return;
        try {
            const { validation } = buildProjectDatasetExport();
            reportProjectValidation(validation);
        } catch (error) {
            const msg = `Failed to validate project dataset: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        }
    }

    async function handleExportProjectDataset() {
        if (!await ensureProjectImageDimensions()) return;
        try {
            const exportData = buildProjectDatasetExport();
            reportProjectValidation(exportData.validation);
            if (!exportData.validation.valid) return;

            const blob = new Blob([exportData.content], { type: `${exportData.mime};charset=utf-8` });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = exportData.fileName;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);

            const msg = `Exported project COCO: ${exportData.validation.stats.images} images and ${exportData.validation.stats.annotations} annotations.`;
            updateStatus(msg);
            showToast(msg, 'success');
        } catch (error) {
            const msg = `Failed to export project dataset: ${error.message}`;
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

        const imageRecord = appState.currentImage;
        const isCurrent = beginAnnotationOperation('annotations', imageRecord);
        try {
            const format = formatFromFileName(file.name) || currentAnnotationFormat();
            const result = await annotationWorkflowController.importAnnotationFile(
                file,
                {
                    format,
                    imageRecord,
                    parseAnnotationFile
                }
            );

            if (!isCurrent()) return;
            applyLoadedAnnotations(result.annotations, { markDirty: true, imageRecord });

            const matchText = result.usedMatchedRows
                ? `matched to ${publicImageName(imageRecord)}`
                : 'imported without image-name filtering';
            const msg = `Loaded ${result.annotations.length} ${formatLabel(format)} annotations from ${phiSafeMode() ? 'annotation file' : file.name} (${matchText}).`;
            updateStatus(msg);
            showToast(msg, 'success');
        } catch (error) {
            if (!isCurrent()) return;
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

        const imageRecord = appState.currentImage;
        const isCurrent = beginAnnotationOperation('annotations', imageRecord);
        const stopLoading = setLoader(true, 'Loading saved annotations...');

        try {
            const imageSize = imageDimensions(imageRecord);
            const data = await annotationWorkflowController.loadServerAnnotationsForImage(
                appState,
                {
                    imageRecord,
                    imageId: imageRecord.id,
                    format: currentAnnotationFormat(),
                    matchMode: annotationMatchModeForImage(imageRecord),
                    imageSize,
                    isCurrent
                }
            );
            if (data.stale || !isCurrent()) return false;
            updateMatchSummaryDisplay();

            if (!data.exists) {
                if (!silentWhenMissing) {
                    const msg = `No saved ${formatLabel(currentAnnotationFormat())} file found for ${publicImageName(imageRecord)}.`;
                    updateStatus(msg);
                    showToast(msg, 'info');
                }
                renderImageBrowser();
                return false;
            }

            if (Array.isArray(data.classes)) {
                applyLoadedClasses(data.classes);
            }
            applyLoadedAnnotations(data.annotations || [], { markDirty: false, imageRecord, reviewStatus: data.review_status });
            appState.dirtyImages.delete(imageRecord.id);

            const msg = `Loaded ${(appState.annotationsByImage.get(imageRecord.id) || []).length} annotations from ${publicAnnotationPath(data.path)}.`;
            updateStatus(msg);
            if (!silentWhenMissing) showToast(msg, 'success');
            renderImageBrowser();
            return true;
        } catch (error) {
            if (!isCurrent()) return false;
            console.error('Server Annotation Load Error:', error);
            const msg = `Failed to load saved annotations: ${error.message}`;
            updateStatus(msg);
            if (!silentWhenMissing) showToast(msg, 'error');
            return false;
        } finally {
            stopLoading();
        }
    }

    async function handleReviewImage(reviewStatus, advance = true) {
        const imageRecord = appState.currentImage;
        if (!imageRecord || annotationSavePending || annotationDirectoryChangePending) return;
        const annotations = appState.annotationsByImage.get(imageRecord.id) || [];
        if (reviewStatus === 'reviewed' && annotations.length === 0) return;
        if (reviewStatus === 'confirmed_empty' && annotations.length !== 0) return;
        const candidateCount = (appState.candidateAnnotationsByImage.get(imageRecord.id) || []).length;
        if (reviewStatus === 'confirmed_empty' && candidateCount > 0
            && !window.confirm(`Confirm this image has no target objects? ${candidateCount} SAM candidates will be excluded from the dataset.`)) return;
        if (reviewStatus === 'in_progress') stateStore.markImageDirty(appState, imageRecord);
        const isCurrent = beginAnnotationOperation('review-feedback', imageRecord, false);
        const navigationToken = appState.pendingOperations.get('navigate');
        const stopLoading = setLoader(true, 'Saving image review...');
        try {
            const data = await saveImageAnnotationsToServer(imageRecord, { confirmOverwrite: true, reviewStatus });
            if (data.stale || !isCurrent()) return;
            renderImageBrowser();
            updateButtonStates();
            const msg = `${publicImageName(imageRecord)}: ${imageController.reviewStatusLabel(imageRecord.reviewStatus)} saved.`;
            updateStatus(msg);
            showToast(msg, 'success');
            if (advance && appState.currentImage === imageRecord
                && appState.pendingOperations.get('navigate') === navigationToken) {
                const nextIndex = appState.images.indexOf(imageRecord) + 1;
                if (nextIndex < appState.images.length) {
                    await selectImageByIndex(nextIndex, { autoLoadAnnotations: true });
                }
            }
        } catch (error) {
            if (!isCurrent()) return;
            const msg = `Could not save review: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        } finally {
            stopLoading();
        }
    }

    async function handleSaveServerAnnotations() {
        if (!appState.currentImage) return;

        const imageRecord = appState.currentImage;
        const isCurrent = beginAnnotationOperation('save-feedback', imageRecord, false);
        const stopLoading = setLoader(true, 'Saving annotations to server...');

        try {
            const data = await saveImageAnnotationsToServer(imageRecord, { confirmOverwrite: true });
            if (data.stale || !isCurrent()) return;
            renderImageBrowser();
            const msg = `Saved ${data.count} annotations to ${publicAnnotationPath(data.path)}.`;
            updateStatus(msg);
            showToast(msg, 'success');
        } catch (error) {
            if (!isCurrent()) return;
            console.error('Server Annotation Save Error:', error);
            const msg = `Failed to save annotations: ${error.message}`;
            updateStatus(msg);
            showToast(msg, 'error');
        } finally {
            stopLoading();
        }
    }

    async function handleSaveAllServerAnnotations() {
        const dirtyImageRecords = appState.images.filter(imageRecord => appState.dirtyImages.has(imageRecord.id));
        if (dirtyImageRecords.length === 0) return;

        const isCurrent = beginAnnotationOperation('save-all');
        const stopLoading = setLoader(true, `Saving ${dirtyImageRecords.length} modified images...`);

        const failures = [];
        let savedCount = 0;

        for (const imageRecord of dirtyImageRecords) {
            if (!isCurrent()) break;
            try {
                const data = await saveImageAnnotationsToServer(imageRecord);
                if (data.stale) {
                    failures.push(`${publicImageName(imageRecord)}: changed while saving; newer edits remain unsaved.`);
                    continue;
                }
                savedCount++;
            } catch (error) {
                failures.push(`${publicImageName(imageRecord)}: ${error.message}`);
            }
        }

        stopLoading();
        if (!isCurrent()) return;
        renderImageBrowser();
        updateButtonStates();

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

    async function saveImageAnnotationsToServer(imageRecord, { confirmOverwrite = false, reviewStatus = imageRecord.reviewStatus } = {}) {
        // Response guards cannot undo server writes. Allow only one save at a time,
        // including across folder reloads, to keep older writes from winning on disk.
        if (annotationSavePending || annotationDirectoryChangePending) {
            throw new Error('Wait for the current annotation save or folder change to finish.');
        }
        annotationSavePending = true;
        updateButtonStates();
        try {
            const imageSize = imageDimensions(imageRecord);
            const annotations = (appState.annotationsByImage.get(imageRecord.id) || [])
                .map(annotation => normalizeAnnotation(annotation, imageRecord))
                .filter(Boolean);
            appState.annotationsByImage.set(imageRecord.id, annotations);
            const isCurrent = beginAnnotationOperation('save', imageRecord);
            const data = await annotationWorkflowController.saveImageAnnotationsToServer(
                appState,
                {
                    imageRecord,
                    isCurrent,
                    annotations,
                    reviewStatus,
                    classes: appState.classes,
                    format: currentAnnotationFormat(),
                    matchMode: annotationMatchModeForImage(imageRecord),
                    imageSize,
                    confirmOverwrite,
                    confirmConflict: conflictData => confirm(
                        `Overwrite existing annotation file?\n\n${publicAnnotationPath(conflictData.path) || publicImageName(imageRecord)}`
                    ),
                    display: annotationMatchDisplay(imageRecord)
                }
            );
            if (data.stale || !isCurrent()) return { stale: true };
            imageRecord.reviewStatus = imageController.normalizeReviewStatus(data.review_status, annotations.length);
            imageRecord.reviewClassSignature = stateStore.reviewClassSignature(appState);
            appState.dirtyImages.delete(imageRecord.id);
            return data;
        } finally {
            annotationSavePending = false;
            updateButtonStates();
        }
    }

    async function loadProjectSettings() {
        try {
            const response = await apiWorkflows.loadProjectSettings();
            if (!response.ok) return false;

            const data = await response.json();
            if (data.error) throw new Error(data.error);
            applyProjectSettings(data);
            return true;
        } catch (error) {
            console.warn('Project settings could not be loaded.', error);
        }
        return false;
    }

    function currentAnnotationFormat() {
        return settingsController.currentAnnotationFormat(
            annotationFormatSelect.value,
            appState.projectSettings.annotationFormat,
            normalizeAnnotationFormat
        );
    }

    function updateAnnotationFormatUi() {
        const format = currentAnnotationFormat();
        const metadata = ANNOTATION_FORMATS[format];
        annotationFormatSelect.value = format;
        loadAnnotationFileInput.accept = [...new Set(Object.values(ANNOTATION_FORMATS)
            .map(item => item.accept)
            .join(',')
            .split(','))]
            .join(',');
        annotationSourceFilesInput.accept = loadAnnotationFileInput.accept;
        annotationSourceFolderInput.accept = loadAnnotationFileInput.accept;
        exportAnnotationFileBtn.textContent = 'Export current image';
        loadAnnotationFileBtn.textContent = `Import current-image ${metadata.label}`;
        loadServerAnnotationsBtn.textContent = `Load saved current-image ${metadata.label}`;
    }

    function imageDimensions(imageRecord) {
        return imageController.imageDimensions(imageRecord);
    }

    async function handleAnnotationFormatChange() {
        const annotationFormat = currentAnnotationFormat();
        appState.projectSettings.annotationFormat = annotationFormat;
        updateAnnotationFormatUi();
        clearAnnotationMatches();

        try {
            const response = await apiWorkflows.saveProjectSettings({ annotation_format: annotationFormat });
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
        settingsController.normalizeAndStoreProjectSettings(appState, data);

        annotationDirInput.value = appState.projectSettings.annotationOutputDir;
        annotationDirDisplay.textContent = appState.projectSettings.annotationDirDisplay;
        annotationDirDisplay.title = phiSafeMode()
            ? 'PHI-safe mode hides annotation folder paths.'
            : (data.annotation_dir || appState.projectSettings.annotationDirDisplay);
        annotationFormatSelect.value = appState.projectSettings.annotationFormat;
        updateAnnotationFormatUi();
        renderSamSettingsPanel();
        renderSamDevicePanel();
        syncPreprocessSettingsInputs();
        updateAnnotationSourceDisplay();
    }

    function clearAnnotationMatches() {
        annotationWorkflowController.clearAnnotationMatches(appState);
        refreshAnnotationMatchViews();
    }

    function updateMatchSummaryDisplay() {
        matchSummary.textContent = annotationWorkflowController.matchSummaryText(appState);
    }

    function refreshAnnotationMatchViews() {
        renderImageBrowser();
        updateMatchSummaryDisplay();
        updateButtonStates();
    }

    function refreshAnnotationLoadViews() {
        renderClassControls(classificationSelect.value);
        updateAnnotationLog();
        renderImageBrowser();
        updateMatchSummaryDisplay();
        draw();
        updateButtonStates();
    }

    function annotationMatchDisplay(imageRecord) {
        return {
            name: publicImageName(imageRecord),
            displayPath: publicImagePath(imageRecord),
            annotationPath: publicAnnotationPath
        };
    }

    function localAnnotationMatchDisplay(imageRecord) {
        return annotationMatchDisplay(imageRecord);
    }

    function annotationMatchModeForImage(imageRecord) {
        return annotationWorkflowController.annotationMatchModeForImage(appState, imageRecord);
    }

    async function loadProjectClasses() {
        try {
            const response = await apiWorkflows.loadClasses();
            if (!response.ok) return false;

            const data = await response.json();
            if (Array.isArray(data.classes)) {
                appState.nextClassId = Math.max(Number(data.next_class_id) || 1, appState.nextClassId);
                applyLoadedClasses(data.classes);
                return true;
            }
        } catch (error) {
            console.warn('Project classes could not be loaded.', error);
        }
        return false;
    }

    function scheduleProjectClassesSave() {
        classChangesPending = true;
        updateButtonStates();
        if (classSaveTimer) clearTimeout(classSaveTimer);
        classSaveTimer = setTimeout(() => {
            classSaveTimer = null;
            saveProjectClasses({ silent: true });
        }, 500);
    }

    function saveProjectClasses(options = {}) {
        classSaveQueue = classSaveQueue.then(() => persistProjectClasses(options));
        return classSaveQueue;
    }

    async function persistProjectClasses({ silent = false } = {}) {
        const snapshot = JSON.stringify(appState.classes);
        try {
            const response = await apiWorkflows.saveClasses(JSON.parse(snapshot));
            if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

            const data = await response.json();
            if (data.error) throw new Error(data.error);
            if (Array.isArray(data.classes) && JSON.stringify(appState.classes) === snapshot) {
                classChangesPending = false;
                appState.classes = normalizeClassList(data.classes);
                appState.nextClassId = Math.max(Number(data.next_class_id) || 1, appState.nextClassId);
                renderClassControls(classificationSelect.value);
            }
            if (!silent) {
                const msg = `Saved ${appState.classes.length} project classes.`;
                updateStatus(msg);
                showToast(msg, 'success');
            }
            return true;
        } catch (error) {
            classChangesPending = true;
            showClassManagerFeedback(`Classes could not be saved: ${error.message}. Keep this page open; edit a class to retry.`);
            console.warn('Project classes could not be saved.', error);
            if (!silent) {
                const msg = `Failed to save project classes: ${error.message}`;
                updateStatus(msg);
                showToast(msg, 'error');
            }
            return false;
        } finally {
            updateButtonStates();
        }
    }

    function applyLoadedAnnotations(annotations, { markDirty, imageRecord = appState.currentImage, reviewStatus }) {
        const normalizedAnnotations = setAnnotationsForImage(
            imageRecord,
            annotations,
            { markDirty, reviewStatus }
        );
        const selectedClass = appState.currentImage === imageRecord && normalizedAnnotations[0]
            ? normalizedAnnotations[0].class : classificationSelect.value;
        renderClassControls(selectedClass);

        updateAnnotationLog();
        renderImageBrowser();
        draw();
        updateButtonStates();
    }

    function setAnnotationsForImage(imageRecord, annotations, { markDirty, reviewStatus }) {
        const normalizedAnnotations = annotationWorkflowController.setAnnotationsForImage(
            appState,
            imageRecord,
            annotations,
            {
                markDirty,
                reviewStatus,
                normalizeAnnotation,
                ensureClassesForAnnotations,
                scheduleProjectClassesSave,
                currentImageId
            }
        );
        imageRecord.reviewClassSignature = stateStore.reviewClassSignature(appState);
        return normalizedAnnotations;
    }

    function applyLoadedClasses(classes) {
        const normalizedClasses = normalizeClassList(classes);
        appState.classes = normalizedClasses;
        appState.nextClassId = Math.max(
            appState.nextClassId,
            normalizedClasses.reduce((maximum, classInfo) => Math.max(maximum, classInfo.id || 0), 0) + 1
        );
        let addedClassCount = 0;
        for (const annotations of appState.annotationsByImage.values()) {
            addedClassCount += ensureClassesForAnnotations(annotations);
        }
        if (addedClassCount > 0) scheduleProjectClassesSave();
        renderClassControls(classificationSelect.value);
        draw();
        updateButtonStates();
    }

    function parseAnnotationFile(text, format, imageRecord) {
        return annotationWorkflowController.parseAnnotationFile(text, format, imageRecord, {
            classes: appState.classes,
            imageNames: [
                imageRecord?.name,
                imageRecord?.displayPath,
                publicImageName(imageRecord),
                publicImagePath(imageRecord)
            ].filter(Boolean)
        });
    }

    function normalizeAnnotation(annotation, imageRecord = appState.currentImage) {
        return annotationWorkflowController.normalizeAnnotation(appState, annotation, imageRecord, clampBboxToImage);
    }

    // --- RENDERING ---
    function updateWorkingState() {
        const image = appState.currentImage;
        let tool = 'Select / pan';
        if (!image) tool = 'Load an image';
        else if (appState.isAwaitingChoice) tool = 'Choose a class for the new box';
        else if (appState.boxEditMode) tool = appState.boxEditMode === 'resize' ? 'Resize box' : 'Move boxes';
        else if (appState.isDrawing) tool = 'Drawing box';
        else if (overlayVisibility.imageOnly) tool = 'Inspect image · pan / zoom';
        else if (appState.isManualMode) tool = 'Manual box · drag to draw';
        else if (oneClickAcceptInput.checked && overlayVisibility.candidates) tool = 'One-click accept';
        const activeClass = appState.classes.find(cls => cls.name === classificationSelect.value);
        const dirty = Boolean(image && appState.dirtyImages.has(image.id));
        const review = image ? imageController.reviewStatusLabel(dirty ? 'in_progress' : (image.reviewStatus || 'unreviewed')) : 'No image';
        const candidates = appState.selectedCandidateIds.size;
        const annotations = appState.selectedAnnotationIds.size;
        const values = {
            workingTool: `Tool: ${tool}`,
            workingClass: `Class: ${activeClass?.name || 'None selected'}`,
            workingReview: `Review: ${review}`,
            workingSelection: candidates || annotations
                ? `Selected: ${candidates} candidate${candidates === 1 ? '' : 's'} · ${annotations} annotation${annotations === 1 ? '' : 's'}` : 'No selection'
        };
        Object.entries(values).forEach(([id, text]) => {
            const element = document.getElementById(id);
            // Avoid repeated live-region announcements during mouse movement.
            if (element.textContent !== text) element.textContent = text;
        });
        document.getElementById('workingClass').style.borderLeftColor = activeClass?.color || 'transparent';
        document.getElementById('workingReview').dataset.complete = String(Boolean(image
            && !dirty && ['reviewed', 'confirmed_empty'].includes(image.reviewStatus)));
        manualAnnotationBtn.setAttribute('aria-pressed', String(appState.isManualMode));
    }

    function draw() {
        updateWorkingState();
        const busy = appState.isDrawing || appState.isAwaitingChoice || Boolean(appState.boxEditMode);
        Object.entries(visibilityInputs).forEach(([key, input]) => {
            input.checked = overlayVisibility[key];
            input.disabled = busy || (key !== 'imageOnly' && overlayVisibility.imageOnly)
                || (key === 'labels' && !overlayVisibility.annotations);
        });
        document.getElementById('canvasVisibilitySummary').textContent = overlayVisibility.imageOnly
            ? 'Image only' : (!overlayVisibility.candidates || !overlayVisibility.annotations || !overlayVisibility.labels)
                ? 'Overlays hidden' : 'View overlays';
        resizeCanvasToContainer();

        window.SAM2ManualClassPicker.sync({
            container: canvasContainer,
            choice: appState.isAwaitingChoice ? appState.choiceInfo : null,
            classes: appState.classes,
            activeClass: classificationSelect.value,
            onSelect: finalizeAnnotation,
            onCreate: name => {
                const created = createClassFromName(name, { select: true });
                if (created) finalizeAnnotation(created);
            },
            onCancel: cancelManualAnnotation
        });

        canvasRenderer.drawScene(ctx, canvas, {
            imageToDraw: currentDisplayImage(),
            cameraOffset: appState.cameraOffset,
            cameraZoom: appState.cameraZoom,
            candidates: overlayVisibility.candidates && !overlayVisibility.imageOnly ? currentCandidates() : [],
            selectedCandidateIds: appState.selectedCandidateIds,
            annotations: overlayVisibility.annotations && !overlayVisibility.imageOnly ? currentAnnotations() : [],
            selectedAnnotationIds: appState.selectedAnnotationIds,
            isDrawing: appState.isDrawing,
            currentManualBox: appState.currentManualBox,
            isAwaitingChoice: appState.isAwaitingChoice,
            choiceInfo: appState.choiceInfo,
            zoomLevelDisplay,
            getClassColor,
            showLabels: overlayVisibility.labels
        });
    }

    function updateAnnotationLog() {
        annotationLogController.renderAnnotationLog(
            annotationLogRefs(),
            currentAnnotations(),
            appState.selectedAnnotationIds
        );

        updateAnnotationInspector();
        updateButtonStates();
    }

    function updateAnnotationInspector() {
        annotationLogController.renderAnnotationInspector(
            annotationLogRefs(),
            getSelectedAnnotations()
        );
    }

    function applyInspectorBoxEdit() {
        const selectedAnnotations = getSelectedAnnotations();
        if (selectedAnnotations.length !== 1) return;

        const annotation = selectedAnnotations[0];
        const { rawValues, parsedValues, valid } = annotationLogController.readInspectorBboxInputs(annotationLogRefs());

        if (!valid) {
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
        const changes = [{ id: annotation.id, oldBbox, newBbox: newBbox.slice() }];
        annotationController.invalidateMaskGeometryForChanges(currentAnnotations(), changes);
        annotationController.recordHistoryCommand(
            currentHistory(),
            currentRedoHistory(),
            { type: 'geometry_edit', changes }
        );
        markCurrentImageDirty();
        renderImageBrowser();
        updateAnnotationLog();
        draw();

        const msg = `Updated annotation #${annotation.id}.`;
        updateStatus(msg);
        showToast(msg, 'success');
    }

    function getSelectedAnnotations() {
        return annotationController.selectedAnnotations(currentAnnotations(), appState.selectedAnnotationIds);
    }

    function annotationLogRefs() {
        return {
            annotationLogBody,
            annotationLogHint,
            selectedAnnotationSummary,
            bboxXInput,
            bboxYInput,
            bboxWInput,
            bboxHInput,
            applyBoxEditBtn,
            logContextMenu
        };
    }

    function renderClassControls(preferredClassName = classificationSelect.value) {
        const count = appState.classes.length;
        const summary = document.getElementById('classSourceSummary');
        const guidance = count
            ? `${count} ${count === 1 ? 'class' : 'classes'} in this project. Select a class to annotate, or use Edit to change it.`
            : 'Start by creating your first class, or import labeled annotations.';
        if (summary.textContent !== guidance) summary.textContent = guidance;
        summary.hidden = count > 0;
        addClassBtn.textContent = appState.classes.length ? 'Create class' : 'Create first class';
        stateStore.invalidateReviewsForClassChanges(appState);
        renderImageBrowser();
        updateButtonStates();
        classUiController.renderClassControls(
            { classManager, classificationSelect },
            appState.classes,
            preferredClassName
        );
        filterClassList();
        updateWorkingState();
    }

    function showClassManagerFeedback(message) {
        classManagerFeedback.textContent = message;
        classManagerFeedback.classList.remove('hidden');
    }

    function clearClassManagerFeedback() {
        classManagerFeedback.textContent = '';
        classManagerFeedback.classList.add('hidden');
    }

    function updateButtonStates() {
        const imageLoaded = !!appState.currentImage;
        const selectionExists = appState.selectedCandidateIds.size > 0 || appState.selectedAnnotationIds.size > 0;

        controlsUiController.updateButtonStates(
            {
                runSamBtn,
                clearCandidatesBtn,
                keepAnnotationsInput,
                manualAnnotationBtn,
                applyPreprocessBtn,
                restoreOriginalBtn,
                openPreprocessSettingsBtn,
                preprocessSummary,
                classificationSelect,
                applyClassificationBtn,
                oneClickAcceptInput,
                quickClassInput,
                quickAddClassBtn,
                redoBtn,
                undoBtn,
                exportAnnotationFileBtn,
                validateProjectDatasetBtn,
                exportProjectDatasetBtn,
                loadAnnotationFileBtn,
                loadAnnotationFileInput,
                loadServerAnnotationsBtn,
                refreshMatchesBtn,
                loadMatchedBtn,
                useServerAnnotationSourceBtn,
                saveServerBtn,
                saveAllServerBtn,
                reviewAndNextBtn,
                confirmEmptyBtn,
                reopenReviewBtn,
                unsavedStateIndicator,
                selectionSummary,
                nextActionText,
                canvasEmptyState,
                oneClickModeBadge,
                prevImageBtn,
                nextImageBtn
            },
            {
                imageLoaded,
                samHasRun: Boolean(appState.currentImage?.samHasRun),
                selectionExists,
                historyExists: currentHistory().length > 0,
                redoExists: currentRedoHistory().length > 0,
                annotationsExist: currentAnnotations().length > 0,
                candidatesExist: currentCandidates().length > 0,
                classesExist: appState.classes.length > 0,
                isManualMode: appState.isManualMode,
                selectedPreprocess: selectedPreprocessMethod(),
                activePreprocess: hasActivePreprocess(appState.currentImage),
                activePreprocessMethod: appState.currentImage?.preprocessMethod || 'original',
                localAnnotationSourceActive: localAnnotationSourceActive(),
                dirtyImageCount: appState.dirtyImages.size,
                reviewStatus: appState.currentImage?.reviewStatus || 'unreviewed',
                savingAnnotations: annotationSavePending || annotationDirectoryChangePending,
                classChangesPending,
                currentImageDirty: appState.currentImage ? appState.dirtyImages.has(appState.currentImage.id) : false,
                imageCount: appState.images.length,
                matchSummary: appState.matchSummary,
                currentImageIndex: currentImageIndex(),
                selectedCandidateCount: appState.selectedCandidateIds.size,
                selectedAnnotationCount: appState.selectedAnnotationIds.size,
                activeClassName: classificationSelect.value
            },
            {
                classUiController,
                preprocessLabel
            }
        );
        updateWorkingState();
    }

    function ensureClassesForAnnotations(annotations) {
        const result = classManagerLogic.ensureClassesForAnnotations(
            appState.classes,
            annotations,
            appState.nextClassId
        );
        appState.classes = result.classes;
        appState.nextClassId = result.nextClassId;
        return result.addedCount;
    }

    function countAnnotationsWithClass(className) {
        return annotationController.countAnnotationsWithClass(appState.annotationsByImage, className);
    }

    function renameAnnotationClass(oldName, newName) {
        return annotationController.renameAnnotationClass(
            appState.annotationsByImage,
            appState.dirtyImages,
            oldName,
            newName
        );
    }

    // --- STATE HELPERS ---
    function createImageRecord(file, imageElement = null, index = appState.images.length) {
        return imageController.createImageRecord(file, imageElement, index);
    }

    function phiSafeMode() {
        return Boolean(appState.projectSettings.privacy?.phiSafeMode);
    }

    function publicImageName(imageRecord) {
        return fileUtils.publicImageName(imageRecord, phiSafeMode());
    }

    function publicImagePath(imageRecord) {
        return fileUtils.publicImagePath(imageRecord, phiSafeMode());
    }

    function publicAnnotationPath(path) {
        return fileUtils.publicAnnotationPath(path, phiSafeMode());
    }

    function initializeImageState(imageId) {
        stateStore.initializeImageState(appState, imageId);
    }

    function currentImageId() {
        return stateStore.currentImageId(appState);
    }

    function currentImageIndex() {
        return stateStore.currentImageIndex(appState);
    }

    function currentAnnotations() {
        return stateStore.currentAnnotations(appState);
    }

    function setCurrentAnnotations(annotations) {
        const normalizedAnnotations = annotations
            .map(annotation => normalizeAnnotation(annotation, appState.currentImage))
            .filter(Boolean);
        stateStore.setCurrentAnnotations(appState, normalizedAnnotations);
    }

    function currentCandidates() {
        return stateStore.currentCandidates(appState);
    }

    function setCurrentCandidates(candidates) {
        stateStore.setCurrentCandidates(appState, candidates);
    }

    function currentHistory() {
        return stateStore.currentHistory(appState);
    }

    function setCurrentHistory(history) {
        stateStore.setCurrentHistory(appState, history);
    }

    function currentRedoHistory() {
        return stateStore.currentRedoHistory(appState);
    }

    function setCurrentRedoHistory(history) {
        stateStore.setCurrentRedoHistory(appState, history);
    }

    function clearAllAnnotationHistory() {
        for (const imageId of appState.annotationHistoryByImage.keys()) {
            appState.annotationHistoryByImage.set(imageId, []);
            appState.annotationRedoByImage.set(imageId, []);
        }
    }

    function currentDisplayImage() {
        return stateStore.currentDisplayImage(appState, hasActivePreprocess);
    }

    function markCurrentImageDirty() {
        stateStore.markCurrentImageDirty(appState);
    }

    function resetInteractionState() {
        stateStore.resetInteractionState(appState);
        annotationLogController.hideContextMenu(annotationLogRefs());

        if (appState.isManualMode) {
            manualAnnotationBtn.classList.remove('active');
            appState.isManualMode = false;
        }

        canvas.style.cursor = 'grab';
    }

    function resetState() {
        imageQueueSearch.value = '';
        stateStore.resetProjectState(appState);
        setLoader(false);

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
        if (unsavedImageCount() === 0 && !classChangesPending) return;
        event.preventDefault();
        event.returnValue = '';
    }

    function resizeCanvasToContainer() {
        if (canvasContainer.clientWidth !== canvas.width || canvasContainer.clientHeight !== canvas.height) {
            canvas.width = canvasContainer.clientWidth;
            canvas.height = canvasContainer.clientHeight;
            return true;
        }
        return false;
    }

    function fitImageToView() {
        const imageRecord = appState.currentImage;
        if (!imageRecord || canvas.width < 1) return;

        const nextCamera = canvasGeometry.fitImageToView(
            { width: canvas.width, height: canvas.height },
            { width: imageRecord.originalImage.width, height: imageRecord.originalImage.height }
        );
        if (!nextCamera) return;
        appState.cameraZoom = nextCamera.zoom;
        appState.cameraOffset = nextCamera.offset;
    }

    function getScreenPoint(clientX, clientY) {
        const rect = canvas.getBoundingClientRect();
        return canvasGeometry.screenPoint(clientX, clientY, rect);
    }

    function getWorldPoint(screenX, screenY) {
        return canvasGeometry.worldPoint(screenX, screenY, appState.cameraOffset, appState.cameraZoom);
    }

    function pointInsideRect(point, rect) {
        return canvasGeometry.pointInsideRect(point, rect);
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

    const loadingRequests = new Map();

    function setLoader(visible, text = 'Processing...') {
        if (!visible) loadingRequests.clear();
        const token = {};
        if (visible) loadingRequests.set(token, text);
        function renderLoader() {
            const messages = Array.from(loadingRequests.values());
            loaderText.textContent = messages[messages.length - 1] || 'Processing...';
            loader.classList.toggle('hidden', messages.length === 0);
        }
        renderLoader();
        return () => {
            loadingRequests.delete(token);
            renderLoader();
        };
    }

    function updateStatus(message) {
        if (statusText.textContent !== message) statusText.textContent = message;
    }

    function showToast(message, type = 'info', duration = 3000) {
        if (type === 'success' || !toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.animationDuration = '0.3s, 0.5s';
        toast.style.animationDelay = `0s, ${duration / 1000 - 0.5}s`;
        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.remove();
        }, duration);
    }

    async function initializeApp() {
        const workspace = document.querySelector('.app-container');
        workspace.inert = true;
        try {
            const response = await window.SAM2ApiClient.apiFetch('api/project/manifest');
            if (!response.ok) throw new Error('Could not load the project');
            const project = await response.json();
            window.SAM2ApiClient.setProjectId(project.project_id);
            document.getElementById('activeProjectName').textContent = project.name;

            renderSamSettingsPanel();
            syncPreprocessSettingsInputs();
            resetState();
            renderClassControls();
            if (!await loadProjectSettings() || !await loadProjectClasses()) {
                throw new Error('Could not load project settings or classes');
            }
            document.getElementById('manageProjectsBtn').disabled = false;
            resizeCanvasToContainer();
            draw();
            updateButtonStates();
            workspace.inert = false;
        } catch (error) {
            updateStatus(`${error.message}. Reload the page to retry; editing is disabled to protect saved work.`);
        }
    }

    initializeApp();
});
