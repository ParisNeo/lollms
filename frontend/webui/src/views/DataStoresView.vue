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
import IconMagnifyingGlass from '../assets/icons/IconMagnifyingGlass.vue';

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
const folderInputRef = ref(null);
const currentUploadTask = ref(null);
const currentGraphTask = ref(null);
const dragOver = ref(false);
const selectedFilesToDelete = ref(new Set());

const queryText = ref('');
const queryTopK = ref(10);
const queryMinSim = ref(50.0);
const queryResults = ref([]);
const isQuerying = ref(false);
const queryError = ref('');
const searchInChunks = ref('');
const searchMatches = ref([]);
const currentMatchIndex = ref(-1);


const metadataOption = ref('none');
const manualMetadata = ref({});
const vectorizeWithMetadata = ref(true);
const manualMetadataMode = ref('per-file');
const allFilesMetadata = ref('title: \nsubject: \nauthors: ');

const allFilesSelected = computed(() => {
    return filesInSelectedStore.value.length > 0 && selectedFilesToDelete.value.size === filesInSelectedStore.value.length;
});

const someFilesSelected = computed(() => {
    return selectedFilesToDelete.value.size > 0 && !allFilesSelected.value;
});

// Use availableVectorizers directly which now contains models
const vectorizerOptions = computed(() => availableVectorizers.value);

const selectedVectorizerDetails = computed(() => {
    if (!newStoreForm.value.selectedVectorizerKey) return null;
    
    const parts = newStoreForm.value.selectedVectorizerKey.split('/');
    if (parts.length < 2) return null;
    
    // The key format is `${group.alias}/${model.value}`
    // Since model.value can contain slashes (e.g. 'ollama/llama3'), we need to be careful.
    // The first part is always the alias.
    const bindingAlias = parts[0];
    const modelValue = parts.slice(1).join('/');
    
    // Find the binding in availableVectorizers
    const foundBinding = vectorizerOptions.value.find(group => group.alias === bindingAlias);
    
    if (foundBinding) {
        return {
            ...foundBinding,
            selectedModelName: modelValue
        };
    }
    return null;
});

const allDataStores = computed(() => [...ownedDataStores.value, ...sharedDataStores.value].sort((a, b) => a.name.localeCompare(b.name)));
const myDataStores = computed(() => ownedDataStores.value.sort((a, b) => a.name.localeCompare(b.name)));
const currentSelectedStore = computed(() => allDataStores.value.find(s => s.id === selectedStoreId.value));
const isAnyTaskRunningForSelectedStore = computed(() => !!currentUploadTask.value || !!currentGraphTask.value);

function highlightedChunk(text) {
    if (!text) return '';
    if (!searchInChunks.value || searchMatches.value.length === 0) {
        return text;
    }
    const searchTerm = searchInChunks.value;
    const regex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return text.replace(regex, '<mark class="bg-yellow-200 dark:bg-yellow-700 rounded">$1</mark>');
}


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
    selectedFilesToDelete.value.clear();
    if (newId) {
        activeTab.value = 'documents';
        fetchFilesInStore(newId);
        queryText.value = '';
        queryResults.value = [];
        queryError.value = '';
    } else {
        filesInSelectedStore.value = [];
    }
}, { immediate: true });

watch(selectedVectorizerDetails, (details) => {
    newStoreForm.value.config = {};
    if (!details) return;
    
    // Copy base config from binding
    newStoreForm.value.config = { ...(details.vectorizer_config || {}) };
    
    // Override model name if selected
    if (details.selectedModelName) {
        newStoreForm.value.config['model_name'] = details.selectedModelName;
    }
}, { deep: true });

watch(queryResults, () => {
    searchInChunks.value = '';
    searchMatches.value = [];
    currentMatchIndex.value = -1;
});


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
            vectorizer_name: selectedVectorizerDetails.value.vectorizer_name, // Send raw vectorizer name
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
    const { confirmed } = await uiStore.showConfirmation({ title: `Delete Data Store '${store.name}'?`, message: 'This will permanently delete the data store and all its indexed documents.', confirmText: 'Delete' });
    if (confirmed) {
        isLoadingAction.value = `delete_store_${store.id}`;
        try { await dataStore.deleteDataStore(store.id); if (selectedStoreId.value === store.id) selectedStoreId.value = null; } 
        finally { isLoadingAction.value = null; }
    }
}
function handleShareStore(store) { uiStore.openModal('shareDataStore', { store }); }
async function handleFileDrop(event) {
    event.preventDefault();
    dragOver.value = false;
    
    const items = event.dataTransfer.items;
    const allFiles = [];

    function readEntriesPromise(directoryReader) {
        return new Promise((resolve, reject) => {
            directoryReader.readEntries(resolve, reject);
        });
    }

    async function getFilesInDirectory(directoryEntry) {
        const directoryReader = directoryEntry.createReader();
        let allEntries = [];
        let newEntries;
        do {
            newEntries = await readEntriesPromise(directoryReader);
            allEntries = allEntries.concat(newEntries);
        } while (newEntries.length > 0);
        return allEntries;
    }

    async function traverseEntry(entry) {
        if (entry.isFile) {
            await new Promise((resolve, reject) => entry.file(file => {
                allFiles.push(file);
                resolve();
            }, reject));
        } else if (entry.isDirectory) {
            const entries = await getFilesInDirectory(entry);
            for (const subEntry of entries) {
                await traverseEntry(subEntry);
            }
        }
    }

    const traversePromises = [];
    for (let i = 0; i < items.length; i++) {
        const entry = items[i].webkitGetAsEntry();
        if (entry) {
            traversePromises.push(traverseEntry(entry));
        }
    }

    await Promise.all(traversePromises);

    if (allFiles.length > 0) {
        addFilesToSelection(allFiles);
    }
}
function handleFileChange(event) { addFilesToSelection(Array.from(event.target.files)); }
function addFilesToSelection(newFiles) {
    for (const file of newFiles) {
        if (!selectedFilesToUpload.value.some(f => f.name === file.name && f.size === file.size)) {
            selectedFilesToUpload.value.push(file);
            manualMetadata.value[file.name] = 'title: \nsubject: \nauthors: ';
        } else {
            uiStore.addNotification(`File "${file.name}" is already selected.`, 'warning');
        }
    }
    if (fileInputRef.value) fileInputRef.value.value = '';
}
function removeFileFromSelection(index) {
    const removedFile = selectedFilesToUpload.value.splice(index, 1);
    if (removedFile.length > 0) {
        delete manualMetadata.value[removedFile[0].name];
    }
}
async function fetchFilesInStore(storeId) { filesLoading.value = true; try { filesInSelectedStore.value = await dataStore.fetchStoreFiles(storeId); } finally { filesLoading.value = false; } }
async function handleUploadFiles() {
    if (!currentSelectedStore.value || selectedFilesToUpload.value.length === 0) { uiStore.addNotification('Please select files to upload.', 'warning'); return; }
    if (isAnyTaskRunningForSelectedStore.value) { uiStore.addNotification('A task is already running for this Data Store.', 'warning'); return; }

    const formData = new FormData();
    selectedFilesToUpload.value.forEach(file => formData.append('files', file));
    formData.append('metadata_option', metadataOption.value);
    formData.append('vectorize_with_metadata', vectorizeWithMetadata.value);

    if (metadataOption.value === 'manual') {
        let metadataPayload = {};
        const parseKeyValueMetadata = (text) => {
            const metadata = {};
            if(!text) return metadata;
            const lines = text.split('\n');
            for (const line of lines) {
                const parts = line.split(':');
                if (parts.length >= 2) {
                    const key = parts[0].trim();
                    const value = parts.slice(1).join(':').trim();
                    if (key) {
                        if (['authors', 'tags', 'keywords'].includes(key.toLowerCase())) {
                            metadata[key] = value.split(',').map(item => item.trim()).filter(Boolean);
                        } else {
                            metadata[key] = value;
                        }
                    }
                }
            }
            return metadata;
        };

        try {
            if (manualMetadataMode.value === 'all') {
                const commonMetadata = allFilesMetadata.value.trim() ? parseKeyValueMetadata(allFilesMetadata.value) : {};
                for (const file of selectedFilesToUpload.value) {
                    metadataPayload[file.name] = commonMetadata;
                }
            } else { // 'per-file'
                for (const file of selectedFilesToUpload.value) {
                    const fileMetadataStr = manualMetadata.value[file.name] || '';
                    metadataPayload[file.name] = fileMetadataStr.trim() ? parseKeyValueMetadata(fileMetadataStr) : {};
                }
            }
            formData.append('manual_metadata_json', JSON.stringify(metadataPayload));
        } catch (e) {
            uiStore.addNotification(`Invalid metadata format. Please use 'key: value' pairs, with one entry per line.`, 'error');
            console.error("Metadata parsing error:", e);
            return;
        }
    }

    await dataStore.uploadFilesToStore({ storeId: currentSelectedStore.value.id, formData });
    selectedFilesToUpload.value = [];
    manualMetadata.value = {};
    allFilesMetadata.value = 'title: \nsubject: \nauthors: ';
}
function canReadWrite(store) { return store && ['owner', 'read_write', 'revectorize'].includes(store.permission_level); }

function toggleFileSelection(filename) {
    if (selectedFilesToDelete.value.has(filename)) {
        selectedFilesToDelete.value.delete(filename);
    } else {
        selectedFilesToDelete.value.add(filename);
    }
}

function toggleSelectAll(event) {
    if (event.target.checked) {
        selectedFilesToDelete.value = new Set(filesInSelectedStore.value.map(f => f.filename));
    } else {
        selectedFilesToDelete.value.clear();
    }
}

async function handleDeleteSelectedFiles() {
    if (selectedFilesToDelete.value.size === 0) return;
    const { confirmed } = await uiStore.showConfirmation({
        title: `Delete ${selectedFilesToDelete.value.size} file(s)?`,
        message: 'This will permanently remove the selected documents and their data from the data store.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        isLoadingAction.value = 'delete_selected_files';
        try {
            const filesToDelete = Array.from(selectedFilesToDelete.value);
            await dataStore.deleteFilesFromStore({ storeId: currentSelectedStore.value.id, filenames: filesToDelete });
            await fetchFilesInStore(currentSelectedStore.value.id);
            selectedFilesToDelete.value.clear();
        } finally {
            isLoadingAction.value = null;
        }
    }
}

async function handleQueryStore() {
    if (!queryText.value.trim() || !currentSelectedStore.value) return;
    isQuerying.value = true;
    queryError.value = '';
    queryResults.value = [];
    try {
        const results = await dataStore.queryDataStore({
            storeId: currentSelectedStore.value.id,
            query: queryText.value,
            top_k: queryTopK.value,
            min_similarity_percent: queryMinSim.value
        });
        queryResults.value = results;
    } catch (error) {
        queryError.value = 'An error occurred during the query.';
    } finally {
        isQuerying.value = false;
    }
}

function handleInChunkSearch() {
    if (!searchInChunks.value) {
        searchMatches.value = [];
        currentMatchIndex.value = -1;
        document.querySelectorAll('.current-search-highlight').forEach(el => el.classList.remove('current-search-highlight'));
        return;
    }

    const searchTerm = searchInChunks.value;
    const matches = [];
    
    queryResults.value.forEach((chunk, chunkIndex) => {
        const text = chunk.chunk_text || '';
        const regex = new RegExp(searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
        let match;
        while ((match = regex.exec(text)) !== null) {
            matches.push({
                chunkIndex,
                matchIndexInText: match.index
            });
        }
    });
    
    searchMatches.value = matches;
    if (matches.length > 0) {
        currentMatchIndex.value = 0;
        scrollToMatch(matches[0]);
    } else {
        currentMatchIndex.value = -1;
        uiStore.addNotification('No matches found in results.', 'info');
        document.querySelectorAll('.current-search-highlight').forEach(el => el.classList.remove('current-search-highlight'));
    }
}

function navigateMatch(direction) {
    if (searchMatches.value.length === 0) return;
    let newIndex = currentMatchIndex.value + direction;
    if (newIndex < 0) newIndex = searchMatches.value.length - 1;
    if (newIndex >= searchMatches.value.length) newIndex = 0;
    currentMatchIndex.value = newIndex;
    scrollToMatch(searchMatches.value[newIndex]);
}

function scrollToMatch(match) {
    const chunkElement = document.getElementById(`chunk-${match.chunkIndex}`);
    if (chunkElement) {
        document.querySelectorAll('.current-search-highlight').forEach(el => el.classList.remove('current-search-highlight'));

        const markElements = Array.from(chunkElement.querySelectorAll('mark'));
        if (markElements.length > 0) {
            let matchCounterInChunk = 0;
            const text = queryResults.value[match.chunkIndex]?.chunk_text || '';
            const searchTerm = searchInChunks.value;
            const regex = new RegExp(searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
            let m;
            let targetMarkIndex = -1;
            let textOffset = 0;
            
            // This is complex because v-html does not give us direct element mapping.
            // We have to reconstruct the positions.
            const parts = text.split(regex);
            let currentOffset = 0;
            for(let i = 1; i < parts.length; i += 2) { // Iterate over matches
                 if (currentOffset === match.matchIndexInText) {
                    targetMarkIndex = matchCounterInChunk;
                    break;
                }
                currentOffset += (parts[i-1] ? parts[i-1].length : 0) + parts[i].length;
                matchCounterInChunk++;
            }

            if (targetMarkIndex !== -1 && markElements[targetMarkIndex]) {
                const mark = markElements[targetMarkIndex];
                mark.classList.add('current-search-highlight');
                mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                chunkElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        } else {
            chunkElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
}
</script>

<template>
  <PageViewLayout title="Data Studio" :title-icon="IconDatabase">
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
                        <option :value="null" disabled>-- Select a Vectorizer Model --</option>
                        <optgroup 
                            v-for="group in vectorizerOptions" 
                            :key="group.id" 
                            :label="group.alias || group.vectorizer_name"
                        >
                            <option 
                                v-for="model in group.models" 
                                :key="`${group.id}-${model.value}`" 
                                :value="`${group.alias}/${model.value}`"
                            >
                                {{ model.name }}
                            </option>
                        </optgroup>
                    </select>
                    <p v-if="vectorizerOptions.length === 0" class="text-xs text-red-500 mt-1">
                        No active RAG bindings found. Please configure them in Settings.
                    </p>
                </div>
                <div v-if="selectedVectorizerDetails" class="p-4 border dark:border-gray-700 rounded-lg space-y-4">
                    <h4 class="font-medium text-lg">{{ selectedVectorizerDetails.title || selectedVectorizerDetails.name }}</h4>
                    <p class="text-sm text-gray-500">{{ selectedVectorizerDetails.description }}</p>
                    <div v-if="selectedVectorizerDetails.input_parameters?.length > 0" class="space-y-4">
                        <div v-for="param in selectedVectorizerDetails.input_parameters" :key="param.name">
                            <!-- Model parameter is handled by the main select, only show others -->
                            <div v-if="param.name !== 'model'">
                                <label :for="`param-${param.name}`" class="block text-sm font-medium">{{ param.name }} <span v-if="param.mandatory" class="text-red-500">*</span></label>
                                <div class="relative mt-1">
                                    <input :type="(param.name.includes('key') || param.name.includes('token')) && !isKeyVisible[param.name] ? 'password' : 'text'" v-model="newStoreForm.config[param.name]" class="input-field pr-10" :placeholder="param.description">
                                    <button v-if="param.name.includes('key') || param.name.includes('token')" type="button" @click="isKeyVisible[param.name] = !isKeyVisible[param.name]" class="absolute inset-y-0 right-0 px-3 flex items-center text-gray-500 hover:text-gray-700 dark:hover:text-gray-300" :title="isKeyVisible[param.name] ? 'Hide' : 'Show'">
                                        <IconEyeOff v-if="isKeyVisible[param.name]" class="w-5 h-5" /><IconEye v-else class="w-5 h-5" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="flex justify-end gap-3">
                    <button type="button" @click="isAddFormVisible=false; selectStore(myDataStores[0]?.id)" class="btn btn-secondary">Cancel</button>
                    <button type="submit" class="btn btn-primary" :disabled="isLoadingAction === 'add_store'">
                        <IconAnimateSpin v-if="isLoadingAction === 'add_store'" class="w-5 h-5 mr-2 animate-spin" />
                        {{ isLoadingAction === 'add_store' ? 'Creating...' : 'Create Data Store' }}
                    </button>
                </div>
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
                    <button v-if="currentSelectedStore.permission_level === 'owner'" @click="handleDeleteStore(currentSelectedStore)" class="btn btn-danger btn-sm">
                        <IconAnimateSpin v-if="isLoadingAction === `delete_store_${currentSelectedStore.id}`" class="w-4 h-4 mr-2 animate-spin" />
                        <IconTrash v-else class="w-4 h-4 mr-2" />
                        Delete
                    </button>
                </div>
            </div>
            <div class="border-b border-gray-200 dark:border-gray-700 px-6">
                <nav class="-mb-px flex space-x-6" aria-label="Tabs">
                    <button @click="activeTab = 'documents'" :class="['tab-button', activeTab === 'documents' ? 'active' : 'inactive']">Documents</button>
                    <button @click="activeTab = 'query'" :class="['tab-button', activeTab === 'query' ? 'active' : 'inactive']">Query</button>
                    <button @click="activeTab = 'graph'" :class="['tab-button', activeTab === 'graph' ? 'active' : 'inactive']">Graph</button>
                </nav>
            </div>
            <div v-show="activeTab === 'documents'" class="p-6 flex-grow overflow-y-auto space-y-8">
                <div v-if="canReadWrite(currentSelectedStore)" class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-6 space-y-4">
                    <h3 class="text-xl font-semibold text-gray-900 dark:text-white">Add Documents</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label for="metadata-option" class="block text-sm font-medium">Metadata Handling</label>
                            <select id="metadata-option" v-model="metadataOption" class="input-field mt-1">
                                <option value="none">None</option>
                                <option value="manual">Manual Entry</option>
                                <option value="auto-generate">Auto-generate for each file</option>
                                <option value="rewrite-chunk">Rewrite full content with metadata for each chunk</option>
                            </select>
                            <p class="text-xs text-gray-500 mt-1">Choose how to handle metadata for uploaded files.</p>
                        </div>
                        <div class="relative flex items-start pt-7">
                            <div class="flex h-6 items-center">
                                <input id="vectorize-with-metadata" v-model="vectorizeWithMetadata" type="checkbox" class="h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-600">
                            </div>
                            <div class="ml-3 text-sm leading-6">
                                <label for="vectorize-with-metadata" class="font-medium text-gray-900 dark:text-gray-100">Vectorize with Metadata</label>
                                <p class="text-gray-500 dark:text-gray-400">Include document metadata in the vectorization process for better context.</p>
                            </div>
                        </div>
                    </div>
                    <div @dragover.prevent="dragOver = true" @dragleave.prevent="dragOver = false" @drop.prevent="handleFileDrop" class="border-2 border-dashed rounded-lg p-6 text-center transition-colors" :class="{ 'border-blue-500 bg-blue-50 dark:bg-blue-900/20': dragOver, 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500': !dragOver }">
                        <input type="file" multiple ref="fileInputRef" @change="handleFileChange" class="hidden" accept=".pdf,.docx,.pptx,.xlsx,.msg,.vcf,.txt,.md,.py,.js,.ts,.html,.css,.c,.cpp,.h,.hpp,.cs,.java,.json,.xml,.sh,.vhd,.v,.rb,.php,.go,.rs,.swift,.kt,.yaml,.yml,.sql,.log,.csv">
                        <input type="file" ref="folderInputRef" @change="handleFileChange" class="hidden" webkitdirectory directory multiple>
                        <p class="text-gray-600 dark:text-gray-300">Drag & drop files or folders here</p>
                        <div class="mt-4 flex justify-center gap-4">
                            <button type="button" @click="fileInputRef.click()" class="btn btn-secondary">Select File(s)</button>
                            <button type="button" @click="folderInputRef.click()" class="btn btn-secondary">Select Folder</button>
                        </div>
                    </div>
                    
                    <div v-if="selectedFilesToUpload.length > 0">
                        <div v-if="metadataOption === 'manual'" class="mt-4">
                            <label class="block text-sm font-medium">Manual Metadata Mode</label>
                            <div class="flex items-center gap-4 mt-1">
                                <label class="flex items-center"><input type="radio" v-model="manualMetadataMode" value="per-file" class="radio-input"><span class="ml-2">Per File</span></label>
                                <label class="flex items-center"><input type="radio" v-model="manualMetadataMode" value="all" class="radio-input"><span class="ml-2">For All Files</span></label>
                            </div>
                        </div>

                        <div v-if="metadataOption === 'manual' && manualMetadataMode === 'all'" class="mt-4">
                            <h4 class="text-sm font-medium mb-2">Selected Files ({{ selectedFilesToUpload.length }})</h4>
                            <ul class="list-disc list-inside text-sm space-y-1 max-h-40 overflow-y-auto mb-4 p-2 bg-gray-100 dark:bg-gray-800 rounded-md">
                                <li v-for="(file, index) in selectedFilesToUpload" :key="index" class="flex justify-between items-center">
                                    <span class="truncate">{{ file.name }}</span>
                                    <button @click="removeFileFromSelection(index)" class="text-red-500 hover:text-red-700 ml-2" title="Remove"><IconXMark class="w-4 h-4" /></button>
                                </li>
                            </ul>
                            <label class="block text-sm font-medium">Metadata for all files (Key: Value format)</label>
                            <textarea v-model="allFilesMetadata" rows="4" class="input-field mt-1 font-mono text-xs" placeholder="title: My Document&#10;subject: AI Research&#10;authors: John Doe, Jane Smith"></textarea>
                        </div>
                        
                        <div v-else-if="metadataOption === 'manual' && manualMetadataMode === 'per-file'" class="space-y-4 mt-4 max-h-96 overflow-y-auto">
                            <h4 class="text-sm font-medium">Enter Metadata for Each File:</h4>
                            <div v-for="(file, index) in selectedFilesToUpload" :key="index" class="p-3 border rounded-lg dark:border-gray-600 space-y-3">
                                <div class="flex justify-between items-start">
                                    <p class="font-semibold text-sm truncate">{{ file.name }}</p>
                                    <button @click="removeFileFromSelection(index)" class="text-red-500 hover:text-red-700" title="Remove"><IconXMark class="w-5 h-5" /></button>
                                </div>
                                <div><label class="text-xs font-medium">Metadata (Key: Value format)</label><textarea v-model="manualMetadata[file.name]" rows="4" class="input-field-sm w-full mt-1 font-mono text-xs" placeholder="title: ..."></textarea></div>
                            </div>
                        </div>

                        <div v-else-if="metadataOption !== 'manual'" class="mt-4">
                            <h4 class="text-sm font-medium mb-2">Selected for Upload ({{ selectedFilesToUpload.length }})</h4>
                            <ul class="space-y-1 max-h-40 overflow-y-auto">
                                <li v-for="(file, index) in selectedFilesToUpload" :key="index" class="flex justify-between items-center bg-gray-100 dark:bg-gray-800 p-2 rounded text-sm"><span class="truncate">{{ file.name }} ({{ (file.size / 1024 / 1024).toFixed(2) }} MB)</span><button @click="removeFileFromSelection(index)" class="text-red-500 hover:text-red-700 ml-2" title="Remove"><IconXMark class="w-4 h-4" /></button></li>
                            </ul>
                        </div>
                    </div>
                    <div v-else-if="metadataOption === 'manual'" class="mt-4 text-center text-sm text-gray-500 italic p-4 border-2 border-dashed rounded-lg dark:border-gray-600">
                        Select files to enter their metadata manually.
                    </div>
                    <div class="flex justify-end items-center mt-4">
                        <button @click="handleUploadFiles" class="btn btn-primary" :disabled="isAnyTaskRunningForSelectedStore || selectedFilesToUpload.length === 0">
                            <IconArrowUpTray class="w-5 h-5 mr-2" /> Add {{ selectedFilesToUpload.length }} File(s)
                        </button>
                    </div>
                </div>
                <div v-if="currentUploadTask" class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-700"> ... </div>
                <div>
                    <h3 class="text-xl font-semibold mb-4">Indexed Documents ({{ filesInSelectedStore.length }})</h3>
                    <div v-if="!filesLoading && filesInSelectedStore.length > 0 && canReadWrite(currentSelectedStore)" class="flex items-center justify-between bg-gray-50 dark:bg-gray-800/50 p-2 rounded-md mb-2">
                        <div class="flex items-center">
                            <input type="checkbox" @change="toggleSelectAll" :checked="allFilesSelected" :indeterminate="someFilesSelected" id="select-all-files-checkbox" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500">
                            <label for="select-all-files-checkbox" class="ml-2 text-sm select-none cursor-pointer">Select All</label>
                        </div>
                        <button @click="handleDeleteSelectedFiles" class="btn btn-danger btn-sm" :disabled="selectedFilesToDelete.size === 0 || isLoadingAction === 'delete_selected_files'">
                            <IconAnimateSpin v-if="isLoadingAction === 'delete_selected_files'" class="w-4 h-4 mr-2 animate-spin" />
                            <IconTrash v-else class="w-4 h-4 mr-2" />
                            Delete Selected ({{ selectedFilesToDelete.size }})
                        </button>
                    </div>
                    <div v-if="filesLoading" class="text-center py-10"><p>Loading documents...</p></div>
                    <div v-else-if="filesInSelectedStore.length === 0" class="text-center py-10 bg-gray-50 dark:bg-gray-800/50 rounded-lg"><p>No documents indexed.</p></div>
                    <ul v-else class="divide-y divide-gray-200 dark:divide-gray-700">
                        <li v-for="file in filesInSelectedStore" :key="file.filename" class="py-3 flex items-center">
                            <input 
                                v-if="canReadWrite(currentSelectedStore)"
                                type="checkbox" 
                                @change="toggleFileSelection(file.filename)" 
                                :checked="selectedFilesToDelete.has(file.filename)" 
                                class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 mr-4 flex-shrink-0"
                            >
                            <div class="flex-grow min-w-0">
                                <span class="text-sm font-medium truncate">{{ file.filename }}</span>
                                <details v-if="file.metadata && Object.keys(file.metadata).length > 0" class="mt-2 text-xs">
                                    <summary class="cursor-pointer text-gray-500">View Metadata</summary>
                                    <div class="mt-1 p-2 bg-gray-100 dark:bg-gray-700/50 rounded">
                                        <JsonRenderer :json="file.metadata" />
                                    </div>
                                </details>
                            </div>
                        </li>
                    </ul>
                </div>
            </div>
            <div v-if="activeTab === 'query'" class="p-6 flex-grow overflow-y-auto flex flex-col">
                <div class="flex-shrink-0 space-y-4">
                    <h3 class="text-xl font-semibold">Query Data Store</h3>
                    <form @submit.prevent="handleQueryStore" class="space-y-4">
                        <div>
                            <label for="query-text" class="block text-sm font-medium">Query Text</label>
                            <textarea id="query-text" v-model="queryText" rows="3" class="input-field mt-1" placeholder="Enter your question..."></textarea>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                                <label for="query-topk" class="block text-sm font-medium">Top K</label>
                                <input id="query-topk" v-model.number="queryTopK" type="number" min="1" class="input-field mt-1">
                            </div>
                            <div>
                                <label for="query-minsim" class="block text-sm font-medium">Min Similarity %</label>
                                <input id="query-minsim" v-model.number="queryMinSim" type="number" min="0" max="100" step="0.1" class="input-field mt-1">
                            </div>
                            <div class="self-end">
                                <button type="submit" class="btn btn-primary w-full" :disabled="isQuerying || !queryText.trim()">
                                    <IconAnimateSpin v-if="isQuerying" class="w-5 h-5 mr-2 animate-spin" />
                                    {{ isQuerying ? 'Querying...' : 'Query' }}
                                </button>
                            </div>
                        </div>
                    </form>
                </div>
                <div class="flex-grow min-h-0 mt-6 border-t dark:border-gray-700 pt-6">
                    <div class="flex justify-between items-center mb-4">
                        <h4 class="text-lg font-semibold">Results ({{ queryResults.length }})</h4>
                        <div v-if="queryResults.length > 0" class="flex items-center gap-2">
                            <input type="text" v-model="searchInChunks" @keyup.enter="handleInChunkSearch" placeholder="Search in results..." class="input-field !py-1.5 !text-sm">
                            <button @click="handleInChunkSearch" class="btn btn-secondary btn-sm p-2"><IconMagnifyingGlass class="w-4 h-4" /></button>
                            <template v-if="searchMatches.length > 0">
                                <button @click="navigateMatch(-1)" class="btn btn-secondary btn-sm p-2" title="Previous match">‹</button>
                                <span class="text-sm text-gray-500 font-mono">{{ currentMatchIndex + 1 }} / {{ searchMatches.length }}</span>
                                <button @click="navigateMatch(1)" class="btn btn-secondary btn-sm p-2" title="Next match">›</button>
                            </template>
                        </div>
                    </div>
                    <div v-if="isQuerying" class="text-center p-6 text-gray-500">
                        <IconAnimateSpin class="w-8 h-8 mx-auto animate-spin" />
                        <p class="mt-2">Fetching results...</p>
                    </div>
                    <div v-else-if="queryError" class="p-4 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-md">
                        {{ queryError }}
                    </div>
                    <div v-else-if="queryResults.length === 0" class="text-center p-6 text-gray-500">
                        No results to display. Run a query to see matching text chunks.
                    </div>
                    <div v-else-if="searchInChunks && searchMatches.length === 0" class="text-center p-6 text-gray-500">
                        No chunks match your search term.
                    </div>
                    <div v-else class="space-y-4 overflow-y-auto custom-scrollbar h-full pb-10">
                        <div v-for="(chunk, index) in queryResults" :key="index" :id="`chunk-${index}`" class="p-4 border rounded-lg dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                            <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 mb-2">
                                <span class="font-mono truncate" :title="chunk.file_path">.../{{ chunk.file_path.split(/[/\\]/).pop() }}</span>
                                <span class="font-semibold" :title="`Similarity: ${chunk.similarity_percent}`">{{ chunk.similarity_percent.toFixed(2) }}%</span>
                            </div>
                            <pre class="whitespace-pre-wrap font-sans text-sm" v-html="highlightedChunk(chunk.chunk_text)"></pre>
                        </div>
                    </div>
                </div>
            </div>
            <div v-if="activeTab === 'graph'" class="p-6 flex-grow overflow-y-auto">
                <DataStoreGraphManager :store="currentSelectedStore" :task="currentGraphTask" />
            </div>
        </div>
    </template>
  </PageViewLayout>
</template>

<style>
.current-search-highlight {
    background-color: #ff9632 !important;
    color: black !important;
    border-radius: 3px;
    box-shadow: 0 0 5px #ff9632;
}
.tab-button { @apply px-1 py-4 text-sm font-medium border-b-2; }
.tab-button.active { @apply border-blue-500 text-blue-600 dark:text-blue-400; }
.tab-button.inactive { @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600; }
</style>
