import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useAuthStore = defineStore('auth', () => {
    const user = ref(null);
    const token = ref(localStorage.getItem('lollms_token') || null);
    const isAuthenticating = ref(false);
    const loadingMessage = ref('Initializing...');
    const loadingProgress = ref(0);
    const funFact = ref('');

    const isAuthenticated = computed(() => !!user.value);
    const isAdmin = computed(() => user.value?.is_admin || false);

    async function attemptInitialAuth() {
        isAuthenticating.value = true;
        const uiStore = useUiStore();

        loadingProgress.value = 0;
        loadingMessage.value = 'Waking up the hamsters...';

        try {
            const funFactResponse = await apiClient.get('/api/fun-fact');
            funFact.value = funFactResponse.data.fun_fact;
        } catch (e) {
            funFact.value = 'The LoLLMs project is open source and seeks to democratize AI.';
        }
        await new Promise(resolve => setTimeout(resolve, 500));
        loadingProgress.value = 10;
        loadingMessage.value = 'Checking credentials...';

        if (token.value) {
            try {
                apiClient.defaults.headers.common['Authorization'] = `Bearer ${token.value}`;
                loadingProgress.value = 20;
                loadingMessage.value = 'Authenticating...';
                const response = await apiClient.get('/api/auth/me');
                user.value = response.data;
                
                const { useDiscussionsStore } = await import('./discussions');
                const { useDataStore } = await import('./data');
                const discussionsStore = useDiscussionsStore();
                const dataStore = useDataStore();
                
                loadingProgress.value = 40;
                loadingMessage.value = 'Loading user discussions...';
                const p1 = discussionsStore.loadDiscussions();

                loadingProgress.value = 60;
                loadingMessage.value = 'Loading personalities & tools...';
                const p2 = dataStore.loadAllInitialData();
                
                await Promise.all([p1, p2]);

                loadingProgress.value = 80;
                loadingMessage.value = 'Preparing the interface...';

                if (user.value) {
                    let targetView = user.value.first_page;
                    if (user.value.user_ui_level < 2 && targetView === 'feed') {
                        targetView = 'new_discussion'; 
                    }
                    uiStore.setMainView(targetView === 'feed' ? 'feed' : 'chat');

                    if (targetView === 'last_discussion') {
                        if (discussionsStore.sortedDiscussions.length > 0) {
                            await discussionsStore.selectDiscussion(discussionsStore.sortedDiscussions[0].id);
                        } else {
                            await discussionsStore.createNewDiscussion();
                        }
                    } else if (targetView === 'new_discussion') {
                        await discussionsStore.createNewDiscussion();
                    }
                }
                loadingProgress.value = 100;
                loadingMessage.value = 'Done!';

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

    async function login(username, password) {
        const uiStore = useUiStore();
        try {
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);
            const response = await apiClient.post('/api/auth/token', formData);
            token.value = response.data.access_token;
            localStorage.setItem('lollms_token', token.value);
            await attemptInitialAuth();
            if(isAuthenticated.value) {
                uiStore.closeModal('login');
                uiStore.addNotification('Login successful!', 'success');
            } else {
                 throw new Error("Authentication succeeded but failed to fetch user data.");
            }
        } catch (error) {
            const detail = error.response?.data?.detail || "An unknown error occurred.";
            if (detail.includes("account is inactive")) {
                 uiStore.addNotification(detail, 'warning');
            } else {
                 uiStore.addNotification('Login failed: Incorrect username or password.', 'error');
            }
            throw new Error(detail);
        }
    }

    async function register(registrationData) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.post('/api/auth/register', registrationData);
            const registrationMode = response.data.is_active ? 'direct' : 'admin_approval';
            if (registrationMode === 'direct') {
                uiStore.addNotification('Registration successful! You can now log in.', 'success');
            } else {
                uiStore.addNotification('Registration successful! Your account is now pending administrator approval.', 'info', 6000);
            }
            uiStore.closeModal('register');
            uiStore.openModal('login');
        } catch (error) {
            throw error;
        }
    }

    function clearAuthData() {
        user.value = null;
        token.value = null;
        localStorage.removeItem('lollms_token');
        delete apiClient.defaults.headers.common['Authorization'];
    }

    async function logout() {
        const uiStore = useUiStore();
        try {
            await apiClient.post('/api/auth/logout');
            uiStore.openModal('login');
        } catch(error) {
            console.warn("Could not reach logout endpoint, but proceeding with client-side logout.", error);
        } finally {
            const { useDiscussionsStore } = await import('./discussions');
            const { useDataStore } = await import('./data');
            clearAuthData();
            useDiscussionsStore().$reset();
            useDataStore().$reset();
            uiStore.addNotification('You have been logged out.', 'info');
            uiStore.openModal('login');
        }
    }

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
    
    async function updateUserPreferences(preferences) {
        try {
            const response = await apiClient.put('/api/auth/me', preferences);
            if (user.value) {
                Object.assign(user.value, response.data);
            }
            useUiStore().addNotification('Settings saved successfully.', 'success');
        } catch(error) {
            console.error("Failed to update user preferences:", error);
            useUiStore().addNotification('Failed to save settings.', 'error');
            throw error;
        }
    }

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
        user, token, isAuthenticating, isAuthenticated, isAdmin,
        loadingMessage, loadingProgress, funFact,
        attemptInitialAuth, login, register, logout,
        updateUserProfile, updateUserPreferences, changePassword,
    };
});