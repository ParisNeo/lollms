<script setup>
import GenericModal from '../ui/GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useRouter } from 'vue-router';

const uiStore = useUiStore();
const router = useRouter();

const steps = [
    { id: 'bindings', title: '1. Configure LLM Bindings', description: 'Connect to your AI models (e.g., Ollama, Local Llama.cpp).', route: '/admin?tab=bindings' },
    { id: 'personalities', title: '2. Create a Personality', description: 'Define how your AI should behave. You can create your own or clone public ones.', route: '/settings?tab=personalities' },
    { id: 'global_settings', title: '3. Review Global Settings', description: 'Adjust app-wide settings like registration mode, email, etc.', route: '/admin?tab=global_settings' },
    { id: 'apps', title: '4. Explore App Zoo', description: 'Install and manage integrated web applications.', route: '/admin?tab=apps' },
    { id: 'users', title: '5. Manage Users', description: 'Approve new registrations, change roles, or reset passwords.', route: '/admin?tab=users' },
    { id: 'datastores', title: '6. Set up Data Stores (RAG)', description: 'Create knowledge bases to augment AI responses.', route: '/datastores' },
];

function goTo(route) {
    uiStore.closeModal('whatsNext');
    router.push(route);
}

function dismiss() {
    uiStore.closeModal('whatsNext');
}
</script>

<template>
  <GenericModal
    modalName="whatsNext"
    title="Welcome, Superadmin! What's Next?"
    :showCloseButton="true"
    :allowOverlayClose="true"
    maxWidthClass="max-w-xl"
  >
    <template #body>
      <div class="space-y-4 text-gray-800 dark:text-gray-100">
        <p class="text-sm text-center text-gray-600 dark:text-gray-400">
          Congratulations on setting up your LoLLMs instance! Here are some recommended steps to get started:
        </p>
        <ul class="space-y-3">
          <li v-for="step in steps" :key="step.id" class="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg flex items-start space-x-3">
            <div class="text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.532-1.676-1.676a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clip-rule="evenodd" /></svg>
            </div>
            <div>
              <h3 class="font-semibold text-lg">{{ step.title }}</h3>
              <p class="text-sm text-gray-700 dark:text-gray-300">{{ step.description }}</p>
              <button v-if="step.route" @click="goTo(step.route)" class="mt-2 text-blue-600 dark:text-blue-400 hover:underline text-sm font-medium">
                Go to {{ step.route.split('?')[0].replace('/', '').replace('admin', 'Admin Panel') }}
              </button>
            </div>
          </li>
        </ul>
      </div>
    </template>
    <template #footer>
      <button @click="dismiss" class="btn btn-primary">Got It!</button>
    </template>
  </GenericModal>
</template>