<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useNotesStore } from '../../stores/notes';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const notesStore = useNotesStore();

const modalData = computed(() => uiStore.modalData('noteGroup'));
const group = ref(null);
const name = ref('');
const parentId = ref(null);
const isLoading = ref(false);

watch(modalData, (data) => {
  if (data) {
    group.value = data.group;
    name.value = data.group ? data.group.name : '';
    parentId.value = data.group ? data.group.parent_id : (data.parentGroup ? data.parentGroup.id : null);
  } else {
    group.value = null;
    name.value = '';
    parentId.value = null;
  }
}, { immediate: true });

const title = computed(() => group.value ? 'Edit Note Group' : 'New Note Group');
const isFormValid = computed(() => name.value.trim().length > 0);

const groupOptions = computed(() => {
     const flatten = (groups, prefix = '') => {
        let opts = [];
        for (const g of groups) {
            if (group.value && g.id === group.value.id) continue; // Don't allow parent to be self
            opts.push({ value: g.id, text: prefix + g.name });
            if (g.children && g.children.length > 0) {
                opts = opts.concat(flatten(g.children, prefix + '- '));
            }
        }
        return opts;
    };
    return [{ value: null, text: 'None (Top Level)' }, ...flatten(notesStore.notesTree.groups)];
});

async function handleSubmit() {
  if (!isFormValid.value || isLoading.value) return;
  
  isLoading.value = true;
  try {
    if (group.value) {
      await notesStore.updateGroup(group.value.id, name.value, parentId.value);
    } else {
      await notesStore.createGroup(name.value, parentId.value);
    }
    uiStore.closeModal('noteGroup');
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <GenericModal modalName="noteGroup" :title="title">
    <template #body>
      <form @submit.prevent="handleSubmit" id="note-group-form" class="space-y-4 p-6">
        <div>
          <label for="group-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Group Name</label>
          <input
            type="text"
            id="group-name"
            v-model="name"
            class="mt-1 input-field w-full"
            placeholder="e.g., Research"
            required
            autofocus
          />
        </div>
        <div>
            <label for="parent-group" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Parent Group</label>
            <select id="parent-group" v-model="parentId" class="mt-1 input-field w-full">
                <option v-for="option in groupOptions" :key="option.value" :value="option.value">{{ option.text }}</option>
            </select>
        </div>
      </form>
    </template>
    <template #footer>
      <div class="flex justify-end gap-2">
        <button type="button" @click="uiStore.closeModal('noteGroup')" class="btn btn-secondary">
          Cancel
        </button>
        <button type="submit" form="note-group-form" :disabled="!isFormValid || isLoading" class="btn btn-primary">
          {{ isLoading ? 'Saving...' : 'Save' }}
        </button>
      </div>
    </template>
  </GenericModal>
</template>
