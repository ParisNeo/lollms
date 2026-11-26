<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { Bar } from 'vue-chartjs';
import {
    Chart as ChartJS,
    Title,
    Tooltip,
    Legend,
    BarElement,
    CategoryScale,
    LinearScale,
} from 'chart.js';
import { useAdminStore } from '../../stores/admin';

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

const adminStore = useAdminStore();
const { modelUsageStats, isLoadingModelUsageStats } = storeToRefs(adminStore);

// Reactive dark-mode flag. The admin panel is rendered inside the app shell,
// which toggles a `dark` class on <html> AFTER this component mounts. Reading
// colours once at mount therefore captured the light palette and painted
// dark-gray text on the dark card (the reported "unreadable" chart). We watch
// the <html> class/data-theme so chart text repaints with a legible colour
// whenever the theme is applied or toggled.
const isDarkTheme = ref(false);
let themeObserver = null;

function readIsDark() {
    if (typeof document === 'undefined') return false;
    const root = document.documentElement;
    if (root.classList.contains('dark')) return true;
    if (root.getAttribute('data-theme') === 'dark') return true;
    return typeof window !== 'undefined' &&
        typeof window.matchMedia === 'function' &&
        window.matchMedia('(prefers-color-scheme: dark)').matches;
}

onMounted(() => {
    isDarkTheme.value = readIsDark();
    adminStore.fetchModelUsageStats();

    if (typeof MutationObserver !== 'undefined') {
        themeObserver = new MutationObserver(() => {
            isDarkTheme.value = readIsDark();
        });
        themeObserver.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['class', 'data-theme'],
        });
    }
});

onBeforeUnmount(() => {
    if (themeObserver) {
        themeObserver.disconnect();
        themeObserver = null;
    }
});

// Normalize whatever the backend returns into a predictable array of rows.
const rows = computed(() => {
    const raw = modelUsageStats.value;
    if (!Array.isArray(raw)) return [];
    return raw
        .filter((item) => item && typeof item === 'object')
        .map((item) => ({
            model: item.model_name || item.model || item.name || 'unknown',
            count: Number(item.count) || 0,
            totalTokens: Number(item.total_tokens) || 0,
            promptTokens: Number(item.prompt_tokens) || 0,
            completionTokens: Number(item.completion_tokens) || 0,
            percentage: Number(item.percentage) || 0,
        }))
        .sort((a, b) => (b.totalTokens || b.count) - (a.totalTokens || a.count));
});

const hasTokenData = computed(() => rows.value.some((r) => r.totalTokens > 0));

const labels = computed(() => rows.value.map((r) => r.model));

// Text/axis colours keyed off the reactive theme flag so the chart is always
// legible on the gray-800 dark card and the white light card.
const axisColor = computed(() => (isDarkTheme.value ? '#E5E7EB' : '#374151'));
const gridColor = computed(() =>
    isDarkTheme.value ? 'rgba(156, 163, 175, 0.2)' : 'rgba(107, 114, 128, 0.15)'
);

const chartData = computed(() => {
    if (hasTokenData.value) {
        return {
            labels: labels.value,
            datasets: [
                {
                    label: 'Input tokens',
                    data: rows.value.map((r) => r.promptTokens),
                    backgroundColor: 'rgba(59, 130, 246, 0.85)',
                    borderRadius: 4,
                    stack: 'tokens',
                },
                {
                    label: 'Output tokens',
                    data: rows.value.map((r) => r.completionTokens),
                    backgroundColor: 'rgba(16, 185, 129, 0.85)',
                    borderRadius: 4,
                    stack: 'tokens',
                },
            ],
        };
    }
    // Fallback: no token telemetry yet — show request counts per model.
    return {
        labels: labels.value,
        datasets: [
            {
                label: 'Requests',
                data: rows.value.map((r) => r.count),
                backgroundColor: 'rgba(139, 92, 246, 0.85)',
                borderRadius: 4,
            },
        ],
    };
});

const chartOptions = computed(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            display: true,
            position: 'top',
            labels: {
                color: axisColor.value,
                font: { size: 11, weight: '600' },
                boxWidth: 12,
                padding: 12,
            },
        },
        tooltip: {
            callbacks: {
                label(context) {
                    const value = Number(context.raw) || 0;
                    return ` ${context.dataset.label}: ${value.toLocaleString()}`;
                },
            },
        },
    },
    scales: {
        x: {
            stacked: hasTokenData.value,
            ticks: { color: axisColor.value, font: { size: 10 } },
            grid: { color: gridColor.value },
        },
        y: {
            stacked: hasTokenData.value,
            beginAtZero: true,
            ticks: {
                color: axisColor.value,
                font: { size: 10 },
                callback(value) {
                    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
                    if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
                    return value;
                },
            },
            grid: { color: gridColor.value },
        },
    },
}));
</script>

<template>
    <div class="p-6 bg-white dark:bg-gray-800 rounded-3xl border border-gray-200/80 dark:border-gray-700/80 shadow-sm space-y-4">
        <div class="flex items-center justify-between flex-wrap gap-3 border-b border-gray-200/70 dark:border-gray-700/70 pb-4">
            <div>
                <h3 class="text-base font-black text-gray-900 dark:text-white tracking-tight flex items-center gap-2">
                    <span>🧮</span>
                    <span>Model Computation &amp; Token Usage</span>
                </h3>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    Token consumption and request volume distributed across every model profile{{ hasTokenData ? ' (input vs. output)' : '' }}.
                </p>
            </div>
        </div>

        <div v-if="isLoadingModelUsageStats" class="flex justify-center items-center h-48">
            <div class="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        </div>

        <div v-else-if="!rows.length" class="text-center py-12 text-sm italic text-gray-400 dark:text-gray-500 rounded-2xl border border-dashed border-gray-300 dark:border-gray-700">
            No model usage recorded yet.
        </div>

        <div v-else class="grid grid-cols-1 lg:grid-cols-5 gap-6">
            <div class="lg:col-span-3 h-72 relative">
                <Bar :data="chartData" :options="chartOptions" />
            </div>

            <div class="lg:col-span-2 space-y-1.5 max-h-72 overflow-y-auto pr-1">
                <div
                    v-for="(row, index) in rows"
                    :key="row.model + index"
                    class="flex items-center gap-3 p-2.5 rounded-xl bg-gray-50 dark:bg-gray-900/40 border border-gray-200/60 dark:border-gray-700/60"
                >
                    <span class="w-6 text-center font-black font-mono text-xs text-gray-400 shrink-0">{{ index + 1 }}</span>
                    <div class="flex-1 min-w-0">
                        <div class="text-xs font-bold text-gray-900 dark:text-white truncate">{{ row.model }}</div>
                        <div class="text-[10px] font-mono text-gray-500 dark:text-gray-400 truncate">
                            {{ (row.totalTokens || 0).toLocaleString() }} tokens
                            <span class="opacity-60">· {{ row.count.toLocaleString() }} calls</span>
                        </div>
                    </div>
                    <span class="text-sm font-black font-mono text-gray-900 dark:text-white shrink-0">
                        {{ row.percentage.toFixed(1) }}%
                    </span>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
</style>