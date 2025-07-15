<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import UserAvatar from '../components/ui/UserAvatar.vue';

// Import Icon Components
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconShare from '../assets/icons/IconShare.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconDatabase from '../assets/icons/IconDatabase.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';
import IconUserMinus from '../assets/icons/IconUserMinus.vue';
import IconPlusCircle from '../assets/icons/IconPlusCircle.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const { ownedDataStores, sharedDataStores } = storeToRefs(dataStore);
const { user } = storeToRefs(authStore);
const isLoadingStores = ref(false);

const isFormVisible = ref(false);
const isEditMode = ref(false);
const form = ref({ id: null, name: '', description: '' });
const isLoadingForm = ref(false);

const selectedStore = ref(null);
const storeFiles = ref([]);
const storeVectorizers = ref([]);
const selectedVectorizer = ref('');
const isFetchingFiles = ref(false);
const isUploading = ref(false);
const filesToUpload = ref([]);
const isDragging = ref(false);

const sharedWithList = ref([]);
const isFetchingSharedList = ref(false);

const isRevectorizing = ref(false);
const newVectorizerForRevectorize = ref('');
const newVectorizerNameInput = ref('');
const showAddVectorizerInput = ref(false);

const permissionsMap = {
    'owner': 'Owner',
    'revectorize': 'Read/Write & Revectorize',
    'read_write': 'Read/Write',
    'read_query': 'Read (Query)'
};

const permissionOptions = [
    { value: 'read_query', label: 'Read (Query)' },
    { value: 'read_write', label: 'Read/Write' },
    { value: 'revectorize', label: 'Read/Write & Revectorize' },
];

const hasWritePermission = computed(() => {
    if (!selectedStore.value) return false;
    const perm = selectedStore.value.permission_level;
    return perm === 'owner' || perm === 'read_write' || perm === 'revectorize';
});

const hasRevectorizePermission = computed(() => {
    if (!selectedStore.value) return false;
    const perm = selectedStore.value.permission_level;
    return perm === 'owner' || perm === 'revectorize';
});

onMounted(async () => {
    isLoadingStores.value = true;
    await dataStore.fetchDataStores();
    isLoadingStores.value = false;
});

watch(selectedStore, async (newStore) => {
    if (newStore) {
        await handleManage(newStore);
    } else {
        // Reset all detail states
        storeFiles.value = [];
        storeVectorizers.value = [];
        selectedVectorizer.value = '';
        sharedWithList.value = [];
        newVectorizerForRevectorize.value = '';
        newVectorizerNameInput.value = '';
        showAddVectorizerInput.value = false;
    }
});

async function handleManage(store) {
    selectedStore.value = store;
    isFetchingFiles.value = true;
    isFetchingSharedList.value = true;
    try {
        const [files, vectorizers, sharedWith] = await Promise.all([
            dataStore.fetchStoreFiles(store.id),
            dataStore.fetchStoreVectorizers(store.id),
            store.permission_level === 'owner' ? dataStore.getSharedWithList(store.id) : Promise.resolve([])
        ]);
        
        storeFiles.value = files;
        storeVectorizers.value = vectorizers;
        sharedWithList.value = sharedWith;

        // Intelligent vectorizer selection
        if (vectorizers.length > 0) {
            selectedVectorizer.value = vectorizers[0].name; // Default to first existing
            newVectorizerForRevectorize.value = vectorizers[0].name;
        } else if (user.value?.safe_store_vectorizer) {
            selectedVectorizer.value = user.value.safe_store_vectorizer; // Default to user's preference for empty store
        }
        
    } catch (error) {
        uiStore.addNotification('Could not load store details.', 'error');
        selectedStore.value = null;
    } finally {
        isFetchingFiles.value = false;
        isFetchingSharedList.value = false;
    }
}

async function handleRevectorize() {
    if (!newVectorizerForRevectorize.value) {
        uiStore.addNotification('Please select a vectorizer.', 'warning');
        return;
    }
    const confirmed = await uiStore.showConfirmation({
        title: 'Re-vectorize Store?',
        message: `This will re-process all documents in the store with the '${newVectorizerForRevectorize.value}' vectorizer. This can take a long time and cannot be undone.`,
        confirmText: 'Yes, Re-vectorize'
    });
    if (confirmed) {
        isRevectorizing.value = true;
        try {
            await dataStore.revectorizeStore({
                storeId: selectedStore.value.id,
                vectorizerName: newVectorizerForRevectorize.value
            });
            // The process is now running in the background on the server.
        } finally {
            isRevectorizing.value = false;
        }
    }
}

async function handleAddVectorizer() {
    const name = newVectorizerNameInput.value.trim();
    if (!name || (!name.startsWith('st:') && !name.startsWith('tfidf:'))) {
        uiStore.addNotification('Invalid vectorizer name. Must start with "st:" or "tfidf:".', 'error');
        return;
    }
    storeVectorizers.value.push({ name: name, method_name: name });
    selectedVectorizer.value = name;
    newVectorizerNameInput.value = '';
    showAddVectorizerInput.value = false;
}

async function handlePermissionChange(sharedUser, newPermission) {
    try {
        await dataStore.shareDataStore({
            storeId: selectedStore.value.id,
            username: sharedUser.username,
            permissionLevel: newPermission
        });
        const userInList = sharedWithList.value.find(u => u.user_id === sharedUser.user_id);
        if (userInList) {
            userInList.permission_level = newPermission;
        }
        uiStore.addNotification(`Permissions updated for ${sharedUser.username}.`, 'success');
    } catch (error) {
        // Handled by store
    }
}

async function handleRevokeAccess(sharedUser) {
    const confirmed = await uiStore.showConfirmation({
        title: 'Revoke Access?',
        message: `Are you sure you want to stop sharing this store with ${sharedUser.username}?`,
        confirmText: 'Revoke'
    });
    if (confirmed) {
        try {
            const success = await dataStore.revokeShare(selectedStore.value.id, sharedUser.user_id);
            if (success) {
                sharedWithList.value = sharedWithList.value.filter(u => u.user_id !== sharedUser.user_id);
            }
        } catch (error) {
           // Handled by store
        }
    }
}


function showCreateForm() { isFormVisible.value = true; isEditMode.value = false; form.value = { id: null, name: '', description: '' }; window.scrollTo({ top: 0, behavior: 'smooth' }); }
function showEditForm(store) { isFormVisible.value = true; isEditMode.value = true; form.value = { ...store }; window.scrollTo({ top: 0, behavior: 'smooth' }); }
function hideForm() { isFormVisible.value = false; }
async function handleSubmit() { isLoadingForm.value = true; try { if (isEditMode.value) { await dataStore.updateDataStore(form.value); } else { await dataStore.addDataStore(form.value); } hideForm(); } catch (error) {} finally { isLoadingForm.value = false; } }
async function handleDeleteStore(store) { const c = await uiStore.showConfirmation({ title: `Delete '${store.name}'?`, message: 'This will permanently delete the data store and all its files.', confirmText: 'Delete' }); if (c) { if (selectedStore.value?.id === store.id) { selectedStore.value = null; } await dataStore.deleteDataStore(store.id); } }
function closeFileManagement() { selectedStore.value = null; }
function handleFileDrop(event) { isDragging.value = false; filesToUpload.value = [...filesToUpload.value, ...Array.from(event.dataTransfer.files)]; }
function handleFileSelect(event) { filesToUpload.value = [...filesToUpload.value, ...Array.from(event.target.files)]; event.target.value = ''; }
function removeFileToUpload(index) { filesToUpload.value.splice(index, 1); }
async function handleUpload() { if (filesToUpload.value.length === 0 || !selectedVectorizer.value) { uiStore.addNotification('Please select files and a vectorizer.', 'warning'); return; } isUploading.value = true; const formData = new FormData(); filesToUpload.value.forEach(file => formData.append('files', file)); formData.append('vectorizer_name', selectedVectorizer.value); try { await dataStore.uploadFilesToStore({ storeId: selectedStore.value.id, formData }); filesToUpload.value = []; await handleManage(selectedStore.value); } finally { isUploading.value = false; } }
async function handleDeleteFile(filename) { const c = await uiStore.showConfirmation({ title: `Delete File?`, message: `Are you sure you want to delete '${filename}'?`, confirmText: 'Delete' }); if(c) { try { await dataStore.deleteFileFromStore({ storeId: selectedStore.value.id, filename }); storeFiles.value = storeFiles.value.filter(f => f.filename !== filename); } catch(error) {} } }
function handleShare(store) { uiStore.openModal('shareDataStore', { store }); }
</script>

<template>
  <div class="flex h-screen bg-gray-100 dark:bg-gray-900">
    <!-- Master List Panel -->
    <div class="flex-shrink-0 flex flex-col h-full transition-all duration-300 ease-in-out" :class="selectedStore ? 'w-full md:w-1/2 lg:w-1/3' : 'w-full'">
      <header class="bg-white dark:bg-gray-800 border-b dark:border-gray-700 p-4 flex items-center justify-between shadow-sm flex-shrink-0">
        <div class="flex items-center space-x-3"><IconDatabase class="h-6 w-6 text-gray-500 dark:text-gray-400" /><h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">RAG Data Stores</h1></div>
        <div class="flex items-center space-x-2"><button v-if="!isFormVisible" @click="showCreateForm" class="btn btn-primary"><IconPlus class="w-5 h-5 mr-1" /><span>New</span></button><router-link to="/" class="btn-icon" title="Back to App"><IconArrowLeft class="w-5 h-5" /></router-link></div>
      </header>

      <main class="flex-grow overflow-y-auto p-6 space-y-8">
        <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md border dark:border-gray-700"><h2 class="text-lg font-semibold mb-4">{{ isEditMode ? 'Edit' : 'Create' }} Data Store</h2><form @submit.prevent="handleSubmit" class="space-y-4"><div><label for="storeName" class="block text-sm font-medium">Name</label><input type="text" id="storeName" v-model="form.name" required class="input-field mt-1" placeholder="e.g., Project Documents"></div><div><label for="storeDescription" class="block text-sm font-medium">Description</label><textarea id="storeDescription" v-model="form.description" rows="3" class="input-field mt-1" placeholder="A brief description..."></textarea></div><div class="flex justify-end space-x-3"><button type="button" @click="hideForm" class="btn btn-secondary">Cancel</button><button type="submit" class="btn btn-primary" :disabled="isLoadingForm">{{ isLoadingForm ? 'Saving...' : (isEditMode ? 'Save' : 'Create') }}</button></div></form></div>
        <section><h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">Your Data Stores</h2><div v-if="isLoadingStores" class="grid grid-cols-1 md:grid-cols-2 gap-4"><div v-for="i in 2" :key="i" class="h-40 bg-gray-200 dark:bg-gray-700/50 rounded-lg animate-pulse"></div></div><div v-else-if="ownedDataStores.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-4"><div v-for="store in ownedDataStores" :key="store.id" @click="handleManage(store)" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow flex flex-col cursor-pointer hover:ring-2 hover:ring-blue-500 transition-all"><div class="flex justify-between items-start"><h3 class="font-bold text-gray-900 dark:text-white truncate" :title="store.name">{{ store.name }}</h3><span class="status-badge-blue ml-2">Owner</span></div><p class="text-sm text-gray-500 dark:text-gray-400 mt-1 flex-grow line-clamp-2">{{ store.description || 'No description.' }}</p><div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 flex items-center justify-end space-x-2"><button @click.stop="showEditForm(store)" class="btn-icon" title="Edit"><IconPencil class="h-5 w-5" /></button><button @click.stop="handleShare(store)" class="btn-icon" title="Share"><IconShare class="h-5 w-5" /></button><button @click.stop="handleDeleteStore(store)" class="btn-icon-danger" title="Delete"><IconTrash class="h-5 w-5" /></button></div></div></div><div v-else class="text-center py-8 bg-gray-50 dark:bg-gray-800/50 rounded-lg"><p class="text-gray-500 dark:text-gray-400">You haven't created any data stores yet.</p><button @click="showCreateForm" class="mt-2 text-blue-600 dark:text-blue-400 hover:underline text-sm font-medium">Create your first one</button></div></section>
        <section><h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-4">Shared With You</h2><div v-if="isLoadingStores" class="grid grid-cols-1 md:grid-cols-2 gap-4"><div class="h-40 bg-gray-200 dark:bg-gray-700/50 rounded-lg animate-pulse"></div></div><div v-else-if="sharedDataStores.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-4"><div v-for="store in sharedDataStores" :key="store.id" @click="handleManage(store)" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow flex flex-col cursor-pointer hover:ring-2 hover:ring-blue-500 transition-all"><div class="flex justify-between items-start"><h3 class="font-bold text-gray-900 dark:text-white truncate" :title="store.name">{{ store.name }}</h3><span class="status-badge-green ml-2">{{ permissionsMap[store.permission_level] }}</span></div><p class="text-xs text-gray-400 dark:text-gray-500">from {{ store.owner_username }}</p><p class="text-sm text-gray-500 dark:text-gray-400 mt-2 flex-grow line-clamp-2">{{ store.description || 'No description.' }}</p></div></div><div v-else class="text-center py-8 bg-gray-50 dark:bg-gray-800/50 rounded-lg"><p class="text-gray-500 dark:text-gray-400">No data stores have been shared with you.</p></div></section>
      </main>
    </div>

    <!-- Detail Panel -->
    <div class="flex-shrink-0 flex flex-col h-full bg-white dark:bg-gray-800 border-l dark:border-gray-700 transition-all duration-300 ease-in-out" :class="selectedStore ? 'w-full md:w-1/2 lg:w-2/3' : 'w-0 hidden'">
        <div v-if="selectedStore" class="flex flex-col h-full">
            <header class="p-4 border-b dark:border-gray-700 flex-shrink-0 flex items-center justify-between"><div class="min-w-0"><h2 class="text-lg font-semibold truncate" :title="selectedStore.name">{{ selectedStore.name }}</h2><p class="text-sm text-gray-500">Management</p></div><button @click="closeFileManagement" class="btn-icon" title="Close"><IconXMark class="w-6 h-6"/></button></header>
            <div class="flex-grow overflow-y-auto p-6 space-y-8">
                <section v-if="hasWritePermission"><h3 class="font-semibold mb-2">Upload New Files</h3><div @dragover.prevent="isDragging = true" @dragleave.prevent="isDragging = false" @drop.prevent="handleFileDrop" class="p-6 border-2 border-dashed rounded-lg text-center transition-colors" :class="isDragging ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600'"><input type="file" multiple @change="handleFileSelect" class="hidden" ref="fileInput"><button @click="$refs.fileInput.click()" class="text-blue-600 dark:text-blue-400 font-medium">Click to select files</button> or drag and drop.</div><div v-if="filesToUpload.length > 0" class="mt-4 space-y-2"><div v-for="(file, index) in filesToUpload" :key="index" class="flex items-center justify-between p-2 bg-gray-100 dark:bg-gray-700/50 rounded-md text-sm"><span class="truncate">{{ file.name }}</span><button @click="removeFileToUpload(index)" class="btn-icon-danger !p-1"><IconXMark class="w-4 h-4" /></button></div><div class="pt-2 flex items-end gap-2"><div class="flex-grow"><label for="vectorizerSelect" class="block text-sm font-medium mb-1">Vectorizer</label><select id="vectorizerSelect" v-model="selectedVectorizer" class="input-field w-full"><option disabled value="">Select a vectorizer</option><option v-for="v in storeVectorizers" :key="v.name" :value="v.name">{{ v.method_name }}</option></select></div><button @click="showAddVectorizerInput = !showAddVectorizerInput" v-if="hasRevectorizePermission" class="btn-icon" title="Add new vectorizer"><IconPlusCircle class="w-6 h-6"/></button></div><div v-if="showAddVectorizerInput && hasRevectorizePermission" class="flex gap-2 mt-2"><input type="text" v-model="newVectorizerNameInput" class="input-field flex-grow" placeholder="st:new-model-name"><button @click="handleAddVectorizer" class="btn btn-secondary">Add</button></div><button @click="handleUpload" class="btn btn-primary w-full mt-2" :disabled="isUploading || !selectedVectorizer">{{ isUploading ? 'Uploading...' : 'Upload Files' }}</button></div></section>
                <section><h3 class="font-semibold mb-2">Uploaded Files</h3><div v-if="isFetchingFiles" class="text-center text-gray-500">Loading files...</div><ul v-else-if="storeFiles.length > 0" class="space-y-2 max-h-60 overflow-y-auto pr-2"><li v-for="file in storeFiles" :key="file.filename" class="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-700/50 rounded-md text-sm"><span class="truncate">{{ file.filename }}</span><button v-if="hasWritePermission" @click="handleDeleteFile(file.filename)" class="btn-icon-danger !p-1" title="Delete File"><IconTrash class="w-4 h-4" /></button></li></ul><p v-else class="text-center text-gray-500 text-sm py-4">No files in this data store yet.</p></section>
                <section v-if="hasRevectorizePermission"><h3 class="font-semibold mb-2">Re-vectorize Store</h3><div class="p-4 bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-400 dark:border-yellow-500 rounded-r-lg"><p class="text-sm text-yellow-800 dark:text-yellow-200"><b>Warning:</b> Re-vectorizing will re-process all files with a new vectorizer. This can be slow and will replace existing vector data.</p></div><div class="flex items-end gap-2 mt-4"><div class="flex-grow"><label for="revectorizeSelect" class="block text-sm font-medium mb-1">New Vectorizer</label><select id="revectorizeSelect" v-model="newVectorizerForRevectorize" class="input-field w-full"><option disabled value="">Select new vectorizer</option><option v-for="v in storeVectorizers" :key="v.name" :value="v.name">{{ v.method_name }}</option></select></div><button @click="handleRevectorize" class="btn btn-warning" :disabled="isRevectorizing || !newVectorizerForRevectorize"><IconRefresh class="w-5 h-5 mr-1"/>{{ isRevectorizing ? 'Working...' : 'Re-vectorize' }}</button></div></section>
                <section v-if="selectedStore.permission_level === 'owner'"><h3 class="font-semibold mb-2">Sharing Status</h3><div v-if="isFetchingSharedList" class="text-center text-gray-500">Loading...</div><div v-else-if="sharedWithList.length > 0" class="space-y-2 max-h-60 overflow-y-auto pr-2"><div v-for="sharedUser in sharedWithList" :key="sharedUser.user_id" class="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-700/50 rounded-md"><div class="flex items-center gap-3"><UserAvatar :icon="sharedUser.icon" :username="sharedUser.username" size-class="h-8 w-8" /><span class="font-medium text-sm">{{ sharedUser.username }}</span></div><div class="flex items-center gap-2"><select v-model="sharedUser.permission_level" @change="handlePermissionChange(sharedUser, $event.target.value)" class="input-field !py-1 !text-xs"><option v-for="opt in permissionOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option></select><button @click="handleRevokeAccess(sharedUser)" class="btn-icon-danger" title="Revoke Access"><IconUserMinus class="h-5 w-5"/></button></div></div></div><p v-else class="text-center text-gray-500 text-sm py-4">Not shared with anyone.</p></section>
            </div>
        </div>
    </div>
  </div>
</template>
<style scoped>
.status-badge-blue { @apply px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300; }
.status-badge-green { @apply px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300; }
</style>