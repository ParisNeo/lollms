// frontend/webui/src/stores/auth.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useAuthStore = defineStore('auth', () => {
    const user = ref(null);
    const token = ref(localStorage.getItem('lollms_token') || null);
    const isAuthenticating = ref(true); // Start as true
    const loadingMessage = ref('Initializing...');
    const loadingProgress = ref(0);
    const funFact = ref('');

    const isAuthenticated = computed(() => !!user.value);
    const isAdmin = computed(() => user.value?.is_admin || false);

    // This new function centralizes the data loading process
    async function fetchUserAndInitialData() {
        const uiStore = useUiStore();
        try {
            loadingProgress.value = 20;
            loadingMessage.value = 'Authenticating...';
            const response = await apiClient.get('/api/auth/me');
            user.value = response.data;
            
            // Dynamically import stores to avoid circular dependencies
            const { useDiscussionsStore } = await import('./discussions');
            const { useDataStore } = await import('./data');
            const discussionsStore = useDiscussionsStore();
            const dataStore = useDataStore();
            
            loadingProgress.value = 40;
            loadingMessage.value = 'Loading user data...';
            // Use Promise.all to fetch data in parallel for speed
            await Promise.all([
                discussionsStore.loadDiscussions(),
                dataStore.loadAllInitialData()
            ]);

            loadingProgress.value = 80;
            loadingMessage.value = 'Preparing the interface...';

            // Navigate to the correct initial view
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
            return true;
        } catch (error) {
            console.error("Failed to fetch user and initial data:", error);
            clearAuthData(); // Clear invalid auth state
            return false;
        }
    }

    async function attemptInitialAuth() {
        // Skip auth attempt if we are on an SSO route
        if (window.location.pathname.startsWith('/app/')) {
            if(token.value){
                // try to load user data silently if a token exists
                try{
                    const response = await apiClient.get('/api/auth/me');
                    user.value = response.data;
                } catch(e){
                    clearAuthData();
                }
            }
            isAuthenticating.value = false;
            return;
        }

        // Skip auth for reset password view, which is a guest route
        if (window.location.pathname.startsWith('/reset-password')) {
            isAuthenticating.value = false;
            return;
        }

        isAuthenticating.value = true;
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

        const uiStore = useUiStore();

        try {
            const adminStatusResponse = await apiClient.get('/api/auth/admin_status');
            if (!adminStatusResponse.data.admin_exists) {
                loadingMessage.value = 'First run setup...';
                isAuthenticating.value = false; // Set to false so App.vue renders modals directly
                uiStore.openModal('firstAdminSetup'); 
                return; // Stop further execution
            } else if (token.value) {
                const success = await fetchUserAndInitialData();
                if (!success) {
                    uiStore.openModal('login');
                }
            } else {
                uiStore.openModal('login');
            }
        } catch (error) {
            console.error("Failed to check admin status or during initial auth:", error);
            uiStore.addNotification('Failed to connect to server. Please try again later.', 'error');
            clearAuthData();
            uiStore.openModal('login'); // Fallback to login
        } finally {
            if (isAuthenticating.value) { 
                isAuthenticating.value = false;
            }
        }
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

            // Hide the loading screen and modals before fetching all data
            uiStore.closeModal(); // Close any active modal (login, firstAdminSetup, etc.)
            isAuthenticating.value = true; // Show loading screen for data fetch

            const success = await fetchUserAndInitialData();

            isAuthenticating.value = false; // Hide loading screen after data fetch

            if (success) {
                uiStore.addNotification('Login successful!', 'success');
                if (user.value.is_admin && !user.value.first_login_done) { 
                    uiStore.openModal('whatsNext'); 
                }
            } else {
                throw new Error("Authentication succeeded but failed to fetch user data.");
            }
        } catch (error) {
            isAuthenticating.value = false; // Hide loading screen on error
            const detail = error.response?.data?.detail || "An unknown error occurred.";
            if (detail.includes("account is inactive")) {
                 uiStore.addNotification(detail, 'warning');
            } else if (error.message.includes('fetch user data')){
                 uiStore.addNotification('Login succeeded, but failed to load user data.', 'error');
            }
            else {
                 uiStore.addNotification('Login failed: Incorrect username or password.', 'error');
            }
            throw error; // Re-throw to inform the component
        }
    }

    async function ssoLoginWithPassword(appName, username, password) {
        await login(username, password);
        return await ssoAuthorizeApplication(appName);
    }

    async function ssoAuthorizeApplication(appName) {
        const formData = new FormData();
        formData.append('app_name', appName);
        const response = await apiClient.post('/api/sso/authorize', formData);
        const appDetailsResponse = await apiClient.get(`/api/sso/app_details/${appName}`);
        return {
            access_token: response.data.access_token,
            redirect_uri: appDetailsResponse.data.sso_redirect_uri,
        };
    }
    
    async function register(registrationData) {
        const uiStore = useUiStore();
        try {
            const adminStatusResponse = await apiClient.get('/api/auth/admin_status');
            const isAdminExists = adminStatusResponse.data.admin_exists;

            if (!isAdminExists) {
                await apiClient.post('/api/auth/create_first_admin', registrationData);
                // After successful creation, log the new admin in.
                // The login function will handle closing the modal and showing "What's Next".
                await login(registrationData.username, registrationData.password);
            } else {
                const response = await apiClient.post('/api/auth/register', registrationData);
                const registrationMode = response.data.is_active ? 'direct' : 'admin_approval';
                if (registrationMode === 'direct') {
                    uiStore.addNotification('Registration successful! You can now log in.', 'success');
                } else {
                    uiStore.addNotification('Registration successful! Your account is now pending administrator approval.', 'info', 6000);
                }
                uiStore.closeModal('register');
                uiStore.openModal('login');
            }
        } catch (error) {
            // Re-throw to be handled by the component.
            throw error;
        }
    }

    function clearAuthData() {
        user.value = null;
        token.value = null;
        localStorage.removeItem('lollms_token');
    }

    async function logout() {
        const uiStore = useUiStore();
        if (!isAuthenticated.value) { return; }
        const localToken = token.value;

        const { useDiscussionsStore } = await import('./discussions');
        const { useDataStore } = await import('./data');
        clearAuthData();
        useDiscussionsStore().$reset();
        useDataStore().$reset();
        
        uiStore.closeModal();
        uiStore.addNotification('You have been logged out.', 'info');
        if (!window.location.pathname.startsWith('/app/')) {
            uiStore.openModal('login');
        }

        if (localToken) {
            apiClient.post('/api/auth/logout').catch(error => {
                console.warn("Backend logout call failed, which can be normal after token removal.", error);
            });
        }
    }

    async function updateUserProfile(profileData) {
        try {
            const response = await apiClient.put('/api/auth/me', profileData);
            user.value = { ...user.value, ...response.data };
            useUiStore().addNotification('Profile updated successfully.', 'success');
        } catch(error) {
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
            throw error;
        }
    }

    async function changePassword(passwordData) {
         try {
            await apiClient.post('/api/auth/change-password', passwordData);
            useUiStore().addNotification('Password changed successfully.', 'success');
        } catch(error) {
            throw error;
        }
    }



    async function fetchDataZone() {
        if (!isAuthenticated.value) return;
        try {
            const response = await apiClient.get('/api/auth/me/data-zone');
            if (user.value) {
                user.value.data_zone = response.data.content;
            }
        } catch (error) {
            console.error("Failed to fetch data_zone:", error);
            useUiStore().addNotification('Could not load user data zone.', 'error');
        }
    }

    async function updateDataZone(content) {
        if (!isAuthenticated.value) return;
        try {
            const response = await apiClient.put('/api/auth/me/data-zone', { content });
            // FIX: Use Object.assign to merge updates into the existing reactive user object,
            // which is safer than replacing the whole object.
            if (user.value) {
                Object.assign(user.value, response.data);
            } else {
                user.value = response.data;
            }
        } catch (error) {
            useUiStore().addNotification('Failed to save data zone.', 'error');
            throw error;
        }
    }

    async function updateMemoryZone(content) {
        if (!isAuthenticated.value) return;
        try {
            const response = await apiClient.put('/api/auth/me/memory', { content });
            // FIX: Use Object.assign to merge updates into the existing reactive user object,
            // which is safer than replacing the whole object.
            if (user.value) {
                Object.assign(user.value, response.data);
            } else {
                user.value = response.data;
            }
        } catch (error) {
            useUiStore().addNotification('Failed to save data zone.', 'error');
            throw error;
        }
    }

    async function fetchScratchpad() {
        if (!isAuthenticated.value) return;
        try {
            const response = await apiClient.get('/api/auth/me/scratchpad');
            if (user.value) {
                user.value.scratchpad = response.data.content;
            }
        } catch (error) {
            console.error("Failed to fetch scratchpad:", error);
            useUiStore().addNotification('Could not load user scratchpad.', 'error');
        }
    }

    async function updateScratchpad(content) {
        if (!isAuthenticated.value) return;
        try {
            await apiClient.put('/api/auth/me/scratchpad', { content });
            if (user.value) {
                user.value.scratchpad = content;
            }
            // No notification on success for scratchpad to avoid being noisy.
        } catch (error) {
            useUiStore().addNotification('Failed to save scratchpad.', 'error');
            throw error;
        }
    }


    return {
        user, token, isAuthenticating, isAuthenticated, isAdmin,
        loadingMessage, loadingProgress, funFact,
        attemptInitialAuth, login, register, logout,
        updateUserProfile, updateUserPreferences, changePassword,
        ssoLoginWithPassword, ssoAuthorizeApplication,
        fetchScratchpad, updateScratchpad,
        fetchDataZone,
        updateDataZone,
        updateMemoryZone
    };
});
