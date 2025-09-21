// frontend/webui/src/stores/composables/useDiscussionGroups.js
import apiClient from '../../services/api';

export function useDiscussionGroups(state, stores, getActions) {
    const { discussionGroups, discussions } = state;
    const { uiStore } = stores;

    async function fetchDiscussionGroups() {
        try {
            const response = await apiClient.get('/api/discussion-groups');
            discussionGroups.value = response.data;
        } catch (error) {
            console.error("Failed to fetch discussion groups:", error);
            discussionGroups.value = [];
        }
    }

    async function createGroup(name, parentId = null) {
        const response = await apiClient.post('/api/discussion-groups', { name, parent_id: parentId });
        discussionGroups.value.push(response.data);
        uiStore.addNotification(`Group "${name}" created.`, 'success');
    }

    async function updateGroup(id, name, parentId = null) {
        const response = await apiClient.put(`/api/discussion-groups/${id}`, { name, parent_id: parentId });
        const index = discussionGroups.value.findIndex(g => g.id === id);
        if (index !== -1) {
            discussionGroups.value[index] = response.data;
        }
        uiStore.addNotification(`Group renamed to "${name}".`, 'success');
    }

    async function deleteGroup(id) {
        await apiClient.delete(`/api/discussion-groups/${id}`);
        discussionGroups.value = discussionGroups.value.filter(g => g.id !== id);
        Object.values(discussions.value).forEach(d => {
            if (d.group_id === id) {
                d.group_id = null;
            }
        });
        uiStore.addNotification('Group deleted.', 'success');
    }
    
    async function moveDiscussionToGroup(discussionId, groupId) {
        const discussion = discussions.value[discussionId];
        if (!discussion) return;
        const originalGroupId = discussion.group_id;
        discussion.group_id = groupId;
        try {
            await apiClient.put(`/api/discussions/${discussionId}/group`, { group_id: groupId });
        } catch (error) {
            discussion.group_id = originalGroupId; // Revert on failure
            uiStore.addNotification('Failed to move discussion.', 'error');
        }
    }

    return {
        fetchDiscussionGroups,
        createGroup,
        updateGroup,
        deleteGroup,
        moveDiscussionToGroup
    };
}