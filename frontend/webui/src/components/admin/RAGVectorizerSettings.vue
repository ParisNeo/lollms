<template>
    <div class="space-y-8">
        <!-- Main settings and toggle -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg p-6">
            <h3 class="text-xl font-semibold mb-2">RAG Behavior</h3>
            <p class="text-sm text-gray-500 mb-6">Control how users select vectorizers when creating new Data Stores.</p>
            <div class="toggle-container">
                <span class="toggle-label">
                    Restrict to Aliases Only
                    <span class="toggle-description">When enabled, users can only choose from the aliases you define below. When disabled, they can also choose from all built-in `safe_store` vectorizers.</span>
                </span>
                <button @click="toggleRestriction" type="button" :class="[restrictToAliases ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']">
                    <span :class="[restrictToAliases ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                </button>
            </div>
             <div class="mt-4">
                <label for="default_safe_store_vectorizer" class="block text-sm font-medium">Default Vectorizer for New Stores</label>
                <select id="default_safe_store_vectorizer" v-model="defaultVectorizer" class="input-field mt-1">
                    <option v-for="(alias, key) in vectorizerAliases" :key="key" :value="key">{{ alias.title || key }}</option>
                    <option v-if="!restrictToAliases" disabled>---</option>
                    <option v-for="vec in availableVectorizers.filter(v => !v.is_alias)" :key="vec.name" :value="vec.name">{{ vec.title || vec.name }}</option>
                </select>
                <p class="text-xs text-gray-500 mt-1">The default vectorizer pre-selected when a user creates a new Data Store.</p>
            </div>
             <div class="flex justify-end mt-6">
                <button @click="saveGeneralSettings" class="btn btn-primary" :disabled="!hasGeneralChanges">Save General Settings</button>
            </div>
        </div>

        <!-- Alias Management -->
        <div>
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-xl font-semibold">Vectorizer Aliases</h3>
                <button @click="showAddForm()" class="btn btn-primary">+ Add Alias</button>
            </div>
            
            <div v-if="isLoadingAliases" class="text-center p-6">Loading...</div>
            <div v-else-if="Object.keys(vectorizerAliases).length === 0" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <p>No aliases defined. Add one to create a shortcut for users.</p>
            </div>
            <div v-else class="space-y-4">
                <div v-for="(aliasData, aliasName) in vectorizerAliases" :key="aliasName" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md">
                    <div class="flex justify-between items-start">
                        <div>
                            <h4 class="font-bold text-lg text-gray-900 dark:text-white">{{ aliasData.title || aliasName }}</h4>
                            <p class="text-sm font-mono text-blue-600 dark:text-blue-400">{{ aliasName }}</p>
                            <p v-if="aliasData.description" class="text-sm text-gray-500 mt-1">{{ aliasData.description }}</p>
                        </div>
                        <div class="flex gap-2">
                            <button @click="showEditForm(aliasName, aliasData)" class="text-sm font-medium text-blue-600 hover:underline">Edit</button>
                            <button @click="handleDelete(aliasName)" class="text-sm font-medium text-red-600 hover:underline">Delete</button>
                        </div>
                    </div>
                    <div class="mt-4 border-t dark:border-gray-700 pt-3 text-xs space-y-1">
                        <p><span class="font-semibold">Vectorizer Type:</span> {{ aliasData.vectorizer_name }}</p>
                        <div>
                            <span class="font-semibold">Configuration:</span>
                            <JsonRenderer :json="aliasData.vectorizer_config" class="mt-1 p-2 bg-gray-100 dark:bg-gray-900/50 rounded-md" />
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Add/Edit Modal -->
        <GenericModal modalName="ragAliasEditor" :title="isEditMode ? 'Edit Alias' : 'Add Alias'">
            <template #body>
                <form @submit.prevent="handleSubmit" class="space-y-4">
                    <div>
                        <label for="alias-name" class="block text-sm font-medium">Alias Name <span class="text-red-500">*</span></label>
                        <input id="alias-name" v-model="form.alias_name" type="text" class="input-field mt-1 font-mono" required :disabled="isEditMode" placeholder="e.g., local_minilm">
                    </div>
                    <div>
                        <label for="alias-title" class="block text-sm font-medium">Display Title</label>
                        <input id="alias-title" v-model="form.alias_data.title" type="text" class="input-field mt-1" placeholder="e.g., Local MiniLM">
                    </div>
                    <div>
                        <label for="alias-desc" class="block text-sm font-medium">Description</label>
                        <textarea id="alias-desc" v-model="form.alias_data.description" rows="2" class="input-field mt-1" placeholder="A short description for the user."></textarea>
                    </div>
                     <div>
                        <label for="vectorizer-name" class="block text-sm font-medium">Vectorizer Type <span class="text-red-500">*</span></label>
                        <select id="vectorizer-name" v-model="form.alias_data.vectorizer_name" class="input-field mt-1" required>
                            <option value="">-- Select Type --</option>
                            <option v-for="vec in availableVectorizers.filter(v => !v.is_alias)" :key="vec.name" :value="vec.name">{{ vec.title }} ({{ vec.name }})</option>
                        </select>
                    </div>
                    <div>
                        <label for="vectorizer-config" class="block text-sm font-medium">Configuration (JSON)</label>
                        <textarea id="vectorizer-config" v-model="configJson" rows="5" class="input-field mt-1 font-mono"></textarea>
                        <p v-if="jsonError" class="text-xs text-red-500 mt-1">{{ jsonError }}</p>
                    </div>
                </form>
            </template>
            <template #footer>
                <button @click="uiStore.closeModal('ragAliasEditor')" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" :disabled="!!jsonError" class="btn btn-primary">{{ isEditMode ? 'Save Changes' : 'Create Alias' }}</button>
            </template>
        </GenericModal>
    </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import GenericModal from '../modals/GenericModal.vue';
import JsonRenderer from '../ui/JsonRenderer.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const vectorizerAliases = ref({});
const isLoadingAliases = ref(false);
const isEditMode = ref(false);

const form = ref({
    alias_name: '',
    alias_data: {
        vectorizer_name: '',
        vectorizer_config: {},
        title: '',
        description: ''
    }
});
const configJson = ref('{}');
const jsonError = ref('');

const availableVectorizers = computed(() => dataStore.availableVectorizers);
const restrictToAliases = ref(false);
const defaultVectorizer = ref('');
let pristineGeneralSettings = {};

const hasGeneralChanges = computed(() => {
    return restrictToAliases.value !== pristineGeneralSettings.restrict_vectorizers_to_aliases ||
           defaultVectorizer.value !== pristineGeneralSettings.default_safe_store_vectorizer;
});

watch(configJson, (newJson) => {
    try {
        form.value.alias_data.vectorizer_config = JSON.parse(newJson);
        jsonError.value = '';
    } catch(e) {
        jsonError.value = 'Invalid JSON format.';
    }
});

watch(() => adminStore.globalSettings, (settings) => {
    const aliasesSetting = settings.find(s => s.key === 'rag_vectorizer_aliases');
    if (aliasesSetting) {
        vectorizerAliases.value = aliasesSetting.value || {};
    }
    const restrictSetting = settings.find(s => s.key === 'restrict_vectorizers_to_aliases');
    if (restrictSetting) {
        restrictToAliases.value = restrictSetting.value;
        pristineGeneralSettings.restrict_vectorizers_to_aliases = restrictSetting.value;
    }
    const defaultVecSetting = settings.find(s => s.key === 'default_safe_store_vectorizer');
    if (defaultVecSetting) {
        defaultVectorizer.value = defaultVecSetting.value;
        pristineGeneralSettings.default_safe_store_vectorizer = defaultVecSetting.value;
    }
}, { deep: true, immediate: true });

onMounted(async () => {
    isLoadingAliases.value = true;
    await adminStore.fetchGlobalSettings();
    await dataStore.fetchAvailableVectorizers();
    isLoadingAliases.value = false;
});

function toggleRestriction() {
    restrictToAliases.value = !restrictToAliases.value;
}

async function saveGeneralSettings() {
    await adminStore.updateGlobalSettings({
        'restrict_vectorizers_to_aliases': restrictToAliases.value,
        'default_safe_store_vectorizer': defaultVectorizer.value
    });
}

function showAddForm() {
    isEditMode.value = false;
    form.value = { alias_name: '', alias_data: { vectorizer_name: '', vectorizer_config: {}, title: '', description: '' } };
    configJson.value = '{}';
    uiStore.openModal('ragAliasEditor');
}

function showEditForm(aliasName, aliasData) {
    isEditMode.value = true;
    form.value = {
        alias_name: aliasName,
        alias_data: JSON.parse(JSON.stringify(aliasData))
    };
    configJson.value = JSON.stringify(aliasData.vectorizer_config || {}, null, 2);
    uiStore.openModal('ragAliasEditor');
}

async function handleSubmit() {
    if (jsonError.value) return;
    if (!form.value.alias_name.trim() || !form.value.alias_data.vectorizer_name) {
        uiStore.addNotification('Alias Name and Vectorizer Type are required.', 'warning');
        return;
    }
    await adminStore.addOrUpdateRagAlias(form.value);
    uiStore.closeModal('ragAliasEditor');
}

async function handleDelete(aliasName) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete alias '${aliasName}'?`,
        message: 'This cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed.confirmed) {
        await adminStore.deleteRagAlias(aliasName);
    }
}
</script>

<style scoped>
.toggle-container { @apply flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg; }
.toggle-label { @apply flex-grow flex flex-col text-sm font-medium text-gray-900 dark:text-gray-100; }
.toggle-description { @apply text-xs text-gray-500 dark:text-gray-400 font-normal mt-1; }
.toggle-switch { @apply relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out; }
.toggle-knob { @apply pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out; }
</style>