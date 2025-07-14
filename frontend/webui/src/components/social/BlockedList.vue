<script setup>
import { computed } from 'vue';
import { useSocialStore } from '../../stores/social';
import UserAvatar from '../ui/UserAvatar.vue';

const socialStore = useSocialStore();

const blockedUsers = computed(() => socialStore.blockedUsers);
const isLoading = computed(() => socialStore.isLoadingBlocked);

function handleUnblock(user) {
    socialStore.unblockUser(user.id);
}
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <div v-if="isLoading" class="text-center py-6 text-gray-500 dark:text-gray-400">
      Loading blocked list...
    </div>
    <div v-else-if="blockedUsers.length === 0" class="text-center py-10 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
      <p class="text-gray-500 dark:text-gray-400">You haven't blocked any users.</p>
    </div>
    <ul v-else class="space-y-3">
      <li v-for="user in blockedUsers" :key="user.id" class="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-sm flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <UserAvatar :icon="user.icon" :username="user.username" size-class="h-10 w-10" />
          <span class="font-medium text-gray-800 dark:text-gray-100">{{ user.username }}</span>
        </div>
        <button @click="handleUnblock(user)" class="btn btn-secondary btn-sm">Unblock</button>
      </li>
    </ul>
  </div>
</template>