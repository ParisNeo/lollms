<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useNotebookStore } from '../../stores/notebooks';
import { useAuthStore } from '../../stores/auth';
import GenericModal from './GenericModal.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconSpeakerWave from '../../assets/icons/IconSpeakerWave.vue';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const notebookStore = useNotebookStore();
const authStore = useAuthStore();

const user = computed(() => authStore.user);

// Capabilities check
const hasLLM = computed(() => !!user.value?.lollms_model_name);
const hasTTI = computed(() => !!user.value?.tti_binding_model_name);
const hasTTS = computed(() => !!user.value?.tts_binding_model_name);
const hasVideo = computed(() => false); // Placeholder

const steps = ['Select Type', 'Add Sources', 'Describe Concept', 'Review Structure'];
const currentStep = ref(0);
const isLoading = ref(false);

const formData = ref({
    type: 'generic',
    title: '',
    prompt: '',
    files: [],
    urls: [],
    structure: [] 
});

const notebookTypes = computed(() => [
    { 
        id: 'generic', 
        name: 'Empty Notebook', 
        desc: 'Standard multi-tab scratchpad.', 
        icon: IconFileText, 
        available: true 
    },
    { 
        id: 'report', 
        name: 'Report / Article', 
        desc: 'Structured long-form document with sections.', 
        icon: IconBookOpen, 
        available: hasLLM.value 
    },
    { 
        id: 'presentation', 
        name: 'Presentation', 
        desc: 'Slide deck with text and generated visuals.', 
        icon: IconPhoto, 
        available: hasLLM.value && hasTTI.value 
    },
    { 
        id: 'audiobook', 
        name: 'Audio Book / Podcast', 
        desc: 'Script generation with TTS audio.', 
        icon: IconSpeakerWave, 
        available: hasLLM.value && hasTTS.value 
    },
    { 
        id: 'video', 
        name: 'Video', 
        desc: 'Video content generation.', 
        icon: IconVideoCamera, 
        available: hasVideo.value 
    }
]);

const fileInput = ref(null);
const urlInput = ref('');

function selectType(typeId) {
    formData.value.type = typeId;
    if (typeId === 'generic') {
        createNotebook(); 
    } else {
        currentStep.value = 1;
    }
}

function handleFileUpload(e) {
    const files = Array.from(e.target.files);
    formData.value.files.push(...files);
}

function addUrl() {
    if (urlInput.value.trim()) {
        formData.value.urls.push(urlInput.value.trim());
        urlInput.value = '';
    }
}

function removeFile(index) {
    formData.value.files.splice(index, 1);
}

function removeUrl(index) {
    formData.value.urls.splice(index, 1);
}

async function generateStructure() {
    if (!formData.value.prompt.trim()) {
        uiStore.addNotification("Please describe what you want to build.", "warning");
        return;
    }
    
    isLoading.value = true;
    try {
        const structure = await notebookStore.generateNotebookStructure({
            type: formData.value.type,
            prompt: formData.value.prompt,
            urls: formData.value.urls,
            files: formData.value.files
        });
        formData.value.structure = structure;
        formData.value.title = formData.value.title || "My New Project"; 
        currentStep.value = 3;
    } catch (e) {
        console.error(e);
        uiStore.addNotification("Failed to generate structure.", "error");
    } finally {
        isLoading.value = false;
    }
}

async function createNotebook() {
    isLoading.value = true;
    try {
        const newNotebook = await notebookStore.createStructuredNotebook({
            title: formData.value.title || 'Untitled Notebook',
            type: formData.value.type,
            structure: formData.value.structure,
            initialPrompt: formData.value.prompt,
            files: formData.value.files,
            urls: formData.value.urls
        });
        
        uiStore.closeModal('notebookWizard');
        // Reset form
        formData.value = { type: 'generic', title: '', prompt: '', files: [], urls: [], structure: [] };
        currentStep.value = 0;
        
        if (newNotebook) {
            notebookStore.selectNotebook(newNotebook.id);
        }
    } catch (e) {
        console.error(e);
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal modalName="notebookWizard" title="Create New Notebook" maxWidthClass="max-w-4xl">
        <template #body>
            <div class="flex justify-center mb-8" v-if="formData.type !== 'generic' && currentStep > 0">
                <div v-for="(step, index) in steps" :key="index" class="flex items-center">
                    <div class="flex flex-col items-center">
                        <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors"
                             :class="currentStep >= index ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'">
                            {{ index + 1 }}
                        </div>
                        <span class="text-[10px] mt-1 uppercase font-bold" :class="currentStep >= index ? 'text-blue-600' : 'text-gray-400'">{{ step }}</span>
                    </div>
                    <div v-if="index < steps.length - 1" class="w-12 h-0.5 mx-2" :class="currentStep > index ? 'bg-blue-600' : 'bg-gray-200'"></div>
                </div>
            </div>

            <!-- STEP 0: TYPE SELECTION -->
            <div v-if="currentStep === 0" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <button v-for="type in notebookTypes" :key="type.id" 
                    @click="selectType(type.id)"
                    :disabled="!type.available"
                    class="flex flex-col items-center p-6 border rounded-xl hover:shadow-lg transition-all text-center group disabled:opacity-50 disabled:cursor-not-allowed"
                    :class="formData.type === type.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-blue-300'"
                >
                    <component :is="type.icon" class="w-10 h-10 mb-3 text-gray-500 group-hover:text-blue-500" :class="{'text-blue-600': formData.type === type.id}" />
                    <h3 class="font-bold text-gray-900 dark:text-white">{{ type.name }}</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{{ type.desc }}</p>
                    <span v-if="!type.available" class="mt-2 px-2 py-0.5 bg-red-100 text-red-600 text-[10px] rounded uppercase font-bold">Missing Models</span>
                </button>
            </div>

            <!-- STEP 1: SOURCES -->
            <div v-if="currentStep === 1" class="space-y-6">
                <div class="bg-blue-50 dark:bg-blue-900/10 p-4 rounded-lg border border-blue-100 dark:border-blue-800">
                    <h3 class="font-bold text-sm mb-2 text-blue-800 dark:text-blue-300">Add Context Sources</h3>
                    <p class="text-xs text-gray-600 dark:text-gray-400">Upload documents or add links. The AI will read these to build your content.</p>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label class="label">Files</label>
                        <div class="mt-1 flex items-center gap-2">
                            <button @click="fileInput.click()" class="btn btn-secondary btn-sm">Choose Files</button>
                            <input type="file" multiple ref="fileInput" class="hidden" @change="handleFileUpload">
                        </div>
                        <ul class="mt-2 space-y-1">
                            <li v-for="(file, idx) in formData.files" :key="idx" class="flex justify-between items-center text-xs bg-gray-100 dark:bg-gray-800 p-2 rounded">
                                <span class="truncate">{{ file.name }}</span>
                                <button @click="removeFile(idx)" class="text-red-500 hover:text-red-700">&times;</button>
                            </li>
                        </ul>
                    </div>
                    <div>
                        <label class="label">URLs</label>
                        <div class="mt-1 flex gap-2">
                            <input v-model="urlInput" @keyup.enter="addUrl" type="text" class="input-field flex-grow" placeholder="https://...">
                            <button @click="addUrl" class="btn btn-secondary btn-sm">Add</button>
                        </div>
                        <ul class="mt-2 space-y-1">
                            <li v-for="(url, idx) in formData.urls" :key="idx" class="flex justify-between items-center text-xs bg-gray-100 dark:bg-gray-800 p-2 rounded">
                                <span class="truncate">{{ url }}</span>
                                <button @click="removeUrl(idx)" class="text-red-500 hover:text-red-700">&times;</button>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>

            <!-- STEP 2: CONCEPT -->
            <div v-if="currentStep === 2" class="space-y-4">
                <div>
                    <label class="label">Project Title</label>
                    <input v-model="formData.title" type="text" class="input-field w-full" placeholder="e.g. Q4 Marketing Report">
                </div>
                <div>
                    <label class="label">Concept / Prompt</label>
                    <p class="text-xs text-gray-500 mb-1">Describe the structure and content you want.</p>
                    <textarea v-model="formData.prompt" class="input-field w-full h-32" placeholder="Describe your project..."></textarea>
                </div>
            </div>

            <!-- STEP 3: STRUCTURE REVIEW -->
            <div v-if="currentStep === 3" class="space-y-4">
                <div class="flex justify-between items-center">
                    <h3 class="font-bold">Proposed Structure</h3>
                    <button @click="generateStructure" class="text-xs text-blue-500 hover:underline">Regenerate</button>
                </div>
                <div class="bg-gray-50 dark:bg-gray-800 rounded border dark:border-gray-700 max-h-64 overflow-y-auto p-2 space-y-2">
                    <div v-for="(item, idx) in formData.structure" :key="idx" class="flex items-center gap-2 p-2 bg-white dark:bg-gray-700 rounded shadow-sm border border-gray-100 dark:border-gray-600">
                        <span class="text-xs font-mono text-gray-400 w-6">{{ idx + 1 }}.</span>
                        <input v-model="item.title" class="flex-grow bg-transparent border-none text-sm font-bold focus:ring-0 p-0" />
                        <span class="text-[10px] uppercase bg-gray-200 dark:bg-gray-600 px-1.5 py-0.5 rounded text-gray-600 dark:text-gray-300">{{ item.type }}</span>
                    </div>
                </div>
            </div>

        </template>

        <template #footer>
            <div class="flex justify-between w-full">
                <button v-if="currentStep > 0" @click="currentStep--" class="btn btn-secondary">Back</button>
                <div v-else></div>

                <div class="flex gap-2">
                    <button @click="uiStore.closeModal('notebookWizard')" class="btn btn-secondary">Cancel</button>
                    
                    <button v-if="currentStep === 1 || currentStep === 2" @click="currentStep === 2 ? generateStructure() : currentStep++" class="btn btn-primary" :disabled="isLoading">
                        <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                        {{ currentStep === 2 ? 'Generate Structure' : 'Next' }}
                    </button>
                    
                    <button v-if="currentStep === 3" @click="createNotebook" class="btn btn-primary" :disabled="isLoading">
                        <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                        Create Notebook
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>
