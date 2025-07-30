import { defineStore } from 'pinia';
import { ref, computed, onMounted } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';
import { useDataStore } from './data';
import { useTasksStore } from './tasks';
import useEventBus from '../services/eventBus';

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
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();
    const { on } = useEventBus();

    const discussions = ref({});
    const currentDiscussionId = ref(null);
    const messages = ref([]);
    const generationInProgress = ref(false);
    const titleGenerationInProgressId = ref(null);
    const activeDiscussionContextStatus = ref(null);
    const activeAiTasks = ref({}); // Tracks running AI tasks per discussion: { [discussionId]: 'summarize' | 'memorize' }
    const dataZonesTokenCount = ref(0);
    let tokenizeDataZonesDebounceTimer = null;


    const sortedDiscussions = computed(() => {
        return Object.values(discussions.value).sort((a, b) => {
            const dateA = new Date(a.last_activity_at || a.created_at);
            const dateB = new Date(b.last_activity_at || b.created_at);
            return dateB - dateA;
        });
    });
    const activeDiscussion = computed(() => currentDiscussionId.value ? discussions.value[currentDiscussionId.value] : null);
    const activeMessages = computed(() => messages.value);

    const activePersonality = computed(() => {
        const authStore = useAuthStore();
        const dataStore = useDataStore();
        const personalityId = authStore.user?.active_personality_id;
        if (!personalityId) return null;
        return dataStore.getPersonalityById(personalityId);
    });

    function handleTaskCompletion(task) {
        // Handle prune task completion
        if (task && task.name.startsWith('Prune empty discussions')) {
            loadDiscussions(); // Force a refresh of the discussion list
            const deletedCount = task.result?.deleted_count || 0;
            uiStore.addNotification(`Pruning complete. ${deletedCount} discussion(s) removed.`, 'success');
            return;
        }
        
        if (!task.result || !task.result.discussion_id) return;

        const { discussion_id, new_content, zone } = task.result;
        const discussion = discussions.value[discussion_id];

        if (discussion) {
            // Create a new object for reactivity
            const updatedDiscussion = { ...discussion };

            if (zone === 'discussion') {
                updatedDiscussion.discussion_data_zone = new_content;
                uiStore.addNotification('Data zone summarized successfully.', 'success');
            } else if (zone === 'memory') {
                updatedDiscussion.memory = new_content;
                const authStore = useAuthStore();
                if (authStore.user) {
                    authStore.user.memory = new_content;
                }
                uiStore.addNotification('Memorization complete.', 'success');
            }
            
            // Replace the object in the main ref to trigger reactivity
            discussions.value[discussion_id] = updatedDiscussion;
        }
        
        if (activeAiTasks.value[discussion_id]) {
            const { [discussion_id]: _, ...rest } = activeAiTasks.value;
            activeAiTasks.value = rest;
        }
    }

    function initialize() {
        onMounted(() => {
            on('task:completed', handleTaskCompletion);
        });
    }

    function processMessages(rawMessages) {
        if (!Array.isArray(rawMessages)) return [];
        return rawMessages.map(msg => processSingleMessage(msg));
    }

    async function updateDataZonesTokenCount(combinedText) {
        clearTimeout(tokenizeDataZonesDebounceTimer);
        if (!combinedText || !combinedText.trim()) {
            dataZonesTokenCount.value = 0;
            return;
        }

        tokenizeDataZonesDebounceTimer = setTimeout(async () => {
            try {
                const response = await apiClient.post('/api/discussions/tokenize', { text: combinedText });
                dataZonesTokenCount.value = response.data.tokens;
            } catch (error) {
                console.error("Data zone tokenization failed:", error);
                dataZonesTokenCount.value = 0; // Reset on error
            }
        }, 750);
    }
    
    async function refreshDataZones(discussionId) {
        const uiStore = useUiStore();
        if (!discussions.value[discussionId]) return;
        try {
            uiStore.addNotification('Refreshing data zones...', 'info');
            await fetchDataZones(discussionId);
            uiStore.addNotification('Data zones refreshed.', 'success');
        } catch(error) {
            uiStore.addNotification('Failed to refresh data zones.', 'error');
        }
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

    async function fetchDataZones(discussionId) {
        if (!discussions.value[discussionId]) return;
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}/data_zones`);
            discussions.value[discussionId] = {
                ...discussions.value[discussionId],
                ...response.data
            };
        } catch (error) {
            useUiStore().addNotification('Could not load discussion data zones.', 'error');
            if (discussions.value[discussionId]) {
                 discussions.value[discussionId].discussion_data_zone = '';
                 discussions.value[discussionId].personality_data_zone = '';
                 discussions.value[discussionId].memory = '';
            }
        }
    }

    async function updateDataZone({ discussionId, content }) {
        if (!discussions.value[discussionId]) return;
        try {
            await apiClient.put(`/api/discussions/${discussionId}/data_zone`, { content });
            discussions.value[discussionId].discussion_data_zone = content;
        } catch (error) {
            useUiStore().addNotification('Failed to save discussion data zone.', 'error');
            throw error;
        }
    }
    
    async function summarizeDiscussionDataZone(discussionId, prompt = null) {
        if (activeAiTasks.value[discussionId]) {
            uiStore.addNotification(`An AI task (${activeAiTasks.value[discussionId]}) is already running for this discussion.`, 'warning');
            return;
        }
        if (!discussions.value[discussionId]) return;
        try {
            const formData = new FormData();
            if (prompt) {
                formData.append('prompt', prompt);
            }
            const response = await apiClient.post(`/api/discussions/${discussionId}/summarize_data_zone`, formData);
            const task = response.data;
            activeAiTasks.value[discussionId] = 'summarize';
            tasksStore.addTask(task);
            uiStore.addNotification('Summarization task started.', 'info');
        } catch (error) {
            // Handled by interceptor
        }
    }

    async function memorizeLTM(discussionId) {
        if (activeAiTasks.value[discussionId]) {
            uiStore.addNotification(`An AI task (${activeAiTasks.value[discussionId]}) is already running for this discussion.`, 'warning');
            return;
        }
        if (!discussions.value[discussionId]) return;
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/memorize`);
            const task = response.data;
            activeAiTasks.value[discussionId] = 'memorize';
            tasksStore.addTask(task);
            uiStore.addNotification('Memorization task started.', 'info');
        } catch (error) {
            // Handled by interceptor
        }
    }

    async function loadDiscussions() {
        try {
            const response = await apiClient.get('/api/discussions');
            const discussionData = response.data;
            if (!Array.isArray(discussionData)) return;
            const newDiscussions = {};
            discussionData.forEach(d => {
                const existingData = discussions.value[d.id] || {};
                newDiscussions[d.id] = {
                    ...d,
                    discussion_data_zone: existingData.discussion_data_zone || '',
                    personality_data_zone: existingData.personality_data_zone || '',
                    memory: existingData.memory || ''
                };
            });
            discussions.value = newDiscussions;
        } catch (error) { console.error("Failed to load discussions:", error); }
    }

    async function selectDiscussion(id) {
        if (!id || generationInProgress.value) return;
        const uiStore = useUiStore();
        const authStore = useAuthStore();
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
                fetchDataZones(id),
                authStore.fetchDataZone()
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
            discussions.value[newDiscussion.id] = { 
                ...newDiscussion,
                discussion_data_zone: '',
                personality_data_zone: '',
                memory: ''
            };
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
        
        try {
            const response = await apiClient.post('/api/discussions/prune');
            const task = response.data;
            tasksStore.addTask(task);
            uiStore.addNotification(`Pruning task '${task.name}' has started.`, 'info');
        } catch (error) {
            console.error("Failed to start pruning task:", error);
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
            id: `temp-ai-${Date.now()}`, sender: activePersonality.value?.name || 'assistant', sender_type: 'assistant',
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
        generationInProgress.value = false;
        
        if (currentDiscussionId.value) {
            try { 
                await apiClient.post(`/api/discussions/${currentDiscussionId.value}/stop_generation`); 
            } catch(e) { 
                console.warn("Backend stop signal failed, but proceeding with client-side cleanup.", e);
            }
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
        const discussionId = currentDiscussionId.value;
        const uiStore = useUiStore();

        // Find the index for optimistic update
        const messageIndex = messages.value.findIndex(m => m.id === messageId);
        if (messageIndex === -1) {
            console.warn("Attempted to delete a message not in the current view. Re-fetching for safety.");
            await selectDiscussion(discussionId);
            return;
        }

        // 1. Optimistic UI Update
        const oldMessages = [...messages.value];
        // Remove the target message and all subsequent messages in the current branch view.
        messages.value.splice(messageIndex);
        
        try {
            // 2. API Call
            await apiClient.delete(`/api/discussions/${discussionId}/messages/${messageId}`);
            
            // 3. Re-sync with backend state to handle any branch changes
            // This also implicitly handles refreshing context status and data zones.
            await selectDiscussion(discussionId); 

            uiStore.addNotification('Message and branch deleted.', 'success');

        } catch (error) {
            console.error("Error deleting message:", error);
            uiStore.addNotification('Failed to delete message. Reverting change.', 'error');
            // 4. Rollback UI on failure
            messages.value = oldMessages;
        }
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
        titleGenerationInProgressId.value = null;
        activeDiscussionContextStatus.value = null;
        activeAiTasks.value = {};
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
        fetchDataZones, updateDataZone, activePersonality,
        summarizeDiscussionDataZone, memorizeLTM, activeAiTasks,
        dataZonesTokenCount, updateDataZonesTokenCount,
        initialize,
        refreshDataZones
    };
});