<script setup>
import { ref, onMounted, computed, watch, defineAsyncComponent } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useUiStore } from '../../../stores/ui';
import { useTasksStore } from '../../../stores/tasks';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconEye from '../../../assets/icons/IconEye.vue';
import IconEyeOff from '../../../assets/icons/IconEyeOff.vue';
import IconTerminal from '../../../assets/icons/ui/IconTerminal.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconPlayCircle from '../../../assets/icons/IconPlayCircle.vue';
import JsonRenderer from '../../ui/JsonRenderer.vue';

const BindingModelsManager = defineAsyncComponent(() => import('./BindingModelsManager.vue'));
const BindingZoo = defineAsyncComponent(() => import('./BindingZoo.vue'));

const adminStore = useAdminStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();

const { bindings, availableBindingTypes, isLoadingBindings, globalSettings } = storeToRefs(adminStore);
const { tasks } = storeToRefs(tasksStore);

const isFormVisible = ref(false);
const editingBinding = ref(null);
const isLoadingForm = ref(false);
const isKeyVisible = ref({});
const commandParams = ref({});
const activeTab = ref('settings');

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
    return availableBindingTypes.value.find(b => b.binding_name === form.value.name);
});

const allFormParameters = computed(() => {
    if (!selectedBindingType.value) return [];
    
    const paramsFromDesc = selectedBindingType.value.input_parameters || [];
    const paramNamesFromDesc = new Set(paramsFromDesc.map(p => p.name));
    
    const paramsFromConfig = Object.keys(form.value.config || {})
        .filter(key => !paramNamesFromDesc.has(key) && key !== 'model_name')
        .map(key => ({
            name: key,
            type: typeof form.value.config[key] === 'boolean' ? 'bool' : (typeof form.value.config[key] === 'number' ? 'float' : 'str'),
            description: `(Parameter not in binding description)`,
            mandatory: false,
        }));
        
    return [
        ...paramsFromDesc.filter(p => p.name !== 'model_name'), 
        ...paramsFromConfig
    ];
});

watch(() => form.value.name, (newName, oldName) => {
    if (newName !== oldName && !isEditMode.value) {
        const bindingDesc = availableBindingTypes.value.find(b => b.binding_name === newName);
        const newConfig = {};
        if (bindingDesc && bindingDesc.input_parameters) {
            bindingDesc.input_parameters.forEach(param => {
                newConfig[param.name] = param.default;
            });
        }
        form.value.config = newConfig;
    }
});

const modelDisplayMode = computed({
  get() {
    if (!Array.isArray(globalSettings.value)) {
        return 'mixed';
    }
    const setting = globalSettings.value.find(s => s.key === 'model_display_mode');
    return setting ? setting.value : 'mixed';
  },
  set(newValue) {
    adminStore.updateGlobalSettings({ 'model_display_mode': newValue });
  }
});

onMounted(() => {
    adminStore.fetchBindings();
    adminStore.fetchAvailableBindingTypes();
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
    
    const bindingType = availableBindingTypes.value.find(b => b.binding_name === binding.name);
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
            await adminStore.updateBinding(editingBinding.value.id, payload);
        } else {
            await adminStore.addBinding(payload);
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
        title: `Delete Binding '${binding.alias}'?`,
        message: 'Are you sure? This action cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        await adminStore.deleteBinding(binding.id);
    }
}

async function toggleBindingActive(binding) {
    await adminStore.updateBinding(binding.id, { is_active: !binding.is_active });
}

function getBindingTitle(name) {
    const bindingType = availableBindingTypes.value.find(b => b.binding_name === name);
    return bindingType ? bindingType.title : name;
}

async function executeCommand(cmd, bindingId, params) {
    // Reset state for new execution
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
</script>

<template>
    <div class="space-y-8">
        <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 shadow-md rounded-lg p-6">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-xl font-semibold">{{ isEditMode ? 'Edit Binding: ' + form.alias : 'Add New Binding' }}</h3>
                <div v-if="isEditMode" class="flex gap-2 text-sm font-medium overflow-x-auto">
                    <button @click="activeTab = 'settings'" :class="{'text-blue-600 border-b-2 border-blue-600': activeTab === 'settings', 'text-gray-500 hover:text-gray-700': activeTab !== 'settings'}" class="px-3 py-2 whitespace-nowrap">Settings</button>
                    <button @click="activeTab = 'commands'" :class="{'text-blue-600 border-b-2 border-blue-600': activeTab === 'commands', 'text-gray-500 hover:text-gray-700': activeTab !== 'commands'}" class="px-3 py-2 whitespace-nowrap">Commands</button>
                    <button @click="activeTab = 'zoo'" :class="{'text-blue-600 border-b-2 border-blue-600': activeTab === 'zoo', 'text-gray-500 hover:text-gray-700': activeTab !== 'zoo'}" class="px-3 py-2 whitespace-nowrap">Models Zoo</button>
                    <button @click="activeTab = 'models'" :class="{'text-blue-600 border-b-2 border-blue-600': activeTab === 'models', 'text-gray-500 hover:text-gray-700': activeTab !== 'models'}" class="px-3 py-2 whitespace-nowrap">Installed Models</button>
                </div>
            </div>

            <!-- Settings Tab -->
            <div v-if="activeTab === 'settings'">
                <form @submit.prevent="handleSubmit" class="space-y-6">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label for="alias" class="block text-sm font-medium">Alias <span class="text-red-500">*</span></label>
                            <input type="text" id="alias" v-model="form.alias" class="input-field mt-1" required placeholder="e.g., local_ollama" autocomplete="off">
                            <p class="text-xs text-gray-500 mt-1">A unique, short name for this configuration.</p>
                        </div>
                        <div>
                            <label for="name" class="block text-sm font-medium">Binding Type <span class="text-red-500">*</span></label>
                            <select id="name" v-model="form.name" class="input-field mt-1" required :disabled="isEditMode">
                                <option disabled value="">Select a type</option>
                                <option v-for="type in availableBindingTypes" :key="type.binding_name" :value="type.binding_name">{{ type.title }}</option>
                            </select>
                        </div>
                    </div>

                    <div v-if="selectedBindingType" class="space-y-6 border-t dark:border-gray-700 pt-6">
                        <p class="text-sm text-gray-600 dark:text-gray-400">{{ selectedBindingType.description }}</p>
                        <div v-for="param in allFormParameters" :key="param.name" class="space-y-1">
                            <label :for="`param-${param.name}`" class="block text-sm font-medium capitalize">
                                {{ param.name.replace(/_/g, ' ') }}
                                <span v-if="param.mandatory" class="text-red-500">*</span>
                            </label>
                            
                            <select v-if="param.options && param.options.length > 0" :id="`param-${param.name}`" v-model="form.config[param.name]" class="input-field">
                                <option v-for="option in parseOptions(param.options)" :key="option" :value="option">{{ option }}</option>
                            </select>

                            <div v-else-if="['str', 'int', 'float'].includes(param.type)">
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
                                <span class="flex-grow flex flex-col pr-4"><span class="text-sm text-gray-500 dark:text-gray-400">{{ param.description }}</span></span>
                                <button @click="form.config[param.name] = !form.config[param.name]" type="button" :class="[form.config[param.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                    <span :class="[form.config[param.name] ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                            <p class="text-xs text-gray-500 mt-1">{{ param.description }}</p>
                        </div>
                    </div>
                    
                    <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                        <span class="flex-grow flex flex-col"><span class="text-sm font-medium text-gray-900 dark:text-gray-100">Active</span><span class="text-sm text-gray-500 dark:text-gray-400">If disabled, users cannot see or use models from this binding.</span></span>
                        <button @click="form.is_active = !form.is_active" type="button" :class="[form.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                            <span :class="[form.is_active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                        </button>
                    </div>

                    <div class="flex justify-end gap-3">
                        <button type="button" @click="hideForm" class="btn btn-secondary">Close</button>
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
                                     <button @click="commandParams[cmd.name][p.name] = !commandParams[cmd.name][p.name]" type="button" :class="[commandParams[cmd.name][p.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
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

            <!-- Zoo Tab -->
            <div v-else-if="activeTab === 'zoo'">
                <BindingZoo :binding="editingBinding" binding-type="llm" />
                <div class="flex justify-end gap-3 mt-4">
                     <button type="button" @click="hideForm" class="btn btn-secondary">Close</button>
                </div>
            </div>

            <!-- Installed Models Tab -->
            <div v-else-if="activeTab === 'models'">
                <BindingModelsManager :binding="editingBinding" binding-type="llm" />
                <div class="flex justify-end gap-3 mt-4">
                     <button type="button" @click="hideForm" class="btn btn-secondary">Close</button>
                </div>
            </div>
        </div>

        <div v-else>
            <div class="flex justify-between items-center mb-4 flex-wrap gap-4">
                <h2 class="text-2xl font-bold">LLM Bindings</h2>
                <div class="flex items-center gap-4">
                    <div>
                        <label for="model-display-mode" class="block text-xs font-medium text-gray-500 dark:text-gray-400">Model Display Mode</label>
                        <select id="model-display-mode" v-model="modelDisplayMode" class="input-field mt-1">
                            <option value="mixed">Mixed (Alias or Original)</option>
                            <option value="aliased">Aliased Only</option>
                            <option value="original">Original Names Only</option>
                        </select>
                    </div>
                    <button @click="showAddForm" class="btn btn-primary self-end">+ Add New Binding</button>
                </div>
            </div>

            <div v-if="isLoadingBindings" class="text-center p-6">Loading bindings...</div>
            <div v-else-if="bindings.length === 0" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <p>No LLM bindings configured yet.</p>
                <button @click="showAddForm" class="mt-2 text-blue-600 hover:underline">Add your first one</button>
            </div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                <div v-for="binding in bindings" :key="binding.id" @click="showEditForm(binding)" class="bg-white dark:bg-gray-800 p-5 rounded-lg shadow-md hover:shadow-lg transition-shadow cursor-pointer flex flex-col gap-4 border border-transparent hover:border-blue-500 group relative">
                    <div class="absolute top-4 right-4 z-10" @click.stop>
                         <button @click="toggleBindingActive(binding)" type="button" :class="[binding.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']" :title="binding.is_active ? 'Deactivate' : 'Activate'">
                            <span :class="[binding.is_active ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>
                    
                    <div class="flex-grow">
                         <div class="flex items-center gap-3 mb-2">
                             <IconCpuChip class="w-8 h-8 text-blue-500" />
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
                        <span>Click to edit</span>
                        <button @click.stop="handleDelete(binding)" class="text-red-500 hover:underline p-1">Delete</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
