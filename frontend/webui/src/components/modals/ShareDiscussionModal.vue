<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';
import UserAvatar from '../ui/UserAvatar.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import { storeToRefs } from 'pinia';
import MultiSelectMenu from '../ui/MultiSelectMenu.vue'; // Import MultiSelectMenu

const socialStore = useSocialStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const { friends, isLoadingFriends } = storeToRefs(socialStore);

const modalData = computed(() => uiStore.modalProps.shareDiscussion);
const discussionId = computed(() => modalData.value?.discussionId);
const discussionTitle = computed(() => modalData.value?.title);
 
const sharedWith = ref([]);
const isLoadingSharedWith = ref(false);
const friendsToAdd = ref([]);
const newPermissionLevel = ref('view');
const isSending = ref(false);

const availableFriends = computed(() => {
    const sharedUserIds = new Set(sharedWith.value.map(s => s.shared_with_user_id));
    return (friends.value || []).filter(f => !sharedUserIds.has(f.id)).map(f => ({id: f.id, name: f.username, icon: f.icon}));
});

async function refreshFriends() {
    await socialStore.fetchFriends();
}

async function fetchSharedWithList() {
    if (!discussionId.value) return;
    isLoadingSharedWith.value = true;
    try {
        // This is a placeholder for a new store action
        const response = await (await import('../../services/api')).default.get(`/api/discussions/${discussionId.value}/shared-with`);
        sharedWith.value = response.data;
    } catch (e) {
        uiStore.addNotification("Could not load sharing information.", "error");
        sharedWith.value = [];
    } finally {
        isLoadingSharedWith.value = false;
    }
}

watch(discussionId, (newId) => {
    if (newId) {
        fetchSharedWithList();
        refreshFriends();
    } else {
        sharedWith.value = [];
    }
}, { immediate: true });

onMounted(() => {
    if (discussionId.value) {
        fetchSharedWithList();
        refreshFriends();
    }
});

async function handleAddShares() {
    if (friendsToAdd.value.length === 0) {
        uiStore.addNotification("Please select at least one friend to add.", "warning");
        return;
    }
    isSending.value = true;
    try {
        for (const friendId of friendsToAdd.value) {
            await discussionsStore.shareDiscussion({
                discussionId: discussionId.value,
                targetUserId: friendId,
                permissionLevel: newPermissionLevel.value
            });
        }
        uiStore.addNotification(`Shared with ${friendsToAdd.value.length} friend(s).`, "success");
        friendsToAdd.value = [];
        await fetchSharedWithList();
    } finally {
        isSending.value = false;
    }
}

async function handleUpdatePermission(share) {
    await discussionsStore.shareDiscussion({
        discussionId: discussionId.value,
        targetUserId: share.shared_with_user_id,
        permissionLevel: share.permission_level
    });
    await fetchSharedWithList();
}

async function handleRevoke(share) {
    await discussionsStore.revokeShare({
        discussionId: discussionId.value,
        shareId: share.share_id
    });
    await fetchSharedWithList(); // Refresh list after revoking
}
</script>

<template>
  <GenericModal modalName="shareDiscussion" title="Share Discussion">
    <template #body>
      <div class="space-y-4">
        <div class="text-sm">
          <p class="text-gray-600 dark:text-gray-400">You are sharing:</p>
          <p class="font-semibold text-gray-800 dark:text-gray-200 truncate" :title="discussionTitle">{{ discussionTitle || 'Discussion' }}</p>
        </div>
        
        <!-- Existing Shares -->
        <div class="space-y-2">
            <h3 class="font-medium text-gray-700 dark:text-gray-300">Already Shared With</h3>
            <div v-if="isLoadingSharedWith" class="text-center py-4 text-sm text-gray-500">Loading...</div>
            <div v-else-if="sharedWith.length === 0" class="text-center py-4 border rounded-lg bg-gray-50 dark:bg-gray-700/50 text-sm text-gray-500">Not shared with anyone yet.</div>
            <div v-else class="max-h-48 overflow-y-auto space-y-2 pr-2">
                <div v-for="share in sharedWith" :key="share.share_id" class="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <div class="flex items-center space-x-3">
                        <UserAvatar :icon="share.shared_with_user_icon" :username="share.shared_with_username" size-class="h-8 w-8" />
                        <span class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ share.shared_with_username }}</span>
                    </div>
                    <div class="flex items-center space-x-2">
                        <select v-model="share.permission_level" @change="handleUpdatePermission(share)" class="input-field !py-1 !text-xs w-28">
                            <option value="view">Can View</option>
                            <option value="interact">Can Interact</option>
                        </select>
                        <button @click="handleRevoke(share)" class="btn btn-danger btn-sm !p-1.5" title="Revoke Access">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" /></svg>
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Add New Shares -->
        <div class="space-y-2 border-t dark:border-gray-600 pt-4">
            <div class="flex justify-between items-center">
                <label class="font-medium text-gray-700 dark:text-gray-300">Share with more friends:</label>
                <button @click="refreshFriends" class="btn-icon" title="Refresh friends list" :disabled="isLoadingFriends">
                    <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingFriends}" />
                </button>
            </div>
            
            <MultiSelectMenu v-model="friendsToAdd" :items="availableFriends" placeholder="Select friends..." :disabled="availableFriends.length === 0" />

            <div class="flex items-center gap-4">
                <label for="permission-level" class="font-medium text-gray-700 dark:text-gray-300 flex-shrink-0">Permission:</label>
                <select id="permission-level" v-model="newPermissionLevel" class="input-field w-full">
                    <option value="view">Can View</option>
                    <option value="interact">Can View & Interact</option>
                </select>
            </div>
        </div>

      </div>
    </template>
    
    <template #footer>
      <button @click="uiStore.closeModal()" type="button" class="btn btn-secondary">
         Cancel
      </button>
      <button 
        @click="handleAddShares" 
        :disabled="friendsToAdd.length === 0 || isSending"
        class="btn btn-primary"
      >
        {{ isSending ? 'Sharing...' : `Share with ${friendsToAdd.length || ''}` }}
      </button>
    </template>
  </GenericModal>
</template>