(() => {
    const apiWorkflows = window.SAM2ApiWorkflows;
    if (!apiWorkflows) {
        throw new Error('SAM2ApiWorkflows must be loaded before annotationWorkflowController.js.');
    }

    const annotationCodecs = window.SAM2AnnotationCodecs;
    if (!annotationCodecs) {
        throw new Error('SAM2AnnotationCodecs must be loaded before annotationWorkflowController.js.');
    }

    const annotationController = window.SAM2AnnotationController;
    if (!annotationController) {
        throw new Error('SAM2AnnotationController must be loaded before annotationWorkflowController.js.');
    }

    const annotationMatching = window.SAM2AnnotationMatching;
    if (!annotationMatching) {
        throw new Error('SAM2AnnotationMatching must be loaded before annotationWorkflowController.js.');
    }

    const imageController = window.SAM2ImageController;
    if (!imageController) {
        throw new Error('SAM2ImageController must be loaded before annotationWorkflowController.js.');
    }

    function localAnnotationSourceActive(annotationSource) {
        return annotationMatching.localAnnotationSourceActive(annotationSource);
    }

    function serverAnnotationSource() {
        return {
            mode: 'server',
            files: [],
            fileMap: new Map(),
            displayName: 'Server folder source active.'
        };
    }

    function localAnnotationSourceFromFiles(selectedFiles, { formatFromFileName, phiSafeMode = false }) {
        const annotationFiles = selectedFiles.filter(file => formatFromFileName(file.name));
        return {
            annotationFiles,
            annotationSource: annotationMatching.buildLocalAnnotationSource(annotationFiles, { phiSafeMode })
        };
    }

    function imagePayloads(images) {
        return imageController.imagePayloads(images);
    }

    async function refreshServerAnnotationMatches(state, { format }) {
        if (state.images.length === 0) {
            clearAnnotationMatches(state);
            return { skipped: true };
        }

        const response = await apiWorkflows.matchAnnotations({
            images: imagePayloads(state.images),
            format
        });
        if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

        const data = await response.json();
        if (data.error) throw new Error(data.error);

        state.annotationMatchesByImage.clear();
        (data.results || []).forEach(match => {
            state.annotationMatchesByImage.set(match.id, match);
        });
        state.matchSummary = data.summary || null;
        if (data.annotation_dir_display) {
            state.projectSettings.annotationDirDisplay = data.annotation_dir_display;
        }

        return data;
    }

    async function refreshLocalAnnotationMatches(state, {
        format,
        parseAnnotationFile,
        displayForImage
    }) {
        if (state.images.length === 0 || !localAnnotationSourceActive(state.annotationSource)) {
            clearAnnotationMatches(state);
            return { skipped: true };
        }

        const duplicateStems = annotationMatching.duplicateImageStems(state.images);
        const results = [];

        for (const imageRecord of state.images) {
            const match = resolveLocalAnnotationMatch(state, imageRecord, duplicateStems, format, displayForImage);
            if (match.status === 'matched') {
                match.annotation_count = await countLocalAnnotationFile(match.sourceFile, format, imageRecord, parseAnnotationFile);
            }
            results.push(match);
        }

        state.annotationMatchesByImage.clear();
        results.forEach(match => state.annotationMatchesByImage.set(match.id, match));
        state.matchSummary = annotationMatching.summarizeMatchResults(results);

        return { results, summary: state.matchSummary };
    }

    async function loadServerMatchedAnnotations(state, {
        format,
        setAnnotationsForImage,
        applyLoadedClasses
    }) {
        if (state.images.length === 0) return { loadedCount: 0, annotationCount: 0, summary: state.matchSummary };

        const response = await apiWorkflows.bulkLoadAnnotations({
            images: imagePayloads(state.images),
            format
        });
        if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

        const data = await response.json();
        if (data.error) throw new Error(data.error);

        if (Array.isArray(data.classes)) {
            applyLoadedClasses(data.classes);
        }

        let loadedCount = 0;
        let annotationCount = 0;
        const imageById = new Map(state.images.map(imageRecord => [imageRecord.id, imageRecord]));

        (data.results || []).forEach(result => {
            state.annotationMatchesByImage.set(result.id, result);
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
            state.dirtyImages.delete(imageRecord.id);
        });

        state.matchSummary = data.summary || state.matchSummary;
        return { loadedCount, annotationCount, summary: state.matchSummary };
    }

    async function loadLocalMatchedAnnotations(state, {
        format,
        parseAnnotationFile,
        setAnnotationsForImage
    }) {
        let loadedCount = 0;
        let annotationCount = 0;
        let errorCount = 0;

        for (const imageRecord of state.images) {
            const match = state.annotationMatchesByImage.get(imageRecord.id);
            if (match?.status !== 'matched' || !match.sourceFile) continue;

            try {
                const text = await match.sourceFile.text();
                const result = parseAnnotationFile(text, format, imageRecord);
                const normalizedAnnotations = setAnnotationsForImage(
                    imageRecord,
                    result.annotations || [],
                    { markDirty: false }
                );
                annotationCount += normalizedAnnotations.length;
                loadedCount++;
                imageRecord.serverAnnotationsChecked = true;
                state.dirtyImages.delete(imageRecord.id);
            } catch (error) {
                errorCount++;
                state.annotationMatchesByImage.set(imageRecord.id, {
                    ...match,
                    status: 'error',
                    exists: false,
                    annotations: [],
                    message: `Failed to load local annotations: ${error.message}`
                });
            }
        }

        recomputeMatchSummaryFromMatches(state);
        return { loadedCount, annotationCount, errorCount, summary: state.matchSummary };
    }

    async function importAnnotationFile(file, { format, imageRecord, parseAnnotationFile }) {
        const text = await file.text();
        const result = parseAnnotationFile(text, format, imageRecord);
        if (result.annotations.length === 0) {
            throw new Error('No valid annotations were found in this file.');
        }
        return result;
    }

    function buildAnnotationExport(sourceImageName, annotations, format, imageRecord, { classes, normalizeAnnotation }) {
        return annotationCodecs.buildAnnotationExport(sourceImageName, annotations, format, imageRecord, {
            classes,
            normalizeAnnotation
        });
    }

    function parseAnnotationFile(text, format, imageRecord, { classes, imageNames }) {
        return annotationCodecs.parseAnnotationFile(text, format, imageRecord, {
            classes,
            imageNames
        });
    }

    async function loadServerAnnotationsForImage(state, {
        imageRecord,
        imageId,
        format,
        matchMode,
        imageSize
    }) {
        const params = new URLSearchParams({
            image_name: imageRecord.name,
            image_path: imageRecord.displayPath,
            match_mode: matchMode,
            format
        });
        if (imageSize) {
            params.set('image_width', String(imageSize.width));
            params.set('image_height', String(imageSize.height));
        }

        const response = await apiWorkflows.loadAnnotations(params);
        if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

        const data = await response.json();
        if (data.error) throw new Error(data.error);

        imageRecord.serverAnnotationsChecked = true;
        if (data.match) {
            state.annotationMatchesByImage.set(imageId, data.match);
            recomputeMatchSummaryFromMatches(state);
        }

        return data;
    }

    async function saveImageAnnotationsToServer(state, {
        imageRecord,
        annotations,
        classes,
        format,
        matchMode,
        imageSize,
        confirmOverwrite = false,
        confirmConflict,
        display
    }) {
        const payload = {
            image_name: imageRecord.name,
            image_path: imageRecord.displayPath,
            match_mode: matchMode,
            format,
            overwrite: !confirmOverwrite,
            annotations,
            classes,
            image_width: imageSize ? imageSize.width : null,
            image_height: imageSize ? imageSize.height : null
        };

        const response = await apiWorkflows.saveAnnotations(payload);

        if (response.status === 409 && confirmOverwrite) {
            const conflictData = await response.json();
            if (!confirmConflict(conflictData)) throw new Error('Save cancelled.');

            const overwriteResponse = await apiWorkflows.saveAnnotations({ ...payload, overwrite: true });
            if (!overwriteResponse.ok) throw new Error(`Server error: ${overwriteResponse.statusText}`);
            const overwriteData = await overwriteResponse.json();
            if (overwriteData.error) throw new Error(overwriteData.error);
            updateAnnotationMatchAfterSave(state, imageRecord, overwriteData, { format, matchMode, display });
            return overwriteData;
        }

        if (!response.ok) throw new Error(`Server error: ${response.statusText}`);

        const data = await response.json();
        if (data.error) throw new Error(data.error);
        updateAnnotationMatchAfterSave(state, imageRecord, data, { format, matchMode, display });
        return data;
    }

    function normalizeAnnotation(state, annotation, imageRecord, clampBboxToImage) {
        return annotationController.normalizeAnnotation(state, annotation, imageRecord, clampBboxToImage);
    }

    function setAnnotationsForImage(state, imageRecord, annotations, {
        markDirty,
        normalizeAnnotation,
        ensureClassesForAnnotations,
        scheduleProjectClassesSave,
        currentImageId
    }) {
        if (!imageRecord) return [];

        const previousAnnotations = state.annotationsByImage.get(imageRecord.id) || [];
        const normalizedAnnotations = annotations
            .map(annotation => normalizeAnnotation(annotation, imageRecord))
            .filter(Boolean);

        state.annotationsByImage.set(imageRecord.id, normalizedAnnotations);
        if (markDirty) {
            const history = state.annotationHistoryByImage.get(imageRecord.id) || [];
            const redoHistory = state.annotationRedoByImage.get(imageRecord.id) || [];
            state.annotationHistoryByImage.set(imageRecord.id, history);
            state.annotationRedoByImage.set(imageRecord.id, redoHistory);
            annotationController.recordHistoryCommand(history, redoHistory, {
                type: 'replace_annotations',
                beforeRecords: previousAnnotations.map((item, index) => ({ item, index })),
                afterRecords: normalizedAnnotations.map((item, index) => ({ item, index }))
            });
        } else {
            state.annotationHistoryByImage.set(imageRecord.id, []);
            state.annotationRedoByImage.set(imageRecord.id, []);
        }
        state.annotationCounter = Math.max(
            state.annotationCounter,
            ...normalizedAnnotations.map(annotation => annotation.id),
            0
        );

        const addedClassCount = ensureClassesForAnnotations(normalizedAnnotations);
        if (addedClassCount > 0) scheduleProjectClassesSave();

        if (markDirty) {
            state.dirtyImages.add(imageRecord.id);
        }

        if (currentImageId() === imageRecord.id) {
            state.selectedAnnotationIds.clear();
            state.selectedCandidateIds.clear();
        }

        return normalizedAnnotations;
    }

    function dirtyMatchedImages(state) {
        return state.images.filter(imageRecord => (
            state.dirtyImages.has(imageRecord.id)
            && state.annotationMatchesByImage.get(imageRecord.id)?.status === 'matched'
        ));
    }

    function resolveLocalAnnotationMatch(state, imageRecord, duplicateStems, annotationFormat, displayForImage) {
        return annotationMatching.resolveLocalAnnotationMatch(
            imageRecord,
            duplicateStems,
            annotationFormat,
            state.annotationSource.fileMap,
            displayForImage(imageRecord)
        );
    }

    async function countLocalAnnotationFile(file, annotationFormat, imageRecord, parseAnnotationFile) {
        if (!file) return 0;
        try {
            const text = await file.text();
            return parseAnnotationFile(text, annotationFormat, imageRecord).annotations.length;
        } catch {
            return null;
        }
    }

    function annotationMatchModeForImage(state, imageRecord) {
        const match = state.annotationMatchesByImage.get(imageRecord.id);
        return annotationMatching.annotationMatchModeForImage(imageRecord, state.images, match);
    }

    function clearAnnotationMatches(state) {
        state.annotationMatchesByImage.clear();
        state.matchSummary = null;
    }

    function matchSummaryText(state) {
        if (state.images.length === 0) {
            return 'No image folder checked.';
        }

        const summary = state.matchSummary;
        if (!summary) {
            return localAnnotationSourceActive(state.annotationSource)
                ? 'Local annotation matches not checked.'
                : 'Annotation matches not checked.';
        }

        const prefix = localAnnotationSourceActive(state.annotationSource) ? 'Local source: ' : '';
        return `${prefix}${summary.matched || summary.loaded || 0} matched, ${summary.missing || 0} missing, ${summary.ambiguous || 0} ambiguous.`;
    }

    function updateAnnotationMatchAfterSave(state, imageRecord, data, { format, matchMode, display = {} }) {
        state.annotationMatchesByImage.set(imageRecord.id, {
            id: imageRecord.id,
            name: display.name ?? imageRecord.name,
            display_path: display.displayPath ?? imageRecord.displayPath,
            status: 'matched',
            exists: true,
            ambiguous: false,
            match_mode: data.match_mode || matchMode,
            path: display.annotationPath ? display.annotationPath(data.path) : data.path,
            annotation_count: data.count,
            format: data.format || format,
            message: 'Saved annotation file.'
        });
        recomputeMatchSummaryFromMatches(state);
    }

    function recomputeMatchSummaryFromMatches(state) {
        state.matchSummary = annotationMatching.recomputeMatchSummaryFromMatches(
            state.images,
            state.annotationMatchesByImage
        );
        return state.matchSummary;
    }

    window.SAM2AnnotationWorkflowController = {
        localAnnotationSourceActive,
        serverAnnotationSource,
        localAnnotationSourceFromFiles,
        imagePayloads,
        refreshServerAnnotationMatches,
        refreshLocalAnnotationMatches,
        loadServerMatchedAnnotations,
        loadLocalMatchedAnnotations,
        importAnnotationFile,
        buildAnnotationExport,
        parseAnnotationFile,
        loadServerAnnotationsForImage,
        saveImageAnnotationsToServer,
        normalizeAnnotation,
        setAnnotationsForImage,
        dirtyMatchedImages,
        annotationMatchModeForImage,
        clearAnnotationMatches,
        matchSummaryText,
        updateAnnotationMatchAfterSave,
        recomputeMatchSummaryFromMatches
    };
})();
