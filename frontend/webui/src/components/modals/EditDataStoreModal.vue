<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const dataStore = useDataStore();

const storeToEdit = computed(() => uiStore.modalData('editDataStore')?.store);

const form = ref({
    id: '',
    name: '',
    description: ''
});

const isLoading = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

watch(storeToEdit, (newStore) => {
    if (newStore) {
        form.value = {
            id: newStore.id,
            name: newStore.name,
            description: newStore.description || ''
        };
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
    }
}, { immediate: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== pristineState;
}, { deep: true });

async function handleSubmit() {
    if (!form.value.name.trim()) {
        uiStore.addNotification('Data Store name cannot be empty.', 'warning');
        return;
    }
    isLoading.value = true;
    try {
        await dataStore.updateDataStore(form.value);
        handleClose();
    } catch (error) {
        // Error is handled in the store
    } finally {
        isLoading.value = false;
    }
}

function handleClose() {
    uiStore.closeModal('editDataStore');
}
</script>

<template>
  <GenericModal
    modalName="editDataStore"
    :title="`Edit Data Store`"
    :allow-overlay-close="!isLoading"
  >
    <template #body>
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label for="ds-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Name
          </label>
          <input
            id="ds-name"
            v-model="form.name"
            type="text"
            required
            class="input-field mt-1"
            placeholder="e.g., Project Documentation"
          />
        </div>
        <div>
          <label for="ds-description" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Description
          </label>
          <textarea
            id="ds-description"
            v-model="form.description"
            rows="3"
            class="input-field mt-1"
            placeholder="A brief description of the data store's content."
          ></textarea>
        </div>
      </form>
    </template>
    
    <template #footer>
      <button type="button" @click="handleClose" :disabled="isLoading" class="btn btn-secondary">
        Cancel
      </button>
      <button
        type="button"
        @click="handleSubmit"
        :disabled="isLoading || !hasChanges"
        class="btn btn-primary"
      >
        {{ isLoading ? 'Saving...' : 'Save Changes' }}
      </button>
    </template>
  </GenericModal>
</template>