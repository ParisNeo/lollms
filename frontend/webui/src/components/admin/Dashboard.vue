<script setup>
import { computed, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';

// Analytics & Chart Components
import GlobalStatsChart from './GlobalStatsChart.vue';
import ModelUsageChart from './ModelUsageChart.vue';

// Icons
import IconUserGroup from '../../assets/icons/IconUserGroup.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconClock from '../../assets/icons/IconClock.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const emit = defineEmits(['navigate']);

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { 
    dashboardStats, 
    isLoadingDashboardStats,
    globalGenerationStats,
    isLoadingGlobalGenerationStats
} = storeToRefs(adminStore);

onMounted(() => {
    refreshAllDashboardData();
});

function refreshAllDashboardData() {
    adminStore.fetchDashboardStats();
    adminStore.fetchGlobalGenerationStats();
    adminStore.fetchModelUsageStats();
}

function openPendingModal() {
    uiStore.openModal('pendingUsers');
}

function navigateToUsers(statusFilter = null) {
    if (statusFilter === 'pending_admin_validation') {
        openPendingModal();
    } else {
        emit('navigate', { tab: 'user-table', filter: statusFilter });
    }
}
</script>

<template>
    <div class="space-y-6">
        <!-- Metric Cards Header Grid -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            
            <!-- 1. Total Registered Users -->
            <div 
                @click="navigateToUsers()"
                class="bg-white dark:bg-gray-800 p-5 rounded-2xl border border-gray-200/80 dark:border-gray-700/80 shadow-sm hover:shadow-md hover:border-blue-500/50 cursor-pointer transition-all flex items-center justify-between group"
            >
                <div class="space-y-1 min-w-0">
                    <span class="text-[10px] font-black uppercase tracking-widest text-gray-400 block">Total Accounts</span>
                    <div class="text-2xl font-black font-mono text-gray-900 dark:text-white">
                        <IconAnimateSpin v-if="isLoadingDashboardStats && !dashboardStats" class="w-6 h-6 animate-spin text-blue-500" />
                        <span v-else>{{ dashboardStats?.total_users ?? 0 }}</span>
                    </div>
                    <span class="text-[10px] text-gray-500 flex items-center gap-1">Registered members</span>
                </div>
                <div class="w-12 h-12 rounded-2xl bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
                    <IconUserGroup class="w-6 h-6" />
                </div>
            </div>

            <!-- 2. Active in Last 24h -->
            <div 
                @click="navigateToUsers()"
                class="bg-white dark:bg-gray-800 p-5 rounded-2xl border border-gray-200/80 dark:border-gray-700/80 shadow-sm hover:shadow-md hover:border-emerald-500/50 cursor-pointer transition-all flex items-center justify-between group"
            >
                <div class="space-y-1 min-w-0">
                    <span class="text-[10px] font-black uppercase tracking-widest text-gray-400 block">Active Users (24h)</span>
                    <div class="text-2xl font-black font-mono text-emerald-600 dark:text-emerald-400">
                        <IconAnimateSpin v-if="isLoadingDashboardStats && !dashboardStats" class="w-6 h-6 animate-spin text-emerald-500" />
                        <span v-else>{{ dashboardStats?.active_users_24h ?? 0 }}</span>
                    </div>
                    <span class="text-[10px] text-emerald-500 font-bold flex items-center gap-1">Online & interacting</span>
                </div>
                <div class="w-12 h-12 rounded-2xl bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
                    <IconCheckCircle class="w-6 h-6" />
                </div>
            </div>

            <!-- 3. New Registrations (7 Days) -->
            <div 
                @click="navigateToUsers()"
                class="bg-white dark:bg-gray-800 p-5 rounded-2xl border border-gray-200/80 dark:border-gray-700/80 shadow-sm hover:shadow-md hover:border-purple-500/50 cursor-pointer transition-all flex items-center justify-between group"
            >
                <div class="space-y-1 min-w-0">
                    <span class="text-[10px] font-black uppercase tracking-widest text-gray-400 block">New Users (7 Days)</span>
                    <div class="text-2xl font-black font-mono text-purple-600 dark:text-purple-400">
                        <IconAnimateSpin v-if="isLoadingDashboardStats && !dashboardStats" class="w-6 h-6 animate-spin text-purple-500" />
                        <span v-else>{{ dashboardStats?.new_users_7d ?? 0 }}</span>
                    </div>
                    <span class="text-[10px] text-gray-500 flex items-center gap-1">Recent sign-ups</span>
                </div>
                <div class="w-12 h-12 rounded-2xl bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
                    <IconPlus class="w-6 h-6" />
                </div>
            </div>

            <!-- 4. PENDING APPROVAL (Interactive Card) -->
            <div 
                @click="openPendingModal"
                class="p-5 rounded-2xl border transition-all cursor-pointer flex items-center justify-between group relative overflow-hidden"
                :class="[
                    (dashboardStats?.pending_approval || 0) > 0 
                        ? 'bg-amber-500/10 border-amber-400 dark:border-amber-600 text-amber-900 dark:text-amber-200 shadow-md ring-2 ring-amber-500/20 hover:bg-amber-500/20' 
                        : 'bg-white dark:bg-gray-800 border-gray-200/80 dark:border-gray-700/80 hover:border-gray-300 dark:hover:border-gray-600'
                ]"
            >
                <div class="space-y-1 min-w-0 z-10">
                    <span class="text-[10px] font-black uppercase tracking-widest block" :class="(dashboardStats?.pending_approval || 0) > 0 ? 'text-amber-700 dark:text-amber-300' : 'text-gray-400'">
                        Pending Approval
                    </span>
                    <div class="text-2xl font-black font-mono" :class="(dashboardStats?.pending_approval || 0) > 0 ? 'text-amber-600 dark:text-amber-400 animate-pulse' : 'text-gray-900 dark:text-white'">
                        <IconAnimateSpin v-if="isLoadingDashboardStats && !dashboardStats" class="w-6 h-6 animate-spin text-amber-500" />
                        <span v-else>{{ dashboardStats?.pending_approval ?? 0 }}</span>
                    </div>
                    <span class="text-[10px] font-bold flex items-center gap-1" :class="(dashboardStats?.pending_approval || 0) > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-gray-400'">
                        {{ (dashboardStats?.pending_approval || 0) > 0 ? 'Click to validate & activate' : 'All users validated' }}
                    </span>
                </div>
                <div class="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 z-10 group-hover:scale-110 transition-transform"
                     :class="(dashboardStats?.pending_approval || 0) > 0 ? 'bg-amber-500 text-white shadow-lg shadow-amber-500/30' : 'bg-gray-100 dark:bg-gray-700 text-gray-400'">
                    <IconClock class="w-6 h-6" />
                </div>
            </div>

        </div>

        <!-- ── GLOBAL USAGE & TELEMETRY STATISTICS CHARTS ── -->
        <div class="space-y-6">
            <!-- Global Generation Frequency Chart with Props -->
            <GlobalStatsChart 
                :stats="globalGenerationStats" 
                :is-loading="isLoadingGlobalGenerationStats" 
            />

            <!-- Model Usage & Token Distribution Chart -->
            <ModelUsageChart />
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
</style>