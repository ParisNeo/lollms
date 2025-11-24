<!-- frontend/webui/src/components/modals/ManageModelsModal.vue -->
<template>
    <GenericModal modal-name="manageModels" :title="binding ? `Manage Models for: ${binding.alias}` : 'Manage Models'" maxWidthClass="max-w-5xl">
        <template #body>
            <div v-if="!binding" class="text-center p-8 text-red-500 dark:text-red-400">
                <p>Error: Binding information is missing.</p>
            </div>
            <div v-else-if="isLoading" class="text-center p-8">
                <div class="flex justify-center items-center gap-3">
                    <IconAnimateSpin class="w-6 h-6 text-blue-500" />
                    <p class="font-semibold">Loading models...</p>
                </div>
                <p class="mt-3 text-sm text-gray-500 dark:text-gray-400">
                    Please be patient. The first time a binding is loaded, it may need to download and install large files, which can take a very long time.
                </p>
            </div>
            <div v-else class="flex gap-6 h-[70vh]">
                <!-- Model List -->
                <div class="w-1/3 border-r dark:border-gray-600 pr-4 flex flex-col">
                    <div class="relative mb-2">
                         <input type="text" v-model="searchTerm" placeholder="Search models..." class="input-field w-full pl-10" />
                         <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"><svg class="h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg></div>
                    </div>
                    <div class="overflow-y-auto flex-grow">
                        <ul v-if="filteredModels.length > 0">
                            <li v-for="model in filteredModels" :key="model.original_model_name">
                                <button @click="selectModel(model)"
                                        class="w-full text-left p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-between"
                                        :class="{'bg-blue-100 dark:bg-blue-900/50': selectedModel && selectedModel.original_model_name === model.original_model_name}">
                                    <div class="flex-grow min-w-0">
                                        <p class="font-mono text-sm truncate" :class="{'font-bold': model.alias}">{{ model.alias?.title || model.original_model_name }}</p>
                                        <p v-if="model.alias" class="text-xs text-gray-500 truncate">{{ model.original_model_name }}</p>
                                    </div>
                                    <div class="flex-shrink-0 flex items-center gap-1.5 pl-2">
                                        <span v-if="isBindingDefault(model.original_model_name)" class="tag text-xs bg-blue-100 text-blue-800" title="Binding Default">B</span>
                                        <span v-if="isGlobalDefault(model.original_model_name)" class="tag text-xs bg-green-100 text-green-800" title="Global Default">G</span>
                                    </div>
                                </button>
                            </li>
                        </ul>
                         <div v-else class="text-center text-sm text-gray-500 py-4">No models match your search.</div>
                    </div>
                </div>

                <!-- Alias Form & Default Settings -->
                <div class="w-2/3 overflow-y-auto pr-2">
                    <div v-if="!selectedModel" class="flex items-center justify-center h-full">
                        <p class="text-gray-500">Select a model to configure its alias and defaults.</p>
                    </div>
                    <div v-else>
                        <h3 class="font-semibold mb-4">Editing Alias for: <span class="font-mono text-blue-600 dark:text-blue-400">{{ selectedModel.original_model_name }}</span></h3>
                        <form @submit.prevent="saveAlias" class="space-y-6 pb-6 border-b dark:border-gray-600">

                            <div>
                                <label class="label">Icon</label>
                                <div v-if="isGeneratingIcon" class="mt-1 p-4 text-center bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                                    <IconAnimateSpin class="w-8 h-8 mx-auto text-blue-500" />
                                    <p class="mt-3 font-semibold">Generation in Progress...</p>
                                </div>
                                <div v-else class="mt-1">
                                    <input type="file" ref="fileInput" @change="handleFileChange" class="hidden" accept="image/png, image/jpeg, image/webp">
                                    <div class="group relative w-24 h-24 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 flex items-center justify-center">
                                        <img v-if="form.icon" :src="form.icon" alt="Model Icon" class="w-full h-full object-cover rounded-md">
                                        <IconPhoto v-else class="w-10 h-10 text-gray-400" />

                                        <div class="absolute inset-0 bg-black/60 rounded-md flex items-center justify-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <button @click="triggerFileUpload" type="button" title="Upload Icon" class="p-2 rounded-full bg-white/20 hover:bg-white/40 text-white">
                                                <IconArrowUpTray class="w-6 h-6" />
                                            </button>
                                            <button v-if="isTtiConfigured" @click="generateIcon" type="button" title="Generate Icon with AI" class="p-2 rounded-full bg-white/20 hover:bg-white/40 text-white" :disabled="isSubmittingIconRequest">
                                                <IconAnimateSpin v-if="isSubmittingIconRequest" class="w-6 h-6" />
                                                <IconSparkles v-else class="w-6 h-6" />
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>                            
                            <div>
                                <label for="alias-title" class="label">Alias Title</label>
                                <input id="alias-title" v-model="form.title" type="text" class="input-field" placeholder="e.g., Llama 3 Chat (Fast)">
                            </div>
                            <div>
                                <label for="alias-description" class="label">Description</label>
                                <textarea id="alias-description" v-model="form.description" rows="3" class="input-field" placeholder="A short description of the model's capabilities for users."></textarea>
                            </div>
                            <div v-if="bindingType === 'llm'" class="p-4 border rounded-lg dark:border-gray-700">
                                <h4 class="font-medium mb-4">LLM Generation Parameters</h4>
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div>
                                        <label for="alias-ctx-size" class="label text-xs">Context Size</label>
                                        <div class="flex items-center gap-2">
                                            <input id="alias-ctx-size" v-model="form.ctx_size" type="number" class="input-field" placeholder="e.g., 8192">
                                            <button type="button" @click="fetchCtxSize" class="btn btn-secondary p-2" title="Auto-detect max context size from binding" :disabled="isFetchingCtxSize">
                                                <IconAnimateSpin v-if="isFetchingCtxSize" class="w-5 h-5" />
                                                <IconSparkles v-else class="w-5 h-5"/>
                                            </button>
                                        </div>
                                    </div>
                                    <div><label for="alias-temp" class="label text-xs">Temperature</label><input id="alias-temp" v-model="form.temperature" type="number" step="0.01" class="input-field" placeholder="e.g., 0.7"></div>
                                    <div><label for="alias-top-k" class="label text-xs">Top K</label><input id="alias-top-k" v-model="form.top_k" type="number" class="input-field" placeholder="e.g., 50"></div>
                                    <div><label for="alias-top-p" class="label text-xs">Top P</label><input id="alias-top-p" v-model="form.top_p" type="number" step="0.01" class="input-field" placeholder="e.g., 0.95"></div>
                                    <div><label for="alias-repeat-penalty" class="label text-xs">Repeat Penalty</label><input id="alias-repeat-penalty" v-model="form.repeat_penalty" type="number" step="0.01" class="input-field" placeholder="e.g., 1.1"></div>
                                    <div><label for="alias-repeat-last-n" class="label text-xs">Repeat Last N</label><input id="alias-repeat-last-n" v-model="form.repeat_last_n" type="number" class="input-field" placeholder="e.g., 64"></div>
                                </div>
                                <div class="mt-4 border-t pt-4 dark:border-gray-600">
                                    <h4 class="font-medium mb-2 text-sm">Reasoning Capabilities</h4>
                                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                                            <span class="flex-grow flex flex-col pr-4">
                                                <span class="text-sm font-medium">Enable Reasoning (Thinking)</span>
                                                <span class="text-xs text-gray-500 dark:text-gray-400">Activates thought generation if supported.</span>
                                            </span>
                                            <button @click="form.reasoning_activation = !form.reasoning_activation" type="button" :class="[form.reasoning_activation ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                                <span :class="[form.reasoning_activation ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                            </button>
                                        </div>
                                        <div>
                                            <label for="reasoning-effort" class="label text-xs">Reasoning Effort</label>
                                            <select id="reasoning-effort" v-model="form.reasoning_effort" class="input-field mt-1">
                                                <option :value="null">Default</option>
                                                <option value="low">Low</option>
                                                <option value="medium">Medium</option>
                                                <option value="high">High</option>
                                            </select>
                                        </div>
                                         <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md md:col-span-2">
                                            <span class="flex-grow flex flex-col pr-4">
                                                <span class="text-sm font-medium">Reasoning Summary</span>
                                                <span class="text-xs text-gray-500 dark:text-gray-400">Enable summarization of reasoning steps in output.</span>
                                            </span>
                                            <button @click="form.reasoning_summary = !form.reasoning_summary" type="button" :class="[form.reasoning_summary ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                                <span :class="[form.reasoning_summary ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- TTI/TTS Model Parameters -->
                            <div v-if="['tti', 'tts'].includes(bindingType) && modelParameters.length > 0" class="p-4 border rounded-lg dark:border-gray-700">
                                <h4 class="font-medium mb-4">{{ bindingType.toUpperCase() }} Generation Parameters</h4>
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div v-for="param in modelParameters" :key="param.name">
                                        <label :for="`param-${param.name}`" class="label text-xs">{{ param.title || param.name.replace(/_/g, ' ') }}</label>
                                        <input 
                                            v-if="['str', 'int', 'float'].includes(param.type)"
                                            :type="param.type === 'str' ? 'text' : 'number'"
                                            :step="param.type === 'float' ? '0.1' : '1'"
                                            :id="`param-${param.name}`"
                                            v-model="form[param.name]"
                                            class="input-field mt-1"
                                            :placeholder="param.help || ''"
                                        />
                                        <div v-else-if="param.type === 'bool'" class="mt-1">
                                            <button @click="form[param.name] = !form[param.name]" type="button" :class="[form[param.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                                <span :class="[form[param.name] ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>


                             <div v-if="bindingType === 'llm'" class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                                <span class="flex-grow flex flex-col">
                                    <span class="text-sm font-medium">Vision Support</span>
                                    <span class="text-sm text-gray-500 dark:text-gray-400">Enable if this model can process images.</span>
                                </span>
                                <button @click="form.has_vision = !form.has_vision" type="button" :class="[form.has_vision ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                    <span :class="[form.has_vision ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                            
                             <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                                <span class="flex-grow flex flex-col">
                                    <span class="text-sm font-medium">
                                        <template v-if="bindingType === 'llm'">Lock Context Size</template>
                                        <template v-else>Allow User Overrides</template>
                                    </span>
                                    <span class="text-sm text-gray-500 dark:text-gray-400">
                                        <template v-if="bindingType === 'llm'">If enabled, users cannot override the context size for this model.</template>
                                        <template v-else>If enabled, users can change these generation parameters for their own use.</template>
                                    </span>
                                </span>
                                <button v-if="bindingType === 'llm'" @click="form.ctx_size_locked = !form.ctx_size_locked" type="button" :class="[form.ctx_size_locked ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                    <span :class="[form.ctx_size_locked ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                </button>
                                <button v-else @click="form.allow_parameters_override = !form.allow_parameters_override" type="button" :class="[form.allow_parameters_override ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                    <span :class="[form.allow_parameters_override ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                            
                            <div v-if="bindingType === 'llm'" class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                                <span class="flex-grow flex flex-col">
                                    <span class="text-sm font-medium">Allow User Overrides</span>
                                    <span class="text-sm text-gray-500 dark:text-gray-400">If disabled, all generation parameters above will be forced for this model.</span>
                                </span>
                                <button @click="form.allow_parameters_override = !form.allow_parameters_override" type="button" :class="[form.allow_parameters_override ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                    <span :class="[form.allow_parameters_override ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                </button>
                            </div>

                            <div class="flex justify-end gap-3 pt-4">
                                <button v-if="selectedModel.alias" type="button" @click="deleteAlias" class="btn btn-danger-outline" :disabled="isSaving">Delete Alias</button>
                                <button type="submit" class="btn btn-primary" :disabled="isSaving">{{ isSaving ? 'Saving...' : 'Save Alias' }}</button>
                            </div>
                        </form>

                        <div class="mt-6">
                             <h3 class="font-semibold mb-4">Default Model Settings</h3>
                             <div class="space-y-4">
                                <div class="flex items-center gap-4">
                                    <button @click="setAsBindingDefault" class="btn btn-secondary w-full" :disabled="isCurrentBindingDefault || isSettingBindingDefault">
                                        {{ isSettingBindingDefault ? 'Setting...' : 'Set as Binding Default' }}
                                    </button>
                                    <p v-if="isCurrentBindingDefault" class="text-sm text-green-600 dark:text-green-400 font-medium">✓ Current binding default</p>
                                </div>
                                 <div v-if="bindingType === 'llm'" class="flex items-center gap-4">
                                    <button @click="setAsGlobalDefault" class="btn btn-secondary w-full" :disabled="isCurrentGlobalDefault || isSettingGlobalDefault">
                                        {{ isSettingGlobalDefault ? 'Setting...' : 'Set as Global Default' }}
                                    </button>
                                    <p v-if="isCurrentGlobalDefault" class="text-sm text-green-600 dark:text-green-400 font-medium">✓ Global default for new users</p>
                                </div>
                             </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>
    </GenericModal>
</template>

<script setup>
import { ref, watch, computed, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { useDataStore } from '../../stores/data';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import GenericModal from './GenericModal.vue';
import IconUploader from '../ui/IconUploader.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();
const dataStore = useDataStore();
const tasksStore = useTasksStore();
const { globalSettings, availableBindingTypes, availableTtiBindingTypes, availableTtsBindingTypes, ttiBindings } = storeToRefs(adminStore);
const { tasks } = storeToRefs(tasksStore);

const modalData = computed(() => uiStore.modalData('manageModels'));
const binding = computed(() => modalData.value?.binding);
const bindingType = computed(() => modalData.value?.bindingType);

const isLoading = ref(true);
const isSaving = ref(false);
const isSettingBindingDefault = ref(false);
const isSettingGlobalDefault = ref(false);
const isFetchingCtxSize = ref(false);
const iconGenerationTaskId = ref(null);
const isSubmittingIconRequest = ref(false);
const fileInput = ref(null);

const models = ref([]);
const selectedModel = ref(null);
const searchTerm = ref('');
const modelParameters = ref([]);

const isTtiConfigured = computed(() => ttiBindings.value && ttiBindings.value.some(b => b.is_active));

const getInitialFormState = () => ({
    icon: '',
    title: '',
    name: '', // Added name for backward compatibility and to solve the required field issue
    description: '',
    has_vision: true,
    ctx_size: null,
    ctx_size_locked: false,
    temperature: null,
    top_k: null,
    top_p: null,
    repeat_penalty: null,
    repeat_last_n: null,
    allow_parameters_override: true,
    reasoning_activation: false,
    reasoning_effort: null,
    reasoning_summary: false
});

const form = ref(getInitialFormState());

const currentIconGenerationTask = computed(() => {
    if (!iconGenerationTaskId.value) return null;
    return tasks.value.find(t => t.id === iconGenerationTaskId.value);
});

const isGeneratingIcon = computed(() => {
    if (isSubmittingIconRequest.value) return true;
    return currentIconGenerationTask.value ? ['pending', 'running'].includes(currentIconGenerationTask.value.status) : false;
});

watch(currentIconGenerationTask, (newTask) => {
    if (!newTask) return;
    if (newTask.status === 'completed') {
        let result = newTask.result;
        if (result && typeof result === 'string') { try { result = JSON.parse(result); } catch (e) { /* ignore*/ } }
        let b64 = (result && typeof result === 'object' && result.icon_base64) ? result.icon_base64 : (typeof result === 'string' ? result : null);
        if (b64) {
            form.value.icon = b64.startsWith('data:image') ? b64 : `data:image/png;base64,${b64}`;
            uiStore.addNotification('Icon generated successfully!', 'success');
        } else {
            uiStore.addNotification('Icon generation completed, but no image was returned.', 'warning');
        }
        iconGenerationTaskId.value = null;
    } else if (newTask.status === 'failed' || newTask.status === 'cancelled') {
        uiStore.addNotification(`Icon generation failed: ${newTask.error || 'Unknown error.'}`, 'error');
        iconGenerationTaskId.value = null;
    }
});


const filteredModels = computed(() => {
    if (!searchTerm.value) return models.value;
    const lowerSearch = searchTerm.value.toLowerCase();
    return models.value.filter(m => 
        m.original_model_name.toLowerCase().includes(lowerSearch) || 
        m.alias?.title?.toLowerCase().includes(lowerSearch)
    );
});

const globalDefaultModel = computed(() => {
    const setting = globalSettings.value.find(s => s.key === 'default_lollms_model_name');
    return setting ? setting.value : null;
});

const isCurrentBindingDefault = computed(() => selectedModel.value && binding.value && selectedModel.value.original_model_name === binding.value.default_model_name);
const isCurrentGlobalDefault = computed(() => selectedModel.value && binding.value && `${binding.value.alias}/${selectedModel.value.original_model_name}` === globalDefaultModel.value);
const isBindingDefault = (modelName) => binding.value && modelName === binding.value.default_model_name;
const isGlobalDefault = (modelName) => binding.value && `${binding.value.alias}/${modelName}` === globalDefaultModel.value;

async function fetchModels() {
    if (!binding.value) { isLoading.value = false; models.value = []; return; }
    isLoading.value = true;
    try {
        switch (bindingType.value) {
            case 'llm': models.value = await adminStore.fetchBindingModels(binding.value.id); break;
            case 'tti': models.value = await adminStore.fetchTtiBindingModels(binding.value.id); break;
            case 'tts': models.value = await adminStore.fetchTtsBindingModels(binding.value.id); break;
            case 'stt': models.value = await adminStore.fetchSttBindingModels(binding.value.id); break;
            case 'rag': models.value = await adminStore.fetchRagBindingModels(binding.value.id); break;

            default: models.value = [];
        }
    } finally {
        isLoading.value = false;
    }
}

function selectModel(model) {
    selectedModel.value = model;
    const newForm = { ...getInitialFormState(), ...(model.alias || {}) };
    if (bindingType.value === 'llm' && !newForm.name) {
        newForm.name = newForm.title || model.original_model_name;
    }
    let bindingTypes;
    if (bindingType.value === 'tti') bindingTypes = availableTtiBindingTypes.value;
    else if (bindingType.value === 'tts') bindingTypes = availableTtsBindingTypes.value;
    else if (bindingType.value === 'rag') bindingTypes = adminStore.availableRagBindingTypes;
    else bindingTypes = availableBindingTypes.value; // Fallback for llm
    
    const bindingName = binding.value?.name;
    if (bindingName) {
        const bindingDesc = bindingTypes.find(b => (b.binding_name || b.name) === bindingName);
        const params = bindingDesc?.model_parameters || bindingDesc?.input_parameters || [];
        modelParameters.value = params;
        params.forEach(param => { if (!(param.name in newForm)) newForm[param.name] = param.default; });
    } else {
        modelParameters.value = [];
    }
    
    form.value = newForm;
}

async function fetchCtxSize() {
    if (!selectedModel.value || !binding.value || bindingType.value !== 'llm') return;
    isFetchingCtxSize.value = true;
    try {
        const size = await adminStore.getModelCtxSize(binding.value.id, selectedModel.value.original_model_name);
        if (size !== null) form.value.ctx_size = size;
    } finally {
        isFetchingCtxSize.value = false;
    }
}

async function generateIcon() {
    if (!form.value.title && !selectedModel.value.original_model_name) {
        uiStore.addNotification('Please provide an Alias Title to generate an icon.', 'warning');
        return;
    }
    isSubmittingIconRequest.value = true;
    iconGenerationTaskId.value = null; 
    try {
        const modelIdentifier = form.value.title || selectedModel.value.original_model_name;
        const prompt = `a high-quality, abstract, minimalist, vector logo for an AI model named "${modelIdentifier}". Description: ${form.value.description || 'General purpose model.'}`;
        const task = await adminStore.generateIconForModel(prompt);
        if (task?.id) {
            iconGenerationTaskId.value = task.id;
            uiStore.addNotification('Icon generation started...', 'info');
        }
    } finally {
        isSubmittingIconRequest.value = false;
    }
}

async function saveAlias() {
    if (!selectedModel.value || !binding.value) return;
    isSaving.value = true;
    try {
        const payload = { ...form.value };
        let aliasPayload = {};

        if (bindingType.value === 'llm') {
            if (payload.title) payload.name = payload.title;
            ['ctx_size', 'temperature', 'top_k', 'top_p', 'repeat_penalty', 'repeat_last_n'].forEach(key => {
                const value = payload[key];
                payload[key] = (value === '' || value === null || isNaN(parseFloat(value))) ? null : Number(value);
            });
            aliasPayload = { original_model_name: selectedModel.value.original_model_name, alias: payload };
            await adminStore.saveModelAlias(binding.value.id, aliasPayload);
        } else {
            modelParameters.value.forEach(param => {
                if (['int', 'float'].includes(param.type)) {
                    const value = payload[param.name];
                    payload[param.name] = (value === '' || value === null || isNaN(parseFloat(value))) ? null : Number(value);
                }
            });
            aliasPayload = { original_model_name: selectedModel.value.original_model_name, alias: payload };
            if (bindingType.value === 'tti') await adminStore.saveTtiModelAlias(binding.value.id, aliasPayload);
            else if (bindingType.value === 'tts') await adminStore.saveTtsModelAlias(binding.value.id, aliasPayload);
            else if (bindingType.value === 'stt') await adminStore.saveSttModelAlias(binding.value.id, aliasPayload);
            else if (bindingType.value === 'rag') await adminStore.saveRagModelAlias(binding.value.id, aliasPayload);
        }
        await fetchModels();
        const updatedModel = models.value.find(m => m.original_model_name === selectedModel.value.original_model_name);
        if (updatedModel) selectModel(updatedModel);
    } finally {
        isSaving.value = false;
    }
}

async function deleteAlias() {
    if (!selectedModel.value?.alias || !binding.value) return;
    if (await uiStore.showConfirmation({ title: 'Delete Alias?', message: `Delete the alias for '${selectedModel.value.original_model_name}'?`, confirmText: 'Delete' })) {
        isSaving.value = true;
        try {
            switch (bindingType.value) {
                case 'llm': await adminStore.deleteModelAlias(binding.value.id, selectedModel.value.original_model_name); break;
                case 'tti': await adminStore.deleteTtiModelAlias(binding.value.id, selectedModel.value.original_model_name); break;
                case 'tts': await adminStore.deleteTtsModelAlias(binding.value.id, selectedModel.value.original_model_name); break;
                case 'rag': await adminStore.deleteRagModelAlias(binding.value.id, selectedModel.value.original_model_name); break;
            }
            await fetchModels();
            const updatedModel = models.value.find(m => m.original_model_name === selectedModel.value.original_model_name);
            selectModel(updatedModel || models.value[0] || null);
        } finally {
            isSaving.value = false;
        }
    }
}

async function setAsBindingDefault() {
    if (!selectedModel.value || !binding.value) return;
    isSettingBindingDefault.value = true;
    try {
        const payload = { default_model_name: selectedModel.value.original_model_name };
        switch (bindingType.value) {
            case 'llm': await adminStore.updateBinding(binding.value.id, payload); break;
            case 'tti': await adminStore.updateTtiBinding(binding.value.id, payload); break;
            case 'tts': await adminStore.updateTtsBinding(binding.value.id, payload); break;
            // RAG bindings do not have a default model concept
        }
        uiStore.addNotification('Binding default model updated.', 'success');
    } finally {
        isSettingBindingDefault.value = false;
    }
}

async function setAsGlobalDefault() {
    if (!selectedModel.value || !binding.value || bindingType.value !== 'llm') return;
    isSettingGlobalDefault.value = true;
    try {
        const fullModelName = `${binding.value.alias}/${selectedModel.value.original_model_name}`;
        await adminStore.updateGlobalSettings({ 'default_lollms_model_name': fullModelName });
        uiStore.addNotification('Global default model for new users has been updated.', 'success');
    } finally {
        isSettingGlobalDefault.value = false;
    }
}

function triggerFileUpload() {
    fileInput.value.click();
}

function handleFileChange(event) {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { uiStore.addNotification('File is too large (max 5MB).', 'error'); return; }
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { uiStore.addNotification('Invalid file type. Use JPG, PNG, or WEBP.', 'error'); return; }
    const reader = new FileReader();
    reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
            const canvas = document.createElement('canvas'), MAX_DIM = 128;
            let { width, height } = img;
            if (width > height) { if (width > MAX_DIM) { height *= MAX_DIM / width; width = MAX_DIM; } }
            else { if (height > MAX_DIM) { width *= MAX_DIM / height; height = MAX_DIM; } }
            canvas.width = width;
            canvas.height = height;
            canvas.getContext('2d').drawImage(img, 0, 0, width, height);
            form.value.icon = canvas.toDataURL('image/png');
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
    event.target.value = '';
}

onMounted(() => {
    adminStore.fetchGlobalSettings();
    adminStore.fetchAvailableBindingTypes();
    adminStore.fetchAvailableTtiBindingTypes();
    adminStore.fetchAvailableTtsBindingTypes();
    adminStore.fetchTtiBindings();
});

watch(binding, (newBinding) => {
    if (newBinding) {
        selectedModel.value = null;
        form.value = getInitialFormState();
        fetchModels();
    } else {
        models.value = [];
        isLoading.value = true;
    }
}, { immediate: true });
</script>
