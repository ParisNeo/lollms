
<!-- frontend/webui/src/components/admin/bindings/BindingSettingsPanel.vue -->
<script setup>
import { ref, computed, onMounted, watch, defineAsyncComponent } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useUiStore } from '../../../stores/ui';
import { useDataStore } from '../../../stores/data';
import apiClient from '../../../services/api';
import { BINDING_TYPES, bindingActions } from './bindingConfigs';

import IconCpuChip from '../../../assets/icons/IconCpuChip.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';

const BindingCard = defineAsyncComponent(() => import('./BindingCard.vue'));
const ModelProfilesGrid = defineAsyncComponent(() => import('./ModelProfilesGrid.vue'));

const props = defineProps({
    bindingType: { type: String, required: true },
});

const adminStore = useAdminStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const cfg = computed(() => BINDING_TYPES[props.bindingType] || BINDING_TYPES.llm);
const actions = computed(() => bindingActions(props.bindingType));

// Two-tab layout: physical bindings vs. universal profiles (cross-binding view)
const viewTab = ref('bindings');
const isAddFormOpen = ref(false);
const isSaving = ref(false);
const isHealing = ref(false);
const isAutoCreating = ref(false);

const newBinding = ref(buildInitialNewBinding());

function buildInitialNewBinding() {
    return {
        alias: '',
        name: '',
        config: {},
        is_active: true,
        default_model_name: '',
    };
}

// Bindings come from the store's modality-specific slice.
const bindingsRef = computed(() => {
    // adminStore exposes llm as `bindings` and every other modality as
    // `<type>Bindings` (ttiBindings, ttsBindings, …, ragBindings).
    const stateKey = props.bindingType === 'llm'
        ? 'bindings'
        : `${props.bindingType}Bindings`;
    return adminStore[stateKey];
});

const bindings = computed(() => Array.isArray(bindingsRef.value) ? bindingsRef.value : []);

const isLoading = computed(() => {
    const flagKey = props.bindingType === 'llm' ? 'isLoadingBindings' : `isLoading${
        props.bindingType.charAt(0).toUpperCase() + props.bindingType.slice(1)
    }Bindings`;
    return Boolean(adminStore[flagKey]);
});

const availableTypes = computed(() => {
    const typesKey = props.bindingType === 'llm' ? 'availableBindingTypes' : `available${
        props.bindingType.charAt(0).toUpperCase() + props.bindingType.slice(1)
    }BindingTypes`;
    const list = adminStore[typesKey];
    return Array.isArray(list) ? list : [];
});

const selectedTypeDescriptor = computed(() => {
    if (!newBinding.value.name) return null;
    const target = newBinding.value.name.toLowerCase();
    return availableTypes.value.find(t => (t.binding_name || t.name || '').toLowerCase() === target) || null;
});

const newFormParameters = computed(() => {
    const desc = selectedTypeDescriptor.value;
    if (!desc) return [];
    const seen = new Set();
    const out = [];
    const sources = [desc.global_input_parameters, desc.input_parameters, desc.parameters];
    for (const src of sources) {
        if (!Array.isArray(src)) continue;
        for (const p of src) {
            if (!p || !p.name || seen.has(p.name)) continue;
            if (p.name === 'model_name' || p.name === 'model') continue;
            seen.add(p.name);
            out.push(p);
        }
    }
    return out;
});

watch(() => newBinding.value.name, (newName, oldName) => {
    if (newName === oldName) return;
    const desc = selectedTypeDescriptor.value;
    if (desc && Array.isArray(desc.input_parameters)) {
        const config = {};
        for (const p of desc.input_parameters) {
            config[p.name] = p.default !== undefined ? p.default : '';
        }
        newBinding.value.config = config;
    } else {
        newBinding.value.config = {};
    }
});

async function loadBindings(force = false) {
    const fn = adminStore[actions.value.fetch];
    if (typeof fn !== 'function') return;
    try {
        await fn.call(adminStore, force);
    } catch (e) {
        console.error(`Failed to load ${props.bindingType} bindings:`, e);
    }
}

async function loadAvailableTypes(force = false) {
    const fn = adminStore[actions.value.fetchAvailableTypes];
    if (typeof fn !== 'function') return;
    try {
        await fn.call(adminStore, force);
    } catch (e) {
        console.error(`Failed to load available ${props.bindingType} types:`, e);
    }
}

onMounted(async () => {
    await Promise.all([loadBindings(), loadAvailableTypes()]);
});

watch(() => props.bindingType, async () => {
    viewTab.value = 'bindings';
    isAddFormOpen.value = false;
    newBinding.value = buildInitialNewBinding();
    await Promise.all([loadBindings(true), loadAvailableTypes(true)]);
});

function openAddForm() {
    newBinding.value = buildInitialNewBinding();
    isAddFormOpen.value = true;
    // Scroll to top of container
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function closeAddForm() {
    isAddFormOpen.value = false;
    newBinding.value = buildInitialNewBinding();
}

async function submitNewBinding() {
    if (!newBinding.value.alias.trim() || !newBinding.value.name) {
        uiStore.addNotification('Alias and Engine Type are required.', 'warning');
        return;
    }
    isSaving.value = true;
    try {
        const fn = adminStore[actions.value.add];
        if (typeof fn !== 'function') throw new Error(`Missing store action: ${actions.value.add}`);
        await fn.call(adminStore, {
            alias: newBinding.value.alias,
            name: newBinding.value.name,
            config: newBinding.value.config || {},
            is_active: newBinding.value.is_active,
            default_model_name: newBinding.value.default_model_name || null,
        });
        // Refresh the modal's models feed if that data store slice exists
        if (typeof dataStore.refreshAllModels === 'function') {
            dataStore.refreshAllModels().catch(() => {});
        }
        closeAddForm();
    } catch (e) {
        console.error(`Failed to add ${props.bindingType} binding:`, e);
    } finally {
        isSaving.value = false;
    }
}

async function handleSyncAndHeal() {
    isHealing.value = true;
    try {
        const res = await apiClient.post('/api/admin/bindings/migrate-and-heal');
        uiStore.addNotification(res.data.message || 'Migration and healing completed.', 'success');
        await loadBindings(true);
    } catch (e) {
        uiStore.addNotification('Sync & heal operation failed.', 'error');
    } finally {
        isHealing.value = false;
    }
}

async function handleAutoCreateAllProfiles() {
    const activeBindings = bindings.value.filter(b => b.is_active);
    if (activeBindings.length === 0) {
        uiStore.addNotification('No active bindings to auto-profile.', 'warning');
        return;
    }
    isAutoCreating.value = true;
    try {
        let total = 0;
        for (const b of activeBindings) {
            try {
                const res = await adminStore.autoCreateProfilesForBinding(b.id, props.bindingType);
                total += res?.created_count || 0;
            } catch (e) {
                console.warn(`Auto-profile failed for ${b.alias}:`, e);
            }
        }
        uiStore.addNotification(`Created ${total} new profile(s) across ${activeBindings.length} binding(s).`, 'success');
        await loadBindings(true);
    } finally {
        isAutoCreating.value = false;
    }
}

function onBindingSaved() {
    loadBindings(true);
}

function onBindingDeleted() {
    loadBindings(true);
}

function parseOptions(options) {
    if (typeof options === 'string') return options.split(',').map(o => o.trim()).filter(Boolean);
    if (Array.isArray(options)) return options.map(o => typeof o === 'object' && o !== null ? (o.value || o.name || o.label) : String(o)).filter(Boolean);
    return [];
}
</script>

<template>
    <div class="space-y-6">
        <!-- Root Tabs -->
        <div class="flex items-center justify-between border-b border-gray-200 dark:border-gray-700/80 pb-3 flex-wrap gap-3">
            <div class="flex items-center gap-2 p-1 bg-gray-100 dark:bg-gray-800 rounded-xl text-xs font-bold">
                <button
                    @click="viewTab = 'bindings'"
                    :class="viewTab === 'bindings' ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    class="px-4 py-2 rounded-lg transition-all flex items-center gap-2"
                >
                    <IconCpuChip class="w-4 h-4" />
                    <span>Physical Bindings ({{ bindings.length }})</span>
                </button>
                <button
                    @click="viewTab = 'profiles'"
                    :class="viewTab === 'profiles' ? 'bg-white dark:bg-gray-700 text-purple-600 dark:text-purple-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                    class="px-4 py-2 rounded-lg transition-all flex items-center gap-2"
                >
                    <IconSparkles class="w-4 h-4 text-purple-500" />
                    <span>Universal Profiles</span>
                </button>
            </div>

            <div class="flex items-center gap-2">
                <button
                    @click="handleSyncAndHeal"
                    :disabled="isHealing"
                    class="btn btn-secondary btn-sm flex items-center gap-1.5"
                    title="Migrate legacy aliases and heal orphaned user references"
                >
                    <IconAnimateSpin v-if="isHealing" class="w-3.5 h-3.5 animate-spin" />
                    <IconSparkles v-else class="w-3.5 h-3.5 text-purple-500" />
                    <span>Sync &amp; Heal</span>
                </button>
                <button
                    @click="handleAutoCreateAllProfiles"
                    :disabled="isAutoCreating"
                    class="btn btn-secondary btn-sm flex items-center gap-1.5"
                    title="Auto-create universal profiles for models discovered on every active binding"
                >
                    <IconAnimateSpin v-if="isAutoCreating" class="w-3.5 h-3.5 animate-spin" />
                    <IconSparkles v-else class="w-3.5 h-3.5 text-amber-500" />
                    <span>Auto-Profiles (All)</span>
                </button>
                <button
                    v-if="viewTab === 'bindings'"
                    @click="openAddForm"
                    class="btn btn-primary btn-sm flex items-center gap-1.5"
                >
                    <IconPlus class="w-3.5 h-3.5" />
                    <span>Add Binding</span>
                </button>
            </div>
        </div>

        <!-- Universal Profiles View -->
        <div v-if="viewTab === 'profiles'" class="bg-white dark:bg-gray-850 p-5 rounded-2xl border border-gray-200/80 dark:border-gray-700/80 shadow-sm">
            <div class="mb-4">
                <h3 class="text-lg font-black text-gray-900 dark:text-white flex items-center gap-2">
                    <IconSparkles class="w-5 h-5 text-purple-500" />
                    <span>{{ cfg.longLabel }} Universal Profiles</span>
                </h3>
                <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    Declarative model execution layer. Configure usable models, routing, sampling parameters, and vision companions across all physical bindings.
                </p>
            </div>
            <ModelProfilesGrid :binding-type="bindingType" @changed="onBindingSaved" />
        </div>

        <!-- Physical Bindings View -->
        <div v-else class="space-y-6">
            <!-- Add Form -->
            <div v-if="isAddFormOpen" class="bg-white dark:bg-gray-800 shadow-md rounded-2xl p-6 border border-gray-100 dark:border-gray-700">
                <div class="flex items-center justify-between mb-4 pb-3 border-b dark:border-gray-700">
                    <div>
                        <span class="text-[9px] font-black uppercase text-blue-500 tracking-widest">New Connection</span>
                        <h3 class="text-lg font-bold text-gray-900 dark:text-white">Register {{ cfg.label }} Binding</h3>
                    </div>
                </div>

                <form @submit.prevent="submitNewBinding" class="space-y-5">
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-5">
                        <div>
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Alias</label>
                            <input v-model="newBinding.alias" type="text" class="input-field text-xs" placeholder="e.g., local_ollama" required />
                        </div>
                        <div>
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Engine Type</label>
                            <select v-model="newBinding.name" class="input-field text-xs" required>
                                <option disabled value="">Select an engine type</option>
                                <option v-for="t in availableTypes" :key="t.binding_name || t.name" :value="t.binding_name || t.name">
                                    {{ t.title || t.name }}
                                </option>
                            </select>
                        </div>
                    </div>

                    <div v-if="newFormParameters.length" class="space-y-4 border-t dark:border-gray-700 pt-4">
                        <h4 class="text-xs font-bold uppercase text-gray-500">Engine Parameters</h4>
                        <div v-for="p in newFormParameters" :key="p.name" class="space-y-1">
                            <label class="block text-xs font-bold uppercase text-gray-500">
                                {{ p.name.replace(/_/g, ' ') }}
                                <span v-if="p.mandatory" class="text-red-500">*</span>
                            </label>
                            <select v-if="p.options && p.options.length" v-model="newBinding.config[p.name]" class="input-field text-xs">
                                <option v-for="opt in parseOptions(p.options)" :key="opt" :value="opt">{{ opt }}</option>
                            </select>
                            <div v-else-if="p.type === 'bool'" class="flex items-center justify-between p-2.5 bg-gray-50 dark:bg-gray-800 rounded-lg border dark:border-gray-700">
                                <span class="text-xs text-gray-600 dark:text-gray-400">{{ p.description }}</span>
                                <button
                                    @click="newBinding.config[p.name] = !newBinding.config[p.name]"
                                    type="button"
                                    :class="[newBinding.config[p.name] ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors']"
                                >
                                    <span :class="[newBinding.config[p.name] ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                                </button>
                            </div>
                            <input
                                v-else
                                :type="(p.name.includes('key') || p.name.includes('token')) ? 'password' : 'text'"
                                v-model="newBinding.config[p.name]"
                                class="input-field text-xs"
                                :placeholder="p.description || p.default || ''"
                                :required="p.mandatory"
                                autocomplete="off"
                            />
                        </div>
                    </div>

                    <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-700">
                        <span class="text-xs font-bold text-gray-800 dark:text-gray-200">Active Connection</span>
                        <button
                            @click="newBinding.is_active = !newBinding.is_active"
                            type="button"
                            :class="[newBinding.is_active ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600', 'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors']"
                        >
                            <span :class="[newBinding.is_active ? 'translate-x-4' : 'translate-x-0', 'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>

                    <div class="flex justify-end gap-3">
                        <button type="button" @click="closeAddForm" class="btn btn-secondary text-xs">Cancel</button>
                        <button type="submit" :disabled="isSaving" class="btn btn-primary text-xs flex items-center gap-1.5">
                            <IconAnimateSpin v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
                            <IconPlus v-else class="w-3.5 h-3.5" />
                            <span>{{ isSaving ? 'Creating...' : 'Add Binding' }}</span>
                        </button>
                    </div>
                </form>
            </div>

            <!-- Loading -->
            <div v-if="isLoading" class="flex items-center justify-center py-12 text-xs font-bold text-gray-400">
                <IconAnimateSpin class="w-6 h-6 text-blue-500 mr-2" />
                <span>Loading {{ cfg.label }} bindings...</span>
            </div>

            <!-- Empty -->
            <div v-else-if="bindings.length === 0" class="text-center py-16 bg-gray-50 dark:bg-gray-800/40 rounded-2xl border border-dashed dark:border-gray-700">
                <IconCpuChip class="w-12 h-12 text-gray-400 mx-auto mb-2 opacity-40" />
                <p class="text-sm font-bold text-gray-700 dark:text-gray-300">No {{ cfg.label }} bindings configured</p>
                <p class="text-xs text-gray-500 mt-1">{{ cfg.description }}</p>
                <button @click="openAddForm" class="btn btn-primary btn-sm mt-3">
                    <IconPlus class="w-3.5 h-3.5 mr-1" />
                    Add First Binding
                </button>
            </div>

            <!-- Cards Grid -->
            <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                <BindingCard
                    v-for="b in bindings"
                    :key="b.id"
                    :binding="b"
                    :binding-type="bindingType"
                    :available-types="availableTypes"
                    @saved="onBindingSaved"
                    @deleted="onBindingDeleted"
                />
            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
</style>
