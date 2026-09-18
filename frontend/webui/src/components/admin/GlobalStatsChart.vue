<script setup>
import { ref, computed } from 'vue';
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
const chartMode = ref('time_series'); // 'time_series', 'weekday_mean', 'weekday_variance', 'weekly_stats'
const chartRef = ref(null);

// Interactive multi-curve visibility toggles
const selectedCurves = ref({
    total_tokens: true,
    webui_tokens: true,
    api_tokens: true,
    requests: false
});

function selectOnlyCurve(key) {
    Object.keys(selectedCurves.value).forEach(k => {
        selectedCurves.value[k] = (k === key);
    });
}

function selectAllCurves() {
    Object.keys(selectedCurves.value).forEach(k => {
        selectedCurves.value[k] = true;
    });
}

const isTimeScale = computed(() => chartMode.value === 'time_series');

const chartComponent = computed(() => {
    return (isTimeScale.value || chartMode.value === 'weekly_stats') ? Line : Bar;
});

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: 'index',
    intersect: false,
  },
  plugins: {
    legend: { 
        display: true,
        labels: {
            color: uiStore.currentTheme === 'dark' ? '#cbd5e1' : '#4b5563',
            font: { weight: 'bold', size: 11 },
            boxWidth: 12,
            usePointStyle: true
        }
    },
    title: { 
        display: true, 
        text: chartTitle.value, 
        color: uiStore.currentTheme === 'dark' ? '#e5e7eb' : '#1f2937',
        font: { size: 13, weight: 'bold' }
    },
    tooltip: {
        backgroundColor: uiStore.currentTheme === 'dark' ? 'rgba(17, 24, 39, 0.95)' : 'rgba(255, 255, 255, 0.95)',
        titleColor: uiStore.currentTheme === 'dark' ? '#f3f4f6' : '#111827',
        bodyColor: uiStore.currentTheme === 'dark' ? '#e5e7eb' : '#374151',
        borderColor: uiStore.currentTheme === 'dark' ? '#374151' : '#e5e7eb',
        borderWidth: 1,
        padding: 10,
        callbacks: {
            label: function(context) {
                let label = context.dataset.label || '';
                if (label) label += ': ';
                if (context.parsed.y !== null) {
                    label += context.parsed.y.toLocaleString();
                }
                return label;
            }
        }
    }
  },
  scales: {
    x: {
      type: isTimeScale.value ? 'time' : 'category',
      time: { unit: 'day', tooltipFormat: 'MMM d, yyyy' },
      grid: { color: uiStore.currentTheme === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)' },
      ticks: { color: uiStore.currentTheme === 'dark' ? '#cbd5e1' : '#4b5563' }
    },
    y: {
      type: 'linear',
      display: true,
      position: 'left',
      beginAtZero: true,
      grid: { color: uiStore.currentTheme === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)' },
      ticks: { 
          color: uiStore.currentTheme === 'dark' ? '#cbd5e1' : '#4b5563',
          callback: function(value) {
              if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
              if (value >= 1000) return (value / 1000).toFixed(0) + 'k';
              return value;
          }
      }
    },
    y1: {
      type: 'linear',
      display: isTimeScale.value && selectedCurves.value.requests,
      position: 'right',
      beginAtZero: true,
      grid: { drawOnChartArea: false },
      ticks: { color: '#f59e0b', precision: 0 }
    }
  }
}));

const chartTitle = computed(() => {
    switch (chartMode.value) {
        case 'time_series': return 'Daily Consumption & Generation Throughput (Last 30 Days)';
        case 'weekday_mean': return 'Average Daily Activity by Weekday';
        case 'weekday_variance': return 'Activity Variance by Weekday';
        case 'weekly_stats': return 'Weekly Distribution Statistics (Mean ± Std Dev)';
        default: return 'Global Usage Telemetry';
    }
});

const chartData = computed(() => {
    if (!props.stats) return { labels: [], datasets: [] };

    const weekdayOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

    if (chartMode.value === 'time_series') {
        const datasets = [];

        // 1. Total Tokens (Sum)
        if (selectedCurves.value.total_tokens) {
            const dataArr = props.stats.tokens_per_day || [];
            datasets.push({
                label: 'Total Tokens (Sum)',
                data: dataArr.map(s => ({ x: s.date, y: s.count })),
                borderColor: '#10B981',
                backgroundColor: 'rgba(16, 185, 129, 0.15)',
                borderWidth: 2.5,
                tension: 0.2,
                fill: true,
                pointRadius: 3,
                yAxisID: 'y'
            });
        }

        // 2. WebUI Tokens
        if (selectedCurves.value.webui_tokens) {
            const dataArr = props.stats.webui_tokens_per_day || [];
            datasets.push({
                label: 'WebUI Tokens',
                data: dataArr.map(s => ({ x: s.date, y: s.count })),
                borderColor: '#3B82F6',
                backgroundColor: 'rgba(59, 130, 246, 0.12)',
                borderWidth: 2,
                tension: 0.2,
                fill: false,
                pointRadius: 3,
                yAxisID: 'y'
            });
        }

        // 3. API Tokens
        if (selectedCurves.value.api_tokens) {
            const dataArr = props.stats.api_tokens_per_day || [];
            datasets.push({
                label: 'API Tokens',
                data: dataArr.map(s => ({ x: s.date, y: s.count })),
                borderColor: '#8B5CF6',
                backgroundColor: 'rgba(139, 92, 246, 0.12)',
                borderWidth: 2,
                tension: 0.2,
                fill: false,
                pointRadius: 3,
                yAxisID: 'y'
            });
        }

        // 4. Requests Count
        if (selectedCurves.value.requests) {
            const dataArr = props.stats.generations_per_day || [];
            datasets.push({
                label: 'Requests Count',
                data: dataArr.map(s => ({ x: s.date, y: s.count })),
                borderColor: '#F59E0B',
                backgroundColor: 'rgba(245, 158, 11, 0.15)',
                borderWidth: 2,
                borderDash: [5, 5],
                tension: 0.2,
                fill: false,
                pointRadius: 3,
                yAxisID: 'y1'
            });
        }

        const allDates = [
            ...(props.stats.tokens_per_day || []).map(s => s.date),
            ...(props.stats.generations_per_day || []).map(s => s.date)
        ];
        const uniqueDates = Array.from(new Set(allDates)).sort();

        return {
            labels: uniqueDates,
            datasets
        };
    }
    if (chartMode.value === 'weekday_mean') {
        return {
            labels: weekdayOrder,
            datasets: [{
                label: 'Mean Generations',
                data: weekdayOrder.map(day => props.stats.mean_per_weekday[day]),
                backgroundColor: '#10b981',
                borderRadius: 6
            }]
        };
    }
    if (chartMode.value === 'weekday_variance') {
        return {
            labels: weekdayOrder,
            datasets: [{
                label: 'Variance',
                data: weekdayOrder.map(day => props.stats.variance_per_weekday[day]),
                backgroundColor: '#f59e0b',
                borderRadius: 6
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
        <div class="bg-white dark:bg-gray-800 rounded-3xl shadow-sm border border-gray-100 dark:border-gray-700/80 p-6">
            <!-- Header Mode Switcher & Export -->
            <div class="flex justify-between items-center mb-4 flex-wrap gap-3 border-b dark:border-gray-700/80 pb-4">
                <div class="inline-flex rounded-xl shadow-xs bg-gray-100 dark:bg-gray-900/50 p-1 border dark:border-gray-700 text-xs font-bold" role="group">
                    <button @click="chartMode = 'time_series'" type="button" class="px-3.5 py-1.5 rounded-lg transition-all" :class="chartMode === 'time_series' ? 'bg-white dark:bg-gray-700 text-emerald-600 dark:text-emerald-400 shadow-xs' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'">Daily Activity (Multi-Curve)</button>
                    <button @click="chartMode = 'weekly_stats'" type="button" class="px-3.5 py-1.5 rounded-lg transition-all" :class="chartMode === 'weekly_stats' ? 'bg-white dark:bg-gray-700 text-purple-600 dark:text-purple-400 shadow-xs' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'">Weekly Stats</button>
                    <button @click="chartMode = 'weekday_mean'" type="button" class="px-3.5 py-1.5 rounded-lg transition-all" :class="chartMode === 'weekday_mean' ? 'bg-white dark:bg-gray-700 text-teal-600 dark:text-teal-400 shadow-xs' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'">Weekday Mean</button>
                    <button @click="chartMode = 'weekday_variance'" type="button" class="px-3.5 py-1.5 rounded-lg transition-all" :class="chartMode === 'weekday_variance' ? 'bg-white dark:bg-gray-700 text-amber-600 dark:text-amber-400 shadow-xs' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'">Variance</button>
                </div>

                <div class="flex items-center gap-2">
                    <button @click="exportChartImage" class="btn btn-secondary btn-xs flex items-center gap-1 shadow-xs" title="Export current visible curves as PNG screenshot">
                        <IconArrowDownTray class="w-3.5 h-3.5 text-blue-500" />
                        <span>Screenshot PNG</span>
                    </button>
                    <button @click="exportChartCSV" class="btn btn-secondary btn-xs flex items-center gap-1" title="Export as CSV">
                        <IconArrowDownTray class="w-3.5 h-3.5" />
                        <span>CSV</span>
                    </button>
                </div>
            </div>

            <!-- Curve Selection Bar (Interactive Checkboxes / Presets) -->
            <div v-if="chartMode === 'time_series'" class="flex items-center justify-between flex-wrap gap-3 mb-4 p-3 bg-gray-50/80 dark:bg-gray-900/40 rounded-2xl border dark:border-gray-700/60 text-xs">
                <div class="flex items-center gap-4 flex-wrap select-none">
                    <span class="text-[10px] font-black uppercase tracking-wider text-gray-400">Select Curves:</span>

                    <label class="flex items-center gap-1.5 cursor-pointer font-bold text-emerald-700 dark:text-emerald-400">
                        <input type="checkbox" v-model="selectedCurves.total_tokens" class="rounded text-emerald-600 focus:ring-emerald-500 w-3.5 h-3.5">
                        <span>Total Tokens (Sum)</span>
                    </label>

                    <label class="flex items-center gap-1.5 cursor-pointer font-bold text-blue-700 dark:text-blue-400">
                        <input type="checkbox" v-model="selectedCurves.webui_tokens" class="rounded text-blue-600 focus:ring-blue-500 w-3.5 h-3.5">
                        <span>WebUI Chat Tokens</span>
                    </label>

                    <label class="flex items-center gap-1.5 cursor-pointer font-bold text-purple-700 dark:text-purple-400">
                        <input type="checkbox" v-model="selectedCurves.api_tokens" class="rounded text-purple-600 focus:ring-purple-500 w-3.5 h-3.5">
                        <span>API Services Tokens</span>
                    </label>

                    <label class="flex items-center gap-1.5 cursor-pointer font-bold text-amber-700 dark:text-amber-400">
                        <input type="checkbox" v-model="selectedCurves.requests" class="rounded text-amber-600 focus:ring-amber-500 w-3.5 h-3.5">
                        <span>Requests Count</span>
                    </label>
                </div>

                <div class="flex items-center gap-1.5">
                    <button @click="selectAllCurves" class="text-[10px] font-bold text-gray-500 hover:text-blue-600 underline">Show All</button>
                    <span class="text-gray-300 dark:text-gray-700">|</span>
                    <button @click="selectOnlyCurve('webui_tokens')" class="text-[10px] font-bold text-blue-500 hover:underline">WebUI Only</button>
                    <span class="text-gray-300 dark:text-gray-700">|</span>
                    <button @click="selectOnlyCurve('api_tokens')" class="text-[10px] font-bold text-purple-500 hover:underline">API Only</button>
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
@reference "tailwindcss";
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