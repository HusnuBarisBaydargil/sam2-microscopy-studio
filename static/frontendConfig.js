(() => {
    const DEFAULT_CLASSES = [];
    const ANNOTATION_FORMATS = {
        csv: {
            label: 'Simple CSV',
            extension: 'csv',
            mime: 'text/csv',
            accept: '.csv,text/csv'
        },
        csv_rich: {
            label: 'Rich CSV',
            extension: 'csv',
            mime: 'text/csv',
            accept: '.csv,text/csv'
        },
        yolo: {
            label: 'YOLO TXT',
            extension: 'txt',
            mime: 'text/plain',
            accept: '.txt,text/plain'
        },
        coco: {
            label: 'COCO JSON',
            extension: 'json',
            mime: 'application/json',
            accept: '.json,application/json'
        },
        voc: {
            label: 'Pascal VOC XML',
            extension: 'xml',
            mime: 'application/xml',
            accept: '.xml,application/xml,text/xml'
        }
    };
    const CLASS_COLOR_PALETTE = [
        '#39d353',
        '#9ca3af',
        '#58a6ff',
        '#f2cc60',
        '#ff7b72',
        '#d2a8ff',
        '#56d4dd',
        '#ffa657'
    ];
    const ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'];
    const ALLOWED_IMAGE_MIME_TYPES = new Set([
        'image/jpeg',
        'image/png',
        'image/bmp',
        'image/x-ms-bmp',
        'image/tiff',
        'image/x-tiff'
    ]);
    const OVERLAY_COLORS = {
        candidate: '#38bdf8',
        contrastStroke: 'rgba(0, 0, 0, 0.82)',
        labelBackground: 'rgba(0, 0, 0, 0.78)',
        labelBorder: 'rgba(255, 255, 255, 0.55)',
        labelText: '#ffffff',
        selectedHalo: '#ffffff',
        manualBox: '#d97706'
    };
    const MAX_ZOOM = 10;
    const MIN_ZOOM = 0.1;
    const SCROLL_SENSITIVITY = 0.001;
    const ZOOM_STEP = 1.2;
    const BOX_HANDLE_SCREEN_SIZE = 9;
    const MIN_BOX_SIZE = 2;
    const NEW_CLASS_ACTION = '__new_class__';
    const DEFAULT_SAM_PRESET = 'cell_1920x1440';
    const DEFAULT_SAM_PARAMS = {
        points_per_side: 64,
        crop_n_layers: 2,
        min_mask_region_area: 400,
        crop_overlap_ratio: 0.4,
        crop_n_points_downscale_factor: 2,
        points_per_batch: 64,
        pred_iou_thresh: 0.92,
        stability_score_thresh: 0.92,
        stability_score_offset: 1.0,
        box_nms_thresh: 0.5,
        crop_nms_thresh: 0.5,
        use_m2m: true,
        area_mode: 'pixels',
        min_overall_area: 300,
        max_overall_area: 30000
    };
    const DEFAULT_SAM_PRESETS = [
        {
            key: DEFAULT_SAM_PRESET,
            label: 'Cell 1920x1440',
            description: 'Current default tuned for the original cell workflow.',
            params: { ...DEFAULT_SAM_PARAMS }
        }
    ];
    const PREPROCESS_METHODS = {
        original: { label: 'Original', badge: '' },
        clahe: { label: 'CLAHE', badge: 'CLAHE' },
        gamma: { label: 'Gamma', badge: 'Gamma' },
        clahe_unsharp: { label: 'CLAHE + Unsharp', badge: 'CLAHE+USM' },
        gamma_unsharp: { label: 'Gamma + Unsharp', badge: 'Gamma+USM' },
        retinex_mild: { label: 'Retinex mild', badge: 'Retinex' }
    };
    const DEFAULT_PREPROCESS_PARAMS = {
        clahe_clip_limit: 2.0,
        clahe_tile_grid_size: 8,
        gamma: 1.2,
        unsharp_amount: 0.8,
        unsharp_radius: 1.2,
        unsharp_threshold: 3,
        retinex_strength: 0.55
    };

    window.SAM2FrontendConfig = {
        DEFAULT_CLASSES,
        ANNOTATION_FORMATS,
        CLASS_COLOR_PALETTE,
        ALLOWED_IMAGE_EXTENSIONS,
        ALLOWED_IMAGE_MIME_TYPES,
        OVERLAY_COLORS,
        MAX_ZOOM,
        MIN_ZOOM,
        SCROLL_SENSITIVITY,
        ZOOM_STEP,
        BOX_HANDLE_SCREEN_SIZE,
        MIN_BOX_SIZE,
        NEW_CLASS_ACTION,
        DEFAULT_SAM_PRESET,
        DEFAULT_SAM_PARAMS,
        DEFAULT_SAM_PRESETS,
        PREPROCESS_METHODS,
        DEFAULT_PREPROCESS_PARAMS
    };
})();
