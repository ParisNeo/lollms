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
    response => response,
    error => {
      const uiStore = useUiStore();
      const authStore = useAuthStore();
  
      // -----------------------------------------------------------------
      // 1️⃣  Maintenance mode (503) – unchanged
      // -----------------------------------------------------------------
      if (error.response && error.response.status === 503) {
        const detail = error.response.data?.detail || "System under maintenance.";
        uiStore.setMaintenanceMode(true, typeof detail === 'string' ? detail : "System Unavailable");
        return Promise.reject(error);
      }
  
      // -----------------------------------------------------------------
      // 2️⃣  **Whitelist** – skip auth‑failure handling for known endpoints
      // -----------------------------------------------------------------
      const whitelist403 = [
        '/api/api-keys',          // API‑keys service disabled
        // add any other “feature‑disabled” paths here, e.g.
        // '/api/feature-x',
      ];
  
      const isWhitelisted = error.response &&
                           error.response.status === 403 &&
                           whitelist403.some(path => error.config?.url?.includes(path));
  
      // -----------------------------------------------------------------
      // 3️⃣  Auth failures (401/403) – only if NOT whitelisted
      // -----------------------------------------------------------------
      if (!isWhitelisted && error.response && (error.response.status === 401 || error.response.status === 403)) {
        // do not run this for the whitelisted routes
        if (!error.config?.url?.includes('/auth/token')) {
          authStore.logout();
          uiStore.activeModal = 'login';
          if (router.currentRoute.value.path !== '/') {
            router.push('/');
          }
        }
        // No notification – login modal will inform the user
        return Promise.reject(error);
      }
  
      // -----------------------------------------------------------------
      // 4️⃣  All other errors – show a toast / console warning
      // -----------------------------------------------------------------
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
