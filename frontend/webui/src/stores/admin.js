import { defineStore } from 'pinia';
import { ref } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useTasksStore } from './tasks';
import { usePromptsStore } from './prompts';

export const useAdminStore = defineStore('admin', () => {
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();
    const promptsStore = usePromptsStore();

    // --- State ---
    const allUsers = ref([]);
    const isLoadingUsers = ref(false);
    const bindings = ref([]);
    const isLoadingBindings = ref(false);
    const availableBindingTypes = ref([]);
    const globalSettings = ref([]);
    const isLoadingSettings = ref(false);
    const isImporting = ref(false);
    const mcps = ref([]);
    const apps = ref([]);
    const isLoadingServices = ref(false);
    const isEnhancingEmail = ref(false);
    const adminAvailableLollmsModels = ref([]);
    const isLoadingLollmsModels = ref(false);
    const zooRepositories = ref([]);
    const isLoadingZooRepositories = ref(false);
    const mcpZooRepositories = ref([]);
    const isLoadingMcpZooRepositories = ref(false);
    const promptZooRepositories = ref([]);
    const isLoadingPromptZooRepositories = ref(false);
    const zooApps = ref({ items: [], total: 0, pages: 1, categories: [] });
    const isLoadingZooApps = ref(false);
    const zooMcps = ref({ items: [], total: 0, pages: 1, categories: [] });
    const isLoadingZooMcps = ref(false);
    const zooPrompts = ref({ items: [], total: 0, pages: 1, categories: [] });
    const isLoadingZooPrompts = ref(false);
    const installedApps = ref([]);
    const isLoadingInstalledApps = ref(false);
    const systemStatus = ref(null);
    const isLoadingSystemStatus = ref(false);

    // --- Actions ---
    async function fetchSystemStatus() {
        isLoadingSystemStatus.value = true;
        try {
            const response = await apiClient.get('/api/admin/system-status');
            systemStatus.value = response.data;
        } catch (error) {
            systemStatus.value = null;
            uiStore.addNotification('Could not load system status.', 'error');
        } finally {
            isLoadingSystemStatus.value = false;
        }
    }

    async function purgeUnusedUploads() {
        const response = await apiClient.post('/api/admin/purge-unused-uploads');
        const task = response.data;
        uiStore.addNotification(`Task '${task.name}' started.`, 'info');
        tasksStore.addTask(task);
        return task;
    }

    async function fetchAllUsers() {
        isLoadingUsers.value = true;
        try {
            const response = await apiClient.get('/api/admin/users');
            allUsers.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load user list.', 'error');
        } finally {
            isLoadingUsers.value = false;
        }
    }
    
    async function sendEmailToUsers(subject, body, user_ids, backgroundColor, sendAsText) {
        const payload = { subject, body, user_ids, background_color: backgroundColor, send_as_text: sendAsText };
        const response = await apiClient.post('/api/admin/email-users', payload);
        const task = response.data;
        uiStore.addNotification(`Email task '${task.name}' started.`, 'success');
        tasksStore.addTask(task);
        return true;
    }
    
    async function enhanceEmail(subject, body, backgroundColor, prompt) {
        isEnhancingEmail.value = true;
        try {
            const response = await apiClient.post('/api/admin/enhance-email', { subject, body, background_color: backgroundColor, prompt });
            uiStore.addNotification('Email content enhanced by AI.', 'success');
            return response.data;
        } finally {
            isEnhancingEmail.value = false;
        }
    }

    async function batchUpdateUsers(payload) {
        const response = await apiClient.post('/api/admin/users/batch-update-settings', payload);
        uiStore.addNotification(response.data.message || 'Settings applied successfully.', 'success');
        await fetchAllUsers();
    }
    
    async function fetchAdminAvailableLollmsModels() {
        if (adminAvailableLollmsModels.value.length > 0) return;
        isLoadingLollmsModels.value = true;
        try {
            const response = await apiClient.get('/api/admin/available-models');
            adminAvailableLollmsModels.value = response.data;
        } catch (error) {
            adminAvailableLollmsModels.value = [];
        } finally {
            isLoadingLollmsModels.value = false;
        }
    }

    async function fetchBindings() {
        isLoadingBindings.value = true;
        try {
            const response = await apiClient.get('/api/admin/bindings');
            bindings.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load LLM bindings.', 'error');
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

    async function fetchGlobalSettings() {
        isLoadingSettings.value = true;
        try {
            const response = await apiClient.get('/api/admin/settings');
            globalSettings.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load global settings.', 'error');
        } finally {
            isLoadingSettings.value = false;
        }
    }
    async function updateGlobalSettings(configs) {
        const response = await apiClient.put('/api/admin/settings', { configs });
        await fetchGlobalSettings();
        uiStore.addNotification(response.data.message, 'success');
    }

    async function importOpenWebUIData(file) {
        isImporting.value = true;
        const formData = new FormData();
        formData.append('file', file);
        try {
            const response = await apiClient.post('/api/admin/import-openwebui', formData);
            uiStore.addNotification(response.data.message, 'success', { duration: 5000 });
        } finally {
            isImporting.value = false;
        }
    }
    
    // --- App Zoo ---
    async function fetchZooRepositories() { isLoadingZooRepositories.value = true; try { const res = await apiClient.get('/api/apps_zoo/repositories'); zooRepositories.value = res.data; } finally { isLoadingZooRepositories.value = false; } }
    async function addZooRepository(name, url) { const res = await apiClient.post('/api/apps_zoo/repositories', { name, url }); zooRepositories.value.push(res.data); uiStore.addNotification(`Repo '${name}' added.`, 'success'); }
    async function deleteZooRepository(repoId) { await apiClient.delete(`/api/apps_zoo/repositories/${repoId}`); zooRepositories.value = zooRepositories.value.filter(r => r.id !== repoId); uiStore.addNotification('Repo deleted.', 'success'); }
    async function pullZooRepository(repoId) { const res = await apiClient.post(`/api/apps_zoo/repositories/${repoId}/pull`); tasksStore.addTask(res.data); uiStore.addNotification(res.data.name + ' started.', 'info'); }
    async function pullAllZooRepositories() { uiStore.addNotification('Pulling all app repos...', 'info'); for (const repo of zooRepositories.value) await pullZooRepository(repo.id); }
    async function fetchZooApps(params = {}) { isLoadingZooApps.value = true; try { const [cat_res, items_res] = await Promise.all([apiClient.get('/api/apps_zoo/categories'), apiClient.get('/api/apps_zoo/available', { params })]); zooApps.value = { ...items_res.data, categories: cat_res.data }; } finally { isLoadingZooApps.value = false; } }
    async function installZooApp(payload) { const res = await apiClient.post('/api/apps_zoo/install', payload); tasksStore.addTask(res.data); uiStore.addNotification(res.data.name + ' started.', 'info'); await fetchInstalledApps(); }
    async function fetchAppReadme(repo, folder) { const res = await apiClient.get('/api/apps_zoo/readme', { params: { repository: repo, folder_name: folder } }); return res.data; }
    
    // --- MCP Zoo ---
    async function fetchMcpZooRepositories() { isLoadingMcpZooRepositories.value = true; try { const res = await apiClient.get('/api/mcps_zoo/repositories'); mcpZooRepositories.value = res.data; } finally { isLoadingMcpZooRepositories.value = false; } }
    async function addMcpZooRepository(name, url) { const res = await apiClient.post('/api/mcps_zoo/repositories', { name, url }); mcpZooRepositories.value.push(res.data); uiStore.addNotification(`MCP Repo '${name}' added.`, 'success'); }
    async function deleteMcpZooRepository(repoId) { await apiClient.delete(`/api/mcps_zoo/repositories/${repoId}`); mcpZooRepositories.value = mcpZooRepositories.value.filter(r => r.id !== repoId); uiStore.addNotification('MCP Repo deleted.', 'success'); }
    async function pullMcpZooRepository(repoId) { const res = await apiClient.post(`/api/mcps_zoo/repositories/${repoId}/pull`); tasksStore.addTask(res.data); uiStore.addNotification(res.data.name + ' started.', 'info'); }
    async function pullAllMcpZooRepositories() { uiStore.addNotification('Pulling all MCP repos...', 'info'); for (const repo of mcpZooRepositories.value) await pullMcpZooRepository(repo.id); }
    async function fetchZooMcps(params = {}) { isLoadingZooMcps.value = true; try { const [cat_res, items_res] = await Promise.all([apiClient.get('/api/mcps_zoo/categories'), apiClient.get('/api/mcps_zoo/available', { params })]); zooMcps.value = { ...items_res.data, categories: cat_res.data }; } finally { isLoadingZooMcps.value = false; } }
    async function installZooMcp(payload) { const res = await apiClient.post('/api/mcps_zoo/install', payload); tasksStore.addTask(res.data); uiStore.addNotification(res.data.name + ' started.', 'info'); await fetchInstalledApps(); }
    async function fetchMcpReadme(repo, folder) { const res = await apiClient.get('/api/mcps_zoo/readme', { params: { repository: repo, folder_name: folder } }); return res.data; }
    
    // --- Prompt Zoo ---
    async function fetchPromptZooRepositories() { isLoadingPromptZooRepositories.value = true; try { const res = await apiClient.get('/api/prompts_zoo/repositories'); promptZooRepositories.value = res.data; } finally { isLoadingPromptZooRepositories.value = false; } }
    async function addPromptZooRepository(repoData) { const res = await apiClient.post('/api/prompts_zoo/repositories', repoData); promptZooRepositories.value.push(res.data); uiStore.addNotification(`Prompt Repo '${repoData.name}' added.`, 'success'); }
    async function deletePromptZooRepository(repoId) { await apiClient.delete(`/api/prompts_zoo/repositories/${repoId}`); promptZooRepositories.value = promptZooRepositories.value.filter(r => r.id !== repoId); uiStore.addNotification('Prompt Repo deleted.', 'success'); }
    async function pullPromptZooRepository(repoId) { const res = await apiClient.post(`/api/prompts_zoo/repositories/${repoId}/pull`); tasksStore.addTask(res.data); uiStore.addNotification(res.data.name + ' started.', 'info'); }
    async function pullAllPromptZooRepositories() { uiStore.addNotification('Pulling all prompt repos...', 'info'); for (const repo of promptZooRepositories.value) await pullPromptZooRepository(repo.id); }
    async function fetchZooPrompts(params = {}) { isLoadingZooPrompts.value = true; try { const [cat_res, items_res] = await Promise.all([apiClient.get('/api/prompts_zoo/categories'), apiClient.get('/api/prompts_zoo/available', { params })]); zooPrompts.value = { ...items_res.data, categories: cat_res.data }; } finally { isLoadingZooPrompts.value = false; } }
    async function installZooPrompt(payload) { const res = await apiClient.post('/api/prompts_zoo/install', payload); tasksStore.addTask(res.data); uiStore.addNotification(res.data.name + ' started.', 'info'); }
    async function fetchPromptReadme(repo, folder) { const res = await apiClient.get('/api/prompts_zoo/readme', { params: { repository: repo, folder_name: folder } }); return res.data; }

    // --- System Prompt Management ---
    async function createSystemPrompt(promptData) { await apiClient.post('/api/prompts_zoo/installed', promptData); uiStore.addNotification('System prompt created.', 'success'); await promptsStore.fetchPrompts(); }
    async function updateSystemPrompt(promptId, promptData) { await apiClient.put(`/api/prompts_zoo/installed/${promptId}`, promptData); uiStore.addNotification('System prompt updated.', 'success'); await promptsStore.fetchPrompts(); }
    async function deleteSystemPrompt(promptId) { await apiClient.delete(`/api/prompts_zoo/installed/${promptId}`); uiStore.addNotification('System prompt deleted.', 'success'); await promptsStore.fetchPrompts(); }
    async function generateSystemPrompt(prompt) {
        const res = await apiClient.post('/api/prompts_zoo/generate_from_prompt', { prompt });
        tasksStore.addTask(res.data);
        uiStore.addNotification(`Task '${res.data.name}' started.`, 'info');
        return res.data;
    }


    // --- Installed Apps ---
    async function fetchInstalledApps() { isLoadingInstalledApps.value = true; try { const res = await apiClient.get('/api/apps_zoo/installed'); installedApps.value = res.data; } finally { isLoadingInstalledApps.value = false; } }
    async function fetchNextAvailablePort(port = null) { const params = port ? { port } : {}; const res = await apiClient.get('/api/apps_zoo/get-next-available-port', { params }); return res.data.port; }
    async function startApp(appId) { const res = await apiClient.post(`/api/apps_zoo/installed/${appId}/start`); tasksStore.addTask(res.data); uiStore.addNotification(`Task '${res.data.name}' started.`, 'info'); }
    async function stopApp(appId) { const res = await apiClient.post(`/api/apps_zoo/installed/${appId}/stop`); tasksStore.addTask(res.data); uiStore.addNotification(`Task '${res.data.name}' started.`, 'info'); }
    async function uninstallApp(appId) { const res = await apiClient.delete(`/api/apps_zoo/installed/${appId}`); uiStore.addNotification(res.data.message, 'success'); await fetchInstalledApps(); }
    async function updateInstalledApp(appId, payload) { const res = await apiClient.put(`/api/apps_zoo/installed/${appId}`, payload); uiStore.addNotification(`App '${res.data.name}' updated.`, 'success'); const i = installedApps.value.findIndex(a => a.id === appId); if (i !== -1) installedApps.value[i] = res.data; return res.data; }
    async function fetchAppLog(appId) { const res = await apiClient.get(`/api/apps_zoo/installed/${appId}/logs`); return res.data.log_content; }
    async function fetchAppConfigSchema(appId) { const res = await apiClient.get(`/api/apps_zoo/installed/${appId}/config-schema`); return res.data; }
    async function fetchAppConfig(appId) { const res = await apiClient.get(`/api/apps_zoo/installed/${appId}/config`); return res.data; }
    async function updateAppConfig(appId, configData) { const res = await apiClient.put(`/api/apps_zoo/installed/${appId}/config`, configData); uiStore.addNotification(res.data.message || 'Config saved.', 'success'); }

    return {
        allUsers, isLoadingUsers, fetchAllUsers, sendEmailToUsers,
        bindings, isLoadingBindings, availableBindingTypes, fetchBindings, fetchAvailableBindingTypes, addBinding, updateBinding, deleteBinding,
        globalSettings, isLoadingSettings, fetchGlobalSettings, updateGlobalSettings,
        isImporting, importOpenWebUIData,
        adminAvailableLollmsModels, isLoadingLollmsModels, fetchAdminAvailableLollmsModels,
        batchUpdateUsers, isEnhancingEmail, enhanceEmail,
        zooRepositories, isLoadingZooRepositories, fetchZooRepositories, addZooRepository, deleteZooRepository, pullZooRepository, pullAllZooRepositories,
        mcpZooRepositories, isLoadingMcpZooRepositories, fetchMcpZooRepositories, addMcpZooRepository, deleteMcpZooRepository, pullMcpZooRepository, pullAllMcpZooRepositories,
        promptZooRepositories, isLoadingPromptZooRepositories, fetchPromptZooRepositories, addPromptZooRepository, deletePromptZooRepository, pullPromptZooRepository, pullAllPromptZooRepositories,
        zooApps, isLoadingZooApps, fetchZooApps,
        zooMcps, isLoadingZooMcps, fetchZooMcps, fetchMcpReadme, installZooMcp,
        zooPrompts, isLoadingZooPrompts, fetchZooPrompts, fetchPromptReadme, installZooPrompt,
        installedApps, isLoadingInstalledApps, fetchInstalledApps, startApp, stopApp, uninstallApp, fetchNextAvailablePort,
        purgeUnusedUploads, updateInstalledApp, fetchAppLog,
        systemStatus, isLoadingSystemStatus, fetchSystemStatus,
        fetchAppConfigSchema, fetchAppConfig, updateAppConfig,
        installZooApp, fetchAppReadme,
        createSystemPrompt, updateSystemPrompt, deleteSystemPrompt, generateSystemPrompt
    };
});