import axios from 'axios';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';

const apiClient = axios.create({
  // The base URL can be inferred from the window origin.
  // Vite's proxy will handle API calls during development.
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
});

// --- Request Interceptor ---
// This runs BEFORE every request is sent. Its job is to ensure
// the latest authentication token is attached.
apiClient.interceptors.request.use(
  (config) => {
    // We get a fresh instance of the auth store each time.
    const authStore = useAuthStore();
    const token = authStore.token; // Get the current token from the store

    if (token) {
      // Attach the token as a Bearer token.
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    // If there's an error setting up the request, reject the promise.
    return Promise.reject(error);
  }
);

// --- Response Interceptor ---
// This runs AFTER a response is received. Its job is to handle
// global responses, especially errors like 401, 403, etc.
apiClient.interceptors.response.use(
  (response) => {
    // If the response is successful (status 2xx), just return it.
    return response;
  },
  (error) => {
    const uiStore = useUiStore();
    const authStore = useAuthStore();

    if (error.response) {
      // The server responded with an error status code (4xx or 5xx)
      const { status, data, config } = error.response;
      const detail = data?.detail || 'An unexpected error occurred.';

      if (status === 401) {
        // If we get a 401 Unauthorized, it means the token is invalid or expired.
        // The exception is the login endpoint itself, which is expected to return 401 on failure.
        if (config.url !== '/api/auth/token') {
            console.error("Authentication error (401), logging out.");
            // We trigger a full logout, which will clear the bad token and show the login modal.
            authStore.logout();
        }
      } else if (status === 403) {
        // 403 Forbidden means the user is authenticated but not authorized for this action.
        uiStore.addNotification(detail, 'error');
      } else if (status === 409) {
        // 409 Conflict is often used for duplicate entries (e.g., username already exists).
        uiStore.addNotification(detail, 'warning');
      } else {
        // For other server errors (e.g., 404, 500), show a generic error notification.
        const errorMessage = typeof detail === 'object' ? JSON.stringify(detail, null, 2) : detail;
        uiStore.addNotification(errorMessage, 'error');
      }
    } else if (error.request) {
      // The request was made but no response was received (e.g., network error, server down).
      uiStore.addNotification('Could not connect to the server. Please check your network.', 'error');
    } else {
      // Something else went wrong setting up the request.
      uiStore.addNotification(`Request Error: ${error.message}`, 'error');
    }

    // Reject the promise so that component-level .catch() blocks can still run if needed.
    return Promise.reject(error);
  }
);

export default apiClient;