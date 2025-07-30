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

    async function exportPrompts() {
        try {
            const response = await apiClient.get('/api/prompts/export');
            const dataStr = JSON.stringify(response.data, null, 2);
            const blob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'lollms_prompts_export.json';
            a.click();
            URL.revokeObjectURL(url);
            uiStore.addNotification('Prompts exported successfully!', 'success');
        } catch (error) {
            console.error("Failed to export prompts:", error);
        }
    }

    async function importPrompts(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = async (event) => {
                try {
                    const importData = JSON.parse(event.target.result);
                    if (!importData || !Array.isArray(importData.prompts)) {
                        throw new Error("Invalid import file format.");
                    }
                    const response = await apiClient.post('/api/prompts/import', importData);
                    await fetchPrompts(); // Refresh list
                    uiStore.addNotification(response.data.message, 'success');
                    resolve();
                } catch (error) {
                    const message = error.response?.data?.detail || error.message || 'Failed to import prompts.';
                    uiStore.addNotification(message, 'error');
                    reject(error);
                }
            };
            reader.onerror = (error) => {
                uiStore.addNotification('Failed to read import file.', 'error');
                reject(error);
            };
            reader.readAsText(file);
        });
    }

    return {
        savedPrompts,
        isLoading,
        fetchPrompts,
        savePrompt,
        updatePrompt,
        deletePrompt,
        sharePrompt,
        exportPrompts,
        importPrompts,
    };
});