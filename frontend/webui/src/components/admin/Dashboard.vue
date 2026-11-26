
<template>
  <div class="dashboard-root">
    <!-- Tab bar -->
    <div class="dash-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['dash-tab', { active: activeTab === tab.id }]"
        @click="selectTab(tab.id)"
      >
        <component :is="tab.icon" class="w-4 h-4" />
        <span>{{ tab.label }}</span>
      </button>
      <button class="dash-refresh" :disabled="refreshing" @click="refreshActive" title="Refresh">
        <IconArrowPath :class="['w-4 h-4', { 'animate-spin': refreshing }]" />
      </button>
    </div>

    <!-- ── OVERVIEW ── -->
    <section v-show="activeTab === 'overview'" class="tab-panel">
      <div class="stat-grid">
        <div class="stat-card" v-for="s in overviewStats" :key="s.key">
          <div class="stat-icon" :style="{ color: s.color }">
            <component :is="s.icon" class="w-5 h-5" />
          </div>
          <div class="stat-body">
            <div class="stat-value">{{ s.value }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </div>
        </div>
      </div>

      <div class="chart-grid">
        <GlobalStatsChart
          :stats="adminStore.globalGenerationStats"
          :is-loading="adminStore.isLoadingGlobalGenerationStats"
        />
        <ModelUsageChart />
      </div>
    </section>

    <!-- ── TOKEN CONSUMPTION ── -->
    <section v-show="activeTab === 'consumption'" class="tab-panel">
      <TokenConsumptionPanel />
    </section>

    <!-- ── TOP USERS ── -->
    <section v-show="activeTab === 'topusers'" class="tab-panel">
      <div class="topusers-controls">
        <div class="control-group">
          <label>Source</label>
          <select :value="topUsersParams.source || 'all'" @change="onTopSource($event.target.value)">
            <option value="all">All</option>
            <option value="webui">WebUI</option>
            <option value="api">API</option>
          </select>
        </div>
        <div class="control-group">
          <label>Metric</label>
          <select :value="topUsersParams.metric" @change="onTopMetric($event.target.value)">
            <option value="total_tokens">Total Tokens</option>
            <option value="prompt_tokens">Input Tokens</option>
            <option value="completion_tokens">Output Tokens</option>
            <option value="calls">Calls</option>
          </select>
        </div>
        <div class="control-group">
          <label>Window</label>
          <select :value="topUsersParams.days" @change="onTopDays(Number($event.target.value))">
            <option :value="0">All time</option>
            <option :value="1">24 hours</option>
            <option :value="7">7 days</option>
            <option :value="30">30 days</option>
            <option :value="90">90 days</option>
          </select>
        </div>
      </div>

      <div class="table-card">
        <div v-if="isLoadingTopUsers" class="table-state">Loading…</div>
        <div v-else-if="!topUsers.length" class="table-state">No usage recorded for this filter.</div>
        <table v-else class="data-table">
          <thead>
            <tr>
              <th>#</th><th>User</th><th class="num">Input</th>
              <th class="num">Output</th><th class="num">Total</th><th class="num">Calls</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(u, i) in topUsers" :key="u.user_id || u.username">
              <td class="rank">{{ i + 1 }}</td>
              <td class="user-cell">{{ u.username }}</td>
              <td class="num">{{ fmt(u.prompt_tokens) }}</td>
              <td class="num">{{ fmt(u.completion_tokens) }}</td>
              <td class="num strong">{{ fmt(u.total_tokens) }}</td>
              <td class="num">{{ fmt(u.calls) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useAdminStore } from '../../stores/admin';
import GlobalStatsChart from './GlobalStatsChart.vue';
import ModelUsageChart from './ModelUsageChart.vue';
import TokenConsumptionPanel from './TokenConsumptionPanel.vue';

import IconDashboard from '../../assets/icons/IconDashboard.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconUserGroup from '../../assets/icons/IconUserGroup.vue';
import IconUser from '../../assets/icons/IconUser.vue';
import IconChatBubbleLeftRight from '../../assets/icons/IconChatBubbleLeftRight.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconShieldCheck from '../../assets/icons/IconShieldCheck.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';

const props = defineProps({
  onNavigate: { type: Function, default: null },
});

const adminStore = useAdminStore();
const activeTab = ref('overview');
const refreshing = ref(false);

const tabs = [
  { id: 'overview', label: 'Overview', icon: IconDashboard },
  { id: 'consumption', label: 'Token Consumption', icon: IconPresentationChartBar },
  { id: 'topusers', label: 'Top Users', icon: IconUserGroup },
];

const stats = computed(() => adminStore.dashboardStats || {});
const topUsers = computed(() => adminStore.topUsers || []);
const isLoadingTopUsers = computed(() => adminStore.isLoadingTopUsers);
const topUsersParams = computed(() => adminStore.topUsersParams || { source: null, metric: 'total_tokens', days: 0, limit: 10 });

function fmt(n) {
  return (Number(n) || 0).toLocaleString();
}
function dash(label, icon, color) {
  const v = stats.value?.[arguments[3]] ?? stats.value?.[label];
  return { key: label, label, value: v ?? '—', icon, color };
}

const overviewStats = computed(() => {
  const s = stats.value;
  return [
    { key: 'users', label: 'Total Users', value: s?.total_users ?? '—', icon: IconUserGroup, color: '#3b82f6' },
    { key: 'active', label: 'Active Today', value: s?.active_today ?? '—', icon: IconSparkles, color: '#10b981' },
    { key: 'discussions', label: 'Discussions', value: s?.total_discussions ?? '—', icon: IconChatBubbleLeftRight, color: '#8b5cf6' },
    { key: 'messages', label: 'Messages', value: s?.total_messages ?? '—', icon: IconChatBubbleLeftRight, color: '#f59e0b' },
    { key: 'connected', label: 'Connected', value: s?.connected_users ?? '—', icon: IconServer, color: '#0ea5e9' },
    { key: 'admins', label: 'Admins', value: s?.admin_users ?? '—', icon: IconShieldCheck, color: '#ef4444' },
  ];
});

async function refreshActive() {
  refreshing.value = true;
  try {
    if (activeTab.value === 'overview') {
      await Promise.all([
        adminStore.fetchDashboardStats(),
        // ``force=true`` so the Refresh button actually refreshes the chart
        // instead of being a silent no-op when the cache is already warm.
        adminStore.fetchGlobalGenerationStats(true),
        adminStore.fetchModelUsageStats(),
      ]);
    } else if (activeTab.value === 'consumption') {
      await adminStore.fetchConsumptionAnalytics();
    } else if (activeTab.value === 'topusers') {
      await adminStore.fetchTopUsers();
    }
  } finally {
    refreshing.value = false;
  }
}

function selectTab(id) {
  activeTab.value = id;
  // Load lazily the first time a tab is opened; cached store data short-circuits.
  if (id === 'topusers' && !topUsers.value.length) adminStore.fetchTopUsers();
  if (id === 'consumption' && !adminStore.consumptionAnalytics) adminStore.fetchConsumptionAnalytics();
}

function onTopSource(v) { adminStore.fetchTopUsers({ source: v === 'all' ? null : v }); }
function onTopMetric(v) { adminStore.fetchTopUsers({ metric: v }); }
function onTopDays(v) { adminStore.fetchTopUsers({ days: v }); }

onMounted(() => {
  // Fetch everything the Overview tab needs on first mount. Previously only
  // ``fetchDashboardStats`` was called, leaving ``globalGenerationStats``
  // forever null -> the GlobalStatsChart component received ``stats=null``
  // and rendered its "Could not load statistics." empty state, even though
  // the backend endpoint was healthy.
  adminStore.fetchDashboardStats();
  adminStore.fetchGlobalGenerationStats();
  adminStore.fetchModelUsageStats();
});
</script>

<style scoped>
.dashboard-root { display: flex; flex-direction: column; gap: 1rem; }
.dash-tabs { display: flex; align-items: center; gap: 0.25rem; flex-wrap: wrap; border-bottom: 1px solid var(--border-main, #e5e7eb); padding-bottom: 0.5rem; }
.dash-tab {
  display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.45rem 0.9rem;
  border-radius: 0.6rem; border: none; background: transparent; cursor: pointer;
  font-size: 0.85rem; font-weight: 600; color: var(--text-dim, #6b7280); transition: all 0.15s ease;
}
.dash-tab.active { background: var(--bg-card, #fff); color: #3b82f6; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.dash-refresh { margin-left: auto; display: inline-flex; align-items: center; justify-content: center; width: 2rem; height: 2rem; border-radius: 0.5rem; border: 1px solid var(--border-main, #e5e7eb); background: var(--bg-card, #fff); cursor: pointer; }
.tab-panel { display: flex; flex-direction: column; gap: 1rem; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.75rem; }
.stat-card { display: flex; align-items: center; gap: 0.75rem; padding: 0.85rem 1rem; border-radius: 0.75rem; background: var(--bg-card, #fff); border: 1px solid var(--border-main, #e5e7eb); }
.stat-value { font-size: 1.4rem; font-weight: 800; }
.stat-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.03em; color: var(--text-dim, #6b7280); font-weight: 700; }
.chart-grid { display: grid; grid-template-columns: 1fr; gap: 1rem; }
.topusers-controls { display: flex; gap: 1rem; flex-wrap: wrap; }
.control-group { display: flex; align-items: center; gap: 0.4rem; }
.control-group label { font-size: 0.78rem; font-weight: 600; color: var(--text-dim, #6b7280); }
.control-group select { padding: 0.35rem 0.6rem; border-radius: 0.5rem; font-size: 0.82rem; border: 1px solid var(--border-main, #d1d5db); background: var(--bg-card, #fff); }
.table-card { padding: 1rem; border-radius: 0.75rem; background: var(--bg-card, #fff); border: 1px solid var(--border-main, #e5e7eb); }
.table-state { text-align: center; color: var(--text-dim, #9ca3af); padding: 1.5rem; font-size: 0.85rem; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.data-table th, .data-table td { padding: 0.45rem 0.5rem; text-align: left; border-bottom: 1px solid var(--border-main, #f3f4f6); }
.data-table th { font-weight: 700; color: var(--text-dim, #6b7280); font-size: 0.72rem; text-transform: uppercase; }
.data-table .num { text-align: right; font-variant-numeric: tabular-nums; }
.data-table .strong { font-weight: 700; }
.rank { font-weight: 800; color: var(--text-dim, #9ca3af); width: 2rem; }
.user-cell { font-weight: 600; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
