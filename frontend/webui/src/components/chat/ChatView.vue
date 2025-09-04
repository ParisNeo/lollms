<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { useDiscussionsStore } from '../../stores/discussions';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { usePromptsStore } from '../../stores/prompts';
import { useTasksStore } from '../../stores/tasks';
import { useMemoriesStore } from '../../stores/memories'; // NEW
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

// --- Store Initialization ---
const discussionsStore = useDiscussionsStore();
const authStore = useAuthStore();
const uiStore = useUiStore();
const promptsStore = usePromptsStore();
const tasksStore = useTasksStore();
const dataStore = useDataStore();
const memoriesStore = useMemoriesStore(); // NEW
const router = useRouter();
const { on, off } = useEventBus();
const { liveDataZoneTokens, currentModelVisionSupport, activeDiscussionArtefacts, isLoadingArtefacts } = storeToRefs(discussionsStore);
const { lollmsPrompts, systemPromptsByZooCategory, userPromptsByCategory } = storeToRefs(promptsStore);
const { tasks } = storeToRefs(tasksStore);
const { availableTtiModels } = storeToRefs(dataStore);
const { memories, isLoading: isLoadingMemories } = storeToRefs(memoriesStore); // NEW

// --- Component State ---
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
const memorySearchTerm = ref(''); // NEW
const loadedMemoryTitles = ref(new Set()); // NEW

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

const discussionEditorOptions = computed(() => {
    return { readOnly: isProcessing.value };
});

const keywords = computed(() => uiStore.keywords);
const canUndoDiscussion = computed(() => discussionHistoryIndex.value > 0);
const canRedoDiscussion = computed(() => discussionHistoryIndex.value < discussionHistory.value.length - 1);
const canUndoUser = computed(() => userHistoryIndex.value > 0);
const canRedoUser = computed(() => userHistoryIndex.value < userHistory.value.length - 1);
const canUndoMemory = computed(() => memoryHistoryIndex.value > 0);
const canRedoMemory = computed(() => memoryHistoryIndex.value < memoryHistory.value.length - 1);

const groupedArtefacts = computed(() => {
    if (!activeDiscussionArtefacts.value || !Array.isArray(activeDiscussionArtefacts.value)) return [];
    
    const groups = activeDiscussionArtefacts.value.reduce((acc, artefact) => {
        if (!acc[artefact.title]) {
            acc[artefact.title] = {
                title: artefact.title,
                versions: [],
                isAnyVersionLoaded: false
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

const filteredLollmsPrompts = computed(() => {
    if (!Array.isArray(lollmsPrompts.value)) return [];
    if (!userPromptSearchTerm.value) return lollmsPrompts.value;
    const term = userPromptSearchTerm.value.toLowerCase();
    return lollmsPrompts.value.filter(p => p.name.toLowerCase().includes(term));
});

const filteredUserPromptsByCategory = computed(() => {
    const term = userPromptSearchTerm.value.toLowerCase();
    const source = userPromptsByCategory.value;
    if (!source || typeof source !== 'object') return {};
    
    if (!term) return source;
    
    const filtered = {};
    for (const category in source) {
        const filteredPrompts = source[category].filter(p => p.name.toLowerCase().includes(term));
        if (filteredPrompts.length > 0) {
            filtered[category] = filteredPrompts;
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
        const filteredPrompts = source[category].filter(p => p.name.toLowerCase().includes(term));
        if (filteredPrompts.length > 0) {
            filtered[category] = filteredPrompts;
        }
    }
    return filtered;
});

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

const userDataZone = computed({
    get: () => authStore.user?.data_zone || '',
    set: (newVal) => {
        if (authStore.user) { authStore.user.data_zone = newVal; }
        clearTimeout(userSaveDebounceTimer);
        userSaveDebounceTimer = setTimeout(() => { authStore.updateDataZone(newVal); }, 750);
    }
});
const personalityDataZone = computed(() => activeDiscussion.value?.personality_data_zone || '');

const filteredMemories = computed(() => { // NEW
    if (!memorySearchTerm.value) return memories.value;
    const term = memorySearchTerm.value.toLowerCase();
    return memories.value.filter(m => 
        m.title.toLowerCase().includes(term) || 
        m.content.toLowerCase().includes(term)
    );
});

const memory = computed({
    get: () => {
        // Construct the memory string from loaded memories
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
            // Always default to the newest version, which is the first one after sorting.
            newSelections[group.title] = group.versions[0].version;
        }
    }
    selectedArtefactVersions.value = newSelections;
}, { deep: true, immediate: true });


onMounted(() => {
    const savedWidth = localStorage.getItem('lollms_dataZoneWidth');
    if (savedWidth) dataZoneWidth.value = parseInt(savedWidth, 10);
    setupHistory(userHistory, userHistoryIndex, userDataZone.value);
    memoriesStore.fetchMemories(); // NEW
    on('discussion:dataZoneUpdated', onDataZoneUpdatedFromStore);
});
onUnmounted(() => {
    window.removeEventListener('mousemove', handleResize);
    window.removeEventListener('mouseup', stopResize);
    off('discussion:dataZoneUpdated', onDataZoneUpdatedFromStore);
});

function onDataZoneUpdatedFromStore({ discussionId, newContent }) {
    if (activeDiscussion.value && activeDiscussion.value.id === discussionId) {
        updateDiscussionDataZoneAndRecordHistory(newContent);
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
        // For memory, we treat it as adding an artefact. The user can then create a memory from it.
        // This avoids needing a separate backend endpoint just for text extraction to memory.
        handleArtefactFileUpload({ target: { files } });
        uiStore.addNotification('File added as an artefact. You can now create a memory from its content.', 'info', 6000);
    }
}

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
function setupHistory(historyRef, indexRef, initialValue) { historyRef.value = [initialValue]; indexRef.value = 0; }

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

watch(activeDiscussion, (newDiscussion, oldDiscussion) => {
    if (newDiscussion) {
        if (!oldDiscussion || newDiscussion.id !== oldDiscussion.id) {
            setupHistory(discussionHistory, discussionHistoryIndex, newDiscussion.discussion_data_zone || '');
            // NEW: Reset loaded memories for the new discussion
            loadedMemoryTitles.value.clear();
        }
        tokenizeContent(discussionDataZone.value, 'discussion');
        tokenizeContent(userDataZone.value, 'user');
        tokenizeContent(personalityDataZone.value, 'personality');
        tokenizeContent(memory.value, 'memory');
    }
}, { immediate: true, deep: true });

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
function triggerArtefactFileUpload() { artefactFileInput.value?.click(); }

async function handleArtefactFileUpload(event) {
    const files = Array.from(event.target.files);
    if (!files || files.length === 0 || !activeDiscussion.value) return;
    isUploadingArtefact.value = true;
    try {
        await Promise.all(files.map(file => discussionsStore.addArtefact({
            discussionId: activeDiscussion.value.id,
            file: file,
        })));
    } finally {
        isUploadingArtefact.value = false;
        if (artefactFileInput.value) {
            artefactFileInput.value.value = '';
        }
    }
}

async function handleImportArtefactFromUrl() {
    if (!urlToImport.value.trim() || !activeDiscussion.value) return;
    await discussionsStore.importArtefactFromUrl({
        discussionId: activeDiscussion.value.id,
        url: urlToImport.value
    });
    urlToImport.value = '';
    showUrlImport.value = false;
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
    }
}
async function handleLoadArtefact(title) {
    if (activeDiscussion.value) {
        const version = selectedArtefactVersions.value[title];
        await discussionsStore.loadArtefactToContext({ discussionId: activeDiscussion.value.id, artefactTitle: title, version: version });
    }
}
async function handleUnloadArtefact(title, version) {
    if (activeDiscussion.value) {
        await discussionsStore.unloadArtefactFromContext({ discussionId: activeDiscussion.value.id, artefactTitle: title, version: version });
    }
}

async function handleEditArtefact(title) {
    if (activeDiscussion.value) {
        const version = selectedArtefactVersions.value[title];
        const artefact = await discussionsStore.fetchArtefactContent({
            discussionId: activeDiscussion.value.id,
            artefactTitle: title,
            version: version
        });
        console.log("Fetched artefact for editing:", artefact);
        if (artefact) {
            uiStore.openModal('artefactEditor', { artefact, discussionId: activeDiscussion.value.id });
        }
    }
}

async function handleDeleteArtefact(title) {
    if (activeDiscussion.value) {
        const confirmed = await uiStore.showConfirmation({ title: `Delete Artefact '${title}'?`, message: 'This will permanently delete the artefact and all its versions.', confirmText: 'Delete' });
        if (confirmed) {
            await discussionsStore.deleteArtefact({ discussionId: activeDiscussion.value.id, artefactTitle: title });
        }
    }
}

function handleCreateArtefact() {
    if (!activeDiscussion.value) return;
    uiStore.openModal('artefactEditor', { discussionId: activeDiscussion.value.id });
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

// --- NEW/UPDATED Memory Functions ---
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
        await memoriesStore.deleteMemory(memoryId);
    }
}

function handleLoadMemory(memoryTitle) {
    loadedMemoryTitles.value.add(memoryTitle);
}

function handleUnloadMemory(memoryTitle) {
    loadedMemoryTitles.value.delete(memoryTitle);
}

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
    <div class="flex-1 flex flex-col h-full bg-gray-50 dark:bg-gray-900 overflow-hidden">
        <input type="file" ref="artefactFileInput" @change="handleArtefactFileUpload" multiple class="hidden">
        <input type="file" ref="discussionImageInput" @change="handleDiscussionImageUpload" class="hidden" accept="image/*,application/pdf" multiple>
        
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
                    <div v-show="activeDataZoneTab === 'discussion'" class="flex-1 flex flex-col min-h-0 relative">
                        <div v-if="isProcessing" class="absolute inset-0 bg-gray-400/30 dark:bg-gray-900/50 z-10 flex flex-col items-center justify-center">
                            <IconAnimateSpin class="w-10 h-10 text-gray-800 dark:text-gray-100 animate-spin" />
                            <p class="mt-3 font-semibold text-gray-800 dark:text-gray-100">Processing...</p>
                        </div>
                        <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                            <div class="flex justify-between items-center"><h3 class="font-semibold flex items-center gap-2"><IconDataZone class="w-5 h-5" /> Discussion Data</h3>
                                <div class="flex items-center gap-1">
                                    <button @click="uiStore.toggleDataZoneExpansion()" class="btn-icon" :title="isDataZoneExpanded ? 'Shrink' : 'Expand'"><IconMinimize v-if="isDataZoneExpanded" class="w-5 h-5" /><IconMaximize v-else class="w-5 h-5" /></button>
                                    <button @click="refreshDataZones" class="btn-icon" title="Refresh Data"><IconRefresh class="w-5 h-5" /></button>
                                    <button @click="exportDataZone" class="btn-icon" title="Export to Markdown"><IconArrowUpTray class="w-5 h-5" /></button>
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

                        <div class="flex-grow min-h-0 flex" :onpaste="handlePasteInDataZone">
                            <div class="flex-grow flex flex-col min-w-0">
                                <div class="p-2 border-b dark:border-gray-600 flex-shrink-0 flex items-center justify-between">
                                    <h4 class="font-semibold text-sm">Content</h4>
                                    <div class="flex items-center gap-1">
                                        <button @click="handleCloneDiscussionContext" class="btn-icon" title="Clone Discussion Context"><IconCopy class="w-5 h-5" /></button>
                                        <button @click="openContextToArtefactModal" class="btn-icon" title="Save Context as Artefact"><IconArrowDownTray class="w-5 h-5" /></button>
                                        <button @click="toggleViewMode('discussion')" class="btn-icon" :title="dataZoneViewModes.discussion === 'edit' ? 'Switch to Preview' : 'Switch to Edit'"><IconEye v-if="dataZoneViewModes.discussion === 'edit'" class="w-5 h-5" /><IconPencil v-else class="w-5 h-5" /></button>
                                        <button @click="handleUndoDiscussion" class="btn-icon" title="Undo" :disabled="!canUndoDiscussion"><IconUndo class="w-5 h-5" /></button>
                                        <button @click="handleRedoDiscussion" class="btn-icon" title="Redo" :disabled="!canRedoDiscussion"><IconRedo class="w-5 h-5" /></button>
                                    </div>
                                </div>
                                <div class="flex-grow min-h-0 p-2">
                                    <CodeMirrorEditor v-if="dataZoneViewModes.discussion === 'edit'" ref="discussionCodeMirrorEditor" v-model="discussionDataZone" class="h-full" :options="discussionEditorOptions" />
                                    <div v-else class="rendered-prose-container h-full"><MessageContentRenderer :content="discussionDataZone" /></div>
                                </div>
                                <div class="p-4 border-t dark:border-gray-600 flex-shrink-0 space-y-3">
                                    <div class="flex items-center gap-2">
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
                                        <textarea v-model="dataZonePromptText" placeholder="Enter a prompt to process the data zone content..." rows="2" class="input-field text-sm flex-grow"></textarea>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <button v-if="isTtiConfigured" @click="handleGenerateImage" class="btn btn-secondary btn-sm w-full" :disabled="isProcessing || (!discussionDataZone.trim() && !dataZonePromptText.trim())"><IconPhoto class="w-4 h-4 mr-1.5" :class="{'animate-pulse': isProcessing}"/>{{ isProcessing ? 'Processing...' : 'Generate Image' }}</button>
                                        <button @click="handleProcessContent" class="btn btn-secondary btn-sm w-full" :disabled="isProcessing || (!discussionDataZone.trim() && discussionImages.length === 0 && !dataZonePromptText.trim())"><IconSparkles class="w-4 h-4 mr-1.5" :class="{'animate-pulse': isProcessing}"/>{{ isProcessing ? 'Processing...' : 'Process Content' }}</button>
                                    </div>
                                </div>
                            </div>

                            <div class="w-72 flex-shrink-0 border-l dark:border-gray-600 flex flex-col">
                                <div class="flex-1 flex flex-col min-h-0">
                                    <div class="p-2 border-b dark:border-gray-600 flex-shrink-0 flex items-center justify-between"><h4 class="font-semibold text-sm">Images</h4><button @click="triggerDiscussionImageUpload" class="btn-icon" title="Add Image(s) or PDF" :disabled="isUploadingDiscussionImage"><IconAnimateSpin v-if="isUploadingDiscussionImage" class="w-5 h-5" /><IconPhoto v-else class="w-5 h-5" /></button></div>
                                    <div class="flex-grow overflow-y-auto p-2">
                                        <div v-if="discussionImages.length === 0" class="text-center text-xs text-gray-500 pt-4">No images.</div>
                                        <div v-else class="grid grid-cols-2 gap-2">
                                            <div v-for="(img_b64, index) in discussionImages" :key="img_b64.substring(0, 20) + index" class="relative group/image"><img :src="'data:image/png;base64,' + img_b64" class="w-full h-16 object-cover rounded-md transition-all duration-300" :class="{'grayscale': !isImageActive(index)}"/><div class="absolute inset-0 bg-black/50 opacity-0 group-hover/image:opacity-100 transition-opacity flex items-center justify-center gap-1"><button @click="uiStore.openImageViewer('data:image/png;base64,' + img_b64)" class="p-1.5 bg-white/20 text-white rounded-full hover:bg-white/40" title="View"><IconMaximize class="w-4 h-4" /></button><button @click="discussionsStore.toggleDiscussionImageActivation(index)" class="p-1.5 bg-white/20 text-white rounded-full hover:bg-white/40" :title="isImageActive(index) ? 'Deactivate' : 'Activate'"><IconEye v-if="isImageActive(index)" class="w-4 h-4" /><IconEyeOff v-else class="w-4 h-4" /></button><button @click="discussionsStore.deleteDiscussionImage(index)" class="p-1.5 bg-red-500/80 text-white rounded-full hover:bg-red-600" title="Delete"><IconXMark class="w-4 h-4" /></button></div></div>
                                        </div>
                                        <div v-if="isUploadingDiscussionImage" class="grid grid-cols-2 gap-2 mt-2"><div class="relative w-full h-16 bg-gray-200 dark:bg-gray-700 rounded-md flex items-center justify-center animate-pulse"><IconPhoto class="w-8 h-8 text-gray-400 dark:text-gray-500" /></div></div>
                                    </div>
                                </div>
                                <div class="flex-1 flex flex-col min-h-0">
                                    <div class="p-2 border-t dark:border-gray-600 flex-shrink-0 flex items-center justify-between"><h4 class="font-semibold text-sm">Artefacts</h4>
                                        <div class="flex items-center gap-1">
                                            <button @click="handleCreateArtefact" class="btn-icon" title="Create Artefact"><IconPlus class="w-5 h-5" /></button>
                                            <button @click="showUrlImport = !showUrlImport" class="btn-icon" title="Import from URL"><IconWeb class="w-5 h-5" /></button>
                                            <button @click="triggerArtefactFileUpload" class="btn-icon" title="Upload Artefact" :disabled="isUploadingArtefact"><IconAnimateSpin v-if="isUploadingArtefact" class="w-5 h-5" /><IconArrowUpTray v-else class="w-5 h-5" /></button>
                                        </div>
                                    </div>
                                    <div @dragover.prevent="isDraggingFile = true" @dragleave.prevent="isDraggingFile = false" @drop="handleDrop($event, 'artefact')" class="flex-grow overflow-y-auto p-2 space-y-2" :class="{'bg-blue-100 dark:bg-blue-900/20 border-2 border-dashed border-blue-400': isDraggingFile}">
                                        <div v-if="showUrlImport" class="p-2 bg-gray-50 dark:bg-gray-700/50 rounded-md">
                                            <label class="text-xs font-semibold">Import from URL</label>
                                            <div class="flex items-center gap-1 mt-1">
                                                <input v-model="urlToImport" type="url" placeholder="https://example.com" class="input-field-sm flex-grow">
                                                <button @click="handleImportArtefactFromUrl" class="btn btn-secondary btn-sm !p-2" :disabled="isProcessing || !urlToImport">
                                                    <IconAnimateSpin v-if="isProcessing" class="w-4 h-4" />
                                                    <span v-else>Fetch</span>
                                                </button>
                                            </div>
                                        </div>
                                        <div v-if="isLoadingArtefacts" class="text-center text-xs text-gray-500 pt-4">Loading...</div>
                                        <div v-else-if="groupedArtefacts.length === 0" class="text-center text-xs text-gray-500 pt-4">No artefacts. Drag files here to add.</div>
                                        
                                        <div v-else v-for="group in groupedArtefacts" :key="group.title" class="flex flex-col p-1.5 rounded-md" :class="group.isAnyVersionLoaded ? 'bg-green-100 dark:bg-green-900/40' : 'bg-gray-100 dark:bg-gray-700/50'">
                                            <div class="flex items-center justify-between">
                                                <div class="flex items-center gap-2 min-w-0">
                                                    <IconFileText class="w-4 h-4 text-gray-500 flex-shrink-0" />
                                                    <span class="truncate text-xs font-semibold" :title="group.title">{{ group.title }}</span>
                                                </div>
                                                <div class="flex items-center gap-1 flex-shrink-0">
                                                    <button @click="handleEditArtefact(group.title)" class="p-1 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500" title="View & Edit Content"><IconPencil class="w-3.5 h-3.5" /></button>
                                                    <button @click="handleDeleteArtefact(group.title)" class="p-1 rounded-full hover:bg-red-100 dark:hover:bg-red-900/50 text-red-500" title="Delete Artefact (all versions)"><IconTrash class="w-3.5 h-3.5" /></button>
                                                </div>
                                            </div>
                                            <div class="flex items-center gap-2 mt-1.5">
                                                <select v-model="selectedArtefactVersions[group.title]" class="input-field-sm text-xs flex-grow min-w-0">
                                                    <option v-for="artefact in group.versions" :key="artefact.version" :value="artefact.version">
                                                        Version {{ artefact.version }} {{ artefact.is_loaded ? ' (Loaded)' : '' }}
                                                    </option>
                                                </select>
                                                
                                                <template v-if="group.versions.find(v => v.version == selectedArtefactVersions[group.title])?.is_loaded">
                                                    <button @click="handleUnloadArtefact(group.title, selectedArtefactVersions[group.title])" class="btn btn-secondary btn-sm !p-2" title="Unload from Context">
                                                        <IconCheckCircle class="w-4 h-4 text-green-600 dark:text-green-400" />
                                                    </button>
                                                </template>
                                                <template v-else>
                                                     <button @click="handleLoadArtefact(group.title)" class="btn btn-secondary btn-sm !p-2" title="Load to Context">
                                                        <IconArrowDownTray class="w-4 h-4" />
                                                    </button>
                                                </template>
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
                    <div v-show="activeDataZoneTab === 'ltm'" class="flex-1 flex flex-col min-h-0 relative">
                        <div v-if="isMemorizing" class="absolute inset-0 bg-gray-400/30 dark:bg-gray-900/50 z-10 flex flex-col items-center justify-center">
                            <IconAnimateSpin class="w-10 h-10 text-gray-800 dark:text-gray-100 animate-spin" />
                            <p class="mt-3 font-semibold text-gray-800 dark:text-gray-100">Memorizing...</p>
                        </div>
                        <div class="p-4 border-b dark:border-gray-600 flex-shrink-0">
                            <div class="flex justify-between items-center">
                                <div><h3 class="font-semibold flex items-center gap-2"><IconThinking class="w-5 h-5" /> Long-Term Memory (LTM)</h3></div>
                                <div class="flex items-center gap-1">
                                    <button @click="handleMemorize" class="btn-icon" title="Memorize Current Discussion"><IconSparkles class="w-5 h-5" :class="{'animate-pulse': isMemorizing}"/></button>
                                </div>
                            </div>
                            <div class="mt-2"><div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400 font-mono"><span>Tokens</span><span>{{ formatNumber(memoryDataZoneTokens) }} / {{ formatNumber(maxTokens) }}</span></div><div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-1"><div class="h-1.5 rounded-full bg-yellow-500 transition-width duration-500" :style="{ width: `${getPercentage(memoryDataZoneTokens)}%` }"></div></div></div>
                        </div>
                        <div class="flex-grow min-h-0 flex">
                             <div class="flex-grow flex flex-col min-w-0">
                                <div class="p-2 border-b dark:border-gray-600 flex-shrink-0 flex items-center justify-between">
                                    <h4 class="font-semibold text-sm">Loaded Memory Context</h4>
                                    <button @click="toggleViewMode('ltm')" class="btn-icon" :title="dataZoneViewModes.ltm === 'edit' ? 'Switch to Preview' : 'Switch to Edit'"><IconEye v-if="dataZoneViewModes.ltm === 'edit'" class="w-5 h-5" /><IconPencil v-else class="w-5 h-5" /></button>
                                </div>
                                <div class="flex-grow min-h-0 p-2">
                                    <CodeMirrorEditor v-if="dataZoneViewModes.ltm === 'edit'" :model-value="memory" class="h-full" :options="{readOnly: true}" />
                                    <div v-else class="rendered-prose-container h-full"><MessageContentRenderer :content="memory" /></div>
                                </div>
                            </div>

                            <div class="w-72 flex-shrink-0 border-l dark:border-gray-600 flex flex-col">
                                <div class="p-2 border-b dark:border-gray-600 flex-shrink-0 flex items-center justify-between">
                                    <h4 class="font-semibold text-sm">Memory Bank</h4>
                                    <div class="flex items-center gap-1">
                                        <button @click="handleWipeAllMemories" class="btn-icon-danger" title="Unload all memories from context">
                                            <IconTrash class="w-5 h-5" />
                                        </button>
                                        <button @click="handleCreateMemory" class="btn-icon" title="Create New Memory"><IconPlus class="w-5 h-5" /></button>
                                    </div>
                                </div>
                                <div class="p-2 border-b dark:border-gray-600 flex-shrink-0">
                                    <input type="text" v-model="memorySearchTerm" placeholder="Search memories..." class="input-field-sm w-full" />
                                </div>
                                <div @dragover.prevent="isDraggingFile = true" @dragleave.prevent="isDraggingFile = false" @drop="handleDrop($event, 'memory')" class="flex-grow overflow-y-auto p-2 space-y-2" :class="{'bg-blue-100 dark:bg-blue-900/20 border-2 border-dashed border-blue-400': isDraggingFile}">
                                    <div v-if="isLoadingMemories" class="text-center text-xs text-gray-500 pt-4">Loading...</div>
                                    <div v-else-if="filteredMemories.length === 0" class="text-center text-xs text-gray-500 pt-4">No memories found.</div>
                                    <div v-else v-for="mem in filteredMemories" :key="mem.id" class="p-1.5 rounded-md" :class="loadedMemoryTitles.has(mem.title) ? 'bg-green-100 dark:bg-green-900/40' : 'bg-gray-100 dark:bg-gray-700/50'">
                                        <div class="flex items-center justify-between">
                                            <div class="flex items-center gap-2 min-w-0">
                                                <IconFileText class="w-4 h-4 text-gray-500 flex-shrink-0" />
                                                <span class="truncate text-xs font-semibold" :title="mem.title">{{ mem.title }}</span>
                                            </div>
                                            <div class="flex items-center gap-1 flex-shrink-0">
                                                <button @click="handleEditMemory(mem)" class="p-1 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-500" title="View & Edit Memory"><IconPencil class="w-3.5 h-3.5" /></button>
                                                <button @click="handleDeleteMemory(mem.id)" class="p-1 rounded-full hover:bg-red-100 dark:hover:bg-red-900/50 text-red-500" title="Delete Memory"><IconTrash class="w-3.5 h-3.5" /></button>
                                            </div>
                                        </div>
                                        <div class="flex items-center gap-2 mt-1.5">
                                            <template v-if="loadedMemoryTitles.has(mem.title)">
                                                <button @click="handleUnloadMemory(mem.title)" class="btn btn-secondary btn-sm !p-2 flex-grow justify-center" title="Unload from Context">
                                                    <IconCheckCircle class="w-4 h-4 text-green-600 dark:text-green-400" />
                                                </button>
                                            </template>
                                            <template v-else>
                                                <button @click="handleLoadMemory(mem.title)" class="btn btn-secondary btn-sm !p-2 flex-grow justify-center" title="Load to Context">
                                                    <IconArrowDownTray class="w-4 h-4" />
                                                </button>
                                            </template>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
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
.rendered-prose-container { @apply overflow-y-auto p-2; }
</style>