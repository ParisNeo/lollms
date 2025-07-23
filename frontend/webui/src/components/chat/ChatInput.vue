<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import apiClient from '../../services/api';

// UI Components
import MultiSelectMenu from '../ui/MultiSelectMenu.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';

// Icon Components
import IconToken from '../../assets/icons/IconToken.vue';
import IconDataZone from '../../assets/icons/IconDataZone.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconMcp from '../../assets/icons/IconMcp.vue';
import IconDatabase from '../../assets/icons/IconDatabase.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconChevronDown from '../../assets/icons/IconChevronDown.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';

// CodeMirror imports
import { markdown } from '@codemirror/lang-markdown';
import { indentUnit } from '@codemirror/language';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView, keymap } from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import { defaultKeymap, indentWithTab } from '@codemirror/commands';

const props = defineProps({
    dataZoneContent: {
        type: String,
        default: ''
    }
});

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

const isRefreshingMcps = ref(false);
const isRefreshingRags = ref(false);

// --- Token Count State ---
const inputTokenCount = ref(0);
const dataZoneTokenCount = ref(0);
const isTokenizingInput = ref(false);
const isTokenizingDataZone = ref(false);
let tokenizeInputDebounceTimer = null;
let tokenizeDataZoneDebounceTimer = null;

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

const totalCurrentTokens = computed(() => discussionTokens.value + inputTokenCount.value + dataZoneTokenCount.value);

const discussionTokensPercentage = computed(() => {
    if (maxTokens.value <= 0) return 0;
    return (discussionTokens.value / maxTokens.value) * 100;
});

const inputTokensPercentage = computed(() => {
    if (maxTokens.value <= 0) return 0;
    return (inputTokenCount.value / maxTokens.value) * 100;
});

const dataZoneTokensPercentage = computed(() => {
    if (maxTokens.value <= 0) return 0;
    return (dataZoneTokenCount.value / maxTokens.value) * 100;
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

const showContextWarning = computed(() => totalPercentage.value > 90);
const contextWarningMessage = computed(() => {
    if (totalPercentage.value > 100) {
        return "Context limit exceeded! The model may not see all of your message.";
    }
    if (totalPercentage.value > 90) {
        return "You are approaching the context limit. Consider shortening your message or data zones.";
    }
    return "";
});


// --- FLOATING/MOVABLE BEHAVIOR ---
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
async function fetchTokenCount(text, targetRef, loadingRef) {
    if (loadingRef.value) return;
    loadingRef.value = true;
    try {
        const response = await apiClient.post('/api/discussions/tokenize', { text });
        targetRef.value = response.data.tokens;
    } catch (error) {
        console.error("Tokenization failed:", error);
        targetRef.value = 0;
    } finally {
        loadingRef.value = false;
    }
}

watch(messageText, (newValue) => {
    clearTimeout(tokenizeInputDebounceTimer);
    if (!newValue.trim()) {
        inputTokenCount.value = 0;
    } else if (showContextBar.value) {
        tokenizeInputDebounceTimer = setTimeout(() => {
            fetchTokenCount(newValue, inputTokenCount, isTokenizingInput);
        }, 500);
    }
});

watch(() => props.dataZoneContent, (newValue) => {
    clearTimeout(tokenizeDataZoneDebounceTimer);
    if (typeof newValue !== 'string' || !newValue.trim()) {
        dataZoneTokenCount.value = 0;
    } else if (showContextBar.value) {
        tokenizeDataZoneDebounceTimer = setTimeout(() => {
            fetchTokenCount(newValue, dataZoneTokenCount, isTokenizingDataZone);
        }, 500);
    }
}, { immediate: true });

watch(activeDiscussion, () => {
    clearTimeout(tokenizeInputDebounceTimer);
    clearTimeout(tokenizeDataZoneDebounceTimer);
    inputTokenCount.value = 0;
    dataZoneTokenCount.value = 0;
    if (props.dataZoneContent) {
        fetchTokenCount(props.dataZoneContent, dataZoneTokenCount, isTokenizingDataZone);
    }
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
    clearTimeout(tokenizeDataZoneDebounceTimer);
});

// --- Chat Input Logic ---
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
    try { await dataStore.refreshMcps(); } finally { isRefreshingMcps.value = false; }
}
async function refreshRags() {
    isRefreshingRags.value = true;
    try { await dataStore.refreshRags(); } finally { isRefreshingRags.value = false; }
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
    if (event && event.target) {
        cursorPositionToSet.value = event.target.selectionStart;
    }
    isAdvancedMode.value = true;
    await nextTick();
}

const advancedEditorExtensions = computed(() => {
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
    payload.view.focus();
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
    event.target.value = '';
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
        
        <div @mousedown.prevent="onMouseDown" class="flex items-center justify-between h-10 px-4 border-b border-gray-200 dark:border-gray-700 rounded-t-xl" :class="isDragging ? 'cursor-grabbing' : 'cursor-grab'">
            <h3 class="text-sm font-semibold truncate text-gray-800 dark:text-gray-100 select-none">{{ headerTitle }}</h3>
            <button @click.stop="toggleShrink" @mousedown.stop class="p-1 rounded-full text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-600" title="Shrink Chat"><svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M18 12H6" /></svg></button>
        </div>

        <div class="p-3" @mousedown.stop>
            <div v-if="showContextBar" class="px-1 pb-2">
                <div class="flex justify-between items-center mb-1 text-xs text-gray-600 dark:text-gray-400 font-mono">
                    <div class="flex items-center gap-1.5"><IconToken class="w-4 h-4" /><span>Context: {{ discussionTokens.toLocaleString() }} + {{ dataZoneTokenCount.toLocaleString() }} + {{ inputTokenCount.toLocaleString() }}</span></div>
                    <span>{{ totalCurrentTokens.toLocaleString() }} / {{ maxTokens.toLocaleString() }}</span>
                </div>
                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 relative overflow-hidden">
                    <div class="absolute top-0 left-0 h-full transition-all duration-300 opacity-50" :class="progressColorClass" :style="{ width: `${Math.min(discussionTokensPercentage, 100)}%` }"></div>
                    <div class="absolute top-0 h-full transition-all duration-300 opacity-75" :class="progressColorClass" :style="{ left: `${Math.min(discussionTokensPercentage, 100)}%`, width: `${Math.min(dataZoneTokensPercentage, 100)}%` }"></div>
                    <div class="absolute top-0 h-full transition-all duration-300" :class="progressColorClass" :style="{ left: `${Math.min(discussionTokensPercentage + dataZoneTokensPercentage, 100)}%`, width: `${Math.min(inputTokensPercentage, 100)}%` }"></div>
                </div>
                <p v-if="showContextWarning" class="mt-1.5 text-xs text-center" :class="totalPercentage > 100 ? 'text-red-600 dark:text-red-400' : 'text-yellow-600 dark:text-yellow-400'">{{ contextWarningMessage }}</p>
            </div>
            
            <div>
                <div v-if="uploadedImages.length > 0 || isUploading" class="mb-2 p-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md">
                    <div class="flex flex-wrap gap-2">
                        <div v-for="(image, index) in uploadedImages" :key="image.server_path" class="relative w-16 h-16"><img :src="image.local_url" class="w-full h-full object-cover rounded-md" alt="Image preview" /><button @click="removeImage(index)" class="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold leading-none">×</button></div>
                        <div v-if="isUploading" class="w-16 h-16 bg-gray-200 dark:bg-gray-700 rounded-md flex items-center justify-center"><IconAnimateSpin class="h-6 w-6 text-gray-500" /></div>
                    </div>
                </div>
                <input type="file" ref="imageInput" @change="handleImageSelection" multiple accept="image/*" class="hidden">
                
                <div v-if="generationInProgress" class="flex flex-row items-center justify-between p-2 h-[60px]">
                    <div class="flex items-center space-x-3"><IconAnimateSpin class="h-6 w-6 text-blue-500" /><p class="text-sm font-semibold text-gray-600 dark:text-gray-300">Working...</p></div>
                    <button @click="discussionsStore.stopGeneration" class="btn btn-danger !py-1 !px-3">Stop Generation</button>
                </div>
                
                <div v-else class="flex items-end space-x-2">
                    <button @click="triggerImageUpload" :disabled="isUploading" class="btn btn-secondary !p-2.5 self-end disabled:opacity-50" title="Upload Images"><IconPhoto class="w-6 h-6"/></button>
                    <button @click="$emit('toggle-data-zone')" v-if="user.user_ui_level >= 2" class="btn btn-secondary !p-2.5 self-end" title="Toggle Data Zone"><IconDataZone class="w-6 h-6" /></button>
                    <div v-if="user.user_ui_level >= 3" class="self-end">
                        <MultiSelectMenu v-model="mcpToolSelection" :items="availableMcpTools" placeholder="MCP Tools" activeClass="!bg-purple-600 !text-white" inactiveClass="btn-secondary">
                            <template #button="{ toggle, selected, activeClass, inactiveClass }"><button type="button" @click="toggle" :class="[selected.length > 0 ? activeClass : inactiveClass]" class="relative btn !p-2.5" title="Select MCP Tools"><IconMcp class="w-6 h-6"/><span v-if="selected.length > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-purple-800 rounded-full">{{ selected.length }}</span></button></template>
                            <template #footer>
                                <div class="p-2">
                                    <button @click="refreshMcps" :disabled="isRefreshingMcps" class="w-full btn btn-secondary text-sm !justify-center"><IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isRefreshingMcps}"/><span>{{ isRefreshingMcps ? 'Refreshing...' : 'Refresh Tools' }}</span></button>
                                </div>
                            </template>
                        </MultiSelectMenu>
                    </div>
                    <div v-if="user.user_ui_level >= 1" class="self-end">
                        <MultiSelectMenu v-model="ragStoreSelection" :items="availableRagStores" placeholder="RAG Stores" activeClass="!bg-green-600 !text-white" inactiveClass="btn-secondary">
                            <template #button="{ toggle, selected, activeClass, inactiveClass }"><button type="button" @click="toggle" :class="[selected.length > 0 ? activeClass : inactiveClass]" class="relative btn !p-2.5" title="Select RAG Store"><IconDatabase class="w-6 h-6" /><span v-if="selected.length > 0" class="absolute -top-1 -right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-green-800 rounded-full">{{ selected.length }}</span></button></template>
                            <template #footer>
                                <div class="p-2">
                                    <button @click="refreshRags" :disabled="isRefreshingRags" class="w-full btn btn-secondary text-sm !justify-center"><IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isRefreshingRags}"/><span>{{ isRefreshingRags ? 'Refreshing...' : 'Refresh Stores' }}</span></button>
                                </div>
                            </template>
                        </MultiSelectMenu>
                    </div>
                    <div class="flex-1 self-end">
                        <textarea v-if="!isAdvancedMode" v-model="messageText" @keydown.enter.exact.prevent="handleSendMessage" @keydown.enter.shift.prevent="switchToAdvancedMode($event)" placeholder="Type your message... (Shift+Enter for advanced editor)" rows="1" class="simple-chat-input"></textarea>
                        <CodeMirrorEditor v-else v-model="messageText" placeholder="Type your message... (Ctrl+Enter to send)" :style="{ maxHeight: '200px' }" :autofocus="true" :extensions="advancedEditorExtensions" @ready="handleEditorReady" class="w-full"/>
                    </div>
                     <button v-if="isAdvancedMode" @click="isAdvancedMode = false" class="btn btn-secondary !p-2.5 self-end" title="Switch to Simple Input"><IconChevronDown class="w-6 h-6" /></button>
                    <button @click="handleSendMessage" :disabled="isSendDisabled" class="btn btn-primary self-end !p-2.5" title="Send Message (Enter or Ctrl+Enter)"><IconSend class="w-6 h-6"/></button>
                </div>
            </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style>
.simple-chat-input { @apply w-full flex-1 p-2.5 bg-transparent rounded-md border border-gray-300 dark:border-gray-600 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 text-sm resize-none overflow-y-auto; min-height: 46px; }
.cm-editor-container .cm-editor { border: 1px solid theme('colors.gray.300'); border-radius: theme('borderRadius.md'); padding-top: 0.5rem; padding-bottom: 0.5rem; font-size: theme('fontSize.sm'); outline: none; }
.dark .cm-editor-container .cm-editor { border-color: theme('colors.gray.600'); }
.cm-editor-container .cm-editor.cm-focused { border-color: theme('colors.blue.500'); box-shadow: 0 0 0 1px theme('colors.blue.500'); }
.cm-editor-container .cm-scroller { overflow-y: auto; }
</style>