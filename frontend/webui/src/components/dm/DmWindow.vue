<!-- [UPDATE] frontend/webui/src/components/dm/DmWindow.vue -->
<script setup>
import { ref, computed, onMounted, onUpdated, nextTick, watch } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useSocialStore } from '../../stores/social';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import { useUiStore } from '../../stores/ui';

const props = defineProps({
  conversation: {
    type: Object,
    required: true,
  },
  compact: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['back']);

const authStore = useAuthStore();
const socialStore = useSocialStore();
const uiStore = useUiStore();
const currentUser = computed(() => authStore.user);

const messageContainer = ref(null);
const newMessageContent = ref('');
const dmInputRef = ref(null);
const fileInputRef = ref(null);

const scrollHeightBeforeLoad = ref(0);

const partner = computed(() => props.conversation.partner);
const messages = computed(() => props.conversation.messages || []);

// --- MENTION STATE ---
const mentionQuery = ref('');
const mentionSuggestions = ref([]);
const isMentioning = ref(false);
let mentionDebounceTimer = null;
const mentionStartIndex = ref(-1);

// --- FILE UPLOAD STATE ---
const uploadedFiles = ref([]);
const isUploading = ref(false);
const isDraggingOver = ref(false);

async function scrollToBottom() {
  await nextTick();
  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight;
  }
}

watch(() => messages.value.length, () => {
    scrollToBottom();
});

async function handleScroll(event) {
  const container = event.target;
  if (container.scrollTop === 0 && !props.conversation.isLoading && !props.conversation.fullyLoaded) {
    scrollHeightBeforeLoad.value = container.scrollHeight;
    await socialStore.fetchMoreMessages(partner.value.id);
  }
}

function triggerFileUpload() {
  fileInputRef.value.click();
}

function handleFileSelection(event) {
    const files = Array.from(event.target.files);
    addFiles(files);
    event.target.value = '';
}

function addFiles(files) {
    for (const file of files) {
        if (file.type.startsWith('image/')) {
             uploadedFiles.value.push({ file, preview: URL.createObjectURL(file) });
        } else {
            uiStore.addNotification(`File ${file.name} is not an image.`, 'warning');
        }
    }
}

function removeFile(index) {
    URL.revokeObjectURL(uploadedFiles.value[index].preview);
    uploadedFiles.value.splice(index, 1);
}

function sendMessage() {
  if (newMessageContent.value.trim() === '' && uploadedFiles.value.length === 0) return;
  
  isUploading.value = true;
  
  const filesToSend = uploadedFiles.value.map(f => f.file);
  
  socialStore.sendDirectMessage({
    receiverUserId: partner.value.id,
    content: newMessageContent.value,
    files: filesToSend
  }).finally(() => {
      isUploading.value = false;
  });

  newMessageContent.value = '';
  uploadedFiles.value.forEach(f => URL.revokeObjectURL(f.preview));
  uploadedFiles.value = [];
  isMentioning.value = false;
}

onMounted(() => {
  scrollToBottom();
  if (partner.value) {
      socialStore.markConversationAsRead(partner.value.id);
  }
});

watch(() => partner.value.id, (newId) => {
    if (newId) {
        socialStore.markConversationAsRead(newId);
        scrollToBottom();
        newMessageContent.value = '';
        uploadedFiles.value = [];
    }
});

onUpdated(() => {
  if (messageContainer.value) {
    if (scrollHeightBeforeLoad.value > 0) {
      const newScrollTop = messageContainer.value.scrollHeight - scrollHeightBeforeLoad.value;
      messageContainer.value.scrollTop = newScrollTop;
      scrollHeightBeforeLoad.value = 0;
    }
  }
});

function formatTimestamp(dateString) {
  const date = new Date(dateString);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// --- MENTION LOGIC ---
function handleInputForMentions(event) {
    const text = event.target.value;
    const cursorPosition = event.target.selectionStart;
    
    const textBeforeCursor = text.substring(0, cursorPosition);
    const atMatch = textBeforeCursor.match(/@(\w*)$/);

    if (atMatch) {
        mentionStartIndex.value = atMatch.index;
        const query = atMatch[1];
        mentionQuery.value = query;
        isMentioning.value = true;

        clearTimeout(mentionDebounceTimer);
        mentionDebounceTimer = setTimeout(async () => {
            if (mentionQuery.value === query) {
                mentionSuggestions.value = await socialStore.searchForMentions(query);
            }
        }, 200);
    } else {
        isMentioning.value = false;
        mentionSuggestions.value = [];
    }
}

function selectMention(user) {
    const beforeText = newMessageContent.value.substring(0, mentionStartIndex.value);
    const afterText = newMessageContent.value.substring(mentionStartIndex.value + mentionQuery.value.length + 1);
    
    const newText = `${beforeText}@${user.username} ${afterText}`;
    newMessageContent.value = newText;
    
    isMentioning.value = false;
    mentionSuggestions.value = [];
    
    nextTick(() => {
        const newCursorPos = beforeText.length + user.username.length + 2;
        dmInputRef.value.focus();
        dmInputRef.value.setSelectionRange(newCursorPos, newCursorPos);
    });
}

function closeMentionBox() {
    isMentioning.value = false;
}

function handleDragOver(event) {
    event.preventDefault();
    isDraggingOver.value = true;
}

function handleDragLeave(event) {
    if (!event.currentTarget.contains(event.relatedTarget)) {
        isDraggingOver.value = false;
    }
}

function handleDrop(event) {
    event.preventDefault();
    isDraggingOver.value = false;
    const files = Array.from(event.dataTransfer.files);
    addFiles(files);
}

function handlePaste(event) {
    const items = (event.clipboardData || window.clipboardData).items;
    for (const item of items) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
            const file = item.getAsFile();
            addFiles([file]);
        }
    }
}

function openImageViewer(src) {
    uiStore.openImageViewer({ imageList: [{ src, prompt: 'DM Image' }], startIndex: 0 });
}
</script>

<template>
  <div 
    v-if="conversation && conversation.partner" 
    class="flex flex-col h-full bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-lg"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
    @paste="handlePaste"
  >
    <div v-if="isDraggingOver" class="absolute inset-0 bg-blue-500/20 border-4 border-dashed border-blue-500 z-50 pointer-events-none flex items-center justify-center">
        <span class="text-blue-600 font-bold text-lg bg-white/80 px-4 py-2 rounded">Drop images here</span>
    </div>

    <header class="flex items-center p-3 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
      <button v-if="compact" @click="$emit('back')" class="mr-2 p-1 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300">
          <IconArrowLeft class="w-5 h-5" />
      </button>
      <UserAvatar :icon="partner.icon" :username="partner.username" size-class="h-9 w-9" />
      <div class="ml-3">
        <h3 class="font-semibold text-gray-900 dark:text-gray-100">{{ partner.username }}</h3>
      </div>
      <div class="flex-grow"></div>
      <button @click="socialStore.closeConversation(partner.id)" class="p-1 rounded-full text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600">
        <IconXMark class="w-5 h-5" />
      </button>
    </header>

    <div ref="messageContainer" @scroll="handleScroll" class="flex-grow p-4 overflow-y-auto">
      <div v-if="conversation.isLoading" class="text-center py-2 text-sm text-gray-500">Loading...</div>
      
      <div v-if="conversation.error" class="text-center py-2 text-red-500 text-sm">
        {{ conversation.error }}
      </div>

      <div v-if="conversation.fullyLoaded" class="text-center py-4">
        <p class="text-xs text-gray-400 dark:text-gray-500">This is the beginning of your conversation with {{ partner.username }}.</p>
      </div>

      <div v-for="message in conversation.messages" :key="message.id" class="flex my-2" :class="message.sender_id === currentUser.id ? 'justify-end' : 'justify-start'">
        <div class="max-w-[80%] px-3 py-2 rounded-lg" :class="{
            'bg-blue-500 text-white': message.sender_id === currentUser.id,
            'bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-200': message.sender_id !== currentUser.id,
            'opacity-60': message.isTemporary,
            'border border-red-500': message.error
        }">
            <div v-if="message.image_references && message.image_references.length > 0" class="mb-2 grid gap-1" :class="message.image_references.length > 1 ? 'grid-cols-2' : 'grid-cols-1'">
                 <div v-for="(imgRef, idx) in message.image_references" :key="idx" class="relative group cursor-pointer">
                    <AuthenticatedImage :src="imgRef" class="rounded-md max-h-48 object-cover w-full" @click.stop="openImageViewer(imgRef)" />
                </div>
            </div>
          <p class="text-sm break-words whitespace-pre-wrap">{{ message.content }}</p>
          <p class="text-xs mt-1 opacity-70" :class="message.sender_id === currentUser.id ? 'text-right' : 'text-left'">
            {{ formatTimestamp(message.sent_at) }}
          </p>
        </div>
      </div>
    </div>

    <footer class="p-3 border-t border-gray-200 dark:border-gray-700 flex-shrink-0 relative">
      <!-- MENTION POPUP -->
      <div v-if="isMentioning && mentionSuggestions.length > 0" v-on-click-outside="closeMentionBox" class="absolute bottom-full left-0 right-0 mb-2 p-2 bg-white dark:bg-gray-900 border dark:border-gray-700 rounded-lg shadow-lg max-h-48 overflow-y-auto z-10">
        <ul>
          <li v-for="user in mentionSuggestions" :key="user.id" @click="selectMention(user)" class="flex items-center p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer">
            <UserAvatar :icon="user.icon" :username="user.username" size-class="h-6 w-6" />
            <span class="ml-2 text-sm font-medium">{{ user.username }}</span>
          </li>
        </ul>
      </div>
      
      <!-- IMAGE PREVIEW -->
        <div v-if="uploadedFiles.length > 0" class="flex gap-2 p-2 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 overflow-x-auto mb-2 rounded-t-md">
            <div v-for="(file, index) in uploadedFiles" :key="index" class="relative w-16 h-16 flex-shrink-0 group">
                <img :src="file.preview" class="w-full h-full object-cover rounded-md border dark:border-gray-600" />
                <button @click="removeFile(index)" class="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs opacity-0 group-hover:opacity-100 transition-opacity">&times;</button>
            </div>
        </div>

      <form @submit.prevent="sendMessage" class="flex items-center space-x-2">
         <input type="file" ref="fileInputRef" @change="handleFileSelection" multiple accept="image/*" class="hidden">
         <button type="button" @click="triggerFileUpload" class="p-2 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400">
             <IconPhoto class="w-5 h-5" />
         </button>
        <input ref="dmInputRef" type="text" v-model="newMessageContent" @input="handleInputForMentions" placeholder="Type a message..." class="input-field flex-grow !py-2" autocomplete="off" />
        <button type="submit" class="btn btn-primary p-2" :disabled="isUploading || (newMessageContent.trim() === '' && uploadedFiles.length === 0)">
             <IconAnimateSpin v-if="isUploading" class="w-5 h-5 animate-spin" />
             <span v-else class="text-sm font-semibold px-2">Send</span>
        </button>
      </form>
    </footer>
  </div>
</template>
