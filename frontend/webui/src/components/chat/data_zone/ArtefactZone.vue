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
import IconDatabase from '../../../assets/icons/IconDatabase.vue';

const props = defineProps({
    notebookId: { type: String, default: null }
});

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const { activeDiscussionArtefacts, isLoadingArtefacts, starredArtefacts } = storeToRefs(discussionsStore);

function handleStarToggle(title) {
    discussionsStore.toggleStarArtefact(title);
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
    
    const currentId = String(idToUse.value); // Coerce to string for comparison
    
    // Filter artefacts for the current project context
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

async function handleLoadAllArtefacts() {
    if (!idToUse.value) return;
    const confirmed = await uiStore.showConfirmation({ title: 'Load All Artefacts?', message: `This will load all ${groupedArtefacts.value.length} source(s) into context.`, confirmText: 'Load All' });
    if (confirmed.confirmed) discussionsStore.loadAllArtefactsToDataZone(idToUse.value);
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

    // Set a timer to provide feedback if the backend is slow (likely installing packages)
    const installHintTimer = setTimeout(() => {
        uploadingMessage.value = 'Preparing environment (this might involve installing required libraries)...';
    }, 5000);

    try {
        await Promise.all(files.map(file => discussionsStore.addArtefact({ discussionId: idToUse.value, file, extractImages: true, pdfMode: currentUploadPdfMode.value })));
    } finally {
        clearTimeout(installHintTimer);
        isUploadingArtefact.value = false;
        if (artefactFileInput.value) artefactFileInput.value.value = '';
    }
}

// Watch for notebook ID or active discussion change to refresh list
watch(() => [props.notebookId, discussionsStore.currentDiscussionId], () => {
    handleRefreshArtefacts();
}, { immediate: true });

// Listen for global state change event from library to refresh sidebar list
onMounted(() => {
    handleRefreshArtefacts();
});

async function handleDrop(event) {
    isDraggingFile.value = false;
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0 && idToUse.value) {
        uiStore.addNotification('Adding files to workspace...', 'info');
        // CRITICAL: Set the active split title to switch the workspace focus
        uiStore.activeSplitArtefactTitle = files[0].name; 
        await Promise.all(files.map(file => discussionsStore.addArtefact({ 
            discussionId: idToUse.value, 
            file, 
            extractImages: true 
        })));
    }
}

function openArtefactInWorkspace(group) {
    if (!group || !group.versions || group.versions.length === 0) return;
    
    // Open the artefact in the workspace editor
    uiStore.isDataZoneVisible = true;
    uiStore.dataZoneTab = 'workspace';
    uiStore.activeSplitArtefactTitle = group.title;
}
function handleCreateNew() {
    // [FIX] Correctly trigger the manual creation modal
    uiStore.openModal('createArtefact', { 
        discussionId: discussionsStore.currentDiscussionId 
    });
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
                        <div class="p-1 min-w-[250px]">
                            <button @click="triggerArtefactFileUpload('text')" class="menu-item"><IconFileText class="w-4 h-4 mr-3 text-gray-500" /> <span>Text</span></button>
                            <button @click="triggerArtefactFileUpload('text_embedded_images')" class="menu-item"><IconFileText class="w-4 h-4 mr-3 text-blue-600" /> <span>Text + Embedded Images</span></button>
                            <button @click="triggerArtefactFileUpload('text_images')" class="menu-item"><IconFileText class="w-4 h-4 mr-3 text-blue-500" /> <span>Text + Pages as Images</span></button>
                            <button @click="triggerArtefactFileUpload('ocr')" class="menu-item"><IconEye class="w-4 h-4 mr-3 text-indigo-500" /> <span>OCR</span></button>
                            <button @click="triggerArtefactFileUpload('images_only')" class="menu-item"><IconPhoto class="w-4 h-4 mr-3 text-purple-500" /> <span>Images</span></button>
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
            <div class="flex items-center gap-1.5">
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
                        @star="handleStarToggle(group.title)"
                        @share="handleShareArtefact(group)"
                        @import="handleImportToCurrent(group)"
                    />
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>
