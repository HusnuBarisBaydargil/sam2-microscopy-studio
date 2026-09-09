// Accessible DOM controls for a pending manual box; geometry stays in the controller.
(() => {
    let previousChoice = null;
    let previousClasses = '';
    function sync({ container, choice, classes, activeClass, onSelect, onCreate, onCancel }) {
        let panel = container.querySelector('.manual-class-picker');
        if (!choice) {
            panel?.remove();
            previousChoice = null;
            return;
        }
        const classSignature = JSON.stringify([classes, activeClass]);
        if (choice !== previousChoice || classSignature !== previousClasses || !panel) {
            panel?.remove();
            panel = document.createElement('div');
            panel.className = 'manual-class-picker';
            panel.setAttribute('role', 'group');
            panel.setAttribute('aria-label', 'Classify new annotation');
            const heading = document.createElement('div');
            heading.className = 'picker-heading';
            heading.textContent = classes.length ? 'Classify new annotation' : 'Create your first class';
            panel.appendChild(heading);
            const choices = document.createElement('div');
            choices.className = 'picker-classes';
            const ordered = [...classes].sort((a, b) => Number(b.name === activeClass) - Number(a.name === activeClass));
            ordered.slice(0, 3).forEach(cls => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `btn ${cls.name === activeClass ? 'btn-primary' : 'btn-secondary'}`;
                const swatch = document.createElement('span');
                swatch.className = 'class-swatch';
                swatch.style.backgroundColor = cls.color;
                button.append(swatch, document.createTextNode(cls.name));
                if (cls.hotkey && !window.SAM2ClassManager?.isReservedHotkey?.(cls.hotkey)) {
                    const key = document.createElement('kbd');
                    key.textContent = cls.hotkey.toUpperCase();
                    button.appendChild(key);
                }
                button.addEventListener('click', () => onSelect(cls.name));
                choices.appendChild(button);
            });
            panel.appendChild(choices);
            if (classes.length > 3) {
                const select = document.createElement('select');
                select.className = 'form-control';
                select.setAttribute('aria-label', 'Choose another class');
                const placeholder = document.createElement('option');
                placeholder.value = '';
                placeholder.textContent = 'Choose class…';
                select.appendChild(placeholder);
                classes.forEach(cls => {
                    const option = document.createElement('option');
                    option.value = cls.name;
                    option.textContent = cls.name;
                    select.appendChild(option);
                });
                select.addEventListener('change', () => { if (select.value) onSelect(select.value); });
                panel.appendChild(select);
            }
            const actions = document.createElement('div');
            actions.className = 'picker-actions';
            const create = document.createElement('button');
            create.type = 'button';
            create.className = 'btn btn-secondary';
            create.textContent = 'Create class…';
            const cancel = document.createElement('button');
            cancel.type = 'button';
            cancel.className = 'btn btn-secondary';
            cancel.textContent = 'Cancel';
            cancel.addEventListener('click', onCancel);
            actions.append(create, cancel);
            panel.appendChild(actions);
            const form = document.createElement('form');
            form.className = 'picker-create-form';
            form.hidden = classes.length > 0;
            create.hidden = classes.length === 0;
            const input = document.createElement('input');
            input.className = 'form-control';
            input.placeholder = 'New class name';
            input.setAttribute('aria-label', 'New class name for this annotation');
            input.required = true;
            const submit = document.createElement('button');
            submit.type = 'submit';
            submit.className = 'btn btn-primary';
            submit.textContent = 'Create & apply';
            form.append(input, submit);
            form.addEventListener('submit', event => {
                event.preventDefault();
                if (input.value.trim()) onCreate(input.value);
                else input.focus();
            });
            create.addEventListener('click', () => { form.hidden = false; position(); input.focus(); });
            panel.appendChild(form);
            panel.addEventListener('keydown', event => {
                if (event.key === 'Escape') { event.stopPropagation(); onCancel(); }
            });
            container.appendChild(panel);
            previousChoice = choice;
            previousClasses = classSignature;
            position();
            (classes.length ? (choices.querySelector('button') || create) : input).focus({ preventScroll: true });
        }
        position();
        function position() {
            const { x, y, w, h } = choice.rect;
            const left = Math.min(x, x + w);
            const bottom = Math.max(y, y + h);
            const top = bottom + 8 + panel.offsetHeight <= container.clientHeight
                ? bottom + 8 : Math.min(y, y + h) - panel.offsetHeight - 8;
            panel.style.left = `${Math.max(4, Math.min(left, container.clientWidth - panel.offsetWidth - 4))}px`;
            panel.style.top = `${Math.max(4, Math.min(top, container.clientHeight - panel.offsetHeight - 4))}px`;
        }
    }
    window.SAM2ManualClassPicker = { sync };
})();
