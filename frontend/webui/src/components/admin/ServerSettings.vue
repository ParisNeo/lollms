<!-- [UPDATE] frontend/webui/src/components/admin/ServerSettings.vue -->
<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import StringListEditor from '../ui/StringListEditor.vue';
import IconLock from '../../assets/icons/IconLock.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import JsonRenderer from '../ui/JsonRenderer.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const form = ref({});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const certFileInput = ref(null);
const keyFileInput = ref(null);
const jsonEditStates = ref({});

const uiLevels = [
    { value: 0, label: 'Beginner' }, { value: 1, label: 'Novice' },
    { value: 2, label: 'Intermediate' }, { value: 3, label: 'Advanced' },
    { value: 4, label: 'Expert' }
];

const categoryOrder = ['Server', 'Authentication', 'Registration', 'Defaults', 'Global LLM Overrides'];

const settingsByGroup = computed(() => {
    const grouped = {};
    adminStore.globalSettings.forEach(s => {
        const cat = s.category || 'Other';
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(s);
    });
    
    const sorted = {};
    categoryOrder.forEach(cat => { if (grouped[cat]) sorted[cat] = grouped[cat]; });
    Object.keys(grouped).forEach(cat => { if (!categoryOrder.includes(cat)) sorted[cat] = grouped[cat]; });
    
    return sorted;
});

const availableVectorizers = computed(() => dataStore.availableVectorizers);
const groupedModels = computed(() => dataStore.availableLLMModelsGrouped);

onMounted(async () => {
    if (adminStore.globalSettings.length === 0) await adminStore.fetchGlobalSettings();
    if (dataStore.availableLollmsModels.length === 0) await dataStore.fetchAdminAvailableLollmsModels();
    await dataStore.fetchAvailableVectorizers();
});

watch(() => adminStore.globalSettings, populateForm, { deep: true, immediate: true });
watch(form, (newValue) => { hasChanges.value = JSON.stringify(newValue) !== pristineState; }, { deep: true });

function populateForm() {
    const newFormState = {};
    adminStore.globalSettings.forEach(setting => {
        if (setting.type === 'json') {
            try { newFormState[setting.key] = JSON.stringify(setting.value, null, 2); }
            catch { newFormState[setting.key] = setting.value; }
            jsonEditStates.value[setting.key] = false;
        } else {
            newFormState[setting.key] = setting.value;
        }
    });
    form.value = newFormState;
    pristineState = JSON.stringify(newFormState);
    hasChanges.value = false;
}

function getParsedJson(key) {
    try { return JSON.parse(form.value[key]); }
    catch (e) { return { "error": "Invalid JSON format" }; }
}

async function handleFileUpload(event, fileType) {
    const file = event.target.files[0];
    if (!file) return;
    isLoading.value = true;
    try {
        const newPath = await adminStore.uploadSslFile(file, fileType);
        form.value[fileType === 'cert' ? 'ssl_certfile' : 'ssl_keyfile'] = newPath;
        uiStore.addNotification(`${file.name} uploaded successfully.`, 'success');
    } finally {
        isLoading.value = false;
    }
}

async function handleSave() {
    isLoading.value = true;
    const payload = {};
    for (const key in form.value) {
        const setting = adminStore.globalSettings.find(s => s.key === key);
        if (setting?.type === 'json') {
            try { payload[key] = JSON.parse(form.value[key]); } catch (e) { 
                uiStore.addNotification(`Invalid JSON in ${setting.description}`, 'error');
                isLoading.value = false; return;
            }
        } else {
            payload[key] = form.value[key];
        }
    }
    try {
        await adminStore.updateGlobalSettings(payload);
        Object.keys(jsonEditStates.value).forEach(k => jsonEditStates.value[k] = false);
    } finally { isLoading.value = false; }
}

async function generateCert() {
    const confirmed = await uiStore.showConfirmation({ title: 'Generate Certificate?', message: 'This will generate a new self-signed certificate. Restart required.', confirmText: 'Generate' });
    if (confirmed.confirmed) await adminStore.generateSelfSignedCert();
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="p-6 border-b border-gray-200 dark:border-gray-700">
            <h3 class="text-xl font-semibold text-gray-900 dark:text-white">Server & Application Settings</h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Configure global server behavior, security, and defaults.</p>
        </div>
        
        <form v-if="Object.keys(form).length" @submit.prevent="handleSave" class="p-6 space-y-12">
            <div v-for="(settings, category) in settingsByGroup" :key="category" class="space-y-6">
                <h4 class="text-lg font-bold text-gray-800 dark:text-gray-100 border-b pb-2">{{ category }}</h4>
                
                <div v-if="category === 'Server'" class="mb-4 p-4 bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-400 text-blue-800 dark:text-blue-200 rounded-r-lg text-sm">
                    Note: Most server changes require a restart.
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div v-for="setting in settings" :key="setting.key" class="flex flex-col justify-center" :class="{'md:col-span-2': ['cors_origins_exceptions', 'ssl_certfile', 'ssl_keyfile'].includes(setting.key)}">
                        
                        <label :for="setting.key" class="block text-sm font-medium mb-1">{{ setting.description || setting.key }}</label>

                        <!-- Types -->
                        <StringListEditor v-if="setting.key === 'cors_origins_exceptions'" v-model="form[setting.key]" />
                        
                        <div v-else-if="setting.type === 'boolean'" class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/30 p-3 rounded-lg border dark:border-gray-600">
                            <span class="text-xs text-gray-500">{{ setting.description }}</span>
                            <button @click="form[setting.key] = !form[setting.key]" type="button" :class="[form[setting.key] ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch']">
                                <span :class="[form[setting.key] ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                            </button>
                        </div>

                        <select v-else-if="setting.key === 'registration_mode'" v-model="form[setting.key]" class="input-field">
                            <option value="direct">Direct (Instantly Active)</option>
                            <option value="admin_approval">Admin Approval Required</option>
                        </select>

                        <select v-else-if="setting.key === 'password_recovery_mode'" v-model="form[setting.key]" class="input-field">
                            <option value="manual">Manual (Admin Managed)</option>
                            <option value="automatic">SMTP Server</option>
                            <option value="system_mail">System Mail Command</option>
                            <option value="outlook">Outlook (Windows)</option>
                        </select>

                        <select v-else-if="setting.key === 'default_lollms_model_name'" v-model="form[setting.key]" class="input-field">
                            <option value="">(None)</option>
                            <optgroup v-for="group in groupedModels" :key="group.label" :label="group.label">
                                <option v-for="model in group.items" :key="model.id" :value="model.id">{{ model.name }}</option>
                            </optgroup>
                        </select>

                        <div v-else-if="setting.type === 'json'" class="space-y-2">
                             <div class="flex justify-between items-center">
                                <button @click="jsonEditStates[setting.key] = !jsonEditStates[setting.key]" type="button" class="btn btn-secondary btn-xs">
                                    {{ jsonEditStates[setting.key] ? 'View Rendered' : 'Edit Raw' }}
                                </button>
                            </div>
                            <textarea v-if="jsonEditStates[setting.key]" v-model="form[setting.key]" rows="5" class="input-field font-mono text-xs"></textarea>
                            <div v-else class="p-2 bg-gray-50 dark:bg-gray-900 rounded border dark:border-gray-700 max-h-40 overflow-y-auto">
                                <JsonRenderer :json="getParsedJson(setting.key)" />
                            </div>
                        </div>

                        <div v-else-if="setting.key === 'ssl_certfile' || setting.key === 'ssl_keyfile'" class="flex gap-2">
                            <input type="text" v-model="form[setting.key]" class="input-field flex-grow text-xs font-mono">
                            <input type="file" @change="e => handleFileUpload(e, setting.key === 'ssl_certfile' ? 'cert' : 'key')" class="hidden" :ref="setting.key === 'ssl_certfile' ? 'certFileInput' : 'keyFileInput'">
                            <button @click.prevent="(setting.key === 'ssl_certfile' ? certFileInput : keyFileInput).click()" type="button" class="btn btn-secondary btn-xs">Upload</button>
                        </div>

                        <input v-else :type="setting.type === 'string' ? 'text' : 'number'" v-model="form[setting.key]" class="input-field">
                    </div>
                </div>

                <!-- HTTPS Extra UI -->
                <div v-if="category === 'Server'" class="mt-4 flex flex-wrap gap-2">
                    <button type="button" @click="generateCert" class="btn btn-secondary btn-sm flex items-center gap-2"><IconSparkles class="w-4 h-4" /> Auto-Cert</button>
                    <button type="button" @click="adminStore.downloadCertificate" class="btn btn-secondary btn-sm flex items-center gap-2"><IconArrowDownTray class="w-4 h-4" /> Download Cert</button>
                </div>
            </div>

            <div class="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700 flex justify-end">
                <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                    {{ isLoading ? 'Saving...' : 'Save All Settings' }}
                </button>
            </div>
        </form>
    </div>
</template>

<style scoped>
.toggle-switch { @apply relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out; }
.toggle-knob { @apply pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out; }
</style>
