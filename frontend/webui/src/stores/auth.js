import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useAuthStore = defineStore('auth', () => {
    // --- State ---
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
    
    // System-wide permissions from config
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
    const hasConnectedOnce = ref(false); 
    let reconnectTimeout = null;
    let heartbeatInterval = null;

    // --- Audio Objects ---
    const audioChime = new Audio('/audio/chime_aud.wav');
    const audioLost = new Audio('/audio/connection_lost.wav');
    const audioRecovered = new Audio('/audio/connection_recovered.wav');

    // --- Getters ---
    const isAuthenticated = computed(() => !!user.value);
    const isAdmin = computed(() => user.value?.is_admin || false);

    // --- Actions ---

    async function fetchWelcomeInfo() {
        try {
            const welcomeInfoResponse = await apiClient.get('/api/welcome-info');
            funFact.value = welcomeInfoResponse.data.fun_fact;
            welcomeText.value = welcomeInfoResponse.data.welcome_text;
            welcomeSlogan.value = welcomeInfoResponse.data.welcome_slogan;
            welcome_logo_url.value = welcomeInfoResponse.data.welcome_logo_url;
            welcome_fun_fact_color.value = welcomeInfoResponse.data.fun_fact_color;
            welcome_fun_fact_category.value = welcomeInfoResponse.data.fun_fact_category;
            latex_builder_enabled.value = !!welcomeInfoResponse.data.latex_builder_enabled;
            export_to_txt_enabled.value = !!welcomeInfoResponse.data.export_to_txt_enabled;
            export_to_markdown_enabled.value = !!welcomeInfoResponse.data.export_to_markdown_enabled;
            export_to_html_enabled.value = !!welcomeInfoResponse.data.export_to_html_enabled;
            export_to_pdf_enabled.value = !!welcomeInfoResponse.data.export_to_pdf_enabled;
            export_to_docx_enabled.value = !!welcomeInfoResponse.data.export_to_docx_enabled;
            export_to_xlsx_enabled.value = !!welcomeInfoResponse.data.export_to_xlsx_enabled;
            export_to_pptx_enabled.value = !!welcomeInfoResponse.data.export_to_pptx_enabled;
        } catch (e) {
            console.warn("Could not fetch welcome info. Using defaults.");
        }
    }

    async function fetchNewFunFact() {
        if (isFetchingFunFact.value) return;
        isFetchingFunFact.value = true;
        try {
            const welcomeInfoResponse = await apiClient.get('/api/fun-fact');
            funFact.value = welcomeInfoResponse.data.fun_fact;
            welcome_fun_fact_color.value = welcomeInfoResponse.data.color;
            welcome_fun_fact_category.value = welcomeInfoResponse.data.category;
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
            return response.data;
        } catch (error) {
            console.error("Failed to refresh user details:", error);
            if (error.response?.status === 401) clearAuthData();
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
        
        console.log(`[WebSocket] Connecting to ${wsUrl}...`);
        ws.value = new WebSocket(wsUrl);

        ws.value.onopen = () => {
            console.log('[WebSocket] Connected.');
            if (hasConnectedOnce.value && !wsConnected.value) {
                audioRecovered.play().catch(() => {});
                useUiStore().addNotification('Connection recovered', 'success');
            }

            wsConnected.value = true;
            hasConnectedOnce.value = true;
            clearTimeout(reconnectTimeout);
            
            if (heartbeatInterval) clearInterval(heartbeatInterval);
            heartbeatInterval = setInterval(() => {
                if (ws.value && ws.value.readyState === WebSocket.OPEN) ws.value.send("ping");
            }, 30000); 
        };

        ws.value.onmessage = async (event) => {
            if (event.data === "pong") return;
            let data;
            try { data = JSON.parse(event.data); } catch (e) { return; }
            
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
                case 'notification': uiStore.addNotification(data.data.message, data.data.type || 'info', data.data.duration || 3000); break;
                case 'new_dm': 
                    socialStore.handleNewDm(data.data);
                    if (user.value && data.data.sender_id !== user.value.id) {
                        audioChime.play().catch(() => {});
                        if ("Notification" in window && Notification.permission === "granted") {
                             new Notification(`Message from ${data.data.sender_username}`, { body: data.data.content, icon: data.data.sender_icon || '/favicon.ico' });
                        }
                    }
                    break;
                case 'new_comment': socialStore.handleNewComment(data.data); break;
                case 'new_friend_request': socialStore.handleIncomingFriendRequest(data.data); break;
                case 'friend_online': uiStore.addNotification(`${data.data.username} is now online.`, 'info', 4000, false, null, data.data.icon); break;
                case 'new_shared_discussion': discussionsStore.fetchSharedWithMe(); uiStore.addNotification(`'${data.data.discussion_title}' was shared by ${data.data.from_user}.`, 'info'); break;
                case 'discussion_updated':
                    if (discussionsStore.currentDiscussionId === data.data.discussion_id) {
                        uiStore.addNotification(`Discussion updated by ${data.data.sender_username}.`, 'info');
                        discussionsStore.refreshActiveDiscussionMessages();
                    }
                    discussionsStore.loadDiscussions();
                    break;
                case 'discussion_images_updated':
                    discussionsStore.handleDiscussionImagesUpdated(data.data);
                    break;
                case 'new_message_from_task': discussionsStore.handleNewMessageFromTask(data.data); break;
                case 'admin_broadcast': uiStore.addNotification(data.data.message, 'broadcast', 0, true, data.data.sender); break;
                case 'task_update': tasksStore.addTask(data.data); break;
                case 'task_end': {
                    tasksStore.addTask(data.data);
                    const task = data.data;
                    if (task.status === 'completed' && task.result?.status === 'image_generated_in_message') {
                        discussionsStore.handleNewMessageFromTask({ discussion_id: task.result.discussion_id, message: task.result.new_message });
                        uiStore.addNotification(`Image generated.`, 'success');
                    } else if (task.name === 'Generate User Avatar' && task.result?.new_icon_url) {
                        refreshUser();
                        uiStore.addNotification('Avatar updated!', 'success');
                    }
                    break;
                }
                case 'settings_updated': await Promise.all([refreshUser(), fetchWelcomeInfo()]); break;
                case 'bindings_updated': await Promise.all([dataStore.fetchAvailableLollmsModels(), dataStore.fetchAvailableTtiModels(), dataStore.fetchAvailableTtsModels(), dataStore.fetchAvailableSttModels(), refreshUser()]); break;
            }
        };

        ws.value.onclose = (event) => {
            if (wsConnected.value) {
                audioLost.play().catch(() => {});
                useUiStore().addNotification('Connection lost', 'error');
            }
            wsConnected.value = false;
            ws.value = null;
            if (heartbeatInterval) clearInterval(heartbeatInterval);
            if (event.code !== 1000) reconnectTimeout = setTimeout(connectWebSocket, 5000);
        };
    }

    function disconnectWebSocket() {
        wsConnected.value = false;
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
        if (heartbeatInterval) clearInterval(heartbeatInterval);
        if (ws.value) { ws.value.close(1000, "Logout"); ws.value = null; }
    }

    async function fetchUserAndInitialData() {
        try {
            loadingProgress.value = 20;
            loadingMessage.value = 'Authenticating...';
            await refreshUser();
            
            if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
            connectWebSocket();
            
            const { useDiscussionsStore } = await import('./discussions');
            const { useDataStore } = await import('./data');
            const { useSocialStore } = await import('./social');
            const { useMemoriesStore } = await import('./memories');
            const discussionsStore = useDiscussionsStore();
            const dataStore = useDataStore();
            const socialStore = useSocialStore();
            const memoriesStore = useMemoriesStore();
            
            loadingProgress.value = 40;
            loadingMessage.value = 'Loading user data...';
            await Promise.all([
                discussionsStore.loadDiscussions(),
                discussionsStore.fetchSharedWithMe(),
                discussionsStore.fetchDiscussionGroups(),
                dataStore.loadAllInitialData(),
                memoriesStore.fetchMemories(),
                socialStore.fetchFriends().catch(() => {}),
                socialStore.fetchConversations().catch(() => {})
            ]);

            loadingProgress.value = 80;
            loadingMessage.value = 'Preparing interface...';

            if (user.value) {
                const uiStore = useUiStore();
                let targetView = user.value.first_page;
                if (user.value.user_ui_level < 2 && targetView === 'feed') targetView = 'new_discussion'; 
                uiStore.setMainView(targetView === 'feed' ? 'feed' : 'chat');

                if (targetView === 'last_discussion') {
                    const lastId = user.value.last_discussion_id;
                    if (lastId && discussionsStore.sortedDiscussions.some(d => d.id === lastId)) await discussionsStore.selectDiscussion(lastId, null, true);
                    else if (discussionsStore.sortedDiscussions.length > 0) await discussionsStore.selectDiscussion(discussionsStore.sortedDiscussions[0].id, null, true);
                    else await discussionsStore.createNewDiscussion();
                } else if (targetView === 'new_discussion') {
                    await discussionsStore.createNewDiscussion();
                }
            }
            loadingProgress.value = 100;
            loadingMessage.value = 'Done!';
            return true;
        } catch (error) {
            clearAuthData();
            return false;
        }
    }

    async function attemptInitialAuth() {
        if (window.location.pathname.startsWith('/app/') || window.location.pathname.startsWith('/reset-password')) {
            if (token.value) await refreshUser().catch(() => clearAuthData());
            isAuthenticating.value = false;
            return;
        }

        isAuthenticating.value = true;
        loadingProgress.value = 0;
        loadingMessage.value = 'Waking up the hamsters...';

        await Promise.all([fetchWelcomeInfo(), fetchSsoClientConfig()]);
        
        loadingProgress.value = 10;
        loadingMessage.value = 'Checking credentials...';

        try {
            const adminStatusResponse = await apiClient.get('/api/auth/admin_status');
            if (!adminStatusResponse.data.admin_exists) {
                isAuthenticating.value = false;
                useUiStore().openModal('firstAdminSetup'); 
                return;
            } else if (token.value) {
                await fetchUserAndInitialData();
            }
        } catch (error) {
            useUiStore().addNotification('Failed to connect to server.', 'error');
            clearAuthData();
        } finally {
            isAuthenticating.value = false;
        }
    }

    async function login(username, password) {
        try {
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);
            const response = await apiClient.post('/api/auth/token', formData);
            
            token.value = response.data.access_token;
            localStorage.setItem('lollms-token', token.value);

            useUiStore().closeModal();
            isAuthenticating.value = true;
            await fetchUserAndInitialData();
            isAuthenticating.value = false;
            window.location.reload(); 
        } catch (error) {
            isAuthenticating.value = false;
            useUiStore().addNotification('Login failed.', 'error');
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
        if (!isAuthenticated.value) return;
        const { useDiscussionsStore } = await import('./discussions');
        const { useDataStore } = await import('./data');
        const { useSocialStore } = await import('./social');
        const { useTasksStore } = await import('./tasks');
        const { useMemoriesStore } = await import('./memories');

        await apiClient.post('/api/auth/logout').catch(() => {});
        clearAuthData();
        
        useDiscussionsStore().$reset();
        useDataStore().$reset();
        useSocialStore().$reset();
        useTasksStore().$reset();
        useMemoriesStore().$reset();
        
        useUiStore().closeModal();
        window.location.href = '/';
    }
    
    async function ssoLoginWithPassword(clientId, username, password) {
        await login(username, password);
        return await ssoAuthorizeApplication(clientId);
    }

    async function ssoAuthorizeApplication(clientId) {
        const formData = new FormData();
        formData.append('client_id', clientId);
        const response = await apiClient.post('/api/sso/authorize', formData);
        return { access_token: response.data.access_token, redirect_uri: response.data.sso_redirect_uri };
    }
    
    async function register(registrationData) {
        try {
            const adminStatusResponse = await apiClient.get('/api/auth/admin_status');
            const isAdminExists = adminStatusResponse.data.admin_exists;
            const endpoint = isAdminExists ? '/api/auth/register' : '/api/auth/create_first_admin';
            const response = await apiClient.post(endpoint, registrationData);

            if (!isAdminExists) await login(registrationData.username, registrationData.password);
            else {
                useUiStore().addNotification('Registration successful!', 'success');
                useUiStore().closeModal('register');
                useUiStore().openModal('login');
            }
        } catch (error) { throw error; }
    }

    async function updateUserProfile(profileData) {
        const response = await apiClient.put('/api/auth/me', profileData);
        user.value = { ...user.value, ...response.data };
        useUiStore().addNotification('Profile updated.', 'success');
    }
    
    // --- Helper to map option key to preference key ---
    function optionToPrefKey(opt) {
        const map = {
            'image_generation': 'image_generation_enabled',
            'image_editing': 'image_editing_enabled',
            'slide_maker': 'slide_maker_enabled',
            'memory': 'memory_enabled',
            'note_generation': 'note_generation_enabled'
        };
        return map[opt];
    }

    async function updateUserPreferences(preferences, notify = true) {
        // --- NEW LOGIC: Handle Personality Requirements ---
        const { useDataStore } = await import('./data');
        const dataStore = useDataStore();
        const uiStore = useUiStore();

        // 1. If switching personality, enable its required options
        if (preferences.active_personality_id) {
            const personality = dataStore.getPersonalityById(preferences.active_personality_id);
            if (personality && personality.required_context_options) {
                personality.required_context_options.forEach(opt => {
                    const prefKey = optionToPrefKey(opt);
                    if (prefKey) preferences[prefKey] = true;
                });
            }
        }

        // 2. If changing context settings, verify against current active personality
        // Determine the effective personality ID (new one if changing, else current)
        const targetPersonalityId = preferences.active_personality_id !== undefined 
            ? preferences.active_personality_id 
            : user.value?.active_personality_id;

        if (targetPersonalityId) {
            const personality = dataStore.getPersonalityById(targetPersonalityId);
            if (personality && personality.required_context_options) {
                let revertToDefault = false;
                personality.required_context_options.forEach(opt => {
                    const prefKey = optionToPrefKey(opt);
                    // Check if this specific option is being explicitly disabled in this update
                    if (prefKey && preferences[prefKey] === false) {
                        revertToDefault = true;
                    }
                });
                
                if (revertToDefault) {
                    preferences.active_personality_id = null; // Reset to default
                    if (notify) uiStore.addNotification(`Reverted to default personality because a required option was disabled.`, 'warning');
                }
            }
        }
        // --- END NEW LOGIC ---

        const response = await apiClient.put('/api/auth/me', preferences);
        if (user.value) {
            Object.assign(user.value, response.data);
            if (preferences.message_font_size) uiStore.message_font_size = preferences.message_font_size;
        }
        if (notify) uiStore.addNotification('Settings saved.', 'success');
    }

    async function changePassword(passwordData) {
        await apiClient.post('/api/auth/change-password', passwordData);
        useUiStore().addNotification('Password changed.', 'success');
    }

    async function generateAvatar(prompt) {
        const response = await apiClient.post('/api/auth/me/generate-icon', { prompt });
        const { useTasksStore } = await import('./tasks');
        useTasksStore().addTask(response.data);
        return response.data;
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
        ssoClientConfig, isFetchingFunFact,
        latex_builder_enabled, export_to_txt_enabled, export_to_markdown_enabled, export_to_html_enabled, export_to_pdf_enabled, export_to_docx_enabled, export_to_xlsx_enabled, export_to_pptx_enabled,
        allow_user_chunking_config, default_chunk_size, default_chunk_overlap,
        attemptInitialAuth, login, register, logout, fetchWelcomeInfo, fetchNewFunFact,
        updateUserProfile, updateUserPreferences, changePassword,
        ssoLoginWithPassword, ssoAuthorizeApplication,
        refreshUser, generateAvatar, fetchSsoClientConfig, connectWebSocket, disconnectWebSocket
    };
});
