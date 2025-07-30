<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { usePromptsStore } from '../../stores/prompts';
import { useSocialStore } from '../../stores/social';
import GenericModal from '../ui/GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconShare from '../../assets/icons/IconShare.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';

const uiStore = useUiStore();
const promptsStore = usePromptsStore();
const socialStore = useSocialStore();

const modalProps = computed(() => uiStore.modalData('dataZonePromptManagement'));
const onLoad = computed(() => modalProps.value?.onLoad);

const savedPrompts = computed(() => promptsStore.savedPrompts);
const selectedPrompt = ref(null);
const newPromptName = ref('');
const newPromptContent = ref('');
const isEditing = ref(false);
const importInputRef = ref(null);

watch(() => uiStore.isModalOpen('dataZonePromptManagement'), (isOpen) => {
    if (isOpen) {
        promptsStore.fetchPrompts();
        socialStore.fetchFriends();
        resetForm();
    }
});

function resetForm() {
    selectedPrompt.value = null;
    isEditing.value = false;
    newPromptName.value = '';
    newPromptContent.value = '';
}

function selectPrompt(prompt) {
    if (isEditing.value && selectedPrompt.value?.id === prompt.id) {
        resetForm();
    } else {
        selectedPrompt.value = { ...prompt };
        newPromptName.value = prompt.name;
        newPromptContent.value = prompt.content;
        isEditing.value = true;
    }
}

function startNewPrompt() {
    resetForm();
    isEditing.value = true;
}

async function handleSave() {
    if (!newPromptName.value.trim() || !newPromptContent.value.trim()) {
        uiStore.addNotification('Name and content are required.', 'warning');
        return;
    }
    if (selectedPrompt.value) {
        await promptsStore.updatePrompt(selectedPrompt.value.id, newPromptName.value, newPromptContent.value);
    } else {
        await promptsStore.savePrompt(newPromptName.value, newPromptContent.value);
    }
    resetForm();
}

async function handleDelete(prompt) {
    const confirmed = await uiStore.showConfirmation({ title: `Delete '${prompt.name}'?`, message: 'This action cannot be undone.' });
    if (confirmed) {
        await promptsStore.deletePrompt(prompt.id);
        if (selectedPrompt.value?.id === prompt.id) {
            resetForm();
        }
    }
}

function usePrompt() {
    if (onLoad.value && newPromptContent.value) {
        onLoad.value(newPromptContent.value);
        uiStore.closeModal('dataZonePromptManagement');
    }
}

function triggerImport() { importInputRef.value?.click(); }
async function handleImport(event) {
    const file = event.target.files[0];
    if (file) {
        await promptsStore.importPrompts(file);
    }
    event.target.value = '';
}

async function handleShare(prompt) {
    const friendUsername = await uiStore.showConfirmation({
        title: `Share '${prompt.name}'`,
        message: 'Select a friend to share this prompt with:',
        inputType: 'select',
        inputOptions: socialStore.friends.map(f => ({ value: f.username, text: f.username })),
        confirmText: 'Share'
    });
    if (friendUsername) {
        await promptsStore.sharePrompt(prompt.content, friendUsername);
    }
}
</script>

<template>
    <GenericModal modal-name="dataZonePromptManagement" title="Data Zone Prompt Management" maxWidthClass="max-w-5xl">
        <template #body>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 h-[60vh]">
                <!-- Prompt List -->
                <div class="md:col-span-1 flex flex-col h-full bg-gray-50 dark:bg-gray-700/50 rounded-lg p-2">
                    <div class="flex-shrink-0 mb-2">
                        <button @click="startNewPrompt" class="btn btn-secondary w-full">
                            <IconPlus class="w-4 h-4 mr-2" /> New Prompt
                        </button>
                    </div>
                    <div class="flex-grow overflow-y-auto">
                        <div v-if="promptsStore.isLoading" class="text-center p-4 text-sm">Loading...</div>
                        <div v-else-if="savedPrompts.length === 0" class="text-center p-4 text-sm text-gray-500">No saved prompts.</div>
                        <ul v-else class="space-y-1">
                            <li v-for="prompt in savedPrompts" :key="prompt.id">
                                <button @click="selectPrompt(prompt)" class="w-full text-left p-2 rounded-md truncate text-sm" :class="[selectedPrompt?.id === prompt.id ? 'bg-blue-200 dark:bg-blue-800 font-semibold' : 'hover:bg-gray-200 dark:hover:bg-gray-600']">
                                    {{ prompt.name }}
                                </button>
                            </li>
                        </ul>
                    </div>
                </div>

                <!-- Editor/Details View -->
                <div class="md:col-span-2 flex flex-col h-full">
                    <div v-if="isEditing" class="flex flex-col h-full space-y-4">
                        <div>
                            <label class="block text-sm font-medium">Prompt Name</label>
                            <input type="text" v-model="newPromptName" class="input-field mt-1" placeholder="A descriptive name for your prompt" />
                        </div>
                        <div class="flex-grow flex flex-col min-h-0">
                            <label class="block text-sm font-medium mb-1">Prompt Content</label>
                            <CodeMirrorEditor v-model="newPromptContent" class="flex-grow" placeholder="Enter your prompt here. Use @<name:type:default>@ for placeholders." />
                        </div>
                    </div>
                    <div v-else class="flex items-center justify-center h-full bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <p class="text-gray-500">Select a prompt to view or edit, or create a new one.</p>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-between w-full">
                <div>
                    <input type="file" ref="importInputRef" @change="handleImport" class="hidden" accept=".json" />
                    <button @click="triggerImport" class="btn btn-secondary" title="Import from JSON"><IconArrowDownTray class="w-4 h-4 mr-2" />Import</button>
                    <button @click="promptsStore.exportPrompts()" class="btn btn-secondary ml-2" title="Export all to JSON"><IconArrowUpTray class="w-4 h-4 mr-2" />Export</button>
                </div>
                <div class="flex gap-3">
                    <button @click="uiStore.closeModal('dataZonePromptManagement')" class="btn btn-secondary">Close</button>
                    <button v-if="isEditing && selectedPrompt" @click="handleDelete(selectedPrompt)" class="btn btn-danger">Delete</button>
                    <button v-if="isEditing && selectedPrompt" @click="handleShare(selectedPrompt)" class="btn btn-secondary">Share</button>
                    <button v-if="isEditing" @click="handleSave" class="btn btn-secondary">{{ selectedPrompt ? 'Save Changes' : 'Save New' }}</button>
                    <button @click="usePrompt" class="btn btn-primary" :disabled="!newPromptContent.trim()">Use Prompt</button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>