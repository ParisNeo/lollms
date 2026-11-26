<script setup>
import { ref, computed, watch } from 'vue';
import { Line, Bar } from 'vue-chartjs';
import {
  Chart as ChartJS,
  Title, Tooltip, Legend,
  LineElement, BarElement,
  CategoryScale, LinearScale, PointElement, TimeScale,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../modals/GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconTable from '../../assets/icons/IconTable.vue';
import IconDocumentText from '../../assets/icons/IconDocumentText.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import TokenQuotaPanel from './TokenQuotaPanel.vue';

ChartJS.register(
  Title, Tooltip, Legend,
  LineElement, BarElement,
  CategoryScale, LinearScale, PointElement, TimeScale,
);

const props = defineProps({
  userId: { type: Number, required: true },
  username: { type: String, required: true },
  // Full user record (optional) so the identity block can show role/status/
  // email without an extra round-trip. Falls back gracefully when absent.
  user: { type: Object, default: null },
});

const adminStore = useAdminStore();
const uiStore = useUiStore();
const stats = ref(null);
const isLoading = ref(true);

// Palette shared across all charts so WebUI (indigo) vs API (amber) is
// consistently recognisable across the two timeseries charts.
const COLOR_WEBUI = '#6366f1';  // indigo-500
const COLOR_API = '#f59e0b';    // amber-500
const COLOR_TOTAL = '#10b981';  // emerald-500
const COLOR_TASKS = '#3b82f6';  // blue-500
const COLOR_INPUT = '#0ea5e9';  // sky-500  (prompt tokens)
const COLOR_OUTPUT = '#f43f5e'; // rose-500 (completion tokens)

const themeColor = (dark, light) => (uiStore.currentTheme === 'dark' ? dark : light);
const gridColor = computed(() => themeColor('rgba(255,255,255,0.08)', 'rgba(0,0,0,0.08)'));
const tickColor = computed(() => themeColor('#cbd5e1', '#4b5563'));

// ── Shared time-aware chart options (token chart, generation chart) ────────
function timeOptions({ yLabel = 'Count', stacked = false } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      x: {
        type: 'time',
        time: {
          unit: 'day',
          tooltipFormat: 'MMM d, yyyy',
          displayFormats: { day: 'MMM d' },
        },
        grid: { color: gridColor.value },
        ticks: { color: tickColor.value, maxRotation: 0, autoSkip: true, autoSkipPadding: 16 },
        stacked,
      },
      y: {
        beginAtZero: true,
        grid: { color: gridColor.value },
        ticks: { color: tickColor.value, precision: 0 },
        stacked,
        title: { display: true, text: yLabel, color: tickColor.value, font: { size: 10 } },
      },
    },
    plugins: {
      legend: { labels: { color: tickColor.value, boxWidth: 12, boxHeight: 12, font: { size: 11 } } },
    },
  };
}

const tokenChartOptions = computed(() => timeOptions({ yLabel: 'Tokens', stacked: true }));
const generationChartOptions = computed(() => timeOptions({ yLabel: 'Generations', stacked: true }));

// ── Weekday profile bar chart options ──────────────────────────────────────
const weekdayChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    x: {
      grid: { display: false },
      ticks: { color: tickColor.value, font: { size: 10 } },
    },
    y: {
      beginAtZero: true,
      grid: { color: gridColor.value },
      ticks: { color: tickColor.value, precision: 1 },
      title: { display: true, text: 'Avg gens / day', color: tickColor.value, font: { size: 10 } },
    },
  },
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx) => `Avg: ${Number(ctx.parsed.y || 0).toFixed(2)} gens`,
      },
    },
  },
}));

// ── Datasets ──────────────────────────────────────────────────────────────

// Builds a 30-day bucket map so a day with zero activity still renders as 0
// instead of creating a visual gap in the line.
function buildDailyMap(series) {
  const map = new Map();
  for (let i = 29; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    map.set(d.toISOString().split('T')[0], 0);
  }
  (series || []).forEach((entry) => {
    if (entry?.date && map.has(entry.date)) {
      map.set(entry.date, Number(entry.count) || 0);
    }
  });
  return map;
}

const tokenChartData = computed(() => {
  if (!stats.value) return { labels: [], datasets: [] };
  const webui = buildDailyMap(stats.value.webui_tokens_per_day);
  const api = buildDailyMap(stats.value.api_tokens_per_day);
  const labels = Array.from(webui.keys());
  return {
    labels,
    datasets: [
      {
        label: 'WebUI tokens',
        data: labels.map((k) => webui.get(k) || 0),
        backgroundColor: COLOR_WEBUI,
        borderColor: COLOR_WEBUI,
        fill: true,
        tension: 0.15,
        pointRadius: 0,
      },
      {
        label: 'API tokens',
        data: labels.map((k) => api.get(k) || 0),
        backgroundColor: COLOR_API,
        borderColor: COLOR_API,
        fill: true,
        tension: 0.15,
        pointRadius: 0,
      },
    ],
  };
});

// Input (prompt) vs Output (completion) tokens per day. These are billed /
// consumed differently, so they are charted together but as distinct curves.
// Falls back gracefully to empty arrays when the backend omits the series.
const inputOutputChartData = computed(() => {
  if (!stats.value) return { labels: [], datasets: [] };
  const prompt = buildDailyMap(stats.value.prompt_tokens_per_day);
  const completion = buildDailyMap(stats.value.completion_tokens_per_day);
  const labels = Array.from(prompt.keys());
  return {
    labels,
    datasets: [
      {
        label: 'Input (prompt) tokens',
        data: labels.map((k) => prompt.get(k) || 0),
        backgroundColor: COLOR_INPUT,
        borderColor: COLOR_INPUT,
        fill: true,
        tension: 0.15,
        pointRadius: 0,
      },
      {
        label: 'Output (completion) tokens',
        data: labels.map((k) => completion.get(k) || 0),
        backgroundColor: COLOR_OUTPUT,
        borderColor: COLOR_OUTPUT,
        fill: true,
        tension: 0.15,
        pointRadius: 0,
      },
    ],
  };
});

const hasInputOutputSeries = computed(() =>
  Boolean(
    stats.value &&
    ((stats.value.prompt_tokens_per_day && stats.value.prompt_tokens_per_day.length) ||
     (stats.value.completion_tokens_per_day && stats.value.completion_tokens_per_day.length))
  )
);

const generationChartData = computed(() => {
  if (!stats.value) return { labels: [], datasets: [] };
  const webui = buildDailyMap(stats.value.messages_per_day);
  // messages_per_day carries the total; WebUI-only count lives inside
  // webui_tokens_per_day's companion... actually generations are not split
  // by source on the response; we show the total to keep this chart honest.
  const labels = Array.from(webui.keys());
  return {
    labels,
    datasets: [
      {
        label: 'Generations',
        data: labels.map((k) => webui.get(k) || 0),
        backgroundColor: COLOR_TOTAL,
        borderColor: COLOR_TOTAL,
        fill: true,
        tension: 0.15,
        pointRadius: 0,
      },
    ],
  };
});

const weekdayChartData = computed(() => {
  if (!stats.value) return { labels: [], datasets: [] };
  const order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const mean = stats.value.weekday_generation_mean || {};
  return {
    labels: order.map((d) => d.slice(0, 3)),
    datasets: [
      {
        label: 'Avg generations',
        data: order.map((d) => Number(mean[d] || 0)),
        backgroundColor: COLOR_WEBUI,
        borderRadius: 6,
        maxBarThickness: 32,
      },
    ],
  };
});

// ── Summary cards ─────────────────────────────────────────────────────────
const summaryCards = computed(() => {
  if (!stats.value) return [];
  const s = stats.value;
  return [
    {
      label: 'Tokens · 7d',
      value: formatInt(s.tokens_last_7d),
      sub: `${formatInt(s.generations_last_7d)} generations`,
      accent: COLOR_TOTAL,
    },
    {
      label: 'Tokens · 30d',
      value: formatInt(s.tokens_last_30d),
      sub: `${formatInt(s.generations_last_30d)} generations`,
      accent: COLOR_WEBUI,
    },
    {
      label: 'Lifetime tokens',
      value: formatInt(s.total_tokens),
      sub: `Prompt ${formatInt(s.total_prompt_tokens)} · Completion ${formatInt(s.total_completion_tokens)}`,
      accent: COLOR_API,
    },
    {
      label: 'WebUI / API split',
      value: `${s.source_breakdown?.webui_ratio ?? 0}% / ${s.source_breakdown?.api_ratio ?? 0}%`,
      sub: `${formatInt(s.source_breakdown?.webui_requests)} / ${formatInt(s.source_breakdown?.api_requests)} requests`,
      accent: COLOR_WEBUI,
    },
  ];
});

function formatInt(n) {
  const num = Number(n) || 0;
  return num.toLocaleString();
}

// ── Data loading ──────────────────────────────────────────────────────────
async function fetchStats() {
  isLoading.value = true;
  // Reset so a previously-viewed user's numbers never linger while the next
  // user's payload is loading (prevents cross-user data mingling in the UI).
  stats.value = null;
  try {
    stats.value = await adminStore.fetchUserStats(props.userId);
  } finally {
    isLoading.value = false;
  }
}

// ── Export (HTML / PDF / DOCX / XLSX) — strictly scoped to this user's id ─
// The backend reuses the same aggregation as the modal, so every format is
// guaranteed to match what the admin is currently looking at.
const EXPORT_FORMATS = [
  { value: 'xlsx', label: 'XLSX', icon: IconTable, title: 'Excel workbook with charts & tables' },
  { value: 'html', label: 'HTML', icon: IconDocumentText, title: 'Standalone HTML report' },
  { value: 'docx', label: 'DOCX', icon: IconFileText, title: 'Word document report' },
  { value: 'pdf', label: 'PDF', icon: IconPresentationChartBar, title: 'Print-ready PDF report' },
];
const isExporting = ref(false);
const exportingFormat = ref(null);
async function exportStats(format) {
  if (isExporting.value) return;
  isExporting.value = true;
  exportingFormat.value = format;
  try {
    await adminStore.exportUserStats(props.userId, format);
    uiStore.addNotification(`Export (${String(format).toUpperCase()}) downloaded.`, 'success');
  } catch (e) {
    uiStore.addNotification(`Export failed: ${e?.message || e}`, 'error');
  } finally {
    isExporting.value = false;
    exportingFormat.value = null;
  }
}

// ── Identity block — derived from the optional `user` prop ────────────────
const identity = computed(() => {
  const u = props.user || {};
  const role = u.is_admin ? 'Admin' : (u.is_moderator ? 'Moderator' : 'User');
  return {
    username: u.username || props.username,
    id: u.id ?? props.userId,
    role,
    status: u.status || '—',
    email: u.email || '—',
    joined: u.created_at ? new Date(u.created_at).toLocaleDateString() : '—',
    lastSeen: u.last_activity_at ? new Date(u.last_activity_at).toLocaleString() : 'Never',
  };
});

function exportChart() {
  const chart = chartRef.value?.chart;
  if (chart) {
    const link = document.createElement('a');
    link.href = chart.toBase64Image('image/png', 1);
    link.download = `user_stats_${props.username}.png`;
    link.click();
  } else {
    uiStore.addNotification('Open a chart tab before exporting.', 'warning');
  }
}

watch(() => props.userId, (newId) => {
  if (newId) fetchStats();
}, { immediate: true });
</script>

<template>
  <GenericModal modalName="userStats" :title="`Usage Statistics for ${username}`" maxWidthClass="max-w-6xl">
    <template #body>
      <div v-if="isLoading" class="flex justify-center items-center h-96">
        <IconAnimateSpin class="w-8 h-8 text-blue-500" />
      </div>
      <div v-else-if="!stats" class="text-center h-96 flex items-center justify-center">
        <p class="text-gray-500">Could not load statistics for this user.</p>
      </div>
      <div v-else class="space-y-6">
        <!-- Identity block: who these stats belong to (prevents cross-user confusion) -->
        <div class="rounded-2xl border p-4 flex flex-wrap items-center gap-x-6 gap-y-2"
             style="border-color: var(--border-main); background-color: var(--bg-card);">
          <div class="flex items-center gap-3 min-w-0">
            <div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-black"
                 :style="{ backgroundColor: 'var(--brand-primary, #6366f1)', color: '#fff' }">
              {{ (identity.username || '?').slice(0, 1).toUpperCase() }}
            </div>
            <div class="min-w-0">
              <div class="text-sm font-black truncate" style="color: var(--text-main);">{{ identity.username }}</div>
              <div class="text-[10px] font-mono truncate" style="color: var(--text-dim);">
                ID {{ identity.id }} · {{ identity.email }}
              </div>
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px]">
            <div>
              <span class="uppercase text-[9px] font-black tracking-widest" style="color: var(--text-dim);">Role</span>
              <span class="ml-1 font-bold" style="color: var(--text-main);">{{ identity.role }}</span>
            </div>
            <div>
              <span class="uppercase text-[9px] font-black tracking-widest" style="color: var(--text-dim);">Status</span>
              <span class="ml-1 font-bold" style="color: var(--text-main);">{{ identity.status }}</span>
            </div>
            <div>
              <span class="uppercase text-[9px] font-black tracking-widest" style="color: var(--text-dim);">Joined</span>
              <span class="ml-1 font-bold" style="color: var(--text-main);">{{ identity.joined }}</span>
            </div>
            <div>
              <span class="uppercase text-[9px] font-black tracking-widest" style="color: var(--text-dim);">Last seen</span>
              <span class="ml-1 font-bold" style="color: var(--text-main);">{{ identity.lastSeen }}</span>
            </div>
          </div>
        </div>

        <!-- Summary cards -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div
            v-for="card in summaryCards"
            :key="card.label"
            class="rounded-2xl border p-4"
            style="border-color: var(--border-main); background-color: var(--bg-card);"
          >
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: card.accent }"></span>
              <span class="text-[10px] font-black uppercase tracking-widest" style="color: var(--text-dim);">
                {{ card.label }}
              </span>
            </div>
            <div class="mt-1 text-2xl font-black font-mono" style="color: var(--text-main);">
              {{ card.value }}
            </div>
            <div class="text-[10px] mt-1 font-mono truncate" style="color: var(--text-dim);">
              {{ card.sub }}
            </div>
          </div>
        </div>

        <!-- Token quota management (admin controls) -->
        <TokenQuotaPanel :user-id="userId" :username="username" />

        <!-- Input vs Output tokens per day (distinct cost curves) -->
        <div v-if="hasInputOutputSeries" class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
          <div class="flex items-center justify-between mb-3">
            <h4 class="text-sm font-black tracking-tight" style="color: var(--text-main);">
              Input vs Output tokens <span class="text-[10px] font-mono opacity-60">(30d)</span>
            </h4>
            <span class="text-[10px] font-mono" style="color: var(--text-dim);">
              Prompt {{ formatInt(stats.total_prompt_tokens) }} · Completion {{ formatInt(stats.total_completion_tokens) }}
            </span>
          </div>
          <div class="h-64">
            <Line :data="inputOutputChartData" :options="tokenChartOptions" />
          </div>
        </div>

        <!-- Tokens chart (WebUI vs API) -->
        <div class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
          <div class="flex items-center justify-between mb-3">
            <h4 class="text-sm font-black tracking-tight" style="color: var(--text-main);">
              Tokens per day <span class="text-[10px] font-mono opacity-60">(WebUI vs API · 30d)</span>
            </h4>
            <span class="text-[10px] font-mono" style="color: var(--text-dim);">
              Total 30d: {{ formatInt(stats.tokens_last_30d) }}
            </span>
          </div>
          <div class="h-64">
            <Line :data="tokenChartData" :options="tokenChartOptions" />
          </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <!-- Generations chart -->
          <div class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-black tracking-tight" style="color: var(--text-main);">Generations per day</h4>
              <span class="text-[10px] font-mono" style="color: var(--text-dim);">
                Total 30d: {{ formatInt(stats.total_generations_30d) }}
              </span>
            </div>
            <div class="h-56">
              <Line :data="generationChartData" :options="generationChartOptions" />
            </div>
          </div>

          <!-- Weekday profile -->
          <div class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-sm font-black tracking-tight" style="color: var(--text-main);">Weekday profile</h4>
              <span class="text-[10px] font-mono" style="color: var(--text-dim);">Avg gens / weekday · 30d</span>
            </div>
            <div class="h-56">
              <Bar :data="weekdayChartData" :options="weekdayChartOptions" />
            </div>
          </div>
        </div>

        <!-- Top models -->
        <div v-if="stats.top_models?.length" class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
          <h4 class="text-sm font-black tracking-tight mb-3" style="color: var(--text-main);">Top models</h4>
          <div class="space-y-2">
            <div
              v-for="m in stats.top_models"
              :key="m.model_name"
              class="flex items-center justify-between gap-3 text-xs"
            >
              <span class="font-mono truncate" style="color: var(--brand-text-main);">{{ m.model_name || 'unknown' }}</span>
              <span class="font-mono shrink-0" style="color: var(--text-dim);">
                {{ formatInt(m.total_tokens) }} tokens
                <span class="opacity-60 ml-1">· {{ formatInt(m.count) }} gens</span>
              </span>
            </div>
          </div>
        </div>

        <!-- Carbon footprint (always rendered so a fresh account shows explicit
             zeroes rather than silently hiding the whole section, which previously
             made users think the feature was broken/missing). -->
        <div class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
          <h4 class="text-sm font-black tracking-tight mb-2" style="color: var(--text-main);">Carbon footprint (lifetime)</h4>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div>
              <div class="text-[10px] uppercase" style="color: var(--text-dim);">Energy</div>
              <div class="font-mono font-bold" style="color: var(--text-main);">{{ stats.total_energy_kwh }} kWh</div>
            </div>
            <div>
              <div class="text-[10px] uppercase" style="color: var(--text-dim);">CO₂</div>
              <div class="font-mono font-bold" style="color: var(--text-main);">{{ stats.total_co2_g }} g</div>
            </div>
            <div v-for="(v, k) in stats.co2_equivalents" :key="k">
              <div class="text-[10px] uppercase" style="color: var(--text-dim);">{{ String(k).replace(/_/g, ' ') }}</div>
              <div class="font-mono font-bold" style="color: var(--text-main);">{{ v }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="fetchStats" class="btn btn-secondary" :disabled="isLoading">
        {{ isLoading ? 'Reloading...' : 'Reload Data' }}
      </button>
      <div class="grow"></div>
      <button
        v-for="fmt in EXPORT_FORMATS"
        :key="fmt.value"
        @click="exportStats(fmt.value)"
        class="btn btn-secondary flex items-center gap-1.5"
        :disabled="isExporting || isLoading"
        :title="fmt.title"
      >
        <IconAnimateSpin v-if="exportingFormat === fmt.value" class="w-4 h-4 animate-spin" />
        <component v-else :is="fmt.icon" class="w-4 h-4" />
        <span>{{ exportingFormat === fmt.value ? 'Exporting…' : fmt.label }}</span>
      </button>
      <button @click="uiStore.closeModal('userStats')" class="btn btn-primary">Close</button>
    </template>
  </GenericModal>
</template>