<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
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
const { liveDataZoneTokens, currentModelVisionSupport, activeDiscussionArtefacts, isLoadingArtefacts } = storeToRefs(discussionsStore);
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
const selectedArtefactVersions = ref({});
const isDraggingFile = ref(false);
const memorySearchTerm = ref('');
const loadedMemoryTitles = ref(new Set());

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

const isMemorizing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'memorize');

const discussionEditorOptions = computed(() => ({ readOnly: isProcessing.value }));

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
                isAnyVersionLoaded: false,
                fileType: getFileType(artefact.title)
            };
        }
        acc[artefact.title].versions.push(artefact);
        if (artefact.is_loaded) {
            acc[artefact.title].isAnyVersionLoaded = true;
        }
        return acc;
    }, {});

    Object.values(groups).forEach(group => {
        group.versions.sort((a, b) => b.version - a.version);
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

// Artefact Management
async function handleLoadArtefact(title) {
    if (!activeDiscussion.value) return;
    
    try {
        const version = selectedArtefactVersions.value[title];
        await discussionsStore.loadArtefactToContext({ 
            discussionId: activeDiscussion.value.id, 
            artefactTitle: title, 
            version: version 
        });
        uiStore.addNotification(`Artefact "${title}" loaded to context`, 'success');
    } catch (error) {
        uiStore.addNotification('Failed to load artefact', 'error');
        console.error('Load error:', error);
    }
}

async function handleUnloadArtefact(title, version) {
    if (!activeDiscussion.value) return;
    
    try {
        await discussionsStore.unloadArtefactFromContext({ 
            discussionId: activeDiscussion.value.id, 
            artefactTitle: title, 
            version: version 
        });
        uiStore.addNotification(`Artefact "${title}" removed from context`, 'info');
    } catch (error) {
        uiStore.addNotification('Failed to unload artefact', 'error');
        console.error('Unload error:', error);
    }
}

async function handleEditArtefact(title) {
    if (!activeDiscussion.value) return;
    
    try {
        const version = selectedArtefactVersions.value[title];
        const artefact = await discussionsStore.fetchArtefactContent({
            discussionId: activeDiscussion.value.id,
            artefactTitle: title,
            version: version
        });
        
        if (artefact) {
            uiStore.openModal('artefactEditor', { artefact, discussionId: activeDiscussion.value.id });
        }
    } catch (error) {
        uiStore.addNotification('Failed to fetch artefact', 'error');
        console.error('Fetch error:', error);
    }
}

async function handleDeleteArtefact(title) {
    if (!activeDiscussion.value) return;
    
    try {
        const confirmed = await uiStore.showConfirmation({ 
            title: `Delete Artefact '${title}'?`, 
            message: 'This will permanently delete the artefact and all its versions.', 
            confirmText: 'Delete' 
        });
        
        if (confirmed) {
            await discussionsStore.deleteArtefact({ 
                discussionId: activeDiscussion.value.id, 
                artefactTitle: title 
            });
            uiStore.addNotification('Artefact deleted successfully', 'success');
        }
    } catch (error) {
        uiStore.addNotification('Failed to delete artefact', 'error');
        console.error('Delete error:', error);
    }
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

watch(groupedArtefacts, (newGroups) => {
    const newSelections = { ...selectedArtefactVersions.value };
    for (const group of newGroups) {
        const loadedVersion = group.versions.find(v => v.is_loaded);
        if (loadedVersion) {
            newSelections[group.title] = loadedVersion.version;
        } else if (group.versions.length > 0) {
            newSelections[group.title] = group.versions[0].version;
        }
    }
    selectedArtefactVersions.value = newSelections;
}, { deep: true, immediate: true });

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

// Lifecycle
onMounted(() => {
    const savedWidth = localStorage.getItem('lollms_dataZoneWidth');
    if (savedWidth) dataZoneWidth.value = parseInt(savedWidth, 10);
    setupHistory(userHistory, userHistoryIndex, userDataZone.value);
    memoriesStore.fetchMemories();
    on('discussion:dataZoneUpdated', onDataZoneUpdatedFromStore);
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

function handleCloneDiscussionContext() {
    if (activeDiscussion.value) {
        discussionsStore.cloneDiscussion(activeDiscussion.value.id);
        uiStore.addNotification('Discussion context cloned successfully', 'success');
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

            <!-- Enhanced Data Zone Sidebar -->
            <transition 
                enter-active-class="transition ease-out duration-300" 
                enter-from-class="transform translate-x-full opacity-0" 
                enter-to-class="transform translate-x-0 opacity-100" 
                leave-active-class="transition ease-in duration-300" 
                leave-from-class="transform translate-x-0 opacity-100" 
                leave-to-class="transform translate-x-full opacity-0">
                <aside v-if="isDataZoneVisible && activeDiscussion" 
                       :class="[isDataZoneExpanded ? 'w-full' : 'flex-shrink-0']" 
                       :style="isDataZoneExpanded ? {} : { width: `${dataZoneWidth}px` }" 
                       class="h-full flex flex-col bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-xl">
                    
                    <!-- Enhanced Tab Navigation -->
                    <div class="flex-shrink-0 bg-gradient-to-r from-gray-50 via-white to-gray-50 dark:from-gray-800 dark:via-gray-750 dark:to-gray-800 border-b border-gray-200 dark:border-gray-700">
                        <nav class="flex space-x-1 px-4 py-2" aria-label="Data Zone Tabs">
                            <button v-for="tab in dataTabs" 
                                    :key="tab.id"
                                    @click="activeDataZoneTab = tab.id"
                                    :class="[
                                        'enhanced-tab-btn relative overflow-hidden transition-all duration-300',
                                        activeDataZoneTab === tab.id 
                                            ? 'active bg-white dark:bg-gray-800 shadow-lg border-t-2 border-blue-500 text-blue-600 dark:text-blue-400' 
                                            : 'hover:bg-white/70 dark:hover:bg-gray-700/50 text-gray-600 dark:text-gray-400'
                                    ]"
                                    :title="tab.description">
                                <div class="flex items-center gap-2 relative z-10 px-3 py-2">
                                    <component :is="tab.icon" class="w-4 h-4 flex-shrink-0" />
                                    <span class="font-medium text-sm">{{ tab.label }}</span>
                                    <div v-if="tab.tokenCount > 0" 
                                         class="token-badge px-1.5 py-0.5 bg-gray-200 dark:bg-gray-600 text-xs rounded-full font-mono">
                                        {{ formatTokens(tab.tokenCount) }}
                                    </div>
                                </div>
                                <!-- Active indicator -->
                                <div v-if="activeDataZoneTab === tab.id" 
                                     class="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-400 to-blue-600 rounded-t">
                                </div>
                            </button>
                        </nav>
                    </div>

                    <!-- Discussion Data Zone Tab -->
                    <div v-show="activeDataZoneTab === 'discussion'" class="flex-1 flex flex-col min-h-0 relative">
                        <!-- Processing Overlay -->
                        <div v-if="isProcessing" class="absolute inset-0 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm z-20 flex flex-col items-center justify-center">
                            <div class="processing-spinner">
                                <IconAnimateSpin class="w-12 h-12 text-blue-500 animate-spin" />
                            </div>
                            <p class="mt-4 font-semibold text-lg text-gray-800 dark:text-gray-100">Processing...</p>
                            <p class="text-sm text-gray-600 dark:text-gray-400">This may take a moment</p>
                        </div>

                        <!-- Enhanced Header -->
                        <div class="enhanced-header">
                            <div class="flex justify-between items-center mb-3">
                                <h3 class="header-title">
                                    <IconDataZone class="w-5 h-5 text-blue-600 dark:text-blue-400" />
                                    <span class="bg-gradient-to-r from-blue-600 to-indigo-600 dark:from-blue-400 dark:to-indigo-400 bg-clip-text text-transparent">
                                        Discussion Data
                                    </span>
                                </h3>
                                <div class="action-buttons-group">
                                    <button @click="uiStore.toggleDataZoneExpansion()" class="action-btn" :title="isDataZoneExpanded ? 'Shrink' : 'Expand'">
                                        <IconMinimize v-if="isDataZoneExpanded" class="w-5 h-5" />
                                        <IconMaximize v-else class="w-5 h-5" />
                                    </button>
                                    <button @click="refreshDataZones" class="action-btn" title="Refresh Data">
                                        <IconRefresh class="w-5 h-5" />
                                    </button>
                                    <button @click="exportDataZone" class="action-btn" title="Export to Markdown">
                                        <IconArrowUpTray class="w-5 h-5" />
                                    </button>
                                    <button @click="discussionDataZone = ''" class="action-btn-danger" title="Clear All Text">
                                        <IconTrash class="w-5 h-5" />
                                    </button>
                                </div>
                            </div>
                            
                            <!-- Enhanced Token Progress -->
                            <div class="token-progress-container">
                                <div class="flex justify-between items-center text-xs text-gray-600 dark:text-gray-400 font-mono mb-2">
                                    <div class="flex items-center gap-2">
                                        <IconToken class="w-4 h-4 text-blue-500" />
                                        <span class="font-semibold">Context Usage</span>
                                    </div>
                                    <span class="font-bold">{{ formatNumber(discussionDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                                </div>
                                
                                <div class="progress-bar-container">
                                    <div class="progress-bar-track">
                                        <div class="progress-bar-fill"
                                             :class="getProgressColorClass(getPercentage(discussionDataZoneTokens))"
                                             :style="{ width: `${Math.min(getPercentage(discussionDataZoneTokens), 100)}%` }">
                                            <div class="progress-bar-shine"></div>
                                        </div>
                                        <!-- Warning indicator -->
                                        <div v-if="getPercentage(discussionDataZoneTokens) > 90" 
                                             class="absolute right-2 top-1/2 transform -translate-y-1/2">
                                            <div class="w-2 h-2 bg-red-500 rounded-full animate-ping"></div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Context breakdown -->
                                <div class="flex flex-wrap gap-1.5 mt-2">
                                    <span v-for="part in getContextParts()" 
                                          :key="part.label" 
                                          class="context-chip"
                                          :class="part.colorClass"
                                          :title="part.tooltip">
                                        {{ part.label }}: {{ formatNumber(part.value) }}
                                    </span>
                                </div>
                            </div>
                        </div>

                        <!-- Content Area -->
                        <div class="flex-grow min-h-0 flex" :onpaste="handlePasteInDataZone">
                            <div class="flex-grow flex flex-col min-w-0">
                                <!-- Content Header -->
                                <div class="content-header">
                                    <h4 class="content-title">Content</h4>
                                    <div class="content-actions">
                                        <button @click="handleCloneDiscussionContext" class="action-btn-sm" title="Clone Discussion Context">
                                            <IconCopy class="w-4 h-4" />
                                        </button>
                                        <button @click="openContextToArtefactModal" class="action-btn-sm" title="Save Context as Artefact">
                                            <IconArrowDownTray class="w-4 h-4" />
                                        </button>
                                        <button @click="toggleViewMode('discussion')" class="action-btn-sm" 
                                                :title="dataZoneViewModes.discussion === 'edit' ? 'Switch to Preview' : 'Switch to Edit'">
                                            <IconEye v-if="dataZoneViewModes.discussion === 'edit'" class="w-4 h-4" />
                                            <IconPencil v-else class="w-4 h-4" />
                                        </button>
                                        <button @click="handleUndoDiscussion" class="action-btn-sm" title="Undo" :disabled="!canUndoDiscussion">
                                            <IconUndo class="w-4 h-4" />
                                        </button>
                                        <button @click="handleRedoDiscussion" class="action-btn-sm" title="Redo" :disabled="!canRedoDiscussion">
                                            <IconRedo class="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                                
                                <!-- Editor/Preview Area -->
                                <div class="flex-grow min-h-0 p-3 bg-gray-50 dark:bg-gray-900/50">
                                    <div class="h-full rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-gray-800">
                                        <CodeMirrorEditor v-if="dataZoneViewModes.discussion === 'edit'" 
                                                        ref="discussionCodeMirrorEditor" 
                                                        v-model="discussionDataZone" 
                                                        class="h-full" 
                                                        :options="discussionEditorOptions" />
                                        <div v-else class="rendered-prose-container h-full p-4 overflow-y-auto">
                                            <MessageContentRenderer :content="discussionDataZone" />
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Enhanced Action Bar -->
                                <div class="action-bar">
                                    <div class="flex items-center gap-3">
                                        <DropdownMenu title="Prompts" icon="ticket" collection="ui" button-class="btn-secondary btn-sm !p-2">
                                            <DropdownSubmenu v-if="filteredLollmsPrompts.length > 0" title="Default" icon="lollms" collection="ui">
                                                <button v-for="p in filteredLollmsPrompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm"><span class="truncate">{{ p.name }}</span></button>
                                            </DropdownSubmenu>
                                            <DropdownSubmenu v-if="Object.keys(userPromptsByCategory).length > 0" title="User" icon="user" collection="ui">
                                                <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10"><input type="text" v-model="userPromptSearchTerm" @click.stop placeholder="Search user prompts..." class="input-field w-full text-sm"></div>
                                                <div class="max-h-60 overflow-y-auto">
                                                    <div v-for="(prompts, category) in filteredUserPromptsByCategory" :key="category">
                                                        <h3 class="category-header">{{ category }}</h3>
                                                        <button v-for="p in prompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm"><img v-if="p.icon" :src="p.icon" class="h-5 w-5 rounded-md object-cover mr-2 flex-shrink-0" alt="Icon"><span class="truncate">{{ p.name }}</span></button>
                                                    </div>
                                                </div>
                                            </DropdownSubmenu>
                                            <DropdownSubmenu v-if="Object.keys(systemPromptsByZooCategory).length > 0" title="Zoo" icon="server" collection="ui">
                                                <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10"><input type="text" v-model="zooPromptSearchTerm" @click.stop placeholder="Search zoo..." class="input-field w-full text-sm"></div>
                                                <div class="max-h-60 overflow-y-auto">
                                                    <div v-for="(prompts, category) in filteredSystemPromptsByZooCategory" :key="category">
                                                        <h3 class="category-header">{{ category }}</h3>
                                                        <button v-for="p in prompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm"><img v-if="p.icon" :src="p.icon" class="h-5 w-5 rounded-md object-cover mr-2 flex-shrink-0" alt="Icon"><span class="truncate">{{ p.name }}</span></button>
                                                    </div>
                                                </div>
                                            </DropdownSubmenu>
                                            <div v-if="(lollmsPrompts.length + Object.keys(userPromptsByCategory).length + Object.keys(systemPromptsByZooCategory).length) > 0" class="my-1 border-t dark:border-gray-600"></div>
                                            <button @click="openPromptLibrary" class="menu-item text-sm font-medium text-blue-600 dark:text-blue-400">Manage My Prompts...</button>
                                        </DropdownMenu>
                                        <textarea v-model="dataZonePromptText" 
                                                placeholder="Enter a prompt to process the data zone content..." 
                                                rows="2" 
                                                class="enhanced-textarea"></textarea>
                                    </div>
                                    <div class="flex items-center gap-3 mt-3">
                                        <button v-if="isTtiConfigured" 
                                                @click="handleGenerateImage" 
                                                class="enhanced-primary-btn" 
                                                :disabled="isProcessing || (!discussionDataZone.trim() && !dataZonePromptText.trim())">
                                            <IconPhoto class="w-5 h-5" />
                                            <span>{{ isProcessing ? 'Processing...' : 'Generate Image' }}</span>
                                        </button>
                                        <button @click="handleProcessContent" 
                                                class="enhanced-secondary-btn" 
                                                :disabled="isProcessing || (!discussionDataZone.trim() && discussionImages.length === 0 && !dataZonePromptText.trim())">
                                            <IconSparkles class="w-5 h-5" />
                                            <span>{{ isProcessing ? 'Processing...' : 'Process Content' }}</span>
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <!-- Enhanced Sidebar -->
                            <div class="sidebar-panel">
                                <!-- Images Section -->
                                <div class="sidebar-section">
                                    <div class="section-header">
                                        <h4 class="section-title">
                                            <IconPhoto class="w-4 h-4" />
                                            Images
                                        </h4>
                                        <button @click="triggerDiscussionImageUpload" 
                                                class="action-btn-sm" 
                                                title="Add Image(s) or PDF" 
                                                :disabled="isUploadingDiscussionImage">
                                            <IconAnimateSpin v-if="isUploadingDiscussionImage" class="w-4 h-4 animate-spin" />
                                            <IconPhoto v-else class="w-4 h-4" />
                                        </button>
                                    </div>
                                    
                                    <div class="section-content">
                                        <div v-if="discussionImages.length === 0 && !isUploadingDiscussionImage" class="empty-state">
                                            <IconPhoto class="w-8 h-8 text-gray-400 mx-auto mb-2" />
                                            <p class="text-xs text-gray-500">No images yet</p>
                                        </div>
                                            <div v-else class="image-grid">
                                                <div v-for="(img_b64, index) in discussionImages" 
                                                    :key="img_b64.substring(0, 20) + index" 
                                                    class="image-card group">  <!-- Add group class here -->
                                                    <img :src="'data:image/png;base64,' + img_b64" 
                                                        class="image-thumbnail" 
                                                        :class="{'grayscale opacity-50': !isImageActive(index)}" />
                                                    <div class="image-overlay">
                                                        <button @click="uiStore.openImageViewer('data:image/png;base64,' + img_b64)" 
                                                                class="overlay-btn" title="View">
                                                            <IconMaximize class="w-3 h-3" />
                                                        </button>
                                                        <button @click="discussionsStore.toggleDiscussionImageActivation(index)" 
                                                                class="overlay-btn" 
                                                                :title="isImageActive(index) ? 'Deactivate' : 'Activate'">
                                                            <IconEye v-if="isImageActive(index)" class="w-3 h-3" />
                                                            <IconEyeOff v-else class="w-3 h-3" />
                                                        </button>
                                                        <button @click="discussionsStore.deleteDiscussionImage(index)" 
                                                                class="overlay-btn overlay-btn-danger" title="Delete">
                                                            <IconXMark class="w-3 h-3" />
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>

                                    </div>
                                </div>

                                <!-- Enhanced Artefacts Section -->
                                <div class="sidebar-section">
                                    <div class="section-header">
                                        <h4 class="section-title">
                                            <IconFileText class="w-4 h-4" />
                                            Artefacts
                                        </h4>
                                        <div class="section-actions">
                                            <button @click="handleCreateArtefact" class="action-btn-sm" title="Create Artefact">
                                                <IconPlus class="w-4 h-4" />
                                            </button>
                                            <button @click="showUrlImport = !showUrlImport" class="action-btn-sm" title="Import from URL">
                                                <IconWeb class="w-4 h-4" />
                                            </button>
                                            <button @click="triggerArtefactFileUpload" class="action-btn-sm" title="Upload Artefact" :disabled="isUploadingArtefact">
                                                <IconAnimateSpin v-if="isUploadingArtefact" class="w-4 h-4 animate-spin" />
                                                <IconArrowUpTray v-else class="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>
                                    
                                    <div class="section-content enhanced-drop-zone" 
                                         @dragover="handleDragOver"
                                         @dragleave="handleDragLeave" 
                                         @drop="handleDrop($event, 'artefact')"
                                         :class="{ 'drop-active': isDraggingFile }">
                                        
                                        <!-- URL Import -->
                                        <div v-if="showUrlImport" class="url-import-section">
                                            <label class="url-import-label">Import from URL</label>
                                            <div class="url-import-controls">
                                                <input v-model="urlToImport" type="url" placeholder="https://example.com" class="url-input">
                                                <button @click="handleImportArtefactFromUrl" 
                                                        class="fetch-btn" 
                                                        :disabled="isProcessing || !urlToImport">
                                                    <IconAnimateSpin v-if="isProcessing" class="w-4 h-4 animate-spin" />
                                                    <span v-else>Fetch</span>
                                                </button>
                                            </div>
                                        </div>

                                        <!-- Drop Overlay -->
                                        <div v-if="isDraggingFile" class="drop-overlay">
                                            <div class="drop-indicator">
                                                <IconArrowUpTray class="w-8 h-8 text-blue-500 animate-bounce mb-2" />
                                                <p class="text-sm font-semibold text-blue-600 dark:text-blue-400">Drop files here</p>
                                                <p class="text-xs text-gray-500 mt-1">Supports PDF, images, text files</p>
                                            </div>
                                        </div>

                                        <!-- Loading State -->
                                        <div v-if="isLoadingArtefacts" class="loading-state">
                                            <IconAnimateSpin class="w-6 h-6 text-gray-400 animate-spin mx-auto mb-2" />
                                            <p class="text-xs text-gray-500">Loading artefacts...</p>
                                        </div>

                                        <!-- Empty State -->
                                        <div v-else-if="groupedArtefacts.length === 0 && !isDraggingFile" class="empty-state">
                                            <IconFileText class="w-8 h-8 text-gray-400 mx-auto mb-2" />
                                            <p class="text-xs text-gray-500 mb-3">No artefacts yet</p>
                                            <button @click="triggerArtefactFileUpload" class="empty-state-btn">
                                                <IconPlus class="w-3 h-3 mr-1" />
                                                Add Artefact
                                            </button>
                                        </div>
                                        
                                        <!-- Artefact Cards -->
                                        <div v-else class="artefacts-list">
                                            <div v-for="group in groupedArtefacts" :key="group.title" class="artefact-card group">
                                                <div class="artefact-header">
                                                    <div class="artefact-info">
                                                        <div class="artefact-icon" :class="group.isAnyVersionLoaded ? 'loaded' : ''">
                                                            <IconFileText class="w-4 h-4" />
                                                        </div>
                                                        <div class="artefact-details">
                                                            <h5 class="artefact-title" :title="group.title">{{ group.title }}</h5>
                                                            <p class="artefact-meta">
                                                                {{ group.versions.length }} version{{ group.versions.length !== 1 ? 's' : '' }}
                                                                <span v-if="group.isAnyVersionLoaded" class="loaded-indicator">• Loaded</span>
                                                            </p>
                                                        </div>
                                                    </div>
                                                    <!-- ADD THESE MISSING ACTION BUTTONS -->
                                                    <div class="artefact-actions">
                                                        <button @click="handleEditArtefact(group.title)" class="artefact-action-btn" title="Edit Content">
                                                            <IconPencil class="w-3 h-3" />
                                                        </button>
                                                        <button @click="handleDeleteArtefact(group.title)" class="artefact-action-btn artefact-action-btn-danger" title="Delete Artefact">
                                                            <IconTrash class="w-3 h-3" />
                                                        </button>
                                                    </div>
                                                </div>
                                                
                                                <div class="artefact-controls">
                                                    <select v-model="selectedArtefactVersions[group.title]" class="version-select">
                                                        <option v-for="artefact in group.versions" :key="artefact.version" :value="artefact.version">
                                                            Version {{ artefact.version }}{{ artefact.is_loaded ? ' (Active)' : '' }}
                                                        </option>
                                                    </select>
                                                    
                                                    <button v-if="group.versions.find(v => v.version == selectedArtefactVersions[group.title])?.is_loaded"
                                                            @click="handleUnloadArtefact(group.title, selectedArtefactVersions[group.title])" 
                                                            class="load-btn loaded" title="Unload from Context">
                                                        <IconCheckCircle class="w-3 h-3" />
                                                        Loaded
                                                    </button>
                                                    <button v-else
                                                            @click="handleLoadArtefact(group.title)" 
                                                            class="load-btn" title="Load to Context">
                                                        <IconArrowDownTray class="w-3 h-3" />
                                                        Load
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div v-show="activeDataZoneTab === 'user'" class="flex-1 flex flex-col min-h-0">
                        <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                            <div class="flex justify-between items-center">
                                <div><h3 class="font-semibold flex items-center gap-2"><IconUserCircle class="w-5 h-5" /> User Data Zone</h3><p class="text-xs text-gray-500 mt-1">Context for all of your discussions.</p></div>
                                <div class="flex items-center gap-1"><button @click="toggleViewMode('user')" class="btn-icon" :title="dataZoneViewModes.user === 'edit' ? 'Switch to Preview' : 'Switch to Edit'"><IconEye v-if="dataZoneViewModes.user === 'edit'" class="w-5 h-5" /><IconPencil v-else class="w-5 h-5" /></button><DropdownMenu title="Insert Placeholder" icon="ticket" collection="ui" button-class="btn-icon"><button v-for="keyword in keywords" :key="keyword.keyword" @click="insertPlaceholder(keyword.keyword)" class="w-full text-left p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-sm"><div class="font-mono font-semibold">{{ keyword.keyword }}</div><div class="text-xs text-gray-500">{{ keyword.description }}</div></button></DropdownMenu><button @click="handleUndoUser" class="btn-icon" title="Undo" :disabled="!canUndoUser"><IconUndo class="w-5 h-5" /></button><button @click="handleRedoUser" class="btn-icon" title="Redo" :disabled="!canRedoUser"><IconRedo class="w-5 h-5" /></button></div>
                            </div>
                            <div class="mt-2"><div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 font-mono"><span>Tokens</span><span>{{ formatNumber(userDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span></div><div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1"><div class="h-1.5 rounded-full bg-green-500 transition-width duration-500" :style="{ width: `${getPercentage(userDataZoneTokens)}%` }"></div></div></div>
                        </div>
                        <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor v-if="dataZoneViewModes.user === 'edit'" ref="userCodeMirrorEditor" v-model="userDataZone" class="h-full" /><div v-else class="rendered-prose-container h-full"><MessageContentRenderer :content="userDataZone" /></div></div>
                    </div>
                    <div v-show="activeDataZoneTab === 'personality'" class="flex-1 flex flex-col min-h-0">
                        <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                             <div class="flex justify-between items-center"><div><h3 class="font-semibold flex items-center gap-2"><IconSparkles class="w-5 h-5" /> Personality Data Zone</h3><p class="text-xs text-gray-500 mt-1">Read-only context from the active personality.</p></div><button @click="toggleViewMode('personality')" class="btn-icon" :title="dataZoneViewModes.personality === 'edit' ? 'Switch to Preview' : 'Switch to Edit'"><IconEye v-if="dataZoneViewModes.personality === 'edit'" class="w-5 h-5" /><IconPencil v-else class="w-5 h-5" /></button></div>
                            <div class="mt-2"><div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 font-mono"><span>Tokens</span><span>{{ formatNumber(personalityDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span></div><div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1"><div class="h-1.5 rounded-full bg-purple-500 transition-width duration-500" :style="{ width: `${getPercentage(personalityDataZoneTokens)}%` }"></div></div></div>
                        </div>
                        <div class="flex-grow min-h-0 p-2"><CodeMirrorEditor v-if="dataZoneViewModes.personality === 'edit'" :model-value="personalityDataZone" class="h-full" :options="{ readOnly: true }" /><div v-else class="rendered-prose-container h-full"><MessageContentRenderer :content="personalityDataZone" /></div></div>
                    </div>
                    <!-- Memory Tab -->
                    <div v-show="activeDataZoneTab === 'ltm'" class="flex-1 flex flex-col min-h-0 relative">
                        <!-- Processing Overlay -->
                        <div v-if="isMemorizing" class="absolute inset-0 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm z-20 flex flex-col items-center justify-center">
                            <IconAnimateSpin class="w-12 h-12 text-yellow-500 animate-spin" />
                            <p class="mt-4 font-semibold text-lg text-gray-800 dark:text-gray-100">Memorizing...</p>
                            <p class="text-sm text-gray-600 dark:text-gray-400">Creating long-term memory</p>
                        </div>

                        <!-- Enhanced Memory Header -->
                        <div class="enhanced-header">
                            <div class="flex justify-between items-center mb-3">
                                <h3 class="header-title">
                                    <IconThinking class="w-5 h-5 text-yellow-600 dark:text-yellow-400" />
                                    <span class="bg-gradient-to-r from-yellow-600 to-orange-600 dark:from-yellow-400 dark:to-orange-400 bg-clip-text text-transparent">
                                        Long-Term Memory
                                    </span>
                                </h3>
                                <button @click="handleMemorize" class="memorize-btn" title="Memorize Current Discussion">
                                    <IconSparkles class="w-5 h-5" :class="{'animate-pulse': isMemorizing}"/>
                                    Memorize
                                </button>
                            </div>
                            
                            <!-- Memory Token Progress -->
                            <div class="token-progress-container">
                                <div class="flex justify-between items-center text-xs text-gray-600 dark:text-gray-400 font-mono mb-2">
                                    <div class="flex items-center gap-2">
                                        <IconToken class="w-4 h-4 text-yellow-500" />
                                        <span class="font-semibold">Memory Usage</span>
                                    </div>
                                    <span class="font-bold">{{ formatNumber(memoryDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span>
                                </div>
                                
                                <div class="progress-bar-container">
                                    <div class="progress-bar-track">
                                        <div class="progress-bar-fill bg-gradient-to-r from-yellow-400 to-orange-500"
                                             :style="{ width: `${Math.min(getPercentage(memoryDataZoneTokens), 100)}%` }">
                                            <div class="progress-bar-shine"></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="flex-grow min-h-0 flex">
                            <!-- Memory Context Display -->
                            <div class="flex-grow flex flex-col min-w-0">
                                <div class="content-header">
                                    <h4 class="content-title">Loaded Memory Context</h4>
                                    <button @click="toggleViewMode('ltm')" class="action-btn-sm" 
                                            :title="dataZoneViewModes.ltm === 'edit' ? 'Switch to Preview' : 'Switch to Edit'">
                                        <IconEye v-if="dataZoneViewModes.ltm === 'edit'" class="w-4 h-4" />
                                        <IconPencil v-else class="w-4 h-4" />
                                    </button>
                                </div>
                                
                                <div class="flex-grow min-h-0 p-3 bg-gray-50 dark:bg-gray-900/50">
                                    <div class="h-full rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-gray-800">
                                        <CodeMirrorEditor v-if="dataZoneViewModes.ltm === 'edit'" 
                                                        :model-value="memory" 
                                                        class="h-full" 
                                                        :options="{readOnly: true}" />
                                        <div v-else class="rendered-prose-container h-full p-4 overflow-y-auto">
                                            <MessageContentRenderer :content="memory" />
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- Memory Bank Sidebar -->
                            <div class="sidebar-panel">
                                <div class="sidebar-section">
                                    <div class="section-header">
                                        <h4 class="section-title">
                                            <IconThinking class="w-4 h-4" />
                                            Memory Bank
                                        </h4>
                                        <div class="section-actions">
                                            <button @click="handleWipeAllMemories" class="action-btn-sm action-btn-danger" title="Unload all memories">
                                                <IconTrash class="w-4 h-4" />
                                            </button>
                                            <button @click="handleCreateMemory" class="action-btn-sm" title="Create New Memory">
                                                <IconPlus class="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>
                                    
                                    <!-- Memory Search -->
                                    <div class="px-3 pb-3 border-b dark:border-gray-700">
                                        <input type="text" v-model="memorySearchTerm" placeholder="Search memories..." 
                                               class="w-full px-3 py-2 text-xs bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-md focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500" />
                                    </div>
                                    
                                    <!-- Memory List -->
                                    <div class="section-content enhanced-drop-zone"
                                         @dragover="handleDragOver"
                                         @dragleave="handleDragLeave" 
                                         @drop="handleDrop($event, 'memory')"
                                         :class="{ 'drop-active': isDraggingFile }">
                                        
                                        <!-- Loading State -->
                                        <div v-if="isLoadingMemories" class="loading-state">
                                            <IconAnimateSpin class="w-6 h-6 text-gray-400 animate-spin mx-auto mb-2" />
                                            <p class="text-xs text-gray-500">Loading memories...</p>
                                        </div>

                                        <!-- Empty State -->
                                        <div v-else-if="filteredMemories.length === 0" class="empty-state">
                                            <IconThinking class="w-8 h-8 text-gray-400 mx-auto mb-2" />
                                            <p class="text-xs text-gray-500 mb-3">No memories found</p>
                                            <button @click="handleCreateMemory" class="empty-state-btn">
                                                <IconPlus class="w-3 h-3 mr-1" />
                                                Create Memory
                                            </button>
                                        </div>
                                        
                                        <!-- Memory Cards -->
                                        <div v-else class="memories-list">
                                            <div v-for="mem in filteredMemories" :key="mem.id" class="memory-card">
                                                <div class="memory-header">
                                                    <div class="memory-info">
                                                        <div class="memory-icon" :class="{ 'loaded': loadedMemoryTitles.has(mem.title) }">
                                                            <IconThinking class="w-4 h-4" />
                                                        </div>
                                                        <div class="memory-details">
                                                            <h5 class="memory-title" :title="mem.title">{{ mem.title }}</h5>
                                                            <p class="memory-meta">{{ mem.content.length }} chars</p>
                                                        </div>
                                                    </div>
                                                    <div class="memory-actions">
                                                        <button @click="handleEditMemory(mem)" class="memory-action-btn" title="Edit Memory">
                                                            <IconPencil class="w-3 h-3" />
                                                        </button>
                                                        <button @click="handleDeleteMemory(mem.id)" class="memory-action-btn memory-action-btn-danger" title="Delete Memory">
                                                            <IconTrash class="w-3 h-3" />
                                                        </button>
                                                    </div>
                                                </div>
                                                
                                                <!-- Memory Preview -->
                                                <div class="memory-preview">
                                                    <p class="memory-content">{{ mem.content.substring(0, 100) }}{{ mem.content.length > 100 ? '...' : '' }}</p>
                                                </div>
                                                
                                                <div class="memory-controls">
                                                    <button v-if="loadedMemoryTitles.has(mem.title)"
                                                            @click="handleUnloadMemory(mem.title)" 
                                                            class="memory-load-btn loaded" title="Remove from Context">
                                                        <IconCheckCircle class="w-3 h-3" />
                                                        In Context
                                                    </button>
                                                    <button v-else
                                                            @click="handleLoadMemory(mem.title)" 
                                                            class="memory-load-btn" title="Add to Context">
                                                        <IconPlus class="w-3 h-3" />
                                                        Add to Context
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- User and Personality tabs remain similar but with enhanced styling -->
                    <!-- ... (implement similar enhancements for other tabs) -->
                </aside>
            </transition>
        </div>
    </div>
</template>

<style scoped>
/* Enhanced Tab Styling */
.custom-gray-750 {
    --tw-bg-opacity: 1;
    background-color: rgb(55 65 81 / var(--tw-bg-opacity)); /* Custom gray-750 equivalent */
}

.enhanced-header {
    @apply p-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-blue-50/50 to-indigo-50/50 dark:from-gray-800/50;
    /* Apply custom dark background if needed */
}

.enhanced-tab-btn:hover {
    @apply bg-gradient-to-b from-white/70 to-white/50 dark:from-gray-700/50 dark:to-gray-700/30;
}

.enhanced-tab-btn.active {
    @apply bg-white dark:bg-gray-800 shadow-lg border-t-2;
}

.token-badge {
    @apply px-2 py-1 bg-gradient-to-r from-blue-100 to-blue-200 dark:from-blue-900 dark:to-blue-800 text-blue-700 dark:text-blue-300 text-xs rounded-full font-mono font-medium;
}

/* Enhanced Headers */

.header-title {
    @apply font-semibold text-lg flex items-center gap-3;
}

.action-buttons-group {
    @apply flex items-center gap-1;
}

.action-btn {
    @apply p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-white dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-200 transition-all duration-200 hover:shadow-md;
}

.action-btn-danger {
    @apply p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-red-50 dark:hover:bg-red-900/30 hover:text-red-600 dark:hover:text-red-400 transition-all duration-200;
}

.action-btn-sm {
    @apply p-1.5 rounded-md text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-200 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed;
}

/* Token Progress Styling */
.token-progress-container {
    @apply mt-3;
}

.progress-bar-container {
    @apply relative;
}

.progress-bar-track {
    @apply w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 overflow-hidden shadow-inner relative;
}

.progress-bar-fill {
    @apply h-full rounded-full transition-all duration-700 ease-out bg-gradient-to-r relative overflow-hidden;
}

.progress-bar-shine {
    @apply absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-pulse;
}

.context-chip {
    @apply px-2 py-1 rounded-full text-xs font-medium;
}

/* Content Areas */
.content-header {
    @apply p-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex items-center justify-between;
}

.content-title {
    @apply font-semibold text-sm text-gray-800 dark:text-gray-100;
}

.content-actions {
    @apply flex items-center gap-1;
}

/* Action Bar */
.action-bar {
    @apply p-4 border-t border-gray-200 dark:border-gray-700 bg-gradient-to-t from-white via-white to-transparent dark:from-gray-800 dark:via-gray-800;
}

.enhanced-primary-btn {
    @apply px-4 py-2.5 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white font-medium rounded-lg shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-none flex items-center gap-2;
}

.enhanced-secondary-btn {
    @apply px-4 py-2.5 bg-gradient-to-r from-gray-100 to-gray-200 hover:from-gray-200 hover:to-gray-300 dark:from-gray-700 dark:to-gray-600 dark:hover:from-gray-600 dark:hover:to-gray-500 text-gray-700 dark:text-gray-200 font-medium rounded-lg shadow-md hover:shadow-lg transform hover:scale-105 transition-all duration-200 flex items-center gap-2;
}

.enhanced-textarea {
    @apply flex-1 p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm resize-none transition-all duration-200;
}

/* Sidebar Panels */
.sidebar-panel {
    @apply w-72 flex-shrink-0 border-l border-gray-200 dark:border-gray-700 flex flex-col bg-gray-50 dark:bg-gray-800/50;
}

.sidebar-section {
    @apply flex-1 flex flex-col min-h-0;
}

.section-header {
    @apply p-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between bg-white dark:bg-gray-800;
}

.section-title {
    @apply font-semibold text-sm flex items-center gap-2;
}

.section-actions {
    @apply flex items-center gap-1;
}

.section-content {
    @apply flex-1 overflow-y-auto p-3;
}

/* Drop Zone Styling */
.enhanced-drop-zone {
    @apply relative transition-all duration-300;
}

.enhanced-drop-zone.drop-active {
    @apply bg-blue-50 dark:bg-blue-900/20 border-2 border-dashed border-blue-400 rounded-lg;
}

.drop-overlay {
    @apply absolute inset-0 bg-blue-50/90 dark:bg-blue-900/30 backdrop-blur-sm flex items-center justify-center z-10 rounded-lg;
}

.drop-indicator {
    @apply text-center p-4;
}

/* Empty States */
.empty-state {
    @apply text-center py-8;
}

.empty-state-btn {
    @apply px-3 py-1.5 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-md text-xs font-medium hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors flex items-center justify-center mx-auto;
}

.loading-state {
    @apply text-center py-8;
}

/* Artefact Cards */
.artefacts-list {
    @apply space-y-3;
}

.artefact-card {
    @apply bg-white dark:bg-gray-800 rounded-lg shadow-sm hover:shadow-md transition-all duration-300 border border-gray-200 dark:border-gray-700 overflow-hidden;
}

.artefact-header {
    @apply p-3 flex items-center justify-between bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-700 dark:to-gray-600;
}

.artefact-info {
    @apply flex items-center gap-3 min-w-0 flex-1;
}

.artefact-icon {
    @apply w-8 h-8 rounded-lg flex items-center justify-center bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400;
}

.artefact-icon.loaded {
    @apply bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400;
}

.artefact-details {
    @apply min-w-0 flex-1;
}

.artefact-title {
    @apply font-semibold text-sm truncate text-gray-800 dark:text-gray-100;
}

.artefact-meta {
    @apply text-xs text-gray-500 dark:text-gray-400;
}

.loaded-indicator {
    @apply text-green-600 dark:text-green-400 font-medium;
}

.artefact-actions {
    @apply flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity;
}

.artefact-action-btn {
    @apply p-1.5 rounded-full hover:bg-white dark:hover:bg-gray-800 text-gray-500 hover:text-blue-600 transition-colors;
}

.artefact-action-btn-danger {
    @apply hover:bg-red-50 dark:hover:bg-red-900/30 hover:text-red-600;
}

.artefact-controls {
    @apply p-3 flex items-center gap-2 border-t border-gray-100 dark:border-gray-700;
}

.version-select {
    @apply flex-1 text-xs bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-md px-2 py-1.5 focus:ring-2 focus:ring-blue-500;
}

.load-btn {
    @apply px-3 py-1.5 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-md hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors flex items-center gap-1 font-medium;
}

.load-btn.loaded {
    @apply bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50;
}

/* Memory Cards */
.memories-list {
    @apply space-y-3;
}

.memory-card {
    @apply bg-white dark:bg-gray-800 rounded-lg shadow-sm hover:shadow-md transition-all duration-300 border-l-4 border-gray-300 dark:border-gray-600 overflow-hidden;
}

.memory-card:has(.memory-icon.loaded) {
    @apply border-l-yellow-500 bg-yellow-50 dark:bg-yellow-900/10;
}

.memory-header {
    @apply p-3 flex items-center justify-between;
}

.memory-info {
    @apply flex items-center gap-3 min-w-0 flex-1;
}

.memory-icon {
    @apply w-8 h-8 rounded-lg flex items-center justify-center bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400;
}

.memory-icon.loaded {
    @apply bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400;
}

.memory-details {
    @apply min-w-0 flex-1;
}

.memory-title {
    @apply font-semibold text-sm truncate text-gray-800 dark:text-gray-100;
}

.memory-meta {
    @apply text-xs text-gray-500 dark:text-gray-400;
}

.memory-actions {
    @apply flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity;
}

.memory-action-btn {
    @apply p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 hover:text-blue-600 transition-colors;
}

.memory-action-btn-danger {
    @apply hover:bg-red-50 dark:hover:bg-red-900/30 hover:text-red-600;
}

.memory-preview {
    @apply px-3 pb-2;
}

.memory-content {
    @apply text-xs text-gray-600 dark:text-gray-300 line-clamp-2;
}

.memory-controls {
    @apply p-3 border-t border-gray-100 dark:border-gray-700;
}

.memory-load-btn {
    @apply w-full px-3 py-1.5 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-md hover:bg-blue-200 dark:hover:bg-blue-900/50 transition-colors flex items-center gap-1 justify-center font-medium;
}

.memory-load-btn.loaded {
    @apply bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 hover:bg-yellow-200 dark:hover:bg-yellow-900/50;
}

.memorize-btn {
    @apply px-4 py-2 bg-gradient-to-r from-yellow-400 to-orange-500 hover:from-yellow-500 hover:to-orange-600 text-white font-medium rounded-lg shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 flex items-center gap-2;
}

/* Image Grid */
.image-grid {
    @apply grid grid-cols-2 gap-2;
}

.image-card {
    @apply relative rounded-lg overflow-hidden bg-gray-100 dark:bg-gray-700;
}


.image-thumbnail {
    @apply w-full h-16 object-cover transition-all duration-300;
}

/* This is the key fix - make overlay invisible by default and visible on hover */
.image-overlay {
    @apply absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center gap-1;
    /* Ensure it's above the image */
    z-index: 10;
}

/* Ensure buttons are visible and interactive */
.image-overlay button {
    @apply p-1 bg-white/20 text-white rounded-full hover:bg-white/40 transition-colors;
    /* Make sure buttons are clickable */
    pointer-events: auto;
}

/* Add specific styling for danger buttons */
.image-overlay .overlay-btn-danger {
    @apply bg-red-500/80 hover:bg-red-600;
}

.overlay-btn {
    @apply p-1 bg-white/20 text-white rounded-full hover:bg-white/40 transition-colors;
}

.overlay-btn-danger {
    @apply bg-red-500/80 hover:bg-red-600;
}

/* Animations */
.processing-spinner {
    @apply relative;
}

.processing-spinner::before {
    content: '';
    @apply absolute inset-0 rounded-full border-4 border-blue-200 dark:border-blue-800;
}

.processing-spinner::after {
    content: '';
    @apply absolute inset-0 rounded-full border-4 border-transparent border-t-blue-500 animate-spin;
}

/* Responsive adjustments */
@media (max-width: 768px) {
    .sidebar-panel {
        @apply w-64;
    }
    
    .enhanced-tab-btn {
        @apply px-2 py-2 text-xs;
    }
    
    .token-badge {
        @apply px-1 py-0.5 text-xs;
    }
}

/* Fix for Image Overlay Hover Effect */


</style>
