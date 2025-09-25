<script setup>
import { computed, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';

import ArtefactCard from '../../ui/Cards/ArtefactCard.vue';

// Icons
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconFileText from '../../../assets/icons/IconFileText.vue';
import IconWeb from '../../../assets/icons/ui/IconWeb.vue';
import IconArrowUpTray from '../../../assets/icons/IconArrowUpTray.vue';
import IconChevronRight from '../../../assets/icons/IconChevronRight.vue';
import IconGather from '../../../assets/icons/IconGather.vue';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const router = useRouter();

const { activeDiscussionArtefacts, isLoadingArtefacts } = storeToRefs(discussionsStore);

const showUrlImport = ref(false);
const isUploadingArtefact = ref(false);
const isArtefactsCollapsed = ref(false);
const artefactFileInput = ref(null);
const isDraggingFile = ref(false);

const activeDiscussion = computed(() => discussionsStore.activeDiscussion);

const groupedArtefacts = computed(() => {
    if (!activeDiscussionArtefacts.value || !Array.isArray(activeDiscussionArtefacts.value)) return [];
    const groups = activeDiscussionArtefacts.value.reduce((acc, artefact) => {
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
    if (activeDiscussion.value) discussionsStore.fetchArtefacts(activeDiscussion.value.id);
}

async function handleLoadAllArtefacts() {
    if (!activeDiscussion.value) return;
    const confirmed = await uiStore.showConfirmation({ title: 'Load All Artefacts?', message: `This will clear the current Discussion Data Zone and load all ${groupedArtefacts.value.length} artefact(s).`, confirmText: 'Load All' });
    if (confirmed) discussionsStore.loadAllArtefactsToDataZone(activeDiscussion.value.id);
}

function handleCreateArtefact() {
    if (activeDiscussion.value) uiStore.openModal('artefactEditor', { discussionId: activeDiscussion.value.id });
}

function triggerArtefactFileUpload() {
    artefactFileInput.value?.click();
}


async function handleArtefactFileUpload(event) {
    const files = Array.from(event.target.files || []);
    if (!files.length || !activeDiscussion.value) return;

    const imageExtractableTypes = [
        'application/pdf', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    ];
    // .msg is often application/octet-stream, so we check extension
    const imageExtractableExtensions = ['.pdf', '.docx', '.pptx', '.msg'];
    
    const filesToUpload = [];

    for (const file of files) {
        let extractImages = true;
        const fileExtension = `.${file.name.split('.').pop()}`.toLowerCase();

        if (imageExtractableTypes.includes(file.type) || imageExtractableExtensions.includes(fileExtension)) {
            const result = await uiStore.showConfirmation({
                title: `Extract Images from ${file.name}?`,
                message: 'This file may contain images. Do you want to extract and add them to the discussion context? Choosing "Text Only" may be faster.',
                confirmText: 'Yes, Extract Images',
                cancelText: 'No, Text Only'
            });
            extractImages = result.confirmed;
        }
        filesToUpload.push({ file, extractImages });
    }
    
    if (filesToUpload.length === 0) return;

    isUploadingArtefact.value = true;
    try {
        await Promise.all(filesToUpload.map(({ file, extractImages }) => 
            discussionsStore.addArtefact({ 
                discussionId: activeDiscussion.value.id, 
                file, 
                extractImages 
            })
        ));
    } finally {
        isUploadingArtefact.value = false;
        if (artefactFileInput.value) artefactFileInput.value.value = '';
    }
}

function handleDragLeave(event) {
    if (!event.currentTarget.contains(event.relatedTarget)) isDraggingFile.value = false;
}

async function handleDrop(event) {
    isDraggingFile.value = false;
    const files = Array.from(event.dataTransfer.files);
    if (files.length) await handleArtefactFileUpload({ target: { files } });
}
</script>

<template>
    <div @dragover.prevent="isDraggingFile = true" @dragleave.prevent="handleDragLeave" @drop.prevent="handleDrop" class="p-2 flex flex-col min-h-0 flex-grow relative">
        <input type="file" ref="artefactFileInput" @change="handleArtefactFileUpload" multiple class="hidden">
        <div v-if="isDraggingFile" class="absolute inset-0 bg-blue-500/20 border-2 border-dashed border-blue-500 rounded-lg z-10 flex items-center justify-center">
            <p class="font-semibold text-blue-600">Drop files to upload</p>
        </div>
        <div class="flex justify-between items-center mb-2 flex-shrink-0">
            <button @click="isArtefactsCollapsed = !isArtefactsCollapsed" class="flex items-center gap-2 text-sm font-semibold w-full text-left">
                <IconFileText class="w-4 h-4" /> <span>Artefacts</span>
                <IconChevronRight class="w-4 h-4 ml-auto transition-transform" :class="{'rotate-90': !isArtefactsCollapsed}"/>
            </button>
            <div @click.stop class="flex items-center gap-1">
                <button @click="handleRefreshArtefacts" class="action-btn-sm" title="Refresh Artefacts"> <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingArtefacts}" /> </button>
                <button @click="handleLoadAllArtefacts" class="action-btn-sm" title="Load All Artefacts to Context"> <IconGather class="w-4 h-4" /> </button>
                <button @click="handleCreateArtefact" class="action-btn-sm" title="Create Artefact"><IconPlus class="w-4 h-4" /></button>
                <button @click="showUrlImport = !showUrlImport" class="action-btn-sm" :class="{'bg-gray-200 dark:bg-gray-700': showUrlImport}" title="Import from URL"><IconWeb class="w-4 h-4" /></button>
                <button @click="triggerArtefactFileUpload" class="action-btn-sm" title="Upload Artefact" :disabled="isUploadingArtefact"><IconAnimateSpin v-if="isUploadingArtefact" class="w-4 h-4 animate-spin" /><IconArrowUpTray v-else class="w-4 h-4" /></button>
            </div>
        </div>
        <div v-if="!isArtefactsCollapsed" class="flex-grow flex flex-col min-h-0">
            <div class="flex-grow min-h-0 overflow-y-auto custom-scrollbar">
                <div v-if="isLoadingArtefacts" key="artefacts-loading" class="loading-state"><IconAnimateSpin class="w-6 h-6 text-gray-400 animate-spin mx-auto mb-2" /><p class="text-xs text-gray-500">Loading...</p></div>
                <div v-else-if="groupedArtefacts.length === 0" key="artefacts-empty" class="flex flex-col items-center justify-center h-full text-center p-4 bg-gray-50 dark:bg-gray-800/50 rounded">
                    <IconFileText class="w-10 h-10 text-gray-400 mb-2" />
                    <p class="text-xs text-gray-500 mb-3">No artefacts yet</p>
                    <button @click="triggerArtefactFileUpload" class="btn btn-secondary btn-sm"><IconPlus class="w-3 h-3 mr-1" />Add Artefact</button>
                </div>
                <div v-else key="artefacts-list" class="artefacts-list space-y-2">
                    <ArtefactCard 
                        v-for="group in groupedArtefacts" 
                        :key="group.title"
                        :artefact-group="group"
                    />
                </div>
            </div>
        </div>
    </div>
</template>