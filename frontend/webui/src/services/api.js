// frontend/webui/src/services/api.js
import axios from 'axios';

// Resolve API base URL based on development or production mode
const getBaseUrl = () => {
    if (import.meta.env.VITE_API_URL) {
        return import.meta.env.VITE_API_URL;
    }
    if (import.meta.env.DEV) {
        return 'http://localhost:9642';
    }
    return window.location.origin;
};

const apiClient = axios.create({
    baseURL: getBaseUrl(),
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 60000, // 60s default timeout
});

// Request Interceptor: Attach JWT Token
apiClient.interceptors.request.use(
    (config) => {
        // Do not attach tokens on explicit public authentication endpoints
        const isPublicAuthEndpoint = 
            config.url?.includes('/api/auth/reset-password') ||
            config.url?.includes('/api/auth/forgot-password') ||
            config.url?.includes('/api/auth/token');

        if (!isPublicAuthEndpoint) {
            const token = localStorage.getItem('lollms-token');
            if (token) {
                config.headers['Authorization'] = `Bearer ${token}`;
            }
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response Interceptor: Graceful 401 handling without hijacking public pages
apiClient.interceptors.response.use(
    (response) => {
        return response;
    },
    (error) => {
        const status = error.response ? error.response.status : null;
        const currentPath = window.location.pathname || '';
        const requestUrl = error.config?.url || '';

        // Never redirect or hijack UI if the user is on the password reset screen or calling public endpoints
        const isResetPasswordContext = 
            currentPath.startsWith('/reset-password') || 
            window.location.hash.includes('reset-password') ||
            requestUrl.includes('/api/auth/reset-password') ||
            requestUrl.includes('/api/auth/forgot-password');

        if (status === 401 && !isResetPasswordContext) {
            // Clean dead token to prevent continuous failure loops
            const storedToken = localStorage.getItem('lollms-token');
            if (storedToken && !requestUrl.includes('/api/auth/token')) {
                console.warn('[ApiClient] 401 Unauthorized for:', requestUrl);
            }
        }

        return Promise.reject(error);
    }
);

export default apiClient;

/**
 * Downloads a file from an authenticated endpoint using Axios blob fetching
 * and triggers the browser save dialog securely.
 * 
 * @param {string} url - The API endpoint to download from (e.g., '/api/discussions/1/artefacts/name/download')
 * @param {string} filename - Fallback filename if Content-Disposition is missing
 */
export async function downloadBlob(url, filename = 'download') {
    try {
        const response = await apiClient.get(url, { responseType: 'blob' });
        const blob = new Blob([response.data]);
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        
        let finalFilename = filename;
        const disposition = response.headers['content-disposition'];
        if (disposition && disposition.includes('filename=')) {
            const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
            if (matches != null && matches[1]) {
                finalFilename = matches[1].replace(/['"]/g, '');
            }
        }
        
        link.download = finalFilename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(link.href);
    } catch (error) {
        console.error("Download failed:", error);
        // Fallback to throwing so UI stores can catch it and show a notification
        throw error;
    }
}