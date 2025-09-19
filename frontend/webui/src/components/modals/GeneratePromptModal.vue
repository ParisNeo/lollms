<script setup>
import { ref, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { usePromptsStore } from '../../stores/prompts';
import { useTasksStore } from '../../stores/tasks';
import GenericModal from './GenericModal.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();
const promptsStore = usePromptsStore();
const tasksStore = useTasksStore();

const prompt = ref('');
const isLoading = ref(false);

const modalProps = computed(() => uiStore.modalData('generatePrompt'));
const isSystemPrompt = computed(() => modalProps.value?.isSystemPrompt || false);
const onTaskSubmitted = computed(() => modalProps.value?.onTaskSubmitted);

const title = computed(() => isSystemPrompt.value ? 'Generate New System Prompt' : 'Generate New User Prompt');

async function handleGenerate() {
    if (!prompt.value.trim() || isLoading.value) return;
    isLoading.value = true;
    try {
        let task;
        if (isSystemPrompt.value) {
            task = await adminStore.generateSystemPrompt(prompt.value);
        } else {
            task = await promptsStore.generatePrompt(prompt.value);
        }
        
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
    uiStore.closeModal('generatePrompt');
}
</script>

<template>
    <GenericModal modalName="generatePrompt" :title="title">
        <template #body>
            <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">
                Describe the kind of prompt you want the AI to create. Be descriptive. For example: "Create a prompt that acts as a Python coding expert, specializing in data analysis with pandas."
            </p>
            <form @submit.prevent="handleGenerate">
                <textarea 
                    v-model="prompt"
                    rows="6"
                    class="input-field w-full"
                    placeholder="Describe the prompt you want to create..."
                ></textarea>
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