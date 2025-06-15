import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useAuthStore = defineStore('auth', () => {
    // STATE
    const user = ref(null);
    const token = ref(localStorage.getItem('lollms_token') || null);
    const isAuthenticating = ref(true);

    // GETTERS
    const isAuthenticated = computed(() => !!user.value);
    const isAdmin = computed(() => user.value?.is_admin || false);

    // ACTIONS

    /**
     * Attempts to authenticate the user using a stored token.
     * If successful, fetches initial application data.
     */
    async function attemptInitialAuth() {
        isAuthenticating.value = true;
        const uiStore = useUiStore();

        if (token.value) {
            try {
                const response = await apiClient.get('/api/auth/me');
                user.value = response.data;
                
                // Dynamically import other stores here to avoid circular dependencies at module load time.
                const { useDiscussionsStore } = await import('./discussions');
                const { useDataStore } = await import('./data');
                const discussionsStore = useDiscussionsStore();
                const dataStore = useDataStore();
                
                // Fetch all initial data needed for the app to function.
                await Promise.all([
                    discussionsStore.loadDiscussions(),
                    dataStore.loadAllInitialData()
                ]);

            } catch (error) {
                console.error("Token validation failed, clearing token.", error);
                clearAuthData();
                uiStore.openModal('login');
            }
        } else {
            uiStore.openModal('login');
        }
        isAuthenticating.value = false;
    }

    /**
     * Logs the user in with a username and password, fetches a new token, and initializes the app.
     * @param {string} username - The user's username.
     * @param {string} password - The user's password.
     */
    async function login(username, password) {
        const uiStore = useUiStore();
        try {
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);

            const response = await apiClient.post('/api/auth/token', formData);
            
            token.value = response.data.access_token;
            localStorage.setItem('lollms_token', token.value);
            
            // After getting a new token, re-run the full authentication and data loading process.
            await attemptInitialAuth();

            if(isAuthenticated.value) {
                uiStore.closeModal('login');
                uiStore.addNotification('Login successful!', 'success');
            } else {
                 throw new Error("Authentication succeeded but failed to fetch user data.");
            }

        } catch (error) {
            const errorMessage = error.response?.data?.detail || "Invalid username or password.";
            uiStore.addNotification(errorMessage, 'error');
            throw error;
        }
    }

    /**
     * Clears all authentication-related state locally.
     */
    function clearAuthData() {
        user.value = null;
        token.value = null;
        localStorage.removeItem('lollms_token');
    }

    /**
     * Logs the user out, clears all local data, and shows the login modal.
     */
    async function logout() {
        const uiStore = useUiStore();
        
        // Dynamically import other stores to reset them.
        const { useDiscussionsStore } = await import('./discussions');
        const { useDataStore } = await import('./data');

        clearAuthData();
        useDiscussionsStore().$reset();
        useDataStore().$reset();

        uiStore.addNotification('You have been logged out.', 'info');
        uiStore.openModal('login');
    }

    /**
     * Updates the user's non-sensitive profile information.
     * @param {object} profileData - Object containing fields like first_name, family_name, etc.
     */
    async function updateUserProfile(profileData) {
        try {
            const response = await apiClient.put('/api/auth/me', profileData);
            user.value = { ...user.value, ...response.data };
            useUiStore().addNotification('Profile updated successfully.', 'success');
        } catch(error) {
            console.error("Failed to update user profile:", error);
            // Error notification is handled by the API interceptor.
            throw error;
        }
    }
    
    /**
     * Updates user preferences like LLM settings, RAG parameters, or active personality.
     * @param {object} preferences - An object containing the preferences to update.
     */
    async function updateUserPreferences(preferences) {
        try {
            const response = await apiClient.put('/api/auth/me', preferences);
            user.value = { ...user.value, ...response.data };
            useUiStore().addNotification('Settings saved successfully.', 'success');
        } catch(error) {
            console.error("Failed to update user preferences:", error);
            throw error;
        }
    }

    /**
     * Changes the user's password.
     * @param {object} passwordData - Object with { current_password, new_password }.
     */
    async function changePassword(passwordData) {
         try {
            await apiClient.post('/api/auth/change-password', passwordData);
            useUiStore().addNotification('Password changed successfully.', 'success');
        } catch(error) {
            console.error("Failed to change password:", error);
            throw error;
        }
    }

    return {
        // State
        user,
        token,
        isAuthenticating,
        // Getters
        isAuthenticated,
        isAdmin,
        // Actions
        attemptInitialAuth,
        login,
        logout,
        updateUserProfile,
        updateUserPreferences,
        changePassword,
    };
});