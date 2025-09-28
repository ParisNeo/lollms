<template>
    <GenericModal modal-name="manageModels" :title="binding ? `Manage Models for: ${binding.alias}` : 'Manage Models'" maxWidthClass="max-w-5xl">
        <template #body>
            <div v-if="!binding" class="text-center p-8 text-red-500 dark:text-red-400">
                <p>Error: Binding information is missing.</p>
            </div>
            <div v-else-if="isLoading" class="text-center p-8">
                <p>Loading models...</p>
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
                                <label for="alias-title" class="label">Alias Title</label>
                                <input id="alias-title" v-model="form.title" type="text" class="input-field" placeholder="e.g., Llama 3 Chat (Fast)">
                            </div>
                            <div>
                                <label for="alias-description" class="label">Description</label>
                                <textarea id="alias-description" v-model="form.description" rows="3" class="input-field" placeholder="A short description of the model's capabilities for users."></textarea>
                            </div>
                            
                            <div>
                                <div v-if="isGeneratingIcon" class="p-4 text-center bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                                    <IconAnimateSpin class="w-8 h-8 mx-auto text-blue-500" />
                                    <p class="mt-3 font-semibold">Generation in Progress...</p>
                                    <p v-if="currentIconGenerationTask" class="text-sm text-gray-500 mt-1">{{ currentIconGenerationTask.description }}</p>
                                    <div v-if="currentIconGenerationTask" class="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-600 mt-3">
                                        <div class="bg-blue-600 h-2.5 rounded-full" :style="{ width: currentIconGenerationTask.progress + '%' }"></div>
                                    </div>
                                    <p v-if="currentIconGenerationTask" class="text-xs text-gray-500 mt-1">{{ currentIconGenerationTask.progress }}%</p>
                                </div>
                                <div v-else class="flex items-end gap-4">
                                    <IconUploader v-model="form.icon" label="Icon" />
                                    <button @click="generateIcon" type="button" class="btn btn-secondary flex items-center gap-2" :disabled="isSubmittingIconRequest">
                                        <IconAnimateSpin v-if="isSubmittingIconRequest" class="w-5 h-5" />
                                        <IconSparkles v-else class="w-5 h-5" />
                                        <span>Generate</span>
                                    </button>
                                </div>
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

const uiStore = useUiStore();
const adminStore = useAdminStore();
const dataStore = useDataStore();
const tasksStore = useTasksStore();
const { globalSettings, availableBindingTypes, availableTtiBindingTypes, availableTtsBindingTypes } = storeToRefs(adminStore);
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

const models = ref([]);
const selectedModel = ref(null);
const searchTerm = ref('');
const modelParameters = ref([]);

const getInitialFormState = () => ({
    icon: '',
    title: '',
    description: '',
    has_vision: true,
    ctx_size: null,
    ctx_size_locked: false,
    temperature: null,
    top_k: null,
    top_p: null,
    repeat_penalty: null,
    repeat_last_n: null,
    allow_parameters_override: true
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
    console.log("[ManageModelsModal] DEBUG: Watching task update:", JSON.parse(JSON.stringify(newTask)));

    if (newTask.status === 'completed') {
        let result = newTask.result;
        console.log("[ManageModelsModal] DEBUG: Task completed. Raw result:", result);
        
        // Safely parse if result is a stringified JSON
        if (result && typeof result === 'string') {
            try {
                result = JSON.parse(result);
                console.log("[ManageModelsModal] DEBUG: Parsed task result:", result);
            } catch (e) {
                console.warn("[ManageModelsModal] Task result is a non-JSON string, trying to use as raw value:", result);
            }
        }
        
        let b64 = null;
        if (result && typeof result === 'object' && result.icon_base64) {
            b64 = result.icon_base64;
            console.log("[ManageModelsModal] DEBUG: Extracted icon_base64 from object.");
        } else if (typeof result === 'string') {
            // Fallback for raw base64 string
            b64 = result;
            console.log("[ManageModelsModal] DEBUG: Using raw string as base64.");
        }
        
        if (b64) {
            // Ensure it has the correct data URI prefix
            const finalIconValue = b64.startsWith('data:image') ? b64 : `data:image/png;base64,${b64}`;
            form.value.icon = finalIconValue;
            console.log("[ManageModelsModal] DEBUG: Setting form icon to:", finalIconValue.substring(0, 60) + "...");
            uiStore.addNotification('Icon generated successfully!', 'success');
        } else {
            console.log("[ManageModelsModal] DEBUG: Icon generation completed, but no image was returned in the result.");
            uiStore.addNotification('Icon generation completed, but no image was returned.', 'warning');
        }
        iconGenerationTaskId.value = null; // Reset for next generation
    } else if (newTask.status === 'failed' || newTask.status === 'cancelled') {
        console.log("[ManageModelsModal] DEBUG: Icon generation task failed or was cancelled.", newTask);
        uiStore.addNotification(`Icon generation failed: ${newTask.error || 'Unknown error.'}`, 'error');
        iconGenerationTaskId.value = null; // Reset
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
            case 'llm':
                models.value = await adminStore.fetchBindingModels(binding.value.id);
                break;
            case 'tti':
                models.value = await adminStore.fetchTtiBindingModels(binding.value.id);
                break;
            case 'tts':
                models.value = await adminStore.fetchTtsBindingModels(binding.value.id);
                break;
            default:
                models.value = [];
        }
    } finally {
        isLoading.value = false;
    }
}

function selectModel(model) {
    selectedModel.value = model;
    const newForm = { ...getInitialFormState(), ...(model.alias || {}) };
    
    let bindingTypes;
    if (bindingType.value === 'tti') bindingTypes = availableTtiBindingTypes.value;
    else if (bindingType.value === 'tts') bindingTypes = availableTtsBindingTypes.value;
    else bindingTypes = availableBindingTypes.value;

    const bindingDesc = bindingTypes.find(b => b.binding_name === binding.value.name);
    const params = bindingDesc?.model_parameters || [];
    modelParameters.value = params;

    params.forEach(param => {
        if (!(param.name in newForm)) {
            newForm[param.name] = param.default;
        }
    });

    form.value = newForm;
}

async function fetchCtxSize() {
    if (!selectedModel.value || !binding.value || bindingType.value !== 'llm') return;
    isFetchingCtxSize.value = true;
    try {
        const size = await adminStore.getModelCtxSize(binding.value.id, selectedModel.value.original_model_name);
        if (size !== null) {
            form.value.ctx_size = size;
        }
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
        if (task && task.id) {
            iconGenerationTaskId.value = task.id;
            console.log(`[ManageModelsModal] DEBUG: Icon generation task submitted with ID: ${task.id}`);
            uiStore.addNotification('Icon generation started...', 'info');
        } else {
            console.error("[ManageModelsModal] DEBUG: Failed to get a task ID from the backend.");
        }
    } catch (error) {
        console.error("[ManageModelsModal] DEBUG: Error submitting icon generation task:", error);
        // error is handled by the global interceptor
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
            ['ctx_size', 'temperature', 'top_k', 'top_p', 'repeat_penalty', 'repeat_last_n'].forEach(key => {
                const value = payload[key];
                payload[key] = (value === '' || value === null || isNaN(parseFloat(value))) ? null : Number(value);
            });
            aliasPayload = { original_model_name: selectedModel.value.original_model_name, alias: payload };
            await adminStore.saveModelAlias(binding.value.id, aliasPayload);
        } else { // For TTI and TTS
            modelParameters.value.forEach(param => {
                if (['int', 'float'].includes(param.type)) {
                    const value = payload[param.name];
                    payload[param.name] = (value === '' || value === null || isNaN(parseFloat(value))) ? null : Number(value);
                }
            });
            aliasPayload = { original_model_name: selectedModel.value.original_model_name, alias: payload };
            if (bindingType.value === 'tti') {
                await adminStore.saveTtiModelAlias(binding.value.id, aliasPayload);
            } else if (bindingType.value === 'tts') {
                await adminStore.saveTtsModelAlias(binding.value.id, aliasPayload);
            }
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
    const confirmed = await uiStore.showConfirmation({
        title: 'Delete Alias?',
        message: `Are you sure you want to delete the alias for '${selectedModel.value.original_model_name}'?`,
        confirmText: 'Delete'
    });
    if (confirmed) {
        isSaving.value = true;
        try {
            switch (bindingType.value) {
                case 'llm': await adminStore.deleteModelAlias(binding.value.id, selectedModel.value.original_model_name); break;
                case 'tti': await adminStore.deleteTtiModelAlias(binding.value.id, selectedModel.value.original_model_name); break;
                case 'tts': await adminStore.deleteTtsModelAlias(binding.value.id, selectedModel.value.original_model_name); break;
            }
            await fetchModels();
            const updatedModel = models.value.find(m => m.original_model_name === selectedModel.value.original_model_name);
            selectModel(updatedModel || (models.value.length > 0 ? models.value[0] : null));
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

onMounted(() => {
    adminStore.fetchGlobalSettings();
    adminStore.fetchAvailableBindingTypes();
    adminStore.fetchAvailableTtiBindingTypes();
    adminStore.fetchAvailableTtsBindingTypes();
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