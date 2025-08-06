<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { usePromptsStore } from '../../stores/prompts';
import apiClient from '../../services/api';
import useEventBus from '../../services/eventBus';
import { storeToRefs } from 'pinia';

// Component Imports
import MessageArea from './MessageArea.vue';
import ChatInput from './ChatInput.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import DropdownMenu from '../ui/DropdownMenu.vue';
import DropdownSubmenu from '../ui/DropdownSubmenu.vue';

// Asset & Icon Imports
import logoUrl from '../../assets/logo.png';
import IconDataZone from '../../assets/icons/IconDataZone.vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconThinking from '../../assets/icons/IconThinking.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconTicket from '../../assets/icons/IconTicket.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../assets/icons/IconMinimize.vue';
import IconUndo from '../../assets/icons/IconUndo.vue';
import IconRedo from '../../assets/icons/IconRedo.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconUser from '../../assets/icons/IconUser.vue';
import IconLollms from '../../assets/icons/IconLollms.vue';

// --- Store Initialization ---
const discussionsStore = useDiscussionsStore();
const authStore = useAuthStore();
const uiStore = useUiStore();
const promptsStore = usePromptsStore();
const { on, off } = useEventBus();
const { liveDataZoneTokens } = storeToRefs(discussionsStore);
const { lollmsPrompts, userPrompts, systemPromptsByZooCategory } = storeToRefs(promptsStore);

// --- Component State ---
const knowledgeFileInput = ref(null);
const discussionImageInput = ref(null);
const isUploadingDiscussionImage = ref(false);
const isExtractingText = ref(false);
const activeDataZoneTab = ref('discussion');
const discussionCodeMirrorEditor = ref(null);
const userCodeMirrorEditor = ref(null);
const dataZonePromptText = ref('');
const dataZoneWidth = ref(448);
const isResizing = ref(false);
const dataZonePromptSearchTerm = ref('');

// --- Data Zone State ---
let discussionSaveDebounceTimer = null;
let userSaveDebounceTimer = null;
let memorySaveDebounceTimer = null;
let tokenizeDebounceTimers = {};

// --- History State for Undo/Redo ---
const discussionHistory = ref([]);
const discussionHistoryIndex = ref(-1);
let discussionHistoryDebounceTimer = null;
const userHistory = ref([]);
const userHistoryIndex = ref(-1);
let userHistoryDebounceTimer = null;
const memoryHistory = ref([]);
const memoryHistoryIndex = ref(-1);
let memoryHistoryDebounceTimer = null;

// --- Computed Properties ---
const isDataZoneVisible = computed(() => uiStore.isDataZoneVisible);
const isDataZoneExpanded = computed(() => uiStore.isDataZoneExpanded);
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);

const discussionImages = computed(() => activeDiscussion.value?.discussion_images || []);
const discussionActiveImages = computed(() => activeDiscussion.value?.active_discussion_images || []);

const isProcessing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'summarize');
const isMemorizing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'memorize');

const keywords = computed(() => uiStore.keywords);
const canUndoDiscussion = computed(() => discussionHistoryIndex.value > 0);
const canRedoDiscussion = computed(() => discussionHistoryIndex.value < discussionHistory.value.length - 1);
const canUndoUser = computed(() => userHistoryIndex.value > 0);
const canRedoUser = computed(() => userHistoryIndex.value < userHistory.value.length - 1);
const canUndoMemory = computed(() => memoryHistoryIndex.value > 0);
const canRedoMemory = computed(() => memoryHistoryIndex.value < memoryHistory.value.length - 1);

const filteredLollmsPrompts = computed(() => {
    if (!Array.isArray(lollmsPrompts.value)) return [];
    if (!dataZonePromptSearchTerm.value) return lollmsPrompts.value;
    const term = dataZonePromptSearchTerm.value.toLowerCase();
    return lollmsPrompts.value.filter(p => p.name.toLowerCase().includes(term));
});

const filteredUserPrompts = computed(() => {
    if (!Array.isArray(userPrompts.value)) return [];
    if (!dataZonePromptSearchTerm.value) return userPrompts.value;
    const term = dataZonePromptSearchTerm.value.toLowerCase();
    return userPrompts.value.filter(p => p.name.toLowerCase().includes(term));
});

const filteredSystemPromptsByZooCategory = computed(() => {
    const term = dataZonePromptSearchTerm.value.toLowerCase();
    if (!systemPromptsByZooCategory.value || typeof systemPromptsByZooCategory.value !== 'object') return {};
    if (!term) return systemPromptsByZooCategory.value;
    const filtered = {};
    for (const category in systemPromptsByZooCategory.value) {
        const filteredPrompts = systemPromptsByZooCategory.value[category].filter(p => p.name.toLowerCase().includes(term));
        if (filteredPrompts.length > 0) {
            filtered[category] = filteredPrompts;
        }
    }
    const sortedFiltered = {};
    Object.keys(filtered).sort().forEach(key => {
        sortedFiltered[key] = filtered[key];
    });
    return sortedFiltered;
});

const discussionDataZone = computed({
    get: () => activeDiscussion.value?.discussion_data_zone || '',
    set: (newVal) => {
        if (activeDiscussion.value) {
            discussionsStore.setUserDataZoneContent(activeDiscussion.value.id, newVal);
            clearTimeout(discussionSaveDebounceTimer);
            discussionSaveDebounceTimer = setTimeout(() => {
                if (activeDiscussion.value) discussionsStore.updateDataZone({ discussionId: activeDiscussion.value.id, content: newVal });
            }, 750);
        }
    }
});
const userDataZone = computed({
    get: () => authStore.user?.data_zone || '',
    set: (newVal) => {
        if (authStore.user) { authStore.user.data_zone = newVal; }
        clearTimeout(userSaveDebounceTimer);
        userSaveDebounceTimer = setTimeout(() => { authStore.updateDataZone(newVal); }, 750);
    }
});
const personalityDataZone = computed(() => activeDiscussion.value?.personality_data_zone || '');
const memory = computed({
    get: () => authStore.user?.memory || '',
    set: (newVal) => {
        if (authStore.user) { authStore.user.memory = newVal; }
        clearTimeout(memorySaveDebounceTimer);
        memorySaveDebounceTimer = setTimeout(() => { authStore.updateMemoryZone(newVal); }, 750);
    }
});

const contextStatus = computed(() => discussionsStore.activeDiscussionContextStatus);
const maxTokens = computed(() => contextStatus.value?.max_tokens || 1);
const discussionDataZoneTokens = computed(() => liveDataZoneTokens.value.discussion);
const userDataZoneTokens = computed(() => liveDataZoneTokens.value.user);
const personalityDataZoneTokens = computed(() => liveDataZoneTokens.value.personality);
const memoryDataZoneTokens = computed(() => liveDataZoneTokens.value.memory);

const getPercentage = (tokens) => {
    if (maxTokens.value <= 0) return 0;
    return Math.min((tokens / maxTokens.value) * 100, 100);
};
const formatNumber = (num) => num ? num.toLocaleString() : '0';

async function tokenizeContent(content, zone) {
    clearTimeout(tokenizeDebounceTimers[zone]);
    if (!content || !content.trim()) {
        discussionsStore.updateLiveTokenCount(zone, 0);
        return;
    }
    tokenizeDebounceTimers[zone] = setTimeout(async () => {
        try {
            const response = await apiClient.post('/api/discussions/tokenize', { text: content });
            discussionsStore.updateLiveTokenCount(zone, response.data.tokens);
        } catch (error) {
            console.error(`Tokenization for ${zone} failed:`, error);
            discussionsStore.updateLiveTokenCount(zone, 0);
        }
    }, 750);
}

watch(discussionDataZone, (newVal) => { tokenizeContent(newVal, 'discussion'); });
watch(userDataZone, (newVal) => { tokenizeContent(newVal, 'user'); });
watch(memory, (newVal) => { tokenizeContent(newVal, 'memory'); });

onMounted(() => {
    on('task:completed', handleTaskCompletion);
    const savedWidth = localStorage.getItem('lollms_dataZoneWidth');
    if (savedWidth) dataZoneWidth.value = parseInt(savedWidth, 10);
    setupHistory(userHistory, userHistoryIndex, userDataZone.value);
    setupHistory(memoryHistory, memoryHistoryIndex, memory.value);
});
onUnmounted(() => {
    off('task:completed', handleTaskCompletion);
    window.removeEventListener('mousemove', handleResize);
    window.removeEventListener('mouseup', stopResize);
});

async function handlePasteInDataZone(event) {
    const items = (event.clipboardData || window.clipboardData).items;
    if (!items) return;
    const filesToUpload = [];
    for (const item of items) {
        if (item.kind === 'file' && (item.type.startsWith('image/') || item.type === 'application/pdf')) {
            const file = item.getAsFile();
            if (file) filesToUpload.push(file);
        }
    }
    if (filesToUpload.length > 0) {
        event.preventDefault();
        isUploadingDiscussionImage.value = true;
        try {
            await Promise.all(filesToUpload.map(file => discussionsStore.uploadDiscussionImage(file)));
        } finally {
            isUploadingDiscussionImage.value = false;
        }
    }
}
function handleTaskCompletion(task) { if (activeDiscussion.value && task?.result?.discussion_id === activeDiscussion.value.id) { if (task.name.includes('Process') || task.name.includes('Memorize')) refreshDataZones(); } }
function setupHistory(historyRef, indexRef, initialValue) { historyRef.value = [initialValue]; indexRef.value = 0; }
function recordHistory(historyRef, indexRef, debounceTimer, content) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        if (historyRef.value[indexRef.value] === content) return;
        if (indexRef.value < historyRef.value.length - 1) historyRef.value.splice(indexRef.value + 1);
        historyRef.value.push(content);
        indexRef.value++;
    }, 500);
    return debounceTimer;
}
function undo(historyRef, indexRef, canUndo) { if (canUndo.value) { indexRef.value--; return historyRef.value[indexRef.value]; } }
function redo(historyRef, indexRef, canRedo) { if (canRedo.value) { indexRef.value++; return historyRef.value[indexRef.value]; } }

watch(discussionDataZone, (newVal) => { discussionHistoryDebounceTimer = recordHistory(discussionHistory, discussionHistoryIndex, discussionHistoryDebounceTimer, newVal); });
watch(userDataZone, (newVal) => { userHistoryDebounceTimer = recordHistory(userHistory, userHistoryIndex, userHistoryDebounceTimer, newVal); });
watch(memory, (newVal) => { memoryHistoryDebounceTimer = recordHistory(memoryHistory, memoryHistoryIndex, memoryHistoryDebounceTimer, newVal); });

watch(activeDiscussion, (newDiscussion) => {
    if (newDiscussion) {
        setupHistory(discussionHistory, discussionHistoryIndex, newDiscussion.discussion_data_zone || '');
        tokenizeContent(discussionDataZone.value, 'discussion');
        tokenizeContent(userDataZone.value, 'user');
        tokenizeContent(personalityDataZone.value, 'personality');
        tokenizeContent(memory.value, 'memory');
    }
}, { immediate: true, deep: true });

watch([isProcessing, isMemorizing], ([newIsProcessing, newIsMemorizing], [oldIsProcessing, oldIsMemorizing]) => {
    const taskFinished = (oldIsProcessing && !newIsProcessing) || (oldIsMemorizing && !newIsMemorizing);
    if (taskFinished && activeDiscussion.value) discussionsStore.refreshDataZones(activeDiscussion.value.id);
});

let startX = 0;
let startWidth = 0;
function startResize(event) {
    isResizing.value = true; startX = event.clientX; startWidth = dataZoneWidth.value;
    document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', handleResize); window.addEventListener('mouseup', stopResize);
}
function handleResize(event) {
    if (!isResizing.value) return; const dx = event.clientX - startX;
    const newWidth = startWidth - dx; const minWidth = 320;
    const maxWidth = window.innerWidth * 0.75; dataZoneWidth.value = Math.max(minWidth, Math.min(newWidth, maxWidth));
}
function stopResize() {
    isResizing.value = false; document.body.style.cursor = ''; document.body.style.userSelect = '';
    window.removeEventListener('mousemove', handleResize); window.removeEventListener('mouseup', stopResize);
    localStorage.setItem('lollms_dataZoneWidth', dataZoneWidth.value);
}
watch(isDataZoneVisible, (isVisible) => { if (isVisible) { promptsStore.fetchPrompts(); uiStore.fetchKeywords(); } });
function isImageActive(index) { return !discussionActiveImages.value || discussionActiveImages.value.length <= index || discussionActiveImages.value[index]; }
function insertPlaceholder(placeholder) {
    const view = userCodeMirrorEditor.value?.editorView; if (!view) return;
    const { from, to } = view.state.selection.main; const textToInsert = placeholder;
    view.dispatch({ changes: { from, to, insert: textToInsert }, selection: { anchor: from + textToInsert.length } }); view.focus();
}
function triggerKnowledgeFileUpload() { knowledgeFileInput.value?.click(); }

async function handleKnowledgeFileUpload(event) {
    const files = event.target.files; if (!files || files.length === 0) return;
    isExtractingText.value = true; const formData = new FormData();
    for (const file of files) { formData.append('files', file); }
    try {
        const response = await apiClient.post('/api/files/extract-text', formData); const extractedText = response.data.text;
        discussionDataZone.value = discussionDataZone.value ? `${discussionDataZone.value}\n\n${extractedText}` : extractedText;
        uiStore.addNotification(`Extracted text from ${files.length} file(s) and added to discussion data zone.`, 'success');
    } finally { isExtractingText.value = false; if (knowledgeFileInput.value) knowledgeFileInput.value.value = ''; }
}
function handleProcessContent() {
    if (!activeDiscussion.value) return; const finalPrompt = dataZonePromptText.value.replace('{{data_zone}}', discussionDataZone.value);
    discussionsStore.summarizeDiscussionDataZone(activeDiscussion.value.id, finalPrompt);
}
function openPromptLibrary() { if (!activeDiscussion.value) return; uiStore.openModal('dataZonePromptManagement'); }
function handlePromptSelection(promptContent) {
    if (/@<.*?>@/g.test(promptContent)) {
        uiStore.openModal('fillPlaceholders', { promptTemplate: promptContent, onConfirm: (filledPrompt) => { dataZonePromptText.value = filledPrompt; } });
    } else { dataZonePromptText.value = promptContent; }
}
function handleMemorize() { if (!activeDiscussion.value) return; discussionsStore.memorizeLTM(activeDiscussion.value.id); }
function refreshDataZones() { if (activeDiscussion.value) discussionsStore.refreshDataZones(activeDiscussion.value.id); }
async function exportDataZone() {
    if (!discussionDataZone.value.trim()) { uiStore.addNotification('Data zone is empty, nothing to export.', 'info'); return; }
    try {
        const formData = new FormData(); formData.append('content', discussionDataZone.value);
        formData.append('filename', `data_zone_${activeDiscussion.value.id.substring(0,8)}.md`);
        const response = await apiClient.post('/api/files/export-markdown', formData, { responseType: 'blob' });
        const url = window.URL.createObjectURL(new Blob([response.data])); const link = document.createElement('a');
        link.href = url; const contentDisposition = response.headers['content-disposition']; let filename = `data_zone_export.md`;
        if (contentDisposition) { const filenameMatch = contentDisposition.match(/filename="(.+)"/); if (filenameMatch.length === 2) filename = filenameMatch[1]; }
        link.setAttribute('download', filename); document.body.appendChild(link); link.click(); link.remove(); window.URL.revokeObjectURL(url);
    } catch (error) { uiStore.addNotification('Could not export data zone.', 'error'); }
}
function triggerDiscussionImageUpload() { discussionImageInput.value?.click(); }
async function handleDiscussionImageUpload(event) {
    const file = event.target.files[0]; if (!file || !activeDiscussion.value) return;
    isUploadingDiscussionImage.value = true;
    try { await discussionsStore.uploadDiscussionImage(file); } finally { isUploadingDiscussionImage.value = false; if (discussionImageInput.value) discussionImageInput.value.value = ''; }
}
</script>

<template>
    <div class="flex-1 flex flex-col h-full bg-gray-50 dark:bg-gray-900 overflow-hidden">
        <input type="file" ref="knowledgeFileInput" @change="handleKnowledgeFileUpload" multiple class="hidden" accept=".txt,.md,.pdf,.docx,.pptx,.xlsx,.xls, .py, .js, .html, .css, .json, .xml, .c, .cpp, .java">
        <input type="file" ref="discussionImageInput" @change="handleDiscussionImageUpload" class="hidden" accept="image/*,application/pdf">
        
        <div class="flex-1 flex min-h-0">
            <!-- Main Content: Chat Area -->
            <div class="flex-1 flex flex-col min-w-0 relative" :class="{'hidden': isDataZoneExpanded}">
                <MessageArea class="flex-1 overflow-y-auto min-w-0" />
                <ChatInput />
            </div>

            <!-- Resizer -->
            <div v-if="isDataZoneVisible && !isDataZoneExpanded" @mousedown.prevent="startResize" class="flex-shrink-0 w-1.5 cursor-col-resize bg-gray-300 dark:bg-gray-600 hover:bg-blue-500 transition-colors duration-200"></div>

            <!-- Data Zone Sidebar/Expanded View -->
            <transition enter-active-class="transition ease-in-out duration-300" enter-from-class="transform translate-x-full" enter-to-class="transform translate-x-0" leave-active-class="transition ease-in-out duration-300" leave-from-class="transform translate-x-0" leave-to-class="transform translate-x-full">
                <aside v-if="isDataZoneVisible && activeDiscussion" :class="[isDataZoneExpanded ? 'w-full' : 'flex-shrink-0']" :style="isDataZoneExpanded ? {} : { width: `${dataZoneWidth}px` }" class="h-full flex flex-col bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700">
                    <div class="flex-shrink-0 border-b border-gray-200 dark:border-gray-700">
                        <nav class="-mb-px flex space-x-2 px-4" aria-label="Tabs">
                            <button @click="activeDataZoneTab = 'discussion'" :class="['tab-btn', {'active': activeDataZoneTab === 'discussion'}]" title="Discussion Data">Discussion</button>
                            <button @click="activeDataZoneTab = 'user'" :class="['tab-btn', {'active': activeDataZoneTab === 'user'}]" title="User Data">User</button>
                            <button @click="activeDataZoneTab = 'personality'" :class="['tab-btn', {'active': activeDataZoneTab === 'personality'}]" title="Personality Data">Personality</button>
                            <button @click="activeDataZoneTab = 'ltm'" :class="['tab-btn', {'active': activeDataZoneTab === 'ltm'}]" title="Long-Term Memory">LTM</button>
                        </nav>
                    </div>
                    <!-- Discussion Data Zone -->
                    <div v-show="activeDataZoneTab === 'discussion'" class="flex-1 flex flex-col min-h-0" @paste="handlePasteInDataZone">
                        <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                            <div class="flex justify-between items-center"><h3 class="font-semibold flex items-center gap-2"><IconDataZone class="w-5 h-5" /> Discussion Data</h3>
                                <div class="flex items-center gap-1">
                                    <button @click="discussionDataZone = undo(discussionHistory, discussionHistoryIndex, canUndoDiscussion)" class="btn-icon" title="Undo" :disabled="!canUndoDiscussion"><IconUndo class="w-5 h-5" /></button>
                                    <button @click="discussionDataZone = redo(discussionHistory, discussionHistoryIndex, canRedoDiscussion)" class="btn-icon" title="Redo" :disabled="!canRedoDiscussion"><IconRedo class="w-5 h-5" /></button>
                                    <button @click="uiStore.toggleDataZoneExpansion()" class="btn-icon" :title="isDataZoneExpanded ? 'Shrink' : 'Expand'">
                                        <IconMinimize v-if="isDataZoneExpanded" class="w-5 h-5" />
                                        <IconMaximize v-else class="w-5 h-5" />
                                    </button>
                                    <button @click="refreshDataZones" class="btn-icon" title="Refresh Data"><IconRefresh class="w-5 h-5" /></button>
                                    <button @click="exportDataZone" class="btn-icon" title="Export to Markdown"><IconArrowUpTray class="w-5 h-5" /></button>
                                    <button @click="triggerDiscussionImageUpload" class="btn-icon" title="Add Image or PDF" :disabled="isUploadingDiscussionImage"><IconAnimateSpin v-if="isUploadingDiscussionImage" class="w-5 h-5" /><IconPhoto v-else class="w-5 h-5" /></button>
                                    <button @click="triggerKnowledgeFileUpload" class="btn-icon" title="Add text from files" :disabled="isExtractingText"><IconAnimateSpin v-if="isExtractingText" class="w-5 h-5" /><IconPlus v-else class="w-5 h-5" /></button>
                                    <button @click="discussionDataZone = ''" class="btn-icon-danger" title="Clear All Text"><IconTrash class="w-5 h-5" /></button>
                                </div>
                            </div>
                            <div class="mt-2">
                                <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 font-mono">
                                    <span>Tokens</span>
                                    <span>{{ formatNumber(discussionDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                                </div>
                                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1">
                                    <div class="h-1.5 rounded-full bg-blue-500 transition-width duration-500" :style="{ width: `${getPercentage(discussionDataZoneTokens)}%` }"></div>
                                </div>
                            </div>
                        </div>
                        <div v-if="discussionImages.length > 0" class="flex-shrink-0 p-2 border-b dark:border-gray-600">
                            <div class="grid grid-cols-4 sm:grid-cols-5 gap-2">
                                <div v-for="(img_b64, index) in discussionImages" :key="img_b64.substring(0, 20) + index" class="relative group/image">
                                    <img :src="'data:image/png;base64,' + img_b64" class="w-full h-16 object-cover rounded-md transition-all duration-300" :class="{'grayscale': !isImageActive(index)}"/>
                                    <div class="absolute inset-0 bg-black/50 opacity-0 group-hover/image:opacity-100 transition-opacity flex items-center justify-center gap-1">
                                        <button @click="uiStore.openImageViewer('data:image/png;base64,' + img_b64)" class="p-1.5 bg-white/20 text-white rounded-full hover:bg-white/40" title="View Image"><IconMaximize class="w-4 h-4" /></button>
                                        <button @click="discussionsStore.toggleDiscussionImageActivation(index)" class="p-1.5 bg-white/20 text-white rounded-full hover:bg-white/40" :title="isImageActive(index) ? 'Deactivate' : 'Activate'"><IconEye v-if="isImageActive(index)" class="w-4 h-4" /><IconEyeOff v-else class="w-4 h-4" /></button>
                                        <button @click="discussionsStore.deleteDiscussionImage(index)" class="p-1.5 bg-red-500/80 text-white rounded-full hover:bg-red-600" title="Delete"><IconXMark class="w-4 h-4" /></button>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div v-if="isUploadingDiscussionImage" class="flex-shrink-0 p-2 border-b dark:border-gray-600">
                            <div class="grid grid-cols-4 sm:grid-cols-5 gap-2">
                                <div class="relative w-full h-16 bg-gray-200 dark:bg-gray-700 rounded-md flex items-center justify-center animate-pulse">
                                    <IconPhoto class="w-8 h-8 text-gray-400 dark:text-gray-500" />
                                </div>
                            </div>
                        </div>
                        <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor ref="discussionCodeMirrorEditor" v-model="discussionDataZone" class="h-full" /></div>
                        <div class="p-4 border-t dark:border-gray-600 flex-shrink-0 space-y-3">
                            <div class="flex items-center gap-2">
                                <DropdownMenu title="Prompts" icon="ticket" collection="ui" button-class="btn-secondary btn-sm !p-2">
                                    <DropdownSubmenu v-if="filteredLollmsPrompts.length > 0" title="Default" icon="lollms" collection="ui">
                                        <button v-for="p in filteredLollmsPrompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm"><span class="truncate">{{ p.name }}</span></button>
                                    </DropdownSubmenu>
                                    <DropdownSubmenu v-if="filteredUserPrompts.length > 0" title="User" icon="user" collection="ui">
                                        <button v-for="p in filteredUserPrompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm">
                                            <img v-if="p.icon" :src="p.icon" class="h-5 w-5 rounded-md object-cover mr-2 flex-shrink-0" alt="Icon">
                                            <span class="truncate">{{ p.name }}</span>
                                        </button>
                                    </DropdownSubmenu>
                                    <DropdownSubmenu v-if="Object.keys(filteredSystemPromptsByZooCategory).length > 0" title="Zoo" icon="server" collection="ui">
                                        <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10">
                                            <input type="text" v-model="dataZonePromptSearchTerm" @click.stop placeholder="Search zoo..." class="input-field w-full text-sm">
                                        </div>
                                        <div class="max-h-60 overflow-y-auto">
                                            <div v-for="(prompts, category) in filteredSystemPromptsByZooCategory" :key="category">
                                                <h3 class="category-header">{{ category }}</h3>
                                                <button v-for="p in prompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm">
                                                    <img v-if="p.icon" :src="p.icon" class="h-5 w-5 rounded-md object-cover mr-2 flex-shrink-0" alt="Icon">
                                                    <span class="truncate">{{ p.name }}</span>
                                                </button>
                                            </div>
                                        </div>
                                    </DropdownSubmenu>
                                    <div v-if="(lollmsPrompts.length + userPrompts.length + Object.keys(systemPromptsByZooCategory).length) > 0" class="my-1 border-t dark:border-gray-600"></div>
                                    <button @click="openPromptLibrary" class="menu-item text-sm font-medium text-blue-600 dark:text-blue-400">Manage My Prompts...</button>
                                </DropdownMenu>
                                <textarea v-model="dataZonePromptText" placeholder="Enter a prompt to process the data zone content..." rows="2" class="input-field text-sm flex-grow"></textarea>
                            </div>
                            <button @click="handleProcessContent" class="btn btn-secondary btn-sm w-full" :disabled="isProcessing || (!discussionDataZone.trim() && discussionImages.length === 0)">
                                <IconSparkles class="w-4 h-4 mr-1.5" :class="{'animate-pulse': isProcessing}"/>{{ isProcessing ? 'Processing...' : 'Process Content' }}
                            </button>
                        </div>
                    </div>
                    <div v-show="activeDataZoneTab === 'user'" class="flex-1 flex flex-col min-h-0">
                        <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                            <div class="flex justify-between items-center">
                                <div>
                                    <h3 class="font-semibold flex items-center gap-2"><IconUserCircle class="w-5 h-5" /> User Data Zone</h3>
                                    <p class="text-xs text-gray-500 mt-1">Context for all of your discussions.</p>
                                </div>
                                <div class="flex items-center gap-1">
                                    <DropdownMenu title="Insert Placeholder" icon="ticket" collection="ui" button-class="btn-icon">
                                        <button v-for="keyword in keywords" :key="keyword.keyword" @click="insertPlaceholder(keyword.keyword)" class="w-full text-left p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-sm">
                                            <div class="font-mono font-semibold">{{ keyword.keyword }}</div>
                                            <div class="text-xs text-gray-500">{{ keyword.description }}</div>
                                        </button>
                                    </DropdownMenu>
                                    <button @click="userDataZone = undo(userHistory, userHistoryIndex, canUndoUser)" class="btn-icon" title="Undo" :disabled="!canUndoUser"><IconUndo class="w-5 h-5" /></button>
                                    <button @click="userDataZone = redo(userHistory, userHistoryIndex, canRedoUser)" class="btn-icon" title="Redo" :disabled="!canRedoUser"><IconRedo class="w-5 h-5" /></button>
                                </div>
                            </div>
                            <div class="mt-2">
                                <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 font-mono">
                                    <span>Tokens</span>
                                    <span>{{ formatNumber(userDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                                </div>
                                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1">
                                    <div class="h-1.5 rounded-full bg-green-500 transition-width duration-500" :style="{ width: `${getPercentage(userDataZoneTokens)}%` }"></div>
                                </div>
                            </div>
                        </div>
                        <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor ref="userCodeMirrorEditor" v-model="userDataZone" class="h-full" /></div>
                    </div>
                    <div v-show="activeDataZoneTab === 'personality'" class="flex-1 flex flex-col min-h-0">
                        <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                            <h3 class="font-semibold flex items-center gap-2"><IconSparkles class="w-5 h-5" /> Personality Data Zone</h3>
                            <p class="text-xs text-gray-500 mt-1">Read-only context from the active personality.</p>
                            <div class="mt-2">
                                <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 font-mono">
                                    <span>Tokens</span>
                                    <span>{{ formatNumber(personalityDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                                </div>
                                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1">
                                    <div class="h-1.5 rounded-full bg-purple-500 transition-width duration-500" :style="{ width: `${getPercentage(personalityDataZoneTokens)}%` }"></div>
                                </div>
                            </div>
                        </div>
                        <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor :model-value="personalityDataZone" class="h-full" :options="{ readOnly: true }" /></div>
                    </div>
                    <div v-show="activeDataZoneTab === 'ltm'" class="flex-1 flex flex-col min-h-0">
                        <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                            <div class="flex justify-between items-center">
                                 <div><h3 class="font-semibold flex items-center gap-2"><IconThinking class="w-5 h-5" /> Long-Term Memory</h3>
                                    <p class="text-xs text-gray-500 mt-1">Facts the AI has learned from conversations.</p>
                                </div>
                                <div class="flex items-center gap-1">
                                    <button @click="memory = undo(memoryHistory, memoryHistoryIndex, canUndoMemory)" class="btn-icon" title="Undo" :disabled="!canUndoMemory"><IconUndo class="w-5 h-5" /></button>
                                    <button @click="memory = redo(memoryHistory, memoryHistoryIndex, canRedoMemory)" class="btn-icon" title="Redo" :disabled="!canRedoMemory"><IconRedo class="w-5 h-5" /></button>
                                    <button @click="handleMemorize" class="btn btn-secondary btn-sm" title="Analyze discussion and memorize new facts" :disabled="isMemorizing"><IconSparkles class="w-4 h-4" :class="{'animate-pulse': isMemorizing}"/></button>
                                </div>
                            </div>
                            <div class="mt-2">
                                <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 font-mono">
                                    <span>Tokens</span>
                                    <span>{{ formatNumber(memoryDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                                </div>
                                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1">
                                    <div class="h-1.5 rounded-full bg-yellow-500 transition-width duration-500" :style="{ width: `${getPercentage(memoryDataZoneTokens)}%` }"></div>
                                </div>
                            </div>
                        </div>
                        <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor v-model="memory" class="h-full" /></div>
                    </div>
                </aside>
            </transition>
        </div>
    </div>
</template>

<style scoped>
.tab-btn { @apply px-3 py-2 text-sm font-medium border-b-2 transition-colors; }
.tab-btn.active { @apply border-blue-500 text-blue-600 dark:text-blue-400; }
.tab-btn:not(.active) { @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-500; }
.btn-icon { @apply p-2 rounded-full text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed; }
.btn-icon-danger { @apply p-2 rounded-full text-gray-500 dark:text-gray-400 hover:bg-red-100 dark:hover:bg-red-900/50 hover:text-red-600 dark:hover:text-red-400 transition-colors; }
.category-header { @apply px-3 py-1.5 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400 sticky top-0 bg-gray-50 dark:bg-gray-700 z-10; }
.menu-item { @apply w-full text-left px-3 py-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 flex items-center; }
</style>