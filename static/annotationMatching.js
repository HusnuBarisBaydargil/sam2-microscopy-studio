(() => {
    const fileUtils = window.SAM2FileUtils;
    if (!fileUtils) {
        throw new Error('SAM2FileUtils must be loaded before annotationMatching.js.');
    }

    const {
        annotationFileNames,
        basename,
        safeImageStem
    } = fileUtils;

    function localAnnotationSourceActive(annotationSource) {
        return annotationSource?.mode === 'local' && Array.isArray(annotationSource.files) && annotationSource.files.length > 0;
    }

    function buildLocalAnnotationSource(annotationFiles, { phiSafeMode = false } = {}) {
        const fileMap = new Map();
        annotationFiles.forEach(file => {
            const key = basename(file.name).toLowerCase();
            if (!fileMap.has(key)) fileMap.set(key, []);
            fileMap.get(key).push(file);
        });

        const folderNames = new Set(annotationFiles
            .map(file => file.webkitRelativePath ? file.webkitRelativePath.split('/')[0] : '')
            .filter(Boolean));
        const displayName = phiSafeMode
            ? `${annotationFiles.length} local annotation files`
            : folderNames.size === 1
            ? `${annotationFiles.length} files from ${Array.from(folderNames)[0]}`
            : `${annotationFiles.length} local annotation files`;

        return {
            mode: 'local',
            files: annotationFiles,
            fileMap,
            displayName
        };
    }

    function annotationSourceTitle(annotationSource, { phiSafeMode = false } = {}) {
        if (!localAnnotationSourceActive(annotationSource)) return '';
        if (phiSafeMode) return 'PHI-safe mode hides local annotation source paths.';
        return annotationSource.files
            .slice(0, 20)
            .map(file => file.webkitRelativePath || file.name)
            .join('\n');
    }

    function duplicateImageStems(images) {
        const counts = new Map();
        images.forEach(imageRecord => {
            const stem = safeImageStem(imageRecord.name);
            counts.set(stem, (counts.get(stem) || 0) + 1);
        });
        return new Set(Array.from(counts.entries())
            .filter(([, count]) => count > 1)
            .map(([stem]) => stem));
    }

    function hasDuplicateImageName(images, imageRecord) {
        const normalizedName = imageRecord.name.toLowerCase();
        return images.filter(otherRecord => otherRecord.name.toLowerCase() === normalizedName).length > 1;
    }

    function annotationMatchModeForImage(imageRecord, images, existingMatch = null) {
        if (existingMatch?.status === 'matched' && existingMatch.match_mode) {
            return existingMatch.match_mode;
        }
        return hasDuplicateImageName(images, imageRecord) ? 'path' : 'basename';
    }

    function resolveLocalAnnotationMatch(imageRecord, duplicateStems, annotationFormat, fileMap, display = {}) {
        const candidates = localAnnotationCandidates(imageRecord, annotationFormat, fileMap);
        const pathCandidate = candidates.find(candidate => candidate.match_mode === 'path');
        const baseCandidate = candidates.find(candidate => candidate.match_mode === 'basename');
        const pathMatch = candidates.find(candidate => candidate.match_mode === 'path' && candidate.sourceFile);
        const baseMatch = candidates.find(candidate => candidate.match_mode === 'basename' && candidate.sourceFile);
        const pathDuplicate = candidates.find(candidate => candidate.match_mode === 'path' && candidate.duplicateFileCount > 1);
        const baseDuplicate = candidates.find(candidate => candidate.match_mode === 'basename' && candidate.duplicateFileCount > 1);
        const isDuplicateName = duplicateStems.has(safeImageStem(imageRecord.name));

        let chosen = null;
        let status = 'missing';
        let message = 'No matching local annotation file found.';

        if (isDuplicateName) {
            if (pathMatch) {
                chosen = pathMatch;
                status = 'matched';
                message = 'Matched local annotation by image folder path.';
            } else if (pathDuplicate) {
                chosen = pathDuplicate;
                status = 'ambiguous';
                message = 'Multiple local annotation files have the same path-specific filename.';
            } else if (baseMatch) {
                chosen = baseMatch;
                status = 'ambiguous';
                message = 'Duplicate image name; local basename annotation file could match more than one image.';
            } else if (baseDuplicate) {
                chosen = baseDuplicate;
                status = 'ambiguous';
                message = 'Multiple local annotation files have the same basename annotation filename.';
            } else {
                chosen = pathCandidate || baseCandidate;
            }
        } else if (baseMatch) {
            chosen = baseMatch;
            status = 'matched';
            message = 'Matched local annotation by image name.';
        } else if (baseDuplicate) {
            chosen = baseDuplicate;
            status = 'ambiguous';
            message = 'Multiple local annotation files have the same basename annotation filename.';
        } else if (pathMatch) {
            chosen = pathMatch;
            status = 'matched';
            message = 'Matched local annotation by image folder path.';
        } else if (pathDuplicate) {
            chosen = pathDuplicate;
            status = 'ambiguous';
            message = 'Multiple local annotation files have the same path-specific filename.';
        } else {
            chosen = baseCandidate || pathCandidate;
        }

        const path = chosen?.sourceFile
            ? (chosen.sourceFile.webkitRelativePath || chosen.sourceFile.name)
            : (chosen?.fileName || annotationFileNames(imageRecord.name, imageRecord.displayPath, 'basename', annotationFormat)[0]);

        return {
            id: imageRecord.id,
            name: display.name ?? imageRecord.name,
            display_path: display.displayPath ?? imageRecord.displayPath,
            format: annotationFormat,
            status,
            exists: status === 'matched',
            ambiguous: status === 'ambiguous',
            match_mode: chosen?.match_mode || 'basename',
            path: display.annotationPath ? display.annotationPath(path) : path,
            source: 'local',
            sourceFile: chosen?.sourceFile || null,
            annotation_count: 0,
            message,
        };
    }

    function localAnnotationCandidates(imageRecord, annotationFormat, fileMap) {
        const candidates = [];
        if (imageRecord.displayPath && imageRecord.displayPath !== imageRecord.name) {
            annotationFileNames(imageRecord.name, imageRecord.displayPath, 'path', annotationFormat)
                .forEach(fileName => candidates.push(localAnnotationCandidate(fileName, 'path', annotationFormat, fileMap)));
        }
        annotationFileNames(imageRecord.name, imageRecord.displayPath, 'basename', annotationFormat)
            .forEach(fileName => candidates.push(localAnnotationCandidate(fileName, 'basename', annotationFormat, fileMap)));
        return candidates;
    }

    function localAnnotationCandidate(fileName, matchMode, annotationFormat, fileMap) {
        const files = fileMap.get(fileName.toLowerCase()) || [];
        return {
            fileName,
            match_mode: matchMode,
            format: annotationFormat,
            sourceFile: files.length === 1 ? files[0] : null,
            duplicateFileCount: files.length,
        };
    }

    function summarizeMatchResults(results) {
        return {
            total: results.length,
            matched: results.filter(result => result.status === 'matched').length,
            missing: results.filter(result => result.status === 'missing').length,
            ambiguous: results.filter(result => result.status === 'ambiguous').length,
        };
    }

    function recomputeMatchSummaryFromMatches(images, matchesByImage) {
        if (images.length === 0 || matchesByImage.size === 0) return null;

        const matches = images
            .map(imageRecord => matchesByImage.get(imageRecord.id))
            .filter(Boolean);
        return summarizeMatchResults(matches);
    }

    window.SAM2AnnotationMatching = {
        localAnnotationSourceActive,
        buildLocalAnnotationSource,
        annotationSourceTitle,
        duplicateImageStems,
        hasDuplicateImageName,
        annotationMatchModeForImage,
        resolveLocalAnnotationMatch,
        localAnnotationCandidates,
        summarizeMatchResults,
        recomputeMatchSummaryFromMatches
    };
})();
