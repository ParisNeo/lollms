<!-- frontend/webui/src/views/HomeView.vue -->
<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../stores/discussions';
import WelcomeView from './WelcomeView.vue';
import ChatView from '../components/chat/ChatView.vue';

const discussionsStore = useDiscussionsStore();
const currentDiscussionId = computed(() => discussionsStore.currentDiscussionId);
</script>

<template>
  <div class="h-full w-full">
    <ChatView v-if="currentDiscussionId" />
    <WelcomeView v-else />
  </div>
</template>