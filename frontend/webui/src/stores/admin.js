// frontend/webui/src/stores/admin.js
import { defineStore } from 'pinia';
import { ref, reactive, watch, onMounted } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import useEventBus from '../services/eventBus';

async function startApp(appId) {
    const { useTasksStore } = await import('./tasks.js');
    const tasksStore = useTasksStore();
    const res = await apiClient.post(`/api/apps_zoo/installed/${appId}/start`);
    tasksStore.addTask(res.data);
}

async function stopApp(appId) {
    const { useTasksStore } = await import('./tasks.js');
    const tasksStore = useTasksStore();
    const res = await apiClient.post(`/api/apps_zoo/installed/${appId}/stop`);
    tasksStore.addTask(res.data);
}

async function fetchAppLog(appId) {
    const res = await apiClient.get(`/api/apps_zoo/installed/${appId}/logs`);
    return res.data.log_content;
}

// Helper to safely get and parse localStorage data
function getStoredFilters(key, defaults) {
    try {
        const stored = localStorage.getItem(key);
        if (stored) {
            const parsed = JSON.parse(stored);
            // Ensure all default keys are present
            return { ...defaults, ...parsed };
        }
    } catch (e) {
        console.error(`Could not parse stored filters for ${key}:`, e);
        localStorage.removeItem(key); // Clear corrupted data
    }
    return defaults;
}

export const useAdminStore = defineStore('admin', () => {
    const uiStore = useUiStore();
    const { on } = useEventBus();

    // --- State ---
    const dashboardStats = ref(null);
    const isLoadingDashboardStats = ref(false);
    const allUsers = ref([]);
    const isLoadingUsers = ref(false);

    const bindings = ref([]);
    const isLoadingBindings = ref(false);
    const availableBindingTypes = ref([]);

    const ttiBindings = ref([]);
    const isLoadingTtiBindings = ref(false);
    const availableTtiBindingTypes = ref([]);

    const ttsBindings = ref([]);
    const isLoadingTtsBindings = ref(false);
    const availableTtsBindingTypes = ref([]);

    const sttBindings = ref([]);
    const isLoadingSttBindings = ref(false);
    const availableSttBindingTypes = ref([]);

    const ragBindings = ref([]);
    const isLoadingRagBindings = ref(false);
    const availableRagBindingTypes = ref([]);

    const globalSettings = ref([]);
    const isLoadingSettings = ref(false);

    const aiBotSettings = ref(null); // NEW: For @lollms user settings
    const isLoadingAiBotSettings = ref(false); // NEW

    const isImporting = ref(false);
    const isEnhancingEmail = ref(false);
    
    const adminAvailableLollmsModels = ref([]);
    const isLoadingLollmsModels = ref(false);

    const zooRepositories = ref([]);
    const isLoadingZooRepositories = ref(false);
    const mcpZooRepositories = ref([]);
    const isLoadingMcpZooRepositories = ref(false);
    const promptZooRepositories = ref([]);
    const isLoadingPromptZooRepositories = ref(false);
    const personalityZooRepositories = ref([]);
    const isLoadingPersonalityZooRepositories = ref(false);

    const zooApps = ref({ items: [], total: 0, pages: 1, categories: [] });
    const isLoadingZooApps = ref(false);
    const zooMcps = ref({ items: [], total: 0, pages: 1, categories: [] });
    const isLoadingZooMcps = ref(false);
    const zooPrompts = ref({ items: [], total: 0, pages: 1, categories: [] });
    const isLoadingZooPrompts = ref(false);
    const zooPersonalities = ref({ items: [], total: 0, pages: 1, categories: [] });
    const isLoadingZooPersonalities = ref(false);

    const installedApps = ref([]);
    const isLoadingInstalledApps = ref(false);

    const systemStatus = ref(null);
    const isLoadingSystemStatus = ref(false);
    
    const connectedUsers = ref([]);
    const isLoadingConnectedUsers = ref(false);
    
    const funFacts = ref([]);
    const isLoadingFunFacts = ref(false);
    const funFactCategories = ref([]);
    const isLoadingFunFactCategories = ref(false);
    
    const newsArticles = ref([]);
    const isLoadingNewsArticles = ref(false);

    const serverInfo = ref(null);
    const isLoadingServerInfo = ref(false);
    const globalGenerationStats = ref(null);
    const isLoadingGlobalGenerationStats = ref(false);


    const appFilters = reactive(getStoredFilters('lollms-app-filters', {
        searchQuery: '',
        selectedCategory: 'All',
        installationStatusFilter: 'All',
        selectedRepository: 'All',
        sortKey: 'last_update_date',
        sortOrder: 'desc',
        currentPage: 1,
        pageSize: 24
    }));

    const mcpFilters = reactive(getStoredFilters('lollms-mcp-filters', {
        searchQuery: '',
        selectedCategory: 'All',
        installationStatusFilter: 'All',
        selectedRepository: 'All',
        sortKey: 'last_update_date',
        sortOrder: 'desc',
        currentPage: 1,
        pageSize: 24
    }));

    const promptFilters = reactive(getStoredFilters('lollms-prompt-filters', {
        searchQuery: '',
        selectedCategory: 'All',
        installationStatusFilter: 'All',
        selectedRepository: 'All',
        sortKey: 'name',
        sortOrder: 'asc',
        currentPage: 1,
        pageSize: 24
    }));

    const availableRagVectorizers = ref([]);


    watch(appFilters, (newFilters) => {
        localStorage.setItem('lollms-app-filters', JSON.stringify(newFilters));
    }, { deep: true });

    watch(mcpFilters, (newFilters) => {
        localStorage.setItem('lollms-mcp-filters', JSON.stringify(newFilters));
    }, { deep: true });

    watch(promptFilters, (newFilters) => {
        localStorage.setItem('lollms-prompt-filters', JSON.stringify(newFilters));
    }, { deep: true });

    async function handleTaskCompletion(task) {
        if (!task || !['completed', 'failed', 'cancelled'].includes(task.status)) return;

        const taskName = (task.name || '').toLowerCase();
        
        const isAppOrMcpTask = (taskName.includes('app') || taskName.includes('mcp')) && (taskName.includes('installing') || taskName.includes('start') || taskName.includes('stop') || taskName.includes('updating') || taskName.includes('fixing') || taskName.includes('purging'));
        const isPromptTask = taskName.includes('prompt');
        const isPersonalityTask = taskName.includes('personality');

        const promises = [];

        if (isAppOrMcpTask) {
            console.log(`[Admin Store] Refreshing Apps/MCPs due to task: ${task.name}`);
            promises.push(fetchZooApps(), fetchZooMcps());
            
            if (taskName.includes('start') && task.status === 'completed' && task.result?.item_type === 'mcp') {
                const { useDataStore } = await import('./data.js');
                promises.push(useDataStore().triggerMcpReload());
            }
        }
        
        if (isPromptTask) {
            console.log(`[Admin Store] Refreshing Prompts due to task: ${task.name}`);
            const { usePromptsStore } = await import('./prompts.js');
            promises.push(usePromptsStore().fetchPrompts(), fetchZooPrompts());
        }
        
        if (isPersonalityTask) {
            console.log(`[Admin Store] Refreshing Personalities due to task: ${task.name}`);
            const { useDataStore } = await import('./data.js');
            promises.push(useDataStore().fetchPersonalities(), fetchZooPersonalities());
        }

        if (taskName.includes('rss feed scraping')) {
            promises.push(fetchNewsArticles());
        }

        if (promises.length > 0) {
            await Promise.allSettled(promises);
            console.log(`[Admin Store] UI data refreshed for task: ${task.name}`);
        }
    }

    on('task:completed', handleTaskCompletion);
    
    function handleAppStatusUpdate(appData) {
        console.log("Admin store received app status update:", appData);
        const updateItemInList = (list) => {
            if (Array.isArray(list)) {
                const index = list.findIndex(item => item.id === appData.id);
                if (index !== -1) {
                    Object.assign(list[index], appData);
                    console.log(`Updated item '${appData.name}' in an admin list.`);
                }
            }
        };

        if (appData.item_type === 'app') {
            updateItemInList(zooApps.value.items);
        } else if (appData.item_type === 'mcp') {
            updateItemInList(zooMcps.value.items);
        }
    }

    async function fetchDashboardStats() {
        isLoadingDashboardStats.value = true;
        try {
            const response = await apiClient.get('/api/admin/stats');
            dashboardStats.value = response.data;
        } catch (error) {
            dashboardStats.value = null;
        } finally {
            isLoadingDashboardStats.value = false;
        }
    }

    async function fetchConnectedUsers() {
        isLoadingConnectedUsers.value = true;
        try {
            const response = await apiClient.get('/api/admin/ws-connections');
            connectedUsers.value = response.data;
        } catch (error) {
            console.error("Failed to fetch connected users:", error);
            connectedUsers.value = [];
        } finally {
            isLoadingConnectedUsers.value = false;
        }
    }

    async function broadcastMessage(message) {
        await apiClient.post('/api/admin/broadcast', { message });
    }

    async function syncInstallations() {
        const { useTasksStore } = await import('./tasks');
        const tasksStore = useTasksStore();
        const response = await apiClient.post('/api/apps_zoo/sync-installs');
        tasksStore.addTask(response.data);
    }

    async function purgeBrokenInstallation(item) {
        const { useTasksStore } = await import('./tasks');
        const tasksStore = useTasksStore();
        const response = await apiClient.post('/api/apps_zoo/purge-broken', { item_type: item.item_type || 'app', folder_name: item.folder_name });
        tasksStore.addTask(response.data);
    }
    
    async function fixBrokenInstallation(item) {
        const { useTasksStore } = await import('./tasks');
        const tasksStore = useTasksStore();
        const response = await apiClient.post('/api/apps_zoo/fix-broken', { item_type: item.item_type || 'app', folder_name: item.folder_name });
        tasksStore.addTask(response.data);
    }

    async function fetchSystemStatus() {
        isLoadingSystemStatus.value = true;
        try {
            const response = await apiClient.get('/api/admin/system-status');
            systemStatus.value = response.data;
        } finally {
            isLoadingSystemStatus.value = false;
        }
    }

    async function fetchServerInfo() {
        isLoadingServerInfo.value = true;
        try {
            const response = await apiClient.get('/api/admin/server-info');
            serverInfo.value = response.data;
        } finally {
            isLoadingServerInfo.value = false;
        }
    }

    async function purgeUnusedUploads() {
        const { useTasksStore } = await import('./tasks');
        const tasksStore = useTasksStore();
        const response = await apiClient.post('/api/admin/purge-unused-uploads');
        tasksStore.addTask(response.data);
        return response.data;
    }
    
        async function fetchSystemStatus() {
        isLoadingSystemStatus.value = true;
        try {
            const response = await apiClient.get('/api/admin/system-status');
            systemStatus.value = response.data;
        } finally {
            isLoadingSystemStatus.value = false;
        }
    }

    async function purgeUnusedUploads() {
        const { useTasksStore } = await import('./tasks');
        const tasksStore = useTasksStore();
        const response = await apiClient.post('/api/admin/purge-unused-uploads');
        tasksStore.addTask(response.data);
        return response.data;
    }


    async function fetchAllUsers(filters = {}) {
        isLoadingUsers.value = true;
        try {
            const response = await apiClient.get('/api/admin/users', { params: filters });
            allUsers.value = response.data;
        } finally {
            isLoadingUsers.value = false;
        }
    }

    async function fetchUserStats(userId) {
        try {
            const response = await apiClient.get(`/api/admin/users/${userId}/stats`);
            return response.data;
        } catch (error) {
            console.error(`Failed to fetch stats for user ${userId}:`, error);
            return null;
        }
    }    

    async function fetchGlobalGenerationStats() {
        isLoadingGlobalGenerationStats.value = true;
        try {
            const response = await apiClient.get('/api/admin/global-generation-stats');
            globalGenerationStats.value = response.data;
        } catch (error) {
            console.error("Failed to fetch global generation stats:", error);
            globalGenerationStats.value = null;
        } finally {
            isLoadingGlobalGenerationStats.value = false;
        }
    }
    
    async function sendEmailToUsers(subject, body, user_ids, backgroundColor, sendAsText) {
        const { useTasksStore } = await import('./tasks');
        const tasksStore = useTasksStore();
        const payload = { subject, body, user_ids, background_color: backgroundColor, send_as_text: sendAsText };
        const response = await apiClient.post('/api/admin/email-users', payload);
        tasksStore.addTask(response.data);
        return true;
    }
    
    async function enhanceEmail(subject, body, backgroundColor, prompt) {
        isEnhancingEmail.value = true;
        try {
            const response = await apiClient.post('/api/admin/enhance-email', { subject, body, background_color: backgroundColor, prompt });
            return response.data;
        } finally {
            isEnhancingEmail.value = false;
        }
    }

    async function batchUpdateUsers(payload) {
        await apiClient.post('/api/admin/users/batch-update-settings', payload);
        await fetchAllUsers();
    }
    
    async function fetchAdminAvailableLollmsModels() {
        if (adminAvailableLollmsModels.value.length > 0) return;
        isLoadingLollmsModels.value = true;
        try {
            const response = await apiClient.get('/api/admin/available-models');
            adminAvailableLollmsModels.value = response.data;
        } finally {
            isLoadingLollmsModels.value = false;
        }
    }

    async function fetchBindings() {
        isLoadingBindings.value = true;
        try {
            const response = await apiClient.get('/api/admin/bindings');
            bindings.value = response.data;
        } finally {
            isLoadingBindings.value = false;
        }
    }
    async function fetchAvailableBindingTypes() {
        const response = await apiClient.get('/api/admin/bindings/available_types');
        availableBindingTypes.value = response.data;
    }
    async function addBinding(payload) {
        const response = await apiClient.post('/api/admin/bindings', payload);
        bindings.value.push(response.data);
        uiStore.addNotification(`Binding '${response.data.alias}' created.`, 'success');
    }
    async function updateBinding(id, payload) {
        const response = await apiClient.put(`/api/admin/bindings/${id}`, payload);
        const index = bindings.value.findIndex(b => b.id === id);
        if (index !== -1) bindings.value[index] = response.data;
        uiStore.addNotification(`Binding '${response.data.alias}' updated.`, 'success');
    }
    async function deleteBinding(id) {
        await apiClient.delete(`/api/admin/bindings/${id}`);
        bindings.value = bindings.value.filter(b => b.id !== id);
        uiStore.addNotification('Binding deleted successfully.', 'success');
    }

    async function fetchBindingModels(bindingId) {
        const response = await apiClient.get(`/api/admin/bindings/${bindingId}/models`);
        return response.data;
    }
    async function getModelCtxSize(bindingId, modelName) {
        const response = await apiClient.post(`/api/admin/bindings/${bindingId}/context-size`, { model_name: modelName });
        return response.data.ctx_size;
    }
    async function saveModelAlias(bindingId, payload) {
        const response = await apiClient.put(`/api/admin/bindings/${bindingId}/alias`, payload);
        const index = bindings.value.findIndex(b => b.id === bindingId);
        if (index !== -1) bindings.value[index] = response.data;
    }
    async function deleteModelAlias(bindingId, modelName) {
        const response = await apiClient.delete(`/api/admin/bindings/${bindingId}/alias`, { data: { original_model_name: modelName } });
        const index = bindings.value.findIndex(b => b.id === bindingId);
        if (index !== -1) bindings.value[index] = response.data;
    }

    // --- TTI Actions ---
    async function fetchTtiBindings() {
        isLoadingTtiBindings.value = true;
        try {
            const response = await apiClient.get('/api/admin/tti-bindings');
            ttiBindings.value = response.data;
        } finally {
            isLoadingTtiBindings.value = false;
        }
    }
    async function fetchAvailableTtiBindingTypes() {
        const response = await apiClient.get('/api/admin/tti-bindings/available_types');
        availableTtiBindingTypes.value = response.data;
    }
    async function addTtiBinding(payload) {
        const response = await apiClient.post('/api/admin/tti-bindings', payload);
        ttiBindings.value.push(response.data);
        uiStore.addNotification(`TTI Binding '${response.data.alias}' created.`, 'success');
    }
    async function updateTtiBinding(id, payload) {
        const response = await apiClient.put(`/api/admin/tti-bindings/${id}`, payload);
        const index = ttiBindings.value.findIndex(b => b.id === id);
        if (index !== -1) ttiBindings.value[index] = response.data;
        uiStore.addNotification(`TTI Binding '${response.data.alias}' updated.`, 'success');
    }
    async function deleteTtiBinding(id) {
        await apiClient.delete(`/api/admin/tti-bindings/${id}`);
        ttiBindings.value = ttiBindings.value.filter(b => b.id !== id);
        uiStore.addNotification('TTI Binding deleted successfully.', 'success');
    }
    async function fetchTtiBindingModels(bindingId) {
        const response = await apiClient.get(`/api/admin/tti-bindings/${bindingId}/models`);
        return response.data;
    }
    async function saveTtiModelAlias(bindingId, payload) {
        const response = await apiClient.put(`/api/admin/tti-bindings/${bindingId}/alias`, payload);
        const index = ttiBindings.value.findIndex(b => b.id === bindingId);
        if (index !== -1) ttiBindings.value[index] = response.data;
    }
    async function deleteTtiModelAlias(bindingId, modelName) {
        const response = await apiClient.delete(`/api/admin/tti-bindings/${bindingId}/alias`, { data: { original_model_name: modelName } });
        const index = ttiBindings.value.findIndex(b => b.id === bindingId);
        if (index !== -1) ttiBindings.value[index] = response.data;
    }

    // --- TTS Actions ---
    async function fetchTtsBindings() {
        isLoadingTtsBindings.value = true;
        try {
            const response = await apiClient.get('/api/admin/tts-bindings');
            ttsBindings.value = response.data;
        } finally {
            isLoadingTtsBindings.value = false;
        }
    }
    async function fetchAvailableTtsBindingTypes() {
        const response = await apiClient.get('/api/admin/tts-bindings/available_types');
        availableTtsBindingTypes.value = response.data;
    }
    async function addTtsBinding(payload) {
        const response = await apiClient.post('/api/admin/tts-bindings', payload);
        ttsBindings.value.push(response.data);
        uiStore.addNotification(`TTS Binding '${response.data.alias}' created.`, 'success');
    }
    async function updateTtsBinding(id, payload) {
        const response = await apiClient.put(`/api/admin/tts-bindings/${id}`, payload);
        const index = ttsBindings.value.findIndex(b => b.id === id);
        if (index !== -1) ttsBindings.value[index] = response.data;
        uiStore.addNotification(`TTS Binding '${response.data.alias}' updated.`, 'success');
    }
    async function deleteTtsBinding(id) {
        await apiClient.delete(`/api/admin/tts-bindings/${id}`);
        ttsBindings.value = ttsBindings.value.filter(b => b.id !== id);
        uiStore.addNotification('TTS Binding deleted successfully.', 'success');
    }
    async function fetchTtsBindingModels(bindingId) {
        const response = await apiClient.get(`/api/admin/tts-bindings/${bindingId}/models`);
        return response.data;
    }
    async function saveTtsModelAlias(bindingId, payload) {
        const response = await apiClient.put(`/api/admin/tts-bindings/${bindingId}/alias`, payload);
        const index = ttsBindings.value.findIndex(b => b.id === bindingId);
        if (index !== -1) ttsBindings.value[index] = response.data;
    }
    async function deleteTtsModelAlias(bindingId, modelName) {
        const response = await apiClient.delete(`/api/admin/tts-bindings/${bindingId}/alias`, { data: { original_model_name: modelName } });
        const index = ttsBindings.value.findIndex(b => b.id === bindingId);
        if (index !== -1) ttsBindings.value[index] = response.data;
    }

    // --- STT Actions ---
    async function fetchSttBindings() {
        isLoadingSttBindings.value = true;
        try {
            console.log("Fetching STT bindings from API...");
            const response = await apiClient.get('/api/admin/stt-bindings');
            sttBindings.value = response.data;
        } finally {
            isLoadingSttBindings.value = false;
        }
    }
    async function fetchAvailableSttBindingTypes() {
        const response = await apiClient.get('/api/admin/stt-bindings/available_types');
        availableSttBindingTypes.value = response.data;
    }
    async function addSttBinding(payload) {
        const response = await apiClient.post('/api/admin/stt-bindings', payload);
        sttBindings.value.push(response.data);
        uiStore.addNotification(`STT Binding '${response.data.alias}' created.`, 'success');
    }
    async function updateSttBinding(id, payload) {
        const response = await apiClient.put(`/api/admin/stt-bindings/${id}`, payload);
        const index = sttBindings.value.findIndex(b => b.id === id);
        if (index !== -1) sttBindings.value[index] = response.data;
        uiStore.addNotification(`STT Binding '${response.data.alias}' updated.`, 'success');
    }
    async function deleteSttBinding(id) {
        await apiClient.delete(`/api/admin/stt-bindings/${id}`);
        sttBindings.value = sttBindings.value.filter(b => b.id !== id);
        uiStore.addNotification('STT Binding deleted successfully.', 'success');
    }
    async function fetchSttBindingModels(bindingId) {
        console.log(`Fetching models for STT binding ID: ${bindingId}`);
        const response = await apiClient.get(`/api/admin/stt-bindings/${bindingId}/models`);
        return response.data;
    }
    async function saveSttModelAlias(bindingId, payload) {
        const response = await apiClient.put(`/api/admin/stt-bindings/${bindingId}/alias`, payload);
        const index = sttBindings.value.findIndex(b => b.id === bindingId);
        if (index !== -1) sttBindings.value[index] = response.data;
    }
    async function deleteSttModelAlias(bindingId, modelName) {
        const response = await apiClient.delete(`/api/admin/stt-bindings/${bindingId}/alias`, { data: { original_model_name: modelName } });
        const index = sttBindings.value.findIndex(b => b.id === bindingId);
        if (index !== -1) sttBindings.value[index] = response.data;
    }

    // --- RAG Actions ---
    async function fetchRagBindings() {
        isLoadingRagBindings.value = true;
        try {
            const response = await apiClient.get('/api/admin/rag-bindings');
            ragBindings.value = response.data;
        } catch (e) {
            ragBindings.value = [];
            console.error("Failed to fetch RAG bindings:", e);
        } finally {
            isLoadingRagBindings.value = false;
        }
    }
    async function fetchAvailableRagBindingTypes() {
        try {
            const response = await apiClient.get('/api/admin/rag-bindings/available_types');
            availableRagBindingTypes.value = response.data;
        } catch(e) {
            availableRagBindingTypes.value = [];
            console.error("Failed to fetch RAG binding types:", e);
        }
    }
    async function addRagBinding(payload) {
        const response = await apiClient.post('/api/admin/rag-bindings', payload);
        ragBindings.value.push(response.data);
        uiStore.addNotification(`RAG Binding '${response.data.alias}' created.`, 'success');
    }
    async function updateRagBinding(id, payload) {
        const response = await apiClient.put(`/api/admin/rag-bindings/${id}`, payload);
        const index = ragBindings.value.findIndex(b => b.id === id);
        if (index !== -1) ragBindings.value[index] = response.data;
        uiStore.addNotification(`RAG Binding '${response.data.alias}' updated.`, 'success');
    }
    async function deleteRagBinding(id) {
        await apiClient.delete(`/api/admin/rag-bindings/${id}`);
        ragBindings.value = ragBindings.value.filter(b => b.id !== id);
        uiStore.addNotification('RAG Binding deleted successfully.', 'success');
    }
    async function fetchRagBindingModels(bindingId) {
        const response = await apiClient.get(`/api/admin/rag-bindings/${bindingId}/models`);
        return response.data;
    }
    async function saveRagModelAlias(bindingId, payload) {
        const response = await apiClient.put(`/api/admin/rag-bindings/${bindingId}/alias`, payload);
        const index = ragBindings.value.findIndex(b => b.id === bindingId);
        if (index !== -1) ragBindings.value[index] = response.data;
    }
    async function deleteRagModelAlias(bindingId, modelName) {
        const response = await apiClient.delete(`/api/admin/rag-bindings/${bindingId}/alias`, { data: { original_model_name: modelName } });
        const index = ragBindings.value.findIndex(b => b.id === bindingId);
        if (index !== -1) ragBindings.value[index] = response.data;
    }
    async function fetchRagModelsForType(vectorizerType) {
        const response = await apiClient.get(`/api/admin/rag-bindings/models-for-type/${vectorizerType}`);
        return response.data;
    }


    async function fetchGlobalSettings() {
        isLoadingSettings.value = true;
        try {
            const response = await apiClient.get('/api/admin/settings');
            globalSettings.value = response.data;
        } finally {
            isLoadingSettings.value = false;
        }
    }
    async function updateGlobalSettings(configs) {
        await apiClient.put('/api/admin/settings', { configs });
        await fetchGlobalSettings();
        uiStore.addNotification('Global settings updated.', 'success');
    }

    // --- NEW AI BOT SETTINGS ACTIONS ---
    async function fetchAiBotSettings() {
        isLoadingAiBotSettings.value = true;
        try {
            const response = await apiClient.get('/api/admin/ai-bot-settings');
            aiBotSettings.value = response.data;
        } finally {
            isLoadingAiBotSettings.value = false;
        }
    }

    async function updateAiBotSettings(settings) {
        const response = await apiClient.put('/api/admin/ai-bot-settings', settings);
        aiBotSettings.value = response.data;
        uiStore.addNotification('AI Bot user settings updated.', 'success');
    }
    // --- END NEW AI BOT ACTIONS ---

    async function uploadWelcomeLogo(file) {
        const formData = new FormData();
        formData.append('file', file);
        const response = await apiClient.post('/api/admin/upload-logo', formData);
        await fetchGlobalSettings(); // Refresh settings to get new logo URL
        uiStore.addNotification(response.data.message, 'success');
    }

    async function removeWelcomeLogo() {
        await apiClient.delete('/api/admin/remove-logo');
        await fetchGlobalSettings();
        uiStore.addNotification('Custom logo removed.', 'success');
    }

    async function uploadSslFile(file, fileType) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('file_type', fileType);
        const response = await apiClient.post('/api/admin/upload-ssl-file', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        await fetchGlobalSettings(); // Refresh settings to get new path
        return response.data.path;
    }


    async function importOpenWebUIData(file) {
        isImporting.value = true;
        const formData = new FormData();
        formData.append('file', file);
        try {
            await apiClient.post('/api/admin/import-openwebui', formData);
        } finally {
            isImporting.value = false;
        }
    }
    
    async function fetchZooRepositories() { isLoadingZooRepositories.value = true; try { const res = await apiClient.get('/api/apps_zoo/repositories'); zooRepositories.value = res.data; } finally { isLoadingZooRepositories.value = false; } }
    async function addZooRepository(payload) { const res = await apiClient.post('/api/apps_zoo/repositories', payload); zooRepositories.value.push(res.data); }
    async function deleteZooRepository(repoId) { await apiClient.delete(`/api/apps_zoo/repositories/${repoId}`); zooRepositories.value = zooRepositories.value.filter(r => r.id !== repoId); }
    async function pullZooRepository(repoId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/apps_zoo/repositories/${repoId}/pull`); tasksStore.addTask(res.data); }
    async function pullAllZooRepositories() { for (const repo of zooRepositories.value) await pullZooRepository(repo.id); }
    async function fetchZooApps() {
        isLoadingZooApps.value = true;
        const params = { page: appFilters.currentPage, page_size: appFilters.pageSize, sort_by: appFilters.sortKey, sort_order: appFilters.sortOrder, category: appFilters.selectedCategory !== 'All' ? appFilters.selectedCategory : undefined, repository: appFilters.selectedRepository !== 'All' ? appFilters.selectedRepository : undefined, search_query: appFilters.searchQuery || undefined, installation_status: appFilters.installationStatusFilter !== 'All' ? appFilters.installationStatusFilter : undefined };
        try {
            const [cat_res, items_res] = await Promise.all([ apiClient.get('/api/apps_zoo/categories'), apiClient.get('/api/apps_zoo/available', { params }) ]);
            zooApps.value = { ...items_res.data, categories: cat_res.data };
        } finally {
            isLoadingZooApps.value = false;
        }
    }
    async function installZooApp(payload) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post('/api/apps_zoo/install', payload); tasksStore.addTask(res.data); }
    async function fetchAppReadme(repo, folder) { const res = await apiClient.get('/api/apps_zoo/readme', { params: { repository: repo, folder_name: folder } }); return res.data; }
    
    async function fetchMcpZooRepositories() { isLoadingMcpZooRepositories.value = true; try { const res = await apiClient.get('/api/mcps_zoo/repositories'); mcpZooRepositories.value = res.data; } finally { isLoadingMcpZooRepositories.value = false; } }
    async function addMcpZooRepository(payload) { const res = await apiClient.post('/api/mcps_zoo/repositories', payload); mcpZooRepositories.value.push(res.data); }
    async function deleteMcpZooRepository(repoId) { await apiClient.delete(`/api/mcps_zoo/repositories/${repoId}`); mcpZooRepositories.value = mcpZooRepositories.value.filter(r => r.id !== repoId); }
    async function pullMcpZooRepository(repoId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/mcps_zoo/repositories/${repoId}/pull`); tasksStore.addTask(res.data); }
    async function pullAllMcpZooRepositories() { for (const repo of mcpZooRepositories.value) await pullMcpZooRepository(repo.id); }
    async function fetchZooMcps() {
        isLoadingZooMcps.value = true;
        const params = { page: mcpFilters.currentPage, page_size: mcpFilters.pageSize, sort_by: mcpFilters.sortKey, sort_order: mcpFilters.sortOrder, category: mcpFilters.selectedCategory !== 'All' ? mcpFilters.selectedCategory : undefined, repository: mcpFilters.selectedRepository !== 'All' ? mcpFilters.selectedRepository : undefined, search_query: mcpFilters.searchQuery || undefined, installation_status: mcpFilters.installationStatusFilter !== 'All' ? mcpFilters.installationStatusFilter : undefined };
        try {
            const [cat_res, items_res] = await Promise.all([ apiClient.get('/api/mcps_zoo/categories'), apiClient.get('/api/mcps_zoo/available', { params }) ]);
            zooMcps.value = { ...items_res.data, categories: cat_res.data };
        } finally {
            isLoadingZooMcps.value = false;
        }
    }
    async function installZooMcp(payload) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post('/api/mcps_zoo/install', payload); tasksStore.addTask(res.data); }
    async function fetchMcpReadme(repo, folder) { const res = await apiClient.get('/api/mcps_zoo/readme', { params: { repository: repo, folder_name: folder } }); return res.data; }
    
    async function fetchPromptZooRepositories() { isLoadingPromptZooRepositories.value = true; try { const res = await apiClient.get('/api/prompts_zoo/repositories'); promptZooRepositories.value = res.data; } finally { isLoadingPromptZooRepositories.value = false; } }
    async function addPromptZooRepository(repoData) { const res = await apiClient.post('/api/prompts_zoo/repositories', repoData); promptZooRepositories.value.push(res.data); }
    async function deletePromptZooRepository(repoId) { await apiClient.delete(`/api/prompts_zoo/repositories/${repoId}`); promptZooRepositories.value = promptZooRepositories.value.filter(r => r.id !== repoId); }
    async function pullPromptZooRepository(repoId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/prompts_zoo/repositories/${repoId}/pull`); tasksStore.addTask(res.data); }
    async function pullAllPromptZooRepositories() { for (const repo of promptZooRepositories.value) await pullPromptZooRepository(repo.id); }
    async function fetchZooPrompts(params = {}) { isLoadingZooPrompts.value = true; try { const [cat_res, items_res] = await Promise.all([apiClient.get('/api/prompts_zoo/categories'), apiClient.get('/api/prompts_zoo/available', { params })]); zooPrompts.value = { ...items_res.data, categories: cat_res.data }; } finally { isLoadingZooPrompts.value = false; } }
    async function installZooPrompt(payload) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post('/api/prompts_zoo/install', payload); tasksStore.addTask(res.data); }
    async function fetchPromptReadme(repo, folder) { const res = await apiClient.get('/api/prompts_zoo/readme', { params: { repository: repo, folder_name: folder } }); return res.data; }

    async function fetchPersonalityZooRepositories() { isLoadingPersonalityZooRepositories.value = true; try { const res = await apiClient.get('/api/personalities_zoo/repositories'); personalityZooRepositories.value = res.data; } catch(e){ console.error(e) } finally { isLoadingPersonalityZooRepositories.value = false; } }
    async function addPersonalityZooRepository(payload) { const res = await apiClient.post('/api/personalities_zoo/repositories', payload); personalityZooRepositories.value.push(res.data); }
    async function deletePersonalityZooRepository(repoId) { await apiClient.delete(`/api/personalities_zoo/repositories/${repoId}`); personalityZooRepositories.value = personalityZooRepositories.value.filter(r => r.id !== repoId); }
    async function pullPersonalityZooRepository(repoId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/personalities_zoo/repositories/${repoId}/pull`); tasksStore.addTask(res.data); }
    async function fetchZooPersonalities(params = {}) { isLoadingZooPersonalities.value = true; try { const [cat_res, items_res] = await Promise.all([apiClient.get('/api/personalities_zoo/categories'), apiClient.get('/api/personalities_zoo/available', { params })]); zooPersonalities.value = { ...items_res.data, categories: cat_res.data }; } catch(e){ console.error(e) } finally { isLoadingZooPersonalities.value = false; } }
    async function installZooPersonality(payload) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post('/api/personalities_zoo/install', payload); tasksStore.addTask(res.data); }
    async function fetchPersonalityReadme(repo, folder) { const res = await apiClient.get('/api/personalities_zoo/readme', { params: { repository: repo, folder_name: folder } }); return res.data; }

    async function createSystemPrompt(promptData) { const { usePromptsStore } = await import('./prompts.js'); const response = await apiClient.post('/api/prompts_zoo/installed', promptData); await usePromptsStore().fetchPrompts(); return response.data; }
    async function updateSystemPrompt(promptId, promptData) { const { usePromptsStore } = await import('./prompts.js'); await apiClient.put(`/api/prompts_zoo/installed/${promptId}`, promptData); await usePromptsStore().fetchPrompts(); }
    async function deleteSystemPrompt(promptId) { const { usePromptsStore } = await import('./prompts.js'); await apiClient.delete(`/api/prompts_zoo/installed/${promptId}`); await usePromptsStore().fetchPrompts(); await fetchZooPrompts(); }
    async function updateSystemPromptFromZoo(promptId) {
        const { useTasksStore } = await import('./tasks.js');
        const tasksStore = useTasksStore();
        const response = await apiClient.post(`/api/prompts_zoo/installed/${promptId}/update`);
        tasksStore.addTask(response.data);
    }
    async function generateSystemPrompt(prompt) {
        const { useTasksStore } = await import('./tasks.js');
        const tasksStore = useTasksStore();
        const res = await apiClient.post('/api/prompts_zoo/generate_from_prompt', { prompt });
        tasksStore.addTask(res.data);
        return res.data;
    }
    async function generateIconForModel(prompt) {
        const { useTasksStore } = await import('./tasks.js');
        const tasksStore = useTasksStore();
        const response = await apiClient.post('/api/personalities/generate_icon', { prompt });
        tasksStore.addTask(response.data);
        return response.data;
    }

    async function fetchInstalledApps() { isLoadingInstalledApps.value = true; try { const res = await apiClient.get('/api/apps_zoo/installed'); installedApps.value = res.data; } finally { isLoadingInstalledApps.value = false; } }
    async function fetchNextAvailablePort(port = null) { const params = port ? { port } : {}; const res = await apiClient.get('/api/apps_zoo/get-next-available-port', { params }); return res.data.port; }
    
    async function startApp(appId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/apps_zoo/installed/${appId}/start`); tasksStore.addTask(res.data); }
    async function stopApp(appId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/apps_zoo/installed/${appId}/stop`); tasksStore.addTask(res.data); }
    async function restartApp(appId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/apps_zoo/installed/${appId}/restart`); tasksStore.addTask(res.data); }
    async function updateApp(appId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/apps_zoo/installed/${appId}/update`); tasksStore.addTask(res.data); }
    async function uninstallApp(appId) { await apiClient.delete(`/api/apps_zoo/installed/${appId}`); await fetchZooApps(); await fetchZooMcps(); }
    async function updateInstalledApp(appId, payload) {
        const allItems = [...(zooApps.value.items || []), ...(zooMcps.value.items || [])];
        const item = allItems.find(i => i.id === appId);
        const oldAuthType = item ? item.authentication_type : 'none';

        await apiClient.put(`/api/apps_zoo/installed/${appId}`, payload);
        
        if (payload.authentication_type === 'lollms_sso' && oldAuthType !== 'lollms_sso') {
            uiStore.addNotification('SSO enabled for an app. A server reboot is required for this to take effect.', 'warning', 15000);
        }

        await fetchZooApps(); 
        await fetchZooMcps(); 
    }
    async function fetchAppLog(appId) { const res = await apiClient.get(`/api/apps_zoo/installed/${appId}/logs`); return res.data.log_content; }
    async function fetchAppConfigSchema(appId) { const res = await apiClient.get(`/api/apps_zoo/installed/${appId}/config-schema`); return res.data; }
    async function fetchAppConfig(appId) { const res = await apiClient.get(`/api/apps_zoo/installed/${appId}/config`); return res.data; }
    async function updateAppConfig(appId, configData) { await apiClient.put(`/api/apps_zoo/installed/${appId}/config`, configData); }
    async function fetchAppEnv(appId) { const res = await apiClient.get(`/api/apps_zoo/installed/${appId}/env`); return res.data; }
    async function updateAppEnv(appId, content) { await apiClient.put(`/api/apps_zoo/installed/${appId}/env`, { content }); uiStore.addNotification('.env file saved successfully.', 'success'); }
    async function deleteRegisteredApp(appId) { await apiClient.delete(`/api/apps/${appId}`); await fetchZooApps(); }
    async function deleteRegisteredMcp(mcpId) { await apiClient.delete(`/api/mcps/${mcpId}`); await fetchZooMcps(); }

    // --- Fun Fact Actions ---
    async function fetchFunFacts() { isLoadingFunFacts.value = true; try { const res = await apiClient.get('/api/admin/fun-facts'); funFacts.value = res.data; } finally { isLoadingFunFacts.value = false; } }
    async function fetchFunFactCategories() { isLoadingFunFactCategories.value = true; try { const res = await apiClient.get('/api/admin/fun-facts/categories'); funFactCategories.value = res.data; } finally { isLoadingFunFactCategories.value = false; } }
    async function createFunFact(payload) { await apiClient.post('/api/admin/fun-facts', payload); await fetchFunFacts(); }
    async function updateFunFact(id, payload) { await apiClient.put(`/api/admin/fun-facts/${id}`, payload); await fetchFunFacts(); }
    async function deleteFunFact(id) { await apiClient.delete(`/api/admin/fun-facts/${id}`); funFacts.value = funFacts.value.filter(f => f.id !== id); }
    async function createFunFactCategory(payload) { await apiClient.post('/api/admin/fun-facts/categories', payload); await fetchFunFactCategories(); }
    async function updateFunFactCategory(id, payload) { await apiClient.put(`/api/admin/fun-facts/categories/${id}`, payload); await fetchFunFactCategories(); }
    async function deleteFunFactCategory(id) { await apiClient.delete(`/api/admin/fun-facts/categories/${id}`); await Promise.all([fetchFunFactCategories(), fetchFunFacts()]); }
    async function exportFunFacts() { const response = await apiClient.get('/api/admin/fun-facts/export', { responseType: 'blob' }); const url = URL.createObjectURL(new Blob([response.data])); const a = document.createElement('a'); a.href = url; a.download = 'fun_facts_export.json'; a.click(); URL.revokeObjectURL(url); }
    async function exportCategory(categoryId, categoryName) { const response = await apiClient.get(`/api/admin/fun-facts/categories/${categoryId}/export`, { responseType: 'blob' }); const url = URL.createObjectURL(new Blob([response.data])); const a = document.createElement('a'); a.href = url; a.download = `fun_facts_${categoryName}.json`; a.click(); URL.revokeObjectURL(url); }
    async function importFunFacts(data) { const payload = { fun_facts: data }; const response = await apiClient.post('/api/admin/fun-facts/import', payload); await Promise.all([fetchFunFacts(), fetchFunFactCategories()]); uiStore.addNotification(`Imported ${response.data.facts_created} facts and ${response.data.categories_created} new categories.`, 'success'); }
    async function importCategoryFromFile(file) { const formData = new FormData(); formData.append('file', file); const response = await apiClient.post('/api/admin/fun-facts/categories/import', formData); await Promise.all([fetchFunFacts(), fetchFunFactCategories()]); uiStore.addNotification(`Imported ${response.data.facts_created} facts for category.`, 'success'); }
    
    // --- News Article Actions ---
    async function fetchNewsArticles() {
        isLoadingNewsArticles.value = true;
        try {
            const response = await apiClient.get('/api/admin/news-articles');
            newsArticles.value = response.data;
        } finally {
            isLoadingNewsArticles.value = false;
        }
    }
    async function updateNewsArticle(id, payload) {
        await apiClient.put(`/api/admin/news-articles/${id}`, payload);
        await fetchNewsArticles();
        uiStore.addNotification('Article updated.', 'success');
    }
    async function deleteBatchNewsArticles(ids) {
        await apiClient.post('/api/admin/news-articles/batch-delete', { article_ids: ids });
        await fetchNewsArticles();
        uiStore.addNotification(`${ids.length} article(s) deleted.`, 'success');
    }

    async function addOrUpdateRagAlias(payload) {
        const response = await apiClient.post('/api/admin/rag/aliases', payload);
        const setting = globalSettings.value.find(s => s.key === 'rag_vectorizer_aliases');
        if (setting) setting.value = response.data;
        uiStore.addNotification(`Alias '${payload.alias_name}' saved.`, 'success');
    }

    async function deleteRagAlias(aliasName) {
        const response = await apiClient.delete('/api/admin/rag/aliases', { data: { alias_name: aliasName } });
        const setting = globalSettings.value.find(s => s.key === 'rag_vectorizer_aliases');
        if (setting) setting.value = response.data;
        uiStore.addNotification(`Alias '${aliasName}' deleted.`, 'success');
    }

    async function fetchAvailableRagVectorizers() {
        try {
            const response = await apiClient.get('/api/admin/rag/available-vectorizers');
            availableRagVectorizers.value = response.data;
        } catch (error) {
            console.error("Failed to fetch available RAG vectorizers:", error);
            availableRagVectorizers.value = [];
        }
    }

    async function refreshZooCache() {
        const { useTasksStore } = await import('./tasks.js');
        const tasksStore = useTasksStore();
        try {
            const response = await apiClient.post('/api/admin/refresh-zoo-cache');
            const task = response.data;
            tasksStore.addTask(task);
            return task;
        } catch (error) {
            uiStore.addNotification('Failed to start Zoo cache refresh.', 'error');
            return null;
        }
    }

    async function triggerRssScraping() {
        const { useTasksStore } = await import('./tasks.js');
        const tasksStore = useTasksStore();
        try {
            const response = await apiClient.post('/api/admin/rss-feeds/scrape');
            const task = response.data;
            tasksStore.addTask(task);
            uiStore.openModal('tasksManager', { initialTaskId: task.id });
            return task;
        } catch (error) {
            uiStore.addNotification('Failed to start RSS scraping task.', 'error');
            return null;
        }
    }


    return {
        dashboardStats, isLoadingDashboardStats, fetchDashboardStats, broadcastMessage,
        allUsers, isLoadingUsers, fetchAllUsers, sendEmailToUsers, batchUpdateUsers,
        bindings, isLoadingBindings, availableBindingTypes, fetchBindings, fetchAvailableBindingTypes, addBinding, updateBinding, deleteBinding,
        fetchBindingModels, saveModelAlias, deleteModelAlias, getModelCtxSize,
        ttiBindings, isLoadingTtiBindings, availableTtiBindingTypes,
        fetchTtiBindings, fetchAvailableTtiBindingTypes, addTtiBinding, updateTtiBinding, deleteTtiBinding,
        fetchTtiBindingModels, saveTtiModelAlias, deleteTtiModelAlias,
        ttsBindings, isLoadingTtsBindings, availableTtsBindingTypes,
        fetchTtsBindings, fetchAvailableTtsBindingTypes, addTtsBinding, updateTtsBinding, deleteTtsBinding,
        fetchTtsBindingModels, saveTtsModelAlias, deleteTtsModelAlias,
        sttBindings, isLoadingSttBindings, availableSttBindingTypes,
        fetchSttBindings, fetchAvailableSttBindingTypes, addSttBinding, updateSttBinding, deleteSttBinding,
        fetchSttBindingModels, saveSttModelAlias, deleteSttModelAlias,
        ragBindings, isLoadingRagBindings, availableRagBindingTypes,
        fetchRagBindings, fetchAvailableRagBindingTypes, addRagBinding, updateRagBinding, deleteRagBinding,
        fetchRagBindingModels, saveRagModelAlias, deleteRagModelAlias, fetchRagModelsForType,
        globalSettings, isLoadingSettings, fetchGlobalSettings, updateGlobalSettings, uploadWelcomeLogo, removeWelcomeLogo,
        aiBotSettings, isLoadingAiBotSettings, fetchAiBotSettings, updateAiBotSettings, // NEW
        uploadSslFile,
        isImporting, importOpenWebUIData,
        adminAvailableLollmsModels, isLoadingLollmsModels, fetchAdminAvailableLollmsModels,
        isEnhancingEmail, enhanceEmail,
        zooRepositories, isLoadingZooRepositories, fetchZooRepositories, addZooRepository, deleteZooRepository, pullZooRepository, pullAllZooRepositories,
        zooApps, isLoadingZooApps, fetchZooApps, installZooApp, fetchAppReadme, appFilters,
        mcpZooRepositories, isLoadingMcpZooRepositories, fetchMcpZooRepositories, addMcpZooRepository, deleteMcpZooRepository, pullMcpZooRepository, pullAllMcpZooRepositories,
        zooMcps, isLoadingZooMcps, fetchZooMcps, fetchMcpReadme, installZooMcp, mcpFilters,
        promptZooRepositories, isLoadingPromptZooRepositories, fetchPromptZooRepositories, addPromptZooRepository, deletePromptZooRepository, pullPromptZooRepository, pullAllPromptZooRepositories,
        zooPrompts, isLoadingZooPrompts, fetchZooPrompts, installZooPrompt, fetchPromptReadme, promptFilters,
        personalityZooRepositories, isLoadingPersonalityZooRepositories, fetchPersonalityZooRepositories, addPersonalityZooRepository, deletePersonalityZooRepository, pullPersonalityZooRepository,
        zooPersonalities, isLoadingZooPersonalities, fetchZooPersonalities, installZooPersonality, fetchPersonalityReadme,
        createSystemPrompt, updateSystemPrompt, deleteSystemPrompt, generateSystemPrompt, updateSystemPromptFromZoo,
        installedApps, isLoadingInstalledApps, fetchInstalledApps, fetchNextAvailablePort,
        startApp, stopApp, uninstallApp, updateInstalledApp, fetchAppLog, fetchAppConfigSchema, fetchAppConfig, updateAppConfig, updateApp,
        fetchAppEnv, updateAppEnv,
        purgeUnusedUploads, systemStatus, isLoadingSystemStatus, fetchSystemStatus,
        syncInstallations, purgeBrokenInstallation, fixBrokenInstallation, handleTaskCompletion,
        handleAppStatusUpdate, deleteRegisteredApp, deleteRegisteredMcp,
        funFacts, isLoadingFunFacts, funFactCategories, isLoadingFunFactCategories,
        fetchFunFacts, fetchFunFactCategories, createFunFact, updateFunFact, deleteFunFact,
        createFunFactCategory, updateFunFactCategory, deleteFunFactCategory, exportFunFacts, importFunFacts,
        exportCategory, importCategoryFromFile,
        newsArticles, isLoadingNewsArticles, fetchNewsArticles, updateNewsArticle, deleteBatchNewsArticles,
        connectedUsers, isLoadingConnectedUsers, fetchConnectedUsers,
        serverInfo, isLoadingServerInfo, fetchServerInfo,
        globalGenerationStats, isLoadingGlobalGenerationStats, fetchGlobalGenerationStats,
        generateIconForModel,
        startApp,
        stopApp,
        restartApp,
        fetchAppLog,
        fetchUserStats,
        addOrUpdateRagAlias,
        deleteRagAlias,
        availableRagVectorizers,
        fetchAvailableRagVectorizers,
        refreshZooCache,
        triggerRssScraping
    };
});