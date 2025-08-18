// frontend/webui/src/stores/data.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue'; // Remove onMounted from this import list
import apiClient from '../services/api';
import { useAuthStore } from './auth';
import { useUiStore } from './ui';
import { useTasksStore } from './tasks'; // Import tasks store
import useEventBus from '../services/eventBus';

export const useDataStore = defineStore('data', () => {
    const { on } = useEventBus();

    const availableLollmsModels = ref([]);
    const availableTtiModels = ref([]); // NEW
    const ownedDataStores = ref([]);
    const sharedDataStores = ref([]);
    const userPersonalities = ref([]);
    const publicPersonalities = ref([]);
    const userMcps = ref([]);
    const systemMcps = ref([]);
    const mcpTools = ref([]);
    const userApps = ref([]);
    const systemApps = ref([]);
    const isLoadingLollmsModels = ref(false);
    const isLoadingTtiModels = ref(false); // NEW
    const _languages = ref([]);
    const isLoadingLanguages = ref(false);
    const apiKeys = ref([]);

    const defaultLanguages = [
        { label: 'English', value: 'en' },
        { label: 'French', value: 'fr' },
        { label: 'German', value: 'de' },
        { label: 'Spanish', value: 'es' },
        { label: 'Italian', value: 'it' },
        { label: 'Portuguese', value: 'pt' },
        { label: 'Russian', value: 'ru' },
        { label: 'Chinese', value: 'zh' },
        { label: 'Japanese', value: 'ja' },
        { label: 'Korean', value: 'ko' },
        { label: 'Arabic', value: 'ar' },
    ];

    const languages = computed(() => {
        const sourceList = _languages.value.length > 0 ? _languages.value : defaultLanguages;
        return sourceList;
    });

    const availableRagStores = computed(() => {
        const authStore = useAuthStore();
        if (!authStore.user) return [];
        const owned = ownedDataStores.value.map(ds => ({ id: ds.id, name: `${ds.name} (You)` }));
        const shared = sharedDataStores.value.map(ds => ({ id: ds.id, name: `${ds.name} (from ${ds.owner_username})` }));
        return [...owned, ...shared].sort((a, b) => a.name.localeCompare(b.name));
    });
    const availableMcpToolsForSelector = computed(() => {
        if (!Array.isArray(mcpTools.value) || mcpTools.value.length === 0) return [];
        const grouped = mcpTools.value.reduce((acc, tool) => {
            const parts = tool.name.split('::');
            if (parts.length !== 2) return acc;
            const mcpName = parts[0];
            const toolName = parts[1];
            if (!acc[mcpName]) {
                acc[mcpName] = [];
            }
            acc[mcpName].push({ id: tool.name, name: toolName });
            return acc;
        }, {});
        return Object.entries(grouped).map(([mcpName, tools]) => ({ isGroup: true, label: mcpName, items: tools.sort((a, b) => a.name.localeCompare(b.name))})).sort((a,b) => a.label.localeCompare(b.label));
    });
    const availableLLMModelsGrouped = computed(() => {
        if (!Array.isArray(availableLollmsModels.value) || availableLollmsModels.value.length === 0) {
            return [];
        }

        const grouped = availableLollmsModels.value.reduce((acc, model) => {
            if (!model || typeof model.id !== 'string') {
                console.warn("Skipping invalid model entry in availableLollmsModels:", model);
                return acc;
            }
            
            const [bindingAlias] = model.id.split('/');
            if (!acc[bindingAlias]) {
                acc[bindingAlias] = { isGroup: true, label: bindingAlias, items: [] };
            }

            // The backend now handles the display name based on the mode.
            // We just need to map the icon.
            acc[bindingAlias].items.push({ 
                id: model.id, 
                name: model.name, // Use the name from the API directly
                icon_base64: model.alias?.icon,
                description: model.alias?.description,
                alias: model.alias
            });
            return acc;
        }, {});

        Object.values(grouped).forEach(group => {
            group.items.sort((a, b) => a.name.localeCompare(b.name));
        });

        return Object.values(grouped).filter(g => g.items.length > 0).sort((a, b) => a.label.localeCompare(b.label));
    });
    // NEW
    const availableTtiModelsGrouped = computed(() => {
        if (!Array.isArray(availableTtiModels.value) || availableTtiModels.value.length === 0) {
            return [];
        }

        const grouped = availableTtiModels.value.reduce((acc, model) => {
            if (!model || typeof model.id !== 'string') {
                console.warn("Skipping invalid TTI model entry:", model);
                return acc;
            }
            
            const [bindingAlias] = model.id.split('/');
            if (!acc[bindingAlias]) {
                acc[bindingAlias] = { isGroup: true, label: bindingAlias, items: [] };
            }

            acc[bindingAlias].items.push({ 
                id: model.id, 
                name: model.name, // Use name from API directly
                icon_base64: model.alias?.icon,
                description: model.alias?.description,
                alias: model.alias
            });
            return acc;
        }, {});

        Object.values(grouped).forEach(group => {
            group.items.sort((a, b) => a.name.localeCompare(b.name));
        });

        return Object.values(grouped).filter(g => g.items.length > 0).sort((a, b) => a.label.localeCompare(b.label));
    });
    const allPersonalities = computed(() => [...userPersonalities.value, ...publicPersonalities.value]);
    const getPersonalityById = computed(() => {
        return (id) => allPersonalities.value.find(p => p.id === id);
    });

    async function handleTaskCompletion(task) {
        if (!task || !['completed', 'failed', 'cancelled'].includes(task.status)) return;
        const taskName = task.name || '';
        const isAppOrMcpTask = /app|mcp/i.test(taskName) && (
            taskName.includes('Installing') ||
            taskName.includes('Start') ||
            taskName.includes('Stop') ||
            taskName.includes('Updating') ||
            taskName.includes('Fixing') ||
            taskName.includes('Purging')
        );

        if (isAppOrMcpTask) {
            console.log(`[Data Store] Refreshing app/mcp lists due to task: ${taskName}`);
            await Promise.allSettled([fetchApps(), fetchMcps()]);
        }
    }

    // This line registers the event listener as soon as the store is created.
    // It is no longer tied to a component's lifecycle hook.
    on('task:completed', handleTaskCompletion);

    function handleServiceStatusUpdate(serviceData) {
        const listsToUpdate = [userApps, systemApps, userMcps, systemMcps];
        for (const listRef of listsToUpdate) {
            const list = listRef.value;
            if (!Array.isArray(list)) continue;
            const index = list.findIndex(item => item.id === serviceData.id);
            if (index !== -1) {
                Object.assign(list[index], serviceData);
                console.log(`Updated service '${serviceData.name}' in data store.`);
                return;
            }
        }
    }

    async function fetchLanguages() {
        if (_languages.value.length > 0 || isLoadingLanguages.value) return;
        isLoadingLanguages.value = true;
        try {
            const response = await apiClient.get('/api/languages');
            if (Array.isArray(response.data)) {
                _languages.value = response.data;
            } else {
                _languages.value = [];
            }
        } catch (error) {
            console.error("Failed to fetch languages, using fallback.", error);
            _languages.value = [];
        } finally {
            isLoadingLanguages.value = false;
        }
    }

    async function fetchApiKeys() {
        try {
            const response = await apiClient.get('/api/api-keys');
            apiKeys.value = response.data;
        } catch (error) {
            if (error.response?.status !== 403) {
                useUiStore().addNotification('Could not fetch API keys.', 'error');
            }
            console.warn("API keys could not be fetched (this is normal if the service is disabled).");
            apiKeys.value = [];
        }
    }

    async function addApiKey(alias) {
        const response = await apiClient.post('/api/api-keys', { alias });
        await fetchApiKeys();
        return response.data;
    }


    async function deleteSingleApiKey(keyId) {
        const uiStore = useUiStore();
        await apiClient.delete(`/api/api-keys/${keyId}`);
        apiKeys.value = apiKeys.value.filter(key => key.id !== keyId);
        uiStore.addNotification('API Key deleted successfully.', 'success');
    }
    
    async function deleteMultipleApiKeys(keyIds) {
        const uiStore = useUiStore();
        const response = await apiClient.delete('/api/api-keys', { data: { key_ids: keyIds } });
        apiKeys.value = apiKeys.value.filter(key => !keyIds.includes(key.id));
        uiStore.addNotification(response.data.message || 'Selected keys deleted.', 'success');
    }

    async function loadAllInitialData() {
        const { usePromptsStore } = await import('./prompts');
        const promptsStore = usePromptsStore();
        const promises = [
            fetchAvailableLollmsModels().catch(e => console.error("Error fetching models:", e)),
            fetchAvailableTtiModels().catch(e => console.error("Error fetching TTI models:", e)), // NEW
            fetchDataStores().catch(e => console.error("Error fetching data stores:", e)),
            fetchPersonalities().catch(e => console.error("Error fetching personalities:", e)),
            fetchMcps().catch(e => console.error("Error fetching MCPs:", e)),
            fetchMcpTools().catch(e => console.error("Error fetching MCP tools:", e)),
            fetchApps().catch(e => console.error("Error fetching apps:", e)),
            fetchLanguages().catch(e => console.error("Error fetching languages:", e)),
            fetchApiKeys().catch(e => console.error("Error fetching API keys:", e)),
            promptsStore.fetchPrompts().catch(e => console.error("Error fetching saved prompts:", e))
        ];
        await Promise.allSettled(promises);
    }
    
    async function fetchAvailableLollmsModels() {
        isLoadingLollmsModels.value = true;
        try {
            const response = await apiClient.get('/api/config/lollms-models');
            availableLollmsModels.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            availableLollmsModels.value = [];
        } finally {
            isLoadingLollmsModels.value = false;
        }
    }
    // NEW
    async function fetchAvailableTtiModels() {
        isLoadingTtiModels.value = true;
        try {
            const response = await apiClient.get('/api/config/tti-models');
            availableTtiModels.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            availableTtiModels.value = [];
        } finally {
            isLoadingTtiModels.value = false;
        }
    }
    async function fetchAdminAvailableLollmsModels() {
        isLoadingLollmsModels.value = true;
        try {
            const response = await apiClient.get('/api/admin/available-models');
            availableLollmsModels.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            availableLollmsModels.value = [];
        } finally {
            isLoadingLollmsModels.value = false;
        }
    }
    async function fetchDataStores() {
        try {
            const response = await apiClient.get('/api/datastores');
            const authStore = useAuthStore();
            if (Array.isArray(response.data) && authStore.user) {
                ownedDataStores.value = response.data.filter(ds => ds.owner_username === authStore.user.username);
                sharedDataStores.value = response.data.filter(ds => ds.owner_username !== authStore.user.username);
            } else {
                ownedDataStores.value = [];
                sharedDataStores.value = [];
            }
        } catch (error) {
            ownedDataStores.value = [];
            sharedDataStores.value = [];
        }
    }
    async function addDataStore(storeData) {
        const uiStore = useUiStore();
        const response = await apiClient.post('/api/datastores', storeData);
        ownedDataStores.value.push(response.data);
        uiStore.addNotification('Data store created successfully.', 'success');
    }
    async function updateDataStore(storeData) {
        const uiStore = useUiStore();
        await apiClient.put(`/api/datastores/${storeData.id}`, storeData);
        await fetchDataStores();
        uiStore.addNotification('Data store updated successfully.', 'success');
    }
    async function deleteDataStore(storeId) {
        const uiStore = useUiStore();
        await apiClient.delete(`/api/datastores/${storeId}`);
        ownedDataStores.value = ownedDataStores.value.filter(s => s.id !== storeId);
        uiStore.addNotification('Data store deleted.', 'success');
    }
    async function shareDataStore({ storeId, username, permissionLevel }) {
        const uiStore = useUiStore();
        await apiClient.post(`/api/datastores/${storeId}/share`, { target_username: username, permission_level: permissionLevel });
        uiStore.addNotification(`Store shared with ${username}.`, 'success');
    }

    async function revokeShare(storeId, userId) {
        const uiStore = useUiStore();
        await apiClient.delete(`/api/datastores/${storeId}/share/${userId}`);
        uiStore.addNotification('Sharing revoked successfully.', 'success');
        return true;
    }

    async function getSharedWithList(storeId) {
        const response = await apiClient.get(`/api/datastores/${storeId}/shared-with`);
        return response.data || [];
    }

    async function revectorizeStore({ storeId, vectorizerName }) {
        const uiStore = useUiStore();
        const tasksStore = useTasksStore();
        const formData = new FormData();
        formData.append('vectorizer_name', vectorizerName);
        const response = await apiClient.post(`/api/store/${storeId}/revectorize`, formData);
        const task = response.data;
        uiStore.addNotification(`Task '${task.name}' started.`, 'info', { duration: 7000 });
        tasksStore.fetchTasks();
    }

    async function fetchStoreFiles(storeId) {
        const response = await apiClient.get(`/api/store/${storeId}/files`);
        return response.data || [];
    }

    async function fetchStoreVectorizers(storeId) {
        try {
            const response = await apiClient.get(`/api/store/${storeId}/vectorizers`);
            return response.data || { in_store: [], all_possible: [] };
        } catch (error) {
            return { in_store: [], all_possible: [] };
        }
    }
    
    async function uploadFilesToStore({ storeId, formData }) {
        const uiStore = useUiStore();
        const tasksStore = useTasksStore();
        const response = await apiClient.post(`/api/store/${storeId}/upload-files`, formData);
        const task = response.data;
        uiStore.addNotification(`Task '${task.name}' started.`, 'info', { duration: 7000 });
        tasksStore.fetchTasks();
    }
    async function deleteFileFromStore({ storeId, filename }) {
        const uiStore = useUiStore();
        await apiClient.delete(`/api/store/${storeId}/files/${encodeURIComponent(filename)}`);
        uiStore.addNotification(`File '${filename}' deleted.`, 'success');
    }
    async function fetchPersonalities() {
         try {
            const [ownedRes, publicRes] = await Promise.all([
                apiClient.get('/api/personalities/my'),
                apiClient.get('/api/personalities/public')
            ]);
            userPersonalities.value = Array.isArray(ownedRes.data) ? ownedRes.data : [];
            publicPersonalities.value = Array.isArray(publicRes.data) ? publicRes.data : [];
        } catch (error) {
            userPersonalities.value = [];
            publicPersonalities.value = [];
        }
    }
    async function addPersonality(personalityData) {
        if (personalityData.id) {
            userPersonalities.value.unshift(personalityData);
            return;
        }
        
        const response = await apiClient.post('/api/personalities', personalityData);
        userPersonalities.value.unshift(response.data);
        useUiStore().addNotification('Personality created successfully.', 'success');
    }
    async function updatePersonality(personalityData) {
        if (!personalityData.id) return;
        await apiClient.put(`/api/personalities/${personalityData.id}`, personalityData);
        await fetchPersonalities();
        useUiStore().addNotification('Personality updated successfully.', 'success');
    }
    async function deletePersonality(personalityId) {
        await apiClient.delete(`/api/personalities/${personalityId}`);
        await fetchPersonalities();
        useUiStore().addNotification('Personality deleted.', 'success');
    }

    async function generatePersonalityFromPrompt(prompt) {
        const tasksStore = useTasksStore();
        const response = await apiClient.post('/api/personalities/generate_from_prompt', { prompt });
        tasksStore.addTask(response.data);
        return response.data;
    }

    async function enhancePersonalityPrompt(prompt_text, modification_prompt) {
        const tasksStore = useTasksStore();
        const response = await apiClient.post('/api/personalities/enhance_prompt', { prompt_text, modification_prompt });
        tasksStore.addTask(response.data);
        return { task_id: response.data.id, message: 'Task started.' };
    }
    async function triggerMcpReload() {
        const uiStore = useUiStore();
        const tasksStore = useTasksStore();
        const response = await apiClient.post('/api/mcps/reload');
        const task = response.data;
        uiStore.addNotification(`Task '${task.name}' started.`, 'info');
        tasksStore.fetchTasks();
        await fetchMcpTools();
    }
    async function fetchMcps() {
        try {
            const response = await apiClient.get('/api/mcps');
            const authStore = useAuthStore();
            if (Array.isArray(response.data) && authStore.user) {
                userMcps.value = response.data.filter(mcp => mcp.type === 'user');
                systemMcps.value = response.data.filter(mcp => mcp.type === 'system');
            }
        } catch (error) {
            console.error("Failed to fetch MCPS:", error)
            userMcps.value = [];
            systemMcps.value = [];
        }
    }
    async function addMcp(payload) {
        const response = await apiClient.post('/api/mcps', payload);
        await fetchMcps(); // Refresh the list
        useUiStore().addNotification(`MCP '${response.data.name}' created.`, 'success');
    }
    async function updateMcp(id, payload) {
        const response = await apiClient.put(`/api/mcps/${id}`, payload);
        await fetchMcps(); // Refresh the list
        useUiStore().addNotification(`MCP '${response.data.name}' updated.`, 'success');
    }
    async function deleteMcp(id) {
        await apiClient.delete(`/api/mcps/${id}`);
        await fetchMcps(); // Refresh the list
        useUiStore().addNotification('MCP deleted.', 'success');
    }
    
    async function fetchApps() {
        try {
            const response = await apiClient.get('/api/apps');
            const authStore = useAuthStore();
            if (Array.isArray(response.data) && authStore.user) {
                userApps.value = response.data.filter(app => app.type === 'user');
                systemApps.value = response.data.filter(app => app.type === 'system');
            }
        } catch (error) {
            userApps.value = [];
            systemApps.value = [];
        }
    }
    async function addApp(payload) {
        const response = await apiClient.post('/api/apps', payload);
        await fetchApps(); // Refresh the list
        useUiStore().addNotification(`App '${response.data.name}' created.`, 'success');
    }
    async function updateApp(id, payload) {
        const response = await apiClient.put(`/api/apps/${id}`, payload);
        await fetchApps(); // Refresh the list
        useUiStore().addNotification(`App '${response.data.name}' updated.`, 'success');
    }
    async function deleteApp(id) {
        await apiClient.delete(`/api/apps/${id}`);
        await fetchApps(); // Refresh the list
        useUiStore().addNotification('App deleted.', 'success');
    }


    async function fetchMcpTools() {
        try {
            console.log("Fetching MCP tools...");
            const response = await apiClient.get('/api/mcps/tools');
            console.log("MCP tools fetched:", response.data);
            mcpTools.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error("Failed to fetch MCP tools:", error);
            mcpTools.value = [];
        }
    }
    
    async function refreshMcps() {
        const uiStore = useUiStore();
        uiStore.addNotification('Refreshing MCPs...', 'info');
        try {
            await Promise.all([ fetchMcps(), fetchMcpTools() ]);
            uiStore.addNotification('MCPs refreshed.', 'success');
        }  catch(e) {
            uiStore.addNotification('Failed to refresh MCPs.', 'error');
        }
    }
    async function refreshRags() {
        const uiStore = useUiStore();
        uiStore.addNotification('Refreshing RAG stores...', 'info');
        try {
            await fetchDataStores();
            uiStore.addNotification('RAG stores refreshed.', 'success');
        }  catch(e) {
            uiStore.addNotification('Failed to refresh RAG stores.', 'error');
        }
    }
    function $reset() {
        availableLollmsModels.value = [];
        availableTtiModels.value = []; // NEW
        ownedDataStores.value = [];
        sharedDataStores.value = [];
        userPersonalities.value = [];
        publicPersonalities.value = [];
        userMcps.value = [];
        systemMcps.value = [];
        mcpTools.value = [];
        userApps.value = [];
        systemApps.value = [];
        _languages.value = [];
        apiKeys.value = [];
    }

    return {
        languages, isLoadingLanguages, fetchLanguages,
        availableLollmsModels, ownedDataStores, sharedDataStores,
        userPersonalities, publicPersonalities, userMcps, systemMcps, mcpTools,
        userApps, systemApps,
        isLoadingLollmsModels,
        availableRagStores, availableMcpToolsForSelector, availableLLMModelsGrouped,
        allPersonalities, getPersonalityById,
        
        availableTtiModels, isLoadingTtiModels, availableTtiModelsGrouped, // NEW
        fetchAvailableTtiModels, // NEW

        loadAllInitialData, fetchAvailableLollmsModels, fetchAdminAvailableLollmsModels, fetchDataStores,
        addDataStore, updateDataStore, deleteDataStore, shareDataStore,
        revokeShare, getSharedWithList, revectorizeStore,
        fetchStoreFiles, fetchStoreVectorizers, uploadFilesToStore,
        deleteFileFromStore, fetchPersonalities, addPersonality,
        updatePersonality, deletePersonality, generatePersonalityFromPrompt, enhancePersonalityPrompt,
        fetchMcps, addMcp, updateMcp, deleteMcp,
        fetchMcpTools, triggerMcpReload,
        refreshMcps, refreshRags,
        fetchApps, addApp, updateApp, deleteApp,
        
        apiKeys,
        fetchApiKeys, 
        addApiKey,
        deleteMultipleApiKeys, deleteSingleApiKey,

        handleServiceStatusUpdate,

        $reset
    };
});