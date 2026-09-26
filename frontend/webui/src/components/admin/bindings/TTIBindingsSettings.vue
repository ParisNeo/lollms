<script setup>
import { ref, onMounted, computed, watch, defineAsyncComponent } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useDataStore } from '../../../stores/data';
import { useUiStore } from '../../../stores/ui';
import { useTasksStore } from '../../../stores/tasks';
import { parsedMarkdown as parseMarkdown } from '../../../services/markdownParser';
import IconEye from '../../../assets/icons/IconEye.vue';
import IconEyeOff from '../../../assets/icons/IconEyeOff.vue';
import IconTerminal from '../../../assets/icons/ui/IconTerminal.vue';
import IconPhoto from '../../../assets/icons/IconPhoto.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconPlayCircle from '../../../assets/icons/IconPlayCircle.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconCopy from '../../../assets/icons/IconCopy.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import JsonRenderer from '../../ui/JsonRenderer.vue';

const BindingModelsManager = defineAsyncComponent(() => import('./BindingModelsManager.vue'));
const BindingZoo = defineAsyncComponent(() => import('./BindingZoo.vue'));

const adminStore = useAdminStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();

const { ttiBindings, availableTtiBindingTypes, isLoadingTtiBindings, globalSettings } = storeToRefs(adminStore);
const { tasks } = storeToRefs(tasksStore);

const isFormVisible = ref(false);
const editingBinding = ref(null);
const isLoadingForm = ref(false);
const isKeyVisible = ref({});
const commandParams = ref({});
const activeTab = ref('settings');
const hasZoo = ref(false);

// Two-World Architecture: Top-Level Tab ('bindings' = Physical Connections, 'profiles' = Universal Profiles)
const primaryViewTab = ref('bindings');

// Raw Engine Models for viewing in Connection layer
const connectionRawModels = ref([]);
const isLoadingConnectionModels = ref(false);
const isAutoCreatingProfiles = ref(false);
const connectionModelSearch = ref('');
const selectedStyleFilter = ref('All');
const copiedModel = ref(null);

function detectModelStyle(rawName) {
    const name = (rawName || '').toLowerCase();
    if (name.includes('inpaint')) {
        return { label: 'Inpainting', icon: '🖌️', badgeClass: 'bg-purple-100 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border-purple-200 dark:border-purple-800' };
    }
    if (name.includes('anime') || name.includes('anything') || name.includes('counterfeit') || name.includes('abyss') || name.includes('sushi') || name.includes('waifu') || name.includes('manga') || name.includes('lora')) {
        return { label: 'Anime / 2D', icon: '🎨', badgeClass: 'bg-pink-100 text-pink-700 dark:bg-pink-950/60 dark:text-pink-300 border-pink-200 dark:border-pink-800' };
    }
    if (name.includes('real') || name.includes('photo') || name.includes('epic') || name.includes('chillout') || name.includes('absolute') || name.includes('portrait')) {
        return { label: 'Photoreal', icon: '📸', badgeClass: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800' };
    }
    if (name.includes('cartoon') || name.includes('disney') || name.includes('pixar') || name.includes('3d') || name.includes('render') || name.includes('cute')) {
        return { label: '3D / Cartoon', icon: '🎭', badgeClass: 'bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200 dark:border-amber-800' };
    }
    if (name.includes('xl') || name.includes('ccxl') || name.includes('sdxl')) {
        return { label: 'SDXL', icon: '⚡', badgeClass: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950/60 dark:text-cyan-300 border-cyan-200 dark:border-cyan-800' };
    }
    return { label: 'Diffusion', icon: '✨', badgeClass: 'bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 border-blue-200 dark:border-blue-800' };
}

function formatCleanTitle(rawName) {
    if (!rawName) return 'Checkpoint';
    let clean = String(rawName);
    clean = clean.replace(/\.(safetensors|ckpt|pt|bin)$/i, '');
    clean = clean.replace(/_[a-zA-Z0-9]{4,10}$/, '');
    clean = clean.replace(/[_:-]+/g, ' ').trim();
    return clean.replace(/\b\w/g, l => l.toUpperCase());
}

const aliasedModelNames = computed(() => {
    let aliases = editingBinding.value?.model_aliases || {};
    if (typeof aliases === 'string') {
        try { aliases = json.loads(aliases); } catch { aliases = {}; }
    }
    const names = new Set(Object.keys(aliases));
    for (const val of Object.values(aliases)) {
        const v = typeof val === 'object' && val !== null ? (val.alias || val) : {};
        if (v.model_name) names.add(v.model_name);
    }
    return names;
});

function isModelAliased(modelItem) {
    const name = modelItem.original_model_name || modelItem.name || modelItem;
    return aliasedModelNames.value.has(name);
}

function copyModelName(name) {
    navigator.clipboard.writeText(name);
    copiedModel.value = name;
    uiStore.addNotification(`Copied checkpoint: ${name}`, 'success', 2000);
    setTimeout(() => {
        if (copiedModel.value === name) copiedModel.value = null;
    }, 2000);
}

function switchToProfilesWithModel(modelName) {
    hideForm();
    primaryViewTab.value = 'profiles';
}

const styleCategoryCounts = computed(() => {
    const counts = { All: connectionRawModels.value.length };
    for (const m of connectionRawModels.value) {
        const raw = m.original_model_name || m.name || m;
        const style = detectModelStyle(raw).label;
        counts[style] = (counts[style] || 0) + 1;
    }
    return counts;
});

async function handleAutoCreateProfilesForCurrent() {
    if (!editingBinding.value) return;
    isAutoCreatingProfiles.value = true;
    try {
        const res = await adminStore.autoCreateProfilesForBinding(editingBinding.value.id, 'tti');
        uiStore.addNotification(res.message || `Created profiles for ${editingBinding.value.alias}`, 'success');
        await Promise.allSettled([
            fetchConnectionModels(editingBinding.value.id),
            dataStore.fetchAvailableTtiModels()
        ]);
    } catch (e) {
        uiStore.addNotification(e.response?.data?.detail || 'Failed to auto-create profiles.', 'error');
    } finally {
        isAutoCreatingProfiles.value = false;
    }
}

const filteredConnectionModels = computed(() => {
    let list = connectionRawModels.value;
    if (selectedStyleFilter.value !== 'All') {
        list = list.filter(m => {
            const raw = m.original_model_name || m.name || m;
            return detectModelStyle(raw).label === selectedStyleFilter.value;
        });
    }
    if (!connectionModelSearch.value.trim()) return list;
    const q = connectionModelSearch.value.toLowerCase().trim();
    return list.filter(m => (m.original_model_name || m.name || m).toLowerCase().includes(q));
});

async function fetchConnectionModels(bindingId) {
    if (!bindingId) return;
    isLoadingConnectionModels.value = true;
    try {
        const res = await adminStore.fetchTtiBindingModels(bindingId);
        connectionRawModels.value = Array.isArray(res) ? res : [];
    } catch {
        connectionRawModels.value = [];
    } finally {
        isLoadingConnectionModels.value = false;
    }
}

const getInitialFormState = () => ({
    id: null,
    alias: '',
    name: '',
    config: {},
    default_model_name: '',
    is_active: true
});

const form = ref(getInitialFormState());
const isEditMode = computed(() => editingBinding.value !== null);

const selectedBindingType = computed(() => {
    if (!form.value.name || !Array.isArray(availableTtiBindingTypes.value)) return null;
    return availableTtiBindingTypes.value.find(b => (b.binding_name || b.name) === form.value.name);
});

const hasCommands = computed(() => {
    if (!selectedBindingType.value || !Array.isArray(selectedBindingType.value.commands)) return false;
    return selectedBindingType.value.commands.length > 0;
});

async function checkZooAvailability(bindingId) {
    if (!bindingId) { hasZoo.value = false; return; }
    hasZoo.value = false;
    try {
        const res = await adminStore.fetchTtiBindingZoo(bindingId);
        hasZoo.value = Array.isArray(res) && res.length > 0;
    } catch {
        hasZoo.value = false;
    } finally {
        if (!hasZoo.value && activeTab.value === 'zoo') {
            activeTab.value = 'settings';
        }
    }
}

watch(hasCommands, (val) => {
    if (!val && activeTab.value === 'commands') {
        activeTab.value = 'settings';
    }
});

// Command execution tracking
const currentCommandTaskId = ref(null);
const lastExecutedCommandName = ref(null);
const activeCommandResult = ref(null);

const currentTask = computed(() => {
    if (!currentCommandTaskId.value) return null;
    return tasks.value.find(t => t.id === currentCommandTaskId.value);
});

watch(currentTask, (newTask) => {
    if (newTask && newTask.status === 'completed') {
        activeCommandResult.value = newTask.result;
    }
}, { deep: true });

function openPolicyModal() {
    uiStore.openModal('forceSettings');
}

async function handleHealProfiles() {
    try {
        const res = await (await import('../../../services/api')).default.post('/api/admin/bindings/migrate-and-heal');
        uiStore.addNotification(res.data.message, 'success');
        await adminStore.fetchTtiBindings(true);
    } catch (e) {
        uiStore.addNotification('Healing operation failed.', 'error');
    }
}

function getGlobalParametersFromBinding(bindingType) {
    if (!bindingType) return [];
    const seen = new Set();
    const result = [];
    const sources = [
        bindingType.global_input_parameters,
        bindingType.input_parameters,
        bindingType.parameters
    ];
    for (const src of sources) {
        if (Array.isArray(src)) {
            for (const param of src) {
                if (param && param.name && !seen.has(param.name) && param.name !== 'model_name' && param.name !== 'model') {
                    seen.add(param.name);
                    result.push(param);
                }
            }
        }
    }
    return result;
}

const allFormParameters = computed(() => {
    const paramsFromDesc = getGlobalParametersFromBinding(selectedBindingType.value);
    const paramNamesFromDesc = new Set(paramsFromDesc.map(p => p.name));

    const paramsFromConfig = Object.keys(form.value.config || {})
        .filter(key => 
            !paramNamesFromDesc.has(key) && 
            key !== 'model_name' && 
            key !== 'model' &&
            key !== 'class'
        )
        .map(key => ({
            name: key,
            type: typeof form.value.config[key] === 'boolean' ? 'bool' : (typeof form.value.config[key] === 'number' ? 'float' : 'str'),
            description: `(Parameter not in binding description)`,
            mandatory: false,
        }));

    return [
        ...paramsFromDesc, 
        ...paramsFromConfig
    ];
});

watch(globalSettings, (newSettings) => {
}, { deep: true, immediate: true });


watch(() => form.value.name, (newName, oldName) => {
    if (newName !== oldName && !isEditMode.value) {
        if (!Array.isArray(availableTtiBindingTypes.value)) return;
        const bindingDesc = availableTtiBindingTypes.value.find(b => (b.binding_name || b.name) === newName);
        const newConfig = {};
        if (bindingDesc && bindingDesc.input_parameters) {
            bindingDesc.input_parameters.forEach(param => {
                newConfig[param.name] = param.default !== undefined ? param.default : '';
            });
        }
        form.value.config = newConfig;
    }
});

onMounted(() => {
    adminStore.fetchTtiBindings();
    adminStore.fetchAvailableTtiBindingTypes();
    adminStore.fetchGlobalSettings();
});

function showAddForm() {
    editingBinding.value = null;
    form.value = getInitialFormState();
    isKeyVisible.value = {};
    commandParams.value = {};
    isFormVisible.value = true;
    activeTab.value = 'settings';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showEditForm(binding) {
    editingBinding.value = binding;
    form.value = JSON.parse(JSON.stringify(binding));
    if (!form.value.config) {
        form.value.config = {};
    }
    isKeyVisible.value = {};

    checkZooAvailability(binding.id);
    fetchConnectionModels(binding.id);

    const bindingType = Array.isArray(availableTtiBindingTypes.value) ? availableTtiBindingTypes.value.find(b => (b.binding_name || b.name) === binding.name) : null;
    if(bindingType && bindingType.commands){
        const params = {};
        bindingType.commands.forEach(cmd => {
            params[cmd.name] = {};
            if(cmd.parameters){
                cmd.parameters.forEach(p => {
                    params[cmd.name][p.name] = p.default !== undefined ? p.default : '';
                });
            }
        });
        commandParams.value = params;
    } else {
        commandParams.value = {};
    }

    // Reset execution state
    currentCommandTaskId.value = null;
    activeCommandResult.value = null;
    lastExecutedCommandName.value = null;

    isFormVisible.value = true;
    activeTab.value = 'settings';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function hideForm() {
    isFormVisible.value = false;
    editingBinding.value = null;
}

function parseOptions(options) {
    if (typeof options === 'string') {
        return options.split(',').map(o => o.trim()).filter(o => o);
    }
    if (Array.isArray(options)) {
        return options.filter(o => o);
    }
    return [];
}

async function handleSubmit() {
    if (!form.value.alias.trim() || !form.value.name) {
        uiStore.addNotification('Alias and Binding Type are required fields.', 'warning');
        return;
    }

    isLoadingForm.value = true;
    try {
        const payload = {
            alias: form.value.alias,
            name: form.value.name,
            config: form.value.config || {},
            is_active: form.value.is_active,
            default_model_name: form.value.default_model_name || null
        };

        if (isEditMode.value) {
            await adminStore.updateTtiBinding(editingBinding.value.id, payload);
        } else {
            await adminStore.addTtiBinding(payload);
        }
        hideForm();
    } catch (error) {
        console.error("Submit failed:", error.message);
    } finally {
        isLoadingForm.value = false;
    }
}

async function handleDelete(binding) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete TTI Binding '${binding.alias}'?`,
        message: 'Are you sure? This action cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        await adminStore.deleteTtiBinding(binding.id);
    }
}

async function toggleBindingActive(binding) {
    await adminStore.updateTtiBinding(binding.id, { is_active: !binding.is_active });
}

function getBindingTitle(name) {
    if (!Array.isArray(availableTtiBindingTypes.value)) return name;
    const bindingType = availableTtiBindingTypes.value.find(b => (b.binding_name || b.name) === name);
    return bindingType ? (bindingType.title || bindingType.name) : name;
}

async function executeCommand(cmd, bindingId, params) {
    currentCommandTaskId.value = null;
    activeCommandResult.value = null;
    lastExecutedCommandName.value = cmd.name;
    
    try {
        uiStore.addNotification(`Submitting command '${cmd.title || cmd.name}'...`, 'info');
        const taskInfo = await adminStore.executeTtiBindingCommand(bindingId, cmd.name, params);
        if (taskInfo && taskInfo.id) {
             currentCommandTaskId.value = taskInfo.id;
             tasksStore.addTask(taskInfo);
             uiStore.addNotification(`Task started: ${cmd.title || cmd.name}`, 'success');
        }
    } catch (e) {
        console.error(e);
        uiStore.addNotification(`Command submission failed: ${e.message}`, 'error');
    }
}
</script>

<template>
    <div class="space-y-6">
        <!-- ── TWO-TIER DOGMA ROOT TABS (Connections vs Universal Profiles) ── -->
        <div v-if="!isFormVisible" class="flex items-center justify-between border-b border-gray-200 dark:border-gray-700/80 pb-3 flex-wrap gap-3">
            <div class="flex items-center gap-2 p-1 bg-gray-100 dark:bg-gray-800 rounded-xl text-xs font-bold">
                <button 
                    @click="primaryViewTab = 'bindings'" 
                    class="px-4 py-2 rounded-lg transition-all flex items-center gap-2 cursor-pointer select-none"
                    :class="primaryViewTab === 'bindings' ? 'bg-white dark:bg-gray-700 text-pink-600 dark:text-pink-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                >
                    <IconPhoto class="w-4 h-4" />
                    <span>Physical Bindings ({{ ttiBindings.length }})</span>
                </button>
                <button 
                    @click="primaryViewTab = 'profiles'" 
                    class="px-4 py-2 rounded-lg transition-all flex items-center gap-2 cursor-pointer select-none"
                    :class="primaryViewTab === 'profiles' ? 'bg-white dark:bg-gray-700 text-purple-600 dark:text-purple-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                >
                    <IconSparkles class="w-4 h-4 text-purple-500" />
                    <span>Universal Model Profiles</span>
                </button>
            </div>

            <div class="flex items-center gap-2">
                <button @click="handleHealProfiles" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Heal orphaned user preferences">
                    <IconSparkles class="w-3.5 h-3.5 text-purple-500" />
                    <span>Sync & Heal</span>
                </button>
                <button @click="openPolicyModal" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Force models or set system defaults for users">
                    <IconCpuChip class="w-3.5 h-3.5 text-pink-500" />
                    <span>⚡ Policy & Defaults</span>
                </button>
                <button v-if="primaryViewTab === 'bindings'" @click="showAddForm" class="btn btn-primary btn-sm flex items-center gap-1.5 shadow-sm">
                    <span>+ Add TTI Binding</span>
                </button>
            </div>
        </div>

        <!-- SECTION 2: UNIVERSAL TTI PROFILES (ACROSS ALL BINDINGS) -->
        <div v-if="primaryViewTab === 'profiles' && !isFormVisible" class="bg-white dark:bg-gray-850 p-5 rounded-2xl border border-gray-200/80 dark:border-gray-700/80 shadow-sm">
            <div class="mb-4">
                <h3 class="text-lg font-black text-gray-900 dark:text-white flex items-center gap-2">
                    <IconSparkles class="w-5 h-5 text-purple-500" />
                    <span>Universal TTI Image Profiles Catalog</span>
                </h3>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    Configure final usable image diffusion and generation profiles across all physical TTI connections.
                </p>
            </div>
            <BindingModelsManager binding-type="tti" />
        </div>

        <!-- SECTION 1: PHYSICAL CONNECTIONS -->
        <div v-else-if="primaryViewTab === 'bindings' || isFormVisible" class="space-y-6">

        <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 shadow-md rounded-lg p-6">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-xl font-semibold">{{ isEditMode ? 'Edit TTI Binding: ' + form.alias : 'Add New TTI Binding' }}</h3>
                <div v-if="isEditMode" class="flex gap-2 text-sm font-medium overflow-x-auto">
                    <button @click="activeTab = 'settings'" :class="{'text-blue-600 border-b-2 border-blue-600': activeTab === 'settings', 'text-gray-500 hover:text-gray-700': activeTab !== 'settings'}" class="px-3 py-2 whitespace-nowrap">Settings</button>
                    <button @click="activeTab = 'raw_models'" :class="{'text-blue-600 border-b-2 border-blue-600': activeTab === 'raw_models', 'text-gray-500 hover:text-gray-700': activeTab !== 'raw_models'}" class="px-3 py-2 whitespace-nowrap">Detected Models ({{ connectionRawModels.length }})</button>
                    <button v-if="hasZoo" @click="activeTab = 'zoo'" :class="{'text-blue-600 border-b-2 border-blue-600': activeTab === 'zoo', 'text-gray-500 hover:text-gray-700': activeTab !== 'zoo'}" class="px-3 py-2 whitespace-nowrap">Models Zoo</button>
                    <button v-if="hasCommands" @click="activeTab = 'commands'" :class="{'text-blue-600 border-b-2 border-blue-600': activeTab === 'commands', 'text-gray-500 hover:text-gray-700': activeTab !== 'commands'}" class="px-3 py-2 whitespace-nowrap">Commands</button>
                </div>
            </div>

             <div v-if="activeTab === 'settings'">
                <form @submit.prevent="handleSubmit" class="space-y-6">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label for="alias" class="block text-sm font-medium">Alias <span class="text-red-500">*</span></label>
                            <input type="text" id="alias" v-model="form.alias" class="input-field mt-1" required placeholder="e.g., local_sd" autocomplete="off">
                            <p class="text-xs text-gray-500 mt-1">A unique, short name for this configuration.</p>
                        </div>
                        <div>
                            <label for="name" class="block text-sm font-medium">Binding Type <span class="text-red-500">*</span></label>
                            <select id="name" v-model="form.name" class="input-field mt-1" required :disabled="isEditMode">
                                <option disabled value="">Select a type</option>
                                <option v-for="type in availableTtiBindingTypes" :key="type.binding_name || type.name" :value="type.binding_name || type.name">{{ type.title || type.name }}</option>
                            </select>
                        </div>
                    </div>

                    <div v-if="selectedBindingType" class="space-y-6 border-t dark:border-gray-700 pt-6">
                        <div class="text-sm text-gray-600 dark:text-gray-400 prose dark:prose-invert max-w-none" v-html="parseMarkdown(selectedBindingType.description || '')"></div>
                        <div v-for="param in allFormParameters" :key="param.name" class="space-y-1">
                            <label :for="`param-${param.name}`" class="block text-sm font-medium capitalize">
                                {{ param.name.replace(/_/g, ' ') }}
                                <span v-if="param.mandatory" class="text-red-500">*</span>
                            </label>

                            <select v-if="param.options && param.options.length > 0" :id="`param-${param.name}`" v-model="form.config[param.name]" class="input-field">
                                <option v-for="option in parseOptions(param.options)" :key="option" :value="option">{{ option }}</option>
                            </select>
                            
                            <div v-else-if="['str', 'int', 'float', 'list', 'text'].includes(param.type)">
                                <div class="relative">
                                    <input :type="(param.name.includes('key') || param.name.includes('token')) && !isKeyVisible[param.name] ? 'password' : 'text'"
                                        :id="`param-${param.name}`" v-model="form.config[param.name]" class="input-field"
                                        :required="param.mandatory" :placeholder="param.description" autocomplete="off">
                                    <button v-if="param.name.includes('key') || param.name.includes('token')" type="button" @click="isKeyVisible[param.name] = !isKeyVisible[param.name]" class="absolute inset-y-0 right-0 px-3 flex items-center text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" :title="isKeyVisible[param.name] ? 'Hide' : 'Show'">
                                        <IconEyeOff v-if="isKeyVisible[param.name]" class="w-5 h-5" />
                                        <IconEye v-else class="w-5 h-5" />
                                    </button>
                                </div>
                            </div>
                            <div v-else-if="param.type === 'bool'" class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                                <span class="grow flex flex-col pr-4"><span class="text-sm text-gray-500 dark:text-gray-400">{{ param.description }}</span></span>
                                <button @click="form.config[param.name] = !form.config[param.name]" type="button" :class="[form.config[param.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                    <span :class="[form.config[param.name] ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                            <p class="text-xs text-gray-500 mt-1">{{ param.description }}</p>
                        </div>
                    </div>

                    <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                        <span class="grow flex flex-col"><span class="text-sm font-medium text-gray-900 dark:text-gray-100">Active</span><span class="text-sm text-gray-500 dark:text-gray-400">If disabled, this TTI service will not be available.</span></span>
                        <button @click="form.is_active = !form.is_active" type="button" :class="[form.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                            <span :class="[form.is_active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                        </button>
                    </div>

                    <div class="flex justify-end gap-3">
                        <button type="button" @click="hideForm" class="btn btn-secondary">Cancel</button>
                        <button type="submit" class="btn btn-primary" :disabled="isLoadingForm">
                            <IconAnimateSpin v-if="isLoadingForm" class="w-5 h-5 mr-2" />
                            {{ isLoadingForm ? 'Saving...' : (isEditMode ? 'Save Changes' : 'Add Binding') }}
                        </button>
                    </div>
                </form>
            </div>
            
             <!-- Commands Tab -->
             <div v-else-if="activeTab === 'commands'" class="space-y-6">
                <div v-if="selectedBindingType && selectedBindingType.commands && selectedBindingType.commands.length > 0">
                    <div v-for="cmd in selectedBindingType.commands" :key="cmd.name" class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg border dark:border-gray-600 mb-4">
                         <!-- Command Header -->
                         <div class="flex justify-between items-start mb-3">
                            <div>
                                <h5 class="font-bold text-md flex items-center gap-2">
                                    <IconTerminal class="w-4 h-4 text-gray-500"/>
                                    {{ cmd.title || cmd.name }}
                                </h5>
                                <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">{{ cmd.description }}</p>
                            </div>
                            <button 
                                type="button" 
                                @click="executeCommand(cmd, editingBinding.id, commandParams[cmd.name])" 
                                class="btn btn-primary btn-sm flex items-center gap-2"
                                :disabled="currentTask && currentTask.status === 'running'"
                            >
                                <IconPlayCircle class="w-4 h-4" />
                                Execute
                            </button>
                        </div>

                        <!-- Parameters -->
                        <div v-if="cmd.parameters && cmd.parameters.length > 0" class="space-y-3 mb-4 p-3 bg-white dark:bg-gray-800 rounded border dark:border-gray-700">
                            <div v-for="p in cmd.parameters" :key="p.name">
                                <label class="block text-xs font-medium uppercase text-gray-500 dark:text-gray-400 mb-1">{{ p.name }}</label>
                                <input v-if="p.type !== 'bool'" type="text" v-model="commandParams[cmd.name][p.name]" class="input-field text-sm" :placeholder="p.default">
                                <div v-else class="flex items-center gap-2">
                                     <button @click="commandParams[cmd.name][p.name] = !commandParams[cmd.name][p.name]" type="button" :class="[commandParams[cmd.name][p.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                        <span :class="[commandParams[cmd.name][p.name] ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                    </button>
                                    <span class="text-sm text-gray-600 dark:text-gray-400">{{ p.description }}</span>
                                </div>
                            </div>
                        </div>

                        <!-- Progress Bar (If executing this command) -->
                        <div v-if="currentTask && lastExecutedCommandName === cmd.name && (currentTask.status === 'running' || currentTask.status === 'pending')" class="mt-4">
                             <div class="flex justify-between text-xs mb-1 font-semibold text-blue-600 dark:text-blue-400">
                                <span>Executing...</span>
                                <span>{{ currentTask.progress }}%</span>
                            </div>
                            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                                <div class="bg-blue-600 h-2 rounded-full transition-all duration-300 relative overflow-hidden" :style="{ width: currentTask.progress + '%' }">
                                     <div class="absolute inset-0 bg-white/20 animate-[pulse_2s_cubic-bezier(0.4,0,0.6,1)_infinite]"></div>
                                </div>
                            </div>
                            <p class="text-xs text-gray-500 mt-1 truncate">{{ currentTask.description }}</p>
                        </div>
                        
                        <!-- Result -->
                         <div v-if="activeCommandResult && lastExecutedCommandName === cmd.name && currentTask && currentTask.status === 'completed'" class="mt-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-md">
                            <h6 class="text-xs font-bold text-green-800 dark:text-green-300 mb-2 uppercase flex items-center gap-2">
                                <span class="w-2 h-2 rounded-full bg-green-500"></span> Success
                            </h6>
                            <div v-if="typeof activeCommandResult === 'object'">
                                <JsonRenderer :json="activeCommandResult" />
                            </div>
                            <div v-else class="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 font-mono">
                                {{ activeCommandResult }}
                            </div>
                        </div>
                         <div v-if="currentTask && lastExecutedCommandName === cmd.name && (currentTask.status === 'failed' || currentTask.status === 'cancelled')" class="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
                            <h6 class="text-xs font-bold text-red-800 dark:text-red-300 mb-2 uppercase flex items-center gap-2">
                                <span class="w-2 h-2 rounded-full bg-red-500"></span> {{ currentTask.status }}
                            </h6>
                            <p class="text-sm text-red-700 dark:text-red-400">{{ currentTask.error }}</p>
                        </div>
                    </div>
                </div>
                <div v-else class="text-center text-gray-500 py-8 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg">
                    No commands available for this binding type.
                </div>
                <div class="flex justify-end gap-3 mt-4">
                    <button type="button" @click="hideForm" class="btn btn-secondary">Close</button>
                </div>
            </div>

            <div v-else-if="activeTab === 'zoo'">
                <BindingZoo :binding="editingBinding" binding-type="tti" />
                <div class="flex justify-end gap-3 mt-4">
                     <button type="button" @click="hideForm" class="btn btn-secondary">Close</button>
                </div>
            </div>

            <!-- Detected Models Tab (Viewing the models list for this physical TTI connection) -->
            <div v-else-if="activeTab === 'raw_models'" class="space-y-4">
                <!-- Header Control Banner -->
                <div class="flex items-center justify-between gap-4 bg-gradient-to-r from-pink-50/70 via-purple-50/50 to-blue-50/50 dark:from-pink-950/20 dark:via-purple-950/20 dark:to-blue-950/20 p-4 rounded-2xl border border-pink-200/70 dark:border-pink-900/40 shadow-xs flex-wrap">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-2xl bg-gradient-to-tr from-pink-500 to-purple-600 text-white flex items-center justify-center shadow-md shadow-pink-500/20 shrink-0">
                            <IconPhoto class="w-5 h-5" />
                        </div>
                        <div>
                            <h4 class="font-black text-sm text-gray-900 dark:text-white flex items-center gap-2">
                                <span>Detected Diffusion Checkpoints</span>
                                <span class="px-2 py-0.5 rounded-full bg-pink-100 text-pink-700 dark:bg-pink-900/40 dark:text-pink-300 text-[10px] font-mono font-bold">
                                    {{ connectionRawModels.length }} models
                                </span>
                            </h4>
                            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                                Checkpoint weights discovered on connection '{{ editingBinding.alias }}'.
                            </p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <button @click="handleAutoCreateProfilesForCurrent" :disabled="isAutoCreatingProfiles || isLoadingConnectionModels" class="btn btn-primary btn-xs flex items-center gap-1.5 shadow-sm bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-700 hover:to-purple-700 border-none text-white font-bold cursor-pointer">
                            <IconAnimateSpin v-if="isAutoCreatingProfiles" class="w-3.5 h-3.5 animate-spin" />
                            <IconSparkles v-else class="w-3.5 h-3.5 text-amber-300" />
                            <span>Auto-Create Profiles for All</span>
                        </button>
                        <button @click="fetchConnectionModels(editingBinding.id)" :disabled="isLoadingConnectionModels" class="btn btn-secondary btn-xs flex items-center gap-1.5 cursor-pointer">
                            <IconArrowDownTray class="w-3.5 h-3.5 text-blue-500" :class="{'animate-spin': isLoadingConnectionModels}" />
                            <span>Probe Again</span>
                        </button>
                    </div>
                </div>

                <!-- Search & Style Category Filters -->
                <div class="space-y-2.5">
                    <div class="relative">
                        <input 
                            type="text" 
                            v-model="connectionModelSearch" 
                            placeholder="Search diffusion models, checkpoints, safetensors..." 
                            class="input-field text-xs w-full pl-9 py-2 rounded-xl" 
                        />
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                        </div>
                    </div>

                    <!-- Category Pills -->
                    <div v-if="connectionRawModels.length > 0 && !isLoadingConnectionModels" class="flex items-center gap-1.5 flex-wrap text-xs select-none">
                        <button 
                            v-for="(count, cat) in styleCategoryCounts" 
                            :key="cat"
                            @click="selectedStyleFilter = cat"
                            class="px-2.5 py-1 rounded-xl font-bold text-[11px] transition-all cursor-pointer flex items-center gap-1 border"
                            :class="selectedStyleFilter === cat ? 'bg-pink-600 text-white border-pink-600 shadow-xs' : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'"
                        >
                            <span>{{ cat }}</span>
                            <span class="text-[9px] opacity-75 font-mono">({{ count }})</span>
                        </button>
                    </div>
                </div>

                <!-- 1. ACTIVE PROBING ANIMATION (Diffusion Studio Scanner) -->
                <div v-if="isLoadingConnectionModels" class="py-12 px-6 rounded-2xl bg-white/50 dark:bg-gray-850/50 border border-pink-100 dark:border-pink-900/30 text-center space-y-6">
                    <div class="relative w-20 h-20 mx-auto flex items-center justify-center">
                        <div class="absolute inset-0 rounded-3xl bg-pink-500/20 animate-ping"></div>
                        <div class="absolute -inset-2 rounded-3xl bg-gradient-to-tr from-pink-500/20 via-purple-500/20 to-indigo-500/20 blur-md animate-pulse"></div>
                        <div class="relative w-16 h-16 rounded-2xl bg-gradient-to-tr from-pink-500 to-purple-600 flex items-center justify-center text-white shadow-xl shadow-pink-500/30">
                            <IconPhoto class="w-8 h-8 animate-pulse" />
                        </div>
                    </div>

                    <div class="space-y-1.5 max-w-sm mx-auto">
                        <h4 class="text-sm font-black text-gray-900 dark:text-white uppercase tracking-wider flex items-center justify-center gap-2">
                            <IconAnimateSpin class="w-4 h-4 text-pink-500 animate-spin" />
                            <span>Probing TTI Diffusion Checkpoints</span>
                        </h4>
                        <p class="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                            Connecting to {{ editingBinding.alias }} to query local checkpoint files, safetensors, and remote diffusion vaults...
                        </p>
                    </div>

                    <!-- Shimmering Skeleton Preview Cards Grid -->
                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-2 opacity-60">
                        <div v-for="i in 6" :key="i" class="p-4 bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 space-y-2.5 animate-pulse">
                            <div class="flex items-center justify-between">
                                <div class="h-3 w-20 bg-gray-200 dark:bg-gray-700 rounded-md"></div>
                                <div class="h-3 w-12 bg-gray-200 dark:bg-gray-700 rounded-md"></div>
                            </div>
                            <div class="h-4 w-3/4 bg-gray-200 dark:bg-gray-700 rounded-md"></div>
                            <div class="h-2.5 w-full bg-gray-150 dark:bg-gray-750 rounded-md"></div>
                        </div>
                    </div>
                </div>

                <!-- 2. EMPTY STATE -->
                <div v-else-if="filteredConnectionModels.length === 0" class="text-center py-16 px-6 bg-white dark:bg-gray-800/60 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-2xl space-y-3">
                    <div class="w-14 h-14 rounded-2xl bg-gray-100 dark:bg-gray-700 text-gray-400 flex items-center justify-center mx-auto">
                        <IconPhoto class="w-7 h-7" />
                    </div>
                    <div class="space-y-1">
                        <p class="text-sm font-bold text-gray-700 dark:text-gray-300">
                            {{ connectionModelSearch ? 'No models match your filter' : 'No diffusion models discovered' }}
                        </p>
                        <p class="text-xs text-gray-400 max-w-sm mx-auto">
                            Ensure the remote provider is running and API credentials or weights directories are correctly configured in Settings.
                        </p>
                    </div>
                </div>

                <!-- 3. ENHANCED TTI MODEL CHECKPOINT CARDS -->
                <div v-else class="space-y-2">
                    <div class="flex items-center justify-between px-1 text-[11px] font-mono text-gray-400">
                        <span>Showing {{ filteredConnectionModels.length }} of {{ connectionRawModels.length }} checkpoints</span>
                        <span>Click + Profile to configure</span>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 max-h-[55vh] overflow-y-auto custom-scrollbar pr-1 pb-2">
                        <div 
                            v-for="m in filteredConnectionModels" 
                            :key="m.original_model_name || m.name || m" 
                            class="p-4 bg-white dark:bg-gray-850 rounded-2xl border transition-all duration-200 hover:shadow-md hover:border-pink-400/80 dark:hover:border-pink-600/80 flex flex-col justify-between gap-3 group relative overflow-hidden"
                            :class="isModelAliased(m) ? 'border-pink-300/80 dark:border-pink-900/50 shadow-2xs' : 'border-gray-200/80 dark:border-gray-700/80 shadow-xs'"
                        >
                            <div class="space-y-2">
                                <!-- Card Header: Style Badge + Format Tag -->
                                <div class="flex items-center justify-between gap-2">
                                    <span 
                                        class="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider border flex items-center gap-1 shrink-0"
                                        :class="detectModelStyle(m.original_model_name || m.name || m).badgeClass"
                                    >
                                        <span>{{ detectModelStyle(m.original_model_name || m.name || m).icon }}</span>
                                        <span>{{ detectModelStyle(m.original_model_name || m.name || m).label }}</span>
                                    </span>

                                    <!-- Format pill -->
                                    <span class="text-[9px] font-mono uppercase px-1.5 py-0.2 rounded bg-gray-100 dark:bg-gray-800 text-gray-400 font-bold">
                                        {{ String(m.original_model_name || m.name || m).endsWith('.ckpt') ? 'CKPT' : 'SAFETENSORS' }}
                                    </span>
                                </div>

                                <!-- Human-Readable Formatted Checkpoint Name -->
                                <div>
                                    <h5 class="text-xs font-black text-gray-900 dark:text-white leading-snug group-hover:text-pink-600 dark:group-hover:text-pink-400 transition-colors">
                                        {{ formatCleanTitle(m.original_model_name || m.name || m) }}
                                    </h5>
                                </div>

                                <!-- Raw Filename Pill with Copy Trigger -->
                                <div 
                                    @click="copyModelName(m.original_model_name || m.name || m)" 
                                    class="p-2 rounded-xl bg-gray-50 dark:bg-gray-900/70 border dark:border-gray-800 flex items-center justify-between gap-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                                    title="Click to copy exact checkpoint filename"
                                >
                                    <p class="text-[10px] font-mono text-gray-500 dark:text-gray-400 truncate select-all">
                                        {{ m.original_model_name || m.name || m }}
                                    </p>
                                    <div class="shrink-0 text-gray-400 hover:text-pink-500">
                                        <IconCheckCircle v-if="copiedModel === (m.original_model_name || m.name || m)" class="w-3.5 h-3.5 text-emerald-500" />
                                        <IconCopy v-else class="w-3.5 h-3.5" />
                                    </div>
                                </div>
                            </div>

                            <!-- Card Footer: Status & Action -->
                            <div class="pt-2 border-t border-gray-100 dark:border-gray-800 flex items-center justify-between gap-2">
                                <span v-if="isModelAliased(m)" class="flex items-center gap-1 text-[10px] font-black uppercase text-emerald-600 dark:text-emerald-400 font-mono">
                                    <IconCheckCircle class="w-3.5 h-3.5" />
                                    <span>Profile Ready</span>
                                </span>
                                <span v-else class="text-[10px] font-mono text-gray-400">
                                    Raw Checkpoint
                                </span>

                                <button 
                                    @click="switchToProfilesWithModel(m.original_model_name || m.name || m)" 
                                    class="btn btn-secondary btn-xs py-1 px-2.5 flex items-center gap-1 text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/40 font-bold transition-all cursor-pointer"
                                    title="Open Universal Profiles to configure this model"
                                >
                                    <IconSparkles class="w-3 h-3 text-purple-500" />
                                    <span>+ Profile</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="flex justify-end gap-2 pt-2 border-t dark:border-gray-700/80">
                    <button type="button" @click="hideForm" class="btn btn-secondary text-xs">Close</button>
                </div>
            </div>
        </div>

        <div v-else class="space-y-6">
            <div class="flex justify-between items-center flex-wrap gap-4 bg-white/60 dark:bg-gray-850/50 p-4 rounded-2xl border border-gray-200/80 dark:border-gray-700/60 backdrop-blur-md">
                <div>
                    <h2 class="text-xl font-black tracking-tight text-gray-900 dark:text-white flex items-center gap-2">
                        <IconPhoto class="w-6 h-6 text-pink-500" />
                        <span>Physical TTI Connections</span>
                        <span class="text-xs font-bold px-2.5 py-0.5 rounded-full bg-pink-50 text-pink-600 dark:bg-pink-900/40 dark:text-pink-300">
                            {{ ttiBindings.length }} Connections
                        </span>
                    </h2>
                    <p class="text-xs text-gray-500 mt-0.5">Manage text-to-image engines and diffusion drivers.</p>
                </div>

                <div class="flex items-center gap-2">
                    <button @click="primaryViewTab = 'profiles'" class="btn btn-secondary btn-sm flex items-center gap-1.5 text-purple-600 dark:text-purple-400" title="Switch to Universal Model Profiles">
                        <IconSparkles class="w-3.5 h-3.5" />
                        <span>View Model Profiles</span>
                    </button>
                    <button @click="showAddForm" class="btn btn-primary btn-sm flex items-center gap-1.5 shadow-sm">
                        <span>+ Add Connection</span>
                    </button>
                </div>
            </div>

            <div v-if="isLoadingTtiBindings" class="text-center p-6">Loading TTI bindings...</div>
            <div v-else-if="ttiBindings.length === 0 && !isFormVisible" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <p>No TTI bindings configured yet.</p>
                <button @click="showAddForm" class="mt-2 text-blue-600 hover:underline">Add your first one</button>
            </div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                <div v-for="binding in ttiBindings" :key="binding.id" @click="showEditForm(binding)" class="bg-white dark:bg-gray-800 p-5 rounded-lg shadow-md hover:shadow-lg transition-shadow cursor-pointer flex flex-col gap-4 border border-transparent hover:border-blue-500 group relative">
                    <div class="absolute top-4 right-4 z-10" @click.stop>
                         <button @click="toggleBindingActive(binding)" type="button" :class="[binding.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']" :title="binding.is_active ? 'Deactivate' : 'Activate'">
                            <span :class="[binding.is_active ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>
                    
                    <div class="grow">
                         <div class="flex items-center gap-3 mb-2">
                             <IconPhoto class="w-8 h-8 text-blue-500" />
                             <div>
                                <h4 class="font-bold text-lg text-gray-900 dark:text-white">{{ binding.alias }}</h4>
                                <p class="text-xs text-gray-500 dark:text-gray-400">{{ getBindingTitle(binding.name) }}</p>
                             </div>
                         </div>
                        
                        <div class="mt-3 text-sm text-gray-600 dark:text-gray-300">
                             <p v-if="binding.default_model_name" class="mb-1"><span class="font-semibold">Default:</span> {{ binding.default_model_name }}</p>
                             <p class="text-xs text-gray-400 truncate">{{ binding.config ? Object.keys(binding.config).filter(k=>!k.includes('key')).join(', ') : '' }}</p>
                        </div>
                    </div>
                    
                     <div class="border-t dark:border-gray-700 pt-3 flex justify-between items-center text-xs text-gray-500">
                        <span>Click to edit connection</span>
                        <button @click.stop="handleDelete(binding)" class="text-red-500 hover:underline p-1">Delete</button>
                    </div>
                </div>
            </div>
        </div>
        </div>
    </div>
</template>
