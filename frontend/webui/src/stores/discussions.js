import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';

let activeGenerationAbortController = null;

function processSingleMessage(msg) {
    if (!msg) return null;
    const authStore = useAuthStore();
    const username = authStore.user?.username?.toLowerCase();
    return {
        ...msg,
        sender_type: msg.sender_type || (msg.sender?.toLowerCase() === username ? 'user' : 'assistant'),
        events: msg.events || (msg.metadata?.events) || [],
        sources: msg.sources || (msg.metadata?.sources) || [],
        image_references: msg.image_references || [],
    };
}


export const useDiscussionsStore = defineStore('discussions', () => {
    const discussions = ref({});
    const currentDiscussionId = ref(null);
    const messages = ref([]);
    const generationInProgress = ref(false);
    const titleGenerationInProgressId = ref(null);
    const activeDiscussionContextStatus = ref(null);

    const sortedDiscussions = computed(() => {
        return Object.values(discussions.value).sort((a, b) => {
            const dateA = new Date(a.last_activity_at || a.created_at);
            const dateB = new Date(b.last_activity_at || b.created_at);
            return dateB - dateA;
        });
    });
    const activeDiscussion = computed(() => currentDiscussionId.value ? discussions.value[currentDiscussionId.value] : null);
    const activeMessages = computed(() => messages.value);

    function processMessages(rawMessages) {
        if (!Array.isArray(rawMessages)) return [];
        return rawMessages.map(msg => processSingleMessage(msg));
    }

    async function sendDiscussion({ discussionId, targetUsername }) {
        const uiStore = useUiStore();
        try {
            const response = await apiClient.post(`/api/dm/send-discussion`, { discussion_id: discussionId, target_username: targetUsername });
            uiStore.addNotification(response.data.message || `Discussion sent to ${targetUsername}!`, 'success');
            uiStore.closeModal();
        } catch (error) {
            console.error("Failed to send discussion:", error);
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
        } catch (error) {
            console.error("Failed to fetch context status:", error);
            activeDiscussionContextStatus.value = null;
        }
    }

    async function fetchDataZone(discussionId) {
        if (!discussions.value[discussionId]) return;
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}/data_zone`);
            discussions.value[discussionId].data_zone = response.data.content;
        } catch (error) {
            useUiStore().addNotification('Could not load discussion data zone.', 'error');
            if (discussions.value[discussionId]) discussions.value[discussionId].data_zone = '';
        }
    }

    async function updateDataZone({ discussionId, content }) {
        if (!discussions.value[discussionId]) return;
        try {
            await apiClient.put(`/api/discussions/${discussionId}/data_zone`, { content });
            discussions.value[discussionId].data_zone = content;
            useUiStore().addNotification('Data Zone saved successfully.', 'success');
        } catch (error) {
            throw error;
        }
    }

    async function loadDiscussions() {
        try {
            const response = await apiClient.get('/api/discussions');
            const discussionData = response.data;
            if (!Array.isArray(discussionData)) return;
            const loadedDiscussions = {};
            discussionData.forEach(d => { 
                loadedDiscussions[d.id] = { ...d, data_zone: '' }; // Initialize with data_zone
            });
            discussions.value = loadedDiscussions;
        } catch (error) { console.error("Failed to load discussions:", error); }
    }

    async function selectDiscussion(id) {
        if (!id || generationInProgress.value) return;
        const uiStore = useUiStore();
        if (currentDiscussionId.value === id) {
            uiStore.setMainView('chat');
            return; 
        }
        currentDiscussionId.value = id;
        messages.value = [];
        if (!discussions.value[id]) {
            currentDiscussionId.value = null;
            return;
        }
        uiStore.setMainView('chat');
        try {
            const response = await apiClient.get(`/api/discussions/${id}`);
            messages.value = processMessages(response.data);
            await Promise.all([
                fetchContextStatus(id),
                fetchDataZone(id) // Fetch data zone on selection
            ]);
        } catch (error) {
            useUiStore().addNotification('Failed to load messages.', 'error');
            currentDiscussionId.value = null;
        }
    }

    async function createNewDiscussion() {
        try {
            const response = await apiClient.post('/api/discussions');
            const newDiscussion = response.data;
            discussions.value[newDiscussion.id] = { ...newDiscussion, data_zone: '' };
            await selectDiscussion(newDiscussion.id);
            return newDiscussion;
        } catch (error) {
            console.error("Failed to create discussion:", error);
            useUiStore().addNotification('Failed to create new discussion.', 'error');
            throw error;
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
                messages.value = [];
            }
            uiStore.addNotification('Discussion deleted.', 'success');
        } catch(error) {}
    }

    async function pruneDiscussions() {
        const uiStore = useUiStore();
        const confirmed = await uiStore.showConfirmation({
            title: 'Prune Discussions',
            message: 'Are you sure you want to delete all empty and single-message discussions? This action cannot be undone.',
            confirmText: 'Prune'
        });
        if (!confirmed) return;
        uiStore.addNotification('Pruning discussions...', 'info');
        try {
            const response = await apiClient.post('/api/discussions/prune');
            await loadDiscussions();
            uiStore.addNotification(response.data.message || 'Pruning complete.', 'success');
        } catch (error) {
            console.error("Failed to prune discussions:", error);
            uiStore.addNotification('An error occurred while pruning.', 'error');
        }
    }

    async function generateAutoTitle(discussionId) {
        const uiStore = useUiStore();
        titleGenerationInProgressId.value = discussionId;
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/auto-title`);
            if (discussions.value[discussionId]) {
                discussions.value[discussionId].title = response.data.title;
            }
        } catch (error) {
            console.error("Failed to generate auto-title:", error);
            uiStore.addNotification('Could not generate a new title.', 'error');
        } finally {
            titleGenerationInProgressId.value = null;
        }
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
        } catch(error) {}
    }

    async function updateDiscussionRagStore({ discussionId, ragDatastoreIds }) {
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
            await apiClient.put(`/api/discussions/${discussionId}/tools`, { tools: mcp_tool_ids });
            useUiStore().addNotification('Tools updated.', 'success');
        } catch (error) {
            if (discussions.value[discussionId]) disc.active_tools = originalTools;
        }
    }

    async function sendMessage(payload) {
        const uiStore = useUiStore();
        if (generationInProgress.value) {
            uiStore.addNotification('A generation is already in progress.', 'warning');
            return;
        }
        if (!currentDiscussionId.value) {
            try {
                await createNewDiscussion();
            } catch (error) {
                return;
            }
        }
        if (!activeDiscussion.value) return;
        const authStore = useAuthStore();
        generationInProgress.value = true;
        activeGenerationAbortController = new AbortController();
        const lastMessage = messages.value.length > 0 ? messages.value[messages.value.length - 1] : null;
        
        const tempUserMessage = {
            id: `temp-user-${Date.now()}`, sender: authStore.user.username,
            sender_type: 'user', content: payload.prompt,
            localImageUrls: payload.localImageUrls || [],
            created_at: new Date().toISOString(),
            parent_message_id: lastMessage ? lastMessage.id : null
        };
        const tempAiMessage = {
            id: `temp-ai-${Date.now()}`, sender: 'assistant', sender_type: 'assistant',
            content: '', isStreaming: true, created_at: new Date().toISOString(),
            events: []
        };

        if (!payload.is_resend) {
            messages.value.push(tempUserMessage);
        }
        messages.value.push(tempAiMessage);

        const formData = new FormData();
        formData.append('prompt', payload.prompt);
        formData.append('image_server_paths_json', JSON.stringify(payload.image_server_paths || []));
        if (payload.is_resend) formData.append('is_resend', 'true');

        const messageToUpdate = messages.value.find(m => m.id === tempAiMessage.id);
        
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
                if (done) break;
                
                const textChunk = decoder.decode(value, { stream: true });
                const lines = textChunk.split('\n').filter(line => line.trim() !== '');

                lines.forEach(line => {
                    try {
                        const data = JSON.parse(line);
                        if (!messageToUpdate) return;

                        switch (data.type) {
                            case 'chunk':
                                messageToUpdate.content += data.content;
                                break;
                            case 'step':
                            case 'info':
                            case 'observation':
                            case 'thought':
                            case 'reasoning':
                            case 'tool_call':
                            case 'scratchpad':
                            case 'exception':
                            case 'error':
                            case 'step_start':
                            case 'step_end':
                                messageToUpdate.events = [...messageToUpdate.events, data];
                                break;
                            case 'new_title_start':
                                uiStore.addNotification("Building title...", "info");
                                break;
                            case 'new_title_end':
                                uiStore.addNotification(`Title set to: ${data.new_title}`, "success");
                                break;
                            case 'finalize': {
                                const finalData = data.data;
                                
                                if (finalData.ai_message) {
                                    const aiMsgIndex = messages.value.findIndex(m => m.id === tempAiMessage.id);
                                    if (aiMsgIndex !== -1) {
                                        messages.value.splice(aiMsgIndex, 1, processSingleMessage(finalData.ai_message));
                                    }
                                }
                                
                                if (finalData.user_message) {
                                    const userMsgIndex = messages.value.findIndex(m => m.id === tempUserMessage.id);
                                    if (userMsgIndex !== -1) {
                                        messages.value.splice(userMsgIndex, 1, processSingleMessage(finalData.user_message));
                                    }
                                }

                                const disc = discussions.value[currentDiscussionId.value];
                                if (disc && data.new_title) {
                                    disc.title = data.new_title;
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
            if (messageToUpdate) {
                messageToUpdate.isStreaming = false;
            }
            generationInProgress.value = false;
            activeGenerationAbortController = null;
            loadDiscussions();
            if (currentDiscussionId.value) {
                fetchContextStatus(currentDiscussionId.value);
            }
        }
    }

    async function stopGeneration() {
        const uiStore = useUiStore();
        if (activeGenerationAbortController) {
            activeGenerationAbortController.abort();
            activeGenerationAbortController = null;
        }

        if (currentDiscussionId.value) {
            try { 
                await apiClient.post(`/api/discussions/${currentDiscussionId.value}/stop_generation`); 
            } catch(e) { 
                console.warn("Backend stop signal failed, but proceeding with client-side cleanup.", e);
            }
        }
        
        generationInProgress.value = false;
        
        await loadDiscussions(); 
        
        if (currentDiscussionId.value) {
            await selectDiscussion(currentDiscussionId.value);
        }

        uiStore.addNotification('Generation stopped.', 'info');
    }

    async function updateMessageContent({ messageId, newContent }) {
        if (!currentDiscussionId.value) return;
        try {
            await apiClient.put(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}`, { content: newContent });
            const message = messages.value.find(m => m.id === messageId);
            if (message) message.content = newContent;
            useUiStore().addNotification('Message updated.', 'success');
        } catch(e) {}
    }

    async function deleteMessage({ messageId }) {
        if (!currentDiscussionId.value) return;
        try {
            await apiClient.delete(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}`);
            const index = messages.value.findIndex(m => m.id === messageId);
            if (index !== -1) {
                messages.value.splice(index, 1);
            }
            useUiStore().addNotification('Message deleted.', 'success');
            await fetchContextStatus(currentDiscussionId.value);
        } catch(e) {}
    }

    async function gradeMessage({ messageId, change }) {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.put(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}/grade`, { change });
            const message = messages.value.find(m => m.id === messageId);
            if(message) message.user_grade = response.data.user_grade;
        } catch (e) {}
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
        discussions, currentDiscussionId, messages, generationInProgress,
        titleGenerationInProgressId, activeDiscussion, activeMessages,
        sortedDiscussions, loadDiscussions, selectDiscussion, createNewDiscussion,
        deleteDiscussion, pruneDiscussions, generateAutoTitle, toggleStarDiscussion,
        updateDiscussionRagStore, renameDiscussion, updateDiscussionMcps,
        sendMessage, stopGeneration, updateMessageContent, gradeMessage,
        deleteMessage, initiateBranch, switchBranch, exportDiscussions,
        importDiscussions, sendDiscussion, $reset, activeDiscussionContextStatus, fetchContextStatus,
        fetchDataZone, updateDataZone,
    };
});