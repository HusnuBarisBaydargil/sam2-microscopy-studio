(() => {
    const frontendConfig = window.SAM2FrontendConfig;
    if (!frontendConfig) {
        throw new Error('SAM2FrontendConfig must be loaded before canvasGeometry.js.');
    }

    const {
        MAX_ZOOM,
        MIN_ZOOM,
        BOX_HANDLE_SCREEN_SIZE,
        MIN_BOX_SIZE
    } = frontendConfig;

    function arrowKeyDelta(key) {
        const deltas = {
            ArrowUp: { dx: 0, dy: -1 },
            ArrowDown: { dx: 0, dy: 1 },
            ArrowLeft: { dx: -1, dy: 0 },
            ArrowRight: { dx: 1, dy: 0 }
        };
        return deltas[key] || null;
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

    function clampBboxToImage(bbox, imageSize = null) {
        const normalized = normalizeRawBbox(bbox);
        if (!normalized) return null;
        if (!imageSize) return normalized;

        const [x, y, w, h] = normalized;
        const x1 = clampNumber(x, 0, imageSize.width);
        const y1 = clampNumber(y, 0, imageSize.height);
        const x2 = clampNumber(x + w, 0, imageSize.width);
        const y2 = clampNumber(y + h, 0, imageSize.height);

        if (x2 <= x1 || y2 <= y1) return null;
        return [x1, y1, x2 - x1, y2 - y1];
    }

    function clampMovedBboxToImage(bbox, imageSize = null) {
        const normalized = normalizeRawBbox(bbox);
        if (!normalized) return null;
        if (!imageSize) return normalized;

        const width = Math.min(normalized[2], imageSize.width);
        const height = Math.min(normalized[3], imageSize.height);
        return [
            clampNumber(normalized[0], 0, Math.max(0, imageSize.width - width)),
            clampNumber(normalized[1], 0, Math.max(0, imageSize.height - height)),
            width,
            height
        ];
    }

    function clampNumber(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function getResizeHandleAtPoint(annotation, worldPoint, cameraZoom) {
        const handleSize = BOX_HANDLE_SCREEN_SIZE / cameraZoom;
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

    function pointInsideCandidate(point, candidate, normalizeContour) {
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

    function fitImageToView(canvasSize, imageSize, padding = 0.95) {
        if (!imageSize || canvasSize.width < 1 || canvasSize.height < 1) return null;

        const canvasAspect = canvasSize.width / canvasSize.height;
        const imageAspect = imageSize.width / imageSize.height;
        const zoom = canvasAspect > imageAspect
            ? (canvasSize.height / imageSize.height) * padding
            : (canvasSize.width / imageSize.width) * padding;
        return {
            zoom,
            offset: {
                x: (canvasSize.width - imageSize.width * zoom) / 2,
                y: (canvasSize.height - imageSize.height * zoom) / 2
            }
        };
    }

    function screenPoint(clientX, clientY, canvasRect) {
        return { x: clientX - canvasRect.left, y: clientY - canvasRect.top };
    }

    function worldPoint(screenX, screenY, cameraOffset, cameraZoom) {
        return {
            x: (screenX - cameraOffset.x) / cameraZoom,
            y: (screenY - cameraOffset.y) / cameraZoom
        };
    }

    function pointInsideRect(point, rect) {
        return point.x >= rect.x
            && point.x <= rect.x + rect.w
            && point.y >= rect.y
            && point.y <= rect.y + rect.h;
    }

    function zoomState(newZoom, mousePos, cameraOffset, cameraZoom) {
        const worldPosBeforeZoom = worldPoint(mousePos.x, mousePos.y, cameraOffset, cameraZoom);
        const zoom = clampNumber(newZoom, MIN_ZOOM, MAX_ZOOM);
        return {
            zoom,
            offset: {
                x: mousePos.x - worldPosBeforeZoom.x * zoom,
                y: mousePos.y - worldPosBeforeZoom.y * zoom
            }
        };
    }

    function screenUnits(value, cameraZoom) {
        return value / cameraZoom;
    }

    window.SAM2CanvasGeometry = {
        arrowKeyDelta,
        resizeBbox,
        normalizeBboxFromPoints,
        normalizeRawBbox,
        clampBboxToImage,
        clampMovedBboxToImage,
        clampNumber,
        getResizeHandleAtPoint,
        annotationHandles,
        pointInsideCandidate,
        pointInsideBbox,
        pointInsidePolygon,
        cursorForHandle,
        bboxesEqual,
        fitImageToView,
        screenPoint,
        worldPoint,
        pointInsideRect,
        zoomState,
        screenUnits
    };
})();
