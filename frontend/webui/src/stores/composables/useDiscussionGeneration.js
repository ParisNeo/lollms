// [UPDATE] frontend/webui/src/stores/composables/useDiscussionGeneration.js
import apiClient from '../../services/api';
import { processSingleMessage } from './discussionProcessor';
export function useDiscussionGeneration(state, stores, getActions) {
    const { 
        discussions, 
        currentDiscussionId, 
        messages, 
        generationInProgress, 
        activePersonality, 
        promptLoadedArtefacts, 
        generationState, 
        currentModelVisionSupport 
    } = state;
    const { uiStore, authStore, tasksStore } = stores;

    let activeGenerationAbortController = null;

    async function sendMessage(payload) {
        if (generationInProgress.value) {
            uiStore.addNotification('A generation is already in progress.', 'warning');
            return;
        }

        if (!authStore.user) {
            uiStore.addNotification('Session error. Please log in.', 'error');
            return;
        }

        if (!currentDiscussionId.value) {
            try {
                await getActions().createNewDiscussion();
            } catch (err) {
                uiStore.addNotification('Failed to create a new discussion.', 'error');
                return;
            }
        }
        
        if (!currentDiscussionId.value || !state.activeDiscussion.value) {
            uiStore.addNotification('No active conversation.', 'error');
            return;
        }

        // --- Handle Image Uploads ---
        let uploadedPaths = [];
        if (payload.image_files && payload.image_files.length > 0) {
            try {
                const uploadFormData = new FormData();
                payload.image_files.forEach(file => uploadFormData.append('files', file));
                const uploadRes = await apiClient.post('/api/upload/chat_image', uploadFormData, {
                     headers: { 'Content-Type': 'multipart/form-data' }
                });
                uploadedPaths = uploadRes.data.map(f => f.server_path);
            } catch (err) {
                uiStore.addNotification('Image upload failed.', 'error');
            }
        }
        
        let imagesToSend = (payload.image_server_paths || []).concat(uploadedPaths);
        if (!currentModelVisionSupport.value && imagesToSend.length > 0) {
            uiStore.addNotification('Model lacks vision support. Images ignored.', 'warning');
            imagesToSend = [];
        }

        // --- Prepare UI State ---
        generationInProgress.value = true;
        generationState.value = { status: 'starting', details: 'Waking up the model...' };
        
        if (state.activeUpdatingArtefacts?.value) state.activeUpdatingArtefacts.value.clear();
        if (state.liveArtefactBuffers?.value) state.liveArtefactBuffers.value = {};
        
        promptLoadedArtefacts.value.clear();
        activeGenerationAbortController = new AbortController();
        
        const lastMessage = messages.value.length > 0 ? messages.value[messages.value.length - 1] : null;
        const parentId = payload.parent_message_id || (lastMessage ? lastMessage.id : null);
        
        const tempUserMessage = {
            id: `temp-user-${Date.now()}`, sender: authStore.user.username,
            sender_type: 'user', content: payload.prompt,
            localImageUrls: payload.localImageUrls || [],
            created_at: new Date().toISOString(),
            parent_message_id: parentId
        };
        const tempAiMessage = {
            id: `temp-ai-${Date.now()}`, sender: activePersonality.value?.name || 'assistant', sender_type: 'assistant',
            content: '', isStreaming: true, created_at: new Date().toISOString(),
            events: [], lastEvent: null,
            parent_message_id: payload.is_resend ? parentId : tempUserMessage.id
        };

        if (!payload.is_resend) messages.value.push(tempUserMessage);
        messages.value.push(tempAiMessage);

        let finalPrompt = payload.prompt || '';
        if (state.attachedSkills?.value?.length > 0) {
            const skillsContext = state.attachedSkills.value.map(s => `--- Skill: ${s.name} ---\n${s.content}`).join('\n\n');
            finalPrompt = `${skillsContext}\n\nUser: ${finalPrompt}`;
            state.attachedSkills.value = [];
        }

        if (!finalPrompt.trim() && imagesToSend.length > 0) finalPrompt = "Analyze this image";

        const formData = new FormData();
        formData.append('prompt', finalPrompt);
        formData.append('image_server_paths_json', JSON.stringify(imagesToSend));
        if (payload.is_resend) formData.append('is_resend', 'true');
        formData.append('web_search_enabled', payload.webSearchEnabled ? 'true' : 'false');
        if (parentId) formData.append('parent_message_id', parentId);

        const messageToUpdate = messages.value.find(m => m.id === tempAiMessage.id);

        // --- Stream Processing Logic ---
        const processStreamData = (data) => {
            if (data.type === 'new_message_id') {
                const aiIdx = messages.value.findIndex(m => m.id === tempAiMessage.id);
                if (aiIdx !== -1) messages.value[aiIdx].id = data.content;
                return;
            }

            if (!messageToUpdate) return;

            switch (data.type) {
                case 'chunk':
                    // RAW FLOW: Immediate visibility for all text and tags
                    messageToUpdate.content += data.content;
                    break;

                case 'ttft':
                    generationState.value = { status: 'streaming', details: `ttft: ${data.content}ms` };
                    break;

                case 'processing_open':
                    // [FIX] Ensure the opening tag starts on a new line and is added to content so the renderer catches it
                    if (messageToUpdate.content && !messageToUpdate.content.endsWith('\n')) {
                        messageToUpdate.content += '\n';
                    }
                    const openAttrs = data.attrs || {};
                    let openTag = `<processing type="${data.processing_type}" title="${data.title || 'Processing'}"`;
                    for (const [k, v] of Object.entries(openAttrs)) { openTag += ` ${k}="${v}"`; }
                    openTag += '>';
                    messageToUpdate.content += openTag;
                    break;

                case 'processing_status':
                    // [FIX] Append status lines immediately to the visible content
                    messageToUpdate.content += `\n* ${data.status}`;
                    break;

                case 'processing_close':
                    // [FIX] Close the tag to finalize the UI block appearance with a trailing newline
                    messageToUpdate.content += '</processing>\n';
                    break;

                case 'thought':
                    if (!messageToUpdate.thoughts) messageToUpdate.thoughts = "";
                    messageToUpdate.thoughts += data.content;
                    break;

                case 'memory_update':
                    if (data.meta && data.meta.report) {
                        const created = data.meta.report.created || [];
                        const tagged = data.meta.report.tagged || [];
                        if (created.length > 0) {
                            uiStore.addNotification(`🧠 Learned: "${created[0].content.substring(0, 45)}..."`, 'success', 5000);
                        }
                        if (tagged.length > 0) {
                            uiStore.addNotification(`🔗 Recalled Fact: "${tagged[0].content.substring(0, 45)}..."`, 'info', 4000);
                        }
                    }
                    break;

                case 'memory_dream':
                    if (data.meta && data.meta.report) {
                        const rep = data.meta.report;
                        uiStore.addNotification(`💤 Dream: Reinforced ${rep.reinforced || 0} memories, Demoted ${rep.decayed || 0}`, 'info', 5000);
                    }
                    break;

                case 'finalize':
                    const finalData = data.data;
                    const aiIdx = messages.value.findIndex(m => m.id === tempAiMessage.id || m.id === finalData.ai_message?.id);
                    if (aiIdx !== -1 && finalData.ai_message) {
                        messages.value[aiIdx] = processSingleMessage(finalData.ai_message);
                        if (state.activeDiscussion.value) state.activeDiscussion.value.active_branch_id = messages.value[aiIdx].id;
                    }
                    // Clean up buffers explicitly on finalize to prevent stale state
                    if (state.liveArtefactBuffers?.value) state.liveArtefactBuffers.value = {};

                    if (data.discussion && data.discussion.artefacts) {
                        state.activeDiscussionArtefacts.value = data.discussion.artefacts;
                    }
                    break;

                default:
                    // Log tools/steps in background events
                    if (['tool_call', 'tool_output', 'step_start', 'step_end', 'info', 'warning', 'error'].includes(data.type)) {
                        if (!messageToUpdate.events) messageToUpdate.events = [];
                        messageToUpdate.events.push(data);
                        messageToUpdate.lastEvent = data;
                    }
            }
        };

        // --- Fetch Loop ---
        try {
            const baseUrl = apiClient.defaults.baseURL || '';
            const fetchUrl = `${baseUrl.replace(/\/$/, '')}/api/discussions/${currentDiscussionId.value}/chat`;

            const response = await fetch(fetchUrl, {
                method: 'POST', body: formData,
                headers: { 'Authorization': `Bearer ${authStore.token}` },
                signal: activeGenerationAbortController.signal,
            });

            if (!response.ok) throw new Error(`HTTP error ${response.status}`);

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
                            processStreamData(JSON.parse(line));
                        } catch (e) { console.error("Stream line parse error", e); }
                    }
                }
            }
        } catch (error) {
            if (error.name !== 'AbortError') uiStore.addNotification('Connection error during generation.', 'error');
        } finally {
            if (messageToUpdate) messageToUpdate.isStreaming = false;
            generationInProgress.value = false;
            generationState.value = { status: 'idle', details: '' };
            activeGenerationAbortController = null;

            // Auto-refresh the cognitive memories list at the end of the turn
            // in case the AI generated or updated any facts
            try {
                const { useMemoriesStore } = await import('../memories');
                await useMemoriesStore().fetchMemories();
            } catch (memErr) {
                console.warn("Failed to auto-refresh memories list:", memErr);
            }

            getActions().refreshDataZones(currentDiscussionId.value);
        }
    }

    async function stopGeneration() {
        if (activeGenerationAbortController) activeGenerationAbortController.abort();
        if (currentDiscussionId.value) {
            try { await apiClient.post(`/api/discussions/${currentDiscussionId.value}/stop_generation`); } catch(e) {}
        }
        generationInProgress.value = false;
        uiStore.addNotification('Generation stopped.', 'info');
    }

    async function initiateBranch(message) {
        if (!state.activeDiscussion.value || generationInProgress.value || !message) return;

        // Logic: To regenerate/branch, we need the last USER message as the parent.
        // If clicking on an AI message, the target is its parent (the User prompt).
        // If clicking on a User message, the target is that message itself.
        let anchorMessage = message;
        if (anchorMessage.sender_type !== 'user') {
            anchorMessage = messages.value.find(m => m.id === anchorMessage.parent_message_id);
        }

        if (!anchorMessage) {
            uiStore.addNotification('Cannot find parent message for branching.', 'error');
            return;
        }

        try {
            // 1. Tell backend which message we are branching FROM
            await apiClient.put(`/api/discussions/${currentDiscussionId.value}/active_branch`, { active_branch_id: anchorMessage.id });

            // 2. Visually trim the local message list to the branch point
            const idx = messages.value.findIndex(m => m.id === anchorMessage.id);
            if (idx > -1) {
                messages.value = messages.value.slice(0, idx + 1);
            }

            // 3. Trigger new generation starting from this anchor
            await sendMessage({ 
                prompt: anchorMessage.content, 
                is_resend: true, 
                parent_message_id: anchorMessage.id 
            });
        } catch(e) { 
            console.error("Branching failed:", e);
            uiStore.addNotification('Branching failed.', 'error'); 
        }
    }

    async function switchBranch(id) {
        try {
            await apiClient.put(`/api/discussions/${currentDiscussionId.value}/active_branch`, { active_branch_id: id });
            await getActions().selectDiscussion(currentDiscussionId.value, id); 
        } catch (e) { uiStore.addNotification('Switch failed.', 'error'); }
    }

    return { sendMessage, stopGeneration, initiateBranch, switchBranch };
}

