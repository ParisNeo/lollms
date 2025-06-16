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
     * @returns {Array} The processed array of message objects.
     */
    function processMessages(messages) {
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
            console.log(msg)
            return {
                ...msg,
                sender_type: senderType, // 'user', 'assistant', or 'system'
                steps: msg.steps || [],
                sources: msg.sources || [],
                metadata: msg.metadata || {}
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
                    // Map `active_tools` from backend to `mcp_tool_ids` in frontend state
                    mcp_tool_ids: d.active_tools || [], 
                    branches: {},
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
        if (!disc.messages_loaded_fully[branchId]) {
            try {
                const response = await apiClient.get(`/api/discussions/${id}?branch_id=${branchId}`);
                const processedMessages = processMessages(response.data);
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
            // Backend expects `tools` field
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
        
        const tempUserMessageId = `temp-user-${Date.now()}`;
        if (!payload.is_resend) {
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
            metadata: { sources: [] },
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

        // Send active tool IDs with the message
        if (activeDiscussion.value.mcp_tool_ids && activeDiscussion.value.mcp_tool_ids.length > 0) {
            formData.append('mcp_tool_ids_json', JSON.stringify(activeDiscussion.value.mcp_tool_ids));
        }

        if (payload.branch_from_message_id) {
            formData.append('branch_from_message_id', payload.branch_from_message_id);
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
                throw new Error(`HTTP error ${response.status}`);
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
                        const data = JSON.parse(line);
                        const messageToUpdate = activeMessages.value.find(m => m.id === tempAiMessageId);
                        if (!messageToUpdate) return;
                        
                        switch (data.type) {
                            case 'chunk': messageToUpdate.content += data.content; break;
                            case 'model_name': messageToUpdate.model_name = data.name; break;
                            case 'token_count': messageToUpdate.token_count = data.count; break;
                            case 'step_start': messageToUpdate.steps.push({ id: data.id, content: data.content, status: 'pending', type: 'step_start' }); break;
                            case 'step': messageToUpdate.steps.push({ id: data.id, content: data.content, status: 'done', type: 'step' }); break;
                            case 'step_end': {
                                const step = messageToUpdate.steps.find(s => s.id === data.id);
                                if (step) { step.status = 'done'; if(data.content) step.content = data.content; }
                                break;
                            }
                            case 'sources': if (!messageToUpdate.metadata) { messageToUpdate.metadata = {}; } messageToUpdate.metadata.sources = data.sources || []; break;
                            case 'error': uiStore.addNotification(`LLM Error: ${data.content}`, 'error'); if (reader.cancel) reader.cancel(); break;
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
                activeMessages.value.pop();
            }
        } finally {
            const messageToFinalize = activeMessages.value.find(m => m.id === tempAiMessageId);
            if(messageToFinalize) messageToFinalize.isStreaming = false;
            generationInProgress.value = false;
            activeGenerationAbortController = null;
            await refreshActiveBranch();
        }
    }
    
    async function stopGeneration() {
        if (activeGenerationAbortController) {
            activeGenerationAbortController.abort();
            useUiStore().addNotification('Generation stopped.', 'info');
        }
        if(currentDiscussionId.value) {
            try {
                await apiClient.post(`/api/discussions/${currentDiscussionId.value}/stop_generation`);
            } catch(e) { console.warn("Stop signal to backend failed, but was stopped client-side.", e)}
        }
    }

    async function refreshActiveBranch() {
        if (!activeDiscussion.value) return;
        const discId = activeDiscussion.value.id;
        const branchId = activeDiscussion.value.activeBranchId;
        try {
            await new Promise(resolve => setTimeout(resolve, 250));
            
            const localBranch = discussions.value[discId]?.branches?.[branchId] || [];
            
            const response = await apiClient.get(`/api/discussions/${discId}?branch_id=${branchId}`);
            const finalMessages = processMessages(response.data);

            const streamingMsgIndex = localBranch.findIndex(m => m.isStreaming);
            
            if (streamingMsgIndex > -1) {
                const tempMsg = localBranch[streamingMsgIndex];
                const finalMsg = finalMessages[finalMessages.length - 1];

                if (finalMsg) {
                    if (tempMsg.steps?.length > 0 && !finalMsg.steps?.length) {
                        finalMsg.steps = tempMsg.steps;
                    }
                }
            }
            
            discussions.value[discId].branches[branchId] = finalMessages;

        } catch(e) {
            useUiStore().addNotification('Failed to refresh conversation state.', 'warning');
        }
    }
    
    async function updateMessageContent({ messageId, branchId, newContent }) {
        if (!currentDiscussionId.value) return;
        try {
            await apiClient.put(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}?branch_id=${branchId}`, { content: newContent });
            await refreshActiveBranch();
            useUiStore().addNotification('Message updated.', 'success');
        } catch(e) { /* error handled by interceptor */ }
    }
    
    async function deleteMessage({ messageId, branchId }) {
        if (!currentDiscussionId.value) return;
        try {
            await apiClient.delete(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}?branch_id=${branchId}`);
            await refreshActiveBranch();
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

        const branchId = message.branch_id || activeDiscussion.value.activeBranchId;
        const branchMessages = activeDiscussion.value.branches[branchId];
        const messageIndex = branchMessages.findIndex(m => m.id === message.id);
        if (messageIndex === -1) {
            useUiStore().addNotification('Cannot find message to branch from.', 'error');
            return;
        }

        activeDiscussion.value.branches[branchId] = branchMessages.slice(0, messageIndex);
        
        const parentMessageId = message.parent_message_id;

        await sendMessage({
            prompt: message.content,
            image_server_paths: message.server_image_paths || [],
            localImageUrls: message.image_references || [],
            is_resend: true,
            branch_from_message_id: parentMessageId,
        });
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
        exportDiscussions, importDiscussions,
        updateDiscussionMcps,
    };
});