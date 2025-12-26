<script setup>
import { ref, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';
import GlobalStatsChart from './GlobalStatsChart.vue';
import ModelUsageChart from './ModelUsageChart.vue';
import PendingUsersModal from '../modals/PendingUsersModal.vue';

import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconUserGroup from '../../assets/icons/IconUserGroup.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconLock from '../../assets/icons/IconLock.vue';
import IconLockOpen from '../../assets/icons/IconLockOpen.vue';

const stats = ref(null);
const isLoading = ref(true);
const uiStore = useUiStore();
const adminStore = useAdminStore();

const { serverInfo, globalGenerationStats, isLoadingGlobalGenerationStats } = storeToRefs(adminStore);

const pendingCount = computed(() => stats.value?.pending_approval || 0);

async function fetchDashboardData() {
    isLoading.value = true;
    try {
        await Promise.all([
            adminStore.fetchDashboardStats(),
            adminStore.fetchServerInfo(),
            adminStore.fetchGlobalGenerationStats(),
        ]);
        stats.value = adminStore.dashboardStats;
    } finally {
        isLoading.value = false;
    }
}

function openPendingModal() {
    // Check removed to allow opening even if count is 0 or loading
    uiStore.openModal('pendingUsers');
}

onMounted(fetchDashboardData);
</script>

<template>
    <div class="space-y-8 animate-fade-in p-2">
        <!-- Top Header -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
                <h2 class="text-2xl font-bold text-gray-900 dark:text-white">System Dashboard</h2>
                <div v-if="serverInfo" class="flex items-center gap-4 mt-1 text-sm text-gray-500 dark:text-gray-400">
                    <span class="flex items-center gap-1">
                        <span class="w-2 h-2 rounded-full" :class="serverInfo.https_enabled ? 'bg-green-500' : 'bg-yellow-500'"></span>
                        {{ serverInfo.url }}
                    </span>
                    <span v-if="serverInfo.https_enabled" class="flex items-center gap-1 text-green-600 dark:text-green-400"><IconLock class="w-3 h-3"/> HTTPS Active</span>
                    <span v-else class="flex items-center gap-1 text-yellow-600 dark:text-yellow-400"><IconLockOpen class="w-3 h-3"/> HTTP Only</span>
                </div>
            </div>
            <button @click="fetchDashboardData" class="btn btn-secondary btn-sm" :disabled="isLoading">
                <IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isLoading}" /> Refresh
            </button>
        </div>

        <!-- Metric Cards -->
        <div v-if="stats" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <div class="metric-card">
                <div><p class="metric-label">Total Users</p><p class="metric-value">{{ stats.total_users }}</p></div>
                <div class="metric-icon bg-blue-100 dark:bg-blue-900/30 text-blue-600"><IconUserGroup class="w-6 h-6"/></div>
            </div>
            
            <!-- Pending Users Card (Clickable) -->
            <div 
                class="metric-card cursor-pointer hover:ring-2 ring-orange-400 transition-all"
                @click="openPendingModal"
                title="Click to manage pending users"
            >
                <div><p class="metric-label">Pending Approval</p><p class="metric-value">{{ pendingCount }}</p></div>
                <div class="metric-icon bg-orange-100 dark:bg-orange-900/30 text-orange-600">
                    <IconUserGroup class="w-6 h-6"/>
                    <span v-if="pendingCount > 0" class="absolute top-0 right-0 -mt-1 -mr-1 flex h-3 w-3"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span><span class="relative inline-flex rounded-full h-3 w-3 bg-orange-500"></span></span>
                </div>
            </div>

            <div class="metric-card">
                <div><p class="metric-label">Active (24h)</p><p class="metric-value">{{ stats.active_users_24h }}</p></div>
                <div class="metric-icon bg-green-100 dark:bg-green-900/30 text-green-600"><IconCheckCircle class="w-6 h-6"/></div>
            </div>
             <div class="metric-card">
                <div><p class="metric-label">New (7d)</p><p class="metric-value">{{ stats.new_users_7d }}</p></div>
                <div class="metric-icon bg-purple-100 dark:bg-purple-900/30 text-purple-600"><IconUserGroup class="w-6 h-6"/></div>
            </div>
        </div>

        <!-- Charts Row -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GlobalStatsChart :stats="globalGenerationStats" :is-loading="isLoadingGlobalGenerationStats" />
            <ModelUsageChart />
        </div>
        
        <!-- Modals -->
        <PendingUsersModal v-if="uiStore.activeModal === 'pendingUsers'" />
    </div>
</template>

<style scoped>
.metric-card { @apply bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-100 dark:border-gray-700 flex items-center justify-between; }
.metric-label { @apply text-sm font-medium text-gray-500 dark:text-gray-400; }
.metric-value { @apply text-3xl font-bold text-gray-900 dark:text-white mt-1; }
.metric-icon { @apply p-3 rounded-full relative; }
.animate-fade-in { animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
</style>
