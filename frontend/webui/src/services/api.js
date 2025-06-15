import axios from 'axios';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';

const apiClient = axios.create({
    // The base URL will be the same as the window origin, so we don't need to set it.
    // Vite's proxy will handle redirecting /api calls during development.
});

// Interceptor to add the JWT token to every request.
apiClient.interceptors.request.use(
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

// Interceptor to handle responses and errors globally.
apiClient.interceptors.response.use(
    (response) => {
        // Any status code that lie within the range of 2xx cause this function to trigger
        return response;
    },
    (error) => {
        // Any status codes that falls outside the range of 2xx cause this function to trigger
        const authStore = useAuthStore();
        const uiStore = useUiStore();

        if (error.response) {
            // The request was made and the server responded with a status code
            // that falls out of the range of 2xx
            const { status, data } = error.response;

            if (status === 401 && error.config.url !== '/api/auth/token') {
                // If we get a 401 Unauthorized, it means the token is invalid or expired.
                // We log the user out, which will clear the token and show the login modal.
                uiStore.addNotification('Your session has expired. Please log in again.', 'error');
                authStore.logout();
            } else if (status === 403) {
                // NEW: Handle 403 Forbidden errors gracefully without logging out.
                uiStore.addNotification('Permission Denied. You do not have access to this resource.', 'error');
            }
            else {
                // For other errors, we can show a generic notification.
                const errorMessage = data?.detail || error.message || 'An unknown error occurred.';
                uiStore.addNotification(`API Error: ${errorMessage}`, 'error');
            }
        } else if (error.request) {
            // The request was made but no response was received
            uiStore.addNotification('Network Error: Could not connect to the server.', 'error');
        } else {
            // Something happened in setting up the request that triggered an Error
            uiStore.addNotification(`Request Error: ${error.message}`, 'error');
        }

        return Promise.reject(error);
    }
);

export default apiClient;