<script setup>
import { computed, ref, onMounted } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import CodeBlock from './CodeBlock.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import { marked } from 'marked';

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
});

const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

// --- FIX: The default state for steps should be collapsed IF the message is not currently streaming.
const isStepsCollapsed = ref(!props.message.isStreaming);

onMounted(() => {
    // This ensures that for messages loaded from history, the steps are initially collapsed.
    isStepsCollapsed.value = !props.message.isStreaming;
});

const isUser = computed(() => props.message.sender_type === 'user');
const isAi = computed(() => props.message.sender_type === 'assistant');
const isSystem = computed(() => props.message.sender_type === 'system');

const bubbleClass = computed(() => ({
  'user-bubble': isUser.value,
  'ai-bubble': isAi.value,
  'system-bubble': isSystem.value,
  'is-streaming': props.message.isStreaming,
}));

const senderName = computed(() => {
    if (isUser.value) {
        return authStore.user?.username || 'You';
    }
    return props.message.sender || 'Unknown';
});

const renderedContent = computed(() => {
  if (!props.message.content) return '';
  // Ensure 'think' blocks are parsed correctly and not escaped by marked
  let processedContent = props.message.content.replace(/<think>([\s\S]*?)<\/think>/gs, (match, thinkContent) => {
      // Temporarily encode to avoid markdown processing
      return `<details class="think-block my-2"><summary class="px-2 py-1 text-xs italic text-gray-500 dark:text-gray-400 cursor-pointer">Assistant's Thoughts</summary><div class="think-content p-2 border-t border-gray-200 dark:border-gray-700">${marked.parse(thinkContent.trim())}</div></details>`;
  });
  return marked.parse(processedContent, { breaks: true, gfm: true });
});


const getStepContent = (content) => {
    if (!content) return '';
    return marked.parse(content, { breaks: true });
}

const latestStep = computed(() => {
    if (props.message.steps && props.message.steps.length > 0) {
        return props.message.steps[props.message.steps.length - 1];
    }
    return null;
});

function formatTimestamp(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now - date;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return date.toLocaleDateString();
}

function getSimilarityColor(score) {
  if (score >= 85) return 'bg-green-500';
  if (score >= 70) return 'bg-yellow-500';
  return 'bg-red-500';
}

function showSourceDetails(source) {
    uiStore.openModal('sourceViewer', source);
}

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
    discussionsStore.deleteMessage({ messageId: props.message.id, branchId: props.message.branch_id });
  }
}

function handleGrade(change) {
  discussionsStore.gradeMessage({ messageId: props.message.id, branchId: props.message.branch_id, change });
}

function handleBranchOrRegenerate() {
  discussionsStore.initiateBranch(props.message);
}
</script>

<template>
  <div class="message-container group flex flex-col" :data-message-id="message.id">
    <div class="message-bubble" :class="bubbleClass">
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

      <!-- Main Content -->
      <div class="message-content text-sm prose prose-sm dark:prose-invert max-w-none" v-html="renderedContent"></div>
      <div v-if="message.isStreaming && !message.content && (!message.image_references || message.image_references.length === 0)" class="typing-indicator">
            <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      </div>

      <!-- Generation Steps -->
      <div v-if="message.steps && message.steps.length > 0" class="steps-container">
        <button @click="isStepsCollapsed = !isStepsCollapsed" class="text-xs font-medium text-gray-500 hover:text-gray-800 dark:hover:text-gray-200 flex items-center w-full text-left mb-2 group/toggle">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2 transition-transform flex-shrink-0 group-hover/toggle:text-gray-900 dark:group-hover/toggle:text-white" :class="{'rotate-90': !isStepsCollapsed, 'rotate-0': isStepsCollapsed}" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
            <div class="flex items-center space-x-2 overflow-hidden">
                <div v-if="latestStep" class="step-icon">
                    <svg v-if="latestStep.status === 'done'" class="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>
                    <svg v-else class="w-4 h-4 animate-spin text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                </div>
                <span v-if="isStepsCollapsed && latestStep" class="truncate">{{ latestStep.content }}</span>
                <span v-else>Hide Steps</span>
            </div>
        </button>
        <div v-show="!isStepsCollapsed" class="space-y-2 pl-5 border-l-2 border-gray-200 dark:border-gray-700 ml-2">
            <template v-for="step in message.steps" :key="step.id">
                <div v-if="step.type === 'step'" class="step-item step-item-info">
                    <div class="step-icon">
                        <svg class="text-blue-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>
                    </div>
                    <div class="step-text prose prose-sm dark:prose-invert max-w-none" v-html="getStepContent(step.content)"></div>
                </div>
                <div v-else class="step-item step-item-process" :class="{ 'status-pending': step.status !== 'done', 'status-done': step.status === 'done' }">
                    <div class="step-icon">
                        <svg v-if="step.status === 'done'" class="text-green-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>
                        <svg v-else class="animate-spin text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    </div>
                    <div class="step-text" v-html="getStepContent(step.content)"></div>
                </div>
            </template>
        </div>
      </div>
      
      <!-- Footer with Sources and Actions -->
      <div v-if="!isSystem" class="message-footer mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
        <div v-if="message.metadata?.sources?.length" class="flex flex-wrap gap-2 mb-2">
            <button v-for="source in message.metadata.sources" :key="source.document" @click="showSourceDetails(source)" class="source-badge" :title="`View source: ${source.document}`">
                <span class="similarity-chip w-3 h-3 rounded-full" :class="getSimilarityColor(source.similarity*100)"></span>
                <span class="truncate max-w-xs">{{ source.document }}</span>
            </button>
        </div>
        
        <div class="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400">
            <span>{{ formatTimestamp(message.created_at) }}</span>
            <div class="actions flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button @click="copyContent" title="Copy" class="p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg></button>
                <button @click="handleBranchOrRegenerate" :title="isUser ? 'Resend/Branch' : 'Regenerate'" class="p-1.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg></button>
                <button @click="handleDelete" title="Delete" class="p-1.5 rounded-full hover:bg-red-200 dark:hover:bg-red-700 text-red-500"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg></button>
                <div v-if="isAi" class="flex items-center space-x-1 ml-2 border-l border-gray-300 dark:border-gray-600 pl-2">
                    <button @click="handleGrade(1)" title="Good" class="p-1.5 rounded-full" :class="message.user_grade > 0 ? 'bg-green-100 text-green-700' : 'hover:bg-gray-200 dark:hover:bg-gray-600'"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333V17a1 1 0 001 1h6.758a1 1 0 00.97-1.22l-1.933-6.511A1 1 0 0012 9.5H7.083A1 1 0 006 10.333zM7 9a1 1 0 00-1 1v1a1 1 0 102 0v-1a1 1 0 00-1-1z" /></svg></button>
                    <button @click="handleGrade(-1)" title="Bad" class="p-1.5 rounded-full" :class="message.user_grade < 0 ? 'bg-red-100 text-red-700' : 'hover:bg-gray-200 dark:hover:bg-gray-600'"><svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667V3a1 1 0 00-1-1H6.242a1 1 0 00-.97 1.22l1.933 6.511A1 1 0 008 10.5h4.917a1 1 0 00.999-.667zM13 11a1 1 0 10-2 0v1a1 1 0 102 0v-1z" /></svg></button>
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

/* Ensure prose styles within steps are reset correctly */
.step-text > :first-child { margin-top: 0; }
.step-text > :last-child { margin-bottom: 0; }

.think-block summary {
    list-style: none; /* Hide default triangle */
}
.think-block summary::-webkit-details-marker {
    display: none;
}
.think-content {
    @apply prose-sm max-w-none text-gray-600 dark:text-gray-400;
}
</style>