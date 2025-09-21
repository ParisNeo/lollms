<script setup>
import { computed, ref, onMounted, watch } from 'vue';
import { marked } from 'marked';
import { useAuthStore } from '../../stores/auth';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
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
import IconStepStart from '../../assets/icons/IconStepStart.vue';
import IconStepEnd from '../../assets/icons/IconStepEnd.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
});

// --- Markdown Parsing Logic ---
const mathPlaceholders = new Map();
let mathCounter = 0;

function protectMath(text) {
    if (!text) return text;
    mathCounter = 0;
    mathPlaceholders.clear();

    return text.replace(/(\$\$[\s\S]*?\$\$|\$[\s\S]*?\$)/g, (match) => {
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
// --- End Markdown Parsing Logic ---


const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const dataStore = useDataStore();
const { currentModelVisionSupport } = storeToRefs(discussionsStore);

const isEventsCollapsed = ref(true);
const isEditing = ref(false);
const editedContent = ref('');
const codeMirrorView = ref(null);
const isFormattingMenuOpen = ref(false);
const isSourcesVisible = ref(false);
const editedImages = ref([]);
const newImageFiles = ref([]);
const editImageInput = ref(null);

const areActionsDisabled = computed(() => discussionsStore.generationInProgress);
const user = computed(() => authStore.user);

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
});

const imagesToRender = computed(() => {
    if (props.message.localImageUrls?.length > 0) return props.message.localImageUrls;
    if (props.message.image_references?.length > 0) return props.message.image_references;
    return [];
});

const isImageActive = (index) => {
    if (!props.message.active_images || props.message.active_images.length <= index) {
        return true; // Default to active if array is missing or out of bounds
    }
    return props.message.active_images[index];
};

const toggleImage = (index) => {
    if (areActionsDisabled.value) return;
    discussionsStore.toggleImageActivation({
        messageId: props.message.id,
        imageIndex: index
    });
};

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
    return [...props.message.sources].sort((a, b) => (b.similarity_percent || 0) - (a.similarity_percent || 0));
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
  'step_start': IconStepStart, 'step_end': IconStepEnd,
};

function getEventIcon(type) {
  const lowerType = type?.toLowerCase() || 'default';
  if (eventIconMap[lowerType]) return eventIconMap[lowerType];
  const key = Object.keys(eventIconMap).find(k => k !== 'default' && lowerType.includes(k));
  return eventIconMap[key || 'default'];
}

const branchInfo = computed(() => {
    const hasMultipleBranches = props.message.branches && props.message.branches.length > 1;
    if (!hasMultipleBranches || props.message.sender_type !== 'user') return null; // Only show for user messages with multiple AI children

    // Find the immediate child of this user message that is currently displayed in the active messages path
    const currentMessages = discussionsStore.activeMessages;
    const currentMessageIndex = currentMessages.findIndex(m => m.id === props.message.id);
    const nextMessage = currentMessages[currentMessageIndex + 1]; // This should be the AI response to this user message

    let activeBranchIndex = -1;
    if (nextMessage && nextMessage.parent_message_id === props.message.id) {
        activeBranchIndex = props.message.branches.findIndex(id => id === nextMessage.id);
    }
    
    // Fallback: If no next message or it's not a direct child (e.g., initial load of a new branch tip), default to the first branch
    // This handles cases where the current branch might have been deleted, or a fresh load of a discussion where
    // the active_branch_id is a child that is not the first in the `branches` array.
    if (activeBranchIndex === -1) {
        activeBranchIndex = 0; // Default to first branch if we can't determine which one is active
    }

    return {
        isBranchPoint: true,
        current: activeBranchIndex + 1, // 1-based index
        total: props.message.branches.length,
        branchIds: props.message.branches,
        currentIndex: activeBranchIndex, // 0-based index
    };
});

function navigateBranch(direction) {
    if (!branchInfo.value) return;
    const { branchIds, currentIndex } = branchInfo.value;
    const newIndex = (currentIndex + direction + branchIds.length) % branchIds.length;
    discussionsStore.switchBranch(branchIds[newIndex]);
}

const editorExtensions = computed(() => {
    const extensions = [
        EditorView.lineWrapping,
        keymap.of([
            { key: "Mod-Enter", run: () => { handleSaveEdit(); return true; }},
            { key: "Escape", run: () => { handleCancelEdit(); return true; }}
        ])
    ];
    if (uiStore.currentTheme === 'dark' || isCurrentUser.value) {
        extensions.push(oneDark);
    }
    return extensions;
});


function toggleEdit() {
    isEditing.value = !isEditing.value;
    if (isEditing.value) {
        editedContent.value = props.message.content;
        // FIX: Ensure image_references is treated as an array even if it's null/undefined
        editedImages.value = (props.message.image_references || []).map(url => ({ url, isNew: false, file: null }));
        newImageFiles.value = [];
        isFormattingMenuOpen.value = false;
    }
}

async function handleSaveEdit() {
    if (isNewManualMessage.value) {
        // This flow is simpler and should be handled separately if it needs image support
        await discussionsStore.saveManualMessage({
            tempId: props.message.id,
            content: editedContent.value
        });
    } else {
        const keptImagesB64 = editedImages.value
            .filter(img => !img.isNew)
            .map(img => img.url.split(',')); // Extract base64 part

        await discussionsStore.saveMessageChanges({
            messageId: props.message.id,
            newContent: editedContent.value,
            keptImagesB64: keptImagesB64,
            newImageFiles: newImageFiles.value
        });
        isEditing.value = false;
    }
}

function removeEditedImage(index) {
    const removed = editedImages.value.splice(index, 1);
    if (removed.isNew) {
        // Also remove from the new files list
        const fileIndex = newImageFiles.value.findIndex(f => f === removed.file);
        if (fileIndex > -1) {
            newImageFiles.value.splice(index, 1);
        }
    }
}

function triggerEditImageUpload() {
    editImageInput.value.click();
}

function handleEditImageSelected(event) {
    const files = Array.from(event.target.files);
    for (const file of files) {
        const localUrl = URL.createObjectURL(file);
        editedImages.value.push({ url: localUrl, isNew: true, file: file });
        newImageFiles.value.push(file);
    }
    event.target.value = ''; // Reset input
}


function handleCancelEdit() {
    if (isNewManualMessage.value) {
        // If it's a new manual message, cancel means removing it.
        const index = discussionsStore.activeMessages.findIndex(m => m.id === props.message.id);
        if (index !== -1) {
            discussionsStore.activeMessages.splice(index, 1);
        }
    } else {
        isEditing.value = false;
    }
}
function handleEditorReady(payload) { codeMirrorView.value = payload.view; }
function copyContent() { uiStore.copyToClipboard(props.message.content); }
async function handleDelete() { const confirmed = await uiStore.showConfirmation({ title: 'Delete Message', message: 'This will delete the message and its entire branch.', confirmText: 'Delete' }); if (confirmed) discussionsStore.deleteMessage({ messageId: props.message.id}); }
function handleGrade(change) { discussionsStore.gradeMessage({ messageId: props.message.id, change }); }

function handleExportCode() {
    discussionsStore.exportMessageCodeToZip({
        content: props.message.content,
        title: discussionsStore.activeDiscussion?.title || 'discussion'
    });
}

function handleBranchOrRegenerate() {
    let messageToBranchFrom = props.message.sender_type === 'user' ? props.message : null;
    if (!messageToBranchFrom) {
        const currentMessageIndex = discussionsStore.activeMessages.findIndex(m => m.id === props.message.id);
        for (let i = currentMessageIndex - 1; i >= 0; i--) {
            const prevMsg = discussionsStore.activeMessages[i];
            if (prevMsg?.sender_type === 'user') { messageToBranchFrom = prevMsg; break; }
        }
    }
    if (messageToBranchFrom) discussionsStore.initiateBranch(messageToBranchFrom);
    else uiStore.addNotification('Could not find a valid user prompt to regenerate from.', 'error');
}

function showSourceDetails(source) {
    uiStore.openModal('artefactViewer', { ...source });
}

function getSimilarityColor(score) {
  if (score === undefined || score === null) return 'bg-gray-400 dark:bg-gray-600';
  if (score >= 85) return 'bg-green-500';
  if (score >= 70) return 'bg-yellow-500';
  return 'bg-red-500';
}

function insertTextAtCursor(before, after = '', placeholder = '') {
    const view = codeMirrorView.value; if (!view) return;
    const { from, to } = view.state.selection.main;
    const selectedText = view.state.doc.sliceString(from, to);
    let textToInsert, selStart, selEnd;
    if (selectedText) { textToInsert = `${before}${selectedText}${after}`; selStart = from + before.length; selEnd = selStart + selectedText.length; } 
    else { textToInsert = `${before}${placeholder}${after}`; selStart = from + before.length; selEnd = selStart + placeholder.length; }
    view.dispatch({ changes: { from: to, to: to, insert: textToInsert }, selection: { anchor: selStart, head: selEnd } });
    view.focus();
}
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
                <UserAvatar v-if="isCurrentUser" :icon="user.icon" :username="user.username" size-class="h-8 w-8" />
                <UserAvatar v-else-if="isAi || isOtherUser" :icon="isAi ? senderPersonalityIcon : otherUserIcon" :username="senderName" size-class="h-8 w-8" />
            </div>

            <!-- Main Content -->
            <div class="flex-1 min-w-0">
                <div class="font-semibold text-sm text-gray-800 dark:text-gray-100 mb-2 flex items-center">
                    <span>{{ senderName }}</span>
                    <span v-if="isAi && (message.binding_name || message.model_name)" class="model-info ml-2">
                        {{ message.binding_name }}{{ message.binding_name && message.model_name ? '/' : '' }}{{ message.model_name }}
                    </span>
                </div>
                
                <!-- Content Wrapper -->
                <div class="message-content-wrapper">
                    <div v-if="!isEditing">
                        <div v-if="imagesToRender.length > 0" class="my-2 grid gap-2" :class="[imagesToRender.length > 1 ? 'grid-cols-2 md:grid-cols-3' : 'grid-cols-1']">
                            <div v-for="(imgSrc, index) in imagesToRender" 
                                 :key="imgSrc"
                                 @click.stop="uiStore.openImageViewer(imgSrc)"
                                 class="group/image relative rounded-lg overflow-hidden bg-gray-200 dark:bg-gray-800 cursor-pointer">
                                <AuthenticatedImage :src="imgSrc" class="w-full h-auto max-h-80 object-contain transition-all duration-300" :class="{'grayscale': !isImageActive(index)}" />
                                <div class="absolute top-1 right-1 flex items-center gap-1 opacity-0 group-hover/image:opacity-100 transition-opacity duration-200">
                                    <button v-if="currentModelVisionSupport" @click.stop="toggleImage(index)" class="p-1.5 bg-black/60 text-white rounded-full hover:bg-black/80" :title="isImageActive(index) ? 'Deactivate Image' : 'Activate Image'">
                                        <IconEye v-if="isImageActive(index)" class="w-4 h-4" />
                                        <IconEyeOff v-else class="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                        </div>
                        <MessageContentRenderer
                            :content="message.content"
                            :is-streaming="message.isStreaming"
                            :is-user="isCurrentUser"
                            :has-images="imagesToRender.length > 0"
                        />
                        <div v-if="message.isStreaming && !message.content && (!imagesToRender || imagesToRender.length === 0)" class="typing-indicator">
                            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
                        </div>
                    </div>
                    <div v-else class="w-full">
                        <input type="file" ref="editImageInput" @change="handleEditImageSelected" multiple accept="image/*" class="hidden">
                        <div v-if="editedImages.length > 0" class="mb-2 p-2 border-dashed border-gray-300 dark:border-gray-600 rounded-md">
                            <div class="flex flex-wrap gap-2">
                                <div v-for="(image, index) in editedImages" :key="image.url" class="relative w-16 h-16">
                                    <img :src="image.url" class="w-full h-full object-cover rounded-md" alt="Image preview" />
                                    <button @click="removeEditedImage(index)" class="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold leading-none">×</button>
                                </div>
                            </div>
                        </div>
                        <CodeMirrorEditor
                            v-model="editedContent"
                            placeholder="Enter your message..."
                            :autofocus="true"
                            :extensions="editorExtensions"
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

                <!-- Sources -->
                <div v-if="hasSources" class="mt-2 border-t border-gray-200 dark:border-gray-700/50 pt-2">
                    <button @click="isSourcesVisible = !isSourcesVisible" class="flex items-center gap-2 text-xs font-semibold text-gray-500 dark:text-gray-400 cursor-pointer select-none w-full">
                        <IconChevronRight class="toggle-icon" :class="{'rotate-90': isSourcesVisible}" />
                        <span>Sources ({{sortedSources.length}})</span>
                    </button>
                    <div v-if="isSourcesVisible" class="mt-2 space-y-2 pl-4">
                        <div v-for="source in sortedSources" :key="source.document" @click="showSourceDetails(source)" class="source-item">
                            <div class="similarity-chip" :class="getSimilarityColor(source.similarity_percent)" :title="typeof source.similarity_percent === 'number' ? `Similarity: ${(source.similarity_percent).toFixed(1)}%` : 'Similarity: N/A'"></div>
                            <div class="truncate flex-grow" :title="source.document">{{ source.document }}</div>
                            <div v-if="typeof source.similarity_percent === 'number'" class="font-mono text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">{{ (source.similarity_percent).toFixed(1) }}%</div>
                        </div>
                    </div>
                </div>
                
                <!-- Events -->
                <details v-if="hasEvents" class="events-container" :open="!isEventsCollapsed" @toggle="event => isEventsCollapsed = !event.target.open">
                    <summary class="events-summary"><IconChevronRight class="toggle-icon" /><span>{{ isEventsCollapsed ? 'Show Events' : 'Hide Events' }}</span><span v-if="isEventsCollapsed" class="last-event-snippet">{{ lastEventSummary }}</span></summary>
                    <div class="events-content">
                        <div v-for="(event, index) in message.events" :key="index" class="event-item">
                            <div class="event-icon-container" :title="event.type"><component :is="getEventIcon(event.type)" /></div>
                            <div class="event-details"><div class="event-title">{{ event.type }}</div><div class="event-body"><div v-if="typeof event.content === 'string'" class="message-prose" v-html="parsedMarkdown(event.content)"></div><StepDetail v-else :data="event.content" /></div></div>
                        </div>
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
                            <DropdownMenu v-if="exportFormats.length > 0" title="Export" icon="ticket" button-class="action-btn">
                                <button v-for="format in exportFormats" :key="format.value" @click="handleExport(format.value)" class="w-full text-left p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 text-sm">
                                    {{ format.label }}
                                </button>
                            </DropdownMenu>
                            <button v-if="containsCode" :disabled="areActionsDisabled" @click="handleExportCode" title="Export Code" class="action-btn"><IconCode class="w-4 h-4" /></button>
                            <button :disabled="areActionsDisabled" @click="copyContent" title="Copy" class="action-btn"><IconCopy /></button>
                            <button :disabled="areActionsDisabled" @click="toggleEdit" title="Edit" class="action-btn"><IconPencil /></button>
                            <button :disabled="areActionsDisabled" @click="handleBranchOrRegenerate" :title="isCurrentUser ? 'Resend / Branch' : 'Regenerate'" class="action-btn"><IconRefresh /></button>
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