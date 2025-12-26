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
    const data = stats.map(s => s.count);
    
    return {
        labels,
        datasets: [{
            label: 'Users',
            backgroundColor: '#3B82F6',
            borderRadius: 4,
            data,
            barPercentage: 0.6,
            categoryPercentage: 0.8
        }]
    };
});

const chartOptions = {
    indexAxis: 'y', // Switch to Horizontal Bar Chart
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false },
        tooltip: {
            mode: 'index',
            intersect: false,
        }
    },
    scales: {
        x: { // Value axis (Horizontal)
            beginAtZero: true,
            grid: { color: '#374151' },
            ticks: { 
                stepSize: 1, 
                color: '#9CA3AF',
                precision: 0 
            }
        },
        y: { // Label axis (Vertical)
            grid: { display: false },
            ticks: { 
                color: '#9CA3AF',
                autoSkip: false,
                callback: function(value) {
                    // Truncate long model names to keep the chart clean
                    const label = this.getLabelForValue(value);
                    if (label.length > 35) {
                        return label.substr(0, 35) + '...';
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
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-1">
            User Default Model Preferences
        </h3>
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">
            Count of users currently assigned to each model.
        </p>

        <div class="flex-grow relative">
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
