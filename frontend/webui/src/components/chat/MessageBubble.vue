<script setup>
import { computed, ref, onMounted, watch, nextTick } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import { marked } from 'marked';
import CodeBlock from './CodeBlock.vue';
import StepDetail from './StepDetail.vue';
import { Codemirror } from 'vue-codemirror';
import { markdown } from '@codemirror/lang-markdown';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView, keymap } from '@codemirror/view';
import UserAvatar from '../ui/UserAvatar.vue';

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
});

const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const isStepsCollapsed = ref(!props.message.isStreaming);
const isEditing = ref(false);
const editedContent = ref('');
const codeMirrorView = ref(null);
const messageContentRef = ref(null);
const isFormattingMenuOpen = ref(false);

function renderMath() {
  if (messageContentRef.value && window.renderMathInElement) {
    window.renderMathInElement(messageContentRef.value, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false },
        { left: '\\(', right: '\\)', display: false },
        { left: '\\[', right: '\\]', display: true }
      ],
      throwOnError: false
    });
  }
}

watch(() => props.message.content, async () => {
    if (isEditing.value) {
        isEditing.value = false;
    }
    await nextTick();
    renderMath();
}, { flush: 'post' });

onMounted(() => {
    isStepsCollapsed.value = !props.message.isStreaming;
    renderMath();
});

const imagesToRender = computed(() => {
    if (props.message.localImageUrls && props.message.localImageUrls.length > 0) {
        return props.message.localImageUrls;
    }
    if (props.message.image_references && props.message.image_references.length > 0) {
        return props.message.image_references;
    }
    return [];
});

const parsedStreamingContent = computed(() => {
    if (!props.message.content) return '';
    return marked.parse(props.message.content, { gfm: true, breaks: true });
});

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
    return props.message.sender || 'Unknown';
});

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

function parseStepContent(content) {
    if (typeof content !== 'string') return { isJson: false, data: content };
    let processedContent = content.trim();
    if (!((processedContent.startsWith('{') && processedContent.endsWith('}')) || (processedContent.startsWith('[') && processedContent.endsWith(']')))) {
        return { isJson: false, data: content };
    }
    try { return { isJson: true, data: JSON.parse(processedContent) }; } catch (e) { }
    try {
        const repaired = processedContent.replace(/\bTrue\b/g, 'true').replace(/\bFalse\b/g, 'false').replace(/\bNone\b/g, 'null').replace(/'/g, '"');
        return { isJson: true, data: JSON.parse(repaired) };
    } catch (e) { return { isJson: false, data: content }; }
}

const getStepContent = (content) => content ? marked.parse(content, { gfm: true, breaks: true }) : '';

const latestStep = computed(() => {
    if (props.message.steps && props.message.steps.length > 0) {
        return [...props.message.steps].reverse().find(s => s && s.content) || null;
    }
    return null;
});

const editorExtensions = computed(() => {
    return [
        markdown(),
        EditorView.lineWrapping,
        keymap.of([{
            key: "Mod-Enter",
            run: () => { handleSaveEdit(); return true; },
        }, {
            key: "Escape",
            run: () => { handleCancelEdit(); return true; }
        }])
    ];
});

const branchInfo = computed(() => {
    const hasMultipleBranches = props.message.branches && props.message.branches.length > 0;
    if (!hasMultipleBranches) return null;
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

function toggleEdit() {
    isEditing.value = !isEditing.value;
    if (isEditing.value) {
        editedContent.value = props.message.content;
    }
}

async function handleSaveEdit() {
    await discussionsStore.updateMessageContent({ messageId: props.message.id, newContent: editedContent.value });
    isEditing.value = false;
}

function handleCancelEdit() { isEditing.value = false; }
function handleEditorReady(payload) { codeMirrorView.value = payload.view; }

function insertTextAtCursor(before, after = '', placeholder = '') {
    const view = codeMirrorView.value;
    if (!view) return;
    const { from, to } = view.state.selection.main;
    const selectedText = view.state.doc.sliceString(from, to);
    let textToInsert, selStart, selEnd;
    if (selectedText) {
        textToInsert = `${before}${selectedText}${after}`;
        selStart = from + before.length;
        selEnd = selStart + selectedText.length;
    } else {
        textToInsert = `${before}${placeholder}${after}`;
        selStart = from + before.length;
        selEnd = selStart + placeholder.length;
    }
    view.dispatch({
        changes: { from, to, insert: textToInsert },
        selection: { anchor: selStart, head: selEnd }
    });
    view.focus();
}

function copyContent() {
  navigator.clipboard.writeText(props.message.content);
  uiStore.addNotification('Content copied!', 'success');
}

async function handleDelete() {
  const confirmed = await uiStore.showConfirmation({
      title: 'Delete Message', message: 'This will delete the message and its entire branch.', confirmText: 'Delete'
  });
  if (confirmed) discussionsStore.deleteMessage({ messageId: props.message.id});
}

function handleGrade(change) {
  discussionsStore.gradeMessage({ messageId: props.message.id, change });
}

function handleBranchOrRegenerate() {
    let messageToBranchFrom = null;
    if (props.message.sender_type === 'user') {
        messageToBranchFrom = props.message;
    } else {
        const currentMessages = discussionsStore.activeMessages;
        const currentMessageIndex = currentMessages.findIndex(m => m.id === props.message.id);
        if (currentMessageIndex > -1) {
            for (let i = currentMessageIndex - 1; i >= 0; i--) {
                const prevMsg = currentMessages[i];
                if (prevMsg && prevMsg.sender_type === 'user') {
                    messageToBranchFrom = prevMsg;
                    break;
                }
            }
        }
    }
    if (messageToBranchFrom) {
        discussionsStore.initiateBranch(messageToBranchFrom);
    } else {
        uiStore.addNotification('Could not find a valid user prompt to regenerate from.', 'error');
    }
}

function showSourceDetails(source) { uiStore.openModal('sourceViewer', source); }

function getSimilarityColor(score) {
  if (score >= 85) return 'bg-green-500';
  if (score >= 70) return 'bg-yellow-500';
  return 'bg-red-500';
}
const user = computed(() => authStore.user);
const formattingMenuItems = [
    { type: 'header', label: 'Basic' },
    { label: 'Bold', action: () => insertTextAtCursor('**', '**', 'bold text') },
    { label: 'Italic', action: () => insertTextAtCursor('*', '*', 'italic text') },
    { label: 'Inline Code', action: () => insertTextAtCursor('`', '`', 'code') },
    { type: 'separator' },
    { type: 'header', label: 'Math' },
    { label: 'Inline Formula', action: () => insertTextAtCursor('$', '$', 'E=mc^2') },
    { label: 'Display Formula', action: () => insertTextAtCursor('$$\n', '\n$$', 'x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}') },
    { type: 'separator' },
    { type: 'header', label: 'Elements' },
    { label: 'Link', action: () => insertTextAtCursor('[', '](https://)', 'link text') },
    { label: 'Table', action: () => insertTextAtCursor('| Header 1 | Header 2 |\n|---|---|\n| Cell 1 | Cell 2 |\n| Cell 3 | Cell 4 |', '', '') },
    { type: 'separator' },
    { type: 'header', label: 'Code Blocks' },
    { label: 'Python', action: () => insertTextAtCursor('```python\n', '\n```', '# Your code here') },
    { label: 'JavaScript', action: () => insertTextAtCursor('```javascript\n', '\n```', '// Your code here') },
    { label: 'JSON', action: () => insertTextAtCursor('```json\n', '\n```', '{\n  "key": "value"\n}') },
    { label: 'Markdown', action: () => insertTextAtCursor('```markdown\n', '\n```', '## Example') },
];
</script>

<template>
  <div class="message-container group w-full flex" :class="containerClass" :data-message-id="message.id">
    <div class="message-bubble" :class="bubbleClass">
        <div v-if="!isEditing">
            <div v-if="!isUser && !isSystem" class="flex items-center text-xs mb-2 text-gray-500 dark:text-gray-400">
                <span class="font-semibold text-gray-700 dark:text-gray-300">{{ senderName }}</span>
                <span v-if="isAi && message.model_name" class="ml-2">· {{ message.model_name }}</span>
            </div>

            <div v-if="isUser" class="flex-shrink-0 flex items-center space-x-2">
                <UserAvatar v-if="user" :icon="user.icon" :username="user.username" size-class="h-10 w-10" /><span class="truncate max-w-[120px]">{{ user.username }}</span>
            </div>

            <div v-if="imagesToRender.length > 0" 
                class="my-2 grid gap-2"
                :class="[imagesToRender.length > 1 ? 'grid-cols-2 md:grid-cols-3' : 'grid-cols-1']">
                <div v-for="(imgSrc, index) in imagesToRender" :key="index" class="group/image relative rounded-lg overflow-hidden bg-gray-200 dark:bg-gray-800 cursor-pointer" @click="uiStore.openImageViewer(imgSrc)">
                    <AuthenticatedImage :src="imgSrc" class="w-full h-auto max-h-80 object-contain" />
                </div>
            </div>
            
            <div :key="message.isStreaming ? 'streaming' : 'settled'" ref="messageContentRef">
                <div v-if="message.content || (isUser && !imagesToRender.length)" class="message-content text-sm prose prose-sm dark:prose-invert max-w-none">
                    <div v-if="message.isStreaming" v-html="parsedStreamingContent"></div>
                    <template v-else>
                        <template v-for="(part, index) in messageParts" :key="index">
                            <template v-if="part.type === 'content'">
                                <template v-for="(token, tokenIndex) in getContentTokens(part.content)" :key="tokenIndex">
                                    <CodeBlock v-if="token.type === 'code'" :language="token.lang" :code="token.text" />
                                    <div v-else v-html="marked.parse(token.raw, { gfm: true, breaks: true })"></div>
                                </template>
                            </template>
                            <details v-else-if="part.type === 'think'" class="think-block my-4">
                                <summary class="think-summary">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                    <span>Thinking...</span>
                                </summary>
                                <div class="think-content p-3" v-html="marked.parse(part.content, { gfm: true, breaks: true })"></div>
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
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12" /></svg>
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

      <div v-if="!isEditing">
        <div v-if="message.steps && message.steps.length > 0" class="steps-container mt-4">
            
            <div v-if="isStepsCollapsed">
                <button @click="isStepsCollapsed = !isStepsCollapsed" class="collapsed-steps-summary group/summary">
                    <div class="step-icon flex-shrink-0">
                        <svg v-if="latestStep && latestStep.status !== 'done'" class="w-4 h-4 animate-spin text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        <svg v-else class="w-4 h-4 text-gray-500 dark:text-gray-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                            <path d="M10 2.5a7.5 7.5 0 00-7.5 7.5c0 2.08.843 3.96 2.21 5.344l-1.078 3.233a.75.75 0 00.945.945l3.233-1.078A7.5 7.5 0 1010 2.5z" />
                            <path d="M4.5 13.5a.5.5 0 01.5.5v.5a.5.5 0 01-1 0v-.5a.5.5 0 01.5-.5z" />
                            <path d="M3 10.5a.5.5 0 01.5.5v.5a.5.5 0 01-1 0v-.5a.5.5 0 01.5-.5z" />
                        </svg>
                    </div>
                    <span v-if="latestStep" class="truncate" v-text="latestStep.content"></span>
                    <span v-else>Show Steps</span>
                </button>
            </div>

            <div v-else>
                 <button @click="isStepsCollapsed = !isStepsCollapsed" class="text-xs font-medium text-gray-500 hover:text-gray-800 dark:hover:text-gray-200 flex items-center w-full text-left mb-2 group/toggle">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2 transition-transform rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
                    <span>Hide Steps</span>
                </button>
                <div class="space-y-2 pl-5 border-l-2 border-gray-200 dark:border-gray-700 ml-2">
                    <template v-for="(step, index) in message.steps" :key="index">
                        <div v-if="step && step.content" class="step-item">
                            <div class="step-icon">
                                <svg v-if="step.status === 'done'" class="text-green-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>
                                <svg v-else class="animate-spin text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                            </div>
                            <div class="step-content-wrapper">
                                <template v-if="parseStepContent(step.content).isJson">
                                    <StepDetail :data="parseStepContent(step.content).data" />
                                </template>
                                <template v-else>
                                    <div class="step-text prose prose-sm dark:prose-invert max-w-none" v-html="getStepContent(step.content)"></div>
                                </template>
                            </div>
                        </div>
                    </template>
                </div>
            </div>
        </div>
        
        <div v-if="!isSystem" class="message-footer mt-2">
            <div class="flex justify-between items-center gap-2">
                <div class="flex items-center flex-wrap gap-2">
                    <div v-if="branchInfo" class="detail-badge branch-badge-nav">
                        <button @click="navigateBranch(-1)" class="p-1 rounded-full hover:bg-black/10 dark:hover:bg-white/10" title="Previous Branch"><svg class="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" /></svg></button>
                        <span class="font-mono text-xs">{{ branchInfo.current }}/{{ branchInfo.total }}</span>
                        <button @click="navigateBranch(1)" class="p-1 rounded-full hover:bg-black/10 dark:hover:bg-white/10" title="Next Branch"><svg class="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4-4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg></button>
                    </div>
                    <div v-if="message.token_count && !isEditing" class="detail-badge token-badge">
                        <svg class="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M15.988 3.012A2.25 2.25 0 0118 5.25v9.5A2.25 2.25 0 0115.75 17h-3.389a1.5 1.5 0 01-1.49-1.076L9.4 12.5H2.25a.75.75 0 010-1.5h7.15l1.45-3.868A1.5 1.5 0 0112.361 6h3.389A2.25 2.25 0 0115.988 3.012z" clip-rule="evenodd" /></svg>
                        <span>{{ message.token_count }}</span>
                    </div>
                    <button v-if="!isEditing && message.sources" v-for="source in message.sources" :key="source.document" @click="showSourceDetails(source)" class="detail-badge source-badge" :title="`View source: ${source.document}`">
                        <span class="similarity-chip" :class="getSimilarityColor(source.similarity)"></span>
                        <span class="truncate max-w-xs">{{ source.document }}</span>
                    </button>
                </div>
                <div class="flex items-center gap-2 flex-shrink-0">
                    <div class="actions flex items-center space-x-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button @click="copyContent" title="Copy" class="p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg></button>
                        <button @click="toggleEdit" title="Edit" class="p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" /><path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" /></svg></button>
                        <button @click="handleBranchOrRegenerate" :title="isUser ? 'Resend / Branch' : 'Regenerate'" class="p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg></button>
                        <button @click="handleDelete" title="Delete" class="p-1.5 rounded-full hover:bg-red-200 dark:hover:bg-red-700 text-red-500"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg></button>
                    </div>
                    <div v-if="isAi" class="message-rating">
                        <button @click="handleGrade(1)" title="Good response" class="rating-btn upvote" :class="{ 'active': message.user_grade > 0 }"><svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" /></svg></button>
                        <span class="rating-score">{{ message.user_grade || 0 }}</span>
                        <button @click="handleGrade(-1)" title="Bad response" class="rating-btn downvote" :class="{ 'active': message.user_grade < 0 }"><svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M9.106 17.447a1 1 0 001.788 0l7-14a1 1 0 00-1.169-1.409l-5 1.429A1 1 0 0011 4.429V9a1 1 0 11-2 0V4.429a1 1 0 00-.725-.962l-5-1.428a1 1 0 00-1.17 1.408l7 14z" /></svg></button>
                    </div>
                </div>
            </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-container { animation: messageSlideIn 0.3s ease-out forwards; }
.message-bubble { max-width: 90%; word-break: break-word; min-width: 0; }
.typing-indicator .dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background-color: currentColor; margin: 0 1px; animation: bounce 1.4s infinite ease-in-out both; }
.typing-indicator .dot:nth-of-type(1) { animation-delay: -0.32s; }
.typing-indicator .dot:nth-of-type(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1.0); } }
.think-block { @apply bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/50 rounded-lg; }
.think-block[open] .think-summary { @apply border-b border-blue-200 dark:border-blue-800/50; }
.think-summary { @apply flex items-center p-2 text-sm font-semibold text-blue-800 dark:text-blue-200 cursor-pointer list-none; -webkit-tap-highlight-color: transparent; }
.think-summary:focus-visible { @apply ring-2 ring-blue-400 outline-none; }
.think-summary::-webkit-details-marker { display: none; }
.think-content { @apply prose-sm max-w-none text-gray-700 dark:text-gray-300; }
.branch-badge, .branch-badge-nav { @apply bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200; }
.branch-badge-nav { @apply flex items-center gap-1; }
.step-item { display: flex; gap: 0.75rem; align-items: flex-start; }
.step-icon { flex-shrink: 0; width: 1rem; height: 1rem; margin-top: 0.25rem; }
.step-content-wrapper { flex-grow: 1; min-width: 0; overflow: hidden; }
.cm-editor-container { border: 1px solid theme('colors.gray.300'); border-radius: theme('borderRadius.lg'); }
.dark .cm-editor-container { border-color: theme('colors.gray.600'); }
.collapsed-steps-summary {
    @apply flex items-center w-full text-left p-2 space-x-2 rounded-lg
           bg-gray-100 dark:bg-gray-700/50
           border border-gray-200 dark:border-gray-700
           text-xs text-gray-600 dark:text-gray-300
           transition-colors duration-200
           hover:bg-gray-200 dark:hover:bg-gray-700;
}
.collapsed-steps-summary .step-icon {
    @apply mt-0;
}
</style>