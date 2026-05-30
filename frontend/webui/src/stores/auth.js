import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
// Removed specialized static store imports to fix Effective Dynamic Import warnings

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
    let heartbeatInterval = null;
    let reconnectTimeout = null;

    // --- Audio Objects ---
    const audioChime = new Audio('/audio/chime_aud.wav');
    const audioLost = new Audio('/audio/connection_lost.wav');
    const audioRecovered = new Audio('/audio/connection_recovered.wav');
    
    // Throttling for connection lost sound to prevent "Ai Ai Ai" spam loop
    let lastConnectionLostTime = 0;

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
    /**
     * Checks if the JWT token is expired locally.
     * Prevents backend bombardment with dead tokens.
     */
    function isTokenExpired(tokenStr) {
        if (!tokenStr) return true;
        try {
            const base64Url = tokenStr.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const payload = JSON.parse(window.atob(base64));

            if (!payload.exp) return false;
            // Add a 60-second grace period for clock skew
            return (Date.now() / 1000) > (payload.exp - 60);
        } catch (e) {
            return true;
        }
    }
    // --- WebSocket Connection Management ---
    /**
     * Checks if the JWT token is expired locally.
     * Prevents backend bombardment with dead tokens.
     */
    function isTokenExpired(tokenStr) {
        if (!tokenStr) return true;
        try {
            const base64Url = tokenStr.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const payload = JSON.parse(window.atob(base64));
            
            if (!payload.exp) return false;
            // Add a 60-second grace period for clock skew
            return (Date.now() / 1000) > (payload.exp - 60);
        } catch (e) {
            return true;
        }
    }

    function connectWebSocket() {
        if (!token.value || isTokenExpired(token.value)) {
            if (token.value) {
                console.warn("[WebSocket] Token expired. Aborting connection loop.");
                clearAuthData(); // Force logout to stop the loop
            }
            return;
        }

        if (ws.value && (ws.value.readyState === WebSocket.OPEN || ws.value.readyState === WebSocket.CONNECTING)) {
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

        ws.value.onmessage = (event) => {
            if (event.data === "pong") return;
            if (!ws.value || ws.value.readyState !== WebSocket.OPEN) return;

            let data;
            try { data = JSON.parse(event.data); } catch (e) { return; }
            
            // Move store resolution inside an immediate scope to avoid async gaps
            // during high-frequency updates
            const uiStore = useUiStore();
            
            // Helper to get stores without async imports in the loop
            const getSocialStore = () => import('./social').then(m => m.useSocialStore());
            const getTasksStore = () => import('./tasks').then(m => m.useTasksStore());
            const getDataStore = () => import('./data').then(m => m.useDataStore());
            const getDiscussionsStore = () => import('./discussions').then(m => m.useDiscussionsStore());

            // Process message type
            switch (data.type) {
                case 'init_progress':
                    // Update splash screen in real-time
                    loadingMessage.value = data.data.message;
                    // Increment progress bar: we add a bit for every step until it hits 100
                    if (loadingProgress.value < 95) {
                        loadingProgress.value += 5;
                    }
                    if (data.data.is_error) {
                        uiStore.addNotification(data.data.message, 'error');
                    }
                    break;
                case 'notification': 
                    uiStore.addNotification(data.data.message, data.data.type || 'info', data.data.duration || 3000); 
                    break;
                case 'new_dm': 
                    getSocialStore().then(s => s.handleNewDm(data.data));
                    if (user.value && data.data.sender_id !== user.value.id) {
                        audioChime.play().catch(() => {});
                        if ("Notification" in window && Notification.permission === "granted") {
                             new Notification(`Message from ${data.data.sender_username}`, { body: data.data.content, icon: data.data.sender_icon || '/favicon.ico' });
                        }
                    }
                    break;
                case 'new_comment': 
                    getSocialStore().then(s => s.handleNewComment(data.data)); 
                    break;
                case 'new_friend_request': 
                    getSocialStore().then(s => s.handleIncomingFriendRequest(data.data)); 
                    break;
                case 'friend_online': 
                    uiStore.addNotification(`${data.data.username} is now online.`, 'info', 4000, false, null, data.data.icon); 
                    break;
                case 'new_shared_discussion': 
                    getDiscussionsStore().then(async (s) => {
                        // 1. Immediately trigger the fetch to update the sidebar list
                        await s.fetchSharedWithMe(); 

                        // 2. Determine message based on update type
                        const isUpdate = data.data.update_type === 'permission_change';
                        const verb = isUpdate ? 'updated permissions for' : 'shared a new discussion:';

                        uiStore.addNotification(
                            `${data.data.from_user} ${verb} '${data.data.discussion_title}'`, 
                            'info',
                            6000 // Show for slightly longer (6s)
                        );
                    });
                    break;
                case 'discussion_updated':
                    getDiscussionsStore().then(s => {
                        if (s.currentDiscussionId === data.data.discussion_id) {
                            uiStore.addNotification(`Discussion updated by ${data.data.sender_username}.`, 'info');
                            s.refreshActiveDiscussionMessages();
                        }
                        s.loadDiscussions();
                        s.fetchAllUserArtefacts(); // Instantly sync the global artefacts list as well!
                    });
                    break;
                case 'data_zone_processed': 
                    getDiscussionsStore().then(s => s.handleDataZoneUpdate(data.data)); 
                    break;
                case 'skill_saved':
                    import('./skills').then(s => s.useSkillsStore().fetchSkills());
                    uiStore.addNotification(`Skill saved: ${data.data.title}`, 'success');
                    break;
                case 'discussion_images_updated':
                    getDiscussionsStore().then(s => s.handleDiscussionImagesUpdated(data.data));
                    break;
                case 'new_message_from_task': 
                    getDiscussionsStore().then(s => s.handleNewMessageFromTask(data.data)); 
                    break;
                case 'admin_broadcast': 
                    uiStore.addNotification(data.data.message, 'broadcast', 0, true, data.data.sender); 
                    break;
                case 'task_update': 
                    getTasksStore().then(s => s.addTask(data.data)); 
                    break;
                case 'task_end': {
                    getTasksStore().then(ts => {
                        ts.addTask(data.data);
                        const task = data.data;
                        if (task.status === 'completed' && task.result?.status === 'image_generated_in_message') {
                            getDiscussionsStore().then(ds => ds.handleNewMessageFromTask({ discussion_id: task.result.discussion_id, message: task.result.new_message }));
                            uiStore.addNotification(`Image generated.`, 'success');
                        } else if (task.name === 'Generate User Avatar' && task.result?.new_icon_url) {
                            refreshUser();
                            uiStore.addNotification('Avatar updated!', 'success');
                        }
                    });
                    break;
                }
                case 'settings_updated': 
                    Promise.all([refreshUser(), fetchWelcomeInfo()]); 
                    break;
                case 'bindings_updated': 
                    getDataStore().then(ds => {
                        Promise.all([
                            ds.fetchAvailableLollmsModels(), 
                            ds.fetchAvailableTtiModels(), 
                            ds.fetchAvailableTtsModels(), 
                            ds.fetchAvailableSttModels(), 
                            refreshUser()
                        ]);
                    });
                    break;
                case 'dm_deleted':
                    if (activeConversations.value[data.data.partner_id] || (data.data.conversation_id && activeConversations.value[data.data.conversation_id])) {
                        const targetId = data.data.conversation_id || data.data.partner_id;
                        activeConversations.value[targetId].messages = activeConversations.value[targetId].messages.filter(m => m.id !== data.data.message_id);
                    }
                    fetchConversations();
                    break;
            }
        };

        ws.value.onclose = (event) => {
            const wasConnected = wsConnected.value;
            wsConnected.value = false;
            ws.value = null;
            if (heartbeatInterval) clearInterval(heartbeatInterval);

            // Handle abnormal closures
            if (wasConnected) {
                const now = Date.now();
                if (now - lastConnectionLostTime > 10000) {
                    audioLost.play().catch(() => {});
                    lastConnectionLostTime = now;
                }
                useUiStore().addNotification('Connection lost', 'error');
            }

            // Stop retrying if the closure implies an authentication failure (1008 Policy Violation)
            // or if the token is already expired.
            if (event.code === 1008 || event.code === 4003 || isTokenExpired(token.value)) {
                console.error("[WebSocket] Permanent Auth Failure (Code " + event.code + "). Clearing session.");
                useUiStore().addNotification('Your session has expired or the security key changed. Please log in again.', 'error', 10000);
                clearAuthData(); // Force logout so user can re-authenticate
                return;
            }

            // Normal close (1000) doesn't need retry
            if (event.code !== 1000) {
                // Implementation of jittered/incremental backoff to prevent bombardment
                const retryDelay = wasConnected ? 5000 : 15000;
                reconnectTimeout = setTimeout(connectWebSocket, retryDelay);
            }
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
            loadingProgress.value = 10;
            loadingMessage.value = 'Verifying session...';
            await refreshUser();

            if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();

            loadingProgress.value = 20;
            loadingMessage.value = 'Establishing connection...';
            connectWebSocket();

            // Access stores lazily to prevent initial bundle bloat
            const { useDiscussionsStore } = await import('./discussions');
            const { useDataStore } = await import('./data');
            const { useSocialStore } = await import('./social');
            const { useMemoriesStore } = await import('./memories');

            const discussionsStore = useDiscussionsStore();
            const dataStore = useDataStore();
            const socialStore = useSocialStore();
            const memoriesStore = useMemoriesStore();

            // 1. Discussions
            loadingProgress.value = 30;
            loadingMessage.value = 'Syncing your conversations...';
            await Promise.all([
                discussionsStore.loadDiscussions(),
                discussionsStore.fetchSharedWithMe(),
                discussionsStore.fetchDiscussionGroups()
            ]);

            // 2. AI Engines & Models (The heavy part)
            loadingProgress.value = 50;
            loadingMessage.value = 'Loading AI Models & Personalities...';
            await dataStore.loadAllInitialData();

            // 3. Personal Knowledge & Memory
            loadingProgress.value = 75;
            loadingMessage.value = 'Restoring long-term memory...';
            await memoriesStore.fetchMemories();

            // 4. Social & Connections
            loadingProgress.value = 85;
            loadingMessage.value = 'Connecting with friends...';
            await Promise.allSettled([
                socialStore.fetchFriends(),
                socialStore.fetchConversations()
            ]);

            loadingProgress.value = 95;
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
          // 1️⃣  Préparer les paramètres
          const params = new URLSearchParams();
          params.append('username', username);
          params.append('password', password);
      
          // 2️⃣  Envoyer avec le bon header
          const response = await apiClient.post(
            '/api/auth/token',
            params,
            { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
          );
      
          // 3️⃣  Traiter le token
          token.value = response.data.access_token;
          localStorage.setItem('lollms-token', token.value);
      
          // 4️⃣  UI & data
          useUiStore().closeModal();
          isAuthenticating.value = true;
          await fetchUserAndInitialData();
          isAuthenticating.value = false;
      
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

        await apiClient.post('/api/auth/logout').catch(() => {});
        clearAuthData();

        useDiscussionsStore().$reset();
        useDataStore().$reset();
        useSocialStore().$reset();
        useTasksStore().$reset();
        useMemoriesStore().$reset();
        useSkillsStore().$reset();

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
            'note_generation': 'note_generation_enabled',
            'skills_building': 'skills_building_enabled',
            'skills_library': 'skills_library_enabled',
            'web_search': 'web_search_enabled',
            'inline_widgets': 'inline_widgets_enabled',
            'form_building': 'form_building_enabled',
            'book_generation': 'book_generation_enabled',
            'artefacts': 'artefacts_enabled'
        };
        return map[opt];
    }

    async function updateUserPreferences(preferences, notify = true) {
        // 0. Robust Equality Guard
        if (user.value) {
            let isActualChange = false;
            for (const [key, value] of Object.entries(preferences)) {
                const currentVal = user.value[key];
                if (value !== null && typeof value === 'object') {
                    try {
                        if (JSON.stringify(currentVal) !== JSON.stringify(value)) {
                            isActualChange = true;
                            break;
                        }
                    } catch (e) { isActualChange = true; break; }
                } 
                else if (currentVal !== value) {
                    isActualChange = true;
                    break;
                }
            }
            if (!isActualChange) return;
        }

        // --- Handle Personality Requirements & Context Safety ---
        const dataStore = (await import('./data')).useDataStore();
        const uiStore = useUiStore();

        // 1. Determine Intent: Are we selecting a NEW personality?
        // Check for undefined AND null (explicit clear) vs just presence
        const isExplicitlySettingPersonality = preferences.active_personality_id !== undefined;
        const targetPersonalityId = isExplicitlySettingPersonality ? preferences.active_personality_id : user.value?.active_personality_id;

        if (targetPersonalityId) {
            const personality = dataStore.getPersonalityById(targetPersonalityId);
            if (personality?.required_context_options?.length > 0) {

                let hasViolations = false;

                personality.required_context_options.forEach(opt => {
                    const key = optionToPrefKey(opt);
                    if (!key) return;

                    // A. VIOLATION CHECK: User is actively turning a required feature OFF
                    if (preferences[key] === false) {
                        hasViolations = true;
                    } 

                    // B. REQUIREMENT FULFILLMENT: Only force features ON if we are ACTIVELY switching 
                    //    to this personality for the first time.
                    if (isExplicitlySettingPersonality && preferences[key] === undefined && !user.value[key]) {
                        preferences[key] = true;
                    }
                });

                if (hasViolations) {
                    // User priority: They want the feature OFF. Revert to default personality.
                    preferences.active_personality_id = null;
                    if (notify) uiStore.addNotification('Setting manually disabled: Reverting to default personality.', 'info');
                }
            }
        }

        // 1. Optimistic Update
        if (user.value) {
            user.value = { ...user.value, ...preferences };
        }

        const response = await apiClient.put('/api/auth/me', preferences);
        if (user.value) {
            // CRITICAL: Replace the object reference to ensure deep reactivity 
            // and trigger computed properties in the UI (like breadcrumb badges)
            user.value = { ...user.value, ...response.data };
            
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
