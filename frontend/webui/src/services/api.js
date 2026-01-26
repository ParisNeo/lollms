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
      // 1️⃣  Maintenance mode (503)
      // -----------------------------------------------------------------
      if (error.response && error.response.status === 503) {
        const detail = error.response.data?.detail || "System under maintenance.";
        uiStore.setMaintenanceMode(true, typeof detail === 'string' ? detail : "System Unavailable");
        return Promise.reject(error);
      }
  
      // -----------------------------------------------------------------
      // 2️⃣  Whitelist for 403
      // -----------------------------------------------------------------
      const whitelist403 = [
        '/api/api-keys',
      ];
  
      const isWhitelisted = error.response &&
                           error.response.status === 403 &&
                           whitelist403.some(path => error.config?.url?.includes(path));
  
      // -----------------------------------------------------------------
      // 3️⃣  Auth failures (401/403)
      // -----------------------------------------------------------------
      if (!isWhitelisted && error.response && (error.response.status === 401 || error.response.status === 403)) {
        if (!error.config?.url?.includes('/auth/token')) {
          authStore.logout();
          uiStore.activeModal = 'login';
          if (router.currentRoute.value.path !== '/') {
            router.push('/');
          }
        }
        return Promise.reject(error);
      }
  
      // -----------------------------------------------------------------
      // 4️⃣  Other errors & Network Errors
      // -----------------------------------------------------------------
      if (error.response && ![401, 403, 503].includes(error.response.status)) {
        const message = error.response?.data?.detail || 'An unexpected error occurred.';
        uiStore.addNotification(message, 'error');
      } else if (!error.response) {
        // Triggers the ConnectionOverlay when server is completely down (Connection Refused/Network Error)
        uiStore.setConnectionLost(true);
      }
  
      return Promise.reject(error);
    }
  );

export default api;
