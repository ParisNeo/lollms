import apiClient from '../../services/api';

export function useDiscussionGroups(state, stores, getActions) {
    const { discussionGroups, discussions } = state;
    const { uiStore } = stores;

    function isDescendant(childId, parentId) {
        const groupsMap = new Map(discussionGroups.value.map(g => [g.id, g]));
        let currentId = childId;
        while (currentId) {
            const currentGroup = groupsMap.get(currentId);
            if (!currentGroup) return false;
            if (currentGroup.parent_id === parentId) {
                return true;
            }
            currentId = currentGroup.parent_id;
        }
        return false;
    }

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
        const originalGroup = discussionGroups.value.find(g => g.id === id);
        if (!originalGroup) {
            uiStore.addNotification('Group not found.', 'error');
            return;
        }

        const groupName = name !== undefined ? name : originalGroup.name;

        if (parentId === id || (parentId && isDescendant(parentId, id))) {
            uiStore.addNotification('Cannot move a group into itself or one of its descendants.', 'error');
            return;
        }
        
        try {
            const response = await apiClient.put(`/api/discussion-groups/${id}`, { name: groupName, parent_id: parentId });
            const index = discussionGroups.value.findIndex(g => g.id === id);
            if (index !== -1) {
                discussionGroups.value[index] = response.data;
            }
            uiStore.addNotification(`Group updated successfully.`, 'success');
        } catch(e) {
            // Error handled by global handler, which is sufficient
        }
    }

    async function deleteGroup(id) {
        await apiClient.delete(`/api/discussion-groups/${id}`);
        // Optimistic UI updates
        const groupToDelete = discussionGroups.value.find(g => g.id === id);
        if (groupToDelete) {
            // Re-parent children
            discussionGroups.value.forEach(group => {
                if (group.parent_id === id) {
                    group.parent_id = groupToDelete.parent_id;
                }
            });
            // Remove group
            discussionGroups.value = discussionGroups.value.filter(g => g.id !== id);
        }

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
        
        // Prevent unnecessary API calls if already in the target group
        if (discussion.group_id === groupId || (!discussion.group_id && groupId === null)) {
            return;
        }
        
        const originalGroupId = discussion.group_id;
        discussion.group_id = groupId; // Optimistic update
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