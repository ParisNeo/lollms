// [UPDATE] frontend/webui/src/stores/auth.js
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
    const isFetchingFunFact = ref(false);
    const latex_builder_enabled = ref(false);
    const export_to_txt_enabled = ref(true);
    const export_to_markdown_enabled = ref(true);
    const export_to_html_enabled = ref(true);
    const export_to_pdf_enabled = ref(false);
    const export_to_docx_enabled = ref(false);
    const export_to_xlsx_enabled = ref(false);
    const export_to_pptx_enabled = ref(false);
    const allow_user_chunking_config = ref(true);
    const default_chunk_size = ref(1024);
    const default_chunk_overlap = ref(256);
    const ssoClientConfig = ref({ enabled: false, display_name: 'Login with SSO', icon_url: '' });

    // --- WebSocket State ---
    const ws = ref(null);
    const wsConnected = ref(false);
    const hasConnectedOnce = ref(false); // Track initial connection for recovery detection
    let reconnectTimeout = null;
    let heartbeatInterval = null;

    // --- Audio Objects ---
    const audioChime = new Audio('/audio/chime_aud.wav');
    const audioLost = new Audio('/audio/connection_lost.wav');
    const audioRecovered = new Audio('/audio/connection_recovered.wav');

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
            latex_builder_enabled.value = welcomeInfoResponse.data.latex_builder_enabled;
            export_to_txt_enabled.value = welcomeInfoResponse.data.export_to_txt_enabled;
            export_to_markdown_enabled.value = welcomeInfoResponse.data.export_to_markdown_enabled;
            export_to_html_enabled.value = welcomeInfoResponse.data.export_to_html_enabled;
            export_to_pdf_enabled.value = welcomeInfoResponse.data.export_to_pdf_enabled;
            export_to_docx_enabled.value = welcomeInfoResponse.data.export_to_docx_enabled;
            export_to_xlsx_enabled.value = welcomeInfoResponse.data.export_to_xlsx_enabled;
            export_to_pptx_enabled.value = welcomeInfoResponse.data.export_to_pptx_enabled;
        } catch (e) {
            console.warn("Could not fetch welcome info. Using defaults.");
        }
    }

    async function fetchNewFunFact() {
        if (isFetchingFunFact.value) return;
        isFetchingFunFact.value = true;
        try {
            const welcomeInfoResponse = await apiClient.get('/api/welcome-info');
            funFact.value = welcomeInfoResponse.data.fun_fact;
            welcome_fun_fact_color.value = welcomeInfoResponse.data.fun_fact_color;
            welcome_fun_fact_category.value = welcomeInfoResponse.data.fun_fact_category;
        } finally {
            isFetchingFunFact.value = false;
        }
    }
    
    async function refreshUser() {
        if (!token.value) return;
        try {
            const response = await apiClient.get('/api/auth/me');
            user.value = response.data;
            if (user.value) {
                const uiStore = useUiStore();
                if (user.value.message_font_size) {
                    uiStore.message_font_size = user.value.message_font_size;
                }
                allow_user_chunking_config.value = user.value.allow_user_chunking_config;
                default_chunk_size.value = user.value.default_chunk_size;
                default_chunk_overlap.value = user.value.default_chunk_overlap;
            }
        } catch (error) {
            console.error("Failed to refresh user details:", error);
        }
    }

    // --- WebSocket Connection Management ---
    function connectWebSocket() {
        if (!token.value || (ws.value && (ws.value.readyState === WebSocket.OPEN || ws.value.readyState === WebSocket.CONNECTING))) {
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = import.meta.env.DEV ? 'localhost:9642' : window.location.host;
        const wsUrl = `${protocol}//${host}/ws/dm/${token.value}`;
        
        ws.value = new WebSocket(wsUrl);

        ws.value.onopen = () => {
            if (hasConnectedOnce.value && !wsConnected.value) {
                audioRecovered.play().catch(() => {});
                const uiStore = useUiStore();
                uiStore.addNotification('Connection recovered', 'success');
            }

            wsConnected.value = true;
            hasConnectedOnce.value = true;
            clearTimeout(reconnectTimeout);
            // Start heartbeat
            if (heartbeatInterval) clearInterval(heartbeatInterval);
            heartbeatInterval = setInterval(() => {
                if (ws.value && ws.value.readyState === WebSocket.OPEN) {
                    ws.value.send("ping");
                }
            }, 30000); // 30s
        };

        ws.value.onmessage = async (event) => {
            if (event.data === "pong") return; // Ignore pong
            
            let data;
            try {
                data = JSON.parse(event.data);
            } catch (e) {
                return; 
            }
            
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
                    if (user.value && data.data.sender_id !== user.value.id) {
                        audioChime.play().catch(() => {});
                        if ("Notification" in window && Notification.permission === "granted") {
                             new Notification(`Message from ${data.data.sender_username}`, {
                                 body: data.data.content,
                                 icon: data.data.sender_icon || '/favicon.ico'
                             });
                        }
                    }
                    break;
                case 'new_comment': 
                    socialStore.handleNewComment(data.data); 
                    break;
                case 'new_friend_request':
                    socialStore.handleIncomingFriendRequest(data.data);
                    break;
                case 'friend_online':
                    uiStore.addNotification(`${data.data.username} is now online.`, 'info', 4000, false, null, data.data.icon);
                    break;
                case 'new_shared_discussion':
                    discussionsStore.fetchSharedWithMe();
                    uiStore.addNotification(`'${data.data.discussion_title}' was shared with you by ${data.data.from_user}.`, 'info');
                    break;
                case 'discussion_updated':
                    if (discussionsStore.currentDiscussionId === data.data.discussion_id) {
                        uiStore.addNotification(`Discussion updated by ${data.data.sender_username}.`, 'info');
                        discussionsStore.refreshActiveDiscussionMessages();
                    } else {
                         uiStore.addNotification(`A shared discussion was updated by ${data.data.sender_username}.`, 'info');
                    }
                    discussionsStore.loadDiscussions();
                    break;
                case 'new_message_from_task':
                    discussionsStore.handleNewMessageFromTask(data.data);
                    break;
                case 'discussion_unshared':
                    discussionsStore.fetchSharedWithMe(); 
                    if (discussionsStore.currentDiscussionId === data.data.discussion_id) {
                        discussionsStore.selectDiscussion(null);
                        uiStore.setMainView('feed');
                    }
                    uiStore.addNotification(`Access to a shared discussion was revoked by ${data.data.from_user}.`, 'warning');
                    break;
                case 'discussion_unsubscribed':
                     uiStore.addNotification(`${data.data.unsubscribed_user} unsubscribed from '${data.data.discussion_title}'.`, 'info');
                     break;
                case 'admin_broadcast': 
                    uiStore.addNotification(data.data.message, 'broadcast', 0, true, data.data.sender); 
                    break;
                case 'task_update': 
                    tasksStore.addTask(data.data); 
                    break;
                case 'task_end': {
                    tasksStore.addTask(data.data);
                    const task = data.data;
                    if (task.status === 'completed' && task.result) {
                        if (task.result.status === 'image_generated_in_message') {
                            discussionsStore.handleNewMessageFromTask({
                                discussion_id: task.result.discussion_id,
                                message: task.result.new_message
                            });
                            uiStore.addNotification(`Image generated in discussion.`, 'success');
                        } else if (task.result.zone) { 
                            discussionsStore.handleDataZoneUpdate(task.result);
                        } else if (task.name === 'Generate User Avatar' && task.result.new_icon_url) {
                            refreshUser();
                            uiStore.addNotification('Avatar generated and updated!', 'success');
                        } else {
                            uiStore.addNotification(`Task '${task.name}' finished successfully.`, 'success', 5000);
                        }
                    } else if (task.status !== 'completed') {
                        uiStore.addNotification(`Task '${task.name}' finished with status: ${task.status}.`, 'info', 5000);
                    }
                    break;
                }
                case 'app_status_changed': { 
                    const { useAdminStore } = await import('./admin'); 
                    useAdminStore().handleAppStatusUpdate(data.data); 
                    dataStore.handleServiceStatusUpdate(data.data); 
                    break; 
                }
                case 'data_zone_processed':
                    if (data.data.task_data) tasksStore.addTask(data.data.task_data);
                    discussionsStore.handleDataZoneUpdate(data.data);
                    break;
                case 'discussion_images_updated': 
                    discussionsStore.handleDiscussionImagesUpdated(data.data); 
                    break;
                case 'tasks_cleared': 
                    tasksStore.handleTasksCleared(data.data); 
                    break;
                case 'settings_updated':
                    uiStore.addNotification('Global settings updated by an admin. Refreshing your session...', 'info', 5000);
                    await refreshUser(); 
                    await fetchWelcomeInfo();
                    break;
                case 'bindings_updated':
                    uiStore.addNotification('LLM bindings updated by an admin. Refreshing model list.', 'info', 5000);
                    dataStore.fetchAvailableLollmsModels();
                    dataStore.fetchAvailableTtiModels();
                    dataStore.fetchAvailableTtsModels();
                    dataStore.fetchAvailableSttModels();
                    await refreshUser();
                    break;               
            }
        };

        ws.value.onclose = (event) => {
            if (wsConnected.value) {
                audioLost.play().catch(() => {});
                const uiStore = useUiStore();
                uiStore.addNotification('Connection lost', 'error');
            }
            wsConnected.value = false;
            ws.value = null;
            if (heartbeatInterval) clearInterval(heartbeatInterval);
            if (event.code !== 1000) { 
                reconnectTimeout = setTimeout(connectWebSocket, 5000);
            }
        };
        ws.value.onerror = (error) => {
            wsConnected.value = false;
            if (ws.value) ws.value.close();
        };
    }

    function disconnectWebSocket() {
        wsConnected.value = false;
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
        if (heartbeatInterval) clearInterval(heartbeatInterval);
        if (ws.value) { 
            ws.value.close(1000, "User logout"); 
            ws.value = null; 
        }
    }

    async function fetchUserAndInitialData() {
        const uiStore = useUiStore();
        try {
            loadingProgress.value = 20;
            loadingMessage.value = 'Authenticating...';
            const response = await apiClient.get('/api/auth/me');
            user.value = response.data;
            if (user.value) {
                if (user.value.message_font_size) {
                    uiStore.message_font_size = user.value.message_font_size;
                }
                allow_user_chunking_config.value = user.value.allow_user_chunking_config;
                default_chunk_size.value = user.value.default_chunk_size;
                default_chunk_overlap.value = user.value.default_chunk_overlap;
            }

            // Request notification permission on load
            if ("Notification" in window && Notification.permission === "default") {
                Notification.requestPermission();
            }
            
            connectWebSocket();
            
            const { useDiscussionsStore } = await import('./discussions');
            const { useDataStore } = await import('./data');
            const { useSocialStore } = await import('./social');
            const discussionsStore = useDiscussionsStore();
            const dataStore = useDataStore();
            const socialStore = useSocialStore();
            
            loadingProgress.value = 40;
            loadingMessage.value = 'Loading user data...';
            await Promise.all([
                discussionsStore.loadDiscussions(),
                discussionsStore.fetchSharedWithMe(),
                discussionsStore.fetchDiscussionGroups(),
                dataStore.loadAllInitialData(),
                socialStore.fetchFriends().catch(() => {}),
                socialStore.fetchConversations().catch(() => {})
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
                    const lastDiscussionId = user.value.last_discussion_id;
                    const discussionExists = lastDiscussionId && discussionsStore.sortedDiscussions.some(d => d.id === lastDiscussionId);

                    if (discussionExists) {
                        await discussionsStore.selectDiscussion(lastDiscussionId, null, true);
                    } else if (discussionsStore.sortedDiscussions.length > 0) {
                        await discussionsStore.selectDiscussion(discussionsStore.sortedDiscussions[0].id, null, true);
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

        await Promise.all([fetchWelcomeInfo(), fetchSsoClientConfig()]);
        
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
        disconnectWebSocket();
    }

    async function logout() {
        const uiStore = useUiStore();
        if (!isAuthenticated.value) { return; }

        const { useDiscussionsStore } = await import('./discussions');
        const { useDataStore } = await import('./data');
        const { useSocialStore } = await import('./social');
        const { useTasksStore } = await import('./tasks');
        const { useMemoriesStore } = await import('./memories');

        await apiClient.post('/api/auth/logout').catch(error => {
            console.warn("Backend logout call failed, which can be normal after token removal.", error);
        });
        
        clearAuthData();
        
        useDiscussionsStore().$reset();
        useDataStore().$reset();
        useSocialStore().$reset();
        useTasksStore().$reset();
        useMemoriesStore().$reset();
        
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

            let finalRegData = registrationData;
            if (!isAdminExists) {
                finalRegData = {
                    ...registrationData,
                    is_admin: true,
                    is_moderator: true
                };
            }

            const endpoint = isAdminExists ? '/api/auth/register' : '/api/auth/create_first_admin';
            
            const response = await apiClient.post(endpoint, finalRegData);

            if (!isAdminExists) {
                await login(registrationData.username, registrationData.password);
            } else {
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
    
    async function updateUserPreferences(preferences, notify = true) {
        try {
            const response = await apiClient.put('/api/auth/me', preferences);
            if (user.value) {
                Object.assign(user.value, response.data);
                if (preferences.hasOwnProperty('message_font_size')) {
                    const uiStore = useUiStore();
                    uiStore.message_font_size = preferences.message_font_size;
                }
            }
            if (preferences.hasOwnProperty('include_memory_date_in_context')) {
                const { useDiscussionsStore } = await import('./discussions');
                const discussionsStore = useDiscussionsStore();
                if (discussionsStore.currentDiscussionId) {
                    discussionsStore.refreshDataZones(discussionsStore.currentDiscussionId);
                }
            }
            if (notify) {
                useUiStore().addNotification('Settings saved successfully.', 'success');
            }
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

    async function generateAvatar(prompt) {
        const uiStore = useUiStore();
        const { useTasksStore } = await import('./tasks');
        const tasksStore = useTasksStore();
        
        uiStore.addNotification('Starting avatar generation...', 'info');
        try {
            const response = await apiClient.post('/api/auth/me/generate-icon', { prompt });
            const task = response.data;
            tasksStore.addTask(task);
            return task;
        } catch (error) {
            console.error("Failed to start avatar generation task:", error);
            return null;
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

    async function fetchScratchpad() {
         // Kept for backwards compatibility if needed, but data-zone is preferred
         await fetchDataZone();
    }

    async function updateScratchpad(content) {
        await updateDataZone(content);
    }

    async function fetchSsoClientConfig() {
        try {
            const response = await apiClient.get('/api/sso-client/config');
            ssoClientConfig.value = response.data;
        } catch (e) {
            ssoClientConfig.value = { enabled: false, display_name: 'Login with SSO', icon_url: '' };
        }
    }


    return {
        user, token, isAuthenticating, isAuthenticated, isAdmin,
        loadingMessage, loadingProgress, funFact, welcomeText, welcomeSlogan, welcome_logo_url, welcome_fun_fact_color, welcome_fun_fact_category, wsConnected,
        ssoClientConfig,
        isFetchingFunFact,
        latex_builder_enabled,
        export_to_txt_enabled,
        export_to_markdown_enabled,
        export_to_html_enabled,
        export_to_pdf_enabled,
        export_to_docx_enabled,
        export_to_xlsx_enabled,
        export_to_pptx_enabled,
        allow_user_chunking_config,
        default_chunk_size,
        default_chunk_overlap,
        attemptInitialAuth, login, register, logout, fetchWelcomeInfo, fetchNewFunFact,
        updateUserProfile, updateUserPreferences, changePassword,
        ssoLoginWithPassword, ssoAuthorizeApplication,
        fetchScratchpad, updateScratchpad,
        fetchDataZone,
        updateDataZone,
        refreshUser,
        generateAvatar,
        fetchSsoClientConfig
    };
});
