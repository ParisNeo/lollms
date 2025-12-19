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
    if (!activeDiscussionArtefacts.value || !Array.isArray(activeDiscussionArtefacts.value)) return [];
    
    // Filter by relevant ID if we are in Notebook context to prevent cross-contamination
    const filtered = props.notebookId 
        ? activeDiscussionArtefacts.value.filter(a => a.discussion_id === props.notebookId)
        : activeDiscussionArtefacts.value;

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
    if (idToUse.value) uiStore.openModal('artefactEditor', { discussionId: idToUse.value });
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

// Watch for notebook ID change to refresh list
watch(() => props.notebookId, (newId) => {
    if (newId) handleRefreshArtefacts();
}, { immediate: true });

async function handleDrop(event) {
    isDraggingFile.value = false;
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0 && idToUse.value) {
        uiStore.addNotification('Adding files to workspace...', 'info');
        await Promise.all(files.map(file => discussionsStore.addArtefact({ 
            discussionId: idToUse.value, 
            file, 
            extractImages: true 
        })));
    }
}
</script>

<template>
    <div @dragover.prevent="isDraggingFile = true" @dragleave.prevent="isDraggingFile = false" @drop.prevent="handleDrop" class="p-2 flex flex-col flex-grow min-h-0 relative">
        <input type="file" ref="artefactFileInput" @change="handleArtefactFileUpload" multiple class="hidden">
        
        <!-- Drop Overlay -->
        <div v-if="isDraggingFile" class="absolute inset-0 bg-blue-500/10 border-2 border-dashed border-blue-500 rounded-lg z-50 flex items-center justify-center pointer-events-none">
            <p class="text-sm font-bold text-blue-600">Drop to Add</p>
        </div>

        <div class="flex justify-between items-center mb-2 flex-shrink-0 bg-white/50 dark:bg-gray-800/50 p-1 rounded">
            <button @click="isArtefactsCollapsed = !isArtefactsCollapsed" class="flex items-center gap-2 text-[10px] font-black uppercase text-gray-500 dark:text-gray-400">
                <IconChevronRight class="w-3.5 h-3.5 transition-transform" :class="{'rotate-90': !isArtefactsCollapsed}"/>
                <span>{{ notebookId ? 'Sources' : 'Artefacts' }}</span>
            </button>
            <div class="flex items-center gap-0.5">
                <button @click="handleRefreshArtefacts" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500" title="Refresh">
                    <IconRefresh class="w-3.5 h-3.5" :class="{'animate-spin': isLoadingArtefacts}" />
                </button>
                <DropdownMenu icon="menu" buttonClass="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500" title="Actions">
                    <button @click="handleLoadAllArtefacts" class="menu-item"><IconGather class="w-4 h-4 mr-2" />Load All</button>
                    <button @click="handleCreateArtefact" class="menu-item"><IconPencil class="w-4 h-4 mr-2" />Manual Entry</button>
                    <button @click="handleImportFromUrl" class="menu-item"><IconWeb class="w-4 h-4 mr-2" />Scrape URL</button>
                    <button @click="triggerArtefactFileUpload" class="menu-item"><IconArrowUpTray class="w-4 h-4 mr-2" />Upload File</button>
                </DropdownMenu>
            </div>
        </div>
        <div v-if="!isArtefactsCollapsed" class="flex-grow overflow-y-auto custom-scrollbar">
            <div v-if="isLoadingArtefacts" class="text-center py-10"><IconAnimateSpin class="w-6 h-6 text-gray-300 animate-spin mx-auto" /></div>
            <div v-else-if="groupedArtefacts.length === 0" class="text-center py-10 text-gray-400 text-[10px] uppercase font-bold tracking-widest opacity-50">Empty</div>
            <div v-else class="space-y-1">
                <ArtefactCard v-for="group in groupedArtefacts" :key="group.title" :artefact-group="group" />
            </div>
        </div>
    </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>
