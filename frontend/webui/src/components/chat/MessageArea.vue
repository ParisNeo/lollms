<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import MessageBubble from './MessageBubble.vue';

const discussionsStore = useDiscussionsStore();
const activeMessages = computed(() => discussionsStore.activeMessages);
const currentDiscussionId = computed(() => discussionsStore.currentDiscussionId);

const messageContainer = ref(null);
const isNearBottom = ref(true);

// --- SCROLLING LOGIC ---

// Helper to scroll the container to the bottom
const scrollToBottom = (smooth = true) => {
  nextTick(() => {
    const el = messageContainer.value;
    if (el) {
      el.scrollTo({
        top: el.scrollHeight,
        behavior: smooth ? 'smooth' : 'auto',
      });
    }
  });
};

// Event handler to check if the user has scrolled away from the bottom
const handleScroll = () => {
    const el = messageContainer.value;
    if (el) {
        // A threshold to consider "near" the bottom, to account for various UI elements/paddings
        const threshold = 50; 
        const isScrolledToBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
        if (isNearBottom.value !== isScrolledToBottom) {
            isNearBottom.value = isScrolledToBottom;
        }
    }
};

// Attach/detach scroll listeners
onMounted(() => {
  messageContainer.value?.addEventListener('scroll', handleScroll);
});

onUnmounted(() => {
  messageContainer.value?.removeEventListener('scroll', handleScroll);
});

// Watcher for discussion changes to force-scroll to the bottom
watch(currentDiscussionId, (newId) => {
    if (newId) {
        // When a new discussion is selected, we want to be at the bottom by default.
        isNearBottom.value = true;
        scrollToBottom(false); // Use 'auto' behavior for instant scrolling
    }
});

// Watcher for new messages to implement "smart" scrolling
watch(activeMessages, () => {
    // If the user is near the bottom, auto-scroll with new messages.
    // If they have scrolled up to read history, don't interrupt them.
    if (isNearBottom.value) {
        scrollToBottom(true);
    }
}, { deep: true }); // Deep watch is crucial for detecting streaming content changes within a message


// --- MESSAGE GROUPING LOGIC ---

// Groups messages by date for rendering separators.
const groupMessagesByDate = (messages) => {
    if (!messages) return {};
    const groups = {};
    messages.forEach(message => {
        const date = new Date(message.created_at || Date.now());
        const dateKey = date.toDateString();
        if (!groups[dateKey]) {
            groups[dateKey] = [];
        }
        groups[dateKey].push(message);
    });
    return groups;
};

// Formats the date for the separator.
const formatDateSeparator = (dateStr) => {
    const date = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) return 'Today';
    if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return date.toLocaleDateString(undefined, {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
};
</script>

<template>
  <div ref="messageContainer" class="p-4 space-y-2">
    <template v-for="(messagesOnDate, date) in groupMessagesByDate(activeMessages)" :key="date">
      <!-- Date Separator -->
      <div class="date-separator flex items-center my-4 gap-4">
        <div class="flex-1 h-px bg-gray-200 dark:bg-gray-700"></div>
        <div class="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
          {{ formatDateSeparator(date) }}
        </div>
        <div class="flex-1 h-px bg-gray-200 dark:bg-gray-700"></div>
      </div>
      <!-- Messages for that date -->
      <MessageBubble v-for="message in messagesOnDate" :key="message.id" :message="message" />
    </template>
  </div>
</template>