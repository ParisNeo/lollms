<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import { useRouter } from 'vue-router';

const uiStore = useUiStore();
const router = useRouter();

const modalName = 'whatsNext';
const title = "Welcome! What's Next?";

function closeAndNavigate(routeName) {
  uiStore.closeModal(modalName);
  router.push({ name: routeName });
}

function handleClose() {
    uiStore.closeModal(modalName);
}
</script>

<template>
  <GenericModal
    :modal-name="modalName"
    :title="title"
    :allow-overlay-close="false"
    max-width-class="max-w-xl"
    @close="handleClose"
  >
    <template #body>
      <div class="p-6 text-center space-y-6">
        <h3 class="text-xl font-bold text-gray-900 dark:text-white">Congratulations, Admin!</h3>
        <p class="text-gray-700 dark:text-gray-300">
          You've successfully set up your LoLLMs Chat instance. Here are some recommended first steps to get started:
        </p>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button @click="closeAndNavigate('Admin')" class="whats-next-button">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 mb-2 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.827 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.827 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.827-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.827-3.31 2.37-2.37.526.323 1.09.559 1.724 1.066z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
            <span class="font-semibold">Configure Settings</span>
            <span class="text-sm">Adjust global app behavior, LLM bindings, and email.</span>
          </button>
          
          <button @click="closeAndNavigate('DataStores')" class="whats-next-button">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 mb-2 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 7v10l2 2h10l2-2V7m-2 0H6m2 0V5a2 2 0 012-2h4a2 2 0 012 2v2m-6 0h.01M6 20h12a2 2 0 002-2V8l-2-2H6a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
            <span class="font-semibold">Manage Data Stores</span>
            <span class="text-sm">Create personal RAG data stores and upload documents.</span>
          </button>

          <button @click="closeAndNavigate('Settings')" class="whats-next-button">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 mb-2 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.827 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.827 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.827-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.827-3.31 2.37-2.37.526.323 1.09.559 1.724 1.066z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
            <span class="font-semibold">Explore Personal Settings</span>
            <span class="text-sm">Set your preferred LLM parameters, UI level, and language.</span>
          </button>

          <button @click="closeAndNavigate('Home')" class="whats-next-button">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 mb-2 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m0 0l-7 7-7-7m7 7v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
            <span class="font-semibold">Start Chatting!</span>
            <span class="text-sm">Begin a new conversation or explore the social feed.</span>
          </button>
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="handleClose" class="btn btn-secondary">
        Close
      </button>
    </template>
  </GenericModal>
</template>

<style scoped>
.whats-next-button {
    @apply flex flex-col items-center justify-center p-4 text-center rounded-lg border-2 border-gray-200 dark:border-gray-700
           hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:border-blue-400 dark:hover:border-blue-600 transition-all duration-200
           text-gray-800 dark:text-gray-100 space-y-1 h-36; /* Fixed height to keep grid uniform */
}
.whats-next-button span {
    @apply text-sm text-gray-600 dark:text-gray-300;
}
.whats-next-button .font-semibold {
    @apply text-gray-900 dark:text-white text-lg;
}
</style>