(() => {
    const frontendConfig = window.SAM2FrontendConfig;
    const canvasGeometry = window.SAM2CanvasGeometry;
    if (!frontendConfig) {
        throw new Error('SAM2FrontendConfig must be loaded before canvasRenderer.js.');
    }
    if (!canvasGeometry) {
        throw new Error('SAM2CanvasGeometry must be loaded before canvasRenderer.js.');
    }

    const {
        OVERLAY_COLORS,
        BOX_HANDLE_SCREEN_SIZE
    } = frontendConfig;

    function drawScene(ctx, canvas, state) {
        const {
            imageToDraw,
            cameraOffset,
            cameraZoom,
            candidates,
            selectedCandidateIds,
            annotations,
            selectedAnnotationIds,
            isDrawing,
            currentManualBox,
            isAwaitingChoice,
            choiceInfo,
            zoomLevelDisplay,
            getClassColor
        } = state;

        ctx.fillStyle = '#111';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        if (!imageToDraw) return;

        ctx.save();
        ctx.translate(cameraOffset.x, cameraOffset.y);
        ctx.scale(cameraZoom, cameraZoom);
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(imageToDraw, 0, 0);

        candidates.forEach(candidate => {
            drawCandidateOverlay(ctx, candidate, selectedCandidateIds.has(candidate.id), cameraZoom);
        });

        annotations.forEach(annotation => {
            drawAnnotationOverlay(
                ctx,
                annotation,
                selectedAnnotationIds.has(annotation.id),
                cameraZoom,
                getClassColor(annotation.class)
            );
        });

        ctx.restore();

        if (isDrawing && currentManualBox) {
            strokeScreenRect(ctx, currentManualBox, OVERLAY_COLORS.contrastStroke, 4, [7, 5]);
            strokeScreenRect(ctx, currentManualBox, OVERLAY_COLORS.manualBox, 2, [7, 5]);
        }

        if (isAwaitingChoice && choiceInfo) {
            strokeScreenRect(ctx, choiceInfo.rect, OVERLAY_COLORS.selectedHalo, 4);
            strokeScreenRect(ctx, choiceInfo.rect, OVERLAY_COLORS.manualBox, 2);

            choiceInfo.buttons.forEach(button => {
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
            zoomLevelDisplay.textContent = `${Math.round(cameraZoom * 100)}%`;
        }
    }

    function strokeCandidateShape(ctx, candidate) {
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

    function drawCandidateOverlay(ctx, candidate, isSelected, cameraZoom) {
        const lineWidth = screenUnits(isSelected ? 2.5 : 1.75, cameraZoom);
        const dash = [screenUnits(7, cameraZoom), screenUnits(5, cameraZoom)];

        ctx.save();
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.setLineDash(dash);

        ctx.strokeStyle = isSelected ? OVERLAY_COLORS.selectedHalo : OVERLAY_COLORS.contrastStroke;
        ctx.lineWidth = lineWidth + screenUnits(isSelected ? 4 : 2.5, cameraZoom);
        ctx.globalAlpha = isSelected ? 0.95 : 0.72;
        strokeCandidateShape(ctx, candidate);

        ctx.strokeStyle = OVERLAY_COLORS.candidate;
        ctx.lineWidth = lineWidth;
        ctx.globalAlpha = isSelected ? 1 : 0.9;
        strokeCandidateShape(ctx, candidate);

        ctx.restore();
    }

    function drawAnnotationOverlay(ctx, annotation, isHighlighted, cameraZoom, classColor) {
        const [x, y, w, h] = annotation.bbox;

        ctx.save();
        ctx.setLineDash([]);
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';

        ctx.strokeStyle = isHighlighted ? OVERLAY_COLORS.selectedHalo : OVERLAY_COLORS.contrastStroke;
        ctx.lineWidth = screenUnits(isHighlighted ? 6 : 5, cameraZoom);
        ctx.globalAlpha = isHighlighted ? 0.98 : 0.68;
        ctx.strokeRect(x, y, w, h);

        ctx.strokeStyle = classColor;
        ctx.lineWidth = screenUnits(isHighlighted ? 3 : 2.75, cameraZoom);
        ctx.globalAlpha = 1;
        ctx.strokeRect(x, y, w, h);

        drawAnnotationLabel(ctx, annotation, x, y, classColor, cameraZoom);
        ctx.restore();

        if (isHighlighted) {
            drawAnnotationHandles(ctx, annotation, cameraZoom);
        }
    }

    function drawAnnotationLabel(ctx, annotation, x, y, classColor, cameraZoom) {
        const label = `#${annotation.id}`;
        const fontSize = screenUnits(13, cameraZoom);
        const paddingX = screenUnits(5, cameraZoom);
        const paddingY = screenUnits(3, cameraZoom);
        const gap = screenUnits(4, cameraZoom);

        ctx.font = `600 ${fontSize}px system-ui, sans-serif`;
        ctx.textBaseline = 'middle';
        const labelWidth = ctx.measureText(label).width + paddingX * 2;
        const labelHeight = fontSize + paddingY * 2;
        const labelX = x;
        const labelY = y > labelHeight + gap ? y - labelHeight - gap : y + gap;

        ctx.fillStyle = OVERLAY_COLORS.labelBackground;
        ctx.fillRect(labelX, labelY, labelWidth, labelHeight);
        ctx.strokeStyle = OVERLAY_COLORS.labelBorder;
        ctx.lineWidth = screenUnits(1, cameraZoom);
        ctx.strokeRect(labelX, labelY, labelWidth, labelHeight);
        ctx.fillStyle = classColor;
        ctx.fillRect(labelX, labelY, screenUnits(3, cameraZoom), labelHeight);
        ctx.fillStyle = OVERLAY_COLORS.labelText;
        ctx.fillText(label, labelX + paddingX + screenUnits(2, cameraZoom), labelY + labelHeight / 2);
    }

    function strokeScreenRect(ctx, rect, color, width, dash = []) {
        ctx.save();
        ctx.setLineDash(dash);
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.strokeRect(rect.x, rect.y, rect.w, rect.h);
        ctx.restore();
    }

    function drawAnnotationHandles(ctx, annotation, cameraZoom) {
        const handleSize = BOX_HANDLE_SCREEN_SIZE / cameraZoom;
        const half = handleSize / 2;
        const handles = canvasGeometry.annotationHandles(annotation);

        ctx.save();
        ctx.fillStyle = '#ffffff';
        ctx.strokeStyle = '#111111';
        ctx.lineWidth = 1 / cameraZoom;

        Object.values(handles).forEach(point => {
            ctx.fillRect(point.x - half, point.y - half, handleSize, handleSize);
            ctx.strokeRect(point.x - half, point.y - half, handleSize, handleSize);
        });

        ctx.restore();
    }

    function screenUnits(value, cameraZoom) {
        return canvasGeometry.screenUnits(value, cameraZoom);
    }

    window.SAM2CanvasRenderer = {
        drawScene,
        strokeCandidateShape,
        drawCandidateOverlay,
        drawAnnotationOverlay,
        drawAnnotationLabel,
        strokeScreenRect,
        drawAnnotationHandles
    };
})();
