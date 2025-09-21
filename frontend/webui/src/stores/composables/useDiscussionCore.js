// frontend/webui/src/stores/composables/useDiscussionCore.js
import apiClient from '../../services/api';
import { processMessages } from './discussionProcessor';

export function useDiscussionCore(state, stores, getActions) {
    const { 
        discussions, 
        currentDiscussionId, 
        messages, 
        isLoadingMessages, 
        isLoadingDiscussions, 
        titleGenerationInProgressId,
        activeDiscussionArtefacts
    } = state;

    async function loadDiscussions() {
        isLoadingDiscussions.value = true;
        try {
            const response = await apiClient.get('/api/discussions');
            const newDiscussions = {};
            if (Array.isArray(response.data)) {
                response.data.forEach(d => {
                    newDiscussions[d.id] = { ...d, discussion_data_zone: '', personality_data_zone: '', memory: '' };
                });
            }
            discussions.value = newDiscussions;
        } catch (error) {
            console.error("Failed to load discussions:", error);
        } finally {
            isLoadingDiscussions.value = false;
        }
    }

    async function selectDiscussion(discussionId, branchId = null, force = false) {
        if (!discussionId) {
            currentDiscussionId.value = null;
            messages.value = [];
            activeDiscussionArtefacts.value = [];
            return;
        }
        
        if (currentDiscussionId.value === discussionId && !branchId && !force) return;

        currentDiscussionId.value = discussionId;
        messages.value = [];
        isLoadingMessages.value = true;
        
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}`, { params: { branch_id: branchId } });
            messages.value = processMessages(response.data);
            
            const actions = getActions();
            await Promise.all([
                actions.fetchContextStatus(discussionId),
                actions.fetchArtefacts(discussionId),
                actions.fetchDataZones(discussionId)
            ]);
            state.emit('discussion:refreshed');
        } catch (error) {
            currentDiscussionId.value = null;
            stores.uiStore.addNotification('Could not load discussion.', 'error');
        } finally {
            isLoadingMessages.value = false;
        }
    }

    async function createNewDiscussion(groupId = null) {
        try {
            const response = await apiClient.post('/api/discussions', { group_id: groupId });
            const newDiscussion = response.data;
            discussions.value[newDiscussion.id] = { ...newDiscussion, discussion_data_zone: '', personality_data_zone: '', memory:'' };
            await selectDiscussion(newDiscussion.id);
            return newDiscussion;
        } catch (error) {
            stores.uiStore.addNotification('Failed to create new discussion.', 'error');
        }
    }

    async function deleteDiscussion(discussionId) {
        const discussionToDelete = discussions.value[discussionId];
        if (!discussionToDelete) return;

        const confirmed = await stores.uiStore.showConfirmation({
            title: 'Delete Discussion',
            message: `Are you sure you want to delete "${discussionToDelete.title}"?`,
            confirmText: 'Delete'
        });

        if (!confirmed) return;

        try {
            await apiClient.delete(`/api/discussions/${discussionId}`);
            delete discussions.value[discussionId];
            if (currentDiscussionId.value === discussionId) {
                currentDiscussionId.value = null;
                messages.value = [];
            }
            stores.uiStore.addNotification('Discussion deleted.', 'success');
        } catch (error) {
            stores.uiStore.addNotification('Failed to delete discussion.', 'error');
        }
    }

    async function toggleStarDiscussion(discussionId) {
        const discussion = discussions.value[discussionId];
        if (!discussion) return;
        const isCurrentlyStarred = discussion.is_starred;
        discussion.is_starred = !isCurrentlyStarred;
        try {
            const endpoint = `/api/discussions/${discussionId}/star`;
            if (isCurrentlyStarred) {
                await apiClient.delete(endpoint);
            } else {
                await apiClient.post(endpoint);
            }
        } catch (error) {
            discussion.is_starred = isCurrentlyStarred; // Revert on failure
            stores.uiStore.addNotification('Failed to update star status.', 'error');
        }
    }
    
    async function generateAutoTitle(discussionId) {
        if (titleGenerationInProgressId.value) return;
        titleGenerationInProgressId.value = discussionId;
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/auto-title`);
            if (discussions.value[discussionId]) {
                discussions.value[discussionId].title = response.data.title;
            }
        } catch(error) {
            stores.uiStore.addNotification('Failed to generate title.', 'error');
        } finally {
            titleGenerationInProgressId.value = null;
        }
    }

    async function pruneDiscussions() {
        const confirmed = await stores.uiStore.showConfirmation({
            title: 'Prune Discussions?',
            message: 'This will delete all discussions with 1 or fewer messages. This cannot be undone.',
            confirmText: 'Prune'
        });
        if (!confirmed) return;

        try {
            const response = await apiClient.post('/api/discussions/prune');
            stores.tasksStore.addTask(response.data);
            stores.uiStore.addNotification('Pruning task started.', 'info');
        } catch (error) {
            // Error is handled by global interceptor
        }
    }

    async function cloneDiscussion(discussionId) {
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/clone`);
            const newDiscussion = response.data;
            discussions.value[newDiscussion.id] = newDiscussion;
            await selectDiscussion(newDiscussion.id);
            stores.uiStore.addNotification(`Discussion cloned successfully.`, 'success');
        } catch (error) {
            stores.uiStore.addNotification(`Failed to clone discussion.`, 'error');
        }
    }

    return {
        loadDiscussions,
        selectDiscussion,
        createNewDiscussion,
        deleteDiscussion,
        toggleStarDiscussion,
        generateAutoTitle,
        pruneDiscussions,
        cloneDiscussion
    };
}