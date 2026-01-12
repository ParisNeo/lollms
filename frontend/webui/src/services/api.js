import axios from 'axios';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import router from '../router';

const api = axios.create({
    baseURL: '',
    headers: {
        'Content-Type': 'application/json',
    },
});

api.interceptors.request.use(
    (config) => {
        const authStore = useAuthStore();
        if (authStore.token) {
            config.headers.Authorization = `Bearer ${authStore.token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

api.interceptors.response.use(
    (response) => response,
    (error) => {
        const uiStore = useUiStore();
        const authStore = useAuthStore();
        
        // Handle Maintenance Mode (503)
        if (error.response && error.response.status === 503) {
            const detail = error.response.data?.detail || "System under maintenance.";
            // Only trigger maintenance overlay if it's the specific maintenance message
            // OR if it's a generic 503 which usually means maintenance/overload
            if (typeof detail === 'string') {
                 uiStore.setMaintenanceMode(true, detail);
            } else {
                 uiStore.setMaintenanceMode(true, "System Unavailable");
            }
            return Promise.reject(error);
        }

        // Handle Auth Failures (401/403)
        if (error.response && (error.response.status === 401 || error.response.status === 403)) {
            // Special handling for login endpoint to not auto-logout/redirect on failure
            if (!error.config.url.includes('/auth/token')) {
                authStore.logout();
                uiStore.activeModal = 'login';
                // Only redirect if not already on a public page
                if (router.currentRoute.value.path !== '/') {
                     router.push('/');
                }
            }
        }
        
        // Don't show notification for 401/403 as they handle themselves (login modal)
        // or for 503 as it shows the overlay.
        if (error.response && ![401, 403, 503].includes(error.response.status)) {
            const message = error.response?.data?.detail || 'An unexpected error occurred.';
            uiStore.addNotification(message, 'error');
        } else if (!error.response) {
            uiStore.addNotification('Network error. Please check your connection.', 'error');
        }
        
        return Promise.reject(error);
    }
);

export default api;
