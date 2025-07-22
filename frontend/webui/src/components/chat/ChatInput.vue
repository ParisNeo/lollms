<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import apiClient from '../../services/api';
import MultiSelectMenu from '../ui/MultiSelectMenu.vue';
import IconToken from '../../assets/icons/IconToken.vue';
import IconScratchpad from '../../assets/icons/IconScratchpad.vue';

// CodeMirror imports
import { Codemirror } from 'vue-codemirror';
import { markdown } from '@codemirror/lang-markdown';
import { indentUnit } from '@codemirror/language';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView, keymap } from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import { defaultKeymap, indentWithTab } from '@codemirror/commands';

// Emoji Picker import (it registers itself as a custom element)
import 'emoji-picker-element';

const discussionsStore = useDiscussionsStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const emit = defineEmits(['toggle-data-zone']);

const messageText = ref('');
const uploadedImages = ref([]);
const isUploading = ref(false);
const imageInput = ref(null);
const codeMirrorView = ref(null);
const isAdvancedMode = ref(false);
const cursorPositionToSet = ref(null);
const isCodeMenuOpen = ref(false);
const isEmojiPickerOpen = ref(false);

const isRefreshingMcps = ref(false);
const isRefreshingRags = ref(false);

// --- Token Count State ---
const inputTokenCount = ref(0);
const isTokenizingInput = ref(false);
let tokenizeInputDebounceTimer = null;

// --- STATE FOR FLOATING/MOVABLE BEHAVIOR ---
const isShrunk = ref(false);
const chatbarRef = ref(null);
const isDragging = ref(false);
const isPositionModified = ref(false);
const startDragPos = ref({ x: 0, y: 0 });
const startChatboxPos = ref({ x: 0, y: 0 });
const currentChatboxPos = ref(null);

const user = computed(() => authStore.user);
const generationInProgress = computed(() => discussionsStore.generationInProgress);
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const availableRagStores = computed(() => dataStore.availableRagStores);
const availableMcpTools = computed(() => dataStore.availableMcpToolsForSelector);
const contextStatus = computed(() => discussionsStore.activeDiscussionContextStatus);

const isSendDisabled = computed(() => {
  return generationInProgress.value || (messageText.value.trim() === '' && uploadedImages.value.length === 0);
});

// --- Progress Bar Logic ---
const showContextBar = computed(() => {
    if (!user.value || !contextStatus.value) return false;
    return user.value.show_token_counter && user.value.user_ui_level >= 2;
});

const discussionTokens = computed(() => contextStatus.value?.current_tokens || 0);
const maxTokens = computed(() => contextStatus.value?.max_tokens || 1);

const totalCurrentTokens = computed(() => discussionTokens.value + inputTokenCount.value);

const discussionTokensPercentage = computed(() => {
    if (maxTokens.value <= 0) return 0;
    return (discussionTokens.value / maxTokens.value) * 100;
});

const inputTokensPercentage = computed(() => {
    if (maxTokens.value <= 0) return 0;
    return (inputTokenCount.value / maxTokens.value) * 100;
});

const totalPercentage = computed(() => {
    if (maxTokens.value <= 0) return 0;
    return (totalCurrentTokens.value / maxTokens.value) * 100;
});

const progressColorClass = computed(() => {
    const percentage = totalPercentage.value;
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 75) return 'bg-yellow-500';
    return 'bg-blue-500';
});


// --- COMPUTED PROPERTIES FOR FLOATING BEHAVIOR ---
const headerTitle = computed(() => activeDiscussion.value?.title || "New Chat");

const chatbarStyle = computed(() => {
    if (isPositionModified.value && currentChatboxPos.value) {
        return {
            left: `${currentChatboxPos.value.x}px`,
            top: `${currentChatboxPos.value.y}px`,
            bottom: 'auto',
            transform: 'none',
        };
    }
    return {
        left: '50%',
        bottom: '1rem',
        transform: 'translateX(-50%)',
    };
});

// --- METHODS FOR FLOATING/MOVABLE BEHAVIOR (WITH CONSTRAINTS) ---
function clampPosition(x, y) {
    const el = chatbarRef.value;
    if (!el) return { x, y };

    const minX = 0;
    const minY = 0;
    const maxX = window.innerWidth - el.offsetWidth;
    const maxY = window.innerHeight - el.offsetHeight;

    const clampedX = Math.max(minX, Math.min(x, maxX));
    const clampedY = Math.max(minY, Math.min(y, maxY));

    return { x: clampedX, y: clampedY };
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
    
    const newX = startChatboxPos.value.x + dx;
    const newY = startChatboxPos.value.y + dy;

    currentChatboxPos.value = clampPosition(newX, newY);
}

function onMouseUp() {
    isDragging.value = false;
    document.body.style.userSelect = '';
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);

    if (isPositionModified.value && currentChatboxPos.value) {
        const finalPosition = clampPosition(currentChatboxPos.value.x, currentChatboxPos.value.y);
        currentChatboxPos.value = finalPosition;
        localStorage.setItem('lollms_chatbarPosition', JSON.stringify(finalPosition));
        localStorage.setItem('lollms_chatbarPositionModified', 'true');
    }
}

function handleResize() {
    if (isPositionModified.value && currentChatboxPos.value) {
        currentChatboxPos.value = clampPosition(currentChatboxPos.value.x, currentChatboxPos.value.y);
    }
}

// --- Token Counting Logic ---
async function fetchInputTokenCount() {
    if (isTokenizingInput.value) return;
    isTokenizingInput.value = true;
    try {
        const response = await apiClient.post('/api/discussions/tokenize', { text: messageText.value });
        inputTokenCount.value = response.data.tokens;
    } catch (error) {
        console.error("Input tokenization failed:", error);
        inputTokenCount.value = 0; // Reset on error
    } finally {
        isTokenizingInput.value = false;
    }
}

watch(messageText, (newValue) => {
    clearTimeout(tokenizeInputDebounceTimer);
    if (!newValue.trim()) {
        inputTokenCount.value = 0;
    } else {
        if (showContextBar.value) {
            isTokenizingInput.value = true;
            tokenizeInputDebounceTimer = setTimeout(() => {
                fetchInputTokenCount();
            }, 500);
        }
    }
});

watch(activeDiscussion, () => {
    clearTimeout(tokenizeInputDebounceTimer);
    inputTokenCount.value = 0;
});

onMounted(() => {
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


// --- Existing logic from ChatInput ---
const ragStoreSelection = computed({
    get: () => activeDiscussion.value?.rag_datastore_ids || [],
    set(newIds) { if (activeDiscussion.value) discussionsStore.updateDiscussionRagStore({ discussionId: activeDiscussion.value.id, ragDatastoreIds: newIds }); }
});
const mcpToolSelection = computed({
    get: () => activeDiscussion.value?.active_tools || [],
    set(newIds) { if (activeDiscussion.value) discussionsStore.updateDiscussionMcps({ discussionId: activeDiscussion.value.id, mcp_tool_ids: newIds }); }
});

watch(activeDiscussion, (newDiscussion) => {
    isAdvancedMode.value = false;
    if (newDiscussion && !isPositionModified.value) {
        currentChatboxPos.value = null; 
    }
    if (newDiscussion) {
        ragStoreSelection.value = newDiscussion.rag_datastore_ids || [];
        mcpToolSelection.value = newDiscussion.active_tools || [];
    } else {
        isPositionModified.value = false;
        ragStoreSelection.value = [];
        mcpToolSelection.value = [];
    }
}, { immediate: true });

async function refreshMcps() {
    isRefreshingMcps.value = true;
    try {
        await dataStore.refreshMcps();
    } finally {
        isRefreshingMcps.value = false;
    }
}
async function refreshRags() {
    isRefreshingRags.value = true;
    try {
        await dataStore.refreshRags();
    } finally {
        isRefreshingRags.value = false;
    }
}

async function handleSendMessage() {
  if (isSendDisabled.value) return;
  const payload = {
    prompt: messageText.value,
    image_server_paths: uploadedImages.value.map(img => img.server_path),
    localImageUrls: uploadedImages.value.map(img => img.local_url),
  };
  try {
    await discussionsStore.sendMessage(payload);
    messageText.value = '';
    uploadedImages.value = [];
    inputTokenCount.value = 0;
  } catch (error) {
    uiStore.addNotification('There was an error sending your message.', 'error');
  }
}

async function switchToAdvancedMode(event) {
    if (event && event.target) cursorPositionToSet.value = event.target.selectionStart;
    isAdvancedMode.value = true;
    await nextTick();
}

const editorExtensions = computed(() => {
    const customKeymap = keymap.of([
      { key: 'Mod-Enter', run: (view) => { messageText.value = view.state.doc.toString(); handleSendMessage(); return true; }},
      indentWithTab,
    ]);
    const extensions = [ EditorView.lineWrapping, EditorState.tabSize.of(2), indentUnit.of("  "), customKeymap, keymap.of(defaultKeymap), markdown()];
    if (uiStore.currentTheme === 'dark') extensions.push(oneDark);
    return extensions;
});

function handleEditorReady(payload) {
    codeMirrorView.value = payload.view;
    if (cursorPositionToSet.value !== null) {
        const view = payload.view;
        const pos = Math.min(cursorPositionToSet.value, view.state.doc.length);
        view.dispatch({ selection: { anchor: pos, head: pos } });
        cursorPositionToSet.value = null;
    }
}

function insertTextAtCursor(before, after = '', placeholder = '') {
    const view = codeMirrorView.value; if (!view) return;
    const { from, to } = view.state.selection.main;
    const selectedText = view.state.doc.sliceString(from, to);
    let textToInsert, selectionOffsetStart, selectionOffsetEnd;
    if (selectedText) {
        textToInsert = `${before}${selectedText}${after}`;
        selectionOffsetStart = from + before.length;
        selectionOffsetEnd = selectionOffsetStart + selectedText.length;
    } else {
        textToInsert = `${before}${placeholder}${after}`;
        selectionOffsetStart = from + before.length;
        selectionOffsetEnd = selectionOffsetStart + placeholder.length;
    }
    view.dispatch({ changes: { from, to, insert: textToInsert }, selection: { anchor: selectionOffsetStart, head: selectionOffsetEnd }});
    view.focus();
}

function triggerImageUpload() { imageInput.value.click(); }

async function uploadFiles(files) {
    if (files.length === 0) return;
    if (uploadedImages.value.length + files.length > 5) {
        uiStore.addNotification('You can upload a maximum of 5 images.', 'warning');
        return;
    }
    isUploading.value = true;
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    try {
        const response = await apiClient.post('/api/upload/chat_image', formData);
        response.data.forEach(imgInfo => {
            const originalFile = files.find(f => f.name === imgInfo.filename);
            if(originalFile) {
                uploadedImages.value.push({
                    server_path: imgInfo.server_path,
                    local_url: URL.createObjectURL(originalFile),
                    file: originalFile
                });
            }
        });
        uiStore.addNotification(`${files.length} image(s) uploaded.`, 'success');
    } catch (error) { 
        console.error("Image upload failed:", error); 
        uiStore.addNotification('Image upload failed.', 'error');
    }
    finally {
        isUploading.value = false;
    }
}

async function handleImageSelection(event) {
    const files = Array.from(event.target.files);
    await uploadFiles(files);
    event.target.value = ''; // Reset input
}

async function handlePaste(event) {
    const items = (event.clipboardData || window.clipboardData).items;
    if (!items) return;
    const imageFiles = [];
    for (const item of items) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
            const file = item.getAsFile();
            if (file) {
                const extension = (file.type.split('/')[1] || 'png').toLowerCase().replace('jpeg', 'jpg');
                const uniqueName = `pasted_image_${Date.now()}.${extension}`;
                const newFile = new File([file], uniqueName, { type: file.type });
                imageFiles.push(newFile);
            }
        }
    }
    if (imageFiles.length > 0) {
        event.preventDefault();
        await uploadFiles(imageFiles);
    }
}


function removeImage(index) {
    URL.revokeObjectURL(uploadedImages.value[index].local_url);
    uploadedImages.value.splice(index, 1);
}

const codeLanguageGroups = [{ name: 'Common', languages: [{ name: 'Python', value: 'python' }, { name: 'JavaScript', value: 'javascript' }, { name: 'TypeScript', value: 'typescript' }, { name: 'JSON', value: 'json' }, { name: 'Markdown', value: 'markdown' }, { name: 'Shell', value: 'shell' }]}, { name: 'Web', languages: [{ name: 'HTML', value: 'html' }, { name: 'CSS', value: 'css' }, { name: 'SCSS', value: 'scss' }, { name: 'XML', value: 'xml' },]}, { name: 'Backend', languages: [{ name: 'Java', value: 'java' }, { name: 'C#', value: 'csharp' }, { name: 'Go', value: 'go' }, { name: 'Ruby', value: 'ruby' }, { name: 'PHP', value: 'php' }]}, { name: 'Data & Infra', languages: [{ name: 'SQL', value: 'sql' }, { name: 'YAML', value: 'yaml' }, { name: 'Dockerfile', value: 'dockerfile' }, { name: 'Terraform', value: 'terraform' }]}, { name: 'Other', languages: [{ name: 'C++', value: 'cpp' }, { name: 'Rust', value: 'rust' }, { name: 'Kotlin', value: 'kotlin' }, { name: 'Swift', value: 'swift' }]}];
function insertCodeBlock(lang) {
    const placeholder = lang === 'python' ? '# Your code here' : '// Your code here';
    insertTextAtCursor(`\`\`\`${lang}\n`, `\n\`\`\``, placeholder);
    isCodeMenuOpen.value = false;
}
function handleEmojiSelect(event) {
    const view = codeMirrorView.value; if (!view) return;
    const emoji = event.detail.unicode;
    view.dispatch({ changes: { from: view.state.selection.main.head, insert: emoji }});
    isEmojiPickerOpen.value = false;
    view.focus();
}

</script>

<template>
  <div>
    <!-- Shrink Button -->
    <Transition enter-active-class="transition ease-out duration-300" enter-from-class="transform opacity-0 scale-50" enter-to-class="transform opacity-100 scale-100" leave-active-class="transition ease-in duration-200" leave-from-class="transform opacity-100 scale-100" leave-to-class="transform opacity-0 scale-50">
      <button v-if="isShrunk" @click="toggleShrink" class="fixed bottom-4 right-4 z-[60] p-3 bg-blue-500 dark:bg-blue-600 text-white rounded-full shadow-lg hover:bg-blue-600 dark:hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-400 dark:focus:ring-offset-gray-900" title="Expand Chat"><svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg></button>
    </Transition>

    <!-- Main Chat Box -->
    <Transition enter-active-class="transition ease-out duration-300" enter-from-class="transform opacity-0 scale-95 translate-y-4" enter-to-class="transform opacity-100 scale-100 translate-y-0" leave-active-class="transition ease-in duration-200" leave-from-class="transform opacity-100 scale-100 translate-y-0" leave-to-class="transform opacity-0 scale-95 translate-y-4">
      <div v-if="!isShrunk" ref="chatbarRef" :style="chatbarStyle" @paste="handlePaste" class="fixed w-11/12 max-w-4xl bg-white/80 dark:bg-gray-800/80 backdrop-blur-md rounded-xl border border-gray-300 dark:border-gray-700 shadow-2xl transition-shadow z-50" :class="{'cursor-grabbing': isDragging}">
        
        <!-- Draggable Header -->
        <div @mousedown.prevent="onMouseDown" class="flex items-center justify-between h-10 px-4 border-b border-gray-200 dark:border-gray-700 rounded-t-xl" :class="isDragging ? 'cursor-grabbing' : 'cursor-grab'">
            <h3 class="text-sm font-semibold truncate text-gray-800 dark:text-gray-100 select-none">{{ headerTitle }}</h3>
            <button @click.stop="toggleShrink" @mousedown.stop class="p-1 rounded-full text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-600" title="Shrink Chat"><svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M18 12H6" /></svg></button>
        </div>

        <!-- Inner content area -->
        <div class="p-3" @mousedown.stop>
            <!-- Context Progress Bar -->
            <div v-if="showContextBar" class="px-1 pb-2">
                <div class="flex justify-between items-center mb-1 text-xs text-gray-600 dark:text-gray-400 font-mono">
                    <div class="flex items-center gap-1.5">
                        <IconToken class="w-4 h-4" />
                        <span>Context: {{ discussionTokens.toLocaleString() }} + {{ inputTokenCount.toLocaleString() }}</span>
                    </div>
                    <span>{{ totalCurrentTokens.toLocaleString() }} / {{ maxTokens.toLocaleString() }}</span>
                </div>
                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 relative overflow-hidden">
                    <div 
                        class="absolute top-0 left-0 h-full transition-all duration-300 opacity-50"
                        :class="progressColorClass" 
                        :style="{ width: `${Math.min(discussionTokensPercentage, 100)}%` }"
                    ></div>
                        <div 
                        class="absolute top-0 h-full transition-all duration-300"
                        :class="progressColorClass" 
                        :style="{ left: `${Math.min(discussionTokensPercentage, 100)}%`, width: `${Math.min(inputTokensPercentage, 100)}%` }"
                    ></div>
                </div>
            </div>
            <!-- Generation In Progress Animation -->
<!-- Main Input Area -->
            <div>
                <div v-if="uploadedImages.length > 0 || isUploading" class="mb-2 p-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md">
                    <div class="flex flex-wrap gap-2">
                        <div v-for="(image, index) in uploadedImages" :key="image.server_path" class="relative w-16 h-16"><img :src="image.local_url" class="w-full h-full object-cover rounded-md" alt="Image preview" /><button @click="removeImage(index)" class="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold leading-none">×</button></div>
                        <div v-if="isUploading" class="w-16 h-16 bg-gray-200 dark:bg-gray-700 rounded-md flex items-center justify-center"><svg class="animate-spin h-6 w-6 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg></div>
                    </div>
                </div>
                <input type="file" ref="imageInput" @change="handleImageSelection" multiple accept="image/*" class="hidden">

                <!-- Generation In Progress Animation -->
                <div v-if="generationInProgress" class="flex flex-row items-center justify-between p-2 h-[60px]">
                    <div class="flex items-center space-x-3"><svg class="animate-spin h-6 w-6 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><p class="text-sm font-semibold text-gray-600 dark:text-gray-300">Working...</p></div>
                    <button @click="discussionsStore.stopGeneration" class="btn btn-danger !py-1 !px-3">Stop Generation</button>
                </div>

                <!-- SIMPLE INPUT MODE -->
                <div v-else-if="!isAdvancedMode" class="flex items-end space-x-2">
                    <button @click="triggerImageUpload" :disabled="isUploading" class="btn btn-secondary !p-2.5 self-end disabled:opacity-50" title="Upload Images"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v12a1.5 1.5 0 0 0 1.5 1.5Zm10.5-11.25h.008v.008h-.008V8.25Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" /></svg></button>
                    <button @click="$emit('toggle-data-zone')" v-if="user.user_ui_level >= 2" class="btn btn-secondary !p-2.5 self-end" title="Toggle Data Zone (Scratchpad)">
                        <IconScratchpad class="w-6 h-6" />
                    </button>
                    <div v-if="user.user_ui_level >= 3" class="self-end">
                        <MultiSelectMenu v-model="mcpToolSelection" :items="availableMcpTools" placeholder="MCP Tools" activeClass="!bg-purple-600 !text-white" inactiveClass="btn-secondary">
                            <template #button="{ toggle, selected, activeClass, inactiveClass }"><button @click="toggle" :class="[selected.length > 0 ? activeClass : inactiveClass]" class="relative btn !p-2.5" title="Select MCP Tools"><svg viewBox="0 0 359.211 359.211" class="w-6 h-6" fill="currentColor"><path d="M352.203,286.132l-78.933-78.933c-3.578-3.578-8.35-5.548-13.436-5.548c-2.151,0-4.238,0.373-6.21,1.05l-18.929-18.929 c-2.825-2.826-6.593-4.382-10.607-4.382c-4.014,0-7.781,1.556-10.606,4.381l-4.978,4.978l-8.904-8.904l38.965-39.17 c9.105,3.949,19.001,5.837,29.224,5.837c0.002,0,0.004,0,0.007,0c19.618,0,38.064-7.437,51.939-21.312 c18.59-18.588,25.842-45.811,18.926-71.207c-0.859-3.159-3.825-5.401-7.053-5.401c-1.389,0-3.453,0.435-5.39,2.372 c-0.265-0.262-26.512,26.322-35.186,34.996c-0.955,0.955-2.531,1.104-3.45,1.104c-0.659,0-1.022-0.069-1.022-0.069v0.002 l-0.593-0.068c-10.782-0.99-23.716-2.984-26.98-4.489c-1.556-3.289-3.427-16.533-4.427-27.489v-0.147l-0.234-0.308 c-0.058-0.485-0.31-2.958,1.863-5.131c9.028-9.029,33.847-34.072,34.083-34.311c2.1-2.099,2.9-4.739,2.232-7.245 c-0.801-3.004-3.355-4.686-5.469-5.257C280.772,0.859,274.292,0,267.788,0c-19.62,0-38.068,7.64-51.941,21.512 c-21.901,21.901-27.036,54.296-15.446,81.141l-38.996,38.995L94.682,74.927c-0.041-0.041-0.086-0.075-0.128-0.115 c0.63-2.567,0.907-5.233,0.791-7.947c-0.329-7.73-3.723-15.2-9.558-21.034L62.041,22.083c-0.519-0.519-3.318-3.109-7.465-3.109 c-1.926,0-4.803,0.583-7.58,3.359L20.971,48.359c-3.021,3.021-4.098,6.903-2.954,10.652c0.767,2.512,2.258,4.139,2.697,4.578 l23.658,23.658c6.179,6.179,14.084,9.582,22.259,9.582c0,0,0,0,0.001,0c2.287,0,4.539-0.281,6.721-0.818 c0.041,0.042,0.075,0.087,0.116,0.128l66.722,66.722l-31.692,31.692c-1.428,1.428-2.669,2.991-3.726,4.654 c-9.281-4.133-19.404-6.327-29.869-6.327c-19.623,0-38.071,7.642-51.946,21.517c-18.589,18.589-25.841,45.914-18.926,71.31 c0.859,3.158,3.825,5.451,7.052,5.451c0,0,0,0,0.001,0c1.389,0,3.453-0.41,5.39-2.347c0.265-0.262,26.513-26.309,35.187-34.983 c0.955-0.955,2.639-1.097,3.557-1.097c0.66,0,1.125,0.072,1.132,0.072h-0.001l0.487,0.069c10.779,0.988,23.813,2.982,27.078,4.489 c1.556,3.29,3.575,16.534,4.554,27.49l0.07,0.501c0.006,0.026,0.362,2.771-1.952,5.086c-9.029,9.029-33.888,34.072-34.124,34.311 c-2.1,2.099-2.92,4.74-2.252,7.245c0.802,3.004,3.346,4.685,5.459,5.256c6.264,1.694,12.738,2.553,19.243,2.553 c19.621,0,38.066-7.64,51.938-21.512c13.876-13.875,21.518-32.324,21.517-51.947c0-10.465-2.193-20.586-6.326-29.868 c1.664-1.057,3.227-2.298,4.654-3.726l31.693-31.693l8.904,8.904l-4.979,4.979c-2.826,2.825-4.382,6.592-4.382,10.606 c0,4.015,1.556,7.782,4.382,10.607l18.929,18.929c-0.677,1.972-1.05,4.059-1.05,6.209c0,5.086,1.971,9.857,5.549,13.435 l78.934,78.934c3.577,3.577,8.349,5.548,13.435,5.548c5.086,0,9.857-1.971,13.435-5.548l40.659-40.66 c3.578-3.578,5.549-8.349,5.549-13.435C357.752,294.482,355.782,289.71,352.203,286.132z"/></svg><span v-if="selected.length > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-purple-800 rounded-full">{{ selected.length }}</span></button></template>
                                <template #footer>
                                    <div class="p-2">
                                        <button @click="refreshMcps" :disabled="isRefreshingMcps" class="w-full btn btn-secondary text-sm !justify-center">
                                            <svg :class="{'animate-spin': isRefreshingMcps}" class="w-4 h-4 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0011.664 0l3.181-3.183m-11.664 0l4.992-4.993m-4.993 0l3.181-3.183a8.25 8.25 0 0111.664 0l3.181 3.183" /></svg>
                                            <span>{{ isRefreshingMcps ? 'Refreshing...' : 'Refresh Tools' }}</span>
                                        </button>
                                    </div>
                                </template>
                            </MultiSelectMenu>
                        </div>
                        <div v-if="user.user_ui_level >= 1" class="self-end">
                            <MultiSelectMenu v-model="ragStoreSelection" :items="availableRagStores" placeholder="RAG Stores" activeClass="!bg-green-600 !text-white" inactiveClass="btn-secondary">
                                <template #button="{ toggle, selected, activeClass, inactiveClass }"><button @click="toggle" :class="[selected.length > 0 ? activeClass : inactiveClass]" class="relative btn !p-2.5" title="Select RAG Store"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" /></svg><span v-if="selected.length > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-green-800 rounded-full">{{ selected.length }}</span></button></template>
                                <template #footer>
                                    <div class="p-2">
                                        <button @click="refreshRags" :disabled="isRefreshingRags" class="w-full btn btn-secondary text-sm !justify-center">
                                            <svg :class="{'animate-spin': isRefreshingRags}" class="w-4 h-4 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0011.664 0l3.181-3.183m-11.664 0l4.992-4.993m-4.993 0l3.181-3.183a8.25 8.25 0 0111.664 0l3.181 3.183" /></svg>
                                            <span>{{ isRefreshingRags ? 'Refreshing...' : 'Refresh Stores' }}</span>
                                        </button>
                                    </div>
                                </template>
                            </MultiSelectMenu>
                        </div>
                        <textarea v-model="messageText" @keydown.enter.exact.prevent="handleSendMessage" @keydown.enter.shift.prevent="switchToAdvancedMode($event)" placeholder="Type your message... (Shift+Enter for advanced editor)" rows="1" class="simple-chat-input"></textarea>
                        <button @click="handleSendMessage" :disabled="isSendDisabled" class="btn btn-primary self-end !p-2.5" title="Send Message"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" /></svg></button>
                    </div>

                    <!-- ADVANCED INPUT MODE (CodeMirror with Toolbar) -->
                    <div v-else class="flex flex-col space-y-2">
                        <div class="editor-toolbar">
                            <button @click="insertTextAtCursor('**', '**', 'bold text')" title="Bold" class="toolbar-btn"><span class="font-bold text-base">B</span></button>
                            <button @click="insertTextAtCursor('*', '*', 'italic text')" title="Italic" class="toolbar-btn"><span class="italic font-serif text-lg">I</span></button>
                            <div class="relative" v-on-click-outside="() => isCodeMenuOpen = false">
                                <button @click="isCodeMenuOpen = !isCodeMenuOpen" title="Insert Code Block" class="toolbar-btn"><svg xmlns="http://www.w3.org/2000/svg"  viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5"><path d="M13.3252 3.05011L8.66765 20.4323L10.5995 20.9499L15.257 3.56775L13.3252 3.05011Z"/><path d="M7.61222 18.3608L8.97161 16.9124L8.9711 16.8933L3.87681 12.1121L8.66724 7.00798L7.20892 5.63928L1.0498 12.2017L7.61222 18.3608Z"/><path d="M16.3883 18.3608L15.0289 16.9124L15.0294 16.8933L20.1237 12.1121L15.3333 7.00798L16.7916 5.63928L22.9507 12.2017L16.3883 18.3608Z"/></svg></button>
                                <div v-if="isCodeMenuOpen" class="code-menu-dropdown"><template v-for="group in codeLanguageGroups" :key="group.name"><h3 class="px-3 py-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{{ group.name }}</h3><div class="grid grid-cols-3 gap-1 px-2 py-1"><button v-for="lang in group.languages" :key="lang.value" @click="insertCodeBlock(lang.value)" class="code-menu-item">{{ lang.name }}</button></div></template></div>
                            </div>
                            <button @click="insertTextAtCursor('[', '](https://)', 'link text')" title="Insert Link" class="toolbar-btn"><svg xmlns="http://www.w3.org/2000/svg"  viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5"><path d="M7.05025 1.53553C8.03344 0.552348 9.36692 0 10.7574 0C13.6528 0 16 2.34721 16 5.24264C16 6.63308 15.4477 7.96656 14.4645 8.94975L12.4142 11L11 9.58579L13.0503 7.53553C13.6584 6.92742 14 6.10264 14 5.24264C14 3.45178 12.5482 2 10.7574 2C9.89736 2 9.07258 2.34163 8.46447 2.94975L6.41421 5L5 3.58579L7.05025 1.53553Z"/><path d="M7.53553 13.0503L9.58579 11L11 12.4142L8.94975 14.4645C7.96656 15.4477 6.63308 16 5.24264 16C2.34721 16 0 13.6528 0 10.7574C0 9.36693 0.552347 8.03344 1.53553 7.05025L3.58579 5L5 6.41421L2.94975 8.46447C2.34163 9.07258 2 9.89736 2 10.7574C2 12.5482 3.45178 14 5.24264 14C6.10264 14 6.92742 13.6584 7.53553 13.0503Z"/><path d="M5.70711 11.7071L11.7071 5.70711L10.2929 4.29289L4.29289 10.2929L5.70711 11.7071Z"/></svg></button>
                            <button @click="insertTextAtCursor('| Header 1 | Header 2 |\n|---|---|\n| Cell 1 | Cell 2 |\n| Cell 3 | Cell 4 |', '', '')" title="Insert Table" class="toolbar-btn"><svg xmlns="http://www.w3.org/2000/svg"  viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5"><path d="M4 12L20 12M12 4L12 20M6.2 20H17.8C18.9201 20 19.4802 20 19.908 19.782C20.2843 19.5903 20.5903 19.2843 20.782 18.908C21 18.4802 21 17.9201 21 16.8V7.2C21 6.0799 21 5.51984 20.782 5.09202C20.5903 4.71569 20.2843 4.40973 19.908 4.21799C19.4802 4 18.9201 4 17.8 4H6.2C5.0799 4 4.51984 4 4.09202 4.21799C3.71569 4.40973 3.40973 4.71569 3.21799 5.09202C3 5.51984 3 6.07989 3 7.2V16.8C3 17.9201 3 18.4802 3.21799 18.908C3.40973 19.2843 3.71569 19.5903 4.09202 19.782C4.51984 20 5.07989 20 6.2 20Z" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
                            <div class="relative" v-on-click-outside="() => isEmojiPickerOpen = false">
                                <button @click="isEmojiPickerOpen = !isEmojiPickerOpen" title="Insert Emoji" class="toolbar-btn"><svg xmlns="http://www.w3.org/2000/svg"  viewBox="0 0 24 24" fill="currentColor" class="w-5 h-5"><path d="M8.9126 15.9336C10.1709 16.249 11.5985 16.2492 13.0351 15.8642C14.4717 15.4793 15.7079 14.7653 16.64 13.863" stroke="#1C274C" stroke-width="1.5" stroke-linecap="round"/><ellipse cx="14.5094" cy="9.77405" rx="1" ry="1.5" transform="rotate(-15 14.5094 9.77405)" fill="#1C274C"/><ellipse cx="8.71402" cy="11.3278" rx="1" ry="1.5" transform="rotate(-15 8.71402 11.3278)" fill="#1C274C"/><path d="M13 16.0004L13.478 16.9742C13.8393 17.7104 14.7249 18.0198 15.4661 17.6689C16.2223 17.311 16.5394 16.4035 16.1708 15.6524L15.7115 14.7168" stroke="#1C274C" stroke-width="1.5"/><path d="M4.92847 4.92663C6.12901 3.72408 7.65248 2.81172 9.41185 2.34029C14.7465 0.910876 20.2299 4.0767 21.6593 9.41136C23.0887 14.746 19.9229 20.2294 14.5882 21.6588C9.25357 23.0882 3.7702 19.9224 2.34078 14.5877C1.86936 12.8284 1.89775 11.0528 2.33892 9.41186" stroke="#1C274C" stroke-width="1.5" stroke-linecap="round"/></svg></button>
                                <div v-if="isEmojiPickerOpen" class="emoji-picker-container"><emoji-picker @emoji-click="handleEmojiSelect" :class="{'dark-theme': uiStore.currentTheme === 'dark'}"></emoji-picker></div>
                            </div>
                            <div class="flex-grow"></div>
                            <button @click="isAdvancedMode = false" class="toolbar-btn" title="Switch to Simple Input"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" /></svg></button>
                        </div>
                        
                        <div class="flex items-end space-x-2">
                            <button @click="triggerImageUpload" :disabled="isUploading" class="btn btn-secondary !p-2.5 self-end disabled:opacity-50" title="Upload Images"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v12a1.5 1.5 0 0 0 1.5 1.5Zm10.5-11.25h.008v.008h-.008V8.25Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" /></svg></button>
                            <button @click="$emit('toggle-data-zone')" v-if="user.user_ui_level >= 2" class="btn btn-secondary !p-2.5 self-end" title="Toggle Data Zone (Scratchpad)">
                                <IconScratchpad class="w-6 h-6" />
                            </button>
                            <div v-if="user.user_ui_level >= 3" class="self-end">
                                <MultiSelectMenu v-model="mcpToolSelection" :items="availableMcpTools" placeholder="MCP Tools" activeClass="!bg-purple-600 !text-white" inactiveClass="btn-secondary">
                                    <template #button="{ toggle, selected, activeClass, inactiveClass }"><button type="button" @click="toggle" :class="[selected.length > 0 ? activeClass : inactiveClass]" class="relative btn !p-2.5" title="Select MCP Tools"><svg viewBox="0 0 359.211 359.211" class="w-6 h-6" fill="currentColor"><path d="M352.203,286.132l-78.933-78.933c-3.578-3.578-8.35-5.548-13.436-5.548c-2.151,0-4.238,0.373-6.21,1.05l-18.929-18.929 c-2.825-2.826-6.593-4.382-10.607-4.382c-4.014,0-7.781,1.556-10.606,4.381l-4.978,4.978l-8.904-8.904l38.965-39.17 c9.105,3.949,19.001,5.837,29.224,5.837c0.002,0,0.004,0,0.007,0c19.618,0,38.064-7.437,51.939-21.312 c18.59-18.588,25.842-45.811,18.926-71.207c-0.859-3.159-3.825-5.401-7.053-5.401c-1.389,0-3.453,0.435-5.39,2.372 c-0.265-0.262-26.512,26.322-35.186,34.996c-0.955,0.955-2.531,1.104-3.45,1.104c-0.659,0-1.022-0.069-1.022-0.069v0.002 l-0.593-0.068c-10.782-0.99-23.716-2.984-26.98-4.489c-1.556-3.289-3.427-16.533-4.427-27.489v-0.147l-0.234-0.308 c-0.058-0.485-0.31-2.958,1.863-5.131c9.028-9.029,33.847-34.072,34.083-34.311c2.1-2.099,2.9-4.739,2.232-7.245 c-0.801-3.004-3.355-4.686-5.469-5.257C280.772,0.859,274.292,0,267.788,0c-19.62,0-38.068,7.64-51.941,21.512 c-21.901,21.901-27.036,54.296-15.446,81.141l-38.996,38.995L94.682,74.927c-0.041-0.041-0.086-0.075-0.128-0.115 c0.63-2.567,0.907-5.233,0.791-7.947c-0.329-7.73-3.723-15.2-9.558-21.034L62.041,22.083c-0.519-0.519-3.318-3.109-7.465-3.109 c-1.926,0-4.803,0.583-7.58,3.359L20.971,48.359c-3.021,3.021-4.098,6.903-2.954,10.652c0.767,2.512,2.258,4.139,2.697,4.578 l23.658,23.658c6.179,6.179,14.084,9.582,22.259,9.582c0,0,0,0,0.001,0c2.287,0,4.539-0.281,6.721-0.818 c0.041,0.042,0.075,0.087,0.116,0.128l66.722,66.722l-31.692,31.692c-1.428,1.428-2.669,2.991-3.726,4.654 c-9.281-4.133-19.404-6.327-29.869-6.327c-19.623,0-38.071,7.642-51.946,21.517c-18.589,18.589-25.841,45.914-18.926,71.31 c0.859,3.158,3.825,5.451,7.052,5.451c0,0,0,0,0.001,0c1.389,0,3.453-0.41,5.39-2.347c0.265-0.262,26.513-26.309,35.187-34.983 c0.955-0.955,2.639-1.097,3.557-1.097c0.66,0,1.125,0.072,1.132,0.072h-0.001l0.487,0.069c10.779,0.988,23.813,2.982,27.078,4.489 c1.556,3.29,3.575,16.534,4.554,27.49l0.07,0.501c0.006,0.026,0.362,2.771-1.952,5.086c-9.029,9.029-33.888,34.072-34.124,34.311 c-2.1,2.099-2.92,4.74-2.252,7.245c0.802,3.004,3.346,4.685,5.459,5.256c6.264,1.694,12.738,2.553,19.243,2.553 c19.621,0,38.066-7.64,51.938-21.512c13.876-13.875,21.518-32.324,21.517-51.947c0-10.465-2.193-20.586-6.326-29.868 c1.664-1.057,3.227-2.298,4.654-3.726l31.693-31.693l8.904,8.904l-4.979,4.979c-2.826,2.825-4.382,6.592-4.382,10.606 c0,4.015,1.556,7.782,4.382,10.607l18.929,18.929c-0.677,1.972-1.05,4.059-1.05,6.209c0,5.086,1.971,9.857,5.549,13.435 l78.934,78.934c3.577,3.577,8.349,5.548,13.435,5.548c5.086,0,9.857-1.971,13.435-5.548l40.659-40.66 c3.578-3.578,5.549-8.349,5.549-13.435C357.752,294.482,355.782,289.71,352.203,286.132z"/></svg><span v-if="selected.length > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-purple-800 rounded-full">{{ selected.length }}</span></button></template>
                                    <template #footer>
                                        <div class="p-2">
                                            <button @click="refreshMcps" :disabled="isRefreshingMcps" class="w-full btn btn-secondary text-sm !justify-center">
                                                <svg :class="{'animate-spin': isRefreshingMcps}" class="w-4 h-4 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0011.664 0l3.181-3.183m-11.664 0l4.992-4.993m-4.993 0l3.181-3.183a8.25 8.25 0 0111.664 0l3.181 3.183" /></svg>
                                                <span>{{ isRefreshingMcps ? 'Refreshing...' : 'Refresh Tools' }}</span>
                                            </button>
                                        </div>
                                    </template>
                                </MultiSelectMenu>
                            </div>
                            <div v-if="user.user_ui_level >= 1" class="self-end">
                                <MultiSelectMenu v-model="ragStoreSelection" :items="availableRagStores" placeholder="RAG Stores" activeClass="!bg-green-600 !text-white" inactiveClass="btn-secondary">
                                    <template #button="{ toggle, selected, activeClass, inactiveClass }"><button type="button" @click="toggle" :class="[selected.length > 0 ? activeClass : inactiveClass]" class="relative btn !p-2.5" title="Select RAG Store"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" /></svg><span v-if="selected.length > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-green-800 rounded-full">{{ selected.length }}</span></button></template>
                                    <template #footer>
                                        <div class="p-2">
                                            <button @click="refreshRags" :disabled="isRefreshingRags" class="w-full btn btn-secondary text-sm !justify-center">
                                                <svg :class="{'animate-spin': isRefreshingRags}" class="w-4 h-4 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0011.664 0l3.181-3.183m-11.664 0l4.992-4.993m-4.993 0l3.181-3.183a8.25 8.25 0 0111.664 0l3.181 3.183" /></svg>
                                                <span>{{ isRefreshingRags ? 'Refreshing...' : 'Refresh Stores' }}</span>
                                            </button>
                                        </div>
                                    </template>
                                </MultiSelectMenu>
                            </div>
                            <div class="flex-1 self-end"><codemirror v-model="messageText" placeholder="Type your message... (Ctrl+Enter to send)" :style="{ maxHeight: '200px' }" :autofocus="true" :extensions="editorExtensions" @ready="handleEditorReady" class="cm-editor-container"/></div>
                            <button @click="handleSendMessage" :disabled="isSendDisabled" class="btn btn-primary self-end !p-2.5" title="Send Message (Ctrl+Enter)"><svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6"><path stroke-linecap="round" stroke-linejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" /></svg></button>
                    </div>
                </div>
            </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style>
.simple-chat-input { @apply flex-1 p-2.5 pr-10 bg-transparent rounded-md border border-gray-300 dark:border-gray-600 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-sm resize-none overflow-hidden; min-height: 46px; }
.editor-toolbar { @apply flex items-center space-x-1 p-1 bg-gray-100 dark:bg-gray-900/50 rounded-md border border-gray-200 dark:border-gray-700; }
.toolbar-btn { @apply p-1.5 rounded-md text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500; }
.code-menu-dropdown { @apply absolute bottom-full left-0 mb-2 w-72 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow-xl z-20 py-2; }
.code-menu-item { @apply w-full text-left px-2 py-1 text-sm text-gray-700 dark:text-gray-200 hover:bg-blue-500 hover:text-white rounded-md; }
.emoji-picker-container { @apply absolute bottom-full left-0 mb-2 z-40; }
emoji-picker.dark-theme { --background: #1f2937; --border-color: #4b5563; --input-background-color: #374151; --text-color: #d1d5db; --secondary-text-color: #9ca3af; }
.cm-editor-container .cm-editor { border: 1px solid theme('colors.gray.300'); border-radius: theme('borderRadius.md'); padding-top: 0.5rem; padding-bottom: 0.5rem; font-size: theme('fontSize.sm'); outline: none; }
.dark .cm-editor-container .cm-editor { border-color: theme('colors.gray.600'); }
.cm-editor-container .cm-editor.cm-focused { border-color: theme('colors.blue.500'); box-shadow: 0 0 0 1px theme('colors.blue.500'); }
.cm-editor-container .cm-scroller { overflow-y: auto; }
</style>