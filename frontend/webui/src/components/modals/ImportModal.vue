<script setup>
import { ref, watch, computed } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const importFile = ref(null);
const fileInputRef = ref(null);
const parsedDiscussions = ref([]);
const selectedIdsToImport = ref([]);
const isLoading = ref(false);

const isModalActive = computed(() => uiStore.isModalOpen('import'));

// Reset state when modal is opened
watch(isModalActive, (isActive) => {
    if (isActive) {
        resetState();
    }
});

const allSelected = computed({
    get: () => parsedDiscussions.value.length > 0 && selectedIdsToImport.value.length === parsedDiscussions.value.length,
    set: (value) => {
        selectedIdsToImport.value = value ? parsedDiscussions.value.map(d => d.discussion_id) : [];
    }
});

function resetState() {
    importFile.value = null;
    parsedDiscussions.value = [];
    selectedIdsToImport.value = [];
    if(fileInputRef.value) fileInputRef.value.value = '';
}

async function handleFileChange(event) {
    const file = event.target.files[0];
    if (!file) {
        resetState();
        return;
    }
    if (file.type !== 'application/json') {
        uiStore.addNotification('Invalid file type. Please select a JSON file.', 'error');
        resetState();
        return;
    }
    
    importFile.value = file;
    uiStore.addNotification('Reading file...', 'info');

    try {
        const content = await file.text();
        const data = JSON.parse(content);
        if (!data || !Array.isArray(data.discussions)) {
            throw new Error("Invalid import file format.");
        }
        parsedDiscussions.value = data.discussions;
        // Select all by default
        selectedIdsToImport.value = data.discussions.map(d => d.discussion_id); 
    } catch (error) {
        uiStore.addNotification(`Error reading file: ${error.message}`, 'error');
        resetState();
    }
}

async function handleImport() {
    if (!importFile.value || selectedIdsToImport.value.length === 0) {
        uiStore.addNotification('Please select a file and discussions to import.', 'warning');
        return;
    }

    isLoading.value = true;
    try {
        await discussionsStore.importDiscussions({
            file: importFile.value,
            discussionIdsToImport: selectedIdsToImport.value
        });
        uiStore.closeModal('import');
    } catch (error) {
        // Handled by store
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
  <GenericModal modalName="import" title="Import Discussions" maxWidthClass="max-w-lg">
    <template #body>
      <div class="space-y-4">
        <div>
          <label for="importFile" class="block text-sm font-medium mb-1">Select Exported JSON File (.json)</label>
          <input
            type="file"
            id="importFile"
            ref="fileInputRef"
            @change="handleFileChange"
            accept=".json"
            class="block w-full text-sm file:mr-4 file:py-1.5 file:px-3 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-100 dark:file:bg-blue-900/50 file:text-blue-700 dark:file:text-blue-300 hover:file:bg-blue-200 dark:hover:file:bg-blue-800/50 border border-gray-300 dark:border-gray-600 rounded-md cursor-pointer"
          />
        </div>
        <div v-if="parsedDiscussions.length > 0" class="space-y-2">
            <p class="text-sm text-gray-600 dark:text-gray-400">Select discussions to import from the file:</p>
            <div class="border dark:border-gray-600 rounded-md max-h-60 overflow-y-auto p-3 space-y-2">
                <div class="border-b dark:border-gray-600 pb-2 mb-2">
                    <label class="flex items-center text-sm font-medium cursor-pointer">
                        <input type="checkbox" v-model="allSelected" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 mr-2">
                        Select All / Deselect All
                    </label>
                </div>
                <label v-for="disc in parsedDiscussions" :key="disc.discussion_id" class="flex items-center text-sm cursor-pointer p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700">
                    <input type="checkbox" :value="disc.discussion_id" v-model="selectedIdsToImport" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 mr-2">
                    <span>{{ disc.title || 'Untitled Discussion' }}</span>
                </label>
            </div>
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="uiStore.closeModal('import')" class="btn btn-secondary">Cancel</button>
      <button @click="handleImport" class="btn btn-primary" :disabled="isLoading || selectedIdsToImport.length === 0">
        {{ isLoading ? 'Importing...' : 'Import Selected' }}
      </button>
    </template>
  </GenericModal>
</template>