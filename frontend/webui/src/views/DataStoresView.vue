<script setup>
import { ref, computed, onMounted, onBeforeUnmount, onUnmounted, watch, defineAsyncComponent, Teleport, nextTick  } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { marked } from 'marked';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useTasksStore } from '../stores/tasks';
import { useAdminStore } from '../stores/admin';
import { useAuthStore } from '../stores/auth';
import apiClient from '../services/api';
import UserAvatar from '../components/ui/Cards/UserAvatar.vue';
import JsonRenderer from '../components/ui/JsonRenderer.vue';
import GenericModal from '../components/modals/GenericModal.vue';

import IconInfo from '../assets/icons/IconInfo.vue';
import IconFileText from '../assets/icons/IconFileText.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconCpuChip from '../assets/icons/IconCpuChip.vue';
import MessageContentRenderer from '../components/ui/MessageContentRenderer/MessageContentRenderer.vue';

import DataStoreGraphManager from '../components/datastores/DataStoreGraphManager.vue';
import DataLakeViewer from '../components/datastores/DataLakeViewer.vue';

// Icons
import IconDatabase from '../assets/icons/IconDatabase.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconShare from '../assets/icons/IconShare.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';
import IconEye from '../assets/icons/IconEye.vue';
import IconEyeOff from '../assets/icons/IconEyeOff.vue';
import IconMagnifyingGlass from '../assets/icons/IconMagnifyingGlass.vue';
import IconCopy from '../assets/icons/IconCopy.vue';
import IconGlobeAlt from '../assets/icons/IconGlobeAlt.vue';
import IconChevronRight from '../assets/icons/IconChevronRight.vue';
import IconYoutube from '../assets/icons/IconYoutube.vue';
import IconWikipedia from '../assets/icons/IconWikipedia.vue';
import IconServer from '../assets/icons/IconServer.vue';
import IconWeb from '../assets/icons/ui/IconWeb.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';

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
const showStoreInfo = ref(false); // Controls the Info Modal
const CHUNKING_STRATEGIES = [
    { value: 'recursive', label: 'Recursive Tree (Recommended)', desc: 'Hierarchically splits by paragraphs -> markdown headers -> sentences -> words. Best all-around balance.' },
    { value: 'structure', label: 'Structure-Aware (Markdown)', desc: 'Parses Markdown # H1 -> ## H2 stacks, attaching lineage breadcrumbs [H1 > H2].' },
    { value: 'token', label: 'Token Window', desc: 'Slices by tokenizer limits (tiktoken/HF) preserving newline structure.' },
    { value: 'semantic', label: 'Semantic Valley', desc: 'Cuts at cosine similarity valleys when topic shifts across sentences.' },
    { value: 'contextual', label: 'Contextual Retrieval (Anthropic)', desc: 'Injects full-document situating summaries before storage.' },
    { value: 'late', label: 'Late Chunking (Jina AI)', desc: 'Passes full document through transformer first, then mean-pools representations.' },
    { value: 'paragraph', label: 'Paragraph Blocks', desc: 'Groups double-newline paragraph blocks up to chunk size without mid-thought cuts.' },
    { value: 'character', label: 'Fixed Character', desc: 'Fast raw character sliding window for log streams and raw dumps.' }
];

const newStoreForm = ref({
    name: '',
    description: '',
    selectedVectorizerKey: null,
    config: {},
    chunk_size: 2048,
    chunk_overlap: 256,
    chunking_strategy: 'recursive',
    chunking_kwargs: {}
});
const isKeyVisible = ref({});
const filesInSelectedStore = ref([]);
const filesLoading = ref(false);
const isStoreInitializing = ref(false);
const storeDiagnosticInfo = ref(null);
const selectedFilesToUpload = ref([]);
const fileInputRef = ref(null);
const folderInputRef = ref(null);
const currentUploadTask = ref(null);
const currentGraphTask = ref(null);
const currentScrapeTask = ref(null);
const dragOver = ref(false);
const selectedFilesToDelete = ref(new Set());

// Export/Import State
const isExporting = ref(null);
const isImporting = ref(false);
const importInputRef = ref(null);
const importStoreName = ref('');
const importFile = ref(null);

// Scrape URL State
const scrapeUrl = ref('');
const scrapeDepth = ref(0);
const isUploading = ref(false); 
const isScraping = ref(false); 
const isComponentMounted = ref(false);
const isHeaderReady = ref(false);

onMounted(async () => {
    isComponentMounted.value = true;
    // Wait for the Global Header to be fully rendered in the DOM
    await nextTick();
    if (document.getElementById('global-header-title-target')) {
        isHeaderReady.value = true;
    }

    await dataStore.fetchDataStores();
    dataStore.fetchAvailableVectorizers();
    tasksStore.fetchTasks();

    const queryStoreId = router.currentRoute.value.query.storeId;
    if (queryStoreId) {
        selectedStoreId.value = queryStoreId;
        fetchFilesInStore(queryStoreId);
    }

    window.addEventListener('lollms:open-new-datastore', handleAddStoreClick);
});

onBeforeUnmount(() => {
    isComponentMounted.value = false;
    isHeaderReady.value = false;
});

const queryText = ref('')
const queryTopK = ref(10);
const queryMinSim = ref(50.0);
const queryMode = ref('hybrid'); // 'dense' or 'hybrid'
const retrievalTarget = ref('chunks'); // 'chunks' | 'window' | 'full_documents'
const windowBefore = ref(1);
const windowAfter = ref(1);
const denseWeight = ref(0.5);
const bm25Weight = ref(0.5);
const rrfK = ref(60);

// Document Viewer Chunks Pagination State
const docViewerTab = ref('text'); // 'text' or 'chunks'
const docChunksPage = ref(1);
const docChunksData = ref(null);
const isLoadingDocChunks = ref(false);
const queryResults = ref([]);
const isQuerying = ref(false);
const isAnswering = ref(false);
const answerModelName = ref('');
const queryError = ref('');
const searchInChunks = ref('');
const searchMatches = ref([]);
const currentMatchIndex = ref(-1);
const collapsedChunks = ref(new Set());

const aiAnswer = ref('');

function isChunkCollapsed(index) {
    return collapsedChunks.value.has(index);
}

function toggleChunkCollapse(index) {
    if (collapsedChunks.value.has(index)) {
        collapsedChunks.value.delete(index);
    } else {
        collapsedChunks.value.add(index);
    }
}

function toggleAllChunksCollapse() {
    if (collapsedChunks.value.size === queryResults.value.length) {
        // All are collapsed -> expand all
        collapsedChunks.value.clear();
    } else {
        // Collapse all
        collapsedChunks.value = new Set(queryResults.value.map((_, idx) => idx));
    }
}

const viewingFile = ref(null); 
const loadingFileContent = ref(null); 

const metadataOption = ref('none');
const manualMetadata = ref({});
const vectorizeWithMetadata = ref(true);

const extensionOptions = [
    { label: 'Docs', items: ['.pdf', '.docx', '.pptx', '.txt', '.md', '.msg', '.owl', '.ttl', '.rdf'] },
    { label: 'Code', items: ['.py', '.js', '.ts', '.html', '.css', '.cpp', '.c', '.cs', '.java', '.sh', '.bash', '.zsh', '.bat', '.cmd', '.sql', '.vue'] },
    { label: 'Data', items: ['.json', '.yaml', '.yml', '.csv', '.xml', '.log'] }
];

const selectedExtensions = ref(new Set(['.pdf', '.docx', '.txt', '.md', '.py', '.js', '.json', '.csv', '.owl', '.ttl', '.rdf', '.sh', '.bash', '.zsh', '.bat', '.cmd'])); // Sensible defaults

function toggleExtension(ext) {
    if (selectedExtensions.value.has(ext)) {
        selectedExtensions.value.delete(ext);
    } else {
        selectedExtensions.value.add(ext);
    }
}

function selectExtensionGroup(items, select = true) {
    items.forEach(ext => {
        if (select) selectedExtensions.value.add(ext);
        else selectedExtensions.value.delete(ext);
    });
}
const manualMetadataMode = ref('per-file');
const allFilesMetadata = ref('title: \nsubject: \nauthors: ');

const allFilesSelected = computed(() => {
    return filesInSelectedStore.value.length > 0 && selectedFilesToDelete.value.size === filesInSelectedStore.value.length;
});

const someFilesSelected = computed(() => {
    return selectedFilesToDelete.value.size > 0 && !allFilesSelected.value;
});

// Use availableVectorizers directly which now contains models
const hasActiveVectorizers = computed(() => Array.isArray(availableVectorizers.value) && availableVectorizers.value.length > 0);
const isForcedVectorizerMode = computed(() => authStore.user?.rag_settings_forced);
const vectorizerOptions = computed(() => availableVectorizers.value);

// Revectorize Modal State
const isRevectorizeOpen = ref(false);
const revectorizeTargetKey = ref(null);
const isRevectorizing = ref(false);

function openRevectorizeModal() {
    if (!currentSelectedStore.value) return;
    revectorizeTargetKey.value = null;
    isRevectorizeOpen.value = true;
}

async function handleRevectorize() {
    if (!currentSelectedStore.value || !revectorizeTargetKey.value) return;
    isRevectorizing.value = true;
    try {
        const parts = revectorizeTargetKey.value.split('/');
        const alias = parts[0];
        const modelVal = parts.slice(1).join('/');
        const group = vectorizerOptions.value.find(g => g.alias === alias);

        const config = { ...(group?.vectorizer_config || {}) };
        if (modelVal) config['model_name'] = modelVal;

        const res = await apiClient.post(`/api/store/${currentSelectedStore.value.id}/revectorize`, {
            vectorizer_name: group?.vectorizer_name || alias,
            vectorizer_config: config
        });
        tasksStore.addTask(res.data);
        uiStore.addNotification(`Revectorization task started.`, 'info');
        isRevectorizeOpen.value = false;
    } catch (e) {
        uiStore.addNotification(e.response?.data?.detail || 'Revectorization failed.', 'error');
    } finally {
        isRevectorizing.value = false;
    }
}

const selectedVectorizerDetails = computed(() => {
    if (!newStoreForm.value.selectedVectorizerKey) return null;
    
    const parts = newStoreForm.value.selectedVectorizerKey.split('/');
    if (parts.length < 2) return null;
    
    const bindingAlias = parts[0];
    const modelValue = parts.slice(1).join('/');
    
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
const currentSelectedStore = computed(() => allDataStores.value.find(s => s.id === selectedStoreId.value));
const isAnyTaskRunningForSelectedStore = computed(() => !!currentUploadTask.value || !!currentGraphTask.value || !!currentScrapeTask.value);

function parseChunk(rawText) {
    if (!rawText) return { metadata: null, content: '' };

    // Detect and extract Document Context / Metadata block
    const metaBlockRegex = /^---\s*(?:Document Context|Metadata|Context)\s*---([\s\S]*?)(?:---[-]*|\n\n)/i;
    const match = rawText.match(metaBlockRegex);

    if (match) {
        const rawMeta = match[1].trim();
        const metaEntries = [];
        const lines = rawMeta.split('\n');

        for (const line of lines) {
            const colonIdx = line.indexOf(':');
            if (colonIdx > -1) {
                const key = line.substring(0, colonIdx).trim();
                let val = line.substring(colonIdx + 1).trim();

                // Format array-like string e.g. ['ParisNeo'] -> 'ParisNeo'
                if (val.startsWith('[') && val.endsWith(']')) {
                    try {
                        const parsed = JSON.parse(val.replace(/'/g, '"'));
                        if (Array.isArray(parsed)) val = parsed.join(', ');
                    } catch (e) {
                        val = val.slice(1, -1).replace(/'/g, '').trim();
                    }
                }
                metaEntries.push({ key, value: val });
            }
        }

        let content = rawText.slice(match[0].length).trim();
        content = content.replace(/^[-=\s]{3,}\n*/, '').trim();

        return {
            metadata: metaEntries.length > 0 ? metaEntries : null,
            content: content
        };
    }

    return { metadata: null, content: rawText };
}

function highlightSearchTerms(html, term) {
    if (!html || !term || !term.trim()) return html;
    const cleanTerm = term.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(?![^<]*>)(${cleanTerm})`, 'gi');
    return html.replace(regex, '<mark class="bg-yellow-300 dark:bg-yellow-600 rounded px-0.5">$1</mark>');
}

function renderChunkContent(rawText) {
    const parsed = parseChunk(rawText);
    const content = parsed.content || '';
    let html = '';
    try {
        html = marked.parse(content, { gfm: true, breaks: true, mangle: false, headerIds: false });
    } catch (e) {
        html = `<p>${content}</p>`;
    }
    if (searchInChunks.value) {
        html = highlightSearchTerms(html, searchInChunks.value);
    }
    return html;
}

function copyChunkText(text) {
    navigator.clipboard.writeText(text);
    uiStore.addNotification("Chunk content copied to clipboard.", "success");
}

onMounted(() => {
    dataStore.fetchDataStores();
    dataStore.fetchAvailableVectorizers();
    tasksStore.fetchTasks();
    window.addEventListener('lollms:open-new-datastore', handleAddStoreClick);
});

// Watch to manage Title
watch([selectedStoreId, isAddFormVisible], ([newId, adding]) => {
    if (!isComponentMounted.value) return;

    if (newId) {
        // Only hide title if we have a valid store and header is ready
        uiStore.setPageTitle({ title: '' }); 
    } else if (adding) {
        uiStore.setPageTitle({ title: 'New Data Store', icon: IconPlus });
    } else {
        uiStore.setPageTitle({ title: 'Data Studio', icon: IconDatabase });
    }
});

onUnmounted(() => {
    uiStore.setPageTitle({ title: '' });
    window.removeEventListener('lollms:open-new-datastore', handleAddStoreClick);
});

watch(() => router.currentRoute.value.query.storeId, (newId) => {
    // Only update if the ID has actually changed and is different from internal state
    if (newId && newId !== selectedStoreId.value) {
        selectStore(newId);
    }
}, { immediate: true });

// Memoize store name to avoid reactive overhead in the task filter
const currentStoreName = computed(() => currentSelectedStore.value?.name || '');

// Computed properties are more efficient than deep watchers for high-frequency updates
const storeSpecificTasks = computed(() => {
    if (!currentStoreName.value) return [];
    return tasks.value.filter(t => t.name.includes(currentStoreName.value));
});

watch(storeSpecificTasks, (newStoreTasks) => {
    const findLatest = (filterFn) => newStoreTasks
        .filter(t => filterFn(t) && (t.status === 'running' || t.status === 'pending'))
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0] || null;

    const latestUpload = findLatest(t => t.name.includes('Add files to DataStore:') || t.name.includes('to DataStore:'));
    const latestGraph = findLatest(t => t.name.startsWith('Generate Graph for:') || t.name.startsWith('Update Graph for:'));
    const latestScrape = findLatest(t => t.name.startsWith('Scrape URL to DataStore:'));

    // Detect task completion to refresh file list
    const uploadFinished = currentUploadTask.value && !latestUpload;
    const scrapeFinished = currentScrapeTask.value && !latestScrape;

    if ((uploadFinished || scrapeFinished) && selectedStoreId.value) {
        setTimeout(() => {
            fetchFilesInStore(selectedStoreId.value);
            dataStore.fetchDataStores();
        }, 500);
    }

    currentUploadTask.value = latestUpload;
    currentGraphTask.value = latestGraph;
    currentScrapeTask.value = latestScrape;
});

watch(selectedStoreId, (newId) => {
    isAddFormVisible.value = false;
    selectedFilesToDelete.value.clear();
    if (newId) {
        activeTab.value = 'documents';
        fetchFilesInStore(newId);
        queryText.value = '';
        queryResults.value = [];
        queryError.value = '';
        aiAnswer.value = '';
        answerModelName.value = '';
    } else {
        filesInSelectedStore.value = [];
    }
}, { immediate: true });

watch(selectedVectorizerDetails, (details) => {
    newStoreForm.value.config = {};
    if (!details) return;
    newStoreForm.value.config = { ...(details.vectorizer_config || {}) };
    if (details.selectedModelName) {
        newStoreForm.value.config['model_name'] = details.selectedModelName;
    }
}, { deep: true });

watch(queryResults, (results) => {
    searchInChunks.value = '';
    searchMatches.value = [];
    currentMatchIndex.value = -1;
    // Keep first chunk open, collapse the rest for a clean layout
    if (results && results.length > 1) {
        collapsedChunks.value = new Set(results.slice(1).map((_, idx) => idx + 1));
    } else {
        collapsedChunks.value.clear();
    }
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
        chunk_size: user.value?.default_chunk_size || 2048,
        chunk_overlap: user.value?.default_chunk_overlap || 256,
        chunking_strategy: 'recursive',
        chunking_kwargs: {}
    };
}
async function handleAddStore() {
    if (!newStoreForm.value.name.trim() || !selectedVectorizerDetails.value) { uiStore.addNotification('Name and vectorizer are required.', 'warning'); return; }
    isLoadingAction.value = 'add_store';
    try {
        const payload = {
            name: newStoreForm.value.name,
            description: newStoreForm.value.description,
            vectorizer_name: selectedVectorizerDetails.value.vectorizer_name, 
            vectorizer_config: newStoreForm.value.config || {},
            chunk_size: newStoreForm.value.chunk_size,
            chunk_overlap: newStoreForm.value.chunk_overlap,
            chunking_strategy: newStoreForm.value.chunking_strategy || 'recursive',
            chunking_kwargs: newStoreForm.value.chunking_kwargs || {}
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
async function handleLeaveStore(store) {
    const { confirmed } = await uiStore.showConfirmation({ 
        title: `Leave '${store.name}'?`, 
        message: 'You will lose access to this shared Data Store.', 
        confirmText: 'Leave' 
    });
    if (confirmed) {
        await dataStore.leaveDataStore(store.id);
        if (selectedStoreId.value === store.id) selectedStoreId.value = null;
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
            const entries = await getFilesInDirectory(directoryEntry);
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
    const existingNames = new Set(selectedFilesToUpload.value.map(f => f.name + f.size));
    const filesToAdd = [];
    const newMetadata = {};
    let filteredCount = 0;
    
    for (const file of newFiles) {
        const key = file.name + file.size;
        const ext = '.' + file.name.split('.').pop().toLowerCase();

        // Check against extension filter
        if (selectedExtensions.value.size > 0 && !selectedExtensions.value.has(ext)) {
            filteredCount++;
            continue;
        }

        if (!existingNames.has(key)) {
            filesToAdd.push(file);
            newMetadata[file.name] = 'title: \nsubject: \nauthors: ';
            existingNames.add(key);
        }
    }
    
    if (filesToAdd.length > 0) {
        selectedFilesToUpload.value = [...selectedFilesToUpload.value, ...filesToAdd];
        manualMetadata.value = { ...manualMetadata.value, ...newMetadata };
    }
    
    if (filteredCount > 0) {
        uiStore.addNotification(`Filtered out ${filteredCount} file(s) not matching selected extensions.`, 'info');
    }

    if (filesToAdd.length < (newFiles.length - filteredCount)) {
         uiStore.addNotification(`${(newFiles.length - filteredCount) - filesToAdd.length} duplicate files skipped.`, 'info');
    }

    if (fileInputRef.value) fileInputRef.value.value = '';
    if (folderInputRef.value) folderInputRef.value.value = '';
}

function removeFileFromSelection(index) {
    const removedFile = selectedFilesToUpload.value.splice(index, 1);
    if (removedFile.length > 0) {
        delete manualMetadata.value[removedFile[0].name];
    }
}
async function fetchFilesInStore(storeId) { 
    if (!storeId) return;
    filesLoading.value = true; 
    isStoreInitializing.value = true;
    try { 
        const [filesResult, diagInfo] = await Promise.allSettled([
            dataStore.fetchStoreFiles(storeId),
            dataStore.fetchDataStoreInfo(storeId)
        ]);
        filesInSelectedStore.value = (filesResult.status === 'fulfilled' && filesResult.value) ? filesResult.value : [];
        storeDiagnosticInfo.value = (diagInfo.status === 'fulfilled' && diagInfo.value) ? diagInfo.value : null;
    } catch (e) {
        console.error("Failed to fetch store files and diagnostic info:", e);
        filesInSelectedStore.value = [];
    } finally { 
        filesLoading.value = false; 
        isStoreInitializing.value = false;
    } 
}

async function handleUploadFiles() {
    if (!currentSelectedStore.value || selectedFilesToUpload.value.length === 0) { uiStore.addNotification('Please select files to upload.', 'warning'); return; }
    if (isAnyTaskRunningForSelectedStore.value) { uiStore.addNotification('A task is already running for this Data Store.', 'warning'); return; }

    isUploading.value = true; 
    
    try {
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
                } else { 
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
    } finally {
        isUploading.value = false;
    }
}

function openServiceImportModal(serviceMode = 'url') {
    if (!currentSelectedStore.value) return;
    uiStore.openModal('scrapeUrl', {
        datastoreId: currentSelectedStore.value.id,
        mode: serviceMode,
        onStaged: (stagedFiles) => {
            addFilesToSelection(stagedFiles);
            uiStore.addNotification(`${stagedFiles.length} file(s) added to upload staging list.`, 'success');
        }
    });
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
    aiAnswer.value = '';
    answerModelName.value = '';
    queryError.value = '';
    queryResults.value = [];
    try {
        const results = await dataStore.queryDataStore({
            storeId: currentSelectedStore.value.id,
            query: queryText.value,
            top_k: queryTopK.value,
            min_similarity_percent: queryMinSim.value,
            mode: queryMode.value,
            retrieval_target: retrievalTarget.value,
            window_before: windowBefore.value,
            window_after: windowAfter.value,
            dense_weight: denseWeight.value,
            bm25_weight: bm25Weight.value,
            rrf_k: rrfK.value
        });
        queryResults.value = results;
    } catch (error) {
        queryError.value = 'An error occurred during retrieval.';
    } finally {
        isQuerying.value = false;
    }
}

async function handleAskAiWithEvidence() {
    if (!queryText.value.trim() || !currentSelectedStore.value) return;
    isAnswering.value = true;
    aiAnswer.value = '';
    answerModelName.value = '';
    queryError.value = '';
    queryResults.value = [];
    try {
        const response = await dataStore.queryDataStoreAndAnswer({
            storeId: currentSelectedStore.value.id,
            query: queryText.value,
            top_k: queryTopK.value,
            min_similarity_percent: queryMinSim.value,
            mode: queryMode.value,
            dense_weight: denseWeight.value,
            bm25_weight: bm25Weight.value,
            rrf_k: rrfK.value
        });
        aiAnswer.value = response.answer;
        queryResults.value = response.chunks || [];
        answerModelName.value = response.model_name || 'LLM';
    } catch (error) {
        queryError.value = error.response?.data?.detail || error.message || 'Failed to synthesize answer from DataStore.';
    } finally {
        isAnswering.value = false;
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
            
            const parts = text.split(regex);
            let currentOffset = 0;
            for(let i = 1; i < parts.length; i += 2) { 
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

async function viewFileContent(file) {
    if (loadingFileContent.value) return; 
    loadingFileContent.value = file.filename;
    docViewerTab.value = 'text';
    docChunksPage.value = 1;
    docChunksData.value = null;

    try {
        const content = await dataStore.fetchFileContent(currentSelectedStore.value.id, file.filename);
        viewingFile.value = {
            filename: file.filename,
            metadata: file.metadata,
            content: content
        };
        uiStore.openModal('fileContent');
    } catch (e) {
    } finally {
        loadingFileContent.value = null;
    }
}

async function loadDocChunks(page = 1) {
    if (!viewingFile.value || !currentSelectedStore.value) return;
    docChunksPage.value = page;
    isLoadingDocChunks.value = true;
    try {
        const res = await dataStore.fetchDocumentChunksPaginated(currentSelectedStore.value.id, viewingFile.value.filename, page, 5);
        docChunksData.value = res;
    } catch (e) {
        console.error(e);
    } finally {
        isLoadingDocChunks.value = false;
    }
}

function copyContent() {
    if (viewingFile.value && viewingFile.value.content) {
        navigator.clipboard.writeText(viewingFile.value.content);
        uiStore.addNotification("Content copied to clipboard", "success");
    }
}

// Export/Import Functions
async function handleExportStore(store) {
    if (isExporting.value) return;
    
    const confirmed = await uiStore.showConfirmation({ 
        title: `Export '${store.name}'?`, 
        message: 'This will create a ZIP file containing the datastore database and all indexed documents.',
        confirmText: 'Export'
    });
    
    if (!confirmed.confirmed) return;
    
    isExporting.value = store.id;
    try {
        const response = await apiClient.get(`/api/datastores/${store.id}/export`, {
            responseType: 'blob'
        });
        
        // Extract filename from Content-Disposition header or use default
        const contentDisposition = response.headers['content-disposition'];
        let filename = `${store.name}_export.zip`;
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?(.+?)"?$/);
            if (filenameMatch) filename = filenameMatch[1];
        }
        
        // Create download link
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        
        uiStore.addNotification('Datastore exported successfully', 'success');
    } catch (error) {
        console.error('Export failed:', error);
        uiStore.addNotification('Failed to export datastore', 'error');
    } finally {
        isExporting.value = null;
    }
}

function triggerImport() {
    importInputRef.value?.click();
}

async function handleImportFileChange(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    if (!file.name.endsWith('.zip')) {
        uiStore.addNotification('Please select a ZIP file', 'error');
        return;
    }
    
    importFile.value = file;
    importStoreName.value = file.name.replace('_export.zip', '').replace('.zip', '');
    
    // Open modal to ask for name
    uiStore.openModal('importDataStore');
    
    // Reset input
    event.target.value = '';
}

async function handleImportStore() {
    if (!importFile.value) return;
    
    isImporting.value = true;
    const formData = new FormData();
    formData.append('file', importFile.value);
    if (importStoreName.value.trim()) {
        formData.append('name', importStoreName.value.trim());
    }
    
    try {
        const response = await apiClient.post('/api/datastores/import', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        
        uiStore.addNotification(`Datastore '${response.data.name}' imported successfully`, 'success');
        await dataStore.fetchDataStores();
        uiStore.closeModal('importDataStore');
        
        // Select the newly imported store
        selectStore(response.data.id);
        
        // Cleanup
        importFile.value = null;
        importStoreName.value = '';
    } catch (error) {
        console.error('Import failed:', error);
        uiStore.addNotification(error.response?.data?.detail || 'Failed to import datastore', 'error');
    } finally {
        isImporting.value = false;
    }
}
</script>

<template>
    <div class="flex flex-col h-full w-full">
        <!-- Portals to Global Header -->
        <template v-if="isHeaderReady && currentSelectedStore && !isAddFormVisible">
            <!-- Portal for Title and Tabs -->
            <Teleport to="#global-header-title-target">
                <div class="flex items-center gap-4 h-full max-w-full overflow-hidden">
                    <div class="flex items-center gap-2 min-w-0">
                        <IconDatabase class="w-5 h-5 text-green-500 shrink-0" />
                        <h2 class="text-lg font-bold text-gray-800 dark:text-gray-100 truncate max-w-[200px]">{{ currentSelectedStore.name }}</h2>
                    </div>
                    <div class="h-5 w-px bg-gray-300 dark:border-gray-600 hidden md:block"></div>
                    <nav class="flex space-x-1 p-1 bg-gray-100 dark:bg-gray-700/50 rounded-lg">
                        <button @click="activeTab = 'documents'" :class="['px-3 py-1 text-xs font-medium rounded-md transition-all', activeTab === 'documents' ? 'bg-white dark:bg-gray-600 shadow text-blue-600 dark:text-blue-100' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700']">Documents</button>
                        <button @click="activeTab = 'query'" :class="['px-3 py-1 text-xs font-medium rounded-md transition-all', activeTab === 'query' ? 'bg-white dark:bg-gray-600 shadow text-blue-600 dark:text-blue-100' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700']">Query</button>
                        <button @click="activeTab = 'graph'" :class="['px-3 py-1 text-xs font-medium rounded-md transition-all', activeTab === 'graph' ? 'bg-white dark:bg-gray-600 shadow text-blue-600 dark:text-blue-100' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700']">Graph</button>
                        <button @click="activeTab = 'datalake'" :class="['px-3 py-1 text-xs font-medium rounded-md transition-all', activeTab === 'datalake' ? 'bg-white dark:bg-gray-600 shadow text-blue-600 dark:text-blue-100' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700']">Data Lake</button>
                    </nav>
                </div>
            </Teleport>

            <!-- Portal for Actions -->
            <Teleport to="#global-header-actions-target">
                <div class="flex items-center gap-1">
                    <button @click="showStoreInfo = true" class="btn-icon" title="Store Info"><IconInfo class="w-5 h-5"/></button>
                    <div class="h-4 w-px bg-gray-300 dark:border-gray-600 mx-1"></div>
                    <button v-if="currentSelectedStore.permission_level === 'owner'" @click="handleShareStore(currentSelectedStore)" class="btn-icon" title="Share"><IconShare class="w-5 h-5" /></button>
                    <button v-if="canReadWrite(currentSelectedStore)" @click="handleEditStore(currentSelectedStore)" class="btn-icon" title="Edit"><IconPencil class="w-5 h-5" /></button>
                    <button v-if="currentSelectedStore.permission_level === 'owner'" @click="handleDeleteStore(currentSelectedStore)" class="btn-icon-danger" title="Delete">
                        <IconAnimateSpin v-if="isLoadingAction === `delete_store_${currentSelectedStore.id}`" class="w-5 h-5 animate-spin" />
                        <IconTrash v-else class="w-5 h-5" />
                    </button>
                </div>
            </Teleport>
        </template>

        <!-- Inactive RAG State -->
        <div v-if="!hasActiveVectorizers && !filesLoading" class="grow flex flex-col items-center justify-center p-8 text-center bg-white dark:bg-gray-950">
            <div class="w-16 h-16 rounded-3xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 flex items-center justify-center text-amber-500 mb-4 shadow-lg">
                <IconDatabase class="w-8 h-8" />
            </div>
            <h3 class="text-xl font-bold text-gray-900 dark:text-white">Knowledge Studio Offline</h3>
            <p class="text-xs text-gray-500 max-w-sm mt-1">No active RAG embedding bindings are configured. An administrator must activate a RAG binding in Admin Control Center to enable data indexing.</p>
        </div>

        <!-- Main Content Area -->
        <div v-else class="p-4 overflow-y-auto grow h-full w-full">
            <div v-if="isAddFormVisible" class="p-4 sm:p-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm">
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

                    <!-- Chunking Strategy & Windows -->
                    <div class="space-y-4 p-4 bg-gray-50 dark:bg-gray-700/30 rounded-xl border dark:border-gray-700">
                        <div class="flex items-center justify-between">
                            <label for="new-ds-strategy" class="block text-xs font-black uppercase tracking-wider text-gray-700 dark:text-gray-300">Chunking Strategy (safe_store)</label>
                            <span class="text-[10px] font-mono font-bold text-blue-500 uppercase">{{ newStoreForm.chunking_strategy }}</span>
                        </div>

                        <select id="new-ds-strategy" v-model="newStoreForm.chunking_strategy" class="input-field text-xs">
                            <option v-for="strat in CHUNKING_STRATEGIES" :key="strat.value" :value="strat.value">
                                {{ strat.label }}
                            </option>
                        </select>
                        <p class="text-xs text-gray-500 italic">
                            {{ CHUNKING_STRATEGIES.find(s => s.value === newStoreForm.chunking_strategy)?.desc }}
                        </p>

                        <div v-if="user && user.allow_user_chunking_config" class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                            <div>
                                <label for="new-ds-chunk-size" class="block text-xs font-bold uppercase text-gray-500">Chunk Size (chars)</label>
                                <input id="new-ds-chunk-size" v-model.number="newStoreForm.chunk_size" type="number" min="10" max="64000" class="input-field text-xs mt-1">
                            </div>
                            <div>
                                <label for="new-ds-chunk-overlap" class="block text-xs font-bold uppercase text-gray-500">Chunk Overlap (chars)</label>
                                <input id="new-ds-chunk-overlap" v-model.number="newStoreForm.chunk_overlap" type="number" min="0" max="16000" class="input-field text-xs mt-1">
                            </div>
                        </div>
                    </div>

                    <div v-if="!isForcedVectorizerMode">
                        <label for="new-ds-vectorizer" class="block text-sm font-medium">Vectorizer Model</label>
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
                    </div>
                    <div v-else class="p-3 bg-amber-50 dark:bg-amber-950/30 rounded-xl border border-amber-200 dark:border-amber-800 text-xs">
                        <span class="font-bold text-amber-900 dark:text-amber-200">Enforced Vectorizer:</span>
                        <p class="text-gray-500 mt-0.5">The system administrator has assigned a mandatory global embedding vectorizer for all new knowledge bases.</p>
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
                <!-- Quick Status Bar -->
                <div class="px-6 py-3 bg-gray-50 dark:bg-gray-900/30 border-b border-gray-100 dark:border-gray-700/50 flex flex-wrap items-center justify-between gap-4 text-xs shrink-0 select-none">
                    <div class="flex items-center gap-4 flex-wrap">
                        <div class="flex items-center gap-1.5 text-gray-500 dark:text-gray-400">
                            <span class="font-black uppercase tracking-wider text-[9px] opacity-70">Vectorizer:</span>
                            <span class="px-2 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 font-bold capitalize">
                                {{ currentSelectedStore.vectorizer_name }}
                            </span>
                        </div>
                        <div v-if="currentSelectedStore.vectorizer_config && (currentSelectedStore.vectorizer_config.model_name || currentSelectedStore.vectorizer_config.model)" class="flex items-center gap-1.5 text-gray-500 dark:text-gray-400">
                            <span class="font-black uppercase tracking-wider text-[9px] opacity-70">Model:</span>
                            <span class="font-mono bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-gray-700 dark:text-gray-300 font-semibold">
                                {{ currentSelectedStore.vectorizer_config.model_name || currentSelectedStore.vectorizer_config.model }}
                            </span>
                        </div>
                        <div class="flex items-center gap-1.5 text-gray-500 dark:text-gray-400">
                            <span class="font-black uppercase tracking-wider text-[9px] opacity-70">Strategy:</span>
                            <span class="px-2 py-0.5 rounded bg-purple-500/10 text-purple-600 dark:text-purple-400 font-bold uppercase font-mono text-[10px]">
                                {{ currentSelectedStore.chunking_strategy || 'recursive' }}
                            </span>
                        </div>
                        <div class="flex items-center gap-1.5 text-gray-500 dark:text-gray-400">
                            <span class="font-black uppercase tracking-wider text-[9px] opacity-70">Window:</span>
                            <span class="font-semibold text-gray-700 dark:text-gray-300">
                                {{ currentSelectedStore.chunk_size }} chars <span class="opacity-50">/</span> {{ currentSelectedStore.chunk_overlap }} overlap
                            </span>
                        </div>
                    </div>
                    <div v-if="currentSelectedStore.description" class="text-gray-500 dark:text-gray-400 truncate max-w-xs md:max-w-md italic" :title="currentSelectedStore.description">
                        {{ currentSelectedStore.description }}
                    </div>
                </div>

                <!-- Content Area Tabs -->
                <div v-show="activeTab === 'documents'" class="p-6 grow overflow-y-auto space-y-8">
                    <div v-if="canReadWrite(currentSelectedStore)" class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-6 space-y-4">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xl font-semibold text-gray-900 dark:text-white">Add Documents</h3>
                            <div class="flex gap-2">
                                <button @click="selectedExtensions.clear()" class="text-[10px] font-black uppercase text-red-500 hover:underline">Clear Filters</button>
                                <button @click="extensionOptions.forEach(g => selectExtensionGroup(g.items))" class="text-[10px] font-black uppercase text-blue-500 hover:underline">Reset Defaults</button>
                            </div>
                        </div>

                        <!-- Extension Filter UI -->
                        <div class="p-4 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-600 shadow-inner">
                            <div class="space-y-4">
                                <div v-for="group in extensionOptions" :key="group.label" class="space-y-2">
                                    <div class="flex items-center justify-between">
                                        <span class="text-[9px] font-black uppercase tracking-widest text-gray-400">{{ group.label }}</span>
                                        <div class="flex gap-2">
                                            <button @click="selectExtensionGroup(group.items, true)" class="text-[8px] font-bold text-blue-400 hover:text-blue-600">All</button>
                                            <button @click="selectExtensionGroup(group.items, false)" class="text-[8px] font-bold text-gray-400 hover:text-red-400">None</button>
                                        </div>
                                    </div>
                                    <div class="flex flex-wrap gap-1.5">
                                        <button 
                                            v-for="ext in group.items" 
                                            :key="ext"
                                            @click="toggleExtension(ext)"
                                            :class="[
                                                'px-2 py-0.5 rounded text-[10px] font-bold transition-all border',
                                                selectedExtensions.has(ext) 
                                                    ? 'bg-blue-500 border-blue-600 text-white shadow-sm' 
                                                    : 'bg-gray-100 dark:bg-gray-700 border-transparent text-gray-500 dark:text-gray-400'
                                            ]"
                                        >
                                            {{ ext }}
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

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
                        
                        <!-- Upload Options Grid -->
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-4">
                            <!-- File Upload Area -->
                            <div 
                                @dragover.prevent="dragOver = true" 
                                @dragleave.prevent="dragOver = false" 
                                @drop.prevent="handleFileDrop" 
                                class="border-2 border-dashed rounded-lg p-6 text-center transition-colors flex flex-col justify-center min-h-[180px]" 
                                :class="{ 'border-blue-500 bg-blue-50 dark:bg-blue-900/20': dragOver, 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500': !dragOver }"
                            >
                                <input type="file" multiple ref="fileInputRef" @change="handleFileChange" class="hidden" accept=".pdf,.docx,.pptx,.xlsx,.msg,.vcf,.txt,.md,.py,.js,.ts,.html,.css,.c,.cpp,.h,.hpp,.cs,.java,.json,.xml,.sh,.bash,.zsh,.bat,.cmd,.owl,.ttl,.rdf,.vhd,.v,.rb,.php,.go,.rs,.swift,.kt,.yaml,.yml,.sql,.log,.csv">
                                <input type="file" ref="folderInputRef" @change="handleFileChange" class="hidden" webkitdirectory directory multiple>
                                
                                <p class="text-gray-600 dark:text-gray-300 font-medium mb-4">Drag & drop files here</p>
                                <div class="flex justify-center gap-2 flex-wrap">
                                    <button type="button" @click="fileInputRef.click()" class="btn btn-secondary btn-sm">Select File(s)</button>
                                    <button type="button" @click="folderInputRef.click()" class="btn btn-secondary btn-sm">Select Folder</button>
                                </div>
                            </div>

                            <!-- Multi-Service Ingestion Grid (Web, YouTube, Wikipedia, ArXiv, GitHub) -->
                            <div class="border rounded-xl p-5 bg-white dark:bg-gray-800 dark:border-gray-600 flex flex-col justify-between min-h-[180px]">
                                <div>
                                    <h4 class="text-xs font-black uppercase tracking-wider text-gray-500 mb-3 flex items-center gap-2">
                                        <IconGlobeAlt class="w-4 h-4 text-blue-500"/> Multi-Source Ingestion Services
                                    </h4>
                                    <p class="text-xs text-gray-500 mb-4">Ingest transcripts, academic research papers, repositories, and technical encyclopedias directly into this DataStore.</p>

                                    <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                        <button @click="openServiceImportModal('youtube')" class="btn btn-secondary btn-xs flex items-center justify-start gap-1.5 p-2 h-9">
                                            <IconYoutube class="w-4 h-4 text-red-500 shrink-0" />
                                            <span class="truncate">YouTube</span>
                                        </button>
                                        <button @click="openServiceImportModal('wikipedia')" class="btn btn-secondary btn-xs flex items-center justify-start gap-1.5 p-2 h-9">
                                            <IconWikipedia class="w-4 h-4 text-blue-500 shrink-0" />
                                            <span class="truncate">Wikipedia</span>
                                        </button>
                                        <button @click="openServiceImportModal('arxiv')" class="btn btn-secondary btn-xs flex items-center justify-start gap-1.5 p-2 h-9">
                                            <IconServer class="w-4 h-4 text-orange-500 shrink-0" />
                                            <span class="truncate">ArXiv Papers</span>
                                        </button>
                                        <button @click="openServiceImportModal('duckduckgo')" class="btn btn-secondary btn-xs flex items-center justify-start gap-1.5 p-2 h-9">
                                            <IconWeb class="w-4 h-4 text-emerald-500 shrink-0" />
                                            <span class="truncate">Web Search</span>
                                        </button>
                                        <button @click="openServiceImportModal('github')" class="btn btn-secondary btn-xs flex items-center justify-start gap-1.5 p-2 h-9">
                                            <IconServer class="w-4 h-4 text-purple-500 shrink-0" />
                                            <span class="truncate">GitHub Repo</span>
                                        </button>
                                        <button @click="openServiceImportModal('url')" class="btn btn-secondary btn-xs flex items-center justify-start gap-1.5 p-2 h-9">
                                            <IconGlobeAlt class="w-4 h-4 text-cyan-500 shrink-0" />
                                            <span class="truncate">URL Scraper</span>
                                        </button>
                                    </div>
                                </div>
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
                        
                        <!-- Upload Button with Spinner -->
                        <div class="flex justify-end items-center mt-4">
                            <button @click="handleUploadFiles" class="btn btn-primary" :disabled="isAnyTaskRunningForSelectedStore || selectedFilesToUpload.length === 0 || isUploading">
                                <IconAnimateSpin v-if="isUploading" class="w-5 h-5 mr-2 animate-spin" />
                                <IconArrowUpTray v-else class="w-5 h-5 mr-2" /> 
                                {{ isUploading ? 'Uploading...' : `Add ${selectedFilesToUpload.length} File(s)` }}
                            </button>
                        </div>
                    </div>
                    
                    <!-- Task Indicators -->
                    <div v-if="currentUploadTask" class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-700 text-sm">
                        <span class="font-semibold text-blue-800 dark:text-blue-300">File Uploading:</span> {{ currentUploadTask.progress }}% - {{ currentUploadTask.description }}
                    </div>
                    <div v-if="currentScrapeTask" class="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-700 text-sm">
                        <span class="font-semibold text-green-800 dark:text-green-300">Scraping:</span> {{ currentScrapeTask.progress }}% - {{ currentScrapeTask.description }}
                    </div>

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
                        <!-- Store / Vectorizer Loading Indicator -->
                        <div v-if="filesLoading || isStoreInitializing" class="py-16 text-center space-y-3 bg-gray-50/50 dark:bg-gray-900/30 rounded-2xl border border-gray-100 dark:border-gray-800">
                            <div class="flex items-center justify-center">
                                <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
                            </div>
                            <div>
                                <h4 class="font-bold text-sm text-gray-800 dark:text-gray-200 uppercase tracking-wider">Connecting to SafeStore & Probing Vectorizer</h4>
                                <p class="text-xs text-gray-500 font-mono mt-0.5">
                                    {{ currentSelectedStore.vectorizer_name }} · {{ currentSelectedStore.vectorizer_config?.model_name || currentSelectedStore.vectorizer_config?.model || 'Embedding Engine' }}
                                </p>
                            </div>
                        </div>

                        <div v-else-if="filesInSelectedStore.length === 0" class="text-center py-12 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-dashed dark:border-gray-700">
                            <IconFileText class="w-10 h-10 mx-auto text-gray-400 opacity-40 mb-2" />
                            <p class="text-xs text-gray-500 font-medium">No documents indexed in this DataStore yet.</p>
                        </div>

                        <!-- Rich Document List with Chunk Counts -->
                        <div v-else class="space-y-2">
                            <div 
                                v-for="file in filesInSelectedStore" 
                                :key="file.filename" 
                                class="p-3.5 bg-white dark:bg-gray-900/60 rounded-xl border border-gray-150 dark:border-gray-700/80 hover:border-blue-500/50 dark:hover:border-blue-500/50 transition-all flex items-center justify-between gap-4 group"
                            >
                                <div class="flex items-center gap-3 min-w-0">
                                    <input 
                                        v-if="canReadWrite(currentSelectedStore)"
                                        type="checkbox" 
                                        @change="toggleFileSelection(file.filename)" 
                                        :checked="selectedFilesToDelete.has(file.filename)" 
                                        class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 shrink-0"
                                    >
                                    <div class="p-2 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 shrink-0">
                                        <IconFileText class="w-4 h-4" />
                                    </div>
                                    <div class="min-w-0">
                                        <div class="flex items-center gap-2">
                                            <span 
                                                class="text-sm font-bold text-gray-900 dark:text-white truncate cursor-pointer hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                                                @click="viewFileContent(file)"
                                                :title="file.filename"
                                            >
                                                {{ file.filename }}
                                            </span>
                                            <IconAnimateSpin v-if="loadingFileContent === file.filename" class="w-3.5 h-3.5 text-blue-500 animate-spin shrink-0" />
                                        </div>
                                        <div class="flex items-center gap-2 mt-0.5 text-[10px] text-gray-400 font-mono">
                                            <span v-if="file.chunk_count !== undefined" class="font-bold text-blue-500 px-1.5 py-0.2 rounded bg-blue-50 dark:bg-blue-950/50 border border-blue-100 dark:border-blue-900/30">
                                                {{ file.chunk_count }} Chunks
                                            </span>
                                            <span v-if="file.char_count">{{ file.char_count.toLocaleString() }} chars</span>
                                        </div>
                                    </div>
                                </div>

                                <div class="flex items-center gap-2 shrink-0">
                                    <button @click="viewFileContent(file)" class="btn btn-secondary btn-xs py-1 px-2.5 text-xs font-bold" title="Inspect Document Chunks">
                                        Inspect
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div v-if="activeTab === 'query'" class="p-6 grow overflow-y-auto flex flex-col">
                    <div class="shrink-0 space-y-4">
                        <div class="flex items-center justify-between">
                            <div>
                                <h3 class="text-xl font-bold text-gray-900 dark:text-white">Knowledge Studio Query & Synthesis</h3>
                                <p class="text-xs text-gray-500 mt-0.5">Search semantic document vectors or synthesize grounded answers using the LLM.</p>
                            </div>
                        </div>

                        <form @submit.prevent="handleQueryStore" class="space-y-4">
                            <div>
                                <label for="query-text" class="block text-xs font-bold uppercase text-gray-500 mb-1">Question or Search Query</label>
                                <textarea id="query-text" v-model="queryText" rows="3" class="input-field text-sm" placeholder="Ask a question or search for technical concepts..."></textarea>
                            </div>
                            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                                <div>
                                    <label for="query-target" class="block text-xs font-bold uppercase text-gray-500 mb-1">Retrieval Target</label>
                                    <select id="query-target" v-model="retrievalTarget" class="input-field text-xs">
                                        <option value="chunks">🎯 Individual Chunks</option>
                                        <option value="window">🪟 Stitched Window</option>
                                        <option value="full_documents">📖 Full Reconstructed Docs</option>
                                    </select>
                                </div>
                                <div>
                                    <label for="query-mode" class="block text-xs font-bold uppercase text-gray-500 mb-1">Fusion Strategy</label>
                                    <select id="query-mode" v-model="queryMode" class="input-field text-xs">
                                        <option value="hybrid">Tri-Modal Hybrid (Dense + BM25 + RRF)</option>
                                        <option value="dense">Dense Semantic Only</option>
                                    </select>
                                </div>
                                <div>
                                    <label for="query-topk" class="block text-xs font-bold uppercase text-gray-500 mb-1">Top K / Count</label>
                                    <input id="query-topk" v-model.number="queryTopK" type="number" min="1" max="50" class="input-field text-xs">
                                </div>
                                <div>
                                    <label for="query-minsim" class="block text-xs font-bold uppercase text-gray-500 mb-1">Min Relevance %</label>
                                    <input id="query-minsim" v-model.number="queryMinSim" type="number" min="0" max="100" step="1" class="input-field text-xs">
                                </div>
                                <div v-if="retrievalTarget === 'window'" class="flex gap-2">
                                    <div class="flex-1">
                                        <label class="block text-[10px] font-bold text-gray-500 uppercase">Before</label>
                                        <input type="number" v-model.number="windowBefore" min="0" max="5" class="input-field text-xs">
                                    </div>
                                    <div class="flex-1">
                                        <label class="block text-[10px] font-bold text-gray-500 uppercase">After</label>
                                        <input type="number" v-model.number="windowAfter" min="0" max="5" class="input-field text-xs">
                                    </div>
                                </div>
                                <div v-else-if="queryMode === 'hybrid'" class="flex items-center gap-2">
                                    <div class="grow">
                                        <label class="block text-[10px] font-bold text-gray-500 uppercase">Dense: {{ denseWeight }}</label>
                                        <input type="range" v-model.number="denseWeight" min="0" max="1" step="0.1" class="w-full mt-1 accent-blue-600">
                                    </div>
                                    <div class="grow">
                                        <label class="block text-[10px] font-bold text-gray-500 uppercase">BM25: {{ bm25Weight }}</label>
                                        <input type="range" v-model.number="bm25Weight" min="0" max="1" step="0.1" class="w-full mt-1 accent-purple-600">
                                    </div>
                                </div>
                                <div class="self-end flex gap-2 sm:col-span-2 lg:col-span-1">
                                    <button type="submit" class="btn btn-secondary flex-1 text-xs font-bold h-10" :disabled="isQuerying || isAnswering || !queryText.trim()">
                                        <IconAnimateSpin v-if="isQuerying" class="w-4 h-4 mr-1.5 animate-spin" />
                                        <span>Retrieve</span>
                                    </button>
                                    <button type="button" @click="handleAskAiWithEvidence" class="btn btn-primary flex-1 text-xs font-bold h-10 flex items-center justify-center gap-1.5 shadow-md shadow-blue-500/10" :disabled="isQuerying || isAnswering || !queryText.trim()">
                                        <IconAnimateSpin v-if="isAnswering" class="w-4 h-4 animate-spin" />
                                        <IconSparkles v-else class="w-4 h-4 text-amber-300" />
                                        <span>Ask AI</span>
                                    </button>
                                </div>
                            </div>
                        </form>
                    </div>

                    <!-- Answer & Results Area -->
                    <div class="grow min-h-0 mt-6 border-t dark:border-gray-700/80 pt-6 space-y-6">
                        
                        <!-- ── [NEW] Grounded AI Answer Section ── -->
                        <div v-if="isAnswering" class="p-6 rounded-2xl border border-blue-200 dark:border-blue-900/50 bg-blue-50/40 dark:bg-blue-950/20 flex flex-col items-center justify-center gap-3 animate-pulse">
                            <IconAnimateSpin class="w-8 h-8 text-blue-600 dark:text-blue-400 animate-spin" />
                            <span class="text-xs font-bold text-blue-900 dark:text-blue-200 uppercase tracking-widest">Synthesizing Answer with Grounded Evidence...</span>
                        </div>

                        <div v-else-if="aiAnswer" class="p-6 rounded-3xl border border-blue-200/80 dark:border-blue-900/60 bg-gradient-to-br from-blue-50/60 via-white to-indigo-50/30 dark:from-blue-950/30 dark:via-gray-900/80 dark:to-indigo-950/20 shadow-xl space-y-4 animate-in fade-in slide-in-from-top-2">
                            <div class="flex items-center justify-between border-b border-blue-100 dark:border-blue-900/40 pb-3">
                                <div class="flex items-center gap-2.5">
                                    <div class="p-1.5 rounded-lg bg-blue-600 text-white shadow-md shadow-blue-500/20">
                                        <IconSparkles class="w-4 h-4" />
                                    </div>
                                    <div>
                                        <h4 class="text-sm font-black text-gray-900 dark:text-white uppercase tracking-tight">AI Synthesized Response</h4>
                                        <p class="text-[10px] text-gray-500">Grounded exclusively using retrieved evidence from {{ currentSelectedStore.name }}.</p>
                                    </div>
                                </div>
                                <div class="flex items-center gap-2">
                                    <span v-if="answerModelName" class="text-[9px] font-mono font-bold bg-white dark:bg-gray-800 px-2.5 py-1 rounded-full border dark:border-gray-700 text-blue-600 dark:text-blue-400">
                                        {{ answerModelName }}
                                    </span>
                                    <button @click="copyChunkText(aiAnswer)" class="p-1.5 rounded-lg text-gray-500 hover:text-blue-600 hover:bg-white dark:hover:bg-gray-800 transition-colors" title="Copy Answer">
                                        <IconCopy class="w-4 h-4" />
                                    </button>
                                </div>
                            </div>

                            <!-- Markdown Body -->
                            <div class="prose prose-sm dark:prose-invert max-w-none text-gray-800 dark:text-gray-200 leading-relaxed font-sans" v-html="renderChunkContent(aiAnswer)"></div>
                        </div>

                        <!-- Chunks Header & Filter Controls -->
                        <div class="flex flex-wrap justify-between items-center gap-3 mb-3">
                            <div class="flex items-center gap-3">
                                <h4 class="text-base font-bold text-gray-900 dark:text-white">Evidence Chunks ({{ queryResults.length }})</h4>
                                <span v-if="queryResults.length > 0" class="text-[10px] text-gray-400 font-mono">Retrieved via {{ queryMode }} mode</span>
                                <button v-if="queryResults.length > 0" @click="toggleAllChunksCollapse" class="text-xs font-bold text-blue-600 dark:text-blue-400 hover:underline">
                                    {{ collapsedChunks.size === queryResults.length ? 'Expand All' : 'Collapse All' }}
                                </button>
                            </div>

                            <div v-if="queryResults.length > 0" class="flex items-center gap-2">
                                <input type="text" v-model="searchInChunks" @keyup.enter="handleInChunkSearch" placeholder="Search in results..." class="input-field !py-1.5 !text-xs w-44 sm:w-56">
                                <button @click="handleInChunkSearch" class="btn btn-secondary btn-sm p-2"><IconMagnifyingGlass class="w-4 h-4" /></button>
                                <template v-if="searchMatches.length > 0">
                                    <button @click="navigateMatch(-1)" class="btn btn-secondary btn-sm p-2" title="Previous match">‹</button>
                                    <span class="text-xs text-gray-500 font-mono">{{ currentMatchIndex + 1 }} / {{ searchMatches.length }}</span>
                                    <button @click="navigateMatch(1)" class="btn btn-secondary btn-sm p-2" title="Next match">›</button>
                                </template>
                            </div>
                        </div>

                        <div v-if="isQuerying" class="text-center p-8 text-gray-500">
                            <IconAnimateSpin class="w-8 h-8 mx-auto animate-spin text-blue-500" />
                            <p class="mt-2 text-xs font-bold uppercase tracking-wider">Retrieving relevant chunks...</p>
                        </div>
                        <div v-else-if="queryError" class="p-4 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-xl border border-red-200 dark:border-red-800 text-xs">
                            {{ queryError }}
                        </div>
                        <div v-else-if="queryResults.length === 0 && !isAnswering" class="text-center py-12 bg-gray-50 dark:bg-gray-900/30 rounded-2xl border border-dashed dark:border-gray-800">
                            <IconDatabase class="w-8 h-8 text-gray-400 mx-auto opacity-40 mb-2" />
                            <p class="text-xs text-gray-500 font-medium">
                                {{ isQuerying ? 'Searching...' : (queryText.trim() ? `No chunks or documents exceeded the ${queryMinSim}% relevance threshold.` : 'Type a question or query above and click Retrieve or Ask AI.') }}
                            </p>
                        </div>
                        <div v-else-if="searchInChunks && searchMatches.length === 0" class="text-center py-6 text-xs text-gray-400">
                            No chunks match your search term.
                        </div>
                        <div v-else class="space-y-4 overflow-y-auto custom-scrollbar h-full pb-10">
                            <div v-for="(chunk, index) in queryResults" :key="index" :id="`chunk-${index}`" 
                                 class="border border-gray-200 dark:border-gray-700/80 rounded-2xl bg-white dark:bg-gray-900/70 shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden">

                                <!-- Clickable Chunk Header -->
                                <div @click="toggleChunkCollapse(index)" 
                                     class="p-4 flex flex-wrap justify-between items-center gap-2 cursor-pointer bg-gray-50/50 dark:bg-gray-800/30 hover:bg-gray-100/60 dark:hover:bg-gray-800/60 transition-colors select-none">
                                    <div class="flex items-center gap-2.5 min-w-0">
                                        <IconChevronRight class="w-4 h-4 text-gray-400 transition-transform duration-200 shrink-0" :class="{'rotate-90': !isChunkCollapsed(index)}" />
                                        <div class="p-1.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-lg">
                                            <IconFileText class="w-4 h-4 shrink-0" />
                                        </div>
                                        <span class="font-bold text-xs text-gray-800 dark:text-gray-200 truncate" :title="chunk.file_path || chunk.document_title">
                                            {{ (chunk.file_path || chunk.document_title || '').split(/[/\\]/).pop() || `Evidence #${index + 1}` }}
                                        </span>
                                    </div>

                                    <div class="flex items-center gap-2">
                                        <span v-if="chunk.fused_score !== undefined" 
                                              class="text-[10px] font-mono font-bold px-2.5 py-1 rounded-full bg-purple-50 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300 border border-purple-200 dark:border-purple-800/40">
                                            RRF: {{ chunk.fused_score.toFixed(4) }}
                                        </span>
                                        <span v-else-if="chunk.similarity_percent !== undefined" 
                                              class="text-[10px] font-mono font-bold px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/40">
                                            {{ chunk.similarity_percent.toFixed(1) }}% Match
                                        </span>

                                        <button @click.stop="copyChunkText(chunk.full_text || chunk.stitched_window_text || chunk.chunk_text)" class="p-1.5 text-gray-400 hover:text-blue-500 rounded-lg hover:bg-white dark:hover:bg-gray-700 transition-colors" title="Copy text">
                                            <IconCopy class="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                </div>

                                <!-- Collapsed 2-line preview -->
                                <div v-if="isChunkCollapsed(index)" @click="toggleChunkCollapse(index)" class="px-5 py-2.5 text-xs text-gray-500 dark:text-gray-400 line-clamp-2 italic cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 border-t dark:border-gray-800/50 bg-white/40 dark:bg-gray-900/40">
                                    "{{ (chunk.full_text || chunk.stitched_window_text || chunk.chunk_text || '').substring(0, 180) }}..."
                                </div>

                                <!-- Expanded Full Content Body -->
                                <div v-else class="p-5 pt-3 space-y-3.5 border-t border-gray-100 dark:border-gray-800">
                                    <!-- Styled Metadata Card (if present) -->
                                    <div v-if="parseChunk(chunk.chunk_text).metadata" 
                                         class="p-3.5 rounded-xl bg-gradient-to-br from-blue-50/60 to-indigo-50/30 dark:from-blue-950/20 dark:to-indigo-950/10 border border-blue-100 dark:border-blue-900/40 space-y-2">

                                        <div class="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-wider text-blue-600 dark:text-blue-400">
                                            <IconInfo class="w-3.5 h-3.5" />
                                            <span>Document Metadata</span>
                                        </div>

                                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                                            <div v-for="(meta, mIdx) in parseChunk(chunk.chunk_text).metadata" :key="mIdx" 
                                                 :class="meta.key.toLowerCase() === 'title' ? 'sm:col-span-2' : ''"
                                                 class="flex flex-col gap-0.5">
                                                <span class="text-[10px] font-bold uppercase text-gray-400 dark:text-gray-500">{{ meta.key }}</span>
                                                <span class="font-medium text-gray-800 dark:text-gray-200 leading-snug" 
                                                      :class="meta.key.toLowerCase() === 'title' ? 'font-bold text-gray-900 dark:text-white' : ''">
                                                    {{ meta.value }}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Chunk / Window / Full Document Content -->
                                    <div class="prose prose-sm dark:prose-invert max-w-none text-xs text-gray-800 dark:text-gray-200 leading-relaxed font-sans break-words selection:bg-blue-100 dark:selection:bg-blue-900"
                                         v-html="renderChunkContent(chunk.full_text || chunk.stitched_window_text || chunk.chunk_text)">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div v-if="activeTab === 'graph'" class="p-6 grow overflow-y-auto">
                    <DataStoreGraphManager :store="currentSelectedStore" :task="currentGraphTask" />
                </div>
                <div v-if="activeTab === 'datalake'" class="grow overflow-hidden h-full">
                    <DataLakeViewer :store="currentSelectedStore" />
                </div>
            </div>

            <!-- Loading Overlay -->
            <div v-if="loadingFileContent" class="absolute inset-0 z-50 flex flex-col items-center justify-center bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm rounded-lg">
                <IconAnimateSpin class="w-12 h-12 text-blue-600 dark:text-blue-400 mb-4 animate-spin" />
                <h3 class="text-xl font-bold text-gray-900 dark:text-white">Loading file content</h3>
                <p class="text-gray-600 dark:text-gray-300">Please stand by...</p>
            </div>
        </div>
    </div>
    
    <!-- Store Info & Diagnostic Modal -->
    <GenericModal :visible="showStoreInfo" @close="showStoreInfo = false" :title="currentSelectedStore ? `${currentSelectedStore.name} Diagnostic & Topology` : 'Store Details'" maxWidthClass="max-w-2xl">
        <template #body>
            <div v-if="currentSelectedStore" class="space-y-5 p-1 text-xs">
                <!-- Summary Card -->
                <div class="p-4 bg-gradient-to-br from-blue-50/70 to-indigo-50/40 dark:from-blue-950/30 dark:to-indigo-950/20 rounded-2xl border border-blue-100 dark:border-blue-900/50 space-y-3">
                    <div class="flex justify-between items-start">
                        <div>
                            <span class="text-[9px] font-black uppercase text-blue-600 dark:text-blue-400 tracking-widest">SafeStore Diagnostics</span>
                            <h3 class="text-base font-bold text-gray-900 dark:text-white">{{ currentSelectedStore.name }}</h3>
                        </div>
                        <span class="px-2.5 py-1 rounded-full bg-blue-600 text-white font-mono font-bold text-[10px] uppercase">
                            {{ currentSelectedStore.permission_level }}
                        </span>
                    </div>
                    <p class="text-gray-600 dark:text-gray-300 leading-relaxed">{{ currentSelectedStore.description || 'No description provided.' }}</p>
                </div>

                <!-- Diagnostic Stats Grid -->
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono">
                    <div class="p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-800">
                        <span class="text-[9px] font-bold text-gray-400 uppercase block mb-1">Documents</span>
                        <span class="text-lg font-black text-gray-900 dark:text-white">
                            {{ storeDiagnosticInfo?.documents?.total_documents ?? filesInSelectedStore.length }}
                        </span>
                    </div>
                    <div class="p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-800">
                        <span class="text-[9px] font-bold text-gray-400 uppercase block mb-1">Indexed Chunks</span>
                        <span class="text-lg font-black text-blue-500">
                            {{ storeDiagnosticInfo?.chunks?.total_chunks ?? '...' }}
                        </span>
                    </div>
                    <div class="p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-800">
                        <span class="text-[9px] font-bold text-gray-400 uppercase block mb-1">Graph Nodes</span>
                        <span class="text-lg font-black text-purple-500">
                            {{ storeDiagnosticInfo?.knowledge_graph?.total_nodes ?? 0 }}
                        </span>
                    </div>
                    <div class="p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-800">
                        <span class="text-[9px] font-bold text-gray-400 uppercase block mb-1">Graph Edges</span>
                        <span class="text-lg font-black text-emerald-500">
                            {{ storeDiagnosticInfo?.knowledge_graph?.total_relationships ?? 0 }}
                        </span>
                    </div>
                </div>

                <!-- Vectorizer and Chunking Parameters -->
                <div class="grid grid-cols-2 gap-3 p-3 bg-gray-50 dark:bg-gray-900 rounded-xl border dark:border-gray-800">
                    <div>
                        <span class="text-[9px] font-bold text-gray-400 uppercase block">Vectorizer Backend</span>
                        <span class="font-bold text-gray-800 dark:text-gray-200 capitalize">{{ currentSelectedStore.vectorizer_name }}</span>
                    </div>
                    <div>
                        <span class="text-[9px] font-bold text-gray-400 uppercase block">Chunking Strategy</span>
                        <span class="font-bold text-purple-500 uppercase">{{ currentSelectedStore.chunking_strategy || 'recursive' }}</span>
                    </div>
                    <div>
                        <span class="text-[9px] font-bold text-gray-400 uppercase block">Window / Overlap</span>
                        <span class="font-mono">{{ currentSelectedStore.chunk_size }} chars / {{ currentSelectedStore.chunk_overlap }} overlap</span>
                    </div>
                    <div>
                        <span class="text-[9px] font-bold text-gray-400 uppercase block">Storage Size</span>
                        <span class="font-mono">{{ (storeDiagnosticInfo?.size_bytes ? (storeDiagnosticInfo.size_bytes / 1024 / 1024).toFixed(2) + ' MB' : 'Calculating...') }}</span>
                    </div>
                </div>

                <div>
                    <h4 class="font-bold text-[10px] uppercase text-gray-400 tracking-wider mb-1.5">Raw Vectorizer Configuration</h4>
                    <div class="max-h-48 overflow-y-auto border rounded-xl dark:border-gray-800 p-2 bg-gray-50 dark:bg-gray-950 font-mono text-[10px]">
                        <JsonRenderer :json="currentSelectedStore.vectorizer_config" />
                    </div>
                </div>
                
                <!-- Actions -->
                <div class="flex flex-wrap gap-2 pt-2">
                    <button 
                        v-if="canReadWrite(currentSelectedStore) && !isForcedVectorizerMode"
                        @click="openRevectorizeModal"
                        class="btn btn-secondary btn-sm flex items-center gap-2"
                    >
                        <IconRefresh class="w-4 h-4 text-purple-500" />
                        Re-Vectorize
                    </button>

                    <button 
                        v-if="currentSelectedStore.permission_level === 'owner'"
                        @click="handleExportStore(currentSelectedStore)"
                        :disabled="isExporting === currentSelectedStore.id"
                        class="btn btn-secondary btn-sm flex items-center gap-2"
                    >
                        <IconAnimateSpin v-if="isExporting === currentSelectedStore.id" class="w-4 h-4 animate-spin" />
                        <IconArrowUpTray v-else class="w-4 h-4 rotate-180" />
                        {{ isExporting === currentSelectedStore.id ? 'Exporting...' : 'Export' }}
                    </button>
                    
                    <button 
                        v-if="currentSelectedStore.permission_level === 'owner'"
                        @click="handleDeleteStore(currentSelectedStore)"
                        :disabled="isLoadingAction === `delete_store_${currentSelectedStore.id}`"
                        class="btn btn-ghost btn-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                    >
                        <IconAnimateSpin v-if="isLoadingAction === `delete_store_${currentSelectedStore.id}`" class="w-4 h-4 animate-spin" />
                        <IconTrash v-else class="w-4 h-4" />
                        Delete
                    </button>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="showStoreInfo = false" class="btn btn-primary">Close</button>
        </template>
    </GenericModal>

    <!-- Revectorize Modal -->
    <GenericModal :visible="isRevectorizeOpen" @close="isRevectorizeOpen = false" title="Migrate & Re-Vectorize DataStore" maxWidthClass="max-w-md">
        <template #body>
            <div class="space-y-4 p-1">
                <p class="text-xs text-gray-500">Re-embed all document chunks in this DataStore using a new embedding model. Chunks will be re-vectorized in-place.</p>
                <div>
                    <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Target Vectorizer Model</label>
                    <select v-model="revectorizeTargetKey" class="input-field text-xs">
                        <option :value="null" disabled>-- Select New Model --</option>
                        <optgroup v-for="group in vectorizerOptions" :key="group.id" :label="group.alias || group.vectorizer_name">
                            <option v-for="model in group.models" :key="`${group.id}-${model.value}`" :value="`${group.alias}/${model.value}`">
                                {{ model.name }}
                            </option>
                        </optgroup>
                    </select>
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-end gap-2 w-full">
                <button @click="isRevectorizeOpen = false" class="btn btn-secondary" :disabled="isRevectorizing">Cancel</button>
                <button @click="handleRevectorize" class="btn btn-primary" :disabled="!revectorizeTargetKey || isRevectorizing">
                    <IconAnimateSpin v-if="isRevectorizing" class="w-4 h-4 mr-1.5 animate-spin" />
                    <span>{{ isRevectorizing ? 'Starting...' : 'Start Revectorization' }}</span>
                </button>
            </div>
        </template>
    </GenericModal>

    <!-- File Viewer Modal -->
    <GenericModal modalName="fileContent" title="Document Viewer" maxWidthClass="max-w-4xl">
        <template #body>
            <div v-if="viewingFile" class="space-y-4">
                <!-- Info Header -->
                <div class="bg-gray-50 dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700 flex flex-col gap-2">
                    <div class="flex justify-between items-start">
                        <div>
                            <h3 class="text-lg font-bold text-gray-900 dark:text-white break-all">
                                {{ viewingFile.metadata?.title || viewingFile.filename }}
                            </h3>
                            <p class="text-sm text-gray-500 dark:text-gray-400 font-mono mt-1" v-if="viewingFile.metadata?.title && viewingFile.metadata?.title !== viewingFile.filename">
                                {{ viewingFile.filename }}
                            </p>
                        </div>
                        <div class="text-right text-xs text-gray-500 dark:text-gray-400 space-y-1">
                            <div title="Total characters"><span class="font-semibold">{{ viewingFile.content.length.toLocaleString() }}</span> chars</div>
                            <div title="Approximate word count"><span class="font-semibold">{{ viewingFile.content.split(/\s+/).length.toLocaleString() }}</span> words</div>
                            <div title="Estimated tokens (char/4)"><span class="font-semibold">~{{ Math.ceil(viewingFile.content.length / 4).toLocaleString() }}</span> tokens</div>
                        </div>
                    </div>
                    
                    <div v-if="viewingFile.metadata && Object.keys(viewingFile.metadata).length > 0" class="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                        <details class="text-sm group">
                            <summary class="cursor-pointer text-blue-600 dark:text-blue-400 font-medium select-none">Show Metadata</summary>
                            <div class="mt-2 p-2 bg-white dark:bg-gray-900 rounded border dark:border-gray-700">
                                <JsonRenderer :json="viewingFile.metadata" />
                            </div>
                        </details>
                    </div>
                </div>

                <!-- Document Viewer Tabs: Raw Text vs Paginated Chunks -->
                <div class="flex items-center justify-between border-b dark:border-gray-700 pb-2">
                    <div class="flex gap-2 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg">
                        <button type="button" @click="docViewerTab = 'text'" class="px-3 py-1 text-xs font-bold rounded-md transition-all" :class="docViewerTab === 'text' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500'">
                            Raw Document Content
                        </button>
                        <button type="button" @click="docViewerTab = 'chunks'; if(!docChunksData) loadDocChunks(1);" class="px-3 py-1 text-xs font-bold rounded-md transition-all" :class="docViewerTab === 'chunks' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500'">
                            Indexed Chunks Pagination
                        </button>
                    </div>
                    <button @click="copyContent" class="btn btn-secondary btn-xs flex items-center gap-1">
                        <IconCopy class="w-3.5 h-3.5" /> Copy Text
                    </button>
                </div>

                <!-- TAB 1: Raw Text -->
                <div v-if="docViewerTab === 'text'" class="p-4 border rounded-lg dark:border-gray-700 bg-white dark:bg-gray-900 overflow-auto max-h-[60vh] whitespace-pre-wrap font-mono text-sm leading-relaxed">
                    {{ viewingFile.content }}
                </div>

                <!-- TAB 2: Paginated Chunks View -->
                <div v-else class="space-y-4 max-h-[60vh] overflow-y-auto">
                    <div v-if="isLoadingDocChunks" class="text-center py-10 text-gray-500">
                        <IconAnimateSpin class="w-6 h-6 animate-spin mx-auto text-blue-500" />
                        <span class="text-xs font-bold mt-2 block">Loading chunks...</span>
                    </div>
                    <template v-else-if="docChunksData">
                        <div v-for="c in docChunksData.chunks" :key="c.id" class="p-4 border rounded-xl dark:border-gray-700 bg-gray-50 dark:bg-gray-900/60 space-y-2">
                            <div class="flex justify-between items-center text-[10px] font-mono text-gray-400 border-b dark:border-gray-800 pb-1">
                                <span class="font-bold text-blue-500">Chunk #{{ c.chunk_index }}</span>
                                <span>Length: {{ c.text.length }} chars</span>
                            </div>
                            <div class="text-xs font-mono whitespace-pre-wrap text-gray-800 dark:text-gray-200">{{ c.text }}</div>
                        </div>

                        <!-- Pagination Controls -->
                        <div class="flex justify-between items-center pt-2">
                            <button @click="loadDocChunks(docChunksPage - 1)" :disabled="docChunksPage <= 1" class="btn btn-secondary btn-xs">Previous</button>
                            <span class="text-xs font-mono text-gray-500">Page {{ docChunksData.page }} of {{ docChunksData.total_pages }} ({{ docChunksData.total_chunks }} chunks)</span>
                            <button @click="loadDocChunks(docChunksPage + 1)" :disabled="docChunksPage >= docChunksData.total_pages" class="btn btn-secondary btn-xs">Next</button>
                        </div>
                    </template>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('fileContent')" class="btn btn-primary">Close</button>
        </template>
    </GenericModal>
    
    <!-- Import Modal -->
    <GenericModal modalName="importDataStore" title="Import Datastore" maxWidthClass="max-w-lg">
        <template #body>
            <div class="space-y-4">
                <div v-if="importFile" class="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <IconFileText class="w-8 h-8 text-blue-500" />
                    <div>
                        <div class="font-medium text-sm">{{ importFile.name }}</div>
                        <div class="text-xs text-gray-500">{{ (importFile.size / 1024 / 1024).toFixed(2) }} MB</div>
                    </div>
                </div>
                
                <div>
                    <label for="import-name" class="block text-sm font-medium">Datastore Name</label>
                    <input 
                        id="import-name" 
                        v-model="importStoreName" 
                        type="text" 
                        class="input-field mt-1" 
                        placeholder="Leave empty to use original name"
                    >
                </div>
                
                <p class="text-sm text-gray-500">
                    This will create a new datastore with the imported configuration and documents.
                    If a datastore with the same name exists, a number will be appended.
                </p>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('importDataStore'); importFile = null;" class="btn btn-secondary">Cancel</button>
            <button @click="handleImportStore" :disabled="isImporting" class="btn btn-primary">
                <IconAnimateSpin v-if="isImporting" class="w-4 h-4 mr-2 animate-spin" />
                {{ isImporting ? 'Importing...' : 'Import' }}
            </button>
        </template>
    </GenericModal>
</template>

<style>
@reference "tailwindcss";

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