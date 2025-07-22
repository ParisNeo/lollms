import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useAuthStore } from './auth';
import { useUiStore } from './ui';
import { useAdminStore } from './admin';

export const useDataStore = defineStore('data', () => {
    const availableLollmsModels = ref([]);
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
    const availableLollmsModelsGrouped = computed(() => {
        if (!Array.isArray(availableLollmsModels.value) || availableLollmsModels.value.length === 0) {
            return [];
        }
        const grouped = availableLollmsModels.value.reduce((acc, model) => {
            if (!model || typeof model.id !== 'string') {
                console.warn("Skipping invalid model entry in availableLollmsModels:", model);
                return acc;
            }
            const [bindingAlias, ...modelNameParts] = model.id.split('/');
            const modelName = modelNameParts.join('/');
            if (!acc[bindingAlias]) {
                acc[bindingAlias] = { isGroup: true, label: bindingAlias, items: [] };
            }
            acc[bindingAlias].items.push({ id: model.id, name: modelName || bindingAlias });
            return acc;
        }, {});
        Object.values(grouped).forEach(group => {
            group.items.sort((a, b) => a.name.localeCompare(b.name));
        });
        return Object.values(grouped).sort((a, b) => a.label.localeCompare(b.label));
    });
    const allPersonalities = computed(() => [...userPersonalities.value, ...publicPersonalities.value]);
    const getPersonalityById = computed(() => {
        return (id) => allPersonalities.value.find(p => p.id === id);
    });

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
            // This is expected if the service is disabled, so we don't show a notification unless it's another error.
            if (error.response?.status !== 403) {
                useUiStore().addNotification('Could not fetch API keys.', 'error');
            }
            console.warn("API keys could not be fetched (this is normal if the service is disabled).");
            apiKeys.value = [];
        }
    }

    async function addApiKey(alias) {
        try {
            const response = await apiClient.post('/api/api-keys', { alias });
            await fetchApiKeys();
            return response.data;
        } catch (error) {
            throw error;
        }
    }


    async function deleteSingleApiKey(keyId) {
        const uiStore = useUiStore();
        try {
            await apiClient.delete(`/api/api-keys/${keyId}`);
            apiKeys.value = apiKeys.value.filter(key => key.id !== keyId);
            uiStore.addNotification('API Key deleted successfully.', 'success');
        } catch (error) {
            throw error;
        }
    }
    
    async function deleteMultipleApiKeys(keyIds) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.delete('/api/api-keys', { data: { key_ids: keyIds } });
            apiKeys.value = apiKeys.value.filter(key => !keyIds.includes(key.id));
            uiStore.addNotification(response.data.message || 'Selected keys deleted.', 'success');
        } catch (error) {
            throw error;
        }
    }

    async function loadAllInitialData() {
        // Run all fetch operations, but catch individual errors so one failure doesn't stop the others.
        const promises = [
            fetchAvailableLollmsModels().catch(e => console.error("Error fetching models:", e)),
            fetchDataStores().catch(e => console.error("Error fetching data stores:", e)),
            fetchPersonalities().catch(e => console.error("Error fetching personalities:", e)),
            fetchMcps().catch(e => console.error("Error fetching MCPs:", e)),
            fetchMcpTools().catch(e => console.error("Error fetching MCP tools:", e)),
            fetchApps().catch(e => console.error("Error fetching apps:", e)),
            fetchLanguages().catch(e => console.error("Error fetching languages:", e)),
            fetchApiKeys().catch(e => console.error("Error fetching API keys:", e))
        ];
        
        // Wait for all of them to settle, regardless of success or failure.
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
        try {
            const response = await apiClient.post('/api/datastores', storeData);
            ownedDataStores.value.push(response.data);
            uiStore.addNotification('Data store created successfully.', 'success');
        } catch(error) {
            throw error;
        }
    }
    async function updateDataStore(storeData) {
        const uiStore = useUiStore();
        try {
            await apiClient.put(`/api/datastores/${storeData.id}`, storeData);
            await fetchDataStores();
            uiStore.addNotification('Data store updated successfully.', 'success');
        } catch(error) {
            throw error;
        }
    }
    async function deleteDataStore(storeId) {
        const uiStore = useUiStore();
        try {
            await apiClient.delete(`/api/datastores/${storeId}`);
            ownedDataStores.value = ownedDataStores.value.filter(s => s.id !== storeId);
            uiStore.addNotification('Data store deleted.', 'success');
        } catch(error) {
            throw error;
        }
    }
    async function shareDataStore({ storeId, username, permissionLevel }) {
        const uiStore = useUiStore();
        try {
            await apiClient.post(`/api/datastores/${storeId}/share`, { 
                target_username: username, 
                permission_level: permissionLevel 
            });
            uiStore.addNotification(`Store shared with ${username}.`, 'success');
        } catch(error) {
            throw error;
        }
    }

    async function revokeShare(storeId, userId) {
        const uiStore = useUiStore();
        try {
            await apiClient.delete(`/api/datastores/${storeId}/share/${userId}`);
            uiStore.addNotification('Sharing revoked successfully.', 'success');
            return true;
        } catch (error) {
            throw error;
        }
    }

    async function getSharedWithList(storeId) {
        try {
            const response = await apiClient.get(`/api/datastores/${storeId}/shared-with`);
            return response.data || [];
        } catch (error) {
            return [];
        }
    }

    async function revectorizeStore({ storeId, vectorizerName }) {
        const uiStore = useUiStore();
        try {
            const formData = new FormData();
            formData.append('vectorizer_name', vectorizerName);
            const response = await apiClient.post(`/api/store/${storeId}/revectorize`, formData);
            uiStore.addNotification(response.data.message, 'info', { duration: 5000 });
        } catch (error) {
            throw error;
        }
    }

    async function fetchStoreFiles(storeId) {
        try {
            const response = await apiClient.get(`/api/store/${storeId}/files`);
            return response.data || [];
        } catch(error) {
            throw error;
        }
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
        const adminStore = useAdminStore();
        try {
            const response = await apiClient.post(`/api/store/${storeId}/upload-files`, formData);
            const task = response.data;
            uiStore.addNotification(`Task '${task.name}' started. Check the Admin panel for progress.`, 'info', { duration: 7000 });
            adminStore.fetchTasks();
        } catch(error) {
            throw error;
        }
    }
    async function deleteFileFromStore({ storeId, filename }) {
        const uiStore = useUiStore();
        try {
            await apiClient.delete(`/api/store/${storeId}/files/${encodeURIComponent(filename)}`);
            uiStore.addNotification(`File '${filename}' deleted.`, 'success');
        } catch(error) {
            throw error;
        }
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
        try {
            await apiClient.post('/api/personalities', personalityData);
            await fetchPersonalities();
            useUiStore().addNotification('Personality created successfully.', 'success');
        } catch (error) {
            throw error;
        }
    }
    async function updatePersonality(personalityData) {
        if (!personalityData.id) {
            return;
        }
        try {
            await apiClient.put(`/api/personalities/${personalityData.id}`, personalityData);
            await fetchPersonalities();
            useUiStore().addNotification('Personality updated successfully.', 'success');
        } catch (error) {
            throw error;
        }
    }
    async function deletePersonality(personalityId) {
        try {
            await apiClient.delete(`/api/personalities/${personalityId}`);
            await fetchPersonalities();
            useUiStore().addNotification('Personality deleted.', 'success');
        } catch (error) {
            throw error;
        }
    }
    async function triggerMcpReload() {
        const uiStore = useUiStore();
        const adminStore = useAdminStore();
        try {
            const response = await apiClient.post('/api/mcps/reload');
            const task = response.data;
            uiStore.addNotification(`Task '${task.name}' started.`, 'info');
            adminStore.fetchTasks();
            await fetchMcpTools();
        } catch (error) {
            // Handled by interceptor
        }
    }
    async function fetchMcps() {
        try {
            const response = await apiClient.get('/api/mcps');
            userMcps.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            userMcps.value = [];
        }
    }
    async function addMcp(mcpData) {
        const uiStore = useUiStore();
        try {
            await apiClient.post('/api/mcps', mcpData);
            uiStore.addNotification('MCP server added successfully.', 'success');
            await fetchMcps();
            await triggerMcpReload();
        } catch (error) {
            throw error;
        }
    }
    async function updateMcp(mcpId, mcpData) {
        const uiStore = useUiStore();
        try {
            await apiClient.put(`/api/mcps/${mcpId}`, mcpData);
            uiStore.addNotification('MCP server updated successfully.', 'success');
            await fetchMcps();
            await triggerMcpReload();
        } catch (error) {
            throw error;
        }
    }
    async function deleteMcp(mcpId) {
        const uiStore = useUiStore();
        try {
            await apiClient.delete(`/api/mcps/${mcpId}`);
            uiStore.addNotification('MCP server removed.', 'success');
            await fetchMcps();
            await triggerMcpReload();
        } catch (error) {
            throw error;
        }
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
    async function fetchMcpTools() {
        try {
            const response = await apiClient.get('/api/mcps/tools');
            mcpTools.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            mcpTools.value = [];
        }
    }
    async function refreshMcps() {
        const uiStore = useUiStore();
        uiStore.addNotification('Refreshing MCPs...', 'info');
        try {
            await Promise.all([
                fetchMcps(),
                fetchMcpTools()
            ]);
            uiStore.addNotification('MCPs refreshed.', 'success');
        } catch(e) {
            uiStore.addNotification('Failed to refresh MCPs.', 'error');
        }
    }
    async function refreshRags() {
        const uiStore = useUiStore();
        uiStore.addNotification('Refreshing RAG stores...', 'info');
        try {
            await fetchDataStores();
            uiStore.addNotification('RAG stores refreshed.', 'success');
        } catch(e) {
            uiStore.addNotification('Failed to refresh RAG stores.', 'error');
        }
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
    async function addApp(appData) {
        const uiStore = useUiStore();
        try {
            await apiClient.post('/api/apps', appData);
            uiStore.addNotification('App added successfully.', 'success');
            await fetchApps();
        } catch (error) { throw error; }
    }
    async function updateApp(appId, appData) {
        const uiStore = useUiStore();
        try {
            await apiClient.put(`/api/apps/${appId}`, appData);
            uiStore.addNotification('App updated successfully.', 'success');
            await fetchApps();
        } catch (error) { throw error; }
    }
    async function deleteApp(appId) {
        const uiStore = useUiStore();
        const adminStore = useAdminStore();
        try {
            await apiClient.delete(`/api/apps/${appId}`);
            uiStore.addNotification('App removed.', 'success');
            await fetchApps();
            // Also refresh installed apps list in case the deleted app was an installed one.
            if (authStore.isAdmin) {
                adminStore.fetchInstalledApps();
            }
        } catch (error) { throw error; }
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
    function $reset() {
        availableLollmsModels.value = [];
        ownedDataStores.value = [];
        sharedDataStores.value = [];
        userPersonalities.value = [];
        publicPersonalities.value = [];
        userMcps.value = [];
        mcpTools.value = [];
        userApps.value = [];
        systemApps.value = [];
        _languages.value = [];
        apiKeys.value = [];
    }

    return {
        languages, isLoadingLanguages, fetchLanguages,
        availableLollmsModels, ownedDataStores, sharedDataStores,
        userPersonalities, publicPersonalities, userMcps, mcpTools,
        userApps, systemApps,
        isLoadingLollmsModels,
        availableRagStores, availableMcpToolsForSelector, availableLollmsModelsGrouped,
        allPersonalities, getPersonalityById,
        
        loadAllInitialData, fetchAvailableLollmsModels, fetchAdminAvailableLollmsModels, fetchDataStores,
        addDataStore, updateDataStore, deleteDataStore, shareDataStore,
        revokeShare, getSharedWithList, revectorizeStore,
        fetchStoreFiles, fetchStoreVectorizers, uploadFilesToStore,
        deleteFileFromStore, fetchPersonalities, addPersonality,
        updatePersonality, deletePersonality, fetchMcps, addMcp,
        updateMcp, deleteMcp, generateMcpSsoSecret,
        fetchMcpTools, triggerMcpReload,
        refreshMcps, refreshRags,
        fetchApps, addApp, updateApp, deleteApp, generateAppSsoSecret,
        
        apiKeys,
        fetchApiKeys, 
        addApiKey,
        deleteMultipleApiKeys, deleteSingleApiKey,

        $reset
    };
});