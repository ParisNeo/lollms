<script setup>
import { computed } from 'vue';
import { useSocialStore } from '../../stores/social';
import UserAvatar from '../ui/Cards/UserAvatar.vue';

const socialStore = useSocialStore();

const pendingRequests = computed(() => socialStore.pendingFriendRequests);
const isLoading = computed(() => socialStore.isLoadingRequests);

function handleAccept(friendshipId) {
    socialStore.acceptFriendRequest(friendshipId);
}

function handleDecline(friendshipId) {
    socialStore.rejectFriendRequest(friendshipId);
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <div v-if="isLoading" class="text-center py-6 text-gray-500">
      Loading requests...
    </div>
    <div v-else-if="pendingRequests.length === 0" class="text-center py-10 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
      <p class="text-gray-500 dark:text-gray-400">No pending friend requests.</p>
    </div>
    <ul v-else class="space-y-3">
      <li v-for="request in pendingRequests" :key="request.friendship_id" class="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-sm flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <UserAvatar :username="request.requesting_username" size-class="h-10 w-10" />
          <div>
            <span class="font-medium text-gray-800 dark:text-gray-100">{{ request.requesting_username }}</span>
            <p class="text-xs text-gray-500">Sent on {{ new Date(request.requested_at).toLocaleDateString() }}</p>
          </div>
        </div>
        <div class="flex items-center space-x-2">
          <button @click="handleDecline(request.friendship_id)" class="btn btn-secondary btn-sm">Decline</button>
          <button @click="handleAccept(request.friendship_id)" class="btn btn-primary btn-sm">Accept</button>
        </div>
      </li>
    </ul>
  </div>
</template>