// frontend/webui/src/stores/composables/useDiscussionSharing.js
import apiClient from '../../services/api';

export function useDiscussionSharing(state, stores, getActions) {
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
            // Notifications are handled in the modal for individual/bulk actions
        } catch (error) {
            console.error("Failed to share discussion:", error);
            throw error; // Re-throw to be handled in the component
        }
    }

    async function revokeShare({ discussionId, shareId }) {
        try {
            await apiClient.delete(`/api/discussions/${discussionId}/share/${shareId}`);
        } catch (error) {
            console.error("Failed to revoke share:", error);
            throw error; // Re-throw to be handled in the component
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
            const linkToRemove = sharedWithMe.value.find(d => d.share_id === shareId);
            const discussionIdToRemove = linkToRemove?.id;

            await apiClient.delete(`/api/discussions/unsubscribe/${shareId}`);
            
            sharedWithMe.value = sharedWithMe.value.filter(d => d.share_id !== shareId);
            
            if (discussionIdToRemove && currentDiscussionId.value === discussionIdToRemove) {
                getActions().selectDiscussion(null);
                 // If no other discussions, go to feed
                 if (Object.keys(discussions.value).length === 0 && sharedWithMe.value.length === 0) {
                    uiStore.setMainView('feed');
                }
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
        revokeShare,
        unsubscribeFromSharedDiscussion,
        sendDiscussion
    };
}