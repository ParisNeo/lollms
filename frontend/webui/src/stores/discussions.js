// frontend/webui/src/stores/discussions.js
import { defineStore, storeToRefs } from 'pinia';
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import apiClient from '../services/api'; // Import apiClient
import { useUiStore } from './ui';
import { useAuthStore } from './auth';
import { useDataStore } from './data';
import { useTasksStore } from './tasks';
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
    const { tasks } = storeToRefs(tasksStore);
    const { on, off, emit } = useEventBus();

    // --- STATE ---
    const discussions = ref({});
    const discussionGroups = ref([]);
    const sharedWithMe = ref([]);
    const isLoadingDiscussions = ref(false);
    const currentDiscussionId = ref(null);
    const messages = ref([]);
    const isLoadingMessages = ref(false);
    const generationInProgress = ref(false);
    const titleGenerationInProgressId = ref(null);
    const activeDiscussionContextStatus = ref(null);
    const activeAiTasks = ref({});
    const activeDiscussionArtefacts = ref([]);
    const isLoadingArtefacts = ref(false);
    const liveDataZoneTokens = ref({ discussion: 0, user: 0, personality: 0, memory: 0 });
    const promptInsertionText = ref('');
    const promptLoadedArtefacts = ref(new Set());
    const activeDiscussionParticipants = ref({});
    const ttsState = ref({}); // NEW: { [messageId]: { isLoading: boolean, audioUrl: string|null, error: string|null } }
    const currentPlayingAudio = ref({ messageId: null, audio: null });

    function _clearActiveAiTask(discussionId) {
        if (activeAiTasks.value[discussionId]) {
            const newActiveTasks = { ...activeAiTasks.value };
            delete newActiveTasks[discussionId];
            activeAiTasks.value = newActiveTasks;
        }
    }

    // --- WATCHER for task updates ---
    watch(tasks, (newTasks) => {
        const activeTrackedTaskIds = Object.values(activeAiTasks.value).map(t => t.taskId).filter(Boolean);
        if (activeTrackedTaskIds.length === 0) return;

        for (const discussionId in activeAiTasks.value) {
            const trackedTask = activeAiTasks.value[discussionId];
            if (trackedTask && trackedTask.taskId) {
                const correspondingTaskInStore = newTasks.find(t => t.id === trackedTask.taskId);
                if (correspondingTaskInStore) {
                    const isFinished = ['completed', 'failed', 'cancelled'].includes(correspondingTaskInStore.status);
                    if (isFinished) {
                        if (correspondingTaskInStore.status === 'completed' && trackedTask.type === 'import_url') {
                            getActions().fetchArtefacts(discussionId);
                        }
                        _clearActiveAiTask(discussionId);
                    }
                } else {
                    // The task is no longer in the main list, it was probably cleared.
                    _clearActiveAiTask(discussionId);
                }
            }
        }
    }, { deep: true });

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
    
    const sortedDiscussions = computed(() => Object.values(discussions.value).sort((a, b) => new Date(b.last_activity_at || b.created_at) - new Date(a.last_activity_at || a.created_at)));
    const activeMessages = computed(() => messages.value);
    const dataZonesTokensFromContext = computed(() => activeDiscussionContextStatus.value?.zones?.system_context?.breakdown?.discussion_data_zone?.tokens || 0);
    const activeDiscussionContainsCode = computed(() => activeMessages.value.some(msg => msg.content && msg.content.includes('```')));
    const currentModelVisionSupport = computed(() => {
        const modelId = authStore.user?.lollms_model_name;
        if (!modelId) return true; // Default to true if no model selected
        const modelInfo = dataStore.availableLollmsModels.find(m => m.id === modelId);
        return modelInfo?.alias?.has_vision ?? true;
    });
    const discussionGroupsTree = computed(() => {
        const groups = JSON.parse(JSON.stringify(discussionGroups.value));
        const map = new Map(groups.map(g => [g.id, { ...g, children: [], discussions: [] }]));
        const tree = [];

        Object.values(discussions.value).forEach(d => {
            if (d.group_id && map.has(d.group_id)) {
                map.get(d.group_id).discussions.push(d);
            }
        });

        for (const group of map.values()) {
            if (group.parent_id && map.has(group.parent_id)) {
                map.get(group.parent_id).children.push(group);
            } else {
                tree.push(group);
            }
        }
        return tree.sort((a,b) => a.name.localeCompare(b.name));
    });

    // --- ACTIONS ORCHESTRATION ---
    const _actions = {};
    const getActions = () => _actions;

    const composableState = {
        discussions, discussionGroups, sharedWithMe, isLoadingDiscussions, currentDiscussionId, messages,
        isLoadingMessages, 
        generationInProgress, titleGenerationInProgressId, activeDiscussionContextStatus, activeAiTasks,
        activeDiscussionArtefacts, isLoadingArtefacts, liveDataZoneTokens, promptInsertionText,
        promptLoadedArtefacts, _clearActiveAiTask, activeDiscussion, activePersonality, emit,
        activeDiscussionParticipants
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

    async function generateTTSForMessage(messageId, text) {
        if (ttsState.value[messageId]?.isLoading) return;
    
        ttsState.value = { ...ttsState.value, [messageId]: { isLoading: true, audioUrl: null, error: null } };
    
        try {
            const response = await apiClient.post('/api/discussions/generate_tts', 
                { text },
                { responseType: 'blob' }
            );
            const audioBlob = new Blob([response.data], { type: 'audio/mpeg' });
            const audioUrl = URL.createObjectURL(audioBlob);
            
            ttsState.value[messageId] = { isLoading: false, audioUrl: audioUrl, error: null };
        } catch (error) {
            uiStore.addNotification('Failed to generate speech.', 'error');
            console.error("TTS generation failed:", error);
            ttsState.value[messageId] = { isLoading: false, audioUrl: null, error: 'Failed to generate audio.' };
        }
    }
    
    function playAudio(messageId, audioElement) {
        if (currentPlayingAudio.value.audio && currentPlayingAudio.value.audio !== audioElement) {
            currentPlayingAudio.value.audio.pause();
        }
        currentPlayingAudio.value = { messageId, audio: audioElement };
        // The play action is initiated by the user on the element itself.
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

    function $reset() {
        discussions.value = {};
        discussionGroups.value = [];
        sharedWithMe.value = [];
        isLoadingDiscussions.value = false;
        currentDiscussionId.value = null;
        messages.value = [];
        isLoadingMessages.value = false;
        generationInProgress.value = false;
        titleGenerationInProgressId.value = null;
        activeDiscussionContextStatus.value = null;
        activeAiTasks.value = {};
        activeDiscussionArtefacts.value = [];
        isLoadingArtefacts.value = false;
        liveDataZoneTokens.value = { discussion: 0, user: 0, personality: 0, memory: 0 };
        promptInsertionText.value = '';
        promptLoadedArtefacts.value = new Set();
        activeDiscussionParticipants.value = {};
        if (currentPlayingAudio.value.audio) {
            currentPlayingAudio.value.audio.pause();
        }
        currentPlayingAudio.value = { messageId: null, audio: null };
        ttsState.value = {};
    }

    // --- FINAL RETURN ---
    return {
        // State
        discussions, currentDiscussionId, messages, generationInProgress, discussionGroups,
        isLoadingDiscussions, isLoadingMessages, 
        titleGenerationInProgressId, activeDiscussionContextStatus,
        activeAiTasks, activeDiscussionArtefacts, isLoadingArtefacts, liveDataZoneTokens,
        promptInsertionText, promptLoadedArtefacts, sharedWithMe, activeDiscussionParticipants,
        ttsState,
        currentPlayingAudio,
        // Computed
        activeDiscussion, activeMessages, activeDiscussionContainsCode, sortedDiscussions,
        dataZonesTokensFromContext, currentModelVisionSupport, activePersonality, discussionGroupsTree,
        // Actions
        ..._actions,
        generateTTSForMessage,
        playAudio,
        onAudioPausedOrEnded,
        stopCurrentAudio,
        $reset,
    };
});