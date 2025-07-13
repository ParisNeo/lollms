<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const form = ref({
    https_enabled: false,
    ssl_certfile: '',
    ssl_keyfile: ''
});

const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const serverSettings = computed(() => {
    return adminStore.globalSettings.filter(s => s.category === 'Server');
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
    if (serverSettings.value.length > 0) {
        serverSettings.value.forEach(setting => {
            newFormState[setting.key] = setting.value;
        });
        form.value = newFormState;
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
    }
}

async function handleSave() {
    isLoading.value = true;
    try {
        await adminStore.updateGlobalSettings({ ...form.value });
        uiStore.addNotification('HTTPS settings saved. A server restart is required for changes to take effect.', 'warning', 8000);
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
                Server & HTTPS Settings
            </h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Configure server binding and enable secure connections (HTTPS).
            </p>
        </div>
        <form v-if="Object.keys(form).length" @submit.prevent="handleSave" class="p-6">
            <div class="space-y-8">
                <!-- Restart Warning -->
                <div class="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/50 rounded-lg">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <svg class="h-5 w-5 text-yellow-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                                <path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
                            </svg>
                        </div>
                        <div class="ml-3">
                            <h3 class="text-sm font-medium text-yellow-800 dark:text-yellow-200">Restart Required</h3>
                            <div class="mt-2 text-sm text-yellow-700 dark:text-yellow-100">
                                <p>Any changes made on this page will only take effect after the server application has been restarted.</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Host and Port -->
                 <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label for="host" class="block text-sm font-medium">Host Address</label>
                        <input type="text" id="host" v-model="form.host" class="input-field mt-1" placeholder="e.g., 0.0.0.0">
                    </div>
                     <div>
                        <label for="port" class="block text-sm font-medium">Port</label>
                        <input type="number" id="port" v-model.number="form.port" class="input-field mt-1" placeholder="e.g., 9642">
                    </div>
                </div>

                <!-- HTTPS Toggle -->
                <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                    <span class="flex-grow flex flex-col pr-4">
                        <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Enable HTTPS</span>
                        <span class="text-xs text-gray-500 dark:text-gray-400">Serve the application over a secure HTTPS connection.</span>
                    </span>
                    <button @click="form.https_enabled = !form.https_enabled" type="button" :class="[form.https_enabled ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                        <span :class="[form.https_enabled ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out']"></span>
                    </button>
                </div>

                <!-- SSL Certificate and Key Fields (Conditional) -->
                <transition
                    enter-active-class="transition ease-out duration-200"
                    enter-from-class="opacity-0 -translate-y-2"
                    enter-to-class="opacity-100 translate-y-0"
                    leave-active-class="transition ease-in duration-150"
                    leave-from-class="opacity-100 translate-y-0"
                    leave-to-class="opacity-0 -translate-y-2"
                >
                    <div v-if="form.https_enabled" class="space-y-6 pt-4 border-t border-gray-200 dark:border-gray-600">
                        <div>
                            <label for="ssl_certfile" class="block text-sm font-medium">SSL Certificate File Path</label>
                            <input type="text" id="ssl_certfile" v-model="form.ssl_certfile" class="input-field mt-1" placeholder="/path/to/your/certificate.pem">
                            <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">The full path to your SSL certificate file (e.g., cert.pem, fullchain.pem).</p>
                        </div>
                        <div>
                            <label for="ssl_keyfile" class="block text-sm font-medium">SSL Key File Path</label>
                            <input type="text" id="ssl_keyfile" v-model="form.ssl_keyfile" class="input-field mt-1" placeholder="/path/to/your/private_key.pem">
                             <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">The full path to your SSL private key file.</p>
                        </div>
                    </div>
                </transition>
            </div>

            <!-- Save Button -->
            <div class="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700">
                <div class="flex justify-end">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                        {{ isLoading ? 'Saving...' : 'Save Server Settings' }}
                    </button>
                </div>
            </div>
        </form>
        <div v-else class="p-6 text-center">
            <p class="text-gray-500">
                {{ adminStore.isLoadingSettings ? 'Loading settings...' : 'Could not load server settings.' }}
            </p>
        </div>
    </div>
</template>