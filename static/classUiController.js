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
        classManager.innerHTML = '';

        if (classes.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'class-empty-state';
            empty.textContent = 'No classes yet. Add a class or import annotations with class labels.';
            classManager.appendChild(empty);
        }

        classes.forEach((cls, index) => {
            const row = document.createElement('div');
            row.className = 'class-row';
            row.dataset.classIndex = String(index);

            const colorInput = document.createElement('input');
            colorInput.type = 'color';
            colorInput.className = 'class-color-input';
            colorInput.value = cls.color;
            colorInput.title = `Color for ${cls.name}`;

            const nameInput = document.createElement('input');
            nameInput.type = 'text';
            nameInput.className = 'class-name-input';
            nameInput.value = cls.name;
            nameInput.placeholder = 'Class name';
            nameInput.title = 'Class name';

            const hotkeyInput = document.createElement('input');
            hotkeyInput.type = 'text';
            hotkeyInput.className = 'class-hotkey-input';
            hotkeyInput.value = cls.hotkey ? cls.hotkey.toUpperCase() : '';
            hotkeyInput.placeholder = '-';
            hotkeyInput.maxLength = 1;
            hotkeyInput.title = 'Optional keyboard shortcut';

            const hotkeyField = document.createElement('label');
            hotkeyField.className = 'class-hotkey-field';
            hotkeyField.title = 'Optional keyboard shortcut';

            const hotkeyLabel = document.createElement('span');
            hotkeyLabel.textContent = 'Hotkey';

            const deleteButton = document.createElement('button');
            deleteButton.type = 'button';
            deleteButton.className = 'btn btn-secondary class-delete-btn';
            deleteButton.textContent = 'X';
            deleteButton.title = `Delete ${cls.name}`;

            hotkeyField.appendChild(hotkeyLabel);
            hotkeyField.appendChild(hotkeyInput);

            row.appendChild(colorInput);
            row.appendChild(nameInput);
            row.appendChild(hotkeyField);
            row.appendChild(deleteButton);
            classManager.appendChild(row);
        });

        renderClassOptions(classificationSelect, classes, preferredClassName);
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
