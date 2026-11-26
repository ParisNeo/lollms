
<script setup>
import { ref, computed, onMounted } from 'vue';
import { Line, Bar } from 'vue-chartjs';
import {
  Chart as ChartJS,
  Title, Tooltip, Legend,
  LineElement, BarElement,
  CategoryScale, LinearScale, PointElement, TimeScale,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import apiClient from '../../services/api';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconTable from '../../assets/icons/IconTable.vue';
import IconDocumentText from '../../assets/icons/IconDocumentText.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconKey from '../../assets/icons/IconKey.vue';

ChartJS.register(
  Title, Tooltip, Legend,
  LineElement, BarElement,
  CategoryScale, LinearScale, PointElement, TimeScale,
);

const authStore = useAuthStore();
const uiStore = useUiStore();

const stats = ref(null);
const isLoading = ref(true);
const loadError = ref(null);

// Palette shared with the admin UserStatsModal so both surfaces read identically.
const COLOR_WEBUI = '#6366f1';   // indigo
const COLOR_API = '#f59e0b';     // amber
const COLOR_TOTAL = '#10b981';   // emerald
const COLOR_INPUT = '#0ea5e9';   // sky
const COLOR_OUTPUT = '#f43f5e';  // rose

const isDark = computed(() => document.documentElement.classList.contains('dark'));
const gridColor = computed(() => (isDark.value ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'));
const tickColor = computed(() => (isDark.value ? '#cbd5e1' : '#4b5563'));

function timeOptions({ yLabel = 'Count', stacked = false } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    scales: {
      x: {
        type: 'time',
        time: { unit: 'day', tooltipFormat: 'MMM d, yyyy', displayFormats: { day: 'MMM d' } },
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

const weekdayChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    x: { grid: { display: false }, ticks: { color: tickColor.value, font: { size: 10 } } },
    y: {
      beginAtZero: true,
      grid: { color: gridColor.value },
      ticks: { color: tickColor.value, precision: 1 },
      title: { display: true, text: 'Avg gens / day', color: tickColor.value, font: { size: 10 } },
    },
  },
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: (ctx) => `Avg: ${Number(ctx.parsed.y || 0).toFixed(2)} gens` } },
  },
}));

function buildDailyMap(series) {
  const map = new Map();
  for (let i = 29; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    map.set(d.toISOString().split('T')[0], 0);
  }
  (series || []).forEach((entry) => {
    if (entry?.date && map.has(entry.date)) map.set(entry.date, Number(entry.count) || 0);
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
      { label: 'WebUI tokens', data: labels.map((k) => webui.get(k) || 0), backgroundColor: COLOR_WEBUI, borderColor: COLOR_WEBUI, fill: true, tension: 0.15, pointRadius: 0 },
      { label: 'API tokens', data: labels.map((k) => api.get(k) || 0), backgroundColor: COLOR_API, borderColor: COLOR_API, fill: true, tension: 0.15, pointRadius: 0 },
    ],
  };
});

const inputOutputChartData = computed(() => {
  if (!stats.value) return { labels: [], datasets: [] };
  const prompt = buildDailyMap(stats.value.prompt_tokens_per_day);
  const completion = buildDailyMap(stats.value.completion_tokens_per_day);
  const labels = Array.from(prompt.keys());
  return {
    labels,
    datasets: [
      { label: 'Input (prompt) tokens', data: labels.map((k) => prompt.get(k) || 0), backgroundColor: COLOR_INPUT, borderColor: COLOR_INPUT, fill: true, tension: 0.15, pointRadius: 0 },
      { label: 'Output (completion) tokens', data: labels.map((k) => completion.get(k) || 0), backgroundColor: COLOR_OUTPUT, borderColor: COLOR_OUTPUT, fill: true, tension: 0.15, pointRadius: 0 },
    ],
  };
});

const hasInputOutputSeries = computed(() => Boolean(
  stats.value &&
  ((stats.value.prompt_tokens_per_day && stats.value.prompt_tokens_per_day.length) ||
   (stats.value.completion_tokens_per_day && stats.value.completion_tokens_per_day.length))
));

const generationChartData = computed(() => {
  if (!stats.value) return { labels: [], datasets: [] };
  const gens = buildDailyMap(stats.value.messages_per_day);
  const labels = Array.from(gens.keys());
  return {
    labels,
    datasets: [{ label: 'Generations', data: labels.map((k) => gens.get(k) || 0), backgroundColor: COLOR_TOTAL, borderColor: COLOR_TOTAL, fill: true, tension: 0.15, pointRadius: 0 }],
  };
});

const weekdayChartData = computed(() => {
  if (!stats.value) return { labels: [], datasets: [] };
  const order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const mean = stats.value.weekday_generation_mean || {};
  return {
    labels: order.map((d) => d.slice(0, 3)),
    datasets: [{ label: 'Avg generations', data: order.map((d) => Number(mean[d] || 0)), backgroundColor: COLOR_WEBUI, borderRadius: 6, maxBarThickness: 32 }],
  };
});

const summaryCards = computed(() => {
  if (!stats.value) return [];
  const s = stats.value;
  return [
    { label: 'Tokens · 7d', value: formatInt(s.tokens_last_7d), sub: `${formatInt(s.generations_last_7d)} generations`, accent: COLOR_TOTAL },
    { label: 'Tokens · 30d', value: formatInt(s.tokens_last_30d), sub: `${formatInt(s.generations_last_30d)} generations`, accent: COLOR_WEBUI },
    { label: 'Lifetime tokens', value: formatInt(s.total_tokens), sub: `Prompt ${formatInt(s.total_prompt_tokens)} · Completion ${formatInt(s.total_completion_tokens)}`, accent: COLOR_API },
    { label: 'WebUI / API split', value: `${s.source_breakdown?.webui_ratio ?? 0}% / ${s.source_breakdown?.api_ratio ?? 0}%`, sub: `${formatInt(s.source_breakdown?.webui_requests)} / ${formatInt(s.source_breakdown?.api_requests)} requests`, accent: COLOR_WEBUI },
  ];
});

const apiKeyUsage = computed(() => stats.value?.api_key_usage || []);
const apiKeyTotalTokens = computed(() => apiKeyUsage.value.reduce((sum, k) => sum + (Number(k.total_tokens) || 0), 0));

function formatInt(n) {
  return (Number(n) || 0).toLocaleString();
}

async function fetchStats() {
  isLoading.value = true;
  loadError.value = null;
  try {
    const response = await apiClient.get('/api/users/me/stats', { params: { days: 30 } });
    stats.value = response.data || null;
  } catch (error) {
    loadError.value = error?.response?.data?.detail || 'Could not load your statistics.';
    stats.value = null;
  } finally {
    isLoading.value = false;
  }
}

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
    const response = await apiClient.get('/api/users/me/stats/export', {
      params: { format, days: 30 },
      responseType: 'blob',
    });
    const blob = new Blob([response.data]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    link.setAttribute('download', `my_stats_${stamp}.${format}`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    uiStore.addNotification(`Export (${String(format).toUpperCase()}) downloaded.`, 'success');
  } catch (error) {
    uiStore.addNotification(`Export failed: ${error?.response?.data?.detail || error?.message || error}`, 'error');
  } finally {
    isExporting.value = false;
    exportingFormat.value = null;
  }
}

const identity = computed(() => {
  const u = authStore.user || {};
  return {
    username: u.username || '—',
    role: u.is_admin ? 'Admin' : (u.is_moderator ? 'Moderator' : 'User'),
    status: u.status || '—',
    email: u.email || '—',
    joined: u.created_at ? new Date(u.created_at).toLocaleDateString() : '—',
  };
});

onMounted(fetchStats);
</script>

<template>
  <div class="space-y-6">
    <!-- Header + export buttons -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div>
        <h3 class="text-lg font-bold text-gray-900 dark:text-white">Activity &amp; Tokens</h3>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Your personal usage telemetry, token consumption and carbon footprint.</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <button
          v-for="fmt in EXPORT_FORMATS"
          :key="fmt.value"
          @click="exportStats(fmt.value)"
          class="btn btn-secondary btn-sm flex items-center gap-1.5"
          :disabled="isExporting || isLoading"
          :title="fmt.title"
        >
          <IconAnimateSpin v-if="exportingFormat === fmt.value" class="w-4 h-4 animate-spin" />
          <component v-else :is="fmt.icon" class="w-4 h-4" />
          <span>{{ exportingFormat === fmt.value ? 'Exporting…' : fmt.label }}</span>
        </button>
        <button @click="fetchStats" class="btn btn-secondary btn-sm" :disabled="isLoading">Reload</button>
      </div>
    </div>

    <div v-if="isLoading" class="flex justify-center items-center h-72">
      <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
    </div>
    <div v-else-if="loadError || !stats" class="text-center h-72 flex flex-col items-center justify-center gap-3">
      <p class="text-gray-500">{{ loadError || 'Could not load your statistics.' }}</p>
      <button @click="fetchStats" class="btn btn-secondary btn-sm">Retry</button>
    </div>
    <div v-else class="space-y-6">
      <!-- Identity block -->
      <div class="rounded-2xl border p-4 flex flex-wrap items-center gap-x-6 gap-y-2"
           style="border-color: var(--border-main); background-color: var(--bg-card);">
        <div class="flex items-center gap-3 min-w-0">
          <div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-black"
               :style="{ backgroundColor: 'var(--brand-primary, #6366f1)', color: '#fff' }">
            {{ (identity.username || '?').slice(0, 1).toUpperCase() }}
          </div>
          <div class="min-w-0">
            <div class="text-sm font-black truncate" style="color: var(--text-main);">{{ identity.username }}</div>
            <div class="text-[10px] font-mono truncate" style="color: var(--text-dim);">{{ identity.email }}</div>
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px]">
          <div><span class="uppercase text-[9px] font-black tracking-widest" style="color: var(--text-dim);">Role</span><span class="ml-1 font-bold" style="color: var(--text-main);">{{ identity.role }}</span></div>
          <div><span class="uppercase text-[9px] font-black tracking-widest" style="color: var(--text-dim);">Status</span><span class="ml-1 font-bold" style="color: var(--text-main);">{{ identity.status }}</span></div>
          <div><span class="uppercase text-[9px] font-black tracking-widest" style="color: var(--text-dim);">Joined</span><span class="ml-1 font-bold" style="color: var(--text-main);">{{ identity.joined }}</span></div>
        </div>
      </div>

      <!-- Summary cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div v-for="card in summaryCards" :key="card.label" class="rounded-2xl border p-4"
             style="border-color: var(--border-main); background-color: var(--bg-card);">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: card.accent }"></span>
            <span class="text-[10px] font-black uppercase tracking-widest" style="color: var(--text-dim);">{{ card.label }}</span>
          </div>
          <div class="mt-1 text-2xl font-black font-mono" style="color: var(--text-main);">{{ card.value }}</div>
          <div class="text-[10px] mt-1 font-mono truncate" style="color: var(--text-dim);">{{ card.sub }}</div>
        </div>
      </div>

      <!-- Input vs Output tokens -->
      <div v-if="hasInputOutputSeries" class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
        <div class="flex items-center justify-between mb-3">
          <h4 class="text-sm font-black tracking-tight" style="color: var(--text-main);">Input vs Output tokens <span class="text-[10px] font-mono opacity-60">(30d)</span></h4>
          <span class="text-[10px] font-mono" style="color: var(--text-dim);">Prompt {{ formatInt(stats.total_prompt_tokens) }} · Completion {{ formatInt(stats.total_completion_tokens) }}</span>
        </div>
        <div class="h-64"><Line :data="inputOutputChartData" :options="tokenChartOptions" /></div>
      </div>

      <!-- Tokens (WebUI vs API) -->
      <div class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
        <div class="flex items-center justify-between mb-3">
          <h4 class="text-sm font-black tracking-tight" style="color: var(--text-main);">Tokens per day <span class="text-[10px] font-mono opacity-60">(WebUI vs API · 30d)</span></h4>
          <span class="text-[10px] font-mono" style="color: var(--text-dim);">Total 30d: {{ formatInt(stats.tokens_last_30d) }}</span>
        </div>
        <div class="h-64"><Line :data="tokenChartData" :options="tokenChartOptions" /></div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
          <div class="flex items-center justify-between mb-3">
            <h4 class="text-sm font-black tracking-tight" style="color: var(--text-main);">Generations per day</h4>
            <span class="text-[10px] font-mono" style="color: var(--text-dim);">Total 30d: {{ formatInt(stats.total_generations_30d) }}</span>
          </div>
          <div class="h-56"><Line :data="generationChartData" :options="generationChartOptions" /></div>
        </div>
        <div class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
          <div class="flex items-center justify-between mb-3">
            <h4 class="text-sm font-black tracking-tight" style="color: var(--text-main);">Weekday profile</h4>
            <span class="text-[10px] font-mono" style="color: var(--text-dim);">Avg gens / weekday · 30d</span>
          </div>
          <div class="h-56"><Bar :data="weekdayChartData" :options="weekdayChartOptions" /></div>
        </div>
      </div>

      <!-- Usage by API key -->
      <div class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
        <div class="flex items-center justify-between mb-3">
          <h4 class="text-sm font-black tracking-tight flex items-center gap-1.5" style="color: var(--text-main);">
            <IconKey class="w-4 h-4" style="color: var(--brand-primary, #6366f1);" /> Usage by API key
          </h4>
          <span class="text-[10px] font-mono" style="color: var(--text-dim);">Key-attributed total: {{ formatInt(apiKeyTotalTokens) }} tokens</span>
        </div>
        <div v-if="!apiKeyUsage.length" class="rounded-xl border border-dashed py-8 text-center"
             style="border-color: var(--border-main);">
          <p class="text-xs" style="color: var(--text-dim);">No API keys or no consumption recorded. Create keys in the API Keys section to track usage here.</p>
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-left uppercase text-[9px] font-black tracking-widest" style="color: var(--text-dim);">
                <th class="py-2 pr-3">Key</th>
                <th class="py-2 px-3">Prefix</th>
                <th class="py-2 px-3 text-right">Tokens</th>
                <th class="py-2 px-3 text-right">Prompt</th>
                <th class="py-2 px-3 text-right">Completion</th>
                <th class="py-2 px-3 text-right">Calls</th>
                <th class="py-2 pl-3">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="k in apiKeyUsage" :key="k.api_key_id" class="border-t" style="border-color: var(--border-main);">
                <td class="py-2 pr-3 font-semibold truncate max-w-[16rem]" style="color: var(--text-main);">{{ k.name || ('Key #' + k.api_key_id) }}</td>
                <td class="py-2 px-3 font-mono" style="color: var(--text-dim);">{{ k.key_prefix || '—' }}</td>
                <td class="py-2 px-3 text-right font-mono" style="color: var(--text-main);">{{ formatInt(k.total_tokens) }}</td>
                <td class="py-2 px-3 text-right font-mono" style="color: var(--text-dim);">{{ formatInt(k.prompt_tokens) }}</td>
                <td class="py-2 px-3 text-right font-mono" style="color: var(--text-dim);">{{ formatInt(k.completion_tokens) }}</td>
                <td class="py-2 px-3 text-right font-mono" style="color: var(--text-dim);">{{ formatInt(k.calls) }}</td>
                <td class="py-2 pl-3">
                  <span class="text-[10px] font-bold px-2 py-0.5 rounded-full"
                        :style="k.is_active ? 'background:rgba(16,185,129,.15);color:#059669;' : 'background:rgba(107,114,128,.15);color:#6b7280;'">
                    {{ k.is_active ? 'Active' : 'Revoked' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Top models -->
      <div v-if="stats.top_models?.length" class="rounded-2xl border p-4" style="border-color: var(--border-main); background-color: var(--bg-card);">
        <h4 class="text-sm font-black tracking-tight mb-3" style="color: var(--text-main);">Top models</h4>
        <div class="space-y-2">
          <div v-for="m in stats.top_models" :key="m.model_name" class="flex items-center justify-between gap-3 text-xs">
            <span class="font-mono truncate" style="color: var(--brand-text-main);">{{ m.model_name || 'unknown' }}</span>
            <span class="font-mono shrink-0" style="color: var(--text-dim);">{{ formatInt(m.total_tokens) }} tokens <span class="opacity-60 ml-1">· {{ formatInt(m.count) }} gens</span></span>
          </div>
        </div>
      </div>

      <!-- Carbon footprint -->
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
  </div>
</template>
