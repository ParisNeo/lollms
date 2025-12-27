<script setup>
import { ref, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import GenericModal from './GenericModal.vue';
import { useRouter } from 'vue-router';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconArrowRight from '../../assets/icons/IconArrowRight.vue';

const uiStore = useUiStore();
const authStore = useAuthStore();
const router = useRouter();

const modalName = 'whatsNext';
const currentStep = ref(1); // 1: Terms, 2: Welcome (if admin) or Finish

const isAdmin = computed(() => authStore.isAdmin);

const title = computed(() => {
    return currentStep.value === 1 ? 'Terms of Use & Mission' : 'Welcome to LoLLMs!';
});

async function acceptTerms() {
    if (isAdmin.value) {
        currentStep.value = 2;
    } else {
        await finalizeSetup();
    }
}

async function finalizeSetup() {
    try {
        await authStore.updateUserPreferences({ first_login_done: true });
        uiStore.closeModal(modalName);
        if (isAdmin.value) {
            router.push({ name: 'Admin' });
        } else {
            router.push({ name: 'Home' });
        }
    } catch (e) {
        console.error("Failed to update user profile:", e);
        // Close anyway to not block user
        uiStore.closeModal(modalName);
    }
}

function handleClose() {
    // Only allow closing via buttons to ensure terms acceptance
}
</script>

<template>
  <GenericModal
    :modal-name="modalName"
    :title="title"
    :allow-overlay-close="false"
    :show-close-button="false"
    max-width-class="max-w-2xl"
    @close="handleClose"
  >
    <template #body>
      <!-- STEP 1: Terms of Use -->
      <div v-if="currentStep === 1" class="space-y-6">
        <div class="prose dark:prose-invert text-sm text-gray-700 dark:text-gray-300 max-h-[60vh] overflow-y-auto pr-2 custom-scrollbar">
            <h4 class="text-lg font-bold">Mission Statement</h4>
            <p>
                LoLLMs (Lord of Large Language Models) aims to provide open, accessible, and privacy-focused AI tools for everyone. 
                We believe in ethical AI usage that empowers individuals while respecting legal and moral standards.
            </p>

            <h4 class="text-lg font-bold mt-4">Terms of Use</h4>
            <p>By using this platform, you agree to the following conditions:</p>
            
            <ul class="list-disc pl-5 space-y-2">
                <li>
                    <strong>Legal Compliance:</strong> You must respect the legislation of your country of residence at all times while using this software.
                </li>
                <li>
                    <strong>EU AI Act:</strong> If you are located in the European Union, you acknowledge and agree to adhere to all obligations set forth in the EU AI Act, 
                    particularly regarding transparency, data governance, and prohibited AI practices.
                </li>
                <li>
                    <strong>Prohibited Content:</strong> You strictly agree NOT to use this product for the generation or dissemination of:
                    <ul class="list-circle pl-5 mt-1">
                        <li>Disinformation, fake news, or misleading content intended to deceive.</li>
                        <li>Hate speech, harassment, or content promoting violence.</li>
                        <li>Any material that violates applicable laws or regulations.</li>
                    </ul>
                </li>
                <li>
                    <strong>Responsibility:</strong> You are solely responsible for the content you generate and how you use it. The developers of LoLLMs assume no liability for misuse of the platform.
                </li>
            </ul>
        </div>
        
        <div class="flex justify-end pt-4 border-t dark:border-gray-700">
            <button @click="acceptTerms" class="btn btn-primary flex items-center gap-2 px-6 py-2.5 shadow-lg transform hover:scale-105 transition-all">
                <IconCheckCircle class="w-5 h-5" />
                <span>I Accept & Continue</span>
            </button>
        </div>
      </div>

      <!-- STEP 2: Admin Welcome (Only for Admins) -->
      <div v-else class="p-4 text-center space-y-6">
        <h3 class="text-xl font-bold text-gray-900 dark:text-white">Congratulations, Admin!</h3>
        <p class="text-gray-700 dark:text-gray-300">
          You've successfully set up your LoLLMs Chat instance. Here are your next steps to configure the system:
        </p>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
          <div class="whats-next-card">
            <div class="icon-box bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">1</div>
            <div>
                <h5 class="font-bold">Configure Bindings</h5>
                <p class="text-xs text-gray-500 dark:text-gray-400">Go to Settings > Bindings to connect AI providers (Ollama, OpenAI, etc.).</p>
            </div>
          </div>
          
          <div class="whats-next-card">
            <div class="icon-box bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400">2</div>
            <div>
                <h5 class="font-bold">Install Personas</h5>
                <p class="text-xs text-gray-500 dark:text-gray-400">Visit the Zoo to install personalities for different tasks.</p>
            </div>
          </div>

          <div class="whats-next-card">
             <div class="icon-box bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400">3</div>
            <div>
                <h5 class="font-bold">Manage Data</h5>
                <p class="text-xs text-gray-500 dark:text-gray-400">Create RAG Data Stores in the Data Studio to let AI read your docs.</p>
            </div>
          </div>

          <div class="whats-next-card">
             <div class="icon-box bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400">4</div>
            <div>
                <h5 class="font-bold">System Settings</h5>
                <p class="text-xs text-gray-500 dark:text-gray-400">Adjust global server settings, email, and security options.</p>
            </div>
          </div>
        </div>

        <div class="flex justify-center pt-6">
            <button @click="finalizeSetup" class="btn btn-primary flex items-center gap-2 px-8 py-3 text-lg shadow-xl">
                <span>Go to Admin Panel</span>
                <IconArrowRight class="w-5 h-5" />
            </button>
        </div>
      </div>
    </template>
    
    <!-- No Footer needed as buttons are inline -->
    <template #footer><div></div></template>
  </GenericModal>
</template>

<style scoped>
.whats-next-card {
    @apply flex items-start gap-3 p-3 rounded-lg border border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50;
}
.icon-box {
    @apply w-8 h-8 flex items-center justify-center rounded-full font-bold text-sm flex-shrink-0;
}
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>
