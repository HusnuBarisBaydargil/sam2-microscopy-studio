(() => {
    const { createPolygonState } = window.SAM2PolygonState;
    const { geometryContains, duplicatePoints } = window.SAM2PolygonGeometry;
    const { matchFolderFiles } = window.SAM2PolygonPersistence;
    function mount(project, { phiSafeMode = true } = {}) {
        const root = document.getElementById('polygonEditor');
        const byId = name => document.getElementById(`polygon${name}`);
        const svg = byId('Canvas'), shapes = byId('Shapes');
        const stage = svg.parentElement;
        const camera = { cameraOffset: { x: 0, y: 0 }, isPanning: false, isManualMode: false };
        const ns = 'http://www.w3.org/2000/svg';
        let state = null, revision = null, selected = null, draft = null;
        let drawingTool = 'polygon', previewPoint = null, labelObject = null;
        const reservedHotkeys = ['b', 'u', '1', '2', '3'];
        const drawingTools = { Draw: 'polygon', Rectangle: 'rectangle', Circle: 'circle' };
        const requiredPoints = () => drawingTool === 'polygon' ? 3 : 2;
        let classes = project.classes.slice(), busy = false, queue = [], currentIndex = -1;
        let folderAnnotations = new Map();
        const imageReviews = new Map();
        let queueFilter = 'all', queueScan = null, queueRenderKey = '';
        const completedReview = status => status === 'reviewed' || status === 'confirmed_empty';
        const reviewStatus = document => document.review_status || (document.annotations.length ? 'in_progress' : 'unreviewed');
        const reviewLabels = { unchecked: 'Unchecked', unreviewed: 'Needs review', in_progress: 'In progress', reviewed: 'Reviewed', confirmed_empty: 'Confirmed empty', error: 'Load failed' };
        const imageLabel = (file, index) => phiSafeMode ? `Image ${index + 1}` : file.webkitRelativePath?.split('/').slice(1).join('/') || file.name;
        let folderLoadFailed = false;
        let zoom = 100;
        let drag = null, suppressClick = false;
        let saving = false, saveError = false;
        let originalPreview = null, activePreprocess = 'original', disposed = false;
        let appliedPreprocessParams = {}, proposalSelection = new Set();
        let proposalHover = null;
        let promptSession = null;
        let duplicateIssue = null;
        let badgeLayout = null, overlapCycle = null;
        const view = { ShowObjects: true, ShowSuggestions: true, ShowNumbers: true, OutlineOnly: true };
        const viewport = window.SAM2PolygonViewport.create({
            svg, stage, camera, byId,
            getContext: () => ({ state, busy, drag, draft, promptSession, localCorrection: localTools.session, disposed, zoom }),
            setZoom: value => { zoom = value; }, setSuppressClick: value => { suppressClick = value; }, render
        });
        const { imagePoint, fitZoom, resetPan, endPan } = viewport;
        function applyView() {
            for (const [key, value] of Object.entries(view)) {
                byId(key).checked = value;
                svg.setAttribute(`data-${key.toLowerCase()}`, String(value));
            }
        }
        for (const key of Object.keys(view)) byId(key).onchange = () => {
            view[key] = byId(key).checked;
            if (key === 'ShowObjects' && !view[key]) { selected = null; labelObject = null; }
            if (key === 'ShowSuggestions' && !view[key]) { proposalSelection.clear(); proposalHover = null; }
            applyView(); render();
        };
        function cycleOverlap(event) {
            if (!event.altKey || !state || busy || drag || draft !== null || localTools.session) return false;
            const point = imagePoint(event);
            const hits = [
                ...(view.ShowObjects ? state.document.annotations.map(item => ({ key: `object:${item.id}`, item, proposal: false })) : []),
                ...(view.ShowSuggestions ? state.proposals.map(item => ({ key: `proposal:${item.id}`, item, proposal: true })) : [])
            ].filter(hit => geometryContains(hit.item.geometry, point));
            if (!hits.length) return false;
            const key = hits.map(hit => hit.key).join(',');
            const index = overlapCycle?.key === key && Math.hypot(event.clientX - overlapCycle.x, event.clientY - overlapCycle.y) < 5 ? (overlapCycle.index + 1) % hits.length : 0;
            overlapCycle = { key, index, x: event.clientX, y: event.clientY };
            const hit = hits[index];
            if (hit.proposal) toggleProposal(hit.item.id);
            else { selected = hit.item.id; render(); }
            event.preventDefault();
            return true;
        }
        applyView();
        const proposalLayer = byId('Proposals'), badgeLayer = byId('ProposalBadges');
        const { PREPROCESS_METHODS, DEFAULT_PREPROCESS_PARAMS } = window.SAM2FrontendConfig;
        const preprocessInputs = [...byId('PreprocessParams').querySelectorAll('input[data-param]')];
        byId('PreprocessMethod').replaceChildren(...Object.entries(PREPROCESS_METHODS).map(([key, value]) => new Option(value.label, key)));
        function resetPreprocessSettings() {
            for (const input of preprocessInputs) input.value = String(DEFAULT_PREPROCESS_PARAMS[input.dataset.param]);
        }
        function showPreprocessSettings() {
            const method = byId('PreprocessMethod').value;
            for (const label of byId('PreprocessParams').querySelectorAll('[data-methods]')) {
                label.hidden = !label.dataset.methods.split(' ').includes(method);
            }
        }
        byId('PreprocessMethod').onchange = showPreprocessSettings;
        byId('PreprocessDefaults').onclick = resetPreprocessSettings;
        resetPreprocessSettings(); showPreprocessSettings();

        function message(text, important = false) {
            duplicateIssue = null;
            byId('Status').textContent = important ? text : '';
            byId('Status').hidden = !important;
        }
        function canLeave() {
            if (busy || drag || camera.isPanning) { message('Finish the current operation first.', true); return false; }
            return !(state?.dirty || draft?.length || localTools.session?.start || promptSession?.points.length || state?.proposals.length) || window.confirm('Discard unfinished work on this image?');
        }
        function beforeUnload(event) {
            if (busy || drag || state?.dirty || draft?.length || localTools.session?.start || promptSession?.points.length || state?.proposals.length) { event.preventDefault(); event.returnValue = ''; }
        }
        function rememberWorkspace() {
            if (disposed || !state || folderLoadFailed || !window.SAM2ProjectFolder?.remember) return;
            const resumeBar = document.getElementById('projectResumeBar');
            if (resumeBar) resumeBar.hidden = true;
            void window.SAM2ProjectFolder.remember(project.project_id, queue, queue[currentIndex], {
                identity: state.document.image.identity, filter: queueFilter
            });
        }
        window.addEventListener('beforeunload', beforeUnload);
        async function request(path, payload) {
            const response = await window.SAM2ApiClient.apiFetch(path, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'The operation failed.');
            return data;
        }
        async function operate(action) {
            if (busy || disposed) return;
            busy = true;
            render();
            try { await action(); } catch (error) { if (!disposed) message(error.message, true); }
            finally { busy = false; if (!disposed) render(); }
        }
        // Called inside operate: one save at a time, with editing/navigation locked
        // until the server acknowledges this document and its new revision.
        const saveChanges = window.SAM2PolygonPersistence.createSaveChanges({
            get state() { return state; }, get queue() { return queue; }, get currentIndex() { return currentIndex; },
            get folderLoadFailed() { return folderLoadFailed; },
            get revision() { return revision; }, set revision(value) { revision = value; },
            set saving(value) { saving = value; }, set saveError(value) { saveError = value; }
        }, { request, render, message });
        function renderQueue(locked) {
            if (state && currentIndex >= 0) imageReviews.set(queue[currentIndex], {
                status: reviewStatus(state.document), count: state.document.annotations.length,
                unsaved: state.dirty, error: folderLoadFailed
            });
            const completed = queue.filter(file => {
                const entry = imageReviews.get(file);
                return entry && !entry.unsaved && !entry.error && completedReview(entry.status);
            }).length;
            byId('ReviewProgress').max = queue.length || 1;
            byId('ReviewProgress').value = completed;
            byId('ReviewProgress').setAttribute('aria-busy', String(queueScan !== null));
            byId('ReviewCount').textContent = `${completed} / ${queue.length} reviewed`;
            byId('ReviewCount').title = queueScan ? 'Checking saved review states…' : 'Explicitly reviewed images, including confirmed empty images';
            for (const button of byId('QueueFilters').querySelectorAll('button')) {
                button.disabled = !queue.length;
                button.setAttribute('aria-pressed', String(button.dataset.filter === queueFilter));
            }
            const key = JSON.stringify([locked, currentIndex, queueFilter, queue.map((file, index) => [imageLabel(file, index), imageReviews.get(file)])]);
            if (key === queueRenderKey) return;
            queueRenderKey = key;
            byId('ImageQueue').replaceChildren();
            for (const [index, file] of queue.entries()) {
                const entry = imageReviews.get(file) || { status: 'unchecked' };
                const done = !entry.unsaved && !entry.error && completedReview(entry.status);
                if (queueFilter !== 'all' && (queueFilter === 'completed' ? !done : done)) continue;
                const button = document.createElement('button');
                button.type = 'button'; button.className = 'polygon-image-row'; button.disabled = locked;
                button.setAttribute('aria-current', String(index === currentIndex));
                button.setAttribute('data-review', entry.error ? 'error' : entry.unsaved ? 'in_progress' : entry.status);
                const name = document.createElement('span');
                name.textContent = imageLabel(file, index);
                const status = document.createElement('span');
                status.textContent = entry.error ? 'Load failed' : entry.unsaved ? 'Unsaved' : reviewLabels[entry.status];
                status.className = 'polygon-image-review';
                button.title = `${phiSafeMode ? name.textContent : file.webkitRelativePath || file.name} · ${status.textContent}${entry.count === undefined ? '' : ` · ${entry.count} object${entry.count === 1 ? '' : 's'}`}`;
                button.appendChild(name); button.appendChild(status);
                button.onclick = () => navigate(index);
                byId('ImageQueue').appendChild(button);
            }
            byId('QueueEmpty').hidden = byId('ImageQueue').children.length > 0 || !queue.length;
        }
        function nextReviewIndex() {
            return Array.from({ length: queue.length - 1 }, (_, offset) => (currentIndex + offset + 1) % queue.length)
                .find(index => {
                    const entry = imageReviews.get(queue[index]);
                    return !entry || entry.unsaved || entry.error || !completedReview(entry.status);
                });
        }
        async function scanQueue(files) {
            const scan = {}; queueScan = scan;
            try {
                for (const file of files) {
                    if (disposed || queue !== files || queueScan !== scan) return;
                    if (file === queue[currentIndex] || !window.SAM2ProjectFolder?.peek || !window.SAM2ProjectFolder.has(file)) continue;
                    const previousEntry = imageReviews.get(file);
                    try {
                        const text = await window.SAM2ProjectFolder.peek(file, file.name.replace(/\.[^.]+$/, '') + '.json');
                        let entry = { status: 'unreviewed', count: 0 };
                        if (text !== null) {
                            const raw = JSON.parse(text);
                            const hash = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
                            const identity = Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('');
                            entry = await request('api/project/segmentation', { action: 'inspect_labelme', image_name: file.name,
                                image: { identity, width: raw.imageWidth, height: raw.imageHeight }, labelme: raw });
                            entry.status = entry.review_status;
                        }
                        if (disposed || queue !== files || queueScan !== scan) return;
                        if (file !== queue[currentIndex] && imageReviews.get(file) === previousEntry) imageReviews.set(file, entry);
                    } catch (error) {
                        if (disposed || queue !== files || queueScan !== scan) return;
                        if (file !== queue[currentIndex] && imageReviews.get(file) === previousEntry) imageReviews.set(file, { status: 'error', error: true });
                    }
                    render();
                }
            } finally {
                if (queueScan === scan) { queueScan = null; if (!disposed) render(); }
            }
        }
        function drawElement(tag, attrs, layer = shapes) {
            const element = document.createElementNS(ns, tag);
            for (const [name, value] of Object.entries(attrs)) element.setAttribute(name, value);
            layer.appendChild(element);
            return element;
        }
        function drawGeometry(type, points, attributes, layer = shapes) {
            if (type === 'rectangle') {
                const [a, b] = points;
                return drawElement('rect', { x: Math.min(a[0], b[0]), y: Math.min(a[1], b[1]),
                    width: Math.abs(b[0] - a[0]), height: Math.abs(b[1] - a[1]), ...attributes }, layer);
            }
            if (type === 'circle') {
                const [a, b] = points;
                return drawElement('circle', { cx: a[0], cy: a[1], r: Math.hypot(b[0] - a[0], b[1] - a[1]), ...attributes }, layer);
            }
            return drawElement(type, { points: points.map(point => point.join(',')).join(' '), ...attributes }, layer);
        }
        function openLabelPicker(id, anchor) {
            if (busy || drag || camera.isPanning || draft !== null || promptSession || localTools.session) return;
            const bounds = anchor.getBoundingClientRect();
            view.ShowObjects = true; applyView();
            selected = id; labelObject = id; render();
            byId('LabelHeading').textContent = `Change class · #${id}`;
            byId('LabelChoices').replaceChildren();
            for (const cls of classes) {
                const choice = document.createElement('button');
                choice.type = 'button'; choice.className = 'btn btn-secondary';
                choice.textContent = cls.name; choice.style.borderLeft = `5px solid ${cls.color}`;
                choice.setAttribute('aria-pressed', String(state.document.annotations.find(item => item.id === id).class_id === cls.id));
                choice.onclick = () => {
                    labelObject = null;
                    return operate(async () => {
                        if (state.document.annotations.find(item => item.id === id).class_id !== cls.id) {
                            state.change(state.document.annotations.map(item => item.id === id ? { ...item, class_id: cls.id } : item));
                            await saveChanges();
                        }
                    });
                };
                byId('LabelChoices').appendChild(choice);
            }
            const picker = byId('LabelPicker');
            const size = picker.getBoundingClientRect();
            const margin = 8;
            picker.style.left = `${Math.max(margin, Math.min(bounds.left, window.innerWidth - size.width - margin))}px`;
            const below = bounds.bottom + margin;
            picker.style.top = `${Math.max(margin, Math.min(below + size.height <= window.innerHeight - margin ? below : bounds.top - size.height - margin, window.innerHeight - size.height - margin))}px`;
            byId('LabelClose').focus();
        }
        byId('LabelClose').onclick = () => { labelObject = null; render(); };
        function reportDuplicatePoints(points, objectId = null) {
            const indices = duplicatePoints(points);
            if (!indices.length) return false;
            const numbers = indices.map(index => index + 1).join(', ');
            message(objectId === null
                ? `Points ${numbers} overlap at the same location (highlighted in magenta). Drag a highlighted point with the left mouse button to move it, or right-click to remove it. To close the outline, press Enter instead of clicking the first point again.`
                : `Object #${objectId}: points ${numbers} would overlap (highlighted in magenta). The move was not saved. Drag a highlighted point to a different location.`, true);
            duplicateIssue = { objectId, points: structuredClone(points), indices };
            return true;
        }
        function render() {
            if (duplicateIssue && duplicateIssue.objectId !== null && duplicateIssue.objectId !== selected) message('');
            if (!drag && duplicateIssue?.objectId === null && JSON.stringify(draft) !== JSON.stringify(duplicateIssue.points)) {
                if (!draft || !reportDuplicatePoints(draft)) message('');
            }
            byId('LabelPicker').hidden = labelObject === null;
            const locked = busy || drag !== null || camera.isPanning || promptSession !== null || localTools.session !== null;
            stage.style.cursor = camera.isPanning ? 'grabbing' : draft !== null || promptSession || localTools.session ? 'crosshair' : 'grab';
            for (const control of root.querySelectorAll('button, input, select')) control.disabled = locked;
            const editable = Boolean(state) && !locked;
            const selectedObject = state?.document.annotations.find(item => item.id === selected);
            byId('SelectionActions').hidden = draft !== null || Boolean(promptSession || localTools.session) || (!selectedObject && !proposalSelection.size);
            byId('SelectionActions').setAttribute('aria-label', selectedObject ? 'Selected object actions' : 'Selected suggestion actions');
            byId('ModeState').textContent = localTools.session
                ? `${localTools.session.mode === 'split' ? 'Cut' : 'Redraw'} #${localTools.session.objectId} · ${!localTools.session.start ? 'choose start on outline' : !localTools.session.end ? 'choose end on outline' : localTools.session.mode === 'split' ? 'draw cut' : 'draw replacement'}`
                : promptSession
                ? promptSession.mode === 'split' ? 'Split' : promptSession.mode === 'merge' ? 'Merge' : promptSession.objectId != null ? `Correct #${promptSession.objectId}` : promptSession.proposalId != null ? 'Correct suggestion' : 'Click segment'
                : draft !== null ? `${drawingTool[0].toUpperCase() + drawingTool.slice(1)} · ${draft.length} points`
                : selectedObject ? `Object #${selectedObject.id}` : proposalSelection.size ? `${proposalSelection.size} suggestion${proposalSelection.size === 1 ? '' : 's'} selected` : 'Select';
            byId('ModeState').setAttribute('data-mode', promptSession || localTools.session ? 'prompt' : draft !== null ? 'draw' : selectedObject || proposalSelection.size ? 'selection' : 'select');
            localTools.renderControls({ editable, draft, selectedObject, folderLoadFailed });
            byId('Select').disabled = !editable || draft !== null;
            byId('Select').setAttribute('aria-pressed', String(draft === null && !promptSession));
            byId('PromptStart').disabled = !editable || draft !== null || !classes.length;
            byId('PromptStart').setAttribute('aria-pressed', String(Boolean(promptSession && !promptSession.mode && promptSession.objectId == null && promptSession.proposalId == null)));
            byId('Correct').disabled = !editable || draft !== null || !classes.length || !(selectedObject || proposalSelection.size === 1);
            byId('Split').disabled = !editable || draft !== null || !classes.length || !(selected !== null || proposalSelection.size === 1);
            byId('Merge').disabled = !editable || draft !== null || !classes.length || (proposalSelection.size ? proposalSelection.size < 2 : (state?.document.annotations.length || 0) < 2);
            byId('PromptBar').hidden = !promptSession;
            byId('PromptBar').setAttribute('aria-label', promptSession?.mode === 'merge' ? 'Merge objects' : promptSession?.mode === 'split' ? 'Split object' : 'Click-assisted SAM2');
            const mode = promptSession?.mode;
            byId('PromptHint').textContent = mode === 'split' ? 'Click once per cell' : mode === 'merge' ? 'Select objects to merge' : '';
            for (const id of ['PromptInclude', 'PromptExclude']) byId(id).hidden = mode === 'split' || mode === 'merge';
            byId('PromptUndo').hidden = mode === 'merge';
            const originals = promptSession?.mode === 'merge'
                ? mergeItems().filter(item => promptSession.mergeIds.includes(item.id)).map(item => item.geometry)
                : promptSession?.originalGeometry ? [promptSession.originalGeometry] : [];
            byId('PromptCompare').hidden = !originals.length;
            byId('PromptCompare').disabled = busy || !promptSession?.preview;
            byId('PromptCompare').setAttribute('aria-pressed', String(Boolean(promptSession?.showOriginal)));
            svg.setAttribute('data-original', String(Boolean(promptSession?.showOriginal)));
            svg.setAttribute('data-prompting', String(Boolean(promptSession)));
            for (const id of ['PromptInclude', 'PromptExclude', 'PromptClass']) byId(id).disabled = busy || !promptSession;
            byId('PromptCancel').disabled = !promptSession;
            byId('PromptUndo').disabled = busy || !promptSession?.points.length;
            byId('PromptAccept').disabled = busy || !promptSession?.preview || !classes.length;
            byId('PromptAccept').textContent = mode === 'split' ? `Accept split${promptSession.preview ? ` (${promptSession.preview.length})` : ''}` : mode === 'merge' ? 'Accept merge' : promptSession?.objectId != null ? 'Apply correction' : 'Accept preview';
            byId('PromptInclude').setAttribute('aria-pressed', String(promptSession?.label === 1));
            byId('PromptExclude').setAttribute('aria-pressed', String(promptSession?.label === 0));
            byId('Fit').disabled = !state || busy;
            byId('ImportLabelme').disabled = !editable || draft !== null;
            byId('ExportLabelme').disabled = !editable || draft !== null;
            byId('SamRun').disabled = !editable || draft !== null;
            byId('SamClearSuggestions').disabled = !editable || draft !== null || !state.proposals.length;
            byId('SamInfo').textContent = state?.proposals.length ? `${state.proposals.length} suggestion${state.proposals.length === 1 ? '' : 's'}` : '';
            byId('SamAccept').disabled = !editable || draft !== null || !classes.length || !proposalSelection.size;
            byId('SamReject').disabled = !editable || draft !== null || !proposalSelection.size;
            byId('SamClear').disabled = !editable || !proposalSelection.size;
            byId('SamAccept').textContent = proposalSelection.size ? `Accept ${proposalSelection.size} selected` : 'Accept selected';
            byId('PreprocessApply').disabled = !editable;
            byId('PreprocessRestore').disabled = !editable || activePreprocess === 'original';
            byId('PreprocessActive').textContent = activePreprocess === 'original' ? 'Original image' : `Active: ${PREPROCESS_METHODS[activePreprocess].label}`;
            for (const [id, type] of Object.entries(drawingTools)) {
                byId(id).disabled = !editable || !classes.length || draft !== null;
                byId(id).setAttribute('aria-pressed', String(draft !== null && drawingTool === type));
            }
            byId('Finish').disabled = !editable || !draft || draft.length < requiredPoints();
            byId('Cancel').disabled = !editable || draft === null;
            byId('Finish').hidden = draft === null;
            byId('Cancel').hidden = draft === null;
            byId('Undo').disabled = !editable || (draft !== null ? !draft.length : !state.canUndo);
            byId('Redo').disabled = !editable || !state.canRedo || draft !== null;
            byId('Save').disabled = !editable || !state.dirty || draft !== null;
            byId('Save').textContent = saveError ? 'Retry save' : 'Save now';
            byId('Save').hidden = !state?.dirty;
            byId('Delete').disabled = !editable || selected === null || draft !== null;
            byId('Delete').hidden = !selectedObject;
            byId('Relabel').disabled = byId('Delete').disabled;
            byId('Relabel').hidden = selected === null;
            const selectedClass = classes.find(item => item.id === selectedObject?.class_id);
            byId('Relabel').textContent = selectedClass?.name || 'Class';
            byId('Relabel').style.borderLeft = selectedClass ? `4px solid ${selectedClass.color}` : '';
            byId('ObjectCount').textContent = String(state?.document.annotations.length || 0);
            byId('ImageList').disabled = locked || !queue.length;
            byId('Previous').disabled = locked || currentIndex <= 0;
            byId('Next').disabled = locked || currentIndex < 0 || currentIndex >= queue.length - 1;
            byId('Position').textContent = queue.length ? `${currentIndex + 1} / ${queue.length}` : '0 / 0';
            const review = state ? reviewStatus(state.document) : null;
            const reviewed = completedReview(review);
            const nextReview = state ? nextReviewIndex() : undefined;
            const allReviewed = reviewed && !state.dirty && !state.proposals.length && !folderLoadFailed && nextReview === undefined && queueScan === null;
            const reviewBlocked = !editable || draft !== null || labelObject !== null || folderLoadFailed || state?.dirty || Boolean(state?.proposals.length);
            byId('ReviewState').textContent = !state ? 'No image' : folderLoadFailed ? 'Load failed' : state.dirty ? 'Unsaved' : state.proposals.length ? `${state.proposals.length} suggestions to resolve` : reviewLabels[review];
            byId('ReviewState').setAttribute('data-review', state?.dirty ? 'in_progress' : review || 'unchecked');
            byId('ReviewNext').textContent = !state ? 'Mark reviewed & next' : allReviewed ? 'All reviewed' : reviewed ? 'Next to review' : state.document.annotations.length ? 'Mark reviewed & next' : 'Confirm empty & next';
            byId('ReviewNext').disabled = reviewBlocked || reviewed && nextReview === undefined;
            byId('ReviewNext').title = state?.proposals.length ? 'Accept or reject remaining suggestions before completing review' : allReviewed ? 'Every image in this folder is reviewed' : 'Save review and open the next image needing review';
            byId('ReopenReview').hidden = !reviewed;
            byId('ReopenReview').disabled = !editable || draft !== null || labelObject !== null || folderLoadFailed || state?.dirty;
            renderQueue(locked);
            byId('Class').disabled = locked || draft !== null || !classes.length;
            byId('SamClass').disabled = !editable || draft !== null || !classes.length;
            for (const control of byId('ClassManager').querySelectorAll('button, input')) control.disabled = locked || draft !== null;
            byId('AddClass').disabled = locked || draft !== null;
            for (const control of byId('ClassForm').querySelectorAll('button, input')) control.disabled = locked || draft !== null;
            byId('SaveState').textContent = saving ? 'Saving…' : saveError && state?.dirty ? 'Save failed — unsaved changes' : busy ? 'Working…' : !state ? 'No image loaded' : state.dirty ? 'Unsaved changes' : draft?.length || localTools.session?.start || drag ? 'Draft not saved' : 'Saved';
            byId('SaveState').setAttribute('data-state', saving || busy ? 'working' : saveError && state?.dirty ? 'error' : state?.dirty || draft?.length || localTools.session?.start || drag ? 'draft' : state ? 'saved' : 'empty');
            byId('SaveState').title = state && window.SAM2ProjectFolder?.has?.(queue[currentIndex]) ? 'Annotations save beside this image' : byId('SaveState').textContent;
            shapes.replaceChildren();
            byId('ObjectList').replaceChildren();
            let selectedOutline = null;
            for (const object of state?.document.annotations || []) {
                const cls = classes.find(item => item.id === object.class_id);
                const color = cls?.color || '#67d7c3';
                const outline = drawGeometry(object.geometry.type, drag?.id === object.id ? drag.points : object.geometry.points, {
                    fill: color, 'fill-opacity': 0.06, stroke: object.id === selected || promptSession?.mergeIds?.includes(object.id) && promptSession.mergeSource === 'objects' ? '#ffffff' : color,
                    'stroke-width': object.id === selected ? 3 : 2, 'vector-effect': 'non-scaling-stroke',
                    'data-object-id': object.id, style: object.id === selected ? 'cursor: move' : 'cursor: pointer'
                });
                if (object.id === selected) selectedOutline = outline;
                const button = document.createElement('button');
                button.className = 'btn btn-secondary';
                button.style.borderLeft = `4px solid ${color}`;
                button.textContent = `#${object.id} · ${cls?.name || 'Unknown class'}`;
                button.setAttribute('aria-pressed', String(promptSession?.mode === 'merge' ? promptSession.mergeSource === 'objects' && promptSession.mergeIds.includes(object.id) : selected === object.id));
                button.disabled = (locked && !(promptSession?.mode === 'merge' && promptSession.mergeSource === 'objects' && !busy)) || draft !== null;
                button.onclick = () => { if (promptSession?.mode === 'merge') return toggleMerge(object.id); view.ShowObjects = true; applyView(); selected = object.id; message('Drag a corner to move it. Click an edge to add a point.'); render(); };
                const row = document.createElement('div'); row.className = 'polygon-object-row';
                const menu = document.createElement('button'); menu.type = 'button';
                menu.className = 'btn btn-secondary polygon-object-menu'; menu.textContent = '⋯';
                menu.setAttribute('aria-label', `Change class for object ${object.id}`);
                menu.title = 'Change class'; menu.disabled = locked || draft !== null;
                menu.onclick = () => openLabelPicker(object.id, menu);
                row.oncontextmenu = event => { event.preventDefault(); openLabelPicker(object.id, menu); };
                row.appendChild(button); row.appendChild(menu); byId('ObjectList').appendChild(row);
            }
            if (selectedOutline) shapes.appendChild(selectedOutline);
            renderProposals(locked || draft !== null);
            const active = state?.document.annotations.find(object => object.id === selected);
            if (active && view.ShowObjects && draft === null && !busy && !promptSession && !localTools.session) {
                const points = drag?.points || active.geometry.points;
                const matrix = svg.getScreenCTM();
                const radius = 5 / Math.hypot(matrix.a, matrix.b);
                if (active.geometry.type === 'polygon') points.forEach((point, index) => {
                    const next = points[(index + 1) % points.length];
                    drawElement('line', { x1: point[0], y1: point[1], x2: next[0], y2: next[1],
                        stroke: 'transparent', 'stroke-width': 12, 'vector-effect': 'non-scaling-stroke',
                        'data-edge-index': index, class: 'polygon-edge' });
                });
                points.forEach((point, index) => {
                    const handle = drawElement('circle', {
                        cx: point[0], cy: point[1], r: radius, fill: '#101318', stroke: duplicateIssue?.objectId === active.id && duplicateIssue.indices.includes(index) ? '#ff62cb' : '#f7cf75',
                        'stroke-width': 2, 'vector-effect': 'non-scaling-stroke',
                        'data-vertex-index': index, class: 'polygon-vertex'
                    });
                    if (active.geometry.type === 'polygon') {
                        handle.setAttribute('tabindex', '0');
                        handle.setAttribute('role', 'button');
                        handle.setAttribute('aria-label', `Polygon point ${index + 1}. Delete to remove.`);
                        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
                        title.textContent = 'Right-click to remove point'; handle.appendChild(title);
                        handle.oncontextmenu = event => {
                            event.preventDefault(); event.stopPropagation();
                            return removeVertex(active.id, index);
                        };
                        handle.onkeydown = event => {
                            if (event.key !== 'Delete' && event.key !== 'Backspace') return;
                            event.preventDefault(); event.stopPropagation();
                            return removeVertex(active.id, index);
                        };
                    }
                });
                const cls = classes.find(item => item.id === active.class_id);
                const label = `#${active.id} · ${cls?.name || 'Unknown class'} ▾`;
                const scale = Math.hypot(matrix.a, matrix.b);
                const x = Math.max(0, Math.min(...points.map(p => p[0])));
                const y = Math.max(0, Math.min(...points.map(p => p[1])) - 28 / scale);
                const badge = drawElement('g', { transform: `translate(${x} ${y}) scale(${1 / scale})`,
                    role: 'button', tabindex: '0', 'aria-label': `Change class for object ${active.id}: ${cls?.name || 'Unknown class'}`, class: 'polygon-object-label' });
                const rect = document.createElementNS(ns, 'rect');
                for (const [key, value] of Object.entries({width: Math.max(100, label.length * 8 + 16), height: 24, rx: 4, fill: '#172936', stroke: cls?.color || '#67d7c3'})) rect.setAttribute(key, value);
                const text = document.createElementNS(ns, 'text'); text.setAttribute('x', 8); text.setAttribute('y', 16);
                text.textContent = label; badge.appendChild(rect); badge.appendChild(text);
                badge.onclick = event => { event.stopPropagation(); openLabelPicker(active.id, badge); };
                badge.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); openLabelPicker(active.id, badge); } };

            }
            const promptLayer = byId('PromptLayer'); promptLayer.replaceChildren();
            localTools.renderPreview(promptLayer);
            if (promptSession && state) {
                const scale = Math.hypot(svg.getScreenCTM().a, svg.getScreenCTM().b);
                const add = (tag, attributes) => {
                    const node = document.createElementNS(ns, tag);
                    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
                    promptLayer.appendChild(node); return node;
                };
                for (const geometry of originals) drawGeometry(geometry.type, geometry.points, {
                    class: 'prompt-original', fill: 'none', stroke: '#ffffff', 'stroke-width': 2,
                    'stroke-dasharray': '5 4', 'vector-effect': 'non-scaling-stroke'
                }, promptLayer);
                for (const geometry of promptSession.preview ? (Array.isArray(promptSession.preview) ? promptSession.preview : [promptSession.preview]) : []) add('polygon', { points: geometry.points.map(point => point.join(',')).join(' '),
                    class: 'prompt-preview', fill: '#f6cb78', 'fill-opacity': .08, stroke: '#f6cb78', 'stroke-width': 2, 'vector-effect': 'non-scaling-stroke' });
                for (const [x, y, label] of promptSession.points) {
                    add('circle', { cx: x, cy: y, r: 6 / scale, fill: label ? '#234d36' : '#672d32', stroke: 'white', 'stroke-width': 1, 'vector-effect': 'non-scaling-stroke' });
                    const text = add('text', { x, y, fill: 'white', 'font-size': 12 / scale, 'text-anchor': 'middle', 'dominant-baseline': 'central' });
                    text.textContent = promptSession.mode === 'split' ? String(promptSession.points.findIndex(point => point[0] === x && point[1] === y) + 1) : label ? '+' : '−';
                }
            }
            if (draft?.length) {
                drawGeometry(drawingTool === 'polygon' ? 'polyline' : drawingTool,
                    drawingTool !== 'polygon' && draft.length === 1 ? [draft[0], previewPoint || draft[0]] : draft, {
                    fill: 'none', stroke: '#f7cf75', 'stroke-width': 2, 'vector-effect': 'non-scaling-stroke' });
                draft.forEach((point, index) => {
                    const invalid = duplicateIssue?.objectId === null && duplicateIssue.indices.includes(index);
                    const handle = drawElement('circle', { cx: point[0], cy: point[1], r: (invalid ? 7 : 5) / Math.hypot(svg.getScreenCTM().a, svg.getScreenCTM().b), fill: invalid ? '#ff62cb' : '#f7cf75', 'data-draft-index': index, style: 'cursor: move' });
                    if (invalid) {
                        handle.setAttribute('tabindex', '0'); handle.setAttribute('role', 'button');
                        handle.setAttribute('aria-label', `Overlapping point ${index + 1}. Delete to remove.`);
                        const remove = event => { event.preventDefault(); event.stopPropagation(); if (!busy && !drag && draft) { draft.splice(index, 1); render(); } };
                        handle.oncontextmenu = remove;
                        handle.onkeydown = event => { if (event.key === 'Delete' || event.key === 'Backspace') remove(event); };
                    }
                });
            }
            if (duplicateIssue && (duplicateIssue.objectId === null && draft || duplicateIssue.objectId === selected && draft === null)) {
                const scale = Math.hypot(svg.getScreenCTM().a, svg.getScreenCTM().b);
                const locations = new Map();
                for (const index of duplicateIssue.indices) {
                    const point = duplicateIssue.points[index], key = point.join(',');
                    if (!locations.has(key)) locations.set(key, { point, numbers: [] });
                    locations.get(key).numbers.push(index + 1);
                }
                for (const { point: [x, y], numbers } of locations.values()) {
                    drawElement('circle', { cx: x, cy: y, r: 11 / scale, fill: 'none', stroke: '#ff62cb', 'stroke-width': 3, 'vector-effect': 'non-scaling-stroke', 'pointer-events': 'none', 'data-invalid-points': numbers.join(',') });
                    const label = drawElement('text', { x, y: y - 16 / scale, fill: '#ff62cb', stroke: '#101318', 'stroke-width': 3 / scale, 'paint-order': 'stroke', 'font-size': 14 / scale, 'text-anchor': 'middle', 'pointer-events': 'none' });
                    label.textContent = `Points ${numbers.join(', ')}`;
                }
            }
        }
        function toggleProposal(id) {
            if (busy || drag || draft !== null || localTools.session || !state.proposals.some(item => item.id === id)) return;
            proposalSelection.has(id) ? proposalSelection.delete(id) : proposalSelection.add(id);
            selected = null; render();
        }
        function highlightProposal(id) {
            proposalHover = id;
            for (const layer of [proposalLayer, badgeLayer]) {
                for (const element of layer.querySelectorAll('[data-proposal-id]')) {
                    element.classList.toggle('hovered', Number(element.getAttribute('data-proposal-id')) === id);
                }
            }
        }
        function renderProposals(locked) {
            proposalLayer.replaceChildren(); badgeLayer.replaceChildren();
            const proposals = state?.proposals || [];
            byId('SamReview').hidden = !proposals.length || !view.ShowSuggestions || draft !== null || Boolean(promptSession);
            for (const id of ['SamClass', 'SamAccept', 'SamReject', 'SamClear']) byId(id).hidden = !proposalSelection.size;
            if (!proposals.length) return;
            const matrix = svg.getScreenCTM();
            if (!matrix) return;
            const scale = Math.hypot(matrix.a, matrix.b);
            const { width, height } = state.document.image;
            // Place badges in distinct grid cells nearest their objects.
            const labelWidth = Math.max(36, 16 + String(Math.max(...proposals.map(p => p.id))).length * 8);
            const columns = Math.max(1, Math.floor(width * scale / labelWidth));
            const rows = Math.max(1, Math.floor(height * scale / 28), Math.ceil(proposals.length / columns));
            const cellWidth = width / columns, cellHeight = height / rows;
            const badgeScale = Math.min(1 / scale, cellWidth / labelWidth, cellHeight / 28);
            const cachedLayout = badgeLayout?.proposals === proposals && badgeLayout.scale === scale;
            const positions = cachedLayout ? badgeLayout.positions : new Map();
            const occupied = new Set();
            function add(layer, tag, attrs) {
                const node = document.createElementNS(ns, tag);
                for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
                layer.appendChild(node); return node;
            }
            function bind(node, proposal) {
                node.onclick = event => { if (draft !== null || localTools.session) return; event.stopPropagation(); if (!cycleOverlap(event)) { overlapCycle = null; toggleProposal(proposal.id); } };
                node.onmouseenter = () => highlightProposal(proposal.id);
                node.onmouseleave = () => highlightProposal(null);
            }
            // Large proposals underneath small ones; badges above every outline.
            for (const proposal of [...proposals].sort((a, b) => b.area - a.area)) {
                const node = add(proposalLayer, 'polygon', {
                    points: proposal.geometry.points.map(point => point.join(',')).join(' '),
                    class: `sam-proposal ${proposalSelection.has(proposal.id) ? 'selected' : ''}`,
                    'data-proposal-id': proposal.id, 'vector-effect': 'non-scaling-stroke'
                }); bind(node, proposal);
            }
            for (const proposal of proposals) {
                const [x, y, w, h] = proposal.bbox, anchor = [x + w / 2, y + h / 2];
                let best = positions.get(proposal.id) || null, distance = Infinity;
                if (!cachedLayout) for (let row = 0; row < rows; row++) for (let col = 0; col < columns; col++) {
                    const key = row * columns + col;
                    if (occupied.has(key)) continue;
                    const cx = (col + 0.5) * cellWidth, cy = (row + 0.5) * cellHeight;
                    const next = (cx - anchor[0]) ** 2 + (cy - anchor[1]) ** 2;
                    if (next < distance) { best = { key, cx, cy }; distance = next; }
                }
                occupied.add(best.key); positions.set(proposal.id, best);
                add(badgeLayer, 'line', { x1: anchor[0], y1: anchor[1], x2: best.cx, y2: best.cy,
                    stroke: '#b8bdc5', 'stroke-width': 0.5, 'pointer-events': 'none', 'vector-effect': 'non-scaling-stroke' });
                const badge = add(badgeLayer, 'g', { transform: `translate(${best.cx} ${best.cy}) scale(${badgeScale})`,
                    class: `sam-badge ${proposalSelection.has(proposal.id) ? 'selected' : ''}`, 'data-proposal-id': proposal.id,
                    role: 'button', tabindex: locked ? -1 : 0, 'aria-label': `Toggle SAM2 suggestion ${proposal.id}`,
                    'aria-pressed': proposalSelection.has(proposal.id), 'aria-disabled': locked });
                add(badge, 'rect', { x: -(labelWidth - 4) / 2, y: -11, width: labelWidth - 4, height: 22, rx: 4 });
                add(badge, 'text', { x: 0, y: 0 }).textContent = proposal.id;
                bind(badge, proposal);
                badge.onkeydown = event => {
                    if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault(); event.stopPropagation(); toggleProposal(proposal.id);
                        badgeLayer.querySelector(`[data-proposal-id="${proposal.id}"]`)?.focus();
                    }
                };
            }
            badgeLayout = { proposals, scale, positions };
            highlightProposal(proposalHover);
        }
        byId('ViewMenu').onkeydown = event => {
            if (event.key === 'Escape') {
                event.preventDefault(); event.stopPropagation();
                byId('ViewMenu').removeAttribute('open');
                byId('ViewMenu').querySelector('summary').focus();
            }
        };
        byId('SamClear').onclick = () => { proposalSelection.clear(); render(); };
        byId('SamClearSuggestions').onclick = () => {
            if (!state || busy || drag || camera.isPanning || draft !== null || !state.proposals.length) return;
            state.change(state.document.annotations, state.document.next_object_id, []);
            proposalSelection.clear(); proposalHover = null;
            render();
        };
        function startPrompt(correct = false) {
            if (!state || busy || draft !== null || promptSession || localTools.session || correct && proposalSelection.size > 1) return;
            const object = correct ? state.document.annotations.find(item => item.id === selected) : null;
            const proposal = correct && proposalSelection.size === 1 ? state.proposals.find(item => proposalSelection.has(item.id)) : null;
            promptSession = { objectId: object?.id ?? null, proposalId: proposal?.id ?? null,
                originalGeometry: object?.geometry || proposal?.geometry, points: [], preview: null, label: 1 };
            byId('PromptClass').value = String(object?.class_id ?? byId('Class').value);
            selected = null; proposalSelection.clear(); render();
        }
        byId('PromptStart').onclick = () => startPrompt();
        byId('Correct').onclick = () => startPrompt(true);
        const localTools = window.SAM2PolygonLocalTools.create({
            byId, svg, getContext: () => ({ state, selected, busy, camera, view, proposalSelection, disposed }),
            setSelected: value => { selected = value; }, clearLabelPicker: () => { labelObject = null; },
            applyView, imagePoint, request, operate, saveChanges, render, message, drawElement, drawGeometry
        });
        byId('Select').onclick = () => { selected = null; proposalSelection.clear(); render(); };
        byId('PromptCompare').onclick = () => { if (promptSession) { promptSession.showOriginal = !promptSession.showOriginal; render(); } };
        byId('Split').onclick = () => {
            if (byId('Split').disabled) return;
            const target = state.document.annotations.find(item => item.id === selected) || state.proposals.find(item => proposalSelection.has(item.id));
            startPrompt(true);
            promptSession.mode = 'split'; promptSession.parentGeometry = structuredClone(target.geometry);
            message(''); render();
        };
        byId('Merge').onclick = () => {
            if (byId('Merge').disabled) return;
            const fromProposals = proposalSelection.size > 1;
            promptSession = { mode: 'merge', points: [], preview: null, mergeSource: fromProposals ? 'proposals' : 'objects',
                mergeIds: fromProposals ? [...proposalSelection] : selected === null ? [] : [selected] };
            byId('PromptClass').value = String(state.document.annotations.find(item => item.id === selected)?.class_id ?? byId('Class').value);
            selected = null; proposalSelection.clear(); message(''); render();
            return predictMerge();
        };
        function mergeItems() {
            return promptSession.mergeSource === 'objects' ? state.document.annotations : state.proposals;
        }
        function toggleMerge(id) {
            if (busy || promptSession?.mode !== 'merge') return;
            const ids = promptSession.mergeIds;
            ids.includes(id) ? ids.splice(ids.indexOf(id), 1) : ids.push(id);
            return predictMerge();
        }
        async function predictMerge() {
            const session = promptSession; session.preview = null; message('');
            if (session.mergeIds.length < 2) { render(); return; }
            const geometries = mergeItems().filter(item => session.mergeIds.includes(item.id)).map(item => item.geometry);
            return operate(async () => {
                const result = await request('api/project/segmentation', { action: 'merge_preview', image: state.document.image, geometries });
                if (disposed || promptSession !== session) return;
                session.preview = result.geometry;
            });
        }
        byId('PromptInclude').onclick = () => { if (promptSession) { promptSession.label = 1; render(); } };
        byId('PromptExclude').onclick = () => { if (promptSession) { promptSession.label = 0; render(); } };
        byId('PromptCancel').onclick = () => { promptSession = null; message(''); render(); };
        async function predictPrompt() {
            const session = promptSession;
            session.preview = null;
            session.showOriginal = false;
            if (!session.points.length || session.mode === 'split' && session.points.length < 2) { render(); return; }
            return operate(async () => {
                const sourceState = state, file = queue[currentIndex];
                const response = await window.SAM2ApiWorkflows.runSam({ file, imageName: `image${file.name.match(/\.[^.]+$/)?.[0] || '.png'}`,
                    samSettings: { preset: byId('SamPreset').value }, preprocessMethod: activePreprocess,
                    preprocessParams: appliedPreprocessParams, output: 'polygons', points: structuredClone(session.points), splitGeometry: session.parentGeometry });
                const data = await response.json();
                if (disposed || promptSession !== session || state !== sourceState) return;
                if (!response.ok) throw new Error(data.error || 'SAM2 could not create a preview.');
                if (data.image.identity !== state.document.image.identity || data.image.width !== state.document.image.width || data.image.height !== state.document.image.height) throw new Error('SAM2 preview does not match the active image.');
                if (!data.proposals?.length) throw new Error('No editable outline found. Adjust your clicks.');
                if (session.mode === 'split' && data.proposals.length !== session.points.length) throw new Error('Every clicked cell needs an outline. Adjust your clicks.');
                session.preview = session.mode === 'split' ? data.proposals.map(item => item.geometry) : data.proposals[0].geometry;
                message('');
            });
        }
        function addPrompt(event, label = promptSession?.label) {
            if (!promptSession || busy) return;
            if (promptSession.mode === 'merge') {
                const point = imagePoint(event);
                const hit = mergeItems().find(item => geometryContains(item.geometry, point));
                if (hit) return toggleMerge(hit.id);
                return;
            }
            const [x, y] = imagePoint(event), { width, height } = state.document.image;
            if (x < 0 || y < 0 || x >= width || y >= height) return;
            if (promptSession.mode === 'split') {
                label = 1;
                if (!geometryContains(promptSession.parentGeometry, [x, y])) { message('Click inside the selected object.', true); return; }
                if (promptSession.points.length >= 16) { message('Split supports up to 16 cells at a time.', true); return; }
            }
            if (!promptSession.points.length && label !== 1) { message('Start with an include click inside the object.', true); return; }
            if (promptSession.points.length >= 64) { message('Maximum 64 clicks. Undo a click or start another object.', true); return; }
            promptSession.points.push([x, y, label]);
            return predictPrompt();
        }
        byId('PromptUndo').onclick = () => {
            if (!promptSession || busy || !promptSession.points.length) return;
            promptSession.points.pop(); return predictPrompt();
        };
        byId('PromptAccept').onclick = () => operate(async () => {
            const session = promptSession;
            if (!session?.preview) return;
            const document = structuredClone(state.document);
            const classId = Number(byId('PromptClass').value);
            let id;
            let removeProposals = [];
            if (session.mode === 'split' || session.mode === 'merge') {
                const removeObjects = session.mode === 'split' ? [session.objectId] : session.mergeSource === 'objects' ? session.mergeIds : [];
                removeProposals = session.mode === 'split' ? [session.proposalId] : session.mergeSource === 'proposals' ? session.mergeIds : [];
                document.annotations = document.annotations.filter(item => !removeObjects.includes(item.id));
                const geometries = session.mode === 'split' ? session.preview : [session.preview];
                for (const geometry of geometries) {
                    id = document.next_object_id++;
                    document.annotations.push({ id, class_id: classId, source: session.mode === 'split' ? 'sam2' : 'manual', edited: true, geometry: structuredClone(geometry) });
                }
            } else {
                const object = document.annotations.find(item => item.id === session.objectId);
                id = object?.id ?? document.next_object_id++;
                const next = { ...(object || { id, source: 'sam2' }), class_id: classId,
                    geometry: structuredClone(session.preview), edited: Boolean(object) };
                if (object) document.annotations[document.annotations.indexOf(object)] = next;
                else document.annotations.push(next);
                removeProposals = [session.proposalId];
            }
            const validated = await request('api/project/segmentation', { action: 'validate', image: document.image, document });
            if (disposed || promptSession !== session) return;
            state.change(validated.document.annotations, validated.document.next_object_id,
                state.proposals.filter(item => !removeProposals.includes(item.id)));
            promptSession = null; selected = id; view.ShowObjects = true; applyView();
            await saveChanges();
        });
        svg.oncontextmenu = event => {
            if (promptSession) { event.preventDefault(); if (!promptSession.mode) return addPrompt(event, 0); }
        };
        byId('SamRun').onclick = () => operate(async () => {
            const sourceState = state;
            message('Running SAM2 on the active image and applied preprocessing…');
            const file = queue[currentIndex];
            const imageName = `image${file.name?.match(/\.[^.]+$/)?.[0] || '.png'}`;
            const response = await window.SAM2ApiWorkflows.runSam({ file, imageName,
                samSettings: { preset: byId('SamPreset').value }, preprocessMethod: activePreprocess,
                preprocessParams: appliedPreprocessParams, output: 'polygons' });
            const data = await response.json();
            if (disposed || state !== sourceState) return;
            if (!response.ok) throw new Error(data.error || 'SAM2 could not generate suggestions.');
            if (data.image.identity !== state.document.image.identity || data.image.width !== state.document.image.width || data.image.height !== state.document.image.height) {
                throw new Error('SAM2 results do not match the active image. Previous suggestions retained.');
            }
            view.ShowSuggestions = true; applyView(); overlapCycle = null;
            state.setProposals(data.proposals); proposalSelection.clear(); selected = null; proposalHover = null;
            byId('SamDetails').textContent = data.skipped ? `Last SAM2 run: ${data.skipped} masks skipped because their outlines are unsupported.` : '';
            message('Click cells or their numbers, then Accept selected. Choose an active class before accepting.');
        });
        byId('SamAccept').onclick = () => operate(async () => {
            const accepted = state.proposals.filter(item => proposalSelection.has(item.id));
            if (!accepted.length || !classes.length) return;
            const document = structuredClone(state.document);
            for (const proposal of accepted) document.annotations.push({ id: document.next_object_id++,
                class_id: Number(byId('Class').value), source: 'sam2', edited: false, geometry: proposal.geometry });
            const validated = await request('api/project/segmentation', { action: 'validate', image: document.image, document });
            if (disposed) return;
            state.change(validated.document.annotations, validated.document.next_object_id,
                state.proposals.filter(item => !proposalSelection.has(item.id)));
            proposalSelection.clear(); selected = null;
            await saveChanges();
            message(`Accepted and saved ${accepted.length} objects. Undo last action restores the entire batch as suggestions.`);
        });
        byId('SamReject').onclick = () => {
            if (busy || drag || !proposalSelection.size) return;
            state.change(state.document.annotations, state.document.next_object_id,
                state.proposals.filter(item => !proposalSelection.has(item.id)));
            proposalSelection.clear(); render(); message('Selected suggestions rejected. Undo last action restores the batch.');
        };
        function renderClasses(previous = byId('Class').value) {
            const active = classes.find(cls => String(cls.id) === previous) || classes[0];
            window.SAM2ClassUiController.renderClassControls({ classManager: byId('ClassManager'),
                classificationSelect: byId('Class'), reservedHotkeys, shortcutHelp: '1–3 are drawing tools; B and U are reserved.' }, classes, active?.name || '');
            // Detection selects by name; polygon documents reference stable class IDs.
            Array.from(byId('Class').children).forEach((option, index) => { option.value = classes[index] ? String(classes[index].id) : ''; });
            byId('Class').value = active ? String(active.id) : '';
            byId('SamClass').replaceChildren(...classes.map(cls => new Option(cls.name, String(cls.id))));
            byId('SamClass').value = byId('Class').value;
            byId('PromptClass').replaceChildren(...classes.map(cls => new Option(cls.name, String(cls.id))));
            byId('PromptClass').value = byId('Class').value;
            filterClasses();
        }
        function filterClasses() {
            const query = byId('ClassSearch').value.trim().toLocaleLowerCase();
            const rows = Array.from(byId('ClassManager').querySelectorAll('.class-row'));
            rows.forEach(row => { row.hidden = !row.querySelector('.class-select-btn').dataset.className.toLocaleLowerCase().includes(query); });
            byId('ClassSearchEmpty').hidden = !query || rows.some(row => !row.hidden);
        }
        byId('ClassSearch').oninput = filterClasses;
        byId('SamClass').onchange = () => { byId('Class').value = byId('SamClass').value; renderClasses(); render(); };
        byId('Class').onchange = () => { renderClasses(); render(); };
        byId('AddClass').onclick = () => { byId('ClassForm').hidden = !byId('ClassForm').hidden; if (!byId('ClassForm').hidden) byId('ClassName').focus(); };
        byId('ClassManager').onclick = event => {
            if (busy || drag || camera.isPanning || draft !== null) return;
            const remove = event.target.closest('.class-delete-btn');
            if (remove) return deleteClass(window.SAM2ClassUiController.getClassRowIndex(remove));
            const button = event.target.closest('.class-select-btn');
            if (!button) return;
            byId('Class').value = String(classes.find(cls => cls.name === button.dataset.className).id);
            renderClasses(); render();
        };
        function deleteClass(index) {
            const target = classes[index];
            if (!target || promptSession || folderLoadFailed) return;
            const affected = state?.document.annotations.filter(item => item.class_id === target.id).length || 0;
            if (!window.confirm(`Are you sure you want to delete the class "${target.name}" and remove ${affected} annotations?\n\nOnly the current image is affected. Other images keep their annotations.`)) return;
            return operate(async () => {
                const result = await request('api/classes', { classes: classes.filter(item => item.id !== target.id) });
                if (disposed) return;
                classes = result.classes;
                renderClasses();
                if (state) {
                    state.change(state.document.annotations.filter(item => item.class_id !== target.id),
                        state.document.next_object_id, state.proposals, state.document.labelme, { id: target.id, index, item: target });
                    selected = null; labelObject = null;
                    await saveChanges();
                }
                renderClasses();
                message(state ? 'Class deleted. Undo restores the class and its annotations.' : 'Class deleted.');
            });
        }
        byId('ClassManager').onchange = event => {
            if (busy || drag || camera.isPanning || draft !== null) { renderClasses(); return; }
            const index = window.SAM2ClassUiController.getClassRowIndex(event.target);
            if (index === null || !classes[index]) return;
            const next = structuredClone(classes), input = event.target;
            const manager = window.SAM2ClassManager;
            if (input.classList.contains('class-name-input')) {
                const name = manager.normalizeClassName(input.value);
                if (!name || name.length > 128 || classes.some((cls, i) => i !== index && cls.name === name)) {
                    input.value = classes[index].name;
                    message('Choose a unique class name (1–128 characters).', true); renderClasses(); return;
                }
                next[index].name = name;
            } else if (input.classList.contains('class-color-input')) {
                if (classes.some((cls, i) => i !== index && String(cls.color || '').toLowerCase() === input.value.toLowerCase())) {
                    input.value = classes[index].color;
                    message('That color is already assigned to another class.', true); renderClasses(); return;
                }
                next[index].color = input.value;
            } else if (input.classList.contains('class-hotkey-input')) {
                const hotkey = manager.normalizeHotkey(input.value);
                if (hotkey && (manager.isReservedHotkey(hotkey, reservedHotkeys) || classes.some((cls, i) => i !== index && cls.hotkey === hotkey))) {
                    input.value = classes[index].hotkey || '';
                    message('Choose an unused shortcut; 1–3, B and U are reserved.', true); renderClasses(); return;
                }
                next[index].hotkey = hotkey;
            } else return;
            const field = input.classList.contains('class-name-input') ? 'name' : input.classList.contains('class-color-input') ? 'color' : 'hotkey';
            return operate(async () => {
                try {
                    const result = await request('api/classes', { classes: next });
                    if (!disposed) classes = result.classes;
                } finally {
                    if (!disposed) { input.value = classes[index][field] || ''; renderClasses(); }
                }
            });
        };
        const resizeObserver = new ResizeObserver(() => { fitZoom(); render(); });
        resizeObserver.observe(svg.parentElement);
        async function loadFile(file, index, nextQueue = queue, nextAnnotations = folderAnnotations, expectedIdentity = null) {
            const replacedQueue = nextQueue !== queue;
            let opened = false;
            await operate(async () => {
                message('Loading image and saved polygons…');
                const bytes = await file.arrayBuffer();
                const hash = await crypto.subtle.digest('SHA-256', bytes);
                const identity = Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('');
                if (expectedIdentity && identity !== expectedIdentity) throw new Error('The saved image changed. Open the folder to review its current contents.');
                const form = new FormData();
                form.append('image', file);
                const response = await window.SAM2ApiClient.apiFetch('api/load_image', { method: 'POST', body: form });
                const decoded = await response.json();
                if (!response.ok) throw new Error(decoded.error || 'Could not decode image.');
                if (disposed) return;
                const image = { identity, width: decoded.width, height: decoded.height };
                let localAnnotation = null;
                if (window.SAM2ProjectFolder?.has(file)) {
                    localAnnotation = await window.SAM2ProjectFolder.read(file, file.name.replace(/\.[^.]+$/, '') + '.json');
                }
                const loaded = await request('api/project/segmentation', {
                    action: 'load', image, restore_classes: localAnnotation === null,
                });
                if (Array.isArray(loaded.classes)) classes = loaded.classes;
                // The file beside the image is authoritative, including an empty annotation.
                if (localAnnotation !== null) loaded.document = { schema_version: 1, task_type: 'instance_segmentation',
                    project_id: loaded.document.project_id, image, next_object_id: loaded.document.next_object_id, annotations: [] };
                if (disposed) return;
                state = createPolygonState(loaded.document);
                folderLoadFailed = false;
                revision = loaded.revision;
                saveError = false;
                if (replacedQueue) { imageReviews.clear(); queueFilter = 'all'; queueRenderKey = ''; }
                queue = nextQueue;
                folderAnnotations = nextAnnotations;
                byId('ImageList').replaceChildren(...queue.map((item, position) => new Option(phiSafeMode ? imageLabel(item, position) : `${position + 1}. ${imageLabel(item, position)}`, String(position))));
                selected = null; labelObject = null; draft = null; promptSession = null; localTools.clear(); currentIndex = index; proposalSelection.clear(); proposalHover = null;
                byId('SamInfo').textContent = '';
                byId('SamDetails').textContent = '';
                byId('ImageList').value = String(index);
                byId('ImageName').textContent = phiSafeMode ? `Image ${index + 1}` : file.name;
                byId('ImageName').title = phiSafeMode ? `Image ${index + 1}` : file.webkitRelativePath || file.name;
                svg.setAttribute('viewBox', `0 0 ${image.width} ${image.height}`);
                byId('Image').setAttribute('href', decoded.image_url);
                originalPreview = decoded.image_url;
                activePreprocess = 'original'; appliedPreprocessParams = {};
                byId('PreprocessMethod').value = 'original';
                resetPreprocessSettings(); showPreprocessSettings();
                byId('Image').setAttribute('width', image.width);
                byId('Image').setAttribute('height', image.height);
                byId('Empty').hidden = true;
                svg.removeAttribute('hidden');
                resetPan(); zoom = 100; fitZoom(); svg.parentElement.scrollLeft = 0; svg.parentElement.scrollTop = 0; byId('ZoomLabel').textContent = '100%';
                message('Recovered an earlier backup. Check the objects before continuing.', Boolean(loaded.recovered));
                // A saved empty document is still deliberate work; never replace it on reopen.
                if (localAnnotation !== null) {
                    folderLoadFailed = true;
                    await importLabelme(new File([localAnnotation], file.name.replace(/\.[^.]+$/, '') + '.json'), false, false);
                } else if (loaded.revision == null && folderAnnotations.has(file)) {
                    const annotation = folderAnnotations.get(file);
                    if (annotation === null) message('Multiple files share this name. Import the correct Labelme JSON from Files & annotations.', true);
                    else await importLabelme(annotation, false);
                }
                opened = !folderLoadFailed;
            });
            if (!disposed) byId('ImageList').value = String(currentIndex);
            if (!disposed && replacedQueue && queue === nextQueue) void scanQueue(queue);
            if (opened) rememberWorkspace();
            return opened;
        }
        async function resumeWorkspace(saved) {
            if (disposed || busy || queue.length) return false;
            const { images, annotations } = matchFolderFiles(saved.files);
            if (!images.length) return false;
            const last = images.findIndex(file => window.SAM2ProjectFolder.imagePath(file) === saved.lastPath);
            const index = Math.max(0, last);
            const opened = await loadFile(images[index], index, images, annotations, last >= 0 ? saved.identity : null);
            if (disposed || !opened) return false;
            queueFilter = ['all', 'needs_review', 'completed'].includes(saved.filter) ? saved.filter : 'all';
            if (last < 0) message('The last image is no longer in this folder. Opened the first available image.', true);
            rememberWorkspace(); render();
            return true;
        }
        byId('Open').onclick = () => byId('Files').click();
        byId('FileMenu').onclick = event => {
            const button = event.target.closest('button');
            if (button) byId('FileMenu').removeAttribute('open');
        };
        byId('FileMenu').onkeydown = event => {
            if (event.key === 'Escape') {
                event.stopPropagation();
                byId('FileMenu').removeAttribute('open');
                byId('FileMenu').querySelector('summary').focus();
            }
        };
        byId('Files').accept = window.SAM2FrontendConfig.ALLOWED_IMAGE_EXTENSIONS.join(',');
        byId('OpenFolder').onclick = async () => {
            if (!canLeave()) return;
            try {
                const files = await window.SAM2ProjectFolder.open();
                await byId('Folder').onchange({ target: { files, value: '' } });
            } catch (error) { if (error.name !== 'AbortError') message(error.message, true); }
        };
        byId('Folder').onchange = async event => {
            const files = Array.from(event.target.files);
            event.target.value = '';
            if (!files.length || !canLeave()) return;
            const { images, annotations } = matchFolderFiles(files);
            if (!images.length) { message('No supported images found in this folder.', true); return; }
            await loadFile(images[0], 0, images, annotations);
        };
        byId('ImportLabelme').onclick = () => byId('LabelmeFile').click();
        byId('LabelmeFile').onchange = async event => {
            const file = event.target.files[0];
            event.target.value = '';
            if (!file || !state || busy || drag || draft !== null) return;
            await operate(() => importLabelme(file, true));
        };
        async function importLabelme(file, confirmReplacement, persist = true) {
            const sourceState = state;
            if (file.size > 20 * 1024 * 1024) throw new Error('Annotation JSON exceeds the 20 MB import limit. Save from Labelme without embedded image data.');
            const raw = JSON.parse(await file.text());
            if (disposed || state !== sourceState) return;
            if (confirmReplacement && state.document.annotations.length && !window.confirm('Replace the current image’s objects with this Labelme file? You can undo the import.')) return;
            const result = await request('api/project/segmentation', { action: 'import_labelme',
                image: state.document.image, image_name: queue[currentIndex].name || 'image.png',
                next_object_id: state.document.next_object_id, revision, labelme: raw });
            if (disposed || state !== sourceState) return;
            classes = result.classes; renderClasses();
            folderLoadFailed = false;
            if (!persist) {
                state = createPolygonState(result.document);
                selected = null; proposalSelection.clear();
                return;
            }
            state.change(result.document.annotations, result.document.next_object_id, [], result.document.labelme);
            selected = null; proposalSelection.clear();
            await saveChanges();
            message(`Imported and saved ${result.document.annotations.length} objects. Undo restores the previous objects.`);
        }
        byId('ExportLabelme').onclick = () => operate(async () => {
            const sourceState = state, imageName = queue[currentIndex].name || 'image.png';
            const result = await request('api/project/segmentation', { action: 'export_labelme',
                image: state.document.image, image_name: imageName, document: state.document });
            if (disposed || state !== sourceState) return;
            const url = URL.createObjectURL(new Blob([JSON.stringify(result.labelme, null, 2)], { type: 'application/json' }));
            const link = document.createElement('a'); link.href = url;
            link.download = `${result.labelme.imagePath.replace(/\.[^.]+$/, '')}.json`;
            document.body.appendChild(link); link.click(); link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            message(phiSafeMode ? 'JSON downloaded with an anonymized image reference. Use the matching anonymized filename for its source image.' : 'Labelme JSON downloaded. Keep it beside its source image.');
        });
        byId('Files').onchange = async event => {
            const files = Array.from(event.target.files);
            event.target.value = '';
            if (!files.length || !canLeave()) return;
            if (window.SAM2ProjectFolder) {
                try { await window.SAM2ProjectFolder.attach(files); }
                catch (error) { if (error.name !== 'AbortError') message(error.message, true); return; }
            }
            await loadFile(files[0], 0, files, new Map());
        };
        async function navigate(index) {
            if (index < 0 || index >= queue.length || !canLeave()) { byId('ImageList').value = String(currentIndex); return; }
            await loadFile(queue[index], index);
        }
        byId('Previous').onclick = () => navigate(currentIndex - 1);
        byId('Next').onclick = () => navigate(currentIndex + 1);
        byId('ImageList').onchange = async () => {
            const index = Number(byId('ImageList').value);
            await navigate(index);
        };
        byId('QueueFilters').onclick = event => {
            const button = event.target.closest('button[data-filter]');
            if (!button) return;
            queueFilter = button.dataset.filter; render();
            rememberWorkspace();
        };
        byId('ReviewNext').onclick = async () => {
            if (byId('ReviewNext').disabled) return;
            let saved = false;
            await operate(async () => {
                if (!completedReview(reviewStatus(state.document))) {
                    state.setReview(state.document.annotations.length ? 'reviewed' : 'confirmed_empty');
                    await saveChanges();
                }
                saved = true;
            });
            if (!saved || disposed) return;
            const next = nextReviewIndex();
            if (next !== undefined) await navigate(next);
        };
        byId('ReopenReview').onclick = () => {
            if (byId('ReopenReview').disabled) return;
            return operate(async () => {
                state.setReview(state.document.annotations.length ? 'in_progress' : 'unreviewed');
                await saveChanges();
            });
        };
        function restoreOriginal() {
            if (!state || busy || drag) return;
            byId('Image').setAttribute('href', originalPreview);
            activePreprocess = 'original'; appliedPreprocessParams = {};
            byId('PreprocessMethod').value = 'original'; showPreprocessSettings();
            message('Original preview restored. Rerun SAM2 to update suggestions. Polygons are unchanged.'); render();
        }
        byId('PreprocessRestore').onclick = restoreOriginal;
        byId('PreprocessApply').onclick = () => {
            if (!state || busy || drag) return;
            const method = byId('PreprocessMethod').value;
            if (method === 'original') { restoreOriginal(); return; }
            const params = { ...DEFAULT_PREPROCESS_PARAMS };
            for (const input of preprocessInputs) {
                if (!input.parentElement.hidden && (!input.value.trim() || !input.reportValidity())) return;
                const value = Number.parseFloat(input.value);
                if (Number.isFinite(value)) params[input.dataset.param] = value;
            }
            return operate(async () => {
                const sourceState = state;
                message(`Applying ${PREPROCESS_METHODS[method].label}…`);
                const response = await window.SAM2ApiWorkflows.preprocessImage({ file: queue[currentIndex], method, params });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Could not process image.');
                // Decode before replacing the visible preview; failures retain the old one.
                const preview = new Image();
                await new Promise((resolve, reject) => {
                    preview.onload = resolve;
                    preview.onerror = () => reject(new Error('Could not decode the processed preview.'));
                    preview.src = data.image;
                });
                if (disposed || state !== sourceState) return;
                if (preview.naturalWidth !== state.document.image.width || preview.naturalHeight !== state.document.image.height) {
                    throw new Error('Processed image dimensions do not match. Previous preview retained.');
                }
                byId('Image').setAttribute('href', data.image);
                activePreprocess = method;
                appliedPreprocessParams = structuredClone(data.params);
                for (const input of preprocessInputs) input.value = String(data.params[input.dataset.param]);
                message(`${PREPROCESS_METHODS[method].label} applied to preview and SAM2 input. Rerun SAM2 to update suggestions.`);
            });
        };
        byId('ClassForm').onsubmit = event => {
            event.preventDefault();
            const name = window.SAM2ClassManager.normalizeClassName(byId('ClassName').value);
            if (!name || busy || drag || camera.isPanning || draft !== null) return;
            if (classes.some(cls => cls.name === name)) { message('That class already exists.', true); return; }
            return operate(async () => {
                const newClass = window.SAM2ClassManager.buildNewClass(name, classes, 1, reservedHotkeys);
                delete newClass.id; // The server allocates IDs, including after earlier removals.
                const result = await request('api/classes', { classes: [...classes, newClass] });
                if (disposed) return;
                classes = result.classes;
                byId('ClassSearch').value = '';
                renderClasses(String(classes.find(cls => cls.name === name).id));
                byId('ClassName').value = '';
                byId('ClassForm').hidden = true;
                message('Class created.');
            });
        };
        for (const [id, type] of Object.entries(drawingTools)) byId(id).onclick = () => {
            drawingTool = type; draft = []; previewPoint = null; selected = null; proposalSelection.clear(); render();
        };
        viewport.bindPanning();
        function removeVertex(id, index) {
            if (!state || busy || drag || camera.isPanning || draft !== null) return;
            const object = state.document.annotations.find(item => item.id === id);
            if (!object || object.geometry.type !== 'polygon') return;
            if (object.geometry.points.length <= 3) {
                message('A polygon needs at least three points.', true); return;
            }
            const points = structuredClone(object.geometry.points);
            points.splice(index, 1);
            return editPoints(id, points);
        }
        async function editPoints(id, points) {
            if (state.document.annotations.find(item => item.id === id)?.geometry.type === 'polygon' && reportDuplicatePoints(points, id)) { render(); return; }
            message('');
            await operate(async () => {
                const document = structuredClone(state.document);
                const object = document.annotations.find(item => item.id === id);
                object.geometry.points = points;
                object.edited = true;
                const validated = await request('api/project/segmentation', { action: 'validate', image: document.image, document });
                state.change(validated.document.annotations);
                await saveChanges();
            });
        }
        svg.onpointerdown = event => {
            if (promptSession || localTools.session) return;
            if (event.altKey) return;
            suppressClick = false;
            if (!state || busy || drag || camera.isPanning || event.button !== 0 || labelObject !== null) return;
            if (draft !== null) {
                if (drawingTool !== 'polygon' || !event.target.hasAttribute('data-draft-index')) return;
                drag = { isDraft: true, index: Number(event.target.getAttribute('data-draft-index')),
                    original: structuredClone(draft), points: structuredClone(draft), pointerId: event.pointerId };
                svg.setPointerCapture(event.pointerId); event.preventDefault(); render(); return;
            }
            const vertex = event.target.hasAttribute('data-vertex-index');
            if (!vertex && (!event.target.hasAttribute('data-object-id') || Number(event.target.getAttribute('data-object-id')) !== selected)) return;
            const object = state.document.annotations.find(item => item.id === selected);
            drag = { id: selected, index: vertex ? Number(event.target.getAttribute('data-vertex-index')) : null,
                origin: imagePoint(event), original: structuredClone(object.geometry.points), type: object.geometry.type,
                pointerId: event.pointerId, points: structuredClone(object.geometry.points) };
            svg.setPointerCapture(event.pointerId);
            event.preventDefault();
            render();
        };
        svg.onpointermove = event => {
            if (camera.isPanning) return;
            if (localTools.session && !busy) { localTools.moveHover(event); return; }
            if (draft !== null && drawingTool !== 'polygon' && draft.length === 1 && !busy) {
                previewPoint = imagePoint(event); render(); return;
            }
            if (!drag || event.pointerId !== drag.pointerId) return;
            const [x, y] = imagePoint(event);
            const { width, height } = state.document.image;
            if (drag.index === null) {
                const points = drag.original;
                const radius = drag.type === 'circle' ? Math.hypot(points[1][0] - points[0][0], points[1][1] - points[0][1]) : 0;
                const left = radius ? points[0][0] - radius : Math.min(...points.map(p => p[0]));
                const right = radius ? points[0][0] + radius : Math.max(...points.map(p => p[0]));
                const top = radius ? points[0][1] - radius : Math.min(...points.map(p => p[1]));
                const bottom = radius ? points[0][1] + radius : Math.max(...points.map(p => p[1]));
                const dx = Math.max(-left, Math.min(width - right, x - drag.origin[0]));
                const dy = Math.max(-top, Math.min(height - bottom, y - drag.origin[1]));
                drag.points = points.map(p => [p[0] + dx, p[1] + dy]);
            } else drag.points[drag.index] = [Math.max(0, Math.min(width, x)), Math.max(0, Math.min(height, y))];
            if (drag.isDraft) draft = drag.points;
            render();
        };
        function endDrag(cancelled) {
            if (!drag) return;
            const edit = drag;
            drag = null;
            suppressClick = true;
            if (svg.hasPointerCapture(edit.pointerId)) svg.releasePointerCapture(edit.pointerId);
            if (edit.isDraft) {
                draft = structuredClone(cancelled ? edit.original : edit.points);
                if (!reportDuplicatePoints(draft)) message('');
                render(); return;
            }
            const original = state.document.annotations.find(item => item.id === edit.id).geometry.points;
            if (cancelled) message('Point move cancelled.');
            else if (JSON.stringify(original) !== JSON.stringify(edit.points)) {
                return editPoints(edit.id, edit.points);
            }
            render();
        }
        svg.onpointerup = event => {
            if (drag && event.pointerId === drag.pointerId) {
                svg.onpointermove(event);
                return endDrag(false);
            }
        };
        svg.onpointercancel = event => { if (drag?.pointerId === event.pointerId) endDrag(true); };
        svg.onlostpointercapture = event => { if (drag?.pointerId === event.pointerId) endDrag(true); };
        svg.onauxclick = event => { if (event.button === 1) event.preventDefault(); };
        svg.onclick = event => {
            if (event.button != null && event.button !== 0) return;
            if (suppressClick) { suppressClick = false; return; }
            if (localTools.session) return localTools.addPoint(event);
            if (promptSession) return addPrompt(event);
            if (!state || busy || drag || labelObject !== null) return;
            if (draft === null) {
                if (cycleOverlap(event)) return;
                overlapCycle = null;
                if (event.target.hasAttribute('data-vertex-index')) return;
                if (event.target.hasAttribute('data-edge-index')) {
                    const object = state.document.annotations.find(item => item.id === selected);
                    const points = structuredClone(object.geometry.points);
                    if (points.length >= 512) { message('Maximum 512 polygon points reached.', true); return; }
                    const index = Number(event.target.getAttribute('data-edge-index'));
                    const a = points[index], b = points[(index + 1) % points.length];
                    const [x, y] = imagePoint(event);
                    const dx = b[0] - a[0], dy = b[1] - a[1];
                    const t = Math.max(0, Math.min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / (dx * dx + dy * dy)));
                    if (t === 0 || t === 1) return;
                    points.splice(index + 1, 0, [a[0] + t * dx, a[1] + t * dy]);
                    return editPoints(selected, points);
                }
                selected = event.target.hasAttribute('data-object-id') ? Number(event.target.getAttribute('data-object-id')) : null;
                if (selected !== null) message('Drag a corner to move it. Click an edge to add a point.');
            } else {
                if (event.target.hasAttribute('data-draft-index')) return;
                const point = svg.createSVGPoint(); point.x = event.clientX; point.y = event.clientY;
                const world = point.matrixTransform(svg.getScreenCTM().inverse());
                const { width, height } = state.document.image;
                if (world.x < 0 || world.y < 0 || world.x > width || world.y > height) return;
                if (drawingTool !== 'polygon' && draft.length >= 2) return;
                if (draft.length >= 512) { message('Maximum 512 polygon points reached.', true); return; }
                draft.push([world.x, world.y]);
                if (drawingTool === 'polygon') reportDuplicatePoints(draft);
                previewPoint = null;
                if (drawingTool !== 'polygon' && draft.length === 2) return byId('Finish').onclick();
            }
            render();
        };
        byId('Cancel').onclick = () => { draft = null; message('Draft cancelled.'); render(); };
        byId('Finish').onclick = () => operate(async () => {
            if (drawingTool === 'polygon' && reportDuplicatePoints(draft)) return;
            const document = structuredClone(state.document);
            const id = document.next_object_id++;
            document.annotations.push({ id, class_id: Number(byId('Class').value), source: 'manual', edited: false,
                geometry: { type: drawingTool, points: structuredClone(draft) } });
            const validated = await request('api/project/segmentation', { action: 'validate', image: document.image, document });
            state.change(validated.document.annotations, validated.document.next_object_id);
            draft = null; selected = id;
            await saveChanges();
        });
        byId('Delete').onclick = () => operate(async () => {
            state.change(state.document.annotations.filter(object => object.id !== selected)); selected = null;
            await saveChanges();
        });
        byId('Relabel').onclick = () => openLabelPicker(selected, byId('Relabel'));
        async function restoreHistory(direction) {
            const classChange = state[direction](classes);
            if (classChange) {
                const nextClasses = classes.filter(item => item.id !== classChange.id);
                if (classChange.item) nextClasses.splice(classChange.index, 0, classChange.item);
                try {
                    const result = await request('api/classes', { classes: nextClasses });
                    if (disposed) return;
                    classes = result.classes;
                } catch (error) {
                    state[direction === 'undo' ? 'redo' : 'undo'](nextClasses);
                    throw error;
                }
                renderClasses();
            }
            selected = null; proposalSelection.clear(); proposalHover = null;
            await saveChanges();
        }
        byId('Undo').onclick = () => {
            if (draft !== null) { draft.pop(); render(); return; }
            return operate(async () => { await restoreHistory('undo'); message('Last action undone.'); });
        };
        byId('Redo').onclick = () => operate(() => restoreHistory('redo'));
        byId('Save').onclick = () => operate(saveChanges);
        viewport.bindWheel();
        byId('Fit').onclick = () => {
            resetPan(); zoom = 100; fitZoom();
            svg.parentElement.scrollLeft = 0; svg.parentElement.scrollTop = 0;
            byId('ZoomLabel').textContent = '100%'; render();
        };
        function keyboard(event) {
            if (promptSession && !['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName) && !event.target.isContentEditable) {
                if (event.key === 'Escape') { event.preventDefault(); byId('PromptCancel').click(); }
                if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === 'z') { event.preventDefault(); byId('PromptUndo').click(); }
                return;
            }
            if (document.getElementById('projectDialog').open || document.querySelector('.modal:not(.hidden)') || busy) return;
            if (labelObject !== null) {
                if (event.key === 'Escape') { event.preventDefault(); byId('LabelClose').click(); }
                return;
            }
            if (camera.isPanning) {
                if (event.key === 'Escape') { event.preventDefault(); endPan(true); }
                return;
            }
            if (drag) {
                if (event.key === 'Escape') { event.preventDefault(); endDrag(true); }
                return;
            }
            if (['INPUT', 'TEXTAREA', 'SELECT'].includes(event.target.tagName) || event.target.isContentEditable) return;
            if (localTools.session) return localTools.keyboard(event);
            if (['1', '2', '3'].includes(event.key) && !event.ctrlKey && !event.metaKey && !event.altKey) {
                event.preventDefault(); byId({ '1': 'Draw', '2': 'Rectangle', '3': 'Circle' }[event.key]).click(); return;
            }
            if (!event.ctrlKey && !event.metaKey && !event.altKey && draft === null && event.key.length === 1) {
                const cls = classes.find(item => item.hotkey === event.key.toLowerCase() && !window.SAM2ClassManager.isReservedHotkey(item.hotkey, reservedHotkeys));
                if (cls) { event.preventDefault(); byId('Class').value = String(cls.id); renderClasses(); render(); return; }
            }
            if (event.key === 'Escape') { if (draft !== null) byId('Cancel').click(); else { selected = null; proposalSelection.clear(); render(); } }
            if (event.key === 'Delete' && !event.ctrlKey && !event.metaKey && !event.altKey && draft === null && selected !== null) {
                event.preventDefault(); return byId('Delete').click();
            }
            if (event.key === 'Backspace' && draft !== null) { event.preventDefault(); draft.pop(); render(); }
            if (event.key === 'Enter' && draft?.length >= requiredPoints()) { event.preventDefault(); byId('Finish').click(); }
            if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
                event.preventDefault(); return byId(event.shiftKey ? 'Redo' : 'Undo').click();
            }
        }
        document.addEventListener('keydown', keyboard);
        renderClasses(); render();
        return { canLeave, hasImages: () => queue.length > 0, resume: resumeWorkspace, dispose() { disposed = true; endPan(); viewport.unbindPanning(); resizeObserver.disconnect(); viewport.unbindWheel(); window.removeEventListener('beforeunload', beforeUnload); document.removeEventListener('keydown', keyboard); } };
    }
    window.SAM2PolygonEditor = { mount };
})();
