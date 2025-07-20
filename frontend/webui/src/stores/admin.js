import { defineStore } from 'pinia';
import { ref } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useAdminStore = defineStore('admin', () => {
    const uiStore = useUiStore();

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

    const zooApps = ref([]);
    const isLoadingZooApps = ref(false);

    const installedApps = ref([]);
    const isLoadingInstalledApps = ref(false);

    const tasks = ref([]);
    const isLoadingTasks = ref(false);
    const activeTaskIds = ref({}); // Maps app names to task IDs

    // --- Actions ---
    
    // Tasks
    async function fetchTasks() {
        isLoadingTasks.value = true;
        try {
            const response = await apiClient.get('/api/tasks');
            tasks.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not fetch task list.', 'error');
        } finally {
            isLoadingTasks.value = false;
        }
    }
    async function clearCompletedTasks() {
        try {
            await apiClient.post('/api/tasks/clear-completed');
            uiStore.addNotification('Cleared completed tasks.', 'success');
            await fetchTasks();
        } catch (error) {
            // Handled globally
        }
    }
    async function cancelTask(taskId) {
        try {
            const response = await apiClient.post(`/api/tasks/${taskId}/cancel`);
            uiStore.addNotification(`Task cancellation initiated for '${response.data.name}'.`, 'info');
            await fetchTasks();
        } catch (error) {
            // Handled globally
        }
    }


    // Users
    async function fetchAllUsers() {
        isLoadingUsers.value = true;
        try {
            const response = await apiClient.get('/api/admin/users');
            allUsers.value = response.data;
        } catch (error) {
            console.error("Failed to fetch users:", error);
            uiStore.addNotification('Could not load user list.', 'error');
        } finally {
            isLoadingUsers.value = false;
        }
    }
    
    async function sendEmailToUsers(subject, body, user_ids, backgroundColor, sendAsText) {
        try {
            const payload = {
                subject,
                body,
                user_ids,
                background_color: backgroundColor,
                send_as_text: sendAsText
            };
            const response = await apiClient.post('/api/admin/email-users', payload);
            uiStore.addNotification(response.data.message || 'Email task started.', 'success');
            return true;
        } catch (error) {
            return false;
        }
    }
    
    async function enhanceEmail(subject, body, backgroundColor, prompt) {
        isEnhancingEmail.value = true;
        try {
            const response = await apiClient.post('/api/admin/enhance-email', { subject, body, background_color: backgroundColor, prompt });
            uiStore.addNotification('Email content enhanced by AI.', 'success');
            return response.data;
        } catch (error) {
            // Error handled by global interceptor
            return null;
        } finally {
            isEnhancingEmail.value = false;
        }
    }

    async function batchUpdateUsers(payload) {
        try {
            const response = await apiClient.post('/api/admin/users/batch-update-settings', payload);
            uiStore.addNotification(response.data.message || 'Settings applied successfully.', 'success');
            await fetchAllUsers();
        } catch (error) {
            throw error;
        }
    }
    
    async function fetchAdminAvailableLollmsModels() {
        if (adminAvailableLollmsModels.value.length > 0) return;
        isLoadingLollmsModels.value = true;
        try {
            const response = await apiClient.get('/api/admin/available-models');
            adminAvailableLollmsModels.value = response.data;
        } catch (error) {
            uiStore.addNotification("Could not fetch available LLM models for admin.", 'error');
            adminAvailableLollmsModels.value = [];
        } finally {
            isLoadingLollmsModels.value = false;
        }
    }

    // Bindings
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
        try {
            const response = await apiClient.get('/api/admin/bindings/available_types');
            availableBindingTypes.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load available binding types.', 'error');
        }
    }
    async function addBinding(payload) {
        const response = await apiClient.post('/api/admin/bindings', payload);
        bindings.value.push(response.data);
        uiStore.addNotification(`Binding '${response.data.alias}' created.`, 'success');
    }
    async function updateBinding(id, payload) {
        const response = await apiClient.put(`/api/admin/bindings/${id}`, payload);
        const index = bindings.value.findIndex(b => b.id === id);
        if (index !== -1) {
            bindings.value[index] = response.data;
        }
        uiStore.addNotification(`Binding '${response.data.alias}' updated.`, 'success');
    }
    async function deleteBinding(id) {
        await apiClient.delete(`/api/admin/bindings/${id}`);
        bindings.value = bindings.value.filter(b => b.id !== id);
        uiStore.addNotification('Binding deleted successfully.', 'success');
    }

    // Global Settings
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

    // Import
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
    
    // MCPs
    async function fetchMcps() {
        isLoadingServices.value = true;
        try {
            const response = await apiClient.get('/api/mcps');
            mcps.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load MCPs.', 'error');
        } finally {
            isLoadingServices.value = false;
        }
    }
    async function addMcp(payload) {
        const response = await apiClient.post('/api/mcps', payload);
        mcps.value.push(response.data);
        uiStore.addNotification(`MCP '${response.data.name}' created successfully.`, 'success');
    }
    async function updateMcp(id, payload) {
        const response = await apiClient.put(`/api/mcps/${id}`, payload);
        const index = mcps.value.findIndex(m => m.id === id);
        if (index !== -1) mcps.value[index] = response.data;
        uiStore.addNotification(`MCP '${response.data.name}' updated successfully.`, 'success');
    }
    async function deleteMcp(id) {
        await apiClient.delete(`/api/mcps/${id}`);
        mcps.value = mcps.value.filter(m => m.id !== id);
        uiStore.addNotification('MCP deleted successfully.', 'success');
    }
    async function generateMcpSsoSecret(id) {
        try {
            const response = await apiClient.post(`/api/mcps/${id}/generate-sso-secret`);
            await fetchMcps();
            return response.data.sso_secret;
        } catch (error) {
            throw error;
        }
    }

    // Apps
    async function fetchApps() {
        isLoadingServices.value = true;
        try {
            const response = await apiClient.get('/api/apps');
            apps.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load Apps.', 'error');
        } finally {
            isLoadingServices.value = false;
        }
    }
    async function addApp(payload) {
        const response = await apiClient.post('/api/apps', payload);
        apps.value.push(response.data);
        uiStore.addNotification(`App '${response.data.name}' created successfully.`, 'success');
    }
    async function updateApp(id, payload) {
        const response = await apiClient.put(`/api/apps/${id}`, payload);
        const index = apps.value.findIndex(a => a.id === id);
        if (index !== -1) apps.value[index] = response.data;
        uiStore.addNotification(`App '${response.data.name}' updated successfully.`, 'success');
    }
    async function deleteApp(id) {
        await apiClient.delete(`/api/apps/${id}`);
        apps.value = apps.value.filter(a => a.id !== id);
        uiStore.addNotification('App deleted successfully.', 'success');
    }
    async function generateAppSsoSecret(id) {
        try {
            const response = await apiClient.post(`/api/apps/${id}/generate-sso-secret`);
            await fetchApps();
            return response.data.sso_secret;
        } catch (error) {
            throw error;
        }
    }

    // App Zoo Repositories
    async function fetchZooRepositories() {
        isLoadingZooRepositories.value = true;
        try {
            const response = await apiClient.get('/api/apps-management/zoo/repositories');
            zooRepositories.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load App Zoo repositories.', 'error');
        } finally {
            isLoadingZooRepositories.value = false;
        }
    }
    async function addZooRepository(name, url) {
        try {
            const response = await apiClient.post('/api/apps-management/zoo/repositories', { name, url });
            zooRepositories.value.push(response.data);
            uiStore.addNotification(`Repository '${name}' added.`, 'success');
        } catch (error) {
            throw error; // Let the component handle UI feedback on error
        }
    }
    async function deleteZooRepository(repoId) {
        try {
            await apiClient.delete(`/api/apps-management/zoo/repositories/${repoId}`);
            zooRepositories.value = zooRepositories.value.filter(r => r.id !== repoId);
            uiStore.addNotification('Repository deleted.', 'success');
        } catch (error) {
            throw error;
        }
    }
    async function pullZooRepository(repoId) {
        try {
            const response = await apiClient.post(`/api/apps-management/zoo/repositories/${repoId}/pull`);
            const task = response.data;
            activeTaskIds.value[task.name] = task.id;
            uiStore.addNotification(task.name + ' started.', 'info', { duration: 5000 });
            return task;
        } catch (error) {
            throw error;
        }
    }
    async function pullAllZooRepositories() {
        if (zooRepositories.value.length === 0) {
            uiStore.addNotification('No repositories to pull.', 'info');
            return;
        }
        uiStore.addNotification('Starting to pull all repositories...', 'info');
        // Sequentially start the pull tasks. The tasks themselves run in the background.
        for (const repo of zooRepositories.value) {
            try {
                await pullZooRepository(repo.id);
            } catch (error) {
                // The error is already handled and notified by the global interceptor.
                console.error(`Failed to start pull task for repository: ${repo.name}`, error);
            }
        }
    }

    // Available Zoo Apps
    async function fetchZooApps() {
        isLoadingZooApps.value = true;
        try {
            const response = await apiClient.get('/api/apps-management/zoo/available-apps');
            zooApps.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load available apps from the zoo.', 'error');
        } finally {
            isLoadingZooApps.value = false;
        }
    }

    async function fetchAppReadme(repository, folder_name) {
        try {
            const response = await apiClient.get('/api/apps-management/zoo/app-readme', {
                params: { repository, folder_name }
            });
            return response.data;
        } catch (error) {
            throw error;
        }
    }

    async function installZooApp(payload) {
        try {
            const response = await apiClient.post('/api/apps-management/zoo/install-app', payload);
            const task = response.data;
            activeTaskIds.value[task.name] = task.id;
            uiStore.addNotification(task.name + ' started.', 'info', { duration: 5000 });

            // No longer need polling here as the component will do it based on activeTaskIds
            await fetchZooApps();
            await fetchTasks();
            return task;
        } catch (error) {
            throw error;
        }
    }
    
    // Installed Apps Management
    async function fetchInstalledApps() {
        isLoadingInstalledApps.value = true;
        try {
            const response = await apiClient.get('/api/apps-management/installed-apps');
            installedApps.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load installed apps.', 'error');
        } finally {
            isLoadingInstalledApps.value = false;
        }
    }

    async function fetchNextAvailablePort(port = null) {
        try {
            const params = port ? { port } : {};
            const response = await apiClient.get('/api/apps-management/apps/get-next-available-port', { params });
            return response.data.port;
        } catch (error) {
            if (port) throw error; // Re-throw for specific port checks
            uiStore.addNotification('Could not determine an available port.', 'warning');
            return 9601; // Fallback
        }
    }

    async function startApp(appId) {
        const response = await apiClient.post(`/api/apps-management/installed-apps/${appId}/start`);
        uiStore.addNotification(response.data.message, response.data.success ? 'success' : 'warning');
        await fetchInstalledApps();
    }
    async function stopApp(appId) {
        const response = await apiClient.post(`/api/apps-management/installed-apps/${appId}/stop`);
        uiStore.addNotification(response.data.message, response.data.success ? 'success' : 'warning');
        await fetchInstalledApps();
    }
    async function uninstallApp(appId) {
        const response = await apiClient.delete(`/api/apps-management/installed-apps/${appId}`);
        uiStore.addNotification(response.data.message, 'success');
        await fetchInstalledApps();
        await fetchZooApps();
    }

    async function updateInstalledApp(appId, payload) {
        try {
            const response = await apiClient.put(`/api/apps-management/installed-apps/${appId}`, payload);
            uiStore.addNotification(`App '${response.data.name}' updated successfully.`, 'success');
            await fetchInstalledApps();
            return response.data;
        } catch (error) {
            throw error;
        }
    }

    async function fetchAppLog(appId) {
        try {
            const response = await apiClient.get(`/api/apps-management/installed-apps/${appId}/logs`);
            return response.data.log_content;
        } catch (error) {
            throw error;
        }
    }


    return {
        allUsers, isLoadingUsers, fetchAllUsers, sendEmailToUsers,
        bindings, isLoadingBindings, availableBindingTypes, fetchBindings, fetchAvailableBindingTypes, addBinding, updateBinding, deleteBinding,
        globalSettings, isLoadingSettings, fetchGlobalSettings, updateGlobalSettings,
        isImporting, importOpenWebUIData,
        mcps, apps, isLoadingServices,
        fetchMcps, addMcp, updateMcp, deleteMcp, generateMcpSsoSecret,
        fetchApps, addApp, updateApp, deleteApp, generateAppSsoSecret,
        adminAvailableLollmsModels, isLoadingLollmsModels, fetchAdminAvailableLollmsModels,
        batchUpdateUsers,
        isEnhancingEmail, enhanceEmail,
        zooRepositories, isLoadingZooRepositories, fetchZooRepositories, addZooRepository, deleteZooRepository, pullZooRepository, pullAllZooRepositories,
        zooApps, isLoadingZooApps, fetchZooApps, installZooApp, fetchAppReadme,
        installedApps, isLoadingInstalledApps, fetchInstalledApps, startApp, stopApp, uninstallApp, fetchNextAvailablePort,
        tasks, isLoadingTasks, activeTaskIds, fetchTasks, clearCompletedTasks, cancelTask,
        updateInstalledApp, fetchAppLog
    };
});