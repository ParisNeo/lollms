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
        // Sync the versioned artefacts list
        activeDiscussionArtefacts.value = response.data.artefacts;
        
        if (activeDiscussion.value) {
            // CRITICAL: We stop syncing 'discussion_data_zone' text here. 
            // This zone is now purely for manual User instructions.
            activeDiscussion.value.discussion_images = response.data.discussion_images || [];
            activeDiscussion.value.active_discussion_images = response.data.active_discussion_images || [];
        }
        
        // Update tokens for status bar (library still counts artefacts tokens internally)
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
        if (!discussionId) return;
        const formData = new FormData();
        formData.append('file', file);
        formData.append('extract_images', extractImages ? 'true' : 'false');

        try {
            // CRITICAL: Explicitly set artefact_type to 'file' for uploads
            const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                params: { artefact_type: 'file' }
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
        try {
            await apiClient.delete(`/api/discussions/${discussionId}/artefact?artefact_title=${encodeURIComponent(artefactTitle)}`);
            
            // 1. Force refresh of the local list
            await fetchArtefacts(discussionId);
            
            // 2. Clean up UI states
            if (state.activeSplitArtefactTitle?.value === artefactTitle) {
                uiStore.activeSplitArtefactTitle = null;
            }
            if (promptLoadedArtefacts.value.has(artefactTitle)) {
                unloadArtefactFromPrompt(artefactTitle);
            }
            uiStore.addNotification('Artefact deleted.', 'success');
        } catch (e) {
            uiStore.addNotification('Failed to delete artefact.', 'error');
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

    async function importWikipediaArtefact(discussionId, query) {
        if (!discussionId) return;
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/wikipedia`, { query });
            _handleArtefactAndDataZoneUpdate(response);
            uiStore.addNotification('Wikipedia article imported and loaded.', 'success');
        } catch (error) {
            console.error(error);
            uiStore.addNotification(error.response?.data?.detail || 'Failed to import Wikipedia article.', 'error');
            throw error;
        }
    }

    async function importGithubArtefact(discussionId, url) {
        if (!discussionId) return;
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/github`, { url, auto_load: true });
            _handleArtefactAndDataZoneUpdate(response);
            uiStore.addNotification('GitHub content imported and loaded.', 'success');
        } catch (error) {
            console.error(error);
            uiStore.addNotification(error.response?.data?.detail || 'Failed to import GitHub content.', 'error');
            throw error;
        }
    }

    async function importStackOverflowArtefact(discussionId, url) {
        if (!discussionId) return;
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/stackoverflow`, { url, auto_load: true });
            _handleArtefactAndDataZoneUpdate(response);
            uiStore.addNotification('StackOverflow content imported and loaded.', 'success');
        } catch (error) {
            console.error(error);
            uiStore.addNotification(error.response?.data?.detail || 'Failed to import StackOverflow content.', 'error');
            throw error;
        }
    }

    async function importYoutubeTranscript(discussionId, videoUrl, language) {
        if (!discussionId) return;
        const payload = { video_url: videoUrl };
        if (language) payload.language = language;

        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/youtube`, payload);
            _handleArtefactAndDataZoneUpdate(response);
            uiStore.addNotification('YouTube transcript imported and loaded.', 'success');
        } catch (error) {
            console.error(error);
            uiStore.addNotification(error.response?.data?.detail || 'Failed to import YouTube transcript.', 'error');
            throw error;
        }
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
        // 1. Call backend to update metadata
        const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/unload-from-context`, {
            title: artefactTitle,
            version: version
        });
        
        // 2. Local cleanup: Remove the text block from the Data Zone string
        // We call the improved removal action we just added to the main store
        await getActions().removeContextItem(artefactTitle, 'document');
        
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

    async function unloadArtefactFromPrompt(artefactTitle) {
        if (promptLoadedArtefacts.value.has(artefactTitle)) {
            promptLoadedArtefacts.value.delete(artefactTitle);
            emit('artefact:unload-from-prompt');
            uiStore.addNotification(`Artefact "${artefactTitle}" unloaded from prompt.`, 'info');
        }
    }

    async function revertArtefact({ discussionId, artefactTitle, version }) {
        try {
            await apiClient.post(`/api/discussions/${discussionId}/artefacts/revert`, {
                title: artefactTitle,
                version: version
            });
            await fetchArtefacts(discussionId);
            uiStore.addNotification(`Reverted to version ${version}`, 'success');
        } catch (e) {
            uiStore.addNotification('Revert failed.', 'error');
        }
    }

    // NEW: Functions to bridge global notes/skills to the versioned artefact system
    async function addNoteAsArtefact(note) {
        if (!currentDiscussionId.value) return;
        try {
            // Check for existing version to prevent duplicate chips
            const existing = activeDiscussionArtefacts.value.find(a => a.title === note.title);
            
            const response = await apiClient.post(`/api/discussions/${currentDiscussionId.value}/artefacts/manual`, 
                { title: note.title, content: note.content, images_b64: [] },
                { params: { artefact_type: 'note', auto_load: true } }
            );
            _handleArtefactAndDataZoneUpdate(response);
            
            uiStore.activeSplitArtefactTitle = note.title;
            const msg = existing ? `Updated '${note.title}' to v${existing.version + 1}` : `Added '${note.title}' to workspace.`;
            uiStore.addNotification(msg, 'success');
        } catch (e) { console.error(e); }
    }

    async function addSkillAsArtefact(skill) {
        if (!currentDiscussionId.value) return;
        try {
            // Check for existing version to prevent duplicate chips
            const existing = activeDiscussionArtefacts.value.find(a => a.title === skill.name);

            const response = await apiClient.post(`/api/discussions/${currentDiscussionId.value}/artefacts/manual`, 
                { title: skill.name, content: skill.content, images_b64: [] },
                { params: { artefact_type: 'skill', auto_load: true } }
            );
            _handleArtefactAndDataZoneUpdate(response);
            
            uiStore.activeSplitArtefactTitle = skill.name;
            const msg = existing ? `Updated skill '${skill.name}' to v${existing.version + 1}` : `Skill added to workspace.`;
            uiStore.addNotification(msg, 'success');
        } catch (e) { console.error(e); }
    }

    return {
        revertArtefact,
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
        unloadArtefactFromPrompt,
        addNoteAsArtefact,
        addSkillAsArtefact,
        importWikipediaArtefact,
        importGithubArtefact,
        importStackOverflowArtefact,
        importYoutubeTranscript
    };
}
