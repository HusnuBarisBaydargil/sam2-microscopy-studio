(() => {
    const frontendConfig = window.SAM2FrontendConfig;
    if (!frontendConfig) {
        throw new Error('SAM2FrontendConfig must be loaded before annotationCodecs.js.');
    }

    const {
        ANNOTATION_FORMATS,
        CLASS_COLOR_PALETTE
    } = frontendConfig;

    function normalizeAnnotationFormat(format) {
        const key = String(format || 'csv').trim().toLowerCase();
        return ANNOTATION_FORMATS[key] ? key : 'csv';
    }

    function formatLabel(format) {
        return ANNOTATION_FORMATS[normalizeAnnotationFormat(format)].label;
    }

    function annotationDownloadName(sourceImageName, format) {
        const stem = sourceImageName.replace(/\.[^/.]+$/, '') || 'annotations';
        const normalizedFormat = normalizeAnnotationFormat(format);
        if (normalizedFormat === 'yolo') return `${stem}.txt`;
        if (normalizedFormat === 'voc') return `${stem}.xml`;
        if (normalizedFormat === 'coco') return `${stem}_annotations.json`;
        if (normalizedFormat === 'csv_rich') return `${stem}_annotations_rich.csv`;
        return `${stem}_annotations.csv`;
    }

    function formatFromFileName(fileName) {
        const lowerName = String(fileName || '').toLowerCase();
        if (lowerName.endsWith('_annotations_rich.csv')) return 'csv_rich';
        if (lowerName.endsWith('.csv')) return 'csv';
        if (lowerName.endsWith('.txt')) return 'yolo';
        if (lowerName.endsWith('.json')) return 'coco';
        if (lowerName.endsWith('.xml')) return 'voc';
        return null;
    }

    function imageDimensions(imageRecord) {
        const image = imageRecord?.originalImage || imageRecord?.processedImage;
        if (!image || !image.width || !image.height) return null;
        return { width: image.width, height: image.height };
    }

    function buildAnnotationExport(sourceImageName, annotations, format, imageRecord, options = {}) {
        const normalizedFormat = normalizeAnnotationFormat(format);
        const normalizeForExport = typeof options.normalizeAnnotation === 'function'
            ? annotation => options.normalizeAnnotation(annotation, imageRecord)
            : annotation => normalizeAnnotationForCodec(annotation);
        const exportAnnotations = annotations
            .map(normalizeForExport)
            .filter(Boolean);

        if (normalizedFormat === 'csv' || normalizedFormat === 'csv_rich') {
            return {
                content: buildAnnotationCsv(sourceImageName, exportAnnotations, normalizedFormat === 'csv_rich'),
                mime: ANNOTATION_FORMATS[normalizedFormat].mime
            };
        }
        if (normalizedFormat === 'yolo') {
            return {
                content: buildAnnotationYolo(exportAnnotations, imageRecord, options.classes),
                mime: ANNOTATION_FORMATS.yolo.mime
            };
        }
        if (normalizedFormat === 'coco') {
            return {
                content: buildAnnotationCoco(sourceImageName, exportAnnotations, imageRecord, options.classes),
                mime: ANNOTATION_FORMATS.coco.mime
            };
        }
        if (normalizedFormat === 'voc') {
            return {
                content: buildAnnotationVoc(sourceImageName, exportAnnotations, imageRecord),
                mime: ANNOTATION_FORMATS.voc.mime
            };
        }
        throw new Error('Unsupported annotation format.');
    }

    function normalizeAnnotationForCodec(annotation) {
        if (!annotation || !Array.isArray(annotation.bbox) || annotation.bbox.length !== 4) return null;
        const bbox = normalizeImportedBbox(annotation.bbox);
        if (!bbox) return null;
        const existingId = Number(annotation.id);
        return {
            id: Number.isInteger(existingId) && existingId > 0 ? existingId : 1,
            bbox,
            class: String(annotation.class || 'Unlabeled').trim() || 'Unlabeled',
            type: annotation.type || 'loaded',
            ...annotationMaskMetadata(annotation)
        };
    }

    function classesForExport(annotations, existingClasses = []) {
        const classes = normalizeClassList(existingClasses);
        const names = new Set(classes.map(cls => cls.name));
        annotations.forEach(annotation => {
            const name = normalizeClassName(String(annotation.class || 'Unlabeled')) || 'Unlabeled';
            if (names.has(name)) return;
            classes.push({
                name,
                color: CLASS_COLOR_PALETTE[classes.length % CLASS_COLOR_PALETTE.length],
                hotkey: ''
            });
            names.add(name);
        });
        return classes;
    }

    function normalizeClassName(value) {
        return String(value || '').trim().slice(0, 64);
    }

    function normalizeClassList(classes) {
        const normalized = [];
        const names = new Set();
        if (!Array.isArray(classes)) return normalized;

        classes.forEach((cls, index) => {
            const name = normalizeClassName(typeof cls === 'string' ? cls : cls?.name);
            if (!name || names.has(name)) return;
            normalized.push({
                name,
                color: cls?.color || CLASS_COLOR_PALETTE[index % CLASS_COLOR_PALETTE.length],
                hotkey: String(cls?.hotkey || '').trim().slice(0, 1).toLowerCase()
            });
            names.add(name);
        });
        return normalized;
    }

    function classIndexByName(classes) {
        const indexByName = new Map();
        classes.forEach((cls, index) => indexByName.set(cls.name, index));
        return indexByName;
    }

    function normalizeContour(contour) {
        if (typeof contour === 'string' && contour.trim()) {
            try {
                contour = JSON.parse(contour);
            } catch (_error) {
                return null;
            }
        }
        if (!Array.isArray(contour)) return null;

        const points = [];
        contour.forEach(point => {
            if (!Array.isArray(point) || point.length < 2) return;
            const x = Number(point[0]);
            const y = Number(point[1]);
            if (!Number.isFinite(x) || !Number.isFinite(y)) return;
            points.push([x, y]);
        });

        return points.length >= 3 ? points : null;
    }

    function optionalFiniteNumber(value) {
        if (value === null || value === undefined || value === '') return null;
        const number = Number(value);
        return Number.isFinite(number) ? number : null;
    }

    function annotationMaskMetadata(annotation) {
        const metadata = {};
        const contour = normalizeContour(annotation?.contour);
        if (contour) metadata.contour = contour;

        [
            ['mask_area', 'mask_area'],
            ['predicted_iou', 'predicted_iou'],
            ['stability_score', 'stability_score']
        ].forEach(([sourceKey, targetKey]) => {
            const value = optionalFiniteNumber(annotation?.[sourceKey]);
            if (value !== null) metadata[targetKey] = value;
        });

        const source = String(annotation?.source || '').trim();
        if (source) metadata.source = source.slice(0, 64);
        return metadata;
    }

    function cocoSegmentationFromContour(contour) {
        const normalized = normalizeContour(contour);
        if (!normalized) return null;
        return [normalized.flatMap(point => point)];
    }

    function contourFromCocoSegmentation(segmentation) {
        if (!Array.isArray(segmentation) || segmentation.length === 0) return null;
        const polygon = Array.isArray(segmentation[0]) ? segmentation[0] : segmentation;
        if (!Array.isArray(polygon) || polygon.length < 6) return null;
        const contour = [];
        for (let index = 0; index < polygon.length - 1; index += 2) {
            contour.push([polygon[index], polygon[index + 1]]);
        }
        return normalizeContour(contour);
    }

    function buildAnnotationCsv(sourceImageName, annotations, includeMetadata = false) {
        const header = [
            'source_image',
            'x_min',
            'y_min',
            'x_max',
            'y_max',
            'class_label'
        ];
        if (includeMetadata) {
            header.push(
                'contour',
                'mask_area',
                'source',
                'predicted_iou',
                'stability_score'
            );
        }
        const rows = [header];

        annotations.forEach(annotation => {
            const [x, y, w, h] = annotation.bbox.map(Math.round);
            const row = [
                spreadsheetSafe(sourceImageName),
                x,
                y,
                x + w,
                y + h,
                spreadsheetSafe(annotation.class)
            ];
            if (includeMetadata) {
                const metadata = annotationMaskMetadata(annotation);
                row.push(
                    metadata.contour ? JSON.stringify(metadata.contour) : '',
                    metadata.mask_area ?? '',
                    spreadsheetSafe(metadata.source || ''),
                    metadata.predicted_iou ?? '',
                    metadata.stability_score ?? ''
                );
            }
            rows.push(row);
        });

        return rows.map(row => row.map(csvEscape).join(',')).join('\n') + '\n';
    }

    function buildAnnotationYolo(annotations, imageRecord, existingClasses = []) {
        const size = imageDimensions(imageRecord);
        if (!size) throw new Error('YOLO export requires the loaded image dimensions.');

        const classes = classesForExport(annotations, existingClasses);
        const indexByName = classIndexByName(classes);
        return annotations.map(annotation => {
            const [x, y, w, h] = annotation.bbox;
            const className = normalizeClassName(String(annotation.class || 'Unlabeled')) || 'Unlabeled';
            const classIndex = indexByName.has(className) ? indexByName.get(className) : 0;
            const xCenter = (x + w / 2) / size.width;
            const yCenter = (y + h / 2) / size.height;
            return [
                classIndex,
                formatDecimal(xCenter),
                formatDecimal(yCenter),
                formatDecimal(w / size.width),
                formatDecimal(h / size.height)
            ].join(' ');
        }).join('\n') + '\n';
    }

    function buildAnnotationCoco(sourceImageName, annotations, imageRecord, existingClasses = []) {
        const size = imageDimensions(imageRecord) || { width: 0, height: 0 };
        const classes = classesForExport(annotations, existingClasses);
        const indexByName = classIndexByName(classes);
        const payload = {
            images: [{
                id: 1,
                file_name: sourceImageName,
                width: size.width,
                height: size.height
            }],
            categories: classes.map((cls, index) => ({ id: index + 1, name: cls.name })),
            annotations: annotations.map((annotation, index) => {
                const [x, y, w, h] = annotation.bbox;
                const className = normalizeClassName(String(annotation.class || 'Unlabeled')) || 'Unlabeled';
                const categoryId = (indexByName.has(className) ? indexByName.get(className) : 0) + 1;
                const metadata = annotationMaskMetadata(annotation);
                const segmentation = cocoSegmentationFromContour(metadata.contour);
                const cocoAnnotation = {
                    id: index + 1,
                    image_id: 1,
                    category_id: categoryId,
                    bbox: [x, y, w, h],
                    area: metadata.mask_area ?? w * h,
                    iscrowd: 0
                };
                if (segmentation) cocoAnnotation.segmentation = segmentation;
                ['source', 'mask_area', 'predicted_iou', 'stability_score'].forEach(key => {
                    if (metadata[key] !== undefined) cocoAnnotation[key] = metadata[key];
                });
                return cocoAnnotation;
            })
        };
        return JSON.stringify(payload, null, 2) + '\n';
    }

    function buildAnnotationVoc(sourceImageName, annotations, imageRecord) {
        const size = imageDimensions(imageRecord) || { width: 0, height: 0 };
        const lines = [
            '<annotation>',
            `  <filename>${xmlEscape(sourceImageName)}</filename>`,
            '  <size>',
            `    <width>${Math.round(size.width)}</width>`,
            `    <height>${Math.round(size.height)}</height>`,
            '    <depth>3</depth>',
            '  </size>'
        ];

        annotations.forEach(annotation => {
            const [x, y, w, h] = annotation.bbox;
            const className = normalizeClassName(String(annotation.class || 'Unlabeled')) || 'Unlabeled';
            lines.push(
                '  <object>',
                `    <name>${xmlEscape(className)}</name>`,
                '    <pose>Unspecified</pose>',
                '    <truncated>0</truncated>',
                '    <difficult>0</difficult>',
                '    <bndbox>',
                `      <xmin>${Math.round(x)}</xmin>`,
                `      <ymin>${Math.round(y)}</ymin>`,
                `      <xmax>${Math.round(x + w)}</xmax>`,
                `      <ymax>${Math.round(y + h)}</ymax>`,
                '    </bndbox>',
                '  </object>'
            );
        });

        lines.push('</annotation>');
        return lines.join('\n') + '\n';
    }

    function formatDecimal(value) {
        return Number(value).toFixed(6).replace(/0+$/, '').replace(/\.$/, '') || '0';
    }

    function xmlEscape(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&apos;');
    }

    function csvEscape(value) {
        const text = String(value ?? '');
        if (/[",\r\n]/.test(text)) {
            return `"${text.replace(/"/g, '""')}"`;
        }
        return text;
    }

    function spreadsheetSafe(value) {
        const text = String(value ?? '');
        return /^\s*[=+\-@]/.test(text) ? `'${text}` : text;
    }

    function parseAnnotationFile(text, format, imageRecord, options = {}) {
        const normalizedFormat = normalizeAnnotationFormat(format);
        const imageNames = options.imageNames || imageNameAliases(imageRecord);
        if (normalizedFormat === 'csv' || normalizedFormat === 'csv_rich') return parseAnnotationCsv(text, imageNames);
        if (normalizedFormat === 'yolo') return parseAnnotationYolo(text, imageRecord, options.classes);
        if (normalizedFormat === 'coco') return parseAnnotationCoco(text, imageNames);
        if (normalizedFormat === 'voc') return parseAnnotationVoc(text);
        throw new Error('Unsupported annotation format.');
    }

    function imageNameAliases(imageRecord) {
        return [
            imageRecord?.name,
            imageRecord?.displayPath
        ].filter(Boolean);
    }

    function normalizedBasenameSet(names) {
        return new Set(names.map(name => basename(name).toLowerCase()));
    }

    function parseAnnotationCsv(csvText, currentImageNames) {
        const rows = parseCsvRows(csvText).filter(row => row.some(field => field.trim() !== ''));
        if (rows.length < 2) {
            return { annotations: [], usedMatchedRows: false };
        }

        const headers = rows[0].map(normalizeCsvHeader);
        const records = rows.slice(1).map(row => {
            const record = {};
            headers.forEach((header, index) => {
                record[header] = row[index] || '';
            });
            return record;
        });

        const imageNames = normalizedBasenameSet(Array.isArray(currentImageNames) ? currentImageNames : [currentImageNames]);
        const rowsWithSourceImage = records.filter(record => record.source_image);
        const matchedRecords = records.filter(record => (
            record.source_image && imageNames.has(basename(record.source_image).toLowerCase())
        ));
        const selectedRecords = matchedRecords.length > 0 ? matchedRecords : records;

        const annotations = selectedRecords
            .map((record, index) => annotationFromRecord(record, index + 1))
            .filter(Boolean);

        return {
            annotations,
            usedMatchedRows: rowsWithSourceImage.length > 0 && matchedRecords.length > 0
        };
    }

    function parseAnnotationYolo(text, imageRecord, existingClasses = []) {
        const size = imageDimensions(imageRecord);
        if (!size) throw new Error('YOLO import requires the loaded image dimensions.');

        const classes = Array.isArray(existingClasses) ? existingClasses : [];
        const annotations = [];
        text.split(/\r?\n/).forEach((rawLine, index) => {
            const line = rawLine.trim();
            if (!line || line.startsWith('#')) return;

            const parts = line.split(/\s+/);
            if (parts.length < 5) return;

            const classIndex = Number(parts[0]);
            const xCenter = Number(parts[1]) * size.width;
            const yCenter = Number(parts[2]) * size.height;
            const boxWidth = Number(parts[3]) * size.width;
            const boxHeight = Number(parts[4]) * size.height;
            const bbox = normalizeImportedBbox([
                xCenter - boxWidth / 2,
                yCenter - boxHeight / 2,
                boxWidth,
                boxHeight
            ]);
            if (!Number.isInteger(classIndex) || !bbox) return;

            const className = classes[classIndex]?.name || `class_${classIndex}`;
            annotations.push({
                id: index + 1,
                bbox,
                class: className,
                type: 'loaded'
            });
        });

        return { annotations, usedMatchedRows: false };
    }

    function parseAnnotationCoco(text, currentImageNames) {
        const data = JSON.parse(text);
        if (!data || typeof data !== 'object') return { annotations: [], usedMatchedRows: false };

        const categories = new Map();
        (Array.isArray(data.categories) ? data.categories : []).forEach(category => {
            categories.set(category.id, String(category.name || `category_${category.id}`));
        });

        const images = Array.isArray(data.images) ? data.images : [];
        const targetNames = normalizedBasenameSet(Array.isArray(currentImageNames) ? currentImageNames : [currentImageNames]);
        let imageIds = new Set(images
            .filter(image => targetNames.has(basename(String(image.file_name || '')).toLowerCase()))
            .map(image => image.id));
        if (imageIds.size === 0 && images.length === 1) {
            imageIds = new Set([images[0].id]);
        }

        const rawAnnotations = Array.isArray(data.annotations) ? data.annotations : [];
        const annotations = rawAnnotations
            .filter(annotation => imageIds.size === 0 || imageIds.has(annotation.image_id))
            .map((annotation, index) => {
                const bbox = normalizeImportedBbox(annotation.bbox);
                if (!bbox) return null;

                const categoryName = categories.get(annotation.category_id) || `category_${annotation.category_id}`;
                const contour = contourFromCocoSegmentation(annotation.segmentation);
                return {
                    id: Number.isInteger(annotation.id) && annotation.id > 0 ? annotation.id : index + 1,
                    bbox,
                    class: categoryName,
                    type: 'loaded',
                    ...annotationMaskMetadata({
                        contour,
                        mask_area: annotation.mask_area ?? (contour ? annotation.area : null),
                        source: annotation.source,
                        predicted_iou: annotation.predicted_iou,
                        stability_score: annotation.stability_score
                    })
                };
            })
            .filter(Boolean);

        return {
            annotations,
            usedMatchedRows: imageIds.size > 0
        };
    }

    function parseAnnotationVoc(text) {
        if (typeof DOMParser !== 'undefined') {
            return parseAnnotationVocWithDomParser(text);
        }
        return parseAnnotationVocText(text);
    }

    function parseAnnotationVocWithDomParser(text) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(text, 'application/xml');
        if (doc.querySelector('parsererror')) {
            throw new Error('Invalid VOC XML.');
        }

        const annotations = Array.from(doc.querySelectorAll('object'))
            .map((objectNode, index) => {
                const boxNode = objectNode.querySelector('bndbox');
                if (!boxNode) return null;

                const xMin = Number(boxNode.querySelector('xmin')?.textContent);
                const yMin = Number(boxNode.querySelector('ymin')?.textContent);
                const xMax = Number(boxNode.querySelector('xmax')?.textContent);
                const yMax = Number(boxNode.querySelector('ymax')?.textContent);
                const bbox = normalizeImportedBbox([xMin, yMin, xMax - xMin, yMax - yMin]);
                if (!bbox) return null;

                const className = objectNode.querySelector('name')?.textContent?.trim() || 'Unlabeled';
                return {
                    id: index + 1,
                    bbox,
                    class: className,
                    type: 'loaded'
                };
            })
            .filter(Boolean);

        return { annotations, usedMatchedRows: false };
    }

    function parseAnnotationVocText(text) {
        const objectMatches = String(text).match(/<object\b[\s\S]*?<\/object>/gi) || [];
        const annotations = objectMatches
            .map((objectXml, index) => {
                const xMin = Number(xmlTagText(objectXml, 'xmin'));
                const yMin = Number(xmlTagText(objectXml, 'ymin'));
                const xMax = Number(xmlTagText(objectXml, 'xmax'));
                const yMax = Number(xmlTagText(objectXml, 'ymax'));
                const bbox = normalizeImportedBbox([xMin, yMin, xMax - xMin, yMax - yMin]);
                if (!bbox) return null;

                return {
                    id: index + 1,
                    bbox,
                    class: xmlUnescape(xmlTagText(objectXml, 'name') || 'Unlabeled'),
                    type: 'loaded'
                };
            })
            .filter(Boolean);
        return { annotations, usedMatchedRows: false };
    }

    function xmlTagText(xml, tagName) {
        const pattern = new RegExp(`<${tagName}\\b[^>]*>([\\s\\S]*?)<\\/${tagName}>`, 'i');
        const match = String(xml).match(pattern);
        return match ? match[1].trim() : '';
    }

    function xmlUnescape(value) {
        return String(value ?? '')
            .replace(/&apos;/g, "'")
            .replace(/&quot;/g, '"')
            .replace(/&gt;/g, '>')
            .replace(/&lt;/g, '<')
            .replace(/&amp;/g, '&');
    }

    function parseCsvRows(text) {
        const rows = [];
        let row = [];
        let field = '';
        let inQuotes = false;

        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            const nextChar = text[i + 1];

            if (char === '"') {
                if (inQuotes && nextChar === '"') {
                    field += '"';
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }
                continue;
            }

            if (char === ',' && !inQuotes) {
                row.push(field);
                field = '';
                continue;
            }

            if ((char === '\n' || char === '\r') && !inQuotes) {
                if (char === '\r' && nextChar === '\n') i++;
                row.push(field);
                rows.push(row);
                row = [];
                field = '';
                continue;
            }

            field += char;
        }

        row.push(field);
        rows.push(row);
        return rows;
    }

    function normalizeCsvHeader(header) {
        return header.trim().toLowerCase().replace(/\s+/g, '_');
    }

    function annotationFromRecord(record, fallbackId) {
        const className = (
            record.class_label
            || record.class
            || record.label
            || record.category
            || 'Unlabeled'
        ).trim();

        let bbox = null;
        if (hasCsvFields(record, ['x_min', 'y_min', 'x_max', 'y_max'])) {
            const xMin = Number(record.x_min);
            const yMin = Number(record.y_min);
            const xMax = Number(record.x_max);
            const yMax = Number(record.y_max);
            bbox = [xMin, yMin, xMax - xMin, yMax - yMin];
        } else if (hasCsvFields(record, ['x', 'y', 'w', 'h'])) {
            bbox = [Number(record.x), Number(record.y), Number(record.w), Number(record.h)];
        }

        bbox = normalizeImportedBbox(bbox);
        if (!bbox) return null;

        const existingId = Number(record.id);
        return {
            id: Number.isInteger(existingId) && existingId > 0 ? existingId : fallbackId,
            bbox,
            class: className || 'Unlabeled',
            type: 'loaded',
            ...annotationMaskMetadata({
                contour: record.contour || record.segmentation,
                mask_area: record.mask_area,
                source: record.source,
                predicted_iou: record.predicted_iou,
                stability_score: record.stability_score
            })
        };
    }

    function normalizeImportedBbox(rawBbox) {
        if (!Array.isArray(rawBbox) || rawBbox.length !== 4) return null;
        const bbox = rawBbox.map(Number);
        if (bbox.some(value => !Number.isFinite(value))) return null;

        if (bbox[2] < 0) {
            bbox[0] += bbox[2];
            bbox[2] = Math.abs(bbox[2]);
        }
        if (bbox[3] < 0) {
            bbox[1] += bbox[3];
            bbox[3] = Math.abs(bbox[3]);
        }
        if (bbox[2] <= 0 || bbox[3] <= 0) return null;
        return bbox;
    }

    function hasCsvFields(record, fields) {
        return fields.every(field => record[field] !== undefined && record[field] !== '');
    }

    function basename(path) {
        return String(path || '').split(/[\\/]/).pop();
    }

    window.SAM2AnnotationCodecs = {
        normalizeAnnotationFormat,
        formatLabel,
        annotationDownloadName,
        formatFromFileName,
        buildAnnotationExport,
        parseAnnotationFile,
        annotationMaskMetadata,
        normalizeContour
    };
})();
