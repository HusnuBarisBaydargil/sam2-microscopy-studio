(() => {
    const fileUtils = window.SAM2FileUtils;
    if (!fileUtils) {
        throw new Error('SAM2FileUtils must be loaded before imageController.js.');
    }

    const IMAGE_QUEUE_FILTERS = new Set([
        'all',
        'unannotated',
        'has_candidates',
        'annotated',
        'unsaved',
        'missing_matched'
    ]);

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
                const matchFormat = formatLabel(match.format || currentAnnotationFormat());
                badges.push({ type: 'missing', label: 'No saved annotation', title: `No saved ${matchFormat} annotation file found` });
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
            `${candidates.length} SAM candidates`,
        ];

        if (isDirty) {
            parts.push('unsaved changes');
        }
        if (hasActivePreprocess(imageRecord)) {
            parts.push(`${preprocessLabel(imageRecord.preprocessMethod)} preprocessing active`);
        }
        if (match?.status) {
            const matchFormat = formatLabel(match.format || currentAnnotationFormat());
            parts.push(match.status === 'missing' ? `No saved ${matchFormat}` : `${matchFormat} ${match.status}`);
        }

        return parts.join(', ');
    }

    function imageDimensions(imageRecord) {
        const image = imageRecord?.originalImage || imageRecord?.processedImage;
        if (!image || !image.width || !image.height) return null;
        return { width: image.width, height: image.height };
    }

    function imageQueueState(context) {
        const {
            annotations = [],
            candidates = [],
            isDirty = false,
            match = null
        } = context;
        return {
            annotated: annotations.length > 0,
            hasCandidates: candidates.length > 0,
            unsaved: Boolean(isDirty),
            missingMatched: match?.status === 'missing'
        };
    }

    function normalizeQueueFilter(filter) {
        return IMAGE_QUEUE_FILTERS.has(filter) ? filter : 'all';
    }

    function imageMatchesQueueFilter(queueState, filter) {
        switch (normalizeQueueFilter(filter)) {
            case 'unannotated':
                return !queueState.annotated;
            case 'has_candidates':
                return queueState.hasCandidates;
            case 'annotated':
                return queueState.annotated;
            case 'unsaved':
                return queueState.unsaved;
            case 'missing_matched':
                return queueState.missingMatched;
            case 'all':
            default:
                return true;
        }
    }

    function imageQueueProgressSummary(queueStates) {
        return queueStates.reduce((summary, queueState) => {
            summary.total += 1;
            if (queueState.annotated) summary.annotated += 1;
            if (queueState.unsaved) summary.unsaved += 1;
            if (queueState.hasCandidates) summary.candidates += 1;
            return summary;
        }, {
            total: 0,
            annotated: 0,
            unsaved: 0,
            candidates: 0
        });
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
        imageQueueState,
        normalizeQueueFilter,
        imageMatchesQueueFilter,
        imageQueueProgressSummary,
        imagePayloads
    };
})();
