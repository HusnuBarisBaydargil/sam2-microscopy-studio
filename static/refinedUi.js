// Presentation-only controls for the copied UI. Annotation state stays in the app.
(() => {
    const workspace = document.querySelector('.app-container');
    const toggles = [
        ['toggleProjectPanelBtn', 'projectPanel', 'project-collapsed'],
        ['toggleAnnotationPanelBtn', 'annotationPanel', 'annotation-collapsed']
    ];

    toggles.forEach(([buttonId, panelId, className]) => {
        const button = document.getElementById(buttonId);
        const panel = document.getElementById(panelId);
        button.addEventListener('click', () => {
            const collapsed = workspace.classList.toggle(className);
            panel.hidden = collapsed;
            button.setAttribute('aria-expanded', String(!collapsed));
            const label = `${collapsed ? 'Expand' : 'Collapse'} ${panelId === 'projectPanel' ? 'images and SAM2' : 'classes and annotation'} panel`;
            button.setAttribute('aria-label', label);
            button.title = label;
            window.dispatchEvent(new Event('workspace-panels-changed'));
        });
    });

    const exportMenu = document.getElementById('projectExportMenu');
    const exportTrigger = exportMenu.querySelector('summary');
    // Capture keys before the annotation workspace shortcuts see them.
    document.addEventListener('keydown', event => {
        if (!exportMenu.open) return;
        event.stopPropagation();
        if (event.key === 'Escape') {
            event.preventDefault();
            exportMenu.open = false;
            exportTrigger.focus();
        }
    }, true);
    document.addEventListener('pointerdown', event => {
        if (exportMenu.open && !exportMenu.contains(event.target)) exportMenu.open = false;
    });
    exportMenu.addEventListener('focusout', event => {
        if (event.relatedTarget && !exportMenu.contains(event.relatedTarget)) exportMenu.open = false;
    });
    exportMenu.addEventListener('click', event => {
        if (event.target.closest('button')) {
            exportMenu.open = false;
            if (exportMenu.contains(document.activeElement)) exportTrigger.focus();
        }
    });

    document.getElementById('classificationSelect').addEventListener('change', event => {
        document.querySelectorAll('.class-select-btn').forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.className === event.target.value));
        });
    });
    const classNameInput = document.getElementById('quickClassInput');
    function cancelClassCreation() {
        classNameInput.closest('.quick-class-row').hidden = true;
        classNameInput.value = '';
        document.getElementById('addClassBtn').focus();
    }
    document.getElementById('cancelQuickClassBtn').addEventListener('click', cancelClassCreation);
    classNameInput.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            event.stopPropagation();
            cancelClassCreation();
        }
    });

    document.querySelectorAll('label[role="button"][for]').forEach(label => {
        label.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                document.getElementById(label.htmlFor).click();
            }
        });
    });

    // The export disclosure changes header height, including on narrow screens.
    // Observe the canvas container so all layout changes resize its backing store.
    const canvasContainer = document.getElementById('canvas-container');
    const observer = new ResizeObserver(() => window.dispatchEvent(new Event('resize')));
    observer.observe(canvasContainer);
})();
