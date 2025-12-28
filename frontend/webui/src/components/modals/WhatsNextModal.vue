<script setup>
import { ref, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import GenericModal from './GenericModal.vue';
import { useRouter } from 'vue-router';

// Icons
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconArrowRight from '../../assets/icons/IconArrowRight.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue'; // Bindings
import IconUserCircle from '../../assets/icons/IconUserCircle.vue'; // Personalities
import IconServer from '../../assets/icons/IconServer.vue'; // Services/Notebooks
import IconMessage from '../../assets/icons/IconMessage.vue'; // Chat
import IconPhoto from '../../assets/icons/IconPhoto.vue'; // Studios
import IconBookOpen from '../../assets/icons/IconBookOpen.vue'; // Help

const uiStore = useUiStore();
const authStore = useAuthStore();
const router = useRouter();

const modalName = 'whatsNext';
const currentStep = ref(1);

const isAdmin = computed(() => authStore.isAdmin);

// --- Steps Definition ---
const adminSteps = [
    { id: 1, title: 'Terms of Use' },
    { id: 2, title: 'Crucial Setup: Bindings' },
    { id: 3, title: 'Brains & Memory' },
    { id: 4, title: 'Connect to the World' },
    { id: 5, title: 'Ready to Go' }
];

const userSteps = [
    { id: 1, title: 'Terms of Use' },
    { id: 2, title: 'How to Chat' },
    { id: 3, title: 'Power Tools' },
    { id: 4, title: 'Need Help?' }
];

const steps = computed(() => isAdmin.value ? adminSteps : userSteps);
const totalSteps = computed(() => steps.value.length);
const isLastStep = computed(() => currentStep.value === totalSteps.value);

// --- Navigation ---
function nextStep() {
    if (currentStep.value < totalSteps.value) {
        currentStep.value++;
    } else {
        finalizeSetup();
    }
}

function prevStep() {
    if (currentStep.value > 1) {
        currentStep.value--;
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
        uiStore.closeModal(modalName);
    }
}

function handleClose() {
    // Only allow closing via finish button to ensure terms are seen
}
</script>

<template>
  <GenericModal
    :modal-name="modalName"
    :title="steps[currentStep-1].title"
    :allow-overlay-close="false"
    :show-close-button="false"
    max-width-class="max-w-3xl"
    @close="handleClose"
  >
    <template #body>
      <div class="min-h-[350px] flex flex-col justify-between">
          
        <!-- ==================== STEP 1: TERMS OF USE (COMMON) ==================== -->
        <div v-if="currentStep === 1" class="space-y-4 animate-fade-in">
             <div class="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-200 dark:border-blue-800">
                <h4 class="font-bold text-lg text-blue-800 dark:text-blue-200 mb-2">Welcome to LoLLMs</h4>
                <p class="text-sm text-blue-700 dark:text-blue-300">
                    Lord of Large Language Models is your unified platform for AI privacy, power, and connectivity.
                    Before we begin, please review our core principles.
                </p>
            </div>

            <div class="prose dark:prose-invert text-sm max-h-[40vh] overflow-y-auto custom-scrollbar p-2 border rounded-md dark:border-gray-700">
                <h4>1. Legal Compliance</h4>
                <p>You must strictly adhere to the laws and regulations of your country of residence while using this software.</p>
                
                <h4>2. EU AI Act</h4>
                <p>If you are in the European Union, you agree to comply with the EU AI Act, including transparency on AI-generated content.</p>
                
                <h4>3. Prohibited Usage</h4>
                <ul>
                    <li>Do not generate disinformation, fake news, or deepfakes intended to deceive.</li>
                    <li>Do not use for illegal acts, cybercrime, or harassment.</li>
                </ul>

                <h4>4. Liability</h4>
                <p>You accept full responsibility for all content generated and actions performed. The creators disclaim liability for misuse.</p>
            </div>
        </div>

        <!-- ==================== ADMIN TRACK ==================== -->
        <template v-if="isAdmin">
            
            <!-- Step 2: Bindings (The Engine) -->
            <div v-if="currentStep === 2" class="space-y-6 animate-fade-in text-center px-4">
                <div class="flex justify-center mb-4">
                    <div class="p-4 bg-purple-100 dark:bg-purple-900/30 rounded-full text-purple-600">
                        <IconCpuChip class="w-12 h-12" />
                    </div>
                </div>
                <h3 class="text-xl font-bold">The Engine Room: Bindings</h3>
                <p class="text-gray-600 dark:text-gray-300">
                    LoLLMs is an interface; it needs an "engine" to work. <strong>Bindings</strong> connect LoLLMs to AI providers.
                </p>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-left mt-4">
                    <div class="p-3 border rounded-lg dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition">
                        <span class="font-bold block mb-1 text-blue-600">LLM Binding (Required)</span>
                        <span class="text-xs text-gray-500">Connect to Ollama, OpenAI, HuggingFace, or local GGUF models for text generation.</span>
                    </div>
                    <div class="p-3 border rounded-lg dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition">
                        <span class="font-bold block mb-1 text-pink-600">TTI Binding</span>
                        <span class="text-xs text-gray-500">Connect to Stable Diffusion or DALL-E for image generation.</span>
                    </div>
                    <div class="p-3 border rounded-lg dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition">
                        <span class="font-bold block mb-1 text-green-600">TTS / STT</span>
                        <span class="text-xs text-gray-500">Enable voice interaction (Text-to-Speech / Speech-to-Text).</span>
                    </div>
                    <div class="p-3 border rounded-lg dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition">
                        <span class="font-bold block mb-1 text-orange-600">RAG Binding</span>
                        <span class="text-xs text-gray-500">Choose a vector database to let AI read your documents.</span>
                    </div>
                </div>
                <p class="text-xs text-red-500 font-bold mt-2">Action: Go to Settings > Bindings immediately after setup.</p>
            </div>

            <!-- Step 3: Personalities -->
            <div v-if="currentStep === 3" class="space-y-6 animate-fade-in text-center px-4">
                <div class="flex justify-center mb-4">
                    <div class="p-4 bg-yellow-100 dark:bg-yellow-900/30 rounded-full text-yellow-600">
                        <IconUserCircle class="w-12 h-12" />
                    </div>
                </div>
                <h3 class="text-xl font-bold">Brains & Memory</h3>
                <p class="text-gray-600 dark:text-gray-300">
                    Customize how the AI behaves and what it knows.
                </p>
                <div class="space-y-4 text-left max-w-lg mx-auto">
                    <div class="flex gap-3">
                        <div class="font-bold min-w-[100px]">Personalities</div>
                        <div class="text-sm text-gray-500">Pre-prompted roles (e.g., "Python Coder", "Creative Writer"). Download hundreds from the <strong>Zoo</strong>.</div>
                    </div>
                    <div class="flex gap-3">
                        <div class="font-bold min-w-[100px]">Context</div>
                        <div class="text-sm text-gray-500">Adjust context size (memory span) in settings. Higher context = more memory but slower.</div>
                    </div>
                    <div class="flex gap-3">
                        <div class="font-bold min-w-[100px]">Data Stores</div>
                        <div class="text-sm text-gray-500">Upload PDFs or scrape websites in the <strong>Data Studio</strong> to chat with your data (RAG).</div>
                    </div>
                </div>
            </div>

            <!-- Step 4: Services -->
            <div v-if="currentStep === 4" class="space-y-6 animate-fade-in text-center px-4">
                 <div class="flex justify-center mb-4">
                    <div class="p-4 bg-indigo-100 dark:bg-indigo-900/30 rounded-full text-indigo-600">
                        <IconServer class="w-12 h-12" />
                    </div>
                </div>
                <h3 class="text-xl font-bold">Expose as API</h3>
                <p class="text-gray-600 dark:text-gray-300">
                    LoLLMs isn't just a UI. It's a server that can power other apps.
                </p>
                <div class="bg-gray-50 dark:bg-gray-800 p-4 rounded-lg text-left text-sm space-y-2">
                    <p><strong>OpenAI Compatible Endpoint:</strong> <code class="bg-gray-200 dark:bg-gray-700 px-1 rounded">/v1/chat/completions</code></p>
                    <p><strong>Ollama Compatible Endpoint:</strong> <code class="bg-gray-200 dark:bg-gray-700 px-1 rounded">/ollama/v1/chat/completions</code></p>
                    <p class="mt-2 text-gray-500">
                        You can connect tools like VSCode extensions, AutoGen, or CrewAI directly to your LoLLMs instance. 
                        Manage API Keys in <strong>Settings > API Keys</strong>.
                    </p>
                </div>
            </div>

             <!-- Step 5: Finish -->
            <div v-if="currentStep === 5" class="space-y-6 animate-fade-in text-center px-4">
                 <h3 class="text-2xl font-bold text-green-600 dark:text-green-400">You're Ready!</h3>
                 <p class="text-gray-600 dark:text-gray-300">
                     The Admin Panel is your command center.
                 </p>
                 <div class="grid grid-cols-2 gap-4 max-w-md mx-auto text-sm">
                     <div class="bg-gray-100 dark:bg-gray-800 p-3 rounded">Manage Users</div>
                     <div class="bg-gray-100 dark:bg-gray-800 p-3 rounded">Monitor Logs</div>
                     <div class="bg-gray-100 dark:bg-gray-800 p-3 rounded">Install Models</div>
                     <div class="bg-gray-100 dark:bg-gray-800 p-3 rounded">Configure Security</div>
                 </div>
            </div>
        </template>

        <!-- ==================== USER TRACK ==================== -->
        <template v-else>
            
            <!-- Step 2: Basics -->
            <div v-if="currentStep === 2" class="space-y-6 animate-fade-in text-center px-4">
                <div class="flex justify-center mb-4">
                    <div class="p-4 bg-blue-100 dark:bg-blue-900/30 rounded-full text-blue-600">
                        <IconMessage class="w-12 h-12" />
                    </div>
                </div>
                <h3 class="text-xl font-bold">Chat Basics</h3>
                <div class="text-left space-y-4 text-sm text-gray-600 dark:text-gray-300">
                    <p>1. <strong>Select a Model:</strong> Click the header to pick a smart model (LLM) and a Personality (Role).</p>
                    <p>2. <strong>Discussions:</strong> Your chat history is on the left sidebar. Create new chats for different topics.</p>
                    <p>3. <strong>Attachments:</strong> You can drag & drop files or images into the chat bar.</p>
                </div>
            </div>

            <!-- Step 3: Studios -->
            <div v-if="currentStep === 3" class="space-y-6 animate-fade-in text-center px-4">
                <div class="flex justify-center mb-4">
                    <div class="p-4 bg-purple-100 dark:bg-purple-900/30 rounded-full text-purple-600">
                        <IconPhoto class="w-12 h-12" />
                    </div>
                </div>
                <h3 class="text-xl font-bold">Creative Studios</h3>
                <p class="text-gray-600 dark:text-gray-300">Access specialized tools from the User Menu (top right).</p>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-left mt-2">
                    <div class="p-3 border rounded hover:border-purple-500 transition">
                        <strong class="block text-purple-600">Image Studio</strong>
                        <span class="text-xs">Create, edit, and iterate on AI art.</span>
                    </div>
                    <div class="p-3 border rounded hover:border-blue-500 transition">
                        <strong class="block text-blue-600">Notebooks</strong>
                        <span class="text-xs">Write long-form content or code with AI assistance.</span>
                    </div>
                    <div class="p-3 border rounded hover:border-pink-500 transition">
                        <strong class="block text-pink-600">Voice Studio</strong>
                        <span class="text-xs">Generate speech or clone voices (if enabled).</span>
                    </div>
                    <div class="p-3 border rounded hover:border-green-500 transition">
                        <strong class="block text-green-600">Data Studio</strong>
                        <span class="text-xs">Upload documents to chat with them.</span>
                    </div>
                </div>
            </div>

            <!-- Step 4: Help -->
            <div v-if="currentStep === 4" class="space-y-6 animate-fade-in text-center px-4">
                <div class="flex justify-center mb-4">
                    <div class="p-4 bg-green-100 dark:bg-green-900/30 rounded-full text-green-600">
                        <IconBookOpen class="w-12 h-12" />
                    </div>
                </div>
                <h3 class="text-xl font-bold">Need Help?</h3>
                <p class="text-gray-600 dark:text-gray-300">
                    If you get stuck or want to learn advanced tricks, visit the <strong>Help</strong> section in the sidebar.
                </p>
                <p class="text-sm italic">"The only limit is your imagination."</p>
            </div>

        </template>
      </div>

      <!-- Navigation Footer -->
      <div class="mt-8 pt-4 border-t dark:border-gray-700 flex justify-between items-center">
          <button 
            v-if="currentStep > 1" 
            @click="prevStep" 
            class="btn btn-secondary flex items-center gap-2"
          >
            <IconArrowLeft class="w-4 h-4" /> Back
          </button>
          <div v-else></div> <!-- Spacer -->

          <div class="flex gap-1">
              <div v-for="step in totalSteps" :key="step" class="w-2 h-2 rounded-full transition-colors" :class="step === currentStep ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'"></div>
          </div>

          <button 
            @click="nextStep" 
            class="btn btn-primary flex items-center gap-2"
          >
            <span v-if="isLastStep">Finish</span>
            <span v-else>Next</span>
            <IconCheckCircle v-if="isLastStep" class="w-4 h-4" />
            <IconArrowRight v-else class="w-4 h-4" />
          </button>
      </div>
    </template>
    <template #footer><div></div></template>
  </GenericModal>
</template>

<style scoped>
.animate-fade-in { animation: fadeIn 0.4s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>
