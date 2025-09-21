// frontend/webui/src/stores/composables/useDiscussionArtefacts.js
import apiClient from '../../services/api';
import useEventBus from '../../services/eventBus';

export function useDiscussionArtefacts(state, stores, getActions) {
    const { discussions, activeDiscussionArtefacts, isLoadingArtefacts, promptLoadedArtefacts } = state;
    const { uiStore, tasksStore } = stores;
    const { emit } = useEventBus();

    async function fetchArtefacts(discussionId) {
        if (!discussionId) {
            activeDiscussionArtefacts.value = [];
            return;
        }
        isLoadingArtefacts.value = true;
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}/artefacts`);
            activeDiscussionArtefacts.value = response.data.sort((a,b) => a.title.localeCompare(b.title));
        } catch (error) {
            console.error("Failed to fetch artefacts:", error);
            activeDiscussionArtefacts.value = [];
        } finally {
            isLoadingArtefacts.value = false;
        }
    }

    async function addArtefact({ discussionId, file }) {
        if (!discussionId || !file) return;
        uiStore.addNotification(`Uploading ${file.name}...`, 'info');
        try {
            const formData = new FormData();
            formData.append('file', file);
            await apiClient.post(`/api/discussions/${discussionId}/artefacts`, formData);
            await fetchArtefacts(discussionId);
            uiStore.addNotification(`Artefact '${file.name}' added.`, 'success');
        } catch (error) {
            console.error("Failed to add artefact:", error);
            uiStore.addNotification(`Failed to add artefact '${file.name}'.`, 'error');
        }
    }

    async function importArtefactFromUrl({ discussionId, url }) {
        if (!discussionId || !url) return null;
        
        state.activeAiTasks.value[discussionId] = { type: 'import_url', taskId: null };

        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/import_url`, { url });
            const task = response.data;
            tasksStore.addTask(task);
            if (state.activeAiTasks.value[discussionId]) {
                state.activeAiTasks.value[discussionId].taskId = task.id;
            }
            uiStore.addNotification(`URL import started.`, 'info');
        } catch (error) {
             state._clearActiveAiTask(discussionId);
        }
    }

    async function exportContextAsArtefact({ discussionId, title }) {
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/export-context`, { title });
            await fetchArtefacts(discussionId);
            uiStore.addNotification(`Context saved as artefact '${title}'.`, 'success');
            return response.data;
        } catch (error) {
            return null;
        }
    }

    async function deleteArtefact({ discussionId, artefactTitle }) {
        try {
            await apiClient.delete(`/api/discussions/${discussionId}/artefact`, {
                params: { artefact_title: artefactTitle }
            });
            await fetchArtefacts(discussionId);
            uiStore.addNotification(`Artefact '${artefactTitle}' deleted.`, 'success');
        } catch (error) {
            console.error("Failed to delete artefact:", error);
        }
    }

    async function fetchArtefactContent({ discussionId, artefactTitle, version }) {
        try {
            const params = { artefact_title: artefactTitle };
            if (version) {
                params.version = version;
            }
            const response = await apiClient.get(`/api/discussions/${discussionId}/artefact`, { params });
            return response.data;
        } catch (error) {
            uiStore.addNotification(`Could not fetch content for '${artefactTitle}'.`, 'error');
            return null;
        }
    }

    async function loadArtefactToContext({ discussionId, artefactTitle, version }) {
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/load-to-context`, { title: artefactTitle, version: version });
            
            activeDiscussionArtefacts.value = response.data.artefacts.sort((a,b) => a.title.localeCompare(b.title));

            setTimeout(() => {
                if (discussions.value[discussionId]) {
                    discussions.value[discussionId].discussion_data_zone = response.data.discussion_data_zone;
                }
                
                getActions().updateLiveTokenCount('discussion', response.data.discussion_data_zone_tokens);
                getActions().fetchContextStatus(discussionId);
            }, 0);
            
            uiStore.addNotification(`'${artefactTitle}' loaded into context.`, 'success');
        } catch (error) {
            console.error(`Failed to load artefact '${artefactTitle}':`, error);
            uiStore.addNotification(`Failed to load artefact '${artefactTitle}'.`, 'error');
        }
    }

    async function loadAllArtefactsToContext(discussionId) {
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/load-all-to-context`);
            
            activeDiscussionArtefacts.value = response.data.artefacts.sort((a,b) => a.title.localeCompare(b.title));

            setTimeout(() => {
                if (discussions.value[discussionId]) {
                    discussions.value[discussionId].discussion_data_zone = response.data.discussion_data_zone;
                }
                
                getActions().updateLiveTokenCount('discussion', response.data.discussion_data_zone_tokens);
                getActions().fetchContextStatus(discussionId); 
            }, 0);
            
            uiStore.addNotification('All artefacts loaded into context.', 'success');
        } catch (error) {
            console.error(`Failed to load all artefacts:`, error);
            uiStore.addNotification('Failed to load all artefacts.', 'error');
        }
    }
    
    async function loadArtefactToPrompt({ discussionId, artefactTitle, version }) {
        try {
            const artefact = await fetchArtefactContent({ discussionId, artefactTitle, version });
            if (artefact && artefact.content) {
                emit('artefact:load-to-prompt', artefact.content);
                promptLoadedArtefacts.value.add(artefactTitle);
                uiStore.addNotification(`'${artefactTitle}' loaded into processing prompt.`, 'success');
            } else {
                uiStore.addNotification(`Could not load content for '${artefactTitle}'.`, 'warning');
            }
        } catch (error) {
            // fetchArtefactContent already shows a notification
        }
    }

    async function unloadArtefactFromPrompt(artefactTitle) {
        promptLoadedArtefacts.value.delete(artefactTitle);
        emit('artefact:unload-from-prompt', artefactTitle);
        uiStore.addNotification(`'${artefactTitle}' unloaded from prompt.`, 'info');
    }

    async function unloadArtefactFromContext({ discussionId, artefactTitle, version }) {
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/unload-from-context`, { title: artefactTitle, version });
            
            if (response.data.artefacts && Array.isArray(response.data.artefacts)) {
                activeDiscussionArtefacts.value = response.data.artefacts.sort((a, b) => a.title.localeCompare(b.title));
            } else {
                activeDiscussionArtefacts.value = [];
            }
            
            setTimeout(() => {
                if (discussions.value[discussionId]) {
                    discussions.value[discussionId].discussion_data_zone = response.data.discussion_data_zone;
                }
                
                getActions().updateLiveTokenCount('discussion', response.data.discussion_data_zone_tokens);
                getActions().fetchContextStatus(discussionId);
            }, 0);
            
            uiStore.addNotification(`'${artefactTitle}' unloaded from context.`, 'success');
        } catch (error) {
            console.error(`Failed to unload artefact '${artefactTitle}':`, error);
            uiStore.addNotification(`Failed to unload artefact '${artefactTitle}'.`, 'error');
        }
    }

    async function createManualArtefact({ discussionId, title, content, imagesB64 }) {
        try {
            const payload = { title, content, images_b64: imagesB64 };
            await apiClient.post(`/api/discussions/${discussionId}/artefacts/manual`, payload);
            await fetchArtefacts(discussionId);
            uiStore.addNotification('Artefact created successfully.', 'success');
        } catch (error) {
            console.error("Failed to create manual artefact:", error);
        }
    }

    async function updateArtefact({ discussionId, artefactTitle, newContent, newImagesB64, keptImagesB64, version, updateInPlace }) {
        try {
            const payload = {
                new_content: newContent,
                new_images_b64: newImagesB64,
                kept_images_b64: keptImagesB64,
                version: version,
                update_in_place: updateInPlace
            };
            await apiClient.put(`/api/discussions/${discussionId}/artefacts/${artefactTitle}`, payload);
            await fetchArtefacts(discussionId);
            uiStore.addNotification(`Artefact '${artefactTitle}' updated.`, 'success');
        } catch (error) {
            console.error("Failed to update artefact:", error);
        }
    }

    return {
        fetchArtefacts, addArtefact, importArtefactFromUrl,
        exportContextAsArtefact, deleteArtefact, fetchArtefactContent,
        loadArtefactToContext, loadAllArtefactsToContext, unloadArtefactFromContext,
        createManualArtefact, updateArtefact,
        loadArtefactToPrompt, unloadArtefactFromPrompt,
    };
}