<script setup>
import { ref, onMounted, watch, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import IconSelectMenu from '../ui/IconSelectMenu.vue';

const authStore = useAuthStore();
const dataStore = useDataStore();

const { user } = storeToRefs(authStore);
const { availableLLMModelsGrouped, isLoadingLollmsModels } = storeToRefs(dataStore);

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
let pristineState = {};

const areSettingsForced = computed(() => user.value?.llm_settings_overridden ?? false);

const activeModelName = computed({
    get: () => form.value.lollms_model_name,
    set: (name) => {
        if (!areSettingsForced.value) {
            form.value.lollms_model_name = name;
        }
    }
});

const populateForm = () => {
    if (user.value) {
        form.value = {
            lollms_model_name: user.value.lollms_model_name || '',
            llm_ctx_size: user.value.llm_ctx_size ?? null,
            llm_temperature: user.value.llm_temperature ?? null,
            llm_top_k: user.value.llm_top_k ?? null,
            llm_top_p: user.value.llm_top_p ?? null,
            llm_repeat_penalty: user.value.llm_repeat_penalty ?? null,
            llm_repeat_last_n: user.value.llm_repeat_last_n ?? null,
            put_thoughts_in_context: user.value.put_thoughts_in_context || false
        };
        pristineState = JSON.parse(JSON.stringify(form.value));
        hasChanges.value = false;
    }
};

onMounted(() => {
    if (dataStore.availableLollmsModels.length === 0) {
        dataStore.fetchAvailableLollmsModels();
    }
    populateForm();
});

watch(user, populateForm, { deep: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== JSON.stringify(pristineState);
}, { deep: true });

async function handleSave() {
    isLoading.value = true;
    try {
        await authStore.updateUserPreferences(form.value);
    } catch (error) {
        // Handled by API interceptor
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="px-4 py-5 sm:p-6">
            <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">LLM Configuration</h2>
            <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">
                Adjust the default parameters for the Large Language Model. These settings will apply to new discussions.
            </p>
        </div>
        <div class="border-t border-gray-200 dark:border-gray-700">
            <form @submit.prevent="handleSave" class="p-4 sm:p-6 space-y-6">
                <!-- Model Selection -->
                <div>
                    <label for="lollmsModelSelect" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Default LLM Model</label>
                     <IconSelectMenu 
                        v-model="activeModelName" 
                        :items="availableLLMModelsGrouped"
                        :is-loading="isLoadingLollmsModels"
                        placeholder="Select a model"
                        class="mt-1"
                    />
                </div>
                
                 <div v-if="areSettingsForced" class="p-4 bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500 text-blue-800 dark:text-blue-200">
                    <p class="font-semibold">Settings Overridden</p>
                    <p class="text-sm">An administrator has set and locked the generation parameters for this model. Your personal settings will not apply.</p>
                </div>

                <!-- Generation Parameters -->
                <fieldset :disabled="areSettingsForced" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" :class="{'opacity-60 cursor-not-allowed': areSettingsForced}">
                    <div>
                        <label for="contextSize" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Context Size (tokens)</label>
                        <input type="number" id="contextSize" v-model.number="form.llm_ctx_size" class="input-field mt-1" placeholder="e.g., 4096">
                    </div>
                    <div>
                        <label for="temperature" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Temperature</label>
                        <input type="number" id="temperature" v-model.number="form.llm_temperature" class="input-field mt-1" step="0.01" min="0" max="2" placeholder="e.g., 0.7">
                    </div>
                    <div>
                        <label for="topK" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Top K</label>
                        <input type="number" id="topK" v-model.number="form.llm_top_k" class="input-field mt-1" step="1" min="1" placeholder="e.g., 50">
                    </div>
                    <div>
                        <label for="topP" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Top P</label>
                        <input type="number" id="topP" v-model.number="form.llm_top_p" class="input-field mt-1" step="0.01" min="0" max="1" placeholder="e.g., 0.95">
                    </div>
                    <div>
                        <label for="repeatPenalty" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Repeat Penalty</label>
                        <input type="number" id="repeatPenalty" v-model.number="form.llm_repeat_penalty" class="input-field mt-1" step="0.01" min="0" placeholder="e.g., 1.1">
                    </div>
                    <div>
                        <label for="repeatLastN" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Repeat Last N</label>
                        <input type="number" id="repeatLastN" v-model.number="form.llm_repeat_last_n" class="input-field mt-1" step="1" min="0" placeholder="e.g., 64">
                    </div>
                </fieldset>

                <!-- Toggle for 'think' blocks -->
                <div class="relative flex items-start" :class="{'opacity-60 cursor-not-allowed': areSettingsForced}">
                    <div class="flex h-6 items-center">
                        <input id="putThoughts" v-model="form.put_thoughts_in_context" type="checkbox" :disabled="areSettingsForced" class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 dark:bg-gray-700 text-blue-600 focus:ring-blue-600 dark:focus:ring-blue-600 dark:ring-offset-gray-800">
                    </div>
                    <div class="ml-3 text-sm leading-6">
                        <label for="putThoughts" class="font-medium text-gray-900 dark:text-gray-300">Include "think" blocks in context</label>
                        <p class="text-gray-500 dark:text-gray-400">Allows the AI to see its previous reasoning steps.</p>
                    </div>
                </div>

                <!-- Save Button -->
                <div class="flex justify-end pt-4">
                    <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges || areSettingsForced">
                        <span v-if="isLoading">Saving...</span>
                        <span v-else>Save LLM Settings</span>
                    </button>
                </div>
            </form>
        </div>
    </div>
</template>