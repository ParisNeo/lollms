<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import useEventBus from '../../services/eventBus';

import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';
import IconNoSymbol from '../../assets/icons/IconNoSymbol.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();
const { on, off } = useEventBus();

// Live summary pushed by the WebSocket handler in the auth store. Watching it
// keeps the feed fresh without coupling this panel to the socket directly.
const { alertSummary: storeAlertSummary } = storeToRefs(adminStore);

const alerts = ref([]);
const summary = ref({ total: 0, open: 0, critical: 0, warning: 0, info: 0, by_category: {} });
const isLoading = ref(true);
const isScanning = ref(false);
const statusFilter = ref('open');
const categoryFilter = ref('');
const severityFilter = ref('');

let summaryWatchTimer = null;

const categories = computed(() => Object.keys(summary.value.by_category || {}));

// ── Data loading ────────────────────────────────────────────────────────────
async function fetchAlerts() {
    isLoading.value = true;
    try {
        const params = { status: statusFilter.value, limit: 200 };
        if (categoryFilter.value) params.category = categoryFilter.value;
        if (severityFilter.value) params.severity = severityFilter.value;
        const [listRes, sumRes] = await Promise.all([
            apiClient.get('/api/admin/alerts', { params }),
            apiClient.get('/api/admin/alerts/summary'),
        ]);
        alerts.value = listRes.data || [];
        summary.value = sumRes.data || summary.value;
        adminStore.setAlertSummary(sumRes.data);
    } catch (e) {
        console.error('Failed to load admin alerts', e);
        uiStore.addNotification('Failed to load alerts.', 'error');
    } finally {
        isLoading.value = false;
    }
}

// ── Actions ─────────────────────────────────────────────────────────────────
async function scanNow() {
    isScanning.value = true;
    try {
        const { data } = await apiClient.post('/api/admin/alerts/scan');
        uiStore.addNotification(
            `Scan complete — ${data.user_alerts} user / ${data.system_alerts} system alert(s).`,
            'info'
        );
        await fetchAlerts();
    } catch (e) {
        uiStore.addNotification('Scan failed.', 'error');
    } finally {
        isScanning.value = false;
    }
}

async function acknowledge(alert) {
    try {
        await apiClient.post(`/api/admin/alerts/${alert.id}/ack`);
        await fetchAlerts();
    } catch (e) {
        uiStore.addNotification('Failed to acknowledge alert.', 'error');
    }
}

async function acknowledgeAll() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Acknowledge all alerts?',
        message: 'Every open alert will be marked as acknowledged.',
        confirmText: 'Acknowledge all',
    });
    if (!confirmed.confirmed) return;
    try {
        await apiClient.post('/api/admin/alerts/ack-all');
        await fetchAlerts();
        uiStore.addNotification('All alerts acknowledged.', 'success');
    } catch (e) {
        uiStore.addNotification('Failed to acknowledge alerts.', 'error');
    }
}

async function removeAlert(alert) {
    try {
        await apiClient.delete(`/api/admin/alerts/${alert.id}`);
        await fetchAlerts();
    } catch (e) {
        uiStore.addNotification('Failed to delete alert.', 'error');
    }
}

async function emitTest() {
    try {
        await apiClient.post('/api/admin/alerts/test');
        await fetchAlerts();
    } catch (e) {
        uiStore.addNotification('Failed to emit test alert.', 'error');
    }
}

// ── Presentation helpers ────────────────────────────────────────────────────
function severityStyle(sev) {
    if (sev === 'critical') return 'bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300 border-red-300 dark:border-red-800';
    if (sev === 'warning') return 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300 border-amber-300 dark:border-amber-800';
    return 'bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300 border-blue-300 dark:border-blue-800';
}

function severityDot(sev) {
    if (sev === 'critical') return 'bg-red-500';
    if (sev === 'warning') return 'bg-amber-500';
    return 'bg-blue-500';
}

function formatDate(value) {
    if (!value) return '';
    try {
        return new Date(value).toLocaleString();
    } catch {
        return value;
    }
}

function relativeTime(value) {
    if (!value) return '';
    const then = new Date(value).getTime();
    if (Number.isNaN(then)) return '';
    const diffSec = Math.round((Date.now() - then) / 1000);
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.round(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.round(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    return `${Math.round(diffHr / 24)}d ago`;
}

// ── Live refresh wiring ─────────────────────────────────────────────────────
// Debounced: a burst of live alerts triggers a single refetch.
watch(storeAlertSummary, () => {
    clearTimeout(summaryWatchTimer);
    summaryWatchTimer = setTimeout(() => {
        if (statusFilter.value === 'open' || statusFilter.value === 'all') {
            fetchAlerts();
        } else {
            apiClient.get('/api/admin/alerts/summary')
                .then((r) => { summary.value = r.data || summary.value; })
                .catch(() => {});
        }
    }, 400);
}, { deep: true });

function handleLiveAlert() {
    // Socket-delivered alert (auth store re-emits through the event bus).
    if (statusFilter.value === 'open' || statusFilter.value === 'all') {
        fetchAlerts();
    }
}

onMounted(() => {
    fetchAlerts();
    on('admin_alert', handleLiveAlert);
});

onUnmounted(() => {
    off('admin_alert', handleLiveAlert);
    clearTimeout(summaryWatchTimer);
});
</script>

<template>
    <div class="h-full flex flex-col overflow-hidden" style="background-color: var(--bg-app);">
        <!-- Toolbar -->
        <div class="shrink-0 px-6 py-4 border-b space-y-3" style="border-color: var(--border-main); background-color: var(--bg-card);">
            <div class="flex items-start justify-between gap-4 flex-wrap">
                <div>
                    <h3 class="text-lg font-black tracking-tight flex items-center gap-2" style="color: var(--text-main);">
                        <IconNoSymbol class="w-5 h-5 text-amber-500" />
                        Admin Alerts
                    </h3>
                    <p class="text-xs mt-0.5" style="color: var(--text-dim);">
                        Live operational feed: token overconsumption, system incidents, security and task failures.
                    </p>
                </div>
                <div class="flex items-center gap-2 flex-wrap">
                    <span class="px-2.5 py-1 rounded-lg text-[10px] font-black uppercase bg-red-100 dark:bg-red-950/40 text-red-700 dark:text-red-300">
                        {{ summary.critical }} critical
                    </span>
                    <span class="px-2.5 py-1 rounded-lg text-[10px] font-black uppercase bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300">
                        {{ summary.warning }} warning
                    </span>
                    <button
                        type="button"
                        @click="scanNow"
                        :disabled="isScanning"
                        class="btn btn-secondary btn-sm flex items-center gap-1.5"
                        title="Run the token-consumption scan now"
                    >
                        <IconArrowPath class="w-4 h-4" :class="{ 'animate-spin': isScanning }" />
                        <span>{{ isScanning ? 'Scanning…' : 'Scan now' }}</span>
                    </button>
                    <button
                        type="button"
                        @click="acknowledgeAll"
                        :disabled="summary.open === 0"
                        class="btn btn-secondary btn-sm flex items-center gap-1.5"
                    >
                        <IconCheckCircle class="w-4 h-4" />
                        <span>Acknowledge all</span>
                    </button>
                    <button type="button" @click="emitTest" class="btn btn-secondary btn-sm">
                        Test alert
                    </button>
                </div>
            </div>

            <!-- Filters -->
            <div class="flex items-center gap-2 flex-wrap">
                <div class="flex items-center gap-1">
                    <button
                        v-for="st in [
                            { id: 'open', label: 'Open' },
                            { id: 'acknowledged', label: 'Acknowledged' },
                            { id: 'all', label: 'All' },
                        ]"
                        :key="st.id"
                        type="button"
                        @click="statusFilter = st.id; fetchAlerts()"
                        class="px-2.5 py-1 rounded-lg text-[11px] font-bold border transition-colors"
                        :class="statusFilter === st.id ? 'bg-indigo-600 text-white border-indigo-600' : 'themed-btn-surface'"
                    >
                        {{ st.label }}
                    </button>
                </div>

                <select v-model="severityFilter" @change="fetchAlerts" class="input-field !py-1 text-xs w-40">
                    <option value="">All severities</option>
                    <option value="critical">Critical</option>
                    <option value="warning">Warning</option>
                    <option value="info">Info</option>
                </select>

                <select v-model="categoryFilter" @change="fetchAlerts" class="input-field !py-1 text-xs w-40">
                    <option value="">All categories</option>
                    <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
                </select>
            </div>
        </div>

        <!-- Body -->
        <div class="grow overflow-y-auto custom-scrollbar p-6 space-y-3">
            <div v-if="isLoading" class="text-center py-16 text-sm italic" style="color: var(--text-dim);">
                Loading alerts…
            </div>
            <div v-else-if="alerts.length === 0" class="text-center py-16 text-sm italic rounded-2xl border border-dashed" style="color: var(--text-dim); border-color: var(--border-main);">
                No alerts match the current filters. Everything looks quiet.
            </div>

            <div
                v-for="alert in alerts"
                :key="alert.id"
                class="rounded-2xl border p-4 flex flex-col gap-2"
                :class="alert.acknowledged ? 'opacity-60' : ''"
                style="border-color: var(--border-main); background-color: var(--bg-card);"
            >
                <div class="flex items-start justify-between gap-3">
                    <div class="flex items-start gap-3 min-w-0">
                        <span class="w-2.5 h-2.5 rounded-full mt-1.5 shrink-0" :class="severityDot(alert.severity)"></span>
                        <div class="min-w-0">
                            <div class="flex items-center gap-2 flex-wrap">
                                <h4 class="text-sm font-bold truncate" style="color: var(--text-main);">{{ alert.title }}</h4>
                                <span class="px-1.5 py-0.5 rounded text-[9px] font-black uppercase border" :class="severityStyle(alert.severity)">
                                    {{ alert.severity }}
                                </span>
                                <span class="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase" style="background-color: var(--bg-hover); color: var(--text-dim);">
                                    {{ alert.category }}
                                </span>
                                <span v-if="alert.occurrence_count > 1" class="text-[10px] font-mono" style="color: var(--text-dim);">
                                    ×{{ alert.occurrence_count }}
                                </span>
                            </div>
                            <p v-if="alert.message" class="text-xs mt-1 whitespace-pre-wrap break-words" style="color: var(--brand-text-dim);">
                                {{ alert.message }}
                            </p>
                            <p class="text-[10px] mt-1.5 font-mono" style="color: var(--text-dim);">
                                First seen {{ formatDate(alert.first_seen_at) }}
                                <span class="mx-1">·</span>
                                Last seen {{ relativeTime(alert.last_seen_at) }}
                                <span v-if="alert.related_username" class="ml-1">· user: {{ alert.related_username }}</span>
                            </p>
                        </div>
                    </div>

                    <div class="flex items-center gap-1 shrink-0">
                        <button
                            v-if="!alert.acknowledged"
                            @click="acknowledge(alert)"
                            class="p-1.5 rounded-lg themed-btn-surface hover:text-emerald-600"
                            title="Acknowledge"
                        >
                            <IconCheckCircle class="w-4 h-4" />
                        </button>
                        <button
                            @click="removeAlert(alert)"
                            class="p-1.5 rounded-lg themed-btn-surface hover:text-red-600"
                            title="Delete"
                        >
                            <IconTrash class="w-4 h-4" />
                        </button>
                    </div>
                </div>

                <div v-if="alert.acknowledged && alert.acknowledged_by" class="text-[10px] italic" style="color: var(--text-dim);">
                    Acknowledged by {{ alert.acknowledged_by }} on {{ formatDate(alert.acknowledged_at) }}
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
.themed-btn-surface { background-color: var(--brand-bg-elevated); border-color: var(--brand-border-main); color: var(--brand-text-dim); }
.themed-btn-surface:hover { background-color: var(--brand-bg-hover); color: var(--brand-text-main); }
</style>