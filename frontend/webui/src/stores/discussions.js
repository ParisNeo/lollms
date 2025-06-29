import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';

let activeGenerationAbortController = null;

export const useDiscussionsStore = defineStore('discussions', () => {
    // --- STATE ---
    const discussions = ref({});
    const currentDiscussionId = ref(null);
    const messages = ref([]);
    const generationInProgress = ref(false);

    // --- GETTERS ---
    const activeDiscussion = computed(() => currentDiscussionId.value ? discussions.value[currentDiscussionId.value] : null);
    const activeMessages = computed(() => messages.value);

    // --- HELPERS ---
    function processMessages(rawMessages) {
        if (!Array.isArray(rawMessages)) return [];
        const authStore = useAuthStore();
        const username = authStore.user?.username?.toLowerCase();
        return rawMessages.map(msg => ({
            ...msg,
            sender_type: msg.sender_type || (msg.sender?.toLowerCase() === username ? 'user' : 'assistant'),
            steps: msg.steps || [],
            sources: msg.sources || [],
        }));
    }

    // --- ACTIONS ---

    async function loadDiscussions() {
        try {
            const response = await apiClient.get('/api/discussions');
            const discussionData = response.data;
            if (!Array.isArray(discussionData)) return;
            const loadedDiscussions = {};
            discussionData.forEach(d => { loadedDiscussions[d.id] = d; });
            discussions.value = loadedDiscussions;
        } catch (error) { console.error("Failed to load discussions:", error); }
    }

    async function selectDiscussion(id) {
        if (!id || generationInProgress.value) return;
        currentDiscussionId.value = id;
        messages.value = [];
        if (!discussions.value[id]) {
            currentDiscussionId.value = null;
            return;
        }
        try {
            const response = await apiClient.get(`/api/discussions/${id}`);
            messages.value = processMessages(response.data);
        } catch (error) {
            useUiStore().addNotification('Failed to load messages.', 'error');
            currentDiscussionId.value = null;
        }
    }

    async function createNewDiscussion() {
        try {
            const response = await apiClient.post('/api/discussions');
            discussions.value[response.data.id] = response.data;
            await selectDiscussion(response.data.id);
        } catch (error) { console.error("Failed to create discussion:", error); }
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
                messages.value = [];
            }
            uiStore.addNotification('Discussion deleted.', 'success');
        } catch(error) { /* Handled */ }
    }

    async function toggleStarDiscussion(discussionId) {
        const disc = discussions.value[discussionId];
        if (!disc) return;
        const method = disc.is_starred ? 'DELETE' : 'POST';
        try {
            const response = await apiClient({ url: `/api/discussions/${discussionId}/star`, method });
            if (discussions.value[discussionId]) {
                discussions.value[discussionId].is_starred = response.data.is_starred;
            }
        } catch(error) { /* Handled */ }
    }

    async function updateDiscussionRagStore({ discussionId, ragDatastoreIds }) {
        console.log(ragDatastoreIds)
        const disc = discussions.value[discussionId];
        if (!disc) return;
        const originalStoreIds = disc.rag_datastore_ids;
        disc.rag_datastore_ids = ragDatastoreIds;
        try {
            await apiClient.put(`/api/discussions/${discussionId}/rag_datastore`, { rag_datastore_ids: ragDatastoreIds });
            useUiStore().addNotification('RAG datastores updated.', 'success');
        } catch (error) {
            if (discussions.value[discussionId]) disc.rag_datastore_ids = originalStoreIds;
            useUiStore().addNotification('Failed to update RAG datastores.', 'error');
        }
    }

    async function renameDiscussion({ discussionId, newTitle }) {
        const disc = discussions.value[discussionId];
        if (!disc || !newTitle) return;
        const originalTitle = disc.title;
        disc.title = newTitle;
        try {
            const response = await apiClient.put(`/api/discussions/${discussionId}/title`, { title: newTitle });
            if (discussions.value[discussionId]) discussions.value[discussionId].title = response.data.title;
            useUiStore().addNotification('Discussion renamed.', 'success');
        } catch (error) {
            if (discussions.value[discussionId]) disc.title = originalTitle;
        }
    }

    async function updateDiscussionMcps({ discussionId, mcp_tool_ids }) {
        const disc = discussions.value[discussionId];
        if (!disc) return;
        const originalTools = disc.active_tools;
        disc.active_tools = mcp_tool_ids;
        try {
             // This endpoint should be correct now after consolidating routers.
            await apiClient.put(`/api/discussions/${discussionId}/tools`, { tools: mcp_tool_ids });
            useUiStore().addNotification('Tools updated.', 'success');
        } catch (error) {
            if (discussions.value[discussionId]) disc.active_tools = originalTools;
        }
    }

    async function sendMessage(payload) {
        if (!activeDiscussion.value) return;
        const authStore = useAuthStore();
        const uiStore = useUiStore();
        generationInProgress.value = true;
        activeGenerationAbortController = new AbortController();

        const lastMessage = messages.value.length > 0 ? messages.value[messages.value.length - 1] : null;

        // Keep references to the temporary message objects
        const tempUserMessage = {
            id: `temp-user-${Date.now()}`, sender: authStore.user.username,
            sender_type: 'user', content: payload.prompt,
            image_references: payload.localImageUrls || [],
            created_at: new Date().toISOString(),
            parent_message_id: lastMessage ? lastMessage.id : null
        };

        const tempAiMessage = {
            id: `temp-ai-${Date.now()}`, sender: 'assistant', sender_type: 'assistant',
            content: '', isStreaming: true, created_at: new Date().toISOString(),
            steps: []
        };

        if (!payload.is_resend) {
            messages.value.push(tempUserMessage);
        }
        messages.value.push(tempAiMessage);

        const formData = new FormData();
        formData.append('prompt', payload.prompt);
        formData.append('image_server_paths_json', JSON.stringify(payload.image_server_paths || []));
        if (payload.is_resend) formData.append('is_resend', 'true');

        let streamDidComplete = false;

        const messageToUpdate = messages.value.find(m => m.id === tempAiMessage.id);
        let contentBuffer = '';
        let stepsBuffer = [];
        let updateInterval = null;

        if (messageToUpdate) {
            updateInterval = setInterval(() => {
                if (contentBuffer.length > 0) { messageToUpdate.content += contentBuffer; contentBuffer = ''; }
                if (stepsBuffer.length > 0) { messageToUpdate.steps.push(...stepsBuffer); stepsBuffer = []; }
            }, 100);
        }

        try {
            const response = await fetch(`/api/discussions/${currentDiscussionId.value}/chat`, {
                method: 'POST', body: formData,
                headers: { 'Authorization': `Bearer ${authStore.token}` },
                signal: activeGenerationAbortController.signal,
            });
            if (!response.ok || !response.body) throw new Error(`HTTP error ${response.status}`);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            while (true) {
                const { done, value } = await reader.read();
                if (done) { break; } // The 'finalize' event now signals completion
                
                const textChunk = decoder.decode(value, { stream: true });
                const lines = textChunk.split('\n').filter(line => line.trim() !== '');
                lines.forEach(line => {
                    try {
                        const data = JSON.parse(line);
                        if (!messageToUpdate) return;
                        switch (data.type) {
                            case 'chunk': contentBuffer += data.content; break;
                            case 'step_start': stepsBuffer.push({ id: data.id, content: data.content, status: 'pending' }); break;
                            case 'thought': stepsBuffer.push({ id: data.id, content: data.content, status: 'done' }); break;
                            case 'step': {
                                stepsBuffer.push({ id: data.id, content: data.content, status: 'done' }); break;
                            }
                            case 'step_end': {
                                const step = messageToUpdate.steps.find(s => s.id === data.id) || stepsBuffer.find(s => s.id === data.id);
                                if (step) {
                                    step.status = 'done';
                                    if (data.content) {
                                        step.content = data.content;
                                    }
                                }
                                break;
                            }
                            // --- 'FINALIZE' EVENT HANDLER WITH THE FIX ---
                            case 'finalize': {
                                streamDidComplete = true;
                                const finalData = data.data;

                                const aiMessageToFinalize = messages.value.find(m => m.id === tempAiMessage.id);
                                if (aiMessageToFinalize && finalData.ai_message) {
                                    
                                    // --- START OF THE FIX ---
                                    
                                    // 1. Preserve the steps that were collected during the stream.
                                    const collectedSteps = aiMessageToFinalize.steps;

                                    // 2. Update the message object with the final data from the server.
                                    //    This will overwrite the 'steps' property if it's not in the final payload.
                                    Object.assign(aiMessageToFinalize, finalData.ai_message);

                                    // 3. CRITICAL: Restore the collected steps to the updated message object.
                                    aiMessageToFinalize.steps = collectedSteps;

                                    // --- END OF THE FIX ---
                                }

                                const userMessageToFinalize = messages.value.find(m => m.id === tempUserMessage.id);
                                if (userMessageToFinalize && finalData.user_message) {
                                     Object.assign(userMessageToFinalize, finalData.user_message);
                                }
                                
                                const disc = discussions.value[currentDiscussionId.value];
                                if (disc && disc.title.startsWith("New Discussion") && finalData.user_message) {
                                    const newTitle = finalData.user_message.content.split('\n')[0].substring(0, 50);
                                    renameDiscussion({discussionId: disc.id, newTitle: newTitle});
                                }
                                break;
                            }
                            case 'error':
                                uiStore.addNotification(`LLM Error: ${data.content}`, 'error');
                                if (reader.cancel) reader.cancel();
                                break;
                        }
                    } catch (e) { console.error("Error parsing stream line:", line, e); }
                });
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                uiStore.addNotification('An error occurred during generation.', 'error');
                const aiMessageIndex = messages.value.findIndex(m => m.id === tempAiMessage.id);
                if (aiMessageIndex > -1) messages.value.splice(aiMessageIndex, 1);
            }
        } finally {
            if (updateInterval) { clearInterval(updateInterval); }
            if (messageToUpdate) {
                if (contentBuffer.length > 0) messageToUpdate.content += contentBuffer;
                if (stepsBuffer.length > 0) messageToUpdate.steps.push(...stepsBuffer);
            }
            generationInProgress.value = false;
            activeGenerationAbortController = null;
            
            if(messageToUpdate) messageToUpdate.isStreaming = false;
        }
    }

    async function stopGeneration() {
        if (activeGenerationAbortController) activeGenerationAbortController.abort();
        if(currentDiscussionId.value) {
            try { await apiClient.post(`/api/discussions/${currentDiscussionId.value}/stop_generation`); }
            catch(e) { console.warn("Backend stop signal failed.", e)}
        }
    }

    async function updateMessageContent({ messageId, newContent }) {
        if (!currentDiscussionId.value) return;
        try {
            await apiClient.put(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}`, { content: newContent });
            await selectDiscussion(currentDiscussionId.value);
            useUiStore().addNotification('Message updated.', 'success');
        } catch(e) { /* handled */ }
    }

    async function deleteMessage({ messageId }) {
        if (!currentDiscussionId.value) return;
        try {
            await apiClient.delete(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}`);
            await selectDiscussion(currentDiscussionId.value);
            useUiStore().addNotification('Message and branch deleted.', 'success');
        } catch(e) { /* handled */ }
    }

    async function gradeMessage({ messageId, change }) {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.put(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}/grade`, { change });
            const message = messages.value.find(m => m.id === messageId);
            if(message) message.user_grade = response.data.user_grade;
        } catch (e) { /* handled */ }
    }

    async function initiateBranch(userMessageToResend) {
        if (!activeDiscussion.value || generationInProgress.value || !userMessageToResend || userMessageToResend.sender_type !== 'user') return;
        const uiStore = useUiStore();
        try {
            await apiClient.put(`/api/discussions/${currentDiscussionId.value}/active_branch`, { active_branch_id: userMessageToResend.id });
            const promptIndex = messages.value.findIndex(m => m.id === userMessageToResend.id);
            if (promptIndex > -1) messages.value = messages.value.slice(0, promptIndex + 1);
            else { await selectDiscussion(currentDiscussionId.value); return; }
            await sendMessage({
                prompt: userMessageToResend.content,
                image_server_paths: userMessageToResend.server_image_paths || [],
                localImageUrls: userMessageToResend.image_references || [],
                is_resend: true,
            });
        } catch(e) {
            uiStore.addNotification('Failed to start new branch.', 'error');
            console.error(e);
            if (currentDiscussionId.value) await selectDiscussion(currentDiscussionId.value);
        }
    }

    async function switchBranch(newBranchMessageId) {
        if (!activeDiscussion.value || generationInProgress.value) return;
        try {
            await apiClient.put(`/api/discussions/${currentDiscussionId.value}/active_branch`, { active_branch_id: newBranchMessageId });
            await selectDiscussion(currentDiscussionId.value);
            useUiStore().addNotification(`Switched branch.`, 'info');
        } catch (error) {
            console.error("Failed to switch branch:", error);
            await selectDiscussion(currentDiscussionId.value);
        }
    }

    async function exportDiscussions(discussionIds) {
        const uiStore = useUiStore();
        const authStore = useAuthStore();
        uiStore.addNotification('Preparing export...', 'info');
        try {
            const response = await apiClient.post('/api/discussions/export', { discussion_ids: discussionIds.length > 0 ? discussionIds : null }, { responseType: 'blob' });
            const blob = new Blob([response.data], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `lollms_export_${authStore.user?.username}_${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
            document.body.appendChild(a); a.click(); document.body.removeChild(a);
            URL.revokeObjectURL(url);
            uiStore.addNotification('Export successful!', 'success');
        } catch (error) { console.error("Export failed:", error); }
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
        } catch (error) { console.error("Import failed:", error); }
    }
    function $reset() {
        discussions.value = {};
        currentDiscussionId.value = null;
        messages.value = [];
        generationInProgress.value = false;
    }
    return {
        discussions,
        currentDiscussionId,
        messages,
        generationInProgress,
        activeDiscussion,
        activeMessages,
        loadDiscussions,
        selectDiscussion,
        createNewDiscussion,
        deleteDiscussion,
        toggleStarDiscussion,
        updateDiscussionRagStore,
        renameDiscussion,
        updateDiscussionMcps,
        sendMessage,
        stopGeneration,
        updateMessageContent,
        gradeMessage,
        deleteMessage,
        initiateBranch,
        switchBranch,
        exportDiscussions,
        importDiscussions,
        $reset,
    };
});