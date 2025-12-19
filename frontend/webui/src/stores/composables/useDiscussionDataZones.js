// [UPDATE] frontend/webui/src/stores/composables/useDiscussionDataZones.js
import apiClient from '../../services/api';
import useEventBus from '../../services/eventBus';

export function useDiscussionDataZones(state, stores, getActions) {
    const { discussions, currentDiscussionId, activeDiscussionContextStatus, liveDataZoneTokens, activeAiTasks, _clearActiveAiTask, sharedWithMe } = state;
    const { uiStore, tasksStore } = stores;
    const { emit } = useEventBus();

    function updateLiveTokenCount(zone, count) {
        if (liveDataZoneTokens.value.hasOwnProperty(zone)) {
            liveDataZoneTokens.value[zone] = count;
        }
    }

    async function fetchContextStatus(discussionId) {
        if (!discussionId) {
            activeDiscussionContextStatus.value = null;
            return;
        }
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}/context_status`);
            activeDiscussionContextStatus.value = response.data;
            
            const breakdown = response.data?.zones?.system_context?.breakdown || {};
            updateLiveTokenCount('discussion', breakdown.discussion_data_zone?.tokens || 0);
            updateLiveTokenCount('user', breakdown.user_data_zone?.tokens || 0);
            updateLiveTokenCount('personality', breakdown.personality_data_zone?.tokens || 0);
            updateLiveTokenCount('memory', breakdown.memory?.tokens || 0);

        } catch (error) {
            console.error("Failed to fetch context status:", error);
            activeDiscussionContextStatus.value = null;
        }
    }

    async function fetchDataZones(discussionId) {
        if (!discussionId) return;
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}/data_zones`);
            const data = response.data;

            // Ensure we update the discussion object in the map for reactivity
            if (discussions.value[discussionId]) {
                discussions.value[discussionId] = { 
                    ...discussions.value[discussionId], 
                    ...data 
                };
            } else {
                // If it's a shared discussion not in the 'discussions' map, check 'sharedWithMe'
                const sharedIdx = sharedWithMe.value.findIndex(d => d.id === discussionId);
                if (sharedIdx !== -1) {
                    sharedWithMe.value[sharedIdx] = {
                        ...sharedWithMe.value[sharedIdx],
                        ...data
                    };
                }
            }

        } catch (error) {
            console.error("Failed to fetch data zones:", error);
            uiStore.addNotification('Could not load discussion data zones.', 'error');
        }
    }

    async function updateDataZone({ discussionId, content }) {
        if (!discussionId) return;
        try {
            await apiClient.put(`/api/discussions/${discussionId}/data_zone`, { content });
            if (discussions.value[discussionId]) {
                discussions.value[discussionId].discussion_data_zone = content;
            }
        } catch (error) {
            uiStore.addNotification('Failed to save discussion data zone.', 'error');
            throw error;
        }
    }

    async function appendToDataZone({ discussionId, content }) {
        const discussion = discussions.value[discussionId];
        if (!discussion) return;

        const currentContent = discussion.discussion_data_zone || '';
        const separator = currentContent.trim() ? '\n\n' : '';
        const newContent = currentContent + separator + content;

        await updateDataZone({ discussionId, content: newContent });
        uiStore.addNotification('Content appended to Data Zone.', 'success');
    }
    
    async function summarizeDiscussionDataZone(discussionId, prompt = null) {
        if (activeAiTasks.value[discussionId]) {
            uiStore.addNotification(`An AI task (${activeAiTasks.value[discussionId].type}) is already running for this discussion.`, 'warning');
            return;
        }

        const formData = new FormData();
        if (prompt) formData.append('prompt', prompt);

        activeAiTasks.value[discussionId] = { type: 'summarize', taskId: null };
        
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/process_data_zone`, formData);
            const task = response.data;
            uiStore.closeModal('summaryPromptModal');
            if (activeAiTasks.value[discussionId]) activeAiTasks.value[discussionId].taskId = task.id;
            tasksStore.addTask(task);
            uiStore.addNotification(`Content processing started.`, 'info');
        } catch (error) {
             _clearActiveAiTask(discussionId);
        }
    }

    async function generateImageFromDataZone(discussionId, prompt, parentMessageId) {
        if (activeAiTasks.value[discussionId]) {
            uiStore.addNotification(`An AI task (${activeAiTasks.value[discussionId].type}) is already running.`, 'warning');
            return;
        }
        
        const finalPrompt = state.imageGenerationSystemPrompt.value
            ? `${state.imageGenerationSystemPrompt.value}, ${prompt}`
            : prompt;

        const formData = new FormData();
        formData.append('prompt', finalPrompt);
        if (parentMessageId) {
            formData.append('parent_message_id', parentMessageId);
        }

        activeAiTasks.value[discussionId] = { type: 'generate_image', taskId: null };

        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/generate_image`, formData);
            const task = response.data;
            if (activeAiTasks.value[discussionId]) activeAiTasks.value[discussionId].taskId = task.id;
            tasksStore.addTask(task);
            uiStore.addNotification(`Image generation started.`, 'info');
        } catch (error) {
            _clearActiveAiTask(discussionId);
        }
    }

    async function memorizeLTM(discussionId) {
        if (activeAiTasks.value[discussionId]) {
            uiStore.addNotification(`An AI task (${activeAiTasks.value[discussionId].type}) is already running.`, 'warning');
            return;
        }
        
        activeAiTasks.value[discussionId] = { type: 'memorize', taskId: null };

        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/memorize`);
            const task = response.data;
            if (activeAiTasks.value[discussionId]) activeAiTasks.value[discussionId].taskId = task.id;
            tasksStore.addTask(task);
            uiStore.addNotification('Memorization task started.', 'info');
        } catch (error) {
            _clearActiveAiTask(discussionId);
        }
    }

    async function handleDataZoneUpdate({ discussion_id, zone, new_content, discussion_images, active_discussion_images }) {
        if (zone === 'discussion') {
            const discussion = discussions.value[discussion_id];
            if (discussion) {
                discussions.value[discussion_id] = {
                    ...discussion,
                    discussion_data_zone: new_content,
                    discussion_images: discussion_images !== undefined ? discussion_images : discussion.discussion_images,
                    active_discussion_images: active_discussion_images !== undefined ? active_discussion_images : discussion.active_discussion_images
                };
                
                uiStore.addNotification('Data zone has been updated by AI.', 'success');
                
                if (discussion_id === currentDiscussionId.value) {
                    emit('discussion_zone:processed');
                    await getActions().fetchArtefacts(discussion_id);
                    await getActions().fetchContextStatus(discussion_id);
                }
            }
        } else if (zone === 'memory') {
            const { useMemoriesStore } = await import('../../stores/memories');
            await useMemoriesStore().fetchMemories();
            uiStore.addNotification('A new memory has been created.', 'info');
            if (discussion_id === currentDiscussionId.value) {
                emit('discussion_zone:processed');
            }
        }
        
        if (discussion_id === currentDiscussionId.value) {
            fetchContextStatus(discussion_id);
        }
    }
    
    async function handleDiscussionImagesUpdated({ discussion_id, discussion_images, active_discussion_images }) {
        const discussion = discussions.value[discussion_id];
        if (discussion) {
            discussions.value[discussion_id] = {
                ...discussion,
                discussion_images: discussion_images,
                active_discussion_images: active_discussion_images
            };

            if (discussion_id === currentDiscussionId.value) {
                emit('discussion_zone:processed');
            }
        }
    }

    function setDiscussionDataZoneContent(discussionId, content) {
        if (discussions.value[discussionId]) {
            discussions.value[discussionId].discussion_data_zone = content;
        }
    
        const taskInfo = activeAiTasks.value[discussionId];
        if (taskInfo?.type === 'summarize' || taskInfo?.type === 'generate_image') {
            _clearActiveAiTask(discussionId);
            tasksStore.cancelTask(taskInfo.taskId);
            uiStore.addNotification('Processing cancelled due to manual edit.', 'info');
        }
    }

    async function refreshDataZones(discussionId) {
        if (!discussionId) return;
        try {
            await Promise.all([
                fetchDataZones(discussionId),
                fetchContextStatus(discussionId),
                getActions().fetchArtefacts(discussionId)
            ]);
        } catch (error) {
            console.error("Failed to refresh data zones:", error);
        }
    }
    
    async function updateDiscussionRagStores({ discussionId, ragDatastoreIds }) {
        if (!state.discussions.value[discussionId]) return;

        const originalIds = state.discussions.value[discussionId].rag_datastore_ids;
        state.discussions.value[discussionId].rag_datastore_ids = ragDatastoreIds;

        try {
            const response = await apiClient.put(`/api/discussions/${discussionId}/rag_datastore`, { rag_datastore_ids: ragDatastoreIds });
            const updatedDiscussionInfo = response.data;
            if (state.discussions.value[discussionId]) {
                state.discussions.value[discussionId].rag_datastore_ids = updatedDiscussionInfo.rag_datastore_ids;
            }
            getActions().fetchContextStatus(discussionId);
        } catch (error) {
            console.error("Failed to update RAG stores:", error);
            if (state.discussions.value[discussionId]) {
                state.discussions.value[discussionId].rag_datastore_ids = originalIds;
            }
            stores.uiStore.addNotification('Failed to update RAG data stores.', 'error');
        }
    }

    async function uploadAndEmbedFilesToDataZone(discussionId, files, extractImages = true) {
        const formData = new FormData();
        files.forEach(file => formData.append('files', file));
        formData.append('extract_images', extractImages ? '1' : '0');

        try {
            const response = await apiClient.post(`/api/files/extract_and_embed/${discussionId}`, formData);
            const data = response.data;
            
            if (state.discussions.value[discussionId]) {
                state.discussions.value[discussionId].discussion_data_zone = data.text_content;
                state.discussions.value[discussionId].discussion_images = data.discussion_images || [];
                state.discussions.value[discussionId].active_discussion_images = data.active_discussion_images || [];
            }
            
            await getActions().fetchContextStatus(discussionId);
            stores.uiStore.addNotification(`${files.length} file(s) added to context.`, 'success');
        } catch (error) {
            console.error("File embedding failed", error);
        }
    }


    return {
        fetchContextStatus, fetchDataZones, updateDataZone, appendToDataZone,
        summarizeDiscussionDataZone, generateImageFromDataZone, memorizeLTM,
        handleDataZoneUpdate, setDiscussionDataZoneContent, refreshDataZones,
        updateLiveTokenCount, handleDiscussionImagesUpdated,
        updateDiscussionRagStores,
        uploadAndEmbedFilesToDataZone
    };
}
