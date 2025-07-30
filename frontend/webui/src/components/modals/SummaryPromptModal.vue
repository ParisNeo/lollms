<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { usePromptsStore } from '../../stores/prompts';
import { useSocialStore } from '../../stores/social';
import GenericModal from '../ui/GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import apiClient from '../../services/api';

// Icon Imports
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconShare from '../../assets/icons/IconShare.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const promptsStore = usePromptsStore();
const socialStore = useSocialStore();

const modalProps = computed(() => uiStore.modalData('summaryPromptModal'));
const onApply = computed(() => modalProps.value?.onApply);

const promptText = ref('');
const savedPrompts = computed(() => promptsStore.savedPrompts);
const selectedSavedPromptId = ref(null);
const newPromptName = ref('');
const fileInputRef = ref(null);
const importInputRef = ref(null);
const isExtractingText = ref(false);
const showShareUI = ref(false);
const friendToShare = ref(null);
const isSaving = ref(false);

watch(() => uiStore.isModalOpen('summaryPromptModal'), (isOpen) => {
    if (isOpen) {
        promptsStore.fetchPrompts();
        socialStore.fetchFriends();
        promptText.value = modalProps.value?.initialPrompt || '';
        selectedSavedPromptId.value = null;
        newPromptName.value = '';
        showShareUI.value = false;
        friendToShare.value = null;
    }
});

function handleLoadSelected() {
    const selected = savedPrompts.value.find(p => p.id === selectedSavedPromptId.value);
    if (selected) {
        promptText.value = selected.content;
        newPromptName.value = selected.name; // Pre-fill name for saving over it
    }
}

async function handleSave() {
    if (!promptText.value.trim()) return;
    isSaving.value = true;
    try {
        if (selectedSavedPromptId.value) {
            const nameToSave = newPromptName.value.trim() || savedPrompts.value.find(p => p.id === selectedSavedPromptId.value)?.name;
            const updatedPrompt = await promptsStore.updatePrompt(selectedSavedPromptId.value, nameToSave, promptText.value);
            newPromptName.value = updatedPrompt.name;
        } else {
            const name = newPromptName.value.trim() || `Prompt ${new Date().toLocaleString()}`;
            const newPrompt = await promptsStore.savePrompt(name, promptText.value);
            selectedSavedPromptId.value = newPrompt.id;
            newPromptName.value = newPrompt.name;
        }
    } finally {
        isSaving.value = false;
    }
}

async function handleDelete() {
    if (!selectedSavedPromptId.value) return;
    const confirmed = await uiStore.showConfirmation({ title: 'Delete Prompt?', message: 'This saved prompt will be permanently deleted.' });
    if (confirmed) {
        await promptsStore.deletePrompt(selectedSavedPromptId.value);
        selectedSavedPromptId.value = null;
        newPromptName.value = '';
    }
}

function triggerFileInput(ref) { ref.value?.click(); }

async function handleFileLoad(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    isExtractingText.value = true;
    const formData = new FormData();
    for (const file of files) { formData.append('files', file); }
    try {
        const response = await apiClient.post('/api/files/extract-text', formData);
        promptText.value += (promptText.value ? '\n\n' : '') + response.data.text;
        uiStore.addNotification(`Imported text from ${files.length} file(s).`, 'success');
    } finally {
        isExtractingText.value = false;
        if (fileInputRef.value) fileInputRef.value.value = '';
    }
}

function exportToFile() {
    const blob = new Blob([promptText.value], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'prompt.txt';
    a.click();
    URL.revokeObjectURL(url);
}

async function importFromFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    const text = await file.text();
    promptText.value = text;
    event.target.value = '';
}

async function handleShare() {
    if (!friendToShare.value) return;
    await promptsStore.sharePrompt(promptText.value, friendToShare.value);
    showShareUI.value = false;
    friendToShare.value = null;
}

function handleApply() {
    if (onApply.value) {
        onApply.value(promptText.value);
    }
    uiStore.closeModal('summaryPromptModal');
}
</script>

<template>
    <GenericModal modal-name="summaryPromptModal" title="Process Content with AI" maxWidthClass="max-w-4xl">
        <template #body>
            <div class="space-y-4">
                <!-- Toolbar -->
                <div class="flex items-center gap-2 p-2 bg-gray-100 dark:bg-gray-700/50 rounded-lg border dark:border-gray-600">
                    <button @click="triggerFileInput(fileInputRef)" class="btn-icon" title="Load text from file" :disabled="isExtractingText">
                        <IconAnimateSpin v-if="isExtractingText" class="w-5 h-5" />
                        <IconPlus v-else class="w-5 h-5" />
                    </button>
                    <input type="file" ref="fileInputRef" @change="handleFileLoad" multiple class="hidden" />
                    <div class="h-6 border-l dark:border-gray-600"></div>
                    <button @click="triggerFileInput(importInputRef)" class="btn-icon" title="Import prompt from .txt file">
                        <IconArrowDownTray class="w-5 h-5" />
                    </button>
                     <input type="file" ref="importInputRef" @change="importFromFile" class="hidden" accept=".txt"/>
                    <button @click="exportToFile" class="btn-icon" title="Export prompt to .txt file">
                        <IconArrowUpTray class="w-5 h-5" />
                    </button>
                    <div class="h-6 border-l dark:border-gray-600"></div>
                     <button @click="showShareUI = !showShareUI" class="btn-icon" title="Share prompt with a friend">
                        <IconShare class="w-5 h-5" />
                    </button>
                </div>

                <!-- Editor -->
                <CodeMirrorEditor v-model="promptText" class="h-64" />

                <!-- Saved Prompts Section -->
                <div class="space-y-4 pt-4 border-t dark:border-gray-600">
                     <h4 class="text-base font-semibold text-gray-800 dark:text-gray-200">Manage Saved Prompts</h4>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-medium">Load Prompt</label>
                            <div class="flex items-center gap-2 mt-1">
                                <select v-model="selectedSavedPromptId" class="input-field flex-grow">
                                    <option :value="null">-- Select a prompt --</option>
                                    <option v-for="p in savedPrompts" :key="p.id" :value="p.id">{{ p.name }}</option>
                                </select>
                                <button @click="handleLoadSelected" type="button" class="btn-icon" title="Load selected prompt" :disabled="!selectedSavedPromptId">
                                    <IconArrowDownTray class="w-5 h-5" />
                                </button>
                            </div>
                        </div>
                        <div>
                            <label class="block text-sm font-medium">Save Prompt</label>
                            <div class="flex items-center gap-2 mt-1">
                                <input v-model="newPromptName" type="text" :placeholder="selectedSavedPromptId ? 'Rename and save' : 'Enter new name'" class="input-field flex-grow" />
                                <button @click="handleSave" class="btn-icon" title="Save current prompt" :disabled="isSaving || !promptText.trim()">
                                    <IconAnimateSpin v-if="isSaving" class="w-5 h-5" />
                                    <IconArrowUpTray v-else class="w-5 h-5" />
                                </button>
                                <button v-if="selectedSavedPromptId" @click="handleDelete" class="btn-icon-danger" title="Delete selected prompt">
                                    <IconTrash class="w-5 h-5" />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                 <!-- Share UI -->
                <div v-if="showShareUI" class="mt-4 p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <h4 class="font-semibold mb-2">Share with a friend</h4>
                    <div class="flex items-center gap-2">
                        <select v-model="friendToShare" class="input-field flex-grow">
                            <option :value="null">Select a friend</option>
                            <option v-for="friend in socialStore.friends" :key="friend.id" :value="friend.username">{{ friend.username }}</option>
                        </select>
                        <button @click="handleShare" class="btn btn-primary" :disabled="!friendToShare">Send</button>
                        <button @click="showShareUI = false" class="btn btn-secondary">Cancel</button>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end w-full gap-3">
                <button @click="uiStore.closeModal('summaryPromptModal')" class="btn btn-secondary">Cancel</button>
                <button @click="handleApply" class="btn btn-primary flex items-center gap-2">
                    <IconPlayCircle class="w-5 h-5" />
                    <span>Apply & Process</span>
                </button>
            </div>
        </template>
    </GenericModal>
</template>