(() => {
    const frontendConfig = window.SAM2FrontendConfig;
    if (!frontendConfig) {
        throw new Error('SAM2FrontendConfig must be loaded before classManager.js.');
    }

    const { CLASS_COLOR_PALETTE } = frontendConfig;

    function normalizeClassName(value) {
        return String(value || '').trim().replace(/\s+/g, ' ');
    }

    function normalizeHotkey(value) {
        const match = String(value || '').trim().toLowerCase().match(/[a-z0-9]/);
        return match ? match[0] : '';
    }

    function getUniqueClassName(classes) {
        let index = classes.length + 1;
        let name = `Class ${index}`;

        while (classes.some(cls => cls.name === name)) {
            index++;
            name = `Class ${index}`;
        }

        return name;
    }

    function getFirstAvailableHotkey(className, classes) {
        const usedHotkeys = new Set(classes.map(cls => cls.hotkey).filter(Boolean));
        const candidates = [
            ...normalizeClassName(className).toLowerCase().replace(/[^a-z0-9]/g, ''),
            ...'abcdefghijklmnopqrstuvwxyz0123456789'
        ];

        return candidates.find(candidate => !usedHotkeys.has(candidate)) || '';
    }

    function classExists(classes, className) {
        return classes.some(cls => cls.name === className);
    }

    function buildNewClass(className, classes) {
        const normalizedName = normalizeClassName(className);
        return {
            name: normalizedName,
            color: CLASS_COLOR_PALETTE[classes.length % CLASS_COLOR_PALETTE.length],
            hotkey: getFirstAvailableHotkey(normalizedName, classes)
        };
    }

    function normalizeClassList(classes) {
        const seenNames = new Set();
        const seenHotkeys = new Set();
        const normalizedClasses = [];

        if (!Array.isArray(classes)) return [];

        classes.forEach((cls, index) => {
            const name = normalizeClassName(String(cls.name || ''));
            if (!name || seenNames.has(name)) return;

            const hotkey = normalizeHotkey(String(cls.hotkey || ''));
            const safeHotkey = hotkey && !seenHotkeys.has(hotkey) ? hotkey : '';
            const color = /^#[0-9a-f]{6}$/i.test(String(cls.color || ''))
                ? cls.color
                : CLASS_COLOR_PALETTE[index % CLASS_COLOR_PALETTE.length];

            normalizedClasses.push({ name, color, hotkey: safeHotkey });
            seenNames.add(name);
            if (safeHotkey) seenHotkeys.add(safeHotkey);
        });

        return normalizedClasses;
    }

    function ensureClassesForAnnotations(classes, annotations) {
        const nextClasses = classes.slice();
        const existingNames = new Set(nextClasses.map(cls => cls.name));
        let addedCount = 0;

        annotations.forEach(annotation => {
            const className = normalizeClassName(String(annotation.class || 'Unlabeled')) || 'Unlabeled';
            annotation.class = className;

            if (existingNames.has(className)) return;

            nextClasses.push(buildNewClass(className, nextClasses));
            existingNames.add(className);
            addedCount++;
        });

        return { classes: nextClasses, addedCount };
    }

    window.SAM2ClassManager = {
        normalizeClassName,
        normalizeHotkey,
        getUniqueClassName,
        getFirstAvailableHotkey,
        classExists,
        buildNewClass,
        normalizeClassList,
        ensureClassesForAnnotations
    };
})();
