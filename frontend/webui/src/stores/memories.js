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
            memories.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error("Failed to fetch multi-layer memories:", error);
            memories.value = [];
        } finally {
            isLoading.value = false;
        }
    }

    async function addMemory(content, importance = 0.9, tags = null) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.post('/api/memories', { content, importance, tags });
            memories.value.unshift(response.data);
            emit('memories:updated');
            uiStore.addNotification('Cognitive memory created successfully.', 'success');
            await fetchMemories();
        } catch (error) {
            console.error("Failed to add memory:", error);
        }
    }

    async function updateMemory(memoryId, { content, importance, level }) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.put(`/api/memories/${memoryId}`, { content, importance, level });
            emit('memories:updated');
            uiStore.addNotification('Cognitive memory level/weight adjusted.', 'success');
            await fetchMemories();
        } catch (error) {
            console.error("Failed to update memory:", error);
        }
    }

    async function deleteMemory(memoryId) {
        const uiStore = useUiStore();
        try {
            await apiClient.delete(`/api/memories/${memoryId}`);
            emit('memories:updated');
            uiStore.addNotification('Cognitive memory forgotten.', 'success');
            await fetchMemories();
        } catch (error) {
            console.error("Failed to delete memory:", error);
            uiStore.addNotification('Failed to forget memory.', 'error');
            await fetchMemories();
        }
    }

    async function triggerDream() {
        const uiStore = useUiStore();
        uiStore.addNotification('Consolidating memories & Dreaming...', 'info');
        try {
            const response = await apiClient.post('/api/memories/dream');
            emit('memories:updated');
            uiStore.addNotification('Subconscious dream consolidation complete!', 'success');
            await fetchMemories();
            return response.data.report;
        } catch (error) {
            console.error("Dream consolidation failed:", error);
            uiStore.addNotification('Dream execution failed.', 'error');
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
        triggerDream,
        $reset
    };
});
