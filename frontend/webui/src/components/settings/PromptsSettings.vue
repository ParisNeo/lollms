<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { usePromptsStore } from '../../stores/prompts';
import { useUiStore } from '../../stores/ui';
import useEventBus from '../../services/eventBus';
import GenericModal from '../ui/GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconTicket from '../../assets/icons/IconTicket.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

const promptsStore = usePromptsStore();
const uiStore = useUiStore();
const { on, off } = useEventBus();

const currentPrompt = ref(null);
const fileInput = ref(null);
const isEditMode = computed(() => currentPrompt.value && currentPrompt.value.id);
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
    currentPrompt.value = {
        name: '',
        content: '',
        category: '',
        author: '',
        description: '',
        icon: null
    };
    uiStore.openModal('promptEditor');
}

function handleGeneratePrompt() {
    uiStore.openModal('generatePrompt', {
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
    currentPrompt.value = { ...prompt };
    uiStore.openModal('promptEditor');
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

async function handleSavePrompt() {
    if (!currentPrompt.value.name || !currentPrompt.value.content) {
        uiStore.addNotification('Name and Content are required.', 'warning');
        return;
    }
    try {
        if (isEditMode.value) {
            await promptsStore.updatePrompt(currentPrompt.value.id, currentPrompt.value);
        } else {
            await promptsStore.createPrompt(currentPrompt.value);
        }
        uiStore.closeModal('promptEditor');
    } catch(e) {
        // Error notification is handled by the store/API client
    }
}

function triggerIconUpload() {
    fileInput.value?.click();
}

function handleIconChange(event) {
    const file = event.target.files[0];
    if (file && file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (e) => {
            if (currentPrompt.value) {
                currentPrompt.value.icon = e.target.result;
            }
        };
        reader.readAsDataURL(file);
    }
}

function removeIcon() {
    if (currentPrompt.value) {
        currentPrompt.value.icon = null;
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

        <!-- Add/Edit Modal -->
        <GenericModal modalName="promptEditor" :title="isEditMode ? 'Edit Prompt' : 'Add New Prompt'" maxWidthClass="max-w-4xl">
            <template #body>
                <form v-if="currentPrompt" @submit.prevent="handleSavePrompt" class="space-y-4">
                    <div class="flex items-center gap-4">
                        <img v-if="currentPrompt.icon" :src="currentPrompt.icon" class="h-16 w-16 rounded-lg object-cover border dark:border-gray-600">
                        <div v-else class="h-16 w-16 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center border dark:border-gray-600">
                            <IconTicket class="h-10 w-10 text-gray-400" />
                        </div>
                        <div class="space-y-2">
                            <input type="file" ref="fileInput" @change="handleIconChange" accept="image/*" class="hidden">
                            <button type="button" @click="triggerIconUpload" class="btn btn-secondary text-sm">Upload Icon</button>
                            <button v-if="currentPrompt.icon" type="button" @click="removeIcon" class="btn btn-danger-outline text-sm">Remove Icon</button>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label for="prompt-name" class="block text-sm font-medium">Name <span class="text-red-500">*</span></label>
                            <input id="prompt-name" v-model="currentPrompt.name" type="text" class="input-field mt-1" required>
                        </div>
                        <div>
                            <label for="prompt-category" class="block text-sm font-medium">Category</label>
                            <input id="prompt-category" v-model="currentPrompt.category" type="text" class="input-field mt-1" placeholder="e.g., Writing, Coding">
                        </div>
                    </div>
                    <div>
                        <label for="prompt-description" class="block text-sm font-medium">Description</label>
                        <textarea id="prompt-description" v-model="currentPrompt.description" rows="2" class="input-field mt-1"></textarea>
                    </div>
                    <div>
                        <label for="prompt-content" class="block text-sm font-medium">Content <span class="text-red-500">*</span></label>
                        <CodeMirrorEditor v-model="currentPrompt.content" class="mt-1" />
                    </div>
                    <div class="p-3 bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500 text-blue-800 dark:text-blue-200">
                        <div class="flex items-center">
                            <IconInfo class="h-5 w-5 mr-2" />
                            <h4 class="font-bold">Placeholder Help</h4>
                        </div>
                        <div class="mt-2 text-xs space-y-1">
                            <p><code class="font-mono bg-blue-200 dark:bg-blue-800/50 px-1 rounded">@&lt;name&gt;@</code>: Simple text replacement.</p>
                            <p>For advanced options with a user-friendly form:</p>
                            <pre class="whitespace-pre-wrap font-mono text-xs bg-blue-100 dark:bg-blue-900/40 p-2 rounded">@&lt;name&gt;@
title: Display Title
type: str | text | int | float | bool
options: comma, separated, list
default: default value used if the user doesn't set it
help: A helpful tip for the user.
@&lt;/name&gt;@</pre>
                        </div>
                    </div>
                </form>
            </template>
            <template #footer>
                <button @click="uiStore.closeModal('promptEditor')" class="btn btn-secondary">Cancel</button>
                <button @click="handleSavePrompt" class="btn btn-primary">Save Prompt</button>
            </template>
        </GenericModal>
    </div>
</template>