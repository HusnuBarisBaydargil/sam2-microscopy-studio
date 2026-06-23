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
            currentImageDirty,
            imageCount,
            matchSummary,
            currentImageIndex,
            selectedCandidateCount,
            selectedAnnotationCount,
            activeClassName
        } = state;

        refs.canvasEmptyState.classList.toggle('hidden', imageLoaded);
        refs.runSamBtn.disabled = !imageLoaded;
        refs.runSamBtn.textContent = imageLoaded && samHasRun ? 'Re-generate SAM2 candidates' : 'Generate SAM2 candidates';
        refs.clearCandidatesBtn.disabled = !imageLoaded || !candidatesExist;
        refs.keepAnnotationsInput.disabled = !imageLoaded;
        refs.manualAnnotationBtn.disabled = !imageLoaded;
        refs.manualAnnotationBtn.textContent = isManualMode ? 'Exit Manual Box (B)' : 'Manual Box (B)';

        const preprocessSelectedOriginal = selectedPreprocess === 'original';
        refs.applyPreprocessBtn.disabled = !imageLoaded || preprocessSelectedOriginal;
        refs.applyPreprocessBtn.textContent = preprocessSelectedOriginal
            ? 'Original image active'
            : activePreprocess && activePreprocessMethod === selectedPreprocess
                ? `${preprocessLabel(selectedPreprocess)} active`
                : `Apply ${preprocessLabel(selectedPreprocess)}`;
        refs.applyPreprocessBtn.title = PREPROCESS_APPLY_TITLE;
        refs.restoreOriginalBtn.disabled = !imageLoaded || !activePreprocess;
        refs.restoreOriginalBtn.title = PREPROCESS_RESTORE_TITLE;
        refs.openPreprocessSettingsBtn.disabled = false;
        refs.preprocessSummary.textContent = activePreprocess
            ? `${preprocessLabel(activePreprocessMethod)} active. Original image is preserved.`
            : 'Original image is preserved.';
        refs.selectionSummary.textContent = `Selected: ${selectedCandidateCount} candidate${selectedCandidateCount === 1 ? '' : 's'}, ${selectedAnnotationCount} annotation${selectedAnnotationCount === 1 ? '' : 's'}`;
        refs.nextActionText.textContent = nextActionText({
            imageLoaded,
            selectionExists,
            candidatesExist,
            annotationsExist
        });

        classUiController.syncClassControlStates(
            {
                classificationSelect: refs.classificationSelect,
                applyClassificationBtn: refs.applyClassificationBtn,
                oneClickAcceptInput: refs.oneClickAcceptInput,
                quickClassInput: refs.quickClassInput,
                quickAddClassBtn: refs.quickAddClassBtn
            },
            { imageLoaded, selectionExists, classesExist, candidatesExist, activeClassName }
        );
        const oneClickActive = Boolean(refs.oneClickAcceptInput.checked && activeClassName);
        refs.oneClickModeBadge.textContent = oneClickActive ? `One-click accept: ${activeClassName}` : '';
        refs.oneClickModeBadge.classList.toggle('hidden', !oneClickActive);

        refs.undoBtn.disabled = !historyExists;
        refs.exportAnnotationFileBtn.disabled = !annotationsExist;
        refs.loadAnnotationFileBtn.disabled = !imageLoaded;
        refs.loadAnnotationFileInput.disabled = !imageLoaded;
        refs.loadServerAnnotationsBtn.disabled = !imageLoaded;
        refs.refreshMatchesBtn.textContent = localAnnotationSourceActive ? 'Check Local Matches' : 'Check Matches';
        refs.loadMatchedBtn.textContent = localAnnotationSourceActive ? 'Import Local Matched' : 'Import Matched';
        refs.useServerAnnotationSourceBtn.disabled = !localAnnotationSourceActive;
        refs.saveServerBtn.disabled = !imageLoaded;
        refs.saveAllServerBtn.disabled = dirtyImageCount === 0;
        refs.unsavedStateIndicator.textContent = unsavedStateText(dirtyImageCount, currentImageDirty);
        refs.unsavedStateIndicator.title = dirtyImageCount > 0
            ? 'There are unsaved annotation changes.'
            : 'No unsaved annotation changes.';
        if (refs.unsavedStateIndicator.classList) {
            refs.unsavedStateIndicator.classList.toggle('dirty', dirtyImageCount > 0);
            refs.unsavedStateIndicator.classList.toggle('saved', dirtyImageCount === 0);
        }
        refs.refreshMatchesBtn.disabled = imageCount === 0;
        refs.loadMatchedBtn.disabled = !matchSummary || ((matchSummary.matched || matchSummary.loaded || 0) === 0);
        refs.prevImageBtn.disabled = currentImageIndex <= 0;
        refs.nextImageBtn.disabled = currentImageIndex === -1 || currentImageIndex >= imageCount - 1;
    }

    function unsavedStateText(dirtyImageCount, currentImageDirty) {
        if (dirtyImageCount === 0) return 'All changes saved';
        if (currentImageDirty && dirtyImageCount === 1) return 'Unsaved changes: current image';
        if (currentImageDirty) return `Unsaved changes: current + ${dirtyImageCount - 1} other`;
        return `Unsaved changes: ${dirtyImageCount} image${dirtyImageCount === 1 ? '' : 's'}`;
    }

    function nextActionText(state) {
        if (!state.imageLoaded) return 'Load an image or folder.';
        if (state.selectionExists) return 'Apply active class or press a class hotkey.';
        if (state.candidatesExist) return 'Select candidate boxes.';
        if (state.annotationsExist) return 'Review, edit, save, or export annotations.';
        return 'Generate SAM2 candidates or draw manual boxes.';
    }

    window.SAM2ControlsUiController = {
        updateButtonStates,
        unsavedStateText,
        nextActionText
    };
})();
