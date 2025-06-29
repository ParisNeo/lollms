<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useAuthStore } from '../../stores/auth';
import UserAvatar from '../ui/UserAvatar.vue';

const props = defineProps({
  conversation: {
    type: Object,
    required: true
  }
});

const socialStore = useSocialStore();
const authStore = useAuthStore();
const messageContent = ref('');
const messagesContainer = ref(null);
const isMinimized = ref(false);

const partner = computed(() => props.conversation.partner);
const messages = computed(() => props.conversation.messages);
const isLoading = computed(() => props.conversation.isLoading);

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
}

watch(messages, () => {
  scrollToBottom();
}, { deep: true });

onMounted(() => {
  scrollToBottom();
});

function handleSendMessage() {
    if (!messageContent.value.trim()) return;
    socialStore.sendDirectMessage({
        receiverUserId: partner.value.id,
        content: messageContent.value,
    });
    messageContent.value = '';
}

function closeWindow() {
    socialStore.closeConversation(partner.value.id);
}

function toggleMinimize() {
    isMinimized.value = !isMinimized.value;
}

function formatTimestamp(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}
</script>

<template>
  <div class="dm-window" :class="{ 'is-minimized': isMinimized }">
    <!-- Header -->
    <div class="dm-header" @click="toggleMinimize">
      <div class="flex items-center space-x-2">
        <UserAvatar :username="partner.username" :icon="partner.icon" size-class="h-7 w-7" />
        <span class="font-semibold">{{ partner.username }}</span>
      </div>
      <div class="flex items-center space-x-2">
        <button @click.stop="toggleMinimize" class="dm-header-btn">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5 10a1 1 0 011-1h8a1 1 0 110 2H6a1 1 0 01-1-1z" clip-rule="evenodd" /></svg>
        </button>
        <button @click.stop="closeWindow" class="dm-header-btn hover:bg-red-500">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" /></svg>
        </button>
      </div>
    </div>

    <!-- Body -->
    <div v-show="!isMinimized" class="dm-body">
      <!-- Message Area -->
      <div ref="messagesContainer" class="flex-1 p-3 space-y-3 overflow-y-auto">
        <div v-if="isLoading" class="text-center text-sm text-gray-500">Loading messages...</div>
        <div v-else-if="messages.length === 0" class="text-center text-sm text-gray-500">Start the conversation!</div>
        
        <div v-for="message in messages" :key="message.id" class="flex" :class="message.sender_id === authStore.user.id ? 'justify-end' : 'justify-start'">
          <div class="max-w-xs lg:max-w-md px-3 py-2 rounded-lg" :class="message.sender_id === authStore.user.id ? 'bg-blue-500 text-white' : 'bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200'">
            <p class="text-sm">{{ message.content }}</p>
            <div class="text-xs mt-1" :class="message.sender_id === authStore.user.id ? 'text-blue-200 text-right' : 'text-gray-500 dark:text-gray-400 text-left'">
              <span v-if="message.isTemporary">Sending...</span>
              <span v-else-if="message.error" class="text-red-400">Failed to send</span>
              <span v-else>{{ formatTimestamp(message.sent_at) }}</span>
            </div>
          </div>
        </div>
      </div>
      <!-- Input Area -->
      <div class="p-2 border-t border-gray-200 dark:border-gray-600">
        <textarea
            v-model="messageContent"
            @keydown.enter.exact.prevent="handleSendMessage"
            rows="1"
            placeholder="Type a message..."
            class="w-full bg-transparent border-none focus:ring-0 resize-none text-sm p-1"
        ></textarea>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dm-window {
    @apply fixed bottom-0 right-24 flex flex-col w-80 h-96 bg-white dark:bg-gray-800 rounded-t-lg shadow-2xl border border-b-0 border-gray-300 dark:border-gray-700;
    transition: transform 0.3s ease-in-out;
}
.dm-window.is-minimized {
    transform: translateY(calc(100% - 48px)); /* 48px is header height */
}
.dm-header {
    @apply flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 rounded-t-lg cursor-pointer h-12 flex-shrink-0;
}
.dm-header-btn {
    @apply p-1 rounded-full text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700;
}
.dm-body {
    @apply flex-1 flex flex-col min-h-0; /* Crucial for scrolling */
}
</style>