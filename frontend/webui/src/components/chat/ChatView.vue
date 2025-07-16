<script>
import { mapState } from 'pinia';
import { useDiscussionsStore } from '../../stores/discussions';

import ChatHeader from './ChatHeader.vue';
import MessageArea from './MessageArea.vue';
import ChatInput from './ChatInput.vue';
import logoUrl from '../../assets/logo.png';

export default {
  name: 'ChatView',
  components: {
    ChatHeader,
    MessageArea,
    ChatInput,
  },
  data() {
      return {
          logoUrl,
      }
  },
  computed: {
    ...mapState(useDiscussionsStore, ['activeDiscussion']),
  },
};
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-gray-50 dark:bg-gray-900 overflow-hidden">
    <!-- Chat Header -->
    <ChatHeader v-if="activeDiscussion" :discussion="activeDiscussion" />

    <!-- Message Area -->
    <!-- 
      FIX: Added 'pb-40' to ensure the last message is not obscured by the floating chat input.
    -->
    <MessageArea v-if="activeDiscussion" class="flex-1 overflow-y-auto min-w-0 pb-40" />
    
    <!-- Empty State Placeholder -->
    <div v-else class="flex-1 flex items-center justify-center text-center p-4">
      <div class="max-w-md">
        <img :src="logoUrl" alt="LoLLMs Logo" class="w-24 h-24 mx-auto mb-4 opacity-50" />
        <h3 class="text-xl font-semibold text-gray-700 dark:text-gray-300">Welcome to LoLLMs Chat</h3>
        <p class="text-gray-500 dark:text-gray-400 mt-2">
          Start a new conversation using the chat box, or select an existing one to begin.
        </p>
      </div>
    </div>

    <!-- Chat Input is now always rendered and manages its own floating/positioning state -->
    <ChatInput />
  </div>
</template>