<script setup>
import { ref, computed, onMounted } from 'vue';
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';
import IconLock from '../../assets/icons/IconLock.vue';
import IconLockOpen from '../../assets/icons/IconLockOpen.vue';
import IconShieldCheck from '../../assets/icons/IconShieldCheck.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconChevronDown from '../../assets/icons/IconChevronDown.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';

const uiStore = useUiStore();

const loading = ref(true);
const saving = ref(false);
const applying = ref(false);
const searchTerm = ref('');
const activeCategory = ref('All');
const activeStatus = ref('all'); // 'all' | 'pinned' | 'locked' | 'custom'
const collapsedCategories = ref({});

// Catalog from backend (authoritative list of governable fields).
const fields = ref([]);      // [{ field_name, label, category, type, choices, description }]
// Last saved policy state keyed by field_name.
const policies = ref({});    // { field_name: { locked, forced, forced_value } }
// Working copy edited by the UI; diffed against `policies` to compute the payload.
const draft = ref({});       // { field_name: { locked, forced, forced_value } }

// ── Derived views ───────────────────────────────────────────────────────────
const categories = computed(() => {
    const seen = new Set(fields.value.map((f) => f.category));
    return ['All', ...Array.from(seen).sort((a, b) => a.localeCompare(b))];
});

function fieldState(fieldName) {
    return draft.value[fieldName] || { locked: false, forced: false, forced_value: null };
}

const filteredGroups = computed(() => {
    const q = searchTerm.value.trim().toLowerCase();
    const grouped = {};

    for (const field of fields.value) {
        if (activeCategory.value !== 'All' && field.category !== activeCategory.value) continue;

        const state = fieldState(field.field_name);

        // Status quick-filters let an admin jump straight to what matters.
        if (activeStatus.value === 'pinned' && !state.forced) continue;
        if (activeStatus.value === 'locked' && !(state.locked && !state.forced)) continue;
        if (activeStatus.value === 'custom' && !state.forced && !state.locked) continue;

        // Search across the human-visible label, technical key, category, and description.
        if (q) {
            const haystack = [
                field.label,
                field.field_name,
                field.category,
                field.description || '',
            ].join(' ').toLowerCase();
            if (!haystack.includes(q)) continue;
        }

        (grouped[field.category] = grouped[field.category] || []).push({ ...field, ...state });
    }

    return Object.entries(grouped)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([category, items]) => ({ category, items }));
});

// Total number of fields currently passing all filters (for the "N shown" counter).
const visibleFieldCount = computed(() =>
    filteredGroups.value.reduce((sum, grp) => sum + grp.items.length, 0)
);

function sameState(a, b) {
    return a.locked === b.locked
        && a.forced === b.forced
        && JSON.stringify(a.forced_value) === JSON.stringify(b.forced_value);
}

const dirtyFieldCount = computed(() => {
    let count = 0;
    for (const field of fields.value) {
        const saved = policies.value[field.field_name] || { locked: false, forced: false, forced_value: null };
        const current = draft.value[field.field_name] || { locked: false, forced: false, forced_value: null };
        if (!sameState(saved, current)) count += 1;
    }
    return count;
});

const forcedCount = computed(() =>
    Object.values(draft.value).filter((p) => p.forced).length
);
const lockedCount = computed(() =>
    Object.values(draft.value).filter((p) => p.locked && !p.forced).length
);

// ── Draft helpers ────────────────────────────────────────────────────────────
function ensureDraft(fieldName) {
    if (!draft.value[fieldName]) {
        const saved = policies.value[fieldName] || { locked: false, forced: false, forced_value: null };
        draft.value[fieldName] = { locked: !!saved.locked, forced: !!saved.forced, forced_value: saved.forced_value };
    }
    return draft.value[fieldName];
}

function toggleLocked(field) {
    const d = ensureDraft(field.field_name);
    d.locked = !d.locked;
}

function toggleForced(field) {
    const d = ensureDraft(field.field_name);
    d.forced = !d.forced;
    if (d.forced && d.forced_value === null) {
        // Seed a sensible starting value for the type so the editor is usable.
        if (field.type === 'boolean') d.forced_value = false;
        else if (field.type === 'int' || field.type === 'float') d.forced_value = 0;
        else if (field.type === 'enum' && field.choices?.length) d.forced_value = field.choices[0];
        else d.forced_value = '';
    }
    if (!d.forced) {
        // Un-pinning clears the forced value; keep the lock toggle as-is.
        d.forced_value = null;
    }
}

function setForcedValue(field, value) {
    const d = ensureDraft(field.field_name);
    if (field.type === 'int' || field.type === 'float') {
        const num = parseFloat(value);
        d.forced_value = Number.isNaN(num) ? 0 : num;
    } else {
        d.forced_value = value;
    }
}

function toggleCategory(category) {
    collapsedCategories.value[category] = !collapsedCategories.value[category];
}

// ── API ──────────────────────────────────────────────────────────────────────
function normalizePolicies(policyMap) {
    const normalized = {};
    for (const field of fields.value) {
        const p = policyMap?.[field.field_name];
        normalized[field.field_name] = p
            ? { locked: !!p.locked, forced: !!p.forced, forced_value: p.forced_value }
            : { locked: false, forced: false, forced_value: null };
    }
    return normalized;
}

async function fetchPolicy() {
    loading.value = true;
    try {
        const res = await apiClient.get('/api/admin/settings-policy');
        fields.value = res.data.fields || [];
        const normalized = normalizePolicies(res.data.policies);
        policies.value = normalized;
        draft.value = JSON.parse(JSON.stringify(normalized));
    } catch (e) {
        uiStore.addNotification(e.response?.data?.detail || 'Failed to load settings policy.', 'error');
    } finally {
        loading.value = false;
    }
}

async function saveChanges() {
    if (dirtyFieldCount.value === 0) return;

    const payload = { policies: {} };
    for (const field of fields.value) {
        const saved = policies.value[field.field_name] || { locked: false, forced: false, forced_value: null };
        const current = draft.value[field.field_name] || { locked: false, forced: false, forced_value: null };
        if (sameState(saved, current)) continue;

        payload.policies[field.field_name] = {
            locked: current.locked,
            forced: current.forced,
            // Only send a concrete value when the field is actually pinned.
            forced_value: current.forced ? current.forced_value : null,
        };
    }

    saving.value = true;
    try {
        const res = await apiClient.put('/api/admin/settings-policy', payload);
        fields.value = res.data.fields || fields.value;
        const normalized = normalizePolicies(res.data.policies);
        policies.value = normalized;
        draft.value = JSON.parse(JSON.stringify(normalized));
        uiStore.addNotification('Settings policy saved.', 'success');
    } catch (e) {
        uiStore.addNotification(e.response?.data?.detail || 'Failed to save settings policy.', 'error');
    } finally {
        saving.value = false;
    }
}

async function applyToAllUsers() {
    applying.value = true;
    try {
        const res = await apiClient.post('/api/admin/settings-policy/apply');
        const updated = res.data.updated_users ?? 0;
        const forcedFields = res.data.forced_fields ?? 0;
        uiStore.addNotification(
            `Forced values applied — ${forcedFields} field(s), ${updated} user(s) updated.`,
            'success'
        );
    } catch (e) {
        uiStore.addNotification(e.response?.data?.detail || 'Failed to apply forced values.', 'error');
    } finally {
        applying.value = false;
    }
}

function discardChanges() {
    draft.value = JSON.parse(JSON.stringify(policies.value));
}

onMounted(fetchPolicy);
</script>

<template>
    <div class="h-full flex flex-col overflow-hidden" style="background-color: var(--bg-app);">
        <!-- Sticky toolbar -->
        <div class="shrink-0 px-6 py-4 border-b space-y-3" style="border-color: var(--border-main); background-color: var(--bg-card);">
            <div class="flex items-start justify-between gap-4 flex-wrap">
                <div class="min-w-0">
                    <h3 class="text-lg font-black tracking-tight flex items-center gap-2" style="color: var(--text-main);">
                        <IconShieldCheck class="w-5 h-5 text-indigo-500" />
                        Settings Policy
                    </h3>
                    <p class="text-xs mt-0.5" style="color: var(--text-dim);">
                        Control which user-settable settings are <strong>locked</strong> (read-only) or <strong>pinned</strong> to an admin-forced value.
                    </p>
                </div>
                <div class="flex items-center gap-2 shrink-0 flex-wrap">
                    <span class="px-2.5 py-1 rounded-lg text-[10px] font-black uppercase bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300">
                        {{ forcedCount }} pinned
                    </span>
                    <span class="px-2.5 py-1 rounded-lg text-[10px] font-black uppercase bg-blue-100 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300">
                        {{ lockedCount }} locked
                    </span>
                    <button
                        type="button"
                        @click="applyToAllUsers"
                        class="btn btn-secondary btn-sm flex items-center gap-1.5"
                        :disabled="applying || loading"
                        title="Immediately push every pinned value onto all existing users"
                    >
                        <IconCheckCircle class="w-4 h-4" />
                        <span>{{ applying ? 'Applying…' : 'Apply to All Users' }}</span>
                    </button>
                    <button
                        v-if="dirtyFieldCount > 0"
                        type="button"
                        @click="discardChanges"
                        class="btn btn-secondary btn-sm flex items-center gap-1.5"
                        :disabled="saving"
                    >
                        <IconArrowPath class="w-4 h-4" />
                        <span>Discard</span>
                    </button>
                    <button
                        type="button"
                        @click="saveChanges"
                        class="btn btn-primary btn-sm"
                        :disabled="saving || dirtyFieldCount === 0"
                    >
                        <span v-if="saving">Saving…</span>
                        <span v-else>Save{{ dirtyFieldCount > 0 ? ` (${dirtyFieldCount})` : '' }}</span>
                    </button>
                </div>
            </div>

            <!-- Filters -->
            <div class="flex items-center gap-2 flex-wrap">
                <div class="relative flex-1 min-w-[220px] max-w-md">
                    <IconMagnifyingGlass class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style="color: var(--text-dim);" />
                    <input
                        v-model="searchTerm"
                        type="text"
                        placeholder="Search all…"
                        class="input-field pl-9 pr-9 w-full text-sm"
                    />
                    <button
                        v-if="searchTerm"
                        type="button"
                        @click="searchTerm = ''"
                        class="absolute right-2 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center rounded-full hover:bg-black/10 dark:hover:bg-white/10 cursor-pointer"
                        title="Clear search"
                        style="color: var(--text-dim);"
                    >
                        ×
                    </button>
                </div>

                <!-- Status quick-filters -->
                <div class="flex items-center gap-1">
                    <button
                        v-for="st in [
                            { id: 'all', label: 'All' },
                            { id: 'custom', label: 'Customized' },
                            { id: 'pinned', label: 'Pinned' },
                            { id: 'locked', label: 'Locked' },
                        ]"
                        :key="st.id"
                        type="button"
                        @click="activeStatus = st.id"
                        class="px-2.5 py-1 rounded-lg text-[11px] font-bold whitespace-nowrap transition-colors cursor-pointer border"
                        :class="activeStatus === st.id
                            ? 'bg-emerald-600 text-white border-emerald-600 shadow-sm'
                            : 'themed-btn-surface'"
                    >
                        {{ st.label }}
                    </button>
                </div>

                <span class="text-[11px] font-mono ml-auto shrink-0" style="color: var(--text-dim);">
                    {{ visibleFieldCount }} / {{ fields.length }} fields
                </span>
            </div>

            <!-- Category chips -->
            <div class="flex items-center gap-1 overflow-x-auto custom-scrollbar">
                <button
                    v-for="cat in categories"
                    :key="cat"
                    type="button"
                    @click="activeCategory = cat"
                    class="px-2.5 py-1 rounded-lg text-[11px] font-bold whitespace-nowrap transition-colors cursor-pointer border"
                    :class="activeCategory === cat
                        ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                        : 'themed-btn-surface'"
                >
                    {{ cat }}
                </button>
            </div>
        </div>

        <!-- Body -->
        <div class="grow overflow-y-auto custom-scrollbar p-6 space-y-4">
            <!-- In-body quick search (stays visible while scrolling the flag list) -->
            <div class="sticky top-0 z-10 -mx-1 px-1 pb-2" style="background-color: var(--bg-app);">
                <div class="relative">
                    <IconMagnifyingGlass class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style="color: var(--text-dim);" />
                    <input
                        v-model="searchTerm"
                        type="text"
                        placeholder="Search flags by name, key, category or description…"
                        class="input-field pl-9 pr-9 w-full text-sm shadow-sm"
                    />
                    <button
                        v-if="searchTerm"
                        type="button"
                        @click="searchTerm = ''"
                        class="absolute right-2 top-1/2 -translate-y-1/2 w-5 h-5 flex items-center justify-center rounded-full hover:bg-black/10 dark:hover:bg-white/10 cursor-pointer"
                        title="Clear search"
                        style="color: var(--text-dim);"
                    >
                        ×
                    </button>
                </div>
                <div v-if="searchTerm" class="text-[10px] mt-1 px-1 font-mono" style="color: var(--text-dim);">
                    {{ visibleFieldCount }} matching flag{{ visibleFieldCount === 1 ? '' : 's' }}
                </div>
            </div>

            <div v-if="loading" class="text-center py-16 text-sm italic" style="color: var(--text-dim);">
                Loading settings policy…
            </div>

            <div v-else-if="filteredGroups.length === 0" class="text-center py-16 text-sm italic" style="color: var(--text-dim);">
                No fields match the current filters.
            </div>

            <div
                v-for="grp in filteredGroups"
                :key="grp.category"
                class="rounded-2xl border overflow-hidden"
                style="border-color: var(--border-main); background-color: var(--bg-card);"
            >
                <!-- Category header -->
                <button
                    type="button"
                    @click="toggleCategory(grp.category)"
                    class="w-full flex items-center justify-between px-4 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors cursor-pointer text-left"
                >
                    <div class="flex items-center gap-2">
                        <IconChevronDown v-if="!collapsedCategories[grp.category]" class="w-4 h-4" style="color: var(--text-dim);" />
                        <IconChevronRight v-else class="w-4 h-4" style="color: var(--text-dim);" />
                        <span class="text-sm font-black tracking-wide uppercase" style="color: var(--text-main);">{{ grp.category }}</span>
                        <span class="text-[10px] font-mono px-1.5 py-0.5 rounded-full" style="background-color: var(--bg-hover); color: var(--text-dim);">
                            {{ grp.items.length }}
                        </span>
                    </div>
                </button>

                <!-- Field rows -->
                <div v-if="!collapsedCategories[grp.category]" class="divide-y" style="border-color: var(--border-muted);">
                    <div
                        v-for="field in grp.items"
                        :key="field.field_name"
                        class="px-4 py-3 grid grid-cols-1 lg:grid-cols-12 gap-3 items-center"
                        style="border-color: var(--border-muted);"
                    >
                        <!-- Field label -->
                        <div class="lg:col-span-4 min-w-0">
                            <div class="text-sm font-bold truncate" style="color: var(--text-main);">{{ field.label }}</div>
                            <div class="text-[10px] font-mono truncate" style="color: var(--text-dim);">
                                {{ field.field_name }}
                                <span class="ml-1 px-1 py-0.5 rounded uppercase" style="background-color: var(--bg-hover);">{{ field.type }}</span>
                            </div>
                        </div>

                        <!-- Lock toggle -->
                        <div class="lg:col-span-2 flex items-center gap-2">
                            <button
                                type="button"
                                @click="toggleLocked(field)"
                                class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200"
                                :class="draft[field.field_name]?.locked ? 'bg-red-600' : 'bg-bg-hover'"
                                :title="draft[field.field_name]?.locked ? 'Unlock (user may edit)' : 'Lock (user cannot edit)'"
                            >
                                <span
                                    :class="[draft[field.field_name]?.locked ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 my-[2px] ml-[2px]']"
                                ></span>
                            </button>
                            <span class="text-[10px] font-bold uppercase flex items-center gap-1" :class="draft[field.field_name]?.locked ? 'text-red-600 dark:text-red-400' : ''" style="color: var(--text-dim);">
                                <IconLock v-if="draft[field.field_name]?.locked" class="w-3 h-3" />
                                <IconLockOpen v-else class="w-3 h-3" />
                                {{ draft[field.field_name]?.locked ? 'Locked' : 'Free' }}
                            </span>
                        </div>

                        <!-- Force toggle -->
                        <div class="lg:col-span-2 flex items-center gap-2">
                            <button
                                type="button"
                                @click="toggleForced(field)"
                                class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200"
                                :class="draft[field.field_name]?.forced ? 'bg-amber-500' : 'bg-bg-hover'"
                                :title="draft[field.field_name]?.forced ? 'Unpin the forced value' : 'Pin to an admin-forced value'"
                            >
                                <span
                                    :class="[draft[field.field_name]?.forced ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 my-[2px] ml-[2px]']"
                                ></span>
                            </button>
                            <span class="text-[10px] font-bold uppercase" :class="draft[field.field_name]?.forced ? 'text-amber-600 dark:text-amber-400' : ''" style="color: var(--text-dim);">
                                {{ draft[field.field_name]?.forced ? 'Pinned' : 'User' }}
                            </span>
                        </div>

                        <!-- Forced value editor -->
                        <div class="lg:col-span-4 min-w-0">
                            <div v-if="draft[field.field_name]?.forced" class="flex items-center gap-2">
                                <!-- Boolean -->
                                <input
                                    v-if="field.type === 'boolean'"
                                    type="checkbox"
                                    :checked="!!draft[field.field_name]?.forced_value"
                                    @change="setForcedValue(field, $event.target.checked)"
                                    class="w-4 h-4 rounded accent-amber-600"
                                />
                                <!-- Enum -->
                                <select
                                    v-else-if="field.type === 'enum' && field.choices?.length"
                                    :value="draft[field.field_name]?.forced_value"
                                    @change="setForcedValue(field, $event.target.value)"
                                    class="input-field !py-1 text-xs w-full"
                                >
                                    <option v-for="ch in field.choices" :key="ch" :value="ch">{{ ch }}</option>
                                </select>
                                <!-- Numeric -->
                                <input
                                    v-else-if="field.type === 'int' || field.type === 'float'"
                                    type="number"
                                    :step="field.type === 'float' ? '0.01' : '1'"
                                    :value="draft[field.field_name]?.forced_value ?? 0"
                                    @input="setForcedValue(field, $event.target.value)"
                                    class="input-field !py-1 text-xs w-full font-mono"
                                />
                                <!-- String / JSON / fallback -->
                                <input
                                    v-else
                                    type="text"
                                    :value="draft[field.field_name]?.forced_value ?? ''"
                                    @input="setForcedValue(field, $event.target.value)"
                                    class="input-field !py-1 text-xs w-full font-mono"
                                    placeholder="Admin-forced value…"
                                />
                            </div>
                            <span v-else class="text-[10px] italic" style="color: var(--text-dim);">
                                {{ field.type === 'boolean' ? 'Default: user may toggle' : 'Default: user may edit' }}
                            </span>
                        </div>
                    </div>
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