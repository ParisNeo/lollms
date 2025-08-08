<template>
    <GenericModal modal-name="manageModels" :title="binding ? `Manage Models for: ${binding.alias}` : 'Manage Models'" maxWidthClass="max-w-4xl">
        <template #body>
            <div v-if="!binding" class="text-center p-8 text-red-500 dark:text-red-400">
                <p>Error: Binding information is missing.</p>
            </div>
            <div v-else-if="isLoading" class="text-center p-8">
                <p>Loading models...</p>
            </div>
            <div v-else class="flex gap-6 h-[70vh]">
                <!-- Model List -->
                <div class="w-1/3 border-r dark:border-gray-600 pr-4 overflow-y-auto">
                    <h3 class="font-semibold mb-2 sticky top-0 bg-white dark:bg-gray-800 py-2">Available Models ({{ models.length }})</h3>
                    <ul>
                        <li v-for="model in models" :key="model.original_model_name">
                            <button @click="selectModel(model)"
                                    class="w-full text-left p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
                                    :class="{'bg-blue-100 dark:bg-blue-900/50': selectedModel && selectedModel.original_model_name === model.original_model_name}">
                                <p class="font-mono text-sm truncate" :class="{'font-bold': model.alias}">{{ model.alias?.title || model.original_model_name }}</p>
                                <p v-if="model.alias" class="text-xs text-gray-500 truncate">{{ model.original_model_name }}</p>
                            </button>
                        </li>
                    </ul>
                </div>

                <!-- Alias Form -->
                <div class="w-2/3 overflow-y-auto">
                    <div v-if="!selectedModel" class="flex items-center justify-center h-full">
                        <p class="text-gray-500">Select a model to configure its alias.</p>
                    </div>
                    <div v-else>
                        <h3 class="font-semibold mb-4">Editing Alias for: <span class="font-mono text-blue-600 dark:text-blue-400">{{ selectedModel.original_model_name }}</span></h3>
                        <form @submit.prevent="saveAlias" class="space-y-4">
                             <div>
                                <label for="alias-title" class="label">Alias Title</label>
                                <input id="alias-title" v-model="form.title" type="text" class="input-field" placeholder="e.g., Llama 3 Chat (Fast)">
                            </div>
                            <div>
                                <label for="alias-description" class="label">Description</label>
                                <textarea id="alias-description" v-model="form.description" rows="4" class="input-field" placeholder="A short description of the model's capabilities for users."></textarea>
                            </div>
                            
                            <IconUploader v-model="form.icon" />

                             <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                                <span class="flex-grow flex flex-col">
                                    <span class="text-sm font-medium">Vision Support</span>
                                    <span class="text-sm text-gray-500 dark:text-gray-400">Enable if this model can process images.</span>
                                </span>
                                <button @click="form.has_vision = !form.has_vision" type="button" :class="[form.has_vision ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                    <span :class="[form.has_vision ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                                </button>
                            </div>

                            <div class="flex justify-end gap-3 pt-4">
                                <button v-if="selectedModel.alias" type="button" @click="deleteAlias" class="btn btn-danger-outline" :disabled="isSaving">Delete Alias</button>
                                <button type="submit" class="btn btn-primary" :disabled="isSaving">{{ isSaving ? 'Saving...' : 'Save Alias' }}</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </template>
    </GenericModal>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from '../ui/GenericModal.vue';
import IconUploader from '../ui/IconUploader.vue'; // Import the new component

const uiStore = useUiStore();
const adminStore = useAdminStore();

const modalData = computed(() => uiStore.modalData('manageModels'));
const binding = computed(() => modalData.value?.binding);

const isLoading = ref(true);
const isSaving = ref(false);
const models = ref([]);
const selectedModel = ref(null);

const getInitialFormState = () => ({
    icon: '',
    title: '',
    description: '',
    has_vision: true
});

const form = ref(getInitialFormState());

async function fetchModels() {
    if (!binding.value) {
        isLoading.value = false;
        models.value = [];
        return;
    }
    isLoading.value = true;
    try {
        models.value = await adminStore.fetchBindingModels(binding.value.id);
    } finally {
        isLoading.value = false;
    }
}

function selectModel(model) {
    selectedModel.value = model;
    form.value = { ...getInitialFormState(), ...(model.alias || {}) };
}

async function saveAlias() {
    if (!selectedModel.value || !binding.value) return;
    isSaving.value = true;
    try {
        await adminStore.saveModelAlias(binding.value.id, {
            original_model_name: selectedModel.value.original_model_name,
            alias: form.value
        });
        await fetchModels();
        const updatedModel = models.value.find(m => m.original_model_name === selectedModel.value.original_model_name);
        if (updatedModel) {
            selectModel(updatedModel);
        }
    } finally {
        isSaving.value = false;
    }
}

async function deleteAlias() {
    if (!selectedModel.value?.alias || !binding.value) return;
    const confirmed = await uiStore.showConfirmation({
        title: 'Delete Alias?',
        message: `Are you sure you want to delete the alias for '${selectedModel.value.original_model_name}'?`,
        confirmText: 'Delete'
    });
    if (confirmed) {
        isSaving.value = true;
        try {
            await adminStore.deleteModelAlias(binding.value.id, selectedModel.value.original_model_name);
            await fetchModels();
            const updatedModel = models.value.find(m => m.original_model_name === selectedModel.value.original_model_name);
            if (updatedModel) {
                selectModel(updatedModel);
            } else {
                selectedModel.value = null;
            }
        } finally {
            isSaving.value = false;
        }
    }
}

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