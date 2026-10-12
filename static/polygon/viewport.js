(() => {
    function create({ svg, stage, camera, byId, getContext, setZoom, setSuppressClick, render }) {
        const interaction = window.SAM2CanvasInteractionController;
        let panPointer = null, panOrigin = null, panMoved = false;
        function imagePoint(event) {
            const point = svg.createSVGPoint(); point.x = event.clientX; point.y = event.clientY;
            const world = point.matrixTransform(svg.getScreenCTM().inverse());
            return [world.x, world.y];
        }
        function fitZoom() {
            const { state, zoom } = getContext();
            if (!state) return;
            const stage = svg.parentElement;
            const { width, height } = state.document.image;
            const fitWidth = Math.min(stage.clientWidth, width * stage.clientHeight / height);
            svg.style.width = `${fitWidth * zoom / 100}px`;
        }
        function applyPan() {
            svg.style.transform = `translate(${camera.cameraOffset.x}px, ${camera.cameraOffset.y}px)`;
        }
        function resetPan() {
            camera.cameraOffset = { x: 0, y: 0 };
            applyPan();
        }
        function endPan(cancelled = false) {
            if (!camera.isPanning) return;
            const pointer = panPointer;
            interaction.finishPanning(camera);
            panPointer = null;
            if (cancelled) camera.cameraOffset = panOrigin;
            applyPan();
            setSuppressClick(panPointerButton === 0 && (panMoved || cancelled));
            if (svg.hasPointerCapture(pointer)) svg.releasePointerCapture(pointer);
            if (!getContext().disposed) render();
        }
        let panPointerButton = 0;

        function bindPanning() {
            stage.onpointerdown = event => {
                const { state, busy, drag, draft, promptSession, localCorrection } = getContext();
                const middle = event.button === 1;
                if ((promptSession || localCorrection) && !middle) return;
                if (event.altKey) return;
                if (!state || busy || drag || camera.isPanning || (!middle && (draft !== null || event.button !== 0))) return;
                // Match detection: annotation controls take priority over background panning.
                if (!middle && ![stage, svg, byId('Image')].includes(event.target)) return;
                setSuppressClick(false); panMoved = false;
                panPointer = event.pointerId; panPointerButton = event.button;
                panOrigin = { ...camera.cameraOffset };
                interaction.beginPanning(camera, { x: event.clientX, y: event.clientY });
                svg.setPointerCapture(event.pointerId);
                event.preventDefault(); render();
            };
            stage.onpointermove = event => {
                if (!camera.isPanning || event.pointerId !== panPointer) return;
                const { x, y } = camera.cameraOffset;
                interaction.updatePanning(camera, { x: event.clientX, y: event.clientY });
                panMoved ||= Math.hypot(camera.cameraOffset.x - x, camera.cameraOffset.y - y) > 0;
                applyPan();
            };
            stage.onpointerup = event => {
                if (camera.isPanning && event.pointerId === panPointer) {
                    stage.onpointermove(event); endPan();
                }
            };
            stage.onpointercancel = event => { if (event.pointerId === panPointer) endPan(true); };
            stage.onlostpointercapture = event => { if (event.pointerId === panPointer) endPan(); };
        }
        function unbindPanning() {
            stage.onpointerdown = stage.onpointermove = stage.onpointerup = stage.onpointercancel = stage.onlostpointercapture = null;
        }
        function wheelZoom(event) {
            let { state, busy, drag, zoom } = getContext();
            if (!state) return;
            event.preventDefault();
            if (busy || drag || camera.isPanning) return;
            const stage = svg.parentElement;
            const before = svg.getBoundingClientRect();
            const x = (event.clientX - before.left) / before.width;
            const y = (event.clientY - before.top) / before.height;
            // Match detection's wheel sensitivity; normalize line/page wheel units.
            const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? stage.clientHeight : 1);
            const { SCROLL_SENSITIVITY, MAX_ZOOM } = window.SAM2FrontendConfig;
            zoom = Math.max(100, Math.min(MAX_ZOOM * 100, zoom * (1 - delta * SCROLL_SENSITIVITY)));
            setZoom(zoom);
            fitZoom();
            const after = svg.getBoundingClientRect();
            camera.cameraOffset.x -= after.left + x * after.width - event.clientX;
            camera.cameraOffset.y -= after.top + y * after.height - event.clientY;
            applyPan();
            byId('ZoomLabel').textContent = `${Math.round(zoom)}%`;
            render();
        }
        function bindWheel() { svg.parentElement.addEventListener('wheel', wheelZoom, { passive: false }); }
        function unbindWheel() { svg.parentElement.removeEventListener('wheel', wheelZoom); }
        return { imagePoint, fitZoom, resetPan, endPan, bindPanning, unbindPanning, bindWheel, unbindWheel };
    }
    window.SAM2PolygonViewport = { create };
})();
