import { defineStore } from 'pinia';
import { ref } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import useEventBus from '../services/eventBus';

export const useMemoriesStore = defineStore('memories', () => {
    const memories = ref([]);
    const isLoading = ref(false);
    const { emit } = useEventBus();

    async function fetchMemories() {
        isLoading.value = true;
        try {
            const response = await apiClient.get('/api/memories');
            memories.value = response.data;
        } catch (error) {
            console.error("Failed to fetch memories:", error);
            memories.value = [];
        } finally {
            isLoading.value = false;
        }
    }

    async function addMemory(memoryData) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.post('/api/memories', memoryData);
            memories.value.unshift(response.data);
            emit('memories:updated');
            uiStore.addNotification('Memory created successfully.', 'success');
        } catch (error) {
            console.error("Failed to add memory:", error);
        }
    }
    
    async function updateMemory(memoryId, memoryData) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.put(`/api/memories/${memoryId}`, memoryData);
            const index = memories.value.findIndex(m => m.id === memoryId);
            if (index !== -1) {
                memories.value[index] = response.data;
            }
            emit('memories:updated');
            uiStore.addNotification('Memory updated successfully.', 'success');
        } catch (error) {
            console.error("Failed to update memory:", error);
        }
    }

    async function deleteMemory(memoryId) {
        const uiStore = useUiStore();
        try {
            await apiClient.delete(`/api/memories/${memoryId}`);
            
            // Optimistic update
            memories.value = memories.value.filter(m => m.id !== memoryId);
            
            // Re-fetch to ensure sync with server
            await fetchMemories();
            
            emit('memories:updated');
            uiStore.addNotification('Memory deleted.', 'success');
        } catch (error) {
            console.error("Failed to delete memory:", error);
            uiStore.addNotification('Failed to delete memory.', 'error');
            // Re-fetch to restore state if delete failed partially or list is out of sync
            await fetchMemories();
        }
    }
    
    function $reset() {
        memories.value = [];
        isLoading.value = false;
    }

    return {
        memories,
        isLoading,
        fetchMemories,
        addMemory,
        updateMemory,
        deleteMemory,
        $reset
    };
});
