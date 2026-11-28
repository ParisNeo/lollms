
<script setup>
import { computed } from 'vue';
import { Bar, Doughnut } from 'vue-chartjs';
import {
  Chart as ChartJS, Title, Tooltip, Legend, BarElement, CategoryScale,
  LinearScale, ArcElement,
} from 'chart.js';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';
import IconError from '../../assets/icons/IconError.vue';

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, ArcElement);

const adminStore = useAdminStore();
const uiStore = useUiStore();

// ── Data plumbing (the panel reads the shared consumption analytics cache) ──
// ``consumptionAnalytics`` is populated by adminStore.fetchConsumptionAnalytics
// and is already keyed by { totals, buckets, by_model, by_user, ... }.
const consolidated = computed(() => adminStore.consumptionAnalytics || null);
const isLoading = computed(() => adminStore.isLoadingConsumptionAnalytics);
const params = computed(() => adminStore.consumptionParams || { granularity: 'day', source: 'all', days: 30, top_n: 10 });

const currentGranularity = computed(() => params.value.granularity);
const currentSource = computed(() => params.value.source);
const currentDays = computed(() => params.value.days);
const errorMsg = computed(() => (consolidated.value ? '' : ''));

const granularities = [
  { value: 'hour', label: 'Hourly' },
  { value: 'day', label: 'Daily' },
  { value: 'week', label: 'Weekly' },
  { value: 'month', label: 'Monthly' },
];

const sourceLabels = { all: 'All Sources', webui: 'WebUI Chat', api: 'API Only' };
const currentSourceLabel = computed(() => sourceLabels[currentSource.value] || 'All Sources');

const buckets = computed(() => consolidated.value?.buckets || []);
const totals = computed(() => consolidated.value?.totals || {
  input_tokens: 0, output_tokens: 0, total_tokens: 0, calls: 0,
  webui_tokens: 0, api_tokens: 0, energy_kwh: 0, co2_g: 0,
});
const topModels = computed(() => consolidated.value?.by_model || []);
const topUsers = computed(() => consolidated.value?.by_user || []);

const isDark = computed(() => uiStore.currentTheme === 'dark');

// ── Number formatting ─────────────────────────────────────────────────────
function formatNumber(n) {
  const v = Number(n) || 0;
  return v.toLocaleString();
}
function formatCompact(n) {
  const v = Number(n) || 0;
  if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(2) + 'B';
  if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(1) + 'M';
  if (Math.abs(v) >= 1e3) return (v / 1e3).toFixed(v < 1e4 ? 1 : 0) + 'k';
  return String(v);
}

const webuiApiRatio = computed(() => {
  const w = Number(totals.value.webui_tokens) || 0;
  const a = Number(totals.value.api_tokens) || 0;
  const sum = w + a;
  if (!sum) return '—';
  return `${Math.round((w / sum) * 100)}% / ${Math.round((a / sum) * 100)}%`;
});

// ── Actions ───────────────────────────────────────────────────────────────
function refresh() { adminStore.fetchConsumptionAnalytics(); }
function changeGranularity(g) { adminStore.fetchConsumptionAnalytics({ granularity: g }); }
function changeSource(s) { adminStore.fetchConsumptionAnalytics({ source: s }); }
function changeDays(d) { adminStore.fetchConsumptionAnalytics({ days: d }); }

async function exportReport(fmt) {
  try {
    await adminStore.exportConsumptionAnalytics(fmt);
  } catch (e) {
    uiStore.addNotification(`Export (${fmt}) failed.`, 'error');
  }
}

// ── Shared chart theme ────────────────────────────────────────────────────
const theme = computed(() => ({
  grid: isDark.value ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.05)',
  tick: isDark.value ? '#cbd5e1' : '#4b5563',
  legend: isDark.value ? '#cbd5e1' : '#4b5563',
  title: isDark.value ? '#e5e7eb' : '#1f2937',
  tooltipBg: isDark.value ? 'rgba(17,24,39,0.96)' : 'rgba(255,255,255,0.97)',
  tooltipTitle: isDark.value ? '#f3f4f6' : '#111827',
  tooltipBody: isDark.value ? '#e5e7eb' : '#374151',
  tooltipBorder: isDark.value ? '#374151' : '#e5e7eb',
}));

const COLORS = {
  input: '#0EA5E9',
  output: '#F43F5E',
  webui: '#3B82F6',
  api: '#8B5CF6',
  total: '#10B981',
};

function baseOptions(extra = {}) {
  const t = theme.value;
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    animation: { duration: 500 },
    plugins: {
      legend: {
        display: true, position: 'top', align: 'end',
        labels: { color: t.legend, font: { weight: 'bold', size: 11 }, boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle', padding: 14 },
      },
      tooltip: {
        backgroundColor: t.tooltipBg, titleColor: t.tooltipTitle, bodyColor: t.tooltipBody,
        borderColor: t.tooltipBorder, borderWidth: 1, padding: 10, cornerRadius: 8, usePointStyle: true,
        callbacks: { label: (ctx) => `${ctx.dataset.label || ''}: ${formatNumber(ctx.parsed.y ?? ctx.parsed)}` },
      },
    },
    scales: {
      x: { stacked: extra.stacked, grid: { display: false }, ticks: { color: t.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } },
      y: { stacked: extra.stacked, beginAtZero: true, grid: { color: t.grid }, border: { display: false }, ticks: { color: t.tick, callback: (v) => formatCompact(v) } },
    },
    ...(extra.opts || {}),
  };
}

// ── Chart data: Volume over time (stacked input vs output) ─────────────────
const volumeChartData = computed(() => ({
  labels: buckets.value.map((b) => b.label),
  datasets: [
    { label: 'Input', data: buckets.value.map((b) => b.input_tokens || 0), backgroundColor: COLORS.input, borderRadius: 3, stack: 'v' },
    { label: 'Output', data: buckets.value.map((b) => b.output_tokens || 0), backgroundColor: COLORS.output, borderRadius: 3, stack: 'v' },
  ],
}));
const volumeChartOptions = computed(() => baseOptions({ stacked: true }));

// ── Chart data: WebUI vs API over time (stacked) ──────────────────────────
const channelChartData = computed(() => ({
  labels: buckets.value.map((b) => b.label),
  datasets: [
    { label: 'WebUI', data: buckets.value.map((b) => b.webui_tokens || 0), backgroundColor: COLORS.webui, borderRadius: 3, stack: 'c' },
    { label: 'API', data: buckets.value.map((b) => b.api_tokens || 0), backgroundColor: COLORS.api, borderRadius: 3, stack: 'c' },
  ],
}));
const channelChartOptions = computed(() => baseOptions({ stacked: true }));

// ── Chart data: WebUI vs API Doughnut (share of total tokens) ─────────────
const splitDoughnutData = computed(() => ({
  labels: ['WebUI', 'API'],
  datasets: [{
    data: [Number(totals.value.webui_tokens) || 0, Number(totals.value.api_tokens) || 0],
    backgroundColor: [COLORS.webui, COLORS.api],
    borderWidth: 0,
    hoverOffset: 6,
  }],
}));
const splitDoughnutOptions = computed(() => {
  const t = theme.value;
  return {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '62%',
    plugins: {
      legend: { position: 'bottom', labels: { color: t.legend, font: { weight: 'bold', size: 11 }, usePointStyle: true, pointStyle: 'circle', padding: 14 } },
      tooltip: {
        backgroundColor: t.tooltipBg, titleColor: t.tooltipTitle, bodyColor: t.tooltipBody,
        borderColor: t.tooltipBorder, borderWidth: 1, padding: 10, cornerRadius: 8, usePointStyle: true,
        callbacks: {
          label: (ctx) => {
            const total = ctx.dataset.data.reduce((a, b) => a + (Number(b) || 0), 0) || 1;
            const pct = Math.round((Number(ctx.parsed) / total) * 100);
            return `${ctx.label}: ${formatNumber(ctx.parsed)} (${pct}%)`;
          },
        },
      },
    },
  };
});

// ── Chart data: Top models (horizontal bars) ──────────────────────────────
const topModelsChartData = computed(() => ({
  labels: topModels.value.map((m) => m.model_name || m.name || 'unknown'),
  datasets: [{
    label: 'Tokens',
    data: topModels.value.map((m) => m.total_tokens || 0),
    backgroundColor: COLORS.total,
    borderRadius: 4,
  }],
}));
const topModelsChartOptions = computed(() => {
  const t = theme.value;
  return {
    indexAxis: 'y',
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: t.tooltipBg, titleColor: t.tooltipTitle, bodyColor: t.tooltipBody,
        borderColor: t.tooltipBorder, borderWidth: 1, padding: 10, cornerRadius: 8,
        callbacks: { label: (ctx) => `${formatNumber(ctx.parsed.x)} tokens (${ctx.raw} calls)` },
      },
    },
    scales: {
      x: { beginAtZero: true, grid: { color: t.grid }, border: { display: false }, ticks: { color: t.tick, callback: (v) => formatCompact(v) } },
      y: { grid: { display: false }, ticks: { color: t.tick } },
    },
  };
});

const hasSplit = computed(() => (Number(totals.value.webui_tokens) || 0) + (Number(totals.value.api_tokens) || 0) > 0);
</script>

<template>
  <div class="token-consumption-panel">
    <!-- ─── Header / controls ─────────────────────────────────────────── -->
    <div class="panel-header">
      <div class="panel-title-row">
        <h3 class="panel-title">
          <IconPresentationChartBar class="w-5 h-5" />
          <span>Token Consumption Analytics</span>
        </h3>
        <div class="export-buttons">
          <button class="btn-export" @click="exportReport('html')" title="Export HTML">HTML</button>
          <button class="btn-export" @click="exportReport('xlsx')" title="Export Excel">XLSX</button>
          <button class="btn-export" @click="exportReport('docx')" title="Export Word">DOCX</button>
          <button class="btn-export" @click="exportReport('pdf')" title="Export PDF">PDF</button>
        </div>
      </div>

      <div class="panel-controls">
        <div class="granularity-tabs">
          <button
            v-for="g in granularities"
            :key="g.value"
            :class="['gran-tab', { active: currentGranularity === g.value }]"
            @click="changeGranularity(g.value)"
          >
            {{ g.label }}
          </button>
        </div>

        <div class="control-group">
          <label class="control-label">Source</label>
          <select class="panel-select" :value="currentSource" @change="changeSource($event.target.value)">
            <option value="all">All Sources</option>
            <option value="webui">WebUI Chat</option>
            <option value="api">API Only</option>
          </select>
        </div>

        <div class="control-group">
          <label class="control-label">Window</label>
          <select class="panel-select" :value="currentDays" @change="changeDays(Number($event.target.value))">
            <option :value="0">All time</option>
            <option :value="1">Last 24 hours</option>
            <option :value="7">Last 7 days</option>
            <option :value="30">Last 30 days</option>
            <option :value="90">Last 90 days</option>
            <option :value="365">Last year</option>
          </select>
        </div>

        <button class="btn-refresh" :disabled="isLoading" @click="refresh" title="Refresh">
          <IconArrowPath :class="['w-4 h-4', { 'animate-spin': isLoading }]" />
        </button>
      </div>
    </div>

    <!-- ─── Loading / empty states ─────────────────────────────────────── -->
    <div v-if="isLoading" class="state-msg">
      <IconArrowPath class="w-5 h-5 animate-spin" />
      <span>Loading consumption analytics…</span>
    </div>
    <div v-else-if="!consolidated" class="state-msg">
      <IconError class="w-5 h-5 opacity-60" />
      <span>No consumption data available yet. Generate some tokens and refresh.</span>
    </div>

    <template v-else>
      <!-- ─── KPI summary cards ────────────────────────────────────────── -->
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Total Tokens</div>
          <div class="kpi-value">{{ formatCompact(totals.total_tokens) }}</div>
          <div class="kpi-sub">
            <span class="dot input"></span>{{ formatCompact(totals.input_tokens) }} in ·
            <span class="dot output"></span>{{ formatCompact(totals.output_tokens) }} out
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Total Calls</div>
          <div class="kpi-value">{{ formatCompact(totals.calls) }}</div>
          <div class="kpi-sub">{{ consolidated?.avg_tokens_per_call ?? 0 }} tok / call</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">WebUI vs API</div>
          <div class="kpi-value">{{ webuiApiRatio }}</div>
          <div class="kpi-sub">
            <span class="dot webui"></span>{{ formatCompact(totals.webui_tokens) }} ·
            <span class="dot api"></span>{{ formatCompact(totals.api_tokens) }}
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">In : Out Ratio</div>
          <div class="kpi-value">{{ consolidated?.input_output_ratio ?? '—' }}</div>
          <div class="kpi-sub">Avg out/call: {{ consolidated?.avg_output_per_call ?? 0 }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Energy</div>
          <div class="kpi-value">{{ totals.energy_kwh }} kWh</div>
          <div class="kpi-sub">{{ totals.co2_g }} g CO₂</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Peak Bucket</div>
          <div class="kpi-value small">{{ consolidated?.peak_bucket || '—' }}</div>
          <div class="kpi-sub">Highest volume in window</div>
        </div>
      </div>

      <!-- ─── Volume over time (stacked input vs output) ───────────────── -->
      <div class="chart-card">
        <div class="chart-header">
          <h4>Volume over time <span class="chart-subtitle">({{ currentGranularity }} · {{ currentSourceLabel }})</span></h4>
        </div>
        <div class="chart-area">
          <div v-if="!buckets.length" class="chart-empty">No data in this window.</div>
          <Bar v-else :data="volumeChartData" :options="volumeChartOptions" />
        </div>
      </div>

      <!-- ─── WebUI vs API: over time (stacked) + split (doughnut) ─────── -->
      <div class="chart-row">
        <div class="chart-card grow">
          <div class="chart-header">
            <h4>WebUI vs API usage over time</h4>
          </div>
          <div class="chart-area">
            <div v-if="!buckets.length" class="chart-empty">No data in this window.</div>
            <Bar v-else :data="channelChartData" :options="channelChartOptions" />
          </div>
        </div>
        <div class="chart-card split">
          <div class="chart-header">
            <h4>Channel share</h4>
          </div>
          <div class="chart-area doughnut-area">
            <div v-if="!hasSplit" class="chart-empty">No WebUI/API split recorded.</div>
            <Doughnut v-else :data="splitDoughnutData" :options="splitDoughnutOptions" />
          </div>
        </div>
      </div>

      <!-- ─── Top models (horizontal bar + table) ─────────────────────── -->
      <div class="chart-card">
        <div class="chart-header">
          <h4>Top Models</h4>
        </div>
        <div v-if="!topModels.length" class="chart-empty">No model usage recorded.</div>
        <div v-else class="chart-row">
          <div class="chart-area grow">
            <Bar :data="topModelsChartData" :options="topModelsChartOptions" />
          </div>
          <table class="mini-table">
            <thead>
              <tr><th>Model</th><th class="num">Tokens</th><th class="num">Share</th></tr>
            </thead>
            <tbody>
              <tr v-for="m in topModels" :key="m.model_name || m.name">
                <td class="trunc">{{ m.model_name || m.name || 'unknown' }}</td>
                <td class="num">{{ formatCompact(m.total_tokens) }}</td>
                <td class="num">{{ m.percentage }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ─── Top users table ─────────────────────────────────────────── -->
      <div class="chart-card">
        <div class="chart-header">
          <h4>Top Users</h4>
        </div>
        <div v-if="!topUsers.length" class="chart-empty">No user usage recorded.</div>
        <table v-else class="mini-table wide">
          <thead>
            <tr><th>User</th><th class="num">Input</th><th class="num">Output</th><th class="num">Total</th><th class="num">Share</th></tr>
          </thead>
          <tbody>
            <tr v-for="u in topUsers" :key="u.username || u.name">
              <td class="trunc">{{ u.username || u.name || 'anonymous' }}</td>
              <td class="num">{{ formatCompact(u.input_tokens) }}</td>
              <td class="num">{{ formatCompact(u.output_tokens) }}</td>
              <td class="num strong">{{ formatCompact(u.total_tokens) }}</td>
              <td class="num">{{ u.percentage }}%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.token-consumption-panel { display: flex; flex-direction: column; gap: 16px; }

.panel-header {
  display: flex; flex-direction: column; gap: 12px;
  padding: 16px 20px;
  background: var(--bg-secondary, #fff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 12px;
}
.panel-title-row { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.panel-title { display: flex; align-items: center; gap: 8px; font-size: 1rem; font-weight: 700; margin: 0; color: var(--text-primary, #1e293b); }
.export-buttons { display: flex; gap: 6px; }
.btn-export {
  padding: 5px 10px; border-radius: 7px; font-size: 0.72rem; font-weight: 700;
  border: 1px solid var(--border-color, #e2e8f0); background: var(--bg-primary, #fff);
  color: var(--text-secondary, #475569); cursor: pointer;
}
.btn-export:hover { background: var(--bg-hover, #f1f5f9); }

.panel-controls { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.granularity-tabs { display: inline-flex; gap: 3px; padding: 3px; background: var(--bg-hover, #f1f5f9); border-radius: 9px; }
.gran-tab {
  border: none; background: transparent; cursor: pointer;
  font-size: 0.74rem; font-weight: 700; padding: 5px 12px; border-radius: 7px;
  color: var(--text-secondary, #64748b); transition: all 0.15s ease;
}
.gran-tab.active { background: var(--bg-secondary, #fff); color: #10B981; box-shadow: 0 1px 2px rgba(0,0,0,0.12); }
.control-group { display: flex; flex-direction: column; gap: 3px; }
.control-label { font-size: 0.68rem; font-weight: 700; text-transform: uppercase; color: var(--text-secondary, #94a3b8); }
.panel-select {
  padding: 6px 10px; border-radius: 7px; font-size: 0.8rem;
  border: 1px solid var(--border-color, #e2e8f0); background: var(--bg-primary, #fff); color: var(--text-primary, #334155);
}
.btn-refresh {
  display: inline-flex; align-items: center; justify-content: center;
  width: 34px; height: 34px; border-radius: 8px;
  border: 1px solid var(--border-color, #e2e8f0); background: transparent;
  color: var(--text-secondary, #64748b); cursor: pointer;
}
.btn-refresh:hover { background: var(--bg-hover, #f1f5f9); }

.state-msg {
  display: flex; align-items: center; justify-content: center; gap: 10px;
  padding: 40px 20px; color: var(--text-secondary, #64748b); font-size: 0.9rem;
}
.state-msg.error { color: #e11d48; }

/* KPI grid */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.kpi-card {
  padding: 16px 18px; border-radius: 12px;
  background: var(--bg-secondary, #fff); border: 1px solid var(--border-color, #e2e8f0);
}
.kpi-label { font-size: 0.68rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-secondary, #94a3b8); }
.kpi-value { font-size: 1.5rem; font-weight: 800; margin-top: 4px; color: var(--text-primary, #1e293b); line-height: 1.1; }
.kpi-value.small { font-size: 1rem; }
.kpi-sub { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; margin-top: 6px; font-size: 0.72rem; color: var(--text-secondary, #64748b); }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot.input { background: #0EA5E9; }
.dot.output { background: #F43F5E; }
.dot.webui { background: #3B82F6; }
.dot.api { background: #8B5CF6; }

/* Chart cards */
.chart-card {
  padding: 16px 18px; border-radius: 12px;
  background: var(--bg-secondary, #fff); border: 1px solid var(--border-color, #e2e8f0);
}
.chart-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.chart-header h4 { margin: 0; font-size: 0.9rem; font-weight: 700; color: var(--text-primary, #1e293b); }
.chart-subtitle { font-size: 0.74rem; font-weight: 500; color: var(--text-secondary, #94a3b8); }
.chart-area { height: 300px; position: relative; }
.doughnut-area { height: 240px; }
.chart-empty { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-secondary, #94a3b8); font-size: 0.85rem; }

.chart-row { display: flex; gap: 16px; align-items: stretch; flex-wrap: wrap; }
.chart-row .grow { flex: 1 1 360px; min-width: 0; }
.chart-card.split { flex: 0 0 300px; }
@media (max-width: 760px) {
  .chart-card.split { flex: 1 1 100%; }
}

/* Mini tables */
.mini-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; align-self: flex-start; }
.mini-table.wide { margin-top: 4px; }
.mini-table th {
  text-align: left; padding: 8px 10px; font-size: 0.66rem; font-weight: 800;
  text-transform: uppercase; letter-spacing: 0.03em; color: var(--text-secondary, #94a3b8);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}
.mini-table td { padding: 7px 10px; border-bottom: 1px solid var(--border-color, #f1f5f9); color: var(--text-primary, #334155); }
.mini-table .num { text-align: right; font-variant-numeric: tabular-nums; }
.mini-table .strong { font-weight: 700; }
.mini-table .trunc { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
