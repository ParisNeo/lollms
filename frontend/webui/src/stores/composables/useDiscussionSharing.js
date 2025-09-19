// frontend/webui/src/stores/composables/useDiscussionSharing.js
import apiClient from '../../services/api';

export function useDiscussionSharing(state, stores) {
    const { sharedWithMe, currentDiscussionId, discussions } = state;
    const { uiStore } = stores;

    async function fetchSharedWithMe() {
        try {
            const response = await apiClient.get('/api/discussions/shared');
            sharedWithMe.value = response.data;
        } catch (error) {
            console.error("Failed to fetch shared discussions:", error);
            sharedWithMe.value = [];
        }
    }

    async function shareDiscussion({ discussionId, targetUserId, permissionLevel }) {
        try {
            const response = await apiClient.post(`/api/discussions/${discussionId}/share`, {
                target_user_id: targetUserId,
                permission_level: permissionLevel,
            });
            uiStore.addNotification(response.data.message || `Discussion shared successfully!`, 'success');
            uiStore.closeModal();
        } catch (error) {
            console.error("Failed to share discussion:", error);
        }
    }

    async function unsubscribeFromSharedDiscussion(shareId) {
        const confirmed = await uiStore.showConfirmation({
            title: 'Unsubscribe from Discussion',
            message: 'Are you sure you want to remove this shared discussion from your list?',
            confirmText: 'Unsubscribe'
        });
        if (!confirmed) return;

        try {
            await apiClient.delete(`/api/discussions/unsubscribe/${shareId}`);
            sharedWithMe.value = sharedWithMe.value.filter(d => d.share_id !== shareId);
            if (currentDiscussionId.value && !discussions.value[currentDiscussionId.value] && !sharedWithMe.value.some(d => d.id === currentDiscussionId.value)) {
                currentDiscussionId.value = null;
                state.messages.value = [];
            }
            uiStore.addNotification('Successfully unsubscribed from the discussion.', 'success');
        } catch (error) {
            console.error("Failed to unsubscribe:", error);
        }
    }
    
    async function sendDiscussion({ discussionId, targetUsername }) {
        try {
            const response = await apiClient.post(`/api/dm/send-discussion`, { discussion_id: discussionId, target_username: targetUsername });
            uiStore.addNotification(response.data.message || `Discussion sent to ${targetUsername}!`, 'success');
            uiStore.closeModal();
        } catch (error) {
            console.error("Failed to send discussion:", error);
        }
    }
    
    return {
        fetchSharedWithMe,
        shareDiscussion,
        unsubscribeFromSharedDiscussion,
        sendDiscussion
    };
}