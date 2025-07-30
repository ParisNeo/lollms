<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';
import useEventBus from '../../services/eventBus';

// Component Imports
import MessageArea from './MessageArea.vue';
import ChatInput from './ChatInput.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import SimpleSelectMenu from '../ui/SimpleSelectMenu.vue';

// Asset & Icon Imports
import logoUrl from '../../assets/logo.png';
import IconDataZone from '../../assets/icons/IconDataZone.vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconThinking from '../../assets/icons/IconThinking.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';

// --- Store Initialization ---
const discussionsStore = useDiscussionsStore();
const authStore = useAuthStore();
const uiStore = useUiStore();
const { on, off } = useEventBus();

// --- Component State ---
const isDataZoneVisible = ref(false);
const knowledgeFileInput = ref(null);
const isExtractingText = ref(false);
const activeDataZoneTab = ref('discussion');
const userCodeMirrorEditor = ref(null);
const summaryPrompt = ref('');
const placeholderToInsert = ref(null);

// NEW: State for resizable panel
const dataZoneWidth = ref(448); // Default width (28rem)
const isResizing = ref(false);

// --- Data Zone State ---
let discussionSaveDebounceTimer = null;
let userSaveDebounceTimer = null;
let memorySaveDebounceTimer = null;

// --- Computed Properties ---
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const showChatView = computed(() => activeDiscussion.value !== null);

const isSummarizing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id] === 'summarize');
const isMemorizing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id] === 'memorize');

const placeholderItems = computed(() => {
    return uiStore.keywords.map(kw => ({
        value: kw.keyword,
        label: `${kw.keyword} - ${kw.description}`
    }));
});


// --- Reactive Data Zone Management with Computed Properties ---
const discussionDataZone = computed({
    get: () => activeDiscussion.value?.discussion_data_zone || '',
    set: (newVal) => {
        clearTimeout(discussionSaveDebounceTimer);
        discussionSaveDebounceTimer = setTimeout(() => {
            if (activeDiscussion.value) {
                discussionsStore.updateDataZone({ discussionId: activeDiscussion.value.id, content: newVal });
            }
        }, 750);
        if (activeDiscussion.value) {
            discussionsStore.discussions[activeDiscussion.value.id].discussion_data_zone = newVal;
        }
    }
});

const userDataZone = computed({
    get: () => authStore.user?.data_zone || '',
    set: (newVal) => {
        clearTimeout(userSaveDebounceTimer);
        userSaveDebounceTimer = setTimeout(() => {
            authStore.updateDataZone(newVal);
        }, 750);
        if (authStore.user) {
            authStore.user.data_zone = newVal;
        }
    }
});

const personalityDataZone = computed(() => activeDiscussion.value?.personality_data_zone || '');

const memory = computed({
    get: () => activeDiscussion.value?.memory || '',
    set: (newVal) => {
        clearTimeout(memorySaveDebounceTimer);
        memorySaveDebounceTimer = setTimeout(() => {
            authStore.updateMemoryZone(newVal);
        }, 750);
        if (authStore.user) {
            authStore.user.memory = newVal;
        }
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

watch(combinedDataZoneContent, (newCombinedText) => {
    discussionsStore.updateDataZonesTokenCount(newCombinedText);
}, { immediate: true });

// --- LIFECYCLE HOOKS ---
onMounted(() => {
    on('task:completed', handleTaskCompletion);
    const savedWidth = localStorage.getItem('lollms_dataZoneWidth');
    if (savedWidth) {
        dataZoneWidth.value = parseInt(savedWidth, 10);
    }
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
            console.log('Relevant task completed, refreshing data zones...');
            refreshDataZones();
        }
    }
}

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


async function toggleDataZone() {
    isDataZoneVisible.value = !isDataZoneVisible.value;
    if (isDataZoneVisible.value) {
        uiStore.fetchKeywords();
    }
}

function triggerKnowledgeFileUpload() {
    knowledgeFileInput.value?.click();
}

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

function handleSummarize(promptText) {
    if (!activeDiscussion.value) return;
    discussionsStore.summarizeDiscussionDataZone(activeDiscussion.value.id, promptText);
}

function openSummaryPromptModal() {
    if (!activeDiscussion.value) return;
    uiStore.openModal('summaryPromptModal', {
        discussionId: activeDiscussion.value.id,
        initialPrompt: summaryPrompt.value,
        onApply: (promptText) => {
            summaryPrompt.value = promptText;
            handleSummarize(promptText);
        }
    });
}

function refreshDataZones() {
    if (activeDiscussion.value) {
        discussionsStore.refreshDataZones(activeDiscussion.value.id);
    }
}


function insertPlaceholder(keyword) {
    const view = userCodeMirrorEditor.value?.codeMirrorView;
    if (view) {
        const { from, to } = view.state.selection.main;
        view.dispatch({ changes: { from, to, insert: keyword } });
        view.focus();
    }
}

watch(placeholderToInsert, (newValue) => {
    if (newValue) {
        insertPlaceholder(newValue);
        nextTick(() => {
            placeholderToInsert.value = null;
        });
    }
});

async function exportDataZone() {
    if (!discussionDataZone.value.trim()) {
        uiStore.addNotification('Data zone is empty, nothing to export.', 'info');
        return;
    }
    try {
        const formData = new FormData();
        formData.append('content', discussionDataZone.value);
        formData.append('filename', `data_zone_${activeDiscussion.value.id.substring(0,8)}.md`);

        const response = await apiClient.post('/api/files/export-markdown', formData, {
            responseType: 'blob',
        });

        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        const contentDisposition = response.headers['content-disposition'];
        let filename = `data_zone_export.md`;
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="(.+)"/);
            if (filenameMatch.length === 2)
                filename = filenameMatch[1];
        }
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error("Failed to export data zone:", error);
        uiStore.addNotification('Could not export data zone.', 'error');
    }
}
</script>

<template>
  <div class="flex-1 flex flex-col h-full bg-gray-50 dark:bg-gray-900 overflow-hidden">
    <input type="file" ref="knowledgeFileInput" @change="handleKnowledgeFileUpload" multiple class="hidden" accept=".txt,.md,.pdf,.docx,.pptx,.xlsx,.xls, .py, .js, .html, .css, .json, .xml, .c, .cpp, .java">
    <div class="flex-1 flex min-h-0">
        <div class="flex-1 flex flex-col min-w-0 relative">
            <MessageArea v-if="showChatView" class="flex-1 overflow-y-auto min-w-0" />
            <div v-else class="flex-1 flex items-center justify-center text-center p-4">
              <div class="max-w-md">
                <img :src="logoUrl" alt="LoLLMs Logo" class="w-24 h-24 mx-auto mb-4 opacity-50" />
                <h3 class="text-xl font-semibold text-gray-700 dark:text-gray-300">Welcome to LoLLMs Chat</h3>
                <p class="text-gray-500 dark:text-gray-400 mt-2">Start a new conversation or select an existing one to begin.</p>
              </div>
            </div>
            <ChatInput @toggle-data-zone="toggleDataZone" :data-zone-content="combinedDataZoneContent" />
        </div>
        
        <div v-if="isDataZoneVisible && activeDiscussion" 
             @mousedown.prevent="startResize"
             class="flex-shrink-0 w-1.5 cursor-col-resize bg-gray-300 dark:bg-gray-600 hover:bg-blue-500 transition-colors duration-200">
        </div>

        <transition enter-active-class="transition ease-in-out duration-300" enter-from-class="transform translate-x-full" enter-to-class="transform translate-x-0" leave-active-class="transition ease-in-out duration-300" leave-from-class="transform translate-x-0" leave-to-class="transform translate-x-full">
            <aside v-if="isDataZoneVisible && activeDiscussion" :style="{ width: `${dataZoneWidth}px` }" class="h-full flex flex-col flex-shrink-0 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700">
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
                        <div class="flex justify-between items-center">
                            <h3 class="font-semibold flex items-center gap-2"><IconDataZone class="w-5 h-5" /> Discussion Data</h3>
                            <div class="flex items-center gap-2">
                                <button @click="refreshDataZones" class="btn btn-secondary btn-sm" title="Refresh Data Zone"><IconRefresh class="w-4 h-4" /></button>
                                <button @click="exportDataZone" class="btn btn-secondary btn-sm" title="Export to Markdown"><IconArrowUpTray class="w-4 h-4" /></button>
                                <button @click="triggerKnowledgeFileUpload" class="btn btn-secondary btn-sm" title="Add text from files" :disabled="isExtractingText"><IconAnimateSpin v-if="isExtractingText" class="w-4 h-4" /><IconPlus v-else class="w-4 h-4" /></button>
                            </div>
                        </div>
                        <div class="flex justify-end mt-4">
                            <button @click="openSummaryPromptModal" class="btn btn-secondary btn-sm w-full"><IconSparkles class="w-4 h-4 mr-1.5" :class="{'animate-pulse': isSummarizing}"/>Process Content...</button>
                        </div>
                    </div>
                    <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor v-model="discussionDataZone" class="h-full" /></div>
                </div>
                <!-- User Data Zone -->
                <div v-show="activeDataZoneTab === 'user'" class="flex-1 flex flex-col min-h-0">
                    <div class="p-4 border-b dark:border-gray-600 flex-shrink-0 flex justify-between items-center">
                        <div>
                           <h3 class="font-semibold flex items-center gap-2"><IconUserCircle class="w-5 h-5" /> User Data Zone</h3>
                           <p class="text-xs text-gray-500 mt-1">Context for all of your discussions.</p>
                        </div>
                        <SimpleSelectMenu v-model="placeholderToInsert" :items="placeholderItems">
                            <template #button="{ toggle }">
                                <button @click="toggle" type="button" class="btn btn-secondary btn-sm flex items-center gap-1.5">
                                    <IconInfo class="w-4 h-4" /> Insert Placeholder
                                </button>
                            </template>
                        </SimpleSelectMenu>
                    </div>
                    <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor ref="userCodeMirrorEditor" v-model="userDataZone" class="h-full" /></div>
                </div>
                <!-- Personality Data Zone -->
                <div v-show="activeDataZoneTab === 'personality'" class="flex-1 flex flex-col min-h-0">
                    <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                        <h3 class="font-semibold flex items-center gap-2"><IconSparkles class="w-5 h-5" /> Personality Data Zone</h3>
                        <p class="text-xs text-gray-500 mt-1">Read-only context from the active personality.</p>
                    </div>
                    <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor :model-value="personalityDataZone" class="h-full" :options="{ readOnly: true }" /></div>
                </div>
                <!-- Long-Term Memory (LTM) -->
                <div v-show="activeDataZoneTab === 'ltm'" class="flex-1 flex flex-col min-h-0">
                    <div class="p-4 border-b dark:border-gray-600 flex-shrink-0 flex justify-between items-center">
                         <div>
                            <h3 class="font-semibold flex items-center gap-2"><IconThinking class="w-5 h-5" /> Long-Term Memory</h3>
                            <p class="text-xs text-gray-500 mt-1">Facts the AI has learned from conversations.</p>
                        </div>
                        <button @click="handleMemorize" class="btn btn-secondary btn-sm" title="Analyze discussion and memorize new facts" :disabled="isMemorizing"><IconSparkles class="w-4 h-4" :class="{'animate-pulse': isMemorizing}"/></button>
                    </div>
                    <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor :model-value="memory" class="h-full" :options="{ readOnly: true }" /></div>
                </div>
            </aside>
        </transition>
    </div>
  </div>
</template>

<style scoped>
.tab-btn {
    @apply px-3 py-2 text-sm font-medium border-b-2 transition-colors;
}
.tab-btn.active {
    @apply border-blue-500 text-blue-600 dark:text-blue-400;
}
.tab-btn:not(.active) {
    @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-500;
}
</style>