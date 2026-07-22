(() => {
    const annotationCodecs = window.SAM2AnnotationCodecs;
    if (!annotationCodecs) {
        throw new Error('SAM2AnnotationCodecs must be loaded before annotationController.js.');
    }

    const { annotationMaskMetadata, normalizeContour } = annotationCodecs;

    function maskGeometrySnapshot(annotation) {
        const snapshot = {};
        const contour = normalizeContour(annotation?.contour);
        if (contour) {
            snapshot.contour = contour.map(point => point.slice());
        }
        const maskArea = Number(annotation?.mask_area);
        if (annotation?.mask_area !== '' && annotation?.mask_area !== null && Number.isFinite(maskArea)) {
            snapshot.mask_area = maskArea;
        }
        return snapshot;
    }

    function invalidateMaskGeometry(annotation) {
        const snapshot = maskGeometrySnapshot(annotation);
        delete annotation.contour;
        delete annotation.mask_area;
        return snapshot;
    }

    function restoreMaskGeometry(annotation, snapshot) {
        delete annotation.contour;
        delete annotation.mask_area;
        if (!snapshot) return;
        if (snapshot.contour) {
            annotation.contour = snapshot.contour.map(point => point.slice());
        }
        if (Object.prototype.hasOwnProperty.call(snapshot, 'mask_area')) {
            annotation.mask_area = snapshot.mask_area;
        }
    }

    function invalidateMaskGeometryForChanges(annotations, changes) {
        const annotationsById = new Map(annotations.map(annotation => [annotation.id, annotation]));
        changes.forEach(change => {
            const annotation = annotationsById.get(change.id);
            if (!annotation) return;
            const oldMaskGeometry = invalidateMaskGeometry(annotation);
            if (Object.keys(oldMaskGeometry).length > 0) {
                change.oldMaskGeometry = oldMaskGeometry;
            }
        });
        return changes;
    }

    function annotationFromCandidate(state, candidate, className, clampBboxToImage) {
        const bbox = clampBboxToImage(candidate.bbox);
        if (!bbox) return null;

        state.annotationCounter++;
        return {
            id: state.annotationCounter,
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

    function convertSelectedCandidates(state, candidates, annotations, history, className, clampBboxToImage) {
        if (state.selectedCandidateIds.size === 0) {
            return { count: 0, remainingCandidates: candidates };
        }

        const batch = { type: 'convert_candidates', convertedAnnotations: [], originalCandidates: [] };
        const newAnnotations = [];
        const remainingCandidates = [];
        const selectedIds = new Set(state.selectedCandidateIds);

        candidates.forEach(candidate => {
            if (selectedIds.has(candidate.id)) {
                const newAnnotation = annotationFromCandidate(state, candidate, className, clampBboxToImage);
                if (!newAnnotation) return;
                newAnnotations.push(newAnnotation);
                batch.convertedAnnotations.push(newAnnotation);
                batch.originalCandidates.push(candidate);
            } else {
                remainingCandidates.push(candidate);
            }
        });

        if (batch.convertedAnnotations.length > 0) {
            history.push(batch);
        }

        annotations.push(...newAnnotations);
        state.selectedCandidateIds.clear();

        return { count: newAnnotations.length, remainingCandidates };
    }

    function relabelSelectedAnnotations(annotations, selectedAnnotationIds, history, className) {
        if (selectedAnnotationIds.size === 0) return 0;

        const changes = [];
        annotations.forEach(annotation => {
            if (!selectedAnnotationIds.has(annotation.id) || annotation.class === className) return;

            changes.push({
                id: annotation.id,
                oldClass: annotation.class,
                newClass: className
            });
            annotation.class = className;
        });

        if (changes.length > 0) {
            history.push({ type: 'relabel_annotations', changes });
        }

        return changes.length;
    }

    function undoLastBatch(annotations, candidates, history) {
        if (history.length === 0) return null;

        const lastBatch = history.pop();

        if (lastBatch.type === 'relabel_annotations') {
            const changesById = new Map(lastBatch.changes.map(change => [change.id, change]));
            annotations.forEach(annotation => {
                const change = changesById.get(annotation.id);
                if (change) annotation.class = change.oldClass;
            });
            return `Reverted relabeling for ${lastBatch.changes.length} annotations.`;
        }

        if (lastBatch.type === 'geometry_edit') {
            const changesById = new Map(lastBatch.changes.map(change => [change.id, change]));
            annotations.forEach(annotation => {
                const change = changesById.get(annotation.id);
                if (change) {
                    annotation.bbox = change.oldBbox.slice();
                    restoreMaskGeometry(annotation, change.oldMaskGeometry);
                }
            });
            return `Reverted box edit for ${lastBatch.changes.length} annotations.`;
        }

        const idsToRevert = new Set(lastBatch.convertedAnnotations.map(annotation => annotation.id));
        for (let index = annotations.length - 1; index >= 0; index--) {
            if (idsToRevert.has(annotations[index].id)) {
                annotations.splice(index, 1);
            }
        }
        candidates.push(...lastBatch.originalCandidates);
        return `Reverted last batch of ${lastBatch.originalCandidates.length} annotations.`;
    }

    function deleteAnnotationById(annotations, candidates, history, selectedAnnotationIds, idToDelete) {
        if (idToDelete === null) return null;

        const annotationIndex = annotations.findIndex(annotation => annotation.id === idToDelete);
        if (annotationIndex === -1) return null;

        const deletedAnnotation = annotations[annotationIndex];
        annotations.splice(annotationIndex, 1);

        if (deletedAnnotation.type === 'sam_final') {
            for (const batch of history) {
                if (batch.type !== 'convert_candidates' || !Array.isArray(batch.originalCandidates)) continue;

                const originalCandidate = batch.originalCandidates.find(candidate => (
                    candidate.id === deletedAnnotation.originalCandidateId
                ));

                if (originalCandidate) {
                    candidates.push(originalCandidate);
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

        selectedAnnotationIds.delete(idToDelete);
        return deletedAnnotation;
    }

    function normalizeAnnotation(state, annotation, imageRecord, clampBboxToImage) {
        if (!annotation || !Array.isArray(annotation.bbox) || annotation.bbox.length !== 4) return null;

        const bbox = clampBboxToImage(annotation.bbox, imageRecord);
        if (!bbox) return null;

        const existingId = Number(annotation.id);
        return {
            id: Number.isInteger(existingId) && existingId > 0 ? existingId : ++state.annotationCounter,
            bbox,
            class: String(annotation.class || 'Unlabeled').trim() || 'Unlabeled',
            type: annotation.type || 'loaded',
            ...annotationMaskMetadata(annotation)
        };
    }

    function selectedAnnotations(annotations, selectedAnnotationIds) {
        return annotations.filter(annotation => selectedAnnotationIds.has(annotation.id));
    }

    function countAnnotationsWithClass(annotationsByImage, className) {
        let count = 0;
        for (const annotations of annotationsByImage.values()) {
            count += annotations.filter(annotation => annotation.class === className).length;
        }
        return count;
    }

    function countOtherImageAnnotationsWithClass(annotationsByImage, currentImageId, className) {
        let count = 0;
        for (const [imageId, annotations] of annotationsByImage.entries()) {
            if (imageId === currentImageId) continue;
            count += annotations.filter(annotation => annotation.class === className).length;
        }
        return count;
    }

    function renameAnnotationClass(annotationsByImage, dirtyImages, oldName, newName) {
        let changedCount = 0;

        for (const [imageId, annotations] of annotationsByImage.entries()) {
            let imageChanged = false;
            annotations.forEach(annotation => {
                if (annotation.class === oldName) {
                    annotation.class = newName;
                    changedCount++;
                    imageChanged = true;
                }
            });

            if (imageChanged) {
                dirtyImages.add(imageId);
            }
        }

        return changedCount;
    }

    function deleteAnnotationsWithClass(annotations, className) {
        const remainingAnnotations = annotations.filter(annotation => annotation.class !== className);
        return {
            deletedCount: annotations.length - remainingAnnotations.length,
            remainingAnnotations
        };
    }

    window.SAM2AnnotationController = {
        annotationFromCandidate,
        convertSelectedCandidates,
        relabelSelectedAnnotations,
        invalidateMaskGeometryForChanges,
        undoLastBatch,
        deleteAnnotationById,
        normalizeAnnotation,
        selectedAnnotations,
        countAnnotationsWithClass,
        countOtherImageAnnotationsWithClass,
        renameAnnotationClass,
        deleteAnnotationsWithClass
    };
})();
