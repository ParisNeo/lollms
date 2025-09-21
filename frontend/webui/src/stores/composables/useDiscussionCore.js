// frontend/webui/src/stores/composables/useDiscussionCore.js
import apiClient from '../../services/api';
import { processMessages } from './discussionProcessor';

export function useDiscussionCore(state, stores, getActions) {
    const { discussions, currentDiscussionId, messages, isLoadingDiscussions, isLoadingMessages, activeDiscussionParticipants } = state;
    const { uiStore } = stores;

    async function fetchParticipants(discussionId) {
        if (!discussionId) {
            activeDiscussionParticipants.value = {};
            return;
        }
        try {
            const response = await apiClient.get(`/api/discussions/${discussionId}/participants`);
            const participantsMap = {};
            for (const user of response.data) {
                participantsMap[user.username] = user;
            }
            activeDiscussionParticipants.value = participantsMap;
        } catch (error) {
            console.error("Failed to fetch discussion participants:", error);
            activeDiscussionParticipants.value = {};
        }
    }

    async function loadDiscussions() {
        isLoadingDiscussions.value = true;
        try {
            const response = await apiClient.get('/api/discussions');
            const newDiscussions = {};
            for (const disc of response.data) {
                newDiscussions[disc.id] = disc;
            }
            discussions.value = newDiscussions;
        } catch (error) {
            console.error("Failed to load discussions:", error);
            discussions.value = {};
        } finally {
            isLoadingDiscussions.value = false;
        }
    }

    async function selectDiscussion(discussionId, branchId = null, forceReload = false) {
        if (!forceReload && currentDiscussionId.value === discussionId) {
            return;
        }

        currentDiscussionId.value = discussionId;
        
        if (discussionId) {
            isLoadingMessages.value = true;
            messages.value = [];
            
            await fetchParticipants(discussionId);

            try {
                const response = await apiClient.get(`/api/discussions/${discussionId}`, { params: { branch_id: branchId } });
                messages.value = processMessages(response.data);
                state.emit('discussion:refreshed');
                await getActions().fetchContextStatus(discussionId);
                await getActions().fetchArtefacts(discussionId);
            } catch (error) {
                uiStore.addNotification('Could not load the selected discussion.', 'error');
                messages.value = [];
                currentDiscussionId.value = null;
            } finally {
                isLoadingMessages.value = false;
            }
        } else {
            messages.value = [];
            activeDiscussionParticipants.value = {};
        }
    }

    async function createNewDiscussion(groupId = null) {
        try {
            const response = await apiClient.post('/api/discussions', { group_id: groupId });
            const newDiscussion = response.data;
            discussions.value[newDiscussion.id] = newDiscussion;
            await selectDiscussion(newDiscussion.id);
            if (uiStore.mainView !== 'chat') {
                uiStore.setMainView('chat');
            }
        } catch (error) {
            console.error("Failed to create new discussion:", error);
            uiStore.addNotification('Could not create a new discussion.', 'error');
        }
    }

    async function deleteDiscussion(discussionId) {
        const confirmed = await uiStore.showConfirmation({
            title: 'Delete Discussion',
            message: 'Are you sure you want to permanently delete this discussion and all its messages?',
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
            uiStore.addNotification('Discussion deleted successfully.', 'success');
        } catch (error) {
            console.error("Failed to delete discussion:", error);
        }
    }

    async function cloneDiscussion(discussionId) {
        uiStore.addNotification('Cloning discussion...', 'info');
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/clone`);
            const cloned = response.data;
            discussions.value[cloned.id] = cloned;
            await selectDiscussion(cloned.id);
            uiStore.addNotification('Discussion cloned successfully.', 'success');
        } catch(e) {
            // Error handled by global interceptor
        }
    }

    async function generateAutoTitle(discussionId) {
        state.titleGenerationInProgressId.value = discussionId;
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/auto-title`);
            const updatedDiscussion = response.data;
            if (discussions.value[discussionId]) {
                discussions.value[discussionId].title = updatedDiscussion.title;
            }
        } catch (error) {
            console.error("Failed to generate title:", error);
            uiStore.addNotification('Could not generate a title.', 'error');
        } finally {
            state.titleGenerationInProgressId.value = null;
        }
    }

    async function toggleStarDiscussion(discussionId) {
        const discussion = discussions.value[discussionId];
        if (!discussion) return;
        const isCurrentlyStarred = discussion.is_starred;
        discussion.is_starred = !isCurrentlyStarred; // Optimistic update
        try {
            if (isCurrentlyStarred) {
                await apiClient.delete(`/api/discussions/${discussionId}/star`);
            } else {
                await apiClient.post(`/api/discussions/${discussionId}/star`);
            }
        } catch (error) {
            discussion.is_starred = isCurrentlyStarred; // Revert on failure
            console.error("Failed to toggle star:", error);
        }
    }

    async function renameDiscussion({ discussionId, newTitle }) {
        if (!discussions.value[discussionId]) return;
        const originalTitle = discussions.value[discussionId].title;
        discussions.value[discussionId].title = newTitle; // Optimistic update
        try {
            await apiClient.put(`/api/discussions/${discussionId}/title`, { title: newTitle });
            uiStore.addNotification('Discussion renamed.', 'success');
        } catch (error) {
            discussions.value[discussionId].title = originalTitle; // Revert
        }
    }

    return {
        loadDiscussions,
        selectDiscussion,
        createNewDiscussion,
        deleteDiscussion,
        cloneDiscussion,
        generateAutoTitle,
        toggleStarDiscussion,
        renameDiscussion,
        fetchParticipants
    };
}