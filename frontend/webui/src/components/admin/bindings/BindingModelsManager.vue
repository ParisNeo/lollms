<!-- frontend/webui/src/components/admin/bindings/BindingModelsManager.vue -->
<script setup>
import { ref, watch, computed, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useUiStore } from '../../../stores/ui';
import { useAdminStore } from '../../../stores/admin';
import { useDataStore } from '../../../stores/data';
import { useTasksStore } from '../../../stores/tasks';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconArrowUpTray from '../../../assets/icons/IconArrowUpTray.vue';
import IconPhoto from '../../../assets/icons/IconPhoto.vue';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconEye from '../../../assets/icons/IconEye.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconCircle from '../../../assets/icons/IconCircle.vue';
import apiClient from '../../../services/api';

const props = defineProps({
    binding: { type: Object, required: true },
    bindingType: { type: String, required: true } // 'llm', 'tti', 'tts', 'stt', 'ttv', 'ttm', 'rag'
});

const uiStore = useUiStore();
const adminStore = useAdminStore();
const dataStore = useDataStore();
const tasksStore = useTasksStore();
const { 
    globalSettings, availableBindingTypes, availableTtiBindingTypes, 
    availableTtsBindingTypes, ttiBindings 
} = storeToRefs(adminStore);
const { tasks } = storeToRefs(tasksStore);

const isLoading = ref(true);
const isSaving = ref(false);
const isSettingBindingDefault = ref(false);
const isSettingGlobalDefault = ref(false);
const isSettingBeginnerDefault = ref(false);
const isFetchingCtxSize = ref(false);
const iconGenerationTaskId = ref(null);
const isSubmittingIconRequest = ref(false);
const fileInput = ref(null);

const models = ref([]);
const selectedModel = ref(null);
const searchTerm = ref('');
const modelParameters = ref([]);
const allUniversalProfiles = ref({});

const isSmartRouter = computed(() => {
    return props.binding?.name === 'smart_router' || props.binding?.alias === 'smart_router';
});

const isTtiConfigured = computed(() => ttiBindings.value && ttiBindings.value.some(b => b.is_active));

const getInitialFormState = () => ({
    icon: '',
    title: '',
    name: '',
    description: '',
    has_vision: true,
    vision_enabled: true,
    ctx_size: null,
    forced_context_size: null,
    temperature: null,
    top_k: null,
    top_p: null,
    repeat_penalty: null,
    repeat_last_n: null,
    allow_parameters_override: true,
    reasoning_activation: false,
    reasoning_effort: null,
    reasoning_summary: false,
    routing_strategy: 'balanced',
    selected_model_profiles: [],
    routing_config: {
        description: '',
        complexity_tier: 2,
        cost_per_1k_tokens: 0.0,
        avg_latency_ms: 200,
        priority: 1
    },
    vlm_model_profile: ''
});

const form = ref(getInitialFormState());
const associatedModel = ref('');

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
        if (result && typeof result === 'string') { 
            try { result = JSON.parse(result); } catch (e) { /* ignore */ } 
        }
        let b64 = (result && typeof result === 'object' && result.icon_base64) 
            ? result.icon_base64 
            : (typeof result === 'string' ? result : null);
        if (b64) {
            form.value.icon = b64.startsWith('data:image') ? b64 : `data:image/png;base64,${b64}`;
            uiStore.addNotification('Icon generated successfully!', 'success');
        } else {
            uiStore.addNotification('Icon generation completed.', 'warning');
        }
        iconGenerationTaskId.value = null;
    } else if (newTask.status === 'failed' || newTask.status === 'cancelled') {
        uiStore.addNotification(`Icon generation failed: ${newTask.error || 'Unknown error.'}`, 'error');
        iconGenerationTaskId.value = null;
    }
});

const configuredAliases = computed(() => {
    const aliases = props.binding?.model_aliases || {};
    return Object.entries(aliases).map(([model_name, alias_data]) => {
        const data = typeof alias_data === 'object' ? alias_data : { title: String(alias_data) };
        return {
            original_model_name: model_name,
            alias: data
        };
    }).sort((a, b) => (a.alias.title || '').localeCompare(b.alias.title || ''));
});

const filteredConfiguredAliases = computed(() => {
    if (!searchTerm.value) return configuredAliases.value;
    const lowerSearch = searchTerm.value.toLowerCase();
    return configuredAliases.value.filter(item => 
        item.original_model_name.toLowerCase().includes(lowerSearch) || 
        (item.alias?.title || '').toLowerCase().includes(lowerSearch)
    );
});

const filteredModels = computed(() => {
    if (isSmartRouter.value) return [];
    if (!Array.isArray(models.value)) return [];
    const aliasedKeys = new Set(configuredAliases.value.map(a => a.original_model_name));
    const unaliased = models.value.filter(m => m && !aliasedKeys.has(m.original_model_name));

    if (!searchTerm.value) return unaliased;
    const lowerSearch = searchTerm.value.toLowerCase();
    return unaliased.filter(m => 
        m && (m.original_model_name || '').toLowerCase().includes(lowerSearch)
    );
});

const filteredModelParameters = computed(() => {
    return modelParameters.value.filter(param => param.name !== 'model_name' && param.name !== 'model');
});

function selectModelByName(modelName) {
    const model = models.value.find(m => m.original_model_name === modelName);
    if (model) {
        selectModel(model);
    } else {
        const synthesizedModel = {
            original_model_name: modelName,
            alias: props.binding.model_aliases[modelName]
        };
        selectModel(synthesizedModel);
    }
}

const globalDefaultModel = computed(() => {
    const setting = globalSettings.value.find(s => s.key === 'default_lollms_model_name');
    return setting ? setting.value : null;
});

const isCurrentBindingDefault = computed(() => selectedModel.value && props.binding && selectedModel.value.original_model_name === props.binding.default_model_name);
const isCurrentGlobalDefault = computed(() => selectedModel.value && props.binding && `${props.binding.alias}/${selectedModel.value.original_model_name}` === globalDefaultModel.value);
const isCurrentBeginnerDefault = computed(() => {
    if (!selectedModel.value || !props.binding || props.bindingType !== 'llm') return false;
    const fullModelName = `${props.binding.alias}/${selectedModel.value.original_model_name}`;
    const setting = globalSettings.value.find(s => s.key === 'default_lollms_model_name_beginner');
    return setting ? setting.value === fullModelName : false;
});
const isBindingDefault = (modelName) => props.binding && modelName === props.binding.default_model_name;
const isGlobalDefault = (modelName) => props.binding && `${props.binding.alias}/${modelName}` === globalDefaultModel.value;

async function fetchUniversalProfiles() {
    try {
        const res = await apiClient.get('/api/admin/universal-profiles');
        allUniversalProfiles.value = res.data.profiles || {};
    } catch (e) {
        console.error("Failed to fetch universal profiles:", e);
    }
}

async function fetchModels() {
    if (!props.binding) { isLoading.value = false; models.value = []; return; }
    isLoading.value = true;
    try {
        let res = [];
        switch (props.bindingType) {
            case 'llm': res = await adminStore.fetchBindingModels(props.binding.id); break;
            case 'tti': res = await adminStore.fetchTtiBindingModels(props.binding.id); break;
            case 'tts': res = await adminStore.fetchTtsBindingModels(props.binding.id); break;
            case 'stt': res = await adminStore.fetchSttBindingModels(props.binding.id); break;
            case 'ttv': res = await adminStore.fetchTtvBindingModels(props.binding.id); break;
            case 'ttm': res = await adminStore.fetchTtmBindingModels(props.binding.id); break;
            case 'rag': res = await adminStore.fetchRagBindingModels(props.binding.id); break;
            default: res = [];
        }
        models.value = Array.isArray(res) ? res : [];
    } catch (e) {
        models.value = [];
    } finally {
        isLoading.value = false;
    }
}

function selectModel(model) {
    selectedModel.value = model;
    associatedModel.value = model.original_model_name;
    const rawAlias = model.alias || {};
    const newForm = { 
        ...getInitialFormState(), 
        ...rawAlias,
        has_vision: rawAlias.vision_enabled ?? rawAlias.has_vision ?? true,
        vision_enabled: rawAlias.vision_enabled ?? rawAlias.has_vision ?? true,
        ctx_size: rawAlias.forced_context_size ?? rawAlias.ctx_size ?? null,
        forced_context_size: rawAlias.forced_context_size ?? rawAlias.ctx_size ?? null,
        routing_strategy: rawAlias.routing_strategy || 'balanced',
        selected_model_profiles: Array.isArray(rawAlias.selected_model_profiles) ? [...rawAlias.selected_model_profiles] : [],
        routing_config: {
            description: rawAlias.routing_config?.description || '',
            complexity_tier: rawAlias.routing_config?.complexity_tier || 2,
            cost_per_1k_tokens: rawAlias.routing_config?.cost_per_1k_tokens || 0.0,
            avg_latency_ms: rawAlias.routing_config?.avg_latency_ms || 200,
            priority: rawAlias.routing_config?.priority || 1
        },
        vlm_model_profile: rawAlias.vlm_model_profile || ''
    };

    if (props.bindingType === 'llm' && !newForm.name) {
        newForm.name = newForm.title || model.original_model_name;
    }

    form.value = newForm;
}

function addNewRoutingGroup() {
    const defaultKey = `group_${Date.now().toString(36)}`;
    const newGroup = {
        original_model_name: defaultKey,
        alias: {
            title: 'New Smart Routing Group',
            description: 'Custom routed model profile',
            routing_strategy: 'balanced',
            selected_model_profiles: []
        }
    };
    selectModel(newGroup);
}

function toggleProfileInGroup(profId) {
    const list = [...form.value.selected_model_profiles];
    const idx = list.indexOf(profId);
    if (idx > -1) {
        list.splice(idx, 1);
    } else {
        list.push(profId);
    }
    form.value.selected_model_profiles = list;
}

async function fetchCtxSize() {
    if (!selectedModel.value || !props.binding || props.bindingType !== 'llm') return;
    isFetchingCtxSize.value = true;
    try {
        const size = await adminStore.getModelCtxSize(props.binding.id, selectedModel.value.original_model_name);
        if (size !== null) {
            form.value.ctx_size = size;
            form.value.forced_context_size = size;
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
        payload.vision_enabled = Boolean(payload.has_vision);
        payload.forced_context_size = payload.ctx_size ? Number(payload.ctx_size) : null;

        let aliasPayload = {};

        if (props.bindingType === 'llm') {
            if (payload.title) payload.name = payload.title;
            ['ctx_size', 'forced_context_size', 'temperature', 'top_k', 'top_p', 'repeat_penalty', 'repeat_last_n'].forEach(key => {
                const value = payload[key];
                payload[key] = (value === '' || value === null || isNaN(parseFloat(value))) ? null : Number(value);
            });
            aliasPayload = { 
                original_model_name: selectedModel.value.original_model_name, 
                new_model_name: associatedModel.value || selectedModel.value.original_model_name, 
                alias: payload 
            };
            await adminStore.saveModelAlias(props.binding.id, aliasPayload);
        } else {
            aliasPayload = { 
                original_model_name: selectedModel.value.original_model_name, 
                new_model_name: associatedModel.value || selectedModel.value.original_model_name, 
                alias: payload 
            };
            if (props.bindingType === 'tti') await adminStore.saveTtiModelAlias(props.binding.id, aliasPayload);
            else if (props.bindingType === 'tts') await adminStore.saveTtsModelAlias(props.binding.id, aliasPayload);
            else if (props.bindingType === 'stt') await adminStore.saveSttModelAlias(props.binding.id, aliasPayload);
            else if (props.bindingType === 'rag') await adminStore.saveRagModelAlias(props.binding.id, aliasPayload);
        }
        await fetchModels();
        await fetchUniversalProfiles();
        const targetModelName = associatedModel.value || selectedModel.value.original_model_name;
        const updatedModel = models.value.find(m => m.original_model_name === targetModelName);
        if (updatedModel) selectModel(updatedModel);
        uiStore.addNotification('Profile saved successfully.', 'success');
    } finally {
        isSaving.value = false;
    }
}

async function deleteAlias() {
    if (!selectedModel.value?.alias || !props.binding) return;
    if (await uiStore.showConfirmation({ title: 'Delete Profile?', message: `Remove the profile configuration for '${selectedModel.value.original_model_name}'?`, confirmText: 'Delete' })) {
        isSaving.value = true;
        try {
            switch (props.bindingType) {
                case 'llm': await adminStore.deleteModelAlias(props.binding.id, selectedModel.value.original_model_name); break;
                case 'tti': await adminStore.deleteTtiModelAlias(props.binding.id, selectedModel.value.original_model_name); break;
                case 'tts': await adminStore.deleteTtsModelAlias(props.binding.id, selectedModel.value.original_model_name); break;
                case 'stt': await adminStore.deleteSttModelAlias(props.binding.id, selectedModel.value.original_model_name); break;
                case 'rag': await adminStore.deleteRagModelAlias(props.binding.id, selectedModel.value.original_model_name); break;
            }
            await fetchModels();
            await fetchUniversalProfiles();
            const updatedModel = models.value.find(m => m.original_model_name === selectedModel.value.original_model_name);
            selectModel(updatedModel || models.value[0] || null);
            uiStore.addNotification('Profile deleted.', 'success');
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
        }
        uiStore.addNotification('Binding default profile updated.', 'success');
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
        uiStore.addNotification('Global default model profile updated.', 'success');
    } finally {
        isSettingGlobalDefault.value = false;
    }
}

async function setAsBeginnerDefault() {
    if (!selectedModel.value || !props.binding || props.bindingType !== 'llm') return;
    isSettingBeginnerDefault.value = true;
    try {
        const fullModelName = `${props.binding.alias}/${selectedModel.value.original_model_name}`;
        const response = await adminStore.setAsBeginnerDefault(fullModelName);
        await adminStore.fetchGlobalSettings(true);
        uiStore.addNotification(response.message || 'Default model profile for beginners updated.', 'success');
    } finally {
        isSettingBeginnerDefault.value = false;
    }
}

function triggerFileUpload() { fileInput.value.click(); }

function handleFileChange(event) {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { uiStore.addNotification('File is too large (max 5MB).', 'error'); return; }
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
    fetchUniversalProfiles();
});

watch(() => props.binding, (newBinding) => {
    if (newBinding) {
        selectedModel.value = null;
        form.value = getInitialFormState();
        fetchModels();
        fetchUniversalProfiles();
    }
});
</script>

<template>
    <div class="flex flex-col h-[75vh]">
        <div v-if="isLoading" class="grow flex items-center justify-center">
            <div class="text-center">
                <IconAnimateSpin class="w-8 h-8 text-blue-500 mx-auto mb-2" />
                <p class="text-xs font-bold text-gray-500 uppercase tracking-widest">Loading model profiles...</p>
            </div>
        </div>
        <div v-else class="flex grow overflow-hidden">
            <!-- Sidebar: Configured Profiles / Routing Groups -->
            <div class="w-1/3 border-r dark:border-gray-700/80 pr-4 flex flex-col min-w-[260px]">
                <div class="flex items-center justify-between gap-2 mb-3">
                     <div class="relative grow">
                        <input type="text" v-model="searchTerm" placeholder="Search profiles..." class="input-field text-xs w-full pl-8" />
                        <div class="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-gray-400">
                            <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                        </div>
                     </div>
                     <button v-if="isSmartRouter" @click="addNewRoutingGroup" class="btn btn-primary btn-xs flex items-center gap-1 shrink-0 h-8" title="Add New Smart Router Group">
                        <IconPlus class="w-3.5 h-3.5" />
                        <span>Add Group</span>
                     </button>
                </div>

                <div class="overflow-y-auto grow space-y-5 custom-scrollbar pr-1">

                    <!-- Configured Groups / Profiles Section -->
                    <div class="space-y-2">
                        <h4 class="text-[10px] font-black text-gray-400 dark:text-gray-500 uppercase tracking-widest px-2">
                            {{ isSmartRouter ? 'Routing Groups' : 'Configured Profiles' }} ({{ configuredAliases.length }})
                        </h4>
                        <ul class="space-y-1.5">
                            <li v-for="item in filteredConfiguredAliases" :key="item.original_model_name">
                                <button @click="selectModelByName(item.original_model_name)"
                                        class="w-full text-left p-2.5 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center justify-between transition-all border border-transparent hover:border-gray-200 dark:hover:border-gray-700 shadow-xs"
                                        :class="{'bg-blue-50 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 border-blue-200 dark:border-blue-800': selectedModel && selectedModel.original_model_name === item.original_model_name}">
                                    <div class="grow min-w-0 flex items-center gap-2.5">
                                        <div class="w-7 h-7 rounded-lg bg-blue-100/50 dark:bg-blue-900/40 flex items-center justify-center shrink-0 overflow-hidden border border-blue-200 dark:border-blue-800">
                                            <img v-if="item.alias?.icon" :src="item.alias.icon" class="w-full h-full object-cover" />
                                            <IconCpuChip v-else class="w-4 h-4 text-blue-500" />
                                        </div>
                                        <div class="min-w-0">
                                            <p class="font-bold text-xs truncate text-gray-900 dark:text-white">{{ item.alias?.title || item.original_model_name }}</p>
                                            <p class="text-[9px] opacity-60 truncate font-mono text-gray-500">
                                                {{ isSmartRouter ? `Strategy: ${item.alias?.routing_strategy || 'balanced'}` : item.original_model_name }}
                                            </p>
                                        </div>
                                    </div>
                                    <div class="shrink-0 flex items-center gap-1.5 pl-2">
                                        <IconEye v-if="item.alias?.vision_enabled || item.alias?.has_vision" class="w-3.5 h-3.5 text-blue-500" title="Vision Enabled" />
                                        <span v-if="isBindingDefault(item.original_model_name)" class="w-2 h-2 rounded-full bg-blue-500" title="Binding Default"></span>
                                        <span v-if="isGlobalDefault(item.original_model_name)" class="w-2 h-2 rounded-full bg-emerald-500" title="Global Default"></span>
                                    </div>
                                </button>
                            </li>
                        </ul>
                    </div>

                    <!-- Installed Raw Models (Hidden for smart router) -->
                    <div v-if="!isSmartRouter" class="space-y-2">
                        <h4 class="text-[10px] font-black text-gray-400 dark:text-gray-500 uppercase tracking-widest px-2">Engine Models ({{ models.length }})</h4>
                        <ul v-if="filteredModels.length > 0" class="space-y-1">
                            <li v-for="model in filteredModels" :key="model.original_model_name">
                                <button @click="selectModel(model)"
                                        class="w-full text-left p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center justify-between transition-colors"
                                        :class="{'bg-gray-200 dark:bg-gray-700 font-bold': selectedModel && selectedModel.original_model_name === model.original_model_name}">
                                    <div class="grow min-w-0">
                                        <p class="font-medium text-xs font-mono truncate text-gray-700 dark:text-gray-300">{{ model.original_model_name }}</p>
                                    </div>
                                </button>
                            </li>
                        </ul>
                    </div>

                </div>
            </div>

            <!-- Profile / Routing Group Editor -->
            <div class="w-2/3 pl-5 overflow-y-auto custom-scrollbar">
                <div v-if="!selectedModel" class="flex items-center justify-center h-full">
                    <div class="text-center text-gray-400">
                        <IconCpuChip class="w-12 h-12 mx-auto mb-2 opacity-30" />
                        <p class="text-xs uppercase font-bold tracking-wider">
                            {{ isSmartRouter ? 'Select or create a Smart Routing Group' : 'Select a model to configure its Universal Profile' }}
                        </p>
                    </div>
                </div>

                <div v-else class="space-y-6">
                    <div class="flex items-center justify-between pb-3 border-b dark:border-gray-700/80">
                         <div>
                            <span class="text-[9px] font-black uppercase text-blue-500 tracking-widest">
                                {{ isSmartRouter ? 'Smart Routing Group Profile' : 'Model Profile Editor' }}
                            </span>
                            <h3 class="font-bold text-base truncate text-gray-900 dark:text-white">
                                {{ form.title || selectedModel.original_model_name }}
                            </h3>
                         </div>
                    </div>
                   
                    <form @submit.prevent="saveAlias" class="space-y-6 pb-6">

                        <!-- Identity -->
                        <div class="flex gap-4 p-4 bg-gray-50 dark:bg-gray-900/40 rounded-2xl border border-gray-100 dark:border-gray-800">
                            <div class="shrink-0">
                                <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Avatar / Logo</label>
                                <div class="group relative w-20 h-20 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-700 flex items-center justify-center bg-white dark:bg-gray-800 overflow-hidden shadow-sm">
                                    <img v-if="form.icon" :src="form.icon" alt="Icon" class="w-full h-full object-cover">
                                    <IconPhoto v-else class="w-8 h-8 text-gray-400" />

                                    <div class="absolute inset-0 bg-black/60 flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <input type="file" ref="fileInput" @change="handleFileChange" class="hidden" accept="image/*">
                                        <button @click="triggerFileUpload" type="button" title="Upload Logo" class="text-white hover:text-blue-300"><IconArrowUpTray class="w-5 h-5" /></button>
                                        <button v-if="isTtiConfigured" @click="generateIcon" type="button" title="AI Generate" class="text-white hover:text-blue-300"><IconSparkles class="w-5 h-5" /></button>
                                    </div>
                                </div>
                            </div>
                            <div class="grow space-y-3">
                                <div>
                                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Group Title / Alias *</label>
                                    <input v-model="form.title" type="text" class="input-field text-xs" placeholder="e.g., Coding & Architecture Router" required>
                                </div>
                                <div>
                                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Description</label>
                                    <input v-model="form.description" type="text" class="input-field text-xs" placeholder="Capabilities and domain focus...">
                                </div>
                            </div>
                        </div>

                        <!-- SMART ROUTER GROUP COMPOSITION MATRIX -->
                        <div v-if="isSmartRouter" class="p-5 bg-purple-50/50 dark:bg-purple-950/20 rounded-2xl border border-purple-200 dark:border-purple-800/60 space-y-4">
                            <div class="flex items-center justify-between border-b border-purple-200 dark:border-purple-800/60 pb-3">
                                <div>
                                    <h4 class="font-black text-xs uppercase tracking-wider text-purple-900 dark:text-purple-200">
                                        Member Model Profiles for this Group
                                    </h4>
                                    <p class="text-[11px] text-purple-700 dark:text-purple-300 mt-0.5">
                                        Select which model profiles from other engines participate in this routing group.
                                    </p>
                                </div>
                                <div class="flex items-center gap-2">
                                    <label class="text-[10px] font-bold uppercase text-purple-800 dark:text-purple-300">Strategy:</label>
                                    <select v-model="form.routing_strategy" class="input-field text-xs !py-1 !px-2 bg-white dark:bg-gray-800">
                                        <option value="balanced">Balanced (Subject + Tier + Latency)</option>
                                        <option value="cost_optimized">Cost-Optimized</option>
                                        <option value="quality_optimized">Quality-Optimized</option>
                                    </select>
                                </div>
                            </div>

                            <div class="space-y-2 max-h-72 overflow-y-auto custom-scrollbar pr-1">
                                <div v-for="(prof, profId) in allUniversalProfiles" :key="profId"
                                     v-show="prof.binding_alias !== binding.alias"
                                     @click="toggleProfileInGroup(profId)"
                                     class="p-3 bg-white dark:bg-gray-800 rounded-xl border cursor-pointer transition-all flex items-center justify-between gap-4"
                                     :class="(form.selected_model_profiles.length === 0 || form.selected_model_profiles.includes(profId)) ? 'border-purple-500 ring-2 ring-purple-500/20 shadow-xs' : 'border-gray-200 dark:border-gray-700 opacity-60'">
                                    
                                    <div class="flex items-center gap-3 min-w-0">
                                        <IconCheckCircle v-if="form.selected_model_profiles.length === 0 || form.selected_model_profiles.includes(profId)" class="w-4 h-4 text-purple-600 shrink-0" />
                                        <IconCircle v-else class="w-4 h-4 text-gray-400 shrink-0" />
                                        <div class="min-w-0">
                                            <div class="flex items-center gap-2">
                                                <span class="font-bold text-xs text-gray-900 dark:text-white truncate">{{ prof.title }}</span>
                                                <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300">Tier {{ prof.routing_config?.complexity_tier || 2 }}</span>
                                                <IconEye v-if="prof.vision_enabled" class="w-3.5 h-3.5 text-blue-500" title="Vision Capable" />
                                            </div>
                                            <p class="text-[10px] text-gray-500 truncate font-mono">{{ prof.id }}</p>
                                        </div>
                                    </div>

                                    <div class="flex items-center gap-2 text-xs shrink-0">
                                        <span class="font-mono text-[10px] text-gray-400">{{ prof.routing_config?.avg_latency_ms || 200 }}ms</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Regular LLM Parameters (Non-Smart Router) -->
                        <div v-else-if="bindingType === 'llm'" class="p-4 border rounded-2xl dark:border-gray-700 bg-gray-50/70 dark:bg-gray-900/40 space-y-4">
                            <h4 class="font-bold text-xs uppercase tracking-wider text-gray-700 dark:text-gray-300">Execution Parameters & Limits</h4>
                            <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                                <div class="sm:col-span-2 md:col-span-3">
                                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Forced Context Window (tokens)</label>
                                    <div class="flex items-center gap-2">
                                        <input v-model.number="form.ctx_size" type="number" class="input-field text-xs" placeholder="e.g., 32768">
                                        <button type="button" @click="fetchCtxSize" class="btn btn-secondary text-xs h-9 px-3 shrink-0 flex items-center gap-1.5" :disabled="isFetchingCtxSize">
                                            <IconAnimateSpin v-if="isFetchingCtxSize" class="w-3.5 h-3.5 animate-spin" />
                                            <IconSparkles v-else class="w-3.5 h-3.5 text-blue-500" />
                                            <span>Probe</span>
                                        </button>
                                    </div>
                                </div>
                                <div>
                                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Temperature</label>
                                    <input v-model.number="form.temperature" type="number" step="0.05" min="0" max="2" class="input-field text-xs" placeholder="0.7">
                                </div>
                                <div>
                                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Top K</label>
                                    <input v-model.number="form.top_k" type="number" min="1" max="200" class="input-field text-xs" placeholder="50">
                                </div>
                                <div>
                                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Top P</label>
                                    <input v-model.number="form.top_p" type="number" step="0.01" min="0" max="1" class="input-field text-xs" placeholder="0.95">
                                </div>
                            </div>
                        </div>

                        <!-- Vision and VLM Companion Pairing -->
                        <div v-if="bindingType === 'llm' && !isSmartRouter" class="p-4 border rounded-2xl dark:border-gray-700 bg-blue-50/40 dark:bg-blue-950/20 space-y-3">
                            <div class="flex items-center justify-between border-b dark:border-gray-800 pb-2">
                                <div class="flex items-center gap-2">
                                    <IconEye class="w-4 h-4 text-blue-500" />
                                    <span class="text-xs font-bold text-blue-950 dark:text-blue-200">Multimodal Vision & VLM Companion</span>
                                </div>
                                <button type="button" @click="form.has_vision = !form.has_vision" :class="[form.has_vision ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                                    <span :class="[form.has_vision ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                </button>
                            </div>

                            <div v-if="!form.has_vision" class="space-y-1 pt-1">
                                <label class="block text-[10px] font-bold uppercase text-gray-500">VLM Companion Profile</label>
                                <input v-model="form.vlm_model_profile" type="text" class="input-field text-xs" placeholder="e.g. openai_cloud/gpt-4o or ollama/llava:13b">
                            </div>
                        </div>

                        <div class="flex justify-end gap-3 pt-2">
                            <button v-if="selectedModel.alias" type="button" @click="deleteAlias" class="btn btn-secondary text-rose-500" :disabled="isSaving">Delete Group</button>
                            <button type="submit" class="btn btn-primary" :disabled="isSaving">{{ isSaving ? 'Saving...' : 'Save Routing Group' }}</button>
                        </div>
                    </form>

                    <!-- Defaults -->
                    <div class="border-t dark:border-gray-700/80 pt-5 space-y-3">
                        <h4 class="font-bold text-xs uppercase tracking-widest text-gray-400 mb-2">Default Assignments</h4>
                        <div class="p-3 bg-gray-50 dark:bg-gray-900/40 rounded-xl border border-gray-100 dark:border-gray-800 space-y-3 text-xs">
                             <div class="flex items-center justify-between">
                                <span>Default for this Binding</span>
                                <button @click="setAsBindingDefault" class="font-bold text-blue-600 hover:underline" :disabled="isCurrentBindingDefault || isSettingBindingDefault">
                                    {{ isCurrentBindingDefault ? '✓ Assigned' : (isSettingBindingDefault ? 'Saving...' : 'Set as Binding Default') }}
                                </button>
                             </div>
                             <div class="flex items-center justify-between">
                                <span>Global System Default for All Users</span>
                                <button @click="setAsGlobalDefault" class="font-bold text-emerald-600 hover:underline" :disabled="isCurrentGlobalDefault || isSettingGlobalDefault">
                                    {{ isCurrentGlobalDefault ? '✓ Assigned' : (isSettingGlobalDefault ? 'Saving...' : 'Set as Global Default') }}
                                </button>
                             </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>