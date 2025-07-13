<script setup>
import { ref, onMounted, computed } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin'; // To check global settings
import { storeToRefs } from 'pinia';
import IconCopy from '../../assets/icons/IconCopy.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();
const adminStore = useAdminStore();

const { apiKeys } = storeToRefs(dataStore);
const { globalSettings } = storeToRefs(adminStore);

const newKeyAlias = ref('');
const isLoading = ref(false);

const isServiceEnabled = computed(() => {
    const setting = globalSettings.value.find(s => s.key === 'openai_api_service_enabled');
    return setting ? setting.value : false;
});

onMounted(() => {
    // Data is fetched by the main data store loader
    // but we can ensure it's loaded if the user navigates here directly.
    if(adminStore.globalSettings.length === 0) {
        adminStore.fetchGlobalSettings();
    }
    if (dataStore.apiKeys.length === 0) {
        dataStore.fetchApiKeys();
    }
});

function formatTimestamp(timestamp) {
    if (!timestamp) return 'Never';
    return new Date(timestamp).toLocaleString();
}

async function handleCreateKey() {
    if (!newKeyAlias.value.trim()) {
        uiStore.addNotification('Please provide an alias for the new key.', 'warning');
        return;
    }
    isLoading.value = true;
    try {
        const newKeyData = await dataStore.addApiKey(newKeyAlias.value.trim());
        console.log("Opening the new api key modal")
        uiStore.openModal('newApiKey', { keyData: newKeyData });
        console.log("Opening the new api key modal. DONE")

        newKeyAlias.value = '';
    } catch (error) {
        // Error is handled by the global interceptor
    } finally {
        isLoading.value = false;
    }
}

async function handleDeleteKey(key) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete key '${key.alias}'?`,
        message: 'This will permanently revoke the key. This action cannot be undone.',
        confirmText: 'Delete Key'
    });
    if (confirmed) {
        await dataStore.deleteApiKey(key.id);
    }
}
</script>

<template>
    <div class="space-y-10">
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-4 sm:p-6 border-b border-gray-200 dark:border-gray-700">
                <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">API Keys</h2>
                <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">
                    Manage your API keys for accessing the LoLLMs backend with OpenAI-compatible tools.
                </p>
            </div>
            
            <div v-if="!isServiceEnabled" class="p-6 text-center">
                 <div class="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/50 rounded-lg">
                    <p class="text-sm text-yellow-800 dark:text-yellow-200">
                        The OpenAI-compatible API service is currently disabled by the administrator.
                    </p>
                </div>
            </div>

            <div v-else>
                <!-- Create Key Form -->
                <div class="p-4 sm:p-6">
                    <form @submit.prevent="handleCreateKey" class="flex flex-col sm:flex-row items-start sm:items-end gap-4">
                        <div class="flex-grow w-full">
                            <label for="keyAlias" class="block text-sm font-medium text-gray-700 dark:text-gray-300">New Key Alias</label>
                            <input
                                type="text"
                                id="keyAlias"
                                v-model="newKeyAlias"
                                class="input-field mt-1"
                                placeholder="e.g., My Research Tool"
                                required
                            />
                        </div>
                        <button type="submit" class="btn btn-primary w-full sm:w-auto" :disabled="isLoading">
                            {{ isLoading ? 'Creating...' : 'Create New Key' }}
                        </button>
                    </form>
                </div>
                
                <!-- Keys List -->
                <div class="border-t border-gray-200 dark:border-gray-700">
                    <div v-if="apiKeys.length === 0" class="p-6 text-center text-gray-500 dark:text-gray-400">
                        You have not created any API keys yet.
                    </div>
                    <ul v-else role="list" class="divide-y divide-gray-200 dark:divide-gray-700">
                        <li v-for="key in apiKeys" :key="key.id" class="px-4 py-4 sm:px-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                            <div class="flex-grow">
                                <p class="text-sm font-semibold text-gray-900 dark:text-white">{{ key.alias }}</p>
                                <p class="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-2">
                                    <span>{{ key.key_prefix }}...</span>
                                </p>
                            </div>
                            <div class="flex-shrink-0 flex flex-col sm:flex-row sm:items-center gap-4 w-full sm:w-auto">
                                <div class="text-xs text-gray-500 dark:text-gray-400 sm:text-right">
                                    <p>Last used: {{ formatTimestamp(key.last_used_at) }}</p>
                                    <p>Created: {{ formatTimestamp(key.created_at) }}</p>
                                </div>
                                <button @click="handleDeleteKey(key)" class="btn btn-danger-outline btn-sm sm:w-auto w-full">
                                    Delete
                                </button>
                            </div>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</template>