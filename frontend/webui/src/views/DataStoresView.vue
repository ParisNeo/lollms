<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';

// Import Icon Components
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconShare from '../assets/icons/IconShare.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconDatabase from '../assets/icons/IconDatabase.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

// CORRECTED: Use storeToRefs to correctly get reactive state
const { ownedDataStores, sharedDataStores } = storeToRefs(dataStore);
const isLoadingStores = ref(false);

// --- Form State ---
const isFormVisible = ref(false);
const isEditMode = ref(false);
const form = ref({ id: null, name: '', description: '' });
const isLoadingForm = ref(false);

// --- File Management State ---
const selectedStore = ref(null);
const storeFiles = ref([]);
const storeVectorizers = ref([]);
const selectedVectorizer = ref('');
const isFetchingFiles = ref(false);
const isUploading = ref(false);
const filesToUpload = ref([]);
const isDragging = ref(false);

onMounted(async () => {
    isLoadingStores.value = true;
    await dataStore.fetchDataStores();
    isLoadingStores.value = false;
});

watch(selectedStore, (newStore) => {
    if (!newStore) {
        storeFiles.value = [];
        storeVectorizers.value = [];
        selectedVectorizer.value = '';
    }
});

function showCreateForm() {
    isEditMode.value = false;
    form.value = { id: null, name: '', description: '' };
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showEditForm(store) {
    isEditMode.value = true;
    form.value = { ...store };
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function hideForm() {
    isFormVisible.value = false;
}

async function handleSubmit() {
    isLoadingForm.value = true;
    try {
        if (isEditMode.value) {
            await dataStore.updateDataStore(form.value);
        } else {
            await dataStore.addDataStore(form.value);
        }
        hideForm();
    } catch (error) {
        // Error notification is handled by the store/api interceptor
    } finally {
        isLoadingForm.value = false;
    }
}

async function handleDeleteStore(store) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete '${store.name}'?`,
        message: 'Are you sure? This will permanently delete the data store and all its files.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        if (selectedStore.value?.id === store.id) {
            selectedStore.value = null;
        }
        await dataStore.deleteDataStore(store.id);
    }
}

async function handleManage(store) {
    selectedStore.value = store;
    isFetchingFiles.value = true;
    try {
        const [files, vectorizers] = await Promise.all([
            dataStore.fetchStoreFiles(store.id),
            dataStore.fetchStoreVectorizers(store.id)
        ]);
        storeFiles.value = files;
        storeVectorizers.value = vectorizers;
        if (vectorizers.length > 0) {
            selectedVectorizer.value = vectorizers[0].name;
        }
    } catch (error) {
        uiStore.addNotification('Could not load store details.', 'error');
        selectedStore.value = null;
    } finally {
        isFetchingFiles.value = false;
    }
}

function closeFileManagement() {
    selectedStore.value = null;
}

function handleFileDrop(event) {
    isDragging.value = false;
    filesToUpload.value = [...filesToUpload.value, ...Array.from(event.dataTransfer.files)];
}

function handleFileSelect(event) {
    filesToUpload.value = [...filesToUpload.value, ...Array.from(event.target.files)];
    event.target.value = ''; // Reset input
}

function removeFileToUpload(index) {
    filesToUpload.value.splice(index, 1);
}

async function handleUpload() {
    if (filesToUpload.value.length === 0 || !selectedVectorizer.value) {
        uiStore.addNotification('Please select files and a vectorizer.', 'warning');
        return;
    }
    isUploading.value = true;
    const formData = new FormData();
    filesToUpload.value.forEach(file => formData.append('files', file));
    formData.append('vectorizer_name', selectedVectorizer.value);

    try {
        await dataStore.uploadFilesToStore({ storeId: selectedStore.value.id, formData });
        filesToUpload.value = [];
        await handleManage(selectedStore.value); // Refresh file list
    } finally {
        isUploading.value = false;
    }
}

async function handleDeleteFile(filename) {
     const confirmed = await uiStore.showConfirmation({
        title: `Delete File?`,
        message: `Are you sure you want to delete '${filename}'? This cannot be undone.`,
        confirmText: 'Delete'
    });
    if(confirmed) {
        try {
            await dataStore.deleteFileFromStore({ storeId: selectedStore.value.id, filename });
            storeFiles.value = storeFiles.value.filter(f => f.filename !== filename);
        } catch(error) {
            // error handled by store
        }
    }
}

function handleShare(store) {
    // Placeholder for Phase 5
    console.log("Sharing store:", store.name);
}
</script>

<template>
  <div class="flex h-screen bg-gray-100 dark:bg-gray-900">
    <!-- Master List Panel -->
    <div class="flex-shrink-0 flex flex-col h-full transition-all duration-300 ease-in-out" :class="selectedStore ? 'w-full md:w-1/2 lg:w-1/3' : 'w-full'">
      <header class="bg-white dark:bg-gray-800 border-b dark:border-gray-700 p-4 flex items-center justify-between shadow-sm flex-shrink-0">
        <div class="flex items-center space-x-3">
          <IconDatabase class="h-6 w-6 text-gray-500 dark:text-gray-400" />
          <h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">RAG Data Stores</h1>
        </div>
        <div class="flex items-center space-x-2">
            <button v-if="!isFormVisible" @click="showCreateForm" class="btn btn-primary"><IconPlus class="w-5 h-5 mr-1" /><span>New</span></button>
            <router-link to="/" class="btn-icon" title="Back to App"><IconArrowLeft class="w-5 h-5" /></router-link>
        </div>
      </header>

      <main class="flex-grow overflow-y-auto p-6 space-y-8">
        <!-- Create/Edit Form -->
        <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md border dark:border-gray-700">
            <h2 class="text-lg font-semibold mb-4">{{ isEditMode ? 'Edit Data Store' : 'Create New Data Store' }}</h2>
            <form @submit.prevent="handleSubmit" class="space-y-4">
                <div><label for="storeName" class="block text-sm font-medium">Name</label><input type="text" id="storeName" v-model="form.name" required class="input-field mt-1" placeholder="e.g., Project Documents"></div>
                <div><label for="storeDescription" class="block text-sm font-medium">Description</label><textarea id="storeDescription" v-model="form.description" rows="3" class="input-field mt-1" placeholder="A brief description..."></textarea></div>
                <div class="flex justify-end space-x-3"><button type="button" @click="hideForm" class="btn btn-secondary">Cancel</button><button type="submit" class="btn btn-primary" :disabled="isLoadingForm">{{ isLoadingForm ? 'Saving...' : (isEditMode ? 'Save' : 'Create') }}</button></div>
            </form>
        </div>
        <!-- Owned Stores -->
        <section>
            <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">Your Data Stores</h2>
            <div v-if="isLoadingStores" class="grid grid-cols-1 md:grid-cols-2 gap-4"><div v-for="i in 2" :key="i" class="h-40 bg-gray-200 dark:bg-gray-700/50 rounded-lg animate-pulse"></div></div>
            <div v-else-if="ownedDataStores.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div v-for="store in ownedDataStores" :key="store.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow flex flex-col">
                    <h3 class="font-bold text-gray-900 dark:text-white truncate" :title="store.name">{{ store.name }}</h3>
                    <p class="text-sm text-gray-500 dark:text-gray-400 mt-1 flex-grow line-clamp-2">{{ store.description || 'No description.' }}</p>
                    <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-end space-x-2">
                        <button @click="handleManage(store)" class="btn btn-secondary btn-sm">Manage</button>
                        <button @click="showEditForm(store)" class="btn-icon" title="Edit"><IconPencil class="h-5 w-5" /></button>
                        <button @click="handleShare(store)" class="btn-icon" title="Share"><IconShare class="h-5 w-5" /></button>
                        <button @click="handleDeleteStore(store)" class="btn-icon-danger" title="Delete"><IconTrash class="h-5 w-5" /></button>
                    </div>
                </div>
            </div>
            <div v-else class="text-center py-8 bg-gray-50 dark:bg-gray-800/50 rounded-lg"><p class="text-gray-500 dark:text-gray-400">You haven't created any data stores yet.</p><button @click="showCreateForm" class="mt-2 text-blue-600 dark:text-blue-400 hover:underline text-sm font-medium">Create your first one</button></div>
        </section>
        <!-- Shared Stores -->
        <section>
            <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">Shared With You</h2>
            <div v-if="isLoadingStores" class="grid grid-cols-1 md:grid-cols-2 gap-4"><div class="h-40 bg-gray-200 dark:bg-gray-700/50 rounded-lg animate-pulse"></div></div>
            <div v-else-if="sharedDataStores.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div v-for="store in sharedDataStores" :key="store.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow flex flex-col">
                    <h3 class="font-bold text-gray-900 dark:text-white truncate" :title="store.name">{{ store.name }}</h3><p class="text-xs text-gray-400 dark:text-gray-500">from {{ store.owner_username }}</p>
                    <p class="text-sm text-gray-500 dark:text-gray-400 mt-2 flex-grow line-clamp-2">{{ store.description || 'No description.' }}</p>
                    <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 flex justify-end space-x-2"><button @click="handleManage(store)" class="btn btn-secondary btn-sm">Manage</button></div>
                </div>
            </div>
            <div v-else class="text-center py-8 bg-gray-50 dark:bg-gray-800/50 rounded-lg"><p class="text-gray-500 dark:text-gray-400">No data stores have been shared with you.</p></div>
        </section>
      </main>
    </div>
    <!-- Detail Panel -->
    <div class="flex-shrink-0 flex flex-col h-full bg-white dark:bg-gray-800 border-l dark:border-gray-700 transition-all duration-300 ease-in-out" :class="selectedStore ? 'w-full md:w-1/2 lg:w-2/3' : 'w-0 hidden'">
        <div v-if="selectedStore" class="flex flex-col h-full">
            <header class="p-4 border-b dark:border-gray-700 flex-shrink-0 flex items-center justify-between">
                <div><h2 class="text-lg font-semibold truncate" :title="selectedStore.name">{{ selectedStore.name }}</h2><p class="text-sm text-gray-500">File Management</p></div>
                <button @click="closeFileManagement" class="btn-icon" title="Close"><IconXMark class="w-6 h-6"/></button>
            </header>
            <div class="flex-grow overflow-y-auto p-6 space-y-6">
                 <!-- File Upload Section -->
                <section>
                    <h3 class="font-semibold mb-2">Upload New Files</h3>
                    <div @dragover.prevent="isDragging = true" @dragleave.prevent="isDragging = false" @drop.prevent="handleFileDrop"
                        class="p-6 border-2 border-dashed rounded-lg text-center transition-colors" :class="isDragging ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600'">
                        <input type="file" multiple @change="handleFileSelect" class="hidden" ref="fileInput">
                        <button @click="$refs.fileInput.click()" class="text-blue-600 dark:text-blue-400 font-medium">Click to select files</button> or drag and drop.
                    </div>
                    <div v-if="filesToUpload.length > 0" class="mt-4 space-y-2">
                        <div v-for="(file, index) in filesToUpload" :key="index" class="flex items-center justify-between p-2 bg-gray-100 dark:bg-gray-700/50 rounded-md text-sm">
                            <span class="truncate">{{ file.name }}</span>
                            <button @click="removeFileToUpload(index)" class="btn-icon-danger !p-1"><IconXMark class="w-4 h-4" /></button>
                        </div>
                        <div class="pt-2">
                            <label for="vectorizerSelect" class="block text-sm font-medium mb-1">Vectorizer</label>
                            <select id="vectorizerSelect" v-model="selectedVectorizer" class="input-field w-full">
                                <option disabled value="">Select a vectorizer</option>
                                <option v-for="v in storeVectorizers" :key="v.name" :value="v.name">{{ v.method_name }}</option>
                            </select>
                        </div>
                        <button @click="handleUpload" class="btn btn-primary w-full mt-2" :disabled="isUploading || !selectedVectorizer">{{ isUploading ? 'Uploading...' : 'Upload Files' }}</button>
                    </div>
                </section>
                <!-- Existing Files Section -->
                <section>
                    <h3 class="font-semibold mb-2">Uploaded Files</h3>
                    <div v-if="isFetchingFiles" class="text-center text-gray-500">Loading files...</div>
                    <ul v-else-if="storeFiles.length > 0" class="space-y-2">
                        <li v-for="file in storeFiles" :key="file.filename" class="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-700/50 rounded-md text-sm">
                            <span class="truncate">{{ file.filename }}</span>
                            <button @click="handleDeleteFile(file.filename)" class="btn-icon-danger !p-1" title="Delete File"><IconTrash class="w-4 h-4" /></button>
                        </li>
                    </ul>
                    <p v-else class="text-center text-gray-500 text-sm py-4">No files in this data store yet.</p>
                </section>
            </div>
        </div>
    </div>
  </div>
</template>