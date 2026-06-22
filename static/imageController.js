(() => {
    const fileUtils = window.SAM2FileUtils;
    if (!fileUtils) {
        throw new Error('SAM2FileUtils must be loaded before imageController.js.');
    }

    function createImageRecord(file, imageElement = null, index = 0) {
        const displayPath = file.webkitRelativePath || file.name;
        const publicBaseName = `image_${String(index + 1).padStart(5, '0')}`;
        const extension = fileUtils.imageExtension(file.name);
        return {
            id: `${displayPath}:${file.size}:${file.lastModified}`,
            name: file.name,
            displayPath,
            publicName: `${publicBaseName}${extension}`,
            publicDisplayPath: `${publicBaseName}${extension}`,
            file,
            originalImage: imageElement,
            processedImage: null,
            preprocessMethod: 'original',
            preprocessLabel: '',
            preprocessParams: null,
            claheApplied: false,
            samHasRun: false,
            serverAnnotationsChecked: false
        };
    }

    function loadImageElement(src, ImageCtor = Image) {
        return new Promise((resolve, reject) => {
            const img = new ImageCtor();
            img.onload = () => resolve(img);
            img.onerror = () => reject(new Error('Failed to load the image returned by the server.'));
            img.src = src;
        });
    }

    function getImageBadges(imageRecord, context) {
        const {
            annotations = [],
            candidates = [],
            isDirty = false,
            match = null,
            currentAnnotationFormat,
            formatLabel,
            hasActivePreprocess,
            preprocessBadgeLabel,
            preprocessLabel,
            publicAnnotationPath
        } = context;
        const badges = [];

        if (annotations.length > 0) {
            badges.push({ type: 'annotated', label: `Ann ${annotations.length}`, title: `${annotations.length} annotations` });
        }
        if (isDirty) {
            badges.push({ type: 'dirty', label: 'Unsaved', title: 'Unsaved changes' });
        }
        if (candidates.length > 0) {
            badges.push({ type: 'candidates', label: `Cand ${candidates.length}`, title: `${candidates.length} SAM candidates` });
        }
        if (hasActivePreprocess(imageRecord)) {
            badges.push({
                type: 'preprocess',
                label: preprocessBadgeLabel(imageRecord.preprocessMethod),
                title: `${preprocessLabel(imageRecord.preprocessMethod)} is active for display; SAM applies the same preprocessing on the server`
            });
        }
        if (imageRecord.samHasRun && candidates.length === 0) {
            badges.push({ type: 'sam', label: 'SAM 0', title: 'SAM has run but no candidates are currently shown' });
        }

        if (match) {
            if (match.status === 'matched') {
                const matchFormat = formatLabel(match.format || currentAnnotationFormat());
                badges.push({
                    type: 'matched',
                    label: 'Matched',
                    title: `Matched ${matchFormat}: ${publicAnnotationPath(match.path)}${match.annotation_count ? ` (${match.annotation_count} annotations)` : ''}`
                });
            } else if (match.status === 'ambiguous') {
                badges.push({ type: 'ambiguous', label: 'Ambiguous', title: match.message || 'Ambiguous annotation match' });
            } else if (match.status === 'missing') {
                badges.push({ type: 'missing', label: 'Missing', title: 'No matching annotation file found' });
            }
        }

        return badges;
    }

    function imageStateSummary(imageRecord, context) {
        const {
            annotations = [],
            candidates = [],
            isDirty = false,
            match = null,
            currentAnnotationFormat,
            formatLabel,
            hasActivePreprocess,
            preprocessLabel
        } = context;
        const parts = [
            `${annotations.length} annotations`,
            `${candidates.length} candidates`,
        ];

        if (isDirty) {
            parts.push('unsaved');
        }
        if (hasActivePreprocess(imageRecord)) {
            parts.push(`${preprocessLabel(imageRecord.preprocessMethod)} display/server SAM preprocessing`);
        }
        if (match?.status) {
            parts.push(`${formatLabel(match.format || currentAnnotationFormat())} ${match.status}`);
        }

        return parts.join(' | ');
    }

    function imageDimensions(imageRecord) {
        const image = imageRecord?.originalImage || imageRecord?.processedImage;
        if (!image || !image.width || !image.height) return null;
        return { width: image.width, height: image.height };
    }

    function imagePayloads(images = []) {
        return images.map(imageRecord => {
            const size = imageDimensions(imageRecord);
            return {
                id: imageRecord.id,
                name: imageRecord.name,
                display_path: imageRecord.displayPath,
                width: size ? size.width : null,
                height: size ? size.height : null
            };
        });
    }

    window.SAM2ImageController = {
        createImageRecord,
        loadImageElement,
        getImageBadges,
        imageStateSummary,
        imageDimensions,
        imagePayloads
    };
})();
