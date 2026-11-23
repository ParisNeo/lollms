
<script setup>
/**
 * ModelProfilesGrid
 * -----------------
 * Modality-agnostic CRUD surface for *Universal Model Profiles* — the reusable
 * "usable model" layer that sits above physical bindings.
 *
 * One instance renders every modality when given its `bindingType`:
 *     <ModelProfilesGrid binding-type="tti" />
 *
 * Responsibilities:
 *   - Load all connections of the modality, then aggregate their model lists
 *     (each connection returns raw models + the profiles/aliases pinned to it).
 *   - Search by title/description/model name, and filter by binding connection.
 *   - Create / edit / delete profiles through the per-modality store actions
 *     (save…ModelAlias / delete…ModelAlias) resolved from bindingConfigs.
 *   - Multi-select rows for bulk delete / vision toggle / context-size update.
 *
 * The profile "shape" (which editable fields to show) is driven by the
 * descriptor's `aliasFields`, so LLM exposes vision/context/reasoning knobs
 * while image/audio modalities stay minimal — with zero per-type branching here.
 */
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useAdminStore } from '../../../stores/admin';
import { useUiStore } from '../../../stores/ui';
import {
    BINDING_TYPES,
    bindingActions,
    buildDefaultProfilePayload,
    collectTakenProfileNames,
    resolveBindingAction,
} from './bindingConfigs';

import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconMagnifyingGlass from '../../../assets/icons/IconMagnifyingGlass.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconClose from '../../../assets/icons/IconClose.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';

const props = defineProps({
    bindingType: { type: String, required: true },
    // Optional scope: when a binding is provided, ONLY that binding's profiles
    // are loaded/rendered. When omitted (cross-binding "Universal Profiles"
    // view), every binding of this modality is aggregated.
    binding: { type: Object, default: null },
});

const adminStore = useAdminStore();
const uiStore = useUiStore();

const cfg = computed(() => BINDING_TYPES[props.bindingType] || null);
const actions = computed(() => bindingActions(props.bindingType));

// Whether the grid is scoped to a single binding card (vs. the cross-binding
// "Universal Profiles" view which aggregates every connection).
const isScopedToBinding = computed(() => Boolean(props.binding?.id));

// Resolve the reactive store array of physical connections for this modality.
// e.g. 'tti' -> adminStore.ttiBindings ; 'llm' -> adminStore.bindings
const allConnections = computed(() => {
    const refName = actions.value.fetch.replace(/^fetch/, '');
    const normalized = refName.charAt(0).toLowerCase() + refName.slice(1);
    return adminStore[normalized] || [];
});

// The connections this grid actually reads. When scoped to a binding, we
// surface ONLY that card's binding; the cross-binding view keeps all of them.
const connections = computed(() => {
    if (!isScopedToBinding.value) return allConnections.value;
    return allConnections.value.filter((c) => c?.id === props.binding.id);
});

// ── Loading state ────────────────────────────────────────────────────────────
const isLoading = ref(false);
const isSaving = ref(false);
const loadError = ref('');

// ── Aggregated profiles ──────────────────────────────────────────────────────
// Each row: { key, bindingId, bindingAlias, originalModelName, modelName, alias, title, description, isInstalled }
const profiles = ref([]);

// ── Search / filter ──────────────────────────────────────────────────────────
const searchQuery = ref('');
const selectedBindingAlias = ref('');

const bindingAliasOptions = computed(() => {
    const seen = new Set();
    const opts = [];
    for (const c of connections.value) {
        if (c?.alias && !seen.has(c.alias)) {
            seen.add(c.alias);
            opts.push({ alias: c.alias, title: c.alias, name: c.name, id: c.id });
        }
    }
    return opts;
});

const filteredProfiles = computed(() => {
    const q = searchQuery.value.trim().toLowerCase();
    return profiles.value.filter((p) => {
        if (selectedBindingAlias.value && p.bindingAlias !== selectedBindingAlias.value) {
            return false;
        }
        if (!q) return true;
        const haystack = [
            p.title,
            p.description,
            p.originalModelName,
            p.modelName,
            p.bindingAlias,
        ]
            .filter(Boolean)
            .join(' ')
            .toLowerCase();
        return haystack.includes(q);
    });
});

const hasAnyBinding = computed(() => connections.value.length > 0);
const isLlm = computed(() => props.bindingType === 'llm');

// ── Detected-but-unaliased models (per connection) ─────────────────────────
// Mirrors the "Engine Models" section of the legacy manager so every modality
// can build profiles for freshly-detected models straight from the grid.
// Map<connectionId, Array<{ name, description }>>
const detectedByConnection = ref(new Map());
const isLoadingDetected = ref(false);
const quickCreatingName = ref(null);
const isBulkBuilding = ref(false);

// Flatten for rendering when scoped to a single binding; in cross-binding mode
// we group by connection so the user knows which server each row belongs to.
const detectedRows = computed(() => {
    const rows = [];
    for (const conn of collectSourceBindings()) {
        const raw = detectedByConnection.value.get(conn.id) || [];
        const aliased = new Set(Object.keys(aliasesFromBinding(conn)));
        for (const m of raw) {
            const name = m?.original_model_name || m?.name || m;
            if (!name || aliased.has(name)) continue;
            rows.push({
                connectionId: conn.id,
                connectionAlias: conn.alias,
                name,
                description: typeof m === 'object' ? (m.description || '') : '',
            });
        }
    }
    return rows;
});

const detectedCount = computed(() => detectedRows.value.length);

async function loadDetectedModels() {
    const fetchFn = resolveBindingAction(adminStore, props.bindingType, 'fetchModels');
    if (!fetchFn) {
        detectedByConnection.value = new Map();
        return;
    }
    isLoadingDetected.value = true;
    try {
        const next = new Map();
        for (const conn of collectSourceBindings()) {
            try {
                const models = await fetchFn(conn.id);
                next.set(conn.id, Array.isArray(models) ? models : []);
            } catch {
                next.set(conn.id, []);
            }
        }
        detectedByConnection.value = next;
    } finally {
        isLoadingDetected.value = false;
    }
}

async function createProfileForDetected(row) {
    const saveFn = resolveBindingAction(adminStore, props.bindingType, 'saveAlias');
    if (!saveFn) {
        uiStore.addNotification('Profile creation is not supported for this modality.', 'warning');
        return;
    }
    const binding = collectSourceBindings().find((b) => b.id === row.connectionId);
    if (!binding) return;
    quickCreatingName.value = row.name;
    try {
        const taken = collectTakenProfileNames(binding);
        const payload = buildDefaultProfilePayload(binding, props.bindingType, row.name, taken);
        await saveFn(binding.id, payload);
        uiStore.addNotification(`Profile '${payload.alias.title}' created.`, 'success');
        await loadAllProfiles();
        await loadDetectedModels();
    } catch (e) {
        uiStore.addNotification(e?.response?.data?.detail || 'Failed to create profile.', 'error');
    } finally {
        quickCreatingName.value = null;
    }
}

async function buildProfilesForAllDetected() {
    const saveFn = resolveBindingAction(adminStore, props.bindingType, 'saveAlias');
    if (!saveFn) {
        uiStore.addNotification('Profile creation is not supported for this modality.', 'warning');
        return;
    }
    const rows = detectedRows.value;
    if (rows.length === 0) {
        uiStore.addNotification('No models to build profiles for.', 'info');
        return;
    }
    // Snapshot per-binding taken-name sets so collisions across a bulk pass are
    // handled exactly like a manual create.
    const takenByBinding = new Map();
    for (const conn of collectSourceBindings()) {
        takenByBinding.set(conn.id, collectTakenProfileNames(conn));
    }
    isBulkBuilding.value = true;
    let created = 0;
    let failed = 0;
    for (const row of rows) {
        const binding = collectSourceBindings().find((b) => b.id === row.connectionId);
        if (!binding) continue;
        const taken = takenByBinding.get(binding.id) || collectTakenProfileNames(binding);
        try {
            const payload = buildDefaultProfilePayload(binding, props.bindingType, row.name, taken);
            await saveFn(binding.id, payload);
            created += 1;
        } catch {
            failed += 1;
        }
    }
    isBulkBuilding.value = false;
    await loadAllProfiles();
    await loadDetectedModels();
    uiStore.addNotification(
        `Created ${created} profile(s)${failed ? ` · ${failed} failed` : ''}.`,
        failed ? 'warning' : 'success'
    );
}

// ── Editing drawer state ─────────────────────────────────────────────────────
const isEditorOpen = ref(false);
const isNewProfile = ref(false);
const editorError = ref('');
const editorForm = reactive({
    bindingId: null,
    bindingAlias: '',
    originalModelName: '',
    profile: {},
});

const editorFields = computed(() => cfg.value?.aliasFields || []);

// ── Multi-select state ───────────────────────────────────────────────────────
const selectedKeys = ref(new Set());
const isBulkWorking = ref(false);
const bulkContextSize = ref('');

const selectableRows = computed(() => filteredProfiles.value);
const allRowsSelected = computed(
    () =>
        selectableRows.value.length > 0 &&
        selectableRows.value.every((p) => selectedKeys.value.has(p.key))
);
const someRowsSelected = computed(
    () =>
        selectableRows.value.some((p) => selectedKeys.value.has(p.key)) &&
        !allRowsSelected.value
);
const selectedCount = computed(() => selectedKeys.value.size);

function isSelected(rowKey) {
    return selectedKeys.value.has(rowKey);
}
function toggleSelect(rowKey) {
    const next = new Set(selectedKeys.value);
    if (next.has(rowKey)) next.delete(rowKey);
    else next.add(rowKey);
    selectedKeys.value = next;
}
function toggleSelectAll() {
    if (allRowsSelected.value) {
        selectedKeys.value = new Set();
    } else {
        selectedKeys.value = new Set(selectableRows.value.map((p) => p.key));
    }
}
function clearSelection() {
    selectedKeys.value = new Set();
}
function selectedRows() {
    const keys = selectedKeys.value;
    return profiles.value.filter((p) => keys.has(p.key));
}

// Prune the selection when the visible list changes (search/filter/reload) so
// the counter never references rows that are no longer visible.
watch(filteredProfiles, (list) => {
    if (selectedKeys.value.size === 0) return;
    const visibleKeys = new Set(list.map((p) => p.key));
    const next = new Set();
    for (const key of selectedKeys.value) {
        if (visibleKeys.has(key)) next.add(key);
    }
    if (next.size !== selectedKeys.value.size) {
        selectedKeys.value = next;
    }
});

// ── Data loading ─────────────────────────────────────────────────────────────
function normalizeAliasEntry(entry) {
    // The backend alias payload can carry a nested `alias` object or the field
    // values directly on the record. Normalise to a single `alias` dictionary.
    const rawAlias = entry?.alias;
    const alias = rawAlias && typeof rawAlias === 'object'
        ? { ...rawAlias }
        : { ...(entry || {}) };
    // Ensure model_name is present so edits round-trip correctly.
    if (!alias.model_name) {
        alias.model_name = entry?.original_model_name || alias.model_name || '';
    }
    return alias;
}

function buildRow(binding, originalModelName, aliasEntry) {
    const alias = normalizeAliasEntry(aliasEntry);
    const title = alias.title || alias.name || originalModelName;
    const modelName = alias.model_name || originalModelName;
    return {
        key: `${binding.id}::${originalModelName}`,
        bindingId: binding.id,
        bindingAlias: binding.alias,
        bindingType: props.bindingType,
        originalModelName,
        modelName,
        title,
        description: alias.description || '',
        alias,
        isInstalled: Boolean(alias.is_installed ?? alias.is_available),
    };
}

// Scoped mode: prefer the parent-provided binding record (which has the
// freshest `model_aliases` after a save) and fall back to the store copy.
function collectSourceBindings() {
    const list = [];
    const seenIds = new Set();
    if (isScopedToBinding.value && props.binding?.id) {
        list.push(props.binding);
        seenIds.add(props.binding.id);
    }
    for (const c of connections.value || []) {
        if (!c?.id || seenIds.has(c.id)) continue;
        list.push(c);
        seenIds.add(c.id);
    }
    return list;
}

function aliasesFromBinding(binding) {
    let aliases = binding?.model_aliases;
    if (typeof aliases === 'string') {
        try {
            aliases = JSON.parse(aliases);
        } catch {
            aliases = {};
        }
    }
    if (!aliases || typeof aliases !== 'object') return {};
    return aliases;
}

async function loadAllProfiles() {
    isLoading.value = true;
    loadError.value = '';
    try {
        const rows = [];
        for (const binding of collectSourceBindings()) {
            const aliases = aliasesFromBinding(binding);
            for (const [originalModelName, aliasEntry] of Object.entries(aliases)) {
                if (!originalModelName) continue;
                rows.push(buildRow(binding, originalModelName, aliasEntry));
            }
        }
        // Preserve selection across reloads for rows that still exist.
        const existingKeys = new Set(rows.map((r) => r.key));
        const nextSelected = new Set();
        for (const key of selectedKeys.value) {
            if (existingKeys.has(key)) nextSelected.add(key);
        }
        selectedKeys.value = nextSelected;

        profiles.value = rows.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
    } catch (e) {
        loadError.value = e?.response?.data?.detail || 'Failed to load model profiles.';
        uiStore.addNotification(loadError.value, 'error');
        profiles.value = [];
    } finally {
        isLoading.value = false;
    }
}

// ── Editor CRUD ──────────────────────────────────────────────────────────────
function openCreate() {
    isNewProfile.value = true;
    editorError.value = '';
    editorForm.bindingId = isScopedToBinding.value ? props.binding.id : (connections.value[0]?.id ?? null);
    editorForm.bindingAlias = isScopedToBinding.value
        ? props.binding.alias
        : (connections.value[0]?.alias ?? '');
    editorForm.originalModelName = '';
    editorForm.profile = {};
    isEditorOpen.value = true;
}

function openEdit(row) {
    isNewProfile.value = false;
    editorError.value = '';
    editorForm.bindingId = row.bindingId;
    editorForm.bindingAlias = row.bindingAlias;
    editorForm.originalModelName = row.originalModelName;
    editorForm.profile = JSON.parse(JSON.stringify(row.alias || {}));
    isEditorOpen.value = true;
}

function closeEditor() {
    isEditorOpen.value = false;
    editorError.value = '';
}

async function saveEditor() {
    const saveFn = adminStore[actions.value.saveAlias];
    if (typeof saveFn !== 'function') {
        editorError.value = 'Saving profiles is not supported for this modality.';
        return;
    }
    const binding = connections.value.find((b) => b.id === editorForm.bindingId) || props.binding;
    if (!binding?.id) {
        editorError.value = 'A target binding must be selected.';
        return;
    }
    const originalModelName = (editorForm.originalModelName || '').trim();
    if (!originalModelName) {
        editorError.value = 'Model name is required.';
        return;
    }

    const alias = JSON.parse(JSON.stringify(editorForm.profile || {}));
    alias.model_name = alias.model_name || originalModelName;
    if (isLlm.value) {
        if (alias.has_vision !== undefined) {
            alias.vision_enabled = Boolean(alias.has_vision);
        } else if (alias.vision_enabled !== undefined) {
            alias.has_vision = Boolean(alias.vision_enabled);
        }
    }

    isSaving.value = true;
    editorError.value = '';
    try {
        await saveFn.call(adminStore, binding.id, {
            original_model_name: originalModelName,
            new_model_name: alias.model_name,
            alias,
        });
        uiStore.addNotification(`Profile saved for '${alias.title || originalModelName}'.`, 'success');
        closeEditor();
        await loadAllProfiles();
    } catch (e) {
        editorError.value = e?.response?.data?.detail || 'Failed to save profile.';
    } finally {
        isSaving.value = false;
    }
}

async function deleteProfile(row) {
    const deleteFn = adminStore[actions.value.deleteAlias];
    if (typeof deleteFn !== 'function') {
        uiStore.addNotification('Deleting profiles is not supported for this modality.', 'warning');
        return;
    }
    const confirmed = await uiStore.showConfirmation({
        title: `Delete profile '${row.title || row.originalModelName}'?`,
        message: 'The model profile will be removed. The underlying model stays on its binding.',
        confirmText: 'Delete',
    });
    if (!confirmed) return;
    try {
        await deleteFn.call(adminStore, row.bindingId, row.originalModelName);
        uiStore.addNotification('Profile deleted.', 'success');
        await loadAllProfiles();
    } catch (e) {
        uiStore.addNotification(
            e?.response?.data?.detail || 'Failed to delete profile.',
            'error'
        );
    }
}

// ── Bulk operations ──────────────────────────────────────────────────────────
async function bulkDelete() {
    const rows = selectedRows();
    if (rows.length === 0) return;
    const deleteFn = adminStore[actions.value.deleteAlias];
    if (typeof deleteFn !== 'function') {
        uiStore.addNotification('Deleting profiles is not supported for this modality.', 'warning');
        return;
    }
    const confirmed = await uiStore.showConfirmation({
        title: `Delete ${rows.length} profile(s)?`,
        message: 'The selected model profiles will be permanently removed. The underlying models stay on their bindings.',
        confirmText: 'Delete',
    });
    if (!confirmed) return;

    isBulkWorking.value = true;
    let deleted = 0;
    let failed = 0;
    for (const row of rows) {
        try {
            await deleteFn.call(adminStore, row.bindingId, row.originalModelName);
            deleted++;
        } catch {
            failed++;
        }
    }
    isBulkWorking.value = false;
    clearSelection();
    await loadAllProfiles();
    uiStore.addNotification(
        `Deleted ${deleted} profile(s)${failed ? ` · ${failed} failed` : ''}.`,
        failed ? 'warning' : 'success'
    );
}

async function bulkSetVision(mode) {
    const rows = selectedRows();
    if (rows.length === 0) return;
    const saveFn = adminStore[actions.value.saveAlias];
    if (typeof saveFn !== 'function') {
        uiStore.addNotification('Saving profiles is not supported for this modality.', 'warning');
        return;
    }
    isBulkWorking.value = true;
    let updated = 0;
    let failed = 0;
    for (const row of rows) {
        const current = Boolean(row.alias?.vision_enabled ?? row.alias?.has_vision);
        const next = mode === 'toggle' ? !current : mode === 'on';
        const cleanProfile = JSON.parse(JSON.stringify(row.alias || {}));
        cleanProfile.has_vision = next;
        cleanProfile.vision_enabled = next;
        cleanProfile.model_name = cleanProfile.model_name || row.originalModelName;
        try {
            await saveFn.call(adminStore, row.bindingId, {
                original_model_name: row.originalModelName,
                new_model_name: cleanProfile.model_name,
                alias: cleanProfile,
            });
            updated++;
        } catch {
            failed++;
        }
    }
    isBulkWorking.value = false;
    clearSelection();
    await loadAllProfiles();
    uiStore.addNotification(
        `Updated vision on ${updated} profile(s)${failed ? ` · ${failed} failed` : ''}.`,
        failed ? 'warning' : 'success'
    );
}

async function bulkSetContextSize() {
    const rows = selectedRows();
    if (rows.length === 0) return;
    const raw = bulkContextSize.value;
    if (raw === '' || raw === null || raw === undefined || Number.isNaN(Number(raw))) {
        uiStore.addNotification('Enter a valid numeric context size.', 'warning');
        return;
    }
    const ctx = Number(raw);
    if (ctx <= 0) {
        uiStore.addNotification('Context size must be a positive number.', 'warning');
        return;
    }
    const saveFn = adminStore[actions.value.saveAlias];
    if (typeof saveFn !== 'function') {
        uiStore.addNotification('Saving profiles is not supported for this modality.', 'warning');
        return;
    }
    isBulkWorking.value = true;
    let updated = 0;
    let failed = 0;
    for (const row of rows) {
        const cleanProfile = JSON.parse(JSON.stringify(row.alias || {}));
        cleanProfile.ctx_size = ctx;
        cleanProfile.forced_context_size = ctx;
        cleanProfile.model_name = cleanProfile.model_name || row.originalModelName;
        try {
            await saveFn.call(adminStore, row.bindingId, {
                original_model_name: row.originalModelName,
                new_model_name: cleanProfile.model_name,
                alias: cleanProfile,
            });
            updated++;
        } catch {
            failed++;
        }
    }
    isBulkWorking.value = false;
    bulkContextSize.value = '';
    clearSelection();
    await loadAllProfiles();
    uiStore.addNotification(
        `Set ctx=${ctx} on ${updated} profile(s)${failed ? ` · ${failed} failed` : ''}.`,
        failed ? 'warning' : 'success'
    );
}

// ── Lifecycle ────────────────────────────────────────────────────────────────
onMounted(async () => {
    await Promise.all([loadAllProfiles(), loadDetectedModels()]);
});

watch(
    () => props.binding?.id,
    async () => {
        clearSelection();
        selectedBindingAlias.value = '';
        detectedByConnection.value = new Map();
        await Promise.all([loadAllProfiles(), loadDetectedModels()]);
    }
);

watch(
    () => props.bindingType,
    async () => {
        clearSelection();
        searchQuery.value = '';
        selectedBindingAlias.value = '';
        detectedByConnection.value = new Map();
        await Promise.all([loadAllProfiles(), loadDetectedModels()]);
    }
);
</script>

<template>
    <div class="space-y-4">
        <!-- Toolbar -->
        <div class="flex flex-wrap items-center justify-between gap-3 bg-white dark:bg-gray-850 p-4 rounded-2xl border border-gray-200/80 dark:border-gray-700/80 shadow-sm">
            <div class="flex items-center gap-2 flex-wrap min-w-0">
                <h3 class="text-base font-black text-gray-900 dark:text-white flex items-center gap-2">
                    <IconSparkles class="w-4 h-4 text-purple-500" />
                    <span>{{ cfg?.longLabel || cfg?.label || bindingType }} — Model Profiles</span>
                </h3>
                <span
                    v-if="isScopedToBinding"
                    class="text-[10px] font-mono font-bold uppercase tracking-widest px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300"
                >
                    {{ binding.alias }}
                </span>
                <span class="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                    {{ profiles.length }}
                </span>
            </div>

            <div class="flex items-center gap-2 flex-wrap">
                <div class="relative">
                    <input
                        v-model="searchQuery"
                        type="text"
                        placeholder="Search profiles..."
                        class="input-field !py-1.5 !pl-8 !text-xs w-56"
                    />
                    <IconMagnifyingGlass class="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
                </div>
                <select
                    v-if="!isScopedToBinding"
                    v-model="selectedBindingAlias"
                    class="input-field !py-1.5 !text-xs !w-auto"
                >
                    <option value="">All bindings</option>
                    <option v-for="b in bindingAliasOptions" :key="b.id" :value="b.alias">
                        {{ b.alias }}
                    </option>
                </select>
                <button
                    v-if="detectedCount > 0"
                    @click="buildProfilesForAllDetected"
                    :disabled="isBulkBuilding || isLoadingDetected"
                    class="btn btn-primary btn-sm flex items-center gap-1.5"
                    :title="`Create a profile for each of the ${detectedCount} unaliased detected model(s)`"
                >
                    <IconAnimateSpin v-if="isBulkBuilding" class="w-3.5 h-3.5 animate-spin" />
                    <IconSparkles v-else class="w-3.5 h-3.5" />
                    <span>Build profiles for all ({{ detectedCount }})</span>
                </button>
                <button @click="loadAllProfiles" :disabled="isLoading" class="btn btn-secondary btn-sm">
                    {{ isLoading ? 'Refreshing…' : 'Refresh' }}
                </button>
                <button @click="openCreate" class="btn btn-primary btn-sm flex items-center gap-1.5">
                    <IconPlus class="w-3.5 h-3.5" />
                    <span>New Profile</span>
                </button>
            </div>
        </div>

        <!-- Detected models without a profile -->
        <div
            v-if="detectedCount > 0"
            class="bg-white dark:bg-gray-850 rounded-2xl border border-dashed border-blue-300 dark:border-blue-800/60 p-4"
        >
            <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
                <div>
                    <h4 class="text-xs font-black uppercase tracking-widest text-blue-600 dark:text-blue-300">
                        Detected models without a profile ({{ detectedCount }})
                    </h4>
                    <p class="text-[11px] text-gray-500 mt-0.5">
                        Served by the engine but not yet usable. Create a profile to make one available.
                    </p>
                </div>
                <button
                    @click="buildProfilesForAllDetected"
                    :disabled="isBulkBuilding"
                    class="btn btn-primary btn-sm flex items-center gap-1.5"
                >
                    <IconAnimateSpin v-if="isBulkBuilding" class="w-3.5 h-3.5 animate-spin" />
                    <IconSparkles v-else class="w-3.5 h-3.5" />
                    <span>Build profiles for all ({{ detectedCount }})</span>
                </button>
            </div>
            <ul class="space-y-1">
                <li
                    v-for="row in detectedRows"
                    :key="row.connectionId + '::' + row.name"
                    class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-blue-50/60 dark:hover:bg-blue-900/20 transition-colors"
                >
                    <div class="grow min-w-0">
                        <p class="text-xs font-mono font-bold text-gray-800 dark:text-gray-100 truncate">{{ row.name }}</p>
                        <p class="text-[10px] text-gray-400 font-mono truncate">{{ row.connectionAlias }}</p>
                    </div>
                    <button
                        @click="createProfileForDetected(row)"
                        :disabled="quickCreatingName === row.name || isBulkBuilding"
                        type="button"
                        class="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors shrink-0 disabled:opacity-40"
                        :title="`Create a profile named ${row.connectionAlias}_${row.name}`"
                    >
                        <IconAnimateSpin v-if="quickCreatingName === row.name" class="w-3.5 h-3.5 animate-spin" />
                        <IconPlus v-else class="w-3.5 h-3.5" />
                    </button>
                </li>
            </ul>
        </div>

        <!-- Multi-select bar -->
        <div
            v-if="profiles.length > 0"
            class="flex items-center justify-between flex-wrap gap-3 px-4 py-2.5 rounded-xl bg-gray-50 dark:bg-gray-900/50 border border-gray-200/80 dark:border-gray-700/60"
        >
            <label class="flex items-center gap-2 text-xs font-bold text-gray-700 dark:text-gray-200 cursor-pointer select-none">
                <input
                    type="checkbox"
                    class="h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500 cursor-pointer"
                    :checked="allRowsSelected"
                    :indeterminate.prop="someRowsSelected"
                    @change="toggleSelectAll"
                />
                <span>Select all ({{ filteredProfiles.length }})</span>
                <span v-if="selectedCount > 0" class="ml-1 text-purple-600 dark:text-purple-300">
                    · {{ selectedCount }} selected
                </span>
            </label>

            <div v-if="selectedCount > 0" class="flex items-center gap-2 flex-wrap">
                <button
                    v-if="isLlm"
                    type="button"
                    class="btn btn-secondary btn-sm"
                    :disabled="isBulkWorking"
                    title="Invert vision on the selected profiles"
                    @click="bulkSetVision('toggle')"
                >
                    ⇄ Toggle vision
                </button>
                <button
                    v-if="isLlm"
                    type="button"
                    class="btn btn-secondary btn-sm"
                    :disabled="isBulkWorking"
                    @click="bulkSetVision('on')"
                >
                    Vision ON
                </button>
                <button
                    v-if="isLlm"
                    type="button"
                    class="btn btn-secondary btn-sm"
                    :disabled="isBulkWorking"
                    @click="bulkSetVision('off')"
                >
                    Vision OFF
                </button>

                <div v-if="isLlm" class="flex items-center gap-1">
                    <input
                        v-model="bulkContextSize"
                        type="number"
                        min="1"
                        step="1024"
                        placeholder="ctx size"
                        class="input-field text-xs py-1.5 rounded-xl w-28"
                    />
                    <button
                        type="button"
                        class="btn btn-secondary btn-sm"
                        :disabled="isBulkWorking || bulkContextSize === ''"
                        @click="bulkSetContextSize"
                    >
                        Apply ctx
                    </button>
                </div>

                <button
                    type="button"
                    class="btn btn-secondary btn-sm flex items-center gap-1.5 text-red-600 hover:text-red-700 border-red-300 dark:border-red-800"
                    :disabled="isBulkWorking"
                    @click="bulkDelete"
                >
                    <IconTrash class="w-3.5 h-3.5" />
                    <span>Delete ({{ selectedCount }})</span>
                </button>
                <button type="button" class="text-xs text-gray-500 hover:underline cursor-pointer" @click="clearSelection">
                    Clear
                </button>
            </div>
        </div>

        <!-- Loading -->
        <div v-if="isLoading" class="flex justify-center items-center py-16">
            <div class="text-center">
                <IconAnimateSpin class="w-8 h-8 text-purple-500 mx-auto mb-2 animate-spin" />
                <p class="text-xs font-bold text-gray-500 uppercase tracking-widest">Loading profiles…</p>
            </div>
        </div>

        <!-- No connections -->
        <div
            v-else-if="!hasAnyBinding"
            class="text-center p-10 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border-2 border-dashed border-gray-200 dark:border-gray-700"
        >
            <p class="text-sm font-bold text-gray-700 dark:text-gray-300">No {{ cfg?.label || bindingType }} bindings configured</p>
            <p class="text-xs text-gray-500 mt-1">Add a binding to start creating model profiles.</p>
        </div>

        <!-- Empty (has bindings, no profiles) -->
        <div
            v-else-if="profiles.length === 0"
            class="text-center p-10 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border-2 border-dashed border-gray-200 dark:border-gray-700"
        >
            <IconSparkles class="w-10 h-10 text-gray-400 mx-auto mb-2 opacity-40" />
            <p class="text-sm font-bold text-gray-700 dark:text-gray-300">No model profiles yet</p>
            <p class="text-xs text-gray-500 mt-1">Create the first profile to make this model usable.</p>
            <button @click="openCreate" class="btn btn-primary btn-sm mt-3">+ New Profile</button>
        </div>

        <!-- Cards grid -->
        <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div
                v-for="p in filteredProfiles"
                :key="p.key"
                class="bg-white dark:bg-gray-850 rounded-2xl border shadow-xs hover:shadow-md transition-all p-4 flex flex-col gap-3 cursor-pointer"
                :class="isSelected(p.key)
                    ? 'border-purple-400 ring-2 ring-purple-400/30'
                    : 'border-gray-200/80 dark:border-gray-700/70'"
            >
                <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0 flex items-start gap-2">
                        <input
                            type="checkbox"
                            class="mt-0.5 h-4 w-4 rounded border-gray-300 text-purple-600 focus:ring-purple-500 cursor-pointer shrink-0"
                            :checked="isSelected(p.key)"
                            :title="`Select profile '${p.title}'`"
                            @change="toggleSelect(p.key)"
                        />
                        <div class="min-w-0">
                            <h4 class="font-black text-sm text-gray-900 dark:text-white truncate">{{ p.title }}</h4>
                            <p class="text-[11px] font-mono text-purple-600 dark:text-purple-400 truncate">
                                {{ p.bindingAlias }} / {{ p.modelName }}
                            </p>
                        </div>
                    </div>
                    <div class="flex items-center gap-1 shrink-0">
                        <button
                            @click="openEdit(p)"
                            class="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors cursor-pointer"
                            title="Edit profile"
                        >
                            <IconPencil class="w-3.5 h-3.5" />
                        </button>
                        <button
                            @click="deleteProfile(p)"
                            class="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors cursor-pointer"
                            title="Delete profile"
                        >
                            <IconTrash class="w-3.5 h-3.5" />
                        </button>
                    </div>
                </div>

                <p v-if="p.description" class="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
                    {{ p.description }}
                </p>
                <p v-else class="text-xs text-gray-400 dark:text-gray-500 italic">No description.</p>

                <div class="flex flex-wrap gap-1.5 mt-auto pt-2 border-t border-gray-100 dark:border-gray-700/60">
                    <span
                        v-if="p.alias?.vision_enabled || p.alias?.has_vision"
                        class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                    >
                        Vision
                    </span>
                    <span
                        v-if="p.alias?.ctx_size || p.alias?.forced_context_size"
                        class="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                    >
                        {{ p.alias.ctx_size || p.alias.forced_context_size }} ctx
                    </span>
                    <span
                        class="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"
                    >
                        {{ p.bindingAlias }}
                    </span>
                </div>
            </div>
        </div>

        <!-- Editor drawer -->
        <Teleport to="body">
            <div v-if="isEditorOpen" class="fixed inset-0 z-50 flex">
                <div class="absolute inset-0 bg-black/50" @click="closeEditor"></div>
                <div class="relative ml-auto w-full max-w-xl h-full bg-white dark:bg-gray-900 shadow-2xl flex flex-col">
                    <div class="shrink-0 flex items-center justify-between px-6 py-4 border-b dark:border-gray-700">
                        <div class="min-w-0">
                            <span class="text-[9px] font-black uppercase text-purple-500 tracking-widest">
                                {{ isNewProfile ? 'New Profile' : 'Edit Profile' }}
                            </span>
                            <h3 class="text-lg font-black text-gray-900 dark:text-white truncate">
                                {{ editorForm.profile?.title || editorForm.originalModelName || 'Model Profile' }}
                            </h3>
                        </div>
                        <button @click="closeEditor" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 cursor-pointer">
                            <IconClose class="w-5 h-5" />
                        </button>
                    </div>

                    <div class="grow overflow-y-auto px-6 py-5 space-y-4">
                        <div>
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Binding</label>
                            <select
                                v-model="editorForm.bindingId"
                                class="input-field text-xs"
                                :disabled="isScopedToBinding"
                            >
                                <option v-for="b in (isScopedToBinding ? [props.binding] : connections)" :key="b.id" :value="b.id">
                                    {{ b.alias }} ({{ b.name }})
                                </option>
                            </select>
                        </div>

                        <div>
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Original Model Name</label>
                            <input
                                v-model="editorForm.originalModelName"
                                type="text"
                                class="input-field text-xs font-mono"
                                :disabled="!isNewProfile"
                                placeholder="e.g. gpt-4o"
                            />
                        </div>

                        <div>
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Title</label>
                            <input v-model="editorForm.profile.title" type="text" class="input-field text-xs" placeholder="Friendly name for users" />
                        </div>

                        <div>
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Description</label>
                            <textarea v-model="editorForm.profile.description" rows="2" class="input-field text-xs resize-none" placeholder="Capabilities and domain focus…"></textarea>
                        </div>

                        <div v-if="isLlm" class="grid grid-cols-2 gap-3">
                            <div>
                                <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Context Size</label>
                                <input v-model.number="editorForm.profile.ctx_size" type="number" class="input-field text-xs" placeholder="e.g. 256000" />
                            </div>
                            <div>
                                <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Forced Context</label>
                                <input v-model.number="editorForm.profile.forced_context_size" type="number" class="input-field text-xs" placeholder="e.g. 256000" />
                            </div>
                        </div>

                        <div v-if="isLlm" class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/60 rounded-xl border dark:border-gray-700">
                            <span class="text-xs font-bold text-gray-800 dark:text-gray-200">Vision Capable</span>
                            <button
                                type="button"
                                @click="editorForm.profile.has_vision = !editorForm.profile.has_vision"
                                :class="[editorForm.profile.has_vision ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors']"
                            >
                                <span :class="[editorForm.profile.has_vision ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>

                        <p v-if="editorError" class="text-xs text-red-600 dark:text-red-400 font-bold">{{ editorError }}</p>
                    </div>

                    <div class="shrink-0 flex items-center justify-end gap-2 px-6 py-3 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
                        <button @click="closeEditor" class="btn btn-secondary">Cancel</button>
                        <button @click="saveEditor" :disabled="isSaving" class="btn btn-primary flex items-center gap-1.5">
                            <IconAnimateSpin v-if="isSaving" class="w-4 h-4 animate-spin" />
                            <IconCheckCircle v-else class="w-4 h-4" />
                            <span>{{ isSaving ? 'Saving…' : 'Save Profile' }}</span>
                        </button>
                    </div>
                </div>
            </div>
        </Teleport>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
</style>
