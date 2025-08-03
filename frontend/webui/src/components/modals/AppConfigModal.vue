<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from '../ui/GenericModal.vue';
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

const isAppRunning = computed(() => app.value?.status === 'running');
const hasSchema = computed(() => schema.value && schema.value.properties && Object.keys(schema.value.properties).length > 0);
const sortedSchemaProperties = computed(() => {
    if (!hasSchema.value) return [];
    return Object.entries(schema.value.properties).sort(([, a], [, b]) => (a.order || 999) - (b.order || 999));
});

watch(app, async (newApp) => {
    if (newApp) {
        isLoading.value = true;
        schema.value = null;
        configData.value = {};
        configMetadata.value = {};
        sensitiveFieldsVisibility.value = {};
        try {
            const fetchedSchema = await adminStore.fetchAppConfigSchema(newApp.id);
            if (fetchedSchema && Object.keys(fetchedSchema.properties || {}).length > 0) {
                schema.value = fetchedSchema;
                const { config, metadata } = await adminStore.fetchAppConfig(newApp.id);
                configData.value = config;
                configMetadata.value = metadata;
            } else {
                 const currentConfig = { port: newApp.port, autostart: newApp.autostart };
                 configData.value = currentConfig;
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
        } else {
            await adminStore.updateInstalledApp(app.value.id, {
                port: configData.value.port,
                autostart: configData.value.autostart
            });
        }
        uiStore.closeModal('appConfig');
    } catch (error) {
        // Error is handled globally
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
                <IconAnimateSpin class="w-8 h-8 text-gray-500" />
                <span class="ml-3 text-gray-500">Loading configuration...</span>
            </div>
            <form v-else-if="app" @submit.prevent="handleUpdate" class="space-y-6">
                <div v-if="isAppRunning" class="p-4 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300 rounded-lg text-sm">
                    This app is currently running. You must stop it before changing its configuration.
                </div>
                
                <fieldset :disabled="isAppRunning" class="space-y-6">
                    <!-- Schema-driven form -->
                    <div v-if="hasSchema" class="space-y-5">
                        <div v-for="[key, prop] in sortedSchemaProperties" :key="key">
                            <label :for="`config-${key}`" class="block text-sm font-medium">{{ prop.title || key }}</label>
                            <div class="mt-1 relative">
                                <!-- Textarea -->
                                <textarea v-if="prop.format === 'multiline'" :id="`config-${key}`" v-model="configData[key]" class="input-field h-24" :placeholder="prop.description || ''" :disabled="configMetadata.env_overrides?.includes(key)"></textarea>
                                <!-- Select Dropdown -->
                                <select v-else-if="prop.enum" :id="`config-${key}`" v-model="configData[key]" class="input-field" :disabled="configMetadata.env_overrides?.includes(key)">
                                    <option v-for="option in prop.enum" :key="option" :value="option">{{ option }}</option>
                                </select>
                                <!-- Checkbox -->
                                <div v-else-if="prop.type === 'boolean'" class="flex items-center">
                                    <input :id="`config-${key}`" type="checkbox" v-model="configData[key]" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" :disabled="configMetadata.env_overrides?.includes(key)">
                                    <label :for="`config-${key}`" class="ml-2 text-sm text-gray-600 dark:text-gray-300">{{ prop.description || '' }}</label>
                                </div>
                                <!-- Generic Input (text, number, password) -->
                                <div v-else class="relative">
                                    <input 
                                        :id="`config-${key}`"
                                        :type="prop.sensitive && !sensitiveFieldsVisibility[key] ? 'password' : (prop.type === 'integer' || prop.type === 'number' ? 'number' : 'text')"
                                        v-model="configData[key]" 
                                        class="input-field" 
                                        :class="{'pr-10': prop.sensitive}"
                                        :placeholder="prop.description || ''" 
                                        :disabled="configMetadata.env_overrides?.includes(key)"
                                    />
                                    <button v-if="prop.sensitive" type="button" @click="toggleVisibility(key)" class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600">
                                        <IconEyeOff v-if="sensitiveFieldsVisibility[key]" class="h-5 w-5" />
                                        <IconEye v-else class="h-5 w-5" />
                                    </button>
                                </div>
                            </div>
                             <p v-if="configMetadata.env_overrides?.includes(key)" class="mt-1 text-xs text-yellow-600 dark:text-yellow-400">
                                This value is managed by the '{{ prop.envVar }}' environment variable and cannot be changed here.
                            </p>
                        </div>
                    </div>

                    <!-- Fallback/Legacy Config Form -->
                    <div v-else class="space-y-6">
                        <div>
                            <label for="app-port" class="block text-sm font-medium">Port Number</label>
                            <input id="app-port" v-model.number="configData.port" type="number" min="1025" max="65535" required class="input-field mt-1" placeholder="e.g., 9601" />
                        </div>
                        <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                            <span class="flex-grow flex flex-col">
                                <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Start on System Startup</span>
                                <span class="text-sm text-gray-500 dark:text-gray-400">Automatically launch this app when the main server starts.</span>
                            </span>
                            <button @click="configData.autostart = !configData.autostart" type="button" :class="[configData.autostart ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                                <span :class="[configData.autostart ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition']"></span>
                            </button>
                        </div>
                    </div>
                </fieldset>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('appConfig')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleUpdate" type="button" class="btn btn-primary" :disabled="isLoading || isAppRunning">
                    {{ isLoading ? 'Saving...' : 'Save Changes' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>