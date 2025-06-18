import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useAuthStore } from './auth';
import { useUiStore } from './ui';

export const useDataStore = defineStore('data', () => {
    // STATE
    const availableLollmsModels = ref([]);
    const ownedDataStores = ref([]);
    const sharedDataStores = ref([]);
    const userPersonalities = ref([]);
    const publicPersonalities = ref([]);
    const userMcps = ref([]);
    const mcpTools = ref([]);

    // GETTERS
    const availableRagStores = computed(() => {
        const authStore = useAuthStore();
        if (!authStore.user) return [];

        const owned = ownedDataStores.value.map(ds => ({
            id: ds.id,
            name: `${ds.name} (You)`
        }));
        const shared = sharedDataStores.value.map(ds => ({
            id: ds.id,
            name: `${ds.name} (from ${ds.owner_username})`
        }));
        
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

        return Object.entries(grouped)
            .map(([mcpName, tools]) => ({
                isGroup: true,
                label: mcpName,
                items: tools.sort((a, b) => a.name.localeCompare(b.name))
            }))
            .sort((a,b) => a.label.localeCompare(b.label));
    });

    // ACTIONS

    async function loadAllInitialData() {
        await Promise.all([
            fetchAvailableLollmsModels(),
            fetchDataStores(),
            fetchPersonalities(),
            fetchMcps(),
            fetchMcpTools()
        ]);
    }

    async function fetchAvailableLollmsModels() {
        try {
            const response = await apiClient.get('/api/config/lollms-models');
            availableLollmsModels.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error("Failed to load LLM models:", error);
            availableLollmsModels.value = [];
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
            console.error("Failed to load data stores:", error);
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
            console.error("Failed to add data store:", error);
            throw error;
        }
    }

    async function updateDataStore(storeData) {
        const uiStore = useUiStore();
        try {
            await apiClient.put(`/api/datastores/${storeData.id}`, storeData);
            await fetchDataStores(); // Refetch to get updated list
            uiStore.addNotification('Data store updated successfully.', 'success');
        } catch(error) {
            console.error("Failed to update data store:", error);
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
            console.error("Failed to delete data store:", error);
            throw error;
        }
    }
    
    async function shareDataStore({ storeId, username }) {
        const uiStore = useUiStore();
        try {
            await apiClient.post(`/api/datastores/${storeId}/share`, { target_username: username, permission_level: "read_query" });
            uiStore.addNotification(`Store shared with ${username}.`, 'success');
        } catch(error) {
            console.error("Failed to share data store:", error);
            throw error;
        }
    }
    
    async function fetchStoreFiles(storeId) {
        try {
            const response = await apiClient.get(`/api/store/${storeId}/files`);
            return response.data || [];
        } catch(error) {
            console.error(`Failed to fetch files for store ${storeId}:`, error);
            throw error;
        }
    }

    async function fetchStoreVectorizers(storeId) {
        try {
            const response = await apiClient.get(`/api/store/${storeId}/vectorizers`);
            return response.data || [];
        } catch (error) {
            console.error(`Failed to fetch vectorizers for store ${storeId}:`, error);
            return [];
        }
    }

    async function uploadFilesToStore({ storeId, formData }) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.post(`/api/store/${storeId}/upload-files`, formData);
            if (response.status === 207) { // Partial success
                uiStore.addNotification(response.data.message || 'Upload completed with some errors.', 'warning');
            } else {
                uiStore.addNotification(response.data.message || 'Files uploaded successfully.', 'success');
            }
        } catch(error) {
            console.error("File upload failed:", error);
            throw error;
        }
    }

    async function deleteFileFromStore({ storeId, filename }) {
        const uiStore = useUiStore();
        try {
            await apiClient.delete(`/api/store/${storeId}/files/${encodeURIComponent(filename)}`);
            uiStore.addNotification(`File '${filename}' deleted.`, 'success');
        } catch(error) {
            console.error("Failed to delete file:", error);
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
            console.error("Failed to load personalities:", error);
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
            console.error("Failed to create personality:", error);
            throw error;
        }
    }

    async function updatePersonality(personalityData) {
        if (!personalityData.id) {
            console.error("Update failed: Personality ID is missing.");
            return;
        }
        try {
            await apiClient.put(`/api/personalities/${personalityData.id}`, personalityData);
            await fetchPersonalities();
            useUiStore().addNotification('Personality updated successfully.', 'success');
        } catch (error) {
            console.error("Failed to update personality:", error);
            throw error;
        }
    }
    
    async function deletePersonality(personalityId) {
        try {
            await apiClient.delete(`/api/personalities/${personalityId}`);
            await fetchPersonalities();
            useUiStore().addNotification('Personality deleted.', 'success');
        } catch (error) {
            console.error("Failed to delete personality:", error);
            throw error;
        }
    }

    // --- MCP Actions ---

    async function triggerMcpReload() {
        const uiStore = useUiStore();
        uiStore.addNotification('Reloading MCP services...', 'info');
        try {
            await apiClient.post('/api/mcps/reload');
            await fetchMcpTools(); // Also refresh the tool list
            uiStore.addNotification('MCP services reloaded.', 'success');
        } catch (error) {
            uiStore.addNotification('Failed to reload mcp services.', 'fail');
            console.error("Failed to trigger MCP reload:", error);
        }
    }

    async function fetchMcps() {
        try {
            const response = await apiClient.get('/api/mcps');
            userMcps.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error("Failed to load MCP servers:", error);
            userMcps.value = [];
        }
    }

    async function addMcp(mcpData) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.post('/api/mcps/personal', mcpData);
            userMcps.value.push(response.data);
            uiStore.addNotification('MCP server added successfully.', 'success');
            await triggerMcpReload();
        } catch (error) {
            console.error("Failed to add MCP server:", error);
            throw error;
        }
    }

    async function updateMcp(mcpId, mcpData) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.put(`/api/mcps/${mcpId}`, mcpData);
            userMcps.value = userMcps.value.map(mcp => 
                mcp.id === mcpId ? response.data : mcp
            );
            uiStore.addNotification('MCP server updated successfully.', 'success');
            await triggerMcpReload();
        } catch (error) {
            console.error("Failed to update MCP server:", error);
            throw error;
        }
    }

    async function deleteMcp(mcpId) {
        const uiStore = useUiStore();
        try {
            await apiClient.delete(`/api/mcps/${mcpId}`);
            userMcps.value = userMcps.value.filter(m => m.id !== mcpId);
            uiStore.addNotification('MCP server removed.', 'success');
            await triggerMcpReload();
        } catch (error) {
            console.error("Failed to delete MCP server:", error);
            throw error;
        }
    }

    async function fetchMcpTools() {
        try {
            const response = await apiClient.get('/api/mcps/tools');
            mcpTools.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error("Failed to load MCP tools:", error);
            mcpTools.value = [];
        }
    }

    return {
        // State
        availableLollmsModels,
        ownedDataStores,
        sharedDataStores,
        userPersonalities,
        publicPersonalities,
        userMcps,
        mcpTools,
        
        // Getters
        availableRagStores,
        availableMcpToolsForSelector,

        // Actions
        loadAllInitialData,
        fetchAvailableLollmsModels,
        fetchDataStores,
        addDataStore,
        updateDataStore,
        deleteDataStore,
        shareDataStore,
        fetchStoreFiles,
        fetchStoreVectorizers,
        uploadFilesToStore,
        deleteFileFromStore,
        fetchPersonalities,
        addPersonality,
        updatePersonality,
        deletePersonality,
        fetchMcps,
        addMcp,
        updateMcp,
        deleteMcp,
        fetchMcpTools,
        triggerMcpReload,
    };
});
