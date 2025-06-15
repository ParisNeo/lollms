<script setup>
import { ref, watch, computed } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();

const props = defineProps({
  personality: {
    type: Object,
    default: null
  }
});

const form = ref({});
const isLoading = ref(false);
const iconPreview = ref(null);

const modalTitle = computed(() => props.personality?.id ? 'Edit Personality' : 'Create Personality');

// Watch for the personality prop to change and reset the form
watch(() => props.personality, (newVal) => {
  if (newVal) {
    form.value = { ...newVal };
    iconPreview.value = newVal.icon_base64 || null;
  } else {
    // Reset for creating a new one
    form.value = { name: '', category: '', description: '', prompt_text: '', is_public: false, icon_base64: null };
    iconPreview.value = null;
  }
}, { immediate: true, deep: true });

async function handleSave() {
  if (!form.value.name || !form.value.prompt_text) {
    uiStore.addNotification('Name and System Prompt are required.', 'error');
    return;
  }
  
  isLoading.value = true;
  const action = form.value.id ? dataStore.updatePersonality : dataStore.addPersonality;
  
  try {
    await action(form.value);
    uiStore.closeModal('personalityEditor');
  } catch (error) {
    // Error is handled by interceptor, don't close modal on failure
  } finally {
    isLoading.value = false;
  }
}

function handleIconUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  if (file.size > 256 * 1024) { // Max 256KB
    uiStore.addNotification('Icon image is too large (max 256KB).', 'error');
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    form.value.icon_base64 = e.target.result;
    iconPreview.value = e.target.result;
  };
  reader.readAsDataURL(file);
}
</script>

<template>
  <GenericModal modalName="personalityEditor" :title="modalTitle" maxWidthClass="max-w-2xl">
    <template #body>
      <form @submit.prevent="handleSave" class="space-y-4">
        <div>
          <label class="block text-sm font-medium">Name*</label>
          <input type="text" v-model="form.name" required class="input-field mt-1" placeholder="e.g., Creative Writer">
        </div>
        <div>
          <label class="block text-sm font-medium">Category</label>
          <input type="text" v-model="form.category" class="input-field mt-1" placeholder="e.g., Writing, Coding, Fun">
        </div>
        <div>
          <label class="block text-sm font-medium">Icon (Image)</label>
          <input type="file" @change="handleIconUpload" accept="image/png, image/jpeg, image/webp, image/gif" class="input-field mt-1 file:mr-4 file:py-1 file:px-2 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-900/50 dark:file:text-blue-300 dark:hover:file:bg-blue-900">
          <img v-if="iconPreview" :src="iconPreview" alt="Icon Preview" class="mt-2 h-20 w-20 object-cover rounded-md border dark:border-gray-600 bg-gray-100 dark:bg-gray-700"/>
        </div>
        <div>
          <label class="block text-sm font-medium">Description</label>
          <textarea v-model="form.description" rows="3" class="input-field mt-1" placeholder="Briefly describe this personality's purpose and style..."></textarea>
        </div>
        <div>
          <label class="block text-sm font-medium">System Prompt*</label>
          <textarea v-model="form.prompt_text" rows="8" required class="input-field mt-1 font-mono text-sm" placeholder="Enter the core instructions, role, and context for the AI..."></textarea>
        </div>
      </form>
    </template>
    <template #footer>
      <button @click="uiStore.closeModal('personalityEditor')" class="btn btn-secondary">Cancel</button>
      <button @click="handleSave" class="btn btn-primary" :disabled="isLoading">
        {{ isLoading ? 'Saving...' : 'Save Personality' }}
      </button>
    </template>
  </GenericModal>
</template>