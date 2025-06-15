<script setup>
import { ref, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';

const authStore = useAuthStore();
const dataStore = useDataStore();

// Use storeToRefs to get reactive state from the stores
const { user } = storeToRefs(authStore);
const { availableLollmsModels } = storeToRefs(dataStore);

// Form state
const form = ref({
    lollms_model_name: '',
    llm_ctx_size: 4096,
    llm_temperature: 0.7,
    llm_top_k: 50,
    llm_top_p: 0.95,
    llm_repeat_penalty: 1.1,
    llm_repeat_last_n: 64,
    put_thoughts_in_context: false
});
const isLoading = ref(false);
const hasChanges = ref(false);

// Function to populate form from user state
const populateForm = () => {
    if (user.value) {
        form.value = {
            lollms_model_name: user.value.lollms_model_name || '',
            llm_ctx_size: user.value.llm_ctx_size ?? 4096,
            llm_temperature: user.value.llm_temperature ?? 0.7,
            llm_top_k: user.value.llm_top_k ?? 50,
            llm_top_p: user.value.llm_top_p ?? 0.95,
            llm_repeat_penalty: user.value.llm_repeat_penalty ?? 1.1,
            llm_repeat_last_n: user.value.llm_repeat_last_n ?? 64,
            put_thoughts_in_context: user.value.put_thoughts_in_context || false
        };
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
        hasChanges.value = false; // Reset changes state on successful save
    } catch (error) {
        // Error notification handled by the API interceptor
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <section>
        <h4 class="text-lg font-semibold mb-4 border-b dark:border-gray-600 pb-2">LLM Configuration</h4>
        <form @submit.prevent="handleSave" class="space-y-6 max-w-2xl">
            <!-- Model Selection -->
            <div>
                <label for="lollmsModelSelect" class="block text-sm font-medium mb-1">Default LLM Model</label>
                <select id="lollmsModelSelect" v-model="form.lollms_model_name" class="input-field">
                    <option v-if="availableLollmsModels.length === 0" disabled value="">Loading models...</option>
                    <option v-for="model in availableLollmsModels" :key="model.name" :value="model.name">
                        {{ model.name }}
                    </option>
                </select>
            </div>

            <!-- Generation Parameters -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                    <label for="contextSize" class="block text-sm font-medium">Context Size (tokens)</label>
                    <input type="number" id="contextSize" v-model.number="form.llm_ctx_size" class="input-field mt-1" placeholder="e.g., 4096">
                </div>
                 <div>
                    <label for="temperature" class="block text-sm font-medium">Temperature</label>
                    <input type="number" id="temperature" v-model.number="form.llm_temperature" class="input-field mt-1" step="0.01" min="0" max="2" placeholder="e.g., 0.7">
                </div>
                <div>
                    <label for="topK" class="block text-sm font-medium">Top K</label>
                    <input type="number" id="topK" v-model.number="form.llm_top_k" class="input-field mt-1" step="1" min="1" placeholder="e.g., 50">
                </div>
                <div>
                    <label for="topP" class="block text-sm font-medium">Top P</label>
                    <input type="number" id="topP" v-model.number="form.llm_top_p" class="input-field mt-1" step="0.01" min="0" max="1" placeholder="e.g., 0.95">
                </div>
                <div>
                    <label for="repeatPenalty" class="block text-sm font-medium">Repeat Penalty</label>
                    <input type="number" id="repeatPenalty" v-model.number="form.llm_repeat_penalty" class="input-field mt-1" step="0.01" min="0" placeholder="e.g., 1.1">
                </div>
                <div>
                    <label for="repeatLastN" class="block text-sm font-medium">Repeat Last N</label>
                    <input type="number" id="repeatLastN" v-model.number="form.llm_repeat_last_n" class="input-field mt-1" step="1" min="0" placeholder="e.g., 64">
                </div>
            </div>

            <!-- Toggle for 'think' blocks -->
            <div>
                <label for="putThoughts" class="flex items-center cursor-pointer">
                    <input type="checkbox" id="putThoughts" v-model="form.put_thoughts_in_context" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                    <span class="ml-2 text-sm">Put thoughts in context (<code class="text-xs bg-gray-200 dark:bg-gray-700 p-1 rounded">think</code> blocks)</span>
                </label>
            </div>
            
            <!-- Save Button -->
            <div class="text-right pt-4">
                <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                    {{ isLoading ? 'Saving...' : 'Save LLM Settings' }}
                </button>
            </div>
        </form>
    </section>
</template>