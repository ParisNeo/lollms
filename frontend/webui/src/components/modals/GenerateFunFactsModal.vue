<script setup>
import { ref, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import GenericModal from './GenericModal.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const prompt = ref('');
const category = ref('');
const isLoading = ref(false);

const modalProps = computed(() => uiStore.modalData('generateFunFacts'));
const onTaskSubmitted = computed(() => modalProps.value?.onTaskSubmitted);

async function handleGenerate() {
    if (!prompt.value.trim() || isLoading.value) return;
    isLoading.value = true;
    try {
        const task = await adminStore.generateFunFacts(prompt.value, category.value);
        if (task) {
            if (onTaskSubmitted.value) {
                onTaskSubmitted.value(task.id);
            }
            uiStore.openModal('tasksManager', { initialTaskId: task.id });
        }
        closeModal();
    } catch (error) {
        // Error is handled by global interceptor
    } finally {
        isLoading.value = false;
    }
}

function closeModal() {
    prompt.value = '';
    category.value = '';
    uiStore.closeModal('generateFunFacts');
}
</script>

<template>
    <GenericModal modalName="generateFunFacts" title="Generate Fun Facts with AI">
        <template #body>
            <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Provide a topic, idea, or a detailed prompt. The AI will generate fun facts based on your input. You can also specify a category to add them to.
            </p>
            <form @submit.prevent="handleGenerate" class="space-y-4">
                <div>
                    <label for="ff-prompt" class="block text-sm font-medium">Topic or Prompt</label>
                    <textarea 
                        id="ff-prompt"
                        v-model="prompt"
                        rows="4"
                        class="input-field w-full mt-1"
                        placeholder="e.g., 'The history of coffee' or 'Generate 10 surprising facts about space exploration'"
                    ></textarea>
                </div>
                <div>
                    <label for="ff-category" class="block text-sm font-medium">Category (optional)</label>
                    <input 
                        id="ff-category"
                        v-model="category"
                        type="text"
                        class="input-field w-full mt-1"
                        placeholder="e.g., Space, History. If empty, uses the topic."
                    />
                </div>
            </form>
        </template>
        <template #footer>
            <button @click="closeModal" class="btn btn-secondary">Cancel</button>
            <button @click="handleGenerate" class="btn btn-primary" :disabled="!prompt.trim() || isLoading">
                <IconSparkles class="w-4 h-4 mr-2" :class="{'animate-pulse': isLoading}" />
                {{ isLoading ? 'Generating...' : 'Generate' }}
            </button>
        </template>
    </GenericModal>
</template>
