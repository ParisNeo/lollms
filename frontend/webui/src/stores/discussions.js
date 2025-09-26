// frontend/webui/src/stores/discussions.js
import { defineStore, storeToRefs } from 'pinia';
import { ref, computed, onMounted, onUnmounted } from 'vue';
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

    function _clearActiveAiTask(discussionId) {
        if (activeAiTasks.value[discussionId]) {
            const newActiveTasks = { ...activeAiTasks.value };
            delete newActiveTasks[discussionId];
            activeAiTasks.value = newActiveTasks;
        }
    }

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

    // --- EVENT-BASED HANDLER FOR TASK COMPLETIONS ---
    function handleTaskCompletion(completedTask) {
        console.log("Handling task completion in discussions store:", completedTask);
        if (!completedTask || !completedTask.id) return;

        // Find if this task was tracked for a specific discussion
        for (const discussionId in activeAiTasks.value) {
            const trackedTask = activeAiTasks.value[discussionId];
            if (trackedTask && trackedTask.taskId === completedTask.id) {
                if (completedTask.status === 'completed') {
                    if (trackedTask.type === 'import_url') {
                        _actions.fetchArtefacts(discussionId);
                    }
                    if (trackedTask.type === 'memorize') {
                        // The memory store should probably handle its own refresh
                    }
                    if (trackedTask.type === 'summarize' || trackedTask.type === 'generate_image') {
                        _actions.refreshDataZones(discussionId);
                    }
                }
                _clearActiveAiTask(discussionId);
                return; // Found the task, no need to check others
            }
        }
    }

    // Register the event listener directly in the store setup
    on('task:completed', handleTaskCompletion);

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
    }

    // --- FINAL RETURN ---
    return {
        // State
        discussions, currentDiscussionId, messages, generationInProgress, discussionGroups,
        isLoadingDiscussions, isLoadingMessages, 
        titleGenerationInProgressId, activeDiscussionContextStatus,
        activeAiTasks, activeDiscussionArtefacts, isLoadingArtefacts, liveDataZoneTokens,
        promptInsertionText, promptLoadedArtefacts, sharedWithMe, activeDiscussionParticipants,
        // Computed
        activeDiscussion, activeMessages, activeDiscussionContainsCode, sortedDiscussions,
        dataZonesTokensFromContext, currentModelVisionSupport, activePersonality, discussionGroupsTree,
        // Actions
        ..._actions,
        $reset,
    };
});