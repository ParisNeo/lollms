<script setup>
import { computed, ref, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';

import ArtefactCard from '../../ui/Cards/ArtefactCard.vue';
import DropdownMenu from '../../ui/DropdownMenu/DropdownMenu.vue';

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

const props = defineProps({
    notebookId: { type: String, default: null }
});

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const { activeDiscussionArtefacts, isLoadingArtefacts } = storeToRefs(discussionsStore);

const isUploadingArtefact = ref(false);
const isArtefactsCollapsed = ref(false);
const artefactFileInput = ref(null);
const isDraggingFile = ref(false);

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

function triggerArtefactFileUpload() { artefactFileInput.value?.click(); }

function handleImportFromUrl() {
    const url = prompt("Please enter the URL to import:");
    if (url && idToUse.value) discussionsStore.importArtefactFromUrl(idToUse.value, url);
}

async function handleArtefactFileUpload(event) {
    const files = Array.from(event.target.files || []);
    if (!files.length || !idToUse.value) return;

    isUploadingArtefact.value = true;
    try {
        await Promise.all(files.map(file => discussionsStore.addArtefact({ discussionId: idToUse.value, file, extractImages: true })));
    } finally {
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

</script>

<template>
    <div @dragover.prevent="isDraggingFile = true" @dragleave.prevent="isDraggingFile = false" @drop.prevent="handleDrop" class="p-2 flex flex-col flex-grow min-h-0 relative">
        <input type="file" ref="artefactFileInput" @change="handleArtefactFileUpload" multiple class="hidden">
        
        <!-- Drop Overlay -->
        <div v-if="isDraggingFile" class="absolute inset-0 bg-blue-500/10 border-2 border-dashed border-blue-500 rounded-lg z-50 flex items-center justify-center pointer-events-none">
            <p class="text-sm font-bold text-blue-600">Drop to Add</p>
        </div>

        <div class="flex justify-between items-center p-3 mb-2 flex-shrink-0 bg-gray-50 dark:bg-gray-800/50 rounded-lg border dark:border-gray-700">
            <div class="flex items-center gap-2">
                <IconPlus class="w-4 h-4 text-emerald-500 cursor-pointer" @click="handleCreateArtefact" />
                <span class="text-xs font-bold uppercase tracking-widest text-gray-500">Repository</span>
            </div>
            <div class="flex gap-1">
                 <button @click="triggerArtefactFileUpload" class="p-1.5 hover:text-blue-500 transition-colors" title="Upload Files"><IconArrowUpTray class="w-4 h-4" /></button>
                 <button @click="handleImportFromUrl" class="p-1.5 hover:text-blue-500 transition-colors" title="Import from URL"><IconWeb class="w-4 h-4" /></button>
                 <button @click="handleRefreshArtefacts" class="p-1.5 hover:text-blue-500 transition-colors" title="Refresh List"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingArtefacts}" /></button>
            </div>
        </div>
        <div v-if="!isArtefactsCollapsed" class="flex-grow overflow-y-auto custom-scrollbar">
            <div v-if="isLoadingArtefacts" class="text-center py-10"><IconAnimateSpin class="w-6 h-6 text-gray-300 animate-spin mx-auto" /></div>
            <div v-else-if="groupedArtefacts.length === 0" class="text-center py-10 text-gray-400 text-[10px] uppercase font-bold tracking-widest opacity-50">Empty</div>
            <div v-else class="space-y-1">
                <div 
                    v-for="group in groupedArtefacts" 
                    :key="group.title"
                    @click="openArtefactInWorkspace(group)"
                    class="cursor-pointer"
                >
                    <ArtefactCard :artefact-group="group" />
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>
