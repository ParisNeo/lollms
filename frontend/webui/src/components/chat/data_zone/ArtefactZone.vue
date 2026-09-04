<script setup>
import { computed, ref, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';

import ArtefactCard from '../../ui/Cards/ArtefactCard.vue';
import DropdownMenu from '../../ui/DropdownMenu/DropdownMenu.vue';
import DropdownSubmenu from '../../ui/DropdownMenu/DropdownSubmenu.vue';

// Icons
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconFileText from '../../../assets/icons/IconFileText.vue';
import IconWeb from '../../../assets/icons/ui/IconWeb.vue';
import IconArrowUpTray from '../../../assets/icons/IconArrowUpTray.vue';
import IconChevronRight from '../../../assets/icons/IconChevronRight.vue';
import IconGather from '../../../assets/icons/IconGather.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconFolder from '../../../assets/icons/IconFolder.vue';
import IconPhoto from '../../../assets/icons/IconPhoto.vue';
import IconEye from '../../../assets/icons/IconEye.vue';
import IconEyeOff from '../../../assets/icons/IconEyeOff.vue';
import IconDatabase from '../../../assets/icons/IconDatabase.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconXMark from '../../../assets/icons/IconXMark.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconLock from '../../../assets/icons/IconLock.vue';
import IconCircle from '../../../assets/icons/IconCircle.vue';
import IconArrowDownTray from '../../../assets/icons/IconArrowDownTray.vue';
import IconGitBranch from '../../../assets/icons/ui/IconGitBranch.vue';
import IconMicrophone from '../../../assets/icons/IconMicrophone.vue';

const props = defineProps({
    notebookId: { type: String, default: null }
});

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const { activeDiscussionArtefacts, isLoadingArtefacts, starredArtefacts } = storeToRefs(discussionsStore);

// --- Multi-Selection State ---
const selectionMode = ref(false);
const selectedTitles = ref(new Set());

const isAllSelected = computed(() => {
    if (groupedArtefacts.value.length === 0) return false;
    return selectedTitles.value.size === groupedArtefacts.value.length;
});

function toggleSelectAll() {
    if (isAllSelected.value) {
        selectedTitles.value.clear();
    } else {
        groupedArtefacts.value.forEach(group => {
            selectedTitles.value.add(group.title);
        });
    }
}

function toggleSelectTitle(title) {
    if (selectedTitles.value.has(title)) {
        selectedTitles.value.delete(title);
    } else {
        selectedTitles.value.add(title);
    }
}

function exitSelectionMode() {
    selectionMode.value = false;
    selectedTitles.value.clear();
}

// Batch Visibility updates
async function handleBatchVisibility(visibility) {
    if (selectedTitles.value.size === 0 || !idToUse.value) return;
    uiStore.addNotification(`Updating status for ${selectedTitles.value.size} file(s)...`, 'info');
    try {
        await Promise.all(
            Array.from(selectedTitles.value).map(title =>
                discussionsStore.updateArtefactVisibility({
                    discussionId: idToUse.value,
                    artefactTitle: title,
                    visibility
                })
            )
        );
        uiStore.addNotification('Batch update complete.', 'success');
        exitSelectionMode();
    } catch (e) {
        uiStore.addNotification('Failed to update some files.', 'error');
    }
}

// Batch Deletion
async function handleBatchDelete() {
    if (selectedTitles.value.size === 0 || !idToUse.value) return;
    const confirmed = await uiStore.showConfirmation({
        title: 'Delete Selected Files',
        message: `Are you sure you want to permanently delete these ${selectedTitles.value.size} file(s) from the workspace? This action cannot be undone.`,
        confirmText: 'Delete All',
        danger: true
    });

    if (confirmed.confirmed) {
        uiStore.addNotification('Deleting selected files...', 'info');
        try {
            await Promise.all(
                Array.from(selectedTitles.value).map(title =>
                    discussionsStore.deleteArtefact({
                        discussionId: idToUse.value,
                        artefactTitle: title
                    })
                )
            );
            uiStore.addNotification('Deletions completed.', 'success');
            exitSelectionMode();
        } catch (e) {
            uiStore.addNotification('Failed to delete some files.', 'error');
        }
    }
}

// Batch Export .lab Bundle
async function handleBatchExportBundle() {
    if (selectedTitles.value.size === 0 || !idToUse.value) return;
    
    const paths = Array.from(selectedTitles.value).map(title => {
        const matchingGroup = groupedArtefacts.value.find(g => g.title === title);
        const fileExt = matchingGroup?.versions[0]?.file_ext || '';
        return `workspace_data/${title}${fileExt}`;
    });

    await discussionsStore.exportLinkedBundle({
        discussionId: idToUse.value,
        paths,
        includeVersions: false
    });
}

function handleStarToggle(title) {
    discussionsStore.toggleStarArtefact(title);
}

const activeLoadedRagStores = computed(() => {
    const loadedIds = discussionsStore.activeDiscussion?.rag_datastore_ids || [];
    const all = [...(discussionsStore.dataStore?.ownedDataStores || []), ...(discussionsStore.dataStore?.sharedDataStores || [])];
    if (loadedIds.length > 0) {
        return loadedIds.map(id => all.find(s => s.id === id) || { id, name: `DataStore (${id.substring(0, 8)})` });
    }
    return all;
});

function handleOpenMakeRagStore(titlesArray = null) {
    const targetTitles = titlesArray || Array.from(selectedTitles.value);
    if (!targetTitles.length && !idToUse.value) return;

    uiStore.openModal('createDataStoreFromArtefacts', {
        discussionId: idToUse.value,
        titles: targetTitles,
        initialMode: 'create'
    });
}

function handleOpenBatchVectorizeExisting(datastoreId) {
    const targetTitles = Array.from(selectedTitles.value);
    if (!targetTitles.length || !idToUse.value) return;

    uiStore.openModal('createDataStoreFromArtefacts', {
        discussionId: idToUse.value,
        titles: targetTitles,
        initialMode: 'existing',
        targetDatastoreId: datastoreId
    });
}

async function handleSendToDataStore(title, datastoreId, datastoreName) {
    if (!title || !idToUse.value) return;

    uiStore.openModal('createDataStoreFromArtefacts', {
        discussionId: idToUse.value,
        titles: [title],
        initialMode: 'existing',
        targetDatastoreId: datastoreId
    });
}

function handleShareArtefact(group) {
    const latest = group.versions[0];
    if (!latest) return;
    uiStore.openModal('shareResource', {
        id: latest.title,
        name: latest.title,
        type: 'artefact',
        discussionId: latest.discussion_id || discussionsStore.currentDiscussionId
    });
}

async function handleImportToCurrent(group) {
    const latest = group.versions[0];
    if (!latest || !discussionsStore.currentDiscussionId) {
        uiStore.addNotification("Please select or start a discussion first.", "warning");
        return;
    }
    if (latest.discussion_id === discussionsStore.currentDiscussionId) {
        uiStore.addNotification("Artefact is already in the current discussion.", "info");
        return;
    }
    await discussionsStore.importArtefactFromSource({
        targetDiscussionId: discussionsStore.currentDiscussionId,
        sourceDiscussionId: latest.discussion_id,
        artefactTitle: latest.title
    });
}

const isUploadingArtefact = ref(false);
const uploadingMessage = ref('Processing files...');
const isArtefactsCollapsed = ref(false);
const artefactFileInput = ref(null);
const bundleFileInput = ref(null);
const isDraggingFile = ref(false);
const currentUploadPdfMode = ref('text_images');

const idToUse = computed(() => props.notebookId || discussionsStore.activeDiscussion?.id);

const groupedArtefacts = computed(() => {
    const allArtefacts = discussionsStore.activeDiscussionArtefacts;
    if (!allArtefacts || !Array.isArray(allArtefacts)) return [];
    
    const currentId = String(idToUse.value);
    
    const filtered = allArtefacts.filter(a => {
        const artDiscId = String(a.discussion_id || '');
        return !a.discussion_id || artDiscId === currentId;
    });

    const groups = filtered.reduce((acc, artefact) => {
        if (artefact && artefact.title) {
            if (!acc[artefact.title]) { acc[artefact.title] = { title: artefact.title, versions: [] }; }
            acc[artefact.title].versions.push(artefact);
        }
        return acc;
    }, {});

    Object.values(groups).forEach(group => {
        group.versions.sort((a, b) => b.version - a.version);
        group.isAnyVersionLoaded = group.versions.some(v => v.is_loaded);
    });
    return Object.values(groups);
});

function handleRefreshArtefacts() {
    if (idToUse.value) discussionsStore.fetchArtefacts(idToUse.value);
}

function handleCreateArtefact() {
    if (idToUse.value) uiStore.openModal('createArtefact', { discussionId: idToUse.value });
}

function triggerArtefactFileUpload(mode = 'text_and_embedded_images') { 
    currentUploadPdfMode.value = mode;
    artefactFileInput.value?.click(); 
}

function triggerBundleImport() {
    bundleFileInput.value?.click();
}

async function handleBundleImport(event) {
    const file = event.target.files[0];
    if (!file || !idToUse.value) return;
    try {
        const text = await file.text();
        const bundle = JSON.parse(text);
        if (!bundle.main_artefact) {
            uiStore.addNotification('Invalid bundle file. Main artefact is missing.', 'error');
            return;
        }
        isUploadingArtefact.value = true;
        uploadingMessage.value = 'Importing complete artefact bundle...';
        await discussionsStore.importArtefactBundle({
            discussionId: idToUse.value,
            bundle
        });
        uiStore.addNotification('Bundle imported successfully!', 'success');
    } catch (e) {
        console.error("Bundle import failed:", e);
        uiStore.addNotification('Failed to parse or import the bundle.', 'error');
    } finally {
        isUploadingArtefact.value = false;
        if (bundleFileInput.value) bundleFileInput.value.value = '';
    }
}

function handleImportFromUrl() {
    if (idToUse.value) {
        uiStore.openModal('scrapeUrl', { discussionId: idToUse.value, mode: 'url' });
    }
}

async function handleArtefactFileUpload(event) {
    const files = Array.from(event.target.files || []);
    if (!files.length || !idToUse.value) return;

    isUploadingArtefact.value = true;
    uploadingMessage.value = 'Uploading and analyzing files...';

    const installHintTimer = setTimeout(() => {
        uploadingMessage.value = 'Preparing environment (this might involve installing required libraries)...';
    }, 5000);

    try {
        await Promise.all(files.map(file => discussionsStore.addArtefact({ discussionId: idToUse.value, file, extractImages: true, auto_load: true, pdfMode: currentUploadPdfMode.value })));
        await discussionsStore.fetchArtefacts(idToUse.value);
        await discussionsStore.fetchContextStatus(idToUse.value);
    } finally {
        clearTimeout(installHintTimer);
        isUploadingArtefact.value = false;
        if (artefactFileInput.value) artefactFileInput.value.value = '';
    }
}

watch(() => [props.notebookId, discussionsStore.currentDiscussionId], () => {
    handleRefreshArtefacts();
}, { immediate: true });

onMounted(() => {
    handleRefreshArtefacts();
});

async function handleDrop(event) {
    isDraggingFile.value = false;
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0 && idToUse.value) {
        uiStore.addNotification('Adding files to workspace...', 'info');
        uiStore.activeSplitArtefactTitle = files[0].name; 
        await Promise.all(files.map(file => discussionsStore.addArtefact({ 
            discussionId: idToUse.value, 
            file, 
            extractImages: true 
        })));
    }
}

function openArtefactInWorkspace(group) {
    if (selectionMode.value) {
        toggleSelectTitle(group.title);
        return;
    }
    if (!group || !group.versions || group.versions.length === 0) return;
    uiStore.openWorkspaceArtefact(group.title);
}

function toggleSelectionMode() {
    selectionMode.value = !selectionMode.value;
    selectedTitles.value.clear();
}

async function handleCreateDiscussionWithAllArtefacts() {
    if (!idToUse.value || groupedArtefacts.value.length === 0) return;
    const titles = groupedArtefacts.value.map(g => g.title);
    await discussionsStore.createDiscussionWithArtefacts({
        sourceDiscussionId: idToUse.value,
        artefactTitles: titles
    });
}

async function handleBatchCreateDiscussion() {
    if (!idToUse.value || selectedTitles.value.size === 0) return;
    const titles = Array.from(selectedTitles.value);
    await discussionsStore.createDiscussionWithArtefacts({
        sourceDiscussionId: idToUse.value,
        artefactTitles: titles
    });
    exitSelectionMode();
}
</script>

<template>
    <div @dragover.prevent="isDraggingFile = true" @dragleave.prevent="isDraggingFile = false" @drop.prevent="handleDrop" class="p-2 flex flex-col grow min-h-0 relative">
    <input type="file" ref="artefactFileInput" @change="handleArtefactFileUpload" multiple class="hidden">
    <input type="file" ref="bundleFileInput" @change="handleBundleImport" accept=".json" class="hidden">

    <!-- Drop Overlay -->
        <div v-if="isDraggingFile" class="absolute inset-0 bg-blue-500/10 border-2 border-dashed border-blue-500 rounded-lg z-50 flex items-center justify-center pointer-events-none">
            <p class="text-sm font-bold text-blue-600">Drop to Add</p>
        </div>

        <div class="flex justify-between items-center p-3 mb-2 shrink-0 bg-gray-50 dark:bg-gray-800/50 rounded-lg border dark:border-gray-700">
            <div class="flex items-center gap-1.5">
                <DropdownMenu icon="plus" title="Add Local Document" buttonClass="p-1 hover:bg-gray-200 dark:hover:bg-gray-700/50 rounded-lg transition-colors flex items-center justify-center">
                    <template #icon>
                        <IconPlus class="w-4.5 h-4.5 text-emerald-500" />
                    </template>
                    <DropdownSubmenu title="Add Document" icon="file-text" collection="ui">
                        <div class="p-1 min-w-[260px]">
                            <button @click="triggerArtefactFileUpload('as_is')" class="menu-item"><IconFolder class="w-4 h-4 mr-3 text-emerald-500" /> <span>Native File (as-is)</span></button>
                            <button @click="triggerArtefactFileUpload('text')" class="menu-item"><IconFileText class="w-4 h-4 mr-3 text-gray-500" /> <span>Text Only</span></button>
                            <button @click="triggerArtefactFileUpload('text_embedded_images')" class="menu-item"><IconFileText class="w-4 h-4 mr-3 text-blue-600" /> <span>Text + Embedded Images</span></button>
                            <button @click="triggerArtefactFileUpload('text_images')" class="menu-item"><IconFileText class="w-4 h-4 mr-3 text-blue-500" /> <span>Text + Pages as Images</span></button>
                            <button @click="triggerArtefactFileUpload('ocr')" class="menu-item"><IconEye class="w-4 h-4 mr-3 text-indigo-500" /> <span>OCR (Vision LLM)</span></button>
                            <button @click="triggerArtefactFileUpload('images_only')" class="menu-item"><IconPhoto class="w-4 h-4 mr-3 text-purple-500" /> <span>Images Only</span></button>
                            <button @click="triggerArtefactFileUpload('audio_stt')" class="menu-item"><IconMicrophone class="w-4 h-4 mr-3 text-cyan-500" /> <span>Transcribe Audio (STT)</span></button>
                        </div>
                    </DropdownSubmenu>
                    <DropdownSubmenu title="Add Data" icon="database" collection="ui">
                        <div class="p-1 min-w-[320px]">
                            <button @click="triggerArtefactFileUpload('data')" class="menu-item">
                                <IconDatabase class="w-4 h-4 mr-3 text-green-500" />
                                <span>Data Interface (Spreadsheet / SQLite DB Tables)</span>
                            </button>
                            <button @click="triggerArtefactFileUpload('data_bundle')" class="menu-item">
                                <IconFolder class="w-4 h-4 mr-3 text-yellow-500" />
                                <span>Folder Bundle (Consolidates all data files in folder)</span>
                            </button>
                        </div>
                    </DropdownSubmenu>
                    <div class="p-1">
                        <button @click="triggerBundleImport" class="menu-item"><IconRefresh class="w-4 h-4 mr-3 text-teal-500" /> <span>Import Bundle (.json)</span></button>
                        <button @click="handleCreateArtefact" class="menu-item"><IconPencil class="w-4 h-4 mr-3 text-orange-500" /> <span>Create Document (Manual)</span></button>
                    </div>
                </DropdownMenu>
                <span class="text-xs font-bold uppercase tracking-widest text-gray-500 select-none">Repository</span>
            </div>
            
            <!-- Context Control Triggers -->
            <div class="flex items-center gap-1.5">
                 <button v-if="groupedArtefacts.length > 0 && !selectionMode" @click="handleCreateDiscussionWithAllArtefacts" class="p-1.5 hover:text-purple-600 hover:bg-gray-200 dark:hover:bg-gray-700/50 rounded-lg transition-all text-purple-500" title="Start New Chat with All Files">
                     <IconGitBranch class="w-4.5 h-4.5" />
                 </button>
                 <button @click="toggleSelectionMode" class="p-1.5 rounded-lg transition-all" :class="selectionMode ? 'bg-blue-500 text-white shadow-sm' : 'text-gray-400 hover:text-blue-500 hover:bg-gray-200 dark:hover:bg-gray-700/50'" title="Batch Operations (Select Multiple)">
                     <IconGather class="w-4.5 h-4.5" />
                 </button>
                 <button @click="handleImportFromUrl" class="p-1.5 hover:text-blue-500 hover:bg-gray-200 dark:hover:bg-gray-700/50 rounded-lg transition-all" title="Import from URL"><IconWeb class="w-4.5 h-4.5 text-blue-500" /></button>
                 <button @click="handleRefreshArtefacts" class="p-1.5 hover:text-blue-500 hover:bg-gray-200 dark:hover:bg-gray-700/50 rounded-lg transition-all" title="Refresh List"><IconRefresh class="w-4.5 h-4.5" :class="{'animate-spin': isLoadingArtefacts}" /></button>
            </div>
        </div>

        <div v-if="!isArtefactsCollapsed" class="grow overflow-y-auto custom-scrollbar">
            <!-- Active Processing Item -->
            <div v-if="isUploadingArtefact" class="mb-4 animate-in fade-in slide-in-from-top-2">
                 <div class="flex items-center gap-4 p-3 bg-blue-50/50 dark:bg-blue-900/10 rounded-xl border border-blue-100 dark:border-blue-800 shadow-sm">
                    <div class="w-10 h-10 shrink-0 flex items-center justify-center bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700">
                        <IconAnimateSpin class="w-5 h-5 text-blue-500 animate-spin" />
                    </div>
                    <div class="flex flex-col min-w-0">
                        <span class="text-[9px] font-black uppercase tracking-widest text-blue-500 mb-0.5">Workspace Ingestion</span>
                        <p class="text-[11px] font-bold text-gray-700 dark:text-gray-300 leading-tight">
                            {{ uploadingMessage }}
                        </p>
                    </div>
                 </div>
            </div>

            <!-- Global Selection Action Header -->
            <div v-if="selectionMode && groupedArtefacts.length > 0" class="flex justify-between items-center p-2 mb-2 bg-blue-50 dark:bg-blue-900/10 rounded-lg border border-blue-100 dark:border-blue-800 text-xs animate-in fade-in">
                <label class="flex items-center gap-2 cursor-pointer select-none">
                    <input 
                        type="checkbox" 
                        :checked="isAllSelected" 
                        @change="toggleSelectAll" 
                        class="rounded text-blue-600 focus:ring-blue-500 border-gray-300 dark:border-gray-700 bg-transparent h-4 w-4"
                    />
                    <span class="font-bold text-gray-700 dark:text-gray-300">Select All ({{ selectedTitles.size }} / {{ groupedArtefacts.length }})</span>
                </label>
                <button @click="exitSelectionMode" class="text-blue-500 hover:text-red-500 font-bold uppercase text-[10px]">Cancel</button>
            </div>

            <div v-if="isLoadingArtefacts && !isUploadingArtefact" class="text-center py-10"><IconAnimateSpin class="w-6 h-6 text-gray-300 animate-spin mx-auto" /></div>
            <div v-else-if="groupedArtefacts.length === 0 && !isUploadingArtefact" class="text-center py-10 text-gray-400 text-[10px] uppercase font-bold tracking-widest opacity-50">Empty</div>
            <div v-else class="space-y-1">
                <div 
                    v-for="group in groupedArtefacts" 
                    :key="group.title"
                    @click="openArtefactInWorkspace(group)"
                    class="cursor-pointer"
                >
                    <ArtefactCard 
                        :artefact-group="group" 
                        :is-starred="starredArtefacts.includes(group.title)"
                        :selection-mode="selectionMode"
                        :is-selected="selectedTitles.has(group.title)"
                        @toggle-select="toggleSelectTitle"
                        @star="handleStarToggle(group.title)"
                        @share="handleShareArtefact(group)"
                        @import="handleImportToCurrent(group)"
                        @send-to-datastore="(dsId, dsName) => handleSendToDataStore(group.title, dsId, dsName)"
                    />
                </div>
            </div>
        </div>

        <!-- Floating Batch Actions Control Bar -->
        <Transition
            enter-active-class="transition-all duration-300 ease-out"
            enter-from-class="opacity-0 translate-y-6"
            enter-to-class="opacity-100 translate-y-0"
            leave-active-class="transition-all duration-200 ease-in"
            leave-from-class="opacity-100"
            leave-to-class="opacity-0 translate-y-6"
        >
            <div v-if="selectionMode && selectedTitles.size > 0" class="absolute bottom-2 inset-x-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl shadow-2xl p-3 z-40 flex items-center justify-between gap-4">
                <div class="flex flex-col">
                    <span class="text-[9px] font-black uppercase tracking-widest text-blue-500 mb-0.5">Batch Mode</span>
                    <span class="text-xs font-bold text-gray-800 dark:text-gray-200">{{ selectedTitles.size }} item(s) selected</span>
                </div>
                
                <div class="flex items-center gap-1.5">
                    <!-- New Chat with Selected Artefacts -->
                    <button @click="handleBatchCreateDiscussion" class="px-2.5 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs flex items-center gap-1 shadow-sm transition-all active:scale-95" title="Start new conversation with selected documents">
                        <IconGitBranch class="w-3.5 h-3.5" />
                        <span>New Chat</span>
                    </button>

                    <!-- Make RAG Store (Direct Action) -->
                    <button @click="handleOpenMakeRagStore()" class="px-2.5 py-1.5 rounded-lg bg-green-600 hover:bg-green-700 text-white font-bold text-xs flex items-center gap-1 shadow-sm transition-all active:scale-95" title="Create a new DataStore from selected documents and link it to this chat">
                        <IconDatabase class="w-3.5 h-3.5" />
                        <span>Make RAG Store</span>
                    </button>

                    <!-- Vectorize to Existing DataStore Dropdown -->
                    <DropdownMenu v-if="activeLoadedRagStores.length > 0" icon="database" buttonClass="p-2 bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 rounded-lg" title="Vectorize into Existing DataStore">
                        <div class="px-3 py-1 text-[9px] font-black uppercase text-gray-400 tracking-wider">Target DataStore</div>
                        <button v-for="store in activeLoadedRagStores" :key="`batch-ds-${store.id}`" @click="handleOpenBatchVectorizeExisting(store.id)" class="menu-item text-xs">
                            <IconDatabase class="w-4 h-4 mr-2 text-green-500 shrink-0" />
                            <span class="truncate">{{ store.name }}</span>
                        </button>
                    </DropdownMenu>

                    <!-- Batch Visibility Dropdown -->
                    <DropdownMenu icon="eye" buttonClass="p-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 rounded-lg text-gray-600 dark:text-gray-300" title="Set Attention">
                        <button @click="handleBatchVisibility('FULL')" class="menu-item gap-2">
                            <IconCheckCircle class="w-4 h-4 text-green-500" />
                            <span>Load Full Content [C]</span>
                        </button>
                        <button @click="handleBatchVisibility('METADATA')" class="menu-item gap-2">
                            <IconEye class="w-4 h-4 text-sky-500" />
                            <span>Metadata-Only [M]</span>
                        </button>
                        <button @click="handleBatchVisibility('TREE_UNLOCKABLE')" class="menu-item gap-2">
                            <IconCircle class="w-4 h-4 text-gray-400" />
                            <span>Tree Unlockable [U]</span>
                        </button>
                        <button @click="handleBatchVisibility('LOCKED')" class="menu-item gap-2">
                            <IconLock class="w-4 h-4 text-orange-500" />
                            <span>Tree Locked [L]</span>
                        </button>
                        <button @click="handleBatchVisibility('HIDDEN')" class="menu-item gap-2">
                            <IconEyeOff class="w-4 h-4 text-red-500" />
                            <span>Hidden</span>
                        </button>
                    </DropdownMenu>

                    <!-- Export Bundle -->
                    <button @click="handleBatchExportBundle" class="p-2 bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/30 dark:hover:bg-blue-800/40 text-blue-600 dark:text-blue-400 rounded-lg" title="Export as Linked .lab Bundle">
                        <IconFolder class="w-4 h-4" />
                    </button>

                    <!-- Batch Delete -->
                    <button @click="handleBatchDelete" class="p-2 bg-red-50 hover:bg-red-100 dark:bg-red-900/30 dark:hover:bg-red-800/40 text-red-600 dark:text-red-400 rounded-lg" title="Delete Selected">
                        <IconTrash class="w-4 h-4" />
                    </button>
                </div>
            </div>
        </Transition>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>