(() => {
    const frontendConfig = window.SAM2FrontendConfig;
    if (!frontendConfig) {
        throw new Error('SAM2FrontendConfig must be loaded before fileUtils.js.');
    }

    const {
        ALLOWED_IMAGE_EXTENSIONS,
        ALLOWED_IMAGE_MIME_TYPES
    } = frontendConfig;

    function basename(path) {
        return String(path || '').split(/[\\/]/).pop();
    }

    function imageExtension(fileName) {
        const match = String(fileName || '').match(/\.[^.\\/]+$/);
        return match ? match[0].toLowerCase() : '';
    }

    function safeImageStem(imageName) {
        return stripExtension(safeFilePart(basename(imageName || 'image'))) || 'image';
    }

    function safePathStem(imagePath) {
        const parts = String(imagePath || '')
            .replace(/\\/g, '/')
            .split('/')
            .map(part => safeFilePart(part))
            .filter(Boolean);
        if (parts.length === 0) return safeImageStem(imagePath);
        return parts
            .map((part, index) => index === parts.length - 1 ? stripExtension(part) : part)
            .filter(Boolean)
            .join('__') || safeImageStem(imagePath);
    }

    function safeFilePart(value) {
        return String(value || '')
            .trim()
            .replace(/[^A-Za-z0-9_.-]+/g, '_')
            .replace(/^_+|_+$/g, '');
    }

    function stripExtension(fileName) {
        return String(fileName || '').replace(/\.[^/.]+$/, '');
    }

    function annotationFileNames(imageName, imagePath, matchMode, annotationFormat) {
        const stem = matchMode === 'path' && imagePath
            ? safePathStem(imagePath)
            : safeImageStem(imageName);

        if (annotationFormat === 'yolo') return [`${stem}.txt`, `${stem}_annotations.txt`];
        if (annotationFormat === 'coco') return [`${stem}_annotations.json`, `${stem}.json`];
        if (annotationFormat === 'voc') return [`${stem}.xml`, `${stem}_annotations.xml`];
        if (annotationFormat === 'csv_rich') return [`${stem}_annotations_rich.csv`, `${stem}_annotations.csv`];
        return [`${stem}_annotations.csv`];
    }

    function publicImageName(imageRecord, phiSafeMode = false) {
        if (!imageRecord) return 'unknown_image';
        return phiSafeMode ? imageRecord.publicName : imageRecord.name;
    }

    function publicImagePath(imageRecord, phiSafeMode = false) {
        if (!imageRecord) return '';
        return phiSafeMode ? imageRecord.publicDisplayPath : imageRecord.displayPath;
    }

    function publicAnnotationPath(path, phiSafeMode = false) {
        if (!path) return '';
        return phiSafeMode ? 'annotation file' : path;
    }

    function isSupportedImageFile(file) {
        const lowerName = String(file?.name || '').toLowerCase();
        const hasAllowedExtension = ALLOWED_IMAGE_EXTENSIONS.some(extension => lowerName.endsWith(extension));
        if (!hasAllowedExtension) return false;
        if (!file.type) return true;
        return ALLOWED_IMAGE_MIME_TYPES.has(file.type.toLowerCase());
    }

    function imageSortName(file) {
        return file?.webkitRelativePath || file?.name || '';
    }

    window.SAM2FileUtils = {
        basename,
        imageExtension,
        safeImageStem,
        safePathStem,
        safeFilePart,
        stripExtension,
        annotationFileNames,
        publicImageName,
        publicImagePath,
        publicAnnotationPath,
        isSupportedImageFile,
        imageSortName
    };
})();
