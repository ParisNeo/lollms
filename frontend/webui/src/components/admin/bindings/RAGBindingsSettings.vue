<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useUiStore } from '../../../stores/ui';
import IconEye from '../../../assets/icons/IconEye.vue';
import IconEyeOff from '../../../assets/icons/IconEyeOff.vue';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { ragBindings, availableRagBindingTypes, isLoadingRagBindings, globalSettings } = storeToRefs(adminStore);

const isFormVisible = ref(false);
const editingBinding = ref(null);
const isLoadingForm = ref(false);
const isKeyVisible = ref({});

const getInitialFormState = () => ({
    id: null,
    alias: '',
    name: '',
    config: {},
    default_model_name: null,
    is_active: true
});

const form = ref(getInitialFormState());
const isEditMode = computed(() => editingBinding.value !== null);

const selectedBindingType = computed(() => {
    if (!form.value.name) return null;
    return availableRagBindingTypes.value.find(b => b.name === form.value.name);
});

const allFormParameters = computed(() => {
    if (!selectedBindingType.value) return [];
    return selectedBindingType.value.input_parameters || [];
});

const ragModelDisplayMode = computed({
  get() {
    if (!Array.isArray(globalSettings.value)) return 'mixed';
    const setting = globalSettings.value.find(s => s.key === 'rag_model_display_mode');
    return setting ? setting.value : 'mixed';
  },
  set(newValue) {
    adminStore.updateGlobalSettings({ 'rag_model_display_mode': newValue });
  }
});

watch(() => form.value.name, (newName, oldName) => {
    if (newName !== oldName) {
        const bindingDesc = availableRagBindingTypes.value.find(b => b.name === newName);
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
    adminStore.fetchRagBindings();
    adminStore.fetchAvailableRagBindingTypes();
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
    form.value = JSON.parse(JSON.stringify(binding));
    if (!form.value.config) form.value.config = {};
    isKeyVisible.value = {};
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function hideForm() {
    isFormVisible.value = false;
    editingBinding.value = null;
}

async function handleSubmit() {
    if (!form.value.alias.trim() || !form.value.name) {
        uiStore.addNotification('Alias and Vectorizer Type are required.', 'warning');
        return;
    }
    isLoadingForm.value = true;
    try {
        const payload = {
            alias: form.value.alias,
            name: form.value.name,
            config: form.value.config || {},
            is_active: form.value.is_active,
            default_model_name: form.value.default_model_name || null,
        };
        if (isEditMode.value) {
            await adminStore.updateRagBinding(editingBinding.value.id, payload);
        } else {
            await adminStore.addRagBinding(payload);
        }
        hideForm();
    } finally {
        isLoadingForm.value = false;
    }
}

async function handleDelete(binding) {
    const confirmed = await uiStore.showConfirmation({ title: `Delete RAG Binding '${binding.alias}'?`, confirmText: 'Delete' });
    if (confirmed) {
        await adminStore.deleteRagBinding(binding.id);
    }
}

async function toggleBindingActive(binding) {
    await adminStore.updateRagBinding(binding.id, { is_active: !binding.is_active });
}

function getBindingTitle(name) {
    const bindingType = availableRagBindingTypes.value.find(b => b.name === name);
    return bindingType ? bindingType.title : name;
}

function manageModels(binding) {
    uiStore.openModal('manageModels', { binding, bindingType: 'rag' });
}
</script>

<template>
    <div class="space-y-8">
        <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 shadow-md rounded-lg p-6">
            <h3 class="text-xl font-semibold mb-4">{{ isEditMode ? 'Edit RAG Binding' : 'Add New RAG Binding' }}</h3>
            <form @submit.prevent="handleSubmit" class="space-y-6">
                 <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label for="alias" class="block text-sm font-medium">Alias <span class="text-red-500">*</span></label>
                        <input type="text" id="alias" v-model="form.alias" class="input-field mt-1" required placeholder="e.g., local_embeddings">
                    </div>
                    <div>
                        <label for="name" class="block text-sm font-medium">Vectorizer Type <span class="text-red-500">*</span></label>
                        <select id="name" v-model="form.name" class="input-field mt-1" required :disabled="isEditMode">
                            <option disabled value="">Select a type</option>
                            <option v-for="type in availableRagBindingTypes" :key="type.name" :value="type.name">{{ type.title }}</option>
                        </select>
                    </div>
                </div>
                <div v-if="selectedBindingType" class="space-y-6 border-t dark:border-gray-700 pt-6">
                    <p class="text-sm text-gray-600 dark:text-gray-400">{{ selectedBindingType.description }}</p>
                    <div v-for="param in allFormParameters" :key="param.name" class="space-y-1">
                        <label :for="`param-${param.name}`" class="block text-sm font-medium capitalize">
                            {{ param.name.replace(/_/g, ' ') }} <span v-if="param.mandatory" class="text-red-500">*</span>
                        </label>
                        <div class="relative">
                            <input :type="(param.name.includes('key') || param.name.includes('token')) && !isKeyVisible[param.name] ? 'password' : 'text'"
                                   :id="`param-${param.name}`" v-model="form.config[param.name]" class="input-field" :required="param.mandatory" :placeholder="param.default">
                             <button v-if="param.name.includes('key') || param.name.includes('token')" type="button" @click="isKeyVisible[param.name] = !isKeyVisible[param.name]" class="absolute inset-y-0 right-0 px-3 flex items-center text-gray-500">
                                <IconEyeOff v-if="isKeyVisible[param.name]" class="w-5 h-5" /><IconEye v-else class="w-5 h-5" />
                            </button>
                        </div>
                        <p class="text-xs text-gray-500 mt-1">{{ param.description }}</p>
                    </div>
                </div>
                 <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                    <span class="flex-grow flex flex-col"><span class="text-sm font-medium">Active</span><span class="text-sm text-gray-500">Enable this binding for use in Data Stores.</span></span>
                    <button @click="form.is_active = !form.is_active" type="button" :class="[form.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                        <span :class="[form.is_active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                    </button>
                </div>
                <div class="flex justify-end gap-3">
                    <button type="button" @click="hideForm" class="btn btn-secondary">Cancel</button>
                    <button type="submit" class="btn btn-primary" :disabled="isLoadingForm">
                        <IconAnimateSpin v-if="isLoadingForm" class="w-5 h-5 mr-2" />
                        {{ isLoadingForm ? 'Saving...' : (isEditMode ? 'Save Changes' : 'Create Binding') }}
                    </button>
                </div>
            </form>
        </div>

        <div>
            <div class="flex justify-between items-center mb-4 flex-wrap gap-4">
                <h2 class="text-2xl font-bold">RAG Bindings</h2>
                 <div class="flex items-center gap-4">
                    <div>
                        <label for="rag-model-display-mode" class="block text-xs font-medium text-gray-500 dark:text-gray-400">Model Display Mode</label>
                        <select id="rag-model-display-mode" v-model="ragModelDisplayMode" class="input-field mt-1">
                            <option value="mixed">Mixed (Alias or Original)</option>
                            <option value="aliased">Aliased Only</option>
                            <option value="original">Original Names Only</option>
                        </select>
                    </div>
                    <button @click="showAddForm" class="btn btn-primary self-end" v-if="!isFormVisible">+ Add RAG Binding</button>
                </div>
            </div>

            <div v-if="isLoadingRagBindings">Loading...</div>
            <div v-else-if="ragBindings.length === 0 && !isFormVisible" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <p>No RAG bindings configured.</p>
            </div>
            <div v-else class="space-y-4">
                <div v-for="binding in ragBindings" :key="binding.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md flex flex-col gap-4">
                    <div class="flex-grow">
                        <div class="flex justify-between items-center">
                            <div class="flex items-center gap-3">
                                <h4 class="font-bold text-lg">{{ binding.alias }}</h4>
                                <button @click.stop="toggleBindingActive(binding)" type="button" :class="[binding.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']" :title="binding.is_active ? 'Deactivate' : 'Activate'">
                                    <span :class="[binding.is_active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                            <div class="flex gap-3">
                                <button @click="showEditForm(binding)" class="text-sm font-medium text-blue-600 hover:underline">Edit</button>
                                <button @click="handleDelete(binding)" class="text-sm font-medium text-red-600 hover:underline">Delete</button>
                            </div>
                        </div>
                        <p class="text-sm text-gray-500">{{ getBindingTitle(binding.name) }}</p>
                         <div class="mt-2 text-xs space-y-1 text-gray-600 dark:text-gray-300">
                            <template v-for="(value, key) in binding.config" :key="key">
                                 <p v-if="value">
                                    <span class="font-semibold capitalize">{{ key.replace(/_/g, ' ') }}:</span> 
                                    <span v-if="key.includes('key') || key.includes('token')">********</span>
                                    <span v-else>{{ value }}</span>
                                 </p>
                            </template>
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
