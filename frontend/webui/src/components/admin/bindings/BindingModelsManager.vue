<!-- [UPDATE] frontend/webui/src/components/admin/bindings/BindingModelsManager.vue -->
<script setup>
import { ref, watch, computed, onMounted } from 'vue';
import { useUiStore } from '../../../stores/ui';
import { useAdminStore } from '../../../stores/admin';
import { useDataStore } from '../../../stores/data';
import { useTasksStore } from '../../../stores/tasks';
import { storeToRefs } from 'pinia';
import IconUploader from '../../ui/IconUploader.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconArrowUpTray from '../../../assets/icons/IconArrowUpTray.vue';
import IconPhoto from '../../../assets/icons/IconPhoto.vue';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconEye from '../../../assets/icons/IconEye.vue';

const props = defineProps({
    binding: { type: Object, required: true },
    bindingType: { type: String, required: true } // 'llm', 'tti', 'tts', 'stt', 'ttv', 'ttm', 'rag'
});

const uiStore = useUiStore();
const adminStore = useAdminStore();
const dataStore = useDataStore();
const tasksStore = useTasksStore();
const { globalSettings, availableBindingTypes, availableTtiBindingTypes, availableTtsBindingTypes, availableTtvBindingTypes, availableTtmBindingTypes, ttiBindings } = storeToRefs(adminStore);
const { tasks } = storeToRefs(tasksStore);

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
    name: '',
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

const isCurrentBindingDefault = computed(() => selectedModel.value && props.binding && selectedModel.value.original_model_name === props.binding.default_model_name);
const isCurrentGlobalDefault = computed(() => selectedModel.value && props.binding && `${props.binding.alias}/${selectedModel.value.original_model_name}` === globalDefaultModel.value);
const isBindingDefault = (modelName) => props.binding && modelName === props.binding.default_model_name;
const isGlobalDefault = (modelName) => props.binding && `${props.binding.alias}/${modelName}` === globalDefaultModel.value;

async function fetchModels() {
    if (!props.binding) { isLoading.value = false; models.value = []; return; }
    isLoading.value = true;
    try {
        switch (props.bindingType) {
            case 'llm': models.value = await adminStore.fetchBindingModels(props.binding.id); break;
            case 'tti': models.value = await adminStore.fetchTtiBindingModels(props.binding.id); break;
            case 'tts': models.value = await adminStore.fetchTtsBindingModels(props.binding.id); break;
            case 'stt': models.value = await adminStore.fetchSttBindingModels(props.binding.id); break;
            case 'ttv': models.value = await adminStore.fetchTtvBindingModels(props.binding.id); break;
            case 'ttm': models.value = await adminStore.fetchTtmBindingModels(props.binding.id); break;
            case 'rag': models.value = await adminStore.fetchRagBindingModels(props.binding.id); break;

            default: models.value = [];
        }
    } finally {
        isLoading.value = false;
    }
}

function selectModel(model) {
    selectedModel.value = model;
    const newForm = { ...getInitialFormState(), ...(model.alias || {}) };
    if (props.bindingType === 'llm' && !newForm.name) {
        newForm.name = newForm.title || model.original_model_name;
    }
    let bindingTypes;
    if (props.bindingType === 'tti') bindingTypes = availableTtiBindingTypes.value;
    else if (props.bindingType === 'tts') bindingTypes = availableTtsBindingTypes.value;
    else if (props.bindingType === 'ttv') bindingTypes = availableTtvBindingTypes.value;
    else if (props.bindingType === 'ttm') bindingTypes = availableTtmBindingTypes.value;
    else if (props.bindingType === 'rag') bindingTypes = adminStore.availableRagBindingTypes;
    else bindingTypes = availableBindingTypes.value; 
    
    const bindingName = props.binding?.name;
    if (bindingName) {
        const bindingDesc = bindingTypes.find(b => (b.binding_name || b.name) === bindingName);
        const params = bindingDesc?.model_parameters || [];
        modelParameters.value = params;
        params.forEach(param => { if (!(param.name in newForm)) newForm[param.name] = param.default; });
    } else {
        modelParameters.value = [];
    }
    
    form.value = newForm;
}

async function fetchCtxSize() {
    if (!selectedModel.value || !props.binding || props.bindingType !== 'llm') return;
    isFetchingCtxSize.value = true;
    try {
        const size = await adminStore.getModelCtxSize(props.binding.id, selectedModel.value.original_model_name);
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
    if (!selectedModel.value || !props.binding) return;
    isSaving.value = true;
    try {
        const payload = { ...form.value };
        let aliasPayload = {};

        if (props.bindingType === 'llm') {
            if (payload.title) payload.name = payload.title;
            ['ctx_size', 'temperature', 'top_k', 'top_p', 'repeat_penalty', 'repeat_last_n'].forEach(key => {
                const value = payload[key];
                payload[key] = (value === '' || value === null || isNaN(parseFloat(value))) ? null : Number(value);
            });
             modelParameters.value.forEach(param => {
                if (['int', 'float'].includes(param.type)) {
                    const value = payload[param.name];
                    payload[param.name] = (value === '' || value === null || isNaN(parseFloat(value))) ? null : Number(value);
                }
            });
            aliasPayload = { original_model_name: selectedModel.value.original_model_name, alias: payload };
            await adminStore.saveModelAlias(props.binding.id, aliasPayload);
        } else {
            modelParameters.value.forEach(param => {
                if (['int', 'float'].includes(param.type)) {
                    const value = payload[param.name];
                    payload[param.name] = (value === '' || value === null || isNaN(parseFloat(value))) ? null : Number(value);
                }
            });
            aliasPayload = { original_model_name: selectedModel.value.original_model_name, alias: payload };
            
            if (props.bindingType === 'tti') await adminStore.saveTtiModelAlias(props.binding.id, aliasPayload);
            else if (props.bindingType === 'tts') await adminStore.saveTtsModelAlias(props.binding.id, aliasPayload);
            else if (props.bindingType === 'stt') await adminStore.saveSttModelAlias(props.binding.id, aliasPayload);
            else if (props.bindingType === 'ttv') await adminStore.saveTtvModelAlias(props.binding.id, aliasPayload);
            else if (props.bindingType === 'ttm') await adminStore.saveTtmModelAlias(props.binding.id, aliasPayload);
            else if (props.bindingType === 'rag') await adminStore.saveRagModelAlias(props.binding.id, aliasPayload);
        }
        await fetchModels();
        const updatedModel = models.value.find(m => m.original_model_name === selectedModel.value.original_model_name);
        if (updatedModel) selectModel(updatedModel);
        uiStore.addNotification('Alias saved.', 'success');
    } finally {
        isSaving.value = false;
    }
}

async function deleteAlias() {
    if (!selectedModel.value?.alias || !props.binding) return;
    if (await uiStore.showConfirmation({ title: 'Delete Alias?', message: `Delete the alias for '${selectedModel.value.original_model_name}'?`, confirmText: 'Delete' })) {
        isSaving.value = true;
        try {
            switch (props.bindingType) {
                case 'llm': await adminStore.deleteModelAlias(props.binding.id, selectedModel.value.original_model_name); break;
                case 'tti': await adminStore.deleteTtiModelAlias(props.binding.id, selectedModel.value.original_model_name); break;
                case 'tts': await adminStore.deleteTtsModelAlias(props.binding.id, selectedModel.value.original_model_name); break;
                case 'stt': await adminStore.deleteSttModelAlias(props.binding.id, selectedModel.value.original_model_name); break;
                case 'ttv': await adminStore.deleteTtvModelAlias(props.binding.id, selectedModel.value.original_model_name); break;
                case 'ttm': await adminStore.deleteTtmModelAlias(props.binding.id, selectedModel.value.original_model_name); break;
                case 'rag': await adminStore.deleteRagModelAlias(props.binding.id, selectedModel.value.original_model_name); break;
            }
            await fetchModels();
            const updatedModel = models.value.find(m => m.original_model_name === selectedModel.value.original_model_name);
            selectModel(updatedModel || models.value[0] || null);
            uiStore.addNotification('Alias deleted.', 'success');
        } finally {
            isSaving.value = false;
        }
    }
}

async function setAsBindingDefault() {
    if (!selectedModel.value || !props.binding) return;
    isSettingBindingDefault.value = true;
    try {
        const payload = { default_model_name: selectedModel.value.original_model_name };
        switch (props.bindingType) {
            case 'llm': await adminStore.updateBinding(props.binding.id, payload); break;
            case 'tti': await adminStore.updateTtiBinding(props.binding.id, payload); break;
            case 'tts': await adminStore.updateTtsBinding(props.binding.id, payload); break;
            case 'stt': await adminStore.updateSttBinding(props.binding.id, payload); break;
            case 'ttv': await adminStore.updateTtvBinding(props.binding.id, payload); break;
            case 'ttm': await adminStore.updateTtmBinding(props.binding.id, payload); break;
        }
        uiStore.addNotification('Binding default model updated.', 'success');
    } finally {
        isSettingBindingDefault.value = false;
    }
}

async function setAsGlobalDefault() {
    if (!selectedModel.value || !props.binding || props.bindingType !== 'llm') return;
    isSettingGlobalDefault.value = true;
    try {
        const fullModelName = `${props.binding.alias}/${selectedModel.value.original_model_name}`;
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
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { uiStore.addNotification('Invalid file type. Use JPG, PNG, and WEBP.', 'error'); return; }
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
    fetchModels();
});

watch(() => props.binding, (newBinding) => {
    if (newBinding) {
        selectedModel.value = null;
        form.value = getInitialFormState();
        fetchModels();
    }
});
</script>

<template>
    <div class="flex flex-col h-[70vh]">
        <div v-if="isLoading" class="flex-grow flex items-center justify-center">
            <div class="text-center">
                <IconAnimateSpin class="w-8 h-8 text-blue-500 mx-auto mb-2" />
                <p>Loading models...</p>
            </div>
        </div>
        <div v-else class="flex flex-grow overflow-hidden">
            <!-- Model List -->
            <div class="w-1/3 border-r dark:border-gray-700 pr-4 flex flex-col min-w-[250px]">
                <div class="relative mb-2">
                     <input type="text" v-model="searchTerm" placeholder="Search models..." class="input-field w-full pl-8" />
                     <div class="absolute inset-y-0 left-0 pl-2 flex items-center pointer-events-none text-gray-400">
                         <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                     </div>
                </div>
                <div class="overflow-y-auto flex-grow">
                    <ul v-if="filteredModels.length > 0" class="space-y-1">
                        <li v-for="model in filteredModels" :key="model.original_model_name">
                            <button @click="selectModel(model)"
                                    class="w-full text-left p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-between transition-colors"
                                    :class="{'bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-100': selectedModel && selectedModel.original_model_name === model.original_model_name}">
                                <div class="flex-grow min-w-0">
                                    <p class="font-medium text-sm truncate">{{ model.alias?.title || model.original_model_name }}</p>
                                    <p v-if="model.alias" class="text-xs opacity-70 truncate">{{ model.original_model_name }}</p>
                                </div>
                                <div class="flex-shrink-0 flex items-center gap-1">
                                    <span v-if="isBindingDefault(model.original_model_name)" class="w-2 h-2 rounded-full bg-blue-500" title="Binding Default"></span>
                                    <span v-if="isGlobalDefault(model.original_model_name)" class="w-2 h-2 rounded-full bg-green-500" title="Global Default"></span>
                                </div>
                            </button>
                        </li>
                    </ul>
                     <div v-else class="text-center text-sm text-gray-500 py-4">No models match your search.</div>
                </div>
            </div>

            <!-- Alias Form & Default Settings -->
            <div class="w-2/3 pl-4 overflow-y-auto">
                <div v-if="!selectedModel" class="flex items-center justify-center h-full">
                    <div class="text-center text-gray-500">
                        <IconCpuChip class="w-12 h-12 mx-auto mb-2 opacity-50" />
                        <p>Select a model to configure its alias and settings.</p>
                    </div>
                </div>
                <div v-else>
                    <div class="flex items-center justify-between mb-4 pb-2 border-b dark:border-gray-700">
                         <h3 class="font-semibold text-lg truncate pr-4" :title="selectedModel.original_model_name">
                            {{ selectedModel.original_model_name }}
                        </h3>
                    </div>
                   
                    <form @submit.prevent="saveAlias" class="space-y-5 pb-6">

                        <div class="flex gap-4">
                            <div class="flex-shrink-0">
                                <label class="label mb-1">Icon</label>
                                <div class="group relative w-20 h-20 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 flex items-center justify-center bg-gray-50 dark:bg-gray-800">
                                    <img v-if="form.icon" :src="form.icon" alt="Icon" class="w-full h-full object-cover rounded-md">
                                    <IconPhoto v-else class="w-8 h-8 text-gray-400" />
                                    
                                    <div v-if="isGeneratingIcon" class="absolute inset-0 bg-white/80 dark:bg-black/60 flex items-center justify-center rounded-md">
                                        <IconAnimateSpin class="w-6 h-6 text-blue-500" />
                                    </div>

                                    <div v-else class="absolute inset-0 bg-black/60 rounded-md flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <input type="file" ref="fileInput" @change="handleFileChange" class="hidden" accept="image/*">
                                        <button @click="triggerFileUpload" type="button" title="Upload" class="text-white hover:text-blue-300"><IconArrowUpTray class="w-5 h-5" /></button>
                                        <button v-if="isTtiConfigured" @click="generateIcon" type="button" title="Generate" class="text-white hover:text-blue-300"><IconSparkles class="w-5 h-5" /></button>
                                    </div>
                                </div>
                            </div>
                            <div class="flex-grow space-y-3">
                                <div>
                                    <label for="alias-title" class="label">Alias Title</label>
                                    <input id="alias-title" v-model="form.title" type="text" class="input-field" placeholder="Friendly Name">
                                </div>
                                <div>
                                    <label for="alias-description" class="label">Description</label>
                                    <input id="alias-description" v-model="form.description" type="text" class="input-field" placeholder="Short description">
                                </div>
                            </div>
                        </div>

                        <div v-if="bindingType === 'llm'" class="p-4 border rounded-lg dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                            <!-- LLM Specific Fields -->
                            <h4 class="font-medium mb-3 text-sm">Generation Parameters</h4>
                            <div class="grid grid-cols-2 gap-4">
                                <div class="col-span-2 sm:col-span-1">
                                    <label class="label text-xs">Context Size</label>
                                    <div class="flex items-center gap-2">
                                        <input v-model="form.ctx_size" type="number" class="input-field" placeholder="e.g. 4096">
                                        <button type="button" @click="fetchCtxSize" class="btn btn-secondary p-2 h-[38px]" title="Auto-detect" :disabled="isFetchingCtxSize">
                                            <IconAnimateSpin v-if="isFetchingCtxSize" class="w-4 h-4" />
                                            <IconSparkles v-else class="w-4 h-4"/>
                                        </button>
                                    </div>
                                </div>
                                <div><label class="label text-xs">Temperature</label><input v-model="form.temperature" type="number" step="0.1" class="input-field"></div>
                                <div><label class="label text-xs">Top K</label><input v-model="form.top_k" type="number" class="input-field"></div>
                                <div><label class="label text-xs">Top P</label><input v-model="form.top_p" type="number" step="0.01" class="input-field"></div>
                                <div><label class="label text-xs">Repeat Penalty</label><input v-model="form.repeat_penalty" type="number" step="0.1" class="input-field"></div>
                                <div><label class="label text-xs">Repeat Last N</label><input v-model="form.repeat_last_n" type="number" class="input-field"></div>
                            </div>
                        </div>
                        
                        <!-- Dynamic Params for ALL Types -->
                        <div v-if="modelParameters.length > 0" class="p-4 border rounded-lg dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                             <h4 class="font-medium mb-3 text-sm">Model Parameters</h4>
                             <div class="grid grid-cols-2 gap-4">
                                <div v-for="param in modelParameters" :key="param.name">
                                    <label :for="`p-${param.name}`" class="label text-xs">{{ param.title || param.name }}</label>
                                     <input 
                                        v-if="['str', 'int', 'float'].includes(param.type)"
                                        :type="param.type === 'str' ? 'text' : 'number'"
                                        :step="param.type === 'float' ? 'any' : 1"
                                        :id="`p-${param.name}`"
                                        v-model="form[param.name]"
                                        class="input-field"
                                        :placeholder="param.help || ''"
                                    />
                                     <div v-else-if="param.type === 'bool'" class="mt-1">
                                         <button type="button" @click="form[param.name] = !form[param.name]" :class="[form[param.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                                            <span :class="[form[param.name] ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                        </button>
                                     </div>
                                </div>
                             </div>
                        </div>

                        <!-- Vision & Override Flags -->
                         <div v-if="bindingType === 'llm'" class="grid grid-cols-2 gap-4">
                            <div class="flex items-center justify-between p-3 border rounded-md dark:border-gray-700">
                                <div class="flex items-center gap-2">
                                    <IconEye class="w-4 h-4 text-gray-500" />
                                    <span class="text-sm font-medium">Vision Support</span>
                                </div>
                                <button type="button" @click="form.has_vision = !form.has_vision" :class="[form.has_vision ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                                    <span :class="[form.has_vision ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                            <div class="flex items-center justify-between p-3 border rounded-md dark:border-gray-700">
                                <div class="flex items-center gap-2">
                                    <span class="text-sm font-medium">Lock Context</span>
                                </div>
                                <button type="button" @click="form.ctx_size_locked = !form.ctx_size_locked" :class="[form.ctx_size_locked ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                                    <span :class="[form.ctx_size_locked ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                        </div>
                        
                        <div class="flex items-center justify-between p-3 border rounded-md dark:border-gray-700">
                             <div class="flex items-center gap-2">
                                <span class="text-sm font-medium">Allow User Overrides</span>
                            </div>
                            <button type="button" @click="form.allow_parameters_override = !form.allow_parameters_override" :class="[form.allow_parameters_override ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                                <span :class="[form.allow_parameters_override ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>


                        <div class="flex justify-end gap-3 pt-2">
                            <button v-if="selectedModel.alias" type="button" @click="deleteAlias" class="btn btn-danger-outline" :disabled="isSaving">Delete Alias</button>
                            <button type="submit" class="btn btn-primary" :disabled="isSaving">{{ isSaving ? 'Saving...' : 'Save Alias' }}</button>
                        </div>
                    </form>

                    <div class="border-t dark:border-gray-600 pt-4">
                        <h4 class="font-medium mb-3 text-sm">Defaults</h4>
                        <div class="space-y-3">
                             <div class="flex items-center justify-between">
                                <span class="text-sm">Set as Default for this Binding</span>
                                <button @click="setAsBindingDefault" class="text-blue-600 hover:underline text-sm font-medium" :disabled="isCurrentBindingDefault || isSettingBindingDefault">
                                    {{ isCurrentBindingDefault ? 'Current Default' : (isSettingBindingDefault ? 'Setting...' : 'Set') }}
                                </button>
                             </div>
                             <div v-if="bindingType === 'llm'" class="flex items-center justify-between">
                                <span class="text-sm">Set as Global System Default</span>
                                <button @click="setAsGlobalDefault" class="text-blue-600 hover:underline text-sm font-medium" :disabled="isCurrentGlobalDefault || isSettingGlobalDefault">
                                    {{ isCurrentGlobalDefault ? 'Current Global' : (isSettingGlobalDefault ? 'Setting...' : 'Set') }}
                                </button>
                             </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
