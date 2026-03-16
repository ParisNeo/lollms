import { defineStore, storeToRefs } from 'pinia';
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import apiClient from '../services/api'; // Import apiClient
import { useUiStore } from './ui';
import { useAuthStore } from './auth';
import { useDataStore } from './data';
import { useTasksStore } from './tasks';
import { useMemoriesStore } from './memories'; // Import MemoriesStore
import useEventBus from '../services/eventBus';

// Import ALL composables
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
    const tasksStore = useTasksStore();
    const dataStore = useDataStore();
    const authStore = useAuthStore();
    const memoriesStore = useMemoriesStore(); // Initialize
    const { user } = storeToRefs(authStore);
    const { tasks } = storeToRefs(tasksStore);
    const { on, off, emit } = useEventBus();

    // --- STATE ---
    const discussions = ref({});
    const discussionGroups = ref([]);
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
    const isLoadingArtefacts = ref(false);
    const liveDataZoneTokens = ref({ discussion: 0, user: 0, personality: 0, memory: 0 });
    const promptInsertionText = ref('');
    const promptLoadedArtefacts = ref(new Set());
    const attachedSkills = ref([]); // Staged skills for the next message
    const activeUpdatingArtefacts = ref(new Set()); // Files AI is currently writing to
    const liveArtefactBuffers = ref({}); // Temporary storage for streaming content (reactive object)
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

    /**
     * Discussion Zone is now strictly for User Instructions. 
     * Mirroring of artefacts is handled natively by the library's layered context model.
     */

    // --- WATCHER for task updates ---
    // [OPTIMIZATION] Removed { deep: true } to prevent performance freeze on large task lists.
    // The tasks store uses shallowRef and replaces the array reference on updates, so deep watch is unnecessary.
    watch(tasks, async (newTasks) => {
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
                            if (trackedTask.type === 'import_url') {
                                getActions().fetchArtefacts(discussionId);
                            }
                            // --- FIX: Explicitly refresh memories when memorization completes ---
                            if (trackedTask.type === 'memorize') {
                                console.log("Memorization task completed. Refreshing memories...");
                                await memoriesStore.fetchMemories();
                                uiStore.addNotification('Memory bank updated.', 'success');
                            }
                        }
                        _clearActiveAiTask(discussionId);
                    }
                } else {
                    // Task ID exists in our tracker but not in the store list. 
                }
            }
        }
    });

    // NEW WATCHER: Watch for model changes to refresh context status
    watch(() => user.value?.lollms_model_name, (newModel, oldModel) => {
        if (newModel && newModel !== oldModel && currentDiscussionId.value) {
            getActions().fetchContextStatus(currentDiscussionId.value);
        }
    });

    // --- COMPUTED ---
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

    /**
     * Identifies notes and skills that are currently active in the context.
     */
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
    
    // Group artefacts by title, showing only the latest version but preserving 'is_loaded' status
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
        const modelInfo = dataStore.availableLollmsModels.find(m => m.id === modelId);
        return modelInfo?.alias?.has_vision ?? true;
    });

    async function removeContextItem(itemTitle, itemType) {
        // This is now handled by unloading the artefact in the library
        if (!activeDiscussion.value) return;
        await getActions().unloadArtefactFromContext({
            discussionId: activeDiscussion.value.id,
            artefactTitle: itemTitle
        });
    }

    const discussionGroupsTree = computed(() => {
        const groups = JSON.parse(JSON.stringify(discussionGroups.value));
        const allDiscussions = sortedDiscussions.value;
        const sortMode = authStore.user?.discussion_sorting_mode || 'alpha';
        
        const starred = allDiscussions.filter(d => d.is_starred);
        const nonStarredDiscussions = allDiscussions.filter(d => !d.is_starred);

        // Helper to get effective activity time for a group (recursive)
        const getGroupActivity = (group) => {
            let latest = new Date(group.updated_at || group.created_at).getTime();
            group.discussions?.forEach(d => {
                const dt = new Date(d.last_activity_at || d.created_at).getTime();
                if (dt > latest) latest = dt;
            });
            group.children?.forEach(child => {
                const dt = getGroupActivity(child);
                if (dt > latest) latest = dt;
            });
            return latest;
        };

        const groupsMap = new Map(groups.map(g => [g.id, { ...g, children: [], discussions: [] }]));
        
        nonStarredDiscussions.forEach(d => {
            if (d.group_id && groupsMap.has(d.group_id)) {
                groupsMap.get(d.group_id).discussions.push(d);
            }
        });
        
        const tree = [];
        for (const group of groupsMap.values()) {
            group.discussions.sort((a,b)=>new Date(b.last_activity_at || b.created_at) - new Date(a.last_activity_at || a.created_at));
            if (group.parent_id && groupsMap.has(group.parent_id)) {
                groupsMap.get(group.parent_id).children.push(group);
            } else {
                tree.push(group);
            }
        }

        const sortFn = (a, b) => {
            if (sortMode === 'activity') {
                return getGroupActivity(b) - getGroupActivity(a);
            }
            if (sortMode === 'date') {
                return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
            }
            return a.name.localeCompare(b.name);
        };

        for (const group of groupsMap.values()) {
            group.children.sort(sortFn);
        }
        
        const sortedTree = tree.sort(sortFn);
        const ungrouped = nonStarredDiscussions.filter(d => !d.group_id);

        return {
            starred,
            groups: sortedTree,
            ungrouped
        };
    });

    // --- ACTIONS ORCHESTRATION ---
    const _actions = {};
    const getActions = () => _actions;

    const composableState = {
        discussions, discussionGroups, sharedWithMe, isLoadingDiscussions, currentDiscussionId, currentGroupId, messages,
        isLoadingMessages, 
        generationInProgress, titleGenerationInProgressId, activeDiscussionContextStatus, activeAiTasks,
        activeDiscussionArtefacts, isLoadingArtefacts, liveDataZoneTokens, promptInsertionText,
        promptLoadedArtefacts, attachedSkills, activeUpdatingArtefacts, liveArtefactBuffers, // Added missing refs
        _clearActiveAiTask, activeDiscussion, activePersonality, emit,
        activeDiscussionParticipants, generationState, imageGenerationSystemPrompt,
        currentModelVisionSupport
    };
    const composableStores = { uiStore, authStore, dataStore, tasksStore };

    Object.assign(_actions, useDiscussionCore(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionArtefacts(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionDataZones(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionExports(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionGeneration(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionGroups(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionMessages(composableState, composableStores, getActions));
    Object.assign(_actions, useDiscussionSharing(composableState, composableStores, getActions));
    
    // Register the missing function in the actions registry
    _actions.removeContextItem = removeContextItem;

    async function generateTTSForMessage(messageId, text) {
        if (ttsState.value[messageId]?.isLoading) return;
    
        ttsState.value = { ...ttsState.value, [messageId]: { isLoading: true, audioUrl: null, error: null } };
    
        try {
            const response = await apiClient.post('/api/discussions/generate_tts', 
                { text },
                { responseType: 'blob' }
            );
            const audioBlob = new Blob([response.data], { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(audioBlob);
            
            ttsState.value[messageId] = { isLoading: false, audioUrl: audioUrl, error: null };
        } catch (error) {
            uiStore.addNotification('Failed to generate speech.', 'error');
            console.error("TTS generation failed:", error);
            ttsState.value[messageId] = { isLoading: false, audioUrl: null, error: 'Failed to generate audio.' };
        }
    }

    async function transcribeAudio(audioBlob) {
        const uiStore = useUiStore();
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
            await getActions().fetchContextStatus(currentDiscussionId.value);
        } catch (error) {
            uiStore.addNotification('Failed to toggle image status.', 'error');
        }
    }

    // NEW ACTION
    async function triggerTagGeneration({ messageId, tagContent, tagType, rawTag }) {
        if (!currentDiscussionId.value) return;

        // Simple parsing for width/height/n from rawTag if needed
        let width = 1024;
        let height = 1024;
        let num_images = 1;
        
        if (rawTag) {
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

    // Consolidation: Wikipedia, Github, StackOverflow, and Youtube imports are now handled in useDiscussionArtefacts.js

    // Event Bus Listener: Handle artefact/note/skill/widget completion
    on('artefact_done', (data) => {
        const discussionId = data.discussion_id;
        if (discussionId !== currentDiscussionId.value) return;

        const { id, title } = data.content;
        const key = id || title;
        if (key) {
            if (activeUpdatingArtefacts.value) {
                activeUpdatingArtefacts.value.delete(key);
            }
            // Use object spread for reactive re-assignment
            const nextBuffers = { ...liveArtefactBuffers.value };
            delete nextBuffers[key];
            liveArtefactBuffers.value = nextBuffers;
        }
        // Crucial: Fetch final content so it's ready for the fullscreen viewer
        getActions().fetchArtefacts(currentDiscussionId.value);
    });

    on('note_done', (data) => {
        const discussionId = data.discussion_id;
        if (discussionId !== currentDiscussionId.value) return;
        getActions().fetchArtefacts(currentDiscussionId.value);
    });

    on('skill_done', (data) => {
        const discussionId = data.discussion_id;
        if (discussionId !== currentDiscussionId.value) return;
        getActions().fetchArtefacts(currentDiscussionId.value);
    });

    on('widget_done', (data) => {
        const discussionId = data.discussion_id;
        if (discussionId !== currentDiscussionId.value) return;
        getActions().fetchArtefacts(currentDiscussionId.value);
    });
    
    function attachSkill(skill) {
        if (!attachedSkills.value.find(s => s.id === skill.id)) {
            attachedSkills.value.push(skill);
        }
    }

    function detachSkill(skillId) {
        attachedSkills.value = attachedSkills.value.filter(s => s.id !== skillId);
    }

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
        isLoadingArtefacts.value = false;
        liveDataZoneTokens.value = { discussion: 0, user: 0, personality: 0, memory: 0 };
        promptInsertionText.value = '';
        promptLoadedArtefacts.value = new Set();
        activeDiscussionParticipants.value = {};
        
        // Reset Workspace/Live Tracking
        activeUpdatingArtefacts.value = new Set();
        liveArtefactBuffers.value = {};
        
        // Defensive check for audio reset
        if (currentPlayingAudio.value?.audio) {
            try {
                currentPlayingAudio.value.audio.pause();
            } catch (e) { /* ignore cleanup errors */ }
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
        activeAiTasks, activeDiscussionArtefacts, isLoadingArtefacts, liveDataZoneTokens,
        promptInsertionText, promptLoadedArtefacts, sharedWithMe, activeDiscussionParticipants,
        attachedSkills, ttsState, generationState, currentPlayingAudio, imageGenerationSystemPrompt,

        // Computeds
        activeDiscussion, activeMessages, activeDiscussionContainsCode, sortedDiscussions,
        dataZonesTokensFromContext, currentModelVisionSupport, activePersonality, discussionGroupsTree,
        loadedContextItems,

        // Actions (Spread from composables)
        ..._actions,

        // Store-level methods
        attachSkill,
        detachSkill,
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
