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
            label: 'Users Assigned',
            backgroundColor: '#3B82F6',
            borderRadius: 6,
            data
        }]
    };
});

const chartOptions = {
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
        y: {
            beginAtZero: true,
            grid: { color: '#374151' },
            ticks: { stepSize: 1, color: '#9CA3AF' }
        },
        x: {
            grid: { display: false },
            ticks: { color: '#9CA3AF' }
        }
    }
};
</script>

<template>
    <div class="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm border border-gray-100 dark:border-gray-700 h-96 flex flex-col">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">Default Model Distribution</h3>
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
