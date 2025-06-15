<script setup>
import { ref, computed, watch } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth'; // Import auth store
import GenericModal from '../ui/GenericModal.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore(); // Get instance of auth store

// Component State
const filesToUpload = ref(null);
const selectedVectorizer = ref('');
const isUploading = ref(false);
const isFetchingFiles = ref(false);
const storeFiles = ref([]);
const availableVectorizers = ref([]);

// Modal Data
const modalData = computed(() => uiStore.modalData('fileManagement'));
const store = computed(() => modalData.value?.store);
const modalTitle = computed(() => `Manage Files: ${store.value?.name || ''}`);

const isUploadDisabled = computed(() => {
  return isUploading.value || !selectedVectorizer.value || !filesToUpload.value || filesToUpload.value.length === 0;
});

// Fetch data when modal opens
watch(store, async (newStore) => {
  if (newStore?.id) {
    storeFiles.value = [];
    availableVectorizers.value = [];
    selectedVectorizer.value = '';
    filesToUpload.value = null;

    // Fetch files and vectorizers in parallel
    isFetchingFiles.value = true;
    try {
        const [files, vectorizers] = await Promise.all([
            dataStore.fetchStoreFiles(newStore.id),
            dataStore.fetchStoreVectorizers(newStore.id)
        ]);
        storeFiles.value = files;
        availableVectorizers.value = vectorizers;

        // --- MODIFICATION ---
        // Pre-select the user's default vectorizer if it's available in this store
        const userDefaultVectorizer = authStore.user?.safe_store_vectorizer;
        if (userDefaultVectorizer && vectorizers.some(v => v.name === userDefaultVectorizer)) {
            selectedVectorizer.value = userDefaultVectorizer;
        }
        // --- END MODIFICATION ---

    } catch(e) {
        // Handled by store/interceptor
    } finally {
        isFetchingFiles.value = false;
    }
  }
}, { immediate: true });

function handleFileSelection(event) {
  filesToUpload.value = event.target.files;
}

async function handleUpload() {
  if (isUploadDisabled.value || !store.value?.id) return;
  
  isUploading.value = true;
  const formData = new FormData();
  for (const file of filesToUpload.value) {
    formData.append('files', file);
  }
  formData.append('vectorizer_name', selectedVectorizer.value);

  try {
    await dataStore.uploadFilesToStore({ storeId: store.value.id, formData });
    // Refresh file list on success
    const updatedFiles = await dataStore.fetchStoreFiles(store.value.id);
    storeFiles.value = updatedFiles;
    filesToUpload.value = null; // Clear file input
    document.getElementById('fileUploadInput').value = ''; // Reset input element
  } catch(error) {
    // Handled
  } finally {
    isUploading.value = false;
  }
}

async function handleDeleteFile(filename) {
    if (!store.value?.id) return;

    const confirmed = await uiStore.showConfirmation({
        title: `Delete ${filename}?`,
        message: 'This will remove the document from the data store. This action cannot be undone.',
        confirmText: 'Delete File'
    });

    if (confirmed) {
        try {
            await dataStore.deleteFileFromStore({ storeId: store.value.id, filename });
            storeFiles.value = storeFiles.value.filter(f => f.filename !== filename);
        } catch(e) {
            // Handled
        }
    }
}
</script>

<template>
  <GenericModal v-if="store" :modalName="'fileManagement'" :title="modalTitle" maxWidthClass="max-w-3xl">
    <template #body>
      <div class="space-y-6">
        <!-- Upload New Documents Section -->
        <section class="border dark:border-gray-700 rounded-md p-4">
          <h4 class="text-md font-medium mb-3">Upload New Documents</h4>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label for="fileVectorizerSelect" class="block text-sm font-medium mb-1">Vectorizer for Upload</label>
              <select v-model="selectedVectorizer" id="fileVectorizerSelect" class="input-field">
                <option value="" disabled>Select Vectorizer</option>
                <option v-for="v in availableVectorizers" :key="v.name" :value="v.name">{{ v.name }}</option>
              </select>
            </div>
            <div>
              <label for="fileUploadInput" class="block text-sm font-medium mb-1">Select Files</label>
              <input 
                type="file" 
                id="fileUploadInput" 
                @change="handleFileSelection" 
                multiple 
                class="block w-full text-sm file:mr-4 file:py-1.5 file:px-3 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-100 dark:file:bg-blue-900/50 file:text-blue-700 dark:file:text-blue-300 hover:file:bg-blue-200 dark:hover:file:bg-blue-800/50 border border-gray-300 dark:border-gray-600 rounded-md cursor-pointer"
              />
            </div>
          </div>
          <div class="text-right mt-3">
            <button @click="handleUpload" class="btn btn-primary" :disabled="isUploadDisabled">
              <span v-if="isUploading">Uploading...</span>
              <span v-else>Upload Files</span>
            </button>
          </div>
        </section>

        <!-- Indexed Documents Section -->
        <section class="border dark:border-gray-700 rounded-md p-4">
          <h4 class="text-md font-medium mb-3">Indexed Documents</h4>
          <div class="max-h-60 overflow-y-auto space-y-2 border dark:border-gray-600 rounded p-3">
            <div v-if="isFetchingFiles" class="text-sm italic text-gray-500">Loading files...</div>
            <div v-else-if="storeFiles.length === 0" class="text-sm italic text-gray-500">No documents indexed in this store.</div>
            <div v-else v-for="file in storeFiles" :key="file.filename" class="flex justify-between items-center py-1 px-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
              <span class="truncate text-sm" :title="file.filename">{{ file.filename }}</span>
              <button @click="handleDeleteFile(file.filename)" title="Delete File" class="flex-shrink-0 text-red-500 hover:text-red-700 p-1 rounded-full hover:bg-red-100 dark:hover:bg-red-900/50 ml-2">
                 <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              </button>
            </div>
          </div>
        </section>
      </div>
    </template>
    <template #footer>
      <button @click="uiStore.closeModal('fileManagement')" class="btn btn-secondary">Close</button>
    </template>
  </GenericModal>
</template>