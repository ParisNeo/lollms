// frontend/webui/src/stores/composables/useDiscussionGeneration.js
import apiClient from '../../services/api';
import { processSingleMessage } from './discussionProcessor';

// ── Durable client-side generation errors ──────────────────────────────────
// A generation can fail mid-stream (context overflow, engine crash, lost
// connection). The server's persisted message does NOT know about these
// client-observed failures, and `refreshActiveDiscussionMessages()` rebuilds
// `messages.value` from server truth — which would silently wipe a top-level
// field or a metadata blob we set on the temp message objects.
//
// This module-level registry keys the error by the FINAL message id and is
// re-applied to `metadata.generation_error` every time the message array is
// rebuilt. It stays alive for the page session, so the red error card renders
// immediately AND keeps rendering after any refresh/reload of the discussion.
const GENERATION_ERRORS = new Map();

export function getGenerationErrorForMessage(messageId) {
    if (!messageId) return null;
    return GENERATION_ERRORS.get(String(messageId)) || null;
}

export function remapGenerationError(messageId) {
    if (!messageId) return null;
    return GENERATION_ERRORS.get(String(messageId)) || null;
}

// Attach an error to a message id and mirror it onto `metadata` so any consumer
// reading `message.metadata.generation_error` sees the same value.
export function setGenerationError(messageId, error) {
    if (!messageId || !error) return;
    const key = String(messageId);
    if (GENERATION_ERRORS.has(key)) return; // first error wins (root cause)
    GENERATION_ERRORS.set(key, error);
}

// Re-attach the registry entry to whichever message object currently represents
// `messageId` after the messages array was rebuilt from server truth.
export function rehydrateGenerationError(messageObj) {
    if (!messageObj || !messageObj.id) return messageObj;
    const err = GENERATION_ERRORS.get(String(messageObj.id));
    if (!err) return messageObj;
    if (!messageObj.metadata || typeof messageObj.metadata !== 'object') {
        messageObj.metadata = {};
    }
    if (!messageObj.metadata.generation_error) {
        messageObj.metadata.generation_error = err;
    }
    return messageObj;
}

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

        if (currentDiscussionId.value && !discussions.value[currentDiscussionId.value]) {
            discussions.value[currentDiscussionId.value] = {
                id: currentDiscussionId.value,
                title: 'Discussion',
                created_at: new Date().toISOString(),
                last_activity_at: new Date().toISOString()
            };
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
            parent_message_id: parentId,
            message_metadata: {
                rag_sources: payload.rag_sources || [],
                selected_tools: payload.selected_tools || []
            }
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

        // Resolve thinking parameters from payload or read active UI toggle for resends/regenerations
        let effectiveThinking = payload.thinking;
        let effectiveReasoningEffort = payload.reasoning_effort;

        if (effectiveThinking === undefined || effectiveThinking === null) {
            const storedReasoningActive = localStorage.getItem('lollms_input_reasoning_active');
            if (storedReasoningActive === 'false') {
                effectiveThinking = 'false';
                effectiveReasoningEffort = 'none';
            } else if (storedReasoningActive === 'true') {
                effectiveThinking = 'true';
                effectiveReasoningEffort = localStorage.getItem('lollms_input_reasoning_effort') || 'low';
            } else {
                effectiveThinking = authStore.user?.reasoning_activation ? 'true' : 'false';
                effectiveReasoningEffort = authStore.user?.reasoning_activation ? (authStore.user?.reasoning_effort || 'low') : 'none';
            }
        }

        const formData = new FormData();
        formData.append('prompt', finalPrompt);
        formData.append('image_server_paths_json', JSON.stringify(imagesToSend));
        if (payload.is_resend) formData.append('is_resend', 'true');
        formData.append('web_search_enabled', payload.webSearchEnabled ? 'true' : 'false');
        
        if (payload.rag_sources && payload.rag_sources.length > 0) {
            formData.append('rag_sources_json', JSON.stringify(payload.rag_sources));
        }
        if (payload.selected_tools && payload.selected_tools.length > 0) {
            formData.append('active_tools_json', JSON.stringify(payload.selected_tools));
        }
        if (parentId) formData.append('parent_message_id', parentId);
        if (payload.temperature !== undefined && payload.temperature !== null) {
            formData.append('temperature', payload.temperature);
        }
        if (payload.max_nb_rounds !== undefined && payload.max_nb_rounds !== null) {
            formData.append('max_nb_rounds', payload.max_nb_rounds);
        }

        formData.append('reasoning_effort', effectiveReasoningEffort || 'none');
        formData.append('thinking', effectiveThinking || 'false');

        const messageToUpdate = messages.value.find(m => m.id === tempAiMessage.id);

        // --- Stream Processing Logic ---
        const processStreamData = (data) => {
            if (data.type === 'new_message_id') {
                const aiIdx = messages.value.findIndex(m => m.id === tempAiMessage.id);
                if (aiIdx !== -1) {
                    const oldTempId = tempAiMessage.id;
                    messages.value[aiIdx].id = data.content;
                    tempAiMessage.id = data.content;
                    // Move any error we already captured under the temp id so it
                    // follows the message to its final server id.
                    if (GENERATION_ERRORS.has(oldTempId)) {
                        GENERATION_ERRORS.set(String(data.content), GENERATION_ERRORS.get(oldTempId));
                        GENERATION_ERRORS.delete(oldTempId);
                    }
                }
                return;
            }

            if (!messageToUpdate) return;

            switch (data.type) {
                case 'chunk': {
                    let chunkStr = data.content || '';
                    if (chunkStr.includes('<think>') || chunkStr.includes('<thought>')) {
                        const tag = chunkStr.includes('<think>') ? '<think>' : '<thought>';
                        const [before, after] = chunkStr.split(tag, 2);
                        if (before) messageToUpdate.content += before;
                        state._inStreamThink = true;
                        chunkStr = after || '';
                    }

                    if (state._inStreamThink) {
                        const closeTag = chunkStr.includes('</think>') ? '</think>' : (chunkStr.includes('</thought>') ? '</thought>' : null);
                        if (closeTag) {
                            const [thoughtPart, rest] = chunkStr.split(closeTag, 2);
                            if (!messageToUpdate.thoughts) messageToUpdate.thoughts = '';
                            messageToUpdate.thoughts += thoughtPart;
                            state._inStreamThink = false;
                            if (rest) messageToUpdate.content += rest;
                        } else {
                            if (!messageToUpdate.thoughts) messageToUpdate.thoughts = '';
                            messageToUpdate.thoughts += chunkStr;
                        }
                    } else {
                        messageToUpdate.content += chunkStr;
                    }
                    break;
                }

                case 'ttft':
                    // The model finished its prefill pass and is now emitting
                    // tokens. Expose a human status — never the raw technical
                    // "ttft: NNNNms" which means nothing to the user and looked
                    // like an error code. Actual timing lives in message.metadata
                    // for anyone who wants the technical detail.
                    generationState.value = { status: 'streaming', details: 'Streaming the response…' };
                    break;

                case 'processing_open':
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
                    messageToUpdate.content += `\n* ${data.status}`;
                    break;

                case 'processing_close':
                    messageToUpdate.content += '</processing>\n';
                    break;

                case 'thought':
                    if (!messageToUpdate.thoughts) messageToUpdate.thoughts = "";
                    messageToUpdate.thoughts += data.content;
                    messageToUpdate.thoughts = messageToUpdate.thoughts
                        .replace(/^[\s\r\n]*<(?:think|thought)\b[^>]*>[\s\r\n]*/i, '')
                        .replace(/[\s\r\n]*<\/(?:think|thought)>[\s\r\n]*$/i, '');
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

                case 'skill_done':
                    import('../skills').then(s => s.useSkillsStore().fetchSkills());
                    break;

                case 'note_done':
                    import('../notes').then(n => n.useNotesStore().fetchNotes());
                    break;

                case 'form_ready':
                    if (data.content) {
                        if (!messageToUpdate.forms) messageToUpdate.forms = [];
                        const formItem = data.content.form || data.content;
                        const formId = formItem.id || formItem.form_id;
                        if (!messageToUpdate.forms.some(f => (f.id && f.id === formId) || (f.title && f.title === formItem.title))) {
                            messageToUpdate.forms.push(formItem);
                        }
                    }
                    break;

                case 'sources':
                    messageToUpdate.sources = Array.isArray(data.content) ? data.content : [data.content];
                    if (!messageToUpdate.metadata) messageToUpdate.metadata = {};
                    messageToUpdate.metadata.sources = messageToUpdate.sources;
                    break;

                case 'finalize':
                    if (data.new_title && currentDiscussionId.value) {
                        if (discussions.value[currentDiscussionId.value]) {
                            discussions.value[currentDiscussionId.value].title = data.new_title;
                        }
                    }
                    if (data.discussion?.active_tools && Array.isArray(data.discussion.active_tools) && data.discussion.active_tools.length > 0) {
                        if (discussions.value[currentDiscussionId.value]) {
                            discussions.value[currentDiscussionId.value].active_tools = data.discussion.active_tools;
                        }
                    }
                    if (data.data && data.data.ai_message) {
                        const finalAi = data.data.ai_message;
                        messageToUpdate.id = finalAi.id;
                        if (finalAi.content) {
                            messageToUpdate.content = finalAi.content;
                        }
                        if (finalAi.thoughts) {
                            messageToUpdate.thoughts = String(finalAi.thoughts)
                                .replace(/^[\s\r\n]*<(?:think|thought)\b[^>]*>[\s\r\n]*/i, '')
                                .replace(/[\s\r\n]*<\/(?:think|thought)>[\s\r\n]*$/i, '')
                                .trim();
                        }
                        messageToUpdate.tokens = finalAi.tokens || finalAi.token_count || 0;
                        // `finalize` overwrites `metadata` with server truth.
                        // Client-observed generation errors live in the durable
                        // module registry (not in metadata), so re-apply them
                        // onto the freshly-assigned metadata object here.
                        messageToUpdate.metadata = finalAi.metadata || {};
                        rehydrateGenerationError(messageToUpdate);
                        if (finalAi.sources && finalAi.sources.length > 0) {
                            messageToUpdate.sources = finalAi.sources;
                            if (!messageToUpdate.metadata) messageToUpdate.metadata = {};
                            messageToUpdate.metadata.sources = finalAi.sources;
                        } else if (finalAi.metadata?.sources && finalAi.metadata.sources.length > 0) {
                            messageToUpdate.sources = finalAi.metadata.sources;
                            if (!messageToUpdate.metadata) messageToUpdate.metadata = {};
                            messageToUpdate.metadata.sources = finalAi.metadata.sources;
                        }
                        if (finalAi.events && finalAi.events.length > 0) {
                            messageToUpdate.events = finalAi.events;
                        }
                        if (finalAi.forms && finalAi.forms.length > 0) {
                            messageToUpdate.forms = finalAi.forms;
                        } else if (finalAi.metadata?.forms && finalAi.metadata.forms.length > 0) {
                            messageToUpdate.forms = finalAi.metadata.forms;
                        }
                    }
                    break;
                    
                case 'error':
                case 'exception':
                    if (!messageToUpdate.events) messageToUpdate.events = [];
                    messageToUpdate.events.push(data);
                    messageToUpdate.lastEvent = data;
                    // Register the failure in the DURABLE module-level registry,
                    // keyed by the current message id. The `finalize` event
                    // replaces `metadata` wholesale and the post-generation
                    // server refresh rebuilds `messages.value` from server
                    // truth — neither knows about this client-observed error.
                    // The registry is re-applied onto `metadata.generation_error`
                    // by `rehydrateGenerationError()` after every rebuild, so the
                    // red error card survives finalize AND reload.
                    setGenerationError(tempAiMessage.id || messageToUpdate.id, {
                        message: extractStreamErrorMessage(data) || 'Generation failed.',
                        details: formatStreamErrorDetails(data),
                        type: data.type,
                        timestamp: new Date().toISOString(),
                    });
                    // Mirror onto the live object so the card renders IMMEDIATELY
                    // (before any refresh/rehydrate pass).
                    rehydrateGenerationError(messageToUpdate);


                default:
                    if (['tool_call', 'tool_output', 'step_start', 'step_end', 'info', 'warning', 'form_ready', 'form_submitted'].includes(data.type)) {
                        if (!messageToUpdate.events) messageToUpdate.events = [];
                        messageToUpdate.events.push(data);
                        messageToUpdate.lastEvent = data;
                    }
            }
        };

        // Extract a human-readable one-line message from a stream error event.
        const extractStreamErrorMessage = (data) => {
            const content = data?.content ?? data?.message ?? data?.detail;
            if (typeof content === 'string' && content.trim()) {
                return content.trim().split('\n').find((l) => l.trim()) || content.trim();
            }
            if (content && typeof content === 'object') {
                const nested = content.error || content.message || content.detail;
                if (typeof nested === 'string' && nested.trim()) return nested.trim();
                if (nested && typeof nested === 'object') {
                    const m = nested.message || nested.detail;
                    if (typeof m === 'string' && m.trim()) return m.trim();
                }
                try { return JSON.stringify(content); } catch { return ''; }
            }
            return '';
        };

        // Full multi-line details (traceback / structured payload) for the
        // collapsible body of the error card.
        const formatStreamErrorDetails = (data) => {
            const parts = [];
            const content = data?.content ?? data?.message ?? data?.detail;
            if (content && typeof content === 'object') {
                try {
                    parts.push(JSON.stringify(content, null, 2));
                } catch {
                    parts.push(String(content));
                }
            } else if (typeof content === 'string') {
                parts.push(content);
            }
            if (data?.traceback && typeof data.traceback === 'string') {
                parts.push(data.traceback);
            }
            if (data?.error && typeof data.error === 'string' && !parts.includes(data.error)) {
                parts.push(data.error);
            }
            return parts.join('\n\n').trim();
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
            if (error.name !== 'AbortError') {
                uiStore.addNotification('Connection error during generation.', 'error');
                // Route transport-level failures through the SAME durable
                // registry as server-reported errors so they render identically
                // and survive both `finalize` and the post-generation refresh.
                if (messageToUpdate) {
                    setGenerationError(tempAiMessage.id || messageToUpdate.id, {
                        message: error?.message ? `Connection error: ${error.message}` : 'Connection error during generation.',
                        details: String(error?.stack || error?.message || error || ''),
                        type: 'connection_error',
                        timestamp: new Date().toISOString(),
                    });
                    rehydrateGenerationError(messageToUpdate);
                }
            }
        } finally {
            if (messageToUpdate) messageToUpdate.isStreaming = false;
            generationInProgress.value = false;
            generationState.value = { status: 'idle', details: '' };
            activeGenerationAbortController = null;

            try {
                const { useMemoriesStore } = await import('../memories');
                await useMemoriesStore().fetchMemories();
            } catch (memErr) {
                console.warn("Failed to auto-refresh memories list:", memErr);
            }

            // Rehydrate discussion metadata BEFORE refreshing zones so that
            // fetchDataZones sees the server-truth RAG ids and never clobbers them.
            try {
                const discId = currentDiscussionId.value;
                if (discId) {
                    const fullRes = await apiClient.get(`/api/discussions/${discId}`);
                    const fullData = fullRes.data || {};
                    const meta = fullData.discussion_metadata || {};
                    const ragIds = fullData.rag_datastore_ids ?? meta.rag_datastore_ids;
                    const activeTools = fullData.active_tools ?? meta.active_tools;
                    if (discussions.value?.[discId]) {
                        if (Array.isArray(ragIds)) {
                            discussions.value[discId].rag_datastore_ids = ragIds;
                        }
                        if (Array.isArray(activeTools) && activeTools.length > 0) {
                            discussions.value[discId].active_tools = activeTools;
                        }
                    }
                }
            } catch (hydErr) {
                console.warn("Failed to rehydrate metadata after generation:", hydErr);
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

        let anchorMessage = message;
        if (anchorMessage.sender_type !== 'user') {
            anchorMessage = messages.value.find(m => m.id === anchorMessage.parent_message_id);
        }

        if (!anchorMessage) {
            uiStore.addNotification('Cannot find parent message for branching.', 'error');
            return;
        }

        try {
            await apiClient.put(`/api/discussions/${currentDiscussionId.value}/active_branch`, { active_branch_id: anchorMessage.id });

            const idx = messages.value.findIndex(m => m.id === anchorMessage.id);
            if (idx > -1) {
                messages.value = messages.value.slice(0, idx + 1);
            }

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