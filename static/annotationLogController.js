(() => {
    function annotationIdFromRowEvent(event) {
        const row = event.target.closest('tr');
        if (!row) return null;

        const id = parseInt(row.dataset.annotationId, 10);
        return Number.isInteger(id) ? id : null;
    }

    function applyLogSelection(state, event) {
        const id = annotationIdFromRowEvent(event);
        if (id === null) return false;

        if (event.shiftKey || event.ctrlKey || event.metaKey) {
            if (state.selectedAnnotationIds.has(id)) {
                state.selectedAnnotationIds.delete(id);
            } else {
                state.selectedAnnotationIds.add(id);
            }
            state.selectedCandidateIds.clear();
            return true;
        }

        if (state.selectedAnnotationIds.has(id)) {
            state.selectedAnnotationIds.clear();
            return true;
        }

        state.selectedAnnotationIds.clear();
        state.selectedAnnotationIds.add(id);
        state.selectedCandidateIds.clear();
        return true;
    }

    function openContextMenu(refs, state, event) {
        event.preventDefault();
        const id = annotationIdFromRowEvent(event);
        if (id === null) return false;

        state.logItemToModify = id;
        refs.logContextMenu.style.left = `${event.clientX}px`;
        refs.logContextMenu.style.top = `${event.clientY}px`;
        refs.logContextMenu.classList.remove('hidden');
        return true;
    }

    function hideContextMenu(refs) {
        refs.logContextMenu.classList.add('hidden');
    }

    function renderAnnotationLog(refs, annotations, selectedAnnotationIds) {
        refs.annotationLogBody.innerHTML = '';
        renderLogHint(refs, annotations.length > 0);

        if (annotations.length === 0) {
            refs.annotationLogBody.appendChild(emptyLogRow());
            return;
        }

        annotations
            .slice()
            .sort((a, b) => a.id - b.id)
            .forEach(annotation => {
                const row = document.createElement('tr');
                row.dataset.annotationId = annotation.id;
                if (selectedAnnotationIds.has(annotation.id)) {
                    row.classList.add('highlighted');
                }

                const bboxString = `(${annotation.bbox.map(value => Math.round(value)).join(', ')})`;
                [annotation.id, annotation.class, bboxString].forEach(value => {
                    const cell = document.createElement('td');
                    cell.textContent = String(value);
                    row.appendChild(cell);
                });
                refs.annotationLogBody.appendChild(row);
            });
    }

    function renderLogHint(refs, hasAnnotations) {
        refs.annotationLogHint.textContent = hasAnnotations
            ? 'Click row to select. Right-click to delete.'
            : '';
        refs.annotationLogHint.classList.toggle('hidden', !hasAnnotations);
    }

    function emptyLogRow() {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 3;
        cell.className = 'annotation-empty-state';

        const title = document.createElement('div');
        title.className = 'annotation-empty-title';
        title.textContent = 'No annotations yet.';

        const detail = document.createElement('div');
        detail.className = 'annotation-empty-detail';
        detail.textContent = 'Generate SAM2 candidates, assign a class, or draw a manual box.';

        cell.appendChild(title);
        cell.appendChild(detail);
        row.appendChild(cell);
        return row;
    }

    function renderAnnotationInspector(refs, selectedAnnotations) {
        const hasSingleSelection = selectedAnnotations.length === 1;

        if (selectedAnnotations.length === 0) {
            refs.selectedAnnotationSummary.textContent = 'No selected box';
        } else if (hasSingleSelection) {
            refs.selectedAnnotationSummary.textContent = `Box #${selectedAnnotations[0].id} selected`;
        } else {
            refs.selectedAnnotationSummary.textContent = `${selectedAnnotations.length} selected`;
        }

        inspectorControls(refs).forEach(control => {
            control.disabled = !hasSingleSelection;
        });

        if (!hasSingleSelection) {
            clearInspectorInputs(refs);
            return;
        }

        const [x, y, w, h] = selectedAnnotations[0].bbox;
        refs.bboxXInput.value = Math.round(x);
        refs.bboxYInput.value = Math.round(y);
        refs.bboxWInput.value = Math.round(w);
        refs.bboxHInput.value = Math.round(h);
    }

    function readInspectorBboxInputs(refs) {
        const rawValues = [
            refs.bboxXInput.value,
            refs.bboxYInput.value,
            refs.bboxWInput.value,
            refs.bboxHInput.value
        ].map(value => value.trim());
        const parsedValues = rawValues.map(Number);
        return {
            rawValues,
            parsedValues,
            valid: !rawValues.some(value => value === '') && parsedValues.every(Number.isFinite)
        };
    }

    function inspectorControls(refs) {
        return [
            refs.bboxXInput,
            refs.bboxYInput,
            refs.bboxWInput,
            refs.bboxHInput,
            refs.applyBoxEditBtn
        ];
    }

    function clearInspectorInputs(refs) {
        refs.bboxXInput.value = '';
        refs.bboxYInput.value = '';
        refs.bboxWInput.value = '';
        refs.bboxHInput.value = '';
    }

    window.SAM2AnnotationLogController = {
        annotationIdFromRowEvent,
        applyLogSelection,
        openContextMenu,
        hideContextMenu,
        renderAnnotationLog,
        renderAnnotationInspector,
        readInspectorBboxInputs
    };
})();
