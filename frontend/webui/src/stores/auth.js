import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useAuthStore = defineStore('auth', () => {
    // STATE
    const user = ref(null);
    const token = ref(localStorage.getItem('lollms_token') || null);
    const isAuthenticating = ref(false);

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
                // Set the authorization header for this initial request
                apiClient.defaults.headers.common['Authorization'] = `Bearer ${token.value}`;
                const response = await apiClient.get('/api/auth/me');
                console.log(response.data)
                user.value = response.data;
                
                // Dynamically import other stores to avoid circular dependencies
                const { useDiscussionsStore } = await import('./discussions');
                const { useDataStore } = await import('./data');
                const discussionsStore = useDiscussionsStore();
                const dataStore = useDataStore();
                
                // Fetch all initial data needed for the app to function
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
                 // This case might happen if token is valid but /me fails for some reason
                 throw new Error("Authentication succeeded but failed to fetch user data.");
            }

        } catch (error) {
            // Refined error handling to give user-specific feedback
            const detail = error.response?.data?.detail || "An unknown error occurred.";
            if (detail.includes("account is inactive")) {
                 uiStore.addNotification(detail, 'warning');
            } else {
                 // Generic message for other failures like incorrect password
                 uiStore.addNotification('Login failed: Incorrect username or password.', 'error');
            }
            throw new Error(detail); // Throw for component-level error state handling
        }
    }

    /**
     * Registers a new user account by calling the backend API.
     * @param {object} registrationData - Object with { username, email, password }.
     */
    async function register(registrationData) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.post('/api/auth/register', registrationData);
            const registrationMode = response.data.is_active ? 'direct' : 'admin_approval';
            
            if (registrationMode === 'direct') {
                uiStore.addNotification('Registration successful! You can now log in.', 'success');
            } else {
                uiStore.addNotification('Registration successful! Your account is now pending administrator approval.', 'info', 6000); // Longer duration
            }
            uiStore.closeModal('register');
            uiStore.openModal('login'); // Guide user to the login screen
        } catch (error) {
            // The global API interceptor will show the error message from the backend
            throw error; // Propagate error for component-level handling (e.g., stop loading spinner)
        }
    }

    /**
     * Clears all authentication-related state locally and from the apiClient header.
     */
    function clearAuthData() {
        user.value = null;
        token.value = null;
        localStorage.removeItem('lollms_token');
        delete apiClient.defaults.headers.common['Authorization'];
    }

    /**
     * Logs the user out by clearing all local data, calling the backend logout endpoint, and showing the login modal.
     */
    async function logout() {
        const uiStore = useUiStore();
        
        try {
            // Call the backend logout endpoint to ensure server-side session is cleared.
            await apiClient.post('/api/auth/logout');
            uiStore.openModal('login');
        } catch(error) {
            // Log a warning but proceed with client-side cleanup regardless
            console.warn("Could not reach logout endpoint, but proceeding with client-side logout.", error);
        } finally {
            const { useDiscussionsStore } = await import('./discussions');
            const { useDataStore } = await import('./data');

            clearAuthData();
            // Reset all relevant stores to their initial state to prevent data leakage
            useDiscussionsStore().$reset();
            useDataStore().$reset();

            uiStore.addNotification('You have been logged out.', 'info');
            uiStore.openModal('login');
        }
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
        register, // --- EXPOSED new action ---
        logout,
        updateUserProfile,
        updateUserPreferences,
        changePassword,
    };
});