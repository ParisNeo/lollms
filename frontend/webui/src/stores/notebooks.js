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
            if (Array.isArray(res.data)) {
                notebooks.value = res.data;
            }
        } finally {
            isLoading.value = false;
        }
    }

    async function searchArxiv(query) {
        try {
            const res = await apiClient.post('/api/notebooks/search/arxiv', { query, max_results: 10 });
            return res.data;
        } catch (e) {
            uiStore.addNotification("Arxiv search failed.", "error");
            throw e;
        }
    }

    async function createStructuredNotebook(payload) {
        const res = await apiClient.post('/api/notebooks', payload);
        const newNb = res.data;
        notebooks.value.unshift(newNb);
        return newNb;
    }

    async function selectNotebook(id) {
        if (!id) {
            activeNotebook.value = null;
            return;
        }
        
        console.log(`[NotebookStore] Fetching notebook: ${id}`);
        isLoading.value = true;
        try {
            const res = await apiClient.get(`/api/notebooks/${id}`);
            
            // Check for both 'id' and '_id' to be safe
            if (res.data && (res.data.id !== undefined || res.data._id !== undefined)) {
                // Ensure the object has a consistent 'id' property for the UI
                if (!res.data.id && res.data._id) res.data.id = res.data._id;
                
                activeNotebook.value = res.data;
                console.log(`[NotebookStore] Successfully loaded: ${res.data.title}`);
                
                // Sync the local list
                const idx = notebooks.value.findIndex(n => (n.id || n._id) === id);
                if (idx !== -1) notebooks.value[idx] = res.data;
            } else {
                console.error("[NotebookStore] Server returned invalid notebook data:", res.data);
                activeNotebook.value = null;
            }
        } catch (e) {
            console.error("[NotebookStore] Error selecting notebook:", e);
            activeNotebook.value = null;
            uiStore.addNotification("Failed to load notebook content.", "error");
        } finally {
            isLoading.value = false;
        }
    }
    
    function setActiveNotebook(notebook) {
        if (notebook && !notebook.id && notebook._id) notebook.id = notebook._id;
        activeNotebook.value = notebook;
    }

    async function saveActive() {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        if (!id) return;

        try {
            const res = await apiClient.put(`/api/notebooks/${id}`, {
                title: activeNotebook.value.title,
                content: activeNotebook.value.content,
                language: activeNotebook.value.language,
                artefacts: activeNotebook.value.artefacts,
                tabs: activeNotebook.value.tabs
            });
            const updated = res.data;
            if (!updated.id && updated._id) updated.id = updated._id;
            
            const idx = notebooks.value.findIndex(n => (n.id || n._id) === id);
            if (idx !== -1) notebooks.value[idx] = updated;
        } catch (e) {
            uiStore.addNotification("Failed to save notebook.", "error");
        }
    }

    async function exportNotebook(format) {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        try {
            uiStore.addNotification(`Preparing ${format.toUpperCase()} export...`, "info");
            const response = await apiClient.get(`/api/notebooks/${id}/export`, {
                params: { format },
                responseType: 'blob'
            });
            
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            const extension = format === 'markdown' ? 'md' : format;
            link.setAttribute('download', `${activeNotebook.value.title || 'notebook'}.${extension}`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            uiStore.addNotification("Export successful.", "success");
        } catch (e) {
            uiStore.addNotification("Export failed.", "error");
        }
    }

    async function generateTitle() {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        try {
            const res = await apiClient.post(`/api/notebooks/${id}/generate_title`);
            activeNotebook.value.title = res.data.title;
            await saveActive();
        } catch (e) {
            uiStore.addNotification("Failed to generate title.", "error");
        }
    }

    async function deleteNotebook(id) {
        try {
            await apiClient.delete(`/api/notebooks/${id}`);
            notebooks.value = notebooks.value.filter(n => (n.id !== id && n._id !== id));
            if ((activeNotebook.value?.id === id || activeNotebook.value?._id === id)) {
                activeNotebook.value = null;
            }
            uiStore.addNotification("Notebook deleted.", "success");
        } catch (e) {
            uiStore.addNotification("Failed to delete notebook.", "error");
        }
    }

    async function uploadSource(file, useDocling = false) {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        const fd = new FormData();
        fd.append('file', file);
        if (useDocling) fd.append('use_docling', 'true');
        try {
            const res = await apiClient.post(`/api/notebooks/${id}/upload`, fd);
            await selectNotebook(id);
            return res.data;
        } catch (e) {
            uiStore.addNotification("Upload failed.", 'error');
            throw e;
        }
    }

    async function importSources(arg1, arg2) {
        let notebookId = activeNotebook.value?.id || activeNotebook.value?._id;
        let payload = arg1;
        if (typeof arg1 === 'string') {
            notebookId = arg1;
            payload = arg2;
        }
        if (!notebookId) return;

        try {
            const res = await apiClient.post(`/api/notebooks/${notebookId}/import_sources`, payload);
            uiStore.addNotification("Knowledge ingestion started.", "info");
            return res.data;
        } catch (e) {
            uiStore.addNotification("Failed to start ingestion.", "error");
            throw e;
        }
    }

    async function createManualArtefact(title, content) {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        try {
            await apiClient.post(`/api/notebooks/${id}/artefact`, { title, content });
            await selectNotebook(id);
            uiStore.addNotification("Manual artefact added.", "success");
        } catch (e) {
            uiStore.addNotification("Failed to add manual artefact.", "error");
        }
    }

    async function updateArtefact(oldFilename, newFilename, newContent) {
        if (!activeNotebook.value) return;
        const artIdx = activeNotebook.value.artefacts.findIndex(a => a.filename === oldFilename);
        if (artIdx !== -1) {
            activeNotebook.value.artefacts[artIdx].filename = newFilename;
            activeNotebook.value.artefacts[artIdx].content = newContent;
            await saveActive();
            uiStore.addNotification("Artefact updated.", "success");
        }
    }

    async function deleteArtefact(filename) {
        if (!activeNotebook.value) return;
        const confirmed = await uiStore.showConfirmation({ title: 'Delete Source', message: `Remove "${filename}"?`, confirmText: 'Delete' });
        if (confirmed.confirmed) {
            activeNotebook.value.artefacts = activeNotebook.value.artefacts.filter(a => a.filename !== filename);
            await saveActive();
        }
    }

    async function describeAsset(filename) {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        try {
            const res = await apiClient.post(`/api/notebooks/${id}/describe_asset`, { filename });
            return res.data.description;
        } catch (e) {
            uiStore.addNotification(`Analysis failed.`, 'error');
            throw e;
        }
    }

    async function deleteGeneratedAsset(type, tabId, slideId = null) {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        try {
            await apiClient.delete(`/api/notebooks/${id}/generated_asset`, {
                params: { type, tab_id: tabId, slide_id: slideId }
            });
            await selectNotebook(id);
            uiStore.addNotification(`${type} deleted.`, "success");
        } catch (e) {
            uiStore.addNotification("Failed to delete asset.", "error");
        }
    }

    async function cancelTask(taskId) {
        try {
            await apiClient.post(`/api/tasks/${taskId}/cancel`);
            return true;
        } catch (e) {
            uiStore.addNotification("Failed to cancel task.", "error");
            return false;
        }
    }

    async function deleteSlideImage(tabId, slideId, imageIndex) {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        try {
            await apiClient.delete(`/api/notebooks/${id}/generated_asset`, {
                params: { type: 'image', tab_id: tabId, slide_id: slideId, image_index: imageIndex }
            });
            await selectNotebook(id);
            uiStore.addNotification("Image version deleted.", "success");
        } catch (e) {
            uiStore.addNotification("Failed to delete image.", "error");
        }
    }

    async function setSlideImageIndex(tabId, slideId, index) {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        try {
            await apiClient.put(`/api/notebooks/${id}/tabs/${tabId}/slides/${slideId}/select_image`, { index });
            const tab = activeNotebook.value.tabs.find(t => t.id === tabId);
            if (tab) {
                try {
                    const content = JSON.parse(tab.content);
                    const slide = content.slides_data.find(s => s.id === slideId);
                    if (slide) {
                        slide.selected_image_index = index;
                        tab.content = JSON.stringify(content);
                    }
                } catch {}
            }
        } catch (e) {
            uiStore.addNotification("Failed to set active image.", "error");
        }
    }

    async function regenerateSlideImage(tabId, slideId, prompt = null, negativePrompt = "") {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        try {
            const res = await apiClient.post(`/api/notebooks/${id}/regenerate_slide_image`, {
                tab_id: tabId, 
                slide_id: slideId, 
                prompt, 
                negative_prompt: negativePrompt
            });
            tasksStore.addTask(res.data);
            uiStore.addNotification("Image regeneration started.", "info");
        } catch (e) {
            uiStore.addNotification("Regeneration failed.", "error");
        }
    }

    async function sendSlideMessage(tabId, slideId, prompt, selectedArtefacts = []) {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        try {
            const res = await apiClient.post(`/api/notebooks/${id}/slide_chat`, {
                prompt, tab_id: tabId, slide_id: slideId, selected_artefacts: selectedArtefacts
            });
            await selectNotebook(id);
            return res.data;
        } catch (e) {
            uiStore.addNotification("Message failed.", "error");
        }
    }

    async function brainstormSlide(topic, layout, selectedArtefacts = [], author = '') {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        try {
            const res = await apiClient.post(`/api/notebooks/${id}/brainstorm`, {
                topic, layout, selected_artefacts: selectedArtefacts, author
            });
            return res.data;
        } catch (e) {
            uiStore.addNotification("Brainstorming failed.", "error");
            throw e;
        }
    }

    async function processWithAi(prompt, inputTabIds, outputType, targetTabId = null, skipLlm = false, selectedArtefacts = [], negativePrompt = "") {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        let finalPrompt = prompt;
        if (['images', 'refine_image', 'generate_scene_image'].includes(outputType)) {
            if (!prompt.includes('|')) finalPrompt = `${prompt}||${negativePrompt}`;
        }
        try {
            await apiClient.post(`/api/notebooks/${id}/process`, {
                prompt: finalPrompt, 
                input_tab_ids: inputTabIds, 
                output_type: outputType,
                target_tab_id: targetTabId, 
                selected_artefacts: selectedArtefacts, 
                skip_llm: skipLlm
            });
            uiStore.addNotification(`Task: ${outputType} started.`, "info");
        } catch (e) {
            uiStore.addNotification("Task failed.", "error");
        }
    }

    async function generateSlideNotes(slideIdx, prompt = "", targetTabId) {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        const fullPrompt = `SLIDE_INDEX:${slideIdx}| ${prompt}`;
        try {
            await apiClient.post(`/api/notebooks/${id}/process`, {
                prompt: fullPrompt, 
                input_tab_ids: [], 
                output_type: 'generate_notes', 
                target_tab_id: targetTabId
            });
            uiStore.addNotification("Notes generation started...", "info");
        } catch (e) {
            uiStore.addNotification("Failed to start notes generation.", "error");
        }
    }

    async function generateSlideAudio(slideIdx, targetTabId) {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        const fullPrompt = `SLIDE_INDEX:${slideIdx}`;
        try {
            await apiClient.post(`/api/notebooks/${id}/process`, {
                prompt: fullPrompt, 
                input_tab_ids: [], 
                output_type: 'generate_audio', 
                target_tab_id: targetTabId
            });
            uiStore.addNotification("Audio generation started...", "info");
        } catch (e) {
            uiStore.addNotification("Failed to start audio generation.", "error");
        }
    }

    async function generateSlideTitle(slideIdx, prompt = "", targetTabId) {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        const fullPrompt = `SLIDE_INDEX:${slideIdx}| ${prompt}`;
        try {
            await apiClient.post(`/api/notebooks/${id}/process`, {
                prompt: fullPrompt, 
                input_tab_ids: [], 
                output_type: 'generate_slide_title', 
                target_tab_id: targetTabId
            });
            uiStore.addNotification("Title generation started...", "info");
        } catch (e) {
            uiStore.addNotification("Failed to start title generation.", "error");
        }
    }

    async function enhancePrompt(prompt, context = "") {
        try {
            const res = await apiClient.post('/api/notebooks/enhance_prompt', { prompt, context });
            return res.data.enhanced_prompt;
        } catch (e) {
            uiStore.addNotification("Prompt enhancement failed.", "error");
            return prompt;
        }
    }

    async function generateSummary() {
        if (!activeNotebook.value) return;
        const id = activeNotebook.value.id || activeNotebook.value._id;
        try {
            const res = await apiClient.post(`/api/notebooks/${id}/generate_summary`);
            uiStore.addNotification("Summary generation started...", "info");
            return res.data; 
        } catch (e) {
            uiStore.addNotification("Summary generation failed.", "error");
            return null;
        }
    }

    function addTab(type = 'markdown') {
        if (!activeNotebook.value) return;
        if (!activeNotebook.value.tabs) activeNotebook.value.tabs = [];
        const newTab = {
            id: (window.crypto && window.crypto.randomUUID) ? window.crypto.randomUUID() : Math.random().toString(36).substring(2) + Date.now().toString(36),
            title: 'New Tab',
            type: type,
            content: '',
            images: []
        };
        activeNotebook.value.tabs.push(newTab);
        saveActive();
        return newTab;
    }

    function removeTab(tabId) {
        if (!activeNotebook.value || !activeNotebook.value.tabs) return;
        activeNotebook.value.tabs = activeNotebook.value.tabs.filter(t => t.id !== tabId);
        saveActive();
    }

    function $reset() {
        notebooks.value = [];
        activeNotebook.value = null;
        isLoading.value = false;
    }

    return { 
        notebooks, activeNotebook, isLoading, 
        fetchNotebooks, createStructuredNotebook, selectNotebook, setActiveNotebook, saveActive, exportNotebook, generateTitle, deleteNotebook,
        uploadSource, importSources, createManualArtefact, updateArtefact, deleteArtefact, deleteGeneratedAsset,
        deleteSlideImage, setSlideImageIndex, regenerateSlideImage,
        describeAsset, searchArxiv,
        sendSlideMessage, brainstormSlide, processWithAi, generateSlideNotes, generateSlideTitle, generateSlideAudio,
        enhancePrompt, generateSummary,
        addTab, removeTab, cancelTask,
        $reset 
    };
});
