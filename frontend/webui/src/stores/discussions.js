// frontend/webui/src/stores/discussions.js
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
    const dataStore = useDataStore();
    const username = authStore.user?.username?.toLowerCase();
    
    // Determine if the model used supports vision
    const modelUsedId = `${msg.binding_name}/${msg.model_name}`;
    const modelInfo = dataStore.availableLollmsModels.find(m => m.id === modelUsedId);
    const visionSupport = modelInfo?.alias?.has_vision ?? true; // Default to true if no alias info

    return {
        ...msg,
        sender_type: msg.sender_type || (msg.sender?.toLowerCase() === username ? 'user' : 'assistant'),
        events: msg.events || (msg.metadata?.events) || [],
        sources: msg.sources || (msg.metadata?.sources) || [],
        image_references: msg.image_references || [],
        active_images: msg.active_images || [],
        vision_support: visionSupport, // Add vision support flag
    };
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
    });
}


export const useDiscussionsStore = defineStore('discussions', () => {
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();
    const { on, emit } = useEventBus();

    const discussions = ref({});
    const currentDiscussionId = ref(null);
    const messages = ref([]);
    const generationInProgress = ref(false);
    const titleGenerationInProgressId = ref(null);
    const activeDiscussionContextStatus = ref(null);
    const activeAiTasks = ref({}); // Tracks running AI tasks per discussion: { [discussionId]: { type: 'summarize' | 'memorize', taskId: '...' } }
    
    // MODIFIED: From single value to an object for individual tracking
    const liveDataZoneTokens = ref({
        discussion: 0,
        user: 0,
        personality: 0,
        memory: 0
    });

    // MODIFIED: Computed property now sums up the live tokens
    const dataZonesTokenCount = computed(() => {
        return liveDataZoneTokens.value.discussion + 
               liveDataZoneTokens.value.user + 
               liveDataZoneTokens.value.personality + 
               liveDataZoneTokens.value.memory;
    });

    // NEW: Computed property to sum data zone tokens from the official context status
    const dataZonesTokensFromContext = computed(() => {
        if (!activeDiscussionContextStatus.value?.zones?.system_context?.breakdown || typeof activeDiscussionContextStatus.value.zones.system_context.breakdown !== 'object') {
            return 0;
        }
        const breakdown = activeDiscussionContextStatus.value.zones.system_context.breakdown;
        const zoneKeys = ['memory', 'user_data_zone', 'discussion_data_zone', 'personality_data_zone', 'pruning_summary'];
        return zoneKeys.reduce((total, key) => total + (breakdown[key]?.tokens || 0), 0);
    });


    const sortedDiscussions = computed(() => {
        return Object.values(discussions.value).sort((a, b) => {
            const dateA = new Date(a.last_activity_at || a.created_at);
            const dateB = new Date(b.last_activity_at || b.created_at);
            return dateB - dateA;
        });
    });
    const activeDiscussion = computed(() => currentDiscussionId.value ? discussions.value[currentDiscussionId.value] : null);
    const activeMessages = computed(() => messages.value);

    const activeDiscussionContainsCode = computed(() => {
        if (!activeMessages.value || activeMessages.value.length === 0) return false;
        return activeMessages.value.some(msg => msg.content && msg.content.includes('```'));
    });

    const activePersonality = computed(() => {
        const authStore = useAuthStore();
        const dataStore = useDataStore();
        const personalityId = authStore.user?.active_personality_id;
        if (!personalityId) return null;
        return dataStore.getPersonalityById(personalityId);
    });

    function _clearActiveAiTask(discussionId) {
        if (activeAiTasks.value[discussionId]) {
            const newActiveTasks = { ...activeAiTasks.value };
            delete newActiveTasks[discussionId];
            activeAiTasks.value = newActiveTasks;
        }
    }

    function handleTaskCompletion(task) {
        if (task && task.name.startsWith('Prune empty discussions')) {
            loadDiscussions();
            const deletedCount = task.result?.deleted_count || 0;
            uiStore.addNotification(`Pruning complete. ${deletedCount} discussion(s) removed.`, 'success');
            return;
        }
        
        let discussionIdForTask = null;
        for (const [discussionId, activeTaskInfo] of Object.entries(activeAiTasks.value)) {
            if (activeTaskInfo && activeTaskInfo.taskId === task.id) {
                discussionIdForTask = discussionId;
                break;
            }
        }

        if (!discussionIdForTask) return;
        
        // The component (`ChatView`) is now responsible for triggering the data refresh.
        // This handler's only job is to show a final notification.
        if (task.status === 'completed') {
            const { zone } = task.result || {};
            if (zone === 'discussion') {
                uiStore.addNotification('Data zone processed successfully.', 'success');
            } else if (zone === 'memory') {
                uiStore.addNotification('Memorization complete.', 'success');
            } else {
                uiStore.addNotification(`Task '${task.name}' completed.`, 'success');
            }
        } else if (task.status === 'failed') {
            uiStore.addNotification(`Task '${task.name}' failed.`, 'error');
        } else if (task.status === 'cancelled') {
            uiStore.addNotification(`Task '${task.name}' was cancelled.`, 'warning');
        }
    }

    onMounted(() => {
        on('task:completed', handleTaskCompletion);
    });

    function processMessages(rawMessages) {
        if (!Array.isArray(rawMessages)) return [];
        return rawMessages.map(msg => processSingleMessage(msg));
    }

    async function refreshActiveDiscussionMessages() {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.get(`/api/discussions/${currentDiscussionId.value}`);
            messages.value = processMessages(response.data);
            emit('discussion:refreshed'); // Emit event for scrolling
            
            // Also refresh context status
            await fetchContextStatus(currentDiscussionId.value);
        } catch (error) {
            useUiStore().addNotification('Could not refresh discussion after generation.', 'error');
        }
    }

    function setUserDataZoneContent(discussionId, content) {
        const discussion = discussions.value[discussionId];
        if (discussion) {
            discussion.discussion_data_zone = content;
        }
    
        const taskInfo = activeAiTasks.value[discussionId];
        if (taskInfo?.type === 'summarize') {
            _clearActiveAiTask(discussionId);
            tasksStore.cancelTask(taskInfo.taskId);
            uiStore.addNotification('Processing cancelled due to manual edit.', 'info');
        }
    }

    // NEW: Action to update live token counts
    function updateLiveTokenCount(zone, count) {
        if (liveDataZoneTokens.value.hasOwnProperty(zone)) {
            liveDataZoneTokens.value[zone] = count;
        }
    }
    
    async function refreshDataZones(discussionId) {
        const uiStore = useUiStore();
        if (!discussions.value[discussionId]) return;
        try {
            await fetchDataZones(discussionId);
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
            
            // NEW: Sync live token counts with the official backend values
            const breakdown = response.data?.zones?.system_context?.breakdown || {};
            liveDataZoneTokens.value.discussion = breakdown.discussion_data_zone?.tokens || 0;
            liveDataZoneTokens.value.user = breakdown.user_data_zone?.tokens || 0;
            liveDataZoneTokens.value.personality = breakdown.personality_data_zone?.tokens || 0;
            liveDataZoneTokens.value.memory = breakdown.memory?.tokens || 0;

        } catch (error) {
            console.error("Failed to fetch context status:", error);
            activeDiscussionContextStatus.value = null;
        }
    }

    async function fetchDataZones(discussionId) {
        const discussion = discussions.value[discussionId];
        if (!discussion) return;
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}/data_zones`);
            const data = response.data;

            if (discussions.value[discussionId]) {
                discussions.value[discussionId] = {
                    ...discussions.value[discussionId],
                    ...data
                }
            }

        } catch (error) {
            useUiStore().addNotification('Could not load discussion data zones.', 'error');
            discussion.discussion_data_zone = '';
            discussion.personality_data_zone = '';
            discussion.memory = '';
            discussion.discussion_images = [];
            discussion.active_discussion_images = [];
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
            uiStore.addNotification(`An AI task (${activeAiTasks.value[discussionId].type}) is already running for this discussion.`, 'warning');
            return;
        }
        if (!discussions.value[discussionId]) return;
        try {
            const formData = new FormData();
            if (prompt) {
                formData.append('prompt', prompt);
            }
            const response = await apiClient.post(`/api/discussions/${discussionId}/process_data_zone`, formData);
            const task = response.data;
            
            uiStore.closeModal('summaryPromptModal');
            
            activeAiTasks.value[discussionId] = { type: 'summarize', taskId: task.id };
            
            tasksStore.addTask(task);
            
            uiStore.addNotification(`Content processing started. This is a long process that runs in the background. Check the Task Manager for progress.`, 'info', { duration: 10000 });
            
        } catch (error) {
            // Handled by interceptor
            if (activeAiTasks.value[discussionId]) {
                const { [discussionId]: _, ...rest } = activeAiTasks.value;
                activeAiTasks.value = rest;
            }
        }
    }

    async function memorizeLTM(discussionId) {
        if (activeAiTasks.value[discussionId]) {
            uiStore.addNotification(`An AI task (${activeAiTasks.value[discussionId].type}) is already running for this discussion.`, 'warning');
            return;
        }
        if (!discussions.value[discussionId]) return;
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/memorize`);
            const task = response.data;
            activeAiTasks.value[discussionId] = { type: 'memorize', taskId: task.id };
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
        // NEW: Reset live token counts on discussion switch
        liveDataZoneTokens.value = { discussion: 0, user: 0, personality: 0, memory: 0 };
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
        const dataStore = useDataStore();
        const authStore = useAuthStore();
        
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

        const selectedModelId = authStore.user?.lollms_model_name;
        const selectedModel = dataStore.availableLollmsModels.find(m => m.id === selectedModelId);
        const hasVision = selectedModel?.alias?.has_vision ?? true;
        let imagesToSend = payload.image_server_paths || [];
        
        if (!hasVision && imagesToSend.length > 0) {
            uiStore.addNotification(
                `The selected model '${selectedModel.name}' does not support vision. Images will be ignored.`,
                'warning',
                6000
            );
            imagesToSend = [];
        }


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
        formData.append('image_server_paths_json', JSON.stringify(imagesToSend));
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
            await refreshActiveDiscussionMessages();
            loadDiscussions();
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
            await refreshActiveDiscussionMessages();
        }

        uiStore.addNotification('Generation stopped.', 'info');
    }

    async function toggleImageActivation({ messageId, imageIndex }) {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.put(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}/images/${imageIndex}/toggle`);
            const updatedMessage = processSingleMessage(response.data);
            const index = messages.value.findIndex(m => m.id === messageId);
            if (index !== -1) {
                messages.value[index] = updatedMessage;
            }
            await fetchContextStatus(currentDiscussionId.value);
        } catch (error) {
            uiStore.addNotification('Failed to toggle image status.', 'error');
        }
    }

    async function addManualMessage({ sender_type }) {
        if (!currentDiscussionId.value) return;

        const authStore = useAuthStore();
        const lastMessage = messages.value.length > 0 ? messages.value[messages.value.length - 1] : null;

        let senderName = authStore.user.username;
        if (sender_type === 'assistant') {
            senderName = activePersonality.value?.name || 'assistant';
        }

        const newMessage = {
            id: `temp-manual-${Date.now()}`,
            sender: senderName,
            sender_type: sender_type,
            content: '',
            created_at: new Date().toISOString(),
            parent_message_id: lastMessage ? lastMessage.id : null,
            startInEditMode: true // Special flag for the UI
        };

        messages.value.push(newMessage);
    }

    async function saveManualMessage({ tempId, content }) {
        if (!currentDiscussionId.value) return;
        const tempMessage = messages.value.find(m => m.id === tempId);
        if (!tempMessage) return;

        try {
            const response = await apiClient.post(`/api/discussions/${currentDiscussionId.value}/messages`, {
                content: content,
                sender_type: tempMessage.sender_type,
                parent_message_id: tempMessage.parent_message_id
            });

            const finalMessage = processSingleMessage(response.data);
            const index = messages.value.findIndex(m => m.id === tempId);
            if (index !== -1) {
                messages.value.splice(index, 1, finalMessage);
            }
            uiStore.addNotification("Message added successfully.", "success");
        } catch (error) {
            const index = messages.value.findIndex(m => m.id === tempId);
            if (index !== -1) {
                messages.value.splice(index, 1);
            }
        }
    }


    async function saveMessageChanges({ messageId, newContent, keptImagesB64, newImageFiles }) {
        if (!currentDiscussionId.value) return;
        
        const newImagesAsBase64 = await Promise.all(newImageFiles.map(file => fileToBase64(file)));

        const payload = {
            content: newContent,
            kept_images_b64: keptImagesB64,
            new_images_b64: newImagesAsBase64
        };

        try {
            const response = await apiClient.put(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}`, payload);
            const updatedMessage = processSingleMessage(response.data);
            const index = messages.value.findIndex(m => m.id === messageId);
            if (index !== -1) {
                messages.value[index] = updatedMessage;
            }
            uiStore.addNotification('Message updated.', 'success');
            await fetchContextStatus(currentDiscussionId.value);
        } catch (e) {
            // Error handled by global interceptor
        }
    }

    async function deleteMessage({ messageId }) {
        if (!currentDiscussionId.value) return;
        const discussionId = currentDiscussionId.value;
        const uiStore = useUiStore();

        const messageIndex = messages.value.findIndex(m => m.id === messageId);
        if (messageIndex === -1) {
            console.warn("Attempted to delete a message not in the current view. Re-fetching for safety.");
            await selectDiscussion(discussionId);
            return;
        }

        const oldMessages = [...messages.value];
        messages.value.splice(messageIndex);
        
        try {
            await apiClient.delete(`/api/discussions/${discussionId}/messages/${messageId}`);
            await selectDiscussion(discussionId); 
            uiStore.addNotification('Message and branch deleted.', 'success');
        } catch (error) {
            console.error("Error deleting message:", error);
            uiStore.addNotification('Failed to delete message. Reverting change.', 'error');
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

    async function exportCodeToZip(discussionId) {
        if (!discussionId) return;
        const uiStore = useUiStore();
        uiStore.addNotification('Preparing code export...', 'info');
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}/export-code`, {
                responseType: 'blob'
            });
            const blob = new Blob([response.data], { type: 'application/zip' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            
            let filename = `code_export_${discussionId.substring(0, 8)}.zip`;
            const contentDisposition = response.headers['content-disposition'];
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch && filenameMatch.length === 2) {
                    filename = filenameMatch[1];
                }
            }
            
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

        } catch (error) {
            const reader = new FileReader();
            reader.onload = () => {
                try {
                    const errorJson = JSON.parse(reader.result);
                    uiStore.addNotification(errorJson.detail || 'Failed to export code.', 'error');
                } catch {
                    uiStore.addNotification('An unknown error occurred during code export.', 'error');
                }
            };
            reader.readAsText(error.response.data);
            console.error("Code export failed:", error);
        }
    }

    async function exportMessageCodeToZip({ content, title }) {
        if (!content || !content.includes('```')) {
            uiStore.addNotification('No code blocks found in this message.', 'info');
            return;
        }
        uiStore.addNotification('Preparing code export...', 'info');
        try {
            const response = await apiClient.post('/api/discussions/export-message-code', {
                content: content,
                discussion_title: title,
            }, {
                responseType: 'blob'
            });

            const blob = new Blob([response.data], { type: 'application/zip' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            
            let filename = `code_export_${title.replace(/\s/g, '_')}.zip`;
            const contentDisposition = response.headers['content-disposition'];
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch && filenameMatch.length === 2) {
                    filename = filenameMatch[1];
                }
            }
            
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

        } catch (error) {
            const reader = new FileReader();
            reader.onload = () => {
                try {
                    const errorJson = JSON.parse(reader.result);
                    uiStore.addNotification(errorJson.detail || 'Failed to export code from message.', 'error');
                } catch {
                    uiStore.addNotification('An unknown error occurred during code export.', 'error');
                }
            };
            reader.readAsText(error.response.data);
            console.error("Code export from message failed:", error);
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
        } catch (error) { console.error("Import failed:", error); }
    }
    
    // NEW ACTIONS for discussion-level images
    async function uploadDiscussionImage(file) {
        if (!currentDiscussionId.value) return;
        try {
            const formData = new FormData();
            formData.append('file', file);
            const response = await apiClient.post(`/api/discussions/${currentDiscussionId.value}/images`, formData);
            
            const newDiscussions = { ...discussions.value };
            if (newDiscussions[currentDiscussionId.value]) {
                newDiscussions[currentDiscussionId.value] = { 
                    ...newDiscussions[currentDiscussionId.value], 
                    ...response.data 
                };
                discussions.value = newDiscussions;
            }
            await fetchContextStatus(currentDiscussionId.value);
            const message = file.type === 'application/pdf' ? 'PDF processed and pages added as images.' : 'Image added to discussion context.';
            uiStore.addNotification(message, 'success');
        } catch(error) { 
            uiStore.addNotification('Failed to add file to discussion.', 'error');
            console.error("Failed to upload discussion file:", error);
        }
    }

    async function toggleDiscussionImageActivation(imageIndex) {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.put(`/api/discussions/${currentDiscussionId.value}/images/${imageIndex}/toggle`);
            const disc = discussions.value[currentDiscussionId.value];
            if (disc) {
                disc.discussion_images = response.data.discussion_images || [];
                disc.active_discussion_images = response.data.active_discussion_images || [];
            }
            await fetchContextStatus(currentDiscussionId.value);
        } catch(error) { /* Handled by interceptor */ }
    }

    async function deleteDiscussionImage(imageIndex) {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.delete(`/api/discussions/${currentDiscussionId.value}/images/${imageIndex}`);
            const disc = discussions.value[currentDiscussionId.value];
            if (disc) {
                disc.discussion_images = response.data.discussion_images || [];
                disc.active_discussion_images = response.data.active_discussion_images || [];
            }
            await fetchContextStatus(currentDiscussionId.value);
        } catch(error) { /* Handled by interceptor */ }
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
        titleGenerationInProgressId, activeDiscussion, activeMessages, activeDiscussionContainsCode,
        activeDiscussionContextStatus, activePersonality, activeAiTasks,
        sortedDiscussions, dataZonesTokenCount, liveDataZoneTokens, 
        dataZonesTokensFromContext, // EXPORT NEW COMPUTED
        loadDiscussions, selectDiscussion, createNewDiscussion,
        deleteDiscussion, pruneDiscussions, generateAutoTitle, toggleStarDiscussion,
        updateDiscussionRagStore, renameDiscussion, updateDiscussionMcps,
        sendMessage, stopGeneration, saveMessageChanges, gradeMessage,
        deleteMessage, initiateBranch, switchBranch, exportDiscussions, importDiscussions,
        exportCodeToZip, exportMessageCodeToZip, sendDiscussion, $reset, fetchContextStatus,
        fetchDataZones, updateDataZone,
        summarizeDiscussionDataZone, memorizeLTM,
        updateLiveTokenCount,
        refreshDataZones,
        setUserDataZoneContent,
        _clearActiveAiTask,
        addManualMessage,
        saveManualMessage,
        toggleImageActivation,
        uploadDiscussionImage, toggleDiscussionImageActivation, deleteDiscussionImage,
    };
});
