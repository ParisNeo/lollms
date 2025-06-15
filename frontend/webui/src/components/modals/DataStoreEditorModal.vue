<script setup>
import { ref, watch, computed } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();

const form = ref({
  id: null,
  name: '',
  description: ''
});
const isLoading = ref(false);

const modalData = computed(() => uiStore.modalData('dataStoreEditor'));
const isEditMode = computed(() => !!form.value.id);
const modalTitle = computed(() => isEditMode.value ? 'Edit Data Store' : 'Create New Data Store');

// Watch for the modal to open and populate the form
watch(modalData, (newData) => {
  if (newData) {
    form.value = {
      id: newData.id || null,
      name: newData.name || '',
      description: newData.description || ''
    };
  }
}, { immediate: true });

async function handleSubmit() {
  if (!form.value.name) {
    uiStore.addNotification('Data store name is required.', 'warning');
    return;
  }
  
  isLoading.value = true;
  try {
    if (isEditMode.value) {
      await dataStore.updateDataStore(form.value);
    } else {
      await dataStore.addDataStore({ name: form.value.name, description: form.value.description });
    }
    uiStore.closeModal('dataStoreEditor');
  } catch(error) {
    // Error notification is handled by the API interceptor or store action
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <GenericModal modalName="dataStoreEditor" :title="modalTitle" maxWidthClass="max-w-lg">
    <template #body>
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <div>
          <label for="storeName" class="block text-sm font-medium">Name</label>
          <input 
            v-model="form.name"
            type="text" 
            id="storeName" 
            required 
            minlength="3" 
            class="input-field mt-1"
            placeholder="e.g., Project Documents"
          >
        </div>
        <div>
          <label for="storeDescription" class="block text-sm font-medium">Description (Optional)</label>
          <textarea 
            v-model="form.description"
            rows="3"
            id="storeDescription" 
            class="input-field mt-1"
            placeholder="A brief summary of the store's contents"
          ></textarea>
        </div>
      </form>
    </template>
    <template #footer>
      <button @click="uiStore.closeModal('dataStoreEditor')" type="button" class="btn btn-secondary">
        Cancel
      </button>
      <button @click="handleSubmit" type="submit" class="btn btn-primary" :disabled="isLoading">
        {{ isLoading ? 'Saving...' : (isEditMode ? 'Save Changes' : 'Create Store') }}
      </button>
    </template>
  </GenericModal>
</template>
