<script setup>
import { ref, computed, nextTick, onUpdated, onMounted, watch } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';

const props = defineProps({
    conversation: Object,
    compact: Boolean
});
const emit = defineEmits(['back']);

const socialStore = useSocialStore();
const authStore = useAuthStore();
const uiStore = useUiStore();
const content = ref('');
const messageContainer = ref(null);
const fileInput = ref(null);
const importInput = ref(null);
const files = ref([]);
const isUploading = ref(false);

const messages = computed(() => props.conversation.messages);
const title = computed(() => {
    if (props.conversation.isGroup) return props.conversation.name;
    return props.conversation.partner?.username;
});

const currentUser = computed(() => authStore.user);

function triggerFile() { fileInput.value.click(); }
function handleFiles(e) { files.value = Array.from(e.target.files); }

async function send() {
    if (!content.value.trim() && files.value.length === 0) return;
    isUploading.value = true;
    try {
        await socialStore.sendDirectMessage({
            targetId: props.conversation.id,
            isGroup: props.conversation.isGroup,
            content: content.value,
            files: files.value
        });
        content.value = '';
        files.value = [];
    } finally {
        isUploading.value = false;
    }
}

function scrollToBottom() {
  nextTick(() => {
      if (messageContainer.value) {
        messageContainer.value.scrollTop = messageContainer.value.scrollHeight;
      }
  });
}

watch(() => props.conversation.messages.length, scrollToBottom);
onMounted(scrollToBottom);

function openImageViewer(src) {
    uiStore.openImageViewer({ imageList: [{ src, prompt: 'DM Image' }], startIndex: 0 });
}

function formatTimestamp(dateString) {
  const date = new Date(dateString);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function removeFile(index) {
    files.value.splice(index, 1);
}

async function handleDeleteMessage(msgId) {
    if (confirm("Delete this message?")) {
        await socialStore.deleteMessage(msgId);
    }
}

async function handleDeleteConversation() {
    const msg = props.conversation.isGroup ? "Leave this group?" : "Clear conversation history?";
    if (confirm(msg)) {
        await socialStore.deleteConversation(props.conversation.id, props.conversation.isGroup);
        if (props.compact) emit('back');
        else socialStore.activeConversationId = null;
    }
}

async function handleExport() {
    await socialStore.exportConversation(props.conversation.id, props.conversation.isGroup, title.value);
}

function triggerImport() {
    importInput.value.click();
}

async function handleImport(e) {
    const file = e.target.files[0];
    if (!file) return;
    await socialStore.importConversation(props.conversation.id, props.conversation.isGroup, file);
    e.target.value = '';
}

</script>

<template>
    <div class="flex flex-col h-full bg-white dark:bg-gray-900">
        <div class="flex items-center p-3 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800 justify-between">
            <div class="flex items-center gap-2 overflow-hidden">
                <button v-if="compact" @click="$emit('back')" class="p-1 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700"><IconArrowLeft class="w-5 h-5"/></button>
                <UserAvatar v-if="!conversation.isGroup" :icon="conversation.partner?.icon" :username="title" size-class="w-8 h-8" />
                <div v-else class="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center font-bold text-gray-700">{{ title[0] }}</div>
                <span class="font-bold truncate">{{ title }}</span>
            </div>
            <div class="flex items-center gap-1">
                <DropdownMenu icon="ellipsis-vertical" buttonClass="btn-icon p-1">
                    <button @click="handleExport" class="menu-item"><IconArrowDownTray class="w-4 h-4 mr-2"/>Export JSON</button>
                    <button @click="triggerImport" class="menu-item"><IconArrowUpTray class="w-4 h-4 mr-2"/>Import JSON</button>
                    <div class="menu-divider"></div>
                    <button @click="handleDeleteConversation" class="menu-item text-red-500"><IconTrash class="w-4 h-4 mr-2"/>{{ conversation.isGroup ? 'Leave Group' : 'Clear History' }}</button>
                </DropdownMenu>
                <input type="file" ref="importInput" class="hidden" accept=".json" @change="handleImport">
                <button @click="uiStore.isChatSidebarOpen = false" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700"><IconXMark class="w-5 h-5" /></button>
            </div>
        </div>
        
        <div ref="messageContainer" class="flex-1 overflow-y-auto p-4 space-y-3">
            <div v-for="msg in messages" :key="msg.id" class="flex flex-col group" :class="msg.sender_id === authStore.user.id ? 'items-end' : 'items-start'">
                 <div class="relative max-w-[85%] p-2 rounded-lg text-sm shadow-sm border dark:border-gray-700" 
                      :class="msg.sender_id === authStore.user.id ? 'bg-blue-100 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800' : 'bg-white dark:bg-gray-800'">
                    
                    <div v-if="props.conversation.isGroup && msg.sender_id !== authStore.user.id" class="text-xs opacity-75 mb-1 font-bold text-blue-600 dark:text-blue-400">{{ msg.sender_username }}</div>
                    
                    <MessageContentRenderer :content="msg.content" />
                    
                    <div v-if="msg.image_references && msg.image_references.length > 0" class="mt-2 grid gap-2" :class="msg.image_references.length > 1 ? 'grid-cols-2' : 'grid-cols-1'">
                        <div v-for="img in msg.image_references" :key="img" class="relative group/img cursor-pointer">
                            <AuthenticatedImage :src="img" class="rounded-md max-h-48 object-cover w-full border dark:border-gray-600" @click.stop="openImageViewer(img)" />
                        </div>
                    </div>

                    <button 
                        v-if="msg.sender_id === authStore.user.id || authStore.user.is_admin" 
                        @click="handleDeleteMessage(msg.id)" 
                        class="absolute top-0 p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                        :class="msg.sender_id === authStore.user.id ? '-left-8' : '-right-8'"
                        title="Delete"
                    >
                        <IconTrash class="w-4 h-4" />
                    </button>
                 </div>
                 <span class="text-[10px] text-gray-400 mt-1 px-1">{{ formatTimestamp(msg.sent_at) }}</span>
            </div>
        </div>

        <div class="p-3 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
            <div v-if="files.length > 0" class="flex gap-2 mb-2 overflow-x-auto pb-1">
                <div v-for="(file, index) in files" :key="index" class="relative bg-white dark:bg-gray-700 rounded border dark:border-gray-600 p-1 text-xs flex items-center shadow-sm">
                    <span class="truncate max-w-[100px]">{{ file.name }}</span>
                    <button @click="removeFile(index)" class="ml-2 text-red-500 hover:text-red-700"><IconXMark class="w-3 h-3"/></button>
                </div>
            </div>
            <div class="flex gap-2">
                <button @click="triggerFile" class="btn-icon p-2"><IconPhoto class="w-5 h-5"/></button>
                <input type="file" ref="fileInput" class="hidden" multiple @change="handleFiles">
                <input v-model="content" @keyup.enter="send" class="input-field flex-1" placeholder="Type a message..." autocomplete="off" />
                <button @click="send" class="btn-primary p-2 rounded" :disabled="isUploading || (!content.trim() && files.length === 0)">
                    <IconSend class="w-4 h-4"/>
                </button>
            </div>
        </div>
    </div>
</template>
