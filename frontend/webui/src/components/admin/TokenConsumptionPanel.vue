<template>
  <div class="token-consumption-panel">
    <!-- ─── Header / controls ─────────────────────────────────────────── -->
    <div class="panel-header">
      <div class="panel-title-row">
        <h3 class="panel-title">
          <IconPresentationChartBar class="w-5 h-5" />
          <span>Token Consumption Analytics</span>
        </h3>
      </div>

      <!-- Filters: granularity tabs, source scope, time window -->
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

    <!-- ─── Loading / error states ─────────────────────────────────────── -->
    <div v-if="isLoading" class="state-msg">
      <IconArrowPath class="w-5 h-5 animate-spin" />
      <span>Loading consumption analytics…</span>
    </div>
    <div v-else-if="errorMsg" class="state-msg error">
      <IconError class="w-5 h-5" />
      <span>{{ errorMsg }}</span>
    </div>
    <div v-else-if="!consolidated" class="state-msg">
      <IconError class="w-5 h-5 opacity-60" />
      <span>No consumption data available yet. Generate some tokens and refresh.</span>
    </div>

    <template v-else-if="consolidated">
      <!-- ─── KPI summary cards ────────────────────────────────────────── -->
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Total Tokens</div>
          <div class="kpi-value">{{ formatNumber(totals.total_tokens) }}</div>
          <div class="kpi-sub">
            <span class="dot input"></span>{{ formatNumber(totals.input_tokens) }} in ·
            <span class="dot output"></span>{{ formatNumber(totals.output_tokens) }} out
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Total Calls</div>
          <div class="kpi-value">{{ formatNumber(totals.calls) }}</div>
          <div class="kpi-sub">{{ consolidated?.avg_tokens_per_call ?? 0 }} tok / call</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">WebUI vs API</div>
          <div class="kpi-value">{{ webuiApiRatio }}</div>
          <div class="kpi-sub">
            <span class="dot webui"></span>{{ formatNumber(totals.webui_tokens) }} ·
            <span class="dot api"></span>{{ formatNumber(totals.api_tokens) }}
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

      <!-- ─── Timeline chart (stacked bars: input vs output) ───────────── -->
      <div class="chart-card">
        <div class="chart-header">
          <h4>
            Volume over time
            <span class="chart-subtitle">({{ currentGranularity }} · {{ currentSourceLabel }})</span>
          </h4>
          <div class="chart-legend">
            <span><span class="dot input"></span>Input</span>
            <span><span class="dot output"></span>Output</span>
          </div>
        </div>
        <div class="chart-area">
          <div v-if="!buckets.length" class="chart-empty">No data in this window.</div>
          <div
            v-for="(b, idx) in buckets"
            :key="idx"
            class="bar-col"
            :title="`${b.label}\nInput: ${formatNumber(b.input_tokens)}\nOutput: ${formatNumber(b.output_tokens)}\nTotal: ${formatNumber(b.total_tokens)}\nCalls: ${b.calls}`"
          >
            <div class="bar-stack">
              <div class="bar-segment output" :style="{ height: barHeight(b.output_tokens) }"></div>
              <div class="bar-segment input" :style="{ height: barHeight(b.input_tokens) }"></div>
            </div>
            <div class="bar-label">{{ compactLabel(b.label) }}</div>
          </div>
        </div>
      </div>

      <!-- ─── WebUI vs API chart (grouped bars) ────────────────────────── -->
      <div class="chart-card">
        <div class="chart-header">
          <h4>WebUI vs API usage</h4>
          <div class="chart-legend">
            <span><span class="dot webui"></span>WebUI</span>
            <span><span class="dot api"></span>API</span>
          </div>
        </div>
        <div class="chart-area">
          <div v-if="!buckets.length" class="chart-empty">No data in this window.</div>
          <div
            v-for="(b, idx) in buckets"
            :key="idx"
            class="bar-col"
            :title="`${b.label}\nWebUI: ${formatNumber(b.webui_tokens)}\nAPI: ${formatNumber(b.api_tokens)}`"
          >
            <div class="bar-stack side-by-side">
              <div class="bar-segment webui" :style="{ height: barHeight(b.webui_tokens, 'webuiApi') }"></div>
              <div class="bar-segment api" :style="{ height: barHeight(b.api_tokens, 'webuiApi') }"></div>
            </div>
            <div class="bar-label">{{ compactLabel(b.label) }}</div>
          </div>
        </div>
      </div>

      <!-- ─── Breakdowns: by model & by user ───────────────────────────── -->
      <div class="breakdown-grid">
        <div class="table-card">
          <h4>Top Models</h4>
          <table class="data-table">
            <thead>
              <tr><th>Model</th><th class="num">Input</th><th class="num">Output</th><th class="num">Total</th><th class="num">Share</th></tr>
            </thead>
            <tbody>
              <tr v-if="!byModel.length"><td colspan="5" class="empty-cell">No data.</td></tr>
              <tr v-for="m in byModel" :key="m.model_name">
                <td class="model-cell" :title="m.model_name">{{ m.model_name }}</td>
                <td class="num">{{ formatNumber(m.input_tokens) }}</td>
                <td class="num">{{ formatNumber(m.output_tokens) }}</td>
                <td class="num strong">{{ formatNumber(m.total_tokens) }}</td>
                <td class="num"><span class="pct-badge">{{ m.percentage }}%</span></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="table-card">
          <h4>Top Users</h4>
          <table class="data-table">
            <thead>
              <tr><th>User</th><th class="num">Input</th><th class="num">Output</th><th class="num">Total</th><th class="num">Share</th></tr>
            </thead>
            <tbody>
              <tr v-if="!byUser.length"><td colspan="5" class="empty-cell">No data.</td></tr>
              <tr v-for="u in byUser" :key="u.username">
                <td class="model-cell" :title="u.username">{{ u.username }}</td>
                <td class="num">{{ formatNumber(u.input_tokens) }}</td>
                <td class="num">{{ formatNumber(u.output_tokens) }}</td>
                <td class="num strong">{{ formatNumber(u.total_tokens) }}</td>
                <td class="num"><span class="pct-badge">{{ u.percentage }}%</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ─── Export actions (bottom bar) ──────────────────────────────── -->
      <div class="export-footer">
        <span class="export-footer-label">Export report</span>
        <div class="export-actions">
          <button class="btn-export" :disabled="!consolidated" @click="doExport('html')" title="Export as HTML">
            <IconDocumentText class="w-4 h-4" /><span>HTML</span>
          </button>
          <button class="btn-export" :disabled="!consolidated" @click="doExport('pdf')" title="Export as PDF">
            <IconFileText class="w-4 h-4" /><span>PDF</span>
          </button>
          <button class="btn-export" :disabled="!consolidated" @click="doExport('docx')" title="Export as Word Document">
            <IconDocumentText class="w-4 h-4" /><span>DOCX</span>
          </button>
          <button class="btn-export" :disabled="!consolidated" @click="doExport('xlsx')" title="Export as Excel Workbook">
            <IconTable class="w-4 h-4" /><span>XLSX</span>
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';

import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconDocumentText from '../../assets/icons/IconDocumentText.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconTable from '../../assets/icons/IconTable.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';
import IconError from '../../assets/icons/IconError.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const granularities = [
  { value: 'hour', label: 'Hourly' },
  { value: 'day', label: 'Daily' },
  { value: 'week', label: 'Weekly' },
  { value: 'month', label: 'Monthly' },
];

const errorMsg = ref('');

// Only treat a payload that actually carries a `totals` block as rendered
// data. This prevents the panel from showing an entirely blank/unstyled shell
// on a validation error (which returns a bare FastAPI error object, not our
// ConsumptionAnalyticsResponse), and correctly falls back to the empty-state
// message instead of silently rendering zeros as if there were no data.
const consolidated = computed(() => {
  const data = adminStore.consumptionAnalytics;
  return data && data.totals ? data : null;
});

// Defensive totals: the backend may return a partial/error-shaped payload
// (e.g. an auth or validation error body without `totals`). Never assume the
// shape is complete, or the whole render crashes on `totals.total_tokens`.
const totals = computed(() => consolidated.value?.totals || {
  input_tokens: 0, output_tokens: 0, total_tokens: 0, calls: 0,
  webui_input_tokens: 0, webui_output_tokens: 0, webui_tokens: 0, webui_calls: 0,
  api_input_tokens: 0, api_output_tokens: 0, api_tokens: 0, api_calls: 0,
  energy_kwh: 0, co2_g: 0,
});
const buckets = computed(() => consolidated.value?.buckets || []);
// The backend serializes ``by_model``/``by_user`` as typed
// ``ConsumptionBreakdownItem`` objects carrying both the generic ``name``
// field and the semantic ``model_name``/``username`` aliases. Normalize here
// so the template can consume either shape without breaking.
const byModel = computed(() =>
  (consolidated.value?.by_model || []).map((m) => ({
    model_name: m.model_name || m.name || '—',
    input_tokens: m.input_tokens || 0,
    output_tokens: m.output_tokens || 0,
    total_tokens: m.total_tokens || 0,
    calls: m.calls || 0,
    percentage: typeof m.percentage === 'number' ? m.percentage : 0,
  }))
);
const byUser = computed(() =>
  (consolidated.value?.by_user || []).map((u) => ({
    username: u.username || u.name || '—',
    input_tokens: u.input_tokens || 0,
    output_tokens: u.output_tokens || 0,
    total_tokens: u.total_tokens || 0,
    calls: u.calls || 0,
    percentage: typeof u.percentage === 'number' ? u.percentage : 0,
  }))
);
const isLoading = computed(() => adminStore.isLoadingConsumptionAnalytics);

const currentGranularity = computed(() => adminStore.consumptionParams.granularity);
const currentSource = computed(() => adminStore.consumptionParams.source);
const currentDays = computed(() => adminStore.consumptionParams.days);

const currentSourceLabel = computed(() => {
  switch (currentSource.value) {
    case 'webui': return 'WebUI chat';
    case 'api': return 'API';
    default: return 'All sources';
  }
});

const webuiApiRatio = computed(() => {
  const t = totals.value;
  if (!t || !t.total_tokens) return '—';
  return `${Math.round((t.webui_tokens / t.total_tokens) * 100)}% / ${Math.round((t.api_tokens / t.total_tokens) * 100)}%`;
});

// Compute a max value across buckets for the timeline (input vs output chart).
const maxTimeline = computed(() => {
  const buckets = consolidated.value?.buckets || [];
  return buckets.reduce((mx, b) => Math.max(mx, b.input_tokens || 0, b.output_tokens || 0), 0) || 1;
});

// Compute a max value across buckets for the webui/api chart.
const maxWebuiApi = computed(() => {
  const buckets = consolidated.value?.buckets || [];
  return buckets.reduce((mx, b) => Math.max(mx, b.webui_tokens || 0, b.api_tokens || 0), 0) || 1;
});

function barHeight(value, mode = 'timeline') {
  const max = mode === 'webuiApi' ? maxWebuiApi.value : maxTimeline.value;
  const pct = Math.min(100, Math.round(((value || 0) / max) * 100));
  return `${pct}%`;
}

function compactLabel(label) {
  if (!label) return '';
  return label.length > 10 ? label.slice(0, 10) + '…' : label;
}

function formatNumber(n) {
  if (n === null || n === undefined) return '0';
  return Number(n).toLocaleString();
}

async function refresh() {
  errorMsg.value = '';
  const result = await adminStore.fetchConsumptionAnalytics();
  if (!result) errorMsg.value = 'Failed to load consumption analytics.';
}

function changeGranularity(g) {
  if (g === currentGranularity.value) return;
  adminStore.fetchConsumptionAnalytics({ granularity: g });
}

function changeSource(src) {
  if (src === currentSource.value) return;
  adminStore.fetchConsumptionAnalytics({ source: src });
}

function changeDays(d) {
  if (d === currentDays.value) return;
  adminStore.fetchConsumptionAnalytics({ days: d });
}

async function doExport(format) {
  try {
    await adminStore.exportConsumptionAnalytics(format);
    uiStore.addNotification(`Export (${format.toUpperCase()}) downloaded.`, 'success');
  } catch (e) {
    console.error('Export failed:', e);
    uiStore.addNotification(`Export failed: ${e.message || e}`, 'error');
  }
}

onMounted(() => {
  // Only fetch if we have nothing yet, so panel switching stays snappy.
  if (!consolidated.value) refresh();
});
</script>

<style scoped>
.token-consumption-panel {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 0;
  color: var(--text-color, #1f2937);
}

/* Header */
.panel-header { display: flex; flex-direction: column; gap: 0.75rem; }
.panel-title-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem; }
.panel-title { display: flex; align-items: center; gap: 0.5rem; margin: 0; font-size: 1.15rem; font-weight: 700; }

.export-actions { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.export-footer {
  display: flex; align-items: center; justify-content: flex-end; gap: 0.75rem;
  padding: 0.85rem 1rem; border-radius: 0.75rem;
  background: var(--bg-elev, #fff); border: 1px solid var(--border-color, #e5e7eb);
}
.export-footer-label {
  font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;
  color: var(--text-muted, #6b7280);
}
.btn-export {
  display: inline-flex; align-items: center; gap: 0.35rem;
  padding: 0.35rem 0.7rem; border-radius: 0.5rem; font-size: 0.8rem; font-weight: 600;
  border: 1px solid var(--border-color, #d1d5db);
  background: var(--bg-elev, #fff); color: var(--text-color, #1f2937);
  cursor: pointer; transition: all 0.15s ease;
}
.btn-export:hover:not(:disabled) { background: var(--accent, #3b82f6); color: #fff; border-color: var(--accent, #3b82f6); }
.btn-export:disabled { opacity: 0.5; cursor: not-allowed; }

/* Controls */
.panel-controls { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.granularity-tabs {
  display: inline-flex; padding: 0.2rem; border-radius: 0.6rem;
  background: var(--bg-sunken, #f3f4f6); gap: 0.2rem;
}
.gran-tab {
  padding: 0.35rem 0.85rem; border-radius: 0.45rem; border: none;
  background: transparent; color: var(--text-muted, #6b7280);
  font-size: 0.85rem; font-weight: 600; cursor: pointer; transition: all 0.15s ease;
}
.gran-tab.active { background: var(--bg-elev, #fff); color: var(--accent, #3b82f6); box-shadow: 0 1px 3px rgba(0,0,0,0.1); }

.control-group { display: flex; align-items: center; gap: 0.4rem; }
.control-label { font-size: 0.78rem; font-weight: 600; color: var(--text-muted, #6b7280); }
.panel-select {
  padding: 0.35rem 0.6rem; border-radius: 0.5rem; font-size: 0.82rem;
  border: 1px solid var(--border-color, #d1d5db);
  background: var(--bg-elev, #fff); color: var(--text-color, #1f2937);
}
.btn-refresh {
  display: inline-flex; align-items: center; justify-content: center;
  width: 2rem; height: 2rem; border-radius: 0.5rem;
  border: 1px solid var(--border-color, #d1d5db);
  background: var(--bg-elev, #fff); cursor: pointer;
}

/* State */
.state-msg { display: flex; align-items: center; gap: 0.5rem; padding: 2rem; justify-content: center; color: var(--text-muted, #6b7280); }
.state-msg.error { color: #dc2626; }

/* KPI cards */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.75rem; }
.kpi-card {
  padding: 0.85rem 1rem; border-radius: 0.75rem;
  background: var(--bg-elev, #fff); border: 1px solid var(--border-color, #e5e7eb);
}
.kpi-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.03em; color: var(--text-muted, #6b7280); font-weight: 700; }
.kpi-value { font-size: 1.5rem; font-weight: 800; margin-top: 0.25rem; }
.kpi-value.small { font-size: 1rem; }
.kpi-sub { font-size: 0.78rem; color: var(--text-muted, #6b7280); margin-top: 0.25rem; display: flex; align-items: center; gap: 0.3rem; flex-wrap: wrap; }

/* Dots */
.dot { display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 50%; }
.dot.input { background: #3b82f6; }
.dot.output { background: #10b981; }
.dot.webui { background: #8b5cf6; }
.dot.api { background: #f59e0b; }

/* Charts */
.chart-card {
  padding: 1rem; border-radius: 0.75rem;
  background: var(--bg-elev, #fff); border: 1px solid var(--border-color, #e5e7eb);
}
.chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem; }
.chart-header h4 { margin: 0; font-size: 0.95rem; font-weight: 700; }
.chart-subtitle { font-weight: 400; color: var(--text-muted, #6b7280); font-size: 0.8rem; }
.chart-legend { display: flex; gap: 1rem; font-size: 0.78rem; color: var(--text-muted, #6b7280); }
.chart-legend span { display: inline-flex; align-items: center; gap: 0.35rem; }

.chart-area {
  display: flex; align-items: flex-end; gap: 3px;
  height: 180px; overflow-x: auto; padding-top: 0.5rem;
}
.bar-col { display: flex; flex-direction: column; align-items: center; min-width: 29px; flex: 1 0 auto; height: 100%; justify-content: flex-end; }
.bar-stack { display: flex; flex-direction: column; justify-content: flex-end; width: 70%; height: 100%; }
.bar-stack.side-by-side { flex-direction: row; align-items: flex-end; gap: 2px; width: 100%; }
.bar-segment { width: 100%; border-radius: 3px 3px 0 0; transition: height 0.25s ease; min-height: 1px; }
.bar-segment.input { background: #3b82f6; }
.bar-segment.output { background: #10b981; }
.bar-segment.webui { background: #8b5cf6; }
.bar-segment.api { background: #f59e0b; }
.bar-label { font-size: 0.62rem; color: var(--text-muted, #9ca3af); margin-top: 0.25rem; white-space: nowrap; transform: rotate(-35deg); transform-origin: center; height: 1.5rem; }
.chart-empty { margin: auto; color: var(--text-muted, #9ca3af); font-size: 0.85rem; }

/* Breakdown tables */
.breakdown-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
@media (max-width: 900px) { .breakdown-grid { grid-template-columns: 1fr; } }
.table-card { padding: 1rem; border-radius: 0.75rem; background: var(--bg-elev, #fff); border: 1px solid var(--border-color, #e5e7eb); }
.table-card h4 { margin: 0 0 0.6rem; font-size: 0.95rem; font-weight: 700; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.data-table th, .data-table td { padding: 0.4rem 0.5rem; text-align: left; border-bottom: 1px solid var(--border-color, #f3f4f6); }
.data-table th { font-weight: 700; color: var(--text-muted, #6b7280); font-size: 0.72rem; text-transform: uppercase; }
.data-table .num { text-align: right; font-variant-numeric: tabular-nums; }
.data-table .strong { font-weight: 700; }
.model-cell { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pct-badge {
  display: inline-block; padding: 0.1rem 0.45rem; border-radius: 0.75rem;
  background: var(--bg-sunken, #f3f4f6); font-size: 0.72rem; font-weight: 700;
}
.empty-cell { text-align: center; color: var(--text-muted, #9ca3af); padding: 1rem; }
</style>