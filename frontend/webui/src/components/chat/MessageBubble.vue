<script setup>
import { computed, ref, onMounted, watch } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import { marked } from 'marked';

// Import the interactive CodeBlock component
import CodeBlock from './CodeBlock.vue';
// Import the new StepDetail component
import StepDetail from './StepDetail.vue';

// CodeMirror imports for the editor
import { Codemirror } from 'vue-codemirror';
import { markdown } from '@codemirror/lang-markdown';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView, lineNumbers } from '@codemirror/view';

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
});

const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

// --- Component State ---
const isStepsCollapsed = ref(!props.message.isStreaming);
const isEditing = ref(false);
const editedContent = ref('');
const codeMirrorView = ref(null);

// --- Lifecycle & Watchers ---
onMounted(() => {
    isStepsCollapsed.value = !props.message.isStreaming;
});

watch(() => props.message.content, () => {
    if (isEditing.value) {
        isEditing.value = false;
    }
});

// --- Computed Properties ---
const isUser = computed(() => props.message.sender_type === 'user');
const isAi = computed(() => props.message.sender_type === 'assistant');
const isSystem = computed(() => props.message.sender_type === 'system');

const bubbleClass = computed(() => ({
  'user-bubble': isUser.value,
  'ai-bubble': isAi.value,
  'system-bubble': isSystem.value,
  'is-streaming': props.message.isStreaming,
  'is-editing': isEditing.value,
}));

const containerClass = computed(() => ({
    'justify-center': isSystem.value,
    'items-end': isUser.value,
    'items-start': isAi.value
}));

const senderName = computed(() => {
    if (isUser.value) {
        return authStore.user?.username || 'You';
    }
    return props.message.sender || 'Unknown';
});

const messageParts = computed(() => {
    if (!props.message.content) return [{ type: 'content', content: '' }];
    
    const parts = [];
    const content = props.message.content;
    const thinkRegex = /<think>([\s\S]*?)(?:<\/think>|$)/g;
    let lastIndex = 0;
    let match;

    while ((match = thinkRegex.exec(content)) !== null) {
        if (match.index > lastIndex) {
            parts.push({
                type: 'content',
                content: content.substring(lastIndex, match.index)
            });
        }
        if (match[1] && match[1].trim()) {
            parts.push({
                type: 'think',
                content: match[1].trim()
            });
        }
        lastIndex = thinkRegex.lastIndex;
    }

    if (lastIndex < content.length) {
        parts.push({
            type: 'content',
            content: content.substring(lastIndex)
        });
    }

    return parts.length > 0 ? parts : [{ type: 'content', content }];
});

function getContentTokens(text) {
    if (!text) return [];
    const tokens = marked.lexer(text);
    return Array.from(tokens);
}

// Helper to parse step content for JSON rendering
function parseStepContent(content) {
    if (typeof content !== 'string' || !content.trim().startsWith('{') && !content.trim().startsWith('[')) {
        return { isJson: false, data: content };
    }
    try {
        const parsed = JSON.parse(content);
        return { isJson: true, data: parsed };
    } catch (e) {
        return { isJson: false, data: content };
    }
}

// Helper to render plain text/markdown content
const getStepContent = (content) => {
    if (!content) return '';
    return marked.parse(content, { gfm: true, breaks: true });
}

const latestStep = computed(() => {
    if (props.message.steps && props.message.steps.length > 0) {
        const reversedSteps = [...props.message.steps].reverse();
        return reversedSteps.find(s => s.content) || null;
    }
    return null;
});

const editorExtensions = computed(() => {
    const extensions = [markdown(), EditorView.lineWrapping, lineNumbers()];
    if (uiStore.currentTheme === 'dark') {
        extensions.push(oneDark);
    }
    return extensions;
});

// --- Branching Logic ---
const discussion = computed(() => discussionsStore.activeDiscussion);

const branchInfo = computed(() => {
    if (!discussion.value || !props.message.parent_message_id) {
        return null;
    }

    const parentMessage = discussionsStore.activeMessages.find(m => m.id === props.message.parent_message_id);
    if (!parentMessage || parentMessage.children_count <= 1) {
        return null;
    }
    
    // Find all branches that stem from this message's parent
    const siblingBranches = discussion.value.branches_info.filter(
        branch => branch.parent_message_id === props.message.parent_message_id
    );

    if (siblingBranches.length <= 1) return null;
    
    const currentIndex = siblingBranches.findIndex(branch => branch.id === props.message.branch_id);

    return {
        isBranch: true,
        current: currentIndex + 1,
        total: siblingBranches.length,
        branches: siblingBranches,
        currentIndex: currentIndex,
    };
});

function navigateBranch(direction) {
    if (!branchInfo.value) return;
    const { branches, currentIndex } = branchInfo.value;
    const newIndex = (currentIndex + direction + branches.length) % branches.length;
    const newBranchId = branches[newIndex].id;
    discussionsStore.switchBranch(newBranchId);
}

// --- Edit Mode Logic ---
function toggleEdit() {
    isEditing.value = !isEditing.value;
    if (isEditing.value) {
        editedContent.value = props.message.content;
    }
}

async function handleSaveEdit() {
    const branchId = props.message.branch_id || discussionsStore.activeDiscussion.activeBranchId;
    if (!branchId) {
        uiStore.addNotification('Could not save edit: branch not found.', 'error');
        return;
    }
    await discussionsStore.updateMessageContent({
        messageId: props.message.id,
        branchId,
        newContent: editedContent.value,
    });
    isEditing.value = false;
}

function handleCancelEdit() {
    isEditing.value = false;
}

function handleEditorReady(payload) {
    codeMirrorView.value = payload.view;
}

function insertTextAtCursor(before, after = '', placeholder = '') {
    const view = codeMirrorView.value;
    if (!view) return;

    const { from, to } = view.state.selection.main;
    const selectedText = view.state.doc.sliceString(from, to);

    let textToInsert;
    let selectionOffsetStart;
    let selectionOffsetEnd;

    if (selectedText) {
        textToInsert = `${before}${selectedText}${after}`;
        selectionOffsetStart = from + before.length;
        selectionOffsetEnd = selectionOffsetStart + selectedText.length;
    } else {
        textToInsert = `${before}${placeholder}${after}`;
        selectionOffsetStart = from + before.length;
        selectionOffsetEnd = selectionOffsetStart + placeholder.length;
    }
    
    view.dispatch({
        changes: { from, to, insert: textToInsert },
        selection: { anchor: selectionOffsetStart, head: selectionOffsetEnd }
    });
    view.focus();
}

// --- Action Handlers ---
function copyContent() {
  navigator.clipboard.writeText(props.message.content);
  uiStore.addNotification('Content copied!', 'success');
}

async function handleDelete() {
  const confirmed = await uiStore.showConfirmation({
      title: 'Delete Message',
      message: 'Are you sure you want to delete this message and all subsequent replies?',
      confirmText: 'Delete'
  });
  if (confirmed) {
    discussionsStore.deleteMessage({ messageId: props.message.id});
  }
}

function handleGrade(change) {
  const branchId = props.message.branch_id || discussionsStore.activeDiscussion?.activeBranchId;
  if (!branchId) return;
  discussionsStore.gradeMessage({ messageId: props.message.id, branchId: branchId, change });
}

function handleBranchOrRegenerate() {
  discussionsStore.initiateBranch(props.message);
}

function showSourceDetails(source) {
    uiStore.openModal('sourceViewer', source);
}

function getSimilarityColor(score) {
  if (score >= 85) return 'bg-green-500';
  if (score >= 70) return 'bg-yellow-500';
  return 'bg-red-500';
}
</script>

<template>
  <div class="message-container group flex flex-col w-full" :class="containerClass" :data-message-id="message.id">
    <div class="message-bubble" :class="bubbleClass">
        <!-- Default View -->
        <div v-if="!isEditing">
            <!-- Sender & Model Info -->
            <div v-if="!isUser && !isSystem" class="flex items-center text-xs mb-2 text-gray-500 dark:text-gray-400">
                <span class="font-semibold text-gray-700 dark:text-gray-300">{{ senderName }}</span>
                <span v-if="isAi && message.model_name" class="ml-2">· {{ message.model_name }}</span>
            </div>

            <!-- Image Display -->
            <div v-if="message.image_references && message.image_references.length > 0" 
                class="my-2 grid gap-2"
                :class="[message.image_references.length > 1 ? 'grid-cols-2 md:grid-cols-3' : 'grid-cols-1']">
                <div 
                    v-for="(imgSrc, index) in message.image_references" 
                    :key="index" 
                    class="group/image relative rounded-lg overflow-hidden bg-gray-200 dark:bg-gray-800 cursor-pointer"
                    @click="uiStore.openImageViewer(imgSrc)"
                >
                <AuthenticatedImage :src="imgSrc" class="w-full h-auto max-h-80 object-contain" />
                </div>
            </div>

            <!-- Main Content - Part-based rendering -->
            <div class="message-content text-sm prose prose-sm dark:prose-invert max-w-none">
                <template v-for="(part, index) in messageParts" :key="index">
                    <!-- Render normal content -->
                    <template v-if="part.type === 'content'">
                        <template v-for="(token, tokenIndex) in getContentTokens(part.content)" :key="tokenIndex">
                            <CodeBlock v-if="token.type === 'code'" :language="token.lang" :code="token.text" />
                            <div v-else v-html="marked.parse(token.raw, { gfm: true, breaks: true })"></div>
                        </template>
                    </template>
                    <!-- Render <think> blocks -->
                    <details v-else-if="part.type === 'think'" class="think-block my-4">
                        <summary class="think-summary">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                            <span>Thinking...</span>
                        </summary>
                        <div class="think-content p-3" v-html="marked.parse(part.content, { gfm: true, breaks: true })"></div>
                    </details>
                </template>
            </div>
            
            <div v-if="message.isStreaming && !message.content && (!message.image_references || message.image_references.length === 0)" class="typing-indicator">
                    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>
        </div>

        <!-- Editing View -->
        <div v-else class="w-full">
            <!-- Toolbar -->
            <div class="flex items-center space-x-1 border-b dark:border-gray-600 mb-2 pb-2">
                <button @click="insertTextAtCursor('**', '**', 'bold text')" title="Bold" class="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-sm"><b>B</b></button>
                <button @click="insertTextAtCursor('*', '*', 'italic text')" title="Italic" class="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-sm"><i>I</i></button>
                <button @click="insertTextAtCursor('`', '`', 'code')" title="Inline Code" class="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-sm font-mono text-xs"></button>
                <button @click="insertTextAtCursor('$$', '$$', 'latex')" title="LaTeX" class="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-sm">Σ</button>
                <button @click="insertTextAtCursor('```python\n', '\n```')" title="Python Code Block" class="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-sm font-mono text-xs">Py</button>
                <button @click="insertTextAtCursor('```json\n', '\n```')" title="JSON Code Block" class="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-sm font-mono text-xs">Json</button>
                <button @click="insertTextAtCursor('```javascript\n', '\n```')" title="JavaScript Code Block" class="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-sm font-mono text-xs">JS</button>
            </div>
            <!-- CodeMirror Editor -->
            <codemirror
                v-model="editedContent"
                placeholder="Enter your message..."
                :style="{ maxHeight: '500px' }"
                :autofocus="true"
                :indent-with-tab="true"
                :tab-size="2"
                :extensions="editorExtensions"
                @ready="handleEditorReady"
            />
            <!-- Edit Actions -->
            <div class="flex justify-end space-x-2 mt-2">
                <button @click="handleCancelEdit" class="btn btn-secondary !py-1 !px-3">Cancel</button>
                <button @click="handleSaveEdit" class="btn btn-primary !py-1 !px-3">Save</button>
            </div>
        </div>

      <!-- Generation Steps (visible in both modes) -->
      <div v-if="message.steps && message.steps.length > 0 && !isEditing" class="steps-container">
        <button @click="isStepsCollapsed = !isStepsCollapsed" class="text-xs font-medium text-gray-500 hover:text-gray-800 dark:hover:text-gray-200 flex items-center w-full text-left mb-2 group/toggle">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2 transition-transform flex-shrink-0 group-hover/toggle:text-gray-900 dark:group-hover/toggle:text-white" :class="{'rotate-90': !isStepsCollapsed, 'rotate-0': isStepsCollapsed}" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
            <div class="flex items-center space-x-2 overflow-hidden flex-1 min-w-0">
                <div v-if="latestStep" class="step-icon flex-shrink-0">
                     <!-- This icon in the summary is always a process-type icon -->
                    <svg v-if="latestStep.status === 'done'" class="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>
                    <svg v-else class="w-4 h-4 animate-spin text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                </div>
                <span v-if="isStepsCollapsed && latestStep" class="truncate" v-text="latestStep.content"></span>
                <span v-else>Hide Steps</span>
            </div>
        </button>
        <div v-show="!isStepsCollapsed" class="space-y-2 pl-5 border-l-2 border-gray-200 dark:border-gray-700 ml-2">
            <!-- CORRECTED STEP RENDERING LOOP -->
            <template v-for="(step, index) in message.steps" :key="index">
                <div v-if="step.content" class="step-item">
                    <div class="step-icon">
                        <!-- Type-specific icon rendering -->
                        <template v-if="step.type === 'step'">
                            <!-- Static Info Icon for 'step' type -->
                            <svg class="text-blue-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>
                        </template>
                        <template v-else>
                            <!-- Spinner/Check for process steps (start_step, end_step, etc.) -->
                            <svg v-if="step.status === 'done'" class="text-green-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>
                            <svg v-else class="animate-spin text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        </template>
                    </div>
                    <div class="step-content-wrapper">
                        <!-- Universal content rendering (JSON or Markdown) -->
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
      
      <!-- Footer with Sources and Actions (visible in both modes) -->
      <div v-if="!isSystem" class="message-footer">
        <div class="flex justify-between items-center gap-2">
            <!-- Left Side: Details & Branching -->
            <div class="flex items-center flex-wrap gap-2">
                <!-- Branching UI -->
                <div v-if="isUser && message.children_count > 1" class="detail-badge branch-badge">
                    <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0l-1.5-1.5a2 2 0 112.828-2.828l1.5 1.5l3-3a2 2 0 010-2.828z" clip-rule="evenodd" /><path fill-rule="evenodd" d="M6.586 15.414a2 2 0 11-2.828-2.828l3-3a2 2 0 012.828 0l1.5 1.5a2 2 0 11-2.828 2.828l-1.5-1.5-3 3a2 2 0 010 2.828z" clip-rule="evenodd" /></svg>
                    <span>{{ message.children_count }} Branches</span>
                </div>
                <div v-if="isAi && branchInfo" class="detail-badge branch-badge-nav">
                    <button @click="navigateBranch(-1)" class="p-1 rounded-full hover:bg-black/10 dark:hover:bg-white/10" title="Previous Branch">
                        <svg class="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" /></svg>
                    </button>
                    <span class="font-mono text-xs">{{ branchInfo.current }}/{{ branchInfo.total }}</span>
                     <button @click="navigateBranch(1)" class="p-1 rounded-full hover:bg-black/10 dark:hover:bg-white/10" title="Next Branch">
                        <svg class="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4-4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
                    </button>
                </div>

                 <div v-if="message.token_count && !isEditing" class="detail-badge token-badge">
                    <svg class="w-3.5 h-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M15.988 3.012A2.25 2.25 0 0118 5.25v9.5A2.25 2.25 0 0115.75 17h-3.389a1.5 1.5 0 01-1.49-1.076L9.4 12.5H2.25a.75.75 0 010-1.5h7.15l1.45-3.868A1.5 1.5 0 0112.361 6h3.389A2.25 2.25 0 0115.988 3.012z" clip-rule="evenodd" /></svg>
                    <span>{{ message.token_count }}</span>
                </div>
                <button v-if="!isEditing" v-for="source in message.sources" :key="source.document" @click="showSourceDetails(source)" class="detail-badge source-badge" :title="`View source: ${source.document}`">
                    <span class="similarity-chip" :class="getSimilarityColor(source.similarity)"></span>
                    <span class="truncate max-w-xs">{{ source.document }}</span>
                </button>
            </div>

            <!-- Right Side: Actions (Copy, Rate, etc.) -->
            <div class="flex items-center gap-2 flex-shrink-0">
                <div v-if="!isEditing" class="actions flex items-center space-x-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button @click="copyContent" title="Copy" class="p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg></button>
                    <button @click="toggleEdit" title="Edit" class="p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" /><path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" /></svg></button>
                    <button @click="handleBranchOrRegenerate" :title="isUser ? 'Resend/Branch' : 'Regenerate'" class="p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg></button>
                    <button @click="handleDelete" title="Delete" class="p-1.5 rounded-full hover:bg-red-200 dark:hover:bg-red-700 text-red-500"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg></button>
                </div>
                <div v-if="isAi && !isEditing" class="message-rating">
                    <button @click="handleGrade(1)" title="Good response" class="rating-btn upvote" :class="{ 'active': message.user_grade > 0 }"><svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" /></svg></button>
                    <span class="rating-score">{{ message.user_grade || 0 }}</span>
                    <button @click="handleGrade(-1)" title="Bad response" class="rating-btn downvote" :class="{ 'active': message.user_grade < 0 }"><svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path d="M9.106 17.447a1 1 0 001.788 0l7-14a1 1 0 00-1.169-1.409l-5 1.429A1 1 0 0011 4.429V9a1 1 0 11-2 0V4.429a1 1 0 00-.725-.962l-5-1.428a1 1 0 00-1.17 1.408l7 14z" /></svg></button>
                </div>
            </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-container { animation: messageSlideIn 0.3s ease-out forwards; }
.typing-indicator .dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background-color: currentColor; margin: 0 1px; animation: bounce 1.4s infinite ease-in-out both; }
.typing-indicator .dot:nth-of-type(1) { animation-delay: -0.32s; }
.typing-indicator .dot:nth-of-type(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1.0); } }

.step-text > :first-child, .step-text > :last-child { margin-top: 0; margin-bottom: 0; }

.think-block {
    @apply bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/50 rounded-lg;
}
.think-block[open] .think-summary {
    @apply border-b border-blue-200 dark:border-blue-800/50;
}
.think-summary {
    @apply flex items-center p-2 text-sm font-semibold text-blue-800 dark:text-blue-200 cursor-pointer list-none;
    -webkit-tap-highlight-color: transparent;
}
.think-summary:focus-visible {
    @apply ring-2 ring-blue-400 outline-none;
}
.think-summary::-webkit-details-marker {
    display: none;
}
.think-content {
    @apply prose-sm max-w-none text-gray-700 dark:text-gray-300;
}

.branch-badge, .branch-badge-nav {
    @apply bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200;
}
.branch-badge-nav {
    @apply flex items-center gap-1;
}

/* Corrected Step Rendering Styles */
.step-item {
    display: flex;
    gap: 0.75rem; /* Increased gap for better alignment */
    align-items: flex-start;
}
.step-icon {
    flex-shrink: 0;
    width: 1rem;
    height: 1rem;
    margin-top: 0.25rem; /* Align with first line of text/JSON */
}
.step-content-wrapper {
    flex-grow: 1;
    min-width: 0; /* Important for flexbox to allow content to wrap */
    overflow: hidden;
}
</style>