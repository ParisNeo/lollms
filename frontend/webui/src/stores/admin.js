// frontend/webui/src/stores/admin.js
// ... (imports remain same)
import { defineStore } from 'pinia';
import { ref, reactive, watch, onMounted } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useTasksStore } from './tasks'; 
import useEventBus from '../services/eventBus';

// ... (helpers)
function getStoredFilters(key, defaults) {
    try {
        const stored = localStorage.getItem(key);
        if (stored) {
            const parsed = JSON.parse(stored);
            return { ...defaults, ...parsed };
        }
    } catch (e) {
        localStorage.removeItem(key); 
    }
    return defaults;
}

const castSettingValue = (value, type) => {
    if (type === 'boolean') {
        if (typeof value === 'string') return value.toLowerCase() === 'true';
        return !!value;
    }
    if (type === 'integer') {
        const intVal = parseInt(value, 10);
        return isNaN(intVal) ? null : intVal;
    }
    if (type === 'float') {
        const floatVal = parseFloat(value);
        return isNaN(floatVal) ? null : floatVal;
    }
    return value;
};

export const useAdminStore = defineStore('admin', () => {
    // ... (state)
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();
    const { on } = useEventBus();

    // Dashboard & Users
    const dashboardStats = ref(null);
    const isLoadingDashboardStats = ref(false);
    const allUsers = ref([]);
    const isLoadingUsers = ref(false);
    
    // Global Settings
    const globalSettings = ref([]);
    const isLoadingSettings = ref(false);
    const aiBotSettings = ref(null);
    const isLoadingAiBotSettings = ref(false);
    
    // Bindings
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
    const availableRagVectorizers = ref([]);

    // Zoos
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

    // System & Content
    const systemStatus = ref(null);
    const isLoadingSystemStatus = ref(false);
    const connectedUsers = ref([]);
    const isLoadingConnectedUsers = ref(false);
    const serverInfo = ref(null);
    const isLoadingServerInfo = ref(false);
    const globalGenerationStats = ref(null);
    const isLoadingGlobalGenerationStats = ref(false);
    const modelUsageStats = ref([]);
    const isLoadingModelUsageStats = ref(false);
    const funFacts = ref([]);
    const isLoadingFunFacts = ref(false);
    const funFactCategories = ref([]);
    const isLoadingFunFactCategories = ref(false);
    const newsArticles = ref([]);
    const isLoadingNewsArticles = ref(false);
    const isImporting = ref(false);
    const isEnhancingEmail = ref(false);
    const adminAvailableLollmsModels = ref([]);
    const isLoadingLollmsModels = ref(false);
    const systemLogs = ref([]);
    const isLoadingSystemLogs = ref(false);

    const appFilters = reactive(getStoredFilters('lollms-app-filters', {
        searchQuery: '', selectedCategory: 'All', installationStatusFilter: 'All', selectedRepository: 'All', sortKey: 'last_update_date', sortOrder: 'desc', currentPage: 1, pageSize: 24
    }));
    const mcpFilters = reactive(getStoredFilters('lollms-mcp-filters', {
        searchQuery: '', selectedCategory: 'All', installationStatusFilter: 'All', selectedRepository: 'All', sortKey: 'last_update_date', sortOrder: 'desc', currentPage: 1, pageSize: 24
    }));
    const promptFilters = reactive(getStoredFilters('lollms-prompt-filters', {
        searchQuery: '', selectedCategory: 'All', installationStatusFilter: 'All', selectedRepository: 'All', sortKey: 'name', sortOrder: 'asc', currentPage: 1, pageSize: 24
    }));

    // ... (watchers)
    watch(appFilters, (newFilters) => { localStorage.setItem('lollms-app-filters', JSON.stringify(newFilters)); }, { deep: true });
    watch(mcpFilters, (newFilters) => { localStorage.setItem('lollms-mcp-filters', JSON.stringify(newFilters)); }, { deep: true });
    watch(promptFilters, (newFilters) => { localStorage.setItem('lollms-prompt-filters', JSON.stringify(newFilters)); }, { deep: true });


    async function handleTaskCompletion(task) {
        if (!task || !['completed', 'failed', 'cancelled'].includes(task.status)) return;
        const taskName = (task.name || '').toLowerCase();
        
        if (taskName.includes('app') || taskName.includes('mcp')) {
            fetchZooApps(); fetchZooMcps();
        }
        if (taskName.includes('prompt')) { fetchZooPrompts(); }
        if (taskName.includes('personality')) { fetchZooPersonalities(); }

        if (taskName.includes('purge unused temporary files') && task.status === 'completed') {
            const message = task.result?.message || 'Purge completed successfully.';
            uiStore.addNotification(message, 'success', 6000);
        }

        if (taskName.includes('generate self-signed certificate') && task.status === 'completed') {
            fetchGlobalSettings();
            uiStore.addNotification('Certificate generated successfully. Reloading settings...', 'success', 6000);
        }
        
        if (taskName.includes('content') && task.status === 'completed') {
            uiStore.addNotification('Moderation task completed.', 'success', 6000);
        }
    }
    on('task:completed', handleTaskCompletion);

    function handleAppStatusUpdate(appData) {
        const updateItemInList = (list) => {
            if (Array.isArray(list)) {
                const index = list.findIndex(item => item.id === appData.id);
                if (index !== -1) Object.assign(list[index], appData);
            }
        };
        if (appData.item_type === 'app') updateItemInList(zooApps.value.items);
        else if (appData.item_type === 'mcp') updateItemInList(zooMcps.value.items);
    }

    // --- Actions ---
    // (Existing actions omitted for brevity but must be present)
    async function fetchDashboardStats() { isLoadingDashboardStats.value = true; try { const response = await apiClient.get('/api/admin/stats'); dashboardStats.value = response.data; } catch { dashboardStats.value = null; } finally { isLoadingDashboardStats.value = false; } }
    async function fetchConnectedUsers() { isLoadingConnectedUsers.value = true; try { const response = await apiClient.get('/api/admin/ws-connections'); connectedUsers.value = response.data; } catch { connectedUsers.value = []; } finally { isLoadingConnectedUsers.value = false; } }
    async function broadcastMessage(message) { await apiClient.post('/api/admin/broadcast', { message }); }
    async function createBackup(password) { const response = await apiClient.post('/api/admin/backup/create', { password }); tasksStore.addTask(response.data); return response.data; }
    async function analyzeSystemLogs() { try { const response = await apiClient.post('/api/admin/system/analyze-logs'); tasksStore.addTask(response.data); return response.data; } catch (error) { uiStore.addNotification('Failed to start log analysis.', 'error'); throw error; } }
    async function fetchSystemStatus() { isLoadingSystemStatus.value = true; try { const response = await apiClient.get('/api/admin/system-status'); systemStatus.value = response.data; } finally { isLoadingSystemStatus.value = false; } }
    async function fetchSystemLogs() { isLoadingSystemLogs.value = true; try { const response = await apiClient.get('/api/admin/system/logs'); systemLogs.value = response.data; } catch (error) { uiStore.addNotification('Failed to fetch system logs.', 'error'); } finally { isLoadingSystemLogs.value = false; } }
    async function killProcess(pid) { await apiClient.post('/api/admin/system/kill-process', { pid }); uiStore.addNotification(`Process ${pid} killed.`, 'success'); fetchSystemStatus(); }
    async function fetchModelUsageStats() { isLoadingModelUsageStats.value = true; try { const response = await apiClient.get('/api/admin/model-usage-stats'); modelUsageStats.value = response.data || []; } catch (error) { console.error("Failed to fetch model usage stats:", error); modelUsageStats.value = []; } finally { isLoadingModelUsageStats.value = false; } }
    async function fetchServerInfo() { isLoadingServerInfo.value = true; try { const response = await apiClient.get('/api/admin/server-info'); serverInfo.value = response.data; } finally { isLoadingServerInfo.value = false; } }
    async function purgeUnusedUploads() { const response = await apiClient.post('/api/admin/purge-unused-uploads'); tasksStore.addTask(response.data); }

    async function triggerBatchModeration() {
        const response = await apiClient.post('/api/admin/trigger-moderation');
        tasksStore.addTask(response.data);
    }
    
    async function triggerFullRemoderation() {
        const response = await apiClient.post('/api/admin/trigger-full-remoderation');
        tasksStore.addTask(response.data);
    }

    // ... (rest of existing actions)
    async function fetchGlobalGenerationStats() { isLoadingGlobalGenerationStats.value = true; try { const response = await apiClient.get('/api/admin/global-generation-stats'); globalGenerationStats.value = response.data; } catch (error) { globalGenerationStats.value = null; } finally { isLoadingGlobalGenerationStats.value = false; } }
    async function triggerRssScraping() { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); try { const response = await apiClient.post('/api/admin/rss-feeds/scrape'); const task = response.data; tasksStore.addTask(task); return task; } catch (error) { uiStore.addNotification('Failed to start RSS scraping task.', 'error'); return null; } }
    async function refreshZooCache() { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); try { const response = await apiClient.post('/api/admin/refresh-zoo-cache'); const task = response.data; tasksStore.addTask(task); return task; } catch (error) { uiStore.addNotification('Failed to start Zoo cache refresh.', 'error'); return null; } }
    async function fetchAllUsers(filters = {}) { isLoadingUsers.value = true; try { const response = await apiClient.get('/api/admin/users', { params: filters }); allUsers.value = response.data; } finally { isLoadingUsers.value = false; } }
    async function activateUser(userId) { await apiClient.post(`/api/admin/users/${userId}/activate`); uiStore.addNotification('User activated.', 'success'); fetchAllUsers(); }
    async function fetchUserStats(userId) { try { const response = await apiClient.get(`/api/admin/users/${userId}/stats`); return response.data; } catch (error) { return null; } }    
    async function batchUpdateUsers(payload) { await apiClient.post('/api/admin/users/batch-update-settings', payload); await fetchAllUsers(); }
    async function sendEmailToUsers(subject, body, user_ids, backgroundColor, sendAsText) { const r = await apiClient.post('/api/admin/email-users', { subject, body, user_ids, background_color: backgroundColor, send_as_text: sendAsText }); tasksStore.addTask(r.data); return true; }
    async function enhanceEmail(subject, body, backgroundColor, prompt) { isEnhancingEmail.value = true; try { const response = await apiClient.post('/api/admin/enhance-email', { subject, body, background_color: backgroundColor, prompt }); return response.data; } finally { isEnhancingEmail.value = false; } }

    async function fetchGlobalSettings() { isLoadingSettings.value = true; try { const response = await apiClient.get('/api/admin/settings'); globalSettings.value = response.data.map(s => ({ ...s, value: castSettingValue(s.value, s.type) })); } finally { isLoadingSettings.value = false; } }
    async function updateGlobalSettings(configs) { await apiClient.put('/api/admin/settings', { configs }); fetchGlobalSettings(); uiStore.addNotification('Settings updated.', 'success'); }
    async function fetchAiBotSettings() { isLoadingAiBotSettings.value = true; try { const response = await apiClient.get('/api/admin/ai-bot-settings'); aiBotSettings.value = response.data; } finally { isLoadingAiBotSettings.value = false; } }
    async function updateAiBotSettings(settings) { const response = await apiClient.put('/api/admin/ai-bot-settings', settings); aiBotSettings.value = response.data; uiStore.addNotification('AI Bot user settings updated.', 'success'); }
    async function uploadWelcomeLogo(file) { const formData = new FormData(); formData.append('file', file); const response = await apiClient.post('/api/admin/upload-logo', formData); await fetchGlobalSettings(); uiStore.addNotification(response.data.message, 'success'); }
    async function removeWelcomeLogo() { await apiClient.delete('/api/admin/remove-logo'); await fetchGlobalSettings(); uiStore.addNotification('Custom logo removed.', 'success'); }
    async function uploadSslFile(file, fileType) { const formData = new FormData(); formData.append('file', file); formData.append('file_type', fileType); const response = await apiClient.post('/api/admin/upload-ssl-file', formData, { headers: { 'Content-Type': 'multipart/form-data' }, }); await fetchGlobalSettings(); return response.data.path; }
    async function generateSelfSignedCert() { try { const response = await apiClient.post('/api/admin/generate-cert'); tasksStore.addTask(response.data); uiStore.addNotification('Certificate generation task started. Check tasks for progress.', 'info'); return response.data; } catch(e) { const msg = e.response?.data?.detail || 'Failed to start certificate task.'; uiStore.addNotification(msg, 'error'); throw e; } }
    async function downloadCertificate() { try { const response = await apiClient.get('/api/admin/download-cert', { responseType: 'blob' }); const url = window.URL.createObjectURL(new Blob([response.data])); const link = document.createElement('a'); link.href = url; link.setAttribute('download', 'lollms_cert.pem'); document.body.appendChild(link); link.click(); link.remove(); } catch(e) { uiStore.addNotification('Failed to download certificate.', 'error'); } }
    async function downloadTrustScript(type) { try { const response = await apiClient.get('/api/admin/download-trust-script', { params: { script_type: type }, responseType: 'blob' }); const url = window.URL.createObjectURL(new Blob([response.data])); const link = document.createElement('a'); link.href = url; const ext = type === 'windows' ? 'bat' : 'sh'; link.setAttribute('download', `install_lollms_cert.${ext}`); document.body.appendChild(link); link.click(); link.remove(); } catch(e) { console.error(e); uiStore.addNotification('Failed to download trust script.', 'error'); } }
    async function importOpenWebUIData(file) { isImporting.value = true; const formData = new FormData(); formData.append('file', file); try { await apiClient.post('/api/admin/import-openwebui', formData); } finally { isImporting.value = false; } }
    async function fetchAdminAvailableLollmsModels() { if (adminAvailableLollmsModels.value.length > 0) return; isLoadingLollmsModels.value = true; try { const response = await apiClient.get('/api/admin/available-models'); adminAvailableLollmsModels.value = response.data; } finally { isLoadingLollmsModels.value = false; } }
    async function generateIconForModel(prompt) { const response = await apiClient.post('/api/admin/bindings/generate_icon', { prompt }); tasksStore.addTask(response.data); return response.data; }
    
    // Bindings & Zoos Actions (omitted for brevity, assume present)
    async function fetchBindings() { isLoadingBindings.value = true; try { const r = await apiClient.get('/api/admin/bindings'); bindings.value = r.data; } finally { isLoadingBindings.value = false; } }
    async function fetchAvailableBindingTypes() { const r = await apiClient.get('/api/admin/bindings/available_types'); availableBindingTypes.value = r.data; }
    async function addBinding(payload) { const r = await apiClient.post('/api/admin/bindings', payload); bindings.value.push(r.data); uiStore.addNotification(`Binding '${r.data.alias}' created.`, 'success'); }
    async function updateBinding(id, payload) { const r = await apiClient.put(`/api/admin/bindings/${id}`, payload); const i = bindings.value.findIndex(b => b.id === id); if (i !== -1) bindings.value[i] = r.data; uiStore.addNotification(`Binding '${r.data.alias}' updated.`, 'success'); }
    async function deleteBinding(id) { await apiClient.delete(`/api/admin/bindings/${id}`); bindings.value = bindings.value.filter(b => b.id !== id); uiStore.addNotification('Binding deleted.', 'success'); }
    async function fetchBindingModels(id) { const r = await apiClient.get(`/api/admin/bindings/${id}/models`); return r.data; }
    async function getModelCtxSize(id, name) { const r = await apiClient.post(`/api/admin/bindings/${id}/context-size`, { model_name: name }); return r.data.ctx_size; }
    async function saveModelAlias(id, payload) { const r = await apiClient.put(`/api/admin/bindings/${id}/alias`, payload); const i = bindings.value.findIndex(b => b.id === id); if (i !== -1) bindings.value[i] = r.data; }
    async function deleteModelAlias(id, name) { const r = await apiClient.delete(`/api/admin/bindings/${id}/alias`, { data: { original_model_name: name } }); const i = bindings.value.findIndex(b => b.id === id); if (i !== -1) bindings.value[i] = r.data; }
    async function executeBindingCommand(id, cmd, params = {}) { const r = await apiClient.post(`/api/admin/bindings/${id}/execute_command`, { command_name: cmd, parameters: params }); return r.data; }
    
    // ... (rest of TTI/TTS/STT/RAG/Zoos actions)
    // For brevity I am just ensuring the new actions are returned
    async function fetchTtiBindings() { isLoadingTtiBindings.value = true; try { const r = await apiClient.get('/api/admin/tti-bindings'); ttiBindings.value = r.data; } finally { isLoadingTtiBindings.value = false; } }
    async function fetchAvailableTtiBindingTypes() { const r = await apiClient.get('/api/admin/tti-bindings/available_types'); availableTtiBindingTypes.value = r.data; }
    async function addTtiBinding(payload) { const r = await apiClient.post('/api/admin/tti-bindings', payload); ttiBindings.value.push(r.data); uiStore.addNotification(`TTI Binding '${r.data.alias}' created.`, 'success'); }
    async function updateTtiBinding(id, payload) { const r = await apiClient.put(`/api/admin/tti-bindings/${id}`, payload); const i = ttiBindings.value.findIndex(b => b.id === id); if (i !== -1) ttiBindings.value[i] = r.data; uiStore.addNotification(`TTI Binding '${r.data.alias}' updated.`, 'success'); }
    async function deleteTtiBinding(id) { await apiClient.delete(`/api/admin/tti-bindings/${id}`); ttiBindings.value = ttiBindings.value.filter(b => b.id !== id); uiStore.addNotification('TTI Binding deleted.', 'success'); }
    async function fetchTtiBindingModels(id) { const r = await apiClient.get(`/api/admin/tti-bindings/${id}/models`); return r.data; }
    async function saveTtiModelAlias(id, payload) { const r = await apiClient.put(`/api/admin/tti-bindings/${id}/alias`, payload); const i = ttiBindings.value.findIndex(b => b.id === id); if (i !== -1) ttiBindings.value[i] = r.data; }
    async function deleteTtiModelAlias(id, name) { const r = await apiClient.delete(`/api/admin/tti-bindings/${id}/alias`, { data: { original_model_name: name } }); const i = ttiBindings.value.findIndex(b => b.id === id); if (i !== -1) ttiBindings.value[i] = r.data; }
    async function executeTtiBindingCommand(id, cmd, params = {}) { const r = await apiClient.post(`/api/admin/tti-bindings/${id}/execute_command`, { command_name: cmd, parameters: params }); return r.data; }

    async function fetchTtsBindings() { isLoadingTtsBindings.value = true; try { const r = await apiClient.get('/api/admin/tts-bindings'); ttsBindings.value = r.data; } finally { isLoadingTtsBindings.value = false; } }
    async function fetchAvailableTtsBindingTypes() { const r = await apiClient.get('/api/admin/tts-bindings/available_types'); availableTtsBindingTypes.value = r.data; }
    async function addTtsBinding(payload) { const r = await apiClient.post('/api/admin/tts-bindings', payload); ttsBindings.value.push(r.data); uiStore.addNotification(`TTS Binding '${r.data.alias}' created.`, 'success'); }
    async function updateTtsBinding(id, payload) { const r = await apiClient.put(`/api/admin/tts-bindings/${id}`, payload); const i = ttsBindings.value.findIndex(b => b.id === id); if (i !== -1) ttsBindings.value[i] = r.data; uiStore.addNotification(`TTS Binding '${r.data.alias}' updated.`, 'success'); }
    async function deleteTtsBinding(id) { await apiClient.delete(`/api/admin/tts-bindings/${id}`); ttsBindings.value = ttsBindings.value.filter(b => b.id !== id); uiStore.addNotification('TTS Binding deleted.', 'success'); }
    async function fetchTtsBindingModels(id) { const r = await apiClient.get(`/api/admin/tts-bindings/${id}/models`); return r.data; }
    async function saveTtsModelAlias(id, payload) { const r = await apiClient.put(`/api/admin/tts-bindings/${id}/alias`, payload); const i = ttsBindings.value.findIndex(b => b.id === id); if (i !== -1) ttsBindings.value[i] = r.data; }
    async function deleteTtsModelAlias(id, name) { const r = await apiClient.delete(`/api/admin/tts-bindings/${id}/alias`, { data: { original_model_name: name } }); const i = ttsBindings.value.findIndex(b => b.id === id); if (i !== -1) ttsBindings.value[i] = r.data; }
    async function executeTtsBindingCommand(id, cmd, params = {}) { const r = await apiClient.post(`/api/admin/tts-bindings/${id}/execute_command`, { command_name: cmd, parameters: params }); return r.data; }

    async function fetchSttBindings() { isLoadingSttBindings.value = true; try { const r = await apiClient.get('/api/admin/stt-bindings'); sttBindings.value = r.data; } finally { isLoadingSttBindings.value = false; } }
    async function fetchAvailableSttBindingTypes() { const r = await apiClient.get('/api/admin/stt-bindings/available_types'); availableSttBindingTypes.value = r.data; }
    async function addSttBinding(payload) { const r = await apiClient.post('/api/admin/stt-bindings', payload); sttBindings.value.push(r.data); uiStore.addNotification(`STT Binding '${r.data.alias}' created.`, 'success'); }
    async function updateSttBinding(id, payload) { const r = await apiClient.put(`/api/admin/stt-bindings/${id}`, payload); const i = sttBindings.value.findIndex(b => b.id === id); if (i !== -1) sttBindings.value[i] = r.data; uiStore.addNotification(`STT Binding '${r.data.alias}' updated.`, 'success'); }
    async function deleteSttBinding(id) { await apiClient.delete(`/api/admin/stt-bindings/${id}`); sttBindings.value = sttBindings.value.filter(b => b.id !== id); uiStore.addNotification('STT Binding deleted.', 'success'); }
    async function fetchSttBindingModels(id) { const r = await apiClient.get(`/api/admin/stt-bindings/${id}/models`); return r.data; }
    async function saveSttModelAlias(id, payload) { const r = await apiClient.put(`/api/admin/stt-bindings/${id}/alias`, payload); const i = sttBindings.value.findIndex(b => b.id === id); if (i !== -1) sttBindings.value[i] = r.data; }
    async function deleteSttModelAlias(id, name) { const r = await apiClient.delete(`/api/admin/stt-bindings/${id}/alias`, { data: { original_model_name: name } }); const i = sttBindings.value.findIndex(b => b.id === id); if (i !== -1) sttBindings.value[i] = r.data; }
    async function executeSttBindingCommand(id, cmd, params = {}) { const r = await apiClient.post(`/api/admin/stt-bindings/${id}/execute_command`, { command_name: cmd, parameters: params }); return r.data; }

    async function fetchRagBindings() { isLoadingRagBindings.value = true; try { const r = await apiClient.get('/api/admin/rag-bindings'); ragBindings.value = r.data; } catch(e) { console.error(e); } finally { isLoadingRagBindings.value = false; } }
    async function fetchAvailableRagBindingTypes() { try { const r = await apiClient.get('/api/admin/rag-bindings/available_types'); availableRagBindingTypes.value = r.data; } catch(e) { console.error(e); } }
    async function addRagBinding(payload) { const r = await apiClient.post('/api/admin/rag-bindings', payload); ragBindings.value.push(r.data); uiStore.addNotification(`RAG Binding '${r.data.alias}' created.`, 'success'); }
    async function updateRagBinding(id, payload) { const r = await apiClient.put(`/api/admin/rag-bindings/${id}`, payload); const i = ragBindings.value.findIndex(b => b.id === id); if (i !== -1) ragBindings.value[i] = r.data; uiStore.addNotification(`RAG Binding '${r.data.alias}' updated.`, 'success'); }
    async function deleteRagBinding(id) { await apiClient.delete(`/api/admin/rag-bindings/${id}`); ragBindings.value = ragBindings.value.filter(b => b.id !== id); uiStore.addNotification('RAG Binding deleted.', 'success'); }
    async function fetchRagBindingModels(id) { const r = await apiClient.get(`/api/admin/rag-bindings/${id}/models`); return r.data; }
    async function saveRagModelAlias(id, payload) { const r = await apiClient.put(`/api/admin/rag-bindings/${id}/alias`, payload); const i = ragBindings.value.findIndex(b => b.id === id); if (i !== -1) ragBindings.value[i] = r.data; }
    async function deleteRagModelAlias(id, name) { const r = await apiClient.delete(`/api/admin/rag-bindings/${id}/alias`, { data: { original_model_name: name } }); const i = ragBindings.value.findIndex(b => b.id === id); if (i !== -1) ragBindings.value[i] = r.data; }
    async function fetchRagModelsForType(type) { const r = await apiClient.get(`/api/admin/rag-bindings/models-for-type/${type}`); return r.data; }
    async function addOrUpdateRagAlias(payload) { const r = await apiClient.post('/api/admin/rag/aliases', payload); const s = globalSettings.value.find(s => s.key === 'rag_vectorizer_aliases'); if (s) s.value = r.data; uiStore.addNotification(`Alias '${payload.alias_name}' saved.`, 'success'); }
    async function deleteRagAlias(name) { const r = await apiClient.delete('/api/admin/rag/aliases', { data: { alias_name: name } }); const s = globalSettings.value.find(s => s.key === 'rag_vectorizer_aliases'); if (s) s.value = r.data; uiStore.addNotification(`Alias '${name}' deleted.`, 'success'); }
    async function fetchAvailableRagVectorizers() { try { const r = await apiClient.get('/api/admin/rag/available-vectorizers'); availableRagVectorizers.value = r.data; } catch(e) { console.error(e); } }

    async function fetchZooRepositories() { isLoadingZooRepositories.value = true; try { const res = await apiClient.get('/api/apps_zoo/repositories'); zooRepositories.value = res.data; } finally { isLoadingZooRepositories.value = false; } }
    async function addZooRepository(payload) { const res = await apiClient.post('/api/apps_zoo/repositories', payload); zooRepositories.value.push(res.data); }
    async function deleteZooRepository(repoId) { await apiClient.delete(`/api/apps_zoo/repositories/${repoId}`); zooRepositories.value = zooRepositories.value.filter(r => r.id !== repoId); }
    async function pullZooRepository(repoId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/apps_zoo/repositories/${repoId}/pull`); tasksStore.addTask(res.data); }
    async function pullAllZooRepositories() { for (const repo of zooRepositories.value) await pullZooRepository(repo.id); }

    async function fetchMcpZooRepositories() { isLoadingMcpZooRepositories.value = true; try { const res = await apiClient.get('/api/mcps_zoo/repositories'); mcpZooRepositories.value = res.data; } finally { isLoadingMcpZooRepositories.value = false; } }
    async function addMcpZooRepository(payload) { const res = await apiClient.post('/api/mcps_zoo/repositories', payload); mcpZooRepositories.value.push(res.data); }
    async function deleteMcpZooRepository(repoId) { await apiClient.delete(`/api/mcps_zoo/repositories/${repoId}`); mcpZooRepositories.value = mcpZooRepositories.value.filter(r => r.id !== repoId); }
    async function pullMcpZooRepository(repoId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/mcps_zoo/repositories/${repoId}/pull`); tasksStore.addTask(res.data); }
    async function pullAllMcpZooRepositories() { for (const repo of mcpZooRepositories.value) await pullMcpZooRepository(repo.id); }

    async function fetchPromptZooRepositories() { isLoadingPromptZooRepositories.value = true; try { const res = await apiClient.get('/api/prompts_zoo/repositories'); promptZooRepositories.value = res.data; } finally { isLoadingPromptZooRepositories.value = false; } }
    async function addPromptZooRepository(repoData) { const res = await apiClient.post('/api/prompts_zoo/repositories', repoData); promptZooRepositories.value.push(res.data); }
    async function deletePromptZooRepository(repoId) { await apiClient.delete(`/api/prompts_zoo/repositories/${repoId}`); promptZooRepositories.value = promptZooRepositories.value.filter(r => r.id !== repoId); }
    async function pullPromptZooRepository(repoId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/prompts_zoo/repositories/${repoId}/pull`); tasksStore.addTask(res.data); }
    async function pullAllPromptZooRepositories() { for (const repo of promptZooRepositories.value) await pullPromptZooRepository(repo.id); }

    async function fetchPersonalityZooRepositories() { isLoadingPersonalityZooRepositories.value = true; try { const res = await apiClient.get('/api/personalities_zoo/repositories'); personalityZooRepositories.value = res.data; } catch(e){ console.error(e) } finally { isLoadingPersonalityZooRepositories.value = false; } }
    async function addPersonalityZooRepository(payload) { const res = await apiClient.post('/api/personalities_zoo/repositories', payload); personalityZooRepositories.value.push(res.data); }
    async function deletePersonalityZooRepository(repoId) { await apiClient.delete(`/api/personalities_zoo/repositories/${repoId}`); personalityZooRepositories.value = personalityZooRepositories.value.filter(r => r.id !== repoId); }
    async function pullPersonalityZooRepository(repoId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/personalities_zoo/repositories/${repoId}/pull`); tasksStore.addTask(res.data); }

    async function fetchZooApps() { isLoadingZooApps.value = true; try { const [cat_res, items_res] = await Promise.all([ apiClient.get('/api/apps_zoo/categories'), apiClient.get('/api/apps_zoo/available') ]); zooApps.value = { ...items_res.data, categories: cat_res.data }; } finally { isLoadingZooApps.value = false; } }
    async function installZooApp(payload) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post('/api/apps_zoo/install', payload); tasksStore.addTask(res.data); }
    async function fetchAppReadme(repo, folder) { const res = await apiClient.get('/api/apps_zoo/readme', { params: { repository: repo, folder_name: folder } }); return res.data; }

    async function fetchZooMcps() { isLoadingZooMcps.value = true; try { const [cat_res, items_res] = await Promise.all([ apiClient.get('/api/mcps_zoo/categories'), apiClient.get('/api/mcps_zoo/available') ]); zooMcps.value = { ...items_res.data, categories: cat_res.data }; } finally { isLoadingZooMcps.value = false; } }
    async function installZooMcp(payload) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post('/api/mcps_zoo/install', payload); tasksStore.addTask(res.data); }
    async function fetchMcpReadme(repo, folder) { const res = await apiClient.get('/api/mcps_zoo/readme', { params: { repository: repo, folder_name: folder } }); return res.data; }

    async function fetchZooPrompts(params = {}) { isLoadingZooPrompts.value = true; try { const [cat_res, items_res] = await Promise.all([apiClient.get('/api/prompts_zoo/categories'), apiClient.get('/api/prompts_zoo/available', { params })]); zooPrompts.value = { ...items_res.data, categories: cat_res.data }; } finally { isLoadingZooPrompts.value = false; } }
    async function installZooPrompt(payload) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post('/api/prompts_zoo/install', payload); tasksStore.addTask(res.data); }
    async function fetchPromptReadme(repo, folder) { const res = await apiClient.get('/api/prompts_zoo/readme', { params: { repository: repo, folder_name: folder } }); return res.data; }

    async function fetchZooPersonalities(params = {}) { isLoadingZooPersonalities.value = true; try { const [cat_res, items_res] = await Promise.all([apiClient.get('/api/personalities_zoo/categories'), apiClient.get('/api/personalities_zoo/available', { params })]); zooPersonalities.value = { ...items_res.data, categories: cat_res.data }; } catch(e){ console.error(e) } finally { isLoadingZooPersonalities.value = false; } }
    async function installZooPersonality(payload) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post('/api/personalities_zoo/install', payload); tasksStore.addTask(res.data); }
    async function fetchPersonalityReadme(repo, folder) { const res = await apiClient.get('/api/personalities_zoo/readme', { params: { repository: repo, folder_name: folder } }); return res.data; }

    async function createSystemPrompt(promptData) { const { usePromptsStore } = await import('./prompts.js'); const response = await apiClient.post('/api/prompts_zoo/installed', promptData); await usePromptsStore().fetchPrompts(); return response.data; }
    async function updateSystemPrompt(promptId, promptData) { const { usePromptsStore } = await import('./prompts.js'); await apiClient.put(`/api/prompts_zoo/installed/${promptId}`, promptData); await usePromptsStore().fetchPrompts(); }
    async function deleteSystemPrompt(promptId) { const { usePromptsStore } = await import('./prompts.js'); await apiClient.delete(`/api/prompts_zoo/installed/${promptId}`); await usePromptsStore().fetchPrompts(); await fetchZooPrompts(); }
    async function updateSystemPromptFromZoo(promptId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const response = await apiClient.post(`/api/prompts_zoo/installed/${promptId}/update`); tasksStore.addTask(response.data); }
    async function generateSystemPrompt(prompt) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post('/api/prompts_zoo/generate_from_prompt', { prompt }); tasksStore.addTask(res.data); return res.data; }

    async function fetchInstalledApps() { isLoadingInstalledApps.value = true; try { const res = await apiClient.get('/api/apps_zoo/installed'); installedApps.value = res.data; } finally { isLoadingInstalledApps.value = false; } }
    async function fetchNextAvailablePort(port = null) { const params = port ? { port } : {}; const res = await apiClient.get('/api/apps_zoo/get-next-available-port', { params }); return res.data.port; }
    async function startApp(appId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/apps_zoo/installed/${appId}/start`); tasksStore.addTask(res.data); }
    async function stopApp(appId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/apps_zoo/installed/${appId}/stop`); tasksStore.addTask(res.data); }
    async function restartApp(appId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/apps_zoo/installed/${appId}/restart`); tasksStore.addTask(res.data); }
    async function updateApp(appId) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post(`/api/apps_zoo/installed/${appId}/update`); tasksStore.addTask(res.data); }
    async function uninstallApp(appId) { await apiClient.delete(`/api/apps_zoo/installed/${appId}`); await fetchZooApps(); await fetchZooMcps(); uiStore.addNotification('Item uninstalled.', 'success'); }
    async function updateInstalledApp(appId, payload) { await apiClient.put(`/api/apps_zoo/installed/${appId}`, payload); await fetchZooApps(); await fetchZooMcps(); }
    async function fetchAppLog(appId) { const res = await apiClient.get(`/api/apps_zoo/installed/${appId}/logs`); return res.data.log_content; }
    async function fetchAppConfigSchema(appId) { const res = await apiClient.get(`/api/apps_zoo/installed/${appId}/config-schema`); return res.data; }
    async function fetchAppConfig(appId) { const res = await apiClient.get(`/api/apps_zoo/installed/${appId}/config`); return res.data; }
    async function updateAppConfig(appId, configData) { await apiClient.put(`/api/apps_zoo/installed/${appId}/config`, configData); }
    async function fetchAppEnv(appId) { const res = await apiClient.get(`/api/apps_zoo/installed/${appId}/env`); return res.data; }
    async function updateAppEnv(appId, content) { await apiClient.put(`/api/apps_zoo/installed/${appId}/env`, { content }); uiStore.addNotification('.env file saved.', 'success'); }
    async function deleteRegisteredApp(appId) { await apiClient.delete(`/api/apps/${appId}`); await fetchZooApps(); uiStore.addNotification('App registration removed.', 'success'); }
    async function deleteRegisteredMcp(mcpId) { await apiClient.delete(`/api/mcps/${mcpId}`); await fetchZooMcps(); uiStore.addNotification('MCP registration removed.', 'success'); }
    async function syncInstallations() { const { useTasksStore } = await import('./tasks'); const tasksStore = useTasksStore(); const response = await apiClient.post('/api/apps_zoo/sync-installs'); tasksStore.addTask(response.data); }
    async function purgeBrokenInstallation(item) { const { useTasksStore } = await import('./tasks'); const tasksStore = useTasksStore(); const response = await apiClient.post('/api/apps_zoo/purge-broken', { item_type: item.item_type || 'app', folder_name: item.folder_name }); tasksStore.addTask(response.data); }
    async function fixBrokenInstallation(item) { const { useTasksStore } = await import('./tasks'); const tasksStore = useTasksStore(); const response = await apiClient.post('/api/apps_zoo/fix-broken', { item_type: item.item_type || 'app', folder_name: item.folder_name }); tasksStore.addTask(response.data); }

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
    async function generateFunFacts(prompt, category) { const { useTasksStore } = await import('./tasks.js'); const tasksStore = useTasksStore(); const res = await apiClient.post('/api/admin/fun-facts/generate-from-prompt', { prompt, category }); tasksStore.addTask(res.data); return res.data; }
    
    async function fetchNewsArticles() { isLoadingNewsArticles.value = true; try { const response = await apiClient.get('/api/admin/news-articles'); newsArticles.value = response.data; } finally { isLoadingNewsArticles.value = false; } }
    async function updateNewsArticle(id, payload) { await apiClient.put(`/api/admin/news-articles/${id}`, payload); await fetchNewsArticles(); uiStore.addNotification('Article updated.', 'success'); }
    async function deleteBatchNewsArticles(ids) { await apiClient.post('/api/admin/news-articles/batch-delete', { article_ids: ids }); await fetchNewsArticles(); uiStore.addNotification(`${ids.length} article(s) deleted.`, 'success'); }

    // --- Moderation Actions ---
    async function fetchModerationQueue(filter = null) {
        const params = {};
        if (filter) params.status_filter = filter;
        const response = await apiClient.get('/api/admin/moderation/queue', { params });
        return response.data;
    }

    async function approveContent(type, id) {
        await apiClient.post(`/api/admin/moderation/${type}/${id}/approve`);
    }

    async function deleteContent(type, id) {
        await apiClient.delete(`/api/admin/moderation/${type}/${id}`);
    }

    return {
        // State
        dashboardStats, isLoadingDashboardStats, allUsers, isLoadingUsers,
        globalSettings, isLoadingSettings, aiBotSettings, isLoadingAiBotSettings,
        bindings, isLoadingBindings, availableBindingTypes,
        ttiBindings, isLoadingTtiBindings, availableTtiBindingTypes,
        ttsBindings, isLoadingTtsBindings, availableTtsBindingTypes,
        sttBindings, isLoadingSttBindings, availableSttBindingTypes,
        ragBindings, isLoadingRagBindings, availableRagBindingTypes, availableRagVectorizers,
        zooRepositories, isLoadingZooRepositories, mcpZooRepositories, isLoadingMcpZooRepositories, promptZooRepositories, isLoadingPromptZooRepositories, personalityZooRepositories, isLoadingPersonalityZooRepositories,
        zooApps, isLoadingZooApps, zooMcps, isLoadingZooMcps, zooPrompts, isLoadingZooPrompts, zooPersonalities, isLoadingZooPersonalities,
        installedApps, isLoadingInstalledApps,
        systemStatus, isLoadingSystemStatus, connectedUsers, isLoadingConnectedUsers, serverInfo, isLoadingServerInfo, globalGenerationStats, isLoadingGlobalGenerationStats, modelUsageStats, isLoadingModelUsageStats,
        funFacts, isLoadingFunFacts, funFactCategories, isLoadingFunFactCategories, newsArticles, isLoadingNewsArticles,
        isImporting, isEnhancingEmail, adminAvailableLollmsModels, isLoadingLollmsModels,
        appFilters, mcpFilters, promptFilters, systemLogs, isLoadingSystemLogs,

        // Actions
        fetchDashboardStats, fetchConnectedUsers, broadcastMessage, createBackup, analyzeSystemLogs,
        fetchSystemStatus, killProcess, fetchModelUsageStats, fetchServerInfo, purgeUnusedUploads,
        fetchAllUsers, activateUser, fetchUserStats, batchUpdateUsers, fetchGlobalGenerationStats,
        fetchGlobalSettings, updateGlobalSettings, fetchAiBotSettings, updateAiBotSettings, triggerBatchModeration, triggerFullRemoderation,
        uploadWelcomeLogo, removeWelcomeLogo, uploadSslFile, importOpenWebUIData, fetchAdminAvailableLollmsModels, generateIconForModel,
        
        fetchBindings, fetchAvailableBindingTypes, addBinding, updateBinding, deleteBinding, fetchBindingModels, getModelCtxSize, saveModelAlias, deleteModelAlias, executeBindingCommand,
        fetchTtiBindings, fetchAvailableTtiBindingTypes, addTtiBinding, updateTtiBinding, deleteTtiBinding, fetchTtiBindingModels, saveTtiModelAlias, deleteTtiModelAlias, executeTtiBindingCommand,
        fetchTtsBindings, fetchAvailableTtsBindingTypes, addTtsBinding, updateTtsBinding, deleteTtsBinding, fetchTtsBindingModels, saveTtsModelAlias, deleteTtsModelAlias, executeTtsBindingCommand,
        fetchSttBindings, fetchAvailableSttBindingTypes, addSttBinding, updateSttBinding, deleteSttBinding, fetchSttBindingModels, saveSttModelAlias, deleteSttModelAlias, executeSttBindingCommand,
        fetchRagBindings, fetchAvailableRagBindingTypes, addRagBinding, updateRagBinding, deleteRagBinding, fetchRagBindingModels, saveRagModelAlias, deleteRagModelAlias, fetchRagModelsForType, addOrUpdateRagAlias, deleteRagAlias, fetchAvailableRagVectorizers,

        fetchZooRepositories, addZooRepository, deleteZooRepository, pullZooRepository, pullAllZooRepositories,
        fetchMcpZooRepositories, addMcpZooRepository, deleteMcpZooRepository, pullMcpZooRepository, pullAllMcpZooRepositories,
        fetchPromptZooRepositories, addPromptZooRepository, deletePromptZooRepository, pullPromptZooRepository, pullAllPromptZooRepositories,
        fetchPersonalityZooRepositories, addPersonalityZooRepository, deletePersonalityZooRepository, pullPersonalityZooRepository,
        fetchZooApps, installZooApp, fetchAppReadme,
        fetchZooMcps, installZooMcp, fetchMcpReadme,
        fetchZooPrompts, installZooPrompt, fetchPromptReadme,
        fetchZooPersonalities, installZooPersonality, fetchPersonalityReadme,
        
        createSystemPrompt, updateSystemPrompt, deleteSystemPrompt, updateSystemPromptFromZoo, generateSystemPrompt,
        fetchInstalledApps, fetchNextAvailablePort, startApp, stopApp, restartApp, updateApp, uninstallApp, updateInstalledApp, fetchAppLog, fetchAppConfigSchema, fetchAppConfig, updateAppConfig, fetchAppEnv, updateAppEnv,
        deleteRegisteredApp, deleteRegisteredMcp, syncInstallations, purgeBrokenInstallation, fixBrokenInstallation, handleAppStatusUpdate,

        fetchFunFacts, fetchFunFactCategories, createFunFact, updateFunFact, deleteFunFact, createFunFactCategory, updateFunFactCategory, deleteFunFactCategory, exportFunFacts, exportCategory, importFunFacts, importCategoryFromFile, generateFunFacts,
        fetchNewsArticles, updateNewsArticle, deleteBatchNewsArticles, fetchSystemLogs,
        
        sendEmailToUsers, enhanceEmail, triggerRssScraping, refreshZooCache, generateSelfSignedCert, downloadCertificate, downloadTrustScript,

        // Moderation
        fetchModerationQueue, approveContent, deleteContent
    };
});
