<script setup>
import { computed, onMounted } from 'vue';
import { Bar } from 'vue-chartjs';
import { useAdminStore } from '../../stores/admin';
import { storeToRefs } from 'pinia';
import { Chart as ChartJS, Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale } from 'chart.js';

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

const adminStore = useAdminStore();
const { modelUsageStats, isLoadingModelUsageStats } = storeToRefs(adminStore);

onMounted(() => {
    adminStore.fetchModelUsageStats();
});

const chartData = computed(() => {
    const stats = Array.isArray(modelUsageStats.value) ? modelUsageStats.value : [];
    const labels = stats.map(s => s.model_name);
    const tokensData = stats.map(s => s.total_tokens || s.count);

    return {
        labels,
        datasets: [{
            label: 'Total Tokens Consumed',
            backgroundColor: '#8B5CF6',
            hoverBackgroundColor: '#7C3AED',
            borderRadius: 6,
            data: tokensData,
            barPercentage: 0.6,
            categoryPercentage: 0.8
        }]
    };
});

const chartOptions = {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false },
        tooltip: {
            mode: 'index',
            intersect: false,
            callbacks: {
                label: function(context) {
                    const val = context.raw || 0;
                    return ` Tokens: ${val.toLocaleString()}`;
                }
            }
        }
    },
    scales: {
        x: {
            beginAtZero: true,
            grid: { color: 'rgba(156, 163, 175, 0.12)' },
            ticks: { 
                color: '#9CA3AF',
                maxTicksLimit: 6,
                callback: function(value) {
                    if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
                    if (value >= 1000) return (value / 1000).toFixed(0) + 'k';
                    return value;
                }
            }
        },
        y: {
            grid: { display: false },
            ticks: { 
                color: '#9CA3AF',
                autoSkip: false,
                callback: function(value) {
                    const label = this.getLabelForValue(value);
                    if (label.length > 30) {
                        return label.substr(0, 30) + '...';
                    }
                    return label;
                }
            }
        }
    }
};
</script>

<template>
    <div class="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 h-96 flex flex-col">
        <!-- Updated Title to reflect actual data source -->
        <div class="flex items-center justify-between mb-2">
            <div>
                <h3 class="text-lg font-black text-gray-900 dark:text-white">
                    Model Computation & Token Share
                </h3>
                <p class="text-xs text-gray-500 dark:text-gray-400">
                    Volume of tokens generated and energy share across active AI models.
                </p>
            </div>
        </div>

        <div class="grow relative">
            <div v-if="isLoadingModelUsageStats" class="absolute inset-0 flex items-center justify-center">
                <p class="text-gray-500">Loading stats...</p>
            </div>
            <div v-else-if="!modelUsageStats || modelUsageStats.length === 0" class="absolute inset-0 flex items-center justify-center">
                <p class="text-gray-500">No data available.</p>
            </div>
            <Bar v-else :data="chartData" :options="chartOptions" />
        </div>
    </div>
</template>
