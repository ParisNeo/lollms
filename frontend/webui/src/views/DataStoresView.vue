<!-- [UPDATE] frontend/webui/src/views/DataStoresView.vue -->
<script setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useTasksStore } from '../stores/tasks';
import { useAdminStore } from '../stores/admin';
import { useAuthStore } from '../stores/auth';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import UserAvatar from '../components/ui/Cards/UserAvatar.vue';
import DataStoreGraphManager from '../components/datastores/DataStoreGraphManager.vue';
import JsonRenderer from '../components/ui/JsonRenderer.vue';

// Icons
import IconDatabase from '../assets/icons/IconDatabase.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconShare from '../assets/icons/IconShare.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';
import IconEye from '../assets/icons/IconEye.vue';
import IconEyeOff from '../assets/icons/IconEyeOff.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const adminStore = useAdminStore();
const authStore = useAuthStore();
const router = useRouter();

const { user } = storeToRefs(authStore);
const { ownedDataStores, sharedDataStores, availableVectorizers } = storeToRefs(dataStore);
const { tasks } = storeToRefs(tasksStore);

const selectedStoreId = ref(null);
const isLoadingAction = ref(null);
const activeTab = ref('documents');
const isAddFormVisible = ref(false);
const newStoreForm = ref({ name: '', description: '', selectedVectorizerKey: null, config: {}, chunk_size: 1024, chunk_overlap: 256 });
const isKeyVisible = ref({});
const filesInSelectedStore = ref([]);
const filesLoading = ref(false);
const selectedFilesToUpload = ref([]);
const fileInputRef = ref(null);
const currentUploadTask = ref(null);
const currentGraphTask = ref(null);
const dragOver = ref(false);
const vectorizerModels = ref([]);
const isLoadingVectorizerModels = ref(false);

const vectorizerOptions = computed(() => {
    const options = [];
    const aliases = availableVectorizers.value.filter(v => v.is_alias);
    const rawVectorizers = availableVectorizers.value.filter(v => !v.is_alias);
    if (aliases.length > 0) {
        options.push({ isGroup: true, label: 'Configured Bindings', items: aliases.map(v => ({ id: `alias:${v.name}`, name: v.name, description: v.title, isAlias: true, ...v })) });
    }
    if (rawVectorizers.length > 0) {
        options.push({ isGroup: true, label: 'Raw Vectorizers', items: rawVectorizers.map(v => ({ id: v.name, name: v.name, description: v.title, isAlias: false, ...v })) });
    }
    return options;
});

const selectedVectorizerDetails = computed(() => {
    if (!newStoreForm.value.selectedVectorizerKey) return null;
    for (const group of vectorizerOptions.value) {
        const found = group.items.find(item => item.id === newStoreForm.value.selectedVectorizerKey);
        if (found) return found;
    }
    return null;
});

const allDataStores = computed(() => [...ownedDataStores.value, ...sharedDataStores.value].sort((a, b) => a.name.localeCompare(b.name)));
const myDataStores = computed(() => ownedDataStores.value.sort((a, b) => a.name.localeCompare(b.name)));
const currentSelectedStore = computed(() => allDataStores.value.find(s => s.id === selectedStoreId.value));
const isAnyTaskRunningForSelectedStore = computed(() => !!currentUploadTask.value || !!currentGraphTask.value);

let taskPollingInterval;
onMounted(() => {
    dataStore.fetchDataStores();
    dataStore.fetchAvailableVectorizers();
    tasksStore.fetchTasks();
    taskPollingInterval = setInterval(tasksStore.fetchTasks, 3000);
});
onUnmounted(() => clearInterval(taskPollingInterval));

watch(tasks, (newTasks) => {
    if (!currentSelectedStore.value) { currentUploadTask.value = null; currentGraphTask.value = null; return; }
    const storeName = currentSelectedStore.value.name;
    const findLatestTask = (namePrefix) => newTasks.filter(task => task.name.startsWith(namePrefix) && task.name.includes(storeName) && (task.status === 'running' || task.status === 'pending')).sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0] || null;
    const latestUploadTask = findLatestTask('Add files to DataStore:');
    const latestGraphTask = findLatestTask('Generate Graph for:') || findLatestTask('Update Graph for:');
    const taskJustFinished = (currentTask, latestTask) => currentTask && !latestTask && (currentTask.status === 'running' || currentTask.status === 'pending');
    if (taskJustFinished(currentUploadTask.value, latestUploadTask)) { fetchFilesInStore(currentSelectedStore.value.id); }
    currentUploadTask.value = latestUploadTask;
    currentGraphTask.value = latestGraphTask;
}, { deep: true });

watch(selectedStoreId, (newId) => {
    isAddFormVisible.value = false;
    if (newId) {
        activeTab.value = 'documents';
        fetchFilesInStore(newId);
    } else {
        filesInSelectedStore.value = [];
    }
}, { immediate: true });

watch(selectedVectorizerDetails, async (details) => {
    newStoreForm.value.config = {};
    vectorizerModels.value = [];
    if (!details) return;
    if (details.isAlias) { newStoreForm.value.config = { ...(details.vectorizer_config || {}) }; } 
    else { (details.input_parameters || []).forEach(param => { newStoreForm.value.config[param.name] = param.default; }); }
    const modelParam = (details.input_parameters || []).find(p => p.name === 'model');
    if (modelParam && !details.isAlias) {
        isLoadingVectorizerModels.value = true;
        try {
            const vectorizerType = details.vectorizer_name || details.name;
            const models = await adminStore.fetchRagModelsForType(vectorizerType);
            vectorizerModels.value = Array.isArray(models) ? models : [];
        } catch (error) {
            console.error("Failed to fetch vectorizer models:", error);
            vectorizerModels.value = [];
        } finally {
            isLoadingVectorizerModels.value = false;
        }
    }
}, { deep: true });

function selectStore(storeId) { selectedStoreId.value = storeId; }
function handleAddStoreClick() {
    isAddFormVisible.value = true;
    selectedStoreId.value = null;
    newStoreForm.value = { 
        name: '', 
        description: '', 
        selectedVectorizerKey: null, 
        config: {},
        chunk_size: user.value?.default_chunk_size || 1024,
        chunk_overlap: user.value?.default_chunk_overlap || 256
    };
}
async function handleAddStore() {
    if (!newStoreForm.value.name.trim() || !selectedVectorizerDetails.value) { uiStore.addNotification('Name and vectorizer are required.', 'warning'); return; }
    isLoadingAction.value = 'add_store';
    try {
        const payload = {
            name: newStoreForm.value.name,
            description: newStoreForm.value.description,
            vectorizer_name: selectedVectorizerDetails.value.isAlias ? selectedVectorizerDetails.value.vectorizer_name : selectedVectorizerDetails.value.name,
            vectorizer_config: newStoreForm.value.config || {},
            chunk_size: newStoreForm.value.chunk_size,
            chunk_overlap: newStoreForm.value.chunk_overlap
        };
        const newStore = await dataStore.addDataStore(payload);
        newStoreForm.value = { name: '', description: '', selectedVectorizerKey: null, config: {}, chunk_size: 1024, chunk_overlap: 256 };
        isAddFormVisible.value = false;
        await dataStore.fetchDataStores();
        if (newStore && newStore.id) {
            selectStore(newStore.id);
        }
    } finally { isLoadingAction.value = null; }
}
function handleEditStore(store) { uiStore.openModal('editDataStore', { store }); }
async function handleDeleteStore(store) {
    const confirmed = await uiStore.showConfirmation({ title: `Delete Data Store '${store.name}'?`, message: 'This will permanently delete the data store and all its indexed documents.', confirmText: 'Delete' });
    if (confirmed.confirmed) {
        isLoadingAction.value = `delete_store_${store.id}`;
        try { await dataStore.deleteDataStore(store.id); if (selectedStoreId.value === store.id) selectedStoreId.value = null; } 
        finally { isLoadingAction.value = null; }
    }
}
function handleShareStore(store) { uiStore.openModal('shareDataStore', { store }); }
function handleFileDrop(event) { event.preventDefault(); dragOver.value = false; addFilesToSelection(Array.from(event.dataTransfer.files)); }
function handleFileChange(event) { addFilesToSelection(Array.from(event.target.files)); }
function addFilesToSelection(newFiles) {
    for (const file of newFiles) {
        if (!selectedFilesToUpload.value.some(f => f.name === file.name && f.size === file.size)) selectedFilesToUpload.value.push(file);
        else uiStore.addNotification(`File "${file.name}" is already selected.`, 'warning');
    }
    if (fileInputRef.value) fileInputRef.value.value = '';
}
function removeFileFromSelection(index) { selectedFilesToUpload.value.splice(index, 1); }
async function fetchFilesInStore(storeId) { filesLoading.value = true; try { filesInSelectedStore.value = await dataStore.fetchStoreFiles(storeId); } finally { filesLoading.value = false; } }
async function handleUploadFiles() {
    if (!currentSelectedStore.value || selectedFilesToUpload.value.length === 0) { uiStore.addNotification('Please select files to upload.', 'warning'); return; }
    if (isAnyTaskRunningForSelectedStore.value) { uiStore.addNotification('A task is already running for this Data Store.', 'warning'); return; }
    const formData = new FormData();
    selectedFilesToUpload.value.forEach(file => formData.append('files', file));
    await dataStore.uploadFilesToStore({ storeId: currentSelectedStore.value.id, formData });
    selectedFilesToUpload.value = [];
}
async function handleDeleteFile(filename) {
    if (!currentSelectedStore.value || !filename) return;
    const confirmed = await uiStore.showConfirmation({ title: `Delete '${filename}'?`, message: 'This will remove the document.', confirmText: 'Delete File' });
    if (confirmed) {
        isLoadingAction.value = `delete_file_${filename}`;
        try { await dataStore.deleteFileFromStore({ storeId: currentSelectedStore.value.id, filename }); await fetchFilesInStore(currentSelectedStore.value.id); } 
        finally { isLoadingAction.value = null; }
    }
}
function canReadWrite(store) { return store && ['owner', 'read_write', 'revectorize'].includes(store.permission_level); }
</script>

<template>
  <PageViewLayout title="Data Stores" :title-icon="IconDatabase">
    <template #sidebar>
        <button @click="handleAddStoreClick" class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/50 transition-colors">
            <IconPlus class="w-5 h-5 flex-shrink-0" />
            <span>New Data Store</span>
        </button>
        <button @click="dataStore.fetchDataStores()" class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors mt-2">
            <IconRefresh class="w-5 h-5 flex-shrink-0" />
            <span>Refresh All Stores</span>
        </button>
        <h3 class="text-sm font-semibold uppercase text-gray-500 dark:text-gray-400 mt-4 px-3">Your Stores</h3>
        <ul class="space-y-1 mt-2">
            <li v-for="store in myDataStores" :key="store.id">
                <button @click="selectStore(store.id)" class="w-full flex items-center justify-between text-left px-3 py-2 rounded-lg text-sm transition-colors group" :class="{'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300': selectedStoreId === store.id, 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700': selectedStoreId !== store.id}">
                    <span class="truncate">{{ store.name }}</span>
                    <span class="ml-2 text-xs px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">Owner</span>
                </button>
            </li>
        </ul>
        <h3 class="text-sm font-semibold uppercase text-gray-500 dark:text-gray-400 mt-4 px-3">Shared With You</h3>
        <ul class="space-y-1 mt-2">
            <li v-for="store in sharedDataStores" :key="store.id">
                <button @click="selectStore(store.id)" class="w-full flex items-center justify-between text-left px-3 py-2 rounded-lg text-sm transition-colors group" :class="{'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300': selectedStoreId === store.id, 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700': selectedStoreId !== store.id}">
                    <span class="truncate">{{ store.name }}</span>
                    <span class="ml-2 text-xs px-2 py-0.5 rounded-full" :class="{ 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300': store.permission_level === 'revectorize', 'bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300': store.permission_level === 'read_write', 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300': store.permission_level === 'read_query' }">
                        {{ store.permission_level.replace('_', ' ') }}
                    </span>
                </button>
            </li>
        </ul>
    </template>
    <template #main>
        <div v-if="isAddFormVisible" class="p-4 sm:p-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm h-full overflow-y-auto">
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Create New Data Store</h2>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">A Data Store turns your documents into a queryable knowledge base.</p>
            <form @submit.prevent="handleAddStore" class="mt-6 space-y-6">
                <div>
                    <label for="new-ds-name" class="block text-sm font-medium">Name</label>
                    <input id="new-ds-name" v-model="newStoreForm.name" type="text" class="input-field mt-1" required>
                </div>
                <div>
                    <label for="new-ds-desc" class="block text-sm font-medium">Description</label>
                    <textarea id="new-ds-desc" v-model="newStoreForm.description" rows="2" class="input-field mt-1"></textarea>
                </div>

                <div v-if="user && user.allow_user_chunking_config" class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label for="new-ds-chunk-size" class="block text-sm font-medium">Chunk Size</label>
                        <input id="new-ds-chunk-size" v-model.number="newStoreForm.chunk_size" type="number" min="1" class="input-field mt-1">
                        <p class="text-xs text-gray-500 mt-1">Number of characters per data chunk.</p>
                    </div>
                    <div>
                        <label for="new-ds-chunk-overlap" class="block text-sm font-medium">Chunk Overlap</label>
                        <input id="new-ds-chunk-overlap" v-model.number="newStoreForm.chunk_overlap" type="number" min="0" class="input-field mt-1">
                         <p class="text-xs text-gray-500 mt-1">Number of overlapping characters between chunks.</p>
                    </div>
                </div>

                <div>
                    <label for="new-ds-vectorizer" class="block text-sm font-medium">Vectorizer</label>
                    <select id="new-ds-vectorizer" v-model="newStoreForm.selectedVectorizerKey" class="input-field mt-1">
                        <option :value="null" disabled>-- Select a Vectorizer or Alias --</option>
                        <template v-for="group in vectorizerOptions">
                            <optgroup :label="group.label">
                                <option v-for="item in group.items" :key="item.id" :value="item.id">{{ item.name }} - <span class="text-gray-400">{{ item.description }}</span></option>
                            </optgroup>
                        </template>
                    </select>
                </div>
                <div v-if="selectedVectorizerDetails" class="p-4 border dark:border-gray-700 rounded-lg space-y-4">
                    <h4 class="font-medium text-lg">{{ selectedVectorizerDetails.title || selectedVectorizerDetails.name }}</h4>
                    <p class="text-sm text-gray-500">{{ selectedVectorizerDetails.description }}</p>
                    <div v-if="selectedVectorizerDetails.input_parameters?.length > 0" class="space-y-4">
                        <div v-for="param in selectedVectorizerDetails.input_parameters" :key="param.name">
                            <div v-if="!(selectedVectorizerDetails.isAlias && param.name === 'model')">
                                <label :for="`param-${param.name}`" class="block text-sm font-medium">{{ param.name }} <span v-if="param.mandatory" class="text-red-500">*</span></label>
                                <div v-if="param.name === 'model'">
                                    <select v-if="!isLoadingVectorizerModels && vectorizerModels.length > 0" v-model="newStoreForm.config.model" class="input-field mt-1">
                                        <option v-for="modelName in vectorizerModels" :key="modelName" :value="modelName">{{ modelName }}</option>
                                    </select>
                                    <input v-else type="text" v-model="newStoreForm.config.model" class="input-field mt-1" :placeholder="isLoadingVectorizerModels ? 'Loading models...' : 'Enter model name'">
                                </div>
                                <div v-else class="relative mt-1">
                                    <input :type="(param.name.includes('key') || param.name.includes('token')) && !isKeyVisible[param.name] ? 'password' : 'text'" v-model="newStoreForm.config[param.name]" class="input-field pr-10" :placeholder="param.description">
                                    <button v-if="param.name.includes('key') || param.name.includes('token')" type="button" @click="isKeyVisible[param.name] = !isKeyVisible[param.name]" class="absolute inset-y-0 right-0 px-3 flex items-center text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" :title="isKeyVisible[param.name] ? 'Hide' : 'Show'">
                                        <IconEyeOff v-if="isKeyVisible[param.name]" class="w-5 h-5" /><IconEye v-else class="w-5 h-5" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    <p v-else class="text-sm text-gray-500 italic">This vectorizer requires no additional configuration.</p>
                </div>
                <div class="flex justify-end gap-3"><button type="button" @click="isAddFormVisible=false; selectStore(myDataStores[0]?.id)" class="btn btn-secondary">Cancel</button><button type="submit" class="btn btn-primary" :disabled="isLoadingAction === 'add_store'">{{ isLoadingAction === 'add_store' ? 'Creating...' : 'Create Data Store' }}</button></div>
            </form>
        </div>
        <div v-else-if="!selectedStoreId" class="h-full flex items-center justify-center bg-white dark:bg-gray-800 rounded-lg shadow-sm">
            <div class="text-center">
                <IconDatabase class="mx-auto h-12 w-12 text-gray-400" />
                <h3 class="mt-2 text-xl font-semibold text-gray-900 dark:text-white">Select a Data Store</h3>
                <p class="mt-1 text-sm text-gray-500">Choose a store from the sidebar or create a new one to begin.</p>
            </div>
        </div>
        <div v-else-if="!currentSelectedStore" class="text-center py-20 bg-white dark:bg-gray-800 rounded-lg shadow-sm">
            <h3 class="text-xl font-semibold text-gray-700 dark:text-gray-200">Data Store Not Found</h3>
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">The selected data store could not be loaded.</p>
        </div>
        <div v-else class="bg-white dark:bg-gray-800 rounded-lg shadow-md h-full overflow-hidden flex flex-col">
            <div class="p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-start flex-wrap gap-4">
                <div>
                    <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{{ currentSelectedStore.name }}</h2>
                    <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{{ currentSelectedStore.description || 'No description provided.' }}</p>
                    <div class="flex items-center text-xs text-gray-500 dark:text-gray-400 mt-2">
                        <span class="mr-1">Owner:</span><UserAvatar :username="currentSelectedStore.owner_username" size-class="h-4 w-4" class="mr-1" /><span>{{ currentSelectedStore.owner_username }}</span>
                    </div>
                    <div class="mt-2 text-xs font-mono p-2 bg-gray-100 dark:bg-gray-700/50 rounded-md">
                        <p><span class="font-semibold">Vectorizer:</span> {{ currentSelectedStore.vectorizer_name }}</p>
                        <p><span class="font-semibold">Chunking:</span> {{ currentSelectedStore.chunk_size }} / {{ currentSelectedStore.chunk_overlap }}</p>
                        <details v-if="Object.keys(currentSelectedStore.vectorizer_config).length > 0" class="mt-1"><summary class="cursor-pointer text-gray-500">View Config</summary><JsonRenderer :json="currentSelectedStore.vectorizer_config" class="mt-1 text-xs" /></details>
                    </div>
                </div>
                <div class="flex items-center space-x-3 flex-shrink-0">
                    <button v-if="currentSelectedStore.permission_level === 'owner'" @click="handleShareStore(currentSelectedStore)" class="btn btn-secondary btn-sm"><IconShare class="w-4 h-4 mr-2" /> Share</button>
                    <button v-if="canReadWrite(currentSelectedStore)" @click="handleEditStore(currentSelectedStore)" class="btn btn-secondary btn-sm"><IconPencil class="w-4 h-4 mr-2" /> Edit</button>
                    <button v-if="currentSelectedStore.permission_level === 'owner'" @click="handleDeleteStore(currentSelectedStore)" class="btn btn-danger btn-sm"><IconTrash class="w-4 h-4 mr-2" /> Delete</button>
                </div>
            </div>
            <div class="border-b border-gray-200 dark:border-gray-700 px-6">
                <nav class="-mb-px flex space-x-6" aria-label="Tabs">
                    <button @click="activeTab = 'documents'" :class="['tab-button', activeTab === 'documents' ? 'active' : 'inactive']">Documents</button>
                    <button @click="activeTab = 'graph'" :class="['tab-button', activeTab === 'graph' ? 'active' : 'inactive']">Graph</button>
                </nav>
            </div>
            <div v-show="activeTab === 'documents'" class="p-6 flex-grow overflow-y-auto space-y-8">
                <div v-if="canReadWrite(currentSelectedStore)" class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-6 space-y-4">
                    <h3 class="text-xl font-semibold text-gray-900 dark:text-white">Add Documents</h3>
                    <div @dragover.prevent="dragOver = true" @dragleave.prevent="dragOver = false" @drop.prevent="handleFileDrop" @click="fileInputRef.click()" class="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors" :class="{ 'border-blue-500 bg-blue-50 dark:bg-blue-900/20': dragOver, 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500': !dragOver }">
                        <input type="file" multiple ref="fileInputRef" @change="handleFileChange" class="hidden" accept="*/*"><p class="text-gray-600 dark:text-gray-300">Drag & drop files here, or <span class="text-blue-600 dark:text-blue-400 font-medium">click to browse</span></p>
                    </div>
                    <div v-if="selectedFilesToUpload.length > 0">
                        <h4 class="text-sm font-medium mb-2">Selected for Upload ({{ selectedFilesToUpload.length }})</h4>
                        <ul class="list-disc list-inside text-sm space-y-1 max-h-40 overflow-y-auto">
                            <li v-for="(file, index) in selectedFilesToUpload" :key="index" class="flex justify-between items-center bg-gray-100 dark:bg-gray-800 p-2 rounded"><span class="truncate">{{ file.name }} ({{ (file.size / 1024 / 1024).toFixed(2) }} MB)</span><button @click="removeFileFromSelection(index)" class="text-red-500 hover:text-red-700 ml-2" title="Remove"><IconXMark class="w-4 h-4" /></button></li>
                        </ul>
                    </div>
                    <div class="flex justify-end items-center">
                        <button @click="handleUploadFiles" class="btn btn-primary" :disabled="isAnyTaskRunningForSelectedStore || selectedFilesToUpload.length === 0">
                            <IconArrowUpTray class="w-5 h-5 mr-2" /> Add {{ selectedFilesToUpload.length }} File(s)
                        </button>
                    </div>
                </div>
                <div v-if="currentUploadTask" class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-700"> ... </div>
                <div>
                    <h3 class="text-xl font-semibold mb-4">Indexed Documents ({{ filesInSelectedStore.length }})</h3>
                    <div v-if="filesLoading" class="text-center py-10"><p>Loading documents...</p></div>
                    <div v-else-if="filesInSelectedStore.length === 0" class="text-center py-10 bg-gray-50 dark:bg-gray-800/50 rounded-lg"><p>No documents indexed.</p></div>
                    <ul v-else class="divide-y divide-gray-200 dark:divide-gray-700">
                        <li v-for="file in filesInSelectedStore" :key="file.filename" class="py-3 flex items-center justify-between">
                            <span class="text-sm font-medium truncate flex-grow mr-4">{{ file.filename }}</span>
                            <button v-if="canReadWrite(currentSelectedStore)" @click="handleDeleteFile(file.filename)" class="btn btn-danger btn-sm p-1.5" :disabled="isLoadingAction === `delete_file_${file.filename}`"><IconTrash class="w-4 h-4" /></button>
                        </li>
                    </ul>
                </div>
            </div>
            <div v-if="activeTab === 'graph'" class="p-6 flex-grow overflow-y-auto">
                <DataStoreGraphManager :store="currentSelectedStore" :task="currentGraphTask" />
            </div>
        </div>
    </template>
  </PageViewLayout>
</template>

<style scoped>
.tab-button { @apply px-1 py-4 text-sm font-medium border-b-2; }
.tab-button.active { @apply border-blue-500 text-blue-600 dark:text-blue-400; }
.tab-button.inactive { @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600; }
</style>