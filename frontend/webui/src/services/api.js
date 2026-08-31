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