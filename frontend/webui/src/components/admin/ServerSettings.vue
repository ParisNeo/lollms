<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import StringListEditor from '../ui/StringListEditor.vue';
import IconLock from '../../assets/icons/IconLock.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

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
const availableVectorizers = computed(() => dataStore.availableVectorizers);

// Use the shared grouping logic from dataStore to match GlobalHeader
const groupedModels = computed(() => dataStore.availableLLMModelsGrouped);

onMounted(async () => {
    if (adminStore.globalSettings.length === 0) {
        await adminStore.fetchGlobalSettings();
    }
    if (dataStore.availableLollmsModels.length === 0) {
        await dataStore.fetchAdminAvailableLollmsModels();
    }
    await dataStore.fetchAvailableVectorizers();
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

async function generateCert() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Generate Certificate?',
        message: 'This will generate a new self-signed certificate and overwrite existing SSL settings. A server restart will be required.',
        confirmText: 'Generate & Enable'
    });
    
    const isConfirmed = typeof confirmed === 'object' ? confirmed.confirmed : confirmed;
    if (!isConfirmed) return;
    
    isLoading.value = true;
    try {
        await adminStore.generateSelfSignedCert();
    } catch(e) {
        // Error handled in store
    } finally {
        isLoading.value = false;
    }
}

function downloadCert() {
    adminStore.downloadCertificate();
}

function downloadTrustScript(type) {
    adminStore.downloadTrustScript(type);
}

function isFullWidth(key) {
    return ['cors_origins_exceptions', 'data_path', 'huggingface_cache_path', 'ssl_certfile', 'ssl_keyfile'].includes(key);
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="p-6 border-b border-gray-200 dark:border-gray-700">
            <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">Server Settings</h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Manage core server behavior, user registration, and defaults for new users.</p>
        </div>
        
        <form v-if="Object.keys(form).length" @submit.prevent="handleSave" class="p-6">
            <div class="space-y-12">
                
                <!-- Server Configuration -->
                <div v-if="serverSettings.length > 0">
                    <h4 class="settings-category-title">Server Configuration</h4>
                    <div class="mb-6 p-4 bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-400 text-blue-800 dark:text-blue-200 rounded-r-lg">
                        <p class="text-sm font-medium">Note: Changing server host, port, or SSL settings requires a server restart.</p>
                    </div>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div v-for="setting in serverSettings.filter(s => !['ssl_certfile', 'ssl_keyfile', 'https_enabled'].includes(s.key))" 
                             :key="setting.key" 
                             class="setting-card"
                             :class="{'md:col-span-2': isFullWidth(setting.key)}">
                            
                            <label :for="setting.key" class="label mb-2">{{ setting.description }}</label>
                            
                            <StringListEditor v-if="setting.key === 'cors_origins_exceptions'" v-model="form[setting.key]" />
                            
                            <div v-else-if="setting.type === 'boolean'" class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/30 p-3 rounded-lg border dark:border-gray-600">
                                <span class="text-sm text-gray-700 dark:text-gray-300">{{ setting.description }}</span>
                                <button @click="form[setting.key] = !form[setting.key]" type="button" :class="[form[setting.key] ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch']">
                                    <span :class="[form[setting.key] ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                                </button>
                            </div>

                            <input v-else
                                :type="setting.type === 'string' ? 'text' : 'number'"
                                :step="setting.type === 'float' ? '0.1' : '1'"
                                :id="setting.key"
                                v-model="form[setting.key]"
                                class="input-field w-full"
                                :readonly="setting.key === 'data_path' || setting.key === 'huggingface_cache_path'"
                                :class="{'bg-gray-100 dark:bg-gray-700 cursor-not-allowed opacity-75': setting.key === 'data_path' || setting.key === 'huggingface_cache_path'}"
                            >
                        </div>
                    </div>
                </div>

                <!-- HTTPS Configuration Block -->
                <div class="border-t pt-8 dark:border-gray-700">
                    <h4 class="settings-category-title flex items-center gap-2">
                        <IconLock class="w-5 h-5 text-green-600 dark:text-green-400"/> HTTPS Configuration
                    </h4>
                    
                    <div class="bg-gray-50 dark:bg-gray-700/20 p-6 rounded-xl border dark:border-gray-700">
                        <div class="flex items-center justify-between mb-6 pb-6 border-b dark:border-gray-600">
                            <div>
                                <h5 class="text-base font-semibold text-gray-900 dark:text-gray-100">Enable Secure Connection</h5>
                                <p class="text-sm text-gray-500 dark:text-gray-400">Toggle HTTPS support. Requires valid certificate files.</p>
                            </div>
                            <button @click="form.https_enabled = !form.https_enabled" type="button" :class="[form.https_enabled ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch']">
                                <span :class="[form.https_enabled ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                            </button>
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <!-- Certificate -->
                            <div>
                                <label class="label">SSL Certificate</label>
                                <div class="flex gap-2 mt-1">
                                    <input type="text" v-model="form.ssl_certfile" class="input-field flex-grow text-xs font-mono" placeholder="/path/to/cert.pem">
                                    <input type="file" ref="certFileInput" @change="e => handleFileUpload(e, 'cert')" class="hidden">
                                    <button @click.prevent="$refs.certFileInput.click()" type="button" class="btn btn-secondary text-xs whitespace-nowrap">Upload PEM</button>
                                </div>
                            </div>
                            <!-- Private Key -->
                            <div>
                                <label class="label">SSL Private Key</label>
                                <div class="flex gap-2 mt-1">
                                    <input type="text" v-model="form.ssl_keyfile" class="input-field flex-grow text-xs font-mono" placeholder="/path/to/key.pem">
                                    <input type="file" ref="keyFileInput" @change="e => handleFileUpload(e, 'key')" class="hidden">
                                    <button @click.prevent="$refs.keyFileInput.click()" type="button" class="btn btn-secondary text-xs whitespace-nowrap">Upload PEM</button>
                                </div>
                            </div>
                        </div>

                        <div class="flex flex-wrap gap-4 pt-6 mt-2">
                            <button type="button" @click="generateCert" class="btn btn-primary flex items-center gap-2" :disabled="isLoading">
                                <IconSparkles class="w-4 h-4" /> Auto-Generate Self-Signed Cert
                            </button>
                            <button type="button" @click="downloadCert" class="btn btn-secondary flex items-center gap-2" :disabled="!form.ssl_certfile">
                                <IconArrowDownTray class="w-4 h-4" /> Download Certificate
                            </button>
                            <!-- New Install Buttons -->
                            <div class="flex gap-2">
                                <button type="button" @click="downloadTrustScript('windows')" class="btn btn-secondary flex items-center gap-2" :disabled="!form.ssl_certfile" title="Download .bat script to trust cert on Windows">
                                    <IconArrowDownTray class="w-4 h-4" /> Trust Script (Win)
                                </button>
                                <button type="button" @click="downloadTrustScript('linux')" class="btn btn-secondary flex items-center gap-2" :disabled="!form.ssl_certfile" title="Download .sh script to trust cert on Linux">
                                    <IconArrowDownTray class="w-4 h-4" /> Trust Script (Linux)
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Registration -->
                <div v-if="registrationSettings.length > 0" class="border-t pt-8 dark:border-gray-700">
                    <h4 class="settings-category-title">New User Registration</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div v-for="setting in registrationSettings" :key="setting.key" 
                             class="setting-card" :class="{'md:col-span-2': setting.key === 'registration_mode' && setting.description.length > 50}">
                            
                            <template v-if="setting.type === 'boolean'">
                                <div class="flex items-center justify-between h-full bg-gray-50 dark:bg-gray-700/30 p-3 rounded-lg border dark:border-gray-600">
                                    <span class="text-sm font-medium text-gray-700 dark:text-gray-300 pr-4">{{ setting.description }}</span>
                                    <button @click="form[setting.key] = !form[setting.key]" type="button" :class="[form[setting.key] ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch flex-shrink-0']">
                                        <span :class="[form[setting.key] ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                                    </button>
                                </div>
                            </template>
                            
                            <template v-else-if="setting.key === 'registration_mode'">
                                <label :for="setting.key" class="label mb-1">{{ setting.description }}</label>
                                <select :id="setting.key" v-model="form[setting.key]" class="input-field w-full">
                                    <option value="direct">Direct (Instantly Active)</option>
                                    <option value="admin_approval">Admin Approval Required</option>
                                </select>
                            </template>
                        </div>
                    </div>
                </div>

                <!-- Defaults -->
                <div v-if="defaultSettings.length > 0" class="border-t pt-8 dark:border-gray-700">
                    <h4 class="settings-category-title">Defaults for New Users</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div v-for="setting in defaultSettings" :key="setting.key" class="setting-card">
                            
                            <template v-if="setting.type === 'boolean'">
                                <div class="flex items-center justify-between h-full bg-gray-50 dark:bg-gray-700/30 p-3 rounded-lg border dark:border-gray-600">
                                    <span class="text-sm font-medium text-gray-700 dark:text-gray-300 pr-4">{{ setting.description }}</span>
                                    <button @click="form[setting.key] = !form[setting.key]" type="button" :class="[form[setting.key] ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch flex-shrink-0']">
                                        <span :class="[form[setting.key] ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                                    </button>
                                </div>
                            </template>

                            <template v-else>
                                <label :for="setting.key" class="label mb-1">{{ setting.description }}</label>
                                
                                <select v-if="setting.key === 'default_lollms_model_name'" :id="setting.key" v-model="form[setting.key]" class="input-field w-full">
                                    <option value="">(None - User Selects)</option>
                                    <optgroup v-for="group in groupedModels" :key="group.label" :label="group.label">
                                        <option v-for="model in group.items" :key="model.id" :value="model.id">
                                            {{ model.name }}
                                        </option>
                                    </optgroup>
                                </select>

                                <select v-else-if="setting.key === 'default_safe_store_vectorizer'" :id="setting.key" v-model="form[setting.key]" class="input-field w-full">
                                    <option value="" disabled>Select Vectorizer Model</option>
                                    <template v-for="group in availableVectorizers" :key="group.id">
                                        <optgroup :label="group.alias || group.vectorizer_name">
                                            <option v-for="model in group.models" :key="model.value" :value="`${group.alias}/${model.value}`">
                                                {{ model.name }}
                                            </option>
                                        </optgroup>
                                    </template>
                                </select>

                                <select v-else-if="setting.key === 'default_user_ui_level'" :id="setting.key" v-model.number="form[setting.key]" class="input-field w-full">
                                    <option v-for="level in uiLevels" :key="level.value" :value="level.value">{{ level.label }}</option>
                                </select>

                                <input v-else 
                                    :type="setting.type === 'string' ? 'text' : 'number'" 
                                    :id="setting.key" 
                                    v-model="form[setting.key]" 
                                    class="input-field w-full"
                                >
                            </template>
                        </div>
                    </div>
                </div>
            </div>

            <div class="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
                <div class="flex justify-end">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                        {{ isLoading ? 'Saving...' : 'Save All Settings' }}
                    </button>
                </div>
            </div>
        </form>
        
        <div v-else class="p-12 text-center text-gray-500">
            <p v-if="adminStore.isLoadingSettings" class="animate-pulse">Loading settings...</p>
            <p v-else>Could not load server settings.</p>
        </div>
    </div>
</template>

<style scoped>
.settings-category-title { @apply text-lg font-bold text-gray-800 dark:text-gray-100 mb-4; }
.label { @apply block text-sm font-medium text-gray-700 dark:text-gray-300; }
.toggle-switch { @apply relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800; }
.toggle-knob { @apply pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out; }
.setting-card { @apply flex flex-col justify-center; }
</style>
