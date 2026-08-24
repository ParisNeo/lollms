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
        uiStore.addNotification('Configuration saved successfully.', 'success');
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
                <IconAnimateSpin class="w-6 h-6 text-primary animate-spin" />
                <span class="ml-2 text-xs text-gray-500">Loading settings...</span>
            </div>

            <form v-else-if="app" @submit.prevent="handleUpdate" class="space-y-5">
                <!-- Running Warning -->
                <div v-if="isAppRunning" class="p-3.5 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 rounded-xl text-xs border border-amber-300/60 dark:border-amber-700/40">
                    <strong>Service Running:</strong> You must stop the application before modifying network or system properties.
                </div>

                <fieldset :disabled="isAppRunning" class="space-y-4">
                    <!-- Tab Switcher (if Schema exists) -->
                    <div v-if="hasSchema" class="border-b border-gray-200 dark:border-gray-700 flex space-x-4">
                        <button 
                            type="button" 
                            @click="activeTab = 'system'" 
                            :class="[activeTab === 'system' ? 'border-blue-500 text-blue-600 font-bold' : 'border-transparent text-gray-500 hover:text-gray-700', 'pb-2 border-b-2 text-xs transition-colors']"
                        >
                            System Settings
                        </button>
                        <button 
                            type="button" 
                            @click="activeTab = 'app'" 
                            :class="[activeTab === 'app' ? 'border-blue-500 text-blue-600 font-bold' : 'border-transparent text-gray-500 hover:text-gray-700', 'pb-2 border-b-2 text-xs transition-colors']"
                        >
                            App Schema Options
                        </button>
                    </div>

                    <!-- TAB 1: SYSTEM SETTINGS -->
                    <div v-show="activeTab === 'system'" class="space-y-4">
                        <div>
                            <label for="app-name" class="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Display Name</label>
                            <input id="app-name" v-model="configData.name" type="text" class="input-field text-xs py-2 rounded-xl" />
                        </div>
                        <div>
                            <label for="app-desc" class="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Description</label>
                            <textarea id="app-desc" v-model="configData.description" rows="2" class="input-field text-xs py-2 rounded-xl"></textarea>
                        </div>
                        <div>
                            <label for="app-port" class="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Port Allocation</label>
                            <input id="app-port" v-model.number="configData.port" type="number" min="1025" max="65535" required class="input-field text-xs py-2 rounded-xl font-mono" />
                        </div>

                        <!-- Toggles -->
                        <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200/80 dark:border-gray-700/60">
                            <span class="text-xs font-medium text-gray-900 dark:text-gray-100">Launch on Server Startup</span>
                            <button @click="configData.autostart = !configData.autostart" type="button" :class="[configData.autostart ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-700', 'relative inline-flex h-5 w-10 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200']">
                                <span :class="[configData.autostart ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200']"></span>
                            </button>
                        </div>

                        <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200/80 dark:border-gray-700/60">
                            <span class="text-xs font-medium text-gray-900 dark:text-gray-100">Allow OpenAI API Access</span>
                            <button @click="configData.allow_openai_api_access = !configData.allow_openai_api_access" type="button" :class="[configData.allow_openai_api_access ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-700', 'relative inline-flex h-5 w-10 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200']">
                                <span :class="[configData.allow_openai_api_access ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200']"></span>
                            </button>
                        </div>

                        <!-- Auth Configuration -->
                        <div class="pt-3 border-t dark:border-gray-700 space-y-3">
                            <h4 class="font-bold text-xs uppercase tracking-wider text-gray-700 dark:text-gray-300">Authentication Configuration</h4>
                            <div>
                                <label for="service-auth-type" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Auth Type</label>
                                <select id="service-auth-type" v-model="configData.authentication_type" class="input-field text-xs py-2 rounded-xl">
                                    <option value="none">None</option>
                                    <option value="bearer">Bearer Token</option>
                                    <option value="lollms_sso">LoLLMs SSO</option>
                                </select>
                            </div>
                            <div v-if="configData.authentication_type === 'bearer'" class="space-y-1">
                                <label for="service-auth-key" class="block text-xs font-medium text-gray-700 dark:text-gray-300">Bearer Token</label>
                                <input id="service-auth-key" v-model="configData.authentication_key" type="password" class="input-field text-xs py-2 rounded-xl" placeholder="Enter Bearer Token">
                            </div>
                            <div v-if="configData.authentication_type === 'lollms_sso'" class="space-y-1">
                                <label for="sso-redirect-uri" class="block text-xs font-medium text-gray-700 dark:text-gray-300">Redirect URI</label>
                                <input id="sso-redirect-uri" v-model="configData.sso_redirect_uri" type="url" class="input-field text-xs py-2 rounded-xl" placeholder="https://app.local/callback">
                            </div>
                        </div>
                    </div>
                    
                    <!-- TAB 2: SCHEMA-DRIVEN APP SETTINGS -->
                    <div v-show="activeTab === 'app' && hasSchema" class="space-y-4">
                        <div v-for="[key, prop] in sortedSchemaProperties" :key="key" class="space-y-1">
                            <label :for="`config-${key}`" class="block text-xs font-semibold text-gray-700 dark:text-gray-300">
                                {{ prop.title || key }}
                            </label>
                            
                            <div class="relative">
                                <textarea 
                                    v-if="prop.format === 'multiline'" 
                                    v-model="configData[key]" 
                                    class="input-field text-xs py-2 rounded-xl h-24" 
                                    :disabled="configMetadata.env_overrides?.includes(key)"
                                ></textarea>
                                
                                <select 
                                    v-else-if="prop.enum" 
                                    v-model="configData[key]" 
                                    class="input-field text-xs py-2 rounded-xl" 
                                    :disabled="configMetadata.env_overrides?.includes(key)"
                                >
                                    <option v-for="o in prop.enum" :key="o" :value="o">{{ o }}</option>
                                </select>
                                
                                <div v-else-if="prop.type === 'boolean'" class="flex items-center gap-2 pt-1">
                                    <input :id="`config-${key}`" type="checkbox" v-model="configData[key]" class="h-4 w-4 rounded" :disabled="configMetadata.env_overrides?.includes(key)">
                                    <label :for="`config-${key}`" class="text-xs text-gray-600 dark:text-gray-300">{{ prop.description }}</label>
                                </div>
                                
                                <div v-else class="relative">
                                    <input 
                                        :type="prop.sensitive && !sensitiveFieldsVisibility[key] ? 'password' : (prop.type === 'integer' ? 'number' : 'text')" 
                                        v-model="configData[key]" 
                                        class="input-field text-xs py-2 rounded-xl" 
                                        :class="{'pr-10': prop.sensitive}" 
                                        :disabled="configMetadata.env_overrides?.includes(key)"
                                    />
                                    <button 
                                        v-if="prop.sensitive" 
                                        type="button" 
                                        @click="toggleVisibility(key)" 
                                        class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
                                    >
                                        <IconEyeOff v-if="sensitiveFieldsVisibility[key]" class="h-4 w-4"/>
                                        <IconEye v-else class="h-4 w-4"/>
                                    </button>
                                </div>
                            </div>
                            <p v-if="configMetadata.env_overrides?.includes(key)" class="text-[10px] text-amber-500">
                                Overridden by '{{ prop.envVar }}' environment variable.
                            </p>
                        </div>
                    </div>
                </fieldset>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end gap-2">
                <button @click="uiStore.closeModal('appConfig')" type="button" class="btn btn-secondary btn-sm">Cancel</button>
                <button @click="handleUpdate" type="button" class="btn btn-primary btn-sm font-semibold" :disabled="isLoading || isAppRunning">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-1.5 animate-spin" />
                    {{ isLoading ? 'Saving...' : 'Save Configuration' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>