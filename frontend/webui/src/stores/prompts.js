import { defineStore } from 'pinia';
import { ref } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const usePromptsStore = defineStore('prompts', () => {
    const uiStore = useUiStore();

    const savedPrompts = ref([]);
    const isLoading = ref(false);

    async function fetchPrompts() {
        isLoading.value = true;
        try {
            const response = await apiClient.get('/api/prompts');
            savedPrompts.value = response.data;
        } catch (error) {
            console.error("Failed to fetch saved prompts:", error);
            savedPrompts.value = [];
        } finally {
            isLoading.value = false;
        }
    }

    async function savePrompt(name, content) {
        try {
            const response = await apiClient.post('/api/prompts', { name, content });
            savedPrompts.value.push(response.data);
            savedPrompts.value.sort((a, b) => a.name.localeCompare(b.name));
            uiStore.addNotification('Prompt saved successfully!', 'success');
            return response.data;
        } catch (error) {
            throw error;
        }
    }

    async function updatePrompt(id, name, content) {
        try {
            const response = await apiClient.put(`/api/prompts/${id}`, { name, content });
            const index = savedPrompts.value.findIndex(p => p.id === id);
            if (index !== -1) {
                savedPrompts.value[index] = response.data;
                savedPrompts.value.sort((a, b) => a.name.localeCompare(b.name));
            }
            uiStore.addNotification('Prompt updated successfully!', 'success');
            return response.data;
        } catch (error) {
            throw error;
        }
    }

    async function deletePrompt(id) {
        try {
            await apiClient.delete(`/api/prompts/${id}`);
            savedPrompts.value = savedPrompts.value.filter(p => p.id !== id);
            uiStore.addNotification('Prompt deleted.', 'success');
        } catch (error) {
            throw error;
        }
    }

    async function sharePrompt(prompt_content, target_username) {
        try {
            const response = await apiClient.post('/api/prompts/share', { prompt_content, target_username });
            uiStore.addNotification(response.data.message || 'Prompt shared successfully!', 'success');
            return true;
        } catch (error) {
            return false;
        }
    }

    return {
        savedPrompts,
        isLoading,
        fetchPrompts,
        savePrompt,
        updatePrompt,
        deletePrompt,
        sharePrompt,
    };
});