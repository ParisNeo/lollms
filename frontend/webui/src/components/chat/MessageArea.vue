<script>
import { mapState } from 'pinia';
import { useDiscussionsStore } from '../../stores/discussions';
import MessageBubble from './MessageBubble.vue';
import { nextTick } from 'vue';

export default {
  name: 'MessageArea',
  components: {
    MessageBubble,
  },
  computed: {
    ...mapState(useDiscussionsStore, ['activeMessages']),
  },
  watch: {
    // Watch for changes in the messages array to scroll to the bottom.
    activeMessages: {
      handler(newMessages, oldMessages) {
        // Use nextTick to ensure the DOM has updated before scrolling.
        nextTick(() => {
          this.scrollToBottom();
        });
      },
      deep: true, // Watch for changes inside the array objects as well.
    },
  },
  mounted() {
    this.scrollToBottom(false); // Initial scroll on mount
  },
  methods: {
    scrollToBottom(smooth = true) {
      const el = this.$refs.messageContainer;
      if (el) {
        el.scrollTo({
          top: el.scrollHeight,
          behavior: smooth ? 'smooth' : 'auto',
        });
      }
    },
    // Groups messages by date for rendering separators.
    groupMessagesByDate(messages) {
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
    },
    // Formats the date for the separator.
    formatDateSeparator(dateStr) {
        const date = new Date(dateStr);
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);

        if (date.toDateString() === today.toDateString()) return 'Today';
        if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
        return date.toLocaleDateString(undefined, {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });
    }
  },
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
      <MessageBubble v-for="(message, index) in messagesOnDate" :key="message.id" :message="message" />
    </template>
  </div>
</template>