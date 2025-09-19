<script setup>
import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';
import { useDataStore } from '../../../stores/data';
import { usePromptsStore } from '../../../stores/prompts';
import useEventBus from '../../../services/eventBus';
import CodeMirrorEditor from '../../ui/CodeMirrorEditor.vue';
import ArtefactCard from '../../ui/ArtefactCard.vue';
import MessageContentRenderer from '../../ui/MessageContentRenderer.vue';
import DropdownMenu from '../../ui/DropdownMenu.vue';
import DropdownSubmenu from '../../ui/DropdownSubmenu.vue';

// Icons
import IconCopy from '../../../assets/icons/IconCopy.vue';
import IconSave from '../../../assets/icons/IconSave.vue';
import IconUndo from '../../../assets/icons/IconUndo.vue';
import IconRedo from '../../../assets/icons/IconRedo.vue';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconPhoto from '../../../assets/icons/IconPhoto.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconFileText from '../../../assets/icons/IconFileText.vue';
import IconWeb from '../../../assets/icons/ui/IconWeb.vue';
import IconArrowUpTray from '../../../assets/icons/IconArrowUpTray.vue';
import IconChevronRight from '../../../assets/icons/IconChevronRight.vue';
import IconMaximize from '../../../assets/icons/IconMaximize.vue';
import IconEye from '../../../assets/icons/IconEye.vue';
import IconEyeOff from '../../../assets/icons/IconEyeOff.vue';
import IconXMark from '../../../assets/icons/IconXMark.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconTicket from '../../../assets/icons/IconTicket.vue';
import IconLollms from '../../../assets/icons/IconLollms.vue';
import IconUser from '../../../assets/icons/IconUser.vue';
import IconServer from '../../../assets/icons/IconServer.vue';
import IconGather from '../../../assets/icons/IconGather.vue';


const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const dataStore = useDataStore();
const promptsStore = usePromptsStore();
const router = useRouter();
const { on, off } = useEventBus();

const { liveDataZoneTokens, activeDiscussionArtefacts, isLoadingArtefacts, promptLoadedArtefacts } = storeToRefs(discussionsStore);
const { lollmsPrompts, systemPromptsByZooCategory, userPromptsByCategory } = storeToRefs(promptsStore);
const { availableTtiModels } = storeToRefs(dataStore);

const discussionCodeMirrorEditor = ref(null);
const isProgrammaticChange = ref(false);
const showUrlImport = ref(false);
const urlToImport = ref('');
const isUploadingArtefact = ref(false);
const isImagesCollapsed = ref(false);
const isArtefactsCollapsed = ref(false);
const artefactListWidth = ref(384);
const isResizingArtefacts = ref(false);
const artefactFileInput = ref(null);
const discussionImageInput = ref(null);
const isUploadingDiscussionImage = ref(false);
const dataZonePromptText = ref('');
const dataZonePromptTextareaRef = ref(null);
const isDraggingFile = ref(false);
const discussionHistory = ref([]);
const discussionHistoryIndex = ref(-1);
let discussionHistoryDebounceTimer = null;
const userPromptSearchTerm = ref('');
const zooPromptSearchTerm = ref('');

const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const discussionDataZone = computed({
    get: () => activeDiscussion.value?.discussion_data_zone || '',
    set: (newVal) => {
        if (activeDiscussion.value) {
            discussionsStore.setDiscussionDataZoneContent(activeDiscussion.value.id, newVal);
        }
    }
});

const discussionImages = computed(() => activeDiscussion.value?.discussion_images || []);
const discussionActiveImages = computed(() => activeDiscussion.value?.active_discussion_images || []);
const isProcessing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'summarize');
const isGeneratingImage = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'generate_image');
const isTaskRunning = computed(() => isProcessing.value || isGeneratingImage.value);

const discussionEditorOptions = computed(() => ({
    readOnly: isTaskRunning.value
}));

const isTtiConfigured = computed(() => availableTtiModels.value.length > 0);
const canUndoDiscussion = computed(() => discussionHistoryIndex.value > 0);
const canRedoDiscussion = computed(() => discussionHistoryIndex.value < discussionHistory.value.length - 1);

const groupedArtefacts = computed(() => {
    if (!activeDiscussionArtefacts.value || !Array.isArray(activeDiscussionArtefacts.value)) return [];
    const groups = activeDiscussionArtefacts.value.reduce((acc, artefact) => {
        if (!acc[artefact.title]) { acc[artefact.title] = { title: artefact.title, versions: [] }; }
        acc[artefact.title].versions.push(artefact);
        return acc;
    }, {});
    Object.values(groups).forEach(group => {
        group.versions.sort((a, b) => b.version - a.version);
        group.isAnyVersionLoaded = group.versions.some(v => v.is_loaded);
    });
    return Object.values(groups);
});

const filteredLollmsPrompts = computed(() => {
    if (!Array.isArray(lollmsPrompts.value)) return [];
    const term = userPromptSearchTerm.value.toLowerCase();
    return term ? lollmsPrompts.value.filter(p => p.name.toLowerCase().includes(term)) : lollmsPrompts.value;
});

const filteredUserPromptsByCategory = computed(() => {
    const term = userPromptSearchTerm.value.toLowerCase();
    const source = userPromptsByCategory.value;
    if (!source || typeof source !== 'object') return {};
    if (!term) return source;
    
    const filtered = {};
    for (const category in source) {
        const filteredPrompts = source[category].filter(p => p.name.toLowerCase().includes(term));
        if (filteredPrompts.length > 0) filtered[category] = filteredPrompts;
    }
    return filtered;
});

const filteredSystemPromptsByZooCategory = computed(() => {
    const term = zooPromptSearchTerm.value.toLowerCase();
    const source = systemPromptsByZooCategory.value;
    if (!source || typeof source !== 'object') return {};
    if (!term) return source;
    
    const filtered = {};
    for (const category in source) {
        const filteredPrompts = source[category].filter(p => p.name.toLowerCase().includes(term));
        if (filteredPrompts.length > 0) filtered[category] = filteredPrompts;
    }
    return filtered;
});

function setupHistory(initialValue) {
    discussionHistory.value = [initialValue];
    discussionHistoryIndex.value = 0;
}

function recordHistory(content) {
    clearTimeout(discussionHistoryDebounceTimer);
    discussionHistoryDebounceTimer = setTimeout(() => {
        if (discussionHistory.value[discussionHistoryIndex.value] === content) return;
        if (discussionHistoryIndex.value < discussionHistory.value.length - 1) {
            discussionHistory.value.splice(discussionHistoryIndex.value + 1);
        }
        discussionHistory.value.push(content);
        discussionHistoryIndex.value++;
    }, 750);
}

async function handleUndoDiscussion() {
    if (!canUndoDiscussion.value) return;
    isProgrammaticChange.value = true;
    discussionHistoryIndex.value--;
    discussionDataZone.value = discussionHistory.value[discussionHistoryIndex.value];
    await nextTick();
    isProgrammaticChange.value = false;
}

async function handleRedoDiscussion() {
    if (!canRedoDiscussion.value) return;
    isProgrammaticChange.value = true;
    discussionHistoryIndex.value++;
    discussionDataZone.value = discussionHistory.value[discussionHistoryIndex.value];
    await nextTick();
    isProgrammaticChange.value = false;
}

watch(discussionDataZone, (newVal) => {
    if (!isProgrammaticChange.value) {
        recordHistory(newVal);
    }
});

watch(activeDiscussion, (newDiscussion, oldDiscussion) => {
    if (newDiscussion && (!oldDiscussion || newDiscussion.id !== oldDiscussion.id)) {
        setupHistory(newDiscussion.discussion_data_zone || '');
    }
}, { immediate: true, deep: true });

function startArtefactResize(event) {
    isResizingArtefacts.value = true;
    const startX = event.clientX;
    const startWidth = artefactListWidth.value;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    
    function handleArtefactResize(e) {
        if (!isResizingArtefacts.value) return;
        const dx = e.clientX - startX;
        const newWidth = startWidth - dx;
        const maxWidth = (document.querySelector('.flex-grow.flex.min-h-0')?.clientWidth || window.innerWidth) * 0.75;
        artefactListWidth.value = Math.min(newWidth, maxWidth);
    }
    
    function stopArtefactResize() {
        isResizingArtefacts.value = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        window.removeEventListener('mousemove', handleArtefactResize);
        window.removeEventListener('mouseup', stopArtefactResize);
        localStorage.setItem('lollms_artefactListWidth', artefactListWidth.value);
    }
    
    window.addEventListener('mousemove', handleArtefactResize);
    window.addEventListener('mouseup', stopArtefactResize);
}

function handleCloneDiscussion() {
    if (activeDiscussion.value) discussionsStore.cloneDiscussion(activeDiscussion.value.id);
}

function openContextToArtefactModal() {
    if (activeDiscussion.value) uiStore.openModal('contextToArtefact');
}

function refreshDataZones() {
    if (activeDiscussion.value) discussionsStore.refreshDataZones(activeDiscussion.value.id);
}

async function handleDeleteAllImages() {
    const confirmed = await uiStore.showConfirmation({ title: 'Delete All Images?', message: 'This will remove all images from this discussion\'s context.', confirmText: 'Delete All' });
    if (confirmed) discussionsStore.deleteAllDiscussionImages();
}

function triggerDiscussionImageUpload() {
    discussionImageInput.value?.click();
}

async function handleDiscussionImageUpload(event) {
    const files = Array.from(event.target.files);
    if (!files.length || !activeDiscussion.value) return;
    isUploadingDiscussionImage.value = true;
    try {
        await Promise.all(files.map(file => discussionsStore.uploadDiscussionImage(file)));
    } finally {
        isUploadingDiscussionImage.value = false;
        if (discussionImageInput.value) discussionImageInput.value.value = '';
    }
}

function handleRefreshArtefacts() {
    if (activeDiscussion.value) discussionsStore.fetchArtefacts(activeDiscussion.value.id);
}

async function handleLoadAllArtefacts() {
    if (!activeDiscussion.value) return;
    const confirmed = await uiStore.showConfirmation({ title: 'Load All Artefacts?', message: `This will clear the current Discussion Data Zone and load all ${groupedArtefacts.value.length} artefact(s).`, confirmText: 'Load All' });
    if (confirmed) discussionsStore.loadAllArtefactsToContext(activeDiscussion.value.id);
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
    isUploadingArtefact.value = true;
    try {
        await Promise.all(files.map(file => discussionsStore.addArtefact({ discussionId: activeDiscussion.value.id, file })));
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

function handleProcessContent() {
    if (activeDiscussion.value) discussionsStore.summarizeDiscussionDataZone(activeDiscussion.value.id, dataZonePromptText.value);
}

function handleGenerateImage() {
    if (!activeDiscussion.value) return;
    let prompt = dataZonePromptText.value.trim() || discussionDataZone.value.trim();
    if (!prompt) {
        uiStore.addNotification('Please provide a prompt to generate an image.', 'warning');
        return;
    }
    discussionsStore.generateImageFromDataZone(activeDiscussion.value.id, prompt);
}

function handlePromptSelection(promptContent) {
    if (/@<.*?>@/g.test(promptContent)) {
        uiStore.openModal('fillPlaceholders', { promptTemplate: promptContent, onConfirm: (filled) => { dataZonePromptText.value = filled; } });
    } else {
        dataZonePromptText.value = promptContent;
    }
}

function openPromptLibrary() {
    router.push({ path: '/settings', query: { tab: 'prompts' } });
}

function isImageActive(index) {
    return !discussionActiveImages.value || discussionActiveImages.value.length <= index || discussionActiveImages.value[index];
}

function onDataZoneUpdatedFromStore({ discussionId, newContent }) {
    if (activeDiscussion.value && activeDiscussion.value.id === discussionId) {
        updateDiscussionDataZoneAndRecordHistory(newContent);
    }
}

function updateDiscussionDataZoneAndRecordHistory(newContent) {
    if (discussionDataZone.value === newContent) return;
    clearTimeout(discussionHistoryDebounceTimer);
    if (discussionHistoryIndex.value < discussionHistory.value.length - 1) {
        discussionHistory.value.splice(discussionHistoryIndex.value + 1);
    }
    discussionHistory.value.push(newContent);
    discussionHistoryIndex.value++;
    
    isProgrammaticChange.value = true;
    discussionDataZone.value = newContent;
    nextTick(() => { isProgrammaticChange.value = false; });
}

onMounted(() => {
    const savedWidth = localStorage.getItem('lollms_artefactListWidth');
    if (savedWidth) artefactListWidth.value = parseInt(savedWidth, 10);
    on('discussion:dataZoneUpdated', onDataZoneUpdatedFromStore);
});

onUnmounted(() => {
    off('discussion:dataZoneUpdated', onDataZoneUpdatedFromStore);
});
</script>

<template>
  <div class="flex-1 flex flex-col min-h-0">
    <div class="flex-grow flex flex-col min-h-0">
        <input type="file" ref="artefactFileInput" @change="handleArtefactFileUpload" multiple class="hidden">
        <input type="file" ref="discussionImageInput" @change="handleDiscussionImageUpload" class="hidden" accept="image/*,application/pdf" multiple>
        <!-- Main Content -->
        <div class="flex-grow flex min-h-0">
            <!-- Left side (Editor) -->
            <div class="flex-grow flex flex-col min-h-0 p-2">
                 <div class="flex-shrink-0 px-1 pb-2 flex items-center justify-between gap-4">
                    <div class="flex items-center gap-1">
                        <button @click="handleUndoDiscussion" class="action-btn-sm" title="Undo" :disabled="!canUndoDiscussion"><IconUndo class="w-4 h-4" /></button>
                        <button @click="handleRedoDiscussion" class="action-btn-sm" title="Redo" :disabled="!canRedoDiscussion"><IconRedo class="w-4 h-4" /></button>
                        <div class="w-px h-5 bg-gray-200 dark:bg-gray-600 mx-1"></div>
                        <button @click="handleCloneDiscussion" class="action-btn-sm" title="Clone Discussion & Artefacts"><IconCopy class="w-4 h-4" /></button>
                        <button @click="openContextToArtefactModal" class="action-btn-sm" title="Save as Artefact"><IconSave class="w-4 h-4" /></button>
                        <button @click="refreshDataZones" class="action-btn-sm" title="Refresh Data"><IconRefresh class="w-4 h-4" /></button>
                        <button @click="discussionDataZone = ''" class="action-btn-sm-danger" title="Clear All Text"><IconTrash class="w-4 h-4" /></button>
                    </div>
                </div>
                <div class="flex-grow min-h-0 border dark:border-gray-700 rounded-md overflow-hidden">
                    <CodeMirrorEditor ref="discussionCodeMirrorEditor" v-model="discussionDataZone" class="h-full" :options="discussionEditorOptions" />
                </div>
            </div>
            <!-- Artefacts/Images resizer -->
            <div @mousedown.prevent="startArtefactResize" class="resizer"></div>
            <!-- Right side (Panels) -->
            <div :style="{ width: `${artefactListWidth}px` }" class="flex-shrink-0 border-l border-gray-200 dark:border-gray-700 flex flex-col h-full min-w-[256px]">
                <!-- Images -->
                <div class="p-2 border-b dark:border-gray-700 flex flex-col">
                    <div class="flex justify-between items-center mb-2 flex-shrink-0">
                        <button @click="isImagesCollapsed = !isImagesCollapsed" class="flex items-center gap-2 text-sm font-semibold w-full text-left">
                            <IconPhoto class="w-4 h-4" /> <span>Images</span>
                            <IconChevronRight class="w-4 h-4 ml-auto transition-transform" :class="{'rotate-90': !isImagesCollapsed}"/>
                        </button>
                        <div @click.stop class="flex items-center gap-1">
                            <button @click="handleDeleteAllImages" class="action-btn-sm-danger" title="Delete All Images" :disabled="discussionImages.length === 0"><IconTrash class="w-4 h-4" /></button>
                            <button @click="triggerDiscussionImageUpload" class="action-btn-sm" title="Add Image(s)" :disabled="isUploadingDiscussionImage">
                                <IconAnimateSpin v-if="isUploadingDiscussionImage" class="w-4 h-4 animate-spin" /><IconPlus v-else class="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                    <div v-if="!isImagesCollapsed" class="overflow-y-auto custom-scrollbar min-h-0">
                        <div v-if="discussionImages.length === 0 && !isUploadingDiscussionImage" class="text-center py-4 text-xs text-gray-500 bg-gray-50 dark:bg-gray-800/50 rounded">No images yet</div>
                        <div v-else class="image-grid"><div v-for="(img_b64, index) in discussionImages" :key="img_b64.substring(0, 20) + index" class="image-card group"><img :src="'data:image/png;base64,' + img_b64" class="image-thumbnail" :class="{'grayscale opacity-50': !isImageActive(index)}" /><div class="image-overlay"><button @click="uiStore.openImageViewer('data:image/png;base64,' + img_b64)" class="overlay-btn" title="View"><IconMaximize class="w-3 h-3" /></button><button @click="discussionsStore.toggleDiscussionImageActivation(index)" class="overlay-btn" :title="isImageActive(index) ? 'Deactivate' : 'Activate'"><IconEye v-if="isImageActive(index)" class="w-3 h-3" /><IconEyeOff v-else class="w-3 h-3" /></button><button @click="discussionsStore.deleteDiscussionImage(index)" class="overlay-btn overlay-btn-danger" title="Delete"><IconXMark class="w-3 h-3" /></button></div></div></div>
                    </div>
                </div>
                <!-- Artefacts -->
                <div @dragover.prevent="isDraggingFile = true" @dragleave.prevent="handleDragLeave" @drop.prevent="handleDrop" class="p-2 flex flex-col min-h-0 flex-grow relative">
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
            </div>
        </div>
    </div>
    <!-- Bottom Action Bar -->
    <div class="flex-shrink-0 p-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
      <div class="relative flex items-center">
        <DropdownMenu title="Prompts" icon="ticket" collection="ui" button-class="btn-icon absolute left-1.5 top-1/2 -translate-y-1/2 z-10">
            <DropdownSubmenu v-if="filteredLollmsPrompts.length > 0" title="Default" icon="lollms" collection="ui"> <button v-for="p in filteredLollmsPrompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm"><span class="truncate">{{ p.name }}</span></button> </DropdownSubmenu>
            <DropdownSubmenu v-if="Object.keys(userPromptsByCategory).length > 0" title="User" icon="user" collection="ui"> <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10"><input type="text" v-model="userPromptSearchTerm" @click.stop placeholder="Search user prompts..." class="input-field w-full text-sm"></div> <div class="max-h-60 overflow-y-auto"> <div v-for="(prompts, category) in filteredUserPromptsByCategory" :key="category"> <h3 class="category-header">{{ category }}</h3> <button v-for="p in prompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm"><img v-if="p.icon" :src="p.icon" class="h-5 w-5 rounded-md object-cover mr-2 flex-shrink-0" alt="Icon"><span class="truncate">{{ p.name }}</span></button> </div> </div> </DropdownSubmenu>
            <DropdownSubmenu v-if="Object.keys(systemPromptsByZooCategory).length > 0" title="Zoo" icon="server" collection="ui"> <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10"><input type="text" v-model="zooPromptSearchTerm" @click.stop placeholder="Search zoo..." class="input-field w-full text-sm"></div> <div class="max-h-60 overflow-y-auto"> <div v-for="(prompts, category) in filteredSystemPromptsByZooCategory" :key="category"> <h3 class="category-header">{{ category }}</h3> <button v-for="p in prompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm"><img v-if="p.icon" :src="p.icon" class="h-5 w-5 rounded-md object-cover mr-2 flex-shrink-0" alt="Icon"><span class="truncate">{{ p.name }}</span></button> </div> </div> </DropdownSubmenu>
            <div v-if="(filteredLollmsPrompts.length + Object.keys(filteredUserPromptsByCategory).length + Object.keys(filteredSystemPromptsByZooCategory).length) > 0" class="my-1 border-t dark:border-gray-600"></div>
            <button @click="openPromptLibrary" class="menu-item text-sm font-medium text-blue-600 dark:text-blue-400">Manage My Prompts...</button>
        </DropdownMenu>
        <textarea ref="dataZonePromptTextareaRef" v-model="dataZonePromptText" placeholder="Enter a prompt to process content..." class="enhanced-textarea w-full !pl-10 !pr-24"></textarea>
        <div class="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-2">
             <button v-if="isTtiConfigured && !isProcessing" 
                    @click="handleGenerateImage" 
                    class="btn btn-primary !py-2 !px-3 flex items-center" 
                    :disabled="isTaskRunning || (!discussionDataZone.trim() && !dataZonePromptText.trim())" 
                    :title="isGeneratingImage ? 'Generating image...' : 'Generate an image using the prompt'">
                <IconAnimateSpin v-if="isGeneratingImage" class="w-5 h-5 animate-spin" />
                <IconPhoto v-else class="w-5 h-5" />
                <span v-if="isGeneratingImage" class="ml-2 text-sm">Generating...</span>
            </button>
            <button v-if="!isGeneratingImage" 
                    @click="handleProcessContent" 
                    class="btn btn-secondary !py-2 !px-3 flex items-center" 
                    :disabled="isTaskRunning || (!discussionDataZone.trim() && discussionImages.length === 0 && !dataZonePromptText.trim())" 
                    :title="isProcessing ? 'Processing text...' : 'Process the text in the data zone using the prompt'">
                <IconAnimateSpin v-if="isProcessing" class="w-5 h-5 animate-spin" />
                <IconSparkles v-else class="w-5 h-5" />
                <span v-if="isProcessing" class="ml-2 text-sm">Processing...</span>
            </button>
        </div>
      </div>
    </div>
  </div>
</template>