<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('discussionGroup'));
const group = ref(null);
const parentGroup = ref(null);
const name = ref('');
const parentId = ref(null);
const isLoading = ref(false);

const allGroups = computed(() => discussionsStore.discussionGroups);

watch(modalData, (data) => {
  if (data) {
    group.value = data.group;
    parentGroup.value = data.parentGroup;
    name.value = data.group ? data.group.name : '';
    parentId.value = data.group ? data.group.parent_id : (data.parentGroup ? data.parentGroup.id : null);
  } else {
    group.value = null;
    parentGroup.value = null;
    name.value = '';
    parentId.value = null;
  }
}, { immediate: true });

const title = computed(() => group.value ? 'Edit Discussion Group' : 'New Discussion Group');
const isFormValid = computed(() => name.value.trim().length > 0);

function getHierarchicalGroups(groups, parentId = null, indent = 0) {
    let result = [];
    const children = groups.filter(g => g.parent_id === parentId);
    for (const child of children) {
        if (group.value && child.id === group.value.id) continue;
        result.push({
            value: child.id,
            text: `${'—'.repeat(indent)} ${child.name}`
        });
        result = result.concat(getHierarchicalGroups(groups, child.id, indent + 1));
    }
    return result;
}

const availableParentGroups = computed(() => {
    return [
        { value: null, text: 'None (Top Level)' },
        ...getHierarchicalGroups(allGroups.value)
    ];
});

async function handleSubmit() {
  if (!isFormValid.value || isLoading.value) return;
  
  isLoading.value = true;
  try {
    if (group.value) {
      await discussionsStore.updateGroup(group.value.id, name.value, parentId.value);
    } else {
      await discussionsStore.createGroup(name.value, parentId.value);
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
    <template #body>
      <form @submit.prevent="handleSubmit" id="discussion-group-form" class="space-y-4 p-6">
        <div>
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
        <div>
            <label for="parent-group" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Parent Group</label>
            <select id="parent-group" v-model="parentId" class="mt-1 input-field w-full">
                <option v-for="option in availableParentGroups" :key="option.value" :value="option.value">{{ option.text }}</option>
            </select>
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