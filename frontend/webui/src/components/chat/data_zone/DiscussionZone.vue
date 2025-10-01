<script setup>
import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';
import { useDataStore } from '../../../stores/data';
import { usePromptsStore } from '../../../stores/prompts';
import { useTasksStore } from '../../../stores/tasks';
import useEventBus from '../../../services/eventBus';
import CodeMirrorEditor from '../../ui/CodeMirrorComponent/index.vue';
import ArtefactZone from './ArtefactZone.vue';
import DropdownMenu from '../../ui/DropdownMenu/DropdownMenu.vue';
import DropdownSubmenu from '../../ui/DropdownMenu/DropdownSubmenu.vue';
import apiClient from '../../../services/api';
import { useAuthStore } from '../../../stores/auth';
import IconCopy from '../../../assets/icons/IconCopy.vue';
import IconSave from '../../../assets/icons/IconSave.vue';
import IconUndo from '../../../assets/icons/IconUndo.vue';
import IconRedo from '../../../assets/icons/IconRedo.vue';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconPhoto from '../../../assets/icons/IconPhoto.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconChevronRight from '../../../assets/icons/IconChevronRight.vue';
import IconMaximize from '../../../assets/icons/IconMaximize.vue';
import IconEye from '../../../assets/icons/IconEye.vue';
import IconEyeOff from '../../../assets/icons/IconEyeOff.vue';
import IconXMark from '../../../assets/icons/IconXMark.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconToken from '../../../assets/icons/IconToken.vue';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const dataStore = useDataStore();
const promptsStore = usePromptsStore();
const tasksStore = useTasksStore();
const router = useRouter();
const { on, off } = useEventBus();
const authStore = useAuthStore();

const { promptLoadedArtefacts, activeDiscussionContextStatus, dataZonesTokensFromContext } = storeToRefs(discussionsStore);
const { lollmsPrompts, systemPromptsByZooCategory, userPromptsByCategory } = storeToRefs(promptsStore);
const { availableTtiModels } = storeToRefs(dataStore);
const { tasks } = storeToRefs(tasksStore);

const codeMirrorView = ref(null);
const isProgrammaticChange = ref(false);
const isImagesCollapsed = ref(false);
const artefactListWidth = ref(384);
const isResizingArtefacts = ref(false);
const discussionImageInput = ref(null);
const isUploadingDiscussionImage = ref(false);
const dataZonePromptText = ref('');
const dataZonePromptTextareaRef = ref(null);
const discussionHistory = ref([]);
const discussionHistoryIndex = ref(-1);
let discussionHistoryDebounceTimer = null;
let saveDebounceTimer = null;
const userPromptSearchTerm = ref('');
const zooPromptSearchTerm = ref('');

const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const discussionDataZone = computed({
    get: () => activeDiscussion.value?.discussion_data_zone || '',
    set: (newVal) => {
        if (activeDiscussion.value) {
            discussionsStore.setDiscussionDataZoneContent(activeDiscussion.value.id, newVal);

            clearTimeout(saveDebounceTimer);
            saveDebounceTimer = setTimeout(() => {
                if (activeDiscussion.value) {
                    apiClient.put(`/api/discussions/${activeDiscussion.value.id}/data_zone`, { content: newVal })
                        .catch(err => {
                            console.error("Failed to save data zone content:", err);
                            uiStore.addNotification('Failed to auto-save data zone.', 'error');
                        });
                }
            }, 1500);
        }
    }
});

const discussionImages = computed(() => activeDiscussion.value?.discussion_images || []);
const discussionActiveImages = computed(() => activeDiscussion.value?.active_discussion_images || []);
const isProcessing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'summarize');
const isGeneratingImage = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'generate_image');
const isTaskRunning = computed(() => {
    if (!activeDiscussion.value) return false;
    const taskInfo = discussionsStore.activeAiTasks[activeDiscussion.value.id];
    if (!taskInfo || !taskInfo.taskId) return false;
    const task = tasks.value.find(t => t.id === taskInfo.taskId);
    return task ? (task.status === 'running' || task.status === 'pending') : false;
});

const activeTask = computed(() => {
    if (!activeDiscussion.value) return null;
    const taskInfo = discussionsStore.activeAiTasks[activeDiscussion.value.id];
    if (!taskInfo || !taskInfo.taskId) return null;
    return tasks.value.find(t => t.id === taskInfo.taskId);
});

const isTtiConfigured = computed(() => availableTtiModels.value.length > 0);
const canUndoDiscussion = computed(() => discussionHistoryIndex.value > 0);
const canRedoDiscussion = computed(() => discussionHistoryIndex.value < discussionHistory.value.length - 1);

const user = computed(() => authStore.user);
const contextStatus = computed(() => discussionsStore.activeDiscussionContextStatus);
const showContextBar = computed(() => user.value?.show_token_counter && user.value?.user_ui_level >= 2 && contextStatus.value);

const maxTokens = computed(() => contextStatus.value?.max_tokens || 1);
const systemPromptTokens = computed(() => contextStatus.value?.zones?.system_context?.breakdown?.system_prompt?.tokens || 0);
const dataZonesTokens = computed(() => dataZonesTokensFromContext.value);
const historyTextTokens = computed(() => contextStatus.value?.zones?.message_history?.breakdown?.text_tokens || 0);
const historyImageTokens = computed(() => contextStatus.value?.zones?.message_history?.breakdown?.image_tokens || 0);
const totalCurrentTokens = computed(() => systemPromptTokens.value + dataZonesTokens.value + historyTextTokens.value + historyImageTokens.value);

const getPercentage = (tokens) => maxTokens.value > 0 ? (tokens / maxTokens.value) * 100 : 0;

const contextParts = computed(() => {
    const parts = [];
    if (systemPromptTokens.value > 0) parts.push({ label: 'S', value: systemPromptTokens.value, title: 'System Prompt', colorClass: 'bg-blue-100 dark:bg-blue-900/50' });
    if (dataZonesTokens.value > 0) parts.push({ label: 'D', value: dataZonesTokens.value, title: 'Data Zones', colorClass: 'bg-yellow-100 dark:bg-yellow-900/50' });
    if (historyTextTokens.value > 0) parts.push({ label: 'H', value: historyTextTokens.value, title: 'History (Text)', colorClass: 'bg-green-100 dark:bg-green-900/50' });
    if (historyImageTokens.value > 0) parts.push({ label: 'I', value: historyImageTokens.value, title: 'History (Images)', colorClass: 'bg-teal-100 dark:bg-teal-900/50' });
    if (parts.length === 0) parts.push({ label: 'Empty', value: 0, title: 'Empty context', colorClass: 'bg-gray-100 dark:bg-gray-900/50' });
    return parts;
});

const systemPromptPercentage = computed(() => getPercentage(systemPromptTokens.value));
const dataZonesPercentage = computed(() => getPercentage(dataZonesTokens.value));
const historyTextPercentage = computed(() => getPercentage(historyTextTokens.value));
const historyImagePercentage = computed(() => getPercentage(historyImageTokens.value));
const totalPercentage = computed(() => getPercentage(totalCurrentTokens.value));

const progressBorderColorClass = computed(() => {
    const percentage = totalPercentage.value;
    return percentage >= 90 ? 'border-red-500 dark:border-red-400' : percentage >= 75 ? 'border-yellow-500 dark:border-yellow-400' : 'border-gray-300 dark:border-gray-600';
});

const showContextWarning = computed(() => totalPercentage.value > 90);
const contextWarningMessage = computed(() => {
    return totalPercentage.value > 100 ? "Context limit exceeded! The model may not see all of your message." : 
           totalPercentage.value > 90 ? "You are approaching the context limit. Consider shortening your message or data zones." : "";
});
function showContext() {
    if (activeDiscussion.value) uiStore.openModal('contextViewer');
}

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

function handleEditorReady(payload) { codeMirrorView.value = payload.view; }

function handlePromptSelection(promptContent) {
    const processAndInsert = (finalContent) => {
        dataZonePromptText.value = finalContent;
        nextTick(() => dataZonePromptTextareaRef.value?.focus());
    };

    if (/@<.*?>@/g.test(promptContent)) {
        uiStore.openModal('fillPlaceholders', { 
            promptTemplate: promptContent, 
            onConfirm: (filled) => processAndInsert(filled) 
        });
    } else {
        processAndInsert(promptContent);
    }
}

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

watch(discussionDataZone, (newVal, oldVal) => {
    if (!isProgrammaticChange.value && newVal !== oldVal) recordHistory(newVal);
}, { flush: 'post' });

watch(activeDiscussion, (newDiscussion, oldDiscussion) => {
    if (newDiscussion && (!oldDiscussion || newDiscussion.id !== oldDiscussion.id)) {
        if (newDiscussion.discussion_data_zone === undefined) discussionsStore.refreshDataZones(newDiscussion.id);
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

function handleCloneDiscussion() { if (activeDiscussion.value) discussionsStore.cloneDiscussion(activeDiscussion.value.id); }
function openContextToArtefactModal() { if (activeDiscussion.value) uiStore.openModal('contextToArtefact'); }
function refreshDataZones() { if (activeDiscussion.value) discussionsStore.refreshDataZones(activeDiscussion.value.id); }

async function handleDeleteAllImages() {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete All ${discussionImages.value.length} Images?`,
        message: 'This will remove all images from this discussion\'s context. This action cannot be undone.',
        confirmText: 'Delete All'
    });
    if (confirmed.confirmed) discussionsStore.deleteAllDiscussionImages();
}

function triggerDiscussionImageUpload() { discussionImageInput.value?.click(); }

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

function handleProcessContent() { if (activeDiscussion.value) discussionsStore.summarizeDiscussionDataZone(activeDiscussion.value.id, dataZonePromptText.value); }

function handleGenerateImage() {
    if (!activeDiscussion.value) return;
    let prompt = dataZonePromptText.value.trim() || discussionDataZone.value.trim();
    if (!prompt) { uiStore.addNotification('Please provide a prompt to generate an image.', 'warning'); return; }
    discussionsStore.generateImageFromDataZone(activeDiscussion.value.id, prompt);
}

function openPromptLibrary() { router.push({ path: '/settings', query: { tab: 'prompts' } }); }
function isImageActive(index) { return !discussionActiveImages.value || discussionActiveImages.value.length <= index || discussionActiveImages.value[index]; }
function handleLoadArtefactToPrompt(content) { dataZonePromptText.value = content; }
function handleUnloadArtefactFromPrompt() { if (promptLoadedArtefacts.value.size === 0) dataZonePromptText.value = ''; }
function handleZoneProcessed(data) { dataZonePromptText.value = ''; }
function openImageViewer(index) {
    uiStore.openImageViewer({
        imageList: discussionImages.value.map(img_b64 => ({ src: `data:image/png;base64,${img_b64}`, prompt: 'Image from Data Zone' })),
        startIndex: index
    });
}

onMounted(() => {
    const savedWidth = localStorage.getItem('lollms_artefactListWidth');
    if (savedWidth) artefactListWidth.value = parseInt(savedWidth, 10);
    on('artefact:load-to-prompt', handleLoadArtefactToPrompt);
    on('artefact:unload-from-prompt', handleUnloadArtefactFromPrompt);
    on('discussion_zone:processed', handleZoneProcessed);
});

onUnmounted(() => {
    off('artefact:load-to-prompt', handleLoadArtefactToPrompt);
    off('artefact:unload-from-prompt', handleUnloadArtefactFromPrompt);
    off('discussion_zone:processed', handleZoneProcessed);
});
</script>

<template>
  <div class="flex-1 flex flex-col min-h-0">
    <div v-if="showContextBar" class="px-3 pt-2 pb-1 border-b border-gray-200 dark:border-gray-700 relative group flex-shrink-0">
        <!-- Context Bar Content -->
    </div>
    <div class="flex-grow flex flex-col min-h-0">
        <input type="file" ref="discussionImageInput" @change="handleDiscussionImageUpload" class="hidden" accept="image/*,application/pdf" multiple>
        <div class="flex-grow flex min-h-0">
            <div class="flex-grow flex flex-col min-h-0 p-2">
                 <!-- Editor Controls -->
                <div class="flex-grow min-h-0 border dark:border-gray-700 rounded-md overflow-hidden">
                    <CodeMirrorEditor 
                        ref="discussionCodeMirrorEditor" 
                        v-model="discussionDataZone" 
                        class="h-full" 
                        :read-only="isTaskRunning"
                        :renderable="true"
                        @ready="handleEditorReady"
                    />
                </div>
            </div>
            
            <div @mousedown.prevent="startArtefactResize" class="resizer"></div>
            
            <div :style="{ width: `${artefactListWidth}px` }" class="flex-shrink-0 border-l border-gray-200 dark:border-gray-700 flex flex-col h-full min-w-[256px]">
                <div class="p-2 border-b dark:border-gray-700 flex flex-col max-h-[50%] min-h-0">
                    <div class="flex justify-between items-center mb-2 flex-shrink-0">
                        <button @click="isImagesCollapsed = !isImagesCollapsed" class="flex items-center gap-2 text-sm font-semibold w-full text-left">
                            <IconPhoto class="w-4 h-4" /> <span>Images</span>
                            <IconChevronRight class="w-4 h-4 ml-auto transition-transform" :class="{'rotate-90': !isImagesCollapsed}"/>
                        </button>
                        <div @click.stop class="flex items-center gap-1">
                            <button @click="handleDeleteAllImages" class="action-btn-sm-danger" title="Delete All Images" :disabled="discussionImages.length === 0 || isTaskRunning"><IconTrash class="w-4 h-4" /></button>
                            <button @click="triggerDiscussionImageUpload" class="action-btn-sm" title="Add Image(s)" :disabled="isUploadingDiscussionImage || isTaskRunning">
                                <IconAnimateSpin v-if="isUploadingDiscussionImage" class="w-4 h-4 animate-spin" /><IconPlus v-else class="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                    <div v-if="!isImagesCollapsed" class="overflow-y-auto custom-scrollbar min-h-0">
                        <div v-if="discussionImages.length === 0 && !isUploadingDiscussionImage" class="text-center py-4 text-xs text-gray-500 bg-gray-50 dark:bg-gray-800/50 rounded">No images yet</div>
                        <div v-else class="image-grid">
                            <div v-for="(img_b64, index) in discussionImages" :key="img_b64.substring(0, 20) + index" class="image-card group">
                                <img :src="'data:image/png;base64,' + img_b64" class="image-thumbnail" :class="{'grayscale opacity-50': !isImageActive(index)}" />
                                <div class="image-overlay">
                                    <button @click="openImageViewer(index)" class="overlay-btn" title="View"><IconMaximize class="w-3 h-3" /></button>
                                    <button @click="discussionsStore.toggleDiscussionImage(index)" class="overlay-btn" :title="isImageActive(index) ? 'Deactivate' : 'Activate'"><IconEye v-if="isImageActive(index)" class="w-3 h-3" /><IconEyeOff v-else class="w-3 h-3" /></button>
                                    <button @click="discussionsStore.deleteDiscussionImage(index)" class="overlay-btn overlay-btn-danger" title="Delete"><IconXMark class="w-3 h-3" /></button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <ArtefactZone :is-task-running="isTaskRunning" />
            </div>
        </div>
    </div>
    <div class="flex-shrink-0 p-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
      <!-- Task/Prompt Bar -->
    </div>
  </div>
</template>
<style>
.progress-segment {
    @apply absolute h-full top-0;
}
.resizer {
    @apply flex-shrink-0 w-1.5 cursor-col-resize bg-gray-200 dark:bg-gray-700 hover:bg-blue-400 transition-colors duration-200;
}
.enhanced-textarea {
    @apply w-full p-2.5 pr-20 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 focus:ring-blue-500 focus:border-blue-500 transition text-sm resize-none;
    min-height: 44px; /* Adjust to match button height */
}
.sidebar-section {
    @apply flex flex-col flex-grow min-h-0;
}
.section-header {
    @apply flex justify-between items-center mb-2 flex-shrink-0;
}
.section-title {
    @apply text-sm font-semibold flex items-center gap-2;
}
.section-actions {
    @apply flex items-center gap-1;
}
.section-content {
    @apply flex-grow min-h-0 overflow-y-auto;
}

/* Image grid styles */
.image-grid {
    @apply grid grid-cols-2 gap-2;
}
.image-card {
    @apply relative overflow-hidden rounded-md;
}
.image-thumbnail {
    @apply w-full h-20 object-cover;
}
.image-overlay {
    @apply absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2;
}
.overlay-btn {
    @apply p-1.5 bg-white/20 text-white rounded-full hover:bg-white/40;
}
.overlay-btn-danger {
    @apply hover:bg-red-500/80;
}
.loading-state, .empty-state {
    @apply text-center p-4;
}
.menu-item {
    @apply w-full text-left p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-sm flex items-center;
}
.danger-item {
    @apply text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/50;
}
.category-header {
    @apply px-3 py-1.5 text-xs font-semibold text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700/50 sticky top-0;
}
</style>