<script setup>
import { ref } from 'vue';
import GenericModal from './GenericModal.vue';
import { useUiStore } from '../../stores/ui';

const uiStore = useUiStore();
const emit = defineEmits(['insert']);
const MODAL_NAME = 'insertImage';

const activeTab = ref('url'); // url, svg, upload
const imageUrl = ref('');
const svgCode = ref('');
const fileInput = ref(null);
const isLoading = ref(false);

function resetState() {
    activeTab.value = 'url';
    imageUrl.value = '';
    svgCode.value = '';
    if (fileInput.value) {
        fileInput.value.value = '';
    }
    isLoading.value = false;
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        uiStore.addNotification('Please select a valid image file.', 'error');
        return;
    }

    isLoading.value = true;
    const reader = new FileReader();
    reader.onload = (e) => {
        emit('insert', e.target.result);
        uiStore.closeModal(MODAL_NAME);
        resetState();
    };
    reader.onerror = () => {
        uiStore.addNotification('Failed to read the file.', 'error');
        isLoading.value = false;
    };
    reader.readAsDataURL(file);
}

function handleInsert() {
    if (activeTab.value === 'url') {
        if (!imageUrl.value) {
            uiStore.addNotification('Please enter an image URL.', 'warning');
            return;
        }
        emit('insert', imageUrl.value);
    } else if (activeTab.value === 'svg') {
        if (!svgCode.value.trim().startsWith('<svg') || !svgCode.value.trim().endsWith('</svg>')) {
            uiStore.addNotification('Please enter valid SVG code.', 'warning');
            return;
        }
        const dataUri = `data:image/svg+xml;base64,${btoa(svgCode.value)}`;
        emit('insert', dataUri);
    }
    uiStore.closeModal(MODAL_NAME);
    resetState();
}
</script>

<template>
  <GenericModal
    :modal-name="MODAL_NAME"
    title="Insert Image"
    @close="() => { uiStore.closeModal(MODAL_NAME); resetState(); }"
  >
    <template #body>
      <div class="space-y-4">
        <div class="border-b border-gray-200 dark:border-gray-700">
          <nav class="-mb-px flex space-x-4" aria-label="Tabs">
            <button @click="activeTab = 'url'" :class="['tab-btn', { 'active': activeTab === 'url' }]">From URL</button>
            <button @click="activeTab = 'svg'" :class="['tab-btn', { 'active': activeTab === 'svg' }]">From SVG Code</button>
            <button @click="activeTab = 'upload'" :class="['tab-btn', { 'active': activeTab === 'upload' }]">Upload</button>
          </nav>
        </div>

        <div v-if="activeTab === 'url'">
          <label for="imageUrl" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Image URL</label>
          <input
            v-model="imageUrl"
            type="url"
            id="imageUrl"
            class="input-field mt-1"
            placeholder="https://example.com/image.png"
          />
        </div>

        <div v-if="activeTab === 'svg'">
          <label for="svgCode" class="block text-sm font-medium text-gray-700 dark:text-gray-300">SVG Code</label>
          <textarea
            v-model="svgCode"
            id="svgCode"
            rows="6"
            class="input-field font-mono mt-1"
            placeholder="<svg>...</svg>"
          ></textarea>
        </div>

        <div v-if="activeTab === 'upload'">
          <label for="file-upload" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Upload Image</label>
          <div class="mt-1 flex justify-center rounded-md border-2 border-dashed border-gray-300 dark:border-gray-600 px-6 pt-5 pb-6">
            <div class="space-y-1 text-center">
              <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48" aria-hidden="true">
                <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              <div class="flex text-sm text-gray-600 dark:text-gray-400">
                <label for="file-upload-input" class="relative cursor-pointer rounded-md bg-white dark:bg-gray-800 font-medium text-blue-600 dark:text-blue-400 hover:text-blue-500">
                  <span>Upload a file</span>
                  <input id="file-upload-input" ref="fileInput" @change="handleFileSelect" type="file" class="sr-only" accept="image/*" />
                </label>
                <p class="pl-1">or drag and drop</p>
              </div>
              <p class="text-xs text-gray-500">PNG, JPG, GIF, SVG up to 2MB</p>
            </div>
          </div>
        </div>
      </div>
    </template>
    <template #footer>
      <div class="flex justify-end space-x-3">
        <button @click="() => { uiStore.closeModal(MODAL_NAME); resetState(); }" type="button" class="btn btn-secondary">Cancel</button>
        <button v-if="activeTab !== 'upload'" @click="handleInsert" type="button" class="btn btn-primary">Insert Image</button>
      </div>
    </template>
  </GenericModal>
</template>

<style scoped>
.tab-btn {
    @apply px-3 py-2 text-sm font-medium border-b-2;
}
.tab-btn.active {
    @apply border-blue-500 text-blue-600 dark:text-blue-400;
}
.tab-btn:not(.active) {
    @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-500;
}
</style>