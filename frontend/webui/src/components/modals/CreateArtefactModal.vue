<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('createArtefact'));
const discussionId = computed(() => modalData.value?.discussionId || discussionsStore.currentDiscussionId);

const title = ref('');
const content = ref('');
const isLoading = ref(false);

watch(() => uiStore.isModalOpen('createArtefact'), (isOpen) => {
    if (isOpen) {
        title.value = 'Untitled Document.md';
        content.value = '';
    }
});

async function handleSubmit() {
    if (!discussionId.value) {
        uiStore.addNotification('No discussion selected.', 'error');
        return;
    }
    if (!title.value.trim()) {
        uiStore.addNotification('Title is required.', 'warning');
        return;
    }
    if (!content.value.trim()) {
        uiStore.addNotification('Content is required.', 'warning');
        return;
    }

    isLoading.value = true;
    try {
        await discussionsStore.createManualArtefact(
            discussionId.value,
            title.value.trim(),
            content.value
        );
        uiStore.closeModal('createArtefact');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modalName="createArtefact"
        title="Create New Document"
        maxWidthClass="max-w-3xl"
    >
        <template #body>
            <div class="space-y-4 p-1 h-full flex flex-col">
                <div>
                    <label for="artefact-title" class="label">Document Title</label>
                    <div class="relative mt-1">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <IconFileText class="h-4 w-4 text-gray-400" />
                        </div>
                        <input
                            id="artefact-title"
                            v-model="title"
                            type="text"
                            class="input-field pl-10"
                            placeholder="e.g. My Notes.md"
                            required
                        />
                    </div>
                </div>

                <div class="flex-grow flex flex-col min-h-[300px]">
                    <label class="label mb-1">Content</label>
                    <div class="flex-grow border border-gray-300 dark:border-gray-600 rounded-md overflow-hidden relative">
                        <CodeMirrorEditor 
                            v-model="content" 
                            class="h-full absolute inset-0"
                            placeholder="Start typing..."
                        />
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('createArtefact')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" type="button" class="btn btn-primary" :disabled="isLoading || !title.trim() || !content.trim()">
                    <IconAnimateSpin v-if="isLoading" class="w-4 h-4 mr-2 animate-spin" />
                    {{ isLoading ? 'Create & Load' : 'Create & Load' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>
