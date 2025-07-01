<script setup>
import { ref, computed } from 'vue';
import { useSocialStore } from '../stores/social';
import ConversationList from '../components/dm/ConversationList.vue';
import DmWindow from '../components/dm/DmWindow.vue';

const socialStore = useSocialStore();
const selectedUserId = ref(null);

const selectedConversation = computed(() => {
  if (!selectedUserId.value) return null;
  return socialStore.activeConversations[selectedUserId.value];
});
</script>

<template>
  <div class="flex h-screen w-screen">
    <!-- Conversation List Sidebar -->
    <div class="w-1/4 max-w-xs h-full flex-shrink-0">
      <ConversationList v-model="selectedUserId" />
    </div>

    <!-- Main Chat Window -->
    <div class="flex-grow h-full">
      <DmWindow v-if="selectedConversation" :conversation="selectedConversation" />
      <div v-else class="h-full flex items-center justify-center bg-gray-100 dark:bg-gray-900">
        <div class="text-center">
          <h2 class="text-xl font-semibold text-gray-600 dark:text-gray-300">Select a conversation</h2>
          <p class="mt-1 text-gray-500">Choose a user from the list on the left to view messages.</p>
        </div>
      </div>
    </div>
  </div>
</template>