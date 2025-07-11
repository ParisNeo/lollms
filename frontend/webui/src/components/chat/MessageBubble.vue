<script setup>
import { computed, ref, onMounted, watch, nextTick } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import { marked } from 'marked';

// Component Imports
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import CodeBlock from './CodeBlock.vue';
import StepDetail from './StepDetail.vue';
import { Codemirror } from 'vue-codemirror';
import { markdown } from '@codemirror/lang-markdown';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView, keymap } from '@codemirror/view';
import UserAvatar from '../ui/UserAvatar.vue';

// Action & UI Icon Imports
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconThumbUp from '../../assets/icons/IconThumbUp.vue';
import IconThumbDown from '../../assets/icons/IconThumbDown.vue';
import IconToken from '../../assets/icons/IconToken.vue';
import IconFormat from '../../assets/icons/IconFormat.vue';

// Event Icon Imports (NEW)
import IconThinking from '../../assets/icons/IconThinking.vue';
import IconTool from '../../assets/icons/IconTool.vue';
import IconObservation from '../../assets/icons/IconObservation.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconError from '../../assets/icons/IconError.vue';
import IconScratchpad from '../../assets/icons/IconScratchpad.vue';
import IconEventDefault from '../../assets/icons/IconEventDefault.vue';


const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
});

const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const isEventsCollapsed = ref(true);
const isEditing = ref(false);
const editedContent = ref('');
const codeMirrorView = ref(null);
const messageContentRef = ref(null);
const isFormattingMenuOpen = ref(false);

const areActionsDisabled = computed(() => discussionsStore.generationInProgress);
const user = computed(() => authStore.user);

const senderPersonality = computed(() => {
    if (isAi.value && user.value?.active_personality_id) {
        return dataStore.getPersonalityById(user.value.active_personality_id);
    }
    return null;
});

function renderMath() {
  if (messageContentRef.value && window.renderMathInElement) {
    window.renderMathInElement(messageContentRef.value, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '\\[', right: '\\]', display: true },
        { left: '\\(', right: '\\)', display: false },
        { left: '$', right: '$', display: false }
      ],
      throwOnError: false
    });
  }
}

watch(() => props.message.content, async () => {
    if (isEditing.value) isEditing.value = false;
    await nextTick();
    renderMath();
}, { flush: 'post' });

onMounted(() => renderMath());

const imagesToRender = computed(() => {
    if (props.message.localImageUrls?.length > 0) return props.message.localImageUrls;
    if (props.message.image_references?.length > 0) return props.message.image_references;
    return [];
});

const parsedMarkdown = (content) => {
    if (typeof content !== 'string') return '';
    return marked.parse(content, { gfm: true, breaks: true });
}

const messageParts = computed(() => {
    if (!props.message.content || props.message.isStreaming) return [];
    const parts = [];
    const content = props.message.content;
    const thinkRegex = /<think>([\s\S]*?)(?:<\/think>|$)/g;
    let lastIndex = 0, match;
    while ((match = thinkRegex.exec(content)) !== null) {
        if (match.index > lastIndex) parts.push({ type: 'content', content: content.substring(lastIndex, match.index) });
        if (match[1] && match[1].trim()) parts.push({ type: 'think', content: match[1].trim() });
        lastIndex = thinkRegex.lastIndex;
    }
    if (lastIndex < content.length) parts.push({ type: 'content', content: content.substring(lastIndex) });
    return parts.length > 0 ? parts : [{ type: 'content', content: '' }];
});

const getContentTokens = (text) => text ? Array.from(marked.lexer(text)) : [];
const parsedStreamingContent = computed(() => parsedMarkdown(props.message.content));

const isUser = computed(() => props.message.sender_type === 'user');
const isAi = computed(() => props.message.sender_type === 'assistant');
const isSystem = computed(() => props.message.sender_type === 'system');

const bubbleClass = computed(() => ({
  'user-bubble': isUser.value,
  'ai-bubble': isAi.value,
  'system-bubble': isSystem.value,
}));

const containerClass = computed(() => ({
    'justify-end': isUser.value,
    'justify-start': isAi.value,
    'justify-center': isSystem.value,
}));

const senderName = computed(() => {
    if (isUser.value) return authStore.user?.username || 'You';
    if (isAi.value) return senderPersonality.value?.name || props.message.sender || 'Assistant';
    return props.message.sender || 'System';
});

const hasEvents = computed(() => props.message.events && props.message.events.length > 0);

const lastEventSummary = computed(() => {
    if (!hasEvents.value) return '';
    const lastEvent = props.message.events[props.message.events.length - 1];
    let summary = `Event: ${lastEvent.type}`;
    if (typeof lastEvent.content === 'string' && lastEvent.content.length > 0) {
        summary += ` - ${lastEvent.content.substring(0, 50)}${lastEvent.content.length > 50 ? '...' : ''}`;
    }
    return summary;
});

// NEW: Map event types to imported components
const eventIconMap = {
  'thought': IconThinking,
  'tool_call': IconTool,
  'observation': IconObservation,
  'info': IconInfo,
  'exception': IconError,
  'error': IconError,
  'scratchpad': IconScratchpad,
  'default': IconEventDefault
  // Note: 'reasoning', 'step_start', 'step_end' will use the default icon.
  // You can create and map specific icons for them if needed.
};

function getEventIcon(type) {
  const lowerType = type?.toLowerCase() || 'default';
  const key = Object.keys(eventIconMap).find(k => lowerType.includes(k) && k !== 'default');
  return eventIconMap[key || 'default'];
}

const branchInfo = computed(() => {
    const hasMultipleBranches = props.message.branches && props.message.branches.length > 1;
    if (!hasMultipleBranches || props.message.sender_type !== 'user') return null;
    const currentMessages = discussionsStore.activeMessages;
    const currentMessageIndex = currentMessages.findIndex(m => m.id === props.message.id);
    const nextMessage = currentMessages[currentMessageIndex + 1];
    let activeBranchIndex = nextMessage ? props.message.branches.findIndex(id => id === nextMessage.id) : -1;
    if (activeBranchIndex === -1) activeBranchIndex = 0;
    return {
        isBranchPoint: true,
        current: activeBranchIndex + 1,
        total: props.message.branches.length,
        branchIds: props.message.branches,
        currentIndex: activeBranchIndex,
    };
});

function navigateBranch(direction) {
    if (!branchInfo.value) return;
    const { branchIds, currentIndex } = branchInfo.value;
    const newIndex = (currentIndex + direction + branchIds.length) % branchIds.length;
    discussionsStore.switchBranch(branchIds[newIndex]);
}

const editorExtensions = computed(() => [
    markdown(), EditorView.lineWrapping,
    keymap.of([
        { key: "Mod-Enter", run: () => { handleSaveEdit(); return true; }},
        { key: "Escape", run: () => { handleCancelEdit(); return true; }}
    ]),
    ...(uiStore.currentTheme === 'dark' ? [oneDark] : [])
]);

function toggleEdit() {
    isEditing.value = !isEditing.value;
    if (isEditing.value) {
        editedContent.value = props.message.content;
        isFormattingMenuOpen.value = false;
    }
}

async function handleSaveEdit() {
    await discussionsStore.updateMessageContent({ messageId: props.message.id, newContent: editedContent.value });
    isEditing.value = false;
}

function handleCancelEdit() { isEditing.value = false; }
function handleEditorReady(payload) { codeMirrorView.value = payload.view; }
function copyContent() { navigator.clipboard.writeText(props.message.content); uiStore.addNotification('Content copied!', 'success'); }
async function handleDelete() { const confirmed = await uiStore.showConfirmation({ title: 'Delete Message', message: 'This will delete the message and its entire branch.', confirmText: 'Delete' }); if (confirmed) discussionsStore.deleteMessage({ messageId: props.message.id}); }
function handleGrade(change) { discussionsStore.gradeMessage({ messageId: props.message.id, change }); }

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

function showSourceDetails(source) { uiStore.openModal('sourceViewer', source); }

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
    view.dispatch({ changes: { from, to, insert: textToInsert }, selection: { anchor: selStart, head: selEnd } });
    view.focus();
}

const formattingMenuItems = [
    { type: 'header', label: 'Basic' }, { label: 'Bold', action: () => insertTextAtCursor('**', '**', 'bold text') }, { label: 'Italic', action: () => insertTextAtCursor('*', '*', 'italic text') }, { label: 'Inline Code', action: () => insertTextAtCursor('`', '`', 'code') },
    { type: 'separator' }, { type: 'header', label: 'Math' }, { label: 'Inline Formula', action: () => insertTextAtCursor('$', '$', 'E=mc^2') }, { label: 'Display Formula', action: () => insertTextAtCursor('$$\n', '\n$$', 'x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}') },
    { type: 'separator' }, { type: 'header', label: 'Elements' }, { label: 'Link', action: () => insertTextAtCursor('[', '](https://)', 'link text') }, { label: 'Table', action: () => insertTextAtCursor('| Header 1 | Header 2 |\n|---|---|\n| Cell 1 | Cell 2 |\n| Cell 3 | Cell 4 |', '', '') },
    { type: 'separator' }, { type: 'header', label: 'Code Blocks' }, { label: 'Python', action: () => insertTextAtCursor('```python\n', '\n```', '# Your code here') }, { label: 'JavaScript', action: () => insertTextAtCursor('```javascript\n', '\n```', '// Your code here') },
];
</script>

<template>
  <div class="message-container group" :class="containerClass" :data-message-id="message.id">
    
    <div class="message-bubble" :class="bubbleClass">
        <!-- Message Header -->
        <div v-if="!isSystem" class="message-header">
            <UserAvatar v-if="isUser" :icon="user.icon" :username="user.username" size-class="h-8 w-8" />
            <UserAvatar v-else-if="isAi" :icon="senderPersonality?.icon_base64" :username="senderName" size-class="h-8 w-8" />
            
            <div class="sender-info">
                <span class="font-semibold">{{ senderName }}</span>
                <span v-if="isAi && (message.binding_name || message.model_name)" class="model-info">
                    {{ message.binding_name }}{{ message.binding_name && message.model_name ? '/' : '' }}{{ message.model_name }}
                </span>
            </div>
        </div>

        <!-- Main Content -->
        <div class="message-content-wrapper">
             <div v-if="!isEditing">
                <div v-if="imagesToRender.length > 0" 
                    class="my-2 grid gap-2"
                    :class="[imagesToRender.length > 1 ? 'grid-cols-2 md:grid-cols-3' : 'grid-cols-1']">
                    <div v-for="(imgSrc, index) in imagesToRender" :key="index" class="group/image relative rounded-lg overflow-hidden bg-gray-200 dark:bg-gray-800 cursor-pointer" @click="uiStore.openImageViewer(imgSrc)">
                        <AuthenticatedImage :src="imgSrc" class="w-full h-auto max-h-80 object-contain" />
                    </div>
                </div>
                
                <div :key="message.isStreaming ? 'streaming' : 'settled'" ref="messageContentRef">
                    <div v-if="message.content || (isUser && !imagesToRender.length)" class="message-prose">
                        <div v-if="message.isStreaming" v-html="parsedStreamingContent"></div>
                        <template v-else>
                            <template v-for="(part, index) in messageParts" :key="index">
                                <template v-if="part.type === 'content'">
                                    <template v-for="(token, tokenIndex) in getContentTokens(part.content)" :key="tokenIndex">
                                        <CodeBlock v-if="token.type === 'code'" :language="token.lang" :code="token.text" />
                                        <div v-else v-html="parsedMarkdown(token.raw)"></div>
                                    </template>
                                </template>
                                <details v-else-if="part.type === 'think'" class="think-block my-4" open>
                                    <summary class="think-summary">
                                        <IconThinking class="h-5 w-5 flex-shrink-0" />
                                        <span>Thinking...</span>
                                    </summary>
                                    <div class="think-content" v-html="parsedMarkdown(part.content)"></div>
                                </details>
                            </template>
                        </template>
                    </div>
                </div>
                
                <div v-if="message.isStreaming && !message.content && (!imagesToRender || imagesToRender.length === 0)" class="typing-indicator">
                    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
                </div>
            </div>

            <div v-else class="w-full">
                <div class="flex items-center space-x-1 border-b dark:border-gray-600 mb-2 pb-2">
                    <div class="relative">
                        <button @click="isFormattingMenuOpen = !isFormattingMenuOpen" class="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-600" title="Formatting Options">
                            <IconFormat class="w-5 h-5" />
                        </button>
                        <div v-if="isFormattingMenuOpen" v-on-click-outside="() => isFormattingMenuOpen = false"
                            class="absolute bottom-full left-0 mb-2 w-56 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow-xl z-20 py-1">
                            <template v-for="(item, index) in formattingMenuItems" :key="index">
                                <div v-if="item.type === 'separator'" class="my-1 h-px bg-gray-200 dark:bg-gray-600"></div>
                                <div v-else-if="item.type === 'header'" class="px-3 py-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">{{ item.label }}</div>
                                <button v-else @click="item.action(); isFormattingMenuOpen = false" class="w-full text-left flex items-center px-3 py-1.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-blue-500 hover:text-white">
                                    {{ item.label }}
                                </button>
                            </template>
                        </div>
                    </div>
                </div>
                <codemirror v-model="editedContent" placeholder="Enter your message..." :style="{ maxHeight: '500px' }" :autofocus="true" :indent-with-tab="true" :tab-size="2" :extensions="editorExtensions" @ready="handleEditorReady" class="cm-editor-container"/>
                <div class="flex justify-end space-x-2 mt-2">
                    <button @click="handleCancelEdit" class="btn btn-secondary !py-1 !px-3">Cancel</button>
                    <button @click="handleSaveEdit" class="btn btn-primary !py-1 !px-3">Save</button>
                </div>
            </div>
        </div>

        <!-- Collapsible Events Area -->
        <details v-if="hasEvents" class="events-container" :open="!isEventsCollapsed" @toggle="event => isEventsCollapsed = !event.target.open">
            <summary class="events-summary">
                <IconChevronRight class="toggle-icon" />
                <span>{{ isEventsCollapsed ? 'Show Events' : 'Hide Events' }}</span>
                <span v-if="isEventsCollapsed" class="last-event-snippet">{{ lastEventSummary }}</span>
            </summary>
            <div class="events-content">
                <div v-for="(event, index) in message.events" :key="index" class="event-item">
                    <!-- CHANGED: Using dynamic component instead of v-html -->
                    <div class="event-icon-container" :title="event.type">
                      <component :is="getEventIcon(event.type)" />
                    </div>
                    <div class="event-details">
                        <div class="event-title">{{ event.type }}</div>
                        <div class="event-body">
                           <div v-if="typeof event.content === 'string'" class="message-prose" v-html="parsedMarkdown(event.content)"></div>
                           <StepDetail v-else :data="event.content" />
                        </div>
                    </div>
                </div>
            </div>
        </details>

        <!-- Footer with Actions -->
        <div v-if="!isSystem" class="message-footer">
            <div class="flex-grow flex items-center flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
                <div v-if="branchInfo" class="detail-badge branch-badge-nav">
                    <button @click="navigateBranch(-1)" class="p-1 rounded-full hover:bg-black/10 dark:hover:bg-white/10" title="Previous Branch"><IconChevronRight class="w-3.5 h-3.5 rotate-180" /></button>
                    <span class="font-mono text-xs">{{ branchInfo.current }}/{{ branchInfo.total }}</span>
                    <button @click="navigateBranch(1)" class="p-1 rounded-full hover:bg-black/10 dark:hover:bg-white/10" title="Next Branch"><IconChevronRight class="w-3.5 h-3.5" /></button>
                </div>
                <div v-if="isAi && message.token_count" class="detail-badge">
                    <IconToken class="w-3.5 h-3.5" />
                    <span>{{ message.token_count }}</span>
                </div>
                <button v-if="isAi && message.sources && message.sources.length" v-for="source in message.sources" :key="source.document" @click="showSourceDetails(source)" class="detail-badge source-badge" :title="`View source: ${source.document}`">
                    <span class="similarity-chip" :class="getSimilarityColor(source.similarity_percent)"></span>
                    <span class="truncate max-w-[150px]">{{ source.document }}</span>
                </button>
            </div>
            <div v-if="!isEditing" class="flex-shrink-0 flex items-center gap-1">
                <div class="actions flex items-center space-x-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button :disabled="areActionsDisabled" @click="copyContent" title="Copy" class="action-btn"><IconCopy /></button>
                    <button :disabled="areActionsDisabled" @click="toggleEdit" title="Edit" class="action-btn"><IconPencil /></button>
                    <button :disabled="areActionsDisabled" @click="handleBranchOrRegenerate" :title="isUser ? 'Resend / Branch' : 'Regenerate'" class="action-btn"><IconRefresh /></button>
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
</template>

<style scoped>
.message-container { @apply w-full flex; }
.message-bubble { @apply flex flex-col p-3 rounded-2xl max-w-[85%] md:max-w-[75%] shadow; }
.ai-bubble { @apply bg-gray-100 dark:bg-gray-800 rounded-bl-none; }
.user-bubble { @apply bg-blue-500 text-white rounded-br-none dark:bg-blue-600; }
.system-bubble { @apply text-center bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs italic p-2 rounded-lg max-w-md mx-auto shadow-none; }
.message-header { @apply flex items-center gap-3 mb-2; }
.sender-info { @apply flex flex-col items-start; }
.sender-info .font-semibold { @apply text-sm leading-tight text-gray-800 dark:text-gray-100; }
.user-bubble .sender-info .font-semibold { @apply text-blue-100; }
.model-info { @apply text-xs leading-tight text-gray-400 dark:text-gray-500 font-mono; }
.user-bubble .model-info { @apply text-blue-200; }
.message-content-wrapper { @apply min-w-0; }
.message-prose { @apply text-sm prose prose-sm dark:prose-invert max-w-none break-words; }
.user-bubble .message-prose { @apply text-white prose-headings:text-white prose-a:text-blue-200 prose-code:text-blue-100 prose-strong:text-white; }
.typing-indicator .dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background-color: currentColor; margin: 0 1px; animation: bounce 1.4s infinite ease-in-out both; }
.typing-indicator .dot:nth-of-type(1) { animation-delay: -0.32s; }
.typing-indicator .dot:nth-of-type(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1.0); } }

.think-block { @apply bg-blue-50 dark:bg-gray-900/40 border border-blue-200 dark:border-blue-800/30 rounded-lg; }
.user-bubble .think-block { @apply bg-blue-400/50 border-blue-300/50; }
details[open] > .think-summary { @apply border-b border-blue-200 dark:border-blue-800/30; }
.user-bubble details[open] > .think-summary { @apply border-b-blue-300/50; }
.think-summary { @apply flex items-center gap-2 p-2 text-sm font-semibold text-blue-800 dark:text-blue-200 cursor-pointer list-none select-none; -webkit-tap-highlight-color: transparent; }
.user-bubble .think-summary { @apply text-blue-100; }
.think-summary:focus-visible { @apply ring-2 ring-blue-400 outline-none; }
.think-summary::-webkit-details-marker { display: none; }
.think-content { @apply p-3; }

.events-container { @apply mt-2 border-t border-black/10 dark:border-white/10 pt-2; }
.user-bubble .events-container { @apply border-white/20; }
.events-summary { @apply flex items-center gap-2 text-xs font-semibold text-gray-500 dark:text-gray-400 cursor-pointer list-none select-none; }
.user-bubble .events-summary { @apply text-blue-200; }
.events-summary::-webkit-details-marker { display: none; }
.events-summary .toggle-icon { @apply transition-transform duration-200 w-4 h-4; }
details[open] > summary .toggle-icon { @apply rotate-90; }
.last-event-snippet { @apply ml-auto text-gray-400 dark:text-gray-500 font-normal italic truncate pl-4; }
.user-bubble .last-event-snippet { @apply text-blue-300; }

.events-content { @apply mt-2 space-y-3; }
.event-item { @apply flex items-start gap-3; }
.event-icon-container { @apply flex-shrink-0 w-5 h-5 mt-0.5 text-gray-600 dark:text-gray-300; }
.user-bubble .event-icon-container { @apply text-blue-200; }
.event-details { @apply flex-1 min-w-0; }
.event-title { @apply text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400; }
.event-body { @apply mt-1 text-sm; }
.event-body .message-prose :where(p, ul, ol, pre) { margin-top: 0.25em; margin-bottom: 0.25em; }

.cm-editor-container { border: 1px solid theme('colors.gray.300'); border-radius: theme('borderRadius.lg'); }
.dark .cm-editor-container { border-color: theme('colors.gray.600'); }
.message-footer { @apply flex items-center justify-between mt-2 pt-2 border-t border-black/10 dark:border-white/10; min-height: 28px; }
.user-bubble .message-footer { @apply border-white/20; }
.detail-badge { @apply flex items-center gap-1.5 px-2 py-1 rounded-full bg-gray-200/50 dark:bg-gray-700/50 text-gray-600 dark:text-gray-300 font-mono; }
.user-bubble .detail-badge { @apply bg-white/20 text-blue-100; }
.branch-badge-nav { @apply flex items-center gap-1 p-0; }
.user-bubble .branch-badge-nav { @apply bg-white/20 text-blue-100; }
.source-badge { @apply cursor-pointer hover:bg-gray-300/70 dark:hover:bg-gray-600/70 transition-colors; }
.source-badge .similarity-chip { @apply w-2 h-2 rounded-full flex-shrink-0; }
.action-btn { @apply p-1.5 rounded-full text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed; }
.user-bubble .action-btn { @apply text-blue-200 hover:bg-white/20; }
.message-rating { @apply flex items-center gap-1 bg-gray-200/50 dark:bg-gray-700/50 rounded-full; }
.user-bubble .message-rating { @apply bg-white/20; }
.rating-btn { @apply p-1.5 rounded-full text-gray-500 dark:text-gray-400 hover:bg-gray-300 dark:hover:bg-gray-600; }
.user-bubble .rating-btn { @apply text-blue-200 hover:bg-white/20; }
.rating-btn.upvote.active { @apply text-green-500; }
.rating-btn.downvote.active { @apply text-red-500; }
.rating-score { @apply px-1 text-xs font-bold w-6 text-center; }
</style>
