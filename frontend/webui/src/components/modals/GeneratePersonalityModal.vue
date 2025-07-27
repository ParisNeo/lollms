<script setup>
import { ref, computed, watch, onUnmounted } from 'vue';
import GenericModal from '../ui/GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const dataStore = useDataStore();
const tasksStore = useTasksStore();

const { tasks } = storeToRefs(tasksStore);

const prompt = ref('');
const taskId = ref(null);
const isLoading = ref(false);

const currentTask = computed(() => {
    if (!taskId.value) return null;
    return tasks.value.find(t => t.id === taskId.value);
});

const showProgressIndicator = computed(() => {
    return isLoading.value || (currentTask.value && ['pending', 'running'].includes(currentTask.value.status));
});

watch(() => uiStore.isModalOpen('generatePersonality'), (isOpen) => {
    if (isOpen) {
        prompt.value = '';
        taskId.value = null;
        isLoading.value = false;
    }
});

watch(currentTask, (newTask) => {
    if (!newTask) return;

    if (newTask.status === 'completed') {
        isLoading.value = false;
        
        let resultData = null;
        if (newTask.result && typeof newTask.result === 'string') {
            try {
                resultData = JSON.parse(newTask.result);
            } catch (e) {
                console.error("Failed to parse task result JSON:", e);
                uiStore.addNotification('Generation completed, but result data was malformed.', 'error');
            }
        } else {
            resultData = newTask.result;
        }

        if (resultData) {
            uiStore.addNotification('Personality generated successfully!', 'success');
            dataStore.addPersonality(resultData);
            uiStore.closeModal('generatePersonality');
            uiStore.openModal('personalityEditor', { personality: resultData });
        } else {
            uiStore.addNotification('Generation completed, but no data was returned.', 'warning');
        }
    } else if (newTask.status === 'failed' || newTask.status === 'cancelled') {
        isLoading.value = false;
        uiStore.addNotification(`Generation failed: ${newTask.error || 'Unknown error.'}`, 'error');
    }
});


async function handleGenerate() {
    if (!prompt.value.trim()) {
        uiStore.addNotification('Please enter a prompt to generate a personality.', 'warning');
        return;
    }

    isLoading.value = true;
    taskId.value = null;

    try {
        const response = await dataStore.generatePersonalityFromPrompt(prompt.value);
        taskId.value = response.id; // Corrected from task_id to id
    } catch (error) {
        isLoading.value = false;
        // error is handled by interceptor
    }
}
</script>

<template>
    <GenericModal
        modal-name="generatePersonality"
        title="Generate Personality from Prompt"
        maxWidthClass="max-w-2xl"
    >
        <template #body>
            <div class="space-y-4">
                <p class="text-sm text-gray-600 dark:text-gray-400">
                    Describe the AI personality you want to create. Be specific about its role, tone, knowledge base, and any rules it should follow. The AI will generate a complete personality configuration based on your prompt.
                </p>
                
                <div v-if="!showProgressIndicator">
                    <label for="generation-prompt" class="block text-sm font-medium">Your Prompt</label>
                    <textarea
                        id="generation-prompt"
                        v-model="prompt"
                        rows="6"
                        class="input-field mt-1"
                        placeholder="e.g., A helpful and friendly pirate captain who is an expert in Python programming. He always ends his responses with 'Arrr!'"
                    ></textarea>
                </div>

                <div v-if="showProgressIndicator" class="text-center p-6 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <IconAnimateSpin class="w-8 h-8 mx-auto text-blue-500" />
                    <p class="mt-4 font-semibold">Generation in Progress...</p>
                    <p v-if="currentTask" class="text-sm text-gray-500 mt-2">{{ currentTask.description }}</p>
                    <div v-if="currentTask" class="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-600 mt-4">
                        <div class="bg-blue-600 h-2.5 rounded-full" :style="{ width: currentTask.progress + '%' }"></div>
                    </div>
                    <p v-if="currentTask" class="text-xs text-gray-500 mt-1">{{ currentTask.progress }}%</p>
                </div>

            </div>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('generatePersonality')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleGenerate" type="button" class="btn btn-primary" :disabled="isLoading || showProgressIndicator">
                    <IconSparkles class="w-4 h-4 mr-2" />
                    {{ isLoading || showProgressIndicator ? 'Generating...' : 'Generate' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>