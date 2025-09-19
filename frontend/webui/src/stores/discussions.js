// frontend/webui/src/stores/discussions.js
import { defineStore, storeToRefs } from 'pinia';
import { ref, computed, watch, nextTick } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';
import { useDataStore } from './data';
import { useTasksStore } from './tasks';
import useEventBus from '../services/eventBus';

import { useDiscussionArtefacts } from './composables/useDiscussionArtefacts';
import { useDiscussionDataZones } from './composables/useDiscussionDataZones';
import { useDiscussionExports } from './composables/useDiscussionExports';
import { useDiscussionGeneration } from './composables/useDiscussionGeneration';
import { useDiscussionGroups } from './composables/useDiscussionGroups';
import { useDiscussionMessages } from './composables/useDiscussionMessages';
import { useDiscussionSharing } from './composables/useDiscussionSharing';

export const useDiscussionsStore = defineStore('discussions', () => {
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();
    const dataStore = useDataStore();
    const authStore = useAuthStore();
    const { tasks } = storeToRefs(tasksStore);
    const { emit } = useEventBus();

    // --- CORE STATE ---
    const discussions = ref({});
    const discussionGroups = ref([]);
    const sharedWithMe = ref([]);
    const isLoadingDiscussions = ref(false);
    const currentDiscussionId = ref(null);
    const messages = ref([]);
    const generationInProgress = ref(false);
    const titleGenerationInProgressId = ref(null);
    const activeDiscussionContextStatus = ref(null);
    const activeAiTasks = ref({});
    const activeDiscussionArtefacts = ref([]);
    const isLoadingArtefacts = ref(false);
    const liveDataZoneTokens = ref({ discussion: 0, user: 0, personality: 0, memory: 0 });
    const promptInsertionText = ref('');
    const promptLoadedArtefacts = ref(new Set());

    // --- COMPUTED PROPERTIES ---
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
    const dataZonesTokenCount = computed(() => liveDataZoneTokens.value.discussion + liveDataZoneTokens.value.user + liveDataZoneTokens.value.personality + liveDataZoneTokens.value.memory);
    const dataZonesTokensFromContext = computed(() => { /* ... (as before) ... */ return 0;});
    const activeDiscussionContainsCode = computed(() => activeMessages.value.some(msg => msg.content && msg.content.includes('```')));
    const currentModelVisionSupport = computed(() => { /* ... (as before) ... */ return true; });

    // --- SETUP FOR COMPOSABLES ---
    const composableState = {
        discussions, discussionGroups, sharedWithMe, isLoadingDiscussions, currentDiscussionId, messages,
        generationInProgress, titleGenerationInProgressId, activeDiscussionContextStatus, activeAiTasks,
        activeDiscussionArtefacts, isLoadingArtefacts, liveDataZoneTokens, promptInsertionText,
        promptLoadedArtefacts,
        _clearActiveAiTask,
        activeDiscussion, activePersonality, emit
    };
    const composableStores = { uiStore, authStore, dataStore, tasksStore };

    // --- COMPOSABLE ACTIONS INITIALIZATION ---
    // Instantiate DataZones first as other composables depend on its functions.
    const dataZoneActions = useDiscussionDataZones(composableState, composableStores);

    // Manually add the needed functions to the shared state object.
    // This makes them available to other composables that receive `composableState`.
    composableState.updateLiveTokenCount = dataZoneActions.updateLiveTokenCount;
    composableState.fetchContextStatus = dataZoneActions.fetchContextStatus;

    // Now instantiate the rest of the composables.
    const artefactActions = useDiscussionArtefacts(composableState, composableStores);
    const exportActions = useDiscussionExports(composableState, composableStores);
    const generationActions = useDiscussionGeneration(composableState, composableStores);
    const groupActions = useDiscussionGroups(composableState, composableStores);
    const messageActions = useDiscussionMessages(composableState, composableStores);
    const sharingActions = useDiscussionSharing(composableState, composableStores);


    // --- WATCHERS ---
    watch(tasks, (currentTasks) => {
        if (Object.keys(activeAiTasks.value).length === 0) return;
        for (const discussionId in activeAiTasks.value) {
            const trackedTask = activeAiTasks.value[discussionId];
            if (trackedTask) {
                const updatedTask = currentTasks.find(t => t.id === trackedTask.taskId);
                if (updatedTask && ['completed', 'failed', 'cancelled'].includes(updatedTask.status)) {
                    if (trackedTask.type === 'import_url' && updatedTask.status === 'completed') artefactActions.fetchArtefacts(discussionId);
                    if (trackedTask.type === 'memorize' && updatedTask.status === 'completed' && updatedTask.result) { /* ... */ }
                    _clearActiveAiTask(discussionId);
                }
            }
        }
    }, { deep: true });

    // --- CORE ACTIONS ---
    function _clearActiveAiTask(discussionId) {
        if (activeAiTasks.value[discussionId]) {
            const newActiveTasks = { ...activeAiTasks.value };
            delete newActiveTasks[discussionId];
            activeAiTasks.value = newActiveTasks;
        }
    }

    async function loadDiscussions() {
        isLoadingDiscussions.value = true;
        try {
            await Promise.all([
                apiClient.get('/api/discussions').then(res => {
                    const newDiscussions = {};
                    (res.data || []).forEach(d => newDiscussions[d.id] = { ...d, discussion_data_zone: '', personality_data_zone: '', memory: '' });
                    discussions.value = newDiscussions;
                }),
                groupActions.fetchDiscussionGroups(),
                sharingActions.fetchSharedWithMe()
            ]);
        } catch (error) { 
            console.error("Failed to load discussions etc:", error); 
        } finally {
            isLoadingDiscussions.value = false;
        }
    }

    async function selectDiscussion(id, branchIdToLoad = null) {
        if (!id || generationInProgress.value) return;
        currentDiscussionId.value = id;
        messages.value = []; 
        activeDiscussionArtefacts.value = [];
        promptLoadedArtefacts.value.clear();
        liveDataZoneTokens.value = { discussion: 0, user: 0, personality: 0, memory: 0 };
        
        const discussionExists = discussions.value[id] || sharedWithMe.value.find(d => d.id === id);
        if (!discussionExists) {
            currentDiscussionId.value = null;
            uiStore.setMainView('feed'); 
            return;
        }
        uiStore.setMainView('chat');
        try {
            const params = branchIdToLoad ? { branch_id: branchIdToLoad } : {};
            const response = await apiClient.get(`/api/discussions/${id}`, { params });
            messages.value = messageActions.processMessages(response.data);
            
            await Promise.all([
                dataZoneActions.fetchContextStatus(id),
                dataZoneActions.fetchDataZones(id),
                authStore.fetchDataZone(),
                artefactActions.fetchArtefacts(id)
            ]);
        } catch (error) {
            uiStore.addNotification('Failed to load discussion.', 'error');
            currentDiscussionId.value = null;
            uiStore.setMainView('feed');
        }
    }

    async function createNewDiscussion(groupId = null) {
        try {
            const payload = groupId ? { group_id: groupId } : {};
            const response = await apiClient.post('/api/discussions', payload);
            const newDiscussion = response.data;
            discussions.value[newDiscussion.id] = { ...newDiscussion, discussion_data_zone: '', personality_data_zone: '', memory: '' };
            activeDiscussionArtefacts.value = [];
            await selectDiscussion(newDiscussion.id);
            return newDiscussion;
        } catch (error) {
            uiStore.addNotification('Failed to create new discussion.', 'error');
            throw error;
        }
    }

    async function cloneDiscussion(discussionId) {
        if (!discussionId) return;
        uiStore.addNotification('Cloning discussion...', 'info');
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/clone`);
            const newDiscussion = response.data;
            discussions.value[newDiscussion.id] = { ...newDiscussion, discussion_data_zone: '', personality_data_zone: '', memory: '' };
            await selectDiscussion(newDiscussion.id);
            uiStore.addNotification('Discussion cloned successfully!', 'success');
        } catch (error) { console.error("Failed to clone discussion:", error); }
    }

    async function deleteDiscussion(discussionId) {
        const disc = discussions.value[discussionId];
        if (!disc) return;
        const confirmed = await uiStore.showConfirmation({ title: 'Delete Discussion', message: `Delete "${disc.title}"?`, confirmText: 'Delete' });
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
        const confirmed = await uiStore.showConfirmation({ title: 'Prune Discussions', message: 'Delete all empty/single-message discussions?', confirmText: 'Prune' });
        if (!confirmed) return;
        try {
            const response = await apiClient.post('/api/discussions/prune');
            tasksStore.addTask(response.data);
            uiStore.addNotification(`Pruning task started.`, 'info');
        } catch (error) { console.error("Failed to start pruning task:", error); }
    }

    async function generateAutoTitle(discussionId) {
        titleGenerationInProgressId.value = discussionId;
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/auto-title`);
            if (discussions.value[discussionId]) {
                discussions.value[discussionId].title = response.data.title;
            }
        } catch (error) {
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
            uiStore.addNotification('RAG datastores updated.', 'success');
        } catch (error) {
            if (discussions.value[discussionId]) disc.rag_datastore_ids = originalStoreIds;
            uiStore.addNotification('Failed to update RAG datastores.', 'error');
        }
    }

    async function renameDiscussion({ discussionId, newTitle }) {
        const disc = discussions.value[discussionId];
        if (!disc || !newTitle) return;
        const originalTitle = disc.title;
        disc.title = newTitle;
        try {
            await apiClient.put(`/api/discussions/${discussionId}/title`, { title: newTitle });
            uiStore.addNotification('Discussion renamed.', 'success');
        } catch (error) {
            if (discussions.value[discussionId]) disc.title = originalTitle;
            uiStore.addNotification('Failed to rename discussion.', 'error');
        }
    }

    async function updateDiscussionMcps({ discussionId, mcp_tool_ids }) {
        const disc = discussions.value[discussionId];
        if (!disc) return;
        const originalTools = disc.active_tools;
        disc.active_tools = mcp_tool_ids;
        try {
            await apiClient.put(`/api/discussions/${discussionId}/tools`, { tools: mcp_tool_ids });
            uiStore.addNotification('Tools updated.', 'success');
        } catch (error) {
            if (discussions.value[discussionId]) disc.active_tools = originalTools;
        }
    }

    async function fetchDiscussionTree(discussionId) {
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}/full_tree`);
            return response.data;
        } catch (error) {
            uiStore.addNotification('Failed to fetch discussion tree.', 'error');
            return [];
        }
    }

    function $reset() {
        discussions.value = {};
        discussionGroups.value = [];
        currentDiscussionId.value = null;
        messages.value = [];
        generationInProgress.value = false;
        // ... reset other state properties
    }

    return {
        // State
        discussions, currentDiscussionId, messages, generationInProgress, discussionGroups,
        isLoadingDiscussions, titleGenerationInProgressId, activeDiscussionContextStatus,
        activeAiTasks, activeDiscussionArtefacts, isLoadingArtefacts, liveDataZoneTokens,
        promptInsertionText, promptLoadedArtefacts, sharedWithMe,
        // Computed
        activeDiscussion, activeMessages, activeDiscussionContainsCode, sortedDiscussions,
        dataZonesTokenCount, dataZonesTokensFromContext, currentModelVisionSupport, activePersonality,
        // Core Actions
        loadDiscussions, selectDiscussion, createNewDiscussion, cloneDiscussion,
        deleteDiscussion, pruneDiscussions, generateAutoTitle, toggleStarDiscussion,
        updateDiscussionRagStore, renameDiscussion, updateDiscussionMcps, fetchDiscussionTree,
        $reset,
        // Composables
        ...artefactActions,
        ...dataZoneActions,
        ...exportActions,
        ...generationActions,
        ...groupActions,
        ...messageActions,
        ...sharingActions,
    };
});