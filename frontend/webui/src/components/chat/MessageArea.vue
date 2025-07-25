<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import MessageBubble from './MessageBubble.vue';

const discussionsStore = useDiscussionsStore();
const activeMessages = computed(() => discussionsStore.activeMessages);
const currentDiscussionId = computed(() => discussionsStore.currentDiscussionId);
const hasMoreMessages = computed(() => discussionsStore.hasMoreMessages);
const isLoadingMessages = computed(() => discussionsStore.isLoadingMessages);

const messageContainer = ref(null);
const loadMoreTrigger = ref(null);
const isNearBottom = ref(true);
let observer;

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

onMounted(() => {
    messageContainer.value?.addEventListener('scroll', handleScroll);
    observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && hasMoreMessages.value && !isLoadingMessages.value) {
            const el = messageContainer.value;
            const oldScrollHeight = el.scrollHeight;
            discussionsStore.loadMoreMessages().then(() => {
                nextTick(() => {
                    el.scrollTop = el.scrollHeight - oldScrollHeight;
                });
            });
        }
    }, { root: messageContainer.value, threshold: 0.1 });
    if (loadMoreTrigger.value) observer.observe(loadMoreTrigger.value);
});

onUnmounted(() => {
    messageContainer.value?.removeEventListener('scroll', handleScroll);
    if(observer && loadMoreTrigger.value) observer.unobserve(loadMoreTrigger.value);
});

watch(currentDiscussionId, (newId) => {
    if (newId) {
        isNearBottom.value = true;
        scrollToBottom(false);
    }
});

watch(activeMessages, (newMessages, oldMessages) => {
    if (newMessages.length > oldMessages.length && isNearBottom.value) {
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

const displayItems = computed(() => {
    if (!activeMessages.value) return [];
    const items = [];
    const groups = activeMessages.value.reduce((acc, message) => {
        const dateKey = new Date(message.created_at || Date.now()).toDateString();
        if (!acc[dateKey]) acc[dateKey] = [];
        acc[dateKey].push(message);
        console.log(acc)
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
    <div ref="loadMoreTrigger" v-if="hasMoreMessages" class="p-4 text-center">
        <svg class="animate-spin h-6 w-6 text-gray-400 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
    </div>
    <TransitionGroup name="list" tag="div" class="relative flex flex-col gap-4 pb-40">
      <div v-for="item in displayItems" :key="item.id">
        <div v-if="item.type === 'separator'" class="date-separator">
            <div class="flex-1 h-px bg-gray-200 dark:bg-gray-700"></div>
            <div class="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
              {{ formatDateSeparator(item.date) }}
            </div>
            <div class="flex-1 h-px bg-gray-200 dark:bg-gray-700"></div>
        </div>
        <MessageBubble v-else-if="item.type === 'message'" :message="item.data" />
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.date-separator { @apply flex items-center my-4 gap-4; }
.list-move, .list-enter-active, .list-leave-active { transition: all 0.5s ease; }
.list-enter-from { opacity: 0; transform: translateY(30px); }
.list-leave-to { opacity: 0; transform: translateX(30px); }
.list-leave-active { position: absolute; width: calc(100% - 2rem); }
</style>