// [UPDATE] frontend/webui/src/stores/composables/useDiscussionGeneration.js
import apiClient from '../../services/api';
import { processSingleMessage } from './discussionProcessor'; // IMPORT the shared function

export function useDiscussionGeneration(state, stores, getActions) {
    const { discussions, currentDiscussionId, messages, generationInProgress, activePersonality, promptLoadedArtefacts, _clearActiveAiTask, generationState } = state;
    const { uiStore, authStore, dataStore } = stores;

    let activeGenerationAbortController = null;

    async function sendMessage(payload) {
        if (generationInProgress.value) {
            uiStore.addNotification('A generation is already in progress.', 'warning');
            return;
        }
        if (!currentDiscussionId.value) {
            await getActions().createNewDiscussion();
        }
        if (!state.activeDiscussion.value) return;

        const selectedModelId = authStore.user?.lollms_model_name;
        const selectedModel = dataStore.availableLollmsModels.find(m => m.id === selectedModelId);
        const hasVision = selectedModel?.alias?.has_vision ?? true;
        let imagesToSend = payload.image_server_paths || [];
        
        if (!hasVision && imagesToSend.length > 0) {
            uiStore.addNotification(`The selected model '${selectedModel.name}' does not support vision. Images will be ignored.`, 'warning', 6000);
            imagesToSend = [];
        }

        generationInProgress.value = true;
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
        formData.append('image_server_paths_json', JSON.stringify(imagesToSend));
        if (payload.is_resend) formData.append('is_resend', 'true');

        const messageToUpdate = messages.value.find(m => m.id === tempAiMessage.id);

        const processStreamData = (data) => {
            if (!messageToUpdate) return;
            
            // First, handle state updates based on type
            switch (data.type) {
                case 'chunk':
                    if (generationState.value.status !== 'streaming') {
                        generationState.value = { status: 'streaming', details: 'Receiving response...' };
                    }
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
                    generationState.value = { status: 'generating_title', details: 'Generating title...' };
                    break;
                case 'new_title_end':
                    state.titleGenerationInProgressId.value = null;
                    if (state.discussions.value[currentDiscussionId.value]) {
                        state.discussions.value[currentDiscussionId.value].title = data.new_title;
                    }
                    if (generationInProgress.value) {
                        generationState.value = { status: 'thinking', details: 'Continuing generation...' };
                    }
                    break;
                case 'step_end':
                    if (generationInProgress.value) { 
                        generationState.value = { status: 'thinking', details: 'Continuing generation...' };
                    }
                    break;
            }

            // Then, handle data processing for the message object
            switch (data.type) {
                case 'chunk':
                    messageToUpdate.content += data.content;
                    break;
                case 'sources':
                    if (!messageToUpdate.sources) messageToUpdate.sources = [];
                    messageToUpdate.sources = data.content;
                    // Fallthrough to events
                case 'step_start':
                case 'step_end':
                case 'info':
                case 'observation':
                case 'thought':
                case 'reasoning':
                case 'tool_call':
                case 'scratchpad':
                case 'exception':
                case 'error':
                    if (!messageToUpdate.events) messageToUpdate.events = [];
                    messageToUpdate.events.push(data);
                    break;
                case 'new_title_start':
                case 'new_title_end':
                    // Already handled state, nothing to do for message object here
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
            }
        };
        
        try {
            const response = await fetch(`/api/discussions/${currentDiscussionId.value}/chat`, {
                method: 'POST', body: formData,
                headers: { 'Authorization': `Bearer ${authStore.token}` },
                signal: activeGenerationAbortController.signal,
            });

            if (!response.ok || !response.body) throw new Error(`HTTP error ${response.status}`);
            
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
            if (buffer.trim()) {
                try {
                    const data = JSON.parse(buffer.trim());
                    processStreamData(data);
                } catch(e) {
                    console.error("Error parsing final buffered line:", buffer.trim(), e);
                }
            }

        } catch (error) {
            if (error.name !== 'AbortError') {
                uiStore.addNotification('An error occurred during generation.', 'error');
                const aiMessageIndex = messages.value.findIndex(m => m.id === tempAiMessage.id);
                if (aiMessageIndex > -1) messages.value.splice(aiMessageIndex, 1);
            }
        } finally {
            if (messageToUpdate) messageToUpdate.isStreaming = false;
            generationInProgress.value = false;
            generationState.value = { status: 'idle', details: '' };
            activeGenerationAbortController = null;
            await getActions().fetchContextStatus(currentDiscussionId.value);
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
