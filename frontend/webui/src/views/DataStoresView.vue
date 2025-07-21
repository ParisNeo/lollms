<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import UserAvatar from '../components/ui/UserAvatar.vue';
import PageViewLayout from '../components/layout/PageViewLayout.vue';

// Import Icon Components
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

const viewMode = ref('welcome'); // 'welcome', 'details', 'form'
const isEditMode = ref(false);
const form = ref({ id: null, name: '', description: '' });
const isLoadingForm = ref(false);

const selectedStore = ref(null);
const storeFiles = ref([]);
const storeVectorizersInStore = ref([]);
const storeVectorizersAllPossible = ref([]);
const selectedVectorizer = ref('');
const isFetchingFiles = ref(false);
const isUploading = ref(false);
const filesToUpload = ref([]);
const isDragging = ref(false);

const sharedWithList = ref([]);
const isFetchingSharedList = ref(false);

const isRevectorizing = ref(false);
const newVectorizerForRevectorize = ref('');
const showAddVectorizerControls = ref(false);
const newVectorizerToAdd = ref(null);

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
    if (newStore && viewMode.value === 'details') {
        await fetchStoreDetails(newStore);
    }
});

async function fetchStoreDetails(store) {
    isFetchingFiles.value = true;
    isFetchingSharedList.value = true;
    try {
        const [files, vectorizersData, sharedWith] = await Promise.all([
            dataStore.fetchStoreFiles(store.id),
            dataStore.fetchStoreVectorizers(store.id),
            store.permission_level === 'owner' ? dataStore.getSharedWithList(store.id) : Promise.resolve([])
        ]);
        
        storeFiles.value = files;
        storeVectorizersInStore.value = vectorizersData.in_store;
        storeVectorizersAllPossible.value = vectorizersData.all_possible;
        sharedWithList.value = sharedWith;

        selectedVectorizer.value = user.value?.safe_store_vectorizer || '';
        if (selectedVectorizer.value && !storeVectorizersInStore.value.some(v => v.name === selectedVectorizer.value)) {
             const defaultInAll = storeVectorizersAllPossible.value.find(v => v.name === selectedVectorizer.value);
             if (defaultInAll) {
                storeVectorizersInStore.value.unshift(defaultInAll);
             }
        }
        if (storeVectorizersInStore.value.length > 0) {
            newVectorizerForRevectorize.value = storeVectorizersInStore.value[0].name;
        }
    } catch (error) {
        uiStore.addNotification('Could not load store details.', 'error');
        selectedStore.value = null;
        viewMode.value = 'welcome';
    } finally {
        isFetchingFiles.value = false;
        isFetchingSharedList.value = false;
    }
}

function handleSelectStore(store) {
    selectedStore.value = store;
    viewMode.value = 'details';
}

async function handleRevectorize() {
    if (!newVectorizerForRevectorize.value) { uiStore.addNotification('Please select a vectorizer.', 'warning'); return; }
    const confirmed = await uiStore.showConfirmation({ title: 'Re-vectorize Store?', message: `This will re-process all documents in the store with the '${newVectorizerForRevectorize.value}' vectorizer. This can take a long time and cannot be undone.`, confirmText: 'Yes, Re-vectorize' });
    if (confirmed) { isRevectorizing.value = true; try { await dataStore.revectorizeStore({ storeId: selectedStore.value.id, vectorizerName: newVectorizerForRevectorize.value }); } finally { isRevectorizing.value = false; } }
}

function handleAddVectorizer() {
    if (!newVectorizerToAdd.value) return;
    const vectorizer = storeVectorizersAllPossible.value.find(v => v.name === newVectorizerToAdd.value);
    if (vectorizer && !storeVectorizersInStore.value.some(v => v.name === vectorizer.name)) {
        storeVectorizersInStore.value.push(vectorizer);
        storeVectorizersInStore.value.sort((a, b) => a.name.localeCompare(b.name));
    }
    selectedVectorizer.value = newVectorizerToAdd.value;
    newVectorizerToAdd.value = null;
    showAddVectorizerControls.value = false;
}

async function handlePermissionChange(sharedUser, newPermission) { try { await dataStore.shareDataStore({ storeId: selectedStore.value.id, username: sharedUser.username, permissionLevel: newPermission }); const userInList = sharedWithList.value.find(u => u.user_id === sharedUser.user_id); if (userInList) { userInList.permission_level = newPermission; } uiStore.addNotification(`Permissions updated for ${sharedUser.username}.`, 'success'); } catch (error) {} }
async function handleRevokeAccess(sharedUser) { const confirmed = await uiStore.showConfirmation({ title: 'Revoke Access?', message: `Are you sure you want to stop sharing this store with ${sharedUser.username}?`, confirmText: 'Revoke' }); if (confirmed) { try { const success = await dataStore.revokeShare(selectedStore.value.id, sharedUser.user_id); if (success) { sharedWithList.value = sharedWithList.value.filter(u => u.user_id !== sharedUser.user_id); } } catch (error) {} } }
function showCreateForm() { isEditMode.value = false; form.value = { id: null, name: '', description: '' }; viewMode.value = 'form'; selectedStore.value = null; }
function showEditForm() { isEditMode.value = true; form.value = { ...selectedStore.value }; viewMode.value = 'form'; }
function hideForm() { if(isEditMode.value && selectedStore.value) { viewMode.value = 'details'; } else { viewMode.value = 'welcome'; } isEditMode.value = false; }
async function handleSubmit() { isLoadingForm.value = true; try { let storeId; if (isEditMode.value) { await dataStore.updateDataStore(form.value); storeId = form.value.id; } else { const newStore = await dataStore.addDataStore(form.value); storeId = newStore.id; } await dataStore.fetchDataStores(); const store = ownedDataStores.value.find(s => s.id === storeId); if (store) { handleSelectStore(store); } else { viewMode.value = 'welcome'; } } catch (error) {} finally { isLoadingForm.value = false; } }
async function handleDeleteStore(store) { const c = await uiStore.showConfirmation({ title: `Delete '${store.name}'?`, message: 'This will permanently delete the data store and all its files.', confirmText: 'Delete' }); if (c) { if (selectedStore.value?.id === store.id) { selectedStore.value = null; viewMode.value = 'welcome'; } await dataStore.deleteDataStore(store.id); } }
function handleFileDrop(event) { isDragging.value = false; filesToUpload.value = [...filesToUpload.value, ...Array.from(event.dataTransfer.files)]; }
function handleFileSelect(event) { filesToUpload.value = [...filesToUpload.value, ...Array.from(event.target.files)]; event.target.value = ''; }
function removeFileToUpload(index) { filesToUpload.value.splice(index, 1); }
async function handleUpload() { if (filesToUpload.value.length === 0 || !selectedVectorizer.value) { uiStore.addNotification('Please select files and a vectorizer.', 'warning'); return; } isUploading.value = true; const formData = new FormData(); filesToUpload.value.forEach(file => formData.append('files', file)); formData.append('vectorizer_name', selectedVectorizer.value); try { await dataStore.uploadFilesToStore({ storeId: selectedStore.value.id, formData }); filesToUpload.value = []; await fetchStoreDetails(selectedStore.value); } finally { isUploading.value = false; } }
async function handleDeleteFile(filename) { const c = await uiStore.showConfirmation({ title: `Delete File?`, message: `Are you sure you want to delete '${filename}'?`, confirmText: 'Delete' }); if(c) { try { await dataStore.deleteFileFromStore({ storeId: selectedStore.value.id, filename }); storeFiles.value = storeFiles.value.filter(f => f.filename !== filename); } catch(error) {} } }
function handleShare(store) { uiStore.openModal('shareDataStore', { store }); }
</script>

<template>
  <PageViewLayout title="RAG Data Stores" :title-icon="IconDatabase">
    <template #sidebar>
        <div class="p-4 flex flex-col h-full">
            <button @click="showCreateForm" class="btn btn-primary w-full mb-6 flex-shrink-0">
                <IconPlus class="w-5 h-5 mr-1" />
                <span>New Data Store</span>
            </button>
            <div class="flex-grow overflow-y-auto -mx-4 px-4">
                <div class="space-y-6">
                    <section>
                        <h3 class="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400 tracking-wider mb-2 px-2">Your Stores</h3>
                        <div v-if="isLoadingStores" class="space-y-2"><div v-for="i in 3" :key="i" class="h-10 bg-gray-200 dark:bg-gray-700/50 rounded-lg animate-pulse"></div></div>
                        <ul v-else-if="ownedDataStores.length > 0" class="space-y-1">
                            <li v-for="store in ownedDataStores" :key="store.id">
                                <button @click="handleSelectStore(store)" class="w-full text-left flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors" :class="selectedStore?.id === store.id ? 'bg-blue-100 dark:bg-blue-900/50 font-semibold text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'">
                                    <IconDatabase class="w-5 h-5 flex-shrink-0" />
                                    <span class="truncate">{{ store.name }}</span>
                                </button>
                            </li>
                        </ul>
                        <p v-else class="text-xs text-gray-400 dark:text-gray-500 px-2 italic">No stores created.</p>
                    </section>
                    <section>
                        <h3 class="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400 tracking-wider mb-2 px-2">Shared With You</h3>
                        <div v-if="isLoadingStores" class="space-y-2"><div v-for="i in 2" :key="i" class="h-10 bg-gray-200 dark:bg-gray-700/50 rounded-lg animate-pulse"></div></div>
                        <ul v-else-if="sharedDataStores.length > 0" class="space-y-1">
                             <li v-for="store in sharedDataStores" :key="store.id">
                                <button @click="handleSelectStore(store)" class="w-full text-left flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors" :class="selectedStore?.id === store.id ? 'bg-blue-100 dark:bg-blue-900/50 font-semibold text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'">
                                    <IconShare class="w-5 h-5 flex-shrink-0 text-green-500" />
                                    <span class="truncate">{{ store.name }}</span>
                                </button>
                            </li>
                        </ul>
                        <p v-else class="text-xs text-gray-400 dark:text-gray-500 px-2 italic">No stores shared with you.</p>
                    </section>
                </div>
            </div>
        </div>
    </template>
    <template #main>
        <div v-if="viewMode === 'welcome'" class="h-full flex flex-col items-center justify-center text-center">
            <IconDatabase class="w-16 h-16 text-gray-300 dark:text-gray-600 mb-4" />
            <h2 class="text-xl font-semibold text-gray-800 dark:text-gray-200">Welcome to Data Stores</h2>
            <p class="text-gray-500 dark:text-gray-400 mt-1">Select a store from the sidebar to manage it, or create a new one.</p>
        </div>

        <div v-if="viewMode === 'form'" class="h-full">
            <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md border dark:border-gray-700 max-w-2xl mx-auto">
                <h2 class="text-lg font-semibold mb-4">{{ isEditMode ? `Edit '${form.name}'` : 'Create New Data Store' }}</h2>
                <form @submit.prevent="handleSubmit" class="space-y-4">
                    <div><label for="storeName" class="block text-sm font-medium">Name</label><input type="text" id="storeName" v-model="form.name" required class="input-field mt-1" placeholder="e.g., Project Documents"></div>
                    <div><label for="storeDescription" class="block text-sm font-medium">Description</label><textarea id="storeDescription" v-model="form.description" rows="3" class="input-field mt-1" placeholder="A brief description..."></textarea></div>
                    <div class="flex justify-end space-x-3"><button type="button" @click="hideForm" class="btn btn-secondary">Cancel</button><button type="submit" class="btn btn-primary" :disabled="isLoadingForm">{{ isLoadingForm ? 'Saving...' : (isEditMode ? 'Save Changes' : 'Create Store') }}</button></div>
                </form>
            </div>
        </div>

        <div v-if="viewMode === 'details' && selectedStore" class="h-full flex flex-col">
            <header class="p-4 border-b dark:border-gray-700 flex-shrink-0 flex items-center justify-between bg-white dark:bg-gray-800 rounded-t-lg">
                <div class="min-w-0">
                    <h2 class="text-lg font-semibold truncate" :title="selectedStore.name">{{ selectedStore.name }}</h2>
                    <p class="text-sm text-gray-500">{{ permissionsMap[selectedStore.permission_level] }}</p>
                </div>
                <div class="flex items-center gap-2">
                    <button v-if="selectedStore.permission_level === 'owner'" @click="showEditForm" class="btn-icon" title="Edit Store"><IconPencil class="w-5 w-5"/></button>
                    <button v-if="selectedStore.permission_level === 'owner'" @click="handleDeleteStore(selectedStore)" class="btn-icon-danger" title="Delete Store"><IconTrash class="w-5 w-5"/></button>
                </div>
            </header>
            <div class="flex-grow overflow-y-auto p-6 space-y-8 bg-white dark:bg-gray-800 rounded-b-lg">
                <section v-if="hasWritePermission"><h3 class="font-semibold mb-2">Upload New Files</h3><div @dragover.prevent="isDragging = true" @dragleave.prevent="isDragging = false" @drop.prevent="handleFileDrop" class="p-6 border-2 border-dashed rounded-lg text-center transition-colors" :class="isDragging ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600'"><input type="file" multiple @change="handleFileSelect" class="hidden" ref="fileInput"><button @click="$refs.fileInput.click()" class="text-blue-600 dark:text-blue-400 font-medium">Click to select files</button> or drag and drop.</div><div v-if="filesToUpload.length > 0" class="mt-4 space-y-2"><div v-for="(file, index) in filesToUpload" :key="index" class="flex items-center justify-between p-2 bg-gray-100 dark:bg-gray-700/50 rounded-md text-sm"><span class="truncate">{{ file.name }}</span><button @click="removeFileToUpload(index)" class="btn-icon-danger !p-1"><IconXMark class="w-4 h-4" /></button></div><div class="pt-2"><label class="block text-sm font-medium mb-1">Vectorizer</label><div class="flex items-end gap-2"><div class="flex-grow"><select v-model="selectedVectorizer" class="input-field w-full"><option disabled value="">Select vectorizer</option><option v-for="v in storeVectorizersInStore" :key="v.name" :value="v.name">{{ v.method_name }}</option></select></div><button @click="showAddVectorizerControls = !showAddVectorizerControls" v-if="hasRevectorizePermission" class="btn-icon" title="Add vectorizer to store"><IconPlusCircle class="w-6 h-6"/></button></div><div v-if="showAddVectorizerControls && hasRevectorizePermission" class="flex gap-2 mt-2"><div class="flex-grow"><select v-model="newVectorizerToAdd" class="input-field w-full"><option :value="null" disabled>Select from all possible...</option><option v-for="v in storeVectorizersAllPossible" :key="v.name" :value="v.name">{{ v.method_name }}</option></select></div><button @click="handleAddVectorizer" class="btn btn-secondary">Add</button></div></div><button @click="handleUpload" class="btn btn-primary w-full mt-2" :disabled="isUploading || !selectedVectorizer">{{ isUploading ? 'Uploading...' : 'Upload Files' }}</button></div></section>
                <section><h3 class="font-semibold mb-2">Uploaded Files</h3><div v-if="isFetchingFiles" class="text-center text-gray-500">Loading files...</div><ul v-else-if="storeFiles.length > 0" class="space-y-2 max-h-60 overflow-y-auto pr-2"><li v-for="file in storeFiles" :key="file.filename" class="flex items-center justify-between p-2 bg-gray-100 dark:bg-gray-700/50 rounded-md text-sm"><span class="truncate">{{ file.filename }}</span><button v-if="hasWritePermission" @click="handleDeleteFile(file.filename)" class="btn-icon-danger !p-1" title="Delete File"><IconTrash class="w-4 h-4" /></button></li></ul><p v-else class="text-center text-gray-500 text-sm py-4">No files in this data store yet.</p></section>
                <section v-if="hasRevectorizePermission"><h3 class="font-semibold mb-2">Re-vectorize Store</h3><div class="p-4 bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-400 dark:border-yellow-500 rounded-r-lg"><p class="text-sm text-yellow-800 dark:text-yellow-200"><b>Warning:</b> Re-vectorizing will re-process all files with a new vectorizer. This can be slow and will replace existing vector data.</p></div><div class="flex items-end gap-2 mt-4"><div class="flex-grow"><label for="revectorizeSelect" class="block text-sm font-medium mb-1">New Vectorizer</label><select id="revectorizeSelect" v-model="newVectorizerForRevectorize" class="input-field w-full"><option disabled value="">Select new vectorizer</option><option v-for="v in storeVectorizersInStore" :key="v.name" :value="v.name">{{ v.method_name }}</option></select></div><button @click="handleRevectorize" class="btn btn-warning" :disabled="isRevectorizing || !newVectorizerForRevectorize"><IconRefresh class="w-5 h-5 mr-1"/>{{ isRevectorizing ? 'Working...' : 'Re-vectorize' }}</button></div></section>
                <section v-if="selectedStore.permission_level === 'owner'"><h3 class="font-semibold mb-2">Sharing Status</h3><div v-if="isFetchingSharedList" class="text-center text-gray-500">Loading...</div><div v-else-if="sharedWithList.length > 0" class="space-y-2 max-h-60 overflow-y-auto pr-2"><div v-for="sharedUser in sharedWithList" :key="sharedUser.user_id" class="flex items-center justify-between p-2 bg-gray-100 dark:bg-gray-700/50 rounded-md"><div class="flex items-center gap-3"><UserAvatar :icon="sharedUser.icon" :username="sharedUser.username" size-class="h-8 w-8" /><span class="font-medium text-sm">{{ sharedUser.username }}</span></div><div class="flex items-center gap-2"><select v-model="sharedUser.permission_level" @change="handlePermissionChange(sharedUser, $event.target.value)" class="input-field !py-1 !text-xs"><option v-for="opt in permissionOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option></select><button @click="handleRevokeAccess(sharedUser)" class="btn-icon-danger" title="Revoke Access"><IconUserMinus class="h-5 w-5"/></button></div></div></div><div v-else class="text-center text-gray-500 text-sm py-4">Not shared with anyone. <button @click="handleShare(selectedStore)" class="text-blue-600 hover:underline">Share now</button></div></section>
            </div>
        </div>
    </template>
  </PageViewLayout>
</template>