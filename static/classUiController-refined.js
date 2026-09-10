(() => {
    function selectedClassName(classes, preferredClassName) {
        return classes.find(cls => cls.name === preferredClassName)
            ? preferredClassName
            : classes[0]?.name || '';
    }

    function renderClassOptions(classificationSelect, classes, preferredClassName = classificationSelect.value) {
        classificationSelect.innerHTML = '';
        if (classes.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'Create a class first';
            classificationSelect.appendChild(option);
            classificationSelect.value = '';
            return;
        }

        classes.forEach(cls => {
            const option = document.createElement('option');
            option.value = cls.name;
            option.textContent = cls.name;
            classificationSelect.appendChild(option);
        });

        classificationSelect.value = selectedClassName(classes, preferredClassName);
    }

    function renderClassControls(refs, classes, preferredClassName = refs.classificationSelect.value) {
        const { classManager, classificationSelect } = refs;
        const openEditors = new Set(Array.from(classManager.querySelectorAll('.class-editor[open]'))
            .map(editor => editor.closest('.class-row').dataset.classId));
        const focused = document.activeElement;
        const editing = classManager.contains(focused) && focused.tagName === 'INPUT' ? {
            id: focused.closest('.class-row').dataset.classId,
            field: focused.className,
            value: focused.value,
            start: focused.selectionStart,
            end: focused.selectionEnd
        } : null;
        classManager.innerHTML = '';

        if (classes.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'class-empty-state';
            empty.textContent = 'Name the objects you want to annotate. No classes are supplied automatically.';
            classManager.appendChild(empty);
        }

        classes.forEach((cls, index) => {
            const row = document.createElement('div');
            row.className = 'class-row';
            row.dataset.classIndex = String(index);
            row.dataset.classId = String(cls.id ?? index);

            const selectButton = document.createElement('button');
            selectButton.type = 'button';
            selectButton.className = 'class-select-btn';
            selectButton.dataset.className = cls.name;
            const swatch = document.createElement('span');
            swatch.className = 'class-swatch';
            swatch.style.backgroundColor = cls.color;
            const name = document.createElement('span');
            name.className = 'class-display-name';
            name.textContent = cls.name;
            const key = document.createElement('kbd');
            const reserved = window.SAM2ClassManager.isReservedHotkey(cls.hotkey);
            key.textContent = cls.hotkey ? `${cls.hotkey.toUpperCase()}${reserved ? ' reserved' : ''}` : '';
            if (reserved) key.title = 'This shortcut belongs to an app tool. Edit or clear it.';
            selectButton.append(swatch, name, key);
            row.appendChild(selectButton);
            const editor = document.createElement('details');
            editor.className = 'class-editor';
            editor.open = openEditors.has(row.dataset.classId);
            const edit = document.createElement('summary');
            const updateEditorToggle = () => {
                edit.textContent = editor.open ? '×' : 'Edit';
                edit.setAttribute('aria-label', `${editor.open ? 'Close editor for' : 'Edit class'} ${cls.name}`);
                edit.title = editor.open ? 'Close class editor' : 'Edit class';
            };
            updateEditorToggle();
            editor.addEventListener('toggle', updateEditorToggle);
            editor.appendChild(edit);
            const fields = document.createElement('div');
            fields.className = 'class-editor-fields';

            const colorInput = document.createElement('input');
            colorInput.type = 'color';
            colorInput.className = 'class-color-input';
            colorInput.value = cls.color;
            colorInput.title = `Color for ${cls.name}`;
            colorInput.setAttribute('aria-label', `Color for ${cls.name}`);

            const nameInput = document.createElement('input');
            nameInput.type = 'text';
            nameInput.className = 'class-name-input';
            nameInput.value = cls.name;
            nameInput.placeholder = 'Class name';
            nameInput.title = 'Class name';
            nameInput.setAttribute('aria-label', 'Class name');

            const hotkeyInput = document.createElement('input');
            hotkeyInput.type = 'text';
            hotkeyInput.className = 'class-hotkey-input';
            hotkeyInput.value = cls.hotkey ? cls.hotkey.toUpperCase() : '';
            hotkeyInput.placeholder = '-';
            hotkeyInput.maxLength = 1;
            hotkeyInput.title = 'Optional shortcut; B (Manual Box) and U (Undo) are reserved.';
            hotkeyInput.setAttribute('aria-invalid', String(reserved));
            hotkeyInput.setAttribute('aria-label', `Shortcut for ${cls.name}`);

            const hotkeyField = document.createElement('label');
            hotkeyField.className = 'class-hotkey-field';
            hotkeyField.title = 'Optional keyboard shortcut';

            const hotkeyLabel = document.createElement('span');
            hotkeyLabel.textContent = 'Hotkey';

            const deleteButton = document.createElement('button');
            deleteButton.type = 'button';
            deleteButton.className = 'btn btn-secondary class-delete-btn';
            deleteButton.textContent = 'Remove class';
            deleteButton.title = `Remove ${cls.name} from the class list; annotations are preserved`;

            hotkeyField.appendChild(hotkeyLabel);
            hotkeyField.appendChild(hotkeyInput);

            fields.appendChild(colorInput);
            fields.appendChild(nameInput);
            fields.appendChild(hotkeyField);
            fields.appendChild(deleteButton);
            editor.appendChild(fields);
            row.appendChild(editor);
            classManager.appendChild(row);
        });

        renderClassOptions(classificationSelect, classes, preferredClassName);
        classManager.querySelectorAll('.class-select-btn').forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.className === classificationSelect.value));
        });
        if (editing) {
            const row = Array.from(classManager.querySelectorAll('.class-row'))
                .find(candidate => candidate.dataset.classId === editing.id);
            const input = row?.querySelector(`.${editing.field}`);
            if (input) {
                input.value = editing.value;
                input.focus({ preventScroll: true });
                if (editing.start !== null) input.setSelectionRange(editing.start, editing.end);
            }
        }
    }

    function syncClassControlStates(refs, state) {
        const {
            classificationSelect,
            applyClassificationBtn,
            oneClickAcceptInput,
            quickClassInput,
            quickAddClassBtn
        } = refs;
        const {
            imageLoaded,
            selectionExists,
            classesExist,
            candidatesExist,
            activeClassName = classesExist ? 'active' : ''
        } = state;

        classificationSelect.disabled = !classesExist;
        applyClassificationBtn.disabled = !selectionExists || !classesExist;
        oneClickAcceptInput.disabled = !imageLoaded || !classesExist || !candidatesExist || !activeClassName;
        if (oneClickAcceptInput.disabled) oneClickAcceptInput.checked = false;
        quickClassInput.disabled = false;
        quickAddClassBtn.disabled = false;
    }

    function getClassRowIndex(element) {
        const row = element.closest('.class-row');
        if (!row) return null;

        const index = parseInt(row.dataset.classIndex, 10);
        return Number.isInteger(index) ? index : null;
    }

    window.SAM2ClassUiController = {
        selectedClassName,
        renderClassOptions,
        renderClassControls,
        syncClassControlStates,
        getClassRowIndex
    };
})();
