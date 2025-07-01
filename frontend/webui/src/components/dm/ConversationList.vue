<script setup>
import { computed } from 'vue';
import { useSocialStore } from '../../stores/social';
import UserAvatar from '../ui/UserAvatar.vue';

const props = defineProps({
  modelValue: { // The selected user ID (v-model)
    type: Number,
    default: null
  }
});

const emit = defineEmits(['update:modelValue']);

const socialStore = useSocialStore();
const activeConversations = computed(() => Object.values(socialStore.activeConversations));

function selectConversation(userId) {
  emit('update:modelValue', userId);
}
</script>

<template>
  <div class="h-full bg-gray-50 dark:bg-gray-800/50 border-r border-gray-200 dark:border-gray-700">
    <div class="p-3">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100">Messages</h2>
    </div>
    <div v-if="activeConversations.length === 0" class="p-4 text-center text-sm text-gray-500">
      No active conversations. Start one from a user's profile.
    </div>
    <div v-else class="overflow-y-auto">
      <ul>
        <li v-for="convo in activeConversations" :key="convo.partner.id">
          <button
            @click="selectConversation(convo.partner.id)"
            class="w-full text-left flex items-center p-3 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
            :class="{ 'bg-blue-100 dark:bg-blue-900/50': modelValue === convo.partner.id }"
          >
            <UserAvatar :icon="convo.partner.icon" :username="convo.partner.username" size-class="h-10 w-10" />
            <div class="ml-3">
              <p class="font-semibold text-gray-900 dark:text-gray-100">{{ convo.partner.username }}</p>
              <!-- Placeholder for last message preview -->
            </div>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>