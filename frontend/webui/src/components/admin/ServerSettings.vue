<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import StringListEditor from '../ui/StringListEditor.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const form = ref({});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const certFileInput = ref(null);
const keyFileInput = ref(null);

const uiLevels = [
    { value: 0, label: 'Beginner' }, { value: 1, label: 'Novice' },
    { value: 2, label: 'Intermediate' }, { value: 3, label: 'Advanced' },
    { value: 4, label: 'Expert' }
];

const serverSettings = computed(() => adminStore.globalSettings.filter(s => s.category === 'Server'));
const registrationSettings = computed(() => adminStore.globalSettings.filter(s => s.category === 'Registration'));
const defaultSettings = computed(() => adminStore.globalSettings.filter(s => s.category === 'Defaults'));
const allModels = computed(() => dataStore.availableLollmsModels);

onMounted(async () => {
    if (adminStore.globalSettings.length === 0) {
        await adminStore.fetchGlobalSettings();
    }
    if (dataStore.availableLollmsModels.length === 0) {
        await dataStore.fetchAdminAvailableLollmsModels();
    }
});

watch(() => adminStore.globalSettings, populateForm, { deep: true, immediate: true });
watch(form, (newValue) => { hasChanges.value = JSON.stringify(newValue) !== pristineState; }, { deep: true });

function populateForm() {
    const allSettings = adminStore.globalSettings;
    if (!allSettings || allSettings.length === 0) {
        form.value = {};
        pristineState = '{}';
        hasChanges.value = false;
        return;
    }

    const newFormState = {};
    const relevantSettings = allSettings.filter(s => 
        ['Server', 'Registration', 'Defaults'].includes(s.category)
    );
    
    relevantSettings.forEach(setting => {
        newFormState[setting.key] = setting.value;
    });

    form.value = newFormState;
    pristineState = JSON.stringify(newFormState);
    hasChanges.value = false;
}


async function handleFileUpload(event, fileType) {
    const file = event.target.files[0];
    if (!file) return;
    isLoading.value = true;
    try {
        const newPath = await adminStore.uploadSslFile(file, fileType);
        if (fileType === 'cert') {
            form.value.ssl_certfile = newPath;
        } else if (fileType === 'key') {
            form.value.ssl_keyfile = newPath;
        }
        uiStore.addNotification(`${file.name} uploaded successfully.`, 'success');
    } finally {
        isLoading.value = false;
        if (certFileInput.value && certFileInput.value.length > 0) certFileInput.value[0].value = '';
        if (keyFileInput.value && keyFileInput.value.length > 0) keyFileInput.value[0].value = '';
    }
}

async function handleSave() {
    isLoading.value = true;
    try {
        await adminStore.updateGlobalSettings({ ...form.value });
        uiStore.addNotification('Settings saved. A server restart may be required for some changes to take effect.', 'info', 8000);
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="p-6 border-b border-gray-200 dark:border-gray-700">
            <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">Server Settings</h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage core server behavior, user registration, and defaults for new users.</p>
        </div>
        <form v-if="Object.keys(form).length" @submit.prevent="handleSave" class="p-6">
            <div class="space-y-10">
                
                <!-- Server Configuration -->
                <div v-if="serverSettings.length > 0">
                    <h4 class="settings-category-title">Server Configuration</h4>
                    <div class="space-y-6">
                        <div class="p-4 bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-400 text-yellow-800 dark:text-yellow-200 rounded-r-lg">
                            <p class="text-sm font-medium">A server restart is required for any changes in this section to take effect.</p>
                        </div>
                        <div v-for="setting in serverSettings" :key="setting.key" class="space-y-1">
                            <label :for="setting.key" class="label">{{ setting.description }}</label>
                            
                            <StringListEditor v-if="setting.key === 'cors_origins_exceptions'" v-model="form[setting.key]" />
                            
                            <div v-else-if="setting.key === 'ssl_certfile'" class="flex items-center gap-2">
                                <input type="text" :id="setting.key" v-model="form[setting.key]" class="input-field flex-grow" placeholder="/path/to/cert.pem">
                                <input type="file" ref="certFileInput" @change="event => handleFileUpload(event, 'cert')" class="hidden">
                                <button @click.prevent="certFileInput[0].click()" type="button" class="btn btn-secondary">Upload</button>
                            </div>

                            <div v-else-if="setting.key === 'ssl_keyfile'" class="flex items-center gap-2">
                                <input type="text" :id="setting.key" v-model="form[setting.key]" class="input-field flex-grow" placeholder="/path/to/key.pem">
                                <input type="file" ref="keyFileInput" @change="event => handleFileUpload(event, 'key')" class="hidden">
                                <button @click.prevent="keyFileInput[0].click()" type="button" class="btn btn-secondary">Upload</button>
                            </div>
                            
                            <div v-else-if="setting.type === 'boolean'" class="toggle-container-flat">
                                <button @click="form[setting.key] = !form[setting.key]" type="button" :class="[form[setting.key] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']"><span :class="[form[setting.key] ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span></button>
                            </div>

                            <input v-else
                                :type="setting.type === 'string' ? 'text' : (setting.type === 'integer' || setting.type === 'float' ? 'number' : 'text')"
                                :id="setting.key"
                                v-model="form[setting.key]"
                                class="input-field"
                                :readonly="setting.key === 'data_path' || setting.key === 'huggingface_cache_path'"
                                :class="{'bg-gray-100 dark:bg-gray-700 cursor-not-allowed': setting.key === 'data_path' || setting.key === 'huggingface_cache_path'}"
                            >
                        </div>
                    </div>
                </div>

                <!-- Registration -->
                <div v-if="registrationSettings.length > 0">
                    <h4 class="settings-category-title">New User Registration</h4>
                    <div class="space-y-6">
                        <div v-for="setting in registrationSettings.filter(s => s.type === 'boolean')" :key="setting.key" class="toggle-container">
                            <span class="toggle-label">{{ setting.description }}</span>
                            <button @click="form[setting.key] = !form[setting.key]" type="button" :class="[form[setting.key] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']"><span :class="[form[setting.key] ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span></button>
                        </div>
                        <div v-for="setting in registrationSettings.filter(s => s.key === 'registration_mode')" :key="setting.key">
                            <label :for="setting.key" class="label">{{ setting.description }}</label>
                            <select :id="setting.key" v-model="form[setting.key]" class="input-field mt-1">
                                <option value="direct">Direct (instantly active)</option>
                                <option value="admin_approval">Admin Approval</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- Defaults -->
                <div v-if="defaultSettings.length > 0">
                    <h4 class="settings-category-title">Defaults for New Users</h4>
                    <div class="space-y-6">
                        <div v-for="setting in defaultSettings.filter(s => s.type === 'boolean')" :key="setting.key" class="toggle-container">
                            <span class="toggle-label">{{ setting.description }}</span>
                            <button @click="form[setting.key] = !form[setting.key]" type="button" :class="[form[setting.key] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']"><span :class="[form[setting.key] ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span></button>
                        </div>
                        <div v-for="setting in defaultSettings.filter(s => s.type !== 'boolean' && s.key !== 'default_user_ui_level')" :key="setting.key">
                            <label :for="setting.key" class="label">{{ setting.description }}</label>
                            <input v-if="setting.key !== 'default_lollms_model_name'" :type="setting.type === 'string' ? 'text' : 'number'" :id="setting.key" v-model="form[setting.key]" class="input-field mt-1">
                            <select v-else :id="setting.key" v-model="form[setting.key]" class="input-field mt-1">
                                <option value="">(None)</option>
                                <option v-for="model in allModels" :key="model.id" :value="model.id">{{ model.name }}</option>
                            </select>
                        </div>
                        <div v-for="setting in defaultSettings.filter(s => s.key === 'default_user_ui_level')" :key="setting.key">
                            <label :for="setting.key" class="label">{{ setting.description }}</label>
                            <select :id="setting.key" v-model.number="form[setting.key]" class="input-field mt-1">
                                <option v-for="level in uiLevels" :key="level.value" :value="level.value">{{ level.label }}</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>

            <div class="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700">
                <div class="flex justify-end">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">{{ isLoading ? 'Saving...' : 'Save Settings' }}</button>
                </div>
            </div>
        </form>
        <div v-else class="p-6 text-center text-gray-500">
            <p v-if="adminStore.isLoadingSettings">Loading settings...</p>
            <p v-else>Could not load server settings.</p>
        </div>
    </div>
</template>

<style scoped>
.settings-category-title { @apply text-lg font-medium text-gray-800 dark:text-gray-200 border-b border-gray-200 dark:border-gray-600 pb-2 mb-6; }
.label { @apply block text-sm font-medium text-gray-700 dark:text-gray-300; }
.toggle-container { @apply flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg; }
.toggle-label { @apply flex-grow flex flex-col text-sm font-medium text-gray-900 dark:text-gray-100; }
.toggle-switch { @apply relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out; }
.toggle-knob { @apply pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out; }
.toggle-container-flat { @apply pt-2; }
</style>