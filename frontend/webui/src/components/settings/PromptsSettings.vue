<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { usePromptsStore } from '../../stores/prompts';
import { useUiStore } from '../../stores/ui';
import useEventBus from '../../services/eventBus';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconTicket from '../../assets/icons/IconTicket.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

const promptsStore = usePromptsStore();
const uiStore = useUiStore();
const { on, off } = useEventBus();

const openedCategories = ref({});
const pendingGenerationTaskId = ref(null);

onMounted(() => {
    promptsStore.fetchPrompts();
    on('task:completed', handleTaskCompletion);
});

onUnmounted(() => {
    off('task:completed', handleTaskCompletion);
});

const userPromptsByCategory = computed(() => promptsStore.userPromptsByCategory);

function toggleCategory(category) {
    openedCategories.value[category] = !openedCategories.value[category];
}

function handleAddPrompt() {
    uiStore.openModal('editPrompt', { prompt: {}, isSystemPrompt: false });
}

function handleGeneratePrompt() {
    uiStore.openModal('generatePrompt', {
        isSystemPrompt: false,
        onTaskSubmitted: (taskId) => {
            pendingGenerationTaskId.value = taskId;
        }
    });
}

function handleTaskCompletion(task) {
    if (task && task.id === pendingGenerationTaskId.value) {
        pendingGenerationTaskId.value = null;
        if (uiStore.isModalOpen('tasksManager')) {
            uiStore.closeModal('tasksManager');
        }
        if (task.status === 'completed' && task.result) {
            handleEditPrompt(task.result);
        } else {
            uiStore.addNotification('Prompt generation did not complete successfully.', 'warning');
        }
    }
}

function handleEditPrompt(prompt) {
    uiStore.openModal('editPrompt', { prompt: { ...prompt }, isSystemPrompt: false });
}

async function handleDeletePrompt(prompt) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Prompt '${prompt.name}'?`,
        message: 'This action cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        await promptsStore.deletePrompt(prompt.id);
    }
}
</script>

<template>
    <div class="space-y-6">
        <div class="flex justify-between items-center">
            <div>
                <h2 class="text-xl font-bold">My Prompts</h2>
                <p class="text-sm text-gray-500">Manage your personal library of reusable prompts.</p>
            </div>
            <div class="flex items-center gap-2">
                <button @click="handleGeneratePrompt" class="btn btn-secondary">
                    <IconSparkles class="w-4 h-4 mr-2" />
                    Generate with AI
                </button>
                <button @click="handleAddPrompt" class="btn btn-primary">Add New Prompt</button>
            </div>
        </div>

        <div v-if="promptsStore.isLoading" class="text-center p-4">Loading prompts...</div>
        <div v-else-if="Object.keys(userPromptsByCategory).length === 0" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
            <p>You haven't created any prompts yet.</p>
        </div>

        <div v-else class="space-y-3">
            <div v-for="(prompts, category) in userPromptsByCategory" :key="category">
                <button @click="toggleCategory(category)" class="w-full flex justify-between items-center p-2 bg-gray-100 dark:bg-gray-700/50 rounded-t-lg">
                    <h3 class="font-semibold">{{ category }}</h3>
                    <IconChevronRight class="w-5 h-5 transition-transform" :class="{'rotate-90': openedCategories[category]}" />
                </button>
                <div v-if="openedCategories[category]" class="border border-t-0 dark:border-gray-700/50 rounded-b-lg">
                    <div v-for="prompt in prompts" :key="prompt.id" class="p-3 flex items-center justify-between border-t dark:border-gray-700/50 first:border-t-0">
                        <div class="flex items-center gap-3 flex-grow truncate">
                            <img v-if="prompt.icon" :src="prompt.icon" class="h-8 w-8 rounded-md flex-shrink-0 object-cover" alt="Icon">
                            <IconTicket v-else class="h-8 w-8 flex-shrink-0 text-gray-400 p-1" />
                            <div class="flex-grow truncate">
                                <p class="font-medium truncate">{{ prompt.name }}</p>
                                <p class="text-xs text-gray-500 truncate">{{ prompt.description || 'No description' }}</p>
                            </div>
                        </div>
                        <div class="flex items-center gap-x-2 flex-shrink-0">
                            <button @click="handleEditPrompt(prompt)" class="btn btn-secondary btn-sm p-2" title="Edit"><IconPencil class="w-4 h-4" /></button>
                            <button @click="handleDeletePrompt(prompt)" class="btn btn-danger btn-sm p-2" title="Delete"><IconTrash class="w-4 h-4" /></button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>