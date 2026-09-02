<!-- frontend/webui/src/components/admin/bindings/LLMBindingsSettings.vue -->
<script setup>
import { ref, onMounted, computed, watch, defineAsyncComponent } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useUiStore } from '../../../stores/ui';
import { useTasksStore } from '../../../stores/tasks';
import { useDataStore } from '../../../stores/data';
import { parsedMarkdown as parseMarkdown } from '../../../services/markdownParser';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconEye from '../../../assets/icons/IconEye.vue';
import IconEyeOff from '../../../assets/icons/IconEyeOff.vue';
import IconTerminal from '../../../assets/icons/ui/IconTerminal.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconPlayCircle from '../../../assets/icons/IconPlayCircle.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import JsonRenderer from '../../ui/JsonRenderer.vue';
import apiClient from '../../../services/api';

const BindingModelsManager = defineAsyncComponent(() => import('./BindingModelsManager.vue'));
const BindingZoo = defineAsyncComponent(() => import('./BindingZoo.vue'));

const adminStore = useAdminStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const dataStore = useDataStore();

const { bindings, availableBindingTypes, isLoadingBindings, globalSettings } = storeToRefs(adminStore);
const { tasks } = storeToRefs(tasksStore);
const { availableLLMModelsGrouped } = storeToRefs(dataStore);

const isFormVisible = ref(false);
const editingBinding = ref(null);
const isLoadingForm = ref(false);
const isKeyVisible = ref({});
const commandParams = ref({});
const activeTab = ref('settings');
const hasZoo = ref(false);

// Smart Router Model Profiles Selection State
const allUniversalProfiles = ref({});
const isSmartRouterBinding = computed(() => {
    return form.value.name === 'smart_router' || form.value.alias === 'smart_router';
});

const currentCommandTaskId = ref(null);
const lastExecutedCommandName = ref(null);
const activeCommandResult = ref(null);

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
    if (!form.value.name) return null;
    const rawTarget = form.value.name.toLowerCase();
    const cleanTarget = rawTarget.replace(/[^a-z0-9]/g, '');

    return availableBindingTypes.value.find(b => {
        const bName = (b.binding_name || '').toLowerCase();
        const bShortName = (b.name || '').toLowerCase();
        return bName === rawTarget || 
               bShortName === rawTarget ||
               bName.replace(/[^a-z0-9]/g, '') === cleanTarget ||
               bShortName.replace(/[^a-z0-9]/g, '') === cleanTarget;
    }) || null;
});

const hasCommands = computed(() => {
    if (!selectedBindingType.value || !Array.isArray(selectedBindingType.value.commands)) return false;
    return selectedBindingType.value.commands.length > 0;
});

async function checkZooAvailability(bindingId) {
    if (!bindingId) { hasZoo.value = false; return; }
    hasZoo.value = false;
    try {
        const res = await adminStore.fetchBindingZoo(bindingId);
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

const currentTask = computed(() => {
    if (!currentCommandTaskId.value) return null;
    return tasks.value.find(t => t.id === currentCommandTaskId.value);
});

watch(currentTask, (newTask) => {
    if (newTask && newTask.status === 'completed') {
        activeCommandResult.value = newTask.result;
    }
}, { deep: true });

const allFormParameters = computed(() => {
    const paramsFromDesc = selectedBindingType.value ? (
        selectedBindingType.value.input_parameters || 
        selectedBindingType.value.global_input_parameters || 
        selectedBindingType.value.parameters || []
    ) : [];
    
    const paramNamesFromDesc = new Set(paramsFromDesc.map(p => p.name));
    const modelParams = selectedBindingType.value ? (
        selectedBindingType.value.model_parameters || 
        selectedBindingType.value.model_input_parameters || []
    ) : [];
    const modelParamNames = new Set(modelParams.map(p => p.name));
    
    const paramsFromConfig = Object.keys(form.value.config || {})
        .filter(key => 
            !paramNamesFromDesc.has(key) && 
            !modelParamNames.has(key) && 
            key !== 'model_name' &&
            key !== 'model' &&
            key !== 'class' &&
            key !== 'model_profiles'
        )
        .map(key => ({
            name: key,
            type: typeof form.value.config[key] === 'boolean' ? 'bool' : (typeof form.value.config[key] === 'number' ? 'float' : 'str'),
            description: `(Configuration parameter)`,
            mandatory: false,
        }));
        
    return [
        ...paramsFromDesc.filter(p => !modelParamNames.has(p.name) && p.name !== 'model_name'), 
        ...paramsFromConfig
    ];
});

async function fetchUniversalProfiles() {
    try {
        const res = await apiClient.get('/api/admin/universal-profiles');
        allUniversalProfiles.value = res.data.profiles || {};
    } catch (e) {
        console.error("Failed to fetch universal profiles:", e);
    }
}

onMounted(() => {
    adminStore.fetchBindings();
    adminStore.fetchAvailableBindingTypes();
    adminStore.fetchGlobalSettings();
    dataStore.fetchAvailableLollmsModels();
    fetchUniversalProfiles();
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
    if (!form.value.config) form.value.config = {};
    isKeyVisible.value = {};

    fetchUniversalProfiles();
    checkZooAvailability(binding.id);

    const bType = availableBindingTypes.value.find(b => (b.binding_name || b.name) === binding.name);
    if (bType && bType.commands && Array.isArray(bType.commands)) {
        const params = {};
        bType.commands.forEach(cmd => {
            params[cmd.name] = {};
            if (cmd.parameters && Array.isArray(cmd.parameters)) {
                cmd.parameters.forEach(p => {
                    params[cmd.name][p.name] = p.default !== undefined ? p.default : '';
                });
            }
        });
        commandParams.value = params;
    } else {
        commandParams.value = {};
    }

    currentCommandTaskId.value = null;
    activeCommandResult.value = null;
    lastExecutedCommandName.value = null;

    isFormVisible.value = true;
    activeTab.value = 'settings';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function executeCommand(cmd, bindingId, params) {
    currentCommandTaskId.value = null;
    activeCommandResult.value = null;
    lastExecutedCommandName.value = cmd.name;

    try {
        uiStore.addNotification(`Submitting command '${cmd.title || cmd.name}'...`, 'info');
        const taskInfo = await adminStore.executeBindingCommand(bindingId, cmd.name, params);
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

function hideForm() {
    isFormVisible.value = false;
    editingBinding.value = null;
}

function parseOptions(options) {
    if (typeof options === 'string') return options.split(',').map(o => o.trim()).filter(Boolean);
    if (Array.isArray(options)) return options.filter(Boolean);
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
            await adminStore.updateBinding(editingBinding.value.id, payload);
        } else {
            await adminStore.addBinding(payload);
        }
        await dataStore.fetchAvailableLollmsModels();
        hideForm();
    } finally {
        isLoadingForm.value = false;
    }
}

async function handleDelete(binding) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Binding '${binding.alias}'?`,
        message: 'This will permanently remove the binding and its registered profiles.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        await adminStore.deleteBinding(binding.id);
        await dataStore.fetchAvailableLollmsModels();
    }
}

async function toggleBindingActive(binding) {
    await adminStore.updateBinding(binding.id, { is_active: !binding.is_active });
    await dataStore.fetchAvailableLollmsModels();
}

function getBindingTitle(name) {
    if (!Array.isArray(availableBindingTypes.value)) return name;
    const bindingType = availableBindingTypes.value.find(b => (b.binding_name || b.name) === name);
    return bindingType ? (bindingType.title || bindingType.name) : name;
}

function openPolicyModal() {
    uiStore.openModal('forceSettings');
}

async function handleHealProfiles() {
    try {
        const res = await apiClient.post('/api/admin/bindings/migrate-and-heal');
        uiStore.addNotification(res.data.message, 'success');
        await adminStore.fetchBindings(true);
    } catch (e) {
        uiStore.addNotification('Healing operation failed.', 'error');
    }
}
</script>

<template>
    <div class="space-y-8">
        <!-- EDIT / ADD FORM VIEW -->
        <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 shadow-md rounded-2xl p-6 border border-gray-100 dark:border-gray-700">
            <div class="flex justify-between items-center mb-6 pb-3 border-b dark:border-gray-700">
                <div>
                    <span class="text-[9px] font-black uppercase text-blue-500 tracking-widest">{{ isEditMode ? 'Connection Configuration' : 'New Connection' }}</span>
                    <h3 class="text-xl font-bold text-gray-900 dark:text-white">{{ isEditMode ? form.alias : 'Register Engine Binding' }}</h3>
                </div>
                <div v-if="isEditMode" class="flex gap-2 text-xs font-bold overflow-x-auto p-1 bg-gray-100 dark:bg-gray-700/50 rounded-xl">
                    <button @click="activeTab = 'settings'" :class="{'bg-white dark:bg-gray-600 text-blue-600 shadow-sm': activeTab === 'settings', 'text-gray-500': activeTab !== 'settings'}" class="px-3 py-1.5 rounded-lg transition-all">Connection Settings</button>
                    <button @click="activeTab = 'models'" :class="{'bg-white dark:bg-gray-600 text-blue-600 shadow-sm': activeTab === 'models', 'text-gray-500': activeTab !== 'models'}" class="px-3 py-1.5 rounded-lg transition-all">Universal Profiles</button>
                    <button v-if="hasZoo" @click="activeTab = 'zoo'" :class="{'bg-white dark:bg-gray-600 text-blue-600 shadow-sm': activeTab === 'zoo', 'text-gray-500': activeTab !== 'zoo'}" class="px-3 py-1.5 rounded-lg transition-all">Models Zoo</button>
                    <button v-if="hasCommands" @click="activeTab = 'commands'" :class="{'bg-white dark:bg-gray-600 text-blue-600 shadow-sm': activeTab === 'commands', 'text-gray-500': activeTab !== 'commands'}" class="px-3 py-1.5 rounded-lg transition-all">Commands</button>
                </div>
            </div>

            <!-- Settings Tab -->
            <div v-if="activeTab === 'settings'">
                <form @submit.prevent="handleSubmit" class="space-y-6">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
                        <div>
                            <label for="alias" class="block text-xs font-bold uppercase text-gray-500 mb-1">Binding Alias *</label>
                            <input type="text" id="alias" v-model="form.alias" class="input-field text-xs" required placeholder="e.g., local_ollama">
                        </div>
                        <div>
                            <label for="name" class="block text-xs font-bold uppercase text-gray-500 mb-1">Engine Type *</label>
                            <select id="name" v-model="form.name" class="input-field text-xs" required :disabled="isEditMode">
                                <option disabled value="">Select engine type</option>
                                <option v-for="type in availableBindingTypes" :key="type.binding_name || type.name" :value="type.binding_name || type.name">{{ type.title || type.name }}</option>
                            </select>
                        </div>
                    </div>

                    <!-- Smart Router Composition View -->
                    <div v-if="isSmartRouterBinding" class="p-5 bg-purple-50/50 dark:bg-purple-950/20 rounded-2xl border border-purple-200 dark:border-purple-800/60 space-y-4">
                        <div class="flex items-center justify-between border-b border-purple-200 dark:border-purple-800/60 pb-3">
                            <div>
                                <h4 class="font-black text-sm text-purple-900 dark:text-purple-200 uppercase tracking-wider flex items-center gap-2">
                                    <span>⚡ Smart Router Composition Matrix</span>
                                </h4>
                                <p class="text-xs text-purple-700 dark:text-purple-300 mt-0.5">
                                    Select which universal model profiles participate in the automated auto-router pool. No duplicate configuration required.
                                </p>
                            </div>
                            <div class="flex items-center gap-2">
                                <label class="text-[10px] font-bold uppercase text-purple-800 dark:text-purple-300">Strategy:</label>
                                <select v-model="form.config.routing_strategy" class="input-field text-xs !py-1 !px-2 bg-white dark:bg-gray-800">
                                    <option value="balanced">Balanced (Subject + Tier + Latency)</option>
                                    <option value="cost_optimized">Cost-Optimized</option>
                                    <option value="quality_optimized">Quality-Optimized</option>
                                </select>
                            </div>
                        </div>

                        <!-- Grid of All Available Universal Profiles -->
                        <div class="space-y-2 max-h-80 overflow-y-auto custom-scrollbar pr-1">
                            <div v-for="(prof, profId) in allUniversalProfiles" :key="profId" 
                                 v-show="prof.binding_alias !== form.alias"
                                 class="p-3 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 flex items-center justify-between gap-4">
                                <div class="flex items-center gap-3 min-w-0">
                                    <div class="w-8 h-8 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center shrink-0">
                                        <IconCpuChip class="w-4 h-4 text-purple-500" />
                                    </div>
                                    <div class="min-w-0">
                                        <div class="flex items-center gap-2">
                                            <span class="font-bold text-xs text-gray-900 dark:text-white truncate">{{ prof.title }}</span>
                                            <span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300">Tier {{ prof.routing_config?.complexity_tier || 2 }}</span>
                                            <IconEye v-if="prof.vision_enabled" class="w-3.5 h-3.5 text-blue-500" title="Vision Capable" />
                                        </div>
                                        <p class="text-[10px] text-gray-500 truncate font-mono">{{ prof.id }}</p>
                                    </div>
                                </div>

                                <div class="flex items-center gap-3 text-xs shrink-0">
                                    <span class="font-mono text-[10px] text-gray-400 hidden sm:inline">{{ prof.routing_config?.avg_latency_ms || 200 }}ms</span>
                                    <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200">
                                        Included in Router
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Global Binding Parameters -->
                    <div v-if="selectedBindingType && !isSmartRouterBinding" class="space-y-4 border-t dark:border-gray-700/80 pt-5">
                        <div v-for="param in allFormParameters" :key="param.name" class="space-y-1">
                            <label :for="`param-${param.name}`" class="block text-xs font-bold uppercase text-gray-500">
                                {{ param.name.replace(/_/g, ' ') }}
                                <span v-if="param.mandatory" class="text-red-500">*</span>
                            </label>
                            
                            <select v-if="param.options && param.options.length > 0" :id="`param-${param.name}`" v-model="form.config[param.name]" class="input-field text-xs">
                                <option v-for="option in parseOptions(param.options)" :key="option" :value="option">{{ option }}</option>
                            </select>

                            <div v-else-if="['str', 'int', 'float'].includes(param.type)">
                                <div class="relative">
                                    <input :type="(param.name.includes('key') || param.name.includes('token')) && !isKeyVisible[param.name] ? 'password' : 'text'" 
                                        :id="`param-${param.name}`" v-model="form.config[param.name]" class="input-field text-xs"
                                        :required="param.mandatory" :placeholder="param.description" autocomplete="off">
                                    <button v-if="param.name.includes('key') || param.name.includes('token')" type="button" @click="isKeyVisible[param.name] = !isKeyVisible[param.name]" class="absolute inset-y-0 right-0 px-3 flex items-center text-gray-400 hover:text-gray-600">
                                        <IconEyeOff v-if="isKeyVisible[param.name]" class="w-4 h-4" />
                                        <IconEye v-else class="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                            <div v-else-if="param.type === 'bool'" class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-700">
                                <span class="text-xs text-gray-600 dark:text-gray-400">{{ param.description }}</span>
                                <button @click="form.config[param.name] = !form.config[param.name]" type="button" :class="[form.config[param.name] ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                                    <span :class="[form.config[param.name] ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                        </div>
                    </div>

                    <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-700">
                        <span class="text-xs font-bold text-gray-800 dark:text-gray-200">Active Connection</span>
                        <button @click="form.is_active = !form.is_active" type="button" :class="[form.is_active ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                            <span :class="[form.is_active ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>

                    <div class="flex justify-end gap-3 pt-2">
                        <button type="button" @click="hideForm" class="btn btn-secondary text-xs">Close</button>
                        <button type="submit" class="btn btn-primary text-xs" :disabled="isLoadingForm">
                            <IconAnimateSpin v-if="isLoadingForm" class="w-4 h-4 mr-1.5 animate-spin" />
                            <span>{{ isEditMode ? 'Save Connection' : 'Add Binding' }}</span>
                        </button>
                    </div>
                </form>
            </div>

            <!-- Profiles Tab -->
            <div v-else-if="activeTab === 'models'">
                <BindingModelsManager :binding="editingBinding" binding-type="llm" />
            </div>

            <!-- Zoo Tab -->
            <div v-else-if="activeTab === 'zoo'">
                <BindingZoo :binding="editingBinding" binding-type="llm" />
            </div>

            <!-- Commands Tab -->
            <div v-else-if="activeTab === 'commands' && hasCommands" class="space-y-6">
                <div v-for="cmd in selectedBindingType.commands" :key="cmd.name" class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-2xl border dark:border-gray-600 mb-4">
                    <div class="flex justify-between items-start mb-3">
                        <div>
                            <h5 class="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2">
                                <IconTerminal class="w-4 h-4 text-blue-500"/>
                                <span>{{ cmd.title || cmd.name }}</span>
                            </h5>
                            <p class="text-xs text-gray-500 mt-1">{{ cmd.description }}</p>
                        </div>
                        <button 
                            type="button" 
                            @click="executeCommand(cmd, editingBinding.id, commandParams[cmd.name])" 
                            class="btn btn-primary btn-sm flex items-center gap-1.5"
                            :disabled="currentTask && (currentTask.status === 'running' || currentTask.status === 'pending')"
                        >
                            <IconPlayCircle class="w-4 h-4" />
                            <span>Execute</span>
                        </button>
                    </div>

                    <div v-if="cmd.parameters && cmd.parameters.length > 0" class="space-y-3 mb-4 p-3 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700">
                        <div v-for="p in cmd.parameters" :key="p.name">
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">{{ p.name }}</label>
                            <input v-if="p.type !== 'bool'" type="text" v-model="commandParams[cmd.name][p.name]" class="input-field text-xs" :placeholder="p.default">
                            <div v-else class="flex items-center gap-2">
                                <button @click="commandParams[cmd.name][p.name] = !commandParams[cmd.name][p.name]" type="button" :class="[commandParams[cmd.name][p.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                                    <span :class="[commandParams[cmd.name][p.name] ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                </button>
                                <span class="text-xs text-gray-600 dark:text-gray-400">{{ p.description }}</span>
                            </div>
                        </div>
                    </div>

                    <div v-if="currentTask && lastExecutedCommandName === cmd.name && (currentTask.status === 'running' || currentTask.status === 'pending')" class="mt-4">
                        <div class="flex justify-between text-xs mb-1 font-semibold text-blue-600 dark:text-blue-400">
                            <span>Executing command...</span>
                            <span>{{ currentTask.progress }}%</span>
                        </div>
                        <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                            <div class="bg-blue-600 h-2 rounded-full transition-all duration-300 relative overflow-hidden" :style="{ width: currentTask.progress + '%' }">
                                <div class="absolute inset-0 bg-white/20 animate-pulse"></div>
                            </div>
                        </div>
                        <p class="text-xs text-gray-500 mt-1 truncate">{{ currentTask.description }}</p>
                    </div>

                    <div v-if="activeCommandResult && lastExecutedCommandName === cmd.name && currentTask && currentTask.status === 'completed'" class="mt-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl">
                        <h6 class="text-xs font-bold text-green-800 dark:text-green-300 mb-2 uppercase flex items-center gap-2">
                            <IconCheckCircle class="w-4 h-4 text-green-500" />
                            <span>Command Finished</span>
                        </h6>
                        <div v-if="typeof activeCommandResult === 'object'">
                            <JsonRenderer :json="activeCommandResult" />
                        </div>
                        <div v-else class="whitespace-pre-wrap text-xs text-gray-800 dark:text-gray-200 font-mono">
                            {{ activeCommandResult }}
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- MAIN BINDINGS LIST VIEW -->
        <div v-else class="space-y-6">
            <div class="flex justify-between items-center flex-wrap gap-4 bg-white/60 dark:bg-gray-850/50 p-4 rounded-2xl border border-gray-200/80 dark:border-gray-700/60 backdrop-blur-md">
                <div>
                    <h2 class="text-xl font-black tracking-tight text-gray-900 dark:text-white flex items-center gap-2">
                        <IconCpuChip class="w-6 h-6 text-blue-500" />
                        <span>LLM Universal Bindings</span>
                        <span class="text-xs font-bold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-600 dark:bg-blue-900/40 dark:text-blue-300">
                            {{ bindings.length }} Connections
                        </span>
                    </h2>
                    <p class="text-xs text-gray-500 mt-0.5">Manage connection engines, universal model profiles, and smart routing policies.</p>
                </div>

                <div class="flex items-center gap-2">
                    <button @click="handleHealProfiles" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Heal orphaned user preferences and migrate legacy aliases">
                        <IconSparkles class="w-3.5 h-3.5 text-purple-500" />
                        <span>Sync & Heal</span>
                    </button>

                    <button @click="openPolicyModal" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Force models or set system defaults for users">
                        <IconCpuChip class="w-3.5 h-3.5 text-blue-500" />
                        <span>⚡ Policy & Defaults</span>
                    </button>

                    <button @click="showAddForm" class="btn btn-primary btn-sm flex items-center gap-1.5 shadow-sm">
                        <span>+ Add Engine Binding</span>
                    </button>
                </div>
            </div>

            <div v-if="isLoadingBindings" class="text-center py-12 text-xs font-bold text-gray-400">Loading engine bindings...</div>
            <div v-else-if="bindings.length === 0" class="text-center py-16 bg-gray-50 dark:bg-gray-800/40 rounded-2xl border border-dashed dark:border-gray-700">
                <IconCpuChip class="w-12 h-12 text-gray-400 mx-auto mb-2 opacity-40" />
                <p class="text-sm font-bold text-gray-700 dark:text-gray-300">No LLM Bindings Configured</p>
                <button @click="showAddForm" class="btn btn-primary btn-sm mt-3">+ Add First Binding</button>
            </div>

            <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                <div v-for="binding in bindings" :key="binding.id" @click="showEditForm(binding)" 
                     class="bg-white dark:bg-gray-800/90 p-5 rounded-2xl shadow-xs hover:shadow-lg transition-all cursor-pointer flex flex-col justify-between border border-gray-200/80 dark:border-gray-700/80 hover:border-blue-500 group relative">
                    <div>
                        <div class="flex items-start justify-between gap-3 mb-3">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400 font-black shrink-0">
                                    <IconCpuChip class="w-5 h-5" />
                                </div>
                                <div class="min-w-0">
                                    <h4 class="font-bold text-sm text-gray-900 dark:text-white truncate">{{ binding.alias }}</h4>
                                    <p class="text-[10px] text-gray-500 font-mono capitalize">{{ getBindingTitle(binding.name) }}</p>
                                </div>
                            </div>

                            <button @click.stop="toggleBindingActive(binding)" type="button" :class="[binding.is_active ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out']">
                                <span :class="[binding.is_active ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>

                        <!-- Stats & Info -->
                        <div class="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-xl border dark:border-gray-700/60 text-xs space-y-1.5 font-mono">
                            <div class="flex justify-between items-center text-[10px]">
                                <span class="text-gray-400">Profiles:</span>
                                <span class="font-bold text-blue-500">{{ Object.keys(binding.model_aliases || {}).length }} Universal Profiles</span>
                            </div>
                            <div v-if="binding.default_model_name" class="flex justify-between items-center text-[10px] truncate">
                                <span class="text-gray-400">Default:</span>
                                <span class="font-bold text-gray-700 dark:text-gray-300 truncate max-w-[140px]">{{ binding.default_model_name }}</span>
                            </div>
                        </div>
                    </div>

                    <div class="border-t dark:border-gray-700/60 pt-3 mt-4 flex justify-between items-center text-xs">
                        <span class="text-blue-500 font-bold text-[10px] uppercase tracking-wider group-hover:underline">Configure Profiles &rarr;</span>
                        <button @click.stop="handleDelete(binding)" class="text-rose-500 hover:text-rose-700 font-bold text-[10px] uppercase">Delete</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
</style>