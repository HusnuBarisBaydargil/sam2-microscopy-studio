(() => {
    const apiClient = window.SAM2ApiClient;
    if (!apiClient) {
        throw new Error('SAM2ApiClient must be loaded before apiWorkflows.js.');
    }

    const { apiPath, apiFetch } = apiClient;

    function postJson(path, payload) {
        return apiFetch(apiPath(path), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    }

    function loadImage(file) {
        const formData = new FormData();
        formData.append('image', file);
        return apiFetch(apiPath('/api/load_image'), { method: 'POST', body: formData });
    }

    function loadImageInfo(file) {
        const formData = new FormData();
        formData.append('image', file);
        return apiFetch(apiPath('/api/image_info'), { method: 'POST', body: formData });
    }

    function preprocessImage({ file, method, params }) {
        const formData = new FormData();
        formData.append('image', file);
        formData.append('method', method);
        formData.append('params', JSON.stringify(params));
        return apiFetch(apiPath('/api/preprocess'), { method: 'POST', body: formData });
    }

    function runSam({ file, imageName, samSettings, preprocessMethod, preprocessParams }) {
        const formData = new FormData();
        formData.append('image', file, imageName);
        formData.append('sam_settings', JSON.stringify(samSettings));
        formData.append('preprocess_method', preprocessMethod);
        formData.append('preprocess_params', JSON.stringify(preprocessParams));
        return apiFetch(apiPath('/api/run_sam'), { method: 'POST', body: formData });
    }

    function saveProjectSettings(settings) {
        return postJson('/api/project/settings', settings);
    }

    function loadProjectSettings() {
        return apiFetch(apiPath('/api/project/settings'));
    }

    function matchAnnotations({ images, format }) {
        return postJson('/api/annotations/match', { images, format });
    }

    function bulkLoadAnnotations({ images, format }) {
        return postJson('/api/annotations/bulk_load', { images, format });
    }

    function loadAnnotations(params) {
        const query = params instanceof URLSearchParams ? params : new URLSearchParams(params);
        return apiFetch(`${apiPath('/api/annotations/load')}?${query.toString()}`);
    }

    function saveAnnotations(payload) {
        return postJson('/api/annotations/save', payload);
    }

    function loadClasses() {
        return apiFetch(apiPath('/api/classes'));
    }

    function saveClasses(classes) {
        return postJson('/api/classes', { classes });
    }

    window.SAM2ApiWorkflows = {
        loadImage,
        loadImageInfo,
        preprocessImage,
        runSam,
        saveProjectSettings,
        loadProjectSettings,
        matchAnnotations,
        bulkLoadAnnotations,
        loadAnnotations,
        saveAnnotations,
        loadClasses,
        saveClasses
    };
})();
