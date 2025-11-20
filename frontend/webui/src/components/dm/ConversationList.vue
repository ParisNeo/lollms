<script setup>
import { computed } from 'vue';
import { useSocialStore } from '../../stores/social';
import UserAvatar from '../ui/Cards/UserAvatar.vue';

const props = defineProps({
  modelValue: { // The selected user ID (v-model)
    type: Number,
    default: null
  }
});

const emit = defineEmits(['update:modelValue']);

const socialStore = useSocialStore();
// Use the full list of conversations (history), not just the active/open windows
const conversations = computed(() => socialStore.conversations);
const isLoading = computed(() => socialStore.isLoadingConversations);

function selectConversation(userId) {
  emit('update:modelValue', userId);
}

function formatTime(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    if (date.toDateString() === now.toDateString()) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString();
}
</script>

<template>
  <div class="h-full bg-white dark:bg-gray-800 flex flex-col">
    <div class="p-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100">Messages</h2>
    </div>
    
    <div class="flex-grow overflow-y-auto custom-scrollbar">
        <div v-if="isLoading && conversations.length === 0" class="p-4 text-center text-sm text-gray-500">
            Loading conversations...
        </div>
        <div v-else-if="conversations.length === 0" class="p-8 text-center">
            <p class="text-sm text-gray-500">No conversations yet.</p>
        </div>
        <ul v-else class="divide-y divide-gray-100 dark:divide-gray-700/50">
            <li v-for="convo in conversations" :key="convo.partner_user_id">
                <button
                    @click="selectConversation(convo.partner_user_id)"
                    class="w-full text-left flex items-center p-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors relative"
                    :class="{ 'bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500': modelValue === convo.partner_user_id }"
                >
                    <UserAvatar :icon="convo.partner_icon" :username="convo.partner_username" size-class="h-12 w-12 flex-shrink-0" />
                    <div class="ml-3 flex-1 min-w-0">
                        <div class="flex justify-between items-baseline">
                            <p class="font-semibold text-sm text-gray-900 dark:text-gray-100 truncate pr-2">{{ convo.partner_username }}</p>
                            <span class="text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">{{ formatTime(convo.last_message_at) }}</span>
                        </div>
                        <div class="flex justify-between items-center mt-1">
                            <p class="text-xs text-gray-500 dark:text-gray-400 truncate pr-2" :class="{'font-medium text-gray-800 dark:text-gray-200': convo.unread_count > 0}">
                                {{ convo.last_message }}
                            </p>
                            <span v-if="convo.unread_count > 0" class="flex-shrink-0 inline-flex items-center justify-center px-2 py-0.5 text-xs font-bold leading-none text-white bg-blue-600 rounded-full">
                                {{ convo.unread_count }}
                            </span>
                        </div>
                    </div>
                </button>
            </li>
        </ul>
    </div>
  </div>
</template>
