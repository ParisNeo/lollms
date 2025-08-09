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
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import DropdownMenu from '../ui/DropdownMenu.vue';
import DropdownSubmenu from '../ui/DropdownSubmenu.vue';

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

// CodeMirror imports
import { markdown } from '@codemirror/lang-markdown';
import { indentUnit } from '@codemirror/language';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView, keymap } from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import { defaultKeymap, indentWithTab } from '@codemirror/commands';

const discussionsStore = useDiscussionsStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const promptsStore = usePromptsStore();
const router = useRouter();
const { dataZonesTokensFromContext, currentModelVisionSupport } = storeToRefs(discussionsStore);
const { lollmsPrompts, systemPromptsByZooCategory, userPromptsByCategory } = storeToRefs(promptsStore);

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

const isShrunk = ref(false);
const chatbarRef = ref(null);
const isDragging = ref(false);
const isPositionModified = ref(false);
const startDragPos = ref({ x: 0, y: 0 });
const startChatboxPos = ref({ x: 0, y: 0 });
const currentChatboxPos = ref(null);

const userPromptSearchTerm = ref('');
const zooPromptSearchTerm = ref('');

const user = computed(() => authStore.user);
const generationInProgress = computed(() => discussionsStore.generationInProgress);
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const availableRagStores = computed(() => dataStore.availableRagStores);
const availableMcpTools = computed(() => dataStore.availableMcpToolsForSelector);
const contextStatus = computed(() => discussionsStore.activeDiscussionContextStatus);

const filteredLollmsPrompts = computed(() => {
    if (!Array.isArray(lollmsPrompts.value)) return [];
    const term = userPromptSearchTerm.value.toLowerCase(); // Share search with user prompts for simplicity
    if (!term) return lollmsPrompts.value;
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

const isSendDisabled = computed(() => {
  return generationInProgress.value || (messageText.value.trim() === '' && uploadedImages.value.length === 0);
});

const showContextBar = computed(() => {
    if (!user.value || !contextStatus.value) return false;
    return user.value.show_token_counter && user.value.user_ui_level >= 2;
});

const maxTokens = computed(() => contextStatus.value?.max_tokens || 1);
const systemPromptTokens = computed(() => contextStatus.value?.zones?.system_context?.breakdown?.system_prompt?.tokens || 0);
const dataZonesTokens = computed(() => dataZonesTokensFromContext.value);
const historyTextTokens = computed(() => contextStatus.value?.zones?.message_history?.breakdown?.text_tokens || 0);
const historyImageTokens = computed(() => contextStatus.value?.zones?.message_history?.breakdown?.image_tokens || 0);

const totalCurrentTokens = computed(() => systemPromptTokens.value + dataZonesTokens.value + historyTextTokens.value + historyImageTokens.value + inputTokenCount.value);

const getPercentage = (tokens) => {
    if (maxTokens.value <= 0) return 0;
    return (tokens / maxTokens.value) * 100;
};

const contextParts = computed(() => {
    const parts = [];
    if (systemPromptTokens.value > 0) {
        parts.push({ label: 'S', value: systemPromptTokens.value, title: 'System Prompt', colorClass: 'bg-blue-100 dark:bg-blue-900/50' });
    }
    if (dataZonesTokens.value > 0) {
        parts.push({ label: 'D', value: dataZonesTokens.value, title: 'Data Zones', colorClass: 'bg-yellow-100 dark:bg-yellow-900/50' });
    }
    if (historyTextTokens.value > 0) {
        parts.push({ label: 'H', value: historyTextTokens.value, title: 'History (Text)', colorClass: 'bg-green-100 dark:bg-green-900/50' });
    }
    if (historyImageTokens.value > 0) {
        parts.push({ label: 'I', value: historyImageTokens.value, title: 'History (Images)', colorClass: 'bg-teal-100 dark:bg-teal-900/50' });
    }
    if (inputTokenCount.value > 0 || parts.length === 0) {
        parts.push({ label: 'U', value: inputTokenCount.value, title: 'User Input', colorClass: 'bg-purple-100 dark:bg-purple-900/50' });
    }
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
    if (percentage >= 90) return 'border-red-500 dark:border-red-400';
    if (percentage >= 75) return 'border-yellow-500 dark:border-yellow-400';
    return 'border-gray-300 dark:border-gray-600';
});

const showContextWarning = computed(() => totalPercentage.value > 90);
const contextWarningMessage = computed(() => {
    if (totalPercentage.value > 100) return "Context limit exceeded! The model may not see all of your message.";
    if (totalPercentage.value > 90) return "You are approaching the context limit. Consider shortening your message or data zones.";
    return "";
});

function showContext() {
    if (!activeDiscussion.value) return;
    uiStore.openModal('contextViewer');
}

const headerTitle = computed(() => activeDiscussion.value?.title || "New Chat");
const chatbarStyle = computed(() => {
    if (isPositionModified.value && currentChatboxPos.value) return { left: `${currentChatboxPos.value.x}px`, top: `${currentChatboxPos.value.y}px`, bottom: 'auto', transform: 'none' };
    return { left: '50%', bottom: '1rem', transform: 'translateX(-50%)' };
});

function clampPosition(x, y) {
    const el = chatbarRef.value;
    if (!el) return { x, y };
    const maxX = window.innerWidth - el.offsetWidth;
    const maxY = window.innerHeight - el.offsetHeight;
    return { x: Math.max(0, Math.min(x, maxX)), y: Math.max(0, Math.min(y, maxY)) };
}

function toggleShrink() {
    isShrunk.value = !isShrunk.value;
    localStorage.setItem('lollms_chatbarShrunk', JSON.stringify(isShrunk.value));
}

function onMouseDown(event) {
    if (event.button !== 0 || isShrunk.value) return;
    isDragging.value = true;
    document.body.style.userSelect = 'none';
    startDragPos.value = { x: event.clientX, y: event.clientY };
    const el = chatbarRef.value;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (!isPositionModified.value) {
        isPositionModified.value = true;
        currentChatboxPos.value = { x: rect.left, y: rect.top };
    }
    startChatboxPos.value = { ...currentChatboxPos.value };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
}

function onMouseMove(event) {
    if (!isDragging.value) return;
    event.preventDefault();
    const dx = event.clientX - startDragPos.value.x;
    const dy = event.clientY - startDragPos.value.y;
    currentChatboxPos.value = clampPosition(startChatboxPos.value.x + dx, startChatboxPos.value.y + dy);
}

function onMouseUp() {
    isDragging.value = false;
    document.body.style.userSelect = '';
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
    if (isPositionModified.value && currentChatboxPos.value) {
        currentChatboxPos.value = clampPosition(currentChatboxPos.value.x, currentChatboxPos.value.y);
        localStorage.setItem('lollms_chatbarPosition', JSON.stringify(currentChatboxPos.value));
        localStorage.setItem('lollms_chatbarPositionModified', 'true');
    }
}

function handleResize() {
    if (isPositionModified.value && currentChatboxPos.value) {
        currentChatboxPos.value = clampPosition(currentChatboxPos.value.x, currentChatboxPos.value.y);
    }
}

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

watch(messageText, (newValue) => {
    clearTimeout(tokenizeInputDebounceTimer);
    if (!newValue.trim()) {
        inputTokenCount.value = 0;
    } else if (showContextBar.value) {
        tokenizeInputDebounceTimer = setTimeout(() => {
            fetchTokenCount(newValue);
        }, 500);
    }
});

watch(activeDiscussion, () => {
    clearTimeout(tokenizeInputDebounceTimer);
    inputTokenCount.value = 0;
});

onMounted(() => {
    promptsStore.fetchPrompts();
    const storedShrunk = localStorage.getItem('lollms_chatbarShrunk');
    if (storedShrunk) isShrunk.value = JSON.parse(storedShrunk);
    const storedPosModified = localStorage.getItem('lollms_chatbarPositionModified');
    const storedPos = localStorage.getItem('lollms_chatbarPosition');
    if (storedPosModified === 'true' && storedPos) {
        isPositionModified.value = true;
        currentChatboxPos.value = JSON.parse(storedPos);
        handleResize();
    }
    window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
    window.removeEventListener('resize', handleResize);
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
    clearTimeout(tokenizeInputDebounceTimer);
});

const ragStoreSelection = computed({
    get: () => activeDiscussion.value?.rag_datastore_ids || [],
    set(newIds) { if (activeDiscussion.value) discussionsStore.updateDiscussionRagStore({ discussionId: activeDiscussion.value.id, ragDatastoreIds: newIds }) }
});

const mcpToolSelection = computed({
    get: () => activeDiscussion.value?.active_tools || [],
    set(newIds) { if (activeDiscussion.value) discussionsStore.updateDiscussionMcps({ discussionId: activeDiscussion.value.id, mcp_tool_ids: newIds }) }
});

watch(activeDiscussion, (newDiscussion) => {
    isAdvancedMode.value = false;
    if (newDiscussion && !isPositionModified.value) currentChatboxPos.value = null;
}, { immediate: true });

async function refreshMcps() { isRefreshingMcps.value = true; try { await dataStore.refreshMcps(); } finally { isRefreshingMcps.value = false; } }
async function refreshRags() { isRefreshingRags.value = true; try { await dataStore.refreshRags(); } finally { isRefreshingRags.value = false; } }

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
            }
        });
    } else {
        messageText.value = promptContent;
        if(isAdvancedMode.value && codeMirrorView.value) {
            codeMirrorView.value.dispatch({
                changes: { from: 0, to: codeMirrorView.value.state.doc.length, insert: promptContent }
            });
            codeMirrorView.value.focus();
        }
    }
}

function manageMyPrompts() {
    router.push({ path: '/settings', query: { tab: 'prompts' } });
}

async function handleSendMessage() {
    if (isSendDisabled.value) return;
    try {
        await discussionsStore.sendMessage({
            prompt: messageText.value,
            image_server_paths: uploadedImages.value.map(img => img.server_path),
            localImageUrls: uploadedImages.value.map(img => img.local_url),
        });
        messageText.value = '';
        uploadedImages.value = [];
        inputTokenCount.value = 0;
    } catch (error) { uiStore.addNotification('There was an error sending your message.', 'error'); }
}

async function switchToAdvancedMode(event) {
    if (event?.target) cursorPositionToSet.value = event.target.selectionStart;
    isAdvancedMode.value = true;
    await nextTick();
}

const advancedEditorExtensions = computed(() => {
    const customKeymap = keymap.of([{ key: 'Mod-Enter', run: () => { messageText.value = codeMirrorView.value.state.doc.toString(); handleSendMessage(); return true; }}, indentWithTab ]);
    const extensions = [EditorView.lineWrapping, EditorState.tabSize.of(2), indentUnit.of("  "), customKeymap, keymap.of(defaultKeymap), markdown()];
    if (uiStore.currentTheme === 'dark') extensions.push(oneDark);
    return extensions;
});

function handleEditorReady(payload) {
    codeMirrorView.value = payload.view;
    if (cursorPositionToSet.value !== null) {
        const pos = Math.min(cursorPositionToSet.value, payload.view.state.doc.length);
        payload.view.dispatch({ selection: { anchor: pos, head: pos } });
        cursorPositionToSet.value = null;
    }
    payload.view.focus();
}

function triggerImageUpload() { imageInput.value.click(); }

async function uploadFiles(files) {
    if (files.length === 0) return;
    if (uploadedImages.value.length + files.length > 5) { uiStore.addNotification('You can upload a maximum of 5 images.', 'warning'); return; }
    isUploading.value = true;
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    try {
        const response = await apiClient.post('/api/upload/chat_image', formData);
        response.data.forEach(imgInfo => {
            const originalFile = files.find(f => f.name === imgInfo.filename);
            if(originalFile) uploadedImages.value.push({ server_path: imgInfo.server_path, local_url: URL.createObjectURL(originalFile), file: originalFile });
        });
        uiStore.addNotification(`${files.length} image(s) uploaded.`, 'success');
    } catch (error) { uiStore.addNotification('Image upload failed.', 'error'); }
    finally { isUploading.value = false; }
}

async function handleImageSelection(event) { await uploadFiles(Array.from(event.target.files)); event.target.value = ''; }

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
    if (imageFiles.length > 0) { event.preventDefault(); await uploadFiles(imageFiles); }
}

function removeImage(index) { URL.revokeObjectURL(uploadedImages.value[index].local_url); uploadedImages.value.splice(index, 1); }
</script>

<template>
  <div>
    <Transition enter-active-class="transition ease-out duration-300" enter-from-class="transform opacity-0 scale-50" enter-to-class="transform opacity-100 scale-100" leave-active-class="transition ease-in duration-200" leave-from-class="transform opacity-100 scale-100" leave-to-class="transform opacity-0 scale-50">
      <button v-if="isShrunk" @click="toggleShrink" class="fixed bottom-4 right-4 z-[60] p-3 bg-blue-500 dark:bg-blue-600 text-white rounded-full shadow-lg hover:bg-blue-600 dark:hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-400 dark:focus:ring-offset-gray-900" title="Expand Chat"><svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2-2h-5l-5 5v-5z" /></svg></button>
    </Transition>

    <Transition enter-active-class="transition ease-out duration-300" enter-from-class="transform opacity-0 scale-95 translate-y-4" enter-to-class="transform opacity-100 scale-100 translate-y-0" leave-active-class="transition ease-in duration-200" leave-from-class="transform opacity-100 scale-100 translate-y-0" leave-to-class="transform opacity-0 scale-95 translate-y-4">
      <div v-if="!isShrunk" ref="chatbarRef" :style="chatbarStyle" :onpaste="currentModelVisionSupport ? handlePaste : null" class="fixed w-11/12 max-w-4xl bg-white/80 dark:bg-gray-800/80 backdrop-blur-md rounded-xl border border-gray-300 dark:border-gray-700 shadow-2xl transition-shadow z-50" :class="{'cursor-grabbing': isDragging}">
        <div @mousedown.prevent="onMouseDown" class="flex items-center justify-between h-10 px-4 border-b border-gray-200 dark:border-gray-700 rounded-t-xl" :class="isDragging ? 'cursor-grabbing' : 'cursor-grab'">
            <h3 class="text-sm font-semibold truncate text-gray-800 dark:text-gray-100 select-none">{{ headerTitle }}</h3>
            <button @click.stop="toggleShrink" @mousedown.stop class="p-1 rounded-full text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-600" title="Shrink Chat"><svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M18 12H6" /></svg></button>
        </div>

        <div class="p-3" @mousedown.stop>
            <div v-if="showContextBar" class="px-1 pb-2">
                <div class="flex justify-between items-center mb-1 text-xs text-gray-600 dark:text-gray-400 font-mono">
                    <div class="flex items-center gap-1.5">
                        <IconToken class="w-4 h-4 flex-shrink-0" />
                        <button @click="showContext" class="cursor-pointer hover:underline flex-shrink-0" title="View full context breakdown">Context:</button>
                        <div class="flex items-center gap-x-1 text-xs truncate min-w-0">
                            <template v-for="(part, index) in contextParts" :key="part.label">
                                <span :title="`${part.title}: ${part.value.toLocaleString()} tokens`" class="px-1 py-0.5 rounded" :class="part.colorClass">{{ part.label }}:{{ part.value.toLocaleString() }}</span>
                                <span v-if="index < contextParts.length - 1" class="opacity-50 mx-0.5">+</span>
                            </template>
                        </div>
                    </div>
                    <span>{{ totalCurrentTokens.toLocaleString() }} / {{ maxTokens.toLocaleString() }}</span>
                </div>
                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 relative overflow-hidden border transition-colors duration-300" :class="progressBorderColorClass">
                    <div class="progress-segment bg-blue-500" :style="{ width: `${systemPromptPercentage}%` }" :title="`System Prompt: ${systemPromptTokens.toLocaleString()} tokens`"></div>
                    <div class="progress-segment bg-yellow-500" :style="{ left: `${systemPromptPercentage}%`, width: `${dataZonesPercentage}%` }" :title="`Data Zones: ${dataZonesTokens.toLocaleString()} tokens`"></div>
                    <div class="progress-segment bg-green-500" :style="{ left: `${systemPromptPercentage + dataZonesPercentage}%`, width: `${historyTextPercentage}%` }" :title="`History (Text): ${historyTextTokens.toLocaleString()} tokens`"></div>
                    <div class="progress-segment bg-teal-500" :style="{ left: `${systemPromptPercentage + dataZonesPercentage + historyTextPercentage}%`, width: `${historyImagePercentage}%` }" :title="`History (Images): ${historyImageTokens.toLocaleString()} tokens`"></div>
                    <div class="progress-segment bg-purple-500" :style="{ left: `${systemPromptPercentage + dataZonesPercentage + historyTextPercentage + historyImagePercentage}%`, width: `${inputTokensPercentage}%` }" :title="`Current Input: ${inputTokenCount.toLocaleString()} tokens`"></div>
                </div>
                <p v-if="showContextWarning" class="mt-1.5 text-xs text-center" :class="totalPercentage > 100 ? 'text-red-600 dark:text-red-400' : 'text-yellow-600 dark:text-yellow-400'">{{ contextWarningMessage }}</p>
            </div>
            
            <div>
                <div v-if="uploadedImages.length > 0 || isUploading" class="mb-2 p-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md"><div class="flex flex-wrap gap-2">
                    <div v-for="(image, index) in uploadedImages" :key="image.server_path" class="relative w-16 h-16"><img :src="image.local_url" class="w-full h-full object-cover rounded-md" alt="Image preview" /><button @click="removeImage(index)" class="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold leading-none">×</button></div>
                    <div v-if="isUploading" class="w-16 h-16 bg-gray-200 dark:bg-gray-700 rounded-md flex items-center justify-center"><IconAnimateSpin class="h-6 w-6 text-gray-500 animate-spin" /></div>
                </div></div>
                <input type="file" ref="imageInput" @change="handleImageSelection" multiple accept="image/*" class="hidden">
                <div v-if="generationInProgress" class="flex flex-row items-center justify-between p-2 h-[60px]"><div class="flex items-center space-x-3"><IconAnimateSpin class="h-6 w-6 text-blue-500 animate-spin" /><p class="text-sm font-semibold text-gray-600 dark:text-gray-300">Working...</p></div><button @click="discussionsStore.stopGeneration" class="btn btn-danger !py-1 !px-3">Stop Generation</button></div>
                <div v-else class="flex items-center gap-2">
                    <!-- Action Buttons -->
                    <div class="flex flex-shrink-0 gap-2">
                        <button v-if="currentModelVisionSupport" @click="triggerImageUpload" :disabled="isUploading" class="btn btn-secondary chat-action-button disabled:opacity-50" title="Upload Images"><IconPhoto class="w-5 h-5"/></button>
                        <div v-if="user.user_ui_level >= 3"><MultiSelectMenu v-model="mcpToolSelection" :items="availableMcpTools" placeholder="MCP Tools" activeClass="!bg-purple-600 !text-white" inactiveClass="btn-secondary"><template #button="{ toggle, selected, activeClass, inactiveClass }"><button type="button" @click="toggle" :class="[selected.length > 0 ? activeClass : inactiveClass]" class="relative btn chat-action-button" title="Select MCP Tools"><IconMcp class="w-5 h-5"/><span v-if="selected.length > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-purple-800 rounded-full">{{ selected.length }}</span></button></template><template #footer><div class="p-2"><button @click="refreshMcps" :disabled="isRefreshingMcps" class="w-full btn btn-secondary text-sm !justify-center"><IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isRefreshingMcps}"/><span>{{ isRefreshingMcps ? 'Refreshing...' : 'Refresh Tools' }}</span></button></div></template></MultiSelectMenu></div>
                        <div v-if="user.user_ui_level >= 1"><MultiSelectMenu v-model="ragStoreSelection" :items="availableRagStores" placeholder="RAG Stores" activeClass="!bg-green-600 !text-white" inactiveClass="btn-secondary"><template #button="{ toggle, selected, activeClass, inactiveClass }"><button type="button" @click="toggle" :class="[selected.length > 0 ? activeClass : inactiveClass]" class="relative btn chat-action-button" title="Select RAG Store"><IconDatabase class="w-5 h-5" /><span v-if="selected.length > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-green-800 rounded-full">{{ selected.length }}</span></button></template><template #footer><div class="p-2"><button @click="refreshRags" :disabled="isRefreshingRags" class="w-full btn btn-secondary text-sm !justify-center"><IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isRefreshingRags}"/><span>{{ isRefreshingRags ? 'Refreshing...' : 'Refresh Stores' }}</span></button></div></template></MultiSelectMenu></div>
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
                            <textarea v-model="messageText" @keydown.enter.exact.prevent="handleSendMessage" @keydown.enter.shift.prevent="switchToAdvancedMode($event)" placeholder="Type your message... (Shift+Enter for advanced editor)" rows="1" class="simple-chat-input"></textarea>
                        </div>
                        <div v-else class="space-y-2">
                            <CodeMirrorEditor v-model="messageText" placeholder="Type your message... (Ctrl+Enter to send)" :style="{ maxHeight: '200px' }" :autofocus="true" :extensions="advancedEditorExtensions" @ready="handleEditorReady" class="w-full"/>
                            <div class="flex justify-end">
                                <button @click="isAdvancedMode = false" class="btn btn-secondary !p-2" title="Switch to Simple Input"><IconChevronDown class="w-5 h-5" /></button>
                            </div>
                        </div>
                    </div>

                    <!-- Send Button -->
                    <div class="flex-shrink-0">
                        <button @click="handleSendMessage" :disabled="isSendDisabled" class="btn btn-primary chat-action-button" title="Send Message (Enter or Ctrl+Enter)"><IconSend class="w-5 h-5"/></button>
                    </div>
                </div>
            </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style>
.simple-chat-input { @apply w-full flex-1 p-2 bg-transparent rounded-md border border-gray-300 dark:border-gray-600 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-sm resize-none overflow-y-auto; height: 40px; }
.cm-editor-container .cm-editor { border: 1px solid theme('colors.gray.300'); border-radius: theme('borderRadius.md'); padding-top: 0.5rem; padding-bottom: 0.5rem; font-size: theme('fontSize.sm'); outline: none; }
.dark .cm-editor-container .cm-editor { border-color: theme('colors.gray.600'); }
.cm-editor-container .cm-editor.cm-focused { border-color: theme('colors.blue.500'); box-shadow: 0 0 0 1px theme('colors.blue.500'); }
.cm-editor-container .cm-scroller { overflow-y: auto; }
.progress-segment { @apply absolute top-0 h-full transition-all duration-300 ease-out opacity-80; }
.category-header { @apply px-3 py-1.5 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400 sticky top-0 bg-gray-50 dark:bg-gray-700 z-10; }
.menu-item { @apply w-full text-left px-3 py-1.5 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 flex items-center; }

</style>
