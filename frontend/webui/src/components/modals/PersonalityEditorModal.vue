<script setup>
import { ref, watch, computed } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();

const modalData = computed(() => uiStore.modalData('personalityEditor'));

const form = ref({});
const isLoading = ref(false);
const iconPreview = ref(null);

const modalTitle = computed(() => form.value.id ? 'Edit Personality' : 'Create Personality');

// Watch for the modal to open and populate the form with data
watch(modalData, (newData) => {
  if (newData?.personality) {
    form.value = { ...newData.personality };
    iconPreview.value = newData.personality.icon_base64 || null;
  }
}, { immediate: true });


/**
 * Compresses and resizes an image file client-side.
 * @param {File} file The image file to process.
 * @param {number} maxSize The maximum width/height of the output image.
 * @returns {Promise<string>} A promise that resolves with the compressed Base64 data URL.
 */
function compressImage(file, maxSize = 96) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                let { width, height } = img;

                if (width > height) {
                    if (width > maxSize) {
                        height = Math.round(height * (maxSize / width));
                        width = maxSize;
                    }
                } else {
                    if (height > maxSize) {
                        width = Math.round(width * (maxSize / height));
                        height = maxSize;
                    }
                }

                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                // Try to get WebP format first, fallback to JPEG
                const dataUrl = canvas.toDataURL('image/webp', 0.8);
                if (dataUrl.length > 10) { // Simple check if webp is supported
                    resolve(dataUrl);
                } else {
                    resolve(canvas.toDataURL('image/jpeg', 0.85));
                }
            };
            img.onerror = reject;
            img.src = e.target.result;
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}


async function handleIconUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) { // Max 5MB raw upload
        uiStore.addNotification('Image file is too large (max 5MB).', 'error');
        return;
    }

    try {
        const compressedDataUrl = await compressImage(file);
        form.value.icon_base64 = compressedDataUrl;
        iconPreview.value = compressedDataUrl;
    } catch(error) {
        console.error("Image compression failed:", error);
        uiStore.addNotification('Failed to process image.', 'error');
    }
}

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
</script>

<template>
  <GenericModal modalName="personalityEditor" :title="modalTitle" maxWidthClass="max-w-4xl">
    <template #body>
      <form @submit.prevent="handleSave" class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium">Name*</label>
              <input type="text" v-model="form.name" required class="input-field mt-1" placeholder="e.g., Creative Writer">
            </div>
            <div>
              <label class="block text-sm font-medium">Category</label>
              <input type="text" v-model="form.category" class="input-field mt-1" placeholder="e.g., Writing, Coding, Fun">
            </div>
            <div>
                <label class="block text-sm font-medium">Author</label>
                <input type="text" v-model="form.author" class="input-field mt-1" placeholder="Your name or alias">
            </div>
            <div>
                <label class="block text-sm font-medium">Icon (Image, max 5MB)</label>
                <div class="flex items-center space-x-4">
                    <input type="file" @change="handleIconUpload" accept="image/png, image/jpeg, image/webp" class="input-field mt-1 file:mr-4 file:py-1 file:px-2 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-900/50 dark:file:text-blue-300 dark:hover:file:bg-blue-900">
                    <img v-if="iconPreview" :src="iconPreview" alt="Icon Preview" class="h-12 w-12 object-cover rounded-md border dark:border-gray-600 bg-gray-100 dark:bg-gray-700 flex-shrink-0"/>
                </div>
            </div>
        </div>
        <div>
          <label class="block text-sm font-medium">Description</label>
          <textarea v-model="form.description" rows="2" class="input-field mt-1" placeholder="Briefly describe this personality's purpose and style..."></textarea>
        </div>
        <div>
          <label class="block text-sm font-medium">Disclaimer</label>
          <textarea v-model="form.disclaimer" rows="2" class="input-field mt-1" placeholder="Any warnings or disclaimers for the user..."></textarea>
        </div>
        <div>
          <label class="block text-sm font-medium">System Prompt*</label>
          <textarea v-model="form.prompt_text" rows="8" required class="input-field mt-1 font-mono text-sm" placeholder="Enter the core instructions, role, and context for the AI..."></textarea>
        </div>
        <div>
          <label class="block text-sm font-medium">Script Code (Optional)</label>
          <textarea v-model="form.script_code" rows="6" class="input-field mt-1 font-mono text-sm" placeholder="Enter Python script for advanced logic..."></textarea>
        </div>
         <div>
            <label class="flex items-center">
                <input type="checkbox" v-model="form.is_public" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                <span class="ml-2 text-sm">Make this personality public for all users</span>
            </label>
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