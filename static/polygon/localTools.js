(() => {
    // Owns only the uncommitted redraw/cut session. The editor owns committed history and saves.
    function create({ byId, svg, getContext, setSelected, clearLabelPicker, applyView,
        imagePoint, request, operate, saveChanges, render, message, drawElement, drawGeometry }) {
        const { correctedBoundary } = window.SAM2PolygonGeometry;
        let localCorrection = null;
        function startLocalCorrection(mode) {
            const { state, selected, view, proposalSelection } = getContext();
            if (byId(mode === 'split' ? 'ManualSplit' : 'LocalCorrect').disabled) return;
            const object = state.document.annotations.find(item => item.id === selected);
            localCorrection = { objectId: object.id, original: structuredClone(object.geometry.points), start: null, end: null,
                points: [], hover: null, otherSide: false, showOriginal: false, mode };
            view.ShowObjects = true; applyView(); clearLabelPicker(); proposalSelection.clear(); message(''); render();
        }
        byId('LocalCorrect').onclick = () => startLocalCorrection('redraw');
        byId('ManualSplit').onclick = () => startLocalCorrection('split');
        function boundaryAnchor(point) {
            let nearest = null;
            const points = localCorrection.original;
            for (const [edge, a] of points.entries()) {
                const b = points[(edge + 1) % points.length], dx = b[0] - a[0], dy = b[1] - a[1];
                const t = Math.max(0, Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy)));
                const projected = t === 0 ? a : t === 1 ? b : [a[0] + t * dx, a[1] + t * dy];
                const distance = Math.hypot(projected[0] - point[0], projected[1] - point[1]);
                if (!nearest || distance < nearest.distance) nearest = { edge: t === 1 ? (edge + 1) % points.length : edge,
                    t: t === 1 ? 0 : t, point: projected, distance };
            }
            const scale = Math.hypot(svg.getScreenCTM().a, svg.getScreenCTM().b);
            return nearest.distance * scale <= 12 ? nearest : null;
        }
        function addLocalPoint(event) {
            const { state, busy, camera } = getContext();
            if (busy || camera.isPanning) return;
            const point = imagePoint(event);
            const { width, height } = state.document.image;
            if (point[0] < 0 || point[1] < 0 || point[0] > width || point[1] > height) return;
            if (!localCorrection.end) {
                const anchor = boundaryAnchor(point);
                if (!anchor) { message('Choose a point on the selected outline.', true); return; }
                if (!localCorrection.start) localCorrection.start = anchor;
                else if (anchor.point[0] === localCorrection.start.point[0] && anchor.point[1] === localCorrection.start.point[1]) {
                    message('Choose a different end point on the outline.', true); return;
                } else localCorrection.end = anchor;
            } else {
                const limit = localCorrection.mode === 'split' ? 510 : 512;
                if (localCorrection.points.length >= limit) { message(`Maximum ${limit} ${localCorrection.mode === 'split' ? 'cut' : 'replacement'} points reached. Undo a point before continuing.`, true); return; }
                localCorrection.points.push(point);
            }
            localCorrection.hover = null; localCorrection.showOriginal = false; message(''); render();
        }
        byId('LocalUndo').onclick = () => {
            if (!localCorrection) return;
            if (localCorrection.points.length) localCorrection.points.pop();
            else if (localCorrection.end) { localCorrection.end = null; localCorrection.otherSide = false; }
            else { localCorrection.start = null; localCorrection.otherSide = false; }
            localCorrection.hover = null; localCorrection.showOriginal = false; message(''); render();
        };
        byId('LocalSide').onclick = () => { localCorrection.otherSide = !localCorrection.otherSide; localCorrection.showOriginal = false; message(''); render(); };
        byId('LocalCompare').onclick = () => { localCorrection.showOriginal = !localCorrection.showOriginal; render(); };
        byId('LocalCancel').onclick = () => { localCorrection = null; message(''); render(); };
        byId('LocalApply').onclick = () => operate(async () => {
            const session = localCorrection;
            if (!session?.end) return;
            const document = structuredClone(getContext().state.document);
            const object = document.annotations.find(item => item.id === session.objectId);
            if (session.mode === 'split') {
                const result = await request('api/project/segmentation', { action: 'manual_split_preview', image: document.image,
                    geometry: { type: 'polygon', points: session.original }, points: session.points,
                    start: { edge: session.start.edge, t: session.start.t }, end: { edge: session.end.edge, t: session.end.t } });
                if (getContext().disposed || localCorrection !== session) return;
                if (!Array.isArray(result.geometries) || result.geometries.length !== 2) throw new Error('The cut must produce exactly two outlines.');
                document.annotations = document.annotations.filter(item => item.id !== object.id);
                for (const geometry of result.geometries) document.annotations.push({ id: document.next_object_id++, class_id: object.class_id,
                    source: 'manual', edited: true, geometry });
            } else {
                const correction = correctedBoundary(session.original, session.start, session.end, session.points, session.otherSide);
                object.geometry.points = structuredClone(correction.points); object.edited = true;
            }
            const validated = await request('api/project/segmentation', { action: 'validate', image: document.image, document });
            if (getContext().disposed || localCorrection !== session) return;
            getContext().state.change(validated.document.annotations, validated.document.next_object_id);
            if (session.mode === 'split') setSelected(null);
            localCorrection = null; message('');
            await saveChanges();
        });

        function renderControls({ editable, draft, selectedObject, folderLoadFailed }) {
            const { busy, camera } = getContext();
            byId('LocalCorrect').hidden = !selectedObject;
            byId('LocalCorrect').disabled = !editable || draft !== null || selectedObject?.geometry.type !== 'polygon' || folderLoadFailed;
            byId('LocalCorrect').title = selectedObject?.geometry.type === 'polygon' ? 'Choose two boundary anchors, then draw a replacement edge' : 'Redraw edge requires a polygon outline';
            byId('ManualSplit').hidden = !selectedObject;
            byId('ManualSplit').disabled = byId('LocalCorrect').disabled;
            byId('ManualSplit').title = selectedObject?.geometry.type === 'polygon' ? 'Choose two boundary anchors, then draw the cut; no SAM2 required' : 'Cut line requires a polygon outline';
            byId('LocalBar').hidden = !localCorrection;
            byId('LocalBar').setAttribute('aria-label', localCorrection?.mode === 'split' ? 'Manual cut-line split' : 'Local boundary correction');
            byId('LocalUndo').disabled = busy || camera.isPanning || !localCorrection?.start;
            byId('LocalUndo').title = `Undo the last ${localCorrection?.mode === 'split' ? 'cut' : 'replacement'} point or anchor (Ctrl+Z)`;
            byId('LocalSide').disabled = busy || camera.isPanning || !localCorrection?.end;
            byId('LocalSide').hidden = localCorrection?.mode === 'split';
            byId('LocalSide').setAttribute('aria-pressed', String(Boolean(localCorrection?.otherSide)));
            byId('LocalCompare').disabled = busy || camera.isPanning || !localCorrection?.end;
            byId('LocalCompare').setAttribute('aria-pressed', String(Boolean(localCorrection?.showOriginal)));
            byId('LocalApply').disabled = busy || camera.isPanning || !localCorrection?.end;
            byId('LocalApply').textContent = localCorrection?.mode === 'split' ? 'Apply split' : 'Apply edge';
            byId('LocalApply').title = localCorrection?.mode === 'split' ? 'Apply manual split (Enter)' : 'Apply this boundary replacement (Enter)';
            byId('LocalCancel').disabled = busy || camera.isPanning;
            byId('LocalCancel').title = localCorrection?.mode === 'split' ? 'Discard this cut (Escape)' : 'Discard this correction (Escape)';
            svg.setAttribute('data-local-correcting', String(Boolean(localCorrection)));
        }
        function renderPreview(promptLayer) {
            if (!localCorrection) return;
            const { original, start, end, points, hover, otherSide, showOriginal, mode } = localCorrection;
            const attrs = { fill: 'none', 'stroke-width': 3, 'vector-effect': 'non-scaling-stroke' };
            if (showOriginal || !end) drawGeometry('polygon', original, { ...attrs, stroke: '#ffffff', class: 'local-original' }, promptLayer);
            if (end && !showOriginal) {
                const correction = correctedBoundary(original, start, end, points, otherSide);
                if (mode === 'split') {
                    const opposite = correctedBoundary(original, start, end, points, !otherSide);
                    for (const [index, child] of [correction, opposite].entries()) drawGeometry('polygon', child.points, {
                        ...attrs, stroke: index ? '#70b7ff' : '#f6cb78', fill: index ? '#70b7ff' : '#f6cb78', 'fill-opacity': .12,
                        class: 'local-cut-preview', 'data-cut-piece': index + 1
                    }, promptLayer);
                    drawGeometry('polyline', correction.path, { ...attrs, stroke: '#ffffff', class: 'local-cut-line' }, promptLayer);
                } else {
                    drawGeometry('polygon', correction.points, { fill: '#f6cb78', 'fill-opacity': .08, stroke: 'none' }, promptLayer);
                    drawGeometry('polyline', correction.retained, { ...attrs, stroke: '#65c58b', class: 'local-retained' }, promptLayer);
                    drawGeometry('polyline', correction.removed, { ...attrs, stroke: '#ffffff', 'stroke-dasharray': '5 4', class: 'local-removed' }, promptLayer);
                    drawGeometry('polyline', correction.path, { ...attrs, stroke: '#f6cb78', class: 'local-replacement' }, promptLayer);
                }
                if (hover) drawGeometry('polyline', [points.at(-1) || start.point, hover, end.point], { ...attrs, stroke: '#f6cb78', 'stroke-width': 1, 'stroke-dasharray': '3 3' }, promptLayer);
            }
            const scale = Math.hypot(svg.getScreenCTM().a, svg.getScreenCTM().b);
            for (const [index, point] of [start?.point, end?.point, ...points, !end ? hover : null].entries()) {
                if (point) drawElement('circle', { cx: point[0], cy: point[1], r: 5 / scale,
                    fill: index < 2 ? '#101318' : '#f6cb78', stroke: '#f6cb78', 'stroke-width': 2,
                    'vector-effect': 'non-scaling-stroke', 'data-local-point': index }, promptLayer);
            }
        }
        function moveHover(event) {
            const { state } = getContext();
            const point = imagePoint(event), { width, height } = state.document.image;
            localCorrection.hover = localCorrection.end
                ? point[0] >= 0 && point[0] <= width && point[1] >= 0 && point[1] <= height ? point : null
                : boundaryAnchor(point)?.point || null;
            render();
        }
        function keyboard(event) {
            if (event.key === 'Escape') { event.preventDefault(); byId('LocalCancel').click(); }
            if (event.key === 'Enter') { event.preventDefault(); return byId('LocalApply').click(); }
            if (event.key === 'Backspace' || event.key === 'Delete' || (event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === 'z') {
                event.preventDefault(); byId('LocalUndo').click();
            }
            return;
        }
        return { get session() { return localCorrection; }, clear() { localCorrection = null; },
            addPoint: addLocalPoint, moveHover, keyboard, renderControls, renderPreview };
    }
    window.SAM2PolygonLocalTools = { create };
})();
