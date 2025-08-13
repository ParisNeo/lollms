<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useUiStore } from '../../../stores/ui';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconEye from '../../../assets/icons/IconEye.vue';
import IconEyeOff from '../../../assets/icons/IconEyeOff.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { bindings, availableBindingTypes, isLoadingBindings, globalSettings } = storeToRefs(adminStore);

const isFormVisible = ref(false);
const editingBinding = ref(null);
const isLoadingForm = ref(false);
const isKeyVisible = ref({});

// Updated initial state to use a 'config' object for dynamic parameters
const getInitialFormState = () => ({
    id: null,
    alias: '',
    name: '', // This will hold the binding_name
    config: {},
    default_model_name: '',
    is_active: true
});

const form = ref(getInitialFormState());

const isEditMode = computed(() => editingBinding.value !== null);

// Computed property to get the full description of the selected binding type
const selectedBindingType = computed(() => {
    if (!form.value.name) return null;
    return availableBindingTypes.value.find(b => b.binding_name === form.value.name);
});

// Watch for changes in the selected binding type to update the form's config with defaults
watch(() => form.value.name, (newName) => {
    if (!isEditMode.value) { // Only reset config for new bindings
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
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showEditForm(binding) {
    editingBinding.value = binding;
    // Deep copy to avoid reactivity issues
    form.value = JSON.parse(JSON.stringify(binding));
    isKeyVisible.value = {};
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function hideForm() {
    isFormVisible.value = false;
    editingBinding.value = null;
}

async function handleSubmit() {
    isLoadingForm.value = true;
    try {
        const payload = { ...form.value };
        delete payload.id;

        if (isEditMode.value) {
            // Handle placeholder service keys: if unchanged, don't send them
            if (payload.config) {
                for (const key in payload.config) {
                    if ((key.includes('key') || key.includes('token')) && payload.config[key] === '********') {
                        delete payload.config[key];
                    }
                }
            }
            await adminStore.updateBinding(editingBinding.value.id, payload);
        } else {
            await adminStore.addBinding(payload);
        }
        hideForm();
    } catch (error) {
        // Error notification is handled by API interceptor
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

function manageModels(binding) {
    uiStore.openModal('manageModels', { binding });
}

// Helper to get the user-friendly title for a binding name
function getBindingTitle(name) {
    const bindingType = availableBindingTypes.value.find(b => b.binding_name === name);
    return bindingType ? bindingType.title : name;
}
</script>

<template>
    <div class="space-y-8">
        <!-- Add/Edit Form Section -->
        <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 shadow-md rounded-lg p-6">
            <h3 class="text-xl font-semibold mb-4">{{ isEditMode ? 'Edit Binding' : 'Add New Binding' }}</h3>
            <form @submit.prevent="handleSubmit" class="space-y-6">
                <!-- Static Fields: Alias and Binding Type -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label for="alias" class="block text-sm font-medium">Alias <span class="text-red-500">*</span></label>
                        <input type="text" id="alias" v-model="form.alias" class="input-field mt-1" required placeholder="e.g., local_ollama">
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

                <!-- Dynamic Fields based on selectedBindingType -->
                <div v-if="selectedBindingType" class="space-y-6 border-t dark:border-gray-700 pt-6">
                    <p class="text-sm text-gray-600 dark:text-gray-400">{{ selectedBindingType.description }}</p>
                    <div v-for="param in selectedBindingType.input_parameters" :key="param.name" class="space-y-1">
                        <label :for="`param-${param.name}`" class="block text-sm font-medium capitalize">
                            {{ param.name.replace(/_/g, ' ') }}
                            <span v-if="param.mandatory" class="text-red-500">*</span>
                        </label>

                        <!-- Text/Number/Float Input -->
                        <div v-if="['str', 'int', 'float'].includes(param.type)">
                            <div class="relative">
                                <input 
                                    :type="(param.name.includes('key') || param.name.includes('token')) && !isKeyVisible[param.name] ? 'password' : 'text'" 
                                    :id="`param-${param.name}`" 
                                    v-model="form.config[param.name]" 
                                    class="input-field"
                                    :required="param.mandatory" 
                                    :placeholder="param.description" 
                                    autocomplete="off">
                                <button v-if="param.name.includes('key') || param.name.includes('token')" type="button" @click="isKeyVisible[param.name] = !isKeyVisible[param.name]" class="absolute inset-y-0 right-0 px-3 flex items-center text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" :title="isKeyVisible[param.name] ? 'Hide' : 'Show'">
                                    <IconEyeOff v-if="isKeyVisible[param.name]" class="w-5 h-5" />
                                    <IconEye v-else class="w-5 h-5" />
                                </button>
                            </div>
                        </div>

                        <!-- Boolean Toggle -->
                        <div v-else-if="param.type === 'bool'" class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                            <span class="flex-grow flex flex-col pr-4">
                                <span class="text-sm text-gray-500 dark:text-gray-400">{{ param.description }}</span>
                            </span>
                            <button @click="form.config[param.name] = !form.config[param.name]" type="button" :class="[form.config[param.name] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                <span :class="[form.config[param.name] ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                            </button>
                        </div>
                    </div>
                </div>
                
                <!-- Default Model Name (remains static as it's common) -->
                 <div>
                    <label for="default_model_name" class="block text-sm font-medium">Default Model Name</label>
                    <input type="text" id="default_model_name" v-model="form.default_model_name" class="input-field mt-1" placeholder="e.g., phi3:latest or gpt-4o-mini">
                     <p class="text-xs text-gray-500 mt-1">Optional. The default model to use with this binding. Can be overridden.</p>
                </div>

                <!-- Active Toggle (remains static) -->
                <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                    <span class="flex-grow flex flex-col">
                        <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Active</span>
                        <span class="text-sm text-gray-500 dark:text-gray-400">If disabled, users cannot see or use models from this binding.</span>
                    </span>
                    <button @click="form.is_active = !form.is_active" type="button" :class="[form.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                        <span :class="[form.is_active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                    </button>
                </div>

                <!-- Form Actions -->
                <div class="flex justify-end gap-3">
                    <button type="button" @click="hideForm" class="btn btn-secondary">Cancel</button>
                    <button type="submit" class="btn btn-primary" :disabled="isLoadingForm">
                        {{ isLoadingForm ? 'Saving...' : (isEditMode ? 'Save Changes' : 'Add Binding') }}
                    </button>
                </div>
            </form>
        </div>

        <!-- Bindings List Section -->
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
                    <div class="flex items-start gap-4">
                        <span class="mt-1 h-3 w-3 rounded-full flex-shrink-0" :class="binding.is_active ? 'bg-green-500' : 'bg-gray-400'" :title="binding.is_active ? 'Active' : 'Inactive'"></span>
                        <div class="flex-grow">
                            <div class="flex justify-between items-center">
                                <h4 class="font-bold text-lg text-gray-900 dark:text-white">{{ binding.alias }}</h4>
                                <div class="flex gap-3">
                                    <button @click="showEditForm(binding)" class="text-sm font-medium text-blue-600 hover:underline">Edit</button>
                                    <button @click="handleDelete(binding)" class="text-sm font-medium text-red-600 hover:underline">Delete</button>
                                </div>
                            </div>
                            <p class="text-sm text-gray-500 dark:text-gray-400">{{ getBindingTitle(binding.name) }}</p>
                            <!-- Display config values from the binding object -->
                            <div class="mt-2 text-xs space-y-1 text-gray-600 dark:text-gray-300">
                                <template v-for="(value, key) in binding.config" :key="key">
                                     <p v-if="value && !(key.includes('key') || key.includes('token'))">
                                        <span class="font-semibold capitalize">{{ key.replace(/_/g, ' ') }}:</span> {{ value }}
                                     </p>
                                </template>
                                <p v-if="binding.default_model_name"><span class="font-semibold">Default Model:</span> {{ binding.default_model_name }}</p>
                            </div>
                        </div>
                    </div>
                    <div class="border-t dark:border-gray-700 pt-3 flex justify-end">
                        <button @click="manageModels(binding)" class="btn btn-secondary btn-sm flex items-center gap-2">
                            <IconCpuChip class="w-4 h-4" /> Manage Models
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>