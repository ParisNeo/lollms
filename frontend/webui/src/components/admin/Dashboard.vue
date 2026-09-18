<script setup>
import { computed, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { Doughnut } from 'vue-chartjs';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';

ChartJS.register(ArcElement, Tooltip, Legend);

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

const sourceRatioChartData = computed(() => {
    const sb = globalGenerationStats.value?.source_breakdown;
    const webui = sb?.webui_tokens || 0;
    const api = sb?.api_tokens || 0;

    return {
        labels: ['WebUI Chat', 'API Endpoints'],
        datasets: [{
            data: [webui, api],
            backgroundColor: ['#3B82F6', '#8B5CF6'],
            hoverBackgroundColor: ['#2563EB', '#7C3AED'],
            borderWidth: 0
        }]
    };
});

const sourceRatioChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '70%',
    plugins: {
        legend: { display: false },
        tooltip: {
            callbacks: {
                label: function(context) {
                    const label = context.label || '';
                    const val = context.raw || 0;
                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                    const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                    return ` ${label}: ${val.toLocaleString()} tokens (${pct}%)`;
                }
            }
        }
    }
};
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

        <!-- ── GLOBAL USAGE & ENVIRONMENTAL TELEMETRY ── -->
        <div class="space-y-6">
            <!-- Environmental Footprint & Global Consumption Banner -->
            <div class="p-6 bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/20 rounded-3xl border border-emerald-200/80 dark:border-emerald-800/60 shadow-sm space-y-4">
                <div class="flex items-center justify-between flex-wrap gap-4 border-b border-emerald-200/60 dark:border-emerald-800/40 pb-4">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-2xl bg-emerald-500 text-white flex items-center justify-center shadow-lg shadow-emerald-500/30">
                            <span class="text-xl">🌱</span>
                        </div>
                        <div>
                            <h3 class="text-base font-black text-gray-900 dark:text-white tracking-tight">Global Energy & Carbon Footprint Telemetry</h3>
                            <p class="text-xs text-gray-500 dark:text-gray-400">Estimated computation power, total token throughput, and environmental impact.</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2 font-mono text-xs">
                        <span class="px-3 py-1 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 font-bold border border-emerald-300 dark:border-emerald-700">
                            {{ (globalGenerationStats?.total_tokens || 0).toLocaleString() }} Total Sum Tokens
                        </span>
                    </div>
                </div>

                <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <div class="p-4 bg-white/80 dark:bg-gray-850/80 rounded-2xl border border-emerald-100 dark:border-emerald-800/40">
                        <span class="text-[10px] font-black uppercase text-gray-400 tracking-wider">Total Energy</span>
                        <p class="text-xl font-black font-mono text-emerald-600 dark:text-emerald-400 mt-1">
                            {{ globalGenerationStats?.total_energy_kwh ?? 0 }} <span class="text-xs font-normal text-gray-500">kWh</span>
                        </p>
                        <p class="text-[10px] text-gray-400 mt-0.5">GPU Compute draw</p>
                    </div>

                    <div class="p-4 bg-white/80 dark:bg-gray-850/80 rounded-2xl border border-emerald-100 dark:border-emerald-800/40">
                        <span class="text-[10px] font-black uppercase text-gray-400 tracking-wider">Estimated CO2</span>
                        <p class="text-xl font-black font-mono text-teal-600 dark:text-teal-400 mt-1">
                            {{ (globalGenerationStats?.total_co2_g || 0) > 1000 ? ((globalGenerationStats?.total_co2_g || 0)/1000).toFixed(2) + ' kg' : (globalGenerationStats?.total_co2_g || 0) + ' g' }}
                        </p>
                        <p class="text-[10px] text-gray-400 mt-0.5">Carbon emissions</p>
                    </div>

                    <div class="p-4 bg-white/80 dark:bg-gray-850/80 rounded-2xl border border-emerald-100 dark:border-emerald-800/40">
                        <span class="text-[10px] font-black uppercase text-gray-400 tracking-wider">Car Travel Equivalent</span>
                        <p class="text-xl font-black font-mono text-indigo-600 dark:text-indigo-400 mt-1">
                            {{ globalGenerationStats?.co2_equivalents?.car_km ?? 0 }} <span class="text-xs font-normal text-gray-500">km</span>
                        </p>
                        <p class="text-[10px] text-gray-400 mt-0.5">Average petrol car</p>
                    </div>

                    <div class="p-4 bg-white/80 dark:bg-gray-850/80 rounded-2xl border border-emerald-100 dark:border-emerald-800/40">
                        <span class="text-[10px] font-black uppercase text-gray-400 tracking-wider">Phone Charges</span>
                        <p class="text-xl font-black font-mono text-purple-600 dark:text-purple-400 mt-1">
                            {{ globalGenerationStats?.co2_equivalents?.smartphone_charges ?? 0 }} <span class="text-xs font-normal text-gray-500">charges</span>
                        </p>
                        <p class="text-[10px] text-gray-400 mt-0.5">Smartphone cycles</p>
                    </div>
                </div>
            </div>

            <!-- ── CONSUMPTION BREAKDOWN: WEBUI VS API RATIO (CIRCLE GRAPH) ── -->
            <div class="p-6 bg-white dark:bg-gray-800 rounded-3xl border border-gray-200/80 dark:border-gray-700/80 shadow-sm space-y-6">
                <div class="flex items-center justify-between flex-wrap gap-4 border-b dark:border-gray-700/80 pb-4">
                    <div>
                        <h3 class="text-base font-black text-gray-900 dark:text-white tracking-tight flex items-center gap-2">
                            <span>📊</span>
                            <span>Consumption Breakdown: WebUI vs. API</span>
                        </h3>
                        <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Compare token volumes, request counts, and load ratio between web users and external API clients.</p>
                    </div>

                    <!-- Sum Pill -->
                    <div class="flex items-center gap-2">
                        <div class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gray-100 dark:bg-gray-700/50 border dark:border-gray-600 font-mono text-xs">
                            <span class="text-gray-400 font-bold uppercase text-[9px]">Sum Total:</span>
                            <span class="font-black text-gray-900 dark:text-white">{{ (globalGenerationStats?.source_breakdown?.total_tokens || globalGenerationStats?.total_tokens || 0).toLocaleString() }} Tokens</span>
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
                    <!-- Circle Graph (Doughnut) -->
                    <div class="h-56 relative flex items-center justify-center">
                        <Doughnut :data="sourceRatioChartData" :options="sourceRatioChartOptions" />
                        <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                            <span class="text-[9px] font-black uppercase text-gray-400 tracking-widest">Share Ratio</span>
                            <span class="text-sm font-black font-mono text-gray-800 dark:text-gray-100">
                                {{ globalGenerationStats?.source_breakdown?.webui_ratio || 0 }}% / {{ globalGenerationStats?.source_breakdown?.api_ratio || 0 }}%
                            </span>
                        </div>
                    </div>

                    <!-- Metrics Columns -->
                    <div class="md:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <!-- WebUI Card -->
                        <div class="p-5 rounded-2xl bg-blue-50/60 dark:bg-blue-950/20 border border-blue-200/80 dark:border-blue-800/60 space-y-2">
                            <div class="flex items-center justify-between">
                                <span class="flex items-center gap-2 font-bold text-xs text-blue-900 dark:text-blue-300">
                                    <span class="w-3 h-3 rounded-full bg-blue-500"></span>
                                    WebUI Chat
                                </span>
                                <span class="text-xs font-mono font-black text-blue-600 dark:text-blue-400">
                                    {{ globalGenerationStats?.source_breakdown?.webui_ratio || 0 }}%
                                </span>
                            </div>
                            <p class="text-2xl font-black font-mono text-blue-950 dark:text-blue-100">
                                {{ (globalGenerationStats?.source_breakdown?.webui_tokens || 0).toLocaleString() }} <span class="text-xs font-normal text-blue-500">tokens</span>
                            </p>
                            <div class="pt-2 border-t border-blue-100 dark:border-blue-900/40 text-[10px] text-blue-700 dark:text-blue-400 flex justify-between font-mono">
                                <span>{{ (globalGenerationStats?.source_breakdown?.webui_requests || 0).toLocaleString() }} Requests</span>
                                <span>{{ globalGenerationStats?.source_breakdown?.webui_energy_kwh || 0 }} kWh</span>
                            </div>
                        </div>

                        <!-- API Card -->
                        <div class="p-5 rounded-2xl bg-purple-50/60 dark:bg-purple-950/20 border border-purple-200/80 dark:border-purple-800/60 space-y-2">
                            <div class="flex items-center justify-between">
                                <span class="flex items-center gap-2 font-bold text-xs text-purple-900 dark:text-purple-300">
                                    <span class="w-3 h-3 rounded-full bg-purple-500"></span>
                                    API Services
                                </span>
                                <span class="text-xs font-mono font-black text-purple-600 dark:text-purple-400">
                                    {{ globalGenerationStats?.source_breakdown?.api_ratio || 0 }}%
                                </span>
                            </div>
                            <p class="text-2xl font-black font-mono text-purple-950 dark:text-purple-100">
                                {{ (globalGenerationStats?.source_breakdown?.api_tokens || 0).toLocaleString() }} <span class="text-xs font-normal text-purple-500">tokens</span>
                            </p>
                            <div class="pt-2 border-t border-purple-100 dark:border-purple-900/40 text-[10px] text-purple-700 dark:text-purple-400 flex justify-between font-mono">
                                <span>{{ (globalGenerationStats?.source_breakdown?.api_requests || 0).toLocaleString() }} Requests</span>
                                <span>{{ globalGenerationStats?.source_breakdown?.api_energy_kwh || 0 }} kWh</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

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