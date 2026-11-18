<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { storeToRefs } from 'pinia';
import IconTrash from '../../assets/icons/IconTrash.vue';

import { Line } from 'vue-chartjs';
import {
  Chart as ChartJS, Title, Tooltip, Legend, LineElement, BarElement, ArcElement,
  CategoryScale, LinearScale, PointElement, TimeScale, Filler
} from 'chart.js';
import 'chartjs-adapter-date-fns';

ChartJS.register(Title, Tooltip, Legend, LineElement, BarElement, ArcElement, CategoryScale, LinearScale, PointElement, TimeScale, Filler);
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import apiClient from '../../services/api';

const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const { apiKeys } = storeToRefs(dataStore);
const { user } = storeToRefs(authStore);

const newKeyAlias = ref('');
const isLoading = ref(false);
const selectedKeys = ref(new Set());

// ── Per-key consumption analytics ──────────────────────────────────────
const keyUsage = ref([]);            // [{ key_id, alias, key_prefix, total_tokens, prompt_tokens, completion_tokens, requests, last_used_at, tokens_per_day: [{date,count}] }]
const isLoadingKeyUsage = ref(false);
const usageRangeDays = ref(30);


async function fetchKeyUsage() {
    isLoadingKeyUsage.value = true;
    try {
        const res = await apiClient.get('/api/users/me/api-keys/usage', {
            params: { days: usageRangeDays.value }
        });
        keyUsage.value = res.data?.keys || [];
    } catch (e) {
        console.warn("Could not load key usage:", e);
        keyUsage.value = [];
    } finally {
        isLoadingKeyUsage.value = false;
    }
}

function usageFor(keyId) {
    return keyUsage.value.find(k => k.id === keyId) || null;
}

const currentTheme = computed(() => uiStore.currentTheme);

function formatUsageDate(d) {
    if (!d) return 'Never';
    return new Date(d).toLocaleString();
}

function keyChartData(keyId) {
    const entry = usageFor(keyId);
    if (!entry || !(entry.tokens_per_day || []).length) {
        return { labels: [], datasets: [] };
    }
    const series = entry.tokens_per_day;
    return {
        labels: series.map(t => t.date),
        datasets: [{
            label: 'Tokens',
            data: series.map(t => t.count),
            borderColor: '#8B5CF6',
            backgroundColor: 'rgba(139, 92, 246, 0.12)',
            fill: true,
            tension: 0.2,
            pointRadius: 2
        }]
    };
}

const keyChartOptions = computed(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
    scales: {
        x: {
            grid: { color: currentTheme.value === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)' },
            ticks: { color: currentTheme.value === 'dark' ? '#cbd5e1' : '#4b5563', maxRotation: 0, autoSkip: true }
        },
        y: {
            beginAtZero: true,
            grid: { color: currentTheme.value === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)' },
            ticks: { color: currentTheme.value === 'dark' ? '#cbd5e1' : '#4b5563' }
        }
    }
}));

const isAnyServiceEnabled = computed(() => {
    return user.value ? (user.value.openai_api_service_enabled || user.value.ollama_service_enabled) : false;
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


function usageForKey(keyId) {
    return keyUsage.value.find(u => String(u.key_id) === String(keyId)) || null;
}

function toggleKeyChart(keyId) {
    expandedKeyId.value = expandedKeyId.value === keyId ? null : keyId;
}

function chartDataFor(keyId) {
    const u = usageForKey(keyId);
    const series = u?.tokens_per_day || [];
    return {
        datasets: [{
            label: 'Tokens / day',
            data: series.map(p => ({ x: p.date, y: p.count })),
            borderColor: '#3B82F6',
            backgroundColor: 'rgba(59, 130, 246, 0.12)',
            fill: true,
            tension: 0.25,
            pointRadius: 2
        }]
    };
}


onMounted(() => {
    if (isAnyServiceEnabled.value && dataStore.apiKeys.length === 0) {
        try{
            dataStore.fetchApiKeys();
        }
        catch{
            console.log("couldn't fetch api key (this is expected if the service is not enabled by the admin)")
        }
    }
    fetchKeyUsage();
});

watch(isAnyServiceEnabled, (newValue) => {
    if (newValue && dataStore.apiKeys.length === 0) {
        try{
            dataStore.fetchApiKeys();
        }
        catch{
            console.log("couldn't fetch api key (this is expected if the service is not enabled by the admin)")
        }
        fetchKeyUsage();
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
            
            <div class="p-4 sm:p-6">
                <div class="space-y-4 mb-6">
                    <div class="p-4 border rounded-lg dark:border-gray-700">
                        <h3 class="font-semibold text-lg mb-2">API Service Status</h3>
                        <div v-if="user" class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                            <!-- OpenAI Status -->
                            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-md">
                                <p class="font-medium text-gray-800 dark:text-gray-200">OpenAI-Compatible API</p>
                                <p :class="user.openai_api_service_enabled ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'">
                                    Status: {{ user.openai_api_service_enabled ? 'Enabled' : 'Disabled' }}
                                </p>
                                <p class="text-gray-500 dark:text-gray-400">
                                    Key Required: {{ user.openai_api_require_key ? 'Yes' : 'No' }}
                                </p>
                            </div>
                            <!-- Ollama Status -->
                            <div class="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-md">
                                <p class="font-medium text-gray-800 dark:text-gray-200">Ollama-Compatible API</p>
                                <p :class="user.ollama_service_enabled ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'">
                                    Status: {{ user.ollama_service_enabled ? 'Enabled' : 'Disabled' }}
                                </p>
                                <p class="text-gray-500 dark:text-gray-400">
                                    Key Required: {{ user.ollama_require_key ? 'Yes' : 'No' }}
                                </p>
                            </div>
                        </div>
                        <p class="text-xs text-gray-500 mt-2">API keys below can be used for any enabled service that requires a key.</p>
                    </div>
                </div>

                <div v-if="!isAnyServiceEnabled" class="text-center">
                    <div class="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800/50 rounded-lg">
                        <p class="text-sm text-yellow-800 dark:text-yellow-200">
                            All API services are currently disabled by the administrator.
                        </p>
                    </div>
                </div>

                <div v-else>
                    <!-- Create Key Form -->
                    <form @submit.prevent="handleCreateKey" class="flex flex-col sm:flex-row items-start sm:items-end gap-4">
                        <div class="grow w-full">
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
            </div>
            
            <div v-if="isAnyServiceEnabled">
                <!-- Keys Usage Header -->
                <div class="px-4 sm:px-6 py-3 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between flex-wrap gap-2">
                    <h3 class="text-sm font-bold text-gray-700 dark:text-gray-300">Key Usage</h3>
                    <div class="flex items-center gap-2">
                        <div class="flex items-center gap-1 bg-gray-100 dark:bg-gray-900/60 p-1 rounded-lg text-xs font-bold">
                            <button @click="usageRangeDays = 7; fetchKeyUsage();" class="px-2 py-1 rounded transition-all" :class="usageRangeDays === 7 ? 'bg-white dark:bg-gray-700 text-purple-600 shadow-xs' : 'text-gray-500'">7D</button>
                            <button @click="usageRangeDays = 30; fetchKeyUsage();" class="px-2 py-1 rounded transition-all" :class="usageRangeDays === 30 ? 'bg-white dark:bg-gray-700 text-purple-600 shadow-xs' : 'text-gray-500'">30D</button>
                            <button @click="usageRangeDays = 90; fetchKeyUsage();" class="px-2 py-1 rounded transition-all" :class="usageRangeDays === 90 ? 'bg-white dark:bg-gray-700 text-purple-600 shadow-xs' : 'text-gray-500'">90D</button>
                        </div>
                    </div>
                </div>
                <!-- Keys List -->
                <div>
                    <div v-if="!hasKeys" class="p-6 text-center text-gray-500 dark:text-gray-400">
                        You have not created any API keys yet.
                    </div>
                    <div v-else>
                        <!-- Contextual Actions Header -->
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
                                class="px-4 py-4 sm:px-6 group transition-colors duration-150"
                                :class="{ 'bg-blue-50 dark:bg-blue-900/40': selectedKeys.has(key.id) }"
                            >
                                <div class="flex items-center gap-4">
                                    <input
                                        type="checkbox"
                                        :value="key.id"
                                        v-model="selectedKeys"
                                        @click.stop
                                        class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                                    >
                                    <div class="grow ml-2">
                                        <p class="text-sm font-semibold text-gray-900 dark:text-white">{{ key.alias }}</p>
                                        <p class="text-sm text-gray-500 dark:text-gray-400 font-mono">{{ key.key_prefix }}<span>...</span></p>
                                        <div v-if="usageFor(key.id)" class="mt-2 text-xs text-gray-500 dark:text-gray-400 flex items-center gap-3 flex-wrap">
                                            <span>Tokens: <span class="font-mono font-semibold text-purple-600 dark:text-purple-400">{{ (usageFor(key.id)?.total_tokens || 0).toLocaleString() }}</span></span>
                                            <span>Requests: <span class="font-mono">{{ (usageFor(key.id)?.requests || 0).toLocaleString() }}</span></span>
                                        </div>
                                    </div>
                                    <div class="text-xs text-gray-500 dark:text-gray-400 text-right">
                                        <p>Last used: {{ formatUsageDate(key.last_used_at) }}</p>
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
                                </div>
                                <div v-if="usageFor(key.id) && (usageFor(key.id)?.tokens_per_day || []).length" class="mt-3 h-32 pl-8">
                                    <Line :data="keyChartData(key.id)" :options="keyChartOptions" />
                                </div>
                                <div v-else-if="isLoadingKeyUsage" class="mt-3 h-32 pl-8 flex items-center justify-center">
                                    <IconAnimateSpin class="w-5 h-5 text-purple-500 animate-spin" />
                                </div>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
