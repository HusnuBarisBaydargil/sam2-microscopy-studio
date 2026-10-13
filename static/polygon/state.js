(() => {
    function createPolygonState(document) {
        let current = structuredClone(document);
        let saved = JSON.stringify(current);
        // Class names live outside the document but change its exported labels.
        let classRevision = 0, savedClassRevision = 0, nextClassRevision = 0;
        const undo = [], redo = [];
        let proposals = [];
        const snapshot = () => structuredClone({ annotations: current.annotations, labelme: current.labelme, review_status: current.review_status, proposals, classRevision });
        const classSnapshot = (change, classes) => ({ ...change, item: structuredClone(classes.find(item => item.id === change.id) || null) });
        function restore(previous) {
            current.annotations = previous.annotations;
            if (previous.labelme === undefined) delete current.labelme;
            else current.labelme = previous.labelme;
            if (previous.review_status === undefined) delete current.review_status;
            else current.review_status = previous.review_status;
            proposals = previous.proposals;
            classRevision = previous.classRevision;
        }
        return {
            get document() { return current; },
            get proposals() { return proposals; },
            setProposals(items) { undo.push(snapshot()); redo.length = 0; proposals = structuredClone(items); },
            get dirty() { return classRevision !== savedClassRevision || JSON.stringify(current) !== saved; },
            get canUndo() { return undo.length > 0; },
            get canRedo() { return redo.length > 0; },
            change(annotations, nextId = current.next_object_id, nextProposals = proposals, labelme = current.labelme, classChange = null) {
                undo.push({ ...snapshot(), ...(classChange ? { classChange: structuredClone(classChange) } : {}) });
                redo.length = 0;
                if (classChange) classRevision = ++nextClassRevision;
                current.annotations = structuredClone(annotations);
                current.review_status = annotations.length ? 'in_progress' : 'unreviewed';
                proposals = structuredClone(nextProposals);
                if (labelme === undefined) delete current.labelme;
                else current.labelme = structuredClone(labelme);
                current.next_object_id = Math.max(current.next_object_id, nextId);
            },
            setReview(status) {
                undo.push(snapshot()); redo.length = 0; current.review_status = status;
            },
            undo(classes) {
                if (!undo.length) return;
                const previous = undo.pop();
                redo.push({ ...snapshot(), ...(previous.classChange ? { classChange: classSnapshot(previous.classChange, classes) } : {}) });
                restore(previous);
                return previous.classChange;
            },
            redo(classes) {
                if (!redo.length) return;
                const previous = redo.pop();
                undo.push({ ...snapshot(), ...(previous.classChange ? { classChange: classSnapshot(previous.classChange, classes) } : {}) });
                restore(previous);
                return previous.classChange;
            },
            markSaved(document) {
                current = structuredClone(document);
                saved = JSON.stringify(current);
                savedClassRevision = classRevision;
            }
        };
    }
    window.SAM2PolygonState = { createPolygonState };
})();
