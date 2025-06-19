import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';

let activeGenerationAbortController = null;

export const useDiscussionsStore = defineStore('discussions', () => {
    // State
    const discussions = ref({});
    const currentDiscussionId = ref(null);
    const generationInProgress = ref(false);

    // Getters
    const activeDiscussion = computed(() => {
        return currentDiscussionId.value ? discussions.value[currentDiscussionId.value] : null;
    });

    const activeMessages = computed(() => {
        const disc = activeDiscussion.value;
        if (!disc) return [];
        const branchId = disc.activeBranchId || 'main';
        // Ensure the branch array exists before returning
        return disc.branches?.[branchId] || [];
    });

    // Helpers
    function findMessage(discussionId, messageId, branchId) {
        const disc = discussions.value[discussionId];
        if (!disc || !disc.branches || !disc.branches[branchId]) return null;
        return disc.branches[branchId].find(m => m.id === messageId);
    }

    /**
     * Processes raw message objects from the API, adding client-side metadata.
     * @param {Array} messages - The array of message objects.
     * @param {string} branchId - The ID of the branch these messages belong to.
     * @returns {Array} The processed array of message objects.
     */
    function processMessages(messages, branchId) {
        const authStore = useAuthStore();
        return messages.map(msg => {
            let senderType = 'assistant'; // Default to assistant
            const sender = msg.sender?.toLowerCase();
            const username = authStore.user?.username?.toLowerCase();

            if (sender === 'system' || sender === 'error') {
                senderType = 'system';
            } else if (sender === username || sender === 'user') {
                senderType = 'user';
            }
            return {
                ...msg,
                branch_id: branchId,
                sender_type: senderType,
                steps: msg.steps || [],
                sources: msg.sources || [],
                metadata: msg.metadata || {},
                // New property for branching UI
                children_count: msg.children_count || 1,
            };
        });
    }

    // Actions
    async function loadDiscussions() {
        try {
            const response = await apiClient.get('/api/discussions');
            const discussionData = response.data;
            if (!Array.isArray(discussionData)) {
                console.error("Expected an array of discussions, but received:", discussionData);
                discussions.value = {};
                return;
            }
            const loadedDiscussions = {};
            discussionData.forEach(d => {
                loadedDiscussions[d.id] = {
                    ...d,
                    rag_datastore_id: d.rag_datastore_id,
                    mcp_tool_ids: d.active_tools || [],
                    branches: {},
                    // Add branch info from backend, with a fallback for older versions
                    branches_info: d.branches_info || [{ id: d.active_branch_id || 'main', name: 'Main Branch' }],
                    activeBranchId: d.active_branch_id || 'main',
                    messages_loaded_fully: {}
                };
            });
            discussions.value = loadedDiscussions;
        } catch (error) {
            console.error("Failed to load discussions:", error);
            discussions.value = {};
        }
    }

    async function selectDiscussion(id) {
        if (!id || generationInProgress.value) return;
        currentDiscussionId.value = id;
        const disc = discussions.value[id];
        if (!disc) return;
        const branchId = disc.activeBranchId || 'main';
        // Fetch messages for the active branch if not already loaded
        if (!disc.messages_loaded_fully[branchId]) {
            try {
                const response = await apiClient.get(`/api/discussions/${id}?branch_id=${branchId}`);
                const processedMessages = processMessages(response.data, branchId);
                disc.branches = { ...disc.branches, [branchId]: processedMessages };
                disc.messages_loaded_fully[branchId] = true;
            } catch (error) {
                useUiStore().addNotification('Failed to load messages.', 'error');
                currentDiscussionId.value = null;
            }
        }
    }

    async function createNewDiscussion() {
        useUiStore().addNotification('Creating new discussion...', 'info');
        try {
            const response = await apiClient.post('/api/discussions');
            const newDisc = response.data;
            discussions.value[newDisc.id] = {
                ...newDisc,
                mcp_tool_ids: [],
                branches: { 'main': [] },
                branches_info: [{ id: 'main', name: 'Main Branch' }],
                activeBranchId: 'main',
                messages_loaded_fully: { 'main': true }
            };
            await selectDiscussion(newDisc.id);
        } catch (error) {
            console.error(error);
        }
    }

    async function deleteDiscussion(discussionId) {
        const disc = discussions.value[discussionId];
        if (!disc) return;

        const uiStore = useUiStore();
        const confirmed = await uiStore.showConfirmation({
            title: 'Delete Discussion',
            message: `Are you sure you want to delete "${disc.title}"? This cannot be undone.`,
            confirmText: 'Delete'
        });

        if (!confirmed) return;

        try {
            await apiClient.delete(`/api/discussions/${discussionId}`);
            delete discussions.value[discussionId];
            if(currentDiscussionId.value === discussionId) {
                currentDiscussionId.value = null;
            }
            uiStore.addNotification('Discussion deleted.', 'success');
        } catch(error) {
            // Handled by interceptor
        }
    }

    async function toggleStarDiscussion(discussionId) {
        const disc = discussions.value[discussionId];
        if (!disc) return;

        const isCurrentlyStarred = disc.is_starred;
        const method = isCurrentlyStarred ? 'DELETE' : 'POST';

        disc.is_starred = !isCurrentlyStarred;

        try {
            const response = await apiClient({ url: `/api/discussions/${discussionId}/star`, method });
            discussions.value[discussionId].is_starred = response.data.is_starred;
        } catch(error) {
            discussions.value[discussionId].is_starred = isCurrentlyStarred;
        }
    }

    async function updateDiscussionRagStore({ discussionId, ragDatastoreId }) {
        const disc = discussions.value[discussionId];
        if (!disc) return;

        const originalStoreId = disc.rag_datastore_id;
        disc.rag_datastore_id = ragDatastoreId;

        try {
            await apiClient.put(`/api/discussions/${discussionId}/rag_datastore`, { rag_datastore_id: ragDatastoreId });
            useUiStore().addNotification('RAG datastore updated for this discussion.', 'success');
        } catch (error) {
            disc.rag_datastore_id = originalStoreId;
        }
    }

    async function renameDiscussion({ discussionId, newTitle }) {
        const disc = discussions.value[discussionId];
        if (!disc || !newTitle) return;

        const originalTitle = disc.title;
        disc.title = newTitle;

        try {
            const response = await apiClient.put(`/api/discussions/${discussionId}/title`, { title: newTitle });
            disc.title = response.data.title;
            useUiStore().addNotification('Discussion renamed.', 'success');
        } catch (error) {
            disc.title = originalTitle;
        }
    }

    async function updateDiscussionMcps({ discussionId, mcp_tool_ids }) {
        const disc = discussions.value[discussionId];
        if (!disc) return;

        const originalTools = disc.mcp_tool_ids;
        disc.mcp_tool_ids = mcp_tool_ids;

        try {
            await apiClient.put(`/api/discussions/${discussionId}/tools`, { tools: mcp_tool_ids });
            useUiStore().addNotification('Tools updated for this discussion.', 'success');
        } catch (error) {
            disc.mcp_tool_ids = originalTools;
        }
    }

    async function sendMessage(payload) {
        if (!activeDiscussion.value) return;

        const authStore = useAuthStore();
        const uiStore = useUiStore();

        generationInProgress.value = true;
        activeGenerationAbortController = new AbortController();

        // If this is a normal message (not a regeneration), add the user prompt to the view.
        // For regenerations, the prompt is already visible.
        if (!payload.is_resend) {
            const tempUserMessageId = `temp-user-${Date.now()}`;
            const userMessage = {
                id: tempUserMessageId,
                sender: authStore.user.username,
                sender_type: 'user',
                content: payload.prompt,
                image_references: payload.localImageUrls || [],
                server_image_paths: payload.image_server_paths || [],
                parent_message_id: activeMessages.value.length > 0 ? activeMessages.value[activeMessages.value.length-1].id : null,
                created_at: new Date().toISOString(),
            };
            activeMessages.value.push(userMessage);
        }

        const tempAiMessageId = `temp-ai-${Date.now()}`;
        const aiMessage = {
            id: tempAiMessageId,
            sender: 'ai',
            sender_type: 'assistant',
            model_name: null,
            content: '',
            isStreaming: true,
            created_at: new Date().toISOString(),
            steps: [],
            sources: [],
            metadata: {},
        };
        activeMessages.value.push(aiMessage);

        const formData = new FormData();
        formData.append('prompt', payload.prompt);
        formData.append('image_server_paths_json', JSON.stringify(payload.image_server_paths || []));

        if (activeDiscussion.value.rag_datastore_id) {
            formData.append('rag_datastore_id', activeDiscussion.value.rag_datastore_id);
            formData.append('use_rag', 'true');
        } else {
            formData.append('use_rag', 'false');
        }

        if (activeDiscussion.value.mcp_tool_ids && activeDiscussion.value.mcp_tool_ids.length > 0) {
            formData.append('mcp_tool_ids_json', JSON.stringify(activeDiscussion.value.mcp_tool_ids));
        }

        if (payload.branch_from_message_id) {
            formData.append('branch_from_message_id', payload.branch_from_message_id);
        }
         // Tell backend this is a regeneration to create a new branch
        if(payload.is_resend){
            formData.append('is_resend', 'true');
        }

        try {
            const response = await fetch(`/api/discussions/${currentDiscussionId.value}/chat`, {
                method: 'POST',
                body: formData,
                headers: { 'Authorization': `Bearer ${authStore.token}` },
                signal: activeGenerationAbortController.signal,
            });

            if (!response.ok || !response.body) {
                const errorBody = await response.text();
                throw new Error(`HTTP error ${response.status}: ${errorBody}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const textChunk = decoder.decode(value, { stream: true });
                const lines = textChunk.split('\n').filter(line => line.trim() !== '');

                lines.forEach(line => {
                    try {
                        if(line.startsWith("data: ")){
                            line = line.substring(6)
                        }
                        const data = JSON.parse(line);
                        const messageToUpdate = activeMessages.value.find(m => m.id === tempAiMessageId);
                        if (!messageToUpdate) return;
                        
                        // Use a switch for cleaner handling of different event types
                        switch (data.type) {
                            case 'chunk': messageToUpdate.content += data.content; break;
                            case 'model_name': messageToUpdate.model_name = data.name; break;
                            case 'token_count': messageToUpdate.token_count = data.count; break;
                            case 'step_start':
                                // To prevent duplicate steps on reconnect, find existing first
                                const existingStep = messageToUpdate.steps.find(s => s.id === data.id);
                                if (!existingStep) {
                                    messageToUpdate.steps.push({ id: data.id, content: data.content, status: 'pending', type: data.type });
                                }
                                break;
                            case 'step': 
                                const stepToUpdate = messageToUpdate.steps.find(s => s.id === data.id);
                                if(stepToUpdate) {
                                    stepToUpdate.content = data.content; // update content for this step
                                } else {
                                    messageToUpdate.steps.push({ id: data.id, content: data.content, status: 'in_progress', type: data.type });
                                }
                                break;
                            case 'step_end': {
                                const step = messageToUpdate.steps.find(s => s.id === data.id);
                                if (step) { step.status = 'done'; if(data.content) step.content = data.content; }
                                break;
                            }
                            case 'sources': messageToUpdate.sources = data.sources || []; break;
                            case 'error': uiStore.addNotification(`LLM Error: ${data.content}`, 'error'); if (reader.cancel) reader.cancel(); break;
                            default:
                                if(data.message) { // Handle full message object for finalization
                                    Object.assign(messageToUpdate, processMessages([data.message], activeDiscussion.value.activeBranchId)[0]);
                                }
                                break;
                        }

                    } catch (e) {
                        console.error("Error parsing stream line:", line, e);
                    }
                });
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                uiStore.addNotification('An error occurred during generation.', 'error');
                console.error("sendMessage error:", error);
                // Remove the temporary AI message on failure
                const aiMessageIndex = activeMessages.value.findIndex(m => m.id === tempAiMessageId);
                if (aiMessageIndex > -1) activeMessages.value.splice(aiMessageIndex, 1);
            }
        } finally {
            const messageToFinalize = activeMessages.value.find(m => m.id === tempAiMessageId);
            if(messageToFinalize) messageToFinalize.isStreaming = false;
            generationInProgress.value = false;
            activeGenerationAbortController = null;
            // Refresh the entire discussion to get new branch info
            await refreshActiveDiscussion();
        }
    }

    async function stopGeneration() {
        if (activeGenerationAbortController) {
            activeGenerationAbortController.abort();
            useUiStore().addNotification('Generation stopped.', 'info');
        }
        if(currentDiscussionId.value) {
            try {
                // Also signal backend to stop, just in case.
                await apiClient.post(`/api/discussions/${currentDiscussionId.value}/stop_generation`);
            } catch(e) { console.warn("Stop signal to backend failed, but was stopped client-side.", e)}
        }
    }

    async function refreshActiveDiscussion() {
        if (!currentDiscussionId.value) return;
        const discId = currentDiscussionId.value;
        const uiStore = useUiStore();
        try {
            // A small delay can help ensure the backend has processed the last action
            await new Promise(resolve => setTimeout(resolve, 250));

            // Fetch the main discussion object to get the latest branch list and active branch ID
            const discussionResponse = await apiClient.get(`/api/discussions/${discId}`);
            const updatedDiscData = discussionResponse.data;
            const currentDisc = discussions.value[discId];

            const newActiveBranchId = updatedDiscData.active_branch_id || 'main';

            // Smart merge to preserve already loaded messages in other branches
            discussions.value[discId] = {
                ...currentDisc,
                ...updatedDiscData,
                mcp_tool_ids: updatedDiscData.active_tools || [],
                branches: currentDisc.branches, // Keep old branches for now
                messages_loaded_fully: currentDisc.messages_loaded_fully,
                branches_info: updatedDiscData.branches_info || [{ id: newActiveBranchId, name: 'Main Branch' }],
                activeBranchId: newActiveBranchId,
            };

            // Now, fetch and update the messages for the (potentially new) active branch
            const branchResponse = await apiClient.get(`/api/discussions/${discId}?branch_id=${newActiveBranchId}`);
            const finalMessages = processMessages(branchResponse.data, newActiveBranchId);
            discussions.value[discId].branches[newActiveBranchId] = finalMessages;
            discussions.value[discId].messages_loaded_fully[newActiveBranchId] = true;

        } catch(e) {
            uiStore.addNotification('Failed to refresh conversation state.', 'warning');
            console.error('Refresh active discussion failed:', e);
        }
    }

    async function updateMessageContent({ messageId, branchId, newContent }) {
        if (!currentDiscussionId.value) return;
        try {
            await apiClient.put(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}?branch_id=${branchId}`, { content: newContent });
            await refreshActiveDiscussion();
            useUiStore().addNotification('Message updated.', 'success');
        } catch(e) { /* error handled by interceptor */ }
    }

    async function deleteMessage({ messageId }) {
        if (!currentDiscussionId.value) return;
        try {
            await apiClient.delete(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}`);
            await refreshActiveDiscussion();
            useUiStore().addNotification('Message deleted.', 'success');
        } catch(e) { /* handled by interceptor */ }
    }

    async function gradeMessage({ messageId, branchId, change }) {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.put(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}/grade?branch_id=${branchId}`, { change });
            const message = findMessage(currentDiscussionId.value, messageId, branchId);
            if(message) message.user_grade = response.data.user_grade;
        } catch (e) { /* handled by interceptor */ }
    }

    async function initiateBranch(message) {
        if (!activeDiscussion.value || generationInProgress.value) return;
        const uiStore = useUiStore();



        console.log("Branching")


        // Call sendMessage to generate a new response from the chosen prompt.
        // `is_resend: true` prevents it from re-adding the prompt to the view.
        // `branch_from_message_id` tells the backend where to fork the conversation.
        await sendMessage({
            prompt: message.content,
            image_server_paths: message.server_image_paths || [],
            localImageUrls: message.image_references || [],
            is_resend: true,
            branch_from_message_id: message.id,
        });
    }

    async function switchBranch(branchId) {
        if (!activeDiscussion.value || activeDiscussion.value.activeBranchId === branchId) return;

        const disc = activeDiscussion.value;
        const discId = disc.id;
        const originalBranchId = disc.activeBranchId;
        
        try {
            // Optimistically update UI
            disc.activeBranchId = branchId;
            useUiStore().addNotification(`Switched to branch: ${disc.branches_info.find(b => b.id === branchId)?.name || branchId}`, 'info');

            // Inform backend
            await apiClient.put(`/api/discussions/${discId}/branches/${branchId}/activate`);
            
            // Fetch messages for the new branch if not already loaded
            if (!disc.messages_loaded_fully[branchId]) {
                const response = await apiClient.get(`/api/discussions/${discId}?branch_id=${branchId}`);
                const processedMessages = processMessages(response.data, branchId);
                disc.branches = { ...disc.branches, [branchId]: processedMessages };
                disc.messages_loaded_fully[branchId] = true;
            }
        } catch (error) {
            // Revert on error
            disc.activeBranchId = originalBranchId;
            console.error("Failed to switch branch:", error);
        }
    }


    async function exportDiscussions(discussionIds) {
        const uiStore = useUiStore();
        const authStore = useAuthStore();
        uiStore.addNotification('Preparing export...', 'info');
        try {
            const requestBody = { discussion_ids: discussionIds.length > 0 ? discussionIds : null };
            const response = await apiClient.post('/api/discussions/export', requestBody, { responseType: 'blob' });

            const blob = new Blob([response.data], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            a.download = `lollms_export_${authStore.user?.username}_${timestamp}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            uiStore.addNotification('Export successful!', 'success');
        } catch (error) {
            console.error("Export failed:", error);
        }
    }

    async function importDiscussions({ file, discussionIdsToImport }) {
        const uiStore = useUiStore();
        uiStore.addNotification('Importing discussions...', 'info');
        try {
            const formData = new FormData();
            formData.append('import_file', file);
            formData.append('import_request_json', JSON.stringify({ discussion_ids_to_import: discussionIdsToImport }));

            const response = await apiClient.post('/api/discussions/import', formData);

            uiStore.addNotification(response.data.message || 'Import completed.', 'success');
            await loadDiscussions();
        } catch (error) {
            console.error("Import failed:", error);
        }
    }

    return {
        discussions, currentDiscussionId, generationInProgress,
        activeDiscussion, activeMessages,
        loadDiscussions, selectDiscussion, createNewDiscussion, deleteDiscussion, toggleStarDiscussion,
        updateDiscussionRagStore,
        renameDiscussion,
        sendMessage, stopGeneration, updateMessageContent, gradeMessage, deleteMessage,
        initiateBranch,
        switchBranch, // Expose the new action
        exportDiscussions, importDiscussions,
        updateDiscussionMcps,
    };
});
