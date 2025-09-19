<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const newTitle = ref('');
const titleInput = ref(null); // Ref for the input element

const modalData = computed(() => uiStore.modalData('renameDiscussion'));
const discussion = computed(() => {
    return modalData.value ? discussionsStore.discussions[modalData.value.discussionId] : null;
});

// Watch for the modal to become active and then set the title and focus
watch(discussion, (newDiscussion) => {
    if (newDiscussion) {
        newTitle.value = newDiscussion.title;
        // Wait for the DOM to update before trying to focus
        nextTick(() => {
            titleInput.value?.focus();
        });
    }
}, { immediate: true });

const handleRename = async () => {
    if (!discussion.value || !newTitle.value.trim()) return;
    await discussionsStore.renameDiscussion({
        discussionId: discussion.value.id,
        newTitle: newTitle.value,
    });
    uiStore.closeModal('renameDiscussion');
};
</script>

<template>
  <GenericModal
    v-if="discussion"
    modalName="renameDiscussion"
    :title="'Rename Discussion'"
    maxWidthClass="max-w-md"
  >
    <template #body>
      <form @submit.prevent="handleRename">
        <div>
          <label for="discussionTitleInput" class="block text-sm font-medium mb-1">
            New Title
          </label>
          <input
            ref="titleInput"
            v-model="newTitle"
            type="text"
            id="discussionTitleInput"
            class="input-field"
            placeholder="Enter new discussion title"
          />
        </div>
      </form>
    </template>
    <template #footer>
      <button @click="uiStore.closeModal('renameDiscussion')" class="btn btn-secondary">
        Cancel
      </button>
      <button @click="handleRename" class="btn btn-primary">
        Rename
      </button>
    </template>
  </GenericModal>
</template>