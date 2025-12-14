<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from './GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const props = computed(() => uiStore.modalData('appConfig'));
const app = computed(() => props.value?.app);

const isLoading = ref(false);
const schema = ref(null);
const configData = ref({});
const configMetadata = ref({});
const sensitiveFieldsVisibility = ref({});
const activeTab = ref('system');

const isAppRunning = computed(() => app.value?.status === 'running');
const hasSchema = computed(() => schema.value && schema.value.properties && Object.keys(schema.value.properties).length > 0);
const sortedSchemaProperties = computed(() => {
    if (!hasSchema.value) return [];
    return Object.entries(schema.value.properties).sort(([, a], [, b]) => (a.order || 999) - (b.order || 999));
});

watch(app, async (newApp) => {
    if (newApp) {
        isLoading.value = true;
        activeTab.value = 'system';
        schema.value = null;
        configData.value = {};
        configMetadata.value = {};
        sensitiveFieldsVisibility.value = {};
        try {
            const fetchedSchema = await adminStore.fetchAppConfigSchema(newApp.id);
            if (fetchedSchema && Object.keys(fetchedSchema.properties || {}).length > 0) {
                schema.value = fetchedSchema;
                const { config, metadata } = await adminStore.fetchAppConfig(newApp.id);
                configData.value = { ...newApp, ...config };
                if (!configData.value.authentication_type) {
                    configData.value.authentication_type = 'none';
                }
                configMetadata.value = metadata;
            } else {
                configData.value = { ...newApp };
                if (!configData.value.authentication_type) {
                    configData.value.authentication_type = 'none';
                }
            }
        } catch (error) {
            console.error("Failed to load app configuration:", error);
            uiStore.addNotification('Could not load app configuration.', 'error');
            uiStore.closeModal('appConfig');
        } finally {
            isLoading.value = false;
        }
    }
}, { immediate: true, deep: true });

function toggleVisibility(key) {
    sensitiveFieldsVisibility.value[key] = !sensitiveFieldsVisibility.value[key];
}

async function handleUpdate() {
    if (!app.value) return;
    isLoading.value = true;
    try {
        if (hasSchema.value) {
            await adminStore.updateAppConfig(app.value.id, configData.value);
        }
        
        const systemSettingsPayload = {
            name: configData.value.name,
            description: configData.value.description,
            port: configData.value.port,
            autostart: configData.value.autostart,
            allow_openai_api_access: configData.value.allow_openai_api_access,
            authentication_type: configData.value.authentication_type,
            authentication_key: configData.value.authentication_key,
            sso_redirect_uri: configData.value.sso_redirect_uri,
        };
        
        await adminStore.updateInstalledApp(app.value.id, systemSettingsPayload);
        uiStore.closeModal('appConfig');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modal-name="appConfig"
        :title="app ? `Configure: ${app.name}` : 'Configure App'"
        :max-width-class="hasSchema ? 'max-w-2xl' : 'max-w-lg'"
    >
        <template #body>
            <div v-if="isLoading" class="flex justify-center items-center p-8">
                <IconAnimateSpin class="w-8 h-8 text-gray-500 animate-spin" />
                <span class="ml-3 text-gray-500">Loading configuration...</span>
            </div>
            <form v-else-if="app" @submit.prevent="handleUpdate" class="space-y-6">
                 <div v-if="isAppRunning" class="p-4 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300 rounded-lg text-sm">
                    This app is currently running. You must stop it before changing its configuration.
                </div>
                 <fieldset :disabled="isAppRunning" class="space-y-6">
                    <div v-if="hasSchema" class="border-b border-gray-200 dark:border-gray-700">
                        <nav class="-mb-px flex space-x-6">
                            <button type="button" @click="activeTab = 'system'" :class="[activeTab === 'system' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm']">System Settings</button>
                            <button type="button" @click="activeTab = 'app'" :class="[activeTab === 'app' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300', 'whitespace-nowrap py-3 px-1 border-b-2 font-medium text-sm']">App Settings</button>
                        </nav>
                    </div>

                    <div v-show="activeTab === 'system'" class="space-y-4">
                        <h4 class="font-semibold text-lg">System Settings</h4>
                         <div><label for="app-name" class="label">Name</label><input id="app-name" v-model="configData.name" type="text" class="input-field mt-1" /></div>
                         <div><label for="app-desc" class="label">Description</label><textarea id="app-desc" v-model="configData.description" rows="3" class="input-field mt-1"></textarea></div>
                         <div><label for="app-port" class="label">Port Number</label><input id="app-port" v-model.number="configData.port" type="number" min="1025" max="65535" required class="input-field mt-1" /></div>
                         <div class="toggle-container"><span class="toggle-label">Start on System Startup</span><button @click="configData.autostart = !configData.autostart" type="button" :class="[configData.autostart ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']"><span :class="[configData.autostart ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span></button></div>
                         <div class="toggle-container"><span class="toggle-label">Allow OpenAI API Access</span><button @click="configData.allow_openai_api_access = !configData.allow_openai_api_access" type="button" :class="[configData.allow_openai_api_access ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']"><span :class="[configData.allow_openai_api_access ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span></button></div>
                        <div class="pt-4 mt-4 border-t dark:border-gray-600">
                            <h4 class="font-semibold text-lg">Authentication</h4>
                            <div>
                                <label for="service-auth-type" class="label">Authentication Type</label>
                                <select id="service-auth-type" v-model="configData.authentication_type" class="input-field">
                                    <option value="none">None</option>
                                    <option value="bearer">Bearer Token</option>
                                    <option value="lollms_sso">LoLLMs SSO</option>
                                </select>
                            </div>
                            <div v-if="configData.authentication_type === 'bearer'" class="mt-4">
                                <label for="service-auth-key" class="label">Authentication Key</label>
                                <input id="service-auth-key" v-model="configData.authentication_key" type="password" class="input-field" placeholder="Enter Bearer token">
                            </div>
                            <div v-if="configData.authentication_type === 'lollms_sso'" class="mt-4 space-y-4">
                                <div>
                                    <label for="sso-redirect-uri" class="label">Redirect URI</label>
                                    <input id="sso-redirect-uri" v-model="configData.sso_redirect_uri" type="url" class="input-field" placeholder="e.g., https://myapp.com/callback">
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div v-show="activeTab === 'app' && hasSchema" class="space-y-5">
                         <h4 class="font-semibold text-lg">App Settings</h4>
                        <div v-for="[key, prop] in sortedSchemaProperties" :key="key">
                            <label :for="`config-${key}`" class="block text-sm font-medium">{{ prop.title || key }}</label>
                            <div class="mt-1 relative">
                                <textarea v-if="prop.format === 'multiline'" v-model="configData[key]" class="input-field h-24" :disabled="configMetadata.env_overrides?.includes(key)"></textarea>
                                <select v-else-if="prop.enum" v-model="configData[key]" class="input-field" :disabled="configMetadata.env_overrides?.includes(key)"><option v-for="o in prop.enum" :key="o" :value="o">{{o}}</option></select>
                                <div v-else-if="prop.type === 'boolean'" class="flex items-center"><input :id="`config-${key}`" type="checkbox" v-model="configData[key]" class="h-4 w-4 rounded" :disabled="configMetadata.env_overrides?.includes(key)"><label :for="`config-${key}`" class="ml-2 text-sm">{{prop.description}}</label></div>
                                <div v-else class="relative"><input :type="prop.sensitive&&!sensitiveFieldsVisibility[key]?'password':(prop.type==='integer'?'number':'text')" v-model="configData[key]" class="input-field" :class="{'pr-10':prop.sensitive}" :disabled="configMetadata.env_overrides?.includes(key)"/><button v-if="prop.sensitive" type="button" @click="toggleVisibility(key)" class="absolute inset-y-0 right-0 pr-3 flex items-center"><IconEyeOff v-if="sensitiveFieldsVisibility[key]" class="h-5 w-5"/><IconEye v-else class="h-5 w-5"/></button></div>
                            </div>
                            <p v-if="configMetadata.env_overrides?.includes(key)" class="mt-1 text-xs text-yellow-500">Managed by '{{prop.envVar}}' environment variable.</p>
                        </div>
                    </div>
                 </fieldset>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('appConfig')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleUpdate" type="button" class="btn btn-primary" :disabled="isLoading || isAppRunning">
                    <IconAnimateSpin v-if="isLoading" class="w-5 h-5 mr-2 animate-spin" />
                    {{ isLoading ? 'Saving...' : 'Save Changes' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>
<style scoped>
.label { @apply block text-sm font-medium text-gray-700 dark:text-gray-300; }
.toggle-container { @apply flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg; }
.toggle-label { @apply flex-grow flex flex-col text-sm font-medium text-gray-900 dark:text-gray-100; }
.toggle-switch { @apply relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out; }
.toggle-knob { @apply pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out; }
</style>
