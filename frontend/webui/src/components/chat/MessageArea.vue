<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import MessageBubble from './MessageBubble.vue';
import useEventBus from '../../services/eventBus';
import { useFloating, offset, flip, shift } from '@floating-ui/vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconArrowDown from '../../assets/icons/IconArrowDown.vue';

const discussionsStore = useDiscussionsStore();
const activeMessages = computed(() => discussionsStore.activeMessages);
const currentDiscussionId = computed(() => discussionsStore.currentDiscussionId);
const hasMoreMessages = computed(() => discussionsStore.hasMoreMessages);
const isLoadingMessages = computed(() => discussionsStore.isLoadingMessages);

const messageContainer = ref(null);
const messagesListRef = ref(null);
const loadMoreTrigger = ref(null);
const isNearBottom = ref(true);
const newMessagesWhileScrolledUp = ref(false);

let intersectionObserver;
let resizeObserver;
const { on, off } = useEventBus();

const isAddMenuOpen = ref(false);
const addButtonRef = ref(null);
const addMenuRef = ref(null);
const { floatingStyles } = useFloating(addButtonRef, addMenuRef, {
    placement: 'top',
    middleware: [offset(10), flip(), shift()],
});

const scrollToBottom = (smooth = true) => {
  nextTick(() => {
    const el = messageContainer.value;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
      newMessagesWhileScrolledUp.value = false;
    }
  });
};

const handleScroll = () => {
    const el = messageContainer.value;
    if (el) {
        const threshold = 100;
        const wasNearBottom = isNearBottom.value;
        isNearBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
        if (!wasNearBottom && isNearBottom.value) {
            newMessagesWhileScrolledUp.value = false;
        }
    }
};

function handleClickOutside(event) {
    if (addButtonRef.value && !addButtonRef.value.contains(event.target) &&
        addMenuRef.value && !addMenuRef.value.contains(event.target)) {
        isAddMenuOpen.value = false;
    }
}

onMounted(() => {
    messageContainer.value?.addEventListener('scroll', handleScroll);

    intersectionObserver = new IntersectionObserver((entries) => {
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
    if (loadMoreTrigger.value) intersectionObserver.observe(loadMoreTrigger.value);

    if (messagesListRef.value?.$el) {
        resizeObserver = new ResizeObserver(() => {
            if (isNearBottom.value) {
                scrollToBottom(true);
            } else {
                newMessagesWhileScrolledUp.value = true;
            }
        });
        resizeObserver.observe(messagesListRef.value.$el);
    }

    document.addEventListener('mousedown', handleClickOutside);
    on('discussion:refreshed', () => {
      isNearBottom.value = true;
      newMessagesWhileScrolledUp.value = false;
      scrollToBottom(false);
    });
});

onUnmounted(() => {
    messageContainer.value?.removeEventListener('scroll', handleScroll);
    if(intersectionObserver && loadMoreTrigger.value) intersectionObserver.unobserve(loadMoreTrigger.value);
    if (resizeObserver && messagesListRef.value?.$el) resizeObserver.unobserve(messagesListRef.value.$el);
    document.removeEventListener('mousedown', handleClickOutside);
    off('discussion:refreshed');
});

watch(currentDiscussionId, (newId) => {
    if (newId) {
        isNearBottom.value = true;
        newMessagesWhileScrolledUp.value = false;
        scrollToBottom(false);
    }
}, { immediate: true });

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

function shouldShowDateSeparator(currentIndex) {
    if (currentIndex === 0) return true;
    const currentMessage = activeMessages.value[currentIndex];
    const prevMessage = activeMessages.value[currentIndex - 1];
    if (!currentMessage?.created_at || !prevMessage?.created_at) return false;
    
    const currentDate = new Date(currentMessage.created_at).toDateString();
    const prevDate = new Date(prevMessage.created_at).toDateString();
    
    return currentDate !== prevDate;
}

function addManualMessage(sender_type) {
    discussionsStore.addManualMessage({ sender_type });
    isAddMenuOpen.value = false;
}
</script>

<template>
  <div class="relative flex-1 min-w-0">
    <div ref="messageContainer" class="absolute inset-0 overflow-y-auto p-4">
      <div ref="loadMoreTrigger" v-if="hasMoreMessages" class="p-4 text-center">
          <svg class="animate-spin h-6 w-6 text-gray-400 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
      </div>
      <TransitionGroup ref="messagesListRef" name="list" tag="div" class="relative flex flex-col pb-40">
        <template v-for="(message, index) in activeMessages" :key="message.id">
          <div v-if="shouldShowDateSeparator(index)" class="date-separator">
              <div class="flex-1 h-px bg-gray-200 dark:bg-gray-700"></div>
              <div class="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
                {{ formatDateSeparator(message.created_at) }}
              </div>
              <div class="flex-1 h-px bg-gray-200 dark:bg-gray-700"></div>
          </div>
          <MessageBubble :message="message" />
        </template>
      </TransitionGroup>

      <!-- Add Message Button, positioned after messages -->
      <div class="flex justify-center my-6">
        <div class="relative">
            <button ref="addButtonRef" @click="isAddMenuOpen = !isAddMenuOpen" class="flex items-center justify-center w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors duration-200">
                <span class="font-bold text-xl leading-none select-none">+</span>
            </button>
            <Teleport to="body">
                <Transition
                    enter-active-class="transition ease-out duration-100"
                    enter-from-class="transform opacity-0 scale-95"
                    enter-to-class="transform opacity-100 scale-100"
                    leave-active-class="transition ease-in duration-75"
                    leave-from-class="transform opacity-100 scale-100"
                    leave-to-class="transform opacity-0 scale-95"
                >
                    <div v-if="isAddMenuOpen" ref="addMenuRef" :style="floatingStyles" class="z-50 w-56 origin-top-left rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 dark:ring-gray-700 focus:outline-none py-1">
                        <button @click="addManualMessage('user')" class="w-full text-left p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-sm flex items-center">
                            <IconUserCircle class="w-5 h-5 mr-2" />
                            <span>Add User Message</span>
                        </button>
                        <button @click="addManualMessage('assistant')" class="w-full text-left p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-sm flex items-center">
                            <IconSparkles class="w-5 h-5 mr-2" />
                            <span>Add AI Message</span>
                        </button>
                    </div>
                </Transition>
            </Teleport>
        </div>
      </div>
    </div>
    <!-- Scroll to Bottom Button -->
    <div class="absolute bottom-44 right-8 z-10">
        <transition
            enter-active-class="transition-opacity ease-out duration-300"
            enter-from-class="opacity-0"
            enter-to-class="opacity-100"
            leave-active-class="transition-opacity ease-in duration-200"
            leave-from-class="opacity-100"
            leave-to-class="opacity-0"
        >
            <button v-if="!isNearBottom && newMessagesWhileScrolledUp" @click="scrollToBottom(true)"
                    class="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-full shadow-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500">
                <IconArrowDown class="w-5 h-5" />
                <span>New messages</span>
            </button>
        </transition>
    </div>
  </div>
</template>