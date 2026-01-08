<!-- [UPDATE] frontend/webui/src/components/chat/MessageBubble.vue -->
<script setup>
import { computed, ref, onMounted, watch, markRaw } from 'vue';
import { marked } from 'marked';
import { useAuthStore } from '../../stores/auth';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import StepDetail from './StepDetail.vue';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView, keymap } from '@codemirror/view';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconThumbUp from '../../assets/icons/IconThumbUp.vue';
import IconThumbDown from '../../assets/icons/IconThumbDown.vue';
import IconToken from '../../assets/icons/IconToken.vue';
import IconThinking from '../../assets/icons/IconThinking.vue';
import IconTool from '../../assets/icons/IconTool.vue';
import IconObservation from '../../assets/icons/IconObservation.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconError from '../../assets/icons/IconError.vue';
import IconScratchpad from '../../assets/icons/IconScratchpad.vue';
import IconEventDefault from '../../assets/icons/IconEventDefault.vue';
import IconCog from '../../assets/icons/IconCog.vue';
import IconStepEnd from '../../assets/icons/IconStepEnd.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconSpeakerWave from '../../assets/icons/IconSpeakerWave.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconGitBranch from '../../assets/icons/ui/IconGitBranch.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconCircle from '../../assets/icons/IconCircle.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue'; 
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const props = defineProps({
  message: { type: Object, required: true },
});

// ... (math rendering logic remains same)
const mathPlaceholders = new Map();
let mathCounter = 0;

function protectMath(text) {
    if (!text) return text;
    mathCounter = 0;
    mathPlaceholders.clear();

    return text.replace(/(\$\$[\s\S]*?\$$|\$[\s\S]*?\$)/g, (match) => {
        const placeholder = `<!--MATH_PLACEHOLDER_${mathCounter}-->`;
        mathPlaceholders.set(placeholder, match);
        mathCounter++;
        return placeholder;
    });
}

function unprotectHtml(html) {
    if (!html || mathPlaceholders.size === 0) return html;
    let result = html;
    for (const [placeholder, original] of mathPlaceholders.entries()) {
        const regex = new RegExp(placeholder.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&'), 'g');
        result = result.replace(regex, original);
    }
    return result;
}

const parsedMarkdown = (content) => {
    if (typeof content !== 'string') return '';
    const protectedContent = protectMath(content);
    const rawHtml = marked.parse(protectedContent, { gfm: true, breaks: true, mangle: false, smartypants: false });
    return unprotectHtml(rawHtml);
};

const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const dataStore = useDataStore();
const tasksStore = useTasksStore();
const { currentModelVisionSupport, ttsState, currentPlayingAudio } = storeToRefs(discussionsStore);
const { imageGenerationTasks } = storeToRefs(tasksStore);

const isEventsCollapsed = ref(true);
const isEditing = ref(false);
const editedContent = ref('');
const codeMirrorView = ref(null);
const isFormattingMenuOpen = ref(false);
const isSourcesVisible = ref(false);
const editedImages = ref([]);
const newImageFiles = ref([]);
const editImageInput = ref(null);
const audioPlayerRef = ref(null);
const previewMap = ref({});
const sourceRefs = ref({}); // To store refs to source items for scrolling

const selectedViewIndices = ref({});

const areActionsDisabled = computed(() => discussionsStore.generationInProgress);
const user = computed(() => authStore.user);
const isTtsActive = computed(() => !!user.value?.tts_binding_model_name);
const messageTtsState = computed(() => ttsState.value[props.message.id] || {});

const isCurrentUser = computed(() => props.message.sender_type === 'user' && props.message.sender === authStore.user?.username);
const isOtherUser = computed(() => props.message.sender_type === 'user' && props.message.sender !== authStore.user?.username);
const isAi = computed(() => props.message.sender_type === 'assistant');
const isSystem = computed(() => props.message.sender_type === 'system');
const isNewManualMessage = computed(() => props.message.id.startsWith('temp-manual-'));

const otherUserIcon = computed(() => {
    if (!isOtherUser.value) return null;
    return discussionsStore.activeDiscussionParticipants[props.message.sender]?.icon;
});

const senderPersonalityIcon = computed(() => {
    if (!isAi.value || !props.message.sender) return null;
    const personality = dataStore.allPersonalities.find(p => p.name === props.message.sender);
    return personality ? personality.icon_base64 : null;
});

const lastUserImage = computed(() => {
    if (props.message.sender_type !== 'assistant' || !props.message.content.includes('<annotate>')) {
        return null;
    }
    const allMessages = discussionsStore.activeMessages;
    const currentMessageIndex = allMessages.findIndex(m => m.id === props.message.id);
    if (currentMessageIndex === -1) return null;
    for (let i = currentMessageIndex - 1; i >= 0; i--) {
        const msg = allMessages[i];
        if (msg.image_references && msg.image_references.length > 0) {
            return msg.image_references[msg.image_references.length - 1];
        }
    }
    return null;
});

const exportFormats = computed(() => {
    const formats = [];
    if (authStore.export_to_txt_enabled) formats.push({ label: 'Text (.txt)', value: 'txt' });
    if (authStore.export_to_markdown_enabled) formats.push({ label: 'Markdown (.md)', value: 'md' });
    if (authStore.export_to_html_enabled) formats.push({ label: 'HTML (.html)', value: 'html' });
    if (authStore.export_to_pdf_enabled) formats.push({ label: 'PDF (.pdf)', value: 'pdf' });
    if (authStore.export_to_docx_enabled) formats.push({ label: 'Word (.docx)', value: 'docx' });
    if (authStore.export_to_xlsx_enabled) formats.push({ label: 'Excel (.xlsx)', value: 'xlsx' });
    if (authStore.export_to_pptx_enabled) formats.push({ label: 'PowerPoint (.pptx)', value: 'pptx' });
    return formats;
});

function handleExport(format) {
    discussionsStore.exportMessage({
        discussionId: discussionsStore.currentDiscussionId,
        messageId: props.message.id,
        format: format,
    });
}

function handleSpeak() {
    if (messageTtsState.value.audioUrl) {
    } else if (!messageTtsState.value.isLoading) {
        const textToSpeak = props.message.content.replace(/```[\s\S]*?```/g, 'Code block.').replace(/<think>[\s\S]*?<\/think>/g, '');
        discussionsStore.generateTTSForMessage(props.message.id, textToSpeak);
    }
}

function isUrl(str) {
    if (typeof str !== 'string') return false;
    return str.startsWith('http://') || str.startsWith('https://');
}

function togglePreview(index) {
    if (previewMap.value[index]) {
        delete previewMap.value[index];
    } else {
        previewMap.value[index] = true;
    }
}

// Function to handle clicking citation buttons in the content
function handleCitationClick(index) {
    // Ensure sources are visible
    isSourcesVisible.value = true;
    
    // Find the source item. Assuming sortedSources order matches if we use index from props
    // We try to match by the 'index' property if available, or just use array index 
    // BUT sortedSources is sorted by score. The citation [1] refers to the index property we added in backend.
    
    nextTick(() => {
        // Find the element ref. We need to map index to the sorted list index or iterate
        const targetSourceIndex = sortedSources.value.findIndex(s => s.index === index);
        
        if (targetSourceIndex !== -1) {
            const el = sourceRefs.value[targetSourceIndex];
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                // Optional: Flash highlight effect
                el.classList.add('bg-yellow-100', 'dark:bg-yellow-900/50');
                setTimeout(() => {
                    el.classList.remove('bg-yellow-100', 'dark:bg-yellow-900/50');
                }, 2000);
            }
        } else {
             // Fallback to direct array index if no explicit index property
             const el = sourceRefs.value[index - 1]; // citations are 1-based
             if (el) {
                 el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                 el.classList.add('bg-yellow-100', 'dark:bg-yellow-900/50');
                 setTimeout(() => el.classList.remove('bg-yellow-100', 'dark:bg-yellow-900/50'), 2000);
             }
        }
    });
}

onMounted(() => {
    if (props.message.sources && props.message.sources.length > 3) {
        isSourcesVisible.value = false;
    } else {
        isSourcesVisible.value = true;
    }
    if (props.message.startInEditMode) {
        toggleEdit();
        delete props.message.startInEditMode;
    }
    
    // Initialize selected indices for each group
    if (imageGroups.value.length > 0) {
        imageGroups.value.forEach(group => {
            if (!selectedViewIndices.value[group.id]) {
                const activeIdx = group.indices.find(idx => isImageActive(idx));
                selectedViewIndices.value[group.id] = activeIdx !== undefined ? activeIdx : group.indices[group.indices.length - 1];
            }
        });
    }
});

const allImages = computed(() => {
    if (props.message.localImageUrls?.length > 0) return props.message.localImageUrls;
    if (props.message.image_references?.length > 0) return props.message.image_references;
    return [];
});

const imageGroups = computed(() => {
    const images = allImages.value;
    if (images.length === 0) return [];

    const metadata = props.message.metadata || {};
    const metaGroups = (metadata.image_generation_groups || []).concat(metadata.image_groups || []);
    
    const handledIndices = new Set();
    const resultGroups = [];

    // Temporary storage for slide items to group them
    let currentSlideGroup = null;

    // 1. Process defined groups
    metaGroups.forEach((g, idx) => {
        const groupIndices = g.indices.filter(i => i < images.length);
        if (groupIndices.length > 0) {
            groupIndices.forEach(i => handledIndices.add(i));

            if (g.type === 'slide_item') {
                if (!currentSlideGroup) {
                    currentSlideGroup = {
                        id: `slideshow_${idx}`,
                        title: "Generated Slideshow",
                        type: 'slideshow',
                        indices: [],
                        images: []
                    };
                    resultGroups.push(currentSlideGroup);
                }
                currentSlideGroup.indices.push(...groupIndices);
                currentSlideGroup.images.push(...groupIndices.map(i => images[i]));
            } else {
                // If we encounter a non-slide group, close the slide group sequence (if order matters in array)
                // However, logic here pushes to resultGroups immediately if new, so just resetting ref works.
                currentSlideGroup = null;

                resultGroups.push({
                    id: g.id || `gen_group_${idx}`,
                    title: g.prompt || g.title || (g.type === 'upload' ? `Image Pack ${idx + 1}` : `Image Generation ${idx + 1}`),
                    type: g.type || 'generated',
                    indices: groupIndices,
                    images: groupIndices.map(i => images[i])
                });
            }
        }
    });

    // 2. Collect leftover images as distinct "User Upload" packs if they aren't grouped
    const leftoverIndices = images.map((_, i) => i).filter(i => !handledIndices.has(i));
    if (leftoverIndices.length > 0) {
        // Create a SEPARATE group for each leftover image so they stack vertically
        leftoverIndices.forEach((imgIndex, i) => {
            resultGroups.push({
                id: `upload_${imgIndex}`,
                title: `Attachment ${i + 1}`,
                type: 'upload',
                indices: [imgIndex],
                images: [images[imgIndex]]
            });
        });
    }

    return resultGroups;
});

const isImageActive = (index) => {
    if (!props.message.active_images || props.message.active_images.length <= index) {
        return true; 
    }
    return props.message.active_images[index];
};

const toggleImage = (index) => {
    if (areActionsDisabled.value) {
        return;
    }
    
    const currentState = isImageActive(index);
    const desiredState = !currentState;
    
    discussionsStore.toggleImageActivation({
        messageId: props.message.id,
        imageIndex: index,
        active: desiredState
    });
};

function openImageViewer(index) {
    uiStore.openImageViewer({
        imageList: allImages.value.map(src => ({ src, prompt: 'Image from message' })),
        startIndex: index
    });
}

function openSlideshow(group) {
    // NEW: Open specific slideshow modal
    const slides = group.images.map((src, i) => ({ 
        src, 
        prompt: `Slide ${i + 1}`,
        id: `slide_${i}`
    }));
    
    uiStore.openSlideshow({
        slides: slides,
        startIndex: 0,
        title: group.title,
        messageId: props.message.id
    });
}

function handleImageClick(group, index) {
    if (group.type === 'slideshow' || group.type === 'slide_item') {
        openSlideshow(group);
    } else {
        openImageViewer(index);
    }
}

function canRegenerateImage(index, groupType) {
    // [UPDATED] Allow regeneration for slides too
    if (groupType === 'slideshow' || groupType === 'slide_item') return true;
    
    const infos = props.message.metadata?.generated_image_infos || [];
    return infos.some(info => info.index === index);
}

const isRegenerating = (groupId) => {
    const group = imageGroups.value.find(g => g.id === groupId);
    if (!group) return false;
    return group.indices.some(idx => 
        imageGenerationTasks.value.some(t => t.name.includes(`Regenerate Image ${idx}`))
    );
};

function handleRegenerateImage(index) {
    if (areActionsDisabled.value) return;
    discussionsStore.regenerateMessageImage(props.message.id, index);
}

function selectView(groupId, index) {
    selectedViewIndices.value[groupId] = index;
}

watch(() => props.message.image_references, (newRefs, oldRefs) => {
    if (newRefs && oldRefs && newRefs.length > oldRefs.length) {
        imageGroups.value.forEach(group => {
            const lastIndex = group.indices[group.indices.length - 1];
            if (lastIndex >= oldRefs.length) {
                selectedViewIndices.value[group.id] = lastIndex;
            }
        });
    }
}, { deep: true });

const containsCode = computed(() => {
    return props.message.content && props.message.content.includes('```');
});

const senderName = computed(() => {
    if (isCurrentUser.value) return authStore.user?.username || 'You';
    if (isOtherUser.value) return props.message.sender;
    if (isAi.value) return props.message.sender || 'Assistant';
    return props.message.sender || 'System';
});

const hasEvents = computed(() => props.message.events && props.message.events.length > 0);
const hasSources = computed(() => props.message.sources && props.message.sources.length > 0);
const sortedSources = computed(() => {
    if (!hasSources.value) return [];
    // If index property is present, sort by index first, then score
    return [...props.message.sources].sort((a, b) => {
        if (a.index && b.index) return a.index - b.index;
        return (b.score || 0) - (a.score || 0);
    });
});

const lastEventSummary = computed(() => {
    if (!hasEvents.value) return '';
    const lastEvent = props.message.events[props.message.events.length - 1];
    let summary = `Event: ${lastEvent.type}`;
    if (typeof lastEvent.content === 'string' && lastEvent.content.length > 0) {
        summary += ` - ${lastEvent.content.substring(0, 50)}${lastEvent.content.length > 50 ? '...' : ''}`;
    }
    return summary;
});

const eventIconMap = {
  'thought': IconThinking, 'tool_call': IconTool, 'observation': IconObservation,
  'info': IconInfo, 'exception': IconError, 'error': IconError,
  'scratchpad': IconScratchpad, 'default': IconEventDefault,
  'step_start': IconCog, 'step_end': IconStepEnd,
};

const groupedEvents = computed(() => {
    if (!hasEvents.value) return [];
    const result = [];
    const stack = [];
    const filteredEvents = props.message.events.filter(event => event.type !== 'sources');
    for (const event of filteredEvents) {
        const lowerType = event.type?.toLowerCase() || '';
        if (lowerType.includes('step_start')) {
            const newGroup = { type: 'step_group', startEvent: event, children: [], endEvent: null, isInitiallyOpen: false };
            if (stack.length > 0) stack[stack.length - 1].children.push(newGroup);
            else result.push(newGroup);
            stack.push(newGroup);
        } else if (lowerType.includes('step_end')) {
            if (stack.length > 0) {
                const currentGroup = stack.pop();
                currentGroup.endEvent = event;
                const hasContent = (currentGroup.startEvent.content && String(currentGroup.startEvent.content).trim() !== '') || (currentGroup.endEvent.content && String(currentGroup.endEvent.content).trim() !== '');
                if (currentGroup.children.length > 0 || hasContent) currentGroup.isInitiallyOpen = true;
            } else { result.push(event); }
        } else {
            if (stack.length > 0) stack[stack.length - 1].children.push(event);
            else result.push(event);
        }
    }
    return result;
});

function getEventIcon(type) {
  const lowerType = type?.toLowerCase() || 'default';
  if (eventIconMap[lowerType]) return eventIconMap[lowerType];
  const key = Object.keys(eventIconMap).find(k => k !== 'default' && lowerType.includes(k));
  return eventIconMap[key || 'default'];
}

const branchInfo = computed(() => {
    const hasMultipleBranches = props.message.branches && props.message.branches.length > 1;
    if (!hasMultipleBranches || props.message.sender_type !== 'user') return null;
    const currentMessages = discussionsStore.activeMessages;
    const currentMessageIndex = currentMessages.findIndex(m => m.id === props.message.id);
    const nextMessage = currentMessages[currentMessageIndex + 1];
    let activeBranchIndex = -1;
    if (nextMessage && nextMessage.parent_message_id === props.message.id) {
        activeBranchIndex = props.message.branches.findIndex(id => id === nextMessage.id);
    }
    if (activeBranchIndex === -1) activeBranchIndex = 0;
    return { isBranchPoint: true, current: activeBranchIndex + 1, total: props.message.branches.length, branchIds: props.message.branches, currentIndex: activeBranchIndex };
});

function navigateBranch(direction) {
    if (!branchInfo.value) return;
    const { branchIds, currentIndex } = branchInfo.value;
    const newIndex = (currentIndex + direction + branchIds.length) % branchIds.length;
    discussionsStore.switchBranch(branchIds[newIndex]);
}

const editorExtensions = computed(() => {
    const extensions = [EditorView.lineWrapping, keymap.of([{ key: "Mod-Enter", run: () => { handleSaveEdit(); return true; } }, { key: "Escape", run: () => { handleCancelEdit(); return true; } }])];
    if (uiStore.currentTheme === 'dark' || isCurrentUser.value) extensions.push(oneDark);
    return extensions;
});

function toggleEdit() {
    isEditing.value = !isEditing.value;
    if (isEditing.value) {
        editedContent.value = props.message.content;
        editedImages.value = (props.message.image_references || []).map(url => ({ url, isNew: false, file: null }));
        newImageFiles.value = [];
        isFormattingMenuOpen.value = false;
    }
}

async function handleSaveEdit() {
    if (isNewManualMessage.value) {
        await discussionsStore.saveManualMessage({ tempId: props.message.id, content: editedContent.value });
    } else {
        const keptImagesB64 = editedImages.value.filter(img => !img.isNew).map(img => img.url);
        await discussionsStore.saveMessageChanges({ messageId: props.message.id, newContent: editedContent.value, keptImagesB64: keptImagesB64, newImageFiles: newImageFiles.value });
        isEditing.value = false;
    }
}

function removeEditedImage(index) {
    const removed = editedImages.value.splice(index, 1);
    if (removed.isNew) {
        const fileIndex = newImageFiles.value.findIndex(f => f === removed.file);
        if (fileIndex > -1) newImageFiles.value.splice(index, 1);
    }
}

function triggerEditImageUpload() { editImageInput.value.click(); }
function handleEditImageSelected(event) {
    const files = Array.from(event.target.files);
    for (const file of files) {
        const localUrl = URL.createObjectURL(file);
        editedImages.value.push({ url: localUrl, isNew: true, file: file });
        newImageFiles.value.push(file);
    }
    event.target.value = '';
}
function handleCancelEdit() {
    if (isNewManualMessage.value) {
        const index = discussionsStore.activeMessages.findIndex(m => m.id === props.message.id);
        if (index !== -1) discussionsStore.activeMessages.splice(index, 1);
    } else {
        isEditing.value = false;
    }
}
function handleEditorReady(payload) { codeMirrorView.value = payload.view; }
function copyContent() { uiStore.copyToClipboard(props.message.content); }
async function handleDelete() { const confirmed = await uiStore.showConfirmation({ title: 'Delete Message', message: 'This will delete the message and its entire branch.', confirmText: 'Delete' }); if (confirmed.confirmed) discussionsStore.deleteMessage({ messageId: props.message.id}); }
function handleGrade(change) { discussionsStore.gradeMessage({ messageId: props.message.id, change }); }
function handleExportCode() { discussionsStore.exportMessageCodeToZip({ content: props.message.content, title: discussionsStore.activeDiscussion?.title || 'discussion' }); }
function handleBuildNewDiscussion(event) { event.stopPropagation(); discussionsStore.createDiscussionFromMessage({ discussionId: discussionsStore.currentDiscussionId, messageId: props.message.id }); }

function handleBranchOrRegenerate() {
    discussionsStore.initiateBranch(props.message);
}

// NEW: Function to handle regeneration requests from the renderer tags
function handleTagRegeneration(part) {
    if (areActionsDisabled.value) return;
    
    discussionsStore.triggerTagGeneration({
        messageId: props.message.id,
        tagContent: part.prompt,
        tagType: part.mode, 
        rawTag: part.raw
    });
}

function showSourceDetails(source) { uiStore.openModal('sourceViewer', { ...source }); }
function openAllSourcesSearch() { uiStore.openModal('allSourcesSearch', { sources: props.message.sources }); }
function getSimilarityColor(score) { if (score === undefined || score === null) return 'bg-gray-400 dark:bg-gray-600'; if (score >= 80) return 'bg-green-500'; if (score >= 50) return 'bg-yellow-500'; return 'bg-red-500'; }

</script>
<template>
    <div v-if="isSystem" class="w-full flex justify-center my-2" :data-message-id="message.id">
        <div class="system-bubble" v-html="parsedMarkdown(message.content)"></div>
    </div>
    <div v-else class="message-row group" :class="{
        'bg-white dark:bg-slate-800': isAi || isOtherUser,
        'border-t border-gray-200 dark:border-gray-700/50': isAi || isOtherUser
    }">
        <div class="message-content-container">
            <!-- Avatar -->
            <div class="flex-shrink-0 pt-1">
                <UserAvatar :icon="isCurrentUser ? user.icon : (isAi ? senderPersonalityIcon : otherUserIcon)" :username="senderName" size-class="h-8 w-8" />
            </div>

            <!-- Main Content -->
            <div class="flex-1 min-w-0">
                <div class="font-semibold text-sm text-gray-800 dark:text-gray-100 mb-2 flex items-center flex-wrap gap-x-2 gap-y-1">
                    <span>{{ senderName }}</span>
                    <div v-if="isAi && (message.binding_name || message.model_name)" class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 font-mono">
                        <span>{{ message.binding_name }}{{ message.binding_name && message.model_name ? '/' : '' }}{{ message.model_name }}</span>
                        
                        <template v-if="message.metadata && (message.metadata.ttft !== undefined || message.metadata.tps !== undefined)">
                            <span class="text-gray-300 dark:text-gray-600">|</span>
                            <span v-if="message.metadata.ttft !== undefined" :title="`Time to First Token: ${message.metadata.ttft} ms`">
                                TTFT: {{ message.metadata.ttft }}ms
                            </span>
                            <span v-if="message.metadata.tps !== undefined" :title="`Tokens per Second: ${message.metadata.tps.toFixed(2)}`">
                                TPS: {{ message.metadata.tps.toFixed(2) }}
                            </span>
                        </template>
                    </div>
                </div>
                
                <!-- Content Wrapper -->
                <div class="message-content-wrapper">
                    <div v-if="!isEditing">
                        <!-- Text Content -->
                        <MessageContentRenderer
                            :content="message.content"
                            :is-streaming="message.isStreaming"
                            :is-user="isCurrentUser"
                            :has-images="allImages.length > 0"
                            :last-user-image="lastUserImage"
                            :message-id="message.id"
                            @regenerate="handleTagRegeneration"
                            @citation-click="handleCitationClick"
                        />

                        <!-- Centralized Image Zone with Gallery Underneath -->
                        <!-- MOVED BELOW TEXT CONTENT -->
                        <div v-if="imageGroups.length > 0" class="my-4 space-y-6">
                            
                            <!-- Iterate over Groups -->
                            <div v-for="group in imageGroups" :key="group.id" class="image-group-container">
                                <!-- Group Header (for generated series or uploaded packs) -->
                                <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1 flex justify-between">
                                    <span class="truncate" :title="group.title">{{ group.title }}</span>
                                    <span class="text-[10px] bg-gray-200 dark:bg-gray-700 px-1.5 rounded">{{ group.images.length }} version(s)</span>
                                </div>
                                
                                <!-- Export Actions (NEW) -->
                                <div class="flex gap-2 my-1" v-if="group.type === 'slideshow' || group.type === 'slide_item'">
                                     <button @click="handleExport('pptx')" class="btn btn-secondary btn-xs flex items-center gap-1">
                                        <IconArrowDownTray class="w-3 h-3"/> Download PPTX
                                     </button>
                                     <button @click="handleExport('pdf')" class="btn btn-secondary btn-xs flex items-center gap-1">
                                        <IconArrowDownTray class="w-3 h-3"/> Download PDF
                                     </button>
                                     <button @click.stop="openSlideshow(group)" class="btn btn-primary btn-xs flex items-center gap-1">
                                        <IconPlayCircle class="w-3 h-3"/> Play Slideshow
                                     </button>
                                </div>

                                <!-- Main Image Display for this Group -->
                                <div v-if="group.images.length > 0" 
                                     class="main-image-viewport relative aspect-video sm:aspect-square max-h-[500px] w-full rounded-2xl overflow-hidden bg-gray-100 dark:bg-gray-900 border-2 shadow-lg group/viewport transition-all duration-300"
                                     :class="!isImageActive(selectedViewIndices[group.id] ?? group.indices[0]) ? 'border-red-500' : 'border-transparent dark:border-gray-700'"
                                >
                                    
                                    <!-- Spinner Overlay for Regenerating -->
                                    <div v-if="isRegenerating(group.id)" class="absolute inset-0 z-20 bg-white/60 dark:bg-black/60 backdrop-blur-sm flex flex-col items-center justify-center">
                                        <IconAnimateSpin class="w-10 h-10 text-blue-500 animate-spin mb-2" />
                                        <span class="text-sm font-bold text-gray-800 dark:text-gray-200">Generating variation...</span>
                                    </div>

                                    <!-- Handle click on image -->
                                    <div @click.stop="handleImageClick(group, selectedViewIndices[group.id] ?? group.indices[0])" class="w-full h-full cursor-pointer">
                                        <AuthenticatedImage 
                                            :src="allImages[selectedViewIndices[group.id] ?? group.indices[0]]" 
                                            class="w-full h-full object-contain"
                                        />
                                    </div>

                                    <!-- Viewport Controls Overlay -->
                                    <div class="absolute inset-0 bg-black/40 opacity-0 group-hover/viewport:opacity-100 transition-opacity flex items-center justify-center gap-3 z-10 pointer-events-none">
                                        <!-- Need pointer-events-auto on buttons to ensure they are clickable over the container -->
                                        <button @click.stop="handleImageClick(group, selectedViewIndices[group.id] ?? group.indices[0])" class="pointer-events-auto p-3 bg-white/20 hover:bg-white/40 text-white rounded-full backdrop-blur-md shadow-xl transition-all active:scale-90" title="Full Screen">
                                            <IconMaximize class="w-6 h-6" />
                                        </button>
                                        
                                        <!-- Visibility Toggle -->
                                        <button @click.stop="toggleImage(selectedViewIndices[group.id] ?? group.indices[0])" 
                                                :disabled="areActionsDisabled"
                                                class="pointer-events-auto p-3 bg-white/20 hover:bg-white/40 text-white rounded-full backdrop-blur-md shadow-xl transition-all active:scale-90 disabled:opacity-50 disabled:cursor-not-allowed" 
                                                :title="isImageActive(selectedViewIndices[group.id] ?? group.indices[0]) ? 'Deactivate (Hide from LLM)' : 'Activate (Show to LLM)'">
                                            <IconEye v-if="isImageActive(selectedViewIndices[group.id] ?? group.indices[0])" class="w-6 h-6" />
                                            <IconEyeOff v-else class="w-6 h-6 text-red-300" />
                                        </button>

                                        <!-- Regenerate (Only for generated) -->
                                        <button v-if="(group.type === 'generated' || group.type === 'slideshow' || group.type === 'slide_item') && canRegenerateImage(selectedViewIndices[group.id] ?? group.indices[0], group.type)" 
                                                @click.stop="handleRegenerateImage(selectedViewIndices[group.id] ?? group.indices[0])" 
                                                class="pointer-events-auto p-3 bg-white/20 hover:bg-green-500/80 text-white rounded-full backdrop-blur-md shadow-xl transition-all active:scale-90 disabled:opacity-50" 
                                                :disabled="areActionsDisabled"
                                                title="Regenerate another iteration">
                                            <IconRefresh class="w-6 h-6" />
                                        </button>
                                    </div>

                                    <!-- Visibility Status Badge (Discrete) -->
                                    <div v-if="!isImageActive(selectedViewIndices[group.id] ?? group.indices[0])" class="absolute top-3 right-3 z-10 pointer-events-none">
                                         <div class="px-2 py-1 bg-red-500/90 text-white rounded flex items-center gap-1.5 shadow-sm backdrop-blur-md">
                                             <IconEyeOff class="w-3 h-3" />
                                             <span class="font-bold uppercase tracking-widest text-[9px]">Inactive</span>
                                         </div>
                                    </div>
                                </div>

                                <!-- Gallery Thumbnails -->
                                <div v-if="group.images.length > 1" class="gallery-thumb-row flex items-center gap-2 overflow-x-auto pb-2 pt-2 custom-scrollbar">
                                    <div v-for="(imgSrc, idx) in group.images" 
                                         :key="`${group.id}-thumb-${idx}`"
                                         class="relative w-16 h-16 sm:w-20 sm:h-20 shrink-0 rounded-xl overflow-hidden border-2 transition-all duration-200 cursor-pointer shadow-sm"
                                         :class="[
                                            (selectedViewIndices[group.id] ?? group.indices[0]) === group.indices[idx] ? 'border-blue-500 scale-105 shadow-md' : 'border-transparent hover:border-gray-300 dark:hover:border-gray-600',
                                            !isImageActive(group.indices[idx]) ? 'border-red-500' : ''
                                         ]"
                                         @click.stop="selectView(group.id, group.indices[idx])"
                                    >
                                        <AuthenticatedImage :src="allImages[group.indices[idx]]" class="w-full h-full object-cover" />
                                        
                                        <!-- Mini Status Indicators -->
                                        <div v-if="!isImageActive(group.indices[idx])" class="absolute top-0 right-0 p-1 bg-red-500/90 rounded-bl-lg">
                                            <IconEyeOff class="w-3 h-3 text-white" />
                                        </div>
                                        <div v-else-if="isImageActive(group.indices[idx])" class="absolute top-0.5 right-0.5 bg-green-500 text-white rounded-full p-0.5 shadow-sm">
                                            <IconCheckCircle class="w-3 h-3" />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div v-if="message.isStreaming && !message.content && (!allImages || allImages.length === 0)" class="typing-indicator">
                            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
                        </div>
                    </div>
                    <!-- Editing Mode -->
                    <div v-else class="w-full">
                        <input type="file" ref="editImageInput" @change="handleEditImageSelected" multiple accept="image/*" class="hidden">
                        <div v-if="editedImages.length > 0" class="mb-2 p-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md">
                            <div class="flex flex-wrap gap-2">
                                <div v-for="(image, index) in editedImages" :key="image.url" class="relative w-16 h-16">
                                    <img :src="image.url" class="w-full h-full object-cover rounded-md" alt="Image preview" />
                                    <button @click="removeEditedImage(index)" type="button" class="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold leading-none">×</button>
                                </div>
                            </div>
                        </div>
                        <CodeMirrorEditor
                            v-model="editedContent"
                            placeholder="Enter your message..."
                            :autofocus="true"
                            :extensions="editorExtensions"
                            editorClass="max-h-[500px]"
                            @ready="handleEditorReady"
                        />
                        <div class="flex justify-between items-center mt-2">
                             <button v-if="currentModelVisionSupport" @click="triggerEditImageUpload" class="btn btn-secondary !p-2" title="Add Images">
                                <IconPhoto class="w-5 h-5" />
                            </button>
                            <div class="flex justify-end space-x-2">
                                <button @click="handleCancelEdit" class="btn btn-secondary !py-1 !px-3">Cancel</button>
                                <button @click="handleSaveEdit" class="btn btn-primary !py-1 !px-3">Save</button>
                            </div>
                        </div>
                    </div>
                </div>

                 <!-- TTS Player -->
                 <div v-if="isAi && isTtsActive && (messageTtsState.audioUrl || messageTtsState.isLoading)" class="mt-3">
                    <div v-if="messageTtsState.isLoading" class="flex items-center gap-2 text-sm text-gray-500">
                        <IconAnimateSpin class="w-4 h-4 animate-spin" />
                        <span>Generating audio...</span>
                    </div>
                    <div v-else-if="messageTtsState.error" class="text-sm text-red-500">{{ messageTtsState.error }}</div>
                    <audio
                        v-else-if="messageTtsState.audioUrl"
                        ref="audioPlayerRef"
                        :src="messageTtsState.audioUrl"
                        controls
                        class="w-full h-10"
                        @play="discussionsStore.playAudio(message.id, $event.target)"
                        @pause="discussionsStore.onAudioPausedOrEnded(message.id)"
                        @ended="discussionsStore.onAudioPausedOrEnded(message.id)"
                    ></audio>
                </div>


                <!-- Sources -->
                <div v-if="hasSources" class="mt-2 border-t border-gray-200 dark:border-gray-700/50 pt-2">
                    <div class="flex items-center gap-2">
                        <button @click="isSourcesVisible = !isSourcesVisible" class="flex items-center gap-2 text-xs font-semibold text-gray-500 dark:text-gray-400 cursor-pointer select-none">
                            <IconChevronRight class="toggle-icon" :class="{'rotate-90': isSourcesVisible}" />
                            <span>Sources ({{sortedSources.length}})</span>
                        </button>
                        <button @click="openAllSourcesSearch" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600" title="Search all sources">
                            <IconMagnifyingGlass class="w-4 h-4 text-gray-500 dark:text-gray-400" />
                        </button>
                    </div>

                    <div v-if="isSourcesVisible" class="mt-2 space-y-2 pl-4">
                        <div v-for="(source, index) in sortedSources" :key="index" :ref="el => { if(el) sourceRefs[index] = el }" class="flex flex-col gap-1 transition-all duration-300">
                             <div class="flex items-center justify-between p-2 rounded-lg bg-gray-50 dark:bg-gray-800/50 border border-transparent hover:border-gray-300 dark:hover:border-gray-600 transition-all cursor-pointer group" @click="showSourceDetails(source)">
                                <div class="flex items-center gap-2 min-w-0">
                                    <div class="similarity-chip" :class="getSimilarityColor(source.score)" :title="typeof source.score === 'number' ? `Similarity: ${(source.score).toFixed(1)}%` : 'Similarity: N/A'"></div>
                                    <div class="truncate text-xs text-gray-700 dark:text-gray-300" :title="source.title">
                                        <span v-if="source.index" class="font-mono font-bold mr-1">[{{ source.index }}]</span>
                                        {{ source.title }}
                                    </div>
                                </div>
                                <div class="flex items-center gap-2 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                                    <div v-if="typeof source.score === 'number'" class="font-mono text-[10px] text-gray-500 dark:text-gray-400 flex-shrink-0">{{ (source.score).toFixed(1) }}%</div>
                                    <!-- Web Link -->
                                    <a v-if="isUrl(source.source)" :href="source.source" target="_blank" @click.stop class="p-1 rounded hover:bg-blue-100 dark:hover:bg-blue-900 text-blue-500 transition-colors" title="Open Website">
                                        <IconGlobeAlt class="w-3.5 h-3.5" />
                                    </a>
                                    <!-- Sneak Peek -->
                                    <button v-if="isUrl(source.source)" @click.stop="togglePreview(index)" class="p-1 rounded hover:bg-purple-100 dark:hover:bg-purple-900 text-purple-500 transition-colors" :class="{'bg-purple-100 dark:bg-purple-900': previewMap[index]}" title="Toggle Preview">
                                        <IconEye class="w-3.5 h-3.5" />
                                    </button>
                                </div>
                             </div>
                             
                             <!-- Inline Preview -->
                             <div v-if="previewMap[index]" class="w-full h-80 mt-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-white overflow-hidden relative shadow-inner animate-in fade-in zoom-in-95 duration-200">
                                 <iframe :src="source.source" class="w-full h-full" sandbox="allow-scripts allow-same-origin"></iframe>
                                 <div class="absolute top-2 right-2">
                                     <button @click="togglePreview(index)" class="p-1 bg-gray-900/50 text-white rounded-full hover:bg-gray-900 transition-colors"><IconXMark class="w-4 h-4"/></button>
                                 </div>
                                 <div class="absolute inset-0 pointer-events-none flex items-center justify-center bg-gray-50/50 dark:bg-gray-900/50 -z-10">
                                    <span class="text-xs text-gray-400">Loading preview...</span>
                                 </div>
                             </div>
                        </div>
                    </div>
                </div>
                
                <!-- Events -->
                <details v-if="hasEvents" class="events-container" :open="!isEventsCollapsed" @toggle="event => isEventsCollapsed = !event.target.open">
                    <summary class="events-summary"><IconChevronRight class="toggle-icon" /><span>{{ isEventsCollapsed ? 'Show Events' : 'Hide Events' }}</span><span v-if="isEventsCollapsed" class="last-event-snippet">{{ lastEventSummary }}</span></summary>
                    <div class="events-content">
                        <template v-for="(item, index) in groupedEvents" :key="index">
                            <details v-if="item.type === 'step_group'" class="step-group-block" :open="item.isInitiallyOpen">
                                <summary class="step-group-summary">
                                    <IconChevronRight class="toggle-icon" />
                                    <div class="event-icon-container" :title="item.startEvent.type"><component :is="getEventIcon(item.startEvent.type)" /></div>
                                    <div class="event-details font-semibold prose-sm dark:prose-invert" v-html="parsedMarkdown(String(item.startEvent.content || 'Step'))"></div>
                                </summary>
                                <div class="step-group-content">
                                    <div v-for="(childEvent, childIndex) in item.children" :key="childIndex" class="event-item" :class="`event-type-${childEvent.type.toLowerCase()}`">
                                        <div class="event-icon-container" :title="childEvent.type"><component :is="getEventIcon(childEvent.type)" /></div>
                                        <div class="event-details">
                                            <div class="event-title">{{ childEvent.type }}</div>
                                            <div class="event-body">
                                                <div v-if="typeof childEvent.content === 'string'" class="message-prose" v-html="parsedMarkdown(childEvent.content)"></div>
                                                <StepDetail v-else :data="childEvent.content" />
                                            </div>
                                        </div>
                                    </div>
                                    <div v-if="item.endEvent" class="step-end-block">
                                        <div class="event-item">
                                            <div class="event-icon-container" :title="item.endEvent.type"><component :is="getEventIcon(item.endEvent.type)" /></div>
                                            <div class="event-details">
                                                <div class="event-title">Step Result</div>
                                                <div v-if="item.endEvent.content" class="event-body">
                                                    <div v-if="typeof item.endEvent.content === 'string'" class="message-prose" v-html="parsedMarkdown(item.endEvent.content)"></div>
                                                    <StepDetail v-else :data="item.endEvent.content" />
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </details>

                            <div v-else class="event-item" :class="`event-type-${item.type.toLowerCase()}`">
                                <div class="event-icon-container" :title="item.type"><component :is="getEventIcon(item.type)" /></div>
                                <div class="event-details">
                                    <div class="event-title">{{ item.type }}</div>
                                    <div class="event-body">
                                        <div v-if="typeof item.content === 'string'" class="message-prose" v-html="parsedMarkdown(item.content)"></div>
                                        <StepDetail v-else :data="item.content" />
                                    </div>
                                </div>
                            </div>
                        </template>
                    </div>
                </details>

                <!-- Footer -->
                <div class="message-footer">
                    <div class="flex-grow flex items-center flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
                        <div v-if="branchInfo" class="detail-badge branch-badge-nav">
                            <button @click="navigateBranch(-1)" class="p-1 rounded-full hover:bg-black/10 dark:hover:bg-white/10" title="Previous Branch">
                                <IconChevronRight class="w-3.5 h-3.5 rotate-180" />
                            </button>
                            <span class="font-mono text-xs">{{ branchInfo.current }}/{{ branchInfo.total }}</span>
                            <button @click="navigateBranch(1)" class="p-1 rounded-full hover:bg-black/10 dark:hover:bg-white/10" title="Next Branch">
                                <IconChevronRight class="w-3.5 h-3.5" />
                            </button>
                        </div>
                        <div v-if="isAi && message.token_count" class="detail-badge"><IconToken class="w-3.5 h-3.5" /><span>{{ message.token_count }}</span></div>
                    </div>
                    <div v-if="!isEditing" class="flex-shrink-0 flex items-center gap-1">
                        <div class="actions flex items-center space-x-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button v-if="isTtsActive && isAi" @click="handleSpeak" :title="messageTtsState.isLoading ? 'Generating...' : 'Speak'" class="action-btn" :disabled="messageTtsState.isLoading">
                                <IconAnimateSpin v-if="messageTtsState.isLoading" class="w-4 h-4 animate-spin" />
                                <IconSpeakerWave v-else class="w-4 h-4" />
                            </button>
                            <DropdownMenu v-if="exportFormats.length > 0" title="Export" icon="ticket" button-class="action-btn" collection="ui">
                                <button v-for="format in exportFormats" :key="format.value" @click="handleExport(format.value)" class="w-full text-left p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-sm">
                                    {{ format.label }}
                                </button>
                            </DropdownMenu>
                            <button v-if="containsCode" :disabled="areActionsDisabled" @click="handleExportCode" title="Export Code" class="action-btn"><IconCode class="w-4 h-4" /></button>
                            <button :disabled="areActionsDisabled" @click="copyContent" title="Copy" class="action-btn"><IconCopy /></button>
                            <button :disabled="areActionsDisabled" @click="toggleEdit" title="Edit" class="action-btn"><IconPencil /></button>
                            <button :disabled="areActionsDisabled" @click="handleBranchOrRegenerate" :title="isCurrentUser ? 'Resend / Branch' : 'Regenerate'" class="action-btn"><IconRefresh /></button>
                            <button :disabled="areActionsDisabled" @click="handleBuildNewDiscussion" title="Build a new discussion from here" class="action-btn"><IconGitBranch class="w-4 h-4" /></button>
                            <button :disabled="areActionsDisabled" @click="handleDelete" title="Delete" class="action-btn text-red-500 hover:bg-red-200 dark:hover:bg-red-700"><IconTrash /></button>
                        </div>
                        <div v-if="isAi" class="message-rating">
                            <button :disabled="areActionsDisabled" @click="handleGrade(1)" title="Good response" class="rating-btn upvote" :class="{ 'active': message.user_grade > 0 }"><IconThumbUp /></button>
                            <span class="rating-score">{{ message.user_grade || 0 }}</span>
                            <button :disabled="areActionsDisabled" @click="handleGrade(-1)" title="Bad response" class="rating-btn downvote" :class="{ 'active': message.user_grade < 0 }"><IconThumbDown /></button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
<style scoped>
.message-prose {
    @apply prose prose-base dark:prose-invert max-w-none break-words;
    font-size: var(--message-font-size, 14px);
}
.btn-icon-sm { @apply p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors flex items-center justify-center; }
.think-block { @apply bg-blue-50 dark:bg-gray-900/40 border border-blue-200 dark:border-blue-800/30 rounded-lg; }
details[open] > .think-summary { @apply border-b border-blue-200 dark:border-blue-800/30; }
.think-summary { @apply flex items-center gap-2 p-2 text-sm font-semibold text-blue-800 dark:text-blue-200 cursor-pointer list-none select-none; -webkit-tap-highlight-color: transparent; }
.think-summary:focus-visible { @apply ring-2 ring-blue-400 outline-none; }
.think-summary::-webkit-details-marker { display: none; }
.think-content { @apply p-3; }
.document-block { @apply bg-gray-50 dark:bg-gray-900/40 border border-gray-200 dark:border-gray-700/50 rounded-lg; }
.document-summary { @apply flex items-center gap-2 p-2 text-sm font-semibold text-gray-800 dark:text-gray-200 cursor-pointer list-none select-none; -webkit-tap-highlight-color: transparent; }
.document-summary:focus-visible { @apply ring-2 ring-blue-400 outline-none; }
.document-summary::-webkit-details-marker { display: none; }
details[open] > .document-summary { @apply border-b border-gray-200 dark:border-gray-700/50; }
.document-content { @apply p-3; }
</style>
