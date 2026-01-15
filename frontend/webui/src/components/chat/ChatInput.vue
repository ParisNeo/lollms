<script setup>
// ... (Imports from existing ChatInput.vue)
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useRouter } from 'vue-router'; // Added useRouter
import { useDiscussionsStore } from '../../stores/discussions';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { usePromptsStore } from '../../stores/prompts';
import { storeToRefs } from 'pinia';
import apiClient from '../../services/api';
import useEventBus from '../../services/eventBus';

import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';
import DropdownSubmenu from '../ui/DropdownMenu/DropdownSubmenu.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';

// Icons
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconMicrophone from '../../assets/icons/IconMicrophone.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconMcp from '../../assets/icons/IconMcp.vue';
import IconDatabase from '../../assets/icons/IconDatabase.vue';
import IconTicket from '../../assets/icons/IconTicket.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconLollms from '../../assets/icons/IconLollms.vue';
import IconUser from '../../assets/icons/IconUser.vue';
import IconToken from '../../assets/icons/IconToken.vue';
import IconCircle from '../../assets/icons/IconCircle.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconWeb from '../../assets/icons/ui/IconWeb.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconThinking from '../../assets/icons/IconThinking.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue'; 
import IconObservation from '../../assets/icons/IconObservation.vue';
import IconUserGroup from '../../assets/icons/IconUserGroup.vue'; 
import IconSettings from '../../assets/icons/IconSettings.vue'; // Added IconSettings
import IconFilePlus from '../../assets/icons/IconPlusCircle.vue'; // Reusing PlusCircle as FilePlus for manual doc

const discussionsStore = useDiscussionsStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const promptsStore = usePromptsStore();
const { on, off } = useEventBus();
const router = useRouter(); // Initialize router

// ... (Existing reactive refs & storeToRefs - activeDiscussion, user, etc.)
const dStoreRefs = storeToRefs(discussionsStore);
const activeDiscussionArtefacts = computed(() => dStoreRefs.activeDiscussionArtefacts?.value || []);
const activeDiscussion = computed(() => dStoreRefs.activeDiscussion?.value || null);
const generationInProgress = computed(() => dStoreRefs.generationInProgress?.value || false);
const generationState = computed(() => dStoreRefs.generationState?.value || { status: 'idle', details: '' });
const activeDiscussionContextStatus = computed(() => dStoreRefs.activeDiscussionContextStatus?.value || null);
const dataZonesTokensFromContext = computed(() => dStoreRefs.dataZonesTokensFromContext?.value || 0);
const currentModelVisionSupport = computed(() => dStoreRefs.currentModelVisionSupport?.value ?? true);
const activeAiTasks = computed(() => dStoreRefs.activeAiTasks?.value || {});

const { availableRagStores, availableMcpToolsForSelector } = storeToRefs(dataStore);
const { lollmsPrompts, userPromptsByCategory } = storeToRefs(promptsStore);

const messageText = ref('');
const isUploading = ref(false);
const fileInput = ref(null);
const imageInput = ref(null);
const isRecording = ref(false);
const userPromptSearchTerm = ref('');
const inputTokenCount = ref(0);
let tokenizeInputDebounceTimer = null;
const isDraggingOver = ref(false);

const isWebSearchActive = ref(false); 
const stagedImages = ref([]); 
const user = computed(() => authStore.user);

// ... (Existing Watchers & Mounted logic for user pref, etc.)
watch(user, (newUser) => {
    if (newUser) {
        isWebSearchActive.value = !!newUser.web_search_enabled;
    }
}, { immediate: true });

const attachedFiles = computed(() => activeDiscussionArtefacts.value || []);
const isSttConfigured = computed(() => !!user.value?.stt_binding_model_name);
const isTtiConfigured = computed(() => !!user.value?.tti_binding_model_name);
const isGoogleSearchConfigured = computed(() => !!user.value?.google_api_key && !!user.value?.google_cse_id);

// --- Herd Mode Validation ---
const canEnableHerd = computed(() => {
    if (!user.value) return false;
    const u = user.value;
    
    // If Dynamic Mode is set, we need at least one model in the pool
    if (u.herd_dynamic_mode) {
        return Array.isArray(u.herd_model_pool) && u.herd_model_pool.length > 0;
    }
    
    // If Static Mode (default), we need at least one participant in any crew list
    const hasPre = Array.isArray(u.herd_precode_participants) && u.herd_precode_participants.length > 0;
    const hasPost = Array.isArray(u.herd_postcode_participants) && u.herd_postcode_participants.length > 0;
    const hasLegacy = Array.isArray(u.herd_participants) && u.herd_participants.length > 0;
    
    return hasPre || hasPost || hasLegacy;
});

// ... (Context Bar Logic, Rag Selection, Mcp Selection - Unchanged)
const showContextBar = computed(() => user.value?.show_token_counter && activeDiscussionContextStatus.value);
const maxTokens = computed(() => activeDiscussionContextStatus.value?.max_tokens || 1);

const totalCurrentTokens = computed(() => {
    const breakdown = activeDiscussionContextStatus.value?.zones?.system_context?.breakdown || {};
    const historyBreakdown = activeDiscussionContextStatus.value?.zones?.message_history?.breakdown || {};
    const sys = breakdown.system_prompt?.tokens || 0;
    const history = (historyBreakdown.text_tokens || 0) + (historyBreakdown.image_tokens || 0);
    return sys + dataZonesTokensFromContext.value + history + inputTokenCount.value;
});

const getPercentage = (tokens) => maxTokens.value > 0 ? (tokens / maxTokens.value) * 100 : 0;

const contextParts = computed(() => {
    const breakdown = activeDiscussionContextStatus.value?.zones?.system_context?.breakdown || {};
    const historyBreakdown = activeDiscussionContextStatus.value?.zones?.message_history?.breakdown || {};
    const parts = [];
    if (breakdown.system_prompt?.tokens > 0) parts.push({ label: 'S', value: breakdown.system_prompt.tokens, title: 'System Prompt', colorClass: 'bg-blue-500' });
    if (dataZonesTokensFromContext.value > 0) parts.push({ label: 'D', value: dataZonesTokensFromContext.value, title: 'Data Zones', colorClass: 'bg-yellow-500' });
    if (historyBreakdown.text_tokens > 0) parts.push({ label: 'H', value: historyBreakdown.text_tokens, title: 'History (Text)', colorClass: 'bg-green-500' });
    if (historyBreakdown.image_tokens > 0) parts.push({ label: 'I', value: historyBreakdown.image_tokens, title: 'History (Images)', colorClass: 'bg-teal-500' });
    if (inputTokenCount.value > 0) parts.push({ label: 'U', value: inputTokenCount.value, title: 'User Input', colorClass: 'bg-purple-500' });
    return parts;
});

const totalPercentage = computed(() => getPercentage(totalCurrentTokens.value));
const progressBorderColorClass = computed(() => {
    if (totalPercentage.value >= 100) return 'border-red-600 dark:border-red-500';
    if (totalPercentage.value >= 90) return 'border-red-400 dark:border-red-400';
    if (totalPercentage.value >= 75) return 'border-yellow-500 dark:border-yellow-400';
    return 'border-gray-200 dark:border-gray-700';
});

const ragStoreSelection = computed({
    get: () => activeDiscussion.value?.rag_datastore_ids || [],
    set: (newIds) => { if (activeDiscussion.value) discussionsStore.updateDiscussionRagStores({ discussionId: activeDiscussion.value.id, ragDatastoreIds: newIds }); }
});

const mcpToolSelection = computed({
    get: () => activeDiscussion.value?.active_tools || [],
    set: (newIds) => { if (activeDiscussion.value) discussionsStore.updateDiscussionMcps({ discussionId: activeDiscussion.value.id, mcp_tool_ids: newIds }); }
});

const currentActiveTask = computed(() => {
    if (!activeDiscussion.value) return null;
    return activeAiTasks.value[activeDiscussion.value.id];
});

function toggleRagStore(storeId) {
    const current = new Set(ragStoreSelection.value);
    if (current.has(storeId)) current.delete(storeId);
    else current.add(storeId);
    ragStoreSelection.value = Array.from(current);
}

function toggleMcpTool(toolId) {
    const current = new Set(mcpToolSelection.value);
    if (current.has(toolId)) current.delete(toolId);
    else current.add(toolId);
    mcpToolSelection.value = Array.from(current);
}

function toggleWebSearch() {
    if (!isGoogleSearchConfigured.value) {
        uiStore.addNotification("Google Web Search is not configured. Please add your API Key in Settings > User Context.", "error");
        return;
    }
    isWebSearchActive.value = !isWebSearchActive.value;
}

// Function to toggle global user preferences from the menu shortcut
async function toggleUserPref(key, currentValue) {
    // Prevent toggle if herd is disabled and we try to enable it without config
    if (key === 'herd_mode_enabled' && !currentValue && !canEnableHerd.value) {
        uiStore.addNotification("Please configure Herd participants in Settings > User Context first.", "warning");
        return;
    }

    try {
        await authStore.updateUserPreferences({ [key]: !currentValue }, false);
    } catch (e) {
        console.error("Failed to toggle preference:", e);
    }
}

function navigateToContextSettings() {
    router.push('/settings?section=context');
}

// --- Active Features Badges ---
const activeFeatures = computed(() => {
    const features = [];
    
    // Herd Mode
    if (user.value?.herd_mode_enabled) {
        features.push({
            id: 'herd',
            icon: IconUserGroup,
            label: `Herd (${user.value.herd_rounds} rnds)`,
            colorClass: 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800',
            title: `Herd Mode Active. Phase 1 & 3 enabled.`
        });
    }

    // RAG
    if (ragStoreSelection.value.length > 0) {
        features.push({ 
            id: 'rag', 
            icon: IconDatabase, 
            label: 'RAG', 
            colorClass: 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
            title: `${ragStoreSelection.value.length} Data Store(s) Active`
        });
    }
    
    // Tools
    if (mcpToolSelection.value.length > 0) {
        features.push({ 
            id: 'tools', 
            icon: IconMcp, 
            label: 'Tools', 
            colorClass: 'text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800',
            title: `${mcpToolSelection.value.length} Tool(s) Active`
        });
    }
    
    // Web Search
    if (isWebSearchActive.value) {
        features.push({
            id: 'web_search',
            icon: IconGlobeAlt,
            label: 'Web',
            colorClass: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
            title: 'Web Search Active. AI can search the internet.'
        });
    }
    
    // Thinking (Reasoning)
    if (user.value?.reasoning_activation) {
        features.push({
            id: 'thinking',
            icon: IconThinking,
            label: 'Thinking',
            colorClass: 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-800',
            title: 'Thinking Mode Enabled. AI will reason before answering.'
        });
    }

    // Annotation
    if (user.value?.image_annotation_enabled) {
        features.push({
            id: 'annotation',
            icon: IconObservation,
            label: 'Annotate',
            colorClass: 'text-pink-600 dark:text-pink-400 bg-pink-50 dark:bg-pink-900/20 border-pink-200 dark:border-pink-800',
            title: 'Image Annotation Enabled. AI can detect objects.'
        });
    }

    // Memory
    if (user.value?.memory_enabled) {
        features.push({
            id: 'memory',
            icon: IconThinking,
            label: user.value.auto_memory_enabled ? 'Memory (Auto)' : 'Memory',
            colorClass: 'text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-900/20 border-teal-200 dark:border-teal-800',
            title: user.value.auto_memory_enabled 
                ? 'Long-Term Memory Active. AI can automatically save new memories.' 
                : 'Long-Term Memory Active. Use <new_memory> tags to save.'
        });
    }

    // Vision
    if (currentModelVisionSupport.value) {
        features.push({
            id: 'vision',
            icon: IconEye,
            label: 'Vision',
            colorClass: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
            title: 'Vision Supported. AI can see attached images.'
        });
    }

    // Image Gen
    if (user.value?.image_generation_enabled) {
        features.push({
            id: 'img_gen',
            icon: IconPhoto,
            label: 'ImgGen',
            colorClass: 'text-fuchsia-600 dark:text-fuchsia-400 bg-fuchsia-50 dark:bg-fuchsia-900/20 border-fuchsia-200 dark:border-fuchsia-800',
            title: 'Image Generation Enabled. AI can create images.'
        });
    }

    // Image Edit
    if (user.value?.image_editing_enabled) {
        features.push({
            id: 'img_edit',
            icon: IconPencil,
            label: 'ImgEdit',
            colorClass: 'text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-900/20 border-violet-200 dark:border-violet-800',
            title: 'Image Editing Enabled. AI can modify existing images.'
        });
    }

    // Slide Maker
    if (user.value?.slide_maker_enabled) {
        features.push({
            id: 'slides',
            icon: IconPresentationChartBar,
            label: 'Slides',
            colorClass: 'text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-800',
            title: 'Slide Maker Enabled. AI can generate presentations.'
        });
    }

    // Note Generation
    if (user.value?.note_generation_enabled) {
        features.push({
            id: 'notes',
            icon: IconFileText,
            label: 'Notes',
            colorClass: 'text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900/20 border-gray-200 dark:border-gray-800',
            title: 'Note Generation Enabled. AI can create notes.'
        });
    }

    // Audio (TTS/STT)
    if (user.value?.tts_binding_model_name || user.value?.stt_binding_model_name) {
        features.push({
            id: 'audio',
            icon: IconMicrophone,
            label: 'Audio',
            colorClass: 'text-cyan-600 dark:text-cyan-400 bg-cyan-50 dark:bg-cyan-900/20 border-cyan-200 dark:border-cyan-800',
            title: 'Audio Features (TTS/STT) Enabled.'
        });
    }

    return features;
});

const showHeaderRow = computed(() => showContextBar.value || activeFeatures.value.length > 0);
const maxVisibleBadges = 5;
const visibleFeatures = computed(() => activeFeatures.value.slice(0, maxVisibleBadges));
const hiddenFeatures = computed(() => activeFeatures.value.slice(maxVisibleBadges));

// ... (Image & File Handling - Unchanged)
function openStagedImageViewer(startIndex) {
    uiStore.openImageViewer({
        imageList: stagedImages.value.map((img) => ({ 
            src: img.previewUrl, 
            prompt: `Uploaded image: ${img.file.name}` 
        })),
        startIndex
    });
}
async function toggleArtefactLoad(file) {
    if (!activeDiscussion.value) return;
    if (file.is_loaded) {
        await discussionsStore.unloadArtefactFromContext({ discussionId: activeDiscussion.value.id, artefactTitle: file.title, version: file.version });
    } else {
        await discussionsStore.loadArtefactToContext({ discussionId: activeDiscussion.value.id, artefactTitle: file.title, version: file.version });
    }
}
async function removeArtefact(file) {
    if (!activeDiscussion.value) return;
    const confirmed = await uiStore.showConfirmation({ title: 'Remove File?', message: `Remove "${file.title}" from the discussion?`, confirmText: 'Remove' });
    if (confirmed.confirmed) {
        await discussionsStore.deleteArtefact({ discussionId: activeDiscussion.value.id, artefactTitle: file.title });
    }
}
function removeStagedImage(index) {
    const removed = stagedImages.value.splice(index, 1)[0];
    if (removed && removed.previewUrl) {
        URL.revokeObjectURL(removed.previewUrl);
    }
}
function triggerFileUpload() { fileInput.value?.click(); }
function triggerImageUpload() { imageInput.value?.click(); }
async function handleFilesInput(files) {
    if (files.length === 0) return;
    const images = files.filter(f => f.type.startsWith('image/'));
    const others = files.filter(f => !f.type.startsWith('image/'));
    if (images.length > 0) {
        images.forEach(file => {
            stagedImages.value.push({ file, previewUrl: URL.createObjectURL(file) });
        });
    }
    if (others.length > 0) {
        if (!activeDiscussion.value) await discussionsStore.createNewDiscussion();
        if (activeDiscussion.value) {
            isUploading.value = true;
            try {
                // Modified to use auto_load logic implicitly (default backend behavior updated to auto_load=True)
                await Promise.all(others.map(file => discussionsStore.addArtefact({ discussionId: activeDiscussion.value.id, file, extractImages: true, auto_load: true })));
            } finally { isUploading.value = false; }
        }
    }
}
async function handleFileUpload(event) { const files = Array.from(event.target.files || []); await handleFilesInput(files); event.target.value = ''; }
async function handleImageUpload(event) { const files = Array.from(event.target.files || []); await handleFilesInput(files); event.target.value = ''; }
async function handleDrop(event) { event.stopPropagation(); isDraggingOver.value = false; const files = Array.from(event.dataTransfer.files); if (files.length > 0) { await handleFilesInput(files); } }
async function handlePaste(event) {
    event.stopPropagation();
    const items = (event.clipboardData || window.clipboardData).items;
    const imageFiles = [];
    for (let i = 0; i < items.length; i++) {
        if (items[i].type.indexOf("image") !== -1) {
            const blob = items[i].getAsFile();
            if (blob) {
                const extension = (blob.type.split('/')[1] || 'png').toLowerCase().replace('jpeg', 'jpg');
                imageFiles.push(new File([blob], `pasted_image_${Date.now()}.${extension}`, { type: blob.type }));
            }
        }
    }
    if (imageFiles.length > 0) {
        event.preventDefault();
        await handleFilesInput(imageFiles);
    }
}
async function handleImportFromInternet() {
    if (!activeDiscussion.value) { uiStore.addNotification('Please start a discussion first.', 'warning'); return; }
    uiStore.openModal('scrapeUrl', { discussionId: activeDiscussion.value.id, mode: 'url' });
}
async function handleCreateManualArtefact() {
    if (!activeDiscussion.value) { uiStore.addNotification('Please start a discussion first.', 'warning'); return; }
    uiStore.openModal('createArtefact', { discussionId: activeDiscussion.value.id });
}
function handlePromptSelection(content) { messageText.value += (messageText.value ? '\n' : '') + content; }

const filteredUserPromptsByCategory = computed(() => {
    if (!userPromptSearchTerm.value) return userPromptsByCategory.value;
    const term = userPromptSearchTerm.value.toLowerCase();
    const result = {};
    for (const [cat, prompts] of Object.entries(userPromptsByCategory.value)) {
        const filtered = prompts.filter(p => p.name.toLowerCase().includes(term));
        if (filtered.length > 0) result[cat] = filtered;
    }
    return result;
});

let mediaRecorder = null;
let audioChunks = [];
async function toggleRecording() {
    if (isRecording.value) { mediaRecorder?.stop(); isRecording.value = false; } else {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                const text = await discussionsStore.transcribeAudio(audioBlob);
                if (text) messageText.value += (messageText.value ? ' ' : '') + text;
                stream.getTracks().forEach(track => track.stop());
            };
            mediaRecorder.start();
            isRecording.value = true;
        } catch (err) { uiStore.addNotification('Microphone access denied.', 'error'); }
    }
}

// --- Sending ---
async function handleSendMessage() {
    if (generationInProgress.value) return;
    const text = messageText.value.trim();
    if (!text && attachedFiles.value.length === 0 && stagedImages.value.length === 0) return;

    const imagesToUpload = stagedImages.value.map(item => item.file);
    const localPreviews = stagedImages.value.map(item => item.previewUrl);
    messageText.value = '';
    inputTokenCount.value = 0;
    stagedImages.value = []; 

    try {
        await discussionsStore.sendMessage({ 
            prompt: text, 
            image_server_paths: [], 
            localImageUrls: localPreviews,
            image_files: imagesToUpload,
            webSearchEnabled: isWebSearchActive.value
        });
    } catch(err) {
        console.error("SendMessage failed:", err);
        uiStore.addNotification('Failed to send message.', 'error');
        messageText.value = text;
        imagesToUpload.forEach((file, i) => { stagedImages.value.push({ file, previewUrl: localPreviews[i] }); });
    }
}

function handleKeyDown(event) { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); handleSendMessage(); } }
async function fetchInputTokenCount(text) {
    if (!text.trim()) { inputTokenCount.value = 0; return; }
    try {
        const response = await apiClient.post('/api/discussions/tokenize', { text });
        inputTokenCount.value = response.data.tokens;
    } catch (error) {}
}
function handleStopGeneration() { discussionsStore.stopGeneration(); }

watch(messageText, (newText) => {
    clearTimeout(tokenizeInputDebounceTimer);
    if (!newText.trim()) { inputTokenCount.value = 0; }
    else if (showContextBar.value) { tokenizeInputDebounceTimer = setTimeout(() => fetchInputTokenCount(newText), 500); }
});

onMounted(() => {
    promptsStore.fetchPrompts();
    if (dataStore.availableRagStores.length === 0) dataStore.fetchDataStores();
    if (dataStore.availableMcpToolsForSelector.length === 0) dataStore.fetchMcpTools();
    on('files-dropped-in-chat', handleFilesInput);
    on('files-pasted-in-chat', handleFilesInput);
});
onUnmounted(() => {
    off('files-dropped-in-chat', handleFilesInput);
    off('files-pasted-in-chat', handleFilesInput);
    stagedImages.value.forEach(img => URL.revokeObjectURL(img.previewUrl));
});
</script>

<template>
    <div class="flex-shrink-0 bg-white/95 dark:bg-gray-800/95 backdrop-blur border-t dark:border-gray-700 shadow-lg relative"
         @dragover.prevent="isDraggingOver = true" @dragleave="isDraggingOver = false" @drop.prevent="handleDrop">
        
        <!-- Drop Overlay -->
        <div v-if="isDraggingOver" class="absolute inset-0 bg-blue-500/10 border-4 border-dashed border-blue-500 rounded-lg z-50 flex items-center justify-center m-4 pointer-events-none transition-all">
            <p class="text-2xl font-black text-blue-600 uppercase tracking-tighter">Drop files to chat</p>
        </div>

        <!-- Vision Warning -->
        <div v-if="!currentModelVisionSupport && stagedImages.length > 0" class="px-4 py-1.5 bg-yellow-50 dark:bg-yellow-900/20 border-b border-yellow-200 dark:border-yellow-800 text-[10px] text-yellow-700 dark:text-yellow-300 flex items-center gap-2">
            <IconInfo class="w-3.5 h-3.5 flex-shrink-0" />
            <p>Model lacks vision support. Your uploaded images will be ignored.</p>
        </div>

        <!-- Context Bar / Feature Badges Row -->
        <div v-if="showHeaderRow" class="px-3 py-1 bg-gray-50 dark:bg-gray-900 border-b dark:border-gray-700 overflow-x-auto no-scrollbar">
             <div class="max-w-4xl mx-auto flex items-center gap-3">
                <template v-if="showContextBar">
                    <div class="flex items-center gap-1 text-gray-500 flex-shrink-0">
                        <IconToken class="w-3.5 h-3.5" />
                        <span class="text-[10px] font-black uppercase tracking-tight hidden sm:inline">Context</span>
                    </div>
                    <div :class="['flex-grow h-2 rounded-full overflow-hidden flex border dark:border-gray-800 bg-gray-200 dark:bg-gray-700', progressBorderColorClass]">
                        <div v-for="part in contextParts" :key="part.label" :class="[part.colorClass, 'h-full transition-all duration-500 ease-out']" :style="{ width: `${getPercentage(part.value)}%` }" :title="`${part.title}: ${part.value} tokens`"></div>
                    </div>
                    <div class="font-mono text-[10px] text-gray-500 whitespace-nowrap flex-shrink-0">
                        <span>{{ totalCurrentTokens }}</span><span class="opacity-30 mx-1">/</span><span>{{ maxTokens }}</span>
                    </div>
                </template>
                <div v-else class="flex-grow"></div> 

                <div class="h-3 w-px bg-gray-300 dark:bg-gray-700 mx-1 flex-shrink-0" v-if="showContextBar && activeFeatures.length > 0"></div>

                <div class="flex items-center gap-1.5 flex-shrink-0" v-if="activeFeatures.length > 0">
                    <div v-for="feat in visibleFeatures" :key="feat.id" 
                         :class="['flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] font-bold uppercase tracking-wider transition-colors cursor-help', feat.colorClass]"
                         :title="feat.title">
                        <div class="w-3 h-3 flex-shrink-0 flex items-center justify-center">
                            <component :is="feat.icon" class="w-full h-full fill-current" />
                        </div>
                        <span class="hidden md:inline">{{ feat.label }}</span>
                    </div>

                    <div v-if="hiddenFeatures.length > 0" class="relative group/overflow">
                        <div class="flex items-center gap-1 px-1.5 py-0.5 rounded border text-[9px] font-bold uppercase tracking-wider transition-colors cursor-help bg-gray-100 dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300">
                            <span>+{{ hiddenFeatures.length }}</span>
                        </div>
                        <div class="absolute bottom-full right-0 mb-1 w-max p-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl opacity-0 group-hover/overflow:opacity-100 transition-opacity pointer-events-none group-hover/overflow:pointer-events-auto flex flex-col gap-1 z-50">
                            <div v-for="feat in hiddenFeatures" :key="feat.id" 
                                :class="['flex items-center gap-2 px-2 py-1 rounded border text-[10px] font-bold uppercase tracking-wider', feat.colorClass]">
                                <div class="w-3 h-3 flex-shrink-0 flex items-center justify-center">
                                    <component :is="feat.icon" class="w-full h-full fill-current" />
                                </div>
                                <span>{{ feat.label }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="p-3 sm:p-4 max-w-4xl mx-auto space-y-3">
            <!-- SPECIAL SELECTION ZONE -->
            <div v-if="stagedImages.length > 0 || attachedFiles.length > 0" class="flex flex-wrap gap-2 max-h-40 overflow-y-auto custom-scrollbar p-3 mb-2 bg-gray-100 dark:bg-gray-900/60 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-700 transition-all">
                <div v-for="(img, index) in stagedImages" :key="`staged-img-${index}`" 
                     @click="openStagedImageViewer(index)"
                     class="relative w-16 h-16 group rounded-lg overflow-hidden border-2 transition-all shadow-sm cursor-pointer border-blue-500 hover:scale-105"
                     :class="{'grayscale opacity-60': !currentModelVisionSupport}">
                    <img :src="img.previewUrl" class="w-full h-full object-cover" />
                    <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-1">
                        <button @click.stop="removeStagedImage(index)" class="text-white hover:text-red-400 p-0.5" title="Remove"><IconXMark class="w-5 h-5" /></button>
                    </div>
                </div>

                <div v-for="file in attachedFiles" :key="file.title" 
                     class="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border transition-all duration-200 shadow-sm bg-white dark:bg-gray-800"
                     :class="file.is_loaded ? 'border-blue-200 text-blue-700 dark:border-blue-800' : 'border-gray-200 text-gray-400 opacity-60'">
                    <button @click="toggleArtefactLoad(file)" :title="file.is_loaded ? 'Unload' : 'Load'"><IconCheckCircle v-if="file.is_loaded" class="w-4 h-4 text-blue-600"/><IconCircle v-else class="w-4 h-4" /></button>
                    <span class="truncate max-w-[150px] font-medium" :title="file.title">{{ file.title }}</span>
                    <button @click="removeArtefact(file)" class="text-gray-400 hover:text-red-500 transition-colors ml-1" title="Remove"><IconXMark class="w-3.5 h-3.5" /></button>
                </div>
            </div>

            <!-- Input Controls -->
            <div class="flex items-end gap-2 bg-gray-50 dark:bg-gray-900/50 p-2 rounded-2xl border border-gray-200 dark:border-gray-700 focus-within:border-blue-500/50 focus-within:ring-4 focus-within:ring-blue-500/10 transition-all duration-200 shadow-sm relative overflow-hidden">
                
                <div class="pb-1 pl-1">
                    <DropdownMenu icon="plus" collection="" title="Add" buttonClass="btn-icon bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 w-9 h-9 flex items-center justify-center rounded-xl transition-all shadow-sm border dark:border-gray-700 relative">
                         <div v-if="ragStoreSelection.length > 0 || mcpToolSelection.length > 0" class="absolute -top-0.5 -right-0.5 w-3 h-3 bg-blue-500 rounded-full border-2 border-white dark:border-gray-800"></div>
                        <button @click="triggerFileUpload" class="menu-item"><IconFileText class="w-4 h-4 mr-3 text-blue-500" /> <span>Add File</span></button>
                        <button @click="triggerImageUpload" class="menu-item"><IconPhoto class="w-4 h-4 mr-3 text-purple-500" /> <span>Upload Image</span></button>
                        <button @click="handleCreateManualArtefact" class="menu-item"><IconFilePlus class="w-4 h-4 mr-3 text-green-500" /> <span>Create Document</span></button>
                        <button @click="handleImportFromInternet" class="menu-item"><IconWeb class="w-4 h-4 mr-3 text-cyan-500" /> <span>Import from Internet</span></button>
                        
                        <div class="menu-divider"></div>
                        
                        <!-- NEW Context Options Submenu -->
                        <DropdownSubmenu title="Context Options" icon="cog" collection="ui">
                             <div class="p-1 min-w-[200px]">
                                <!-- Group: Knowledge -->
                                <div class="px-3 py-1 text-[10px] font-black text-gray-400 uppercase tracking-widest mt-1">Knowledge</div>
                                
                                <!-- Web Search Toggle -->
                                <button 
                                    @click.stop="toggleWebSearch" 
                                    class="menu-item flex justify-between items-center group/item" 
                                    :class="{'opacity-50 cursor-not-allowed': !isGoogleSearchConfigured}"
                                    :title="!isGoogleSearchConfigured ? 'Requires Google API Key & CSE ID in Settings > User Context' : 'Enable Web Search'"
                                >
                                    <span class="flex items-center gap-2">
                                        <IconGlobeAlt class="w-4 h-4 text-blue-500" />
                                        <span>Web Search</span>
                                    </span>
                                    <IconCheckCircle v-if="isWebSearchActive" class="w-4 h-4 text-green-500" />
                                    <IconCircle v-else class="w-4 h-4 text-gray-400" />
                                </button>
                                
                                <!-- Memory Master Toggle -->
                                <button @click.stop="toggleUserPref('memory_enabled', user.memory_enabled)" class="menu-item flex justify-between items-center group/item">
                                    <span class="flex items-center gap-2">
                                        <IconThinking class="w-4 h-4 text-teal-500" />
                                        <span>Memory</span>
                                    </span>
                                    <IconCheckCircle v-if="user?.memory_enabled" class="w-4 h-4 text-green-500" />
                                    <IconCircle v-else class="w-4 h-4 text-gray-400" />
                                </button>

                                <!-- Auto-Memory Sub-Toggle (Only visible if Memory is enabled) -->
                                <button v-if="user?.memory_enabled" @click.stop="toggleUserPref('auto_memory_enabled', user.auto_memory_enabled)" class="menu-item flex justify-between items-center group/item pl-8 text-xs">
                                    <span class="flex items-center gap-2 text-gray-600 dark:text-gray-400">
                                        <span>↳ Auto Save</span>
                                    </span>
                                    <IconCheckCircle v-if="user?.auto_memory_enabled" class="w-3.5 h-3.5 text-green-500" />
                                    <IconCircle v-else class="w-3.5 h-3.5 text-gray-400" />
                                </button>
                                
                                <!-- Group: Reasoning -->
                                <div class="px-3 py-1 text-[10px] font-black text-gray-400 uppercase tracking-widest mt-2">Reasoning</div>
                                
                                <!-- Herd Mode Toggle -->
                                <button 
                                    @click.stop="toggleUserPref('herd_mode_enabled', user.herd_mode_enabled)" 
                                    class="menu-item flex justify-between items-center group/item"
                                    :disabled="!canEnableHerd"
                                    :class="{'opacity-50 cursor-not-allowed': !canEnableHerd}"
                                    :title="!canEnableHerd ? 'Configure Herd participants in Settings > User Context first' : 'Toggle Herd Mode'"
                                >
                                    <span class="flex items-center gap-2">
                                        <IconUserGroup class="w-4 h-4 text-amber-500" />
                                        <span>Herd Mode</span>
                                    </span>
                                    <IconCheckCircle v-if="user?.herd_mode_enabled" class="w-4 h-4 text-green-500" />
                                    <IconCircle v-else class="w-4 h-4 text-gray-400" />
                                </button>
                                
                                <!-- Thinking Mode Toggle -->
                                <button @click.stop="toggleUserPref('reasoning_activation', user.reasoning_activation)" class="menu-item flex justify-between items-center group/item">
                                    <span class="flex items-center gap-2">
                                        <IconThinking class="w-4 h-4 text-purple-500" />
                                        <span>Thinking</span>
                                    </span>
                                    <IconCheckCircle v-if="user?.reasoning_activation" class="w-4 h-4 text-green-500" />
                                    <IconCircle v-else class="w-4 h-4 text-gray-400" />
                                </button>

                                <!-- Group: Generation -->
                                <div class="px-3 py-1 text-[10px] font-black text-gray-400 uppercase tracking-widest mt-2">Generation</div>

                                <!-- Image Generation Toggle -->
                                <button v-if="isTtiConfigured" @click.stop="toggleUserPref('image_generation_enabled', user.image_generation_enabled)" class="menu-item flex justify-between items-center group/item">
                                    <span class="flex items-center gap-2">
                                        <IconPhoto class="w-4 h-4 text-pink-500" />
                                        <span>Image Gen</span>
                                    </span>
                                    <IconCheckCircle v-if="user?.image_generation_enabled" class="w-4 h-4 text-green-500" />
                                    <IconCircle v-else class="w-4 h-4 text-gray-400" />
                                </button>
                                
                                <!-- Image Editing Toggle -->
                                <button v-if="isTtiConfigured" @click.stop="toggleUserPref('image_editing_enabled', user.image_editing_enabled)" class="menu-item flex justify-between items-center group/item">
                                    <span class="flex items-center gap-2">
                                        <IconPencil class="w-4 h-4 text-indigo-500" />
                                        <span>Image Edit</span>
                                    </span>
                                    <IconCheckCircle v-if="user?.image_editing_enabled" class="w-4 h-4 text-green-500" />
                                    <IconCircle v-else class="w-4 h-4 text-gray-400" />
                                </button>
                                
                                <!-- Image Annotation Toggle -->
                                <button @click.stop="toggleUserPref('image_annotation_enabled', user.image_annotation_enabled)" class="menu-item flex justify-between items-center group/item">
                                    <span class="flex items-center gap-2">
                                        <div class="w-4 h-4 flex-shrink-0 flex items-center justify-center">
                                            <IconObservation class="w-full h-full text-pink-600" />
                                        </div>
                                        <span>Annotate</span>
                                    </span>
                                    <IconCheckCircle v-if="user?.image_annotation_enabled" class="w-4 h-4 text-green-500" />
                                    <IconCircle v-else class="w-4 h-4 text-gray-400" />
                                </button>

                                <!-- Slide Maker Toggle -->
                                <button v-if="isTtiConfigured" @click.stop="toggleUserPref('slide_maker_enabled', user.slide_maker_enabled)" class="menu-item flex justify-between items-center group/item">
                                    <span class="flex items-center gap-2">
                                        <IconPresentationChartBar class="w-4 h-4 text-orange-500" />
                                        <span>Slide Maker</span>
                                    </span>
                                    <IconCheckCircle v-if="user?.slide_maker_enabled" class="w-4 h-4 text-green-500" />
                                    <IconCircle v-else class="w-4 h-4 text-gray-400" />
                                </button>

                                <!-- Note Generation Toggle -->
                                <button @click.stop="toggleUserPref('note_generation_enabled', user.note_generation_enabled)" class="menu-item flex justify-between items-center group/item">
                                    <span class="flex items-center gap-2">
                                        <IconFileText class="w-4 h-4 text-gray-500" />
                                        <span>Notes Gen</span>
                                    </span>
                                    <IconCheckCircle v-if="user?.note_generation_enabled" class="w-4 h-4 text-green-500" />
                                    <IconCircle v-else class="w-4 h-4 text-gray-400" />
                                </button>

                                <!-- Settings Link -->
                                <div class="my-1 border-t border-gray-100 dark:border-gray-700 mt-2"></div>
                                <button @click="navigateToContextSettings" class="menu-item flex justify-between items-center group/item">
                                    <span class="flex items-center gap-2">
                                        <IconSettings class="w-4 h-4 text-gray-500" />
                                        <span>Configure...</span>
                                    </span>
                                </button>

                             </div>
                        </DropdownSubmenu>
                        
                        <!-- RAG, Tools, Prompts Submenus (Same as before) -->
                        <DropdownSubmenu title="RAG Context" icon="database">
                             <div class="p-1 max-h-64 overflow-y-auto min-w-[200px]">
                                <div v-if="availableRagStores.length === 0" class="px-4 py-3 text-xs text-gray-500 italic">No stores available.</div>
                                <button v-for="store in availableRagStores" :key="store.id" @click.stop="toggleRagStore(store.id)" class="menu-item flex justify-between items-center group/item"><span class="truncate pr-4" :class="{'font-bold text-green-600': ragStoreSelection.includes(store.id)}">{{ store.name }}</span><IconCheckCircle v-if="ragStoreSelection.includes(store.id)" class="w-4 h-4 text-green-500 flex-shrink-0" /></button>
                             </div>
                        </DropdownSubmenu>
                        <DropdownSubmenu title="MCP Tools" icon="server">
                            <div class="p-1 max-h-72 overflow-y-auto min-w-[220px]">
                                <div v-if="availableMcpToolsForSelector.length === 0" class="px-4 py-3 text-xs text-gray-500 italic">No tools available.</div>
                                <div v-for="group in availableMcpToolsForSelector" :key="group.label" class="mb-2">
                                    <div class="px-3 py-1 text-[10px] font-black text-gray-400 uppercase tracking-widest">{{ group.label }}</div>
                                    <button v-for="tool in group.items" :key="tool.id" @click.stop="toggleMcpTool(tool.id)" class="menu-item flex justify-between items-center pl-5"><span class="truncate pr-4 text-xs" :class="{'font-bold text-purple-600': mcpToolSelection.includes(tool.id)}">{{ tool.name }}</span><IconCheckCircle v-if="mcpToolSelection.includes(tool.id)" class="w-4 h-4 text-purple-500 flex-shrink-0" /></button>
                                </div>
                            </div>
                        </DropdownSubmenu>
                        <DropdownSubmenu title="Prompts" icon="ticket">
                             <div class="p-1 max-h-72 overflow-y-auto min-w-[200px]">
                                <DropdownSubmenu title="Standard" icon="lollms" class="w-full"><button v-for="p in lollmsPrompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-xs">{{ p.name }}</button></DropdownSubmenu>
                                <DropdownSubmenu title="Personal" icon="user" class="w-full">
                                    <div class="px-2 py-1 sticky top-0 bg-white dark:bg-gray-800 z-10"><input v-model="userPromptSearchTerm" @click.stop placeholder="Search..." class="input-field-sm w-full"></div>
                                    <div v-for="(prompts, cat) in filteredUserPromptsByCategory" :key="cat">
                                        <div class="px-3 py-1 text-[9px] font-bold text-gray-400 uppercase">{{ cat }}</div>
                                        <button v-for="p in prompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-xs pl-5">{{ p.name }}</button>
                                    </div>
                                </DropdownSubmenu>
                             </div>
                        </DropdownSubmenu>
                    </DropdownMenu>
                    <input type="file" ref="fileInput" @change="handleFileUpload" multiple class="hidden">
                    <input type="file" ref="imageInput" @change="handleImageUpload" multiple accept="image/*" class="hidden">
                </div>

                <div class="flex-grow min-w-0 relative">
                    <textarea 
                        ref="textareaRef"
                        v-model="messageText" 
                        @keydown="handleKeyDown" 
                        @paste="handlePaste" 
                        rows="1" 
                        class="w-full bg-transparent border-0 focus:ring-0 resize-none py-2.5 px-3 max-h-64 overflow-y-auto text-sm leading-relaxed" 
                        :class="{ 'opacity-0 pointer-events-none': generationInProgress }"
                        :placeholder="isRecording ? 'Recording... Click to stop.' : 'Type a message... (Shift+Enter for new line)'" 
                    ></textarea>
                    
                    <!-- Status Overlay -->
                    <div v-if="generationInProgress || currentActiveTask" class="absolute inset-0 flex items-center px-3 text-sm text-gray-500 dark:text-gray-400 italic select-none">
                         <IconAnimateSpin class="mr-2 w-4 h-4 animate-spin text-blue-500" /> 
                         <span v-if="currentActiveTask">{{ currentActiveTask.name }} ({{ currentActiveTask.progress }}%)...</span>
                         <span v-else>{{ generationState.details || 'Thinking...' }}</span>
                    </div>
                </div>

                <div class="flex items-center gap-1 pb-1 pr-1">
                    <button v-if="isSttConfigured" @click="toggleRecording" class="w-9 h-9 flex items-center justify-center hover:bg-gray-200 dark:hover:bg-gray-800 rounded-xl" :class="{'text-red-500 animate-pulse bg-red-50 dark:bg-red-900/20': isRecording, 'text-gray-500': !isRecording}"><IconMicrophone class="w-5.5 h-5.5" /></button>
                    <button v-if="!generationInProgress" @click="handleSendMessage" class="w-9 h-9 flex items-center justify-center bg-blue-600 hover:bg-blue-700 text-white rounded-xl shadow-sm transition-all active:scale-95">
                         <IconSend class="w-5 h-5" />
                    </button>
                    <button v-else @click="handleStopGeneration" class="w-9 h-9 flex items-center justify-center bg-red-500 hover:bg-red-600 text-white rounded-xl shadow-sm transition-all active:scale-95" title="Stop Generation">
                        <IconStopCircle class="w-5 h-5" />
                    </button>
                </div>
            </div>
            
            <p v-if="totalPercentage > 100" class="text-[10px] text-center text-red-500 font-black animate-pulse">CONTEXT LIMIT REACHED. PREVIOUS TURNS MAY BE LOST.</p>
        </div>
    </div>
</template>

<style scoped>
.tool-badge { @apply inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black border shadow-sm transition-all; }
.menu-item { @apply flex items-center w-full px-4 py-2.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left; }
.menu-divider { @apply my-1 border-t border-gray-100 dark:border-gray-700; }
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
.no-scrollbar::-webkit-scrollbar { display: none; }
textarea { scrollbar-width: thin; scrollbar-color: rgba(156, 163, 175, 0.5) transparent; }
</style>
