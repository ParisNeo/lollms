<script setup>
import { ref, computed, watch } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();

const targetUsername = ref('');
const isLoading = ref(false);

const modalData = computed(() => uiStore.modalData('shareDataStore'));
const store = computed(() => modalData.value?.store);
const modalTitle = computed(() => `Share "${store.value?.name || 'Data Store'}"`);

// Clear username when modal opens
watch(modalData, (newData) => {
  if (newData) {
    targetUsername.value = '';
  }
});

async function handleShare() {
  if (!targetUsername.value.trim() || !store.value?.id) {
    uiStore.addNotification('Username is required.', 'warning');
    return;
  }

  isLoading.value = true;
  try {
    await dataStore.shareDataStore({
      storeId: store.value.id,
      username: targetUsername.value.trim()
    });
    uiStore.closeModal('shareDataStore');
  } catch(error) {
    // Handled by interceptor
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <GenericModal v-if="store" :modalName="'shareDataStore'" :title="modalTitle" maxWidthClass="max-w-md">
    <template #body>
      <form @submit.prevent="handleShare" class="space-y-4">
        <div>
          <label for="shareUsername" class="block text-sm font-medium">Share with Username</label>
          <input 
            v-model="targetUsername"
            type="text" 
            id="shareUsername"
            required 
            class="input-field mt-1"
            placeholder="Enter friend's username"
          >
        </div>
        <p class="text-xs text-gray-500">The user will be granted read and query access to this data store.</p>
      </form>
    </template>
    <template #footer>
      <button @click="uiStore.closeModal('shareDataStore')" type="button" class="btn btn-secondary">
        Cancel
      </button>
      <button @click="handleShare" class="btn btn-primary" :disabled="isLoading">
        {{ isLoading ? 'Sharing...' : 'Share' }}
      </button>
    </template>
  </GenericModal>
</template>