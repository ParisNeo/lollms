<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useDiscussionsStore } from '../../stores/discussions';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { usePromptsStore } from '../../stores/prompts';
import apiClient from '../../services/api';
import { storeToRefs } from 'pinia';

// UI Components
import MultiSelectMenu from '../ui/MultiSelectMenu.vue';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';
import DropdownSubmenu from '../ui/DropdownMenu/DropdownSubmenu.vue';

// Icon Components
import IconToken from '../../assets/icons/IconToken.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconMcp from '../../assets/icons/IconMcp.vue';
import IconDatabase from '../../assets/icons/IconDatabase.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconChevronDown from '../../assets/icons/IconChevronDown.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTicket from '../../assets/icons/IconTicket.vue';
import IconLollms from '../../assets/icons/IconLollms.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconUser from '../../assets/icons/IconUser.vue';
import IconDataZone from '../../assets/icons/IconDataZone.vue';

// CodeMirror imports
import { markdown } from '@codemirror/lang-markdown';
import { indentUnit } from '@codemirror/language';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView, keymap } from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import { defaultKeymap, indentWithTab } from '@codemirror/commands';

// Store initialization
const discussionsStore = useDiscussionsStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const promptsStore = usePromptsStore();
const router = useRouter();
const { dataZonesTokensFromContext, currentModelVisionSupport } = storeToRefs(discussionsStore);
const { lollmsPrompts, systemPromptsByZooCategory, userPromptsByCategory } = storeToRefs(promptsStore);

// Component state
const messageText = ref('');
const uploadedImages = ref([]);
const isUploading = ref(false);
const imageInput = ref(null);
const codeMirrorView = ref(null);
const isAdvancedMode = ref(false);
const cursorPositionToSet = ref(null);
const isRefreshingMcps = ref(false);
const isRefreshingRags = ref(false);
const inputTokenCount = ref(0);
const isTokenizingInput = ref(false);
let tokenizeInputDebounceTimer = null;

// UI state
const userPromptSearchTerm = ref('');
const zooPromptSearchTerm = ref('');
const showImagePreview = ref(true);
const textareaRef = ref(null);
const imageErrors = ref(new Set());

// Core computed properties
const user = computed(() => authStore.user);
const generationInProgress = computed(() => discussionsStore.generationInProgress);
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const availableRagStores = computed(() => dataStore.availableRagStores);
const availableMcpTools = computed(() => dataStore.availableMcpToolsForSelector);
const contextStatus = computed(() => discussionsStore.activeDiscussionContextStatus);

// Filtered prompts
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

// UI state computed
const isSendDisabled = computed(() => generationInProgress.value || (messageText.value.trim() === '' && uploadedImages.value.length === 0));
const hasActiveTools = computed(() => mcpToolSelection.value.length > 0 || ragStoreSelection.value.length > 0);
const inputPlaceholder = computed(() => {
    if (generationInProgress.value) return "Please wait for generation to complete...";
    return isAdvancedMode.value ? "Type your message... (Ctrl+Enter to send)" : "Type your message... (Shift+Enter for advanced editor)";
});
const showContextBar = computed(() => user.value?.show_token_counter && user.value?.user_ui_level >= 2 && contextStatus.value);

// Context calculations
const maxTokens = computed(() => contextStatus.value?.max_tokens || 1);
const systemPromptTokens = computed(() => contextStatus.value?.zones?.system_context?.breakdown?.system_prompt?.tokens || 0);
const dataZonesTokens = computed(() => dataZonesTokensFromContext.value);
const historyTextTokens = computed(() => contextStatus.value?.zones?.message_history?.breakdown?.text_tokens || 0);
const historyImageTokens = computed(() => contextStatus.value?.zones?.message_history?.breakdown?.image_tokens || 0);
const totalCurrentTokens = computed(() => systemPromptTokens.value + dataZonesTokens.value + historyTextTokens.value + historyImageTokens.value + inputTokenCount.value);

const getPercentage = (tokens) => maxTokens.value > 0 ? (tokens / maxTokens.value) * 100 : 0;

const contextParts = computed(() => {
    const parts = [];
    if (systemPromptTokens.value > 0) parts.push({ label: 'S', value: systemPromptTokens.value, title: 'System Prompt', colorClass: 'bg-blue-100 dark:bg-blue-900/50' });
    if (dataZonesTokens.value > 0) parts.push({ label: 'D', value: dataZonesTokens.value, title: 'Data Zones', colorClass: 'bg-yellow-100 dark:bg-yellow-900/50' });
    if (historyTextTokens.value > 0) parts.push({ label: 'H', value: historyTextTokens.value, title: 'History (Text)', colorClass: 'bg-green-100 dark:bg-green-900/50' });
    if (historyImageTokens.value > 0) parts.push({ label: 'I', value: historyImageTokens.value, title: 'History (Images)', colorClass: 'bg-teal-100 dark:bg-teal-900/50' });
    if (inputTokenCount.value > 0 || parts.length === 0) parts.push({ label: 'U', value: inputTokenCount.value, title: 'User Input', colorClass: 'bg-purple-100 dark:bg-purple-900/50' });
    return parts;
});

const systemPromptPercentage = computed(() => getPercentage(systemPromptTokens.value));
const dataZonesPercentage = computed(() => getPercentage(dataZonesTokens.value));
const historyTextPercentage = computed(() => getPercentage(historyTextTokens.value));
const historyImagePercentage = computed(() => getPercentage(historyImageTokens.value));
const inputTokensPercentage = computed(() => getPercentage(inputTokenCount.value));
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

// Tool selections
const ragStoreSelection = computed({
    get: () => activeDiscussion.value?.rag_datastore_ids || [],
    set(newIds) { if (activeDiscussion.value) discussionsStore.updateDiscussionRagStore({ discussionId: activeDiscussion.value.id, ragDatastoreIds: newIds }) }
});

const mcpToolSelection = computed({
    get: () => activeDiscussion.value?.active_tools || [],
    set(newIds) { if (activeDiscussion.value) discussionsStore.updateDiscussionMcps({ discussionId: activeDiscussion.value.id, mcp_tool_ids: newIds }) }
});

// Advanced editor extensions
const advancedEditorExtensions = computed(() => {
    const customKeymap = keymap.of([
        { key: 'Mod-Enter', run: () => { messageText.value = codeMirrorView.value.state.doc.toString(); handleSendMessage(); return true; }}, 
        indentWithTab 
    ]);
    const extensions = [EditorView.lineWrapping, EditorState.tabSize.of(2), indentUnit.of("  "), customKeymap, keymap.of(defaultKeymap), markdown()];
    if (uiStore.currentTheme === 'dark') extensions.push(oneDark);
    return extensions;
});

// Utility functions
function autoResizeTextarea() {
    if (!textareaRef.value) return;
    textareaRef.value.style.height = 'auto';
    textareaRef.value.style.height = Math.min(textareaRef.value.scrollHeight, 120) + 'px';
}

function focusInput() {
    nextTick(() => {
        if (isAdvancedMode.value && codeMirrorView.value) codeMirrorView.value.focus();
        else if (textareaRef.value) textareaRef.value.focus();
    });
}

// Core functions
function showContext() {
    if (activeDiscussion.value) uiStore.openModal('contextViewer');
}

// Token counting
async function fetchTokenCount(text) {
    if (isTokenizingInput.value) return;
    isTokenizingInput.value = true;
    try {
        const response = await apiClient.post('/api/discussions/tokenize', { text });
        inputTokenCount.value = response.data.tokens;
    } catch (error) {
        console.error("Tokenization failed:", error);
        inputTokenCount.value = 0;
    } finally {
        isTokenizingInput.value = false;
    }
}

// Refresh functions
async function refreshMcps() { 
    isRefreshingMcps.value = true; 
    try { await dataStore.refreshMcps(); } finally { isRefreshingMcps.value = false; } 
}

async function refreshRags() { 
    isRefreshingRags.value = true; 
    try { await dataStore.refreshRags(); } finally { isRefreshingRags.value = false; } 
}

// Prompt handling
function handlePromptSelection(promptContent) {
    const hasPlaceholders = /@<.*?>@/g.test(promptContent);
    if (hasPlaceholders) {
        uiStore.openModal('fillPlaceholders', {
            promptTemplate: promptContent,
            onConfirm: (filledPrompt) => {
                messageText.value = filledPrompt;
                if(isAdvancedMode.value && codeMirrorView.value) {
                    codeMirrorView.value.dispatch({
                        changes: { from: 0, to: codeMirrorView.value.state.doc.length, insert: filledPrompt }
                    });
                }
                focusInput();
            }
        });
    } else {
        messageText.value = promptContent;
        if(isAdvancedMode.value && codeMirrorView.value) {
            codeMirrorView.value.dispatch({
                changes: { from: 0, to: codeMirrorView.value.state.doc.length, insert: promptContent }
            });
            codeMirrorView.value.focus();
        } else {
            focusInput();
        }
    }
}

function manageMyPrompts() {
    router.push({ path: '/settings', query: { tab: 'prompts' } });
}

// Message handling
async function handleSendMessage() {
    if (isSendDisabled.value) return;
    try {
        await discussionsStore.sendMessage({
            prompt: messageText.value,
            image_server_paths: uploadedImages.value.map(img => img.server_path),
            localImageUrls: uploadedImages.value.map(img => img.local_url),
        });
        messageText.value = '';
        uploadedImages.value.forEach(img => URL.revokeObjectURL(img.local_url));
        uploadedImages.value = [];
        inputTokenCount.value = 0;
        imageErrors.value.clear();
        if (textareaRef.value) autoResizeTextarea();
    } catch (error) { 
        console.error(error)
        uiStore.addNotification('There was an error sending your message.', 'error'); 
    }
}

async function switchToAdvancedMode(event) {
    if (event?.target) cursorPositionToSet.value = event.target.selectionStart;
    isAdvancedMode.value = true;
    await nextTick();
}

function handleEditorReady(payload) {
    codeMirrorView.value = payload.view;
    if (cursorPositionToSet.value !== null) {
        const pos = Math.min(cursorPositionToSet.value, payload.view.state.doc.length);
        payload.view.dispatch({ selection: { anchor: pos, head: pos } });
        cursorPositionToSet.value = null;
    }
    payload.view.focus();
}

// Image handling
function triggerImageUpload() { imageInput.value.click(); }

async function uploadFiles(files) {
    if (files.length === 0) return;
    if (uploadedImages.value.length + files.length > 5) { 
        uiStore.addNotification('You can upload a maximum of 5 images.', 'warning'); 
        return; 
    }
    
    const maxSize = 10 * 1024 * 1024; // 10MB
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
    const validFiles = [];
    
    for (const file of files) {
        if (!allowedTypes.includes(file.type)) {
            uiStore.addNotification(`File ${file.name} is not a supported image format.`, 'warning');
            continue;
        }
        if (file.size > maxSize) {
            uiStore.addNotification(`File ${file.name} is too large (max 10MB).`, 'warning');
            continue;
        }
        validFiles.push(file);
    }
    
    if (validFiles.length === 0) return;
    
    isUploading.value = true;
    const formData = new FormData();
    validFiles.forEach(file => formData.append('files', file));
    
    try {
        const response = await apiClient.post('/api/upload/chat_image', formData);
        const newImages = [];
        
        response.data.forEach(imgInfo => {
            if (imgInfo.server_path && imgInfo.filename) {
                const originalFile = validFiles.find(f => f.name === imgInfo.filename);
                if(originalFile) {
                    newImages.push({ 
                        server_path: imgInfo.server_path, 
                        local_url: URL.createObjectURL(originalFile), 
                        file: originalFile 
                    });
                } else {
                    console.warn(`Original file not found for ${imgInfo.filename}`);
                }
            } else {
                console.warn('Invalid image info received:', imgInfo);
            }
        });
        
        uploadedImages.value = [...uploadedImages.value, ...newImages];
        
        const failedCount = validFiles.length - newImages.length;
        if (failedCount > 0) {
            uiStore.addNotification(`${newImages.length} images uploaded successfully, ${failedCount} failed.`, 'warning');
        } else {
            uiStore.addNotification(`${newImages.length} image(s) uploaded successfully.`, 'success');
        }
        
    } catch (error) { 
        console.error('Image upload error:', error);
        uiStore.addNotification(`Image upload failed: ${error.message}`, 'error'); 
    } finally { 
        isUploading.value = false; 
    }
}

async function handleImageSelection(event) { 
    await uploadFiles(Array.from(event.target.files)); 
    event.target.value = ''; 
}

async function handlePaste(event) {
    if (!currentModelVisionSupport.value) return;
    const items = (event.clipboardData || window.clipboardData).items;
    if (!items) return;
    const imageFiles = [];
    for (const item of items) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
            const file = item.getAsFile();
            if (file) {
                const extension = (file.type.split('/')[1] || 'png').toLowerCase().replace('jpeg', 'jpg');
                imageFiles.push(new File([file], `pasted_image_${Date.now()}.${extension}`, { type: file.type }));
            }
        }
    }
    if (imageFiles.length > 0) { 
        event.preventDefault(); 
        await uploadFiles(imageFiles); 
    }
}

function removeImage(index) { 
    const image = uploadedImages.value[index];
    if (image?.local_url) URL.revokeObjectURL(image.local_url);
    uploadedImages.value.splice(index, 1);
    imageErrors.value.delete(index);
    // Reindex error set
    const newErrors = new Set();
    imageErrors.value.forEach(errorIndex => {
        if (errorIndex > index) newErrors.add(errorIndex - 1);
        else if (errorIndex < index) newErrors.add(errorIndex);
    });
    imageErrors.value = newErrors;
}

function handleImageError(index, event) {
    console.error('Image failed to load:', uploadedImages.value[index]);
    imageErrors.value.add(index);
    imageErrors.value = new Set(imageErrors.value);
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.metaKey) {
        event.preventDefault();
        handleSendMessage();
    } else if (event.key === 'Enter' && event.shiftKey) {
        event.preventDefault();
        switchToAdvancedMode(event);
    }
}

// Watchers
watch(messageText, (newValue) => {
    clearTimeout(tokenizeInputDebounceTimer);
    if (!newValue.trim()) {
        inputTokenCount.value = 0;
    } else if (showContextBar.value) {
        tokenizeInputDebounceTimer = setTimeout(() => fetchTokenCount(newValue), 500);
    }
    if (!isAdvancedMode.value) nextTick(() => autoResizeTextarea());
});

watch(activeDiscussion, () => {
    clearTimeout(tokenizeInputDebounceTimer);
    inputTokenCount.value = 0;
    isAdvancedMode.value = false;
}, { immediate: true });

// Lifecycle
onMounted(() => {
    promptsStore.fetchPrompts();
});

onUnmounted(() => {
    clearTimeout(tokenizeInputDebounceTimer);
    uploadedImages.value.forEach(img => { if (img.local_url) URL.revokeObjectURL(img.local_url); });
});
</script>
<template>
    <div class="flex-shrink-0 bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm p-2 sm:p-4 border-t dark:border-gray-700" :onpaste="currentModelVisionSupport ? handlePaste : null">
        <div class="w-full max-w-4xl mx-auto">
            <!-- Context Bar -->
            <div v-if="showContextBar" class="px-1 pb-2 relative group">
                <div class="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400 font-mono">
                    <div class="flex items-center gap-1.5 flex-shrink-0">
                        <IconToken class="w-4 h-4 flex-shrink-0" />
                        <button @click="showContext" class="cursor-pointer hover:underline flex-shrink-0" title="View full context breakdown">Context:</button>
                    </div>
                    <div class="flex-grow w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 relative overflow-hidden border transition-colors duration-300" :class="progressBorderColorClass">
                        <div class="progress-segment bg-blue-500" :style="{ width: `${systemPromptPercentage}%` }" :title="`System Prompt: ${systemPromptTokens.toLocaleString()} tokens`"></div>
                        <div class="progress-segment bg-yellow-500" :style="{ left: `${systemPromptPercentage}%`, width: `${dataZonesPercentage}%` }" :title="`Data Zones: ${dataZonesTokens.toLocaleString()} tokens`"></div>
                        <div class="progress-segment bg-green-500" :style="{ left: `${systemPromptPercentage + dataZonesPercentage}%`, width: `${historyTextPercentage}%` }" :title="`History (Text): ${historyTextTokens.toLocaleString()} tokens`"></div>
                        <div class="progress-segment bg-teal-500" :style="{ left: `${systemPromptPercentage + dataZonesPercentage + historyTextPercentage}%`, width: `${historyImagePercentage}%` }" :title="`History (Images): ${historyImageTokens.toLocaleString()} tokens`"></div>
                        <div class="progress-segment bg-purple-500" :style="{ left: `${systemPromptPercentage + dataZonesPercentage + historyTextPercentage + historyImagePercentage}%`, width: `${inputTokensPercentage}%` }" :title="`Current Input: ${inputTokenCount.toLocaleString()} tokens`"></div>
                    </div>
                    <span class="flex-shrink-0 pl-2">{{ totalCurrentTokens.toLocaleString() }} / {{ maxTokens.toLocaleString() }}</span>
                </div>
                <p v-if="showContextWarning" class="mt-1.5 text-xs text-center" :class="totalPercentage > 100 ? 'text-red-600 dark:text-red-400' : 'text-yellow-600 dark:text-yellow-400'">{{ contextWarningMessage }}</p>
                <div class="absolute bottom-full left-0 mb-2 w-auto p-2 bg-white dark:bg-gray-900 border dark:border-gray-600 rounded-lg shadow-lg text-xs opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-10">
                    <h4 class="font-bold mb-1 whitespace-nowrap">Context Breakdown</h4>
                    <div class="flex flex-wrap gap-1">
                        <template v-for="part in contextParts">
                            <span :title="`${part.title}: ${part.value.toLocaleString()} tokens`" class="px-1.5 py-0.5 rounded" :class="part.colorClass">{{ part.label }}: {{ part.value.toLocaleString() }}</span>
                        </template>
                    </div>
                </div>
            </div>
            
            <!-- Image Preview -->
            <div v-if="uploadedImages.length > 0 || isUploading" class="mb-2 p-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md">
                <div class="flex flex-wrap gap-2">
                    <div v-for="(image, index) in uploadedImages" :key="`img-${image.server_path}-${index}`" class="relative w-14 h-14 sm:w-16 sm:h-16">
                        <img v-if="!imageErrors.has(index)" :src="image.local_url" @error="handleImageError(index, $event)" @load="console.log('Image loaded:', image.server_path)" class="w-full h-full object-cover rounded-md" alt="Image preview" />
                        <div v-else class="w-full h-full bg-gray-200 dark:bg-gray-700 rounded-md flex items-center justify-center">
                            <span class="text-xs text-gray-500">Failed</span>
                        </div>
                        <button @click="removeImage(index)" class="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold leading-none">×</button>
                    </div>
                    <div v-if="isUploading" class="w-14 h-14 sm:w-16 sm:h-16 bg-gray-200 dark:bg-gray-700 rounded-md flex items-center justify-center">
                        <IconAnimateSpin class="h-6 w-6 text-gray-500 animate-spin" />
                    </div>
                </div>
            </div>
                
            <input type="file" ref="imageInput" @change="handleImageSelection" multiple accept="image/*" class="hidden">
            
            <!-- Generation Progress -->
            <div v-if="generationInProgress" class="flex flex-row items-center justify-between p-2 h-[60px]">
                <div class="flex items-center space-x-3">
                    <IconAnimateSpin class="h-6 w-6 text-blue-500 animate-spin" />
                    <p class="text-sm font-semibold text-gray-600 dark:text-gray-300">Working...</p>
                </div>
                <button @click="discussionsStore.stopGeneration" class="btn btn-danger !py-1 !px-3">Stop Generation</button>
            </div>
            
            <!-- Main Interface -->
            <div v-else class="flex items-start gap-2">
                <!-- Action Buttons -->
                <div class="flex flex-shrink-0 gap-1 sm:gap-2 pt-1.5">
                    <button v-if="currentModelVisionSupport" @click="triggerImageUpload" :disabled="isUploading" class="btn btn-secondary chat-action-button disabled:opacity-50" title="Upload Images">
                        <IconPhoto class="w-5 h-5"/>
                    </button>
                    
                    <div v-if="user.user_ui_level >= 3">
                        <MultiSelectMenu v-model="mcpToolSelection" :items="availableMcpTools" placeholder="MCP Tools" activeClass="!bg-purple-600 !text-white" inactiveClass="btn-secondary">
                            <template #button="{ toggle, selected, activeClass, inactiveClass }">
                                <button type="button" @click="toggle" :class="[selected.length > 0 ? activeClass : inactiveClass]" class="relative btn chat-action-button" title="Select MCP Tools">
                                    <IconMcp class="w-5 h-5"/>
                                    <span v-if="selected.length > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-purple-800 rounded-full">{{ selected.length }}</span>
                                </button>
                            </template>
                            <template #footer>
                                <div class="p-2">
                                    <button @click="refreshMcps" :disabled="isRefreshingMcps" class="w-full btn btn-secondary text-sm !justify-center">
                                        <IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isRefreshingMcps}"/>
                                        <span>{{ isRefreshingMcps ? 'Refreshing...' : 'Refresh Tools' }}</span>
                                    </button>
                                </div>
                            </template>
                        </MultiSelectMenu>
                    </div>
                    
                    <div v-if="user.user_ui_level >= 1">
                        <MultiSelectMenu v-model="ragStoreSelection" :items="availableRagStores" placeholder="RAG Stores" activeClass="!bg-green-600 !text-white" inactiveClass="btn-secondary">
                            <template #button="{ toggle, selected, activeClass, inactiveClass }">
                                <button type="button" @click="toggle" :class="[selected.length > 0 ? activeClass : inactiveClass]" class="relative btn chat-action-button" title="Select RAG Store">
                                    <IconDatabase class="w-5 h-5" />
                                    <span v-if="selected.length > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-green-800 rounded-full">{{ selected.length }}</span>
                                </button>
                            </template>
                            <template #footer>
                                <div class="p-2">
                                    <button @click="refreshRags" :disabled="isRefreshingRags" class="w-full btn btn-secondary text-sm !justify-center">
                                        <IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isRefreshingRags}"/>
                                        <span>{{ isRefreshingRags ? 'Refreshing...' : 'Refresh Stores' }}</span>
                                    </button>
                                </div>
                            </template>
                        </MultiSelectMenu>
                    </div>
                    
                    <DropdownMenu title="Prompts" icon="ticket" collection="ui" button-class="btn btn-secondary chat-action-button">
                        <DropdownSubmenu v-if="filteredLollmsPrompts.length > 0" title="Default" icon="lollms" collection="ui">
                            <button v-for="p in filteredLollmsPrompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm">
                                <span class="truncate">{{ p.name }}</span>
                            </button>
                        </DropdownSubmenu>
                        <DropdownSubmenu v-if="Object.keys(userPromptsByCategory).length > 0" title="User" icon="user" collection="ui">
                            <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10">
                                <input type="text" v-model="userPromptSearchTerm" @click.stop placeholder="Search user prompts..." class="input-field w-full text-sm">
                            </div>
                            <div class="max-h-60 overflow-y-auto">
                                <div v-for="(prompts, category) in filteredUserPromptsByCategory" :key="category">
                                    <h3 class="category-header">{{ category }}</h3>
                                    <button v-for="p in prompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm">
                                        <img v-if="p.icon" :src="p.icon" class="h-5 w-5 rounded-md object-cover mr-2 flex-shrink-0" alt="Icon">
                                        <IconTicket v-else class="h-5 w-5 mr-2 flex-shrink-0 text-gray-400" />
                                        <span class="truncate">{{ p.name }}</span>
                                    </button>
                                </div>
                                <div v-if="Object.keys(filteredUserPromptsByCategory).length === 0" class="px-3 py-2 text-sm text-gray-500 italic">No matching prompts.</div>
                            </div>
                        </DropdownSubmenu>
                        <DropdownSubmenu v-if="Object.keys(systemPromptsByZooCategory).length > 0" title="Zoo" icon="server" collection="ui">
                            <div class="p-2 sticky top-0 bg-white dark:bg-gray-800 z-10">
                                <input type="text" v-model="zooPromptSearchTerm" @click.stop placeholder="Search zoo..." class="input-field w-full text-sm">
                            </div>
                            <div class="max-h-60 overflow-y-auto">
                                <div v-for="(prompts, category) in filteredSystemPromptsByZooCategory" :key="category">
                                    <h3 class="category-header">{{ category }}</h3>
                                    <button v-for="p in prompts" :key="p.id" @click="handlePromptSelection(p.content)" class="menu-item text-sm">
                                        <img v-if="p.icon" :src="p.icon" class="h-5 w-5 rounded-md object-cover mr-2 flex-shrink-0" alt="Icon">
                                        <span class="truncate">{{ p.name }}</span>
                                    </button>
                                </div>
                                <div v-if="Object.keys(filteredSystemPromptsByZooCategory).length === 0" class="px-3 py-2 text-sm text-gray-500 italic">No matching prompts.</div>
                            </div>
                        </DropdownSubmenu>
                        <div class="my-1 border-t dark:border-gray-600"></div>
                        <button @click="manageMyPrompts" class="menu-item text-sm font-medium text-blue-600 dark:text-blue-400">Manage My Prompts...</button>
                    </DropdownMenu>
                </div>
                
                <!-- Input Area -->
                <div class="flex-1 min-w-0">
                    <div v-if="!isAdvancedMode">
                        <textarea ref="textareaRef" v-model="messageText" @keydown="handleKeyDown" :placeholder="inputPlaceholder" rows="1" class="simple-chat-input"></textarea>
                    </div>
                    <div v-else class="flex-1 flex flex-col min-h-0">
                        <CodeMirrorEditor class="flex-grow min-h-0" v-model="messageText" :placeholder="inputPlaceholder" :style="{ maxHeight: '200px' }" :autofocus="true" :extensions="advancedEditorExtensions" @ready="handleEditorReady" />
                        <div class="flex justify-end mt-2">
                            <button @click="isAdvancedMode = false" class="btn btn-secondary !p-2" title="Switch to Simple Input">
                                <IconChevronDown class="w-5 h-5" />
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Send Button -->
                <div class="flex-shrink-0 pt-1.5">
                    <button @click="handleSendMessage" :disabled="isSendDisabled" class="btn btn-primary chat-action-button" title="Send Message (Enter or Ctrl+Enter)">
                        <IconSend class="w-5 h-5"/>
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>