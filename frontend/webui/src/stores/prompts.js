import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useTasksStore } from './tasks';

export const usePromptsStore = defineStore('prompts', () => {
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();

    const userPrompts = ref([]);
    const systemPrompts = ref([]);
    const lollmsPrompts = ref([]);
    const isLoading = ref(false);

    const systemPromptsByZooCategory = computed(() => {
        if (!Array.isArray(systemPrompts.value)) return {};
        const categories = {};
        systemPrompts.value.forEach(prompt => {
            const category = prompt.category || 'Uncategorized';
            if (!categories[category]) {
                categories[category] = [];
            }
            categories[category].push(prompt);
        });
        // Sort prompts within each category
        for (const category in categories) {
            categories[category].sort((a, b) => a.name.localeCompare(b.name));
        }
        // Sort categories
        const sortedCategories = {};
        Object.keys(categories).sort().forEach(key => {
            sortedCategories[key] = categories[key];
        });
        return sortedCategories;
    });

    const userPromptsByCategory = computed(() => {
        if (!Array.isArray(userPrompts.value)) return {};
        const categories = {};
        userPrompts.value.forEach(prompt => {
            const category = prompt.category || 'Uncategorized';
            if (!categories[category]) {
                categories[category] = [];
            }
            categories[category].push(prompt);
        });
        // Sort prompts within each category
        for (const category in categories) {
            categories[category].sort((a, b) => a.name.localeCompare(b.name));
        }
        // Sort categories
        const sortedCategories = {};
        Object.keys(categories).sort().forEach(key => {
            sortedCategories[key] = categories[key];
        });
        return sortedCategories;
    });

    async function fetchPrompts() {
        isLoading.value = true;
        try {
            const response = await apiClient.get('/api/prompts');
            userPrompts.value = response.data.user_prompts || [];
            systemPrompts.value = response.data.system_prompts || [];
            
            lollmsPrompts.value = [
                { id: 'default-summarize', name: 'Summarize', content: 'Provide a concise summary of the key points in the following text.' },
                { id: 'default-mindmap', name: 'To Mindmap', content: 'Convert the following text into a MermaidJS mindmap format. Start with the central theme and branch out to main ideas and sub-points.' },
                { id: 'default-bullets', name: 'To Bullet Points', content: 'List the main ideas from the following text as a clear, nested bullet point list.' },
                { id: 'default-translate', name: 'Translate', content: 'Translate the following text to @<language>@.\n\n@<language>@\ntitle: Language to translate to\ntype: str\noptions: English, French, Spanish, German, Italian, Arabic, Chinese, Japanese, Russian\n@</language>@' },
            ];
        } catch (error) {
            console.error("Failed to fetch prompts:", error);
            userPrompts.value = [];
            systemPrompts.value = [];
        } finally {
            isLoading.value = false;
        }
    }

    async function createPrompt(promptData) {
        try {
            const response = await apiClient.post('/api/prompts', promptData);
            userPrompts.value.push(response.data);
            userPrompts.value.sort((a, b) => a.name.localeCompare(b.name));
            uiStore.addNotification('Prompt saved successfully!', 'success');
            return response.data;
        } catch (error) {
            throw error;
        }
    }

    async function updatePrompt(id, promptData) {
        try {
            const response = await apiClient.put(`/api/prompts/${id}`, promptData);
            const index = userPrompts.value.findIndex(p => p.id === id);
            if (index !== -1) {
                userPrompts.value[index] = response.data;
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
            userPrompts.value = userPrompts.value.filter(p => p.id !== id);
            uiStore.addNotification('Prompt deleted.', 'success');
        } catch (error) {
            throw error;
        }
    }

    async function generatePrompt(prompt) {
        try {
            const response = await apiClient.post('/api/prompts/generate-with-ai', { prompt });
            tasksStore.addTask(response.data);
            uiStore.addNotification(`Task '${response.data.name}' started.`, 'info');
            return response.data;
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
        userPrompts,
        systemPrompts,
        lollmsPrompts,
        isLoading,
        systemPromptsByZooCategory,
        userPromptsByCategory,
        fetchPrompts,
        createPrompt,
        updatePrompt,
        deletePrompt,
        generatePrompt,
        sharePrompt,
        exportPrompts,
        importPrompts,
    };
});