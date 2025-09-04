<script setup>
import { computed } from 'vue';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import ChatView from '../components/chat/ChatView.vue';
import FeedComponent from '../components/social/FeedComponent.vue';
import WelcomeView from './WelcomeView.vue';

const uiStore = useUiStore();
const authStore = useAuthStore();

const mainView = computed(() => uiStore.mainView);
const isAuthenticated = computed(() => authStore.isAuthenticated);
const isAuthenticating = computed(() => authStore.isAuthenticating);
</script>

<template>
  <div class="h-full w-full">
    <template v-if="isAuthenticated">
      <FeedComponent v-if="mainView === 'feed'" />
      <ChatView v-else-if="mainView === 'chat'" />
      <!-- Fallback for authenticated user if mainView is not set for some reason -->
      <FeedComponent v-else />
    </template>
    <template v-else-if="!isAuthenticating">
      <WelcomeView />
    </template>
    <!-- App.vue handles the global loading screen when isAuthenticating is true -->
    <div v-else></div>
  </div>
</template>