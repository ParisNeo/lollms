<script setup>
import { ref, computed, onMounted } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';
import UserAvatar from '../ui/UserAvatar.vue';

const socialStore = useSocialStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const modalData = computed(() => uiStore.modalProps);
const discussionId = computed(() => modalData.value?.discussionId);
const discussionTitle = computed(() => modalData.value?.discussionTitle);

const friends = computed(() => socialStore.friends);
const selectedFriendUsername = ref(null);
const isLoadingFriends = ref(false);
const isSending = ref(false);

onMounted(async () => {
    isLoadingFriends.value = true;
    await socialStore.fetchFriends();
    isLoadingFriends.value = false;
});

async function handleSend() {
  if (!selectedFriendUsername.value || !discussionId.value) {
    uiStore.addNotification("Please select a friend to send the discussion to.", "error");
    return;
  }
  
  isSending.value = true;
  await discussionsStore.sendDiscussion({
    discussionId: discussionId.value,
    targetUsername: selectedFriendUsername.value
  });
  isSending.value = false;
}
</script>

<template>
  <GenericModal modalName="shareDiscussion" title="Send Discussion">
    <div class="p-6 space-y-4">
      <div class="text-sm">
        <p class="text-gray-600 dark:text-gray-400">You are sending:</p>
        <p class="font-semibold text-gray-800 dark:text-gray-200 truncate">{{ discussionTitle || 'Discussion' }}</p>
      </div>
      
      <div class="space-y-2">
        <p class="font-medium text-gray-700 dark:text-gray-300">Select a friend:</p>
        
        <div v-if="isLoadingFriends" class="text-center py-4">
          <p class="text-sm text-gray-500">Loading friends...</p>
        </div>
        
        <div v-else-if="friends.length === 0" class="text-center py-4 border rounded-lg bg-gray-50 dark:bg-gray-700/50">
          <p class="text-sm text-gray-500">You don't have any friends yet.</p>
        </div>

        <div v-else class="max-h-60 overflow-y-auto border rounded-lg dark:border-gray-600 p-2 space-y-1">
          <label 
            v-for="friend in friends" 
            :key="friend.id" 
            class="flex items-center p-2 rounded-md cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            :class="{'bg-blue-100 dark:bg-blue-900/50': selectedFriendUsername === friend.username}"
          >
            <input 
              type="radio" 
              name="friend" 
              :value="friend.username"
              v-model="selectedFriendUsername"
              class="h-4 w-4 text-blue-600 border-gray-300 focus:ring-blue-500"
            >
            <UserAvatar :icon="friend.icon" :username="friend.username" size-class="h-8 w-8 ml-3" />
            <span class="ml-3 text-sm font-medium text-gray-900 dark:text-gray-100">{{ friend.username }}</span>
          </label>
        </div>
      </div>
    </div>
    
    <template #footer>
      <button @click="uiStore.closeModal()" class="btn btn-secondary">
        Cancel
      </button>
      <button 
        @click="handleSend" 
        :disabled="!selectedFriendUsername || isSending"
        class="btn btn-primary"
      >
        {{ isSending ? 'Sending...' : 'Send' }}
      </button>
    </template>
  </GenericModal>
</template>