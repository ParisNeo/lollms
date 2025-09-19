<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('moveDiscussion'));
const discussionId = computed(() => modalData.value?.discussionId);
const currentTitle = computed(() => modalData.value?.currentTitle);
const currentGroupId = computed(() => modalData.value?.currentGroupId);

const selectedGroupId = ref(null);
const isLoading = ref(false);

const allGroups = computed(() => discussionsStore.discussionGroups);

watch(modalData, (data) => {
  if (data) {
    selectedGroupId.value = data.currentGroupId || null;
  }
}, { immediate: true });

const title = computed(() => `Move "${currentTitle.value || 'Discussion'}"`);
const isFormValid = computed(() => selectedGroupId.value !== currentGroupId.value);

function getHierarchicalGroups(groups, parentId = null, indent = 0, visited = new Set()) {
    let result = [];
    const children = groups.filter(g => g.parent_id === parentId);

    for (const child of children) {
        if (visited.has(child.id)) {
            console.warn('Circular dependency detected in discussion groups, skipping:', child);
            continue;
        }
        visited.add(child.id);
        result.push({
            value: child.id,
            text: `${'—'.repeat(indent)} ${child.name}`
        });
        result = result.concat(getHierarchicalGroups(groups, child.id, indent + 1, visited));
        visited.delete(child.id); // Backtrack
    }
    return result;
}

const availableParentGroups = computed(() => {
    return [
        { value: null, text: 'None (Ungrouped)' },
        ...getHierarchicalGroups(allGroups.value)
    ];
});

async function handleSubmit() {
  if (!isFormValid.value || isLoading.value) return;
  
  isLoading.value = true;
  try {
    await discussionsStore.moveDiscussionToGroup(discussionId.value, selectedGroupId.value);
    uiStore.closeModal('moveDiscussion');
  } catch (error) {
    // Error is handled globally
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <GenericModal modalName="moveDiscussion" :title="title">
    <template #body>
      <form @submit.prevent="handleSubmit" id="move-discussion-form" class="space-y-4 p-6">
        <div>
          <label for="target-group" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Select a group to move this discussion to:
          </label>
          <select id="target-group" v-model="selectedGroupId" class="mt-1 input-field w-full">
              <option v-for="option in availableParentGroups" :key="option.value" :value="option.value">{{ option.text }}</option>
          </select>
        </div>
      </form>
    </template>
    <template #footer>
      <div class="flex justify-end gap-2">
        <button type="button" @click="uiStore.closeModal('moveDiscussion')" class="btn btn-secondary">
          Cancel
        </button>
        <button type="submit" form="move-discussion-form" :disabled="!isFormValid || isLoading" class="btn btn-primary">
          {{ isLoading ? 'Moving...' : 'Move' }}
        </button>
      </div>
    </template>
  </GenericModal>
</template>