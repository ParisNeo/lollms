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
const dmInputRef = ref(null);

const scrollHeightBeforeLoad = ref(0);

const partner = computed(() => props.conversation.partner);

// --- MENTION STATE ---
const mentionQuery = ref('');
const mentionSuggestions = ref([]);
const isMentioning = ref(false);
let mentionDebounceTimer = null;
const mentionStartIndex = ref(-1);

async function scrollToBottom() {
  await nextTick();
  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight;
  }
}

async function handleScroll(event) {
  const container = event.target;
  if (container.scrollTop === 0 && !props.conversation.isLoading && !props.conversation.fullyLoaded) {
    scrollHeightBeforeLoad.value = container.scrollHeight;
    await socialStore.fetchMoreMessages(partner.value.id);
  }
}

function sendMessage() {
  if (newMessageContent.value.trim() === '') return;
  socialStore.sendDirectMessage({
    receiverUserId: partner.value.id,
    content: newMessageContent.value,
  });
  newMessageContent.value = '';
  isMentioning.value = false;
  scrollToBottom();
}

onMounted(() => {
  scrollToBottom();
});

onUpdated(() => {
  if (messageContainer.value) {
    if (scrollHeightBeforeLoad.value > 0) {
      const newScrollTop = messageContainer.value.scrollHeight - scrollHeightBeforeLoad.value;
      messageContainer.value.scrollTop = newScrollTop;
      scrollHeightBeforeLoad.value = 0;
    }
  }
});

function formatTimestamp(dateString) {
  const date = new Date(dateString);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// --- MENTION LOGIC ---
function handleInputForMentions(event) {
    const text = event.target.value;
    const cursorPosition = event.target.selectionStart;
    
    const textBeforeCursor = text.substring(0, cursorPosition);
    const atMatch = textBeforeCursor.match(/@(\w*)$/);

    if (atMatch) {
        mentionStartIndex.value = atMatch.index;
        const query = atMatch[1];
        mentionQuery.value = query;
        isMentioning.value = true;

        clearTimeout(mentionDebounceTimer);
        mentionDebounceTimer = setTimeout(async () => {
            if (mentionQuery.value === query) {
                mentionSuggestions.value = await socialStore.searchForMentions(query);
            }
        }, 200);
    } else {
        isMentioning.value = false;
        mentionSuggestions.value = [];
    }
}

function selectMention(user) {
    const beforeText = newMessageContent.value.substring(0, mentionStartIndex.value);
    const afterText = newMessageContent.value.substring(mentionStartIndex.value + mentionQuery.value.length + 1);
    
    const newText = `${beforeText}@${user.username} ${afterText}`;
    newMessageContent.value = newText;
    
    isMentioning.value = false;
    mentionSuggestions.value = [];
    
    nextTick(() => {
        const newCursorPos = beforeText.length + user.username.length + 2;
        dmInputRef.value.focus();
        dmInputRef.value.setSelectionRange(newCursorPos, newCursorPos);
    });
}
</script>

<template>
  <div v-if="conversation && conversation.partner" class="flex flex-col h-full bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-lg">
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

    <div ref="messageContainer" @scroll="handleScroll" class="flex-grow p-4 overflow-y-auto">
      <div v-if="conversation.isLoading" class="text-center py-2 text-sm text-gray-500">Loading...</div>
      
      <div v-if="conversation.error" class="text-center py-2 text-red-500 text-sm">
        {{ conversation.error }}
      </div>

      <div v-if="conversation.fullyLoaded" class="text-center py-4">
        <p class="text-xs text-gray-400 dark:text-gray-500">This is the beginning of your conversation with {{ partner.username }}.</p>
      </div>

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

    <footer class="p-3 border-t border-gray-200 dark:border-gray-700 flex-shrink-0 relative">
      <!-- MENTION POPUP -->
      <div v-if="isMentioning && mentionSuggestions.length > 0" class="absolute bottom-full left-0 right-0 mb-2 p-2 bg-white dark:bg-gray-900 border dark:border-gray-700 rounded-lg shadow-lg max-h-48 overflow-y-auto">
        <ul>
          <li v-for="user in mentionSuggestions" :key="user.id" @click="selectMention(user)" class="flex items-center p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer">
            <UserAvatar :icon="user.icon" :username="user.username" size-class="h-6 w-6" />
            <span class="ml-2 text-sm font-medium">{{ user.username }}</span>
          </li>
        </ul>
      </div>

      <form @submit.prevent="sendMessage" class="flex items-center space-x-3">
        <input ref="dmInputRef" type="text" v-model="newMessageContent" @input="handleInputForMentions" placeholder="Type a message..." class="input-field flex-grow" autocomplete="off" />
        <button type="submit" class="btn btn-primary">Send</button>
      </form>
    </footer>
  </div>
</template>