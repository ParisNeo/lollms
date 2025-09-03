// frontend/webui/src/stores/auth.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useAuthStore = defineStore('auth', () => {
    const user = ref(null);
    const token = ref(localStorage.getItem('lollms-token') || null);
    const isAuthenticating = ref(true);
    const loadingMessage = ref('Initializing...');
    const loadingProgress = ref(0);
    const funFact = ref('');
    const welcomeText = ref('lollms');
    const welcomeSlogan = ref('One tool to rule them all');
    const welcome_logo_url = ref(null);
    const welcome_fun_fact_color = ref('#3B82F6');
    const welcome_fun_fact_category = ref(null);

    // --- WebSocket State ---
    const ws = ref(null);
    const wsConnected = ref(false);
    let reconnectTimeout = null;

    if (token.value) {
        apiClient.defaults.headers.common['Authorization'] = `Bearer ${token.value}`;
    }

    const isAuthenticated = computed(() => !!user.value);
    const isAdmin = computed(() => user.value?.is_admin || false);

    async function fetchWelcomeInfo() {
        try {
            const welcomeInfoResponse = await apiClient.get('/api/welcome-info');
            funFact.value = welcomeInfoResponse.data.fun_fact;
            welcomeText.value = welcomeInfoResponse.data.welcome_text;
            welcomeSlogan.value = welcomeInfoResponse.data.welcome_slogan;
            welcome_logo_url.value = welcomeInfoResponse.data.welcome_logo_url;
            welcome_fun_fact_color.value = welcomeInfoResponse.data.fun_fact_color;
            welcome_fun_fact_category.value = welcomeInfoResponse.data.fun_fact_category;
        } catch (e) {
            console.warn("Could not fetch welcome info. Using defaults.");
            funFact.value = 'The LoLLMs project is open source and seeks to democratize AI.';
            welcomeText.value = 'lollms';
            welcomeSlogan.value = 'One tool to rule them all';
            welcome_logo_url.value = null;
            welcome_fun_fact_color.value = '#3B82F6';
            welcome_fun_fact_category.value = 'General';
        }
    }
    
    async function refreshUser() {
        if (!token.value) return;
        try {
            const response = await apiClient.get('/api/auth/me');
            user.value = response.data;
            console.log("[AuthStore] User details refreshed.");
        } catch (error) {
            console.error("Failed to refresh user details:", error);
        }
    }
    // --- WebSocket Connection Management ---
    function connectWebSocket() {
        if (!token.value) {
            console.log("[WebSocket] Connection skipped: no token.");
            return;
        }
        if (ws.value && (ws.value.readyState === WebSocket.OPEN || ws.value.readyState === WebSocket.CONNECTING)) {
            console.log("[WebSocket] Connection already open or connecting.");
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = import.meta.env.DEV ? 'localhost:9642' : window.location.host;
        const wsUrl = `${protocol}//${host}/ws/dm/${token.value}`;
        
        console.log(`[WebSocket] Attempting to connect to ${wsUrl}...`);
        ws.value = new WebSocket(wsUrl);

        ws.value.onopen = () => {
            wsConnected.value = true;
            console.log("[WebSocket] Connection established successfully.");
            clearTimeout(reconnectTimeout);
        };

        ws.value.onmessage = async (event) => {
            const data = JSON.parse(event.data);
            const { useSocialStore } = await import('./social');
            const { useTasksStore } = await import('./tasks');
            const { useDataStore } = await import('./data');
            const { useDiscussionsStore } = await import('./discussions');
            const socialStore = useSocialStore();
            const uiStore = useUiStore();
            const tasksStore = useTasksStore();
            const dataStore = useDataStore();
            const discussionsStore = useDiscussionsStore();

            switch (data.type) {
                case 'new_dm':
                    socialStore.handleNewDm(data.data);
                    break;
                case 'new_shared_discussion':
                    discussionsStore.loadDiscussions();
                    uiStore.addNotification(`'${data.data.discussion_title}' was shared with you by ${data.data.from_user}.`, 'info');
                    break;
                case 'discussion_updated':
                    if (discussionsStore.currentDiscussionId === data.data.discussion_id) {
                        console.log(`[WebSocket] Received update for active discussion ${data.data.discussion_id}. Refreshing messages.`);
                        uiStore.addNotification(`Discussion updated by ${data.data.sender_username}.`, 'info');
                        discussionsStore.refreshActiveDiscussionMessages();
                    } else {
                         uiStore.addNotification(`A shared discussion was updated by ${data.data.sender_username}.`, 'info');
                    }
                    discussionsStore.loadDiscussions();
                    break;
                case 'discussion_unshared':
                    if (discussionsStore.currentDiscussionId === data.data.discussion_id) {
                        discussionsStore.selectDiscussion(null);
                        uiStore.setMainView('feed');
                    }
                    discussionsStore.loadDiscussions();
                    uiStore.addNotification(`Access to a shared discussion was revoked by ${data.data.from_user}.`, 'warning');
                    break;
                case 'admin_broadcast':
                    uiStore.addNotification(data.data.message, 'broadcast', 0, true, data.data.sender);
                    break;
                case 'task_update':
                    tasksStore.addTask(data.data);
                    break;
                case 'app_status_changed': {
                    const { useAdminStore } = await import('./admin');
                    useAdminStore().handleAppStatusUpdate(data.data);
                    dataStore.handleServiceStatusUpdate(data.data);
                    break;
                }
                case 'data_zone_processed':
                    discussionsStore.handleDataZoneUpdate(data.data);
                    break;
                case 'discussion_images_updated':
                    discussionsStore.handleDiscussionImagesUpdated(data.data);
                    break;
                case 'tasks_cleared':
                    tasksStore.handleTasksCleared(data.data);
                    break;
                case 'settings_updated':
                    uiStore.addNotification('Global settings updated by admin. Refreshing session...', 'info');
                    await refreshUser();
                    await fetchWelcomeInfo();
                    break;
                case 'bindings_updated':
                    uiStore.addNotification('LLM bindings updated. Refreshing model list.', 'info');
                    dataStore.fetchAvailableLollmsModels();
                    break;               
            }
        };

        ws.value.onclose = (event) => {
            wsConnected.value = false;
            ws.value = null;
            if (event.code !== 1000) {
                reconnectTimeout = setTimeout(connectWebSocket, 5000);
            }
        };
        ws.value.onerror = (error) => { wsConnected.value = false; ws.value?.close(); };
    }

    function disconnectWebSocket() {
        wsConnected.value = false;
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
        if (ws.value) { ws.value.close(1000, "User logout"); ws.value = null; }
    }

    async function fetchUserAndInitialData() {
        const uiStore = useUiStore();
        try {
            loadingProgress.value = 20;
            loadingMessage.value = 'Authenticating...';
            const response = await apiClient.get('/api/auth/me');
            user.value = response.data;
            
            connectWebSocket();
            
            const { useDiscussionsStore } = await import('./discussions');
            const { useDataStore } = await import('./data');
            const discussionsStore = useDiscussionsStore();
            const dataStore = useDataStore();
            
            loadingProgress.value = 40;
            loadingMessage.value = 'Loading user data...';
            await Promise.all([
                discussionsStore.loadDiscussions(),
                dataStore.loadAllInitialData()
            ]);

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
            return true;
        } catch (error) {
            console.error("Failed to fetch user and initial data:", error);
            clearAuthData();
            return false;
        }
    }

    async function attemptInitialAuth() {
        if (window.location.pathname.startsWith('/app/')) {
            if(token.value){
                try{
                    const response = await apiClient.get('/api/auth/me');
                    user.value = response.data;
                    connectWebSocket();
                } catch(e){
                    clearAuthData();
                }
            }
            isAuthenticating.value = false;
            return;
        }

        if (window.location.pathname.startsWith('/reset-password')) {
            isAuthenticating.value = false;
            return;
        }

        isAuthenticating.value = true;
        loadingProgress.value = 0;
        loadingMessage.value = 'Waking up the hamsters...';

        await fetchWelcomeInfo();
        
        await new Promise(resolve => setTimeout(resolve, 500));
        loadingProgress.value = 10;
        loadingMessage.value = 'Checking credentials...';

        const uiStore = useUiStore();

        try {
            const adminStatusResponse = await apiClient.get('/api/auth/admin_status');
            if (!adminStatusResponse.data.admin_exists) {
                loadingMessage.value = 'First run setup...';
                isAuthenticating.value = false;
                uiStore.openModal('firstAdminSetup'); 
                return;
            } else if (token.value) {
                await fetchUserAndInitialData();
            }
        } catch (error) {
            console.error("Failed to check admin status or during initial auth:", error);
            uiStore.addNotification('Failed to connect to server. Please try again later.', 'error');
            clearAuthData();
        } finally {
            isAuthenticating.value = false;
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
            localStorage.setItem('lollms-token', token.value);
            apiClient.defaults.headers.common['Authorization'] = `Bearer ${token.value}`;


            uiStore.closeModal();
            isAuthenticating.value = true;

            const success = await fetchUserAndInitialData();

            isAuthenticating.value = false;

            if (success) {
                uiStore.addNotification('Login successful!', 'success');
                if (user.value.is_admin && !user.value.first_login_done) { 
                    uiStore.openModal('whatsNext'); 
                }
            } else {
                throw new Error("Authentication succeeded but failed to fetch user data.");
            }
        } catch (error) {
            isAuthenticating.value = false;
            const detail = error.response?.data?.detail || "An unknown error occurred.";
            if (detail.includes("account is inactive")) {
                 uiStore.addNotification(detail, 'warning');
            } else if (error.message.includes('fetch user data')){
                 uiStore.addNotification('Login succeeded, but failed to load user data.', 'error');
            }
            else {
                 uiStore.addNotification('Login failed: Incorrect username or password.', 'error');
            }
            throw error;
        }
    }

    function clearAuthData() {
        user.value = null;
        token.value = null;
        localStorage.removeItem('lollms-token');
        apiClient.defaults.headers.common['Authorization'] = null;
        disconnectWebSocket();
    }

    async function logout() {
        const uiStore = useUiStore();
        if (!isAuthenticated.value) { return; }

        const { useDiscussionsStore } = await import('./discussions');
        const { useDataStore } = await import('./data');
        const { useSocialStore } = await import('./social');
        const { useTasksStore } = await import('./tasks');

        await apiClient.post('/api/auth/logout').catch(error => {
            console.warn("Backend logout call failed, which can be normal after token removal.", error);
        });
        
        clearAuthData();
        
        useDiscussionsStore().$reset();
        useDataStore().$reset();
        useSocialStore().$reset();
        useTasksStore().$reset();
        
        uiStore.closeModal();
        uiStore.addNotification('You have been logged out.', 'info');
    }
    
    async function ssoLoginWithPassword(clientId, username, password) {
        await login(username, password);
        return await ssoAuthorizeApplication(clientId);
    }

    async function ssoAuthorizeApplication(clientId) {
        const formData = new FormData();
        formData.append('client_id', clientId);
        const response = await apiClient.post('/api/sso/authorize', formData);
        return {
            access_token: response.data.access_token,
            redirect_uri: response.data.sso_redirect_uri,
        };
    }
    
    async function register(registrationData) {
        const uiStore = useUiStore();
        try {
            const adminStatusResponse = await apiClient.get('/api/auth/admin_status');
            const isAdminExists = adminStatusResponse.data.admin_exists;

            if (!isAdminExists) {
                await apiClient.post('/api/auth/create_first_admin', registrationData);
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
            throw error;
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
            await apiClient.put('/api/auth/me/data-zone', { content });
            if (user.value) {
                user.value.data_zone = content;
            }
        } catch (error) {
            useUiStore().addNotification('Failed to save data zone.', 'error');
            throw error;
        }
    }

    async function updateMemoryZone(content) {
        if (!isAuthenticated.value) return;
        try {
            await apiClient.put('/api/auth/me/memory', { content });
            if (user.value) {
                user.value.memory = content;
            }
        } catch (error) {
            useUiStore().addNotification('Failed to save memory.', 'error');
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
        } catch (error) {
            useUiStore().addNotification('Failed to save scratchpad.', 'error');
            throw error;
        }
    }


    return {
        user, token, isAuthenticating, isAuthenticated, isAdmin,
        loadingMessage, loadingProgress, funFact, welcomeText, welcomeSlogan, welcome_logo_url, welcome_fun_fact_color, welcome_fun_fact_category, wsConnected,
        attemptInitialAuth, login, register, logout, fetchWelcomeInfo,
        updateUserProfile, updateUserPreferences, changePassword,
        ssoLoginWithPassword, ssoAuthorizeApplication,
        fetchScratchpad, updateScratchpad,
        fetchDataZone,
        updateDataZone,
        updateMemoryZone,
        refreshUser
    };
});