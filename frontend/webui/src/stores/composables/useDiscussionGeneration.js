// [UPDATE] frontend/webui/src/stores/composables/useDiscussionGeneration.js
import apiClient from '../../services/api';
import { processSingleMessage } from './discussionProcessor';

export function useDiscussionGeneration(state, stores, getActions) {
    const { discussions, currentDiscussionId, messages, generationInProgress, activePersonality, promptLoadedArtefacts, _clearActiveAiTask, generationState, currentModelVisionSupport } = state;
    const { uiStore, authStore, dataStore } = stores;

    let activeGenerationAbortController = null;

    async function sendMessage(payload) {
        if (generationInProgress.value) {
            uiStore.addNotification('A generation is already in progress.', 'warning');
            return;
        }
        
        // Ensure user info is loaded
        if (!authStore.user) {
            console.error("No authenticated user found in store.");
            uiStore.addNotification('Session error. Please try logging in again.', 'error');
            return;
        }

        if (!currentDiscussionId.value) {
            try {
                // Ensure we wait for the creation to finish and populate the ID
                await getActions().createNewDiscussion();
            } catch (err) {
                console.error("Auto-creation of discussion failed:", err);
                uiStore.addNotification('Failed to create a new discussion.', 'error');
                return;
            }
        }
        
        // Final sanity check for ID and object
        if (!currentDiscussionId.value || !state.activeDiscussion.value) {
            console.error("No active discussion found to send message to.");
            uiStore.addNotification('Failed to identify active conversation.', 'error');
            return;
        }

        // --- NEW: Handle Image Uploads ---
        let uploadedPaths = [];
        if (payload.image_files && payload.image_files.length > 0) {
            try {
                const uploadFormData = new FormData();
                payload.image_files.forEach(file => {
                    uploadFormData.append('files', file);
                });
                
                // Upload to temp staging
                const uploadRes = await apiClient.post('/api/upload/chat_image', uploadFormData, {
                     headers: { 'Content-Type': 'multipart/form-data' }
                });
                
                // Response is list of {filename, server_path}
                uploadedPaths = uploadRes.data.map(f => f.server_path);
                
            } catch (err) {
                console.error("Failed to upload chat images:", err);
                uiStore.addNotification('Failed to upload images. Sending text only.', 'error');
            }
        }
        
        // Combine with any existing server paths (e.g. from a draft or previous context if applicable)
        let imagesToSend = (payload.image_server_paths || []).concat(uploadedPaths);

        // Vision Support Enforcement:
        // Filter out images if the current model doesn't support them.
        if (!currentModelVisionSupport.value && imagesToSend.length > 0) {
            uiStore.addNotification('Active model does not support images. Sending text only.', 'warning');
            imagesToSend = [];
        }

        generationInProgress.value = true;
        // Granular state updates for better UI feedback
        generationState.value = { status: 'starting', details: 'Waiting for first token...' };
        
        promptLoadedArtefacts.value.clear();
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
        // Pass the array of server-side filenames to the chat endpoint
        formData.append('image_server_paths_json', JSON.stringify(imagesToSend));
        
        if (payload.is_resend) formData.append('is_resend', 'true');
        
        // Pass web search flag
        formData.append('web_search_enabled', payload.webSearchEnabled ? 'true' : 'false');

        // For regeneration (resend), we need to ensure the backend branches from the correct message.
        if (lastMessage) {
            formData.append('parent_message_id', lastMessage.id);
        }

        const messageToUpdate = messages.value.find(m => m.id === tempAiMessage.id);

        const processStreamData = (data) => {
            if (!messageToUpdate) return;
            
            switch (data.type) {
                case 'ttft':
                    generationState.value = { 
                        status: 'streaming', 
                        details: `ttft: ${data.content}ms - generating...` 
                    };
                    break;
                case 'chunk':
                    if (generationState.value.status !== 'streaming' && !generationState.value.details.includes('ttft')) {
                         generationState.value = { status: 'streaming', details: 'generating...' };
                    }
                    messageToUpdate.content += data.content;
                    break;
                case 'step_start':
                    generationState.value = { status: 'thinking', details: data.content || 'Thinking...' };
                    break;
                case 'tool_call':
                    let details = 'Using tool...';
                    try {
                        const toolData = JSON.parse(data.content);
                        details = `Using tool: ${toolData.function || toolData.tool_name || '...'}`;
                    } catch(e) {}
                    generationState.value = { status: 'thinking', details };
                    break;
                case 'new_title_start':
                    state.titleGenerationInProgressId.value = currentDiscussionId.value;
                    generationState.value = { status: 'generating_title', details: 'generating title...' };
                    break;
                case 'new_title_end':
                    state.titleGenerationInProgressId.value = null;
                    if (state.discussions.value[currentDiscussionId.value]) {
                        state.discussions.value[currentDiscussionId.value].title = data.new_title;
                    }
                    // Revert to streaming status if we are still going
                    if (generationInProgress.value) {
                         // Preserve TTFT context if we had it
                         const oldDetails = generationState.value.details;
                         const newDetails = oldDetails.includes('ttft') ? oldDetails : 'generating...';
                         generationState.value = { status: 'streaming', details: newDetails };
                    }
                    break;
                case 'step_end':
                    // Similar logic to preserve TTFT info if desired
                    if (generationInProgress.value) {
                         const oldDetails = generationState.value.details;
                         const newDetails = oldDetails.includes('ttft') ? oldDetails : 'generating...';
                         generationState.value = { status: 'streaming', details: newDetails };
                    }
                    break;
                case 'sources':
                    if (!messageToUpdate.sources) messageToUpdate.sources = [];
                    // Ensure backend sends array, or push if single
                    if (Array.isArray(data.content)) {
                        messageToUpdate.sources = data.content;
                    } else {
                        messageToUpdate.sources.push(data.content);
                    }
                    break;
                case 'finalize': {
                    const finalData = data.data;
                    const userMsgIndex = messages.value.findIndex(m => m.id === tempUserMessage.id);
                    if (userMsgIndex !== -1 && finalData.user_message) {
                        messages.value.splice(userMsgIndex, 1, processSingleMessage(finalData.user_message));
                    }

                    const aiMsgIndex = messages.value.findIndex(m => m.id === tempAiMessage.id);
                    if (aiMsgIndex !== -1 && finalData.ai_message) {
                        messages.value.splice(aiMsgIndex, 1, processSingleMessage(finalData.ai_message));
                    }
                    break;
                }
                default:
                    if (['thought', 'reasoning', 'scratchpad', 'info', 'observation', 'exception', 'error'].includes(data.type)) {
                        if (!messageToUpdate.events) messageToUpdate.events = [];
                        messageToUpdate.events.push(data);
                    }
            }
        };
        
        try {
            // Determine full URL to ensure compatibility with dev proxy and specific baseURL settings
            const baseUrl = apiClient.defaults.baseURL || '';
            const fetchUrl = `${baseUrl.replace(/\/$/, '')}/api/discussions/${currentDiscussionId.value}/chat`;

            const response = await fetch(fetchUrl, {
                method: 'POST', body: formData,
                headers: { 'Authorization': `Bearer ${authStore.token}` },
                signal: activeGenerationAbortController.signal,
            });

            if (!response.ok || !response.body) {
                const errorText = await response.text().catch(() => "No error details available.");
                throw new Error(`HTTP error ${response.status}: ${errorText}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                let newlineIndex;
                while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
                    const line = buffer.slice(0, newlineIndex).trim();
                    buffer = buffer.slice(newlineIndex + 1);
                    if (line) {
                        try {
                            const data = JSON.parse(line);
                            processStreamData(data);
                        } catch (e) { console.error("Error parsing stream line:", line, e); }
                    }
                }
            }

        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error("Chat fetch failed:", error);
                uiStore.addNotification('An error occurred during generation.', 'error');
                
                // Cleanup temp messages on failure
                const aiMessageIndex = messages.value.findIndex(m => m.id === tempAiMessage.id);
                if (aiMessageIndex > -1) messages.value.splice(aiMessageIndex, 1);
                
                if (!payload.is_resend) {
                    const userMessageIndex = messages.value.findIndex(m => m.id === tempUserMessage.id);
                    if (userMessageIndex > -1) messages.value.splice(userMessageIndex, 1);
                }
            }
        } finally {
            if (messageToUpdate) messageToUpdate.isStreaming = false;
            generationInProgress.value = false;
            generationState.value = { status: 'idle', details: '' };
            activeGenerationAbortController = null;
            
            // CRITICAL FIX: Ensure persistence and UI sync by refreshing data zones after generation
            if (currentDiscussionId.value) {
                await getActions().refreshDataZones(currentDiscussionId.value);
            }
            await getActions().loadDiscussions();
        }
    }

    async function stopGeneration() {
        if (activeGenerationAbortController) {
            activeGenerationAbortController.abort();
            activeGenerationAbortController = null;
        }
        generationInProgress.value = false;
        generationState.value = { status: 'idle', details: '' };
        
        if (currentDiscussionId.value) {
            try { 
                await apiClient.post(`/api/discussions/${currentDiscussionId.value}/stop_generation`); 
            } catch(e) { console.warn("Backend stop signal failed.", e); }
            await getActions().refreshActiveDiscussionMessages();
            await getActions().refreshDataZones(currentDiscussionId.value);
        }
        uiStore.addNotification('Generation stopped.', 'info');
    }

    async function initiateBranch(userMessageToResend) {
        if (!state.activeDiscussion.value || generationInProgress.value || !userMessageToResend || userMessageToResend.sender_type !== 'user') return;
        try {
            await apiClient.put(`/api/discussions/${currentDiscussionId.value}/active_branch`, { active_branch_id: userMessageToResend.id });
            const promptIndex = messages.value.findIndex(m => m.id === userMessageToResend.id);
            if (promptIndex > -1) messages.value = messages.value.slice(0, promptIndex + 1);
            else { await getActions().selectDiscussion(currentDiscussionId.value); return; }
            await sendMessage({
                prompt: userMessageToResend.content,
                image_server_paths: userMessageToResend.server_image_paths || [],
                localImageUrls: userMessageToResend.image_references || [],
                is_resend: true,
            });
        } catch(error) {
            console.error("Failed to start new branch:", error);
            uiStore.addNotification('Failed to start new branch.', 'error');
            if (currentDiscussionId.value) await getActions().selectDiscussion(currentDiscussionId.value);
        }
    }

    async function switchBranch(newBranchMessageId) {
        if (!state.activeDiscussion.value || generationInProgress.value) return;
        try {
            await apiClient.put(`/api/discussions/${currentDiscussionId.value}/active_branch`, { active_branch_id: newBranchMessageId });
            await getActions().selectDiscussion(currentDiscussionId.value, newBranchMessageId); 
            uiStore.addNotification(`Switched branch.`, 'info');
        } catch (error) {
            uiStore.addNotification('Failed to switch branch.', 'error');
            await getActions().selectDiscussion(currentDiscussionId.value);
        }
    }

    return {
        sendMessage,
        stopGeneration,
        initiateBranch,
        switchBranch
    };
}
