<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('renameArtefact'));
const artefactTitle = computed(() => modalData.value?.artefactTitle);
const discussionId = computed(() => modalData.value?.discussionId || discussionsStore.currentDiscussionId);

const newTitle = ref('');
const titleInput = ref(null);
const isLoading = ref(false);

watch(() => uiStore.isModalOpen('renameArtefact'), (isOpen) => {
    if (isOpen && artefactTitle.value) {
        newTitle.value = artefactTitle.value;
        nextTick(() => {
            titleInput.value?.focus();
        });
    }
}, { immediate: true });

async function handleSubmit() {
    if (!newTitle.value.trim() || newTitle.value.trim() === artefactTitle.value) {
        uiStore.closeModal('renameArtefact');
        return;
    }

    isLoading.value = true;
    try {
        await discussionsStore.renameArtefact({
            discussionId: discussionId.value,
            artefactTitle: artefactTitle.value,
            newTitle: newTitle.value.trim()
        });
        uiStore.closeModal('renameArtefact');
    } catch (error) {
        // Handled globally
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modalName="renameArtefact"
        title="Rename Workspace Item"
        maxWidthClass="max-w-md"
    >
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-4">
                <p class="text-sm text-gray-500 dark:text-gray-400">
                    Update the title for <span class="font-bold text-gray-700 dark:text-gray-200">{{ artefactTitle }}</span>.
                </p>
                <div>
                    <label for="rename-input" class="label">New Title</label>
                    <input
                        id="rename-input"
                        ref="titleInput"
                        v-model="newTitle"
                        type="text"
                        class="input-field mt-1"
                        required
                        :disabled="isLoading"
                        placeholder="e.g. documentation.md"
                    />
                </div>
                <div class="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-[10px] text-blue-600 dark:text-blue-300">
                    💡 Renaming will also update any visual anchors referencing this item in your message history.
                </div>
            </form>
        </template>
        <template #footer>
            <div class="flex justify-end gap-3">
                <button @click="uiStore.closeModal('renameArtefact')" type="button" class="btn btn-secondary">Cancel</button>
                <button @click="handleSubmit" type="button" class="btn btn-primary" :disabled="isLoading || !newTitle.trim()">
                    {{ isLoading ? 'Processing...' : 'Apply Rename' }}
                </button>
            </div>
        </template>
    </GenericModal>
</template>