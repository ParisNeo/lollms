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
        const found = notebooks.value.find(n => n.id === id);
        if(found) {
             activeNotebook.value = found;
             if (!activeNotebook.value.tabs) activeNotebook.value.tabs = [];
        }
        await fetchNotebooks();
        const updated = notebooks.value.find(n => n.id === id);
        if (updated) {
            activeNotebook.value = updated;
            if (!activeNotebook.value.tabs) activeNotebook.value.tabs = [];
        } else {
            activeNotebook.value = null;
        }
    }

    async function saveActive() {
        if (!activeNotebook.value) return;
        try {
            const res = await apiClient.put(`/api/notebooks/${activeNotebook.value.id}`, {
                title: activeNotebook.value.title,
                content: activeNotebook.value.content,
                artefacts: activeNotebook.value.artefacts,
                tabs: activeNotebook.value.tabs
            });
            activeNotebook.value = res.data;
            const idx = notebooks.value.findIndex(n => n.id === res.data.id);
            if (idx !== -1) notebooks.value[idx] = res.data;
        } catch (e) {
            uiStore.addNotification("Failed to save notebook.", "error");
        }
    }


    async function uploadSource(file, useDocling = false) {
        if (!activeNotebook.value) return;
        const fd = new FormData();
        fd.append('file', file);
        if (useDocling) {
            fd.append('use_docling', 'true');
        }
        try {
            await apiClient.post(`/api/notebooks/${activeNotebook.value.id}/upload`, fd);
            await fetchNotebooks();
            activeNotebook.value = notebooks.value.find(n => n.id === activeNotebook.value.id);
            uiStore.addNotification(`Uploaded ${file.name}`, 'success');
        } catch (e) {
            uiStore.addNotification(`Upload failed: ${file.name}. ${e.message}`, 'error');
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
            uiStore.addNotification(`Scraping task started for ${url}`, 'info');
        } catch (e) {
            uiStore.addNotification(`Scrape request failed: ${e.message}`, 'error');
        }
    }

    async function processWithAi(prompt, inputTabIds, outputType, targetTabId = null, skipLlm = false) {
        if (!activeNotebook.value) return;
        try {
            const res = await apiClient.post(`/api/notebooks/${activeNotebook.value.id}/process`, {
                prompt,
                input_tab_ids: inputTabIds,
                output_type: outputType,
                target_tab_id: targetTabId,
                skip_llm: skipLlm
            });
            uiStore.addNotification(`AI processing (${outputType}) started.`, "info");
        } catch (e) {
            uiStore.addNotification("Failed to start AI processing.", "error");
        }
    }

    async function generateTitle() {
        if (!activeNotebook.value) return;
        try {
            uiStore.addNotification("Generating title...", "info");
            const res = await apiClient.post(`/api/notebooks/${activeNotebook.value.id}/generate_title`);
            activeNotebook.value.title = res.data.title;
            uiStore.addNotification("Title updated.", "success");
            const idx = notebooks.value.findIndex(n => n.id === activeNotebook.value.id);
            if (idx !== -1) notebooks.value[idx].title = res.data.title;
        } catch (e) {
            uiStore.addNotification("Failed to generate title.", "error");
        }
    }
    
    async function describeImage(file) {
        if (!activeNotebook.value) return;
        const fd = new FormData();
        fd.append('file', file);
        try {
            const res = await apiClient.post(`/api/notebooks/${activeNotebook.value.id}/describe_image`, fd);
            return res.data.description;
        } catch (e) {
            uiStore.addNotification(`Failed to describe image: ${e.message}`, 'error');
            throw e;
        }
    }

    async function describeAsset(filename) {
        if (!activeNotebook.value) return;
        try {
            const res = await apiClient.post(`/api/notebooks/${activeNotebook.value.id}/describe_asset`, { filename });
            return res.data.description;
        } catch (e) {
            uiStore.addNotification(`Failed to describe asset: ${e.message}`, 'error');
            throw e;
        }
    }
    
    function addTab(type = 'markdown') {
        if (!activeNotebook.value) return;
        const newTab = {
            id: crypto.randomUUID(),
            title: "New Tab",
            type: type,
            content: "",
            images: []
        };
        activeNotebook.value.tabs.push(newTab);
        saveActive();
    }
    
    function removeTab(tabId) {
        if (!activeNotebook.value) return;
        const index = activeNotebook.value.tabs.findIndex(t => t.id === tabId);
        if (index !== -1) {
            activeNotebook.value.tabs.splice(index, 1);
            saveActive();
        }
    }

    async function createNotebook(title = 'New Research') {
        try {
            const res = await apiClient.post('/api/notebooks', { title, content: '' });
            await fetchNotebooks();
            return res.data;
        } catch (e) {
            uiStore.addNotification("Failed to create notebook.", "error");
            throw e;
        }
    }

    async function generateNotebookStructure(payload) {
        const res = await apiClient.post('/api/notebooks/structure', payload);
        return res.data;
    }

    async function createStructuredNotebook(payload) {
        const res = await apiClient.post('/api/notebooks', payload);
        await fetchNotebooks();
        return res.data;
    }

    async function deleteNotebook(id) {
        try {
            await apiClient.delete(`/api/notebooks/${id}`);
            notebooks.value = notebooks.value.filter(n => n.id !== id);
            if (activeNotebook.value && activeNotebook.value.id === id) {
                activeNotebook.value = null;
            }
            uiStore.addNotification("Notebook deleted.", "success");
        } catch (e) {
            uiStore.addNotification("Failed to delete notebook.", "error");
            throw e;
        }
    }

    function $reset() {
        notebooks.value = [];
        activeNotebook.value = null;
    }

    return { 
        notebooks, activeNotebook, isLoading, 
        fetchNotebooks, selectNotebook, saveActive, uploadSource, createTextArtefact, scrapeUrl, processWithAi, generateTitle,
        describeImage, describeAsset,
        addTab, removeTab,
        createNotebook, deleteNotebook, 
        generateNotebookStructure, createStructuredNotebook,
        $reset 
    };
});
