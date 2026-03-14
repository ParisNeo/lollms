<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { useAdminStore } from '../../stores/admin';
import { useDataStore } from '../../stores/data';
import GenericModal from './GenericModal.vue';
import { useRouter } from 'vue-router';
import { parsedMarkdown } from '../../services/markdownParser';

// Icons
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconCircle from '../../assets/icons/IconCircle.vue';
import IconArrowRight from '../../assets/icons/IconArrowRight.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue'; 
import IconUserCircle from '../../assets/icons/IconUserCircle.vue'; 
import IconServer from '../../assets/icons/IconServer.vue'; 
import IconMessage from '../../assets/icons/IconMessage.vue'; 
import IconPhoto from '../../assets/icons/IconPhoto.vue'; 
import IconBookOpen from '../../assets/icons/IconBookOpen.vue'; 
import IconFingerPrint from '../../assets/icons/IconFingerPrint.vue';
import IconShieldCheck from '../../assets/icons/IconCheckCircle.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import IconDatabase from '../../assets/icons/IconDatabase.vue';
import IconMcp from '../../assets/icons/IconMcp.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';
import IconMicrophone from '../../assets/icons/IconMicrophone.vue';

const uiStore = useUiStore();
const authStore = useAuthStore();
const adminStore = useAdminStore();
const dataStore = useDataStore();
const router = useRouter();

const isAdmin = computed(() => authStore.isAdmin);
const modalData = computed(() => uiStore.modalData(modalName));
const isUpdate = computed(() => !!modalData.value?.isUpdate);
const changelog = computed(() => modalData.value?.changelog);


const modalName = 'whatsNext';
const currentStep = ref(1);

// --- Wizard Binding State ---
const isAddingBinding = ref(false);
const isSavingBinding = ref(false);
const selectedBindingType = ref(null);
const bindingForm = ref({ alias: '', name: '', config: {} });
const isKeyVisible = ref({});

// --- Steps Definition ---
const adminSteps = [
    { id: 1, title: 'Mission & Terms', category: 'welcome' },
    { id: 2, title: 'Step 1: Text Generation (LLM)', category: 'llm' },
    { id: 3, title: 'Step 2: Image Generation (TTI)', category: 'tti' },
    { id: 4, title: 'Step 3: Speech to Text (STT)', category: 'stt' },
    { id: 5, title: 'Step 4: Text to Speech (TTS)', category: 'tts' },
    { id: 6, title: 'Step 5: The Brain (Personalities)', category: 'personalities' },
    { id: 7, title: 'Ready to Go', category: 'finish' }
];

const userSteps = [
    { id: 1, title: 'Mission & Terms' },
    { id: 2, title: 'Understanding LoLLMs' },
    { id: 3, title: 'Chat & Basic Usage' },
    { id: 4, title: 'Advanced: Studios' },
    { id: 5, title: 'Need Help?' }
];

const steps = computed(() => isAdmin.value ? adminSteps : userSteps);
const totalSteps = computed(() => steps.value.length);
const isLastStep = computed(() => currentStep.value === totalSteps.value);

// --- Binding Helpers ---
const currentCategory = computed(() => steps.value[currentStep.value - 1]?.category);

const availableTypes = computed(() => {
    if (currentCategory.value === 'llm') return adminStore.availableBindingTypes;
    if (currentCategory.value === 'tti') return adminStore.availableTtiBindingTypes;
    if (currentCategory.value === 'stt') return adminStore.availableSttBindingTypes;
    if (currentCategory.value === 'tts') return adminStore.availableTtsBindingTypes;
    return [];
});

const configuredBindings = computed(() => {
    if (currentCategory.value === 'llm') return adminStore.bindings;
    if (currentCategory.value === 'tti') return adminStore.ttiBindings;
    if (currentCategory.value === 'stt') return adminStore.sttBindings;
    if (currentCategory.value === 'tts') return adminStore.ttsBindings;
    return [];
});

const activeTypeDesc = computed(() => {
    if (!selectedBindingType.value) return null;
    return availableTypes.value.find(b => (b.binding_name || b.name) === selectedBindingType.value);
});

// Unified parameter resolver to handle different backend naming conventions
const allFormParameters = computed(() => {
    const type = activeTypeDesc.value;
    if (!type) return [];
    // Standardize across different binding versions/types
    return type.input_parameters || type.global_input_parameters || type.parameters || [];
});

// Helper to parse comma-separated options for select inputs
function parseOptions(options) {
    if (typeof options === 'string') return options.split(',').map(o => o.trim()).filter(o => o);
    if (Array.isArray(options)) return options;
    return [];
}

// Watch for category changes to reset form
watch(currentStep, () => {
    isAddingBinding.value = false;
    selectedBindingType.value = null;
    bindingForm.value = { alias: '', name: '', config: {} };
    isKeyVisible.value = {};
    
    // Auto-fetch data for the current category
    if (isAdmin.value) {
        if (currentCategory.value === 'llm') { adminStore.fetchBindings(); adminStore.fetchAvailableBindingTypes(); }
        if (currentCategory.value === 'tti') { adminStore.fetchTtiBindings(); adminStore.fetchAvailableTtiBindingTypes(); }
        if (currentCategory.value === 'stt') { adminStore.fetchSttBindings(); adminStore.fetchAvailableSttBindingTypes(); }
        if (currentCategory.value === 'tts') { adminStore.fetchTtsBindings(); adminStore.fetchAvailableTtsBindingTypes(); }
    }
});

function handleStartAdd() {
    isAddingBinding.value = true;
    selectedBindingType.value = null;
}

function handleSelectType(type) {
    selectedBindingType.value = type.binding_name || type.name;
    bindingForm.value.name = selectedBindingType.value;
    bindingForm.value.alias = `${selectedBindingType.value}_config`;
    
    // Initialize config with proper default values based on types
    const config = {};
    const params = type.input_parameters || type.global_input_parameters || type.parameters || [];
    params.forEach(p => {
        if (p.type === 'bool') {
            config[p.name] = p.default !== undefined ? p.default : false;
        } else if (p.type === 'int' || p.type === 'float') {
            config[p.name] = p.default !== undefined ? p.default : 0;
        } else {
            config[p.name] = p.default !== undefined ? p.default : '';
        }
    });
    bindingForm.value.config = config;
}

async function handleSaveBinding() {
    if (!bindingForm.value.alias || !bindingForm.value.name) return;
    isSavingBinding.value = true;
    try {
        const cat = currentCategory.value;
        if (cat === 'llm') await adminStore.addBinding(bindingForm.value);
        if (cat === 'tti') await adminStore.addTtiBinding(bindingForm.value);
        if (cat === 'stt') await adminStore.addSttBinding(bindingForm.value);
        if (cat === 'tts') await adminStore.addTtsBinding(bindingForm.value);
        
        isAddingBinding.value = false;
        uiStore.addNotification(`${cat.toUpperCase()} Binding added!`, 'success');
    } finally {
        isSavingBinding.value = false;
    }
}

async function handleDeleteBinding(id) {
    const cat = currentCategory.value;
    if (cat === 'llm') await adminStore.deleteBinding(id);
    if (cat === 'tti') await adminStore.deleteTtiBinding(id);
    if (cat === 'stt') await adminStore.deleteSttBinding(id);
    if (cat === 'tts') await adminStore.deleteTtsBinding(id);
}

// --- Navigation ---
function nextStep() {
    // Validation: Require at least one LLM binding to move past step 2
    if (isAdmin.value && currentStep.value === 2 && configuredBindings.value.length === 0) {
        uiStore.addNotification('Please configure at least one LLM binding to continue.', 'warning');
        return;
    }

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
        if (!isUpdate.value) {
            await authStore.updateUserPreferences({ first_login_done: true });
        }
        uiStore.closeModal(modalName);
        
        if (!isUpdate.value) {
            if (isAdmin.value) {
                router.push({ name: 'Admin' });
            } else {
                router.push({ name: 'Home' });
            }
        }
    } catch (e) {
        console.error("Failed to update user profile:", e);
        uiStore.closeModal(modalName);
    }    
}
</script>

<template>
  <GenericModal
    :modal-name="modalName"
    :title="isUpdate ? `What's New in v${changelog?.version || ''}` : steps[currentStep-1].title"
    :allow-overlay-close="false"
    :show-close-button="false"
    max-width-class="max-w-5xl"
  >
    <template #body>
      <div class="min-h-[500px] flex flex-col justify-between p-2">
        <!-- ==================== UPDATE VIEW (Changelog) ==================== -->
        <div v-if="isUpdate && changelog" class="space-y-6 animate-fade-in">
            <div class="bg-blue-600 rounded-2xl p-8 text-white shadow-lg mb-6">
                <h3 class="text-3xl font-black tracking-tight">{{ changelog.title }}</h3>
                <p class="mt-2 opacity-80 font-medium">A new chapter for LoLLMs has arrived.</p>
            </div>
            
            <div class="prose dark:prose-invert max-w-none p-6 border rounded-2xl dark:border-gray-700 bg-white dark:bg-gray-900 shadow-sm overflow-y-auto max-h-[400px] custom-scrollbar">
                <MessageContentRenderer :content="changelog.content" />
            </div>
            
            <div class="mt-auto pt-6 flex justify-end">
                <button @click="finalizeSetup" class="btn btn-primary px-10 py-3 rounded-2xl shadow-xl">
                    Let's Explore
                </button>
            </div>
        </div>
          
        <!-- ==================== STEP 1: ENHANCED MISSION & TERMS ==================== -->
        <div v-if="currentStep === 1" class="space-y-8 animate-fade-in">
             
            <!-- Hero Mission Section -->
            <div class="relative overflow-hidden rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-900 p-8 text-white shadow-xl">
                <div class="relative z-10">
                    <div class="flex items-center gap-4 mb-4">
                        <div class="p-3 bg-white/10 rounded-xl backdrop-blur-md">
                            <IconGlobeAlt class="w-8 h-8 text-blue-200" />
                        </div>
                        <h3 class="text-2xl font-black tracking-tight">The Vision Behind LoLLMs</h3>
                    </div>
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                        <div class="space-y-4 text-blue-50">
                            <p class="text-lg font-medium leading-relaxed">
                                I created LoLLMs (Lord of Large Language Models) to be the ultimate bridge between humanity and AI.
                            </p>
                            <p class="text-sm opacity-90 leading-relaxed">
                                My mission is to <strong>democratize AI access</strong> by providing a unified, privacy-first ecosystem. 
                                I believe that AI shouldn't be a black box controlled by a few giants, but a tool that runs locally, 
                                respecting your data and your freedom. While I developed this tool, it is open for contributions to grow further.
                            </p>
                        </div>
                        <div class="bg-black/20 backdrop-blur-sm rounded-xl p-5 border border-white/10 space-y-3">
                            <h5 class="text-xs font-black uppercase tracking-widest text-blue-300">The "Lord" Concept</h5>
                            <p class="text-sm italic leading-snug opacity-80">
                                "The 'Lord' in LoLLMs is not about authority, but about <strong>orchestration</strong>. It is the hub that connects 
                                all models—text, image, and sound—into a single, seamless intelligent flow that you control entirely."
                            </p>
                            <p class="text-xs font-bold text-right text-blue-200">— ParisNeo, Creator</p>
                        </div>
                    </div>
                </div>
                <!-- Abstract Background Decor -->
                <div class="absolute -right-20 -bottom-20 w-96 h-96 bg-blue-500/20 blur-[100px] rounded-full"></div>
            </div>

            <!-- Enhanced Terms Section -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Legal Card -->
                <div class="lg:col-span-2 space-y-4">
                    <h4 class="text-sm font-black uppercase tracking-widest text-gray-500 dark:text-gray-400 flex items-center gap-2">
                        <IconShieldCheck class="w-4 h-4 text-green-500" />
                        Legal Agreement
                    </h4>
                    <div class="prose dark:prose-invert text-xs max-h-[250px] overflow-y-auto custom-scrollbar p-5 border rounded-2xl dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 shadow-inner">
                        <div class="space-y-4">
                            <section>
                                <h5 class="text-blue-600 dark:text-blue-400 font-bold m-0">1. Global Compliance</h5>
                                <p class="m-0">Users are strictly required to adhere to the laws of their jurisdiction. I provide the tools, but you provide the intent.</p>
                            </section>
                            <section>
                                <h5 class="text-blue-600 dark:text-blue-400 font-bold m-0">2. EU AI Act & Transparency</h5>
                                <p class="m-0">In compliance with modern standards, you must clearly identify AI-generated content when interacting with others to prevent deception.</p>
                            </section>
                            <section>
                                <h5 class="text-blue-600 dark:text-blue-400 font-bold m-0">3. Ethics in Content</h5>
                                <p class="m-0">Generation of disinformation, hate speech, or content promoting illegal acts is strictly prohibited. LoLLMs is built to empower, not to harm.</p>
                            </section>
                            <section>
                                <h5 class="text-blue-600 dark:text-blue-400 font-bold m-0">4. Privacy & Data</h5>
                                <p class="m-0">LoLLMs is designed for local execution. While I provide connectivity to cloud services, your primary safety lies in keeping your data on your hardware.</p>
                            </section>
                        </div>
                    </div>
                </div>

                <!-- Quick Checks Card -->
                <div class="bg-gray-100 dark:bg-gray-800 rounded-2xl p-6 border border-gray-200 dark:border-gray-700">
                    <h4 class="text-sm font-black uppercase tracking-widest text-gray-500 dark:text-gray-400 mb-6">Ethical Pillars</h4>
                    <ul class="space-y-6">
                        <li class="flex items-start gap-3">
                            <div class="mt-1 w-2 h-2 rounded-full bg-green-500 flex-shrink-0"></div>
                            <div class="text-xs"><strong>Privacy First</strong>: Run models locally to ensure your data stays yours.</div>
                        </li>
                        <li class="flex items-start gap-3">
                            <div class="mt-1 w-2 h-2 rounded-full bg-blue-500 flex-shrink-0"></div>
                            <div class="text-xs"><strong>Open Science</strong>: Bridging the gap between researchers and end-users.</div>
                        </li>
                        <li class="flex items-start gap-3">
                            <div class="mt-1 w-2 h-2 rounded-full bg-purple-500 flex-shrink-0"></div>
                            <div class="text-xs"><strong>No Silos</strong>: A unified hub for all AI technologies without walled gardens.</div>
                        </li>
                    </ul>
                </div>
            </div>
            
            <div class="flex items-center gap-3 p-4 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 text-xs font-bold rounded-xl border border-yellow-100 dark:border-yellow-900/30">
                <IconCheckCircle class="w-5 h-5 flex-shrink-0" />
                <span>By clicking "Next", you formally accept these terms and commit to using LoLLMs for the betterment of society.</span>
            </div>
        </div>

        <!-- ==================== ADMIN TRACK (Steps 2-7) ==================== -->
        <template v-if="isAdmin">
            
            <!-- Dynamic Binding Steps (LLM, TTI, STT, TTS) -->
            <div v-if="[2,3,4,5].includes(currentStep)" class="space-y-6 animate-fade-in h-full flex flex-col">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <div class="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30 text-blue-600">
                            <IconCpuChip v-if="currentCategory === 'llm'" class="w-6 h-6" />
                            <IconPhoto v-else-if="currentCategory === 'tti'" class="w-6 h-6" />
                            <IconMicrophone v-else class="w-6 h-6" />
                        </div>
                        <div>
                            <h3 class="text-lg font-bold">Configure {{ currentCategory.toUpperCase() }} Engine</h3>
                            <p class="text-xs text-gray-500">Add at least one provider to enable these features.</p>
                        </div>
                    </div>
                    <button v-if="!isAddingBinding" @click="handleStartAdd" class="btn btn-primary btn-sm flex items-center gap-2">
                        <IconPlus class="w-4 h-4" /> Add Provider
                    </button>
                </div>

                <!-- ADDING FLOW -->
                <div v-if="isAddingBinding" class="flex-grow flex flex-col gap-4 border rounded-2xl p-6 bg-gray-50 dark:bg-gray-900 shadow-inner overflow-hidden">
                    
                    <!-- 1. Select Type -->
                    <template v-if="!selectedBindingType">
                        <div class="flex items-center justify-between mb-2">
                             <h4 class="text-sm font-black uppercase text-gray-400 tracking-widest">Select Binding Type</h4>
                             <button @click="isAddingBinding = false" class="text-xs text-gray-500 hover:text-red-500">Cancel</button>
                        </div>
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 overflow-y-auto custom-scrollbar pr-2">
                            <button v-for="type in availableTypes" :key="type.name" 
                                    @click="handleSelectType(type)"
                                    class="p-4 text-left border-2 rounded-xl bg-white dark:bg-gray-800 hover:border-blue-500 transition-all group">
                                <div class="font-bold text-sm mb-1 group-hover:text-blue-500">{{ type.title || type.name }}</div>
                                <p class="text-[10px] text-gray-500 line-clamp-2">{{ type.description || 'No description' }}</p>
                            </button>
                        </div>
                    </template>

                    <!-- 2. Configure Form -->
                    <template v-else>
                         <div class="flex items-center justify-between mb-2 border-b dark:border-gray-700 pb-2">
                             <div class="flex items-center gap-2">
                                <button @click="selectedBindingType = null" class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg">
                                    <IconArrowLeft class="w-4 h-4" />
                                </button>
                                <span class="font-bold text-sm text-blue-600">{{ activeTypeDesc?.title || selectedBindingType }}</span>
                             </div>
                             <h4 class="text-[10px] font-black uppercase text-gray-400 tracking-widest">Configure Parameters</h4>
                        </div>

                        <div class="flex-grow overflow-y-auto custom-scrollbar space-y-4 pr-2">
                            <div>
                                <label class="label text-xs">Friendly Alias</label>
                                <input v-model="bindingForm.alias" class="input-field" placeholder="e.g. My Local Ollama">
                                <p class="text-[9px] text-gray-400 mt-1 uppercase font-bold">Internal identifier for this configuration</p>
                            </div>

                            <!-- Description of the binding -->
                            <div v-if="activeTypeDesc?.description" class="text-xs text-gray-500 bg-white dark:bg-gray-800 p-3 rounded-xl border border-gray-100 dark:border-gray-700 prose-sm dark:prose-invert" v-html="parsedMarkdown(activeTypeDesc.description)"></div>

                            <!-- Dynamic Parameters -->
                            <div v-for="param in allFormParameters" :key="param.name" class="space-y-1">
                                <label class="block text-[10px] font-black uppercase text-gray-400 tracking-widest">
                                    {{ param.name.replace(/_/g, ' ') }}
                                    <span v-if="param.mandatory" class="text-red-500 ml-1">*</span>
                                </label>
                                
                                <!-- Dropdown/Select -->
                                <select v-if="param.options && param.options.length > 0" v-model="bindingForm.config[param.name]" class="input-field text-sm">
                                    <option v-for="option in parseOptions(param.options)" :key="option" :value="option">{{ option }}</option>
                                </select>

                                <!-- Toggle/Boolean -->
                                <div v-else-if="param.type === 'bool'" class="flex items-center justify-between p-2 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm">
                                    <span class="text-[10px] text-gray-500 pr-4">{{ param.description }}</span>
                                    <button @click="bindingForm.config[param.name] = !bindingForm.config[param.name]" type="button" :class="[bindingForm.config[param.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors']">
                                        <span :class="[bindingForm.config[param.name] ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition']"></span>
                                    </button>
                                </div>

                                <!-- Text/Number/Password -->
                                <div v-else class="relative">
                                    <input 
                                        :type="(param.name.includes('key') || param.name.includes('token')) && !isKeyVisible[param.name] ? 'password' : 'text'"
                                        v-model="bindingForm.config[param.name]" 
                                        class="input-field text-sm" 
                                        :placeholder="param.description || 'Enter value...'"
                                    >
                                    <button v-if="param.name.includes('key') || param.name.includes('token')" type="button" @click="isKeyVisible[param.name] = !isKeyVisible[param.name]" class="absolute inset-y-0 right-0 px-3 flex items-center text-gray-400 hover:text-blue-500 transition-colors">
                                        <IconEyeOff v-if="isKeyVisible[param.name]" class="w-4 h-4" /><IconEye v-else class="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                        </div>

                        <!-- Quick Actions / Commands in Wizard -->
                        <div v-if="activeTypeDesc?.commands?.length > 0" class="mt-4 pt-4 border-t dark:border-gray-700">
                            <h5 class="text-[10px] font-black uppercase text-gray-400 tracking-widest mb-3">Quick Actions</h5>
                            <div class="space-y-2">
                                <button v-for="cmd in activeTypeDesc.commands" :key="cmd.name" 
                                        @click="adminStore.executeBindingCommand(null, cmd.name, bindingForm.config)"
                                        class="w-full flex items-center justify-between p-2 rounded-lg bg-white dark:bg-gray-800 border dark:border-gray-700 hover:bg-gray-100 transition-colors group">
                                    <div class="flex items-center gap-2">
                                        <IconTerminal class="w-4 h-4 text-gray-400 group-hover:text-blue-500" />
                                        <span class="text-xs font-bold">{{ cmd.title || cmd.name }}</span>
                                    </div>
                                    <IconPlayCircle class="w-4 h-4 text-blue-500" />
                                </button>
                            </div>
                        </div>

                        <div class="pt-4 flex justify-end gap-2">
                             <button @click="selectedBindingType = null" class="btn btn-secondary btn-sm">Back</button>
                             <button @click="handleSaveBinding" class="btn btn-primary btn-sm px-6" :disabled="isSavingBinding">
                                 <IconAnimateSpin v-if="isSavingBinding" class="w-4 h-4 mr-2 animate-spin" />
                                 Save Configuration
                             </button>
                        </div>
                    </template>
                </div>

                <!-- LIST VIEW -->
                <div v-else class="flex-grow flex flex-col gap-3 overflow-y-auto custom-scrollbar">
                    <div v-if="configuredBindings.length === 0" class="flex-grow flex flex-col items-center justify-center border-2 border-dashed rounded-3xl p-10 opacity-60">
                        <IconCircle class="w-12 h-12 mb-4 text-gray-300" />
                        <p class="text-sm font-bold text-gray-500 uppercase tracking-widest">No Active Providers</p>
                        <p class="text-xs text-gray-400 mt-1">Click "Add Provider" above to get started.</p>
                    </div>
                    
                    <div v-for="b in configuredBindings" :key="b.id" class="flex items-center justify-between p-4 bg-white dark:bg-gray-800 rounded-2xl border dark:border-gray-700 shadow-sm group">
                        <div class="flex items-center gap-4">
                            <div class="p-2 rounded-xl bg-gray-100 dark:bg-gray-700 text-blue-500">
                                <IconServer class="w-5 h-5" />
                            </div>
                            <div>
                                <h4 class="font-bold text-sm">{{ b.alias }}</h4>
                                <p class="text-[10px] text-gray-500 uppercase font-black tracking-widest">{{ b.name }}</p>
                            </div>
                        </div>
                        <button @click="handleDeleteBinding(b.id)" class="p-2 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity">
                            <IconTrash class="w-5 h-5" />
                        </button>
                    </div>

                    <div v-if="currentCategory === 'llm' && configuredBindings.length > 0" class="mt-auto p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-100 dark:border-blue-800 flex items-center gap-3">
                         <IconCheckCircle class="w-5 h-5 text-green-500 flex-shrink-0" />
                         <span class="text-xs text-blue-800 dark:text-blue-300">LLM Engine ready. You can add more bindings later in Admin Settings.</span>
                    </div>
                </div>
            </div>

            <!-- Step 6: Personalities (Informational) -->
            <div v-if="currentStep === 6" class="space-y-8 animate-fade-in px-4">
                 <div class="text-center">
                    <div class="inline-flex p-4 bg-yellow-100 dark:bg-yellow-900/30 rounded-full text-yellow-600 mb-4 shadow-sm">
                        <IconUserCircle class="w-12 h-12" />
                    </div>
                     <h3 class="text-xl font-bold mb-2">The Brain: Personalities</h3>
                    <p class="text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
                        Personalities define <em>how</em> the AI behaves. They are more than just system prompts; they can contain tools, scripts, and specialized knowledge.
                    </p>
                </div>
                
                <div class="bg-white dark:bg-gray-800 p-6 rounded-xl border dark:border-gray-700 shadow-sm">
                    <ul class="space-y-4 text-sm text-gray-700 dark:text-gray-300">
                        <li class="flex gap-3">
                            <span class="bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-300 font-bold px-2 py-0.5 rounded text-xs h-fit text-nowrap">ZOO</span>
                            <span>Visit the <strong>Personality Zoo</strong> in the Admin Panel to download hundreds of community-made personas (Coders, Writers, Therapists, etc.).</span>
                        </li>
                        <li class="flex gap-3">
                            <span class="bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 font-bold px-2 py-0.5 rounded text-xs h-fit text-nowrap">CREATE</span>
                            <span>You can craft your own personalities with custom scripts and icons in the settings.</span>
                        </li>
                        <li class="flex gap-3">
                            <span class="bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 font-bold px-2 py-0.5 rounded text-xs h-fit text-nowrap">MOUNT</span>
                            <span>Mount multiple personalities and switch between them instantly in the chat header.</span>
                        </li>
                    </ul>
                </div>
            </div>

            <!-- Step 4: Context -->
            <div v-if="currentStep === 4" class="space-y-8 animate-fade-in px-4">
                 <div class="text-center">
                    <div class="inline-flex p-4 bg-teal-100 dark:bg-teal-900/30 rounded-full text-teal-600 mb-4 shadow-sm">
                        <IconFingerPrint class="w-12 h-12" />
                    </div>
                     <h3 class="text-xl font-bold mb-2">The Context: Knowing You</h3>
                    <p class="text-gray-600 dark:text-gray-300 max-w-2xl mx-auto">
                        LoLLMs allows you to define "User Context" so the AI knows who it's talking to without you repeating yourself.
                    </p>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="bg-gray-50 dark:bg-gray-800/50 p-5 rounded-xl border dark:border-gray-700">
                        <h4 class="font-bold text-teal-600 dark:text-teal-400 mb-2">User Data Zone</h4>
                        <p class="text-sm">A dedicated text area in your profile where you can paste bio info, project details, or preferences. The AI reads this before every chat.</p>
                    </div>
                    <div class="bg-gray-50 dark:bg-gray-800/50 p-5 rounded-xl border dark:border-gray-700">
                         <h4 class="font-bold text-teal-600 dark:text-teal-400 mb-2">Memory</h4>
                        <p class="text-sm">Enable <strong>Long Term Memory</strong> in settings to let the AI automatically remember key facts from your conversations over time.</p>
                    </div>
                </div>
                <p class="text-center text-xs text-gray-500">Configure this in <strong>Settings > User Context</strong>.</p>
            </div>

            <!-- Step 5: Connect & Serve -->
            <div v-if="currentStep === 5" class="space-y-8 animate-fade-in px-4">
                 <div class="text-center">
                    <div class="inline-flex p-4 bg-indigo-100 dark:bg-indigo-900/30 rounded-full text-indigo-600 mb-4 shadow-sm">
                        <IconServer class="w-12 h-12" />
                    </div>
                    <h3 class="text-xl font-bold mb-2">The Orchestration Hub</h3>
                    <p class="text-gray-600 dark:text-gray-300 max-w-3xl mx-auto leading-relaxed">
                        I designed LoLLMs to be more than just a chat interface. It is a powerful backend that can serve AI functionality to your entire workflow.
                    </p>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <!-- Standard Compatibility -->
                    <div class="bg-gray-50 dark:bg-gray-800 p-5 rounded-2xl border dark:border-gray-700 space-y-3">
                        <div class="flex items-center gap-2 text-indigo-600 dark:text-indigo-400">
                            <IconCpuChip class="w-5 h-5" />
                            <h4 class="font-black text-xs uppercase tracking-widest">Compatibility Layers</h4>
                        </div>
                        <ul class="text-xs space-y-2 opacity-80">
                            <li>• <strong>OpenAI V1</strong>: Use any app that expects OpenAI endpoints.</li>
                            <li>• <strong>Ollama V1</strong>: Perfect for local LLM ecosystems.</li>
                            <li class="mt-2 p-2 bg-gray-200 dark:bg-gray-900 rounded font-mono text-[10px]">http://localhost:9642/v1</li>
                        </ul>
                    </div>

                    <!-- Native LoLLMs API -->
                    <div class="bg-blue-50 dark:bg-blue-900/20 p-5 rounded-2xl border border-blue-100 dark:border-blue-800 space-y-3">
                         <div class="flex items-center gap-2 text-blue-600 dark:text-blue-400">
                            <IconServer class="w-5 h-5" />
                            <h4 class="font-black text-xs uppercase tracking-widest">LoLLMs Native API</h4>
                        </div>
                        <p class="text-xs leading-relaxed">I have implemented specialized endpoints for advanced control:</p>
                        <ul class="text-xs space-y-1">
                            <li>• <strong>/v1/lollms</strong>: Access the raw orchestrator power.</li>
                            <li>• <strong>Tokenizer</strong>: Precise token counts and debugging.</li>
                            <li>• <strong>Long Context</strong>: Programmatic access to massive documents.</li>
                        </ul>
                    </div>

                    <!-- MCP Section -->
                    <div class="bg-purple-50 dark:bg-purple-900/20 p-5 rounded-2xl border border-purple-100 dark:border-purple-800 space-y-3">
                         <div class="flex items-center gap-2 text-purple-600 dark:text-purple-400">
                            <IconMcp class="w-5 h-5" />
                            <h4 class="font-black text-xs uppercase tracking-widest">MCP Bridge</h4>
                        </div>
                        <p class="text-xs leading-relaxed">LoLLMs acts as both an <strong>MCP Host and Client</strong>. I have made it possible to connect tools like Google Search, Browser Automation, and Python Scripting to <em>any</em> model you have mounted.</p>
                    </div>

                    <!-- RAG & DataStores -->
                    <div class="bg-green-50 dark:bg-green-900/20 p-5 rounded-2xl border border-green-100 dark:border-green-800 space-y-3">
                         <div class="flex items-center gap-2 text-green-600 dark:text-green-400">
                            <IconDatabase class="w-5 h-5" />
                            <h4 class="font-black text-xs uppercase tracking-widest">Programmatic RAG</h4>
                        </div>
                        <p class="text-xs leading-relaxed">Manage your <strong>DataStores</strong> via API. You can programmatically upload documents, scrape URLs, and perform semantic searches to build custom knowledge applications.</p>
                    </div>
                </div>

                <div class="p-3 text-center bg-gray-100 dark:bg-gray-800/50 rounded-xl text-[11px] text-gray-500">
                    Secure your integrations with <strong>API Keys</strong> in settings. I recommend using the native endpoints for the best performance.
                </div>
            </div>

             <!-- Step 7: Finish -->
            <div v-if="currentStep === 7" class="space-y-8 animate-fade-in text-center px-4">
                 <h3 class="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-green-500 to-emerald-700">System Ready</h3>
                 <p class="text-gray-600 dark:text-gray-300">
                     You are now the administrator of your own AI infrastructure.
                 </p>
                 <div class="grid grid-cols-2 gap-4 max-w-md mx-auto text-sm font-medium text-gray-700 dark:text-gray-200">
                     <div class="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg shadow-sm border dark:border-gray-700">Manage Users</div>
                     <div class="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg shadow-sm border dark:border-gray-700">Monitor Logs</div>
                     <div class="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg shadow-sm border dark:border-gray-700">Install Models</div>
                     <div class="bg-gray-100 dark:bg-gray-800 p-4 rounded-lg shadow-sm border dark:border-gray-700">Security Config</div>
                 </div>
                 <div class="pt-4 text-xs text-gray-400">
                     Click 'Finish' to enter the Admin Panel.
                 </div>
            </div>
        </template>

        <!-- ==================== USER TRACK (Steps 2-5) ==================== -->
        <template v-else>
            
            <!-- Step 2: Concepts -->
            <div v-if="currentStep === 2" class="space-y-6 animate-fade-in px-4">
                 <div class="text-center">
                    <h3 class="text-xl font-bold mb-4">Understanding LoLLMs</h3>
                    <p class="text-gray-600 dark:text-gray-300">LoLLMs isn't just a chatbot; it's a workspace.</p>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
                    <div class="p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700">
                        <div class="font-bold text-blue-600 mb-2">1. The Model</div>
                        <p class="text-xs text-gray-500">The raw intelligence engine (like GPT-4 or Llama 3). Selected in the top bar.</p>
                    </div>
                    <div class="p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700">
                        <div class="font-bold text-purple-600 mb-2">2. The Personality</div>
                        <p class="text-xs text-gray-500">The "role" the AI plays (e.g. Coder, Artist). Change this to switch skills.</p>
                    </div>
                    <div class="p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700">
                        <div class="font-bold text-green-600 mb-2">3. The Context</div>
                        <p class="text-xs text-gray-500">Documents you upload or your profile info. This grounds the AI in your data.</p>
                    </div>
                </div>
            </div>

            <!-- Step 3: Basics -->
            <div v-if="currentStep === 3" class="space-y-6 animate-fade-in text-center px-4">
                 <div class="flex justify-center mb-4">
                    <div class="p-4 bg-blue-100 dark:bg-blue-900/30 rounded-full text-blue-600">
                        <IconMessage class="w-12 h-12" />
                    </div>
                </div>
                <h3 class="text-xl font-bold">Chat Basics</h3>
                <div class="text-left space-y-4 text-sm text-gray-600 dark:text-gray-300 max-w-lg mx-auto bg-gray-50 dark:bg-gray-800/50 p-6 rounded-xl border dark:border-gray-700 shadow-sm">
                    <p>• <strong>Sidebar:</strong> Your chat history lives on the left. You can group chats into folders.</p>
                    <p>• <strong>Top Bar:</strong> Switch Models and Personalities here.</p>
                    <p>• <strong>Input:</strong> Drag & drop images or files directly into the chat bar to discuss them.</p>
                    <p>• <strong>Actions:</strong> Hover over messages to copy code, edit, or regenerate responses.</p>
                </div>
            </div>

            <!-- Step 4: Studios -->
            <div v-if="currentStep === 4" class="space-y-6 animate-fade-in px-4">
                <div class="text-center">
                    <div class="inline-flex p-4 bg-purple-100 dark:bg-purple-900/30 rounded-full text-purple-600 mb-4 shadow-sm">
                        <IconPhoto class="w-12 h-12" />
                    </div>
                    <h3 class="text-xl font-bold mb-2">Advanced Studios</h3>
                    <p class="text-gray-600 dark:text-gray-300">Access specialized workspaces from the User Menu (top right).</p>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-left mt-2">
                    <div class="p-4 border rounded-xl hover:border-purple-500 transition bg-white dark:bg-gray-800 shadow-sm">
                        <strong class="block text-purple-600 mb-1">Image Studio</strong>
                        <span class="text-xs text-gray-500">A professional interface for generating, editing, and iterating on AI art with fine-grained control.</span>
                    </div>
                    <div class="p-4 border rounded-xl hover:border-blue-500 transition bg-white dark:bg-gray-800 shadow-sm">
                        <strong class="block text-blue-600 mb-1">Notebooks</strong>
                        <span class="text-xs text-gray-500">A document-based interface for drafting long-form content, code, or research papers with AI assistance.</span>
                    </div>
                    <div class="p-4 border rounded-xl hover:border-pink-500 transition bg-white dark:bg-gray-800 shadow-sm">
                        <strong class="block text-pink-600 mb-1">Voice Studio</strong>
                        <span class="text-xs text-gray-500">Generate speech from text using high-quality AI voices.</span>
                    </div>
                    <div class="p-4 border rounded-xl hover:border-green-500 transition bg-white dark:bg-gray-800 shadow-sm">
                        <strong class="block text-green-600 mb-1">Data Studio</strong>
                        <span class="text-xs text-gray-500">Upload PDFs, websites, or text files to create "Data Stores" that the AI can read and cite (RAG).</span>
                    </div>
                </div>
            </div>

            <!-- Step 5: Help -->
            <div v-if="currentStep === 5" class="space-y-6 animate-fade-in text-center px-4">
                <div class="flex justify-center mb-4">
                    <div class="p-4 bg-green-100 dark:bg-green-900/30 rounded-full text-green-600 shadow-sm">
                        <IconBookOpen class="w-12 h-12" />
                    </div>
                </div>
                <h3 class="text-xl font-bold">Need Help?</h3>
                <p class="text-gray-600 dark:text-gray-300">
                    If you get stuck or want to learn advanced tricks, visit the <strong>Help</strong> section in the sidebar menu.
                </p>
                <div class="mt-8 p-6 bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-100 dark:border-blue-900/40 text-blue-800 dark:text-blue-200 text-sm font-medium">
                    "The only limit is your imagination."
                </div>
            </div>

        </template>
      </div>

      <!-- Navigation Footer -->
      <div class="mt-10 pt-6 border-t dark:border-gray-700 flex justify-between items-center">
          <button 
            v-if="currentStep > 1" 
            @click="prevStep" 
            class="btn btn-secondary flex items-center gap-2 px-6"
          >
            <IconArrowLeft class="w-4 h-4" /> Back
          </button>
          <div v-else class="text-xs font-black uppercase text-gray-400 tracking-[0.2em]">Agreement Phase</div>

          <!-- Progress Indicators -->
          <div class="hidden sm:flex gap-2">
              <div v-for="step in totalSteps" :key="step" 
                class="h-2 rounded-full transition-all duration-500" 
                :class="step === currentStep ? 'bg-blue-600 w-10 shadow-sm shadow-blue-500/50' : (step < currentStep ? 'bg-blue-300 dark:bg-blue-800 w-4' : 'bg-gray-200 dark:bg-gray-700 w-4')">
              </div>
          </div>

          <button 
            @click="nextStep" 
            class="btn btn-primary flex items-center gap-2 px-8 py-3 shadow-xl hover:shadow-2xl hover:scale-105 active:scale-100 transition-all"
          >
            <span v-if="isLastStep">Finish Setup</span>
            <span v-else>Next Step</span>
            <IconCheckCircle v-if="isLastStep" class="w-4 h-4" />
            <IconArrowRight v-else class="w-4 h-4" />
          </button>
      </div>
    </template>
    <template #footer><div></div></template>
  </GenericModal>
</template>

<style scoped>
.animate-fade-in { animation: fadeIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>
