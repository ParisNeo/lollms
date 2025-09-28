<script setup>
import { ref, computed, watch } from 'vue';
import { Bar, Line } from 'vue-chartjs';
import { Chart as ChartJS, Title, Tooltip, Legend, BarElement, LineElement, CategoryScale, LinearScale, PointElement, TimeScale, Filler } from 'chart.js';
import 'chartjs-adapter-date-fns';
import { useUiStore } from '../../stores/ui';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';

ChartJS.register(Title, Tooltip, Legend, BarElement, LineElement, CategoryScale, LinearScale, PointElement, TimeScale, Filler);

const props = defineProps({
  stats: {
    type: Object,
    default: null
  },
  isLoading: {
    type: Boolean,
    default: false
  }
});

const uiStore = useUiStore();
const chartMode = ref('daily'); // 'daily', 'mean', 'variance', 'weekly_stats'
const chartRef = ref(null); // Ref for the chart component instance

const chartComponent = computed(() => {
    return (chartMode.value === 'daily' || chartMode.value === 'weekly_stats') ? Line : Bar;
});

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: chartMode.value === 'daily' || chartMode.value === 'weekly_stats' },
    title: { display: true, text: chartTitle.value, color: uiStore.currentTheme === 'dark' ? '#e5e7eb' : '#1f2937' },
  },
  scales: {
    x: {
      type: chartMode.value === 'daily' ? 'time' : 'category',
      time: { unit: 'day', tooltipFormat: 'MMM d, yyyy' },
      grid: { color: uiStore.currentTheme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)' },
      ticks: { color: uiStore.currentTheme === 'dark' ? '#cbd5e1' : '#4b5563' }
    },
    y: {
      beginAtZero: true,
      grid: { color: uiStore.currentTheme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)' },
      ticks: { color: uiStore.currentTheme === 'dark' ? '#cbd5e1' : '#4b5563' }
    }
  }
}));

const chartTitle = computed(() => {
    switch (chartMode.value) {
        case 'mean': return 'Average Daily Generations by Weekday';
        case 'variance': return 'Generation Variance by Weekday';
        case 'weekly_stats': return 'Weekly Generation Statistics (Mean ± Std Dev)';
        case 'daily':
        default: return 'Total AI Generations (Last 30 Days)';
    }
});

const chartData = computed(() => {
    if (!props.stats) return { labels: [], datasets: [] };

    const weekdayOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

    if (chartMode.value === 'daily') {
        return {
            labels: props.stats.generations_per_day.map(s => s.date),
            datasets: [{
                label: 'Generations',
                data: props.stats.generations_per_day.map(s => s.count),
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.2)',
                tension: 0.1,
                fill: true
            }]
        };
    }
    if (chartMode.value === 'mean') {
        return {
            labels: weekdayOrder,
            datasets: [{
                label: 'Mean Generations',
                data: weekdayOrder.map(day => props.stats.mean_per_weekday[day]),
                backgroundColor: '#10b981'
            }]
        };
    }
    if (chartMode.value === 'variance') {
        return {
            labels: weekdayOrder,
            datasets: [{
                label: 'Variance',
                data: weekdayOrder.map(day => props.stats.variance_per_weekday[day]),
                backgroundColor: '#f59e0b'
            }]
        };
    }
     if (chartMode.value === 'weekly_stats') {
        const meanData = weekdayOrder.map(day => props.stats.mean_per_weekday[day]);
        const stdDevData = weekdayOrder.map(day => Math.sqrt(props.stats.variance_per_weekday[day]));
        
        const upperBoundData = meanData.map((mean, i) => mean + stdDevData[i]);
        const lowerBoundData = meanData.map((mean, i) => Math.max(0, mean - stdDevData[i]));

        return {
            labels: weekdayOrder,
            datasets: [
                {
                    label: 'Mean',
                    data: meanData,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.5)',
                    tension: 0.1,
                    pointRadius: 4,
                    pointBackgroundColor: '#3b82f6',
                },
                {
                    label: 'Std. Deviation Range',
                    data: upperBoundData,
                    borderColor: 'transparent',
                    backgroundColor: 'rgba(59, 130, 246, 0.15)',
                    pointRadius: 0,
                    fill: '+1', // Fill to the next dataset in the array (the lower bound)
                },
                {
                    label: 'Lower Bound', // Not shown in legend
                    data: lowerBoundData,
                    borderColor: 'transparent',
                    backgroundColor: 'transparent',
                    pointRadius: 0,
                    showInLegend: false,
                }
            ]
        };
    }
    return { labels: [], datasets: [] };
});

function exportChartImage() {
    if (chartRef.value && chartRef.value.chart) {
        const link = document.createElement('a');
        link.href = chartRef.value.chart.toBase64Image('image/png', 1);
        link.download = `lollms_global_stats_${chartMode.value}.png`;
        link.click();
    } else {
        uiStore.addNotification('Could not export chart image.', 'error');
    }
}

function exportChartCSV() {
    if (!props.stats) {
        uiStore.addNotification('No data to export.', 'warning');
        return;
    }

    let csvContent = "data:text/csv;charset=utf-8,";
    let rows = [];

    if (chartMode.value === 'daily') {
        rows.push(["date", "generation_count"]);
        props.stats.generations_per_day.forEach(stat => {
            rows.push([stat.date, stat.count]);
        });
    } else if (chartMode.value === 'weekly_stats') {
        rows.push(["weekday", "mean", "variance", "std_deviation"]);
        const weekdayOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
        weekdayOrder.forEach(day => {
            const mean = props.stats.mean_per_weekday[day];
            const variance = props.stats.variance_per_weekday[day];
            const std_dev = Math.sqrt(variance);
            rows.push([day, mean, variance, std_dev]);
        });
    } else {
        rows.push(["weekday", chartMode.value]);
        const data = chartMode.value === 'mean' ? props.stats.mean_per_weekday : props.stats.variance_per_weekday;
        Object.entries(data).forEach(([day, value]) => {
            rows.push([day, value]);
        });
    }

    csvContent += rows.map(e => e.join(",")).join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `lollms_global_stats_${chartMode.value}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
</script>

<template>
    <div class="space-y-6">
        <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
            Global Usage Statistics
        </h3>
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-5">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
                <div class="inline-flex rounded-md shadow-sm" role="group">
                    <button @click="chartMode = 'daily'" type="button" class="btn-group" :class="{'active': chartMode === 'daily'}">Daily</button>
                    <button @click="chartMode = 'weekly_stats'" type="button" class="btn-group" :class="{'active': chartMode === 'weekly_stats'}">Weekly Stats</button>
                    <button @click="chartMode = 'mean'" type="button" class="btn-group" :class="{'active': chartMode === 'mean'}">Mean</button>
                    <button @click="chartMode = 'variance'" type="button" class="btn-group" :class="{'active': chartMode === 'variance'}">Variance</button>
                </div>
                <div class="flex items-center gap-2">
                    <button @click="exportChartImage" class="btn btn-secondary btn-sm" title="Export as PNG">
                        <IconArrowDownTray class="w-4 h-4 mr-1" />
                        PNG
                    </button>
                    <button @click="exportChartCSV" class="btn btn-secondary btn-sm" title="Export as CSV">
                        <IconArrowDownTray class="w-4 h-4 mr-1" />
                        CSV
                    </button>
                </div>
            </div>
            <div class="h-96">
                <div v-if="isLoading" class="flex items-center justify-center h-full">
                    <p class="text-gray-500">Loading chart data...</p>
                </div>
                <div v-else-if="!stats" class="flex items-center justify-center h-full">
                    <p class="text-gray-500">Could not load statistics.</p>
                </div>
                <div v-else class="h-full">
                    <component :is="chartComponent" :data="chartData" :options="chartOptions" ref="chartRef"/>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.btn-group {
    @apply px-4 py-2 text-sm font-medium text-gray-900 bg-white border border-gray-200 hover:bg-gray-100 hover:text-blue-700 focus:z-10 focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:bg-gray-700 dark:border-gray-600 dark:text-white dark:hover:text-white dark:hover:bg-gray-600 dark:focus:ring-blue-500 dark:focus:text-white;
}
.btn-group:first-child {
    @apply rounded-l-lg;
}
.btn-group:last-child {
    @apply rounded-r-lg;
}
.btn-group.active {
    @apply bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300;
}
</style>