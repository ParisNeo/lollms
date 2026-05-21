// frontend/webui/src/stores/composables/useDiscussionArtefacts.js
import apiClient from '../../services/api';

export function useDiscussionArtefacts(composableState, stores, getActions) {
    const {
        activeDiscussionArtefacts,
        allUserArtefacts,
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

    async function fetchAllUserArtefacts() {
        isLoadingArtefacts.value = true;
        try {
            const response = await apiClient.get('/api/discussions/artefacts/all');
            allUserArtefacts.value = response.data;
        } catch (error) {
            console.error("Failed to fetch global artefacts:", error);
            allUserArtefacts.value = [];
        } finally {
            isLoadingArtefacts.value = false;
        }
    }

    async function addArtefact({ discussionId, file, extractImages, pdfMode = 'text_and_embedded_images' }) {
        if (!discussionId) return;
        const formData = new FormData();
        formData.append('file', file);
        formData.append('extract_images', extractImages ? 'true' : 'false');
        formData.append('pdf_mode', pdfMode);

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

    async function createManualArtefact({ discussionId, title, content, imagesB64 = [] }) {
        const payload = { title, content, images_b64: imagesB64 };
        await apiClient.post(`/api/discussions/${discussionId}/artefacts/manual`, payload);
        await fetchArtefacts(discussionId);
    }

    async function renameArtefact({ discussionId, oldTitle, newTitle, newType }) {
        try {
            await apiClient.put(`/api/discussions/${discussionId}/artefacts/rename`, {
                old_title: oldTitle,
                new_title: newTitle,
                new_type: newType
            });
            await fetchArtefacts(discussionId);
            uiStore.addNotification(`Artefact renamed successfully.`, 'success');
        } catch (e) {
            console.error("Rename failed:", e);
            uiStore.addNotification('Failed to rename artefact.', 'error');
        }
    }

    async function updateArtefact({ discussionId, artefactTitle, newContent, newImagesB64, keptImagesB64, version, updateInPlace, artefactType }) {
        const payload = { 
            new_content: newContent, 
            new_images_b64: newImagesB64, 
            kept_images_b64: keptImagesB64, 
            version, 
            update_in_place: updateInPlace,
            artefact_type: artefactType
        };
        await apiClient.put(`/api/discussions/${discussionId}/artefacts/${encodeURIComponent(artefactTitle)}`, payload);
        await fetchArtefacts(discussionId);
    }

    async function renameArtefact({ discussionId, artefactTitle, newTitle }) {
        // Double-encode to ensure title characters like dots don't trigger static file handlers
        const encodedTitle = encodeURIComponent(artefactTitle)
            .replace(/\./g, '%2E')
            .replace(/%/g, '%25');

        await apiClient.put(`/api/discussions/${discussionId}/artefacts/${encodedTitle}/rename`, {
            new_title: newTitle
        });
        
        // Refresh local list
        await fetchArtefacts(discussionId);
        
        // If this file was open in the workspace, update the UI title ref
        if (uiStore.activeSplitArtefactTitle === artefactTitle) {
            uiStore.activeSplitArtefactTitle = newTitle;
        }
        
        uiStore.addNotification(`Renamed to '${newTitle}'`, 'success');
    }
    
    async function deleteArtefact({ discussionId, artefactTitle }) {
        // 1. Capture original state for potential rollback
        const originalArtefacts = [...activeDiscussionArtefacts.value];

        // 2. OPTIMISTIC UPDATE: Filter out all versions of this title immediately
        activeDiscussionArtefacts.value = activeDiscussionArtefacts.value.filter(
            a => a.title !== artefactTitle
        );

        // 3. UI Cleanup: If the file was being viewed, close it now
        if (uiStore.activeSplitArtefactTitle === artefactTitle) {
            uiStore.activeSplitArtefactTitle = null;
            // If we are in workspace tab and it's now empty, maybe switch back to context
            if (uiStore.dataZoneTab === 'workspace') {
                uiStore.dataZoneTab = 'files';
            }
        }

        if (promptLoadedArtefacts.value.has(artefactTitle)) {
            unloadArtefactFromPrompt(artefactTitle);
        }

        try {
            // 4. Perform actual deletion in the background
            await apiClient.delete(`/api/discussions/${discussionId}/artefact`, {
                params: { artefact_title: artefactTitle }
            });

            // Optional: Refresh context status because total tokens decreased
            getActions().fetchContextStatus(discussionId);

            uiStore.addNotification(`'${artefactTitle}' removed from workspace.`, 'success', 2000);
        } catch (e) {
            // 5. ROLLBACK: If API fails, restore the items and notify user
            console.error("Delete artefact failed:", e);
            activeDiscussionArtefacts.value = originalArtefacts;
            uiStore.addNotification(`Failed to delete '${artefactTitle}'. Restoring...`, 'error');
        }
    }

    async function fetchArtefactContent({ discussionId, artefactTitle, version = null, strategy = 'raw' }) {
        // Backend route: GET /{discussion_id}/artefacts/{artefact_title:path}/content
        // CRITICAL: Double-encode to prevent static file handlers from intercepting .html, .js, etc.
        // First encode normally, then encode the % signs to prevent dot interpretation
        const encodedTitle = encodeURIComponent(artefactTitle)
            .replace(/\./g, '%2E')  // Encode dots explicitly to prevent static file matching
            .replace(/%/g, '%25');  // Double-encode for path safety
        
        const response = await apiClient.get(`/api/discussions/${discussionId}/artefacts/${encodedTitle}/content`, {
            params: { version, strategy }
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
        // Pure Artefact Approach: Signal deactivation to the library.
        // We no longer manually manipulate the data zone string.
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

    async function unloadArtefactFromPrompt(artefactTitle) {
        if (promptLoadedArtefacts.value.has(artefactTitle)) {
            promptLoadedArtefacts.value.delete(artefactTitle);
            emit('artefact:unload-from-prompt');
            uiStore.addNotification(`Artefact "${artefactTitle}" unloaded from prompt.`, 'info');
        }
    }

    async function createDiscussionWithArtefactVersion({ discussionId, artefactTitle, version }) {
        uiStore.addNotification('Creating new chat with this document...', 'info');
        try {
            const response = await apiClient.post(
                `/api/discussions/${discussionId}/artefacts/${encodeURIComponent(artefactTitle)}/create_discussion_with_version`,
                null,
                { params: { version } }
            );

            const newDiscussion = response.data;
            // Use the core select action to jump to the new chat
            await getActions().selectDiscussion(newDiscussion.id);

            // Open the new discussion and ensure the workspace follows
            uiStore.activeSplitArtefactTitle = artefactTitle;
            uiStore.dataZoneTab = 'workspace';

            uiStore.addNotification(`New discussion started with '${artefactTitle}'`, 'success');
            return newDiscussion;
        } catch (error) {
            console.error("Failed to create discussion with artefact:", error);
            uiStore.addNotification('Failed to create new discussion.', 'error');
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

    async function fetchArtefactHistory(discussionId, artefactTitle) {
        const encoded = encodeURIComponent(artefactTitle).replace(/\./g, '%2E').replace(/%/g, '%25');
        const response = await apiClient.get(`/api/discussions/${discussionId}/artefacts/${encoded}/history`);
        return response.data;
    }

    async function squashArtefactVersions({ discussionId, artefactTitle, params }) {
        const encoded = encodeURIComponent(artefactTitle).replace(/\./g, '%2E').replace(/%/g, '%25');
        const response = await apiClient.post(`/api/discussions/${discussionId}/artefacts/${encoded}/squash`, params);
        await fetchArtefacts(discussionId);
        uiStore.addNotification(`History squashed. Reclaimed space.`, 'success');
        return response.data;
    }

    async function deleteArtefactVersion({ discussionId, artefactTitle, version }) {
        const encoded = encodeURIComponent(artefactTitle).replace(/\./g, '%2E').replace(/%/g, '%25');
        await apiClient.delete(`/api/discussions/${discussionId}/artefacts/${encoded}/version/${version}`);
        await fetchArtefacts(discussionId);
        uiStore.addNotification(`Version ${version} deleted.`, 'success');
    }

    // NEW: Functions to bridge global notes/skills to the versioned artefact system
    async function addNoteAsArtefact(note) {
        if (!currentDiscussionId.value) return;
        try {
            // Explicitly force 'note' type and 'active' status
            const response = await apiClient.post(
                `/api/discussions/${currentDiscussionId.value}/artefacts/manual`, 
                { 
                    title: note.title, 
                    content: note.content, 
                    images_b64: [],
                    type: 'note' 
                },
                { 
                    params: { 
                        artefact_type: 'note', 
                        auto_load: 'true' 
                    } 
                }
            );
            
            // Refresh local state
            await fetchArtefacts(currentDiscussionId.value);
            await getActions().fetchContextStatus(currentDiscussionId.value);
            
            // Switch Workspace focus to the newly added note
            uiStore.activeSplitArtefactTitle = note.title;
            uiStore.addNotification(`Note added to discussion.`, 'success');
        } catch (e) { 
            console.error("Failed to add note as artefact:", e); 
        }
    }

    async function addSkillAsArtefact(skill) {
        if (!currentDiscussionId.value) return;
        try {
            // CRITICAL FIX: Explicitly set type to 'skill' and auto_load to 'true'
            const response = await apiClient.post(
                `/api/discussions/${currentDiscussionId.value}/artefacts/manual`, 
                { title: skill.name, content: skill.content, images_b64: [] },
                { params: { artefact_type: 'skill', auto_load: 'true' } }
            );
            
            await fetchArtefacts(currentDiscussionId.value);
            await getActions().fetchContextStatus(currentDiscussionId.value);
            
            uiStore.activeSplitArtefactTitle = skill.name;
            uiStore.addNotification(`Skill '${skill.name}' active in workspace.`, 'success');
        } catch (e) { console.error(e); }
    }

    async function importSourceToArtefacts(source) {
        if (!currentDiscussionId.value) return;
        
        const title = source.title || "Imported Source";
        const pathOrUrl = source.source || "";
        
        try {
            if (pathOrUrl.startsWith('http')) {
                // External Web Source: Use the scraping background task
                await importArtefactFromUrl(currentDiscussionId.value, pathOrUrl, 0, false);
                uiStore.addNotification(`Initiated import for: ${title}`, 'info');
            } else {
                // Internal/Snippet Source: Create a manual artefact from the content
                const response = await apiClient.post(`/api/discussions/${currentDiscussionId.value}/artefacts/manual`, 
                    { 
                        title: title.endsWith('.md') ? title : `${title}.md`, 
                        content: source.content || "", 
                        images_b64: [] 
                    },
                    { params: { artefact_type: 'document', auto_load: true } }
                );
                _handleArtefactAndDataZoneUpdate(response);
                
                uiStore.activeSplitArtefactTitle = title;
                uiStore.addNotification(`Source '${title}' saved to workspace.`, 'success');
            }
            
            // Ensure the side panel is open to show the new artefact
            if (!uiStore.isDataZoneVisible) {
                uiStore.isDataZoneVisible = true;
            }
        } catch (e) {
            console.error("Failed to import source:", e);
            uiStore.addNotification("Failed to import source to artefacts.", "error");
        }
    }

    return {
        createDiscussionWithArtefactVersion,
        revertArtefact,
        renameArtefact,
        fetchArtefacts,
        fetchAllUserArtefacts,
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
        importYoutubeTranscript,
        importSourceToArtefacts
    };
}
