<!-- [UPDATE] frontend/webui/src/components/admin/ServicesManagement.vue -->
<script setup>
import { onMounted, computed, ref, watch } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const { serviceStats, isLoadingServiceStats, globalSettings } = storeToRefs(adminStore);

const form = ref({});
const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

onMounted(() => {
    fetchData();
});

async function fetchData() {
    await adminStore.fetchServiceDashboard();
    if (serviceStats.value) {
        form.value = { ...serviceStats.value.settings };
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
    }
}

async function handleSave() {
    isLoading.value = true;
    try {
        await adminStore.updateGlobalSettings(form.value);
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
        // Refresh usage data after saving settings
        await adminStore.fetchServiceDashboard();
    } finally {
        isLoading.value = false;
    }
}

function handleToggle(key) {
    form.value[key] = !form.value[key];
    hasChanges.value = true;
}

const serviceNames = {
    openai: 'OpenAI V1 API',
    ollama: 'Ollama V1 API',
    lollms: 'LoLLMs Exclusive Services'
};

const serviceIcons = {
    openai: 'https://openai.com/favicon.ico',
    ollama: 'https://ollama.com/favicon.ico',
    lollms: '/favicon.ico'
};

// Map usage stats keys to the actual settings keys in the database
const statusSettingMap = {
    openai: 'openai_api_service_enabled',
    ollama: 'ollama_service_enabled',
    lollms: 'lollms_services_enabled'
};

async function handleResetUsage() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Reset Usage Stats?',
        message: 'This will clear all in-memory service hit counters. This action is permanent.',
        confirmText: 'Reset'
    });
    if (confirmed) {
        await adminStore.resetServiceUsage();
    }
}
</script>

<template>
    <div class="space-y-8 animate-fade-in">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
                <h2 class="text-2xl font-bold text-gray-900 dark:text-white">API Services Dashboard</h2>
                <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    Manage OpenAI/Ollama compatibility layers and exclusive LoLLMs endpoints.
                </p>
            </div>
            <div class="flex gap-2">
                <button @click="fetchData" class="btn btn-secondary btn-sm" :disabled="isLoadingServiceStats">
                    <IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isLoadingServiceStats}"/> Refresh
                </button>
                <button @click="handleResetUsage" class="btn btn-danger btn-sm">
                    <IconTrash class="w-4 h-4 mr-2" /> Reset Usage
                </button>
            </div>
        </div>

        <!-- Usage Overview Cards -->
        <div v-if="serviceStats" class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div v-for="(stats, service) in serviceStats.usage" :key="service" 
                 class="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 flex flex-col justify-between group">
                <div>
                    <div class="flex items-center gap-3 mb-4">
                        <div class="w-10 h-10 rounded-lg bg-gray-100 dark:bg-gray-700 p-2 flex items-center justify-center">
                            <img :src="serviceIcons[service]" class="w-full h-full object-contain grayscale opacity-70 group-hover:grayscale-0 transition-all" @error="($event.target.src='/favicon.ico')" />
                        </div>
                        <h4 class="font-bold text-lg text-gray-900 dark:text-white truncate">{{ serviceNames[service] || service }}</h4>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div class="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
                            <p class="text-[10px] uppercase font-black text-gray-400 tracking-wider">Total Requests</p>
                            <p class="text-xl font-mono font-bold text-blue-600 dark:text-blue-400">{{ stats.total_hits.toLocaleString() }}</p>
                        </div>
                        <div class="p-3 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
                            <p class="text-[10px] uppercase font-black text-gray-400 tracking-wider">Active Users</p>
                            <p class="text-xl font-mono font-bold text-purple-600 dark:text-purple-400">{{ stats.user_count.toLocaleString() }}</p>
                        </div>
                    </div>
                </div>
                
                <div class="mt-6 pt-4 border-t dark:border-gray-700 flex items-center justify-between">
                    <span class="text-xs font-medium text-gray-500">Status</span>
                    <!-- Corrected status detection using mapping -->
                    <span v-if="serviceStats.settings[statusSettingMap[service]]" class="px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-[10px] font-bold uppercase tracking-tighter border border-green-200">Enabled</span>
                    <span v-else class="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-[10px] font-bold uppercase tracking-tighter border border-red-200">Disabled</span>
                </div>
            </div>
        </div>

        <!-- Detailed Configuration -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-md border dark:border-gray-700 overflow-hidden">
            <div class="p-6 border-b dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/20">
                <h4 class="text-lg font-bold">Interface & Security Controls</h4>
                <p class="text-sm text-gray-500">Enable interfaces and manage authentication requirements.</p>
            </div>
            
            <div class="p-6 space-y-8">
                <!-- Individual Interface Blocks -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <!-- OpenAI Block -->
                    <div class="p-5 border dark:border-gray-700 rounded-2xl bg-white dark:bg-gray-800/50 space-y-6">
                        <div class="flex items-center justify-between">
                            <h5 class="font-black uppercase text-xs tracking-widest text-gray-400">OPENAI API</h5>
                            <button @click="handleToggle('openai_api_service_enabled')" type="button" 
                                    :class="[form['openai_api_service_enabled'] ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch']">
                                <span :class="[form['openai_api_service_enabled'] ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                            </button>
                        </div>
                        <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-xl space-y-4 border dark:border-gray-700">
                             <div class="flex items-center justify-between">
                                <span class="text-sm font-medium text-gray-700 dark:text-gray-300">Require API Key</span>
                                <button @click="handleToggle('openai_api_require_key')" type="button" 
                                        :class="[form['openai_api_require_key'] ? 'bg-indigo-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch-sm']">
                                    <span :class="[form['openai_api_require_key'] ? 'translate-x-4' : 'translate-x-0', 'toggle-knob-sm']"></span>
                                </button>
                            </div>
                            <p class="text-[10px] text-gray-500 leading-tight">If disabled, anonymous requests will be handled by the primary administrator account.</p>
                        </div>
                    </div>

                    <!-- Ollama Block -->
                    <div class="p-5 border dark:border-gray-700 rounded-2xl bg-white dark:bg-gray-800/50 space-y-6">
                        <div class="flex items-center justify-between">
                            <h5 class="font-black uppercase text-xs tracking-widest text-gray-400">OLLAMA</h5>
                            <button @click="handleToggle('ollama_service_enabled')" type="button" 
                                    :class="[form['ollama_service_enabled'] ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch']">
                                <span :class="[form['ollama_service_enabled'] ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                            </button>
                        </div>
                        <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-xl space-y-4 border dark:border-gray-700">
                             <div class="flex items-center justify-between">
                                <span class="text-sm font-medium text-gray-700 dark:text-gray-300">Require API Key</span>
                                <button @click="handleToggle('ollama_require_key')" type="button" 
                                        :class="[form['ollama_require_key'] ? 'bg-indigo-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch-sm']">
                                    <span :class="[form['ollama_require_key'] ? 'translate-x-4' : 'translate-x-0', 'toggle-knob-sm']"></span>
                                </button>
                            </div>
                            <p class="text-[10px] text-gray-500 leading-tight">If disabled, anonymous requests will be handled by the primary administrator account.</p>
                        </div>
                    </div>

                    <!-- LoLLMs Block -->
                    <div class="p-5 border dark:border-gray-700 rounded-2xl bg-white dark:bg-gray-800/50 space-y-6">
                        <div class="flex items-center justify-between">
                            <h5 class="font-black uppercase text-xs tracking-widest text-gray-400">LOLLMS SERVICES</h5>
                            <button @click="handleToggle('lollms_services_enabled')" type="button" 
                                    :class="[form['lollms_services_enabled'] ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch']">
                                <span :class="[form['lollms_services_enabled'] ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                            </button>
                        </div>
                        <div class="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-xl space-y-4 border dark:border-gray-700">
                             <div class="flex items-center justify-between">
                                <span class="text-sm font-medium text-gray-700 dark:text-gray-300">Require API Key</span>
                                <button @click="handleToggle('lollms_services_require_key')" type="button" 
                                        :class="[form['lollms_services_require_key'] ? 'bg-indigo-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch-sm']">
                                    <span :class="[form['lollms_services_require_key'] ? 'translate-x-4' : 'translate-x-0', 'toggle-knob-sm']"></span>
                                </button>
                            </div>
                            <p class="text-[10px] text-gray-500 leading-tight">If disabled, anonymous requests will be handled by the primary administrator account.</p>
                        </div>
                    </div>
                </div>

                <!-- Global Rate Limiting -->
                <div class="pt-8 border-t dark:border-gray-700">
                    <div class="flex items-center justify-between mb-6">
                        <div>
                            <h4 class="text-lg font-bold text-orange-600 dark:text-orange-400">Global Rate Limiting</h4>
                            <p class="text-sm text-gray-500 dark:text-gray-400">Apply traffic control across all external API interfaces.</p>
                        </div>
                        <button @click="handleToggle('rate_limit_enabled')" type="button" 
                                :class="[form.rate_limit_enabled ? 'bg-orange-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch']">
                            <span :class="[form.rate_limit_enabled ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                        </button>
                    </div>
                    
                    <transition
                        enter-active-class="transition duration-200 ease-out"
                        enter-from-class="transform scale-95 opacity-0"
                        enter-to-class="transform scale-100 opacity-100"
                        leave-active-class="transition duration-150 ease-in"
                        leave-from-class="transform scale-100 opacity-100"
                        leave-to-class="transform scale-95 opacity-0"
                    >
                        <div v-if="form.rate_limit_enabled" class="grid grid-cols-1 md:grid-cols-2 gap-8 p-6 bg-orange-50 dark:bg-orange-900/10 rounded-2xl border border-orange-100 dark:border-orange-900/30">
                            <div>
                                <label class="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">Max Requests</label>
                                <input type="number" v-model.number="form.rate_limit_max_requests" @input="hasChanges = true" class="input-field w-full" placeholder="e.g. 60">
                                <p class="text-[10px] text-gray-500 mt-2 italic">Threshold of requests allowed per user/key within the window.</p>
                            </div>
                            <div>
                                <label class="block text-sm font-bold text-gray-700 dark:text-gray-300 mb-2">Window Size (Seconds)</label>
                                <input type="number" v-model.number="form.rate_limit_window_seconds" @input="hasChanges = true" class="input-field w-full" placeholder="e.g. 60">
                                <p class="text-[10px] text-gray-500 mt-2 italic">The timeframe in seconds for the request count bucket.</p>
                            </div>
                        </div>
                    </transition>
                </div>
            </div>

            <!-- Save Bar -->
            <div class="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 border-t dark:border-gray-700 flex justify-between items-center">
                <span v-if="hasChanges" class="text-xs font-bold text-orange-500 animate-pulse">● Unsaved changes detected</span>
                <span v-else class="text-xs text-gray-400">All settings synchronized</span>
                
                <button @click="handleSave" class="btn btn-primary min-w-[140px]" :disabled="!hasChanges || isLoading">
                    <IconAnimateSpin v-if="isLoading" class="w-5 h-5 mr-2 animate-spin" />
                    {{ isLoading ? 'Saving...' : 'Save Settings' }}
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.toggle-switch { @apply relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out; }
.toggle-knob { @apply pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out; }

.toggle-switch-sm { @apply relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out; }
.toggle-knob-sm { @apply pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out; }

.animate-fade-in { animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
</style>
