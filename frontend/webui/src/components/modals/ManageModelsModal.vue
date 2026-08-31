<template>
    <GenericModal modal-name="manageModels" :title="binding ? `Universal Model Profiles: ${binding.alias}` : 'Manage Models'" maxWidthClass="max-w-5xl">
        <template #body>
            <div v-if="!binding" class="text-center p-8 text-red-500 dark:text-red-400">
                <p>Error: Binding information is missing.</p>
            </div>
            <div v-else-if="isLoading" class="text-center p-8">
                <div class="flex justify-center items-center gap-3">
                    <IconAnimateSpin class="w-6 h-6 text-blue-500" />
                    <p class="font-semibold">Loading universal model profiles...</p>
                </div>
                <p class="mt-3 text-sm text-gray-500 dark:text-gray-400">
                    Probing engine models and routing configurations.
                </p>
            </div>
            <div v-else class="flex gap-6 h-[72vh]">
                <!-- Model Profiles List -->
                <div class="w-1/3 border-r dark:border-gray-700/80 pr-4 flex flex-col min-w-[260px]">
                    <div class="relative mb-3">
                         <input type="text" v-model="searchTerm" placeholder="Search profiles..." class="input-field text-xs w-full pl-8" />
                         <div class="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-gray-400">
                             <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                         </div>
                    </div>
                    <div class="overflow-y-auto grow custom-scrollbar pr-1">
                        <ul v-if="filteredModels.length > 0" class="space-y-1.5">
                            <li v-for="model in filteredModels" :key="model.original_model_name">
                                <button @click="selectModel(model)"
                                        class="w-full text-left p-2.5 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 flex items-center justify-between transition-all border border-transparent hover:border-gray-200 dark:hover:border-gray-700 shadow-xs"
                                        :class="{'bg-blue-50 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 border-blue-200 dark:border-blue-800': selectedModel && selectedModel.original_model_name === model.original_model_name}">
                                    <div class="grow min-w-0">
                                        <p class="font-bold text-xs truncate" :class="{'text-blue-600 dark:text-blue-400': model.alias}">
                                            {{ model.alias?.title || model.original_model_name }}
                                        </p>
                                        <p v-if="model.alias" class="text-[9px] font-mono text-gray-500 truncate">{{ model.original_model_name }}</p>
                                    </div>
                                    <div class="shrink-0 flex items-center gap-1.5 pl-2">
                                        <IconEye v-if="model.alias?.vision_enabled || model.alias?.has_vision" class="w-3.5 h-3.5 text-blue-500" title="Vision Enabled" />
                                        <span v-if="isBindingDefault(model.original_model_name)" class="w-2 h-2 rounded-full bg-blue-500" title="Binding Default"></span>
                                        <span v-if="isGlobalDefault(model.original_model_name)" class="w-2 h-2 rounded-full bg-emerald-500" title="Global Default"></span>
                                    </div>
                                </button>
                            </li>
                        </ul>
                         <div v-else class="text-center text-xs text-gray-500 py-6">No profiles match your search.</div>
                    </div>
                </div>

                <!-- Universal Profile Editor -->
                <div class="w-2/3 overflow-y-auto pr-2 custom-scrollbar">
                    <div v-if="!selectedModel" class="flex items-center justify-center h-full">
                        <p class="text-xs font-bold uppercase text-gray-400">Select a model to configure its Universal Profile</p>
                    </div>
                    <div v-else class="space-y-6">
                        <div class="flex items-center justify-between pb-3 border-b dark:border-gray-700/80">
                            <div>
                                <span class="text-[9px] font-black uppercase text-blue-500 tracking-widest">Editing Profile</span>
                                <h3 class="font-bold text-sm truncate font-mono text-gray-900 dark:text-white">{{ selectedModel.original_model_name }}</h3>
                            </div>
                        </div>

                        <form @submit.prevent="saveAlias" class="space-y-6 pb-6 border-b dark:border-gray-700">

                            <!-- Avatar / Logo -->
                            <div class="flex gap-4 p-4 bg-gray-50 dark:bg-gray-900/40 rounded-2xl border border-gray-100 dark:border-gray-800">
                                <div class="shrink-0">
                                    <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Avatar</label>
                                    <div v-if="isGeneratingIcon" class="w-20 h-20 flex items-center justify-center bg-white dark:bg-gray-800 rounded-xl border">
                                        <IconAnimateSpin class="w-6 h-6 text-blue-500 animate-spin" />
                                    </div>
                                    <div v-else class="group relative w-20 h-20 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-700 flex items-center justify-center overflow-hidden bg-white dark:bg-gray-800 shadow-sm">
                                        <img v-if="form.icon" :src="form.icon" alt="Icon" class="w-full h-full object-cover">
                                        <IconPhoto v-else class="w-8 h-8 text-gray-400" />

                                        <div class="absolute inset-0 bg-black/60 flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <input type="file" ref="fileInput" @change="handleFileChange" class="hidden" accept="image/*">
                                            <button @click="triggerFileUpload" type="button" title="Upload" class="text-white hover:text-blue-300"><IconArrowUpTray class="w-4 h-4" /></button>
                                            <button v-if="isTtiConfigured" @click="generateIcon" type="button" title="AI Generate" class="text-white hover:text-blue-300" :disabled="isSubmittingIconRequest">
                                                <IconSparkles class="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>
                                </div>                            
                                <div class="grow space-y-3">
                                    <div>
                                        <label for="alias-title" class="block text-xs font-bold uppercase text-gray-500 mb-1">Profile Title *</label>
                                        <input id="alias-title" v-model="form.title" type="text" class="input-field text-xs" placeholder="e.g., Llama 3.3 Fast" required>
                                    </div>
                                    <div>
                                        <label for="alias-description" class="block text-xs font-bold uppercase text-gray-500 mb-1">Description</label>
                                        <input id="alias-description" v-model="form.description" type="text" class="input-field text-xs" placeholder="Model strengths and domain specializations...">
                                    </div>
                                </div>
                            </div>

                            <!-- LLM Execution Parameters -->
                            <div v-if="bindingType === 'llm'" class="p-4 border rounded-2xl dark:border-gray-700 bg-gray-50/70 dark:bg-gray-900/40 space-y-4">
                                <h4 class="font-bold text-xs uppercase tracking-wider text-gray-700 dark:text-gray-300">LLM Generation Parameters</h4>
                                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                    <div class="md:col-span-3">
                                        <label for="alias-ctx-size" class="block text-xs font-bold uppercase text-gray-500 mb-1">Forced Context Window</label>
                                        <div class="flex items-center gap-2">
                                            <input id="alias-ctx-size" v-model.number="form.ctx_size" type="number" class="input-field text-xs" placeholder="e.g., 32768">
                                            <button type="button" @click="fetchCtxSize" class="btn btn-secondary text-xs h-9 px-3 shrink-0 flex items-center gap-1.5" title="Probe context limit" :disabled="isFetchingCtxSize">
                                                <IconAnimateSpin v-if="isFetchingCtxSize" class="w-3.5 h-3.5 animate-spin" />
                                                <IconSparkles v-else class="w-3.5 h-3.5 text-blue-500" />
                                                <span>Probe</span>
                                            </button>
                                        </div>
                                    </div>
                                    <div><label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Temperature</label><input v-model.number="form.temperature" type="number" step="0.05" class="input-field text-xs"></div>
                                    <div><label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Top K</label><input v-model.number="form.top_k" type="number" class="input-field text-xs"></div>
                                    <div><label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Top P</label><input v-model.number="form.top_p" type="number" step="0.01" class="input-field text-xs"></div>
                                    <div><label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Repeat Penalty</label><input v-model.number="form.repeat_penalty" type="number" step="0.05" class="input-field text-xs"></div>
                                    <div><label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Repeat Last N</label><input v-model.number="form.repeat_last_n" type="number" class="input-field text-xs"></div>
                                </div>
                            </div>
                            
                            <!-- Smart Router Configuration -->
                            <div v-if="bindingType === 'llm'" class="p-4 border rounded-2xl dark:border-gray-700 bg-purple-50/40 dark:bg-purple-950/20 space-y-4">
                                <h4 class="font-bold text-xs uppercase tracking-wider text-purple-900 dark:text-purple-300">Smart Router Profile</h4>
                                <div>
                                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Routing Subject Keywords</label>
                                    <textarea v-model="form.routing_config.description" rows="2" class="input-field text-xs" placeholder="e.g. coding, complex reasoning, math, casual conversation..."></textarea>
                                </div>
                                <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                                    <div>
                                        <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Complexity Tier</label>
                                        <select v-model.number="form.routing_config.complexity_tier" class="input-field text-xs">
                                            <option :value="1">Tier 1</option>
                                            <option :value="2">Tier 2</option>
                                            <option :value="3">Tier 3</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Priority</label>
                                        <input v-model.number="form.routing_config.priority" type="number" min="1" max="10" class="input-field text-xs">
                                    </div>
                                    <div>
                                        <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Avg Latency (ms)</label>
                                        <input v-model.number="form.routing_config.avg_latency_ms" type="number" class="input-field text-xs">
                                    </div>
                                    <div>
                                        <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Cost / 1k ($)</label>
                                        <input v-model.number="form.routing_config.cost_per_1k_tokens" type="number" step="0.0001" class="input-field text-xs">
                                    </div>
                                </div>
                            </div>

                            <!-- Vision and Overrides -->
                            <div v-if="bindingType === 'llm'" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div class="flex items-center justify-between p-3 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700">
                                    <div class="flex items-center gap-2">
                                        <IconEye class="w-4 h-4 text-blue-500" />
                                        <span class="text-xs font-bold">Vision Support</span>
                                    </div>
                                    <button type="button" @click="form.has_vision = !form.has_vision" :class="[form.has_vision ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                                        <span :class="[form.has_vision ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                    </button>
                                </div>
                                <div class="flex items-center justify-between p-3 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700">
                                    <span class="text-xs font-bold">Allow User Overrides</span>
                                    <button type="button" @click="form.allow_parameters_override = !form.allow_parameters_override" :class="[form.allow_parameters_override ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                                        <span :class="[form.allow_parameters_override ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                    </button>
                                </div>
                            </div>

                            <div class="flex justify-end gap-3 pt-4">
                                <button v-if="selectedModel.alias" type="button" @click="deleteAlias" class="btn btn-secondary text-rose-500" :disabled="isSaving">Delete Profile</button>
                                <button type="submit" class="btn btn-primary" :disabled="isSaving">{{ isSaving ? 'Saving...' : 'Save Profile' }}</button>
                            </div>
                        </form>

                        <div class="mt-6">
                             <h4 class="text-xs font-black uppercase text-gray-400 tracking-widest mb-3">System Defaults</h4>
                             <div class="space-y-3 text-xs">
                                <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 rounded-xl">
                                    <span>Binding Default</span>
                                    <button @click="setAsBindingDefault" class="font-bold text-blue-600 hover:underline" :disabled="isCurrentBindingDefault || isSettingBindingDefault">
                                        {{ isCurrentBindingDefault ? '✓ Current Default' : 'Set as Default' }}
                                    </button>
                                </div>
                                 <div v-if="bindingType === 'llm'" class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 rounded-xl">
                                    <span>Global System Default</span>
                                    <button @click="setAsGlobalDefault" class="font-bold text-emerald-600 hover:underline" :disabled="isCurrentGlobalDefault || isSettingGlobalDefault">
                                        {{ isCurrentGlobalDefault ? '✓ Global Default' : 'Set Global Default' }}
                                    </button>
                                </div>
                             </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('manageModels')" class="btn btn-primary">Close</button>
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
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconEye from '../../assets/icons/IconEye.vue';

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
    routing_config: {
        description: '',
        complexity_tier: 2,
        cost_per_1k_tokens: 0.0,
        avg_latency_ms: 200,
        priority: 1
    }
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
    const rawAlias = model.alias || {};
    const newForm = { 
        ...getInitialFormState(), 
        ...rawAlias,
        has_vision: rawAlias.vision_enabled ?? rawAlias.has_vision ?? true,
        vision_enabled: rawAlias.vision_enabled ?? rawAlias.has_vision ?? true,
        ctx_size: rawAlias.forced_context_size ?? rawAlias.ctx_size ?? null,
        forced_context_size: rawAlias.forced_context_size ?? rawAlias.ctx_size ?? null,
        routing_config: {
            description: rawAlias.routing_config?.description || '',
            complexity_tier: rawAlias.routing_config?.complexity_tier || 2,
            cost_per_1k_tokens: rawAlias.routing_config?.cost_per_1k_tokens || 0.0,
            avg_latency_ms: rawAlias.routing_config?.avg_latency_ms || 200,
            priority: rawAlias.routing_config?.priority || 1
        }
    };
    if (bindingType.value === 'llm' && !newForm.name) {
        newForm.name = newForm.title || model.original_model_name;
    }
    form.value = newForm;
}

async function fetchCtxSize() {
    if (!selectedModel.value || !binding.value || bindingType.value !== 'llm') return;
    isFetchingCtxSize.value = true;
    try {
        const size = await adminStore.getModelCtxSize(binding.value.id, selectedModel.value.original_model_name);
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
    if (!selectedModel.value || !binding.value) return;
    isSaving.value = true;
    try {
        const payload = { ...form.value };
        payload.vision_enabled = Boolean(payload.has_vision);
        payload.forced_context_size = payload.ctx_size ? Number(payload.ctx_size) : null;
        let aliasPayload = {};

        if (bindingType.value === 'llm') {
            if (payload.title) payload.name = payload.title;
            ['ctx_size', 'forced_context_size', 'temperature', 'top_k', 'top_p', 'repeat_penalty', 'repeat_last_n'].forEach(key => {
                const value = payload[key];
                payload[key] = (value === '' || value === null || isNaN(parseFloat(value))) ? null : Number(value);
            });
            aliasPayload = { original_model_name: selectedModel.value.original_model_name, alias: payload };
            await adminStore.saveModelAlias(binding.value.id, aliasPayload);
        } else {
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
    if (await uiStore.showConfirmation({ title: 'Delete Profile?', message: `Remove the profile configuration for '${selectedModel.value.original_model_name}'?`, confirmText: 'Delete' })) {
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
            case 'stt': await adminStore.updateSttBinding(binding.value.id, payload); break;
        }
        uiStore.addNotification('Binding default profile updated.', 'success');
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
        uiStore.addNotification('Global default profile updated.', 'success');
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
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { uiStore.addNotification('Invalid file type.', 'error'); return; }
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