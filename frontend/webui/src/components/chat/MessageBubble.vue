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

// Icon Imports
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconThumbUp from '../../assets/icons/IconThumbUp.vue';
import IconThumbDown from '../../assets/icons/IconThumbDown.vue';
import IconToken from '../../assets/icons/IconToken.vue';

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
    const dirty = marked.parse(content, { gfm: true, breaks: true });
    // In a real production app, you MUST sanitize this HTML before rendering to prevent XSS.
    // Libraries like DOMPurify are recommended for this purpose.
    return dirty;
}

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

const eventIconMap = {
  'thought': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-full h-full"><path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.311a14.994 14.994 0 01-3.75 0M9.75 10.5a3 3 0 116 0 3 3 0 01-6 0z" /></svg>`,
  'reasoning': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-full h-full"><path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" /></svg>`,
  'tool_call': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-full h-full"><path stroke-linecap="round" stroke-linejoin="round" d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.472-2.472a3.375 3.375 0 00-4.773-4.773L6.75 15.75l2.472 2.472a3.375 3.375 0 004.773-4.773z" /></svg>`,
  'observation': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-full h-full"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>`,
  'step_start': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-full h-full"><path stroke-linecap="round" stroke-linejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" /></svg>`,
  'step_end': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-full h-full"><path stroke-linecap="round" stroke-linejoin="round" d="M5.25 7.5A2.25 2.25 0 017.5 5.25h9a2.25 2.25 0 012.25 2.25v9a2.25 2.25 0 01-2.25 2.25h-9a2.25 2.25 0 01-2.25-2.25v-9z" /></svg>`,
  'info': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-full h-full"><path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>`,
  'exception': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-full h-full"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>`,
  'error': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-full h-full"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>`,
  'scratchpad': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-full h-full"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" /><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 7.125l-8.932 8.931m0 0L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" /></svg>`,
  'default': `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-full h-full"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z" /></svg>`
};

function getEventIcon(type) {
  const lowerType = type?.toLowerCase() || 'default';
  const key = Object.keys(eventIconMap).find(k => lowerType.includes(k));
  return eventIconMap[key || 'default'];
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
    if (isEditing.value) editedContent.value = props.message.content;
}

async function handleSaveEdit() {
    await discussionsStore.updateMessageContent({ messageId: props.message.id, newContent: editedContent.value });
    isEditing.value = false;
}

function handleCancelEdit() { isEditing.value = false; }
function handleEditorReady(payload) { codeMirrorView.value = payload.view; }

function copyContent() {
  navigator.clipboard.writeText(props.message.content);
  uiStore.addNotification('Content copied!', 'success');
}

async function handleDelete() {
  const confirmed = await uiStore.showConfirmation({ title: 'Delete Message', message: 'This will delete the message and its entire branch.', confirmText: 'Delete' });
  if (confirmed) discussionsStore.deleteMessage({ messageId: props.message.id});
}

function handleGrade(change) {
  discussionsStore.gradeMessage({ messageId: props.message.id, change });
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
    uiStore.openModal('sourceViewer', source);
}

function getSimilarityColor(score) {
  if (score === undefined || score === null) return 'bg-gray-400 dark:bg-gray-600';
  if (score >= 85) return 'bg-green-500';
  if (score >= 70) return 'bg-yellow-500';
  return 'bg-red-500';
}
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
                    <div v-if="message.content || (isUser && !imagesToRender.length)" class="message-prose" v-html="parsedStreamingContent"></div>
                </div>
                
                <div v-if="message.isStreaming && !message.content && (!imagesToRender || imagesToRender.length === 0)" class="typing-indicator">
                    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
                </div>
            </div>

            <div v-else class="w-full">
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
                    <div class="event-icon-container" :title="event.type" v-html="getEventIcon(event.type)"></div>
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

/* Events Section - NEW ORGANIC STYLES */
.events-container { @apply mt-2 border-t border-black/10 dark:border-white/10 pt-2; }
.user-bubble .events-container { @apply border-white/20; }
.events-summary { @apply flex items-center gap-2 text-xs font-semibold text-gray-500 dark:text-gray-400 cursor-pointer list-none select-none; }
.user-bubble .events-summary { @apply text-blue-200; }
.events-summary::-webkit-details-marker { display: none; }
.events-summary .toggle-icon { @apply transition-transform duration-200; }
details[open] > summary .toggle-icon { @apply rotate-90; }
.last-event-snippet { @apply ml-auto text-gray-400 dark:text-gray-500 font-normal italic truncate pl-4; }
.user-bubble .last-event-snippet { @apply text-blue-300; }

.events-content { @apply mt-2 space-y-3; }
.event-item { @apply flex items-start gap-3; }
.event-icon-container { @apply flex-shrink-0 w-5 h-5 mt-0.5 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 p-0.5; }
.user-bubble .event-icon-container { @apply bg-white/20 text-blue-200; }
.event-details { @apply flex-1 min-w-0; }
.event-title { @apply text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400; }
.event-body { @apply mt-1 text-sm; }

/* Prose inside event body should not have its own margins */
.event-body .message-prose :where(p, ul, ol, pre) {
    margin-top: 0.25em;
    margin-bottom: 0.25em;
}

.cm-editor-container { border: 1px solid theme('colors.gray.300'); border-radius: theme('borderRadius.lg'); }
.dark .cm-editor-container { border-color: theme('colors.gray.600'); }
.message-footer { @apply flex items-center justify-between mt-2 pt-2 border-t border-black/10 dark:border-white/10; min-height: 28px; }
.user-bubble .message-footer { @apply border-white/20; }
.detail-badge { @apply flex items-center gap-1.5 px-2 py-1 rounded-full bg-gray-200/50 dark:bg-gray-700/50 text-gray-600 dark:text-gray-300 font-mono; }
.user-bubble .detail-badge { @apply bg-white/20 text-blue-100; }
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