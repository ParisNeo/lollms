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

// Function to populate form from user state
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
        hasChanges.value = false;
    }
};

// Populate form on mount and when user data changes
onMounted(populateForm);
watch(user, populateForm, { deep: true });

// Watch for changes in the form to enable/disable the save button
watch(form, () => {
    hasChanges.value = true;
}, { deep: true });

// Handle form submission
async function handleSave() {
    isLoading.value = true;
    try {
        await authStore.updateUserPreferences(form.value);
        hasChanges.value = false;
    } catch (error) {
        // Error handled by interceptor
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <section>
        <h4 class="text-lg font-semibold mb-4 border-b dark:border-gray-600 pb-2">RAG Parameters</h4>
        <form @submit.prevent="handleSave" class="space-y-6 max-w-2xl">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                    <label for="ragTopK" class="block text-sm font-medium">RAG Top K</label>
                    <input type="number" id="ragTopK" v-model.number="form.rag_top_k" class="input-field mt-1" step="1" min="1" placeholder="e.g., 10">
                </div>
                <div>
                    <label for="ragMaxLen" class="block text-sm font-medium">Maximum RAG Length (chars)</label>
                    <input type="number" id="ragMaxLen" v-model.number="form.max_rag_len" class="input-field mt-1" step="1" min="1" placeholder="e.g., 80000">
                </div>
                <div>
                    <label for="ragHops" class="block text-sm font-medium">Maximum RAG Hops</label>
                    <input type="number" id="ragHops" v-model.number="form.rag_n_hops" class="input-field mt-1" step="1" min="0" placeholder="e.g., 0">
                </div>
                <div>
                    <label for="ragMinSim" class="block text-sm font-medium">RAG Min Similarity %</label>
                    <input type="number" id="ragMinSim" v-model.number="form.rag_min_sim_percent" class="input-field mt-1" step="1" min="1" max="100" placeholder="e.g., 50">
                </div>
            </div>

            <div class="space-y-4">
                <label for="useGraph" class="flex items-center cursor-pointer">
                    <input type="checkbox" id="useGraph" v-model="form.rag_use_graph" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                    <span class="ml-2 text-sm">Use Graph for RAG (if available)</span>
                </label>
                <div v-if="form.rag_use_graph">
                    <label for="graphResponseType" class="block text-sm font-medium mb-1">Graph Response Type</label>
                    <select id="graphResponseType" v-model="form.rag_graph_response_type" class="input-field">
                        <option value="chunks_summary">Chunks Summary</option>
                        <option value="graph_only">Graph Only</option>
                        <option value="full">Full Response</option>
                    </select>
                </div>
            </div>

             <div class="text-right pt-4">
                <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                    {{ isLoading ? 'Saving...' : 'Save RAG Settings' }}
                </button>
            </div>
        </form>
    </section>
</template>