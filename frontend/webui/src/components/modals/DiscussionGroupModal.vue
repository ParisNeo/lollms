<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from '../ui/GenericModal.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('discussionGroup'));
const group = ref(null);
const name = ref('');
const isLoading = ref(false);

watch(modalData, (data) => {
  if (data) {
    group.value = data.group;
    name.value = data.group ? data.group.name : '';
  } else {
    group.value = null;
    name.value = '';
  }
}, { immediate: true });

const title = computed(() => group.value ? 'Edit Discussion Group' : 'New Discussion Group');
const isFormValid = computed(() => name.value.trim().length > 0);

async function handleSubmit() {
  if (!isFormValid.value || isLoading.value) return;
  
  isLoading.value = true;
  try {
    if (group.value) {
      await discussionsStore.updateGroup(group.value.id, name.value);
    } else {
      await discussionsStore.createGroup(name.value);
    }
    uiStore.closeModal('discussionGroup');
  } catch (error) {
    // Error is handled globally
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <GenericModal modalName="discussionGroup" :title="title">
    <template #content>
      <form @submit.prevent="handleSubmit" id="discussion-group-form">
        <div class="p-6">
          <label for="group-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Group Name</label>
          <input
            type="text"
            id="group-name"
            v-model="name"
            class="mt-1 input-field w-full"
            placeholder="e.g., Work Projects"
            required
            autofocus
          />
        </div>
      </form>
    </template>
    <template #footer>
      <div class="flex justify-end gap-2">
        <button type="button" @click="uiStore.closeModal('discussionGroup')" class="btn btn-secondary">
          Cancel
        </button>
        <button type="submit" form="discussion-group-form" :disabled="!isFormValid || isLoading" class="btn btn-primary">
          {{ isLoading ? 'Saving...' : 'Save' }}
        </button>
      </div>
    </template>
  </GenericModal>
</template>