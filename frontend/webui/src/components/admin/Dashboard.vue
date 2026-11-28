
<template>
  <div class="dashboard-root">
    <!-- Tab bar -->
    <div class="dash-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['dash-tab', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        <component :is="tab.icon" class="dash-tab-icon" />
        <span>{{ tab.label }}</span>
      </button>
      <button class="dash-refresh" title="Refresh current tab" @click="refreshActiveTab">
        <IconArrowPath class="w-4 h-4" />
      </button>
    </div>

    <!-- ══════════════════ OVERVIEW (Operations Command Center) ══════════════════ -->
    <div v-if="activeTab === 'overview'" class="tab-panel">

      <!-- Alert summary banner -->
      <button
        class="alert-banner"
        :class="alertBannerClass"
        @click="activeTab = 'operations'"
      >
        <div class="alert-banner-left">
          <span class="alert-banner-dot" :class="alertDotClass"></span>
          <div>
            <div class="alert-banner-title">{{ alertHeadline }}</div>
            <div class="alert-banner-sub">
              {{ alertSummary.open }} open · {{ alertSummary.critical }} critical · {{ alertSummary.warning }} warning
            </div>
          </div>
        </div>
        <span class="alert-banner-cta">View alerts →</span>
      </button>

      <!-- KPI strip -->
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-icon sky"><IconUserGroup class="w-5 h-5" /></div>
          <div>
            <div class="stat-value">{{ stats.total_users ?? '—' }}</div>
            <div class="stat-label">Total users</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon emerald"><IconUserCircle class="w-5 h-5" /></div>
          <div>
            <div class="stat-value">{{ stats.active_users_24h ?? '—' }}</div>
            <div class="stat-label">Active (24h)</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon amber"><IconClock class="w-5 h-5" /></div>
          <div>
            <div class="stat-value" :class="stats.pending_approval > 0 ? 'text-amber-600' : ''">
              {{ stats.pending_approval ?? '—' }}
            </div>
            <div class="stat-label">Pending approval</div>
          </div>
        </div>
        <button
          class="stat-card stat-card-action"
          :class="warningsKpiClass"
          @click="activeTab = 'operations'"
        >
          <div class="stat-icon" :class="warningsIconClass"><IconError class="w-5 h-5" /></div>
          <div>
            <div class="stat-value">{{ alertSummary.open ?? 0 }}</div>
            <div class="stat-label">System warnings</div>
          </div>
        </button>
      </div>
      <!-- Latest global consumption (30d) — sourced from globalGenerationStats -->
      <section class="table-card">
        <header class="card-head">
          <h3 class="card-title"><IconPresentationChartBar class="w-4 h-4" /> Global consumption (last 30 days)</h3>
          <button class="mini-btn" @click="activeTab = 'consumption'">View consumption →</button>
        </header>
        <div v-if="isLoadingGlobalConsumption" class="table-state">Loading consumption…</div>
        <div v-else-if="!hasGlobalConsumption" class="table-state">No consumption recorded in the last 30 days.</div>
        <div v-else class="consumption-grid">
          <div class="consumption-metric">
            <div class="consumption-value">{{ formatCompact(latestGlobalConsumption.total) }}</div>
            <div class="consumption-label">Total tokens</div>
          </div>
          <div class="consumption-metric">
            <div class="consumption-value sky">{{ formatCompact(latestGlobalConsumption.input) }}</div>
            <div class="consumption-label">Input tokens</div>
          </div>
          <div class="consumption-metric">
            <div class="consumption-value rose">{{ formatCompact(latestGlobalConsumption.output) }}</div>
            <div class="consumption-label">Output tokens</div>
          </div>
          <div class="consumption-metric">
            <div class="consumption-value blue">{{ formatCompact(latestGlobalConsumption.webui) }}</div>
            <div class="consumption-label">WebUI tokens · {{ latestGlobalConsumption.webuiRatio }}%</div>
          </div>
          <div class="consumption-metric">
            <div class="consumption-value purple">{{ formatCompact(latestGlobalConsumption.api) }}</div>
            <div class="consumption-label">API tokens · {{ latestGlobalConsumption.apiRatio }}%</div>
          </div>
          <div class="consumption-metric">
            <div class="consumption-value amber">{{ formatCompact(latestGlobalConsumption.generations) }}</div>
            <div class="consumption-label">Generations</div>
          </div>
          <div class="consumption-metric">
            <div class="consumption-value">{{ latestGlobalConsumption.energy.toFixed(2) }}</div>
            <div class="consumption-label">Energy (kWh)</div>
          </div>
          <div class="consumption-metric">
            <div class="consumption-value">{{ latestGlobalConsumption.co2.toFixed(1) }}</div>
            <div class="consumption-label">CO₂ (g)</div>
          </div>
        </div>
      </section>

      <!-- Two-column operational grid -->
      <div class="ops-grid">

        <!-- LEFT: Pending approvals (quick-validate) -->
        <section class="table-card">
          <header class="card-head">
            <h3 class="card-title"><IconUserPlus class="w-4 h-4" /> Pending approvals</h3>
            <div class="card-head-actions">
              <span class="card-badge" :class="pendingUsers.length ? 'badge-amber' : 'badge-muted'">
                {{ pendingUsers.length }}
              </span>
              <button
                v-if="pendingUsers.length > 1"
                class="btn-validate-all"
                :disabled="validatingAll"
                @click="validateAllPending"
              >
                <IconAnimateSpin v-if="validatingAll" class="w-3.5 h-3.5 animate-spin" />
                <IconCheckCircle v-else class="w-3.5 h-3.5" />
                <span>Validate all</span>
              </button>
            </div>
          </header>

          <div v-if="isLoadingPending" class="table-state">Loading users…</div>
          <div v-else-if="pendingUsers.length === 0" class="table-state">
            <IconCheckCircle class="w-5 h-5 mx-auto mb-1 text-emerald-500" />
            No accounts awaiting approval.
          </div>
          <ul v-else class="pending-list">
            <li v-for="u in pendingUsers" :key="u.id" class="pending-row">
              <div class="pending-user">
                <span class="pending-avatar">{{ (u.username || '?').charAt(0).toUpperCase() }}</span>
                <div class="pending-meta">
                  <span class="pending-name">{{ u.username }}</span>
                  <span class="pending-email">{{ u.email || 'no email' }}</span>
                </div>
              </div>
              <div class="pending-actions">
                <span class="pending-time">{{ formatLastSeen(u.created_at) }}</span>
                <button
                  class="btn-validate"
                  :disabled="activatingIds.includes(u.id)"
                  @click="quickActivate(u)"
                >
                  <IconAnimateSpin v-if="activatingIds.includes(u.id)" class="w-3.5 h-3.5 animate-spin" />
                  <IconCheckCircle v-else class="w-3.5 h-3.5" />
                  <span>Activate</span>
                </button>
              </div>
            </li>
          </ul>
          <footer v-if="pendingUsers.length" class="pending-footer">
            <button class="link-btn" @click="goToUserManagement">
              Open full user management →
            </button>
          </footer>
        </section>

        <!-- RIGHT: Live operations log stream (server stdout/stderr) -->
        <section class="table-card">
          <header class="card-head">
            <h3 class="card-title"><IconCog class="w-4 h-4" /> Live operations log</h3>
            <div class="card-head-actions">
              <select class="log-window-select" :value="processLogWindow" @change="onProcessLogWindow($event.target.value)">
                <option :value="1">Last 1h</option>
                <option :value="6">Last 6h</option>
                <option :value="24">Last 24h</option>
                <option :value="48">Last 48h</option>
                <option :value="168">Last 7d</option>
                <option :value="0">All retained</option>
              </select>
              <button class="mini-btn" :class="{ active: autoRefreshLogs }" @click="toggleAutoRefreshLogs"
                      :title="autoRefreshLogs ? 'Auto-refresh ON (5s)' : 'Auto-refresh OFF'">
                <span class="auto-refresh-dot" :class="{ live: autoRefreshLogs }"></span>
                <span>{{ autoRefreshLogs ? 'Live' : 'Paused' }}</span>
              </button>
              <button class="mini-btn" @click="fetchProcessLogs()" title="Refresh logs">
                <IconArrowPath class="w-3.5 h-3.5" />
              </button>
              <button class="mini-btn" @click="clearProcessLogs" title="Clear the in-memory log buffer">
                <IconTrash class="w-3.5 h-3.5" />
              </button>
            </div>
          </header>

          <div class="log-filter-bar">
            <select class="log-filter-select" :value="processLogLevel" @change="onProcessLogLevel($event.target.value)">
              <option :value="null">All levels</option>
              <option value="DEBUG">Debug</option>
              <option value="INFO">Info</option>
              <option value="WARNING">Warning</option>
              <option value="ERROR">Error</option>
              <option value="CRITICAL">Critical</option>
            </select>
            <select class="log-filter-select" :value="processLogSource" @change="onProcessLogSource($event.target.value)">
              <option :value="null">All sources</option>
              <option value="stdout">stdout</option>
              <option value="stderr">stderr</option>
              <option value="app">app</option>
            </select>
            <span class="log-count-badge">{{ processLogsMeta.count }} shown · {{ processLogsMeta.total_in_buffer }} in buffer</span>
          </div>

          <div v-if="isLoadingProcessLogs && processLogs.length === 0" class="table-state">Loading logs…</div>
          <div v-else-if="processLogs.length === 0" class="table-state">No log entries in this window.</div>
          <div v-else class="log-stream" ref="logStreamRef">
            <div v-for="(log, i) in processLogs" :key="log.timestamp + i" class="log-row">
              <span class="log-time">{{ formatTime(log.timestamp) }}</span>
              <span class="log-level" :class="logLevelClass(log.level)">{{ log.level }}</span>
              <span class="log-source" :class="'src-' + log.source">{{ log.source }}</span>
              <span class="log-msg">{{ log.message }}</span>
            </div>
          </div>
        </section>
      </div>

      <!-- Open alerts (top 5) -->
      <section v-if="openAlertRows.length" class="table-card">
        <header class="card-head">
          <h3 class="card-title"><IconError class="w-4 h-4" /> Active alerts</h3>
          <button class="mini-btn" @click="activeTab = 'operations'">All alerts →</button>
        </header>
        <ul class="alert-row-list">
          <li v-for="a in openAlertRows" :key="a.id" class="alert-row">
            <span class="alert-sev" :class="'sev-' + (a.severity || 'info')"></span>
            <div class="alert-row-body">
              <span class="alert-row-title">{{ a.title }}</span>
              <span class="alert-row-msg">{{ a.message }}</span>
            </div>
            <span class="alert-row-count">×{{ a.occurrence_count }}</span>
          </li>
        </ul>
      </section>

    </div>

    <!-- ══════════════════ OPERATIONS (full alerts + logs) ══════════════════ -->
    <div v-else-if="activeTab === 'operations'" class="tab-panel">
      <AdminAlertsPanel v-if="AdminAlertsPanel" />
      <section class="table-card">
        <header class="card-head">
          <h3 class="card-title"><IconTasks class="w-4 h-4" /> Background task log stream</h3>
          <button class="mini-btn" @click="loadLogs(true)">Refresh</button>
        </header>
        <div v-if="isLoadingLogs" class="table-state">Loading logs…</div>
        <div v-else-if="recentLogs.length === 0" class="table-state">
          No background task log entries. Server console output is in the “Live operations log” panel below.
        </div>
        <div v-else class="log-stream log-stream-tall">
          <div v-for="(log, i) in recentLogs" :key="log.task_id + i" class="log-row">
            <span class="log-time">{{ formatTime(log.timestamp) }}</span>
            <span class="log-level" :class="logLevelClass(log.level)">{{ log.level }}</span>
            <span class="log-msg">{{ log.message }}</span>
          </div>
        </div>
      </section>

      <!-- Server process stdout/stderr (full window) -->
      <section class="table-card">
        <header class="card-head">
          <h3 class="card-title"><IconCog class="w-4 h-4" /> Live operations log</h3>
          <div class="card-head-actions">
            <select class="log-window-select" :value="processLogWindow" @change="onProcessLogWindow($event.target.value)">
              <option :value="1">Last 1h</option>
              <option :value="6">Last 6h</option>
              <option :value="24">Last 24h</option>
              <option :value="48">Last 48h</option>
              <option :value="72">Last 3d</option>
              <option :value="168">Last 7d</option>
              <option :value="0">All retained</option>
            </select>
            <button class="mini-btn" :class="{ active: autoRefreshLogs }" @click="toggleAutoRefreshLogs"
                    :title="autoRefreshLogs ? 'Auto-refresh ON (5s)' : 'Auto-refresh OFF'">
              <span class="auto-refresh-dot" :class="{ live: autoRefreshLogs }"></span>
              <span>{{ autoRefreshLogs ? 'Live' : 'Paused' }}</span>
            </button>
            <button class="mini-btn" @click="fetchProcessLogs()" title="Refresh logs">
              <IconArrowPath class="w-3.5 h-3.5" />
            </button>
            <button class="mini-btn" @click="clearProcessLogs" title="Clear the in-memory log buffer">
              <IconTrash class="w-3.5 h-3.5" />
            </button>
          </div>
        </header>
        <div class="log-filter-bar">
          <select class="log-filter-select" :value="processLogLevel" @change="onProcessLogLevel($event.target.value)">
            <option :value="null">All levels</option>
            <option value="DEBUG">Debug</option>
            <option value="INFO">Info</option>
            <option value="WARNING">Warning</option>
            <option value="ERROR">Error</option>
            <option value="CRITICAL">Critical</option>
          </select>
          <select class="log-filter-select" :value="processLogSource" @change="onProcessLogSource($event.target.value)">
            <option :value="null">All sources</option>
            <option value="stdout">stdout</option>
            <option value="stderr">stderr</option>
            <option value="app">app</option>
          </select>
          <span class="log-count-badge">{{ processLogsMeta.count }} shown · {{ processLogsMeta.total_in_buffer }} in buffer</span>
        </div>
        <div v-if="isLoadingProcessLogs && processLogs.length === 0" class="table-state">Loading logs…</div>
        <div v-else-if="processLogs.length === 0" class="table-state">No log entries in this window.</div>
        <div v-else class="log-stream log-stream-tall" ref="logStreamRef">
          <div v-for="(log, i) in processLogs" :key="log.timestamp + i" class="log-row">
            <span class="log-time">{{ formatTime(log.timestamp) }}</span>
            <span class="log-level" :class="logLevelClass(log.level)">{{ log.level }}</span>
            <span class="log-source" :class="'src-' + log.source">{{ log.source }}</span>
            <span class="log-msg">{{ log.message }}</span>
          </div>
        </div>
      </section>
    </div>

    <!-- ══════════════════ CONSUMPTION (token analytics drill-down) ══════════════════ -->
    <div v-else-if="activeTab === 'consumption'" class="tab-panel">
      <div class="chart-grid">
        <GlobalStatsChart v-if="globalStats" :stats="globalStats" />
      </div>
      <TokenConsumptionPanel v-if="TokenConsumptionPanel" />
    </div>

    <!-- ══════════════════ TOP USERS ══════════════════ -->
    <div v-else-if="activeTab === 'topusers'" class="tab-panel">
      <div class="topusers-controls">
        <div class="control-group">
          <label>Source</label>
          <select :value="topSource" @change="onTopSource($event.target.value)">
            <option value="all">All</option>
            <option value="webui">WebUI</option>
            <option value="api">API</option>
          </select>
        </div>
        <div class="control-group">
          <label>Metric</label>
          <select :value="topMetric" @change="onTopMetric($event.target.value)">
            <option value="total_tokens">Total tokens</option>
            <option value="input_tokens">Input tokens</option>
            <option value="output_tokens">Output tokens</option>
            <option value="calls">Calls</option>
          </select>
        </div>
        <div class="control-group">
          <label>Window</label>
          <select :value="topDays" @change="onTopDays($event.target.value)">
            <option :value="0">All time</option>
            <option :value="7">7 days</option>
            <option :value="30">30 days</option>
            <option :value="90">90 days</option>
          </select>
        </div>
      </div>

      <section class="table-card">
        <div v-if="isLoadingTopUsers" class="table-state">Loading…</div>
        <div v-else-if="!topUsers.length" class="table-state">No usage recorded for this selection.</div>
        <table v-else class="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>User</th>
              <th class="num">Input</th>
              <th class="num">Output</th>
              <th class="num">Total</th>
              <th class="num">Calls</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(u, i) in topUsers" :key="u.user_id">
              <td class="rank">{{ i + 1 }}</td>
              <td class="user-cell">{{ u.username }}</td>
              <td class="num">{{ formatCompact(u.prompt_tokens) }}</td>
              <td class="num">{{ formatCompact(u.completion_tokens) }}</td>
              <td class="num strong">{{ formatCompact(u.total_tokens) }}</td>
              <td class="num">{{ formatCompact(u.calls) }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>

    <!-- ══════════════════ MODEL USAGE ══════════════════ -->
    <div v-else-if="activeTab === 'models'" class="tab-panel">
      <section class="table-card">
        <div v-if="isLoadingModelUsage" class="table-state">Loading…</div>
        <div v-else-if="!modelUsage.length" class="table-state">No model usage recorded.</div>
        <table v-else class="data-table">
          <thead>
            <tr>
              <th>Model</th>
              <th class="num">Calls</th>
              <th class="num">Tokens</th>
              <th class="num">Share</th>
              <th class="num">CO₂</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in modelUsage" :key="m.model_name">
              <td class="user-cell">{{ m.model_name }}</td>
              <td class="num">{{ formatCompact(m.count) }}</td>
              <td class="num strong">{{ formatCompact(m.total_tokens) }}</td>
              <td class="num">{{ m.percentage }}%</td>
              <td class="num">{{ m.co2_g }} g</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, shallowRef } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useRouter } from 'vue-router';
import apiClient from '../../services/api';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';
import IconDashboard from '../../assets/icons/IconDashboard.vue';
import IconShieldCheck from '../../assets/icons/IconShieldCheck.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconUserGroup from '../../assets/icons/IconUserGroup.vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconClock from '../../assets/icons/IconClock.vue';
import IconError from '../../assets/icons/IconError.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconUserPlus from '../../assets/icons/IconUserPlus.vue';
import IconCog from '../../assets/icons/IconCog.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconTasks from '../../assets/icons/IconTasks.vue';

const adminStore = useAdminStore();
const router = useRouter();

const tabs = [
  { id: 'overview', label: 'Overview', icon: IconDashboard },
  { id: 'operations', label: 'Operations', icon: IconShieldCheck },
  { id: 'consumption', label: 'Consumption', icon: IconPresentationChartBar },
  { id: 'topusers', label: 'Top Users', icon: IconUserGroup },
  { id: 'models', label: 'Models', icon: IconCpuChip },
];
const activeTab = ref('overview');

// ── Live alert summary (health banner + System warnings KPI) ──
const alertSummary = computed(() => adminStore.alertSummary || { open: 0, critical: 0, warning: 0, info: 0 });

const alertHeadline = computed(() => {
  const s = alertSummary.value;
  if (!s.open) return 'All systems nominal';
  if (s.critical) return `${s.critical} critical issue${s.critical > 1 ? 's' : ''} require attention`;
  if (s.warning) return `${s.warning} warning${s.warning > 1 ? 's' : ''} detected`;
  return `${s.open} open alert${s.open > 1 ? 's' : ''}`;
});

const alertBannerClass = computed(() => {
  const s = alertSummary.value;
  if (s.critical) return 'banner-critical';
  if (s.warning) return 'banner-warning';
  if (s.open) return 'banner-info';
  return 'banner-ok';
});

const alertDotClass = computed(() => {
  const s = alertSummary.value;
  if (s.critical) return 'dot-critical';
  if (s.warning) return 'dot-warning';
  if (s.open) return 'dot-info';
  return 'dot-ok';
});

const warningsKpiClass = computed(() => {
  const s = alertSummary.value;
  if (s.critical) return 'kpi-critical';
  if (s.warning) return 'kpi-warning';
  return '';
});

const warningsIconClass = computed(() => {
  const s = alertSummary.value;
  if (s.critical) return 'rose';
  if (s.warning) return 'amber';
  return 'slate';
});

// ── KPI / dashboard stats ──
const stats = computed(() => adminStore.dashboardStats || {});

// ── Pending approvals (quick-validate) ──
const pendingUsers = ref([]);
const isLoadingPending = ref(false);
const activatingIds = ref([]);
const validatingAll = ref(false);

async function loadPendingUsers() {
  isLoadingPending.value = true;
  try {
    const { data } = await apiClient.get('/api/admin/users', {
      params: { status_filter: 'pending_approval', sort_by: 'created_at', sort_order: 'desc' },
    });
    pendingUsers.value = Array.isArray(data) ? data : [];
  } catch (e) {
    pendingUsers.value = [];
  } finally {
    isLoadingPending.value = false;
  }
}

async function quickActivate(user) {
  if (activatingIds.value.includes(user.id)) return;
  activatingIds.value.push(user.id);
  try {
    await apiClient.post(`/api/admin/users/${user.id}/activate`);
    pendingUsers.value = pendingUsers.value.filter(u => u.id !== user.id);
  } catch (e) {
    // stay in list on failure; store-level notification surfaces the error
  } finally {
    activatingIds.value = activatingIds.value.filter(id => id !== user.id);
    adminStore.fetchDashboardStats();
  }
}

async function validateAllPending() {
  if (validatingAll.value || pendingUsers.value.length === 0) return;
  validatingAll.value = true;
  try {
    const ids = pendingUsers.value.map(u => u.id);
    await adminStore.bulkActivateUsers(ids);
    await loadPendingUsers();
    adminStore.fetchDashboardStats();
  } finally {
    validatingAll.value = false;
  }
}

function goToUserManagement() {
  router.push({ name: 'admin', query: { section: 'users' } });
}

// ── System log stream (background task logs) ──
const recentLogs = ref([]);
const isLoadingLogs = ref(false);

async function loadLogs(force = false) {
  isLoadingLogs.value = true;
  try {
    const { data } = await apiClient.get('/api/admin/system/logs', { params: { limit: 50 } });
    recentLogs.value = Array.isArray(data) ? data : [];
  } catch (e) {
    if (force) recentLogs.value = [];
  } finally {
    isLoadingLogs.value = false;
  }
}

// ── Process log stream (server stdout/stderr, from backend.log_buffer) ──
// This is the fix for the previously-always-empty "Live operations log": task
// logs are empty unless a background task ran, so we surface the server's own
// console output, captured into a bounded in-memory ring buffer by
// backend.log_buffer (installed in main.py startup). We own the fetching state
// locally here rather than delegating to a store action, because the console
// feed is a dashboard-only concern and the store action did not exist — which
// is exactly why the panel was permanently empty.
const processLogs = ref([]);
const processLogsMeta = ref({ count: 0, total_in_buffer: 0 });
const isLoadingProcessLogs = ref(false);
const processLogWindow = ref(24);   // hours; 0 = everything retained
const processLogLevel = ref(null);
const processLogSource = ref(null);
const autoRefreshLogs = ref(true);
const logStreamRef = ref(null);
let logPollTimer = null;
let processLogRequestSeq = 0;

async function fetchProcessLogs(overrides = {}) {
  // Merge any per-call overrides (window/level/source) into the active state
  // so the select boxes reflect the query that produced the current rows.
  if (Object.prototype.hasOwnProperty.call(overrides, 'hours')) processLogWindow.value = Number(overrides.hours);
  if (Object.prototype.hasOwnProperty.call(overrides, 'level')) processLogLevel.value = overrides.level || null;
  if (Object.prototype.hasOwnProperty.call(overrides, 'source')) processLogSource.value = overrides.source || null;

  const params = { hours: processLogWindow.value, limit: 500 };
  if (processLogLevel.value) params.level = processLogLevel.value;
  if (processLogSource.value) params.source = processLogSource.value;

  const seq = ++processLogRequestSeq;
  isLoadingProcessLogs.value = true;
  try {
    const { data } = await apiClient.get('/api/admin/system/process-logs', { params });
    // Drop stale responses: a slow earlier request must not overwrite a newer one.
    if (seq !== processLogRequestSeq) return;
    processLogs.value = Array.isArray(data?.entries) ? data.entries : [];
    processLogsMeta.value = {
      count: data?.count ?? processLogs.value.length,
      total_in_buffer: data?.total_in_buffer ?? processLogs.value.length,
    };
  } catch (e) {
    if (seq !== processLogRequestSeq) return;
    processLogs.value = [];
    processLogsMeta.value = { count: 0, total_in_buffer: 0 };
  } finally {
    if (seq === processLogRequestSeq) isLoadingProcessLogs.value = false;
  }
}

function loadProcessLogs() {
  return fetchProcessLogs();
}
function onProcessLogWindow(val) {
  fetchProcessLogs({ hours: Number(val) });
}
function onProcessLogLevel(val) {
  fetchProcessLogs({ level: val || null });
}
function onProcessLogSource(val) {
  fetchProcessLogs({ source: val || null });
}
function clearProcessLogs() {
  adminStore.clearProcessLogs()
    .catch(() => {})
    .finally(() => fetchProcessLogs());
}
function toggleAutoRefreshLogs() {
  autoRefreshLogs.value = !autoRefreshLogs.value;
  if (autoRefreshLogs.value) startLogPolling();
  else stopLogPolling();
}
function startLogPolling() {
  stopLogPolling();
  logPollTimer = setInterval(() => {
    // Only poll the process logs while the overview/operations tab is visible.
    if (activeTab.value === 'overview' || activeTab.value === 'operations') {
      fetchProcessLogs();
    }
  }, 5000);
}
function stopLogPolling() {
  if (logPollTimer) {
    clearInterval(logPollTimer);
    logPollTimer = null;
  }
}

function logLevelClass(level) {
  const l = (level || '').toUpperCase();
  if (l === 'ERROR' || l === 'CRITICAL') return 'lvl-error';
  if (l === 'WARNING' || l === 'WARN') return 'lvl-warn';
  if (l === 'DEBUG') return 'lvl-debug';
  return 'lvl-info';
}

// ── Active alerts feed (top 5) ──
const openAlerts = ref([]);

async function loadOpenAlerts() {
  try {
    const { data } = await apiClient.get('/api/admin/alerts', {
      params: { status: 'open', limit: 5 },
    });
    openAlerts.value = Array.isArray(data) ? data : [];
  } catch (e) {
    openAlerts.value = [];
  }
}

const openAlertRows = computed(() => openAlerts.value.slice(0, 5));

// ── Consumption tab (token analytics) ──
const globalStats = computed(() => adminStore.globalGenerationStats);

// ── Overview: latest global consumption (last 30d) ──
// GlobalGenerationStats ships authoritative top-level totals (total_tokens,
// total_prompt_tokens, total_completion_tokens, total_energy_kwh, total_co2_g,
// source_breakdown) alongside the per-day series, so we bind those directly
// rather than re-deriving them from the series (the server's total_tokens is
// webui+api with a raw fallback, which a naive series sum would not match).
const isLoadingGlobalConsumption = computed(() => adminStore.isLoadingGlobalGenerationStats);
const hasGlobalConsumption = computed(() => {
  const s = globalStats.value;
  if (!s) return false;
  return Number(s.total_tokens) > 0
    || (Array.isArray(s.generations_per_day) && s.generations_per_day.length > 0);
});
const latestGlobalConsumption = computed(() => {
  const s = globalStats.value || {};
  const sb = s.source_breakdown || {};
  return {
    total: Number(s.total_tokens) || 0,
    input: Number(s.total_prompt_tokens) || 0,
    output: Number(s.total_completion_tokens) || 0,
    webui: Number(sb.webui_tokens) || 0,
    api: Number(sb.api_tokens) || 0,
    webuiRatio: Number(sb.webui_ratio) || 0,
    apiRatio: Number(sb.api_ratio) || 0,
    generations: Array.isArray(s.generations_per_day)
      ? s.generations_per_day.reduce((acc, r) => acc + (Number(r?.count) || 0), 0)
      : 0,
    energy: Number(s.total_energy_kwh) || 0,
    co2: Number(s.total_co2_g) || 0,
  };
});
const TokenConsumptionPanel = shallowRef(null);
import('../../components/admin/TokenConsumptionPanel.vue')
  .then(m => { TokenConsumptionPanel.value = m.default; })
  .catch(() => {});
const GlobalStatsChart = shallowRef(null);
import('../../components/admin/GlobalStatsChart.vue')
  .then(m => { GlobalStatsChart.value = m.default; })
  .catch(() => {});

// ── Operations tab (alerts panel) ──
const AdminAlertsPanel = shallowRef(null);
import('../../components/admin/AdminAlertsPanel.vue')
  .then(m => { AdminAlertsPanel.value = m.default; })
  .catch(() => {});

// ── Top Users tab ──
const topUsers = computed(() => adminStore.topUsers || []);
const isLoadingTopUsers = computed(() => adminStore.isLoadingTopUsers);
const topUsersParams = computed(() => adminStore.topUsersParams || { source: null, metric: 'total_tokens', days: 0 });
const topSource = computed(() => topUsersParams.value.source || 'all');
const topMetric = computed(() => topUsersParams.value.metric || 'total_tokens');
const topDays = computed(() => topUsersParams.value.days ?? 0);

function onTopSource(val) { adminStore.fetchTopUsers({ source: val === 'all' ? null : val }); }
function onTopMetric(val) { adminStore.fetchTopUsers({ metric: val }); }
function onTopDays(val) { adminStore.fetchTopUsers({ days: Number(val) }); }

// ── Models tab ──
const modelUsage = computed(() => adminStore.modelUsageStats || []);
const isLoadingModelUsage = computed(() => adminStore.isLoadingModelUsageStats);

// ── Formatting helpers ──
function formatCompact(n) {
  const v = Number(n) || 0;
  if (v >= 1e9) return (v / 1e9).toFixed(1) + 'B';
  if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M';
  if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
  return String(v);
}

function formatTime(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatLastSeen(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return '';
  const diffMs = Date.now() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ── Refresh current tab ──
function refreshActiveTab() {
  adminStore.fetchDashboardStats();
  adminStore.fetchAlertSummary();
  if (activeTab.value === 'overview' || activeTab.value === 'operations') {
    loadPendingUsers();
    loadLogs(true);
    loadOpenAlerts();
    fetchProcessLogs();
  }
  if (activeTab.value === 'overview') adminStore.fetchGlobalGenerationStats(true);
  if (activeTab.value === 'overview' || activeTab.value === 'consumption') {
    adminStore.fetchGlobalGenerationStats(true);
  }
  if (activeTab.value === 'topusers') adminStore.fetchTopUsers();
  if (activeTab.value === 'models') adminStore.fetchModelUsageStats();
}

onMounted(() => {
  adminStore.fetchDashboardStats();
  adminStore.fetchAlertSummary();
  adminStore.fetchGlobalGenerationStats();
  loadPendingUsers();
  loadLogs();
  loadOpenAlerts();
  fetchProcessLogs();
  if (autoRefreshLogs.value) startLogPolling();
});

onUnmounted(() => {
  stopLogPolling();
});
</script>

<style scoped>
.dashboard-root {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 8px;
}

/* ── Tabs ── */
.dash-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  padding-bottom: 8px;
}
.dash-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary, #64748b);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.15s ease;
}
.dash-tab:hover { background: var(--bg-hover, #f1f5f9); }
.dash-tab.active {
  background: var(--accent-color, #6366f1);
  color: #fff;
  font-weight: 600;
}
.dash-tab-icon { width: 16px; height: 16px; flex-shrink: 0; }
.dash-refresh {
  margin-left: auto;
  padding: 7px;
  border-radius: 8px;
  border: 1px solid var(--border-color, #e2e8f0);
  background: transparent;
  color: var(--text-secondary, #64748b);
  cursor: pointer;
}
.dash-refresh:hover { background: var(--bg-hover, #f1f5f9); }

.tab-panel { display: flex; flex-direction: column; gap: 16px; }

/* ── Alert banner ── */
.alert-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 14px 18px;
  border-radius: 12px;
  border: 1px solid var(--border-color, #e2e8f0);
  background: var(--bg-secondary, #fff);
  cursor: pointer;
  text-align: left;
  transition: transform 0.1s ease;
}
.alert-banner:hover { transform: translateY(-1px); }
.alert-banner-left { display: flex; align-items: center; gap: 12px; }
.alert-banner-dot {
  width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0;
}
.alert-banner-title { font-weight: 600; font-size: 0.95rem; color: var(--text-primary, #1e293b); }
.alert-banner-sub { font-size: 0.78rem; color: var(--text-secondary, #64748b); margin-top: 2px; }
.alert-banner-cta { font-size: 0.8rem; font-weight: 600; color: var(--accent-color, #6366f1); }

.banner-critical { border-color: #fca5a5; background: #fef2f2; }
.banner-warning  { border-color: #fcd34d; background: #fffbeb; }
.banner-info     { border-color: #93c5fd; background: #eff6ff; }
.banner-ok       { border-color: #86efac; background: #f0fdf4; }

.dot-critical { background: #ef4444; box-shadow: 0 0 0 3px rgba(239,68,68,0.2); }
.dot-warning  { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245,158,11,0.2); }
.dot-info     { background: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.2); }
.dot-ok       { background: #22c55e; box-shadow: 0 0 0 3px rgba(34,197,94,0.2); }

/* ── KPI strip ── */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  border-radius: 12px;
  border: 1px solid var(--border-color, #e2e8f0);
  background: var(--bg-secondary, #fff);
  text-align: left;
}
.stat-card-action { cursor: pointer; transition: transform 0.1s ease; }
.stat-card-action:hover { transform: translateY(-1px); }
.stat-card-action.kpi-critical { border-color: #fca5a5; background: #fef2f2; }
.stat-card-action.kpi-warning  { border-color: #fcd34d; background: #fffbeb; }

.stat-icon {
  display: flex; align-items: center; justify-content: center;
  width: 40px; height: 40px; border-radius: 10px; flex-shrink: 0;
}
.stat-icon.sky     { background: #e0f2fe; color: #0284c7; }
.stat-icon.emerald { background: #dcfce7; color: #16a34a; }
.stat-icon.amber   { background: #fef3c7; color: #d97706; }
.stat-icon.rose    { background: #ffe4e6; color: #e11d48; }
.stat-icon.slate   { background: #f1f5f9; color: #64748b; }

.stat-value { font-size: 1.5rem; font-weight: 700; color: var(--text-primary, #1e293b); line-height: 1.1; }
.stat-label { font-size: 0.78rem; color: var(--text-secondary, #64748b); margin-top: 2px; }
.text-amber-600 { color: #d97706; }

/* ── Latest global consumption ── */
.consumption-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 1px;
  background: var(--border-color, #f1f5f9);
}
.consumption-metric {
  padding: 16px 18px;
  background: var(--bg-secondary, #fff);
  text-align: center;
}
.consumption-value {
  font-size: 1.35rem; font-weight: 700; line-height: 1.1;
  color: var(--text-primary, #1e293b);
}
.consumption-value.sky    { color: #0284c7; }
.consumption-value.rose   { color: #e11d48; }
.consumption-value.blue   { color: #2563eb; }
.consumption-value.purple { color: #7c3aed; }
.consumption-value.amber  { color: #d97706; }
.consumption-label {
  font-size: 0.74rem; color: var(--text-secondary, #64748b); margin-top: 3px;
}

/* ── Latest global consumption ── */
.consumption-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 4px;
  padding: 14px 8px;
}
.consumption-metric { padding: 8px 12px; text-align: left; }
.consumption-value { font-size: 1.25rem; font-weight: 700; line-height: 1.1; color: var(--text-primary, #1e293b); }
.consumption-value.sky    { color: #0284c7; }
.consumption-value.rose   { color: #e11d48; }
.consumption-value.blue   { color: #2563eb; }
.consumption-value.purple { color: #7c3aed; }
.consumption-value.amber  { color: #d97706; }
.consumption-label { font-size: 0.74rem; color: var(--text-secondary, #64748b); margin-top: 3px; }

/* ── Operational grid ── */
.ops-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 16px;
}
.table-card {
  border-radius: 12px;
  border: 1px solid var(--border-color, #e2e8f0);
  background: var(--bg-secondary, #fff);
  overflow: hidden;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color, #f1f5f9);
}
.card-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 0.9rem; font-weight: 600; margin: 0;
  color: var(--text-primary, #1e293b);
}
.card-head-actions { display: flex; align-items: center; gap: 8px; }
.card-badge {
  padding: 2px 9px; border-radius: 999px;
  font-size: 0.72rem; font-weight: 700;
}
.badge-amber { background: #fef3c7; color: #b45309; }
.badge-muted { background: #f1f5f9; color: #64748b; }
.mini-btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 5px 10px; border-radius: 7px;
  border: 1px solid var(--border-color, #e2e8f0);
  background: transparent; color: var(--text-secondary, #64748b);
  font-size: 0.78rem; cursor: pointer;
}
.mini-btn:hover { background: var(--bg-hover, #f1f5f9); }

.table-state {
  padding: 32px 16px; text-align: center;
  font-size: 0.85rem; color: var(--text-secondary, #64748b);
}

/* ── Pending approvals ── */
.pending-list { list-style: none; margin: 0; padding: 0; }
.pending-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--border-color, #f1f5f9);
}
.pending-row:last-child { border-bottom: none; }
.pending-user { display: flex; align-items: center; gap: 10px; min-width: 0; }
.pending-avatar {
  display: flex; align-items: center; justify-content: center;
  width: 34px; height: 34px; border-radius: 50%;
  background: var(--accent-color, #6366f1); color: #fff;
  font-weight: 700; font-size: 0.85rem; flex-shrink: 0;
}
.pending-meta { display: flex; flex-direction: column; min-width: 0; }
.pending-name { font-size: 0.85rem; font-weight: 600; color: var(--text-primary, #1e293b); }
.pending-email { font-size: 0.75rem; color: var(--text-secondary, #64748b); }
.pending-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.pending-time { font-size: 0.72rem; color: var(--text-secondary, #94a3b8); }

.btn-validate, .btn-validate-all {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 12px; border-radius: 7px; border: none;
  background: #16a34a; color: #fff;
  font-size: 0.78rem; font-weight: 600; cursor: pointer;
  transition: background 0.15s ease;
}
.btn-validate:hover, .btn-validate-all:hover { background: #15803d; }
.btn-validate:disabled, .btn-validate-all:disabled { opacity: 0.6; cursor: default; }
.btn-validate-all { padding: 5px 11px; font-size: 0.75rem; }

.pending-footer {
  padding: 10px 16px; border-top: 1px solid var(--border-color, #f1f5f9);
  text-align: right;
}
.link-btn {
  background: none; border: none; padding: 0;
  color: var(--accent-color, #6366f1);
  font-size: 0.8rem; font-weight: 600; cursor: pointer;
}
.link-btn:hover { text-decoration: underline; }

/* ── Log stream ── */
.log-stream { max-height: 320px; overflow-y: auto; }
.log-stream-tall { max-height: 560px; }
.log-row {
  display: flex; align-items: baseline; gap: 8px;
  padding: 6px 16px;
  font-family: ui-monospace, 'SF Mono', Consolas, monospace;
  font-size: 0.76rem;
  border-bottom: 1px solid var(--border-color, #f8fafc);
}
.log-time { color: #94a3b8; flex-shrink: 0; }
.log-level {
  flex-shrink: 0; font-weight: 700; text-transform: uppercase;
  font-size: 0.68rem; padding: 1px 5px; border-radius: 4px;
}
.lvl-error { background: #ffe4e6; color: #e11d48; }
.lvl-warn  { background: #fef3c7; color: #b45309; }
.lvl-info  { background: #e0f2fe; color: #0369a1; }
.lvl-debug { background: #f1f5f9; color: #64748b; }
.log-msg { color: var(--text-primary, #334155); word-break: break-word; }
.log-source {
  flex-shrink: 0; font-weight: 700; text-transform: uppercase;
  font-size: 0.62rem; padding: 1px 5px; border-radius: 4px;
  letter-spacing: 0.03em;
}
.log-source.src-stdout { background: #e0f2fe; color: #0369a1; }
.log-source.src-stderr { background: #fee2e2; color: #b91c1c; }
.log-source.src-app    { background: #ede9fe; color: #6d28d9; }

/* ── Process log controls ── */
.log-window-select, .log-filter-select {
  padding: 5px 8px; border-radius: 7px;
  border: 1px solid var(--border-color, #e2e8f0);
  background: var(--bg-primary, #fff);
  color: var(--text-primary, #334155);
  font-size: 0.76rem;
}
.log-filter-bar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 8px 16px;
  border-bottom: 1px solid var(--border-color, #f1f5f9);
}
.log-count-badge {
  margin-left: auto; font-size: 0.72rem; color: var(--text-secondary, #64748b);
}
.mini-btn.active {
  background: #dcfce7; border-color: #86efac; color: #166534;
}
.auto-refresh-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #cbd5e1; flex-shrink: 0;
}
.auto-refresh-dot.live {
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.22);
  animation: log-pulse 1.6s ease-in-out infinite;
}
@keyframes log-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
.log-source {
  flex-shrink: 0; font-weight: 700; text-transform: uppercase;
  font-size: 0.62rem; padding: 1px 5px; border-radius: 4px;
  letter-spacing: 0.03em;
}
.log-source.src-stdout { background: #e0f2fe; color: #0369a1; }
.log-source.src-stderr { background: #fee2e2; color: #b91c1c; }
.log-source.src-app    { background: #ede9fe; color: #6d28d9; }

/* ── Process log controls ── */
.log-window-select, .log-filter-select {
  padding: 5px 8px; border-radius: 7px;
  border: 1px solid var(--border-color, #e2e8f0);
  background: var(--bg-primary, #fff);
  color: var(--text-primary, #334155);
  font-size: 0.76rem;
}
.log-filter-bar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 8px 16px;
  border-bottom: 1px solid var(--border-color, #f1f5f9);
}
.log-count-badge {
  margin-left: auto; font-size: 0.72rem; color: var(--text-secondary, #64748b);
}
.mini-btn.active {
  background: #dcfce7; border-color: #86efac; color: #166534;
}
.auto-refresh-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #cbd5e1; flex-shrink: 0;
}
.auto-refresh-dot.live {
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.22);
  animation: log-pulse 1.6s ease-in-out infinite;
}
@keyframes log-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

/* ── Active alerts list ── */
.alert-row-list { list-style: none; margin: 0; padding: 0; }
.alert-row {
  display: flex; align-items: center; gap: 12px;
  padding: 11px 16px; border-bottom: 1px solid var(--border-color, #f1f5f9);
}
.alert-row:last-child { border-bottom: none; }
.alert-sev {
  width: 4px; align-self: stretch; border-radius: 2px; flex-shrink: 0;
}
.alert-sev.sev-critical { background: #ef4444; }
.alert-sev.sev-warning  { background: #f59e0b; }
.alert-sev.sev-info     { background: #3b82f6; }
.alert-row-body { display: flex; flex-direction: column; flex: 1; min-width: 0; }
.alert-row-title { font-size: 0.84rem; font-weight: 600; color: var(--text-primary, #1e293b); }
.alert-row-msg { font-size: 0.76rem; color: var(--text-secondary, #64748b); }
.alert-row-count { font-size: 0.74rem; font-weight: 700; color: #94a3b8; }

/* ── Tables (Top Users / Models) ── */
.chart-grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
.topusers-controls {
  display: flex; flex-wrap: wrap; gap: 16px;
  padding: 12px 16px;
  border-radius: 12px; border: 1px solid var(--border-color, #e2e8f0);
  background: var(--bg-secondary, #fff);
}
.control-group { display: flex; flex-direction: column; gap: 4px; }
.control-group label { font-size: 0.72rem; font-weight: 600; color: var(--text-secondary, #64748b); }
.control-group select {
  padding: 6px 10px; border-radius: 7px;
  border: 1px solid var(--border-color, #e2e8f0);
  background: var(--bg-primary, #fff); font-size: 0.82rem;
}

.data-table { width: 100%; border-collapse: collapse; }
.data-table th {
  text-align: left; padding: 10px 16px;
  font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
  color: var(--text-secondary, #64748b);
  border-bottom: 1px solid var(--border-color, #e2e8f0);
}
.data-table th.num, .data-table td.num { text-align: right; }
.data-table td { padding: 10px 16px; border-bottom: 1px solid var(--border-color, #f1f5f9); color: var(--text-primary, #334155); font-size: 0.82rem; }
.data-table tr:last-child td { border-bottom: none; }
.data-table td.strong { font-weight: 700; }
.data-table td.rank { color: #94a3b8; font-weight: 700; }
.data-table td.user-cell { font-weight: 600; }
</style>
