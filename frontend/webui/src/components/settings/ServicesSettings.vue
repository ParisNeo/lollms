<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const form = ref({
    openai_api_service_enabled: false,
    openai_api_require_key: true,
    ollama_service_enabled: false,
    ollama_require_key: true,
});

const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const serviceSettings = computed(() => {
    return adminStore.globalSettings.filter(s => s.category === 'Services');
});

onMounted(() => {
    if (adminStore.globalSettings.length === 0) {
        adminStore.fetchGlobalSettings();
    } else {
        populateForm();
    }
});

watch(() => adminStore.globalSettings, populateForm, { deep: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== pristineState;
}, { deep: true });

function populateForm() {
    const newFormState = {};
    if (serviceSettings.value.length > 0) {
        serviceSettings.value.forEach(setting => {
            newFormState[setting.key] = setting.value;
        });
        form.value = { ...form.value, ...newFormState };
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
    }
}

async function handleSave() {
    isLoading.value = true;
    try {
        await adminStore.updateGlobalSettings({ ...form.value });
        uiStore.addNotification('Service settings saved.', 'success');
    } catch (error) {
        // Error is handled globally
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="p-6 border-b border-gray-200 dark:border-gray-700">
            <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                API Services
            </h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Manage built-in API services like the OpenAI-compatible endpoint.
            </p>
        </div>
        <form v-if="Object.keys(form).length" @submit.prevent="handleSave" class="p-6">
            <div class="space-y-6">
                <div class="p-4 border dark:border-gray-700 rounded-lg">
                    <h4 class="font-semibold text-lg mb-2">OpenAI-Compatible API</h4>
                    <div class="space-y-4">
                        <div class="toggle-container">
                            <span class="toggle-label">
                                Enable OpenAI API Service
                                <span class="toggle-description">Exposes `/v1/...` endpoints for compatibility with OpenAI clients.</span>
                            </span>
                            <button @click="form.openai_api_service_enabled = !form.openai_api_service_enabled" type="button" :class="[form.openai_api_service_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']">
                                <span :class="[form.openai_api_service_enabled ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                            </button>
                        </div>

                        <div class="toggle-container" :class="{'opacity-50 cursor-not-allowed': !form.openai_api_service_enabled}">
                            <span class="toggle-label">
                                Require API Key
                                <span class="toggle-description">If disabled, unauthenticated requests are permitted and handled by the primary admin account.</span>
                            </span>
                            <button @click="form.openai_api_require_key = !form.openai_api_require_key" type="button" :disabled="!form.openai_api_service_enabled" :class="[form.openai_api_require_key ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']">
                                <span :class="[form.openai_api_require_key ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Ollama API section -->
                <div class="p-4 border dark:border-gray-700 rounded-lg">
                    <h4 class="font-semibold text-lg mb-2">Ollama-Compatible API</h4>
                    <div class="space-y-4">
                        <div class="toggle-container">
                            <span class="toggle-label">
                                Enable Ollama API Service
                                <span class="toggle-description">Exposes `/ollama/v1/...` endpoints for compatibility with Ollama clients.</span>
                            </span>
                            <button @click="form.ollama_service_enabled = !form.ollama_service_enabled" type="button" :class="[form.ollama_service_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']">
                                <span :class="[form.ollama_service_enabled ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                            </button>
                        </div>

                        <div class="toggle-container" :class="{'opacity-50 cursor-not-allowed': !form.ollama_service_enabled}">
                            <span class="toggle-label">
                                Require API Key
                                <span class="toggle-description">If disabled, unauthenticated requests are permitted and handled by the primary admin account.</span>
                            </span>
                            <button @click="form.ollama_require_key = !form.ollama_require_key" type="button" :disabled="!form.ollama_service_enabled" :class="[form.ollama_require_key ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']">
                                <span :class="[form.ollama_require_key ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                            </button>
                        </div>
                    </div>
                </div>

            </div>

            <!-- Save Button -->
            <div class="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700">
                <div class="flex justify-end">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                        {{ isLoading ? 'Saving...' : 'Save Service Settings' }}
                    </button>
                </div>
            </div>
        </form>
    </div>
</template>

<style scoped>
.label { @apply block text-sm font-medium text-gray-700 dark:text-gray-300; }
.toggle-container { @apply flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg; }
.toggle-label { @apply flex-grow flex flex-col text-sm font-medium text-gray-900 dark:text-gray-100; }
.toggle-description { @apply text-xs text-gray-500 dark:text-gray-400 font-normal mt-1; }
.toggle-switch { @apply relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed; }
.toggle-knob { @apply pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out; }
</style>