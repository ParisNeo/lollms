import { defineStore, storeToRefs } from 'pinia';
import { ref, computed, watch } from 'vue';
import apiClient from '../services/api'; 
import { useUiStore } from './ui';
import { useAuthStore } from './auth';
import { useDataStore } from './data';
import { useTasksStore } from './tasks';
import useEventBus from '../services/eventBus';

// Import Composables
import { useDiscussionCore } from './composables/useDiscussionCore';
import { useDiscussionArtefacts } from './composables/useDiscussionArtefacts';
import { useDiscussionDataZones } from './composables/useDiscussionDataZones';
import { useDiscussionExports } from './composables/useDiscussionExports';
import { useDiscussionGeneration } from './composables/useDiscussionGeneration';
import { useDiscussionGroups } from './composables/useDiscussionGroups';
import { useDiscussionMessages } from './composables/useDiscussionMessages';
import { useDiscussionSharing } from './composables/useDiscussionSharing';

export const useDiscussionsStore = defineStore('discussions', () => {
    // --- STORES ---
    const uiStore = useUiStore();
    const authStore = useAuthStore();
    const dataStore = useDataStore();
    const tasksStore = useTasksStore();

    const { user } = storeToRefs(authStore);
    const { on, off, emit } = useEventBus();

    // --- STATE REFS ---
    const discussions = ref({});
    const discussionGroups = ref([]);
    const starredArtefacts = ref([]);

    try {
        const stored = localStorage.getItem('starredArtefacts');
        if (stored) {
            const parsed = JSON.parse(stored);
            if (Array.isArray(parsed)) {
                starredArtefacts.value = parsed;
            }
        }
    } catch (e) {
        console.error("Failed to parse starredArtefacts:", e);
    }

    const sharedWithMe = ref([]);
    const isLoadingDiscussions = ref(false);
    const currentDiscussionId = ref(null);
    const currentGroupId = ref(null);
    const messages = ref([]);
    const isLoadingMessages = ref(false);
    const generationInProgress = ref(false);
    const generationState = ref({ status: 'idle', details: '' });
    const titleGenerationInProgressId = ref(null);
    const activeDiscussionContextStatus = ref(null);
    const activeAiTasks = ref({});
    const activeDiscussionArtefacts = ref([]);
    const allUserArtefacts = ref([]);
    const isLoadingArtefacts = ref(false);
    const liveDataZoneTokens = ref({ discussion: 0, user: 0, personality: 0, memory: 0 });
    const promptInsertionText = ref('');
    const promptLoadedArtefacts = ref(new Set());
    const attachedSkills = ref([]);
    const activeUpdatingArtefacts = ref(new Set());
    const liveArtefactBuffers = ref({});
    const activeDiscussionParticipants = ref({});
    const ttsState = ref({});
    const currentPlayingAudio = ref({ messageId: null, audio: null });
    const imageGenerationSystemPrompt = ref('');

    function _clearActiveAiTask(discussionId) {
        if (activeAiTasks.value[discussionId]) {
            const newActiveTasks = { ...activeAiTasks.value };
            delete newActiveTasks[discussionId];
            activeAiTasks.value = newActiveTasks;
        }
    }

    function toggleStarArtefact(title) {
        const current = [...starredArtefacts.value];
        const idx = current.indexOf(title);
        if (idx > -1) {
            current.splice(idx, 1);
        } else {
            current.push(title);
        }
        starredArtefacts.value = current;
        localStorage.setItem('starredArtefacts', JSON.stringify(starredArtefacts.value));
    }

    // --- ACTIONS INITIALIZATION (CRITICAL: Defined BEFORE computeds and watchers) ---
    const _actions = {};
    const getActions = () => _actions;

    // --- COMPUTEDS ---
    const activeDiscussion = computed(() => {
        if (!currentDiscussionId.value) return null;
        if (discussions.value[currentDiscussionId.value]) {
            return discussions.value[currentDiscussionId.value];
        }
        return sharedWithMe.value.find(d => d.id === currentDiscussionId.value) || null;
    });

    const activePersonality = computed(() => {
        const personalityId = authStore.user?.active_personality_id;
        if (!personalityId) return null;
        return dataStore.getPersonalityById(personalityId);
    });

    const loadedContextItems = computed(() => {
        if (!Array.isArray(activeDiscussionArtefacts.value)) return [];
        return activeDiscussionArtefacts.value.filter(art => 
            art.is_loaded && (art.artefact_type === 'note' || art.artefact_type === 'skill')
        );
    });
    
    const sortedDiscussions = computed(() => Object.values(discussions.value).sort((a, b) => new Date(b.last_activity_at || b.created_at) - new Date(a.last_activity_at || a.created_at)));
    const activeMessages = computed(() => messages.value);
    const dataZonesTokensFromContext = computed(() => activeDiscussionContextStatus.value?.zones?.system_context?.breakdown?.discussion_data_zone?.tokens || 0);
    const activeDiscussionContainsCode = computed(() => activeMessages.value.some(msg => msg.content && msg.content.includes('```')));
    
    const uniqueAttachedArtefacts = computed(() => {
        const list = activeDiscussionArtefacts.value;
        if (!list || !Array.isArray(list)) return [];
        
        const groups = {};
        list.forEach(art => {
            if (!groups[art.title] || art.version > groups[art.title].version) {
                groups[art.title] = { ...art };
            }
        });
        
        return Object.values(groups).sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
    });

    const currentModelVisionSupport = computed(() => {
        const modelId = authStore.user?.lollms_model_name;
        if (!modelId) return true;
        const modelInfo = Array.isArray(dataStore.availableLollmsModels) ? dataStore.availableLollmsModels.find(m => m.id === modelId) : null;
        return modelInfo?.alias?.has_vision ?? true;
    });

    async function removeContextItem(itemTitle, itemType) {
        if (!activeDiscussion.value) return;
        if (typeof getActions().unloadArtefactFromContext === 'function') {
            await getActions().unloadArtefactFromContext({
                discussionId: activeDiscussion.value.id,
                artefactTitle: itemTitle
            });
        }
    }

    const discussionGroupsTree = computed(() => {
        const sortMode = authStore.user?.discussion_sorting_mode || 'date';
        const sortOrder = authStore.user?.discussion_sorting_order || 'desc';
        const isAsc = sortOrder === 'asc';

        const groups = JSON.parse(JSON.stringify(discussionGroups.value));
        const allDiscussions = Object.values(discussions.value);

        const starred = allDiscussions.filter(d => d.is_starred);
        const nonStarredDiscussions = allDiscussions.filter(d => !d.is_starred);

        const sortDiscussionsFn = (a, b) => {
            let res = 0;
            if (sortMode === 'alpha') res = a.title.localeCompare(b.title);
            else if (sortMode === 'activity') {
                const timeA = new Date(a.last_activity_at || a.created_at).getTime();
                const timeB = new Date(b.last_activity_at || b.created_at).getTime();
                res = timeA - timeB;
            } else {
                res = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
            }
            return isAsc ? res : -res;
        };

        const getGroupSortValue = (group) => {
            if (sortMode === 'alpha') return group.name;

            let bestTime = new Date(group.created_at).getTime();

            const checkItem = (d) => {
                const t = new Date(sortMode === 'activity' ? (d.last_activity_at || d.created_at) : d.created_at).getTime();
                if (t > bestTime) bestTime = t;
            };

            group.discussions?.forEach(checkItem);
            group.children?.forEach(c => {
                const childTime = getGroupSortValue(c);
                if (typeof childTime === 'number' && childTime > bestTime) bestTime = childTime;
            });
            return bestTime;
        };

        const sortGroupsFn = (a, b) => {
            let res = 0;
            if (sortMode === 'alpha') res = a.name.localeCompare(b.name);
            else res = getGroupSortValue(a) - getGroupSortValue(b);
            return isAsc ? res : -res;
        };

        const groupsMap = new Map(groups.map(g => [g.id, { ...g, children: [], discussions: [] }]));

        nonStarredDiscussions.forEach(d => {
            if (d.group_id && groupsMap.has(d.group_id)) {
                groupsMap.get(d.group_id).discussions.push(d);
            }
        });

        const tree = [];
        for (const group of groupsMap.values()) {
            group.discussions.sort(sortDiscussionsFn);
            if (group.parent_id && groupsMap.has(group.parent_id)) {
                groupsMap.get(group.parent_id).children.push(group);
            } else {
                tree.push(group);
            }
        }

        for (const group of groupsMap.values()) {
            group.children.sort(sortGroupsFn);
        }

        const sortedTree = tree.sort(sortGroupsFn);
        const ungrouped = nonStarredDiscussions.filter(d => !d.group_id).sort(sortDiscussionsFn);
        const sortedStarred = starred.sort(sortDiscussionsFn);

        return {
            starred: sortedStarred,
            groups: sortedTree,
            ungrouped
        };
    });

    // --- COMPOSE ACTIONS ---
    const composableState = {
        discussions, discussionGroups, sharedWithMe, isLoadingDiscussions, currentDiscussionId, currentGroupId, messages,
        isLoadingMessages, 
        generationInProgress, titleGenerationInProgressId, activeDiscussionContextStatus, activeAiTasks,
        activeDiscussionArtefacts, allUserArtefacts, isLoadingArtefacts, liveDataZoneTokens, promptInsertionText,
        promptLoadedArtefacts, attachedSkills, activeUpdatingArtefacts, liveArtefactBuffers,
        _clearActiveAiTask, activeDiscussion, activePersonality, emit,
        activeDiscussionParticipants, generationState, imageGenerationSystemPrompt,
        currentModelVisionSupport
    };
    const composableStores = { 
        get uiStore() { return useUiStore(); }, 
        get authStore() { return useAuthStore(); }, 
        get dataStore() { return useDataStore(); }, 
        get tasksStore() { return useTasksStore(); } 
    };

    Object.assign(_actions, useDiscussionCore(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionArtefacts(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionDataZones(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionExports(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionGeneration(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionGroups(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionMessages(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionSharing(composableState, composableStores, getActions));
    
    _actions.removeContextItem = removeContextItem;

    const originalCreateNewDiscussion = _actions.createNewDiscussion;
    if (originalCreateNewDiscussion) {
        _actions.createNewDiscussion = async function(...args) {
            uiStore.isDataZoneVisible = false;
            uiStore.activeSplitArtefactTitle = null;
            uiStore.dataZoneTab = 'context';
            return await originalCreateNewDiscussion.apply(this, args);
        };
    }

    // --- HELPER METHODS ---
    async function generateTTSRaw(text) {
        const response = await apiClient.post('/api/discussions/generate_tts', 
            { text },
            { responseType: 'blob' }
        );
        return new Blob([response.data], { type: 'audio/wav' });
    }

    async function generateTTSForMessage(messageId) {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.post(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}/generate_audio`);
            const task = response.data;
            tasksStore.addTask(task);

            const msg = messages.value.find(m => m.id === messageId);
            if (msg) {
                msg.isGeneratingAudio = true;
                msg.audioTaskId = task.id;
            }
            uiStore.addNotification('Voice synthesis started in background...', 'info');
        } catch (error) {
            uiStore.addNotification('Failed to start speech generation.', 'error');
        }
    }

    async function transcribeAudio(audioBlob) {
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.wav');
        try {
            const response = await apiClient.post('/api/discussions/stt', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            return response.data.text;
        } catch (error) {
            uiStore.addNotification('Speech-to-text transcription failed.', 'error');
            console.error('STT Error:', error);
            return null;
        }
    }
    
    function playAudio(messageId, audioElement) {
        if (currentPlayingAudio.value.audio && currentPlayingAudio.value.audio !== audioElement) {
            currentPlayingAudio.value.audio.pause();
        }
        currentPlayingAudio.value = { messageId, audio: audioElement };
    }
    
    function onAudioPausedOrEnded(messageId) {
        if (currentPlayingAudio.value.messageId === messageId) {
            currentPlayingAudio.value = { messageId: null, audio: null };
        }
    }
    
    function stopCurrentAudio() {
        if (currentPlayingAudio.value.audio) {
            currentPlayingAudio.value.audio.pause();
            currentPlayingAudio.value = { messageId: null, audio: null };
        }
    }

    function handleDiscussionImagesUpdated(data) {
        if (activeDiscussion.value && activeDiscussion.value.id === data.discussion_id) {
            activeDiscussion.value.discussion_images = data.discussion_images;
            activeDiscussion.value.active_discussion_images = data.active_discussion_images;
            uiStore.addNotification('Image generation complete!', 'success');
        }
    }

    async function toggleDiscussionImage(imageIndex) {
        if (!currentDiscussionId.value) return;
        try {
            const response = await apiClient.put(`/api/discussions/${currentDiscussionId.value}/images/${imageIndex}/toggle`);
            if (activeDiscussion.value) {
                activeDiscussion.value.discussion_images = response.data.discussion_images;
                activeDiscussion.value.active_discussion_images = response.data.active_discussion_images;
            }
            if (typeof getActions().fetchContextStatus === 'function') {
                await getActions().fetchContextStatus(currentDiscussionId.value);
            }
        } catch (error) {
            uiStore.addNotification('Failed to toggle image status.', 'error');
        }
    }

    async function triggerTagGeneration({ messageId, tagContent, tagType, rawTag }) {
        if (!currentDiscussionId.value) return;

        let width = 1024;
        let height = 1024;
        let num_images = 1;
        
        if (rawTag && typeof rawTag === 'string') {
            const wMatch = rawTag.match(/width="(\d+)"/);
            const hMatch = rawTag.match(/height="(\d+)"/);
            const nMatch = rawTag.match(/n="(\d+)"/);
            if (wMatch) width = parseInt(wMatch[1]);
            if (hMatch) height = parseInt(hMatch[1]);
            if (nMatch) num_images = parseInt(nMatch[1]);
        }

        const formData = new FormData();
        formData.append('tag_content', tagContent);
        formData.append('tag_type', tagType);
        formData.append('width', width);
        formData.append('height', height);
        formData.append('num_images', num_images);
        
        try {
            const response = await apiClient.post(`/api/discussions/${currentDiscussionId.value}/messages/${messageId}/trigger_tag`, formData);
            const task = response.data;
            tasksStore.addTask(task);
            uiStore.addNotification(`Started ${tagType} regeneration task.`, 'info');
        } catch (error) {
            uiStore.addNotification('Failed to trigger generation.', 'error');
            console.error(error);
        }
    }

    function attachSkill(skill) {
        if (!attachedSkills.value.find(s => s.id === skill.id)) {
            attachedSkills.value.push(skill);
        }
    }

    function detachSkill(skillId) {
        attachedSkills.value = attachedSkills.value.filter(s => s.id !== skillId);
    }

    // --- EVENT BUS LISTENERS ---
    on('artefact_done', (data) => {
        const discussionId = data.discussion_id;
        if (discussionId !== currentDiscussionId.value) return;

        const { id, title } = data.content || {};
        const key = id || title;
        if (key) {
            if (activeUpdatingArtefacts.value) {
                activeUpdatingArtefacts.value.delete(key);
            }
            const nextBuffers = { ...liveArtefactBuffers.value };
            delete nextBuffers[key];
            liveArtefactBuffers.value = nextBuffers;
        }
        if (typeof getActions().fetchArtefacts === 'function') {
            getActions().fetchArtefacts(currentDiscussionId.value);
        }
    });

    const KNOWLEDGE_DONE_EVENTS = ['artefact_done', 'note_done', 'skill_done', 'widget_done', 'artefact_update_done'];
    KNOWLEDGE_DONE_EVENTS.forEach(eventName => {
        on(eventName, (data) => {
            const discussionId = data?.discussion_id || currentDiscussionId.value;
            if (discussionId && discussionId === currentDiscussionId.value) {
                if (typeof getActions().fetchArtefacts === 'function') {
                    getActions().fetchArtefacts(discussionId);
                }
                if (typeof getActions().fetchContextStatus === 'function') {
                    getActions().fetchContextStatus(discussionId);
                }
            }
        });
    });

    // --- WATCHERS (Attached AFTER all functions/actions are defined) ---
    watch(() => {
        try {
            return tasksStore.tasks;
        } catch (e) {
            return [];
        }
    }, async (newTasks) => {
        if (!newTasks) return;
        const artefactAudioTask = newTasks.find(t => t.name && t.name.startsWith('Audio Export:') && t.status === 'completed' && t.result?.download_url);
        if (artefactAudioTask && !artefactAudioTask._processed_for_download) {
            artefactAudioTask._processed_for_download = true; 
            const downloadUrl = `${apiClient.defaults.baseURL}${artefactAudioTask.result.download_url}`;
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = artefactAudioTask.result.filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            uiStore.addNotification(`Audio file ready: ${artefactAudioTask.result.filename}`, 'success');
        }

        const msgAudioTask = newTasks.find(t => t.name === 'Generating Audio for Message' && (t.status === 'completed' || t.status === 'failed' || t.status === 'cancelled'));
        if (msgAudioTask && !msgAudioTask._processed_for_ui) {
            msgAudioTask._processed_for_ui = true;

            const messageId = msgAudioTask.result?.message_id;
            if (messageId) {
                const msg = messages.value.find(m => m.id === messageId);
                if (msg) {
                    msg.isGeneratingAudio = false;
                    if (msgAudioTask.status === 'completed' && msgAudioTask.result?.audio_url) {
                        if (!msg.metadata) msg.metadata = {};
                        msg.metadata.audio_url = `${apiClient.defaults.baseURL}${msgAudioTask.result.audio_url}`;
                        uiStore.addNotification('Voice synthesis complete.', 'success');
                    }
                    const idx = messages.value.indexOf(msg);
                    messages.value.splice(idx, 1, { ...msg });
                }
            }
        }

        const pruneTask = newTasks.find(t => t.name && t.name.startsWith('Prune empty discussions') && t.status === 'completed');
        if (pruneTask && !pruneTask._processed_for_ui) {
            pruneTask._processed_for_ui = true;
            if (typeof getActions().loadDiscussions === 'function') {
                await getActions().loadDiscussions();
            }

            if (currentDiscussionId.value && !discussions.value[currentDiscussionId.value]) {
                if (typeof getActions().selectDiscussion === 'function') {
                    await getActions().selectDiscussion(null);
                }
                uiStore.setMainView('feed');
            }
            uiStore.addNotification('Empty discussions pruned successfully.', 'success');
        }

        const activeTrackedTaskIds = Object.values(activeAiTasks.value).map(t => t.taskId).filter(Boolean);
        if (activeTrackedTaskIds.length === 0) return;

        for (const discussionId in activeAiTasks.value) {
            const trackedTask = activeAiTasks.value[discussionId];
            if (trackedTask && trackedTask.taskId) {
                const correspondingTaskInStore = newTasks.find(t => t.id === trackedTask.taskId);
                if (correspondingTaskInStore) {
                    const isFinished = ['completed', 'failed', 'cancelled'].includes(correspondingTaskInStore.status);
                    if (isFinished) {
                        if (correspondingTaskInStore.status === 'completed') {
                            if (trackedTask.type === 'import_url' || trackedTask.type === 'import_file') {
                                if (typeof getActions().fetchArtefacts === 'function') {
                                    getActions().fetchArtefacts(discussionId);
                                }
                            }
                            if (trackedTask.type === 'memorize') {
                                try {
                                    const { useMemoriesStore } = await import('./memories');
                                    await useMemoriesStore().fetchMemories();
                                    uiStore.addNotification('Memory bank updated.', 'success');
                                } catch (memErr) {
                                    console.warn("Failed to auto-refresh memories list:", memErr);
                                }
                            }
                        }
                        _clearActiveAiTask(discussionId);
                    }
                }
            }
        }
    });

    watch(() => user.value?.lollms_model_name, (newModel, oldModel) => {
        if (newModel && newModel !== oldModel && currentDiscussionId.value) {
            if (typeof getActions().fetchContextStatus === 'function') {
                getActions().fetchContextStatus(currentDiscussionId.value);
            }
        }
    });

    function $reset() {
        discussions.value = {};
        discussionGroups.value = [];
        sharedWithMe.value = [];
        isLoadingDiscussions.value = false;
        currentDiscussionId.value = null;
        currentGroupId.value = null;
        messages.value = [];
        isLoadingMessages.value = false;
        generationInProgress.value = false;
        generationState.value = { status: 'idle', details: '' };
        titleGenerationInProgressId.value = null;
        activeDiscussionContextStatus.value = null;
        activeAiTasks.value = {};
        activeDiscussionArtefacts.value = [];
        allUserArtefacts.value = [];
        isLoadingArtefacts.value = false;
        liveDataZoneTokens.value = { discussion: 0, user: 0, personality: 0, memory: 0 };
        promptInsertionText.value = '';
        promptLoadedArtefacts.value = new Set();
        activeDiscussionParticipants.value = {};
        activeUpdatingArtefacts.value = new Set();
        liveArtefactBuffers.value = {};
        
        if (currentPlayingAudio.value?.audio) {
            try {
                currentPlayingAudio.value.audio.pause();
            } catch (e) { /* ignore */ }
        }
        currentPlayingAudio.value = { messageId: null, audio: null };
        ttsState.value = {};
        imageGenerationSystemPrompt.value = '';
    }

    return {
        // State
        discussions, currentDiscussionId, currentGroupId, messages, generationInProgress, discussionGroups,
        isLoadingDiscussions, isLoadingMessages, 
        titleGenerationInProgressId, activeDiscussionContextStatus,
        activeAiTasks, activeDiscussionArtefacts, allUserArtefacts, isLoadingArtefacts, liveDataZoneTokens,
        promptInsertionText, promptLoadedArtefacts, sharedWithMe, activeDiscussionParticipants,
        attachedSkills, ttsState, generationState, currentPlayingAudio, imageGenerationSystemPrompt,
        activeUpdatingArtefacts, liveArtefactBuffers,
        
        starredArtefacts,
        toggleStarArtefact,

        // Computeds
        activeDiscussion, activeMessages, activeDiscussionContainsCode, sortedDiscussions,
        dataZonesTokensFromContext, currentModelVisionSupport, activePersonality, discussionGroupsTree,
        loadedContextItems,

        // Actions
        ..._actions,

        // Store-level methods
        attachSkill,
        detachSkill,
        generateTTSRaw,
        generateTTSForMessage,
        transcribeAudio,
        playAudio,
        onAudioPausedOrEnded,
        stopCurrentAudio,
        handleDiscussionImagesUpdated,
        toggleDiscussionImage,
        triggerTagGeneration,
        $reset,
    };
});