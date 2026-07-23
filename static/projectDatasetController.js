(() => {
    const annotationCodecs = window.SAM2AnnotationCodecs;
    if (!annotationCodecs) {
        throw new Error('SAM2AnnotationCodecs must be loaded before projectDatasetController.js.');
    }

    function issue(code, message, context = {}) {
        return { code, message, ...context };
    }

    function isPositiveInteger(value) {
        return Number.isInteger(value) && value > 0;
    }

    function imageDimensions(imageRecord) {
        const image = imageRecord?.originalImage || imageRecord?.processedImage;
        const width = Number(image?.width || imageRecord?.width);
        const height = Number(image?.height || imageRecord?.height);
        return Number.isFinite(width) && width > 0 && Number.isFinite(height) && height > 0
            ? { width, height }
            : null;
    }

    function validUuid(value) {
        return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
            String(value || '')
        );
    }

    function validateCocoDataset(dataset) {
        const errors = [];
        const images = Array.isArray(dataset?.images) ? dataset.images : [];
        const categories = Array.isArray(dataset?.categories) ? dataset.categories : [];
        const annotations = Array.isArray(dataset?.annotations) ? dataset.annotations : [];
        if (!dataset || typeof dataset !== 'object') {
            return {
                valid: false,
                errors: [issue('dataset_type', 'Dataset must be an object.')],
                stats: { images: 0, categories: 0, annotations: 0 }
            };
        }
        if (!Array.isArray(dataset.images)) errors.push(issue('images_type', 'COCO images must be an array.'));
        if (!Array.isArray(dataset.categories)) errors.push(issue('categories_type', 'COCO categories must be an array.'));
        if (!Array.isArray(dataset.annotations)) errors.push(issue('annotations_type', 'COCO annotations must be an array.'));

        const imageIds = new Set();
        const fileNames = new Set();
        const imageById = new Map();
        images.forEach((image, index) => {
            if (!isPositiveInteger(image?.id) || imageIds.has(image.id)) {
                errors.push(issue('image_id', `Image ${index + 1} has a missing or duplicate positive integer ID.`));
            } else {
                imageIds.add(image.id);
                imageById.set(image.id, image);
            }
            const fileName = String(image?.file_name || '').trim();
            if (!fileName || fileNames.has(fileName)) {
                errors.push(issue('image_file_name', `Image ${index + 1} has a missing or duplicate file_name.`));
            } else {
                fileNames.add(fileName);
            }
            if (!(Number(image?.width) > 0) || !(Number(image?.height) > 0)) {
                errors.push(issue('image_dimensions', `Image "${fileName || index + 1}" has invalid dimensions.`));
            }
        });

        const categoryIds = new Set();
        const categoryNames = new Set();
        categories.forEach((category, index) => {
            const name = String(category?.name || '').trim();
            if (!isPositiveInteger(category?.id) || categoryIds.has(category.id)) {
                errors.push(issue('category_id', `Category ${index + 1} has a missing or duplicate positive integer ID.`));
            } else {
                categoryIds.add(category.id);
            }
            if (!name || categoryNames.has(name)) {
                errors.push(issue('category_name', `Category ${index + 1} has a missing or duplicate name.`));
            } else {
                categoryNames.add(name);
            }
        });

        const annotationIds = new Set();
        annotations.forEach((annotation, index) => {
            if (!isPositiveInteger(annotation?.id) || annotationIds.has(annotation.id)) {
                errors.push(issue('annotation_id', `Annotation ${index + 1} has a missing or duplicate positive integer ID.`));
            } else {
                annotationIds.add(annotation.id);
            }
            const image = imageById.get(annotation?.image_id);
            if (!image) errors.push(issue('annotation_image', `Annotation ${index + 1} references an unknown image.`));
            if (!categoryIds.has(annotation?.category_id)) {
                errors.push(issue('annotation_category', `Annotation ${index + 1} references an unknown category.`));
            }

            const bbox = annotation?.bbox;
            const validBbox = Array.isArray(bbox)
                && bbox.length === 4
                && bbox.every(value => Number.isFinite(Number(value)))
                && Number(bbox[2]) > 0
                && Number(bbox[3]) > 0;
            if (!validBbox) {
                errors.push(issue('annotation_bbox', `Annotation ${index + 1} has an invalid bounding box.`));
            } else if (image) {
                const [x, y, width, height] = bbox.map(Number);
                if (x < 0 || y < 0 || x + width > Number(image.width) + 1e-6 || y + height > Number(image.height) + 1e-6) {
                    errors.push(issue('annotation_bounds', `Annotation ${index + 1} extends outside its image.`));
                }
            }
            if (!(Number(annotation?.area) > 0)) {
                errors.push(issue('annotation_area', `Annotation ${index + 1} has an invalid area.`));
            }
            if (annotation?.segmentation !== undefined) {
                const polygons = annotation.segmentation;
                const validPolygons = Array.isArray(polygons)
                    && polygons.length > 0
                    && polygons.every(polygon => (
                        Array.isArray(polygon)
                        && polygon.length >= 6
                        && polygon.length % 2 === 0
                        && polygon.every(value => Number.isFinite(Number(value)))
                    ));
                if (!validPolygons) {
                    errors.push(issue('annotation_segmentation', `Annotation ${index + 1} has invalid polygon segmentation.`));
                } else if (image) {
                    const outsideImage = polygons.some(polygon => {
                        for (let pointIndex = 0; pointIndex < polygon.length; pointIndex += 2) {
                            const x = Number(polygon[pointIndex]);
                            const y = Number(polygon[pointIndex + 1]);
                            if (x < 0 || y < 0 || x > Number(image.width) || y > Number(image.height)) return true;
                        }
                        return false;
                    });
                    if (outsideImage) {
                        errors.push(issue(
                            'annotation_segmentation_bounds',
                            `Annotation ${index + 1} has polygon points outside its image.`
                        ));
                    }
                }
            }
        });

        return {
            valid: errors.length === 0,
            errors,
            stats: {
                images: images.length,
                categories: categories.length,
                annotations: annotations.length
            }
        };
    }

    function uniqueIssues(issues) {
        const seen = new Set();
        return issues.filter(item => {
            const key = `${item.code}\u0000${item.message}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });
    }

    function buildProjectCocoExport({
        projectId,
        schemaVersion,
        taskType,
        images,
        annotationsByImage,
        annotationMatchesByImage,
        candidateAnnotationsByImage,
        dirtyImageIds,
        classes,
        imageName,
        imagePath,
        normalizeAnnotation,
        generatedAt = new Date().toISOString()
    }) {
        const errors = [];
        const warnings = [];
        if (!validUuid(projectId)) errors.push(issue('project_id', 'Project manifest ID is missing or invalid.'));
        if (Number(schemaVersion) !== 1) errors.push(issue('schema_version', 'Project manifest schema version must be 1.'));
        if (taskType !== 'bounding_box') errors.push(issue('task_type', 'Project task type must be bounding_box.'));

        const categoryIds = new Set();
        const categoryNames = new Set();
        const categories = [];
        (Array.isArray(classes) ? classes : []).forEach((classInfo, index) => {
            const classId = Number(classInfo?.id);
            const name = String(classInfo?.name || '').trim();
            if (!isPositiveInteger(classId) || categoryIds.has(classId)) {
                errors.push(issue('manifest_class_id', `Class ${index + 1} has a missing or duplicate stable ID.`));
                return;
            }
            if (!name || categoryNames.has(name)) {
                errors.push(issue('manifest_class_name', `Class ${index + 1} has a missing or duplicate name.`));
                return;
            }
            categoryIds.add(classId);
            categoryNames.add(name);
            categories.push({ id: classId, name });
        });
        categories.sort((left, right) => left.id - right.id);

        const sourceImages = Array.isArray(images) ? [...images] : [];
        sourceImages.sort((left, right) => {
            const pathOrder = String(imagePath(left)).localeCompare(String(imagePath(right)));
            return pathOrder || String(left?.id || '').localeCompare(String(right?.id || ''));
        });
        if (sourceImages.length === 0) errors.push(issue('project_images', 'Load at least one image before validation or export.'));

        const cocoImages = [];
        const cocoAnnotations = [];
        const exportedFileNames = new Set();
        let annotationId = 1;
        let emptyImageCount = 0;

        sourceImages.forEach((imageRecord, imageIndex) => {
            const fileName = String(imagePath(imageRecord) || imageName(imageRecord) || '').trim();
            const dimensions = imageDimensions(imageRecord);
            const annotationMatch = annotationMatchesByImage?.get(imageRecord.id);
            if (annotationMatch?.status === 'matched' && !imageRecord.serverAnnotationsChecked) {
                errors.push(issue(
                    'matched_annotations_not_loaded',
                    `Matched annotations for "${fileName || imageIndex + 1}" have not been loaded into the browser.`
                ));
            } else if (annotationMatch?.status === 'ambiguous') {
                warnings.push(issue(
                    'ambiguous_annotation_match',
                    `Image "${fileName || imageIndex + 1}" has an unresolved ambiguous annotation match.`
                ));
            }
            if (!fileName || exportedFileNames.has(fileName)) {
                errors.push(issue('source_image_name', `Loaded image ${imageIndex + 1} has a missing or duplicate export path.`));
            }
            exportedFileNames.add(fileName);
            if (!dimensions) {
                errors.push(issue('source_image_dimensions', `Image "${fileName || imageIndex + 1}" has invalid dimensions.`));
            }
            const cocoImage = {
                id: imageIndex + 1,
                file_name: fileName,
                width: dimensions?.width || 0,
                height: dimensions?.height || 0
            };
            cocoImages.push(cocoImage);

            const rawAnnotations = Array.isArray(annotationsByImage?.get(imageRecord.id))
                ? [...annotationsByImage.get(imageRecord.id)]
                : [];
            rawAnnotations.sort((left, right) => Number(left?.id || 0) - Number(right?.id || 0));
            if (rawAnnotations.length === 0) emptyImageCount++;

            const localAnnotationIds = new Set();
            rawAnnotations.forEach(annotation => {
                if (!isPositiveInteger(Number(annotation?.id)) || localAnnotationIds.has(Number(annotation.id))) {
                    errors.push(issue('source_annotation_id', `Image "${fileName}" has a missing or duplicate annotation ID.`));
                }
                localAnnotationIds.add(Number(annotation?.id));
                if (!categoryNames.has(String(annotation?.class || '').trim())) {
                    errors.push(issue(
                        'source_annotation_class',
                        `Annotation #${annotation?.id ?? '?'} in "${fileName}" uses a class not present in the project manifest.`
                    ));
                }
            });

            let exportedAnnotations = [];
            try {
                const perImage = annotationCodecs.buildAnnotationExport(
                    fileName,
                    rawAnnotations,
                    'coco',
                    imageRecord,
                    { classes, normalizeAnnotation }
                );
                exportedAnnotations = JSON.parse(perImage.content).annotations || [];
            } catch (error) {
                errors.push(issue('source_annotation_export', `Could not normalize annotations for "${fileName}": ${error.message}`));
            }
            if (exportedAnnotations.length !== rawAnnotations.length) {
                errors.push(issue('source_annotation_invalid', `Image "${fileName}" contains annotations that could not be normalized.`));
            }
            exportedAnnotations.forEach((annotation, index) => {
                cocoAnnotations.push({
                    ...annotation,
                    id: annotationId++,
                    image_id: cocoImage.id,
                    source_annotation_id: rawAnnotations[index]?.id ?? null
                });
            });
        });

        const dirtyCount = sourceImages.filter(image => dirtyImageIds?.has(image.id)).length;
        if (dirtyCount > 0) {
            warnings.push(issue('unsaved_annotations', `Export includes unsaved in-memory changes for ${dirtyCount} image${dirtyCount === 1 ? '' : 's'}.`));
        }
        const candidateCount = sourceImages.reduce((total, image) => (
            total + (candidateAnnotationsByImage?.get(image.id)?.length || 0)
        ), 0);
        if (candidateCount > 0) {
            warnings.push(issue('unaccepted_candidates', `${candidateCount} unaccepted SAM candidate${candidateCount === 1 ? '' : 's'} are not included.`));
        }
        if (emptyImageCount > 0) {
            warnings.push(issue('empty_images', `${emptyImageCount} image${emptyImageCount === 1 ? '' : 's'} have no annotations and are included as negative examples.`));
        }
        if (cocoAnnotations.length === 0) warnings.push(issue('empty_dataset', 'The project contains no final annotations.'));

        const dataset = {
            info: {
                description: 'SAM2 Microscopy Studio project export',
                version: '1.0',
                date_created: generatedAt,
                project_id: String(projectId || ''),
                manifest_schema_version: Number(schemaVersion) || null,
                task_type: String(taskType || '')
            },
            images: cocoImages,
            categories,
            annotations: cocoAnnotations
        };
        const cocoValidation = validateCocoDataset(dataset);
        const validation = {
            valid: errors.length === 0 && cocoValidation.valid,
            errors: uniqueIssues([...errors, ...cocoValidation.errors]),
            warnings: uniqueIssues(warnings),
            stats: cocoValidation.stats
        };
        validation.valid = validation.errors.length === 0;

        const safeProjectId = validUuid(projectId) ? String(projectId).slice(0, 8) : 'unidentified';
        return {
            dataset,
            validation,
            content: JSON.stringify(dataset, null, 2),
            mime: 'application/json',
            fileName: `sam2_project_${safeProjectId}_coco.json`
        };
    }

    function validationSummary(validation) {
        const { images, annotations, categories } = validation.stats;
        if (!validation.valid) {
            const firstError = validation.errors[0]?.message || 'Unknown validation error.';
            return `Project validation failed with ${validation.errors.length} error${validation.errors.length === 1 ? '' : 's'}. ${firstError}`;
        }
        const warningText = validation.warnings.length > 0
            ? ` ${validation.warnings.length} warning${validation.warnings.length === 1 ? '' : 's'}.`
            : '';
        return `Project dataset valid: ${images} images, ${annotations} annotations, ${categories} classes.${warningText}`;
    }

    window.SAM2ProjectDatasetController = {
        buildProjectCocoExport,
        validateCocoDataset,
        validationSummary
    };
})();
