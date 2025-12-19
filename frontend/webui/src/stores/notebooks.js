import { defineStore } from 'pinia';
import { ref } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useTasksStore } from './tasks';

export const useNotebookStore = defineStore('notebooks', () => {
    const notebooks = ref([]);
    const activeNotebook = ref(null);
    const isLoading = ref(false);
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();

    async function fetchNotebooks() {
        isLoading.value = true;
        try {
            const res = await apiClient.get('/api/notebooks');
            notebooks.value = res.data;
        } finally {
            isLoading.value = false;
        }
    }

    async function selectNotebook(id) {
        // Optimistically set active notebook if available in list
        const found = notebooks.value.find(n => n.id === id);
        if(found) {
             activeNotebook.value = found;
        }
        // Then refresh list to ensure we have latest data
        await fetchNotebooks();
        activeNotebook.value = notebooks.value.find(n => n.id === id) || null;
    }

    async function saveActive() {
        if (!activeNotebook.value) return;
        try {
            const res = await apiClient.put(`/api/notebooks/${activeNotebook.value.id}`, {
                title: activeNotebook.value.title,
                content: activeNotebook.value.content,
                artefacts: activeNotebook.value.artefacts
            });
            activeNotebook.value = res.data;
            // Update list entry
            const idx = notebooks.value.findIndex(n => n.id === res.data.id);
            if (idx !== -1) notebooks.value[idx] = res.data;
        } catch (e) {
            uiStore.addNotification("Failed to save notebook.", "error");
        }
    }

    async function uploadSource(file) {
        if (!activeNotebook.value) return;
        const fd = new FormData();
        fd.append('file', file);
        try {
            await apiClient.post(`/api/notebooks/${activeNotebook.value.id}/upload`, fd);
            await fetchNotebooks(); // Refresh all to get updated artefacts list
            // Re-select active notebook to update view
            activeNotebook.value = notebooks.value.find(n => n.id === activeNotebook.value.id);
            uiStore.addNotification(`Uploaded ${file.name}`, 'success');
        } catch (e) {
            uiStore.addNotification(`Upload failed: ${file.name}. ${e.message}`, 'error');
            console.error(e);
        }
    }
    
    async function createTextArtefact(title, content) {
        if (!activeNotebook.value) return;
        try {
            await apiClient.post(`/api/notebooks/${activeNotebook.value.id}/artefact`, {
                title,
                content
            });
            await fetchNotebooks();
            activeNotebook.value = notebooks.value.find(n => n.id === activeNotebook.value.id);
            uiStore.addNotification(`Saved "${title}" as source.`, 'success');
        } catch(e) {
            uiStore.addNotification(`Failed to save source: ${e.message}`, 'error');
        }
    }
    
    async function scrapeUrl(url) {
        if (!activeNotebook.value) return;
        try {
            const res = await apiClient.post(`/api/notebooks/${activeNotebook.value.id}/scrape`, { url });
            tasksStore.addTask(res.data);
            uiStore.addNotification(`Scraping task started for ${url}`, 'info');
        } catch (e) {
            uiStore.addNotification(`Scrape request failed: ${e.message}`, 'error');
        }
    }

    async function processWithAi(prompt) {
        if (!activeNotebook.value) return;
        try {
            const fd = new FormData();
            fd.append('prompt', prompt);
            const res = await apiClient.post(`/api/notebooks/${activeNotebook.value.id}/process`, fd);
            tasksStore.addTask(res.data);
            uiStore.addNotification("AI processing started.", "info");
        } catch (e) {
            uiStore.addNotification("Failed to start AI processing.", "error");
        }
    }

    function $reset() {
        notebooks.value = [];
        activeNotebook.value = null;
    }

    return { 
        notebooks, activeNotebook, isLoading, 
        fetchNotebooks, selectNotebook, saveActive, uploadSource, createTextArtefact, scrapeUrl, processWithAi,
        $reset 
    };
});
