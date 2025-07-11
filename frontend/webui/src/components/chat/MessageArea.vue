<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import MessageBubble from './MessageBubble.vue';

const discussionsStore = useDiscussionsStore();
const activeMessages = computed(() => discussionsStore.activeMessages);
const currentDiscussionId = computed(() => discussionsStore.currentDiscussionId);

const messageContainer = ref(null);
const isNearBottom = ref(true);

const scrollToBottom = (smooth = true) => {
  nextTick(() => {
    const el = messageContainer.value;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
    }
  });
};

const handleScroll = () => {
    const el = messageContainer.value;
    if (el) {
        const threshold = 50; 
        isNearBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
    }
};

onMounted(() => messageContainer.value?.addEventListener('scroll', handleScroll));
onUnmounted(() => messageContainer.value?.removeEventListener('scroll', handleScroll));

watch(currentDiscussionId, (newId) => {
    if (newId) {
        isNearBottom.value = true;
        scrollToBottom(false);
    }
});

watch(activeMessages, () => {
    if (isNearBottom.value) {
        scrollToBottom(true);
    }
}, { deep: true });

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

// Flatten the grouped messages into a single array for TransitionGroup
const displayItems = computed(() => {
    if (!activeMessages.value) return [];
    const items = [];
    const groups = activeMessages.value.reduce((acc, message) => {
        const dateKey = new Date(message.created_at || Date.now()).toDateString();
        if (!acc[dateKey]) acc[dateKey] = [];
        acc[dateKey].push(message);
        return acc;
    }, {});

    for (const date in groups) {
        items.push({ type: 'separator', id: `sep-${date}`, date: date });
        groups[date].forEach(message => {
            items.push({ type: 'message', id: message.id, data: message });
        });
    }
    return items;
});
</script>

<template>
  <div ref="messageContainer" class="flex-1 overflow-y-auto min-w-0 p-4">
    <TransitionGroup name="list" tag="div" class="relative flex flex-col gap-4 pb-40">
      <div v-for="item in displayItems" :key="item.id">
        <!-- Date Separator -->
        <div v-if="item.type === 'separator'" class="date-separator">
            <div class="flex-1 h-px bg-gray-200 dark:bg-gray-700"></div>
            <div class="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
              {{ formatDateSeparator(item.date) }}
            </div>
            <div class="flex-1 h-px bg-gray-200 dark:bg-gray-700"></div>
        </div>
        <!-- Message -->
        <MessageBubble v-else-if="item.type === 'message'" :message="item.data" />
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.date-separator {
    @apply flex items-center my-4 gap-4;
}

/* Transitions for list items (messages and separators) */
.list-move,
.list-enter-active,
.list-leave-active {
    transition: all 0.5s ease;
}
.list-enter-from {
    opacity: 0;
    transform: translateY(30px);
}
.list-leave-to {
    opacity: 0;
    transform: translateX(30px);
}
.list-leave-active {
    position: absolute;
    width: calc(100% - 2rem); /* Match padding of container */
}
</style>