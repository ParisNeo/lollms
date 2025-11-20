<script setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useSocialStore } from '../../stores/social';
import { useUiStore } from '../../stores/ui';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import IconMessage from '../../assets/icons/IconMessage.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

const socialStore = useSocialStore();
const uiStore = useUiStore();
const router = useRouter();

const friends = computed(() => socialStore.friends);
const isLoading = computed(() => socialStore.isLoadingFriends);

async function handleRemoveFriend(friend) {
    const confirmed = await uiStore.showConfirmation({
        title: `Remove Friend`,
        message: `Are you sure you want to remove ${friend.username} from your friends list?`,
        confirmText: 'Remove'
    });
    if (confirmed) {
        socialStore.removeFriend(friend.id);
    }
}

async function handleMessageFriend(friend) {
    socialStore.openConversation({
        id: friend.id,
        username: friend.username,
        icon: friend.icon
    });
    // If the sidebar is handling chat now, we might not want to navigate.
    // But user request history implied navigation, so keeping it optionally or removing if sidebar is preferred.
    // Since ChatSidebar is global, opening conversation triggers it.
    // We can stay on the current page.
}

function getStatusColor(status) {
    if (status === 'connected') return 'bg-green-500';
    if (status === 'absent') return 'bg-yellow-500';
    return 'bg-gray-400';
}

function getStatusText(status) {
    if (status === 'connected') return 'Online';
    if (status === 'absent') return 'Absent';
    return 'Offline';
}
</script>

<template>
  <div class="max-w-4xl mx-auto">
    <div v-if="isLoading" class="text-center py-6 text-gray-500 dark:text-gray-400">
      Loading friends...
    </div>
    <div v-else-if="friends.length === 0" class="text-center py-10 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
      <p class="text-gray-500 dark:text-gray-400">Your friends list is empty.</p>
      <p class="text-sm text-gray-400 dark:text-gray-500 mt-1">Use the 'Add Friend' tab to find people.</p>
    </div>
    <ul v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <li v-for="friend in friends" :key="friend.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex flex-col items-center text-center">
        <router-link :to="`/profile/${friend.username}`" class="relative">
            <UserAvatar :icon="friend.icon" :username="friend.username" size-class="h-20 w-20" />
            <div 
                class="absolute bottom-1 right-1 w-5 h-5 border-4 border-white dark:border-gray-800 rounded-full"
                :class="getStatusColor(friend.status)"
                :title="getStatusText(friend.status)"
            ></div>
        </router-link>
        <router-link :to="`/profile/${friend.username}`" class="mt-3 font-bold text-gray-900 dark:text-gray-100 hover:underline truncate w-full">
            {{ friend.username }}
        </router-link>
        <p class="text-xs text-gray-500 mb-3">{{ getStatusText(friend.status) }}</p>
        
        <div class="mt-auto flex items-center space-x-2 w-full">
            <button @click="handleMessageFriend(friend)" class="btn btn-secondary btn-sm flex-1 flex items-center justify-center space-x-1.5">
                <IconMessage class="w-4 h-4" />
                <span>Message</span>
            </button>
             <button @click="handleRemoveFriend(friend)" class="btn-icon-danger p-2" title="Remove Friend">
                <IconTrash class="w-4 h-4" />
            </button>
        </div>
      </li>
    </ul>
  </div>
</template>
