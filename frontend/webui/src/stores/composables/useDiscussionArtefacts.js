// frontend/webui/src/stores/composables/useDiscussionArtefacts.js
import apiClient from '../../services/api';

export function useDiscussionArtefacts(composableState, stores, getActions) {
    const {
        activeDiscussionArtefacts,
        isLoadingArtefacts,
        currentDiscussionId,
        promptLoadedArtefacts,
        emit,
        activeDiscussion,
        activeAiTasks,
        _clearActiveAiTask,
        liveDataZoneTokens
    } = composableState;

    const { uiStore, tasksStore } = stores;

    function _handleArtefactAndDataZoneUpdate(response) {
        activeDiscussionArtefacts.value = response.data.artefacts;
        if (activeDiscussion.value) {
            activeDiscussion.value.discussion_data_zone = response.data.discussion_data_zone;
            activeDiscussion.value.discussion_images = response.data.discussion_images || [];
            activeDiscussion.value.active_discussion_images = response.data.active_discussion_images || [];
        }
        liveDataZoneTokens.value.discussion = response.data.discussion_data_zone_tokens;
        if (currentDiscussionId.value) {
            getActions().fetchContextStatus(currentDiscussionId.value);
        }
    }

    async function fetchArtefacts(discussionId) {
        if (!discussionId) return;
        isLoadingArtefacts.value = true;
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}/artefacts`);
            activeDiscussionArtefacts.value = response.data;
        } catch (error) {
            console.error("Failed to fetch artefacts:", error);
            activeDiscussionArtefacts.value = [];
        } finally {
            isLoadingArtefacts.value = false;
        }
    }

    async function addArtefact({ discussionId, file, extractImages }) {
        if (!discussionId) {
            console.error("No discussionId provided for addArtefact");
            return;
        }
        const formData = new FormData();
        formData.append('file', file);
        formData.append('extract_images', extractImages ? 'true' : 'false');

        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            
            // If the upload was for the currently active discussion/notebook, update the list
            if (currentDiscussionId.value === discussionId || !currentDiscussionId.value) {
                // If it's a notebook or the active chat, we refetch to ensure we have the full synced list
                await fetchArtefacts(discussionId);
            }
            
            return response.data;
        } catch (error) {
            console.error("Failed to add artefact:", error);
            uiStore.addNotification(`Failed to upload ${file.name}`, 'error');
            throw error;
        }
    }

    async function createManualArtefact({ discussionId, title, content, imagesB64 }) {
        const payload = { title, content, images_b64: imagesB64 };
        await apiClient.post(`/api/discussions/${discussionId}/artefacts/manual`, payload);
        await fetchArtefacts(discussionId);
    }

    async function updateArtefact({ discussionId, artefactTitle, newContent, newImagesB64, keptImagesB64, version, updateInPlace }) {
        const payload = { new_content: newContent, new_images_b64: newImagesB64, kept_images_b64: keptImagesB64, version, update_in_place: updateInPlace };
        await apiClient.put(`/api/discussions/${discussionId}/artefacts/${encodeURIComponent(artefactTitle)}`, payload);
        await fetchArtefacts(discussionId);
    }
    
    async function deleteArtefact({ discussionId, artefactTitle }) {
        await apiClient.delete(`/api/discussions/${discussionId}/artefact?artefact_title=${encodeURIComponent(artefactTitle)}`);
        await fetchArtefacts(discussionId);
        if (promptLoadedArtefacts.value.has(artefactTitle)) {
            unloadArtefactFromPrompt(artefactTitle);
        }
    }

    async function fetchArtefactContent({ discussionId, artefactTitle, version }) {
        const response = await apiClient.get(`/api/discussions/${discussionId}/artefact`, {
            params: { artefact_title: artefactTitle, version: version }
        });
        return response.data;
    }

    async function exportContextAsArtefact({ discussionId, title }) {
        const idToUse = discussionId || currentDiscussionId.value;
        if (!idToUse) {
            uiStore.addNotification('Error: No discussion selected to export context from.', 'error');
            return;
        }
        await apiClient.post(`/api/discussions/${idToUse}/artefacts/export-context`, { title });
        await fetchArtefacts(idToUse);
        uiStore.addNotification(`Context saved as artefact '${title}'`, 'success');
    }

    async function importArtefactFromUrl(discussionId, url, depth = 0, processWithAi = false) {
        const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/import_url`, { 
            url, 
            depth, 
            process_with_ai: processWithAi 
        });
        const task = response.data;
        activeAiTasks.value[discussionId] = { taskId: task.id, type: 'import_url' };
        tasksStore.addTask(task);
        uiStore.addNotification(`Importing from URL started (Depth: ${depth}).`, 'info');
    }
    
    async function loadAllArtefactsToDataZone(discussionId) {
        const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/load-all-to-context`);
        _handleArtefactAndDataZoneUpdate(response);
        uiStore.addNotification('All artefacts loaded to data zone.', 'success');
    }
    
    async function loadArtefactToContext({ discussionId, artefactTitle, version }) {
        const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/load-to-context`, {
            title: artefactTitle,
            version: version
        });
        _handleArtefactAndDataZoneUpdate(response);
    }
    
    async function unloadArtefactFromContext({ discussionId, artefactTitle, version }) {
        const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/unload-from-context`, {
            title: artefactTitle,
            version: version
        });
        _handleArtefactAndDataZoneUpdate(response);
    }

    async function loadArtefactToPrompt({ discussionId, artefactTitle, version }) {
        try {
            const artefact = await fetchArtefactContent({ discussionId, artefactTitle, version });
            if (artefact && artefact.content) {
                promptLoadedArtefacts.value.add(artefact.title);
                emit('artefact:load-to-prompt', artefact.content);
                uiStore.addNotification(`Artefact "${artefact.title}" content sent to prompt.`, 'success');
            } else {
                uiStore.addNotification(`Could not load content for artefact "${artefactTitle}".`, 'error');
            }
        } catch (error) {
            // Error handled globally
        }
    }

    function unloadArtefactFromPrompt(artefactTitle) {
        if (promptLoadedArtefacts.value.has(artefactTitle)) {
            promptLoadedArtefacts.value.delete(artefactTitle);
            emit('artefact:unload-from-prompt');
            uiStore.addNotification(`Artefact "${artefactTitle}" unloaded from prompt.`, 'info');
        }
    }

    return {
        fetchArtefacts,
        addArtefact,
        createManualArtefact,
        updateArtefact,
        deleteArtefact,
        fetchArtefactContent,
        exportContextAsArtefact,
        importArtefactFromUrl,
        loadAllArtefactsToDataZone,
        loadArtefactToContext,
        unloadArtefactFromContext,
        loadArtefactToPrompt,
        unloadArtefactFromPrompt
    };
}
