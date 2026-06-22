(() => {
    const PREPROCESS_APPLY_TITLE = 'Apply the selected preprocessing to the displayed image; future SAM runs apply the same preprocessing on the server.';
    const PREPROCESS_RESTORE_TITLE = 'Restore the original display and use the original image for future SAM runs.';

    function updateButtonStates(refs, state, helpers) {
        const {
            classUiController,
            preprocessLabel
        } = helpers;
        const {
            imageLoaded,
            samHasRun,
            selectionExists,
            historyExists,
            annotationsExist,
            candidatesExist,
            classesExist,
            isManualMode,
            selectedPreprocess,
            activePreprocess,
            activePreprocessMethod,
            localAnnotationSourceActive,
            dirtyImageCount,
            imageCount,
            matchSummary,
            currentImageIndex
        } = state;

        refs.runSamBtn.disabled = !imageLoaded;
        refs.runSamBtn.textContent = imageLoaded && samHasRun ? 'Re-run SAM2' : 'Run SAM2 & Filter';
        refs.clearCandidatesBtn.disabled = !imageLoaded || !candidatesExist;
        refs.keepAnnotationsInput.disabled = !imageLoaded;
        refs.manualAnnotationBtn.disabled = !imageLoaded;
        refs.manualAnnotationBtn.textContent = isManualMode ? 'Exit Manual Box (B)' : 'Manual Box (B)';

        const preprocessSelectedOriginal = selectedPreprocess === 'original';
        refs.applyPreprocessBtn.disabled = !imageLoaded || preprocessSelectedOriginal;
        refs.applyPreprocessBtn.textContent = preprocessSelectedOriginal
            ? 'Original Active'
            : activePreprocess && activePreprocessMethod === selectedPreprocess
                ? `${preprocessLabel(selectedPreprocess)} Active`
                : `Apply ${preprocessLabel(selectedPreprocess)}`;
        refs.applyPreprocessBtn.title = PREPROCESS_APPLY_TITLE;
        refs.restoreOriginalBtn.disabled = !imageLoaded || !activePreprocess;
        refs.restoreOriginalBtn.title = PREPROCESS_RESTORE_TITLE;
        refs.openPreprocessSettingsBtn.disabled = false;
        refs.preprocessSummary.textContent = activePreprocess
            ? `${preprocessLabel(activePreprocessMethod)} active. Original image is preserved.`
            : 'Original image is preserved.';

        classUiController.syncClassControlStates(
            {
                classificationSelect: refs.classificationSelect,
                applyClassificationBtn: refs.applyClassificationBtn,
                oneClickAcceptInput: refs.oneClickAcceptInput,
                quickClassInput: refs.quickClassInput,
                quickAddClassBtn: refs.quickAddClassBtn
            },
            { imageLoaded, selectionExists, classesExist, candidatesExist }
        );

        refs.undoBtn.disabled = !historyExists;
        refs.exportAnnotationFileBtn.disabled = !annotationsExist;
        refs.loadAnnotationFileBtn.disabled = !imageLoaded;
        refs.loadAnnotationFileInput.disabled = !imageLoaded;
        refs.loadServerAnnotationsBtn.disabled = !imageLoaded;
        refs.refreshMatchesBtn.textContent = localAnnotationSourceActive ? 'Check Local Matches' : 'Check Matches';
        refs.loadMatchedBtn.textContent = localAnnotationSourceActive ? 'Load Local Matched' : 'Load Matched';
        refs.useServerAnnotationSourceBtn.disabled = !localAnnotationSourceActive;
        refs.saveServerBtn.disabled = !imageLoaded;
        refs.saveAllServerBtn.disabled = dirtyImageCount === 0;
        refs.refreshMatchesBtn.disabled = imageCount === 0;
        refs.loadMatchedBtn.disabled = !matchSummary || ((matchSummary.matched || matchSummary.loaded || 0) === 0);
        refs.prevImageBtn.disabled = currentImageIndex <= 0;
        refs.nextImageBtn.disabled = currentImageIndex === -1 || currentImageIndex >= imageCount - 1;
    }

    window.SAM2ControlsUiController = {
        updateButtonStates
    };
})();
