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

        // --- Handle Image Uploads ---
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
        
        // [FIX] Reset scratchpad for the new turn
        if (state.activeDiscussion.value) {
            state.activeDiscussion.value.scratchpad = "";
        }
        
        // Granular state updates for better UI feedback
        generationState.value = { status: 'starting', details: 'Waiting for first token...' };
        
        // Reset tracking states for the new turn
        if (state.activeUpdatingArtefacts?.value) state.activeUpdatingArtefacts.value.clear();
        if (state.liveArtefactBuffers?.value) state.liveArtefactBuffers.value = {};
        
        promptLoadedArtefacts.value.clear();
        activeGenerationAbortController = new AbortController();
        
        // Determine parent ID: Use explicit payload ID if present, otherwise last message in list
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
            events: [],
            lastEvent: null, // Track the absolute latest event for live UI
            parent_message_id: payload.is_resend ? parentId : tempUserMessage.id // Ensure temp AI message has correct parent link locally
        };

        if (!payload.is_resend) {
            messages.value.push(tempUserMessage);
        }
        messages.value.push(tempAiMessage);

        // [FIX] Defensive check for attachedSkills to prevent "reading 'value' of undefined"
        let finalPrompt = payload.prompt || '';
        if (state.attachedSkills && state.attachedSkills.value && state.attachedSkills.value.length > 0) {
            const skillsContext = state.attachedSkills.value.map(s => `--- Skill: ${s.name} ---\n${s.content}\n--- End Skill ---`).join('\n\n');
            finalPrompt = `${skillsContext}\n\nUser request: ${finalPrompt}`;
            // Clear skills after they are added to the prompt
            state.attachedSkills.value = [];
        }

        // [FIX] 422 Unprocessable Entity Guard: 
        // Backend Form validation expects a non-null value for 'prompt'.
        const totalImages = (payload.image_files?.length || 0) + (payload.image_server_paths?.length || 0);
        if (!finalPrompt.trim() && totalImages > 0) {
            finalPrompt = "Analyze this image";
        }

        const formData = new FormData();
        formData.append('prompt', finalPrompt);
        // Pass the array of server-side filenames to the chat endpoint
        formData.append('image_server_paths_json', JSON.stringify(imagesToSend));
        
        if (payload.is_resend) formData.append('is_resend', 'true');
        
        // Pass web search flag
        formData.append('web_search_enabled', payload.webSearchEnabled ? 'true' : 'false');

        // Pass explicit parent ID to backend to ensure correct branching
        if (parentId) {
            formData.append('parent_message_id', parentId);
        }

        const messageToUpdate = messages.value.find(m => m.id === tempAiMessage.id);

        // --- BUFFERING & INTERCEPTION LOGIC START ---
        let contentBuffer = '';
        let tagBuffer = ''; 
        let isInterceptingTag = false;
        let interceptedTagName = ''; // Track which tag we are currently hiding
        let lastUpdateTimestamp = 0;
        const UPDATE_INTERVAL = 40; // High frequency for smooth text
        
        const flushBuffer = () => {
            if (contentBuffer && messageToUpdate) {
                messageToUpdate.content += contentBuffer;
                contentBuffer = '';
            }
            lastUpdateTimestamp = Date.now();
        };

        const processStreamData = (data) => {
            // [FIX] ID Swapping Logic: Essential to link background events to the UI bubble
            if (data.type === 'new_message_id') {
                const tempId = tempAiMessage.id;
                const realId = data.content;
                const msgIndex = messages.value.findIndex(m => m.id === tempId);
                if (msgIndex !== -1) {
                    console.log(`[ID Swap] Successfully linked ${tempId} to DB ID ${realId}`);
                    messages.value[msgIndex].id = realId;
                }
                return; 
            }

            if (!messageToUpdate) return;

            // [FIX] Clear "Starting" status on ANY activity (Thoughts, Steps, Tool Calls)
            if (generationState.value.status === 'starting') {
                generationState.value = { 
                    status: data.type === 'chunk' ? 'streaming' : 'thinking', 
                    details: 'Processing...' 
                };
            }
            
            switch (data.type) {
                case 'ttft':
                    generationState.value = { 
                        status: 'streaming', 
                        details: `ttft: ${data.content}ms - generating...` 
                    };
                    break;

                case 'artefact_chunk':
                case 'chunk':
                    const chunk = data.content;
                    
                    // Technical tags that contain HTML/CSS/JS and break the app if streamed partially
                    const messyTags = ['lollms_widget', 'lollms_inline', 'annotate', 'generate_image', 'edit_image', 'generate_slides'];
                    const passiveTags = ['note', 'skill', 'artefact', 'think'];
                    
                    // Detect if a known tag is starting in this chunk
                    if (!isInterceptingTag) {
                        const allTags = [...messyTags, ...passiveTags];
                        let foundTag = null;
                        for (const tag of allTags) {
                            if (chunk.includes(`<${tag}`)) {
                                foundTag = tag;
                                break;
                            }
                        }

                        if (foundTag) {
                            isInterceptingTag = true;
                            interceptedTagName = foundTag;
                            
                            // [FIX] Push the tag start marker into the visible content 
                            // so the renderer can trigger the "Building" UI
                            const tagIndex = chunk.indexOf(`<${foundTag}`);
                            contentBuffer += chunk.substring(0, tagIndex + `<${foundTag}`.length);
                            tagBuffer = chunk.substring(tagIndex + `<${foundTag}`.length);
                            
                            generationState.value = { 
                                status: 'thinking', 
                                details: `Building ${foundTag.replace('_', ' ')}...` 
                            };
                            flushBuffer();
                            return; // Stop processing this chunk to ensure sync
                        }
                    }

                    if (isInterceptingTag) {
                        tagBuffer += chunk;
                        
                        // Detect closure
                        const closeTag = `</${interceptedTagName}>`;
                        const isSelfClosing = (interceptedTagName === 'lollms_widget' || interceptedTagName === 'lollms_inline') && tagBuffer.trim().endsWith('/>');
                        
                        if (tagBuffer.includes(closeTag) || isSelfClosing) {
                            // Tag is complete, release it
                            contentBuffer += tagBuffer;
                            tagBuffer = '';
                            isInterceptingTag = false;
                            interceptedTagName = '';
                            
                            generationState.value = { 
                                status: 'streaming', 
                                details: `Generating...` 
                            };
                            flushBuffer();
                        } else {
                            // While intercepting a "Messy" tag (HTML/CSS), we do NOT flush anything.
                            // However, for "Passive" tags (Notes/Thoughts), we can let the text flow 
                            // as they are just text and don't break the app CSS.
                            if (passiveTags.includes(interceptedTagName)) {
                                // For things like <think>, we want to see the text immediately
                                // but we keep the wrapper tag in the buffer to avoid breaking markdown parsers
                                // This is handled by letting the renderer show a "Building" state separately
                            }
                        }
                    } else {
                        // Regular prose flushes based on interval
                        contentBuffer += chunk;
                        if (Date.now() - lastUpdateTimestamp > UPDATE_INTERVAL) flushBuffer();
                    }
                    break;

                case 'artefact_chunk':
                case 'note_chunk':
                case 'skill_chunk':
                case 'widget_chunk': {
                    const { id, title, chunk } = data.content;
                    const key = id || title;
                    if (key) {
                        state.liveArtefactBuffers.value = {
                            ...state.liveArtefactBuffers.value,
                            [key]: (state.liveArtefactBuffers.value[key] || "") + chunk
                        };
                    }
                    break;
                }

                case 'artefact_done':
                case 'note_done':
                case 'skill_done':
                case 'widget_done': {
                    const { id, title } = data.content;
                    const key = id || title;
                    if (key) {
                        if (state.activeUpdatingArtefacts?.value) {
                            state.activeUpdatingArtefacts.value.delete(key);
                        }
                        const nextBuffers = { ...state.liveArtefactBuffers.value };
                        delete nextBuffers[key];
                        state.liveArtefactBuffers.value = nextBuffers;
                    }
                    getActions().fetchArtefacts(currentDiscussionId.value);
                    break;
                }
                case 'form_ready':
                    if (messageToUpdate) {
                        if (!messageToUpdate.forms) messageToUpdate.forms = [];
                        
                        const formId = data.content.id || data.content.form_id;
                        const formWithOffset = { 
                            ...data.content, 
                            id: formId
                        };
                        messageToUpdate.forms.push(formWithOffset);
                        
                        // Inject a permanent anchor so the form survives the cleanup of <lollms_building />
                        if (!messageToUpdate.content.includes(`id="${formId}"`)) {
                             messageToUpdate.content += `\n<lollms_form_anchor id="${formId}" />\n`;
                        }

                        generationState.value = { status: 'waiting_for_user', details: `Form Ready: ${data.content.title}` };
                    }
                    break;
                case 'form_submitted':
                    if (messageToUpdate && messageToUpdate.forms) {
                        const idx = messageToUpdate.forms.findIndex(f => f.id === data.content.form_id);
                        if (idx !== -1) {
                            messageToUpdate.forms[idx].submitted = true;
                            messageToUpdate.forms[idx].answers = data.content.answers;
                        }
                    }
                    break;
                case 'thought':
                    if (!messageToUpdate.thoughts) messageToUpdate.thoughts = "";
                    messageToUpdate.thoughts += data.content;
                    break;
                case 'artefact_chunk':
                case 'note_start':
                case 'skill_start':
                case 'form_start':
                case 'artefact_update':
                case 'inline_widget_start':
                    if (data.content && messageToUpdate) {
                        const title = data.content.title;
                        const id = data.content.id || title; 
                        
                        // If this is the first chunk of a new artefact, or an explicit start event
                        // and we haven't injected an anchor for it yet.
                        const anchorTag = `id="${id}"`;
                        if (!messageToUpdate.content.includes(anchorTag)) {
                            // 1. Inject an inline building anchor into the message text
                            const typeMap = {
                                'note_start': 'Note',
                                'skill_start': 'Skill',
                                'form_start': 'Form',
                                'artefact_update': 'Artefact',
                                'inline_widget_start': 'Widget',
                                'artefact_chunk': 'Document'
                            };
                            const label = typeMap[data.type] || 'Component';
                            messageToUpdate.content += `\n<lollms_building type="${data.type}" label="${label}" title="${title}" id="${id}" />\n`;

                            // 2. UI Side-effects (Split view / Live Tracking)
                            if (data.type !== 'inline_widget_start' && data.type !== 'form_start' && title) {
                                uiStore.activeSplitArtefactTitle = title;
                            }

                            if (id && state.activeUpdatingArtefacts?.value) {
                                state.activeUpdatingArtefacts.value.add(id);
                            }
                            
                            // Initialize buffer if needed (for start events, chunks are handled separately below)
                            if (id && state.liveArtefactBuffers.value[id] === undefined) {
                                state.liveArtefactBuffers.value = {
                                    ...state.liveArtefactBuffers.value,
                                    [id]: ""
                                };
                            }
                            getActions().fetchArtefacts(currentDiscussionId.value);
                        }
                        
                        // FALLTHROUGH: If it's a chunk, we still need to process the 'chunk' property
                        if (data.type === 'artefact_chunk' && data.content.chunk) {
                            const key = id || title;
                            state.liveArtefactBuffers.value = {
                                ...state.liveArtefactBuffers.value,
                                [key]: (state.liveArtefactBuffers.value[key] || "") + data.content.chunk
                            };
                        }
                    }
                    break;
                case 'artefact_event':
                    // Real-time persistence event from library
                    if (data.data?.artefact) {
                        // Immediately update the local artefacts list
                        getActions().fetchArtefacts(currentDiscussionId.value);
                        // If it's a new note/skill, notify user
                        if (data.data.is_new && data.data.artefact.type !== 'document') {
                            uiStore.addNotification(`${data.data.artefact.type.toUpperCase()} saved to workspace.`, 'success', 2000);
                        }
                    }
                    break;
                case 'artefact_update_done':
                    if (data.content && data.content.title) {
                        const title = data.content.title;
                        // Stop live tracking so the workspace reverts to DB-backed content
                        if (state.activeUpdatingArtefacts?.value) {
                            state.activeUpdatingArtefacts.value.delete(title);
                        }
                        delete state.liveArtefactBuffers.value[title];
                        
                        // Refresh to ensure we have the final persistent version
                        getActions().fetchArtefacts(currentDiscussionId.value);
                    }
                    break;
                case 'step_start':
                    generationState.value = { status: 'thinking', details: data.content || 'Thinking...' };
                    if (!messageToUpdate.events) messageToUpdate.events = [];
                    if (!data.id) data.id = `step_start_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
                    // Use backend offset if provided, otherwise fallback to local cursor
                    if (data.offset === undefined) data.offset = messageToUpdate.content.length;
                    messageToUpdate.events.push(data);
                    messageToUpdate.lastEvent = data;
                    break;
                case 'info':
                    generationState.value = { status: 'info', details: data.content };
                    if (!messageToUpdate.events) messageToUpdate.events = [];
                    if (!data.id) data.id = `info_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
                    if (data.offset === undefined) data.offset = messageToUpdate.content.length;
                    messageToUpdate.events.push(data);
                    break;
                case 'tool_call':
                    let callDetails = 'Using tool...';
                    try {
                        const toolData = typeof data.content === 'string' ? JSON.parse(data.content) : data.content;
                        callDetails = `Using tool: ${toolData?.tool || toolData?.function?.name || toolData?.name || '...'}`;
                    } catch(e) {}
                    generationState.value = { status: 'thinking', details: callDetails };
                    if (!messageToUpdate.events) messageToUpdate.events = [];
                    if (!data.id) data.id = `tool_call_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
                    if (data.offset === undefined) data.offset = messageToUpdate.content.length;
                    messageToUpdate.events.push(data);
                    break;
                case 'tool_output':
                    generationState.value = { status: 'thinking', details: 'Tool execution complete.' };
                    
                    // REMOVED: Auto-opening the Context Explorer sidebar for tool outputs.
                    // Tools results are rendered inline or in the timeline, so the sidebar is redundant here.

                    if (!messageToUpdate.events) messageToUpdate.events = [];
                    
                    // [FIX] Avoid duplication by updating existing event if ID matches
                    if (data.id) {
                        const existingIdx = messageToUpdate.events.findIndex(e => e.id === data.id);
                        if (existingIdx !== -1) {
                            messageToUpdate.events[existingIdx] = { ...messageToUpdate.events[existingIdx], ...data };
                            break;
                        }
                    } else {
                        data.id = `tool_output_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
                    }

                    if (data.offset === undefined) data.offset = messageToUpdate.content.length;
                    messageToUpdate.events.push(data);
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
                    if (generationInProgress.value) {
                         const oldDetails = generationState.value.details;
                         const newDetails = oldDetails.includes('ttft') ? oldDetails : 'generating...';
                         generationState.value = { status: 'streaming', details: newDetails };
                    }
                    if (!messageToUpdate.events) messageToUpdate.events = [];
                    // Ensure stable ID for Vue transition rendering
                    if (!data.id) data.id = `step_end_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
                    messageToUpdate.events.push(data);
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
                    flushBuffer(); // Ensure any remaining text is written before finalizing

                    const finalData = data.data;
                    const userMsgIndex = messages.value.findIndex(m => m.id === tempUserMessage.id);
                    if (userMsgIndex !== -1 && finalData.user_message) {
                        const processedUserMsg = processSingleMessage(finalData.user_message);
                        messages.value.splice(userMsgIndex, 1, processedUserMsg);
                        
                        // Update the active discussion's active_branch_id to the new leaf
                        if (state.activeDiscussion.value) {
                            state.activeDiscussion.value.active_branch_id = processedUserMsg.id;
                        }
                    }

                    const aiMsgIndex = messages.value.findIndex(m => m.id === tempAiMessage.id);
                    if (aiMsgIndex !== -1 && finalData.ai_message) {
                        // Simply use the processor. It handles deep mapping of widgets correctly.
                        const processedAiMsg = processSingleMessage(finalData.ai_message);
                        messages.value.splice(aiMsgIndex, 1, processedAiMsg);
                        
                        // Ensure active branch points to the AI message (the new leaf)
                        if (state.activeDiscussion.value) {
                            state.activeDiscussion.value.active_branch_id = processedAiMsg.id;
                        }

                        // NEW: Check if the AI message has triggered a background task (like slides)
                        // and register it as active for UI blocking logic
                        if (processedAiMsg.metadata && processedAiMsg.metadata.active_task_id) {
                            state.activeAiTasks.value[currentDiscussionId.value] = {
                                type: 'background_generation',
                                taskId: processedAiMsg.metadata.active_task_id
                            };
                            console.log(`[Frontend] Registered active background task ${processedAiMsg.metadata.active_task_id} for discussion ${currentDiscussionId.value}`);
                        }
                    }

                    // NEW: Handle discussion data zone updates if included in the finalize event
                    if (data.discussion) {
                        getActions().handleDataZoneUpdate({
                            discussion_id: data.discussion.id,
                            zone: 'discussion',
                            new_content: data.discussion.discussion_data_zone,
                            discussion_images: data.discussion.discussion_images,
                            active_discussion_images: data.discussion.active_discussion_images
                        });
                    }

                    // Handle new title if present
                    if (data.new_title) {
                        if (state.discussions.value[currentDiscussionId.value]) {
                            state.discussions.value[currentDiscussionId.value].title = data.new_title;
                        }
                    }

                    break;
                }
                default:
                    if (['thought', 'reasoning', 'scratchpad', 'info', 'observation', 'exception', 'error'].includes(data.type)) {
                        if (!messageToUpdate.events) messageToUpdate.events =[];
                        // Ensure stable ID for Vue transition rendering
                        if (!data.id) data.id = `${data.type}_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
                        messageToUpdate.events.push(data);
                    }
            }
        };
        // --- BUFFERING LOGIC END ---
        
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
            // Ensure any final buffer content is flushed at the end of stream
            flushBuffer();

        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error("Chat fetch failed:", error);
                uiStore.addNotification('An error occurred during generation.', 'error');
            }
        } finally {
            if (messageToUpdate) messageToUpdate.isStreaming = false;
            generationInProgress.value = false;
            generationState.value = { status: 'idle', details: '' };
            activeGenerationAbortController = null;
            
            if (currentDiscussionId.value && messageToUpdate) {
                // Final Cleanup: Strip all <lollms_building /> tags. 
                // We keep <lollms_form_anchor /> and <lollms_widget /> as they are necessary for rendering.
                messageToUpdate.content = messageToUpdate.content.replace(/<lollms_building[^>]*\/>/g, '').trim();
                
                await getActions().refreshDataZones(currentDiscussionId.value);
                await getActions().refreshActiveDiscussionMessages();
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

    async function initiateBranch(message) {
        /**
         * Orchestrates a new conversation fork from a specific point in time.
         * Sets the discussion pointer to the selected parent and triggers regeneration.
         */
        if (!state.activeDiscussion.value || generationInProgress.value || !message) return;
        
        let targetMessage = message;
        
        // 1. If user clicks "Regenerate" on an AI message, we actually branch from the 
        // User prompt that triggered it.
        if (targetMessage.sender_type !== 'user') {
            if (targetMessage.parent_message_id) {
                const parent = messages.value.find(m => m.id === targetMessage.parent_message_id);
                if (parent) {
                    targetMessage = parent;
                } else {
                    uiStore.addNotification('Cannot regenerate: Parent message not found locally.', 'error');
                    return;
                }
            } else {
                // Fallback for edge cases (fragmented local history)
                const idx = messages.value.findIndex(m => m.id === targetMessage.id);
                let found = false;
                for (let i = idx - 1; i >= 0; i--) {
                    if (messages.value[i].sender_type === 'user') {
                        targetMessage = messages.value[i];
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    uiStore.addNotification('Cannot regenerate: No preceding user message found.', 'error');
                    return;
                }
            }
        }
        
        // At this point, targetMessage is guaranteed to be a 'user' message.
        
        try {
            // 2. Synchronize the backend pointer to the selected fork point
            await apiClient.put(`/api/discussions/${currentDiscussionId.value}/active_branch`, { active_branch_id: targetMessage.id });
            
            // 3. Update local UI state: truncate everything after the branched prompt
            const promptIndex = messages.value.findIndex(m => m.id === targetMessage.id);
            if (promptIndex > -1) {
                messages.value = messages.value.slice(0, promptIndex + 1);
            } else {
                // If the message wasn't in our current view, reload the whole branch
                await getActions().selectDiscussion(currentDiscussionId.value, targetMessage.id); 
                return; 
            }
            
            // 4. Trigger the new generation sequence
            await sendMessage({
                prompt: targetMessage.content,
                image_server_paths: targetMessage.server_image_paths || [],
                localImageUrls: targetMessage.image_references || [],
                is_resend: true,
                parent_message_id: targetMessage.id
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
