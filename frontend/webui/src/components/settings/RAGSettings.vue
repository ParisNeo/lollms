<script setup>
import { ref, onMounted, watch, computed, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import IconDatabase from '../../assets/icons/IconDatabase.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();
const { user } = storeToRefs(authStore);

// Form state
const form = ref({
    rag_top_k: 10,
    max_rag_len: 80000,
    rag_n_hops: 0,
    rag_min_sim_percent: 50,
    rag_retrieval_mode: 'hybrid',
    rag_dense_weight: 0.5,
    rag_bm25_weight: 0.5,
    rag_graph_weight: 0.3,
    rag_rrf_k: 60,
    rag_use_graph: false,
    rag_graph_response_type: 'chunks_summary',
    default_rag_chunk_size: 2048,
    default_rag_chunk_overlap: 256,
    default_rag_metadata_mode: 'none'
});

const isLoading = ref(false);
const hasChanges = ref(false);
let isPopulating = false;
let pristineState = '{}';

const areSettingsForced = computed(() => Boolean(user.value?.rag_settings_forced));

const populateForm = () => {
    if (user.value) {
        isPopulating = true;
        form.value = {
            rag_top_k: user.value.rag_top_k ?? 10,
            max_rag_len: user.value.max_rag_len ?? 80000,
            rag_n_hops: user.value.rag_n_hops ?? 0,
            rag_min_sim_percent: user.value.rag_min_sim_percent ?? 50,
            rag_retrieval_mode: user.value.rag_retrieval_mode || 'hybrid',
            rag_dense_weight: user.value.rag_dense_weight ?? 0.5,
            rag_bm25_weight: user.value.rag_bm25_weight ?? 0.5,
            rag_graph_weight: user.value.rag_graph_weight ?? 0.3,
            rag_rrf_k: user.value.rag_rrf_k ?? 60,
            rag_use_graph: Boolean(user.value.rag_use_graph),
            rag_graph_response_type: user.value.rag_graph_response_type || 'chunks_summary',
            default_rag_chunk_size: user.value.default_rag_chunk_size || 2048,
            default_rag_chunk_overlap: user.value.default_rag_chunk_overlap || 256,
            default_rag_metadata_mode: user.value.default_rag_metadata_mode || 'none',
        };
        pristineState = JSON.stringify(form.value);
        nextTick(() => {
            hasChanges.value = false;
            isPopulating = false;
        });
    }
};

onMounted(populateForm);
watch(user, populateForm, { deep: true });

watch(form, (newValue) => {
    if (!isPopulating && !areSettingsForced.value) {
        hasChanges.value = JSON.stringify(newValue) !== pristineState;
    }
}, { deep: true });

async function handleSave() {
    if (areSettingsForced.value) return;
    isLoading.value = true;
    try {
        await authStore.updateUserPreferences(form.value);
        uiStore.addNotification('RAG preferences updated.', 'success');
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
    } catch (error) {
        // Handled by global interceptor
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-2xl overflow-hidden border border-gray-100 dark:border-gray-700">
        <!-- Header -->
        <div class="px-6 py-5 border-b border-gray-100 dark:border-gray-700/80 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="p-2.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-xl">
                    <IconDatabase class="w-6 h-6" />
                </div>
                <div>
                    <h2 class="text-xl font-bold text-gray-900 dark:text-white">Retrieval-Augmented Generation (RAG)</h2>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        Configure semantic vector retrieval, lexical fusion, and knowledge graph queries.
                    </p>
                </div>
            </div>
            <div v-if="areSettingsForced" class="flex items-center gap-2 px-3 py-1.5 bg-amber-500/10 text-amber-600 dark:text-amber-400 rounded-full border border-amber-500/20 text-xs font-black uppercase tracking-wider">
                <span>🔒 Enforced by Admin</span>
            </div>
        </div>

        <!-- Admin Enforced Banner -->
        <div v-if="areSettingsForced" class="p-4 bg-amber-50 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-800/60 flex items-start gap-3">
            <IconInfo class="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div class="text-xs text-amber-900 dark:text-amber-200 leading-relaxed">
                <strong class="font-bold">System Override Active:</strong> An administrator has enforced global RAG parameters (God Mode). All personal preferences are locked and frozen to maintain enterprise-wide retrieval consistency.
            </div>
        </div>

        <!-- Form Body -->
        <form @submit.prevent="handleSave" class="p-6 space-y-8">
            <fieldset :disabled="areSettingsForced" class="space-y-8" :class="{'opacity-65 pointer-events-none select-none': areSettingsForced}">
                
                <!-- Query Retrieval Strategy & Weights -->
                <div class="space-y-4">
                    <div class="flex items-center justify-between border-b dark:border-gray-700/60 pb-2">
                        <h3 class="text-sm font-black uppercase tracking-wider text-gray-700 dark:text-gray-300">Retrieval Engine & Hybrid Scoring</h3>
                        <span class="text-[10px] font-mono font-bold text-blue-500 uppercase">{{ form.rag_retrieval_mode }}</span>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-5">
                        <div>
                            <label for="rag-retrieval-mode" class="block text-xs font-bold uppercase text-gray-500 mb-1">Strategy</label>
                            <select id="rag-retrieval-mode" v-model="form.rag_retrieval_mode" class="input-field text-xs">
                                <option value="hybrid">Tri-Modal Hybrid (Dense + BM25 + RRF)</option>
                                <option value="dense">Dense Semantic Vectors Only</option>
                                <option value="graph_hybrid">Knowledge Graph Hybrid (Dense + BM25 + Graph)</option>
                            </select>
                        </div>
                        <div>
                            <label for="rag-top-k" class="block text-xs font-bold uppercase text-gray-500 mb-1">Top-K Chunks</label>
                            <input id="rag-top-k" type="number" v-model.number="form.rag_top_k" min="1" max="100" class="input-field text-xs">
                        </div>
                        <div>
                            <label for="rag-min-sim" class="block text-xs font-bold uppercase text-gray-500 mb-1">Min Similarity %</label>
                            <input id="rag-min-sim" type="number" v-model.number="form.rag_min_sim_percent" min="0" max="100" step="1" class="input-field text-xs">
                        </div>
                    </div>

                    <!-- Sliders for Hybrid Weights -->
                    <div class="p-4 bg-gray-50 dark:bg-gray-900/40 rounded-xl border border-gray-100 dark:border-gray-700/60 grid grid-cols-1 sm:grid-cols-3 gap-6">
                        <div>
                            <div class="flex justify-between text-xs font-bold text-gray-700 dark:text-gray-300 mb-1">
                                <span>Dense Vector Weight</span>
                                <span class="text-blue-500 font-mono">{{ form.rag_dense_weight }}</span>
                            </div>
                            <input type="range" v-model.number="form.rag_dense_weight" min="0" max="1" step="0.05" class="w-full accent-blue-600">
                        </div>
                        <div>
                            <div class="flex justify-between text-xs font-bold text-gray-700 dark:text-gray-300 mb-1">
                                <span>BM25 Lexical Weight</span>
                                <span class="text-purple-500 font-mono">{{ form.rag_bm25_weight }}</span>
                            </div>
                            <input type="range" v-model.number="form.rag_bm25_weight" min="0" max="1" step="0.05" class="w-full accent-purple-600">
                        </div>
                        <div>
                            <div class="flex justify-between text-xs font-bold text-gray-700 dark:text-gray-300 mb-1">
                                <span>RRF Constant (k)</span>
                                <span class="text-emerald-500 font-mono">{{ form.rag_rrf_k }}</span>
                            </div>
                            <input type="range" v-model.number="form.rag_rrf_k" min="1" max="120" step="1" class="w-full accent-emerald-600">
                        </div>
                    </div>
                </div>

                <!-- Context Limits & Expansion -->
                <div class="space-y-4">
                    <h3 class="text-sm font-black uppercase tracking-wider text-gray-700 dark:text-gray-300 border-b dark:border-gray-700/60 pb-2">Context Window Allocation</h3>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-5">
                        <div>
                            <label for="max-rag-len" class="block text-xs font-bold uppercase text-gray-500 mb-1">Max RAG Length (chars)</label>
                            <input id="max-rag-len" type="number" v-model.number="form.max_rag_len" min="1000" max="500000" step="1000" class="input-field text-xs">
                            <p class="text-[10px] text-gray-400 mt-1">Maximum characters injected into the prompt context.</p>
                        </div>
                        <div>
                            <label for="rag-n-hops" class="block text-xs font-bold uppercase text-gray-500 mb-1">Expansion Hops</label>
                            <input id="rag-n-hops" type="number" v-model.number="form.rag_n_hops" min="0" max="5" class="input-field text-xs">
                            <p class="text-[10px] text-gray-400 mt-1">Adjacent chunk hops retrieved to preserve continuity.</p>
                        </div>
                    </div>
                </div>

                <!-- Datastore Defaults -->
                <div class="space-y-4">
                    <h3 class="text-sm font-black uppercase tracking-wider text-gray-700 dark:text-gray-300 border-b dark:border-gray-700/60 pb-2">Default Indexing Parameters</h3>
                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-5">
                        <div>
                            <label for="chunk-size" class="block text-xs font-bold uppercase text-gray-500 mb-1">Default Chunk Size</label>
                            <input id="chunk-size" type="number" v-model.number="form.default_rag_chunk_size" min="100" max="16000" class="input-field text-xs">
                        </div>
                        <div>
                            <label for="chunk-overlap" class="block text-xs font-bold uppercase text-gray-500 mb-1">Default Chunk Overlap</label>
                            <input id="chunk-overlap" type="number" v-model.number="form.default_rag_chunk_overlap" min="0" max="4000" class="input-field text-xs">
                        </div>
                        <div>
                            <label for="metadata-mode" class="block text-xs font-bold uppercase text-gray-500 mb-1">Metadata Mode</label>
                            <select id="metadata-mode" v-model="form.default_rag_metadata_mode" class="input-field text-xs">
                                <option value="none">None</option>
                                <option value="manual">Manual</option>
                                <option value="auto-generate">Auto-Generate</option>
                                <option value="rewrite-chunk">Rewrite Chunk</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- Knowledge Graph -->
                <div class="space-y-4">
                    <h3 class="text-sm font-black uppercase tracking-wider text-gray-700 dark:text-gray-300 border-b dark:border-gray-700/60 pb-2">Knowledge Graph Integration</h3>
                    <div class="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-900/40 rounded-xl border border-gray-100 dark:border-gray-700/60">
                        <div>
                            <span class="text-xs font-bold text-gray-800 dark:text-gray-200 block">Use Knowledge Graph</span>
                            <span class="text-[10px] text-gray-400">Include semantic entity relationships in search context.</span>
                        </div>
                        <input type="checkbox" v-model="form.rag_use_graph" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                    </div>
                    <div v-if="form.rag_use_graph" class="grid grid-cols-1 sm:grid-cols-2 gap-5 pl-2">
                        <div>
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Graph Response Format</label>
                            <select v-model="form.rag_graph_response_type" class="input-field text-xs">
                                <option value="chunks_summary">Chunks Summary</option>
                                <option value="graph_only">Graph Only</option>
                                <option value="full">Full Triples Response</option>
                            </select>
                        </div>
                    </div>
                </div>
            </fieldset>

            <!-- Actions Footer -->
            <div class="flex justify-end pt-4 border-t border-gray-100 dark:border-gray-700">
                <button type="submit" class="btn btn-primary px-8" :disabled="areSettingsForced || !hasChanges || isLoading">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isLoading ? 'Saving...' : 'Save RAG Preferences' }}
                </button>
            </div>
        </form>
    </div>
</template>