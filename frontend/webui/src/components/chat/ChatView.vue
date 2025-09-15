<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick, defineAsyncComponent } from 'vue';
import { useRouter } from 'vue-router';
import { useDiscussionsStore } from '../../stores/discussions';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { usePromptsStore } from '../../stores/prompts';
import { useTasksStore } from '../../stores/tasks';
import { useMemoriesStore } from '../../stores/memories';
import apiClient from '../../services/api';
import useEventBus from '../../services/eventBus';
import { storeToRefs } from 'pinia';

// Component Imports
import MessageArea from './MessageArea.vue';
import ChatInput from './ChatInput.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import DropdownMenu from '../ui/DropdownMenu.vue';
import DropdownSubmenu from '../ui/DropdownSubmenu.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer.vue';
import ToolbarButton from '../ui/ToolbarButton.vue';
const ArtefactCard = defineAsyncComponent(() => import('../ui/ArtefactCard.vue'));

// Asset & Icon Imports
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
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../assets/icons/IconMinimize.vue';
import IconUndo from '../../assets/icons/IconUndo.vue';
import IconRedo from '../../assets/icons/IconRedo.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconUser from '../../assets/icons/IconUser.vue';
import IconLollms from '../../assets/icons/IconLollms.vue';
import IconWeb from '../../assets/icons/ui/IconWeb.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconToken from '../../assets/icons/IconToken.vue';
import IconGather from '../../assets/icons/IconGather.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';

// Store Initialization
const discussionsStore = useDiscussionsStore();
const authStore = useAuthStore();
const uiStore = useUiStore();
const promptsStore = usePromptsStore();
const tasksStore = useTasksStore();
const dataStore = useDataStore();
const memoriesStore = useMemoriesStore();
const router = useRouter();
const { on, off } = useEventBus();
const { liveDataZoneTokens, currentModelVisionSupport, activeDiscussionArtefacts, isLoadingArtefacts, generationInProgress, promptLoadedArtefacts } = storeToRefs(discussionsStore);
const { lollmsPrompts, systemPromptsByZooCategory, userPromptsByCategory } = storeToRefs(promptsStore);
const { availableTtiModels } = storeToRefs(dataStore);
const { memories, isLoading: isLoadingMemories } = storeToRefs(memoriesStore);

// Component State
const artefactFileInput = ref(null);
const discussionImageInput = ref(null);
const isUploadingDiscussionImage = ref(false);
const isUploadingArtefact = ref(false);
const activeDataZoneTab = ref('discussion');
const discussionCodeMirrorEditor = ref(null);
const userCodeMirrorEditor = ref(null);
const dataZonePromptText = ref('');
const dataZonePromptTextareaRef = ref(null); // Ref for the textarea
const dataZoneWidth = ref(768);
const isResizing = ref(false);
const userPromptSearchTerm = ref('');
const zooPromptSearchTerm = ref('');
const dataZoneViewModes = ref({
    discussion: 'edit',
    user: 'edit',
    personality: 'view',
    ltm: 'edit'
});
const urlToImport = ref('');
const showUrlImport = ref(false);
const isProgrammaticChange = ref(false);
const isDraggingFile = ref(false);
const memorySearchTerm = ref('');
const loadedMemoryTitles = ref(new Set());
const isExportingArtefact = ref(null); // Holds the title of the artefact being exported

const isImagesCollapsed = ref(false);
const isArtefactsCollapsed = ref(false);

const artefactListWidth = ref(256);
const isResizingArtefacts = ref(false);

// Data Zone State
let discussionSaveDebounceTimer = null;
let userSaveDebounceTimer = null;
let tokenizeDebounceTimers = {};

// History State for Undo/Redo
const discussionHistory = ref([]);
const discussionHistoryIndex = ref(-1);
let discussionHistoryDebounceTimer = null;
const userHistory = ref([]);
const userHistoryIndex = ref(-1);
let userHistoryDebounceTimer = null;

// Computed Properties
const isTtiConfigured = computed(() => availableTtiModels.value.length > 0);
const isDataZoneVisible = computed(() => uiStore.isDataZoneVisible);
const isDataZoneExpanded = computed(() => uiStore.isDataZoneExpanded);
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);

const discussionImages = computed(() => activeDiscussion.value?.discussion_images || []);
const discussionActiveImages = computed(() => activeDiscussion.value?.active_discussion_images || []);

const isProcessing = computed(() => {
    if (!activeDiscussion.value) return false;
    const task = discussionsStore.activeAiTasks[activeDiscussion.value.id];
    return task?.type === 'summarize' || task?.type === 'generate_image' || task?.type === 'import_url';
});

const isGeneratingOrProcessing = computed(() => generationInProgress.value || isProcessing.value);

const isMemorizing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'memorize');

const discussionEditorOptions = computed(() => ({ readOnly: isGeneratingOrProcessing.value }));

const keywords = computed(() => uiStore.keywords);
const canUndoDiscussion = computed(() => discussionHistoryIndex.value > 0);
const canRedoDiscussion = computed(() => discussionHistoryIndex.value < discussionHistory.value.length - 1);
const canUndoUser = computed(() => userHistoryIndex.value > 0);
const canRedoUser = computed(() => userHistoryIndex.value < userHistory.value.length - 1);

// Add these computed properties to your <script setup> section
const filteredLollmsPrompts = computed(() => {
    if (!Array.isArray(lollmsPrompts.value)) return [];
    if (!userPromptSearchTerm.value) return lollmsPrompts.value;
    const term = userPromptSearchTerm.value.toLowerCase();
    return lollmsPrompts.value.filter(p => p?.name?.toLowerCase().includes(term) || false);
});

const filteredUserPromptsByCategory = computed(() => {
    const term = userPromptSearchTerm.value.toLowerCase();
    const source = userPromptsByCategory.value;
    if (!source || typeof source !== 'object') return {};
    
    if (!term) return source;
    
    const filtered = {};
    for (const category in source) {
        if (Array.isArray(source[category])) {
            const filteredPrompts = source[category].filter(p => 
                p?.name?.toLowerCase().includes(term) || false
            );
            if (filteredPrompts.length > 0) {
                filtered[category] = filteredPrompts;
            }
        }
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
        if (Array.isArray(source[category])) {
            const filteredPrompts = source[category].filter(p => 
                p?.name?.toLowerCase().includes(term) || false
            );
            if (filteredPrompts.length > 0) {
                filtered[category] = filteredPrompts;
            }
        }
    }
    return filtered;
}); 

const getProgressColorClass = (percentage) => {
    if (percentage >= 90) return 'from-red-400 to-red-600';
    if (percentage >= 70) return 'from-yellow-400 to-orange-500';
    return 'from-green-400 to-green-500';
};

// Enhanced Data Zone Tabs Configuration
const dataTabs = computed(() => [
    {
        id: 'discussion',
        label: 'Discussion',
        icon: IconDataZone,
        tokenCount: discussionDataZoneTokens.value,
        color: 'blue',
        description: 'Discussion-specific context and data'
    },
    {
        id: 'user',
        label: 'User',
        icon: IconUserCircle,
        tokenCount: userDataZoneTokens.value,
        color: 'green',
        description: 'Global user context for all discussions'
    },
    {
        id: 'personality',
        label: 'Personality',
        icon: IconSparkles,
        tokenCount: personalityDataZoneTokens.value,
        color: 'purple',
        description: 'Active personality context (read-only)'
    },
    {
        id: 'ltm',
        label: 'Memory',
        icon: IconThinking,
        tokenCount: memoryDataZoneTokens.value,
        color: 'yellow',
        description: 'Long-term memory storage'
    }
]);

const groupedArtefacts = computed(() => {
    if (!activeDiscussionArtefacts.value || !Array.isArray(activeDiscussionArtefacts.value)) return [];
    
    const groups = activeDiscussionArtefacts.value.reduce((acc, artefact) => {
        if (!acc[artefact.title]) {
            acc[artefact.title] = {
                title: artefact.title,
                versions: [],
                fileType: getFileType(artefact.title)
            };
        }
        acc[artefact.title].versions.push(artefact);
        return acc;
    }, {});

    Object.values(groups).forEach(group => {
        group.versions.sort((a, b) => b.version - a.version);
        // Explicitly calculate isAnyVersionLoaded after grouping
        group.isAnyVersionLoaded = group.versions.some(v => v.is_loaded);
    });

    return Object.values(groups);
});

const filteredMemories = computed(() => {
    if (!memorySearchTerm.value) return memories.value;
    const term = memorySearchTerm.value.toLowerCase();
    return memories.value.filter(m => 
        m.title.toLowerCase().includes(term) || 
        m.content.toLowerCase().includes(term)
    );
});

// Data Zone Content Getters/Setters
const discussionDataZone = computed({
    get: () => activeDiscussion.value?.discussion_data_zone || '',
    set: (newVal) => {
        if (activeDiscussion.value) {
            discussionsStore.setDiscussionDataZoneContent(activeDiscussion.value.id, newVal);
            clearTimeout(discussionSaveDebounceTimer);
            discussionSaveDebounceTimer = setTimeout(() => {
                if (activeDiscussion.value) discussionsStore.updateDataZone({ discussionId: activeDiscussion.value.id, content: newVal });
            }, 750);
        }
    }
});

function insertPlaceholder(placeholder) {
    let targetEditor = null;
    
    // Determine which editor to use based on active tab and view mode
    switch (activeDataZoneTab.value) {
        case 'discussion':
            if (dataZoneViewModes.value.discussion === 'edit') {
                targetEditor = discussionCodeMirrorEditor.value;
            }
            break;
        case 'user':
            if (dataZoneViewModes.value.user === 'edit') {
                targetEditor = userCodeMirrorEditor.value;
            }
            break;
        // Add other cases if needed for personality/ltm tabs
        default:
            // Fallback to user editor
            targetEditor = userCodeMirrorEditor.value;
            break;
    }
    
    if (!targetEditor?.editorView) {
        console.warn('No active editor found for placeholder insertion');
        return;
    }
    
    const view = targetEditor.editorView;
    const { from, to } = view.state.selection.main;
    const textToInsert = placeholder;
    
    view.dispatch({ 
        changes: { from, to, insert: textToInsert }, 
        selection: { anchor: from + textToInsert.length } 
    });
    
    view.focus();
}


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
    get: () => {
        return memories.value
            .filter(m => loadedMemoryTitles.value.has(m.title))
            .map(m => `--- Memory: ${m.title} ---\n${m.content}\n--- End Memory: ${m.title} ---`)
            .join('\n\n');
    },
    set: (newVal) => {
        if (activeDiscussion.value) {
            discussionsStore.activeDiscussion.memory = newVal;
        }
    }
});

// Token Management
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
const formatTokens = (tokens) => tokens > 1000 ? `${(tokens/1000).toFixed(1)}K` : tokens.toString();


// Helper Functions
function getFileType(filename) {
    const ext = filename.split('.').pop()?.toLowerCase();
    const typeMap = {
        'pdf': { icon: 'pdf', color: 'text-red-500' },
        'txt': { icon: 'txt', color: 'text-gray-500' },
        'md': { icon: 'md', color: 'text-blue-500' },
        'docx': { icon: 'doc', color: 'text-blue-600' },
        'json': { icon: 'json', color: 'text-yellow-600' }
    };
    return typeMap[ext] || { icon: 'file', color: 'text-gray-500' };
}

function getContextParts() {
    const parts = [];
    if (discussionDataZoneTokens.value > 0) {
        parts.push({ 
            label: 'Discussion', 
            value: discussionDataZoneTokens.value, 
            colorClass: 'bg-blue-500 text-white',
            tooltip: `Discussion Data: ${formatNumber(discussionDataZoneTokens.value)} tokens`
        });
    }
    if (userDataZoneTokens.value > 0) {
        parts.push({ 
            label: 'User', 
            value: userDataZoneTokens.value, 
            colorClass: 'bg-green-500 text-white',
            tooltip: `User Data: ${formatNumber(userDataZoneTokens.value)} tokens`
        });
    }
    if (personalityDataZoneTokens.value > 0) {
        parts.push({ 
            label: 'Personality', 
            value: personalityDataZoneTokens.value, 
            colorClass: 'bg-purple-500 text-white',
            tooltip: `Personality Data: ${formatNumber(personalityDataZoneTokens.value)} tokens`
        });
    }
    if (memoryDataZoneTokens.value > 0) {
        parts.push({ 
            label: 'Memory', 
            value: memoryDataZoneTokens.value, 
            colorClass: 'bg-yellow-500 text-white',
            tooltip: `Memory Data: ${formatNumber(memoryDataZoneTokens.value)} tokens`
        });
    }
    return parts;
}

// Event Handlers
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
// Initialize history system
function setupHistory(historyRef, indexRef, initialValue) {
    historyRef.value = [initialValue];
    indexRef.value = 0;
}

// Record changes in history with debounce
function recordHistory(historyRef, indexRef, debounceTimer, content) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        if (historyRef.value[indexRef.value] === content) return;
        if (indexRef.value < historyRef.value.length - 1) {
            historyRef.value.splice(indexRef.value + 1);
        }
        historyRef.value.push(content);
        indexRef.value++;
    }, 750);
    return debounceTimer;
}

// Undo/Redo functions for Discussion
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

// Undo/Redo functions for User
async function handleUndoUser() {
    if (!canUndoUser.value) return;
    isProgrammaticChange.value = true;
    userHistoryIndex.value--;
    userDataZone.value = userHistory.value[userHistoryIndex.value];
    await nextTick();
    isProgrammaticChange.value = false;
}

async function handleRedoUser() {
    if (!canRedoUser.value) return;
    isProgrammaticChange.value = true;
    userHistoryIndex.value++;
    userDataZone.value = userHistory.value[userHistoryIndex.value];
    await nextTick();
    isProgrammaticChange.value = false;
}


function handleDragOver(event) {
    event.preventDefault();
    isDraggingFile.value = true;
}

function handleDragLeave(event) {
    event.preventDefault();
    if (!event.currentTarget.contains(event.relatedTarget)) {
        isDraggingFile.value = false;
    }
}

async function handleDrop(event, target) {
    event.preventDefault();
    isDraggingFile.value = false;
    const files = Array.from(event.dataTransfer.files);
    if (!files.length) return;

    if (target === 'artefact') {
        handleArtefactFileUpload({ target: { files } });
    } else if (target === 'memory') {
        handleArtefactFileUpload({ target: { files } });
        uiStore.addNotification('File added as an artefact. You can now create a memory from its content.', 'info', 6000);
    }
}



// Memory Management
function handleCreateMemory() {
    uiStore.openModal('memoryEditor');
}

function handleEditMemory(memory) {
    uiStore.openModal('memoryEditor', { memory });
}

async function handleDeleteMemory(memoryId) {
    const memoryToDelete = memories.value.find(m => m.id === memoryId);
    if (!memoryToDelete) return;

    const confirmed = await uiStore.showConfirmation({
        title: `Delete Memory '${memoryToDelete.title}'?`,
        message: 'This will permanently delete this memory from your memory bank.',
        confirmText: 'Delete'
    });
    
    if (confirmed) {
        try {
            await memoriesStore.deleteMemory(memoryId);
            uiStore.addNotification('Memory deleted successfully', 'success');
        } catch (error) {
            uiStore.addNotification('Failed to delete memory', 'error');
            console.error('Delete error:', error);
        }
    }
}

function handleLoadMemory(memoryTitle) {
    loadedMemoryTitles.value.add(memoryTitle);
    uiStore.addNotification(`Memory "${memoryTitle}" loaded to context`, 'success');
}

function handleUnloadMemory(memoryTitle) {
    loadedMemoryTitles.value.delete(memoryTitle);
    uiStore.addNotification(`Memory "${memoryTitle}" removed from context`, 'info');
}

// --- Artefact Management ---
async function handleRefreshArtefacts() {
    if (activeDiscussion.value?.id) {
        await discussionsStore.fetchArtefacts(activeDiscussion.value.id);
    }
}

async function handleLoadArtefactToPrompt(title, version) {
    if (!activeDiscussion.value) return;
    const artefact = await discussionsStore.fetchArtefactContent({
        discussionId: activeDiscussion.value.id,
        artefactTitle: title,
        version: version,
    });
    if (artefact && artefact.content) {
        const currentContent = dataZonePromptText.value;
        dataZonePromptText.value = currentContent ? `${currentContent}\n\n${artefact.content}` : artefact.content;
        promptLoadedArtefacts.value.add(title);
        uiStore.addNotification(`'${title}' loaded to prompt.`, 'success');
    }
}

function handleUnloadArtefactFromPrompt(title) {
    promptLoadedArtefacts.value.delete(title);
    dataZonePromptText.value = ''; // Clear prompt on unload for simplicity
    uiStore.addNotification(`'${title}' unloaded from prompt.`, 'info');
}

function handleCreateArtefact() {
    if (!activeDiscussion.value) return;
    uiStore.openModal('artefactEditor', { discussionId: activeDiscussion.value.id });
}

function triggerArtefactFileUpload() {
    artefactFileInput.value?.click();
}

async function handleArtefactFileUpload(event) {
    const files = Array.from(event.target.files || []);
    if (!files || files.length === 0 || !activeDiscussion.value) return;
    
    isUploadingArtefact.value = true;
    try {
        await Promise.all(files.map(file => discussionsStore.addArtefact({
            discussionId: activeDiscussion.value.id,
            file: file,
        })));
        uiStore.addNotification(`${files.length} file(s) uploaded successfully`, 'success');
    } catch (error) {
        uiStore.addNotification('Failed to upload files', 'error');
        console.error('Upload error:', error);
    } finally {
        isUploadingArtefact.value = false;
        if (artefactFileInput.value) {
            artefactFileInput.value.value = '';
        }
    }
}

async function handleImportArtefactFromUrl() {
    if (!urlToImport.value.trim() || !activeDiscussion.value) return;
    
    try {
        await discussionsStore.importArtefactFromUrl({
            discussionId: activeDiscussion.value.id,
            url: urlToImport.value
        });
        urlToImport.value = '';
        showUrlImport.value = false;
        uiStore.addNotification('URL imported successfully', 'success');
    } catch (error) {
        uiStore.addNotification('Failed to import URL', 'error');
        console.error('Import error:', error);
    }
}

// Auto-resize for Data Zone prompt textarea
function autoResizeDataZonePrompt() {
    const textarea = dataZonePromptTextareaRef.value;
    if (textarea) {
        textarea.style.height = 'auto';
        const maxHeight = 120; // max height of 120px
        textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
    }
}


// Watchers
watch(discussionDataZone, (newVal) => { 
    tokenizeContent(newVal, 'discussion');
    if (!isProgrammaticChange.value) {
        discussionHistoryDebounceTimer = recordHistory(discussionHistory, discussionHistoryIndex, discussionHistoryDebounceTimer, newVal);
    }
});

watch(userDataZone, (newVal) => { 
    tokenizeContent(newVal, 'user');
    if (!isProgrammaticChange.value) {
        userHistoryDebounceTimer = recordHistory(userHistory, userHistoryIndex, userHistoryDebounceTimer, newVal);
    }
});

watch(memory, (newVal) => {
    if (activeDiscussion.value) {
        activeDiscussion.value.lollmsDiscussion?.set_memory(newVal);
    }
    tokenizeContent(newVal, 'memory');
}, { immediate: true });

watch(activeDiscussion, (newDiscussion, oldDiscussion) => {
    if (newDiscussion) {
        if (!oldDiscussion || newDiscussion.id !== oldDiscussion.id) {
            setupHistory(discussionHistory, discussionHistoryIndex, newDiscussion.discussion_data_zone || '');
            loadedMemoryTitles.value.clear();
        }
        tokenizeContent(discussionDataZone.value, 'discussion');
        tokenizeContent(userDataZone.value, 'user');
        tokenizeContent(personalityDataZone.value, 'personality');
        tokenizeContent(memory.value, 'memory');
    }
}, { immediate: true, deep: true });

watch(dataZonePromptText, () => {
    nextTick(autoResizeDataZonePrompt);
});


// Lifecycle
onMounted(() => {
    promptsStore.fetchPrompts(); // FIXED: Fetch prompts on mount
    const savedWidth = localStorage.getItem('lollms_dataZoneWidth');
    if (savedWidth) dataZoneWidth.value = parseInt(savedWidth, 10);
    const savedArtefactWidth = localStorage.getItem('lollms_artefactListWidth');
    if (savedArtefactWidth) artefactListWidth.value = parseInt(savedArtefactWidth, 10);
    setupHistory(userHistory, userHistoryIndex, userDataZone.value);
    memoriesStore.fetchMemories();
    on('discussion:dataZoneUpdated', onDataZoneUpdatedFromStore);
    nextTick(autoResizeDataZonePrompt);
});

onUnmounted(() => {
    off('discussion:dataZoneUpdated', onDataZoneUpdatedFromStore);
});

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

// Add this function in your <script setup> block
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
function startResize(event) {
    isResizing.value = true;
    const startX = event.clientX;
    const startWidth = dataZoneWidth.value;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    
    function handleResize(e) {
        if (!isResizing.value) return;
        const dx = e.clientX - startX;
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
    
    window.addEventListener('mousemove', handleResize);
    window.addEventListener('mouseup', stopResize);
}
function startArtefactResize(event) {
    isResizingArtefacts.value = true;
    const startX = event.clientX;
    const startWidth = artefactListWidth.value;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    
    function handleArtefactResize(e) {
        if (!isResizingArtefacts.value) return;
        const dx = e.clientX - startX;
        const newWidth = startWidth - dx; // Dragging left increases width
        const minWidth = 200;
        const maxWidth = dataZoneWidth.value * 0.75; // Max 75% of parent
        artefactListWidth.value = Math.max(minWidth, Math.min(newWidth, maxWidth));
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

function handleProcessContent() {
    if (!activeDiscussion.value) return;
    const finalPrompt = dataZonePromptText.value.replace('{{data_zone}}', discussionDataZone.value);
    discussionsStore.summarizeDiscussionDataZone(activeDiscussion.value.id, finalPrompt);
}

function openPromptLibrary() {
    router.push({ path: '/settings', query: { tab: 'prompts' } });
}
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

async function handleDeleteAllImages() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Delete All Images?',
        message: 'This will remove all images from this discussion\'s context. This action cannot be undone.',
        confirmText: 'Delete All'
    });
    if (confirmed) {
        discussionsStore.deleteAllDiscussionImages();
    }
}

function handleGenerateImage() {
    if (!activeDiscussion.value) return;
    let prompt = dataZonePromptText.value.trim();
    if (!prompt) {
        prompt = discussionDataZone.value.trim();
    }
    if (!prompt) {
        uiStore.addNotification('Please provide a prompt in the Discussion Data Zone or the prompt text area to generate an image.', 'warning');
        return;
    }
    discussionsStore.generateImageFromDataZone(activeDiscussion.value.id, prompt);
}
function toggleViewMode(zone) {
    dataZoneViewModes.value[zone] = dataZoneViewModes.value[zone] === 'edit' ? 'view' : 'edit';
}

function handleCloneDiscussion() {
    if (activeDiscussion.value) {
        discussionsStore.cloneDiscussion(activeDiscussion.value.id, true); // Assuming second paramater is for cloning artefacts
        uiStore.addNotification('Discussion and artefacts cloned successfully', 'success');
    }
}

function openContextToArtefactModal() {
    if (!activeDiscussion.value) return;
    uiStore.openModal('contextToArtefact', {
        discussionId: activeDiscussion.value.id,
        artefacts: Object.values(activeDiscussionArtefacts.value.reduce((acc, art) => {
            if (!acc[art.title]) {
                acc[art.title] = { title: art.title };
            }
            return acc;
        }, {}))
    });
}

// Helper function to check if image is active
function isImageActive(index) {
    return !discussionActiveImages.value || 
           discussionActiveImages.value.length <= index || 
           discussionActiveImages.value[index];
}

function applyMarkdown(before, after = '', placeholder = 'text') {
    const view = discussionCodeMirrorEditor.value?.editorView;
    if (!view) return;
    const { from, to } = view.state.selection.main;
    const selectedText = view.state.doc.sliceString(from, to);
    let textToInsert, selStart, selEnd;

    if (selectedText) {
        textToInsert = `${before}${selectedText}${after}`;
        selStart = from;
        selEnd = to + before.length + after.length;
    } else {
        textToInsert = `${before}${placeholder}${after}`;
        selStart = from + before.length;
        selEnd = selStart + placeholder.length;
    }

    view.dispatch({
        changes: { from, to, insert: textToInsert },
        selection: { anchor: selStart, head: selEnd }
    });
    view.focus();
}

async function handleLoadAllArtefacts() {
    if (!activeDiscussion.value) return;
    
    const unloadedArtefacts = groupedArtefacts.value.filter(group => !group.isAnyVersionLoaded);
    if (unloadedArtefacts.length === 0 && groupedArtefacts.value.length > 0) {
        uiStore.addNotification('All artefacts are already loaded.', 'info');
        return;
    }
    if (groupedArtefacts.value.length === 0) {
        uiStore.addNotification('There are no artefacts to load.', 'info');
        return;
    }

    const confirmed = await uiStore.showConfirmation({
        title: 'Load All Artefacts?',
        message: `This will clear the current Discussion Data Zone and load the latest version of all ${groupedArtefacts.value.length} artefact(s) into it.`,
        confirmText: 'Load All'
    });

    if (confirmed) {
        discussionsStore.loadAllArtefactsToContext(activeDiscussion.value.id);
    }
}

// --- NEW/UPDATED Memory Functions ---
async function handleWipeAllMemories() {
    try {
        const confirmed = await uiStore.showConfirmation({
            title: 'Wipe All Memories?',
            message: 'This will clear all loaded memories from the current context, but will not delete them from your memory bank.',
            confirmText: 'Wipe Context'
        });
        if (confirmed) {
            loadedMemoryTitles.value.clear();
            uiStore.addNotification('All memories unloaded from context.', 'success');
        }
    } catch (error) {
        console.error("An error occurred while wiping memories:", error);
        uiStore.addNotification("Failed to wipe memories. Please check the console for details.", "error");
    }
}
</script>

<template>
    <div class="flex-1 flex flex-col h-full bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 overflow-hidden">
        <input type="file" ref="artefactFileInput" @change="handleArtefactFileUpload" multiple class="hidden">
        <input type="file" ref="discussionImageInput" @change="handleDiscussionImageUpload" class="hidden" accept="image/*,application/pdf" multiple>
        
        <div class="flex-1 flex min-h-0">
            <!-- Main Content: Chat Area -->
            <div class="flex-1 flex flex-col min-w-0 relative" :class="{'hidden': isDataZoneExpanded}">
                <MessageArea class="flex-1 overflow-y-auto min-w-0" />
                <ChatInput />
            </div>

            <!-- Resizer -->
            <div v-if="isDataZoneVisible && !isDataZoneExpanded" 
                 @mousedown.prevent="startResize" 
                 class="flex-shrink-0 w-2 cursor-col-resize bg-gradient-to-b from-gray-300 to-gray-400 dark:from-gray-600 dark:to-gray-700 hover:from-blue-400 hover:to-blue-500 transition-all duration-200 relative group">
                <div class="absolute inset-0 flex items-center justify-center">
                    <div class="w-0.5 h-8 bg-white/50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"></div>
                </div>
            </div>

            <!-- Data Zone Wrapper (NO TRANSITION) -->
            <div v-if="isDataZoneVisible && activeDiscussion"
                 class="relative h-full"
                 :class="[isDataZoneExpanded ? 'w-full' : 'flex-shrink-0']"
                 :style="isDataZoneExpanded ? {} : { width: `${dataZoneWidth}px` }">
                
                <!-- Enhanced Data Zone Sidebar -->
                <aside 
                   class="h-full flex flex-col bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-xl">
                    
                    <!-- Tab Navigation -->
                    <div class="flex-shrink-0 bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
                        <div class="flex items-center justify-between px-2">
                            <nav class="flex space-x-1" aria-label="Data Zone Tabs">
                                <button v-for="tab in dataTabs" :key="tab.id" @click="activeDataZoneTab = tab.id"
                                        :class="[
                                            'flex items-center gap-2 px-3 py-2.5 text-sm font-medium rounded-t-md border-b-2',
                                            activeDataZoneTab === tab.id ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-white dark:bg-gray-800' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                                        ]">
                                    <component :is="tab.icon" class="w-4 h-4" />
                                    <span>{{ tab.label }}</span>
                                    <span v-if="tab.tokenCount > 0" class="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-600 text-xs rounded-full font-mono">{{ formatTokens(tab.tokenCount) }}</span>
                                </button>
                            </nav>
                            <button @click="uiStore.toggleDataZoneExpansion()" class="action-btn" :title="isDataZoneExpanded ? 'Shrink' : 'Expand'">
                                <IconMinimize v-if="isDataZoneExpanded" class="w-5 h-5" />
                                <IconMaximize v-else class="w-5 h-5" />
                            </button>
                        </div>
                    </div>

                    <!-- Discussion Data Zone Tab -->
                    <div v-show="activeDataZoneTab === 'discussion'" class="flex-1 flex flex-col min-h-0">
                        <!-- Main content container -->
                        <div class="flex-grow flex flex-col min-h-0">
                             <!-- Top Bar (Context + Actions) -->
                            <div class="flex-shrink-0 px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-4">
                                <div class="flex items-center gap-2">
                                    <span class="text-sm font-medium text-gray-600 dark:text-gray-300">Context</span>
                                    <div class="w-48 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                        <div class="h-full bg-blue-500 rounded-full" :style="{ width: `${getPercentage(discussionDataZoneTokens)}%` }"></div>
                                    </div>
                                    <span class="text-xs font-mono text-gray-500 dark:text-gray-400">{{ formatNumber(discussionDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                                </div>
                                <div class="flex items-center gap-1">
                                    <button @click="handleCloneDiscussion" class="action-btn-sm" title="Clone Discussion & Artefacts"><IconCopy class="w-4 h-4" /></button>
                                    <button @click="openContextToArtefactModal" class="action-btn-sm" title="Save as Artefact"><IconSave class="w-4 h-4" /></button>
                                    <div class="w-px h-5 bg-gray-200 dark:bg-gray-600 mx-1"></div>
                                    <button @click="handleUndoDiscussion" class="action-btn-sm" title="Undo" :disabled="!canUndoDiscussion"><IconUndo class="w-4 h-4" /></button>
                                    <button @click="handleRedoDiscussion" class="action-btn-sm" title="Redo" :disabled="!canRedoDiscussion"><IconRedo class="w-4 h-4" /></button>
                                    <button @click="refreshDataZones" class="action-btn-sm" title="Refresh Data"><IconRefresh class="w-4 h-4" /></button>
                                    <button @click="discussionDataZone = ''" class="action-btn-sm-danger" title="Clear All Text"><IconTrash class="w-4 h-4" /></button>
                                </div>
                            </div>

                            <div class="flex-grow flex min-h-0">
                                <!-- Left side (Editor) -->
                                <div class="flex-grow flex flex-col min-h-0 p-2">
                                    <div class="flex-grow min-h-0 border dark:border-gray-700 rounded-md overflow-hidden">
                                        <CodeMirrorEditor ref="discussionCodeMirrorEditor" v-model="discussionDataZone" class="h-full" :options="discussionEditorOptions" />
                                    </div>
                                </div>
                                <!-- Artefacts/Images resizer -->
                                <div 
                                    @mousedown.prevent="startArtefactResize" 
                                    class="flex-shrink-0 w-2 cursor-col-resize bg-gradient-to-b from-gray-200 to-gray-300 dark:from-gray-700 dark:to-gray-600 hover:from-blue-400 hover:to-blue-500 transition-all duration-200 relative group">
                                    <div class="absolute inset-0 flex items-center justify-center">
                                        <div class="w-0.5 h-8 bg-white/50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"></div>
                                    </div>
                                </div>
                                <!-- Right side (Panels) -->
                                <div :style="{ width: `${artefactListWidth}px` }" class="flex-shrink-0 border-l border-gray-200 dark:border-gray-700 flex flex-col h-full">
                                    <!-- Images -->
                                    <div class="p-2 border-b dark:border-gray-700 flex flex-col">
                                        <div class="flex justify-between items-center mb-2 flex-shrink-0">
                                            <button @click="isImagesCollapsed = !isImagesCollapsed" class="flex items-center gap-2 text-sm font-semibold w-full text-left">
                                                <IconPhoto class="w-4 h-4" /> 
                                                <span>Images</span>
                                                <IconChevronRight class="w-4 h-4 ml-auto transition-transform" :class="{'rotate-90': !isImagesCollapsed}"/>
                                            </button>
                                            <div @click.stop class="flex items-center gap-1">
                                                <button @click="handleDeleteAllImages" class="action-btn-sm-danger" title="Delete All Images" :disabled="discussionImages.length === 0">
                                                    <IconTrash class="w-4 h-4" />
                                                </button>
                                                <button @click="triggerDiscussionImageUpload" class="action-btn-sm" title="Add Image(s)" :disabled="isUploadingDiscussionImage">
                                                    <IconAnimateSpin v-if="isUploadingDiscussionImage" class="w-4 h-4 animate-spin" /><IconPlus v-else class="w-4 h-4" />
                                                </button>
                                            </div>
                                        </div>
                                        <transition enter-active-class="transition-all ease-out duration-300" enter-from-class="max-h-0 opacity-0" enter-to-class="max-h-screen opacity-100" leave-active-class="transition-all ease-in duration-200" leave-from-class="max-h-screen opacity-100" leave-to-class="max-h-0 opacity-0">
                                            <div v-if="!isImagesCollapsed" class="overflow-y-auto custom-scrollbar min-h-0">
                                                <div v-if="discussionImages.length === 0 && !isUploadingDiscussionImage" class="text-center py-4 text-xs text-gray-500 bg-gray-50 dark:bg-gray-800/50 rounded">No images yet</div>
                                                <div v-else class="image-grid"><div v-for="(img_b64, index) in discussionImages" :key="img_b64.substring(0, 20) + index" class="image-card group"><img :src="'data:image/png;base64,' + img_b64" class="image-thumbnail" :class="{'grayscale opacity-50': !isImageActive(index)}" /><div class="image-overlay"><button @click="uiStore.openImageViewer('data:image/png;base64,' + img_b64)" class="overlay-btn" title="View"><IconMaximize class="w-3 h-3" /></button><button @click="discussionsStore.toggleDiscussionImageActivation(index)" class="overlay-btn" :title="isImageActive(index) ? 'Deactivate' : 'Activate'"><IconEye v-if="isImageActive(index)" class="w-3 h-3" /><IconEyeOff v-else class="w-3 h-3" /></button><button @click="discussionsStore.deleteDiscussionImage(index)" class="overlay-btn overlay-btn-danger" title="Delete"><IconXMark class="w-3 h-3" /></button></div></div></div>
                                            </div>
                                        </transition>
                                    </div>
                                    <!-- Artefacts -->
                                    <div class="p-2 flex flex-col min-h-0 flex-grow">
                                        <div class="flex justify-between items-center mb-2 flex-shrink-0">
                                            <button @click="isArtefactsCollapsed = !isArtefactsCollapsed" class="flex items-center gap-2 text-sm font-semibold w-full text-left">
                                                <IconFileText class="w-4 h-4" /> 
                                                <span>Artefacts</span>
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
                                        <transition enter-active-class="transition-all ease-out duration-300" enter-from-class="max-h-0 opacity-0" enter-to-class="max-h-screen opacity-100" leave-active-class="transition-all ease-in duration-200" leave-from-class="max-h-screen opacity-100" leave-to-class="max-h-0 opacity-0">
                                            <div v-if="!isArtefactsCollapsed" class="flex-grow flex flex-col min-h-0">
                                                <transition enter-active-class="transition ease-out duration-200" enter-from-class="transform opacity-0 -translate-y-2" enter-to-class="transform opacity-100 translate-y-0" leave-active-class="transition ease-in duration-150" leave-from-class="transform opacity-100 translate-y-0" leave-to-class="transform opacity-0 -translate-y-2">
                                                    <div v-if="showUrlImport" class="mb-2 p-2 bg-gray-50 dark:bg-gray-800/50 rounded-md border dark:border-gray-700">
                                                        <div class="flex items-center gap-2">
                                                            <input v-model="urlToImport" type="text" placeholder="https://..." class="input-field-sm flex-grow" @keydown.enter.prevent="handleImportArtefactFromUrl">
                                                            <button @click="handleImportArtefactFromUrl" class="btn btn-secondary btn-sm" :disabled="!urlToImport.trim() || isProcessing">
                                                                <IconAnimateSpin v-if="isProcessing" class="w-4 h-4 animate-spin" />
                                                                <span v-else>Import</span>
                                                            </button>
                                                        </div>
                                                    </div>
                                                </transition>
                                                <div class="flex-grow min-h-0 overflow-y-auto custom-scrollbar">
                                                    <div v-if="isLoadingArtefacts" key="artefacts-loading" class="loading-state"><IconAnimateSpin class="w-6 h-6 text-gray-400 animate-spin mx-auto mb-2" /><p class="text-xs text-gray-500">Loading...</p></div>
                                                    <div v-else-if="groupedArtefacts.length === 0" key="artefacts-empty" class="flex flex-col items-center justify-center h-full text-center p-4 bg-gray-50 dark:bg-gray-800/50 rounded">
                                                        <IconFileText class="w-10 h-10 text-gray-400 mb-2" />
                                                        <p class="text-xs text-gray-500 mb-3">No artefacts yet</p>
                                                        <button @click="triggerArtefactFileUpload" class="btn btn-secondary btn-sm"><IconPlus class="w-3 h-3 mr-1" />Add Artefact</button>
                                                    </div>
                                                    <div v-else key="artefacts-list" class="artefacts-list space-y-2">
                                                        <Suspense>
                                                            <ArtefactCard 
                                                                v-for="group in groupedArtefacts" 
                                                                :key="group.title"
                                                                :artefact-group="group"
                                                                :is-loaded-to-prompt="promptLoadedArtefacts.has(group.title)"
                                                                @load-to-prompt="handleLoadArtefactToPrompt"
                                                                @unload-from-prompt="handleUnloadArtefactFromPrompt"
                                                            />
                                                            <template #fallback>
                                                                <div class="text-center text-sm text-gray-500">Loading artefacts...</div>
                                                            </template>
                                                        </Suspense>
                                                    </div>
                                                </div>
                                            </div>
                                        </transition>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Bottom Action Bar -->
                        <div class="flex-shrink-0 p-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                            <div class="relative flex items-center">
                                <DropdownMenu title="Prompts" icon="ticket" collection="ui" button-class="btn-icon absolute left-1.5 top-1/2 -translate-y-1/2 z-10">
                                    <DropdownSubmenu v-if="filteredLollmsPrompts.length > 0" title="Default" icon="lollms" collection="ui"> <button v-for="p in filteredLollmsPrompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm"><span class="truncate">{{ p.name }}</span></button> </DropdownSubmenu>
                                    <DropdownSubmenu v-if="Object.keys(filteredUserPromptsByCategory).length > 0" title="User" icon="user" collection="ui"> <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10"><input type="text" v-model="userPromptSearchTerm" @click.stop placeholder="Search user prompts..." class="input-field w-full text-sm"></div> <div class="max-h-60 overflow-y-auto"> <div v-for="(prompts, category) in filteredUserPromptsByCategory" :key="category"> <h3 class="category-header">{{ category }}</h3> <button v-for="p in prompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm"><img v-if="p.icon" :src="p.icon" class="h-5 w-5 rounded-md object-cover mr-2 flex-shrink-0" alt="Icon"><span class="truncate">{{ p.name }}</span></button> </div> </div> </DropdownSubmenu>
                                    <DropdownSubmenu v-if="Object.keys(filteredSystemPromptsByZooCategory).length > 0" title="Zoo" icon="server" collection="ui"> <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10"><input type="text" v-model="zooPromptSearchTerm" @click.stop placeholder="Search zoo..." class="input-field w-full text-sm"></div> <div class="max-h-60 overflow-y-auto"> <div v-for="(prompts, category) in filteredSystemPromptsByZooCategory" :key="category"> <h3 class="category-header">{{ category }}</h3> <button v-for="p in prompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm"><img v-if="p.icon" :src="p.icon" class="h-5 w-5 rounded-md object-cover mr-2 flex-shrink-0" alt="Icon"><span class="truncate">{{ p.name }}</span></button> </div> </div> </DropdownSubmenu>
                                    <div v-if="(filteredLollmsPrompts.length + Object.keys(filteredUserPromptsByCategory).length + Object.keys(filteredSystemPromptsByZooCategory).length) > 0" class="my-1 border-t dark:border-gray-600"></div>
                                    <button @click="openPromptLibrary" class="menu-item text-sm font-medium text-blue-600 dark:text-blue-400">Manage My Prompts...</button>
                                </DropdownMenu>
                                <textarea ref="dataZonePromptTextareaRef" v-model="dataZonePromptText" @input="autoResizeDataZonePrompt" placeholder="Enter a prompt to process content..." class="enhanced-textarea !pl-10 !pr-40 w-full" :disabled="isGeneratingOrProcessing" style="max-height: 120px;"></textarea>
                                <div class="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-2">
                                    <button v-if="isTtiConfigured" @click="handleGenerateImage" class="btn btn-primary w-28" :disabled="isProcessing || (!discussionDataZone.trim() && !dataZonePromptText.trim())">
                                        <IconAnimateSpin v-if="isProcessing" class="w-4 h-4 mr-1.5" />
                                        <IconPhoto v-else class="w-4 h-4 mr-1.5" />
                                        <span>{{ isProcessing ? 'Generating...' : 'Generate' }}</span>
                                    </button>
                                    <button @click="handleProcessContent" class="btn btn-secondary w-28" :disabled="isProcessing || (!discussionDataZone.trim() && discussionImages.length === 0 && !dataZonePromptText.trim())">
                                        <IconAnimateSpin v-if="isProcessing" class="w-4 h-4 mr-1.5" />
                                        <IconSparkles v-else class="w-4 h-4 mr-1.5" />
                                        <span>{{ isProcessing ? 'Processing...' : 'Process' }}</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div v-show="activeDataZoneTab === 'user'" class="flex-1 flex flex-col min-h-0">
                        <div class="flex-shrink-0 px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-4">
                            <div class="flex items-center gap-2 flex-grow">
                                <span class="text-sm font-medium text-gray-600 dark:text-gray-300">User Context</span>
                                <div class="w-48 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                    <div class="h-full bg-green-500 rounded-full" :style="{ width: `${getPercentage(userDataZoneTokens)}%` }"></div>
                                </div>
                                <span class="text-xs font-mono text-gray-500 dark:text-gray-400">{{ formatNumber(userDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                            </div>
                            <div class="flex items-center gap-1">
                                <button @click="toggleViewMode('user')" class="action-btn-sm" :title="dataZoneViewModes.user === 'edit' ? 'Switch to Preview' : 'Switch to Edit'"><IconEye v-if="dataZoneViewModes.user === 'edit'" class="w-4 h-4" /><IconPencil v-else class="w-4 h-4" /></button>
                                <DropdownMenu title="Insert Placeholder" icon="ticket" collection="ui" button-class="action-btn-sm">
                                    <div class="max-h-60 overflow-y-auto">
                                        <button v-for="keyword in keywords" :key="keyword.keyword" @click="insertPlaceholder(keyword.keyword)" class="w-full text-left p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 text-sm">
                                            <div class="font-mono font-semibold">{{ keyword.keyword }}</div>
                                            <div class="text-xs text-gray-500">{{ keyword.description }}</div>
                                        </button>
                                    </div>
                                </DropdownMenu>
                                <button @click="handleUndoUser" class="action-btn-sm" title="Undo" :disabled="!canUndoUser"><IconUndo class="w-4 h-4" /></button>
                                <button @click="handleRedoUser" class="action-btn-sm" title="Redo" :disabled="!canRedoUser"><IconRedo class="w-4 h-4" /></button>
                            </div>
                        </div>
                        <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor v-if="dataZoneViewModes.user === 'edit'" ref="userCodeMirrorEditor" v-model="userDataZone" class="h-full border dark:border-gray-700 rounded-md" :options="{ readOnly: isGeneratingOrProcessing }"/><div v-else class="rendered-prose-container h-full p-2 border dark:border-gray-700 rounded-md"><MessageContentRenderer :content="userDataZone" /></div></div>
                    </div>
                    
                    <div v-show="activeDataZoneTab === 'personality'" class="flex-1 flex flex-col min-h-0">
                        <div class="flex-shrink-0 px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-4">
                             <div class="flex items-center gap-2 flex-grow">
                                <span class="text-sm font-medium text-gray-600 dark:text-gray-300">Personality Context</span>
                                <div class="w-48 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                    <div class="h-full bg-purple-500 rounded-full" :style="{ width: `${getPercentage(personalityDataZoneTokens)}%` }"></div>
                                </div>
                                <span class="text-xs font-mono text-gray-500 dark:text-gray-400">{{ formatNumber(personalityDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                            </div>
                            <button @click="toggleViewMode('personality')" class="action-btn-sm" title="Toggle View"><IconPencil class="w-4 h-4" /></button>
                        </div>
                        <div class="flex-grow min-h-0 p-2"><div class="rendered-prose-container h-full p-2 border dark:border-gray-700 rounded-md"><MessageContentRenderer :content="personalityDataZone" /></div></div>
                    </div>
                    
                    <!-- Memory Tab -->
                    <div v-show="activeDataZoneTab === 'ltm'" class="flex-1 flex flex-col min-h-0">
                        <div class="flex-shrink-0 px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-4">
                            <div class="flex items-center gap-2 flex-grow">
                                <span class="text-sm font-medium text-gray-600 dark:text-gray-300">Memory Context</span>
                                <div class="w-48 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                    <div class="h-full bg-yellow-500 rounded-full" :style="{ width: `${getPercentage(memoryDataZoneTokens)}%` }"></div>
                                </div>
                                <span class="text-xs font-mono text-gray-500 dark:text-gray-400">{{ formatNumber(memoryDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                            </div>
                            <button @click="handleMemorize" class="btn btn-secondary btn-sm" title="Memorize Current Discussion"><IconSparkles class="w-4 h-4 mr-1.5" :class="{'animate-pulse': isMemorizing}"/>Memorize</button>
                        </div>

                        <div class="flex-grow min-h-0 flex">
                            <!-- Memory Context Display -->
                            <div class="flex-grow flex flex-col min-w-0 p-2">
                                <div class="flex-grow min-h-0 border dark:border-gray-700 rounded-md overflow-hidden">
                                   <div class="rendered-prose-container h-full p-2"><MessageContentRenderer :content="memory" /></div>
                                </div>
                            </div>

                            <!-- Memory Bank Sidebar -->
                            <div class="w-64 flex-shrink-0 border-l border-gray-200 dark:border-gray-700 flex flex-col p-2">
                                <div class="sidebar-section">
                                    <div class="section-header">
                                        <h4 class="section-title"><IconThinking class="w-4 h-4" /> Memory Bank</h4>
                                        <div class="section-actions">
                                            <button @click="handleWipeAllMemories" class="action-btn-sm-danger" title="Unload all memories"><IconTrash class="w-4 h-4" /></button>
                                            <button @click="handleCreateMemory" class="action-btn-sm" title="Create New Memory"><IconPlus class="w-4 h-4" /></button>
                                        </div>
                                    </div>
                                    <div class="px-1 pb-2">
                                        <input type="text" v-model="memorySearchTerm" placeholder="Search memories..." class="w-full px-2 py-1.5 text-xs bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-md focus:ring-1 focus:ring-yellow-500 focus:border-yellow-500" />
                                    </div>
                                    <div class="section-content flex-grow min-h-0 overflow-y-auto">
                                        <div v-if="isLoadingMemories" class="loading-state"><IconAnimateSpin class="w-6 h-6 text-gray-400 animate-spin mx-auto mb-2" /><p class="text-xs text-gray-500">Loading...</p></div>
                                        <div v-else-if="filteredMemories.length === 0" class="empty-state"><IconThinking class="w-8 h-8 text-gray-400 mx-auto mb-2" /><p class="text-xs text-gray-500 mb-3">No memories</p></div>
                                        <div v-else class="memories-list space-y-2">
                                            <div v-for="mem in filteredMemories" :key="mem.id" class="memory-card">
                                                <div class="memory-header"><div class="memory-info"><div class="memory-icon" :class="{ 'loaded': loadedMemoryTitles.has(mem.title) }"><IconThinking class="w-4 h-4" /></div><div class="memory-details"><h5 class="memory-title" :title="mem.title">{{ mem.title }}</h5></div></div><div class="memory-actions"><button @click="handleEditMemory(mem)" class="memory-action-btn" title="Edit Memory"><IconPencil class="w-3 h-3" /></button><button @click="handleDeleteMemory(mem.id)" class="memory-action-btn memory-action-btn-danger" title="Delete Memory"><IconTrash class="w-3 h-3" /></button></div></div>
                                                <div class="memory-controls"><button v-if="loadedMemoryTitles.has(mem.title)" @click="handleUnloadMemory(mem.title)" class="memory-load-btn loaded" title="Remove from Context"><IconCheckCircle class="w-3 h-3" />In Context</button><button v-else @click="handleLoadMemory(mem.title)" class="memory-load-btn" title="Add to Context"><IconPlus class="w-3 h-3" />Add to Context</button></div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </aside>

                <!-- Generation Overlay -->
                <div v-if="isGeneratingOrProcessing" class="absolute inset-0 bg-white/75 dark:bg-gray-800/75 backdrop-blur-sm z-50 flex flex-col items-center justify-center">
                    <IconAnimateSpin class="w-10 h-10 text-blue-500 animate-spin" />
                    <p class="mt-4 text-sm font-semibold text-gray-700 dark:text-gray-200">Generating...</p>
                </div>

            </div>
        </div>
    </div>
</template>