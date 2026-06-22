(() => {
    function apiPath(path) {
        return path.replace(/^\/+/, '');
    }

    const API_TOKEN_STORAGE_KEY = 'sam2AnnotatorApiToken';
    let apiAuthToken = sessionStorage.getItem(API_TOKEN_STORAGE_KEY) || '';

    function withApiAuthHeaders(init = {}, token = apiAuthToken) {
        const nextInit = { ...init };
        const headers = new Headers(init.headers || {});
        if (token) {
            headers.set('Authorization', `Bearer ${token}`);
            headers.set('X-API-Token', token);
        }
        nextInit.headers = headers;
        return nextInit;
    }

    async function fetchWithApiAuth(path, init = {}, token = apiAuthToken) {
        return fetch(apiPath(path), withApiAuthHeaders(init, token));
    }

    async function apiFetch(path, init = {}) {
        let response = await fetchWithApiAuth(path, init);
        if (response.status !== 401) return response;

        let authRequired = false;
        try {
            const data = await response.clone().json();
            authRequired = Boolean(data && data.auth_required);
        } catch (error) {
            authRequired = false;
        }
        if (!authRequired) return response;

        const token = window.prompt('Enter the API token for this annotator server:');
        if (!token || !token.trim()) {
            throw new Error('API token required.');
        }

        apiAuthToken = token.trim();
        sessionStorage.setItem(API_TOKEN_STORAGE_KEY, apiAuthToken);
        response = await fetchWithApiAuth(path, init, apiAuthToken);
        if (response.status === 401) {
            apiAuthToken = '';
            sessionStorage.removeItem(API_TOKEN_STORAGE_KEY);
            throw new Error('Invalid API token.');
        }
        return response;
    }

    window.SAM2ApiClient = {
        apiPath,
        apiFetch
    };
})();
