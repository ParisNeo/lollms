<script setup>
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconKey from '../../assets/icons/IconKey.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

// Chart components for dashboard stats
import { Line, Doughnut, Bar } from 'vue-chartjs';
import {
  Chart as ChartJS, Title, Tooltip, Legend, LineElement, BarElement, ArcElement,
  CategoryScale, LinearScale, PointElement, TimeScale, Filler
} from 'chart.js';
import 'chartjs-adapter-date-fns';

ChartJS.register(Title, Tooltip, Legend, LineElement, BarElement, ArcElement, CategoryScale, LinearScale, PointElement, TimeScale, Filler);

const authStore = useAuthStore();
const dataStore = useDataStore();
const uiStore = useUiStore();

const user = computed(() => authStore.user);

// ── Usage Stats State ──
const personalStats = ref(null);
const isLoadingStats = ref(false);
const statsRangeDays = ref(30);

// ── Per-API-Key Usage State ──
const keyUsage = ref([]);
const isLoadingKeyUsage = ref(false);

// Interactive curve toggles for personal chart
const dashboardCurves = ref({
    total: true,
    webui: true,
    api: true
});

const currentTheme = computed(() => uiStore.currentTheme);

async function fetchPersonalStats() {
    isLoadingStats.value = true;
    try {
        const res = await apiClient.get('/api/users/me/stats', {
            params: { days: statsRangeDays.value }
        });
        personalStats.value = res.data;
    } catch (e) {
        console.error("Failed to load dashboard stats:", e);
    } finally {
        isLoadingStats.value = false;
    }
}

async function fetchKeyUsage() {
    isLoadingKeyUsage.value = true;
    try {
        const res = await apiClient.get('/api/users/me/api-keys/usage', {
            params: { days: statsRangeDays.value }
        });
        keyUsage.value = res.data?.keys || [];
    } catch (e) {
        // Endpoint may not exist yet in some deployments — fail soft.
        console.warn("Could not load per-key usage:", e);
        keyUsage.value = [];
    } finally {
        isLoadingKeyUsage.value = false;
    }
}

function refreshAll() {
    fetchPersonalStats();
    fetchKeyUsage();
}

onMounted(() => {
    refreshAll();
    // Best-effort: ensure api keys list is populated for naming/labels.
    if (authStore.isAdmin || dataStore.apiKeys.length === 0) {
        dataStore.fetchApiKeys?.().catch(() => {});
    }
});

// ── Daily tokens chart ──
const dailyChartData = computed(() => {
    if (!personalStats.value) return { labels: [], datasets: [] };
    const datasets = [];

    const allDates = [
        ...(personalStats.value.tokens_per_day || []).map(t => t.date),
        ...(personalStats.value.messages_per_day || []).map(t => t.date)
    ];
    const uniqueDates = Array.from(new Set(allDates)).sort();
    const dateSet = new Set(uniqueDates);

    if (dashboardCurves.value.total) {
        const tokens = personalStats.value.tokens_per_day || [];
        datasets.push({
            label: 'Total Tokens',
            data: uniqueDates.map(d => ({ x: d, y: tokens.find(t => t.date === d)?.count ?? 0 })),
            borderColor: '#10B981',
            backgroundColor: 'rgba(16, 185, 129, 0.12)',
            fill: true,
            tension: 0.2,
            pointRadius: 3
        });
    }
    if (dashboardCurves.value.webui) {
        const webuiToks = personalStats.value.webui_tokens_per_day || [];
        datasets.push({
            label: 'WebUI Tokens',
            data: uniqueDates.map(d => ({ x: d, y: webuiToks.find(t => t.date === d)?.count ?? 0 })),
            borderColor: '#3B82F6',
            fill: false,
            tension: 0.2,
            pointRadius: 3
        });
    }
    if (dashboardCurves.value.api) {
        const apiToks = personalStats.value.api_tokens_per_day || [];
        datasets.push({
            label: 'API Tokens',
            data: uniqueDates.map(d => ({ x: d, y: apiToks.find(t => t.date === d)?.count ?? 0 })),
            borderColor: '#8B5CF6',
            fill: false,
            tension: 0.2,
            pointRadius: 3
        });
    }
    return { labels: uniqueDates, datasets };
});

const dailyChartOptions = computed(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false },
        tooltip: { mode: 'index', intersect: false }
    },
    scales: {
        x: {
            type: 'time',
            time: { unit: 'day', tooltipFormat: 'MMM d, yyyy' },
            grid: { color: currentTheme.value === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)' },
            ticks: { color: currentTheme.value === 'dark' ? '#cbd5e1' : '#4b5563' }
        },
        y: {
            beginAtZero: true,
            grid: { color: currentTheme.value === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)' },
            ticks: { color: currentTheme.value === 'dark' ? '#cbd5e1' : '#4b5563' }
        }
    }
}));

// ── Source breakdown doughnut ──
const sourceDoughnutData = computed(() => {
    const sb = personalStats.value?.source_breakdown;
    return {
        labels: ['WebUI Chat', 'API Tokens'],
        datasets: [{
            data: [sb?.webui_tokens || 0, sb?.api_tokens || 0],
            backgroundColor: ['#3B82F6', '#8B5CF6'],
            borderWidth: 0
        }]
    };
});

const sourceDoughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '70%',
    plugins: {
        legend: { display: false },
        tooltip: {
            callbacks: {
                label: function (context) {
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

// ── Per-model usage bar ──
const modelUsageData = computed(() => {
    const models = personalStats.value?.models || [];
    return {
        labels: models.map(m => m.model_name || 'unknown'),
        datasets: [{
            label: 'Tokens Consumed',
            data: models.map(m => m.total_tokens || 0),
            backgroundColor: '#6366F1',
            borderRadius: 6
        }]
    };
});

const modelUsageOptions = computed(() => ({
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: {
        legend: { display: false },
        tooltip: {
            callbacks: {
                label: (ctx) => `${(ctx.raw || 0).toLocaleString()} tokens`
            }
        }
    },
    scales: {
        x: {
            beginAtZero: true,
            grid: { color: currentTheme.value === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)' },
            ticks: { color: currentTheme.value === 'dark' ? '#cbd5e1' : '#4b5563' }
        },
        y: {
            grid: { display: false },
            ticks: { color: currentTheme.value === 'dark' ? '#cbd5e1' : '#4b5563' }
        }
    }
}));

const hasModels = computed(() => (personalStats.value?.models || []).length > 0);

// ── Rate-limit / token-quota state ──
const rateLimit = computed(() => personalStats.value?.rate_limit || null);
const tokenQuota = computed(() => {
    const q = personalStats.value?.token_quota;
    if (!q || !q.limit) return null;
    const used = q.used || 0;
    const remaining = Math.max(0, q.limit - used);
    return {
        limit: q.limit,
        used,
        remaining,
        pct: q.limit > 0 ? Math.min(100, (used / q.limit) * 100) : 0,
        resetAt: q.reset_at || null
    };
});

// ── Per-key aggregated chart data ──
const combinedKeyChartData = computed(() => {
    if (!keyUsage.value.length) return { labels: [], datasets: [] };
    const palette = ['#3B82F6', '#8B5CF6', '#EC4899', '#F59E0B', '#10B981', '#EF4444', '#06B6D4', '#84CC16'];
    const allDates = Array.from(new Set(
        keyUsage.value.flatMap(k => (k.tokens_per_day || []).map(t => t.date))
    )).sort();
    const datasets = keyUsage.value.map((k, idx) => {
        const map = new Map((k.tokens_per_day || []).map(t => [t.date, t.count]));
        return {
            label: k.alias || `key-${k.id}`,
            data: allDates.map(d => map.get(d) ?? 0),
            borderColor: palette[idx % palette.length],
            backgroundColor: 'transparent',
            fill: false,
            tension: 0.2,
            pointRadius: 2
        };
    });
    return { labels: allDates, datasets };
});

const combinedKeyChartOptions = computed(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
        legend: { position: 'bottom', labels: { color: currentTheme.value === 'dark' ? '#cbd5e1' : '#4b5563', boxWidth: 10, font: { size: 10 } } },
        tooltip: { mode: 'index', intersect: false }
    },
    scales: {
        x: {
            grid: { color: currentTheme.value === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)' },
            ticks: { color: currentTheme.value === 'dark' ? '#cbd5e1' : '#4b5563', maxRotation: 0, autoSkip: true }
        },
        y: {
            beginAtZero: true,
            grid: { color: currentTheme.value === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)' },
            ticks: { color: currentTheme.value === 'dark' ? '#cbd5e1' : '#4b5563' }
        }
    }
}));

function formatNumber(n) {
    return (n || 0).toLocaleString();
}

function formatDate(d) {
    if (!d) return '—';
    return new Date(d).toLocaleString();
}

// ── Export to HTML / PDF ──
function buildStatsHtml() {
    const s = personalStats.value || {};
    const sb = s.source_breakdown || {};
    const quota = tokenQuota.value;
    const rl = rateLimit.value;
    const rows = (s.models || []).map(m => `
        <tr>
            <td>${escapeHtml(m.model_name || 'unknown')}</td>
            <td style="text-align:right">${formatNumber(m.total_tokens)}</td>
            <td style="text-align:right">${formatNumber(m.prompt_tokens)}</td>
            <td style="text-align:right">${formatNumber(m.completion_tokens)}</td>
        </tr>`).join('');

    const keyRows = (keyUsage.value || []).map(k => `
        <tr>
            <td>${escapeHtml(k.alias || ('key-' + k.id))}</td>
            <td style="text-align:right">${formatNumber(k.total_tokens)}</td>
            <td style="text-align:right">${formatNumber(k.requests)}</td>
        </tr>`).join('');

    return `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Usage Report</title>
<style>
  body{font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:#111827;padding:32px;max-width:960px;margin:0 auto;}
  h1{font-size:22px;margin:0 0 4px;}
  h2{font-size:15px;text-transform:uppercase;letter-spacing:.05em;color:#6b7280;margin:24px 0 8px;border-bottom:1px solid #e5e7eb;padding-bottom:6px;}
  .sub{color:#6b7280;font-size:13px;margin-bottom:24px;}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th,td{padding:8px 10px;border-bottom:1px solid #f3f4f6;text-align:left;}
  th{color:#6b7280;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em;}
  .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:12px 0 4px;}
  .card{background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:14px;}
  .card .label{font-size:10px;text-transform:uppercase;color:#6b7280;letter-spacing:.05em;font-weight:700;}
  .card .value{font-size:20px;font-weight:800;margin-top:4px;}
  .card .hint{font-size:11px;color:#9ca3af;margin-top:2px;}
  .progress{height:10px;background:#e5e7eb;border-radius:6px;overflow:hidden;margin-top:6px;}
  .progress > div{height:100%;background:#8b5cf6;}
  .footer{margin-top:32px;font-size:11px;color:#9ca3af;text-align:center;}
</style></head>
<body>
  <h1>Personal AI Usage Report</h1>
  <div class="sub">User: ${escapeHtml(user.value?.username || 'N/A')} &middot; Period: last ${statsRangeDays.value} days &middot; Generated ${new Date().toLocaleString()}</div>

  <h2>Summary</h2>
  <div class="grid">
    <div class="card"><div class="label">Total Tokens</div><div class="value">${formatNumber(s.total_tokens)}</div><div class="hint">${formatNumber(s.total_prompt_tokens)} in / ${formatNumber(s.total_completion_tokens)} out</div></div>
    <div class="card"><div class="label">Energy Used</div><div class="value">${s.total_energy_kwh ?? 0} kWh</div><div class="hint">GPU compute</div></div>
    <div class="card"><div class="label">Estimated CO2</div><div class="value">${s.total_co2_g ?? 0} g</div><div class="hint">~${s.co2_equivalents?.car_km ?? 0} km in car</div></div>
    <div class="card"><div class="label">Phone Charges</div><div class="value">${s.co2_equivalents?.smartphone_charges ?? 0}</div><div class="hint">equivalent</div></div>
  </div>

  ${quota ? `<h2>Token Quota</h2>
    <div class="card">
      <div class="label">Used ${formatNumber(quota.used)} / ${formatNumber(quota.limit)} tokens</div>
      <div class="progress"><div style="width:${quota.pct.toFixed(1)}%"></div></div>
      <div class="hint">${formatNumber(quota.remaining)} remaining${quota.resetAt ? ' · resets ' + formatDate(quota.resetAt) : ''}</div>
    </div>` : ''}

  ${rl ? `<h2>Rate Limiting</h2>
    <div class="card">
      <div class="label">${rl.limit ? escapeHtml(String(rl.limit)) + ' / ' + escapeHtml(String(rl.window_seconds || 60)) + 's' : 'Unlimited'}</div>
      <div class="hint">${rl.remaining !== undefined ? formatNumber(rl.remaining) + ' remaining in current window' : ''}${rl.reset_at ? ' · resets ' + formatDate(rl.reset_at) : ''}</div>
    </div>` : ''}

  <h2>Consumption Channels</h2>
  <table>
    <thead><tr><th>Channel</th><th style="text-align:right">Tokens</th><th style="text-align:right">Requests</th><th style="text-align:right">Ratio</th></tr></thead>
    <tbody>
      <tr><td>WebUI Chat</td><td style="text-align:right">${formatNumber(sb.webui_tokens)}</td><td style="text-align:right">${formatNumber(sb.webui_requests)}</td><td style="text-align:right">${sb.webui_ratio ?? 0}%</td></tr>
      <tr><td>API Tokens</td><td style="text-align:right">${formatNumber(sb.api_tokens)}</td><td style="text-align:right">${formatNumber(sb.api_requests)}</td><td style="text-align:right">${sb.api_ratio ?? 0}%</td></tr>
    </tbody>
  </table>

  ${rows ? `<h2>Usage by Model</h2>
    <table>
      <thead><tr><th>Model</th><th style="text-align:right">Total</th><th style="text-align:right">Prompt</th><th style="text-align:right">Completion</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>` : ''}

  ${keyRows ? `<h2>Usage by API Key</h2>
    <table>
      <thead><tr><th>Key Alias</th><th style="text-align:right">Tokens</th><th style="text-align:right">Requests</th></tr></thead>
      <tbody>${keyRows}</tbody>
    </table>` : ''}

  <div class="footer">Generated by LoLLMs · AI for the people</div>
</body></html>`;
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function exportAsHtml() {
    const html = buildStatsHtml();
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lollms-usage-${user.value?.username || 'report'}-${new Date().toISOString().slice(0, 10)}.html`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    uiStore.addNotification('HTML report exported.', 'success');
}

function exportAsPdf() {
    const html = buildStatsHtml();
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
        uiStore.addNotification('Please allow pop-ups to export PDF.', 'warning');
        return;
    }
    printWindow.document.open();
    printWindow.document.write(html);
    printWindow.document.close();
    // Defer print so charts/styles are laid out.
    printWindow.onload = () => {
        printWindow.focus();
        printWindow.print();
    };
    // Fallback in case onload already fired.
    setTimeout(() => {
        try { printWindow.focus(); printWindow.print(); } catch (e) { /* noop */ }
    }, 300);
}
</script>

<template>
<div class="space-y-8">
    <!-- Header + range selector + export -->
    <div class="flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-3">
            <div class="w-11 h-11 rounded-2xl bg-purple-50 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 flex items-center justify-center">
                <IconSparkles class="w-6 h-6" />
            </div>
            <div>
                <h1 class="text-2xl font-black text-gray-900 dark:text-white">Dashboard</h1>
                <p class="text-xs text-gray-500 dark:text-gray-400">Your AI consumption, quotas and footprint at a glance.</p>
            </div>
        </div>

        <div class="flex items-center gap-2 flex-wrap">
            <div class="flex items-center gap-1 bg-gray-100 dark:bg-gray-900/60 p-1 rounded-xl text-xs font-bold">
                <button @click="statsRangeDays = 7; refreshAll();" class="px-3 py-1 rounded-lg transition-all" :class="statsRangeDays === 7 ? 'bg-white dark:bg-gray-700 text-purple-600 shadow-xs' : 'text-gray-500'">7D</button>
                <button @click="statsRangeDays = 30; refreshAll();" class="px-3 py-1 rounded-lg transition-all" :class="statsRangeDays === 30 ? 'bg-white dark:bg-gray-700 text-purple-600 shadow-xs' : 'text-gray-500'">30D</button>
                <button @click="statsRangeDays = 90; refreshAll();" class="px-3 py-1 rounded-lg transition-all" :class="statsRangeDays === 90 ? 'bg-white dark:bg-gray-700 text-purple-600 shadow-xs' : 'text-gray-500'">90D</button>
            </div>
            <button @click="exportAsHtml" class="btn btn-secondary btn-sm inline-flex items-center gap-1.5" :disabled="isLoadingStats">
                <IconArrowDownTray class="w-4 h-4" /> HTML
            </button>
            <button @click="exportAsPdf" class="btn btn-secondary btn-sm inline-flex items-center gap-1.5" :disabled="isLoadingStats">
                <IconArrowDownTray class="w-4 h-4" /> PDF
            </button>
        </div>
    </div>

    <!-- Loading -->
    <div v-if="isLoadingStats" class="flex items-center justify-center py-16">
        <IconAnimateSpin class="w-8 h-8 text-purple-500 animate-spin" />
    </div>

    <template v-else>
        <!-- Quota / rate-limit banners -->
        <div v-if="tokenQuota" class="bg-white dark:bg-gray-800 shadow-md rounded-2xl border border-gray-100 dark:border-gray-700/80 p-5">
            <div class="flex items-center justify-between flex-wrap gap-2">
                <div>
                    <h2 class="text-sm font-black uppercase tracking-wider text-gray-700 dark:text-gray-300">Token Quota</h2>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ formatNumber(tokenQuota.used) }} / {{ formatNumber(tokenQuota.limit) }} tokens used</p>
                </div>
                <span class="text-sm font-mono font-bold text-purple-600 dark:text-purple-400">{{ formatNumber(tokenQuota.remaining) }} remaining</span>
            </div>
            <div class="mt-3 h-2.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                <div class="h-full rounded-full transition-all"
                     :class="tokenQuota.pct >= 90 ? 'bg-red-500' : tokenQuota.pct >= 70 ? 'bg-amber-500' : 'bg-purple-500'"
                     :style="{ width: tokenQuota.pct.toFixed(1) + '%' }"></div>
            </div>
            <p v-if="tokenQuota.resetAt" class="text-[11px] text-gray-400 mt-1">Resets: {{ formatDate(tokenQuota.resetAt) }}</p>
        </div>

        <div v-if="rateLimit" class="bg-white dark:bg-gray-800 shadow-md rounded-2xl border border-gray-100 dark:border-gray-700/80 p-5">
            <h2 class="text-sm font-black uppercase tracking-wider text-gray-700 dark:text-gray-300">Rate Limiting</h2>
            <p class="text-sm text-gray-700 dark:text-gray-300 mt-1">
                <template v-if="rateLimit.limit">
                    {{ rateLimit.limit }} requests / {{ rateLimit.window_seconds || 60 }}s
                    <span class="text-xs text-gray-500"> · {{ formatNumber(rateLimit.remaining) }} remaining</span>
                </template>
                <template v-else>Unlimited</template>
            </p>
            <p v-if="rateLimit.reset_at" class="text-[11px] text-gray-400 mt-0.5">Resets: {{ formatDate(rateLimit.reset_at) }}</p>
        </div>

        <!-- Metric cards -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div class="p-4 bg-white dark:bg-gray-800 rounded-2xl border dark:border-gray-700">
                <span class="text-[10px] font-black uppercase text-gray-400 tracking-wider">Total Tokens</span>
                <p class="text-xl font-black font-mono text-purple-600 dark:text-purple-400 mt-1">{{ formatNumber(personalStats?.total_tokens) }}</p>
                <p class="text-[10px] text-gray-400 mt-0.5">{{ formatNumber(personalStats?.total_prompt_tokens) }} in / {{ formatNumber(personalStats?.total_completion_tokens) }} out</p>
            </div>
            <div class="p-4 bg-white dark:bg-gray-800 rounded-2xl border dark:border-gray-700">
                <span class="text-[10px] font-black uppercase text-gray-400 tracking-wider">Energy Used</span>
                <p class="text-xl font-black font-mono text-emerald-600 dark:text-emerald-400 mt-1">{{ personalStats?.total_energy_kwh ?? 0 }} <span class="text-xs font-normal text-gray-500">kWh</span></p>
                <p class="text-[10px] text-gray-400 mt-0.5">GPU compute draw</p>
            </div>
            <div class="p-4 bg-white dark:bg-gray-800 rounded-2xl border dark:border-gray-700">
                <span class="text-[10px] font-black uppercase text-gray-400 tracking-wider">Estimated CO2</span>
                <p class="text-xl font-black font-mono text-teal-600 dark:text-teal-400 mt-1">{{ personalStats?.total_co2_g ?? 0 }} <span class="text-xs font-normal text-gray-500">g</span></p>
                <p class="text-[10px] text-gray-400 mt-0.5">~{{ personalStats?.co2_equivalents?.car_km ?? 0 }} km in car</p>
            </div>
            <div class="p-4 bg-white dark:bg-gray-800 rounded-2xl border dark:border-gray-700">
                <span class="text-[10px] font-black uppercase text-gray-400 tracking-wider">Phone Charges</span>
                <p class="text-xl font-black font-mono text-blue-600 dark:text-blue-400 mt-1">{{ personalStats?.co2_equivalents?.smartphone_charges ?? 0 }}</p>
                <p class="text-[10px] text-gray-400 mt-0.5">Charge cycles</p>
            </div>
        </div>

        <!-- Daily tokens trend -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-2xl border border-gray-100 dark:border-gray-700/80 p-5 space-y-3">
            <div class="flex items-center justify-between flex-wrap gap-2 border-b dark:border-gray-700 pb-3">
                <h2 class="text-sm font-black uppercase tracking-wider text-gray-700 dark:text-gray-300">Activity & Tokens</h2>
                <div class="flex items-center gap-3 select-none text-xs">
                    <label class="flex items-center gap-1 font-bold text-emerald-600 dark:text-emerald-400 cursor-pointer">
                        <input type="checkbox" v-model="dashboardCurves.total" class="rounded text-emerald-600 w-3.5 h-3.5"> <span>Total</span>
                    </label>
                    <label class="flex items-center gap-1 font-bold text-blue-600 dark:text-blue-400 cursor-pointer">
                        <input type="checkbox" v-model="dashboardCurves.webui" class="rounded text-blue-600 w-3.5 h-3.5"> <span>WebUI</span>
                    </label>
                    <label class="flex items-center gap-1 font-bold text-purple-600 dark:text-purple-400 cursor-pointer">
                        <input type="checkbox" v-model="dashboardCurves.api" class="rounded text-purple-600 w-3.5 h-3.5"> <span>API</span>
                    </label>
                </div>
            </div>
            <div class="h-64">
                <div v-if="!personalStats || !(personalStats.tokens_per_day || []).length" class="h-full flex items-center justify-center text-center border-2 border-dashed rounded-2xl border-gray-200 dark:border-gray-700">
                    <p class="text-xs text-gray-400">No token activity recorded in the selected time range.</p>
                </div>
                <Line v-else :data="dailyChartData" :options="dailyChartOptions" />
            </div>
        </div>

        <!-- Source breakdown + per-model usage -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div class="bg-white dark:bg-gray-800 shadow-md rounded-2xl border border-gray-100 dark:border-gray-700/80 p-5">
                <h2 class="text-sm font-black uppercase tracking-wider text-gray-700 dark:text-gray-300 border-b dark:border-gray-700 pb-3 mb-3">Consumption Channels</h2>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
                    <div class="h-40 relative flex items-center justify-center">
                        <Doughnut :data="sourceDoughnutData" :options="sourceDoughnutOptions" />
                        <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                            <span class="text-[8px] font-bold uppercase text-gray-400">Ratio</span>
                            <span class="text-xs font-bold font-mono">{{ personalStats?.source_breakdown?.webui_ratio ?? 0 }}% / {{ personalStats?.source_breakdown?.api_ratio ?? 0 }}%</span>
                        </div>
                    </div>
                    <div class="space-y-2">
                        <div class="p-3 bg-gray-50 dark:bg-gray-900/40 rounded-xl border dark:border-gray-700">
                            <div class="flex items-center gap-1.5 text-xs font-bold text-blue-600">
                                <span class="w-2.5 h-2.5 rounded-full bg-blue-500"></span> WebUI Chat
                            </div>
                            <p class="text-base font-black font-mono mt-1">{{ formatNumber(personalStats?.source_breakdown?.webui_tokens) }}</p>
                            <p class="text-[10px] text-gray-400">{{ personalStats?.source_breakdown?.webui_requests ?? 0 }} messages</p>
                        </div>
                        <div class="p-3 bg-gray-50 dark:bg-gray-900/40 rounded-xl border dark:border-gray-700">
                            <div class="flex items-center gap-1.5 text-xs font-bold text-purple-600">
                                <span class="w-2.5 h-2.5 rounded-full bg-purple-500"></span> API Calls
                            </div>
                            <p class="text-base font-black font-mono mt-1">{{ formatNumber(personalStats?.source_breakdown?.api_tokens) }}</p>
                            <p class="text-[10px] text-gray-400">{{ personalStats?.source_breakdown?.api_requests ?? 0 }} requests</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="bg-white dark:bg-gray-800 shadow-md rounded-2xl border border-gray-100 dark:border-gray-700/80 p-5">
                <h2 class="text-sm font-black uppercase tracking-wider text-gray-700 dark:text-gray-300 border-b dark:border-gray-700 pb-3 mb-3">Model Usage</h2>
                <div class="h-64">
                    <div v-if="!hasModels" class="h-full flex items-center justify-center text-center border-2 border-dashed rounded-2xl border-gray-200 dark:border-gray-700">
                        <p class="text-xs text-gray-400">No model usage recorded yet.</p>
                    </div>
                    <Bar v-else :data="modelUsageData" :options="modelUsageOptions" />
                </div>
            </div>
        </div>

        <!-- Per API key usage -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-2xl border border-gray-100 dark:border-gray-700/80 p-5 space-y-3">
            <div class="flex items-center gap-2 border-b dark:border-gray-700 pb-3">
                <IconKey class="w-4 h-4 text-amber-500" />
                <h2 class="text-sm font-black uppercase tracking-wider text-gray-700 dark:text-gray-300">Usage by API Key</h2>
            </div>
            <div v-if="isLoadingKeyUsage" class="flex items-center justify-center py-8">
                <IconAnimateSpin class="w-6 h-6 text-amber-500 animate-spin" />
            </div>
            <div v-else-if="!keyUsage.length" class="flex items-center justify-center py-6 text-center border-2 border-dashed rounded-2xl border-gray-200 dark:border-gray-700">
                <p class="text-xs text-gray-400">No API keys or no consumption recorded. Create keys in the API Keys section to track usage here.</p>
            </div>
            <div v-else class="space-y-4">
                <div class="h-56">
                    <Line :data="combinedKeyChartData" :options="combinedKeyChartOptions" />
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="text-[10px] uppercase text-gray-400 tracking-wider border-b dark:border-gray-700">
                                <th class="text-left py-2 font-bold">Key</th>
                                <th class="text-right py-2 font-bold">Tokens</th>
                                <th class="text-right py-2 font-bold">Requests</th>
                                <th class="text-right py-2 font-bold">Last Used</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-100 dark:divide-gray-700/60">
                            <tr v-for="k in keyUsage" :key="k.id">
                                <td class="py-2 font-medium text-gray-800 dark:text-gray-200">{{ k.alias || ('key-' + k.id) }}</td>
                                <td class="py-2 text-right font-mono">{{ formatNumber(k.total_tokens) }}</td>
                                <td class="py-2 text-right font-mono">{{ formatNumber(k.requests) }}</td>
                                <td class="py-2 text-right text-xs text-gray-500">{{ formatDate(k.last_used_at) }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </template>
</div>
</template>