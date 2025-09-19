<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import GenericModal from './GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const props = computed(() => uiStore.modalData('memoryEditor') || {});
const discussionId = computed(() => props.value.discussionId);
const memory = computed(() => props.value.memory);

const isEditing = computed(() => !!memory.value?.title);
const title = ref('');
const content = ref('');
const isLoading = ref(false);

watch(
    () => uiStore.isModalOpen('memoryEditor'),
    (isOpen) => {
        if (isOpen) {
            title.value = memory.value?.title || '';
            content.value = memory.value?.content || '';
        }
    },
    { immediate: true }
);

async function handleSubmit() {
    if (!title.value.trim() || !discussionId.value) return;

    isLoading.value = true;
    try {
        await discussionsStore.createOrUpdateMemory({
            discussionId: discussionId.value,
            title: title.value,
            content: content.value,
        });
        uiStore.closeModal('memoryEditor');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modal-name="memoryEditor"
        :title="isEditing ? 'Edit Memory' : 'Create New Memory'"
        @close="uiStore.closeModal('memoryEditor')"
        max-width-class="max-w-3xl"
    >
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-4">
                <div>
                    <label for="memory-title" class="label">Title</label>
                    <input
                        id="memory-title"
                        type="text"
                        v-model="title"
                        class="input-field"
                        :disabled="isEditing"
                        required
                    />
                </div>
                <div>
                    <label for="memory-content" class="label">Content</label>
                    <CodeMirrorEditor v-model="content" class="h-64" />
                </div>
            </form>
        </template>
        <template #footer>
            <button
                type="button"
                @click="uiStore.closeModal('memoryEditor')"
                class="btn btn-secondary"
            >
                Cancel
            </button>
            <button
                type="button"
                @click="handleSubmit"
                class="btn btn-primary"
                :disabled="isLoading"
            >
                {{ isLoading ? 'Saving...' : 'Save Memory' }}
            </button>
        </template>
    </GenericModal>
</template>