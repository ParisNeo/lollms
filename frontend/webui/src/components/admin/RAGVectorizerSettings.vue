<template>
    <div class="space-y-8">
        <!-- Admin God Mode Override Card -->
        <div class="bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-950/20 dark:to-orange-950/20 shadow-md rounded-2xl p-6 border-2 border-amber-300 dark:border-amber-700/60">
            <div class="flex items-start justify-between gap-4 mb-4">
                <div>
                    <div class="flex items-center gap-2">
                        <span class="text-xl">⚡</span>
                        <h3 class="text-lg font-black text-amber-900 dark:text-amber-200 uppercase tracking-tight">Admin God Mode (Global Enforced RAG)</h3>
                    </div>
                    <p class="text-xs text-amber-700 dark:text-amber-300/80 mt-1">
                        When enabled, all user-level RAG configurations will be completely overridden and locked. Users will see a frozen read-only view of these exact settings.
                    </p>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                    <span class="text-xs font-black uppercase tracking-wider" :class="isGodModeEnabled ? 'text-amber-600 dark:text-amber-400' : 'text-gray-400'">
                        {{ isGodModeEnabled ? 'Enforced' : 'Disabled' }}
                    </span>
                    <button @click="toggleGodMode" type="button" :class="[isGodModeEnabled ? 'bg-amber-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch']">
                        <span :class="[isGodModeEnabled ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                    </button>
                </div>
            </div>

            <div v-if="isGodModeEnabled" class="mt-6 pt-6 border-t border-amber-200 dark:border-amber-800/60 space-y-6">
                <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
                    <div>
                        <label class="block text-xs font-black uppercase text-amber-800 dark:text-amber-300 tracking-wider mb-1">Forced Vectorizer</label>
                        <select v-model="forcedVectorizer" class="input-field text-xs">
                            <option value="">-- Default System Vectorizer --</option>
                            <option v-for="(alias, key) in vectorizerAliases" :key="key" :value="key">{{ alias.title || key }} (Alias)</option>
                            <option disabled>──────────</option>
                            <option v-for="vec in availableVectorizers" :key="vec.id || vec.alias" :value="vec.alias">{{ vec.alias }} ({{ vec.vectorizer_name }})</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-black uppercase text-amber-800 dark:text-amber-300 tracking-wider mb-1">Forced Retrieval Strategy</label>
                        <select v-model="forcedRetrievalMode" class="input-field text-xs">
                            <option value="hybrid">Tri-Modal Hybrid (Dense + BM25 + RRF)</option>
                            <option value="dense">Dense Semantic Vectors Only</option>
                            <option value="graph_hybrid">Knowledge Graph Hybrid (Dense + BM25 + Graph)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-black uppercase text-amber-800 dark:text-amber-300 tracking-wider mb-1">Forced Top K</label>
                        <input type="number" v-model.number="forcedTopK" min="1" max="100" class="input-field text-xs">
                    </div>
                    <div>
                        <label class="block text-xs font-black uppercase text-amber-800 dark:text-amber-300 tracking-wider mb-1">Forced Chunk Size (chars)</label>
                        <input type="number" v-model.number="forcedChunkSize" min="100" max="64000" class="input-field text-xs">
                    </div>
                    <div>
                        <label class="block text-xs font-black uppercase text-amber-800 dark:text-amber-300 tracking-wider mb-1">Forced Chunk Overlap (chars)</label>
                        <input type="number" v-model.number="forcedChunkOverlap" min="0" max="8000" class="input-field text-xs">
                    </div>
                    <div>
                        <label class="block text-xs font-black uppercase text-amber-800 dark:text-amber-300 tracking-wider mb-1">Forced Min Similarity %</label>
                        <input type="number" v-model.number="forcedMinSim" min="0" max="100" step="1" class="input-field text-xs">
                    </div>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-4 border-t border-amber-200/60 dark:border-amber-800/40">
                    <div>
                        <div class="flex justify-between text-xs font-bold text-amber-900 dark:text-amber-200 mb-1">
                            <span>Forced Dense Weight</span>
                            <span class="font-mono text-amber-600 dark:text-amber-400">{{ forcedDenseWeight }}</span>
                        </div>
                        <input type="range" v-model.number="forcedDenseWeight" min="0" max="1" step="0.05" class="w-full accent-amber-600">
                    </div>
                    <div>
                        <div class="flex justify-between text-xs font-bold text-amber-900 dark:text-amber-200 mb-1">
                            <span>Forced BM25 Sparse Weight</span>
                            <span class="font-mono text-amber-600 dark:text-amber-400">{{ forcedBm25Weight }}</span>
                        </div>
                        <input type="range" v-model.number="forcedBm25Weight" min="0" max="1" step="0.05" class="w-full accent-amber-600">
                    </div>
                    <div>
                        <div class="flex justify-between text-xs font-bold text-amber-900 dark:text-amber-200 mb-1">
                            <span>Forced RRF Constant (k)</span>
                            <span class="font-mono text-amber-600 dark:text-amber-400">{{ forcedRrfK }}</span>
                        </div>
                        <input type="range" v-model.number="forcedRrfK" min="1" max="120" step="1" class="w-full accent-amber-600">
                    </div>
                </div>

                <div class="flex items-center justify-between p-3 bg-white/60 dark:bg-gray-900/60 rounded-xl border border-amber-200 dark:border-amber-800">
                    <span class="text-xs font-bold text-amber-900 dark:text-amber-200">Force Knowledge Graph Retrieval</span>
                    <button @click="forcedUseGraph = !forcedUseGraph" type="button" :class="[forcedUseGraph ? 'bg-amber-600' : 'bg-gray-300 dark:bg-gray-600', 'toggle-switch']">
                        <span :class="[forcedUseGraph ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                    </button>
                </div>
            </div>

            <div class="flex justify-end mt-4">
                <button @click="saveGodModeSettings" class="btn bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs px-5 py-2 rounded-xl shadow-md">
                    Save God Mode Settings
                </button>
            </div>
        </div>

        <!-- Global Defaults & Retrieval Policies -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-2xl p-6 border border-gray-100 dark:border-gray-700">
            <h3 class="text-xl font-bold text-gray-900 dark:text-white mb-1">Standard RAG Engine Policies</h3>
            <p class="text-xs text-gray-500 mb-6">Configure system-wide baseline retrieval policies, default vectorizers, and hybrid scoring parameters.</p>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- Toggle Restriction -->
                <div class="toggle-container md:col-span-2">
                    <span class="toggle-label">
                        Restrict to Aliases Only
                        <span class="toggle-description">When enabled, non-admin users can only select from the aliases you define below.</span>
                    </span>
                    <button @click="toggleRestriction" type="button" :class="[restrictToAliases ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']">
                        <span :class="[restrictToAliases ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                    </button>
                </div>

                <!-- Allow Custom Chunking -->
                <div class="toggle-container md:col-span-2">
                    <span class="toggle-label">
                        Allow User Chunking Customization
                        <span class="toggle-description">When enabled, users can configure custom chunk sizes and overlaps for their personal datastores.</span>
                    </span>
                    <button @click="allowUserChunking = !allowUserChunking" type="button" :class="[allowUserChunking ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']">
                        <span :class="[allowUserChunking ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                    </button>
                </div>

                <!-- Default Chunking Strategy -->
                <div>
                    <label for="default_rag_chunking_strategy" class="block text-xs font-black uppercase text-gray-500 tracking-wider">Default Chunking Strategy</label>
                    <select id="default_rag_chunking_strategy" v-model="defaultChunkingStrategy" class="input-field mt-1.5 text-sm">
                        <option value="recursive">Recursive Tree (Recommended)</option>
                        <option value="structure">Structure-Aware (Markdown)</option>
                        <option value="token">Token Window</option>
                        <option value="semantic">Semantic Valley</option>
                        <option value="contextual">Contextual Retrieval</option>
                        <option value="late">Late Chunking</option>
                        <option value="paragraph">Paragraph Blocks</option>
                        <option value="character">Fixed Character</option>
                    </select>
                    <p class="text-[10px] text-gray-400 mt-1">Default text cutting algorithm used when creating new knowledge stores.</p>
                </div>

                <!-- Default Vectorizer -->
                <div>
                    <label for="default_safe_store_vectorizer" class="block text-xs font-black uppercase text-gray-500 tracking-wider">Default Vectorizer for New Stores</label>
                    <select id="default_safe_store_vectorizer" v-model="defaultVectorizer" class="input-field mt-1.5 text-sm">
                        <option value="">-- Select Default --</option>
                        <option v-for="(alias, key) in vectorizerAliases" :key="key" :value="key">{{ alias.title || key }} (Alias)</option>
                        <option v-if="!restrictToAliases" disabled>──────────</option>
                        <option v-for="vec in availableVectorizers" :key="vec.id || vec.alias" :value="vec.alias">{{ vec.alias }} ({{ vec.vectorizer_name }})</option>
                    </select>
                    <p class="text-[10px] text-gray-400 mt-1">Pre-selected vectorizer when creating a new Data Store.</p>
                </div>

                <!-- Default Retrieval Mode -->
                <div>
                    <label for="default_rag_retrieval_mode" class="block text-xs font-black uppercase text-gray-500 tracking-wider">Default Baseline Retrieval Strategy</label>
                    <select id="default_rag_retrieval_mode" v-model="defaultRetrievalMode" class="input-field mt-1.5 text-sm">
                        <option value="hybrid">Tri-Modal Hybrid (Dense + BM25 Lexical + RRF)</option>
                        <option value="dense">Dense Semantic Vectors Only</option>
                        <option value="graph_hybrid">Knowledge Graph Hybrid (Dense + BM25 + Graph)</option>
                    </select>
                    <p class="text-[10px] text-gray-400 mt-1">Default strategy applied during automated chat turn RAG queries.</p>
                </div>
            </div>

            <!-- Hybrid Scoring Defaults -->
            <div class="mt-6 pt-6 border-t border-gray-100 dark:border-gray-700/60">
                <h4 class="text-xs font-black uppercase text-gray-400 tracking-widest mb-4">Default Fusion Weights (RRF / WCS)</h4>
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
                    <div>
                        <div class="flex justify-between text-xs font-bold text-gray-700 dark:text-gray-300 mb-1">
                            <span>Dense Weight</span>
                            <span class="text-blue-500 font-mono">{{ denseWeight }}</span>
                        </div>
                        <input type="range" v-model.number="denseWeight" min="0" max="1" step="0.05" class="w-full accent-blue-600">
                    </div>
                    <div>
                        <div class="flex justify-between text-xs font-bold text-gray-700 dark:text-gray-300 mb-1">
                            <span>BM25 Sparse Weight</span>
                            <span class="text-purple-500 font-mono">{{ bm25Weight }}</span>
                        </div>
                        <input type="range" v-model.number="bm25Weight" min="0" max="1" step="0.05" class="w-full accent-purple-600">
                    </div>
                    <div>
                        <div class="flex justify-between text-xs font-bold text-gray-700 dark:text-gray-300 mb-1">
                            <span>RRF Constant (k)</span>
                            <span class="text-emerald-500 font-mono">{{ rrfK }}</span>
                        </div>
                        <input type="range" v-model.number="rrfK" min="1" max="120" step="1" class="w-full accent-emerald-600">
                    </div>
                </div>
            </div>

            <div class="flex justify-end mt-6">
                <button @click="saveGeneralSettings" class="btn btn-primary" :disabled="!hasGeneralChanges">
                    Save Baseline Settings
                </button>
            </div>
        </div>

        <!-- Alias Management -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-2xl p-6 border border-gray-100 dark:border-gray-700">
            <div class="flex justify-between items-center mb-6">
                <div>
                    <h3 class="text-xl font-bold text-gray-900 dark:text-white">Vectorizer Aliases</h3>
                    <p class="text-xs text-gray-500 mt-0.5">Pre-configured vectorizer shortcuts exposed to users.</p>
                </div>
                <button @click="showAddForm()" class="btn btn-primary btn-sm">+ Add Alias</button>
            </div>
            
            <div v-if="isLoadingAliases" class="text-center p-8 text-gray-400">Loading Aliases...</div>
            <div v-else-if="Object.keys(vectorizerAliases).length === 0" class="text-center p-8 bg-gray-50 dark:bg-gray-900/30 rounded-xl border border-dashed dark:border-gray-700">
                <p class="text-sm text-gray-500">No aliases defined. Add an alias to create user-friendly vectorizer presets.</p>
            </div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div v-for="(aliasData, aliasName) in vectorizerAliases" :key="aliasName" class="bg-gray-50 dark:bg-gray-900/40 p-4 rounded-xl border border-gray-200 dark:border-gray-700/80 flex flex-col justify-between">
                    <div>
                        <div class="flex justify-between items-start mb-2">
                            <div>
                                <h4 class="font-bold text-base text-gray-900 dark:text-white">{{ aliasData.title || aliasName }}</h4>
                                <p class="text-xs font-mono text-blue-600 dark:text-blue-400">{{ aliasName }}</p>
                            </div>
                            <div class="flex gap-2">
                                <button @click="showEditForm(aliasName, aliasData)" class="text-xs font-semibold text-blue-600 hover:underline">Edit</button>
                                <button @click="handleDelete(aliasName)" class="text-xs font-semibold text-red-500 hover:underline">Delete</button>
                            </div>
                        </div>
                        <p v-if="aliasData.description" class="text-xs text-gray-500 mb-3 line-clamp-2">{{ aliasData.description }}</p>
                    </div>

                    <div class="mt-2 border-t dark:border-gray-800 pt-2 text-[11px] space-y-1">
                        <p><span class="font-semibold text-gray-600 dark:text-gray-400">Backend:</span> <span class="capitalize font-mono">{{ aliasData.vectorizer_name }}</span></p>
                        <div v-if="aliasData.vectorizer_config && Object.keys(aliasData.vectorizer_config).length > 0">
                            <span class="font-semibold text-gray-600 dark:text-gray-400 block mb-1">Config:</span>
                            <JsonRenderer :json="aliasData.vectorizer_config" class="p-2 bg-white dark:bg-gray-950 rounded border dark:border-gray-800 text-[10px]" />
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Add/Edit Modal -->
        <GenericModal modalName="ragAliasEditor" :title="isEditMode ? 'Edit Vectorizer Alias' : 'Add Vectorizer Alias'">
            <template #body>
                <form @submit.prevent="handleSubmit" class="space-y-4">
                    <div>
                        <label for="alias-name" class="block text-sm font-medium">Alias Key <span class="text-red-500">*</span></label>
                        <input id="alias-name" v-model="form.alias_name" type="text" class="input-field mt-1 font-mono" required :disabled="isEditMode" placeholder="e.g., local_minilm">
                    </div>
                    <div>
                        <label for="alias-title" class="block text-sm font-medium">Display Title</label>
                        <input id="alias-title" v-model="form.alias_data.title" type="text" class="input-field mt-1" placeholder="e.g., Fast Local MiniLM">
                    </div>
                    <div>
                        <label for="alias-desc" class="block text-sm font-medium">Description</label>
                        <textarea id="alias-desc" v-model="form.alias_data.description" rows="2" class="input-field mt-1" placeholder="A short description for users."></textarea>
                    </div>
                     <div>
                        <label for="vectorizer-name" class="block text-sm font-medium">Vectorizer Backend <span class="text-red-500">*</span></label>
                        <select id="vectorizer-name" v-model="form.alias_data.vectorizer_name" class="input-field mt-1" required>
                            <option value="">-- Select Type --</option>
                            <option v-for="vec in availableVectorizers" :key="vec.id || vec.alias" :value="vec.vectorizer_name">{{ vec.alias }} ({{ vec.vectorizer_name }})</option>
                        </select>
                    </div>
                    <div>
                        <label for="vectorizer-config" class="block text-sm font-medium">Configuration (JSON)</label>
                        <textarea id="vectorizer-config" v-model="configJson" rows="5" class="input-field mt-1 font-mono text-xs"></textarea>
                        <p v-if="jsonError" class="text-xs text-red-500 mt-1">{{ jsonError }}</p>
                    </div>
                </form>
            </template>
            <template #footer>
                <button @click="uiStore.closeModal('ragAliasEditor')" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" :disabled="!!jsonError" class="btn btn-primary">{{ isEditMode ? 'Save Changes' : 'Create Alias' }}</button>
            </template>
        </GenericModal>
    </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import GenericModal from '../modals/GenericModal.vue';
import JsonRenderer from '../ui/JsonRenderer.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const vectorizerAliases = ref({});
const isLoadingAliases = ref(false);
const isEditMode = ref(false);

// God Mode state
const isGodModeEnabled = ref(false);
const forcedVectorizer = ref('');
const forcedRetrievalMode = ref('hybrid');
const forcedTopK = ref(10);
const forcedChunkSize = ref(2048);
const forcedChunkOverlap = ref(256);
const forcedMinSim = ref(50.0);
const forcedDenseWeight = ref(0.5);
const forcedBm25Weight = ref(0.5);
const forcedRrfK = ref(60);
const forcedUseGraph = ref(false);

// Baseline state
const restrictToAliases = ref(false);
const allowUserChunking = ref(true);
const defaultChunkingStrategy = ref('recursive');
const defaultVectorizer = ref('');
const defaultRetrievalMode = ref('hybrid');
const denseWeight = ref(0.5);
const bm25Weight = ref(0.5);
const rrfK = ref(60);

const form = ref({
    alias_name: '',
    alias_data: {
        vectorizer_name: '',
        vectorizer_config: {},
        title: '',
        description: ''
    }
});
const configJson = ref('{}');
const jsonError = ref('');

const availableVectorizers = computed(() => dataStore.availableVectorizers);

let pristineGeneralSettings = {};

const hasGeneralChanges = computed(() => {
    return restrictToAliases.value !== pristineGeneralSettings.restrict_vectorizers_to_aliases ||
           allowUserChunking.value !== pristineGeneralSettings.allow_user_chunking_config ||
           defaultChunkingStrategy.value !== pristineGeneralSettings.default_rag_chunking_strategy ||
           defaultVectorizer.value !== pristineGeneralSettings.default_safe_store_vectorizer ||
           defaultRetrievalMode.value !== pristineGeneralSettings.default_rag_retrieval_mode ||
           denseWeight.value !== pristineGeneralSettings.default_rag_dense_weight ||
           bm25Weight.value !== pristineGeneralSettings.default_rag_bm25_weight ||
           rrfK.value !== pristineGeneralSettings.default_rag_rrf_k;
});

watch(configJson, (newJson) => {
    try {
        form.value.alias_data.vectorizer_config = JSON.parse(newJson);
        jsonError.value = '';
    } catch(e) {
        jsonError.value = 'Invalid JSON format.';
    }
});

watch(() => adminStore.globalSettings, (settings) => {
    if (!settings || !Array.isArray(settings)) return;

    // Aliases
    const aliasesSetting = settings.find(s => s.key === 'rag_vectorizer_aliases');
    if (aliasesSetting) vectorizerAliases.value = aliasesSetting.value || {};

    // God Mode
    const godModeSetting = settings.find(s => s.key === 'force_rag_settings_mode');
    if (godModeSetting) isGodModeEnabled.value = (godModeSetting.value === 'force_always');

    const fVec = settings.find(s => s.key === 'force_rag_vectorizer');
    if (fVec) forcedVectorizer.value = fVec.value || '';

    const fMode = settings.find(s => s.key === 'force_rag_retrieval_mode');
    if (fMode) forcedRetrievalMode.value = fMode.value || 'hybrid';

    const fTopK = settings.find(s => s.key === 'force_rag_top_k');
    if (fTopK) forcedTopK.value = Number(fTopK.value ?? 10);

    const fChunk = settings.find(s => s.key === 'force_rag_chunk_size');
    if (fChunk) forcedChunkSize.value = Number(fChunk.value ?? 2048);

    const fOverlap = settings.find(s => s.key === 'force_rag_chunk_overlap');
    if (fOverlap) forcedChunkOverlap.value = Number(fOverlap.value ?? 256);

    const fMinSim = settings.find(s => s.key === 'force_rag_min_sim_percent');
    if (fMinSim) forcedMinSim.value = Number(fMinSim.value ?? 50.0);

    const fDense = settings.find(s => s.key === 'force_rag_dense_weight');
    if (fDense) forcedDenseWeight.value = Number(fDense.value ?? 0.5);

    const fBm25 = settings.find(s => s.key === 'force_rag_bm25_weight');
    if (fBm25) forcedBm25Weight.value = Number(fBm25.value ?? 0.5);

    const fRrf = settings.find(s => s.key === 'force_rag_rrf_k');
    if (fRrf) forcedRrfK.value = Number(fRrf.value ?? 60);

    const fGraph = settings.find(s => s.key === 'force_rag_use_graph');
    if (fGraph) forcedUseGraph.value = Boolean(fGraph.value);

    // Standard
    const restrictSetting = settings.find(s => s.key === 'restrict_vectorizers_to_aliases');
    if (restrictSetting) {
        restrictToAliases.value = Boolean(restrictSetting.value);
        pristineGeneralSettings.restrict_vectorizers_to_aliases = restrictToAliases.value;
    }

    const chunkOptSetting = settings.find(s => s.key === 'allow_user_chunking_config');
    if (chunkOptSetting) {
        allowUserChunking.value = Boolean(chunkOptSetting.value);
        pristineGeneralSettings.allow_user_chunking_config = allowUserChunking.value;
    }

    const chunkStratSetting = settings.find(s => s.key === 'default_rag_chunking_strategy');
    if (chunkStratSetting) {
        defaultChunkingStrategy.value = chunkStratSetting.value || 'recursive';
        pristineGeneralSettings.default_rag_chunking_strategy = defaultChunkingStrategy.value;
    }

    const defaultVecSetting = settings.find(s => s.key === 'default_safe_store_vectorizer');
    if (defaultVecSetting) {
        defaultVectorizer.value = defaultVecSetting.value || '';
        pristineGeneralSettings.default_safe_store_vectorizer = defaultVectorizer.value;
    }

    const modeSetting = settings.find(s => s.key === 'default_rag_retrieval_mode');
    if (modeSetting) {
        defaultRetrievalMode.value = modeSetting.value || 'hybrid';
        pristineGeneralSettings.default_rag_retrieval_mode = defaultRetrievalMode.value;
    }

    const dwSetting = settings.find(s => s.key === 'default_rag_dense_weight');
    if (dwSetting) {
        denseWeight.value = Number(dwSetting.value ?? 0.5);
        pristineGeneralSettings.default_rag_dense_weight = denseWeight.value;
    }

    const bwSetting = settings.find(s => s.key === 'default_rag_bm25_weight');
    if (bwSetting) {
        bm25Weight.value = Number(bwSetting.value ?? 0.5);
        pristineGeneralSettings.default_rag_bm25_weight = bm25Weight.value;
    }

    const rrfSetting = settings.find(s => s.key === 'default_rag_rrf_k');
    if (rrfSetting) {
        rrfK.value = Number(rrfSetting.value ?? 60);
        pristineGeneralSettings.default_rag_rrf_k = rrfK.value;
    }
}, { deep: true, immediate: true });

onMounted(async () => {
    isLoadingAliases.value = true;
    await adminStore.fetchGlobalSettings();
    await dataStore.fetchAvailableVectorizers();
    isLoadingAliases.value = false;
});

function toggleRestriction() {
    restrictToAliases.value = !restrictToAliases.value;
}

function toggleGodMode() {
    isGodModeEnabled.value = !isGodModeEnabled.value;
}

async function saveGodModeSettings() {
    await adminStore.updateGlobalSettings({
        'force_rag_settings_mode': isGodModeEnabled.value ? 'force_always' : 'disabled',
        'force_rag_vectorizer': forcedVectorizer.value,
        'force_rag_retrieval_mode': forcedRetrievalMode.value,
        'force_rag_top_k': forcedTopK.value,
        'force_rag_chunk_size': forcedChunkSize.value,
        'force_rag_chunk_overlap': forcedChunkOverlap.value,
        'force_rag_min_sim_percent': forcedMinSim.value,
        'force_rag_dense_weight': forcedDenseWeight.value,
        'force_rag_bm25_weight': forcedBm25Weight.value,
        'force_rag_rrf_k': forcedRrfK.value,
        'force_rag_use_graph': forcedUseGraph.value
    });
    uiStore.addNotification('God Mode RAG settings updated successfully.', 'success');
}

async function saveGeneralSettings() {
    await adminStore.updateGlobalSettings({
        'restrict_vectorizers_to_aliases': restrictToAliases.value,
        'allow_user_chunking_config': allowUserChunking.value,
        'default_rag_chunking_strategy': defaultChunkingStrategy.value,
        'default_safe_store_vectorizer': defaultVectorizer.value,
        'default_rag_retrieval_mode': defaultRetrievalMode.value,
        'default_rag_dense_weight': denseWeight.value,
        'default_rag_bm25_weight': bm25Weight.value,
        'default_rag_rrf_k': rrfK.value
    });
}

function showAddForm() {
    isEditMode.value = false;
    form.value = { alias_name: '', alias_data: { vectorizer_name: '', vectorizer_config: {}, title: '', description: '' } };
    configJson.value = '{}';
    uiStore.openModal('ragAliasEditor');
}

function showEditForm(aliasName, aliasData) {
    isEditMode.value = true;
    form.value = {
        alias_name: aliasName,
        alias_data: JSON.parse(JSON.stringify(aliasData))
    };
    configJson.value = JSON.stringify(aliasData.vectorizer_config || {}, null, 2);
    uiStore.openModal('ragAliasEditor');
}

async function handleSubmit() {
    if (jsonError.value) return;
    if (!form.value.alias_name.trim() || !form.value.alias_data.vectorizer_name) {
        uiStore.addNotification('Alias Key and Vectorizer Backend are required.', 'warning');
        return;
    }
    await adminStore.addOrUpdateRagAlias(form.value);
    uiStore.closeModal('ragAliasEditor');
}

async function handleDelete(aliasName) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete alias '${aliasName}'?`,
        message: 'This cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed.confirmed) {
        await adminStore.deleteRagAlias(aliasName);
    }
}
</script>

<style scoped>
@reference "tailwindcss";
.toggle-container { @apply flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700/50 rounded-xl border border-gray-100 dark:border-gray-700; }
.toggle-label { @apply grow flex flex-col text-sm font-medium text-gray-900 dark:text-gray-100; }
.toggle-description { @apply text-xs text-gray-500 dark:text-gray-400 font-normal mt-1; }
.toggle-switch { @apply relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out; }
.toggle-knob { @apply pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-colors duration-200 ease-in-out; }
</style>