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
                    getDiscussionsStore().then(s => {
                        s.fetchSharedWithMe(); 
                        uiStore.addNotification(`'${data.data.discussion_title}' was shared by ${data.data.from_user}.`, 'info');
                    });
                    break;
                case 'discussion_updated':
                    getDiscussionsStore().then(s => {
                        if (s.currentDiscussionId === data.data.discussion_id) {
                            uiStore.addNotification(`Discussion updated by ${data.data.sender_username}.`, 'info');
                            s.refreshActiveDiscussionMessages();
                        }
                        s.loadDiscussions();
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
            if (wsConnected.value) {
                const now = Date.now();
                // Debounce audio: only play if at least 10 seconds passed since last play
                if (now - lastConnectionLostTime > 10000) {
                    audioLost.play().catch(() => {});
                    lastConnectionLostTime = now;
                }
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
            loadingProgress.value = 10;
            loadingMessage.value = 'Verifying session...';
            await refreshUser();
            
            if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
            
            loadingProgress.value = 20;
            loadingMessage.value = 'Establishing connection...';
            connectWebSocket();
            
            // Import stores sequentially to update UI
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
            'note_generation': 'note_generation_enabled',
            'skills_building': 'skills_building_enabled',
            'skills_library': 'skills_library_enabled',
            'web_search': 'web_search_enabled',
            'inline_widgets': 'inline_widgets_enabled'
        };
        return map[opt];
    }

    async function updateUserPreferences(preferences, notify = true) {
        // 0. Equality Guard: Prevent infinite loops if the values match the current state
        if (user.value) {
            let isActualChange = false;
            for (const [key, value] of Object.entries(preferences)) {
                // Perform a simple comparison. For objects/arrays, we check JSON equality.
                const currentVal = user.value[key];
                if (typeof value === 'object' && value !== null) {
                    if (JSON.stringify(currentVal) !== JSON.stringify(value)) {
                        isActualChange = true;
                        break;
                    }
                } else if (currentVal !== value) {
                    isActualChange = true;
                    break;
                }
            }
            if (!isActualChange) return; // Exit immediately to prevent recursion
        }

        // --- NEW LOGIC: Handle Personality Requirements ---
        const { useDataStore } = await import('./data');
        const dataStore = useDataStore();
        const uiStore = useUiStore();

        // Determine the personality we are evaluating (either the one we are switching to, or the current one)
        const isChangingPersonality = preferences.active_personality_id !== undefined;
        let targetId = isChangingPersonality ? preferences.active_personality_id : user.value?.active_personality_id;

        if (targetId) {
            const personality = dataStore.getPersonalityById(targetId);
            if (personality && personality.required_context_options && personality.required_context_options.length > 0) {
                
                // SCENARIO 1: User is trying to disable a requirement of the CURRENT personality
                if (!isChangingPersonality) {
                    const violatingRequirement = personality.required_context_options.some(opt => {
                        const key = optionToPrefKey(opt);
                        return key && preferences[key] === false;
                    });

                    if (violatingRequirement) {
                        // To allow the user to turn off the feature, we MUST drop the personality requirement
                        preferences.active_personality_id = null;
                        targetId = null; // Requirements no longer apply for this session
                        if (notify) uiStore.addNotification('Reset to default personality to allow disabling required features.', 'info');
                    }
                }

                // SCENARIO 2: If we are still using a personality (or just switched to one), force its rules
                if (targetId) {
                    const activePers = dataStore.getPersonalityById(targetId);
                    activePers.required_context_options.forEach(opt => {
                        const key = optionToPrefKey(opt);
                        if (key) {
                            // Force to true in the outgoing payload
                            preferences[key] = true;
                        }
                    });
                }
            }
        }
        // --- END NEW LOGIC ---

        // 1. Optimistic Update (Moved here to prevent "blinking" UI states)
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
