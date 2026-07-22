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

    function recordHistoryCommand(history, redoHistory, command) {
        history.push(command);
        redoHistory.splice(0, redoHistory.length);
        return command;
    }

    function groupHistoryCommands(history, startIndex, label = 'annotation update') {
        const commands = history.splice(startIndex);
        if (commands.length === 0) return null;
        if (commands.length === 1) {
            history.push(commands[0]);
            return commands[0];
        }
        const command = { type: 'compound', label, commands };
        history.push(command);
        return command;
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

    function convertSelectedCandidates(
        state,
        candidates,
        annotations,
        history,
        redoHistory,
        className,
        clampBboxToImage
    ) {
        if (state.selectedCandidateIds.size === 0) {
            return { count: 0, remainingCandidates: candidates };
        }

        const command = { type: 'convert_candidates', annotationRecords: [], candidateRecords: [] };
        const newAnnotations = [];
        const remainingCandidates = [];
        const selectedIds = new Set(state.selectedCandidateIds);

        candidates.forEach((candidate, candidateIndex) => {
            if (selectedIds.has(candidate.id)) {
                const newAnnotation = annotationFromCandidate(state, candidate, className, clampBboxToImage);
                if (!newAnnotation) return;
                newAnnotations.push(newAnnotation);
                command.annotationRecords.push({
                    item: newAnnotation,
                    index: annotations.length + newAnnotations.length - 1
                });
                command.candidateRecords.push({ item: candidate, index: candidateIndex });
            } else {
                remainingCandidates.push(candidate);
            }
        });

        if (command.annotationRecords.length > 0) {
            recordHistoryCommand(history, redoHistory, command);
        }

        annotations.push(...newAnnotations);
        state.selectedCandidateIds.clear();

        return { count: newAnnotations.length, remainingCandidates };
    }

    function relabelSelectedAnnotations(annotations, selectedAnnotationIds, history, redoHistory, className) {
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
            recordHistoryCommand(history, redoHistory, { type: 'relabel_annotations', changes });
        }

        return changes.length;
    }

    function removeRecordedItems(collection, records) {
        const ids = new Set(records.map(record => record.item.id));
        for (let index = collection.length - 1; index >= 0; index--) {
            if (ids.has(collection[index].id)) collection.splice(index, 1);
        }
    }

    function insertRecordedItems(collection, records) {
        [...records]
            .sort((left, right) => left.index - right.index)
            .forEach(record => {
                if (collection.some(item => item.id === record.item.id)) return;
                const insertionIndex = Math.max(0, Math.min(record.index, collection.length));
                collection.splice(insertionIndex, 0, record.item);
            });
    }

    function applyHistoryCommand(command, direction, annotations, candidates, classes) {
        const undo = direction === 'undo';
        if (command.type === 'compound') {
            const commands = undo ? [...command.commands].reverse() : command.commands;
            commands.forEach(child => applyHistoryCommand(child, direction, annotations, candidates, classes));
            return;
        }
        if (command.type === 'relabel_annotations') {
            const changesById = new Map(command.changes.map(change => [change.id, change]));
            annotations.forEach(annotation => {
                const change = changesById.get(annotation.id);
                if (change) annotation.class = undo ? change.oldClass : change.newClass;
            });
            return;
        }
        if (command.type === 'geometry_edit') {
            const changesById = new Map(command.changes.map(change => [change.id, change]));
            annotations.forEach(annotation => {
                const change = changesById.get(annotation.id);
                if (!change) return;
                annotation.bbox = (undo ? change.oldBbox : change.newBbox).slice();
                restoreMaskGeometry(annotation, undo ? change.oldMaskGeometry : null);
            });
            return;
        }
        if (command.type === 'convert_candidates') {
            if (undo) {
                removeRecordedItems(annotations, command.annotationRecords);
                insertRecordedItems(candidates, command.candidateRecords);
            } else {
                removeRecordedItems(candidates, command.candidateRecords);
                insertRecordedItems(annotations, command.annotationRecords);
            }
            return;
        }
        if (command.type === 'create_annotations') {
            if (undo) removeRecordedItems(annotations, command.annotationRecords);
            else insertRecordedItems(annotations, command.annotationRecords);
            return;
        }
        if (command.type === 'replace_annotations') {
            const removedRecords = undo ? command.afterRecords : command.beforeRecords;
            const insertedRecords = undo ? command.beforeRecords : command.afterRecords;
            removeRecordedItems(annotations, removedRecords);
            insertRecordedItems(annotations, insertedRecords);
            return;
        }
        if (command.type === 'delete_annotations') {
            if (undo) {
                removeRecordedItems(candidates, command.candidateRecords);
                insertRecordedItems(annotations, command.annotationRecords);
            } else {
                removeRecordedItems(annotations, command.annotationRecords);
                insertRecordedItems(candidates, command.candidateRecords);
            }
            return;
        }
        if (command.type === 'remove_class') {
            if (undo) {
                if (!classes.some(classInfo => classInfo.name === command.classRecord.item.name)) {
                    const index = Math.max(0, Math.min(command.classRecord.index, classes.length));
                    classes.splice(index, 0, command.classRecord.item);
                }
            } else {
                const index = classes.findIndex(classInfo => classInfo.name === command.classRecord.item.name);
                if (index >= 0) classes.splice(index, 1);
            }
        }
    }

    function historyCommandMessage(command, direction) {
        const prefix = direction === 'undo' ? 'Undid' : 'Redid';
        const annotationCount = count => `${count} annotation${count === 1 ? '' : 's'}`;
        if (command.type === 'compound') return `${prefix} ${command.label}.`;
        if (command.type === 'relabel_annotations') return `${prefix} relabeling ${annotationCount(command.changes.length)}.`;
        if (command.type === 'geometry_edit') return `${prefix} box edit for ${annotationCount(command.changes.length)}.`;
        if (command.type === 'convert_candidates') return `${prefix} acceptance of ${annotationCount(command.annotationRecords.length)}.`;
        if (command.type === 'create_annotations') return `${prefix} creation of ${annotationCount(command.annotationRecords.length)}.`;
        if (command.type === 'replace_annotations') return `${prefix} annotation import.`;
        if (command.type === 'delete_annotations') return `${prefix} deletion of ${annotationCount(command.annotationRecords.length)}.`;
        if (command.type === 'remove_class') return `${prefix} removal of class "${command.classRecord.item.name}".`;
        return `${prefix} annotation update.`;
    }

    function undoLastAction(annotations, candidates, history, redoHistory, classes = []) {
        if (history.length === 0) return null;
        const command = history.pop();
        applyHistoryCommand(command, 'undo', annotations, candidates, classes);
        redoHistory.push(command);
        return historyCommandMessage(command, 'undo');
    }

    function redoLastAction(annotations, candidates, history, redoHistory, classes = []) {
        if (redoHistory.length === 0) return null;
        const command = redoHistory.pop();
        applyHistoryCommand(command, 'redo', annotations, candidates, classes);
        history.push(command);
        return historyCommandMessage(command, 'redo');
    }

    function commandsInReverse(commands) {
        const flattened = [];
        [...commands].reverse().forEach(command => {
            if (command.type === 'compound') flattened.push(...commandsInReverse(command.commands));
            else flattened.push(command);
        });
        return flattened;
    }

    function originalCandidateForAnnotation(history, annotation) {
        if (!annotation.originalCandidateId) return null;
        for (const command of commandsInReverse(history)) {
            if (command.type !== 'convert_candidates') continue;
            const candidateRecord = command.candidateRecords.find(record => (
                record.item.id === annotation.originalCandidateId
            ));
            if (candidateRecord) return candidateRecord.item;
        }
        return null;
    }

    function deleteAnnotationsByIds(
        annotations,
        candidates,
        history,
        redoHistory,
        selectedAnnotationIds,
        idsToDelete
    ) {
        const targetIds = new Set(idsToDelete);
        const annotationRecords = annotations
            .map((annotation, index) => ({ item: annotation, index }))
            .filter(record => targetIds.has(record.item.id));
        if (annotationRecords.length === 0) return [];

        const candidateRecords = [];
        annotationRecords.forEach(record => {
            const candidate = originalCandidateForAnnotation(history, record.item);
            if (!candidate || candidates.some(item => item.id === candidate.id)) return;
            candidateRecords.push({ item: candidate, index: candidates.length + candidateRecords.length });
        });

        removeRecordedItems(annotations, annotationRecords);
        insertRecordedItems(candidates, candidateRecords);
        annotationRecords.forEach(record => selectedAnnotationIds.delete(record.item.id));
        recordHistoryCommand(history, redoHistory, {
            type: 'delete_annotations',
            annotationRecords,
            candidateRecords
        });
        return annotationRecords.map(record => record.item);
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
        recordHistoryCommand,
        groupHistoryCommands,
        undoLastAction,
        redoLastAction,
        deleteAnnotationsByIds,
        normalizeAnnotation,
        selectedAnnotations,
        countAnnotationsWithClass,
        countOtherImageAnnotationsWithClass,
        renameAnnotationClass,
        deleteAnnotationsWithClass
    };
})();
