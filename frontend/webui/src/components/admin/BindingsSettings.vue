<script setup>
import { ref, onMounted, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { bindings, availableBindingTypes, isLoadingBindings } = storeToRefs(adminStore);

const isFormVisible = ref(false);
const editingBinding = ref(null);
const isLoadingForm = ref(false);

const getInitialFormState = () => ({
    id: null,
    alias: '',
    name: '',
    host_address: '',
    models_path: '',
    service_key: '',
    default_model_name: '',
    verify_ssl_certificate: true,
    is_active: true
});

const form = ref(getInitialFormState());

const isEditMode = computed(() => editingBinding.value !== null);

onMounted(() => {
    adminStore.fetchBindings();
    adminStore.fetchAvailableBindingTypes();
});

function showAddForm() {
    editingBinding.value = null;
    form.value = getInitialFormState();
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showEditForm(binding) {
    editingBinding.value = binding;
    form.value = { ...binding, service_key: '' }; // Don't pre-fill key
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
        delete payload.id; // Don't send ID in payload

        if (isEditMode.value) {
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
</script>

<template>
    <div class="space-y-8">
        <!-- Add/Edit Form Section -->
        <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 shadow-md rounded-lg p-6">
            <h3 class="text-xl font-semibold mb-4">{{ isEditMode ? 'Edit Binding' : 'Add New Binding' }}</h3>
            <form @submit.prevent="handleSubmit" class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label for="alias" class="block text-sm font-medium">Alias <span class="text-red-500">*</span></label>
                        <input type="text" id="alias" v-model="form.alias" class="input-field mt-1" required placeholder="e.g., local_ollama">
                        <p class="text-xs text-gray-500 mt-1">A unique, short name for this configuration.</p>
                    </div>
                    <div>
                        <label for="name" class="block text-sm font-medium">Binding Type <span class="text-red-500">*</span></label>
                        <select id="name" v-model="form.name" class="input-field mt-1" required>
                            <option disabled value="">Select a type</option>
                            <option v-for="type in availableBindingTypes" :key="type" :value="type">{{ type }}</option>
                        </select>
                    </div>
                </div>
                <div>
                    <label for="host_address" class="block text-sm font-medium">Host Address</label>
                    <input type="text" id="host_address" v-model="form.host_address" class="input-field mt-1" placeholder="e.g., http://localhost:11434">
                    <p class="text-xs text-gray-500 mt-1">URL for remote bindings like Ollama or OpenAI-compatible servers.</p>
                </div>
                <div>
                    <label for="models_path" class="block text-sm font-medium">Models Path</label>
                    <input type="text" id="models_path" v-model="form.models_path" class="input-field mt-1" placeholder="e.g., /path/to/your/models">
                     <p class="text-xs text-gray-500 mt-1">Local file path for bindings that load models from disk (e.g., LlamaCPP).</p>
                </div>
                 <div>
                    <label for="service_key" class="block text-sm font-medium">Service API Key</label>
                    <input type="password" id="service_key" v-model="form.service_key" class="input-field mt-1" :placeholder="isEditMode ? 'Leave blank to keep existing key' : 'Paste API key here'">
                    <p class="text-xs text-gray-500 mt-1">For services like OpenAI. Can also be set as an environment variable.</p>
                </div>
                 <div>
                    <label for="default_model_name" class="block text-sm font-medium">Default Model Name</label>
                    <input type="text" id="default_model_name" v-model="form.default_model_name" class="input-field mt-1" placeholder="e.g., phi3:latest or gpt-4o-mini">
                </div>
                <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                    <span class="flex-grow flex flex-col">
                        <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Verify SSL certificate</span>
                        <span class="text-sm text-gray-500 dark:text-gray-400">Verifies SSL certificates. This is advises to avoid man in the middle attacks. If your server has no certificate or there is no authority that can validate it, you can deactivate this setting. But stay caucious.</span>
                    </span>
                    <button @click="form.verify_ssl_certificate = !form.verify_ssl_certificate" type="button" :class="[form.verify_ssl_certificate ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                        <span :class="[form.verify_ssl_certificate ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                    </button>
                </div>

                <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                    <span class="flex-grow flex flex-col">
                        <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Active</span>
                        <span class="text-sm text-gray-500 dark:text-gray-400">If disabled, users cannot see or use models from this binding.</span>
                    </span>
                    <button @click="form.is_active = !form.is_active" type="button" :class="[form.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                        <span :class="[form.is_active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                    </button>
                </div>
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
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-2xl font-bold">LLM Bindings</h2>
                <button @click="showAddForm" class="btn btn-primary" v-if="!isFormVisible">+ Add New Binding</button>
            </div>

            <div v-if="isLoadingBindings" class="text-center p-6">Loading bindings...</div>
            <div v-else-if="bindings.length === 0 && !isFormVisible" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <p>No LLM bindings configured yet.</p>
                <button @click="showAddForm" class="mt-2 text-blue-600 hover:underline">Add your first one</button>
            </div>
            <div v-else class="space-y-4">
                <div v-for="binding in bindings" :key="binding.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md flex items-start gap-4">
                     <span class="mt-1 h-3 w-3 rounded-full flex-shrink-0" :class="binding.is_active ? 'bg-green-500' : 'bg-gray-400'" :title="binding.is_active ? 'Active' : 'Inactive'"></span>
                    <div class="flex-grow">
                        <div class="flex justify-between items-center">
                            <h4 class="font-bold text-lg text-gray-900 dark:text-white">{{ binding.alias }}</h4>
                            <div class="flex gap-3">
                                <button @click="showEditForm(binding)" class="text-sm font-medium text-blue-600 hover:underline">Edit</button>
                                <button @click="handleDelete(binding)" class="text-sm font-medium text-red-600 hover:underline">Delete</button>
                            </div>
                        </div>
                        <p class="text-sm text-gray-500 dark:text-gray-400">{{ binding.name }}</p>
                        <div class="mt-2 text-xs space-y-1 text-gray-600 dark:text-gray-300">
                            <p v-if="binding.host_address"><span class="font-semibold">Host:</span> {{ binding.host_address }}</p>
                            <p v-if="binding.models_path"><span class="font-semibold">Path:</span> {{ binding.models_path }}</p>
                            <p v-if="binding.default_model_name"><span class="font-semibold">Default Model:</span> {{ binding.default_model_name }}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
