<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import { usePromptsStore } from '../../stores/prompts';
import apiClient from '../../services/api';
import useEventBus from '../../services/eventBus';

// Component Imports
import MessageArea from './MessageArea.vue';
import ChatInput from './ChatInput.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import DropdownMenu from '../ui/DropdownMenu.vue';

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

// --- Store Initialization ---
const discussionsStore = useDiscussionsStore();
const authStore = useAuthStore();
const uiStore = useUiStore();
const promptsStore = usePromptsStore();
const { on, off } = useEventBus();

// --- Component State ---
const knowledgeFileInput = ref(null);
const isExtractingText = ref(false);
const activeDataZoneTab = ref('discussion');
const userCodeMirrorEditor = ref(null);
const dataZonePromptText = ref('');

// NEW: State for resizable panel
const dataZoneWidth = ref(448); // Default width (28rem)
const isResizing = ref(false);

// --- Data Zone State ---
let discussionSaveDebounceTimer = null;
let userSaveDebounceTimer = null;
let memorySaveDebounceTimer = null;

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
const showChatView = computed(() => activeDiscussion.value !== null);

const isProcessing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'summarize');
const isMemorizing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'memorize');

const defaultPrompts = [
    { name: 'Translate', content: 'Translate the following text to @<language:text:French>@. Keep the original formatting and style.' },
    { name: 'Summarize', content: 'Provide a concise summary of the key points in the following text.' },
    { name: 'To Mindmap', content: 'Convert the following text into a MermaidJS mindmap format. Start with the central theme and branch out to main ideas and sub-points.' },
    { name: 'To Bullet Points', content: 'List the main ideas from the following text as a clear, nested bullet point list.' },
];

const savedPrompts = computed(() => promptsStore.savedPrompts);
const keywords = computed(() => uiStore.keywords); // NEW: For placeholders

// --- Undo/Redo Computed Properties ---
const canUndoDiscussion = computed(() => discussionHistoryIndex.value > 0);
const canRedoDiscussion = computed(() => discussionHistoryIndex.value < discussionHistory.value.length - 1);
const canUndoUser = computed(() => userHistoryIndex.value > 0);
const canRedoUser = computed(() => userHistoryIndex.value < userHistory.value.length - 1);
const canUndoMemory = computed(() => memoryHistoryIndex.value > 0);
const canRedoMemory = computed(() => memoryHistoryIndex.value < memoryHistory.value.length - 1);

// --- Reactive Data Zone Management with Computed Properties ---
const discussionDataZone = computed({
    get: () => activeDiscussion.value?.discussion_data_zone || '',
    set: (newVal) => {
        if (activeDiscussion.value) {
            // This action handles UI state changes and cancels running tasks correctly.
            discussionsStore.setUserDataZoneContent(activeDiscussion.value.id, newVal);

            clearTimeout(discussionSaveDebounceTimer);
            discussionSaveDebounceTimer = setTimeout(() => {
                if (activeDiscussion.value) {
                    discussionsStore.updateDataZone({ discussionId: activeDiscussion.value.id, content: newVal });
                }
            }, 750);
        }
    }
});

const userDataZone = computed({
    get: () => authStore.user?.data_zone || '',
    set: (newVal) => {
        if (authStore.user) { authStore.user.data_zone = newVal; } // Update local state for immediate reactivity
        clearTimeout(userSaveDebounceTimer);
        userSaveDebounceTimer = setTimeout(() => { authStore.updateDataZone(newVal); }, 750);
    }
});

const personalityDataZone = computed(() => activeDiscussion.value?.personality_data_zone || '');

const memory = computed({
    get: () => authStore.user?.memory || '',
    set: (newVal) => {
        if (authStore.user) { authStore.user.memory = newVal; } // Update local state for immediate reactivity
        clearTimeout(memorySaveDebounceTimer);
        memorySaveDebounceTimer = setTimeout(() => { authStore.updateMemoryZone(newVal); }, 750);
    }
});

const combinedDataZoneContent = computed(() => {
    return [
        userDataZone.value ? `### User Data\n${userDataZone.value}` : '',
        discussionDataZone.value ? `### Discussion Data\n${discussionDataZone.value}` : '',
        personalityDataZone.value ? `### Personality Data\n${personalityDataZone.value}` : '',
        memory.value ? `### Long-Term Memory\n${memory.value}` : ''
    ].filter(Boolean).join('\n\n');
});

// NEW: Context Status Computed Properties
const contextStatus = computed(() => discussionsStore.activeDiscussionContextStatus);
const maxTokens = computed(() => contextStatus.value?.max_tokens || 1);

const discussionDataZoneTokens = computed(() => contextStatus.value?.zones?.system_context?.breakdown?.discussion_data_zone?.tokens || 0);
const userDataZoneTokens = computed(() => contextStatus.value?.zones?.system_context?.breakdown?.user_data_zone?.tokens || 0);
const personalityDataZoneTokens = computed(() => contextStatus.value?.zones?.system_context?.breakdown?.personality_data_zone?.tokens || 0);
const memoryDataZoneTokens = computed(() => contextStatus.value?.zones?.system_context?.breakdown?.memory?.tokens || 0);

const getPercentage = (tokens) => {
    if (maxTokens.value <= 0) return 0;
    return Math.min((tokens / maxTokens.value) * 100, 100); // Capped at 100%
};

const formatNumber = (num) => {
    return num ? num.toLocaleString() : '0';
};

watch(combinedDataZoneContent, (newCombinedText) => {
    discussionsStore.updateDataZonesTokenCount(newCombinedText);
}, { immediate: true });

// --- LIFECYCLE HOOKS ---
onMounted(() => {
    on('task:completed', handleTaskCompletion);
    const savedWidth = localStorage.getItem('lollms_dataZoneWidth');
    if (savedWidth) { dataZoneWidth.value = parseInt(savedWidth, 10); }

    // Initialize history for non-discussion zones
    setupHistory(userHistory, userHistoryIndex, userDataZone.value);
    setupHistory(memoryHistory, memoryHistoryIndex, memory.value);
});

onUnmounted(() => {
    off('task:completed', handleTaskCompletion);
    window.removeEventListener('mousemove', handleResize);
    window.removeEventListener('mouseup', stopResize);
});

// --- METHODS ---
function handleTaskCompletion(task) {
    if (activeDiscussion.value && task?.result?.discussion_id === activeDiscussion.value.id) {
        if (task.name.includes('Summarize') || task.name.includes('Memorize')) {
            refreshDataZones();
        }
    }
}

// --- History Methods ---
function setupHistory(historyRef, indexRef, initialValue) {
    historyRef.value = [initialValue];
    indexRef.value = 0;
}

function recordHistory(historyRef, indexRef, debounceTimer, content) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        if (historyRef.value[indexRef.value] === content) return;

        if (indexRef.value < historyRef.value.length - 1) {
            historyRef.value.splice(indexRef.value + 1);
        }
        historyRef.value.push(content);
        indexRef.value++;
    }, 500);
    return debounceTimer;
}

function undo(historyRef, indexRef, canUndo) {
    if (canUndo.value) {
        indexRef.value--;
        return historyRef.value[indexRef.value];
    }
}

function redo(historyRef, indexRef, canRedo) {
    if (canRedo.value) {
        indexRef.value++;
        return historyRef.value[indexRef.value];
    }
}

watch(discussionDataZone, (newVal) => {
    discussionHistoryDebounceTimer = recordHistory(discussionHistory, discussionHistoryIndex, discussionHistoryDebounceTimer, newVal);
});
watch(userDataZone, (newVal) => {
    userHistoryDebounceTimer = recordHistory(userHistory, userHistoryIndex, userHistoryDebounceTimer, newVal);
});
watch(memory, (newVal) => {
    memoryHistoryDebounceTimer = recordHistory(memoryHistory, memoryHistoryIndex, memoryHistoryDebounceTimer, newVal);
});

watch(activeDiscussion, (newDiscussion) => {
    if (newDiscussion) {
        setupHistory(discussionHistory, discussionHistoryIndex, newDiscussion.discussion_data_zone || '');
    }
}, { immediate: true });

watch([isProcessing, isMemorizing], ([newIsProcessing, newIsMemorizing], [oldIsProcessing, oldIsMemorizing]) => {
    const taskFinished = (oldIsProcessing && !newIsProcessing) || (oldIsMemorizing && !newIsMemorizing);
    if (taskFinished && activeDiscussion.value) {
        // A task related to this discussion has just finished.
        // Refresh the data from the backend to ensure the UI is up-to-date.
        discussionsStore.refreshDataZones(activeDiscussion.value.id);
    }
});

// Resizing Logic
let startX = 0;
let startWidth = 0;

function startResize(event) {
    isResizing.value = true;
    startX = event.clientX;
    startWidth = dataZoneWidth.value;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', handleResize);
    window.addEventListener('mouseup', stopResize);
}

function handleResize(event) {
    if (!isResizing.value) return;
    const dx = event.clientX - startX;
    const newWidth = startWidth - dx;
    const minWidth = 320;
    const maxWidth = window.innerWidth * 0.75;
    dataZoneWidth.value = Math.max(minWidth, Math.min(newWidth, maxWidth));
}

function stopResize() {
    isResizing.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    window.removeEventListener('mousemove', handleResize);
    window.removeEventListener('mouseup', stopResize);
    localStorage.setItem('lollms_dataZoneWidth', dataZoneWidth.value);
}

watch(isDataZoneVisible, (isVisible) => { 
    if (isVisible) { 
        promptsStore.fetchPrompts();
        uiStore.fetchKeywords();
    } 
});

function insertPlaceholder(placeholder) {
    const view = userCodeMirrorEditor.value?.editorView;
    if (!view) return;
    const { from, to } = view.state.selection.main;
    const textToInsert = placeholder;
    
    view.dispatch({
        changes: { from, to, insert: textToInsert },
        selection: { anchor: from + textToInsert.length }
    });
    view.focus();
}

function triggerKnowledgeFileUpload() { knowledgeFileInput.value?.click(); }

async function handleKnowledgeFileUpload(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    isExtractingText.value = true;
    const formData = new FormData();
    for (const file of files) { formData.append('files', file); }
    try {
        const response = await apiClient.post('/api/files/extract-text', formData);
        const extractedText = response.data.text;
        discussionDataZone.value = discussionDataZone.value ? `${discussionDataZone.value}\n\n${extractedText}` : extractedText;
        uiStore.addNotification(`Extracted text from ${files.length} file(s) and added to discussion data zone.`, 'success');
    } finally {
        isExtractingText.value = false;
        if (knowledgeFileInput.value) knowledgeFileInput.value.value = '';
    }
}

function handleProcessContent() {
    if (!activeDiscussion.value) return;
    const finalPrompt = dataZonePromptText.value.replace('{{data_zone}}', discussionDataZone.value);
    discussionsStore.summarizeDiscussionDataZone(activeDiscussion.value.id, finalPrompt);
}

function openPromptLibrary() {
    if (!activeDiscussion.value) return;
    uiStore.openModal('dataZonePromptManagement', {
        initialPrompt: dataZonePromptText.value,
        onLoad: (loadedPrompt) => {
            handlePromptSelection(loadedPrompt);
        }
    });
}

function handlePromptSelection(promptContent) {
    if (/@<.*?>@/g.test(promptContent)) {
        uiStore.openModal('fillPlaceholders', {
            promptTemplate: promptContent,
            onConfirm: (filledPrompt) => {
                dataZonePromptText.value = filledPrompt;
            }
        });
    } else {
        dataZonePromptText.value = promptContent;
    }
}

function handleMemorize() {
    if (!activeDiscussion.value) return;
    discussionsStore.memorizeLTM(activeDiscussion.value.id);
}

function refreshDataZones() {
    if (activeDiscussion.value) {
        discussionsStore.refreshDataZones(activeDiscussion.value.id);
    }
}

async function exportDataZone() {
    if (!discussionDataZone.value.trim()) {
        uiStore.addNotification('Data zone is empty, nothing to export.', 'info');
        return;
    }
    try {
        const formData = new FormData();
        formData.append('content', discussionDataZone.value);
        formData.append('filename', `data_zone_${activeDiscussion.value.id.substring(0,8)}.md`);
        const response = await apiClient.post('/api/files/export-markdown', formData, { responseType: 'blob' });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        const contentDisposition = response.headers['content-disposition'];
        let filename = `data_zone_export.md`;
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="(.+)"/);
            if (filenameMatch.length === 2) filename = filenameMatch[1];
        }
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        uiStore.addNotification('Could not export data zone.', 'error');
    }
}
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-gray-50 dark:bg-gray-900 overflow-hidden">
    <input type="file" ref="knowledgeFileInput" @change="handleKnowledgeFileUpload" multiple class="hidden" accept=".txt,.md,.pdf,.docx,.pptx,.xlsx,.xls, .py, .js, .html, .css, .json, .xml, .c, .cpp, .java">
    <div class="flex-1 flex min-h-0">
        <div v-if="!isDataZoneExpanded" class="flex-1 flex flex-col min-w-0 relative">
            <MessageArea v-if="showChatView" class="flex-1 overflow-y-auto min-w-0" />
            <div v-else class="flex-1 flex items-center justify-center text-center p-4">
              <div class="max-w-md">
                <img :src="logoUrl" alt="LoLLMs Logo" class="w-24 h-24 mx-auto mb-4 opacity-50" />
                <h3 class="text-xl font-semibold text-gray-700 dark:text-gray-300">Welcome to LoLLMs Chat</h3>
                <p class="text-gray-500 dark:text-gray-400 mt-2">Start a new conversation or select an existing one to begin.</p>
              </div>
            </div>
            <ChatInput :data-zone-content="combinedDataZoneContent" />
        </div>
        
        <div v-if="isDataZoneVisible && !isDataZoneExpanded" @mousedown.prevent="startResize" class="flex-shrink-0 w-1.5 cursor-col-resize bg-gray-300 dark:bg-gray-600 hover:bg-blue-500 transition-colors duration-200"></div>

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
                <div v-show="activeDataZoneTab === 'discussion'" class="flex-1 flex flex-col min-h-0">
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
                                <button @click="triggerKnowledgeFileUpload" class="btn-icon" title="Add text from files" :disabled="isExtractingText"><IconAnimateSpin v-if="isExtractingText" class="w-5 h-5" /><IconPlus v-else class="w-5 h-5" /></button>
                                <button @click="discussionDataZone = ''" class="btn-icon-danger" title="Clear All Text"><IconTrash class="w-5 h-5" /></button>
                            </div>
                        </div>
                        <div v-if="contextStatus" class="mt-2">
                            <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 font-mono">
                                <span>Tokens</span>
                                <span>{{ formatNumber(discussionDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                            </div>
                            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1">
                                <div class="h-1.5 rounded-full bg-blue-500" :style="{ width: `${getPercentage(discussionDataZoneTokens)}%` }"></div>
                            </div>
                        </div>
                    </div>
                    <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor v-model="discussionDataZone" class="h-full" /></div>
                    <div class="p-4 border-t dark:border-gray-600 flex-shrink-0 space-y-3">
                        <div class="flex items-center gap-2">
                            <DropdownMenu title="Prompts" icon="ticket" collection="ui" button-class="btn-secondary btn-sm !p-2">
                                <div class="px-1 py-1"><div class="px-2 py-1.5 text-xs font-semibold text-gray-500">Default</div></div>
                                <button v-for="p in defaultPrompts" :key="p.name" @click="handlePromptSelection(p.content)" class="menu-item text-sm"><span>{{ p.name }}</span></button>
                                <div class="my-1 border-t dark:border-gray-600"></div>
                                <div class="px-1 py-1"><div class="px-2 py-1.5 text-xs font-semibold text-gray-500">Saved</div></div>
                                <button v-for="p in savedPrompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm"><span>{{ p.name }}</span></button>
                                <div class="my-1 border-t dark:border-gray-600"></div>
                                <button @click="openPromptLibrary" class="menu-item text-sm font-medium text-blue-600 dark:text-blue-400">Manage Prompts...</button>
                            </DropdownMenu>
                            <textarea v-model="dataZonePromptText" placeholder="Enter a prompt to process the data zone content..." rows="2" class="input-field text-sm flex-grow"></textarea>
                        </div>
                        <button @click="handleProcessContent" class="btn btn-secondary btn-sm w-full" :disabled="isProcessing || !discussionDataZone.trim()">
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
                        <div v-if="contextStatus" class="mt-2">
                            <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 font-mono">
                                <span>Tokens</span>
                                <span>{{ formatNumber(userDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                            </div>
                            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1">
                                <div class="h-1.5 rounded-full bg-green-500" :style="{ width: `${getPercentage(userDataZoneTokens)}%` }"></div>
                            </div>
                        </div>
                    </div>
                    <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor ref="userCodeMirrorEditor" v-model="userDataZone" class="h-full" /></div>
                </div>
                <div v-show="activeDataZoneTab === 'personality'" class="flex-1 flex flex-col min-h-0">
                    <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                        <h3 class="font-semibold flex items-center gap-2"><IconSparkles class="w-5 h-5" /> Personality Data Zone</h3>
                        <p class="text-xs text-gray-500 mt-1">Read-only context from the active personality.</p>
                        <div v-if="contextStatus" class="mt-2">
                            <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 font-mono">
                                <span>Tokens</span>
                                <span>{{ formatNumber(personalityDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                            </div>
                            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1">
                                <div class="h-1.5 rounded-full bg-purple-500" :style="{ width: `${getPercentage(personalityDataZoneTokens)}%` }"></div>
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
                        <div v-if="contextStatus" class="mt-2">
                            <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 font-mono">
                                <span>Tokens</span>
                                <span>{{ formatNumber(memoryDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                            </div>
                            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1">
                                <div class="h-1.5 rounded-full bg-yellow-500" :style="{ width: `${getPercentage(memoryDataZoneTokens)}%` }"></div>
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
.menu-item { @apply w-full text-left p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600; }
</style>