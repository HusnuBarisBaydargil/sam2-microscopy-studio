(() => {
    function toggleManualMode(state) {
        state.isManualMode = !state.isManualMode;

        if (state.isManualMode) {
            state.isPanning = false;
        } else {
            state.isAwaitingChoice = false;
            state.choiceInfo = null;
        }

        return {
            enabled: state.isManualMode,
            cursor: state.isManualMode ? 'crosshair' : 'grab',
            status: state.isManualMode ? 'Manual Box mode enabled. Click and drag.' : 'Manual Box mode disabled.'
        };
    }

    function beginManualDrawing(state, screenPoint) {
        state.isDrawing = true;
        state.isAwaitingChoice = false;
        state.manualBoxStart = screenPoint;
    }

    function updateManualBox(state, currentPoint) {
        state.currentManualBox = {
            x: state.manualBoxStart.x,
            y: state.manualBoxStart.y,
            w: currentPoint.x - state.manualBoxStart.x,
            h: currentPoint.y - state.manualBoxStart.y
        };
        return state.currentManualBox;
    }

    function finishManualDrawing(state, minScreenSize = 5) {
        if (!(state.isDrawing && state.isManualMode && state.currentManualBox)) return false;

        state.isDrawing = false;
        if (
            Math.abs(state.currentManualBox.w) > minScreenSize
            && Math.abs(state.currentManualBox.h) > minScreenSize
        ) {
            state.isAwaitingChoice = true;
            return true;
        }

        state.currentManualBox = null;
        return false;
    }

    function beginPanning(state, point) {
        state.isPanning = true;
        state.lastPanPoint = { x: point.x, y: point.y };
    }

    function updatePanning(state, point) {
        state.cameraOffset.x += point.x - state.lastPanPoint.x;
        state.cameraOffset.y += point.y - state.lastPanPoint.y;
        state.lastPanPoint = { x: point.x, y: point.y };
    }

    function finishPanning(state) {
        state.isPanning = false;
        return state.isManualMode ? 'crosshair' : 'grab';
    }

    function startBoxEdit(state, mode, worldPoint, annotationIds, findAnnotationById, handle = null) {
        state.boxEditMode = mode;
        state.boxEditHandle = handle;
        state.boxEditStartWorld = { ...worldPoint };
        state.boxEditOriginalBboxes = new Map();

        annotationIds.forEach(id => {
            const annotation = findAnnotationById(id);
            if (annotation) {
                state.boxEditOriginalBboxes.set(id, annotation.bbox.slice());
            }
        });
    }

    function updateBoxEdit(state, worldPoint, findAnnotationById, geometry) {
        const dx = worldPoint.x - state.boxEditStartWorld.x;
        const dy = worldPoint.y - state.boxEditStartWorld.y;

        for (const [id, originalBbox] of state.boxEditOriginalBboxes.entries()) {
            const annotation = findAnnotationById(id);
            if (!annotation) continue;

            if (state.boxEditMode === 'move') {
                annotation.bbox = geometry.clampMovedBboxToImage([
                    originalBbox[0] + dx,
                    originalBbox[1] + dy,
                    originalBbox[2],
                    originalBbox[3]
                ]) || annotation.bbox;
            } else if (state.boxEditMode === 'resize') {
                annotation.bbox = geometry.clampBboxToImage(
                    geometry.resizeBbox(originalBbox, state.boxEditHandle, dx, dy)
                ) || annotation.bbox;
            }
        }
    }

    function clearBoxEditState(state) {
        state.boxEditMode = null;
        state.boxEditHandle = null;
        state.boxEditStartWorld = null;
        state.boxEditOriginalBboxes = new Map();
    }

    function commitBoxEdit(state, findAnnotationById, bboxesEqual) {
        const changes = [];

        for (const [id, oldBbox] of state.boxEditOriginalBboxes.entries()) {
            const annotation = findAnnotationById(id);
            if (!annotation) continue;

            const newBbox = annotation.bbox.slice();
            if (!bboxesEqual(oldBbox, newBbox)) {
                changes.push({ id, oldBbox, newBbox });
            }
        }

        clearBoxEditState(state);
        return changes;
    }

    function cancelBoxEdit(state, findAnnotationById) {
        for (const [id, oldBbox] of state.boxEditOriginalBboxes.entries()) {
            const annotation = findAnnotationById(id);
            if (annotation) annotation.bbox = oldBbox.slice();
        }

        clearBoxEditState(state);
        return state.isManualMode ? 'crosshair' : 'grab';
    }

    function nudgeSelectedAnnotations(annotations, selectedAnnotationIds, dx, dy, geometry) {
        const changes = [];
        annotations.forEach(annotation => {
            if (!selectedAnnotationIds.has(annotation.id)) return;

            const oldBbox = annotation.bbox.slice();
            const newBbox = geometry.clampMovedBboxToImage([
                oldBbox[0] + dx,
                oldBbox[1] + dy,
                oldBbox[2],
                oldBbox[3]
            ]) || oldBbox.slice();
            if (geometry.bboxesEqual(oldBbox, newBbox)) return;
            annotation.bbox = newBbox;
            changes.push({ id: annotation.id, oldBbox, newBbox: newBbox.slice() });
        });

        return changes;
    }

    function zoomState(state, newZoom, mousePos, geometryZoomState) {
        const nextCamera = geometryZoomState(newZoom, mousePos, state.cameraOffset, state.cameraZoom);
        state.cameraZoom = nextCamera.zoom;
        state.cameraOffset = nextCamera.offset;
        return nextCamera;
    }

    function setupChoiceButtons(state, canvasSize, classes, newClassAction) {
        const box = state.currentManualBox;
        const buttonWidth = 96;
        const buttonHeight = 30;
        const padding = 8;
        const choices = [
            ...classes.map(cls => ({
                label: cls.name,
                action: cls.name,
                color: cls.color
            })),
            { label: '+ Class', action: newClassAction, color: '#2563eb' },
            { label: 'Cancel', action: 'Cancel', color: '#4a4a4a' }
        ];
        const maxColumns = Math.max(1, Math.floor((canvasSize.width + padding) / (buttonWidth + padding)));
        const columns = Math.min(choices.length, maxColumns);
        const rows = Math.ceil(choices.length / columns);
        const totalWidth = columns * buttonWidth + (columns - 1) * padding;
        const totalHeight = rows * buttonHeight + (rows - 1) * padding;
        const startX = Math.max(0, Math.min(box.x, canvasSize.width - totalWidth));
        const preferredY = box.h >= 0 ? box.y + box.h + padding : box.y + padding;
        const fallbackY = box.h >= 0 ? box.y - totalHeight - padding : box.y + box.h - totalHeight - padding;
        const startY = Math.max(
            0,
            Math.min(
                preferredY + totalHeight <= canvasSize.height ? preferredY : fallbackY,
                canvasSize.height - totalHeight
            )
        );

        state.choiceInfo = {
            rect: { ...box },
            buttons: choices.map((choice, index) => ({
                ...choice,
                x: startX + (index % columns) * (buttonWidth + padding),
                y: startY + Math.floor(index / columns) * (buttonHeight + padding),
                w: buttonWidth,
                h: buttonHeight
            }))
        };
        state.currentManualBox = null;
        return state.choiceInfo;
    }

    function buildManualAnnotation(state, className, getWorldPoint, clampBboxToImage) {
        if (!state.choiceInfo) return { annotation: null, error: null };

        const screenBox = state.choiceInfo.rect;
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
            return { annotation: null, error: 'Invalid box dimensions.' };
        }

        const clampedBbox = clampBboxToImage([worldBox.x, worldBox.y, worldBox.w, worldBox.h]);
        if (!clampedBbox) {
            return { annotation: null, error: 'Box is outside the image bounds.' };
        }

        state.annotationCounter++;
        return {
            annotation: {
                id: state.annotationCounter,
                bbox: clampedBbox,
                class: className,
                type: 'manual'
            },
            error: null
        };
    }

    function closeManualChoice(state) {
        state.isAwaitingChoice = false;
        state.choiceInfo = null;
    }

    window.SAM2CanvasInteractionController = {
        toggleManualMode,
        beginManualDrawing,
        updateManualBox,
        finishManualDrawing,
        beginPanning,
        updatePanning,
        finishPanning,
        startBoxEdit,
        updateBoxEdit,
        commitBoxEdit,
        cancelBoxEdit,
        nudgeSelectedAnnotations,
        zoomState,
        setupChoiceButtons,
        buildManualAnnotation,
        closeManualChoice
    };
})();
