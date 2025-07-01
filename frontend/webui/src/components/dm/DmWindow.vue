<script setup>
import { ref, computed, onMounted, onUpdated, nextTick } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useSocialStore } from '../../stores/social';
import UserAvatar from '../ui/UserAvatar.vue';

const props = defineProps({
  conversation: {
    type: Object,
    required: true,
  },
});

const authStore = useAuthStore();
const socialStore = useSocialStore();
const currentUser = computed(() => authStore.user);

const messageContainer = ref(null);
const newMessageContent = ref('');

// Refs to help manage scroll position during lazy loading
const scrollHeightBeforeLoad = ref(0);

const partner = computed(() => props.conversation.partner);

// Function to scroll to the bottom of the message container
async function scrollToBottom() {
  await nextTick();
  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight;
  }
}

// Handler for the scroll event on the message container
async function handleScroll(event) {
  const container = event.target;
  // If the user has scrolled to the very top, load more messages
  if (container.scrollTop === 0 && !props.conversation.isLoading && !props.conversation.fullyLoaded) {
    // Save the current scroll height before new messages are added
    scrollHeightBeforeLoad.value = container.scrollHeight;
    await socialStore.fetchMoreMessages(partner.value.id);
  }
}

// Function to handle sending a new message
function sendMessage() {
  if (newMessageContent.value.trim() === '') return;
  socialStore.sendDirectMessage({
    receiverUserId: partner.value.id,
    content: newMessageContent.value,
  });
  newMessageContent.value = '';
  // After sending, we want to ensure the view scrolls to the new message
  scrollToBottom();
}

// Scroll to the bottom when the component is first mounted
onMounted(() => {
  scrollToBottom();
});

// onUpdated is crucial for managing scroll position after new data arrives
onUpdated(() => {
  if (messageContainer.value) {
    // If we just lazy-loaded more messages (scrollHeightBeforeLoad is set)
    if (scrollHeightBeforeLoad.value > 0) {
      // Restore the scroll position to where the user was
      const newScrollTop = messageContainer.value.scrollHeight - scrollHeightBeforeLoad.value;
      messageContainer.value.scrollTop = newScrollTop;
      scrollHeightBeforeLoad.value = 0; // Reset for the next load
    }
  }
});

function formatTimestamp(dateString) {
  const date = new Date(dateString);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
</script>

<template>
  <div v-if="conversation && conversation.partner" class="flex flex-col h-full bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-lg">
    <!-- Header -->
    <header class="flex items-center p-3 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
      <UserAvatar :icon="partner.icon" :username="partner.username" size-class="h-9 w-9" />
      <div class="ml-3">
        <h3 class="font-semibold text-gray-900 dark:text-gray-100">{{ partner.username }}</h3>
      </div>
      <div class="flex-grow"></div>
      <button @click="socialStore.closeConversation(partner.id)" class="p-1 rounded-full text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
      </button>
    </header>

    <!-- Message Display Area -->
    <div ref="messageContainer" @scroll="handleScroll" class="flex-grow p-4 overflow-y-auto">
      <!-- Loading indicator for older messages -->
      <div v-if="conversation.isLoading" class="text-center py-2">
        <p class="text-sm text-gray-500">Loading older messages...</p>
      </div>
      <!-- Indicator for the start of the conversation -->
      <div v-if="conversation.fullyLoaded" class="text-center py-4">
        <p class="text-xs text-gray-400 dark:text-gray-500">This is the beginning of your conversation with {{ partner.username }}.</p>
      </div>

      <!-- Messages -->
      <div v-for="message in conversation.messages" :key="message.id" class="flex my-2" :class="message.sender_id === currentUser.id ? 'justify-end' : 'justify-start'">
        <div class="max-w-xs lg:max-w-md px-3 py-2 rounded-lg" :class="{
            'bg-blue-500 text-white': message.sender_id === currentUser.id,
            'bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-200': message.sender_id !== currentUser.id,
            'opacity-60': message.isTemporary,
            'border border-red-500': message.error
        }">
          <p class="text-sm break-words">{{ message.content }}</p>
          <p class="text-xs mt-1 opacity-70" :class="message.sender_id === currentUser.id ? 'text-right' : 'text-left'">
            {{ formatTimestamp(message.sent_at) }}
          </p>
        </div>
      </div>
    </div>

    <!-- Message Input -->
    <footer class="p-3 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
      <form @submit.prevent="sendMessage" class="flex items-center space-x-3">
        <input type="text" v-model="newMessageContent" placeholder="Type a message..." class="input-field flex-grow" autocomplete="off" />
        <button type="submit" class="btn btn-primary">Send</button>
      </form>
    </footer>
  </div>
</template>