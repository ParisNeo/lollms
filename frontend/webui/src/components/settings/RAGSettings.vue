<script setup>
import { ref, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../../stores/auth';

const authStore = useAuthStore();
const { user } = storeToRefs(authStore);

// Form state
const form = ref({
    rag_top_k: 10,
    max_rag_len: 80000,
    rag_n_hops: 0,
    rag_min_sim_percent: 50,
    rag_use_graph: false,
    rag_graph_response_type: 'chunks_summary'
});
const isLoading = ref(false);
const hasChanges = ref(false);

// A pristine copy to compare against for changes
let pristineState = {};

// Function to populate form from user state and set pristine state
const populateForm = () => {
    if (user.value) {
        form.value = {
            rag_top_k: user.value.rag_top_k ?? 10,
            max_rag_len: user.value.max_rag_len ?? 80000,
            rag_n_hops: user.value.rag_n_hops ?? 0,
            rag_min_sim_percent: user.value.rag_min_sim_percent ?? 50,
            rag_use_graph: user.value.rag_use_graph || false,
            rag_graph_response_type: user.value.rag_graph_response_type || 'chunks_summary',
        };
        pristineState = JSON.parse(JSON.stringify(form.value));
        hasChanges.value = false; // Reset on populate
    }
};

// Populate form on mount and when user data changes
onMounted(populateForm);
watch(user, populateForm, { deep: true });

// Watch for changes in the form to enable/disable the save button
watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== JSON.stringify(pristineState);
}, { deep: true });

// Handle form submission
async function handleSave() {
    isLoading.value = true;
    try {
        await authStore.updateUserPreferences(form.value);
        // The user watcher will repopulate the form and reset pristineState
    } catch (error) {
        // Error handled by interceptor
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="px-4 py-5 sm:p-6">
            <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">RAG Parameters</h2>
            <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">
                Configure the Retrieval-Augmented Generation (RAG) settings to control how context is retrieved from documents.
            </p>
        </div>
        <div class="border-t border-gray-200 dark:border-gray-700">
            <form @submit.prevent="handleSave" class="p-4 sm:p-6 space-y-6">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-8">
                    <div>
                        <label for="ragTopK" class="block text-sm font-medium text-gray-700 dark:text-gray-300">RAG Top K</label>
                        <input type="number" id="ragTopK" v-model.number="form.rag_top_k" class="input-field mt-1" step="1" min="1" placeholder="e.g., 10">
                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">The number of top matching document chunks to retrieve.</p>
                    </div>
                    <div>
                        <label for="ragMaxLen" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Maximum RAG Length (chars)</label>
                        <input type="number" id="ragMaxLen" v-model.number="form.max_rag_len" class="input-field mt-1" step="1" min="1" placeholder="e.g., 80000">
                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">The maximum total characters of retrieved chunks to add to the context.</p>
                    </div>
                    <div>
                        <label for="ragHops" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Maximum RAG Hops</label>
                        <input type="number" id="ragHops" v-model.number="form.rag_n_hops" class="input-field mt-1" step="1" min="0" placeholder="e.g., 0">
                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Number of RAG steps for context expansion.</p>
                    </div>
                    <div>
                        <label for="ragMinSim" class="block text-sm font-medium text-gray-700 dark:text-gray-300">RAG Min Similarity %</label>
                        <input type="number" id="ragMinSim" v-model.number="form.rag_min_sim_percent" class="input-field mt-1" step="1" min="1" max="100" placeholder="e.g., 50">
                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">The minimum similarity score for a chunk to be considered.</p>
                    </div>
                </div>

                <div class="space-y-4 pt-2">
                     <div class="relative flex items-start">
                        <div class="flex h-6 items-center">
                            <input id="useGraph" v-model="form.rag_use_graph" type="checkbox" class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 text-blue-600 focus:ring-blue-600 dark:focus:ring-blue-600 dark:ring-offset-gray-800">
                        </div>
                        <div class="ml-3 text-sm leading-6">
                            <label for="useGraph" class="font-medium text-gray-900 dark:text-gray-300">Use Graph for RAG</label>
                            <p class="text-gray-500 dark:text-gray-400">Leverage knowledge graphs for more contextual responses, if available.</p>
                        </div>
                    </div>

                    <transition enter-active-class="transition ease-out duration-200" enter-from-class="opacity-0 translate-y-2" enter-to-class="opacity-100 translate-y-0" leave-active-class="transition ease-in duration-150" leave-from-class="opacity-100 translate-y-0" leave-to-class="opacity-0 translate-y-2">
                        <div v-if="form.rag_use_graph" class="pl-9">
                            <label for="graphResponseType" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Graph Response Type</label>
                            <select id="graphResponseType" v-model="form.rag_graph_response_type" class="input-field">
                                <option value="chunks_summary">Chunks Summary</option>
                                <option value="graph_only">Graph Only</option>
                                <option value="full">Full Response</option>
                            </select>
                            <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">How the graph information should be integrated into the response.</p>
                        </div>
                    </transition>
                </div>

                <div class="flex justify-end pt-4">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                        <span v-if="isLoading">Saving...</span>
                        <span v-else>Save RAG Settings</span>
                    </button>
                </div>
            </form>
        </div>
    </div>
</template>