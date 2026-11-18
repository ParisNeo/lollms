<script setup>
import { ref, computed, onMounted } from 'vue';
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';
import IconAdjustmentsHorizontal from '../../assets/icons/IconAdjustmentsHorizontal.vue';
import IconShieldCheck from '../../assets/icons/IconShieldCheck.vue';
import IconLock from '../../assets/icons/IconLock.vue';
import IconLockOpen from '../../assets/icons/IconLockOpen.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';

const uiStore = useUiStore();

const isLoading = ref(true);
const isSaving = ref(false);
const isApplying = ref(false);

const groups = ref([]);            // [{ id, label }]
const settings = ref({});          // { key: { key, label, type, group, group_label, nullable } }
const policies = ref({});          // { key: { user_editable, force_value } }

const searchTerm = ref('');
const activeGroup = ref('all');

// ── Data loading ────────────────────────────────────────────────────────────
async function loadPolicy() {
    isLoading.value = true;
    try {
        const { data } = await apiClient.get('/api/admin/settings-policy');
        groups.value = data.groups || [];
        settings.value = data.settings || {};
        policies.value = data.policies || {};
    } catch (e) {
        console.error('Failed to load settings policy', e);
        uiStore.addNotification('Failed to load settings policy.', 'error');
    } finally {
        isLoading.value = false;
    }
}

onMounted(loadPolicy);

// ── Derived views ───────────────────────────────────────────────────────────
const filteredSettings = computed(() => {
    const q = searchTerm.value.trim().toLowerCase();
    return Object.values(settings.value)
        .filter(s => activeGroup.value === 'all' || s.group === activeGroup.value)
        .filter(s => !q || s.key.toLowerCase().includes(q) || (s.label || '').toLowerCase().includes(q))
        .sort((a, b) => (a.group_label || '').localeCompare(b.group_label || '') || a.label.localeCompare(b.label));
});

const groupedSettings = computed(() => {
    const map = new Map();
    for (const s of filteredSettings.value) {
        if (!map.has(s.group)) map.set(s.group, { id: s.group, label: s.group_label, items: [] });
        map.get(s.group).items.push(s);
    }
    return Array.from(map.values());
});

const groupCounts = computed(() => {
    const counts = { all: Object.keys(settings.value).length };
    for (const s of Object.values(settings.value)) {
        counts[s.group] = (counts[s.group] || 0) + 1;
    }
    return counts;
});

// ── Policy mutation helpers ──────────────────────────────────────────────────
function ensurePolicy(key) {
    if (!policies.value[key]) {
        policies.value[key] = { user_editable: true, force_value: null };
    }
    return policies.value[key];
}

function isForced(key) {
    return ensurePolicy(key).force_value !== null && ensurePolicy(key).force_value !== undefined;
}

function toggleUserEditable(key) {
    const p = ensurePolicy(key);
    p.user_editable = !p.user_editable;
}

function toggleForced(key) {
    const p = ensurePolicy(key);
    if (isForced(key)) {
        p.force_value = null;
    } else {
        // Seed the forced value from a type-appropriate default so the input shows.
        const type = settings.value[key]?.type;
        p.force_value = type === 'boolean' ? false
            : type === 'integer' || type === 'float' ? 0
            : type === 'json' ? []
            : '';
        // A forced field is inherently non-editable by the user.
        p.user_editable = false;
    }
}

function setForceValue(key, value) {
    const p = ensurePolicy(key);
    const type = settings.value[key]?.type;
    if (type === 'boolean') {
        p.force_value = value === true || value === 'true';
    } else if (type === 'integer') {
        p.force_value = value === '' ? null : parseInt(value, 10);
    } else if (type === 'float') {
        p.force_value = value === '' ? null : parseFloat(value);
    } else {
        p.force_value = value;
    }
}

// ── Save / apply ────────────────────────────────────────────────────────────
async function savePolicies() {
    isSaving.value = true;
    try {
        // Strip any forced entries whose value was cleared to null (un-forced).
        const payload = {};
        for (const [key, p] of Object.entries(policies.value)) {
            payload[key] = {
                user_editable: isForced(key) ? false : !!p.user_editable,
                force_value: isForced(key) ? p.force_value : null,
            };
        }
        const { data } = await apiClient.put('/api/admin/settings-policy', payload);
        policies.value = data.policies || payload;
        uiStore.addNotification('Settings policy saved.', 'success');
    } catch (e) {
        console.error('Failed to save settings policy', e);
        uiStore.addNotification('Failed to save settings policy.', 'error');
    } finally {
        isSaving.value = false;
    }
}

async function applyToAllUsers() {
    isApplying.value = true;
    try {
        const { data } = await apiClient.post('/api/admin/settings-policy/apply');
        uiStore.addNotification(
            `Forced values applied. ${data.updated_users} user(s) updated.`,
            'success'
        );
    } catch (e) {
        console.error('Failed to apply policies', e);
        uiStore.addNotification('Failed to apply forced values.', 'error');
    } finally {
        isApplying.value = false;
    }
}

const forcedCount = computed(() =>
    Object.keys(policies.value).filter(k => isForced(k)).length
);
const lockedCount = computed(() =>
    Object.keys(policies.value).filter(k => !isForced(k) && policies.value[k]?.user_editable === false).length
);
</script>

<template>
    <div class="space-y-4">
        <!-- Header / summary -->
        <div class="themed-panel rounded-2xl border p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-purple-100 dark:bg-purple-950/50 text-purple-600 dark:text-purple-300 flex items-center justify-center shrink-0">
                    <IconAdjustmentsHorizontal class="w-5 h-5" />
                </div>
                <div>
                    <h3 class="text-sm font-black uppercase tracking-wider" style="color: var(--brand-text-main);">User Settings Policy</h3>
                    <p class="text-[11px]" style="color: var(--brand-text-dim);">
                        Decide which settings users may change, and pin values the admin forces for everyone.
                    </p>
                </div>
            </div>
            <div class="flex items-center gap-2 shrink-0">
                <span class="px-2.5 py-1 rounded-lg text-[10px] font-black uppercase bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300">
                    {{ forceCountLabel }}
                </span>
                <span class="px-2.5 py-1 rounded-lg text-[10px] font-black uppercase bg-blue-100 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300">
                    {{ lockedCountLabel }}
                </span>
            </div>
        </div>

        <!-- Controls -->
        <div class="themed-panel rounded-2xl border p-3 flex flex-col sm:flex-row gap-2 items-stretch sm:items-center">
            <input
                v-model="searchTerm"
                type="text"
                placeholder="Search settings..."
                class="input-field !py-1.5 text-xs grow"
            />
            <div class="flex items-center gap-2 shrink-0">
                <button
                    @click="applyToAllUsers"
                    :disabled="isApplying || isLoading"
                    class="btn btn-secondary btn-sm flex items-center gap-1.5 disabled:opacity-50"
                    title="Immediately push forced values onto all existing users"
                >
                    <IconCheckCircle class="w-4 h-4" />
                    <span>{{ isApplying ? 'Applying…' : 'Apply to All Users' }}</span>
                </button>
                <button
                    @click="savePolicies"
                    :disabled="isSaving || isLoading"
                    class="btn btn-primary btn-sm flex items-center gap-1.5 disabled:opacity-50"
                >
                    <IconShieldCheck class="w-4 h-4" />
                    <span>{{ isSaving ? 'Saving…' : 'Save Policy' }}</span>
                </button>
            </div>
        </div>

        <!-- Group filter chips -->
        <div class="flex flex-wrap gap-1.5">
            <button
                @click="activeGroup = 'all'"
                class="px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wide border transition-colors"
                :class="activeGroup === 'all' ? 'bg-purple-600 text-white border-purple-600' : 'themed-btn-surface'"
            >
                All ({{ groupCounts.all || 0 }})
            </button>
            <button
                v-for="g in groups"
                :key="g.id"
                @click="activeGroup = g.id"
                class="px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wide border transition-colors"
                :class="activeGroup === g.id ? 'bg-purple-600 text-white border-purple-600' : 'themed-btn-surface'"
            >
                {{ g.label }} ({{ groupCounts[g.id] || 0 }})
            </button>
        </div>

        <!-- Loading / empty -->
        <div v-if="isLoading" class="themed-panel rounded-2xl border p-8 text-center text-xs italic" style="color: var(--brand-text-dim);">
            Loading settings registry…
        </div>
        <div v-else-if="groupedSettings.length === 0" class="themed-panel rounded-2xl border p-8 text-center text-xs italic" style="color: var(--brand-text-dim);">
            No settings match your filters.
        </div>

        <!-- Groups -->
        <div v-else class="space-y-5">
            <div v-for="grp in groupedSettings" :key="grp.id" class="space-y-2">
                <div class="text-[10px] font-black uppercase tracking-widest px-1" style="color: var(--brand-text-dim);">
                    {{ grp.label }}
                </div>
                <div class="space-y-1.5">
                    <div
                        v-for="s in grp.items"
                        :key="s.key"
                        class="themed-panel rounded-xl border p-2.5 flex flex-col md:flex-row md:items-center md:justify-between gap-2"
                    >
                        <!-- Label + key + type -->
                        <div class="min-w-0 flex-1">
                            <div class="flex items-center gap-2 flex-wrap">
                                <span class="text-xs font-bold" style="color: var(--brand-text-main);">{{ s.label }}</span>
                                <span class="px-1.5 py-0.2 rounded text-[8px] font-mono uppercase bg-bg-hover" style="color: var(--brand-text-dim);">{{ s.type }}</span>
                                <span class="text-[9px] font-mono truncate" style="color: var(--brand-text-dim);">{{ s.key }}</span>
                            </div>
                        </div>

                        <!-- Controls -->
                        <div class="flex items-center gap-2 shrink-0 flex-wrap">
                            <!-- User editable toggle -->
                            <button
                                @click="toggleUserEditable(s.key)"
                                :disabled="isForced(s.key)"
                                class="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold border transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                                :class="!isForced(s.key) && policies[s.key]?.user_editable
                                    ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800'
                                    : 'themed-btn-surface'"
                                :title="isForced(s.key) ? 'Locked because a forced value is set' : 'Toggle user editability'"
                            >
                                <IconLockOpen v-if="!isForced(s.key) && policies[s.key]?.user_editable" class="w-3.5 h-3.5" />
                                <IconLock v-else class="w-3.5 h-3.5" />
                                <span>{{ !isForced(s.key) && policies[s.key]?.user_editable ? 'User editable' : 'Locked' }}</span>
                            </button>

                            <!-- Force toggle -->
                            <button
                                @click="toggleForced(s.key)"
                                class="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold border transition-colors"
                                :class="isForced(s.key)
                                    ? 'bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-800'
                                    : 'themed-btn-surface'"
                                :title="isForced(s.key) ? 'Un-force this setting' : 'Force a specific value for all users'"
                            >
                                <IconShieldCheck class="w-3.5 h-3.5" />
                                <span>{{ isForced(s.key) ? 'Forced' : 'Force value' }}</span>
                            </button>

                            <!-- Force value input -->
                            <div v-if="isForced(s.key)" class="flex items-center gap-1">
                                <select
                                    v-if="s.type === 'boolean'"
                                    :value="String(policies[s.key].force_value)"
                                    @change="setForceValue(s.key, $event.target.value === 'true')"
                                    class="input-field !py-1 text-xs"
                                >
                                    <option value="true">true</option>
                                    <option value="false">false</option>
                                </select>
                                <input
                                    v-else-if="s.type === 'integer' || s.type === 'float'"
                                    type="number"
                                    :step="s.type === 'float' ? 'any' : '1'"
                                    :value="policies[s.key].force_value"
                                    @input="setForceValue(s.key, $event.target.value)"
                                    class="input-field !py-1 text-xs w-24 font-mono"
                                />
                                <input
                                    v-else
                                    type="text"
                                    :value="s.type === 'json' ? JSON.stringify(policies[s.key].force_value) : policies[s.key].force_value"
                                    @input="setForceValue(s.key, $event.target.value)"
                                    class="input-field !py-1 text-xs w-40 font-mono"
                                    :placeholder="s.type === 'json' ? '[] / {} / value' : 'value'"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
export default {
    computed: {
        forceCountLabel() {
            return `${this.forcedCount} forced`;
        },
        lockedCountLabel() {
            return `${this.lockedCount} locked`;
        },
    },
};
</script>

<style scoped>
.themed-panel { background-color: var(--brand-bg-card); border-color: var(--brand-border-main); }
.themed-btn-surface { background-color: var(--brand-bg-elevated); border-color: var(--brand-border-main); color: var(--brand-text-dim); }
.themed-btn-surface:hover { background-color: var(--brand-bg-hover); color: var(--brand-text-main); }
</style>