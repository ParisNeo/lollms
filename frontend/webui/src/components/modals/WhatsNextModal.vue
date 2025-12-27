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

            <h4 class="text-lg font-bold mt-4">Terms of Use & Legal Compliance</h4>
            <div class="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
                <p class="font-semibold text-red-600 dark:text-red-400 mb-2">By continuing, you strictly agree to the following:</p>
                <ul class="list-disc pl-5 space-y-2">
                    <li>
                        <strong>Respect Legislation:</strong> You must strictly adhere to the laws and regulations of your country of residence at all times while using this software.
                    </li>
                    <li>
                        <strong>EU AI Act Compliance:</strong> If you are within the European Union, you acknowledge and agree to comply with all obligations under the EU AI Act, including transparency requirements and prohibitions on unacceptable risk AI practices.
                    </li>
                    <li>
                        <strong>Prohibited Activities:</strong> You agree <strong>NOT</strong> to use this platform for:
                        <ul class="list-circle pl-5 mt-1 text-xs">
                            <li>Generating or spreading disinformation, fake news, or deepfakes intended to deceive.</li>
                            <li>Engaging in illegal acts, cybercrime, or promoting violence/hate speech.</li>
                            <li>Harassing or harming others.</li>
                        </ul>
                    </li>
                    <li>
                        <strong>Liability:</strong> You accept full responsibility for all content generated and actions performed using this tool. The creators of LoLLMs disclaim all liability for misuse.
                    </li>
                </ul>
            </div>
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
