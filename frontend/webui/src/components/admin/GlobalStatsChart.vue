
<script setup>
import { ref, computed } from 'vue';
import { Line } from 'vue-chartjs';
import {
  Chart as ChartJS, Title, Tooltip, Legend, LineElement, CategoryScale,
  LinearScale, PointElement, TimeScale, Filler,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import { useUiStore } from '../../stores/ui';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';

ChartJS.register(Title, Tooltip, Legend, LineElement, CategoryScale, LinearScale, PointElement, TimeScale, Filler);

const props = defineProps({
  stats: { type: Object, default: null },
  isLoading: { type: Boolean, default: false },
});

const uiStore = useUiStore();
const chartRef = ref(null);

const chartMode = ref('time_series'); // time_series | composition | weekday_mean | weekday_variance | weekly_stats
const showArea = ref(true);

const isDark = computed(() => uiStore.currentTheme === 'dark');
const palette = computed(() => ({
  total: '#10B981',
  input: '#0EA5E9',
  output: '#F43F5E',
  webui: '#3B82F6',
  api: '#8B5CF6',
  requests: '#F59E0B',
  grid: isDark.value ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.05)',
  tick: isDark.value ? '#cbd5e1' : '#4b5563',
  legend: isDark.value ? '#cbd5e1' : '#4b5563',
  title: isDark.value ? '#e5e7eb' : '#1f2937',
  tooltipBg: isDark.value ? 'rgba(17,24,39,0.96)' : 'rgba(255,255,255,0.97)',
  tooltipTitle: isDark.value ? '#f3f4f6' : '#111827',
  tooltipBody: isDark.value ? '#e5e7eb' : '#374151',
  tooltipBorder: isDark.value ? '#374151' : '#e5e7eb',
}));

const selectedCurves = ref({
  total_tokens: true,
  input_tokens: true,
  output_tokens: false,
  webui_tokens: false,
  api_tokens: false,
  requests: false,
});

function selectOnlyCurve(key) {
  Object.keys(selectedCurves.value).forEach((k) => { selectedCurves.value[k] = (k === key); });
}
function selectAllCurves() {
  Object.keys(selectedCurves.value).forEach((k) => { selectedCurves.value[k] = true; });
}
function toggleCurve(key) {
  selectedCurves.value[key] = !selectedCurves.value[key];
}

const isTimeScale = computed(() => chartMode.value === 'time_series' || chartMode.value === 'composition');

function fmtCompact(v) {
  const n = Number(v) || 0;
  if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(n < 1e4 ? 1 : 0) + 'k';
  return String(n);
}
function fmtFull(v) {
  return Number(v || 0).toLocaleString();
}

const summary = computed(() => {
  const s = props.stats;
  if (!s) return null;
  const arr = (s.tokens_per_day || []).map((d) => Number(d.count) || 0);
  if (arr.length === 0) return { total: 0, avg: 0, max: 0, min: 0, days: 0 };
  const total = arr.reduce((a, b) => a + b, 0);
  let max = -Infinity, min = Infinity;
  for (const point of (s.tokens_per_day || [])) {
    const v = Number(point.count) || 0;
    if (v > max) max = v;
    if (v < min) min = v;
  }
  return { total, avg: Math.round(total / arr.length), max, min, days: arr.length };
});

const chartTitle = computed(() => {
  switch (chartMode.value) {
    case 'time_series': return 'Daily Consumption & Throughput (last 30 days)';
    case 'composition': return 'Input vs Output Token Composition (stacked)';
    case 'weekday_mean': return 'Average Daily Activity by Weekday';
    case 'weekday_variance': return 'Activity Variance by Weekday';
    case 'weekly_stats': return 'Weekly Distribution (Mean ± Std Dev)';
    default: return 'Global Usage Telemetry';
  }
});

const chartOptions = computed(() => {
  const p = palette.value;
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    animation: { duration: 550, easing: 'easeOutQuart' },
    plugins: {
      legend: {
        display: true, position: 'top', align: 'end',
        labels: {
          color: p.legend, font: { weight: 'bold', size: 11 },
          boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'circle', padding: 14,
        },
      },
      title: { display: true, text: chartTitle.value, color: p.title, font: { size: 13, weight: 'bold' }, padding: { bottom: 10 } },
      tooltip: {
        backgroundColor: p.tooltipBg, titleColor: p.tooltipTitle, bodyColor: p.tooltipBody,
        borderColor: p.tooltipBorder, borderWidth: 1, padding: 12, cornerRadius: 8, boxPadding: 4, usePointStyle: true,
        callbacks: {
          title: (items) => {
            if (!items.length) return '';
            const x = items[0].parsed.x ?? items[0].label;
            if (isTimeScale.value && x) {
              const d = new Date(x);
              if (!Number.isNaN(d.getTime())) {
                return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
              }
            }
            return String(x ?? '');
          },
          label: (ctx) => `${ctx.dataset.label || ''}: ${fmtFull(ctx.parsed.y)}`,
          footer: (items) => {
            if (chartMode.value !== 'composition' || !items.length) return '';
            const idx = items[0].dataIndex;
            const ds = items[0].chart.data.datasets;
            const inp = Number(ds[0]?.data?.[idx]?.y) || 0;
            const out = Number(ds[1]?.data?.[idx]?.y) || 0;
            const sum = inp + out;
            if (!sum) return '';
            return `Input share: ${Math.round((inp / sum) * 100)}%`;
          },
        },
      },
    },
    scales: {
      x: {
        type: isTimeScale.value ? 'time' : 'category',
        time: { unit: 'day', tooltipFormat: 'MMM d, yyyy' },
        grid: { display: false },
        ticks: { color: p.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 10 },
      },
      y: {
        type: 'linear', display: true, position: 'left', beginAtZero: true,
        stacked: chartMode.value === 'composition',
        grid: { color: p.grid }, border: { display: false },
        ticks: { color: p.tick, callback: (v) => fmtCompact(v) },
      },
      y1: {
        type: 'linear',
        display: isTimeScale.value && chartMode.value !== 'composition' && selectedCurves.value.requests,
        position: 'right', beginAtZero: true,
        grid: { drawOnChartArea: false }, border: { display: false },
        ticks: { color: p.requests, precision: 0 },
      },
    },
  };
});

function gradientFill(hex, alphaTop = 0.28) {
  return (ctx) => {
    const { chart } = ctx;
    const { ctx: c, chartArea } = chart;
    if (!chartArea) return 'transparent';
    const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    g.addColorStop(0, hexToRgba(hex, alphaTop));
    g.addColorStop(1, hexToRgba(hex, 0));
    return g;
  };
}
function hexToRgba(hex, a) {
  const h = hex.replace('#', '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

const chartData = computed(() => {
  if (!props.stats) return { labels: [], datasets: [] };
  const p = palette.value;
  const weekdayOrder = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

  if (chartMode.value === 'composition') {
    const inputArr = props.stats.prompt_tokens_per_day || [];
    const outputArr = props.stats.completion_tokens_per_day || [];
    const allDates = Array.from(new Set([
      ...inputArr.map((s) => s.date),
      ...outputArr.map((s) => s.date),
    ])).sort();
    const inputMap = Object.fromEntries(inputArr.map((s) => [s.date, Number(s.count) || 0]));
    const outputMap = Object.fromEntries(outputArr.map((s) => [s.date, Number(s.count) || 0]));
    return {
      labels: allDates,
      datasets: [
        {
          label: 'Input tokens',
          data: allDates.map((d) => ({ x: d, y: inputMap[d] || 0 })),
          borderColor: p.input, backgroundColor: hexToRgba(p.input, 0.75),
          borderWidth: 1.5, fill: true, pointRadius: 0, pointHoverRadius: 4, tension: 0.25,
        },
        {
          label: 'Output tokens',
          data: allDates.map((d) => ({ x: d, y: outputMap[d] || 0 })),
          borderColor: p.output, backgroundColor: hexToRgba(p.output, 0.75),
          borderWidth: 1.5, fill: true, pointRadius: 0, pointHoverRadius: 4, tension: 0.25,
        },
      ],
    };
  }

  if (chartMode.value === 'time_series') {
    const datasets = [];
    const push = (label, dataArr, color, opts = {}) => {
      if (!Array.isArray(dataArr) || dataArr.length === 0) return;
      datasets.push({
        label,
        data: dataArr.map((s) => ({ x: s.date, y: Number(s.count) || 0 })),
        borderColor: color,
        backgroundColor: opts.fill ? gradientFill(color, opts.areaAlpha ?? 0.28) : hexToRgba(color, 0.12),
        borderWidth: opts.width ?? 2.5,
        borderDash: opts.dash || [],
        tension: 0.28,
        fill: !!opts.fill,
        pointRadius: 2.5,
        pointHoverRadius: 6,
        pointHoverBorderWidth: 2,
        pointHoverBackgroundColor: color,
        pointBackgroundColor: isDark.value ? '#0f172a' : '#ffffff',
        pointBorderColor: color,
        pointBorderWidth: 1.5,
        yAxisID: opts.yAxis || 'y',
        spanGaps: true,
      });
    };

    if (selectedCurves.value.total_tokens) push('Total tokens', props.stats.tokens_per_day, p.total, { fill: showArea.value, width: 3 });
    if (selectedCurves.value.input_tokens) push('Input tokens', props.stats.prompt_tokens_per_day, p.input);
    if (selectedCurves.value.output_tokens) push('Output tokens', props.stats.completion_tokens_per_day, p.output);
    if (selectedCurves.value.webui_tokens) push('WebUI tokens', props.stats.webui_tokens_per_day, p.webui);
    if (selectedCurves.value.api_tokens) push('API tokens', props.stats.api_tokens_per_day, p.api);
    if (selectedCurves.value.requests) push('Requests', props.stats.generations_per_day, p.requests, { dash: [5, 5], yAxis: 'y1', width: 2 });

    const allDates = Array.from(new Set([
      ...(props.stats.tokens_per_day || []).map((s) => s.date),
      ...(props.stats.prompt_tokens_per_day || []).map((s) => s.date),
      ...(props.stats.completion_tokens_per_day || []).map((s) => s.date),
      ...(props.stats.generations_per_day || []).map((s) => s.date),
    ])).sort();

    return { labels: allDates, datasets };
  }

  if (chartMode.value === 'weekday_mean') {
    return {
      labels: weekdayOrder,
      datasets: [{
        label: 'Mean generations / day',
        data: weekdayOrder.map((d) => (props.stats.mean_per_weekday?.[d] ?? 0)),
        borderColor: p.total, backgroundColor: gradientFill(p.total, 0.25),
        borderWidth: 2.5, tension: 0.35, fill: true,
        pointRadius: 4, pointHoverRadius: 7, pointBackgroundColor: p.total,
        pointBorderColor: isDark.value ? '#0f172a' : '#fff', pointBorderWidth: 2,
      }],
    };
  }

  if (chartMode.value === 'weekday_variance') {
    return {
      labels: weekdayOrder,
      datasets: [{
        label: 'Variance',
        data: weekdayOrder.map((d) => (props.stats.variance_per_weekday?.[d] ?? 0)),
        borderColor: p.requests, backgroundColor: gradientFill(p.requests, 0.22),
        borderWidth: 2.5, tension: 0.35, fill: true,
        pointRadius: 4, pointHoverRadius: 7, pointBackgroundColor: p.requests,
        pointBorderColor: isDark.value ? '#0f172a' : '#fff', pointBorderWidth: 2,
      }],
    };
  }

  if (chartMode.value === 'weekly_stats') {
    const means = weekdayOrder.map((d) => props.stats.mean_per_weekday?.[d] ?? 0);
    const stds = weekdayOrder.map((d) => Math.sqrt(props.stats.variance_per_weekday?.[d] ?? 0));
    const upper = means.map((m, i) => m + stds[i]);
    const lower = means.map((m, i) => Math.max(0, m - stds[i]));
    return {
      labels: weekdayOrder,
      datasets: [
        { label: 'Mean', data: means, borderColor: p.webui, backgroundColor: p.webui, borderWidth: 2.5, tension: 0.3, pointRadius: 4, pointHoverRadius: 7, fill: false },
        { label: 'Std. deviation band', data: upper, borderColor: 'transparent', backgroundColor: hexToRgba(p.webui, 0.15), pointRadius: 0, fill: '+1' },
        { label: 'Lower bound', data: lower, borderColor: 'transparent', backgroundColor: 'transparent', pointRadius: 0, fill: false },
      ],
    };
  }

  return { labels: [], datasets: [] };
});

function exportChartImage() {
  if (chartRef.value?.chart) {
    const link = document.createElement('a');
    link.href = chartRef.value.chart.toBase64Image('image/png', 1);
    link.download = `lollms_consumption_${chartMode.value}.png`;
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
  const rows = [];
  if (chartMode.value === 'time_series' || chartMode.value === 'composition') {
    rows.push(['date', 'tokens', 'prompt_tokens', 'completion_tokens', 'generations']);
    const promptMap = Object.fromEntries((props.stats.prompt_tokens_per_day || []).map((s) => [s.date, s.count]));
    const compMap = Object.fromEntries((props.stats.completion_tokens_per_day || []).map((s) => [s.date, s.count]));
    const genMap = Object.fromEntries((props.stats.generations_per_day || []).map((s) => [s.date, s.count]));
    for (const s of (props.stats.tokens_per_day || [])) {
      rows.push([s.date, s.count, promptMap[s.date] || 0, compMap[s.date] || 0, genMap[s.date] || 0]);
    }
  } else {
    const weekdayOrder = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    rows.push(['weekday', 'mean', 'variance', 'std_deviation']);
    for (const d of weekdayOrder) {
      const mean = props.stats.mean_per_weekday?.[d] ?? 0;
      const variance = props.stats.variance_per_weekday?.[d] ?? 0;
      rows.push([d, mean, variance, Math.sqrt(variance)]);
    }
  }
  const csv = 'data:text/csv;charset=utf-8,' + rows.map((r) => r.join(',')).join('\n');
  const link = document.createElement('a');
  link.href = encodeURI(csv);
  link.download = `lollms_consumption_${chartMode.value}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
</script>

<template>
  <div class="gs-chart-wrap">
    <div class="gs-card">
      <div class="gs-head">
        <div class="gs-modes" role="group" aria-label="Chart mode">
          <button
            v-for="m in [
              { id: 'time_series', label: 'Multi-Curve' },
              { id: 'composition', label: 'Composition' },
              { id: 'weekly_stats', label: 'Weekly ±σ' },
              { id: 'weekday_mean', label: 'Weekday Mean' },
              { id: 'weekday_variance', label: 'Variance' },
            ]"
            :key="m.id"
            type="button"
            class="gs-mode-btn"
            :class="{ active: chartMode === m.id }"
            @click="chartMode = m.id"
          >{{ m.label }}</button>
        </div>

        <div class="gs-actions">
          <button class="gs-btn" @click="exportChartImage" title="Export current chart as PNG">
            <IconArrowDownTray class="w-3.5 h-3.5 text-sky-500" /><span>PNG</span>
          </button>
          <button class="gs-btn" @click="exportChartCSV" title="Export underlying data as CSV">
            <IconArrowDownTray class="w-3.5 h-3.5" /><span>CSV</span>
          </button>
        </div>
      </div>

      <div v-if="summary && stats" class="gs-summary">
        <div class="gs-kpi"><span class="gs-kpi-label">Total</span><span class="gs-kpi-value" style="color:#10B981">{{ fmtCompact(summary.total) }}</span></div>
        <div class="gs-kpi"><span class="gs-kpi-label">Daily avg</span><span class="gs-kpi-value">{{ fmtCompact(summary.avg) }}</span></div>
        <div class="gs-kpi"><span class="gs-kpi-label">Peak</span><span class="gs-kpi-value" style="color:#0EA5E9">{{ fmtCompact(summary.max) }}</span></div>
        <div class="gs-kpi"><span class="gs-kpi-label">Lowest</span><span class="gs-kpi-value" style="color:#F43F5E">{{ fmtCompact(summary.min) }}</span></div>
        <div class="gs-kpi"><span class="gs-kpi-label">Days</span><span class="gs-kpi-value">{{ summary.days }}</span></div>
      </div>

      <div v-if="chartMode === 'time_series'" class="gs-curves">
        <div class="gs-curve-list">
          <span class="gs-curves-title">Curves:</span>
          <label v-for="c in [
            { key: 'total_tokens', label: 'Total', color: '#10B981' },
            { key: 'input_tokens', label: 'Input', color: '#0EA5E9' },
            { key: 'output_tokens', label: 'Output', color: '#F43F5E' },
            { key: 'webui_tokens', label: 'WebUI', color: '#3B82F6' },
            { key: 'api_tokens', label: 'API', color: '#8B5CF6' },
            { key: 'requests', label: 'Requests', color: '#F59E0B' },
          ]" :key="c.key" class="gs-curve-chip" :class="{ off: !selectedCurves[c.key] }">
            <input type="checkbox" :checked="selectedCurves[c.key]" @change="toggleCurve(c.key)" />
            <span class="gs-swatch" :style="{ background: c.color }"></span>
            <span>{{ c.label }}</span>
          </label>
        </div>
        <div class="gs-curve-tools">
          <label class="gs-toggle"><input type="checkbox" v-model="showArea" /> Area fill</label>
          <button class="gs-mini-link" @click="selectAllCurves">All</button>
          <button class="gs-mini-link" @click="selectOnlyCurve('input_tokens')">Input</button>
          <button class="gs-mini-link" @click="selectOnlyCurve('output_tokens')">Output</button>
        </div>
      </div>

      <div class="gs-canvas">
        <div v-if="isLoading" class="gs-state">Loading chart data…</div>
        <div v-else-if="!stats" class="gs-state">No statistics available.</div>
        <Line v-else ref="chartRef" :data="chartData" :options="chartOptions" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.gs-chart-wrap { width: 100%; }
.gs-card {
  background: var(--bg-secondary, #fff);
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 16px;
  padding: 18px 20px 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.gs-head {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 10px;
  border-bottom: 1px solid var(--border-color, #f1f5f9);
  padding-bottom: 12px; margin-bottom: 12px;
}
.gs-modes { display: inline-flex; gap: 4px; padding: 3px; background: var(--bg-hover, #f1f5f9); border-radius: 10px; }
.gs-mode-btn {
  border: none; background: transparent; cursor: pointer;
  font-size: 0.72rem; font-weight: 700; padding: 6px 12px; border-radius: 8px;
  color: var(--text-secondary, #64748b); transition: all 0.15s ease;
}
.gs-mode-btn:hover { color: var(--text-primary, #1e293b); }
.gs-mode-btn.active { background: var(--bg-secondary, #fff); color: #10B981; box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
.gs-actions { display: flex; gap: 6px; }
.gs-btn {
  display: inline-flex; align-items: center; gap: 5px;
  border: 1px solid var(--border-color, #e2e8f0); background: var(--bg-primary, #fff);
  color: var(--text-secondary, #475569); font-size: 0.72rem; font-weight: 700;
  padding: 5px 10px; border-radius: 8px; cursor: pointer;
}
.gs-btn:hover { background: var(--bg-hover, #f1f5f9); }
.gs-summary {
  display: grid; grid-template-columns: repeat(5, 1fr);
  gap: 1px; background: var(--border-color, #f1f5f9);
  border-radius: 10px; overflow: hidden; margin-bottom: 12px;
}
.gs-kpi { background: var(--bg-secondary, #fff); padding: 10px 12px; display: flex; flex-direction: column; gap: 2px; }
.gs-kpi-label { font-size: 0.62rem; font-weight: 800; letter-spacing: 0.04em; text-transform: uppercase; color: var(--text-secondary, #94a3b8); }
.gs-kpi-value { font-size: 1.05rem; font-weight: 800; color: var(--text-primary, #1e293b); }
.gs-curves {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 10px; margin-bottom: 12px;
  padding: 8px 12px; border-radius: 10px;
  background: var(--bg-hover, #f8fafc); border: 1px solid var(--border-color, #f1f5f9);
}
.gs-curve-list { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.gs-curves-title { font-size: 0.62rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary, #94a3b8); }
.gs-curve-chip { display: inline-flex; align-items: center; gap: 5px; cursor: pointer; font-size: 0.72rem; font-weight: 700; color: var(--text-primary, #334155); }
.gs-curve-chip.off { opacity: 0.4; }
.gs-curve-chip input { width: 13px; height: 13px; accent-color: #10B981; cursor: pointer; }
.gs-swatch { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.gs-curve-tools { display: flex; align-items: center; gap: 10px; }
.gs-toggle { display: inline-flex; align-items: center; gap: 5px; font-size: 0.7rem; font-weight: 700; color: var(--text-secondary, #64748b); cursor: pointer; }
.gs-toggle input { width: 13px; height: 13px; accent-color: #0EA5E9; }
.gs-mini-link { background: none; border: none; padding: 0; font-size: 0.68rem; font-weight: 700; color: #0EA5E9; cursor: pointer; }
.gs-mini-link:hover { text-decoration: underline; }
.gs-canvas { height: 380px; position: relative; }
.gs-state { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--text-secondary, #94a3b8); font-size: 0.85rem; }
@media (max-width: 640px) {
  .gs-summary { grid-template-columns: repeat(3, 1fr); }
  .gs-canvas { height: 300px; }
}
</style>
