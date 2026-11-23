
<!-- frontend/webui/src/components/admin/bindings/BindingZoo.vue -->
<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useUiStore } from '../../../stores/ui';
import { useAdminStore } from '../../../stores/admin';
import {
    bindingActions,
    BINDING_TYPES,
    buildDefaultProfilePayload,
    collectTakenProfileNames,
    resolveBindingAction,
} from './bindingConfigs';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconChevronDown from '../../../assets/icons/IconChevronDown.vue';
import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';

const props = defineProps({
    binding: { type: Object, required: true },
    bindingType: { type: String, required: true },
});

const uiStore = useUiStore();
const adminStore = useAdminStore();

const cfg = computed(() => BINDING_TYPES[props.bindingType] || {});
const actions = computed(() => bindingActions(props.bindingType));
const supportsZoo = computed(() => !!cfg.value.supportsZoo && !!actions.value?.fetchZoo);

// Whether this modality exposes profile save/delete store actions.
// Resolved for all model-bearing modalities (llm → saveModelAlias,
// tti → saveTtiModelAlias, … ; rag → saveRagModelAlias).
const canCreateProfiles = computed(() => {
    const name = actions.value?.saveAlias;
    return Boolean(name && typeof adminStore[name] === 'function');
});
const canDeleteProfiles = computed(() => {
    const name = actions.value?.deleteAlias;
    return Boolean(name && typeof adminStore[name] === 'function');
});

// ── Zoo state ───────────────────────────────────────────────────────────────
const zooModels = ref([]);
const isLoadingZoo = ref(false);
const installingIndex = ref(null);
const searchTerm = ref('');
const loadError = ref('');

// Per-model expand/collapse state for the "existing profiles" disclosure.
const expandedProfiles = ref({});
function toggleProfilesExpanded(key) {
    expandedProfiles.value = { ...expandedProfiles.value, [key]: !expandedProfiles.value[key] };
}
function isProfilesExpanded(key) {
    return !!expandedProfiles.value[key];
}

// ── Existing aliases ────────────────────────────────────────────────────────
// ``binding.model_aliases`` is a dict keyed by original_model_name. Each entry
// is the alias/profile object (or sometimes a bare title string). Normalise
// into a Map of { name, title } so both shapes render uniformly.
const aliasesByModel = computed(() => {
    const map = new Map();
    let aliases = props.binding?.model_aliases;
    if (typeof aliases === 'string') {
        try { aliases = JSON.parse(aliases); } catch { aliases = {}; }
    }
    if (!aliases || typeof aliases !== 'object') return map;
    for (const [key, raw] of Object.entries(aliases)) {
        if (!key) continue;
        let title = key;
        if (raw && typeof raw === 'object') {
            title = raw.title || raw.name || key;
        } else if (typeof raw === 'string' && raw.trim()) {
            title = raw;
        }
        map.set(key, { name: key, title });
    }
    return map;
});

function hasProfileFor(modelName) {
    return aliasesByModel.value.has(modelName);
}

function existingProfilesFor(modelName) {
    const entry = aliasesByModel.value.get(modelName);
    return entry ? [entry] : [];
}

// ── Filtered listing ────────────────────────────────────────────────────────
const filteredZooModels = computed(() => {
    if (!searchTerm.value) return zooModels.value;
    const term = searchTerm.value.toLowerCase();
    return zooModels.value.filter(m =>
        (m.name || '').toLowerCase().includes(term) ||
        (m.description || '').toLowerCase().includes(term)
    );
});

// Models the backend flagged as live-served (source='live' / is_available /
// is_installed). These are already running on the engine, so "install" is
// meaningless; they get a "Create profile" action.
function isServedModel(model) {
    return Boolean(model?.is_available || model?.source === 'live' || model?.is_installed);
}

// How many of the visible zoo entries still have NO profile yet.
const missingProfileCount = computed(() =>
    filteredZooModels.value.filter(m => m?.name && !hasProfileFor(m.name)).length
);

// ── Selection state (multi-select for bulk profile deletion) ───────────────
// Each entry is the model name whose profile should be deleted. Only models
// that actually have a profile are selectable — deleting a non-existent
// profile is a no-op and would just confuse the UX.
const selectedForDeletion = ref(new Set());
const isBulkDeleting = ref(false);

const selectableProfiles = computed(() =>
    filteredZooModels.value.filter(m => m?.name && hasProfileFor(m.name))
);
const allSelectableSelected = computed(() =>
    selectableProfiles.value.length > 0 &&
    selectableProfiles.value.every(m => selectedForDeletion.value.has(m.name))
);
const someSelectableSelected = computed(() =>
    selectableProfiles.value.some(m => selectedForDeletion.value.has(m.name)) &&
    !allSelectableSelected.value
);
const selectedProfileCount = computed(() => selectedForDeletion.value.size);

function toggleSelectForDeletion(modelName) {
    if (!modelName || !hasProfileFor(modelName)) return;
    const next = new Set(selectedForDeletion.value);
    if (next.has(modelName)) next.delete(modelName);
    else next.add(modelName);
    selectedForDeletion.value = next;
}

function toggleSelectAll() {
    if (allSelectableSelected.value) {
        selectedForDeletion.value = new Set();
    } else {
        selectedForDeletion.value = new Set(selectableProfiles.value.map(m => m.name));
    }
}

function isSelectedForDeletion(modelName) {
    return selectedForDeletion.value.has(modelName);
}

// ── Bulk-create state ──────────────────────────────────────────────────────
const isBulkCreating = ref(false);

// Selection set for "create profile" (separate from delete selection — the two
// flows touch different model sets: create targets models with NO profile,
// delete targets models that ALREADY have a profile).
const selectedForCreation = ref(new Set());

const selectableForCreation = computed(() =>
    filteredZooModels.value.filter(m => m?.name && !hasProfileFor(m.name))
);
const recentLackingProfileCount = computed(() => selectableForCreation.value.length);

function isSelectedForCreation(modelName) {
    return selectedForCreation.value.has(modelName);
}
function toggleSelectForCreation(modelName) {
    if (!modelName || hasProfileFor(modelName)) return;
    const next = new Set(selectedForCreation.value);
    if (next.has(modelName)) next.delete(modelName);
    else next.add(modelName);
    selectedForCreation.value = next;
}
function toggleSelectAllForCreation() {
    const current = selectableForCreation.value;
    const allSelected = current.length > 0 &&
        current.every(m => selectedForCreation.value.has(m.name));
    if (allSelected) {
        selectedForCreation.value = new Set();
    } else {
        selectedForCreation.value = new Set(current.map(m => m.name));
    }
}
const selectedForCreationCount = computed(() => selectedForCreation.value.size);

// Vision heuristic, alias-naming and default-payload construction all live in
// bindingConfigs.js so every profile-creation path (this zoo, the profiles
// grid, and the legacy models manager) stays perfectly in sync.

// Snapshot of every name already in use on this binding, seeded from the live
// alias map (which may have drifted from the prop after a background refresh).
function snapshotTakenAliasNames() {
    const taken = collectTakenProfileNames(props.binding);
    for (const name of aliasesByModel.value.keys()) taken.add(name);
    return taken;
}

// ── Fetch zoo ───────────────────────────────────────────────────────────────
async function fetchZoo() {
    if (!supportsZoo.value) {
        zooModels.value = [];
        return;
    }
    const fetchFn = adminStore[actions.value.fetchZoo];
    if (typeof fetchFn !== 'function') {
        loadError.value = `Zoo fetching is not supported for ${props.bindingType}.`;
        zooModels.value = [];
        return;
    }
    isLoadingZoo.value = true;
    loadError.value = '';
    try {
        const models = await fetchFn.call(adminStore, props.binding.id);
        zooModels.value = Array.isArray(models) ? models : [];
    } catch (e) {
        loadError.value = e?.response?.data?.detail || 'Failed to fetch zoo models.';
        zooModels.value = [];
        uiStore.addNotification(loadError.value, 'error');
    } finally {
        isLoadingZoo.value = false;
    }
}

// Build a profile payload from a zoo entry, delegating to the shared builder
// so title conventions and default parameters are identical everywhere.
function buildAliasPayloadForModel(model, aliasTitleOverride, takenSet) {
    const modelName = model.name || model.model_name || '';
    const taken = takenSet || snapshotTakenAliasNames();
    if (aliasTitleOverride) taken.add(aliasTitleOverride);
    const payload = buildDefaultProfilePayload(props.binding, props.bindingType, modelName, taken);
    if (aliasTitleOverride) {
        payload.alias.title = aliasTitleOverride;
        payload.alias.name = aliasTitleOverride;
    }
    if (model.description) payload.alias.description = model.description;
    return payload;
}

// ── Single-action create profile ────────────────────────────────────────────
async function createProfileForModel(model, index) {
    if (installingIndex.value !== null) return;
    if (!canCreateProfiles.value) {
        uiStore.addNotification('Profile creation is not supported for this modality.', 'warning');
        return;
    }
    const modelName = model.name || model.model_name;
    if (!modelName) return;
    const saveFn = resolveBindingAction(adminStore, props.bindingType, 'saveAlias');
    installingIndex.value = index;
    const taken = snapshotTakenAliasNames();
    try {
        // Single-action path uses the canonical `<binding>_<model>` title.
        await saveFn(props.binding.id, buildAliasPayloadForModel(model, null, taken));
        uiStore.addNotification(`Profile created for '${modelName}'.`, 'success');
        // Expand the just-created entry so the new profile is immediately visible.
        expandedProfiles.value = { ...expandedProfiles.value, [modelName]: true };
        await refreshBinding();
    } catch (e) {
        uiStore.addNotification(e?.response?.data?.detail || 'Failed to create profile.', 'error');
    } finally {
        installingIndex.value = null;
    }
}

// ── Bulk create profiles ────────────────────────────────────────────────────
async function createProfilesForAllMissing() {
    if (!canCreateProfiles.value || isBulkCreating.value) return;
    const targets = filteredZooModels.value
        .filter(m => m?.name && !hasProfileFor(m.name))
        .map(m => m.name);
    if (targets.length === 0) {
        uiStore.addNotification('All visible models already have profiles.', 'info');
        return;
    }
    isBulkCreating.value = true;
    const saveFn = resolveBindingAction(adminStore, props.bindingType, 'saveAlias');
    const taken = snapshotTakenAliasNames();
    let created = 0;
    let failed = 0;
    for (const model of filteredZooModels.value) {
        const modelName = model?.name;
        if (!modelName || hasProfileFor(modelName)) continue;
        try {
            await saveFn(
                props.binding.id,
                buildAliasPayloadForModel(model, null, taken)
            );
            created++;
        } catch (e) {
            failed++;
        }
    }
    isBulkCreating.value = false;
    selectedForCreation.value = new Set();
    await refreshBinding();
    if (created > 0) {
        uiStore.addNotification(
            `Created ${created} profile(s)${failed ? ` · ${failed} failed` : ''}.`,
            failed ? 'warning' : 'success'
        );
    } else if (failed > 0) {
        uiStore.addNotification('Failed to create profiles. Check server logs.', 'error');
    }
}

// ── Bulk-create from selection ────────────────────────────────────────────
async function createProfilesForSelection() {
    if (!canCreateProfiles.value || isBulkCreating.value) return;
    const names = Array.from(selectedForCreation.value);
    if (names.length === 0) {
        uiStore.addNotification('No models selected for profile creation.', 'info');
        return;
    }
    isBulkCreating.value = true;
    const saveFn = resolveBindingAction(adminStore, props.bindingType, 'saveAlias');
    const taken = snapshotTakenAliasNames();
    const modelMap = new Map(filteredZooModels.value.map(m => [m.name, m]));
    let created = 0;
    let failed = 0;
    for (const modelName of names) {
        // Skip entries that gained a profile since selection (concurrent edit,
        // external refresh, or a rapid double-submit of this same button).
        if (hasProfileFor(modelName)) continue;
        const model = modelMap.get(modelName) || { name: modelName };
        try {
            await saveFn(
                props.binding.id,
                buildAliasPayloadForModel(model, null, taken)
            );
            created++;
        } catch (e) {
            failed++;
        }
    }
    isBulkCreating.value = false;
    selectedForCreation.value = new Set();
    await refreshBinding();
    if (created > 0) {
        uiStore.addNotification(
            `Created ${created} profile(s)${failed ? ` · ${failed} failed` : ''}.`,
            failed ? 'warning' : 'success'
        );
    } else if (failed > 0) {
        uiStore.addNotification('Failed to create profiles. Check server logs.', 'error');
    }
}

// ── Bulk delete profiles ────────────────────────────────────────────────────
async function deleteSelectedProfiles() {
    if (!canDeleteProfiles.value || isBulkDeleting.value) return;
    const targets = Array.from(selectedForDeletion.value);
    if (targets.length === 0) return;

    const confirmed = await uiStore.showConfirmation({
        title: `Delete ${targets.length} profile(s)?`,
        message: `The selected model profile${targets.length === 1 ? '' : 's'} will be removed from this binding. The underlying models stay on the engine.`,
        confirmText: 'Delete',
    });
    if (!confirmed) return;

    isBulkDeleting.value = true;
    const deleteFn = resolveBindingAction(adminStore, props.bindingType, 'deleteAlias');
    let deleted = 0;
    let failed = 0;
    const stillSelected = new Set();
    for (const modelName of targets) {
        try {
            await deleteFn.call(adminStore, props.binding.id, modelName);
            deleted++;
        } catch (e) {
            failed++;
            stillSelected.add(modelName);
        }
    }
    selectedForDeletion.value = stillSelected;
    isBulkDeleting.value = false;
    await refreshBinding();
    if (deleted > 0) {
        uiStore.addNotification(
            `Deleted ${deleted} profile(s)${failed ? ` · ${failed} failed` : ''}.`,
            failed ? 'warning' : 'success'
        );
    } else if (failed > 0) {
        uiStore.addNotification('Failed to delete profiles. Check server logs.', 'error');
    }
}

// ── Refresh parent binding so ``model_aliases`` reflects the new profiles ──
// The parent (BindingCard / BindingSettingsPanel) hosts this component and
// refreshes its own bindings list on ``changed``-style events. The parent
// passes a ``binding`` prop; when it updates, our computed ``aliasesByModel``
// reacts and the UI reflects the freshly created/removed profiles.
async function refreshBinding() {
    if (typeof props.onChanged === 'function') {
        await props.onChanged();
    }
}

// ── Lifecycle & watchers ───────────────────────────────────────────────────
onMounted(fetchZoo);

watch(() => props.binding?.id, () => {
    zooModels.value = [];
    expandedProfiles.value = {};
    selectedForDeletion.value = new Set();
    selectedForCreation.value = new Set();
    fetchZoo();
});

// Prune the selection set when aliases change (e.g. after a successful delete
// or an external profile change) so the "Delete selected (N)" counter never
// shows stale entries that no longer have a profile.
watch(aliasesByModel, (map) => {
    // Prune deletion selection to names that STILL have a profile.
    if (selectedForDeletion.value.size > 0) {
        const next = new Set();
        for (const name of selectedForDeletion.value) {
            if (map.has(name)) next.add(name);
        }
        if (next.size !== selectedForDeletion.value.size) {
            selectedForDeletion.value = next;
        }
    }
    // Prune creation selection to names that STILL LACK a profile.
    if (selectedForCreation.value.size > 0) {
        const next = new Set();
        for (const name of selectedForCreation.value) {
            if (!map.has(name)) next.add(name);
        }
        if (next.size !== selectedForCreation.value.size) {
            selectedForCreation.value = next;
        }
    }
});
</script>

<template>
    <div class="flex flex-col h-full min-h-[520px]">
        <!-- Modalities without a zoo (e.g. RAG) render a clear, non-empty state. -->
        <div v-if="!supportsZoo" class="grow flex items-center justify-center text-center px-6">
            <div>
                <p class="text-sm font-bold text-gray-700 dark:text-gray-300">
                    The models zoo is not available for {{ cfg.label || bindingType }}.
                </p>
                <p class="text-xs text-gray-500 mt-1">
                    This modality has no remote model catalogue — configure models directly on the binding's profiles.
                </p>
            </div>
        </div>

        <template v-else>
            <!-- Header toolbar: title + master select-all + bulk actions + refresh -->
            <div class="mb-3 flex items-center justify-between flex-wrap gap-2">
                <div class="flex items-center gap-2">
                    <h3 class="font-semibold text-base">Models Zoo: {{ binding.alias }}</h3>
                    <label
                        v-if="canDeleteProfiles && selectableProfiles.length > 0"
                        class="flex items-center gap-1.5 text-xs font-bold text-gray-600 dark:text-gray-300 cursor-pointer select-none ml-2"
                        title="Select every model that already has a profile (for deletion)"
                    >
                        <input
                            type="checkbox"
                            class="h-4 w-4 rounded border-gray-300 text-rose-600 focus:ring-rose-500 cursor-pointer"
                            :checked="allSelectableSelected"
                            :indeterminate.prop="someSelectableSelected"
                            @change="toggleSelectAll"
                        />
                        <span>Delete: select all with profiles ({{ selectableProfiles.length }})</span>
                    </label>
                    <label
                        v-if="canCreateProfiles && selectableForCreation.length > 0"
                        class="flex items-center gap-1.5 text-xs font-bold text-gray-600 dark:text-gray-300 cursor-pointer select-none ml-2"
                        title="Select every detected model that lacks a profile (for creation)"
                    >
                        <input
                            type="checkbox"
                            class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                            :checked="selectableForCreation.length > 0 && selectableForCreation.every(m => selectedForCreation.has(m.name))"
                            :indeterminate.prop="selectableForCreation.some(m => selectedForCreation.has(m.name)) && !selectableForCreation.every(m => selectedForCreation.has(m.name))"
                            @change="toggleSelectAllForCreation"
                        />
                        <span>Select all models without a profile ({{ selectableForCreation.length }})</span>
                    </label>
                </div>
                <div class="flex items-center gap-2 flex-wrap">
                    <button
                        v-if="canDeleteProfiles && selectedProfileCount > 0"
                        type="button"
                        class="btn btn-secondary btn-sm flex items-center gap-1.5 text-rose-600 hover:text-rose-700 border-rose-300 dark:border-rose-800"
                        :disabled="isBulkDeleting"
                        :title="`Delete ${selectedProfileCount} selected profile(s)`"
                        @click="deleteSelectedProfiles"
                    >
                        <IconAnimateSpin v-if="isBulkDeleting" class="w-3.5 h-3.5 animate-spin" />
                        <IconTrash v-else class="w-3.5 h-3.5" />
                        <span>Delete selected ({{ selectedProfileCount }})</span>
                    </button>
                    <button
                        v-if="canCreateProfiles && selectedForCreationCount > 0"
                        type="button"
                        class="btn btn-primary btn-sm flex items-center gap-1.5"
                        :disabled="isBulkCreating"
                        :title="`Create profiles for ${selectedForCreationCount} selected model(s)`"
                        @click="createProfilesForSelection"
                    >
                        <IconAnimateSpin v-if="isBulkCreating" class="w-3.5 h-3.5 animate-spin" />
                        <IconSparkles v-else class="w-3.5 h-3.5" />
                        <span>Create profiles for selected ({{ selectedForCreationCount }})</span>
                    </button>
                    <button
                        v-if="canCreateProfiles && missingProfileCount > 0"
                        type="button"
                        class="btn btn-secondary btn-sm flex items-center gap-1.5"
                        :disabled="isBulkCreating"
                        title="Create a profile for every detected model that lacks one"
                        @click="createProfilesForAllMissing"
                    >
                        <IconAnimateSpin v-if="isBulkCreating" class="w-3.5 h-3.5 animate-spin" />
                        <IconSparkles v-else class="w-3.5 h-3.5" />
                        <span>Create profiles for all models ({{ missingProfileCount }})</span>
                    </button>
                    <button
                        type="button"
                        class="text-blue-600 hover:underline text-sm"
                        :disabled="isLoadingZoo"
                        @click="fetchZoo"
                    >
                        Refresh
                    </button>
                </div>
            </div>

            <div class="mb-3 relative">
                <input type="text" v-model="searchTerm" placeholder="Search zoo..." class="input-field w-full pl-8" />
                <div class="absolute inset-y-0 left-0 pl-2 flex items-center pointer-events-none text-gray-400">
                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                </div>
            </div>

            <div v-if="isLoadingZoo" class="grow flex items-center justify-center">
                <div class="text-center">
                    <IconAnimateSpin class="w-8 h-8 text-blue-500 mx-auto mb-2" />
                    <p>Loading zoo...</p>
                </div>
            </div>

            <div v-else-if="loadError" class="grow flex items-center justify-center text-center px-6">
                <div>
                    <p class="text-sm font-bold text-rose-600 dark:text-rose-400">{{ loadError }}</p>
                    <button @click="fetchZoo" class="mt-2 text-blue-600 hover:underline text-sm">Retry</button>
                </div>
            </div>

            <div v-else-if="zooModels.length === 0" class="grow flex flex-col items-center justify-center text-center px-6 text-gray-500 gap-2">
                <p class="text-sm font-bold text-gray-700 dark:text-gray-300">No models in the {{ cfg.label || bindingType }} zoo.</p>
                <p class="text-xs max-w-md">
                    This binding exposes no downloadable models. Models installed directly on the engine server appear under this connection's detected-model list instead.
                </p>
            </div>

            <div v-else class="grow overflow-y-auto space-y-3 pr-2">
                <div
                    v-for="(model, index) in filteredZooModels"
                    :key="model.name || index"
                    class="bg-white dark:bg-gray-700/50 p-4 rounded-lg border border-gray-200 dark:border-gray-600 flex flex-col gap-3"
                    :class="{ 'ring-2 ring-rose-400/60 bg-rose-50/40 dark:bg-rose-950/20': isSelectedForDeletion(model.name) }"
                >
                    <div class="flex flex-col sm:flex-row gap-3">
                        <div class="grow min-w-0">
                            <div class="flex items-start gap-2">
                                <input
                                    v-if="canDeleteProfiles && hasProfileFor(model.name)"
                                    type="checkbox"
                                    class="mt-1 h-4 w-4 rounded border-gray-300 text-rose-600 focus:ring-rose-500 cursor-pointer shrink-0"
                                    :checked="isSelectedForDeletion(model.name)"
                                    :title="`Select the profile for '${model.name}' for deletion`"
                                    @change="toggleSelectForDeletion(model.name)"
                                />
                                <input
                                    v-else-if="canCreateProfiles"
                                    type="checkbox"
                                    class="mt-1 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer shrink-0"
                                    :checked="isSelectedForCreation(model.name)"
                                    :title="`Select '${model.name}' for profile creation`"
                                    @change="toggleSelectForCreation(model.name)"
                                />
                                <h4 class="font-bold text-gray-900 dark:text-white break-words">{{ model.name }}</h4>
                            </div>
                            <p v-if="model.description" class="text-sm text-gray-600 dark:text-gray-300 mt-1">{{ model.description }}</p>
                            <div class="flex flex-wrap gap-2 mt-2 text-xs text-gray-500 dark:text-gray-400">
                                <span v-if="model.size" class="bg-gray-100 dark:bg-gray-600 px-2 py-0.5 rounded">Size: {{ model.size }}</span>
                                <span v-if="model.type" class="bg-gray-100 dark:bg-gray-600 px-2 py-0.5 rounded">Type: {{ model.type }}</span>
                                <span
                                    v-if="isServedModel(model)"
                                    class="bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 px-2 py-0.5 rounded font-bold"
                                    title="This model is already served by the engine"
                                >✓ Available on engine</span>
                                <span
                                    v-if="hasProfileFor(model.name)"
                                    class="bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded font-bold"
                                >✓ Profile exists</span>
                            </div>
                        </div>
                        <div class="shrink-0 flex items-center gap-2">
                            <button
                                v-if="canCreateProfiles && !hasProfileFor(model.name)"
                                type="button"
                                @click="createProfileForModel(model, index)"
                                class="btn btn-primary btn-sm flex items-center gap-2"
                                :disabled="installingIndex !== null || isBulkCreating"
                            >
                                <IconAnimateSpin v-if="installingIndex === index" class="w-4 h-4 animate-spin" />
                                <IconPlus v-else class="w-4 h-4" />
                                <span>{{ installingIndex === index ? 'Creating…' : 'Create profile' }}</span>
                            </button>
                            <button
                                v-else-if="canCreateProfiles && hasProfileFor(model.name)"
                                type="button"
                                @click="toggleProfilesExpanded(model.name)"
                                class="btn btn-secondary btn-sm flex items-center gap-1.5"
                                :aria-expanded="isProfilesExpanded(model.name)"
                            >
                                <IconChevronDown
                                    class="w-3.5 h-3.5 transition-transform"
                                    :class="{ 'rotate-180': !isProfilesExpanded(model.name) }"
                                />
                                <span>View profile</span>
                            </button>
                            <!-- Fallback: a printable catalogue entry the engine can download. -->
                            <button
                                v-else-if="!isServedModel(model) && actions.installFromZoo"
                                type="button"
                                @click="createProfileForModel(model, index)"
                                class="btn btn-primary btn-sm flex items-center gap-2"
                                :disabled="installingIndex !== null"
                            >
                                <IconArrowDownTray class="w-4 h-4" />
                                <span>Add to engine</span>
                            </button>
                        </div>
                    </div>

                    <!-- Collapsible list of profiles already created for this model. -->
                    <div
                        v-if="hasProfileFor(model.name) && isProfilesExpanded(model.name)"
                        class="border-t border-gray-200 dark:border-gray-600 pt-2 animate-in fade-in"
                    >
                        <p class="text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1.5">
                            Profiles for this model
                        </p>
                        <ul class="space-y-1">
                            <li
                                v-for="profile in existingProfilesFor(model.name)"
                                :key="profile.name"
                                class="flex items-center gap-2 text-xs bg-gray-50 dark:bg-gray-900/50 px-2.5 py-1.5 rounded-md"
                            >
                                <IconCpuChip class="w-3.5 h-3.5 text-blue-500 shrink-0" />
                                <span class="font-mono font-bold text-gray-800 dark:text-gray-100 truncate">{{ profile.title }}</span>
                                <span class="text-[10px] font-mono text-gray-400 truncate">({{ profile.name }})</span>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </template>
    </div>
</template>
