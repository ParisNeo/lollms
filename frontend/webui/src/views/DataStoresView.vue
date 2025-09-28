<script setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useTasksStore } from '../stores/tasks';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import UserAvatar from '../components/ui/Cards/UserAvatar.vue';
import DataStoreGraphManager from '../components/datastores/DataStoreGraphManager.vue';
import IconDatabase from '../assets/icons/IconDatabase.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconShare from '../assets/icons/IconShare.vue';
import IconArrowPath from '../assets/icons/IconArrowPath.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconInfo from '../assets/icons/IconInfo.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';
import IconCog from '../assets/icons/IconCog.vue';
import IconChevronDown from '../assets/icons/IconChevronDown.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const router = useRouter();

const { ownedDataStores, sharedDataStores } = storeToRefs(dataStore);
const { tasks } = storeToRefs(tasksStore);

const selectedStoreId = ref(null);
const newStoreName = ref('');
const newStoreDescription = ref('');
const isAddFormVisible = ref(false);
const isLoadingAction = ref(null);
const activeTab = ref('documents');

const filesInSelectedStore = ref([]);
const filesLoading = ref(false);
const selectedFilesToUpload = ref([]);
const fileInputRef = ref(null);
const currentVectorizer = ref('');
const availableVectorizers = ref({ in_store: [], all_possible: [] });

const currentUploadTask = ref(null);
const currentRevectorizeTask = ref(null);
const currentGraphTask = ref(null);

const showAllPossibleVectorizersForSelection = ref(false);
const showRevectorizePanel = ref(false);

const allDataStores = computed(() => {
    return [...ownedDataStores.value, ...sharedDataStores.value].sort((a, b) => a.name.localeCompare(b.name));
});

const myDataStores = computed(() => {
    return ownedDataStores.value.sort((a, b) => a.name.localeCompare(b.name));
});

const currentSelectedStore = computed(() => {
    return allDataStores.value.find(s => s.id === selectedStoreId.value);
});

const isAnyTaskRunningForSelectedStore = computed(() => {
    return !!currentUploadTask.value || !!currentRevectorizeTask.value || !!currentGraphTask.value;
});


let taskPollingInterval;

onMounted(() => {
    dataStore.fetchDataStores();
    tasksStore.fetchTasks();
    taskPollingInterval = setInterval(tasksStore.fetchTasks, 3000);
});

onUnmounted(() => {
    clearInterval(taskPollingInterval);
});

watch(tasks, (newTasks) => {
    if (!currentSelectedStore.value) {
        currentUploadTask.value = null;
        currentRevectorizeTask.value = null;
        currentGraphTask.value = null;
        return;
    }

    const storeName = currentSelectedStore.value.name;

    const findLatestTask = (namePrefix) => newTasks
        .filter(task =>
            task.name.startsWith(namePrefix) &&
            task.name.includes(storeName) &&
            (task.status === 'running' || task.status === 'pending')
        )
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0] || null;

    const latestUploadTask = findLatestTask('Add files to DataStore:');
    const latestRevectorizeTask = findLatestTask('Revectorize DataStore:');
    const latestGraphTask = findLatestTask('Generate Graph for:') || findLatestTask('Update Graph for:');


    const taskJustFinished = (currentTask, latestTask) => {
        return currentTask && !latestTask && (currentTask.status === 'running' || currentTask.status === 'pending');
    };

    if (taskJustFinished(currentUploadTask.value, latestUploadTask) || taskJustFinished(currentRevectorizeTask.value, latestRevectorizeTask)) {
        fetchFilesInStore(currentSelectedStore.value.id);
        fetchStoreVectorizers(currentSelectedStore.value.id);
    }
    
    currentUploadTask.value = latestUploadTask;
    currentRevectorizeTask.value = latestRevectorizeTask;
    currentGraphTask.value = latestGraphTask;

}, { deep: true });

watch(selectedStoreId, async (newId) => {
    if (newId) {
        activeTab.value = 'documents';
        await fetchFilesInStore(newId);
        await fetchStoreVectorizers(newId);
    } else {
        filesInSelectedStore.value = [];
        availableVectorizers.value = { in_store: [], all_possible: [] };
        currentVectorizer.value = '';
    }
}, { immediate: true });


const displayedVectorizerOptions = computed(() => {
    if (showAllPossibleVectorizersForSelection.value) {
        return availableVectorizers.value.all_possible;
    } else {
        return availableVectorizers.value.in_store;
    }
});

const canAddNewVectorizer = computed(() => {
    if (!currentSelectedStore.value) return false;
    if (!canRevectorize(currentSelectedStore.value)) return false;
    if (availableVectorizers.value.in_store.length === 0) return false;
    const inStoreNames = new Set(availableVectorizers.value.in_store.map(v => v.name));
    const hasNewOptions = availableVectorizers.value.all_possible.some(v => !inStoreNames.has(v.name));
    return !showAllPossibleVectorizersForSelection.value && hasNewOptions;
});

function selectStore(storeId) {
    selectedStoreId.value = storeId;
}

function handleAddStoreClick() {
    isAddFormVisible.value = !isAddFormVisible.value;
    if (!isAddFormVisible.value) {
        newStoreName.value = '';
        newStoreDescription.value = '';
    }
}

async function handleAddStore() {
    if (!newStoreName.value.trim()) {
        uiStore.addNotification('Data Store name is required.', 'warning');
        return;
    }
    isLoadingAction.value = 'add_store';
    try {
        await dataStore.addDataStore({ name: newStoreName.value, description: newStoreDescription.value });
        newStoreName.value = '';
        newStoreDescription.value = '';
        isAddFormVisible.value = false;
        await dataStore.fetchDataStores();
    } finally {
        isLoadingAction.value = null;
    }
}

function handleEditStore(store) {
    uiStore.openModal('editDataStore', { store });
}

async function handleDeleteStore(store) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Data Store '${store.name}'?`,
        message: 'This will permanently delete the data store and all its indexed documents. This action cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        isLoadingAction.value = `delete_store_${store.id}`;
        try {
            await dataStore.deleteDataStore(store.id);
            if (selectedStoreId.value === store.id) {
                selectedStoreId.value = null;
            }
        } finally {
            isLoadingAction.value = null;
        }
    }
}

function handleShareStore(store) {
    uiStore.openModal('shareDataStore', { store });
}

const dragOver = ref(false);

function handleFileDrop(event) {
    event.preventDefault();
    dragOver.value = false;
    const files = Array.from(event.dataTransfer.files);
    addFilesToSelection(files);
}

function handleFileChange(event) {
    const files = Array.from(event.target.files);
    addFilesToSelection(files);
}

function addFilesToSelection(newFiles) {
    for (const file of newFiles) {
        const isDuplicate = selectedFilesToUpload.value.some(
            (existingFile) => existingFile.name === file.name && existingFile.size === file.size
        );
        if (!isDuplicate) {
            selectedFilesToUpload.value.push(file);
        } else {
            uiStore.addNotification(`File "${file.name}" is already selected.`, 'warning');
        }
    }
    if (fileInputRef.value) {
        fileInputRef.value.value = '';
    }
}

function removeFileFromSelection(index) {
    selectedFilesToUpload.value.splice(index, 1);
}

async function fetchFilesInStore(storeId) {
    filesLoading.value = true;
    try {
        filesInSelectedStore.value = await dataStore.fetchStoreFiles(storeId);
    } catch (error) {
        filesInSelectedStore.value = [];
    } finally {
        filesLoading.value = false;
    }
}

async function fetchStoreVectorizers(storeId) {
    try {
        const fetchedVectorizers = await dataStore.fetchStoreVectorizers(storeId);
        availableVectorizers.value = fetchedVectorizers;
        
        showAllPossibleVectorizersForSelection.value = fetchedVectorizers.in_store.length === 0;

        if (fetchedVectorizers.in_store.length > 0 && !showAllPossibleVectorizersForSelection.value) {
            currentVectorizer.value = fetchedVectorizers.in_store[0].name;
        } 
        else if (fetchedVectorizers.all_possible.length > 0) {
            currentVectorizer.value = fetchedVectorizers.all_possible[0].name;
        } 
        else {
            currentVectorizer.value = ''; 
        }
    } catch (error) {
        availableVectorizers.value = { in_store: [], all_possible: [] };
        currentVectorizer.value = '';
    }
}

function toggleVectorizerSelectionMode() {
    showAllPossibleVectorizersForSelection.value = !showAllPossibleVectorizersForSelection.value;
    if (showAllPossibleVectorizersForSelection.value && availableVectorizers.value.all_possible.length > 0) {
        currentVectorizer.value = availableVectorizers.value.all_possible[0].name;
    } else if (!showAllPossibleVectorizersForSelection.value && availableVectorizers.value.in_store.length > 0) {
        currentVectorizer.value = availableVectorizers.value.in_store[0].name;
    } else {
        currentVectorizer.value = '';
    }
}


async function handleUploadFiles() {
    if (!currentSelectedStore.value || selectedFilesToUpload.value.length === 0 || !currentVectorizer.value) {
        uiStore.addNotification('Please select files and a vectorizer.', 'warning');
        return;
    }
    if (isAnyTaskRunningForSelectedStore.value) {
        uiStore.addNotification('A task is already running for this Data Store. Please wait.', 'warning');
        return;
    }

    try {
        const formData = new FormData();
        selectedFilesToUpload.value.forEach(file => {
            formData.append('files', file);
        });
        formData.append('vectorizer_name', currentVectorizer.value);

        await dataStore.uploadFilesToStore({
            storeId: currentSelectedStore.value.id,
            formData: formData
        });
        selectedFilesToUpload.value = [];
    } catch (error) {
    }
}

async function handleDeleteFile(filename) {
    if (!currentSelectedStore.value || !filename) return;

    const confirmed = await uiStore.showConfirmation({
        title: `Delete '${filename}'?`,
        message: 'This will remove the document from the data store. This action cannot be undone.',
        confirmText: 'Delete File'
    });

    if (confirmed) {
        isLoadingAction.value = `delete_file_${filename}`;
        try {
            await dataStore.deleteFileFromStore({
                storeId: currentSelectedStore.value.id,
                filename: filename
            });
            await fetchFilesInStore(currentSelectedStore.value.id);
        } finally {
            isLoadingAction.value = null;
        }
    }
}

async function handleRevectorize() {
    if (!currentSelectedStore.value || !currentVectorizer.value) {
        uiStore.addNotification('Please select a vectorizer to re-index with.', 'warning');
        return;
    }
    if (isAnyTaskRunningForSelectedStore.value) {
        uiStore.addNotification('A task is already running for this Data Store. Please wait.', 'warning');
        return;
    }
    
    try {
        await dataStore.revectorizeStore({
            storeId: currentSelectedStore.value.id,
            vectorizerName: currentVectorizer.value
        });
    } catch (error) {
    }
}

function canReadWrite(store) {
    if (!store) return false;
    return ['owner', 'read_write', 'revectorize'].includes(store.permission_level);
}
function canRevectorize(store) {
    if (!store) return false;
    return store.permission_level === 'owner' || store.permission_level === 'revectorize';
}
</script>

<template>
  <PageViewLayout title="Data Stores" :title-icon="IconDatabase">
    <template #sidebar>
        <button @click="handleAddStoreClick" class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/50 transition-colors">
            <IconPlus class="w-5 h-5 flex-shrink-0" />
            <span>New Data Store</span>
        </button>
        <transition
            enter-active-class="transition ease-out duration-200"
            enter-from-class="opacity-0 -translate-y-2"
            enter-to-class="opacity-100 translate-y-0"
            leave-active-class="transition ease-in duration-150"
            leave-from-class="opacity-100 translate-y-0"
            leave-to-class="opacity-0 -translate-y-2"
        >
            <div v-if="isAddFormVisible" class="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg my-2 space-y-3">
                <input type="text" v-model="newStoreName" placeholder="Data Store Name" class="input-field">
                <textarea v-model="newStoreDescription" placeholder="Description (optional)" rows="2" class="input-field"></textarea>
                <button @click="handleAddStore" class="btn btn-primary w-full" :disabled="isLoadingAction === 'add_store'">
                    {{ isLoadingAction === 'add_store' ? 'Creating...' : 'Create' }}
                </button>
            </div>
        </transition>

        <button @click="dataStore.fetchDataStores()" class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors mt-2">
            <IconRefresh class="w-5 h-5 flex-shrink-0" />
            <span>Refresh All Stores</span>
        </button>

        <h3 class="text-sm font-semibold uppercase text-gray-500 dark:text-gray-400 mt-4 px-3">Your Stores</h3>
        <ul class="space-y-1 mt-2">
            <li v-for="store in myDataStores" :key="store.id">
                <button @click="selectStore(store.id)" 
                        class="w-full flex items-center justify-between text-left px-3 py-2 rounded-lg text-sm transition-colors group"
                        :class="{'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300': selectedStoreId === store.id, 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700': selectedStoreId !== store.id}">
                    <span class="truncate">{{ store.name }}</span>
                    <span class="ml-2 text-xs px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">Owner</span>
                </button>
            </li>
        </ul>

        <h3 class="text-sm font-semibold uppercase text-gray-500 dark:text-gray-400 mt-4 px-3">Shared With You</h3>
        <ul class="space-y-1 mt-2">
            <li v-for="store in sharedDataStores" :key="store.id">
                <button @click="selectStore(store.id)" 
                        class="w-full flex items-center justify-between text-left px-3 py-2 rounded-lg text-sm transition-colors group"
                        :class="{'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300': selectedStoreId === store.id, 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700': selectedStoreId !== store.id}">
                    <span class="truncate">{{ store.name }}</span>
                    <span class="ml-2 text-xs px-2 py-0.5 rounded-full"
                          :class="{
                            'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300': store.permission_level === 'revectorize',
                            'bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300': store.permission_level === 'read_write',
                            'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300': store.permission_level === 'read_query'
                          }">
                        {{ store.permission_level.replace('_', ' ') }}
                    </span>
                </button>
            </li>
        </ul>
    </template>
    <template #main>
        <div v-if="!selectedStoreId" class="text-center py-20 bg-white dark:bg-gray-800 rounded-lg shadow-sm">
            <h3 class="text-xl font-semibold text-gray-700 dark:text-gray-200">Select a Data Store</h3>
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">Choose a data store from the sidebar to manage its documents.</p>
        </div>
        <div v-else-if="!currentSelectedStore" class="text-center py-20 bg-white dark:bg-gray-800 rounded-lg shadow-sm">
            <h3 class="text-xl font-semibold text-gray-700 dark:text-gray-200">Data Store Not Found</h3>
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">The selected data store could not be loaded.</p>
        </div>
        <div v-else class="bg-white dark:bg-gray-800 rounded-lg shadow-md h-full overflow-hidden flex flex-col">
            <div class="p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center flex-wrap gap-4">
                <div>
                    <h2 class="text-2xl font-bold text-gray-900 dark:text-white">{{ currentSelectedStore.name }}</h2>
                    <p class="text-sm text-gray-500 dark:text-gray-400">{{ currentSelectedStore.description || 'No description provided.' }}</p>
                     <div class="flex items-center text-xs text-gray-500 dark:text-gray-400 mt-2">
                        <span class="mr-1">Owner:</span>
                        <UserAvatar :username="currentSelectedStore.owner_username" size-class="h-4 w-4" class="mr-1" />
                        <span>{{ currentSelectedStore.owner_username }}</span>
                    </div>
                </div>
                <div class="flex items-center space-x-3 flex-shrink-0">
                    <button v-if="currentSelectedStore.permission_level === 'owner'" @click="handleShareStore(currentSelectedStore)" class="btn btn-secondary btn-sm">
                        <IconShare class="w-4 h-4 mr-2" /> Share
                    </button>
                    <button v-if="canReadWrite(currentSelectedStore)" @click="handleEditStore(currentSelectedStore)" class="btn btn-secondary btn-sm">
                        <IconPencil class="w-4 h-4 mr-2" /> Edit
                    </button>
                    <button v-if="currentSelectedStore.permission_level === 'owner'" @click="handleDeleteStore(currentSelectedStore)" class="btn btn-danger btn-sm">
                        <IconTrash class="w-4 h-4 mr-2" /> Delete
                    </button>
                    <button @click="fetchFilesInStore(currentSelectedStore.id)" class="btn btn-secondary btn-sm" :disabled="filesLoading || isAnyTaskRunningForSelectedStore">
                        <IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': filesLoading || isAnyTaskRunningForSelectedStore}" /> Refresh Files
                    </button>
                </div>
            </div>

            <div class="border-b border-gray-200 dark:border-gray-700 px-6">
                <nav class="-mb-px flex space-x-6" aria-label="Tabs">
                    <button @click="activeTab = 'documents'" :class="['tab-button', activeTab === 'documents' ? 'active' : 'inactive']">Documents</button>
                    <button @click="activeTab = 'graph'" :class="['tab-button', activeTab === 'graph' ? 'active' : 'inactive']">Graph</button>
                </nav>
            </div>
            
            <div v-show="activeTab === 'documents'" class="p-6 flex-grow overflow-y-auto space-y-8">
                <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-6 space-y-4">
                    <h3 class="text-xl font-semibold text-gray-900 dark:text-white">Active Vectorizers</h3>
                    <p v-if="availableVectorizers.in_store.length === 0" class="text-sm text-gray-500 dark:text-gray-400">
                        No vectorizers are currently in use. Add documents to define one.
                    </p>
                    <ul v-else class="space-y-2">
                        <li v-for="vec in availableVectorizers.in_store" :key="vec.name" class="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                            <IconCheckCircle class="w-4 h-4 text-green-500" />
                            <span>{{ vec.method_name }}</span>
                        </li>
                    </ul>
                </div>

                <div v-if="canReadWrite(currentSelectedStore)" class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-6 space-y-4">
                    <h3 class="text-xl font-semibold text-gray-900 dark:text-white">Add Documents</h3>
                    <div @dragover.prevent="dragOver = true" @dragleave.prevent="dragOver = false" @drop.prevent="handleFileDrop" @click="fileInputRef.click()" class="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors" :class="{ 'border-blue-500 bg-blue-50 dark:bg-blue-900/20': dragOver, 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500': !dragOver }">
                        <input type="file" multiple ref="fileInputRef" @change="handleFileChange" class="hidden" accept="*/*">
                        <p class="text-gray-600 dark:text-gray-300">Drag & drop files here, or <span class="text-blue-600 dark:text-blue-400 font-medium">click to browse</span></p>
                    </div>

                    <div v-if="selectedFilesToUpload.length > 0">
                        <h4 class="text-sm font-medium mb-2">Selected for Upload ({{ selectedFilesToUpload.length }})</h4>
                        <ul class="list-disc list-inside text-sm space-y-1">
                            <li v-for="(file, index) in selectedFilesToUpload" :key="index" class="flex justify-between items-center bg-gray-100 dark:bg-gray-800 p-2 rounded">
                                <span class="truncate">{{ file.name }} ({{ (file.size / 1024 / 1024).toFixed(2) }} MB)</span>
                                <button @click="removeFileFromSelection(index)" class="text-red-500 hover:text-red-700 ml-2" title="Remove"><IconXMark class="w-4 h-4" /></button>
                            </li>
                        </ul>
                    </div>
                    
                    <div>
                        <label for="upload-vectorizer" class="block text-sm font-medium">Vectorizer</label>
                        <div class="flex items-center space-x-2 mt-1">
                            <select id="upload-vectorizer" v-model="currentVectorizer" class="input-field flex-grow" :disabled="displayedVectorizerOptions.length === 0">
                                <option value="">Select a vectorizer</option>
                                <option v-for="vec in displayedVectorizerOptions" :key="vec.name" :value="vec.name">{{ vec.method_name }}</option>
                            </select>
                            <button v-if="canAddNewVectorizer" @click="toggleVectorizerSelectionMode" type="button" class="btn btn-secondary btn-sm">+ Add New</button>
                             <button v-else-if="showAllPossibleVectorizersForSelection && availableVectorizers.in_store.length > 0" @click="toggleVectorizerSelectionMode" type="button" class="btn btn-secondary btn-sm">Show Active</button>
                        </div>
                    </div>

                    <div class="flex justify-between items-center">
                        <div v-if="currentUploadTask" class="flex flex-col items-start w-full"> ... </div>
                        <button @click="handleUploadFiles" class="btn btn-primary ml-auto" :disabled="isAnyTaskRunningForSelectedStore || selectedFilesToUpload.length === 0 || !currentVectorizer">
                            <IconArrowUpTray class="w-5 h-5 mr-2" /> Add Selected Files
                        </button>
                    </div>
                </div>

                <div v-if="canRevectorize(currentSelectedStore)" class="flex justify-between items-center">
                    <h3 class="text-xl font-semibold">Re-Index / Revectorize</h3>
                    <button @click="showRevectorizePanel = !showRevectorizePanel" class="btn btn-secondary btn-sm">
                        <IconCog class="w-4 h-4 mr-2" /> Re-index Settings <IconChevronDown class="w-4 h-4 ml-2 transition-transform" :class="{'rotate-180': showRevectorizePanel}" />
                    </button>
                </div>

                <transition enter-active-class="transition ease-out duration-200" enter-from-class="opacity-0 -translate-y-2" enter-to-class="opacity-100 translate-y-0" leave-active-class="transition ease-in duration-150" leave-from-class="opacity-100 translate-y-0" leave-to-class="opacity-0 -translate-y-2">
                    <div v-if="canRevectorize(currentSelectedStore) && showRevectorizePanel" class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-6 space-y-4">
                        <div class="flex justify-between items-center">
                            <div v-if="currentRevectorizeTask"> ... </div>
                            <button @click="handleRevectorize" class="btn btn-secondary ml-auto" :disabled="isAnyTaskRunningForSelectedStore || !currentVectorizer">
                                <IconArrowPath class="w-4 h-4 mr-2" /> Re-index Now
                            </button>
                        </div>
                    </div>
                </transition>

                <div>
                    <h3 class="text-xl font-semibold mb-4">Indexed Documents ({{ filesInSelectedStore.length }})</h3>
                    <div v-if="filesLoading" class="text-center py-10"><p>Loading documents...</p></div>
                    <div v-else-if="filesInSelectedStore.length === 0" class="text-center py-10 bg-gray-50 dark:bg-gray-800/50 rounded-lg"><p>No documents indexed.</p></div>
                    <ul v-else class="divide-y divide-gray-200 dark:divide-gray-700">
                        <li v-for="file in filesInSelectedStore" :key="file.filename" class="py-3 flex items-center justify-between">
                            <span class="text-sm font-medium truncate flex-grow mr-4">{{ file.filename }}</span>
                            <button v-if="canReadWrite(currentSelectedStore)" @click="handleDeleteFile(file.filename)" class="btn btn-danger btn-sm p-1.5" :disabled="isLoadingAction === `delete_file_${file.filename}`">
                                <IconTrash class="w-4 h-4" />
                            </button>
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
.tab-button {
    @apply px-1 py-4 text-sm font-medium border-b-2;
}
.tab-button.active {
    @apply border-blue-500 text-blue-600 dark:text-blue-400;
}
.tab-button.inactive {
    @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600;
}
</style>