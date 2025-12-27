<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { storeToRefs } from 'pinia';
import GenericModal from './GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import MultiSelectMenu from '../ui/MultiSelectMenu.vue';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import { useAuthStore } from '../../stores/auth';
import { useTasksStore } from '../../stores/tasks';
import useEventBus from '../../services/eventBus';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';

const uiStore = useUiStore();
const dataStore = useDataStore();
const authStore = useAuthStore();
const tasksStore = useTasksStore();
const { on, off } = useEventBus();

const { availableRagStores, availableMcpToolsForSelector } = storeToRefs(dataStore);

const modalProps = computed(() => uiStore.modalData('personalityEditor'));
const personality = computed(() => modalProps.value?.personality);

const getInitialFormState = () => ({
    id: null, name: '', category: '', author: '', description: '',
    prompt_text: '', disclaimer: '', script_code: '', icon_base64: null,
    is_public: false, data_source_type: 'none', data_source: null, active_mcps: [],
    required_context_options: [], // NEW
    owner_type: 'user'
});

const form = ref(getInitialFormState());
const fileInput = ref(null);
const staticTextInputRef = ref(null);
const isLoading = ref(false);
const isLoadingIcon = ref(false);
const formIconLoadFailed = ref(false);
const activeIconTask = ref(null);

const contextOptionChoices = [
    { id: 'image_generation', name: 'Image Generation' },
    { id: 'image_editing', name: 'Image Editing' },
    { id: 'slide_maker', name: 'Slide Maker' },
    { id: 'note_generation', name: 'Note Generation' },
    { id: 'memory', name: 'Long-Term Memory' }
];

// Helper for multi-select - passing flat array directly to fix rendering issue
const formattedContextOptions = computed(() => {
    return contextOptionChoices;
});

watch(() => form.value.icon_base64, () => {
    formIconLoadFailed.value = false;
});

watch(() => personality.value, (newVal) => {
    if (newVal) {
        form.value = { ...getInitialFormState(), ...newVal };
        // Ensure array
        if (!form.value.required_context_options) form.value.required_context_options = [];
    } else {
        form.value = getInitialFormState();
    }
}, { immediate: true, deep: true });

onMounted(() => {
    if(dataStore.availableRagStores.length === 0) dataStore.fetchDataStores();
    if(dataStore.availableMcpToolsForSelector.length === 0) dataStore.fetchMcpTools();
    on('task:completed', handleTaskCompleted);
});

onUnmounted(() => {
    off('task:completed', handleTaskCompleted);
});

function handleTaskCompleted(task) {
    if (activeIconTask.value && task.id === activeIconTask.value) {
        let result = task.result;
        // Safe parsing of result if it's a string
        if (typeof result === 'string') {
            try {
                result = JSON.parse(result);
            } catch (e) {
                console.error("Failed to parse task result JSON", e);
            }
        }

        if (task.status === 'completed' && result?.icon_base64) {
            // FORCE reactivity update by creating a new object
            form.value = { ...form.value, icon_base64: result.icon_base64 };
            formIconLoadFailed.value = false;
            uiStore.addNotification('Icon generated. Don\'t forget to save!', 'success');
        } else if (task.status === 'failed') {
             uiStore.addNotification('Icon generation failed.', 'error');
        }
        isLoadingIcon.value = false;
        activeIconTask.value = null;
    }
}

watch(() => form.value.data_source_type, (newType, oldType) => {
    if (newType !== oldType) {
        form.value.data_source = null;
    }
});


async function handleSubmit() {
    isLoading.value = true;
    try {
        if (form.value.id) {
            await dataStore.updatePersonality(form.value);
        } else {
            await dataStore.addPersonality(form.value);
        }
        uiStore.closeModal('personalityEditor');
    } finally {
        isLoading.value = false;
    }
}

function handleEnhancePrompt() {
    if (!form.value.prompt_text) {
        uiStore.addNotification('Please provide a base prompt to enhance.', 'warning');
        return;
    }
    uiStore.openModal('enhancePersonalityPrompt', {
        prompt_text: form.value.prompt_text,
        onApply: (enhancedPrompt) => {
            form.value.prompt_text = enhancedPrompt;
        }
    });
}

async function handleGenerateIcon() {
    isLoadingIcon.value = true;
    try {
        const name = form.value.name || 'AI Assistant';
        const category = form.value.category || 'General';
        // Take first 100 chars of description to avoid huge prompts, remove newlines
        const desc = form.value.description ? form.value.description.replace(/\n/g, ' ').slice(0, 150) : 'helpful AI assistant';
        
        // Construct a richer prompt that provides context to the image generator
        const prompt = `Profile icon/avatar of ${name}, ${category}. ${desc}. High quality digital art, centered, smooth, professional style.`;

        const task = await dataStore.generatePersonalityIcon(prompt);
        if (task) {
            activeIconTask.value = task.id;
        } else {
            isLoadingIcon.value = false;
        }
    } catch (e) {
        isLoadingIcon.value = false;
    }
}

function triggerFileInput() {
    fileInput.value.click();
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'];
    if (!allowedTypes.includes(file.type)) {
        uiStore.addNotification('Invalid file type. Please select an image.', 'error');
        return;
    }
    
    const reader = new FileReader();
    reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
            const MAX_WIDTH = 128; const MAX_HEIGHT = 128;
            let width = img.width, height = img.height;

            if (width > height) {
                if (width > MAX_WIDTH) { height *= MAX_WIDTH / width; width = MAX_WIDTH; }
            } else {
                if (height > MAX_HEIGHT) { width *= MAX_HEIGHT / height; height = MAX_HEIGHT; }
            }

            const canvas = document.createElement('canvas');
            canvas.width = width; canvas.height = height;
            canvas.getContext('2d').drawImage(img, 0, 0, width, height);
            form.value.icon_base64 = canvas.toDataURL('image/png');
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
    event.target.value = '';
}

function triggerStaticTextImport() {
    staticTextInputRef.value?.click();
}

function handleStaticTextFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        form.value.data_source = e.target.result;
        uiStore.addNotification(`Imported text from ${file.name}`, 'success');
    };
    reader.onerror = (e) => {
        uiStore.addNotification(`Error reading file: ${e.target.error.name}`, 'error');
    };
    reader.readAsText(file);
    event.target.value = '';
}

async function handleExport() {
    if (!form.value.id) return;
    await dataStore.exportPersonality(form.value.id);
}
</script>

<template>
  <GenericModal modal-name="personalityEditor" :title="form.id ? 'Edit Personality' : 'Create Personality'" maxWidthClass="max-w-4xl">
    <template #body>
      <form v-if="personality" @submit.prevent="handleSubmit" class="space-y-6">
        <!-- Icon and Basic Info -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div class="md:col-span-1 flex flex-col items-center">
            <div class="w-24 h-24 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center overflow-hidden mb-2 relative">
              <img v-if="form.icon_base64 && !formIconLoadFailed" :src="form.icon_base64" @error="formIconLoadFailed = true" alt="Icon Preview" class="h-full w-full object-cover">
              <svg v-else class="w-16 h-16 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" /></svg>
               <!-- Spinner Overlay -->
               <div v-if="isLoadingIcon" class="absolute inset-0 bg-black/50 flex items-center justify-center">
                  <svg class="animate-spin h-8 w-8 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
               </div>
            </div>
            <div class="flex gap-2">
                <button @click="triggerFileInput" type="button" class="btn btn-secondary btn-sm">Upload</button>
                <button @click="handleGenerateIcon" type="button" class="btn btn-secondary btn-sm" :disabled="isLoadingIcon">
                    <span v-if="isLoadingIcon">Generating...</span>
                    <span v-else>Generate</span>
                </button>
            </div>
            <input type="file" ref="fileInput" @change="handleFileSelect" class="hidden" accept="image/png, image/jpeg, image/gif, image/webp, image/svg+xml">
          </div>

          <div class="md:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <label for="name" class="block text-sm font-medium">Name</label>
              <input type="text" id="name" v-model="form.name" class="input-field mt-1" required>
            </div>
            <div>
              <label for="category" class="block text-sm font-medium">Category</label>
              <input type="text" id="category" v-model="form.category" class="input-field mt-1">
            </div>
            <div class="sm:col-span-2">
              <label for="author" class="block text-sm font-medium">Author</label>
              <input type="text" id="author" v-model="form.author" class="input-field mt-1" :placeholder="authStore.user.username">
            </div>
          </div>
        </div>
        
        <!-- Owner Type (Admin only for new personalities) -->
        <div v-if="authStore.user.is_admin && !form.id">
            <label for="owner_type" class="block text-sm font-medium">Owner Type</label>
            <select id="owner_type" v-model="form.owner_type" class="input-field mt-1">
                <option value="user">Personal (for me only)</option>
                <option value="system">System (available to all users if public)</option>
            </select>
        </div>

        <!-- Description and Disclaimer -->
        <div>
            <label for="description" class="block text-sm font-medium">Description</label>
            <textarea id="description" v-model="form.description" rows="3" class="input-field mt-1"></textarea>
        </div>
        <div>
            <label for="disclaimer" class="block text-sm font-medium">Disclaimer</label>
            <textarea id="disclaimer" v-model="form.disclaimer" rows="2" class="input-field mt-1"></textarea>
        </div>

        <!-- System Prompt with AI Enhancement -->
        <div>
            <div class="flex items-center justify-between mb-1">
                <label for="prompt" class="block text-sm font-medium">System Prompt</label>
                <button @click="handleEnhancePrompt" type="button" class="btn btn-secondary btn-sm flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.898 20.572L16.5 21.75l-.398-1.178a3.375 3.375 0 00-2.3-2.3L12.75 18l1.178-.398a3.375 3.375 0 002.3-2.3L16.5 14.25l.398 1.178a3.375 3.375 0 002.3 2.3l1.178.398-1.178.398a3.375 3.375 0 00-2.3 2.3z" /></svg>
                    <span>Enhance with AI</span>
                </button>
            </div>
            <CodeMirrorEditor v-model="form.prompt_text" class="h-48" />
        </div>

        <!-- Script Code (Admin only) -->
        <div v-if="authStore.user.is_admin">
            <label for="script_code" class="block text-sm font-medium">Script Code (Python)</label>
            <CodeMirrorEditor v-model="form.script_code" class="h-48 mt-1" language="python" />
        </div>
        
        <!-- Advanced Settings (RAG, MCPs) -->
        <div class="space-y-6 pt-6 border-t dark:border-gray-700">
            <h3 class="text-lg font-medium text-gray-900 dark:text-gray-100">Advanced Settings</h3>
            <!-- RAG Settings -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <label for="data_source_type" class="block text-sm font-medium">Data Source Type</label>
                    <select id="data_source_type" v-model="form.data_source_type" class="input-field mt-1">
                        <option value="none">None</option>
                        <option value="datastore">Data Store</option>
                        <option value="static_text">Static Text</option>
                    </select>
                </div>
                <div v-if="form.data_source_type === 'datastore'">
                    <label for="data_source" class="block text-sm font-medium">Select Data Store</label>
                    <select id="data_source" v-model="form.data_source" class="input-field mt-1">
                        <option :value="null">Select a store</option>
                        <option v-for="store in availableRagStores" :key="store.id" :value="store.id">
                            {{ store.name }}
                        </option>
                    </select>
                </div>
            </div>
            <div v-if="form.data_source_type === 'static_text'">
                <div class="flex items-center justify-between mb-1">
                    <label for="data_source_static" class="block text-sm font-medium">Static Text Content</label>
                    <button @click="triggerStaticTextImport" type="button" class="btn btn-secondary btn-sm">Import from File</button>
                    <input type="file" ref="staticTextInputRef" @change="handleStaticTextFileSelect" class="hidden" accept=".txt,.md,.json,.csv,.py,.js,text/*">
                </div>
                <CodeMirrorEditor v-model="form.data_source" id="data_source_static" class="h-32" />
            </div>

            <!-- Required Context Options (NEW) -->
             <div>
                <label class="block text-sm font-medium mb-1">Mandatory Context Features</label>
                <p class="text-xs text-gray-500 dark:text-gray-400 mb-2">Selecting these will auto-activate them when this personality is used. Disabling them manually later will revert to the default personality.</p>
                 <MultiSelectMenu 
                    v-model="form.required_context_options" 
                    :items="formattedContextOptions"
                    placeholder="Select required features (e.g. Image Gen)"
                    class="mt-1"
                />
            </div>

            <!-- MCP Tools Settings -->
            <div>
                <label class="block text-sm font-medium">Active MCPs</label>
                 <MultiSelectMenu 
                    v-model="form.active_mcps" 
                    :items="availableMcpToolsForSelector"
                    placeholder="Select tools"
                    class="mt-1"
                />
            </div>
        </div>

        <!-- Public Toggle (Admin only) -->
        <div v-if="authStore.user.is_admin" class="flex items-center pt-6 border-t dark:border-gray-700">
            <input id="is_public" type="checkbox" v-model="form.is_public" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
            <label for="is_public" class="ml-2 block text-sm text-gray-900 dark:text-gray-200">Make Public (Available to all users)</label>
        </div>
      </form>
    </template>
    <template #footer>
        <div class="w-full flex justify-between">
            <div class="flex gap-2">
                <button v-if="form.id" @click="handleExport" type="button" class="btn btn-secondary-outline">
                    <IconArrowDownTray class="w-4 h-4 mr-2" />
                    Export
                </button>
            </div>
            <div class="flex gap-2">
                <button @click="uiStore.closeModal('personalityEditor')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" type="button" class="btn btn-primary" :disabled="isLoading">{{ isLoading ? 'Saving...' : 'Save' }}</button>
            </div>
        </div>
    </template>
  </GenericModal>
</template>
