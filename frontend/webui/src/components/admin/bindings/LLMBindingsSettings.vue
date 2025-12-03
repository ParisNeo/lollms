<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useUiStore } from '../../../stores/ui';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconEye from '../../../assets/icons/IconEye.vue';
import IconEyeOff from '../../../assets/icons/IconEyeOff.vue';
import IconTerminal from '../../../assets/icons/ui/IconTerminal.vue';
import GenericModal from '../../modals/GenericModal.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { bindings, availableBindingTypes, isLoadingBindings, globalSettings } = storeToRefs(adminStore);

const isFormVisible = ref(false);
const editingBinding = ref(null);
const isLoadingForm = ref(false);
const isKeyVisible = ref({});
const commandParams = ref({}); // To store parameters for commands in form

// Modal state for commands
const isCommandsModalVisible = ref(false);
const activeBindingForCommands = ref(null);
const activeBindingCommands = ref([]);
const selectedCommand = ref(null);
const modalCommandParams = ref({});
const isExecutingCommand = ref(false);

const getInitialFormState = () => ({
    id: null,
    alias: '',
    name: '',
    config: {},
    default_model_name: '', // Ensure this key exists for consistency
    is_active: true
});

const form = ref(getInitialFormState());

const isEditMode = computed(() => editingBinding.value !== null);

const selectedBindingType = computed(() => {
    if (!form.value.name) return null;
    return availableBindingTypes.value.find(b => b.binding_name === form.value.name);
});

// Create a comprehensive list of parameters from both the description and the saved config
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
        return 'mixed'; // Return default if store is not ready
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
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showEditForm(binding) {
    editingBinding.value = binding;
    form.value = JSON.parse(JSON.stringify(binding));
    if (!form.value.config) {
        form.value.config = {};
    }
    isKeyVisible.value = {};
    
    // Initialize command params for the edit form section
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

    isFormVisible.value = true;
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
        // Construct a clean payload that matches the backend Pydantic model
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
        // Error is now primarily handled in the store, but we catch to stop loading indicator
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

function manageModels(binding) {
    uiStore.openModal('manageModels', { binding, bindingType: 'llm' });
}

function getBindingTitle(name) {
    const bindingType = availableBindingTypes.value.find(b => b.binding_name === name);
    return bindingType ? bindingType.title : name;
}

async function executeCommand(cmd, bindingId, params) {
    try {
        uiStore.addNotification(`Submitting command '${cmd.title || cmd.name}'...`, 'info');
        const result = await adminStore.executeBindingCommand(bindingId, cmd.name, params);
        if (result) {
             uiStore.addNotification(`Task started: ${cmd.title || cmd.name}. Check Task Manager for progress.`, 'success', 5000);
             return result;
        }
    } catch (e) {
        console.error(e);
        uiStore.addNotification(`Command submission failed: ${e.message}`, 'error');
    }
}

// ----- Commands Modal Logic -----
function showCommands(binding) {
    activeBindingForCommands.value = binding;
    const bindingType = availableBindingTypes.value.find(b => b.binding_name === binding.name);
    activeBindingCommands.value = bindingType ? (bindingType.commands || []) : [];
    selectedCommand.value = null;
    modalCommandParams.value = {};
    isCommandsModalVisible.value = true;
}

function selectCommandInModal(cmd) {
    selectedCommand.value = cmd;
    modalCommandParams.value = {};
    if(cmd.parameters) {
        cmd.parameters.forEach(p => {
             modalCommandParams.value[p.name] = p.default !== undefined ? p.default : '';
        });
    }
}

async function executeModalCommand() {
    if (!selectedCommand.value || !activeBindingForCommands.value) return;
    
    isExecutingCommand.value = true;
    try {
        await executeCommand(selectedCommand.value, activeBindingForCommands.value.id, modalCommandParams.value);
        isCommandsModalVisible.value = false;
    } finally {
        isExecutingCommand.value = false;
    }
}
</script>

<template>
    <div class="space-y-8">
        <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 shadow-md rounded-lg p-6">
            <h3 class="text-xl font-semibold mb-4">{{ isEditMode ? 'Edit Binding' : 'Add New Binding' }}</h3>
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

                <!-- Binding Commands Section (Inside Form) -->
                <div v-if="isEditMode && selectedBindingType && selectedBindingType.commands && selectedBindingType.commands.length > 0" class="mt-6 border-t dark:border-gray-700 pt-6">
                    <h4 class="text-lg font-semibold mb-4">Binding Commands</h4>
                    <div class="grid grid-cols-1 gap-4">
                        <div v-for="cmd in selectedBindingType.commands" :key="cmd.name" class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg border dark:border-gray-600">
                            <div class="flex justify-between items-start mb-3">
                                <div>
                                    <h5 class="font-bold text-md">{{ cmd.title || cmd.name }}</h5>
                                    <p class="text-sm text-gray-600 dark:text-gray-400">{{ cmd.description }}</p>
                                </div>
                            </div>
                            
                            <div v-if="cmd.parameters && cmd.parameters.length > 0" class="space-y-3 mb-4">
                                <div v-for="p in cmd.parameters" :key="p.name">
                                    <label class="block text-xs font-medium uppercase text-gray-500 dark:text-gray-400 mb-1">{{ p.name }}</label>
                                    <input v-if="p.type !== 'bool'" type="text" v-model="commandParams[cmd.name][p.name]" class="input-field text-sm" :placeholder="p.default">
                                    <div v-else class="flex items-center gap-2">
                                        <button @click="commandParams[cmd.name][p.name] = !commandParams[cmd.name][p.name]" type="button" :class="[commandParams[cmd.name][p.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                            <span :class="[commandParams[cmd.name][p.name] ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                        </button>
                                        <span class="text-sm">{{ p.description }}</span>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="flex justify-end">
                                <button type="button" @click="executeCommand(cmd, editingBinding.id, commandParams[cmd.name])" class="btn btn-primary btn-sm">Execute</button>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                    <span class="flex-grow flex flex-col"><span class="text-sm font-medium text-gray-900 dark:text-gray-100">Active</span><span class="text-sm text-gray-500 dark:text-gray-400">If disabled, users cannot see or use models from this binding.</span></span>
                    <button @click="form.is_active = !form.is_active" type="button" :class="[form.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                        <span :class="[form.is_active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                    </button>
                </div>

                <div class="flex justify-end gap-3">
                    <button type="button" @click="hideForm" class="btn btn-secondary">Cancel</button>
                    <button type="submit" class="btn btn-primary" :disabled="isLoadingForm">{{ isLoadingForm ? 'Saving...' : (isEditMode ? 'Save Changes' : 'Add Binding') }}</button>
                </div>
            </form>
        </div>

        <div>
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
                    <button @click="showAddForm" class="btn btn-primary self-end" v-if="!isFormVisible">+ Add New Binding</button>
                </div>
            </div>

            <div v-if="isLoadingBindings" class="text-center p-6">Loading bindings...</div>
            <div v-else-if="bindings.length === 0 && !isFormVisible" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <p>No LLM bindings configured yet.</p>
                <button @click="showAddForm" class="mt-2 text-blue-600 hover:underline">Add your first one</button>
            </div>
            <div v-else class="space-y-4">
                <div v-for="binding in bindings" :key="binding.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md flex flex-col gap-4">
                    <div class="flex-grow">
                        <div class="flex justify-between items-center">
                            <div class="flex items-center gap-3">
                                <h4 class="font-bold text-lg text-gray-900 dark:text-white">{{ binding.alias }}</h4>
                                <button @click.stop="toggleBindingActive(binding)" type="button" :class="[binding.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']" :title="binding.is_active ? 'Deactivate' : 'Activate'">
                                    <span :class="[binding.is_active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                            <div class="flex gap-3">
                                <button @click="showEditForm(binding)" class="text-sm font-medium text-blue-600 hover:underline">Edit</button>
                                <button @click="handleDelete(binding)" class="text-sm font-medium text-red-600 hover:underline">Delete</button>
                            </div>
                        </div>
                        <p class="text-sm text-gray-500 dark:text-gray-400">{{ getBindingTitle(binding.name) }}</p>
                        <div class="mt-2 text-xs space-y-1 text-gray-600 dark:text-gray-300">
                            <template v-for="(value, key) in binding.config" :key="key">
                                 <p v-if="value && key !== 'model_name'">
                                    <span class="font-semibold capitalize">{{ key.replace(/_/g, ' ') }}:</span> 
                                    <span v-if="key.includes('key') || key.includes('token')">********</span>
                                    <span v-else>{{ value }}</span>
                                 </p>
                            </template>
                            <p v-if="binding.default_model_name"><span class="font-semibold">Default Model:</span> {{ binding.default_model_name }}</p>
                        </div>
                    </div>
                    <div class="border-t dark:border-gray-700 pt-3 flex justify-end gap-2">
                        <button v-if="availableBindingTypes.find(b => b.binding_name === binding.name)?.commands?.length" @click="showCommands(binding)" class="btn btn-secondary btn-sm flex items-center gap-2" title="Execute Commands">
                            <IconTerminal class="w-4 h-4" /> Commands
                        </button>
                        <button @click="manageModels(binding)" class="btn btn-secondary btn-sm flex items-center gap-2">
                            <IconCpuChip class="w-4 h-4" /> Manage Models
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Commands Modal -->
        <GenericModal :visible="isCommandsModalVisible" title="Binding Commands" @close="isCommandsModalVisible = false">
            <div class="space-y-4">
                <div v-if="!activeBindingCommands.length" class="text-center text-gray-500">
                    No commands available for this binding.
                </div>
                <div v-else class="flex gap-4">
                    <!-- Left: Command List -->
                    <div class="w-1/3 border-r dark:border-gray-700 pr-4 space-y-2">
                        <button 
                            v-for="cmd in activeBindingCommands" 
                            :key="cmd.name"
                            @click="selectCommandInModal(cmd)"
                            :class="['w-full text-left px-3 py-2 rounded-md text-sm transition-colors', selectedCommand && selectedCommand.name === cmd.name ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-200 font-medium' : 'hover:bg-gray-100 dark:hover:bg-gray-700']"
                        >
                            {{ cmd.title || cmd.name }}
                        </button>
                    </div>
                    
                    <!-- Right: Command Details & Execution -->
                    <div class="w-2/3 pl-2">
                        <div v-if="selectedCommand">
                            <h4 class="font-bold text-lg mb-2">{{ selectedCommand.title || selectedCommand.name }}</h4>
                            <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">{{ selectedCommand.description }}</p>
                            
                            <div v-if="selectedCommand.parameters && selectedCommand.parameters.length" class="space-y-3 mb-4 bg-gray-50 dark:bg-gray-800 p-3 rounded-md border dark:border-gray-700">
                                <div v-for="p in selectedCommand.parameters" :key="p.name">
                                    <label class="block text-xs font-medium uppercase text-gray-500 dark:text-gray-400 mb-1">{{ p.name }}</label>
                                    <input v-if="p.type !== 'bool'" type="text" v-model="modalCommandParams[p.name]" class="input-field text-sm" :placeholder="p.default">
                                    <div v-else class="flex items-center gap-2">
                                        <button @click="modalCommandParams[p.name] = !modalCommandParams[p.name]" type="button" :class="[modalCommandParams[p.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                            <span :class="[modalCommandParams[p.name] ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                        </button>
                                        <span class="text-sm">{{ p.description }}</span>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="flex justify-end">
                                <button 
                                    @click="executeModalCommand" 
                                    class="btn btn-primary" 
                                    :disabled="isExecutingCommand"
                                >
                                    {{ isExecutingCommand ? 'Starting Task...' : 'Execute Command' }}
                                </button>
                            </div>
                        </div>
                        <div v-else class="h-full flex items-center justify-center text-gray-400 text-sm">
                            Select a command to view details.
                        </div>
                    </div>
                </div>
            </div>
            <template #footer>
                <button @click="isCommandsModalVisible = false" class="btn btn-secondary">Close</button>
            </template>
        </GenericModal>
    </div>
</template>
