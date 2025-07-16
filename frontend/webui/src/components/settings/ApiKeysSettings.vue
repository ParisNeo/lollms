<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { storeToRefs } from 'pinia';
import IconTrash from '../../assets/icons/IconTrash.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const { apiKeys } = storeToRefs(dataStore);
const { user } = storeToRefs(authStore);

const newKeyAlias = ref('');
const isLoading = ref(false);
const selectedKeys = ref(new Set());

const isServiceEnabled = computed(() => {
    return user.value ? user.value.openai_api_service_enabled : false;
});

const hasKeys = computed(() => apiKeys.value.length > 0);

const allKeysSelected = computed({
    get: () => hasKeys.value && selectedKeys.value.size === apiKeys.value.length,
    set: (value) => {
        if (value) {
            selectedKeys.value = new Set(apiKeys.value.map(k => k.id));
        } else {
            selectedKeys.value.clear();
        }
    }
});

onMounted(() => {
    if (isServiceEnabled.value && dataStore.apiKeys.length === 0) {
        dataStore.fetchApiKeys();
    }
});

watch(isServiceEnabled, (newValue) => {
    if (newValue && dataStore.apiKeys.length === 0) {
        dataStore.fetchApiKeys();
    }
});

watch(apiKeys, () => {
    selectedKeys.value.clear();
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
        uiStore.openModal('newApiKey', { keyData: newKeyData });
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
        await dataStore.deleteSingleApiKey(key.id);
    }
}

async function handleDeleteSelected() {
    const idsToDelete = Array.from(selectedKeys.value);
    if (idsToDelete.length === 0) {
        uiStore.addNotification('No keys selected for deletion.', 'warning');
        return;
    }
    
    const confirmed = await uiStore.showConfirmation({
        title: `Delete ${idsToDelete.length} API Key(s)?`,
        message: 'This will permanently revoke the selected keys. This action cannot be undone.',
        confirmText: 'Delete Selected'
    });

    if (confirmed) {
        await dataStore.deleteMultipleApiKeys(idsToDelete);
    }
}

function toggleSelectAll() {
    allKeysSelected.value = !allKeysSelected.value;
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
                    <div v-if="!hasKeys" class="p-6 text-center text-gray-500 dark:text-gray-400">
                        You have not created any API keys yet.
                    </div>
                    <div v-else>
                        <!-- Contextual Actions Header - Shows only when items are selected -->
                        <div v-if="selectedKeys.size > 0" class="px-4 sm:px-6 py-2 bg-blue-50 dark:bg-blue-900/20 flex items-center justify-between transition-all">
                            <div class="flex items-center gap-4">
                                <span class="text-sm font-semibold text-blue-800 dark:text-blue-200">{{ selectedKeys.size }} selected</span>
                                <button @click="toggleSelectAll" class="text-sm font-medium text-blue-600 hover:underline">
                                    {{ allKeysSelected ? 'Deselect All' : 'Select All' }}
                                </button>
                            </div>
                            <button @click="handleDeleteSelected" class="btn btn-danger btn-sm">
                                Delete Selected
                            </button>
                        </div>

                        <!-- Key List -->
                        <ul role="list" class="divide-y divide-gray-200 dark:divide-gray-700">
                            <li v-for="key in apiKeys" :key="key.id" 
                                class="px-4 py-4 sm:px-6 flex items-center gap-4 group transition-colors duration-150"
                                :class="{ 'bg-blue-50 dark:bg-blue-900/40': selectedKeys.has(key.id) }"
                            >
                                <input 
                                    type="checkbox" 
                                    :value="key.id" 
                                    v-model="selectedKeys" 
                                    class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                                >
                                <div class="flex-grow ml-2">
                                    <p class="text-sm font-semibold text-gray-900 dark:text-white">{{ key.alias }}</p>
                                    <p class="text-sm text-gray-500 dark:text-gray-400 font-mono">{{ key.key_prefix }}<span>...</span>
                                    </p>
                                </div>
                                <div class="text-xs text-gray-500 dark:text-gray-400 text-right">
                                    <p>Last used: {{ formatTimestamp(key.last_used_at) }}</p>
                                    <p>Created: {{ formatTimestamp(key.created_at) }}</p>
                                </div>
                                <button 
                                    @click="handleDeleteKey(key)" 
                                    class="p-2 rounded-full text-gray-400 hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/50 dark:hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                    :class="{'opacity-100': selectedKeys.size>0}"
                                    title="Delete this key"
                                >
                                    <IconTrash class="h-5 w-5" />
                                </button>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>