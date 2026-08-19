<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';

// Icons
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconMicrophone from '../../assets/icons/IconMicrophone.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const props = defineProps({
    conversation: { type: Object, required: true },
    compact: { type: Boolean, default: false }
});
const emit = defineEmits(['back']);

const socialStore = useSocialStore();
const authStore = useAuthStore();
const uiStore = useUiStore();

const content = ref('');
const messageContainer = ref(null);
const fileInput = ref(null);
const importInput = ref(null);
const stagedFiles = ref([]);
const isUploading = ref(false);
const replyingTo = ref(null);
const inThreadSearch = ref('');
const isSearchOpen = ref(false);

// Clean-up & Selection Mode State
const isSelectionMode = ref(false);
const selectedMessageIds = ref(new Set());
const isCleanDrawerOpen = ref(false);

// Voice Recorder State
const isRecordingVoice = ref(false);
let mediaRecorder = null;
let recordedChunks = [];

const messages = computed(() => props.conversation.messages || []);
const activeTyping = computed(() => socialStore.typingUsers[props.conversation.id]);

const title = computed(() => {
    if (props.conversation.isGroup) return props.conversation.name || 'Group Chat';
    return props.conversation.partner?.username || 'Direct Message';
});

const isBotChat = computed(() => {
    return !props.conversation.isGroup && props.conversation.partner?.username?.toLowerCase() === 'lollms';
});

const currentUser = computed(() => authStore.user);

const quickEmojis = ['❤️', '👍', '😂', '😮', '🔥', '🚀'];

const filteredMessages = computed(() => {
    if (!inThreadSearch.value.trim()) return messages.value;
    const q = inThreadSearch.value.toLowerCase().trim();
    return messages.value.filter(m => (m.content || '').toLowerCase().includes(q) || (m.sender_username || '').toLowerCase().includes(q));
});

function scrollToBottom() {
    nextTick(() => {
        if (messageContainer.value) {
            messageContainer.value.scrollTop = messageContainer.value.scrollHeight;
        }
    });
}

watch(() => props.conversation.messages?.length, scrollToBottom);
onMounted(scrollToBottom);

// Typing signal debouncing
let typingSignalTimer = null;
function handleInputChange() {
    if (typingSignalTimer) return;
    typingSignalTimer = setTimeout(() => {
        socialStore.sendTypingSignal({
            targetId: props.conversation.id,
            isGroup: props.conversation.isGroup
        });
        typingSignalTimer = null;
    }, 1500);
}

// Media Selection
function triggerFilePicker() { fileInput.value?.click(); }
function handleFiles(e) {
    const chosen = Array.from(e.target.files || []);
    stagedFiles.value.push(...chosen);
    e.target.value = '';
}

function removeStagedFile(idx) {
    stagedFiles.value.splice(idx, 1);
}

// Voice Note Recording
async function toggleVoiceRecording() {
    if (isRecordingVoice.value) {
        mediaRecorder?.stop();
        isRecordingVoice.value = false;
    } else {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            recordedChunks = [];
            mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) recordedChunks.push(e.data); };
            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(recordedChunks, { type: 'audio/wav' });
                const voiceFile = new File([audioBlob], `voice_note_${Date.now()}.wav`, { type: 'audio/wav' });
                stagedFiles.value.push(voiceFile);
                stream.getTracks().forEach(t => t.stop());
            };
            mediaRecorder.start();
            isRecordingVoice.value = true;
        } catch (err) {
            uiStore.addNotification('Microphone access denied.', 'error');
        }
    }
}

// Sending
async function send() {
    const text = content.value.trim();
    if (!text && stagedFiles.value.length === 0) return;

    isUploading.value = true;
    try {
        await socialStore.sendDirectMessage({
            targetId: props.conversation.id,
            isGroup: props.conversation.isGroup,
            content: text || 'Attachment',
            files: stagedFiles.value,
            replyToId: replyingTo.value?.id || null
        });
        content.value = '';
        stagedFiles.value = [];
        replyingTo.value = null;
    } finally {
        isUploading.value = false;
    }
}

// Quoting / Replying
function startReply(msg) {
    replyingTo.value = msg;
}

// Reactions
async function react(msg, emoji) {
    await socialStore.toggleDmReaction({
        messageId: msg.id,
        emoji,
        targetId: props.conversation.id
    });
}

function openImageViewer(src) {
    uiStore.openImageViewer({ imageList: [{ src, prompt: 'Direct Message Image' }], startIndex: 0 });
}

function formatTimestamp(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Bulk Selection
function toggleMessageSelection(id) {
    if (selectedMessageIds.value.has(id)) {
        selectedMessageIds.value.delete(id);
    } else {
        selectedMessageIds.value.add(id);
    }
}

async function handleExecuteBulkDelete() {
    if (selectedMessageIds.value.size === 0) return;
    const confirmed = await uiStore.showConfirmation({
        title: 'Delete Selected Messages',
        message: `Delete ${selectedMessageIds.value.size} message(s) from this conversation?`,
        confirmText: 'Delete All',
        danger: true
    });
    if (confirmed.confirmed) {
        await socialStore.bulkDeleteDmMessages({
            messageIds: Array.from(selectedMessageIds.value),
            targetId: props.conversation.id
        });
        selectedMessageIds.value.clear();
        isSelectionMode.value = false;
    }
}

// History Pruning
async function handleCleanHistory(days = null, onlyMine = false) {
    const label = days ? `older than ${days} days` : 'all messages';
    const confirmed = await uiStore.showConfirmation({
        title: 'Clean Conversation History',
        message: `Are you sure you want to delete ${label}${onlyMine ? ' sent by you' : ''}?`,
        confirmText: 'Prune',
        danger: true
    });
    if (confirmed.confirmed) {
        await socialStore.cleanConversationHistory({
            targetId: props.conversation.id,
            isGroup: props.conversation.isGroup,
            days,
            onlyMyMessages: onlyMine
        });
        isCleanDrawerOpen.value = false;
    }
}

async function handleDeleteConversation() {
    const msg = props.conversation.isGroup ? "Leave this group?" : "Permanently clear conversation history?";
    const confirmed = await uiStore.showConfirmation({
        title: props.conversation.isGroup ? 'Leave Group' : 'Clear Chat',
        message: msg,
        confirmText: props.conversation.isGroup ? 'Leave' : 'Delete All',
        danger: true
    });
    if (confirmed.confirmed) {
        await socialStore.deleteConversation(props.conversation.id, props.conversation.isGroup);
        if (props.compact) emit('back');
        else socialStore.activeConversationId = null;
    }
}

async function handleExport() {
    await socialStore.exportConversation(props.conversation.id, props.conversation.isGroup, title.value);
}

function triggerImport() { importInput.value?.click(); }
async function handleImport(e) {
    const file = e.target.files[0];
    if (!file) return;
    await socialStore.importConversation(props.conversation.id, props.conversation.isGroup, file);
    e.target.value = '';
}
</script>

<template>
    <div class="flex flex-col h-full bg-white dark:bg-gray-950 overflow-hidden relative">
        <!-- ── HEADER ── -->
        <div class="flex items-center p-3 border-b dark:border-gray-800 bg-gray-50/80 dark:bg-gray-900/80 backdrop-blur-md justify-between shrink-0 z-10 shadow-xs">
            <div class="flex items-center gap-2.5 min-w-0">
                <button v-if="compact" @click="$emit('back')" class="p-1.5 rounded-xl hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500"><IconArrowLeft class="w-5 h-5"/></button>

                <UserAvatar v-if="!conversation.isGroup" :icon="conversation.partner?.icon" :username="title" size-class="w-9 h-9" />
                <div v-else class="w-9 h-9 bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 rounded-full flex items-center justify-center font-bold text-sm shrink-0 border dark:border-gray-700">
                    {{ title.charAt(0).toUpperCase() }}
                </div>

                <div class="flex flex-col min-w-0">
                    <div class="flex items-center gap-1.5">
                        <span class="font-bold text-sm text-gray-900 dark:text-gray-100 truncate">{{ title }}</span>
                        <span v-if="isBotChat" class="px-1.5 py-0.2 text-[9px] font-black uppercase tracking-wider bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 rounded-full border border-purple-200 dark:border-purple-800">
                            🤖 AI
                        </span>
                    </div>
                    <span v-if="activeTyping" class="text-[10px] text-blue-500 dark:text-blue-400 font-medium italic animate-pulse">
                        {{ activeTyping.username }} is typing...
                    </span>
                    <span v-else class="text-[10px] text-gray-400 font-mono">
                        {{ conversation.isGroup ? `${conversation.members?.length || 0} members` : 'Direct message' }}
                    </span>
                </div>
            </div>

            <!-- Header Quick Tools -->
            <div class="flex items-center gap-1 shrink-0">
                <button @click="isSearchOpen = !isSearchOpen" class="btn-icon p-1.5 text-gray-500 hover:text-blue-500" :class="{'text-blue-600 bg-blue-50 dark:bg-blue-900/30': isSearchOpen}" title="Search in Chat">
                    <IconMagnifyingGlass class="w-4 h-4" />
                </button>

                <button @click="isCleanDrawerOpen = !isCleanDrawerOpen" class="btn-icon p-1.5 text-gray-500 hover:text-amber-500" title="Clean Up Options">
                    <span class="text-sm">🧹</span>
                </button>

                <DropdownMenu title="Conversation Options" icon="ellipsis-vertical" buttonClass="btn-icon p-1.5 text-gray-500">
                    <button @click="isSelectionMode = !isSelectionMode" class="menu-item">
                        <IconCheckCircle class="w-4 h-4 mr-2 text-blue-500" />
                        <span>{{ isSelectionMode ? 'Exit Select Mode' : 'Select Messages' }}</span>
                    </button>
                    <button @click="handleExport" class="menu-item"><IconArrowDownTray class="w-4 h-4 mr-2"/>Export JSON</button>
                    <button @click="triggerImport" class="menu-item"><IconArrowUpTray class="w-4 h-4 mr-2"/>Import JSON</button>
                    <div class="menu-divider"></div>
                    <button @click="handleDeleteConversation" class="menu-item text-red-500 font-bold">
                        <IconTrash class="w-4 h-4 mr-2"/>
                        <span>{{ conversation.isGroup ? 'Leave Group' : 'Clear Chat History' }}</span>
                    </button>
                </DropdownMenu>

                <input type="file" ref="importInput" class="hidden" accept=".json" @change="handleImport">
                <button v-if="!compact" @click="uiStore.isChatSidebarOpen = false" class="btn-icon p-1.5 text-gray-400 hover:text-red-500"><IconXMark class="w-5 h-5" /></button>
            </div>
        </div>

        <!-- ── IN-THREAD SEARCH BAR ── -->
        <div v-if="isSearchOpen" class="p-2.5 bg-blue-50/60 dark:bg-blue-950/20 border-b dark:border-gray-800 flex items-center gap-2 animate-in fade-in">
            <IconMagnifyingGlass class="w-4 h-4 text-blue-500 shrink-0" />
            <input v-model="inThreadSearch" placeholder="Search message text or media..." class="input-field !py-1 !text-xs grow bg-white dark:bg-gray-900" autofocus />
            <span class="text-[10px] font-mono text-gray-400 shrink-0">{{ filteredMessages.length }} found</span>
            <button @click="isSearchOpen = false; inThreadSearch = ''" class="text-gray-400 hover:text-red-500 p-1"><IconXMark class="w-4 h-4"/></button>
        </div>

        <!-- ── CLEAN-UP POP-OVER DRAWER ── -->
        <div v-if="isCleanDrawerOpen" class="p-4 bg-amber-50/80 dark:bg-amber-950/30 border-b border-amber-200 dark:border-amber-900/50 space-y-3 animate-in fade-in">
            <div class="flex items-center justify-between">
                <span class="text-[10px] font-black uppercase tracking-widest text-amber-800 dark:text-amber-300">Conversation Clean Up</span>
                <button @click="isCleanDrawerOpen = false" class="text-gray-400 hover:text-red-500"><IconXMark class="w-4 h-4"/></button>
            </div>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <button @click="handleCleanHistory(7, false)" class="btn btn-secondary btn-xs py-2 text-[10px] font-bold">Purge > 7 Days</button>
                <button @click="handleCleanHistory(30, false)" class="btn btn-secondary btn-xs py-2 text-[10px] font-bold">Purge > 30 Days</button>
                <button @click="handleCleanHistory(null, true)" class="btn btn-secondary btn-xs py-2 text-[10px] font-bold">Wipe My Sent</button>
                <button @click="handleCleanHistory(null, false)" class="btn btn-danger-outline btn-xs py-2 text-[10px] font-bold">Wipe All</button>
            </div>
        </div>

        <!-- ── BULK SELECTION ACTION BAR ── -->
        <div v-if="isSelectionMode" class="p-2.5 bg-blue-600 text-white flex items-center justify-between shrink-0 shadow-md animate-in fade-in">
            <span class="text-xs font-bold">{{ selectedMessageIds.size }} message(s) selected</span>
            <div class="flex items-center gap-2">
                <button @click="handleExecuteBulkDelete" :disabled="selectedMessageIds.size === 0" class="px-3 py-1 bg-red-600 hover:bg-red-700 text-white text-xs font-bold rounded-lg shadow-sm disabled:opacity-50">
                    Delete Selected
                </button>
                <button @click="isSelectionMode = false; selectedMessageIds.clear()" class="px-3 py-1 bg-white/20 hover:bg-white/30 text-white text-xs font-bold rounded-lg">
                    Cancel
                </button>
            </div>
        </div>

        <!-- ── MESSAGES VIEWPORT ── -->
        <div ref="messageContainer" class="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
            <div v-if="filteredMessages.length === 0" class="h-full flex flex-col items-center justify-center text-gray-400 text-xs italic">
                {{ inThreadSearch ? 'No messages matching search query.' : 'No messages yet. Send a greeting!' }}
            </div>

            <div 
                v-for="msg in filteredMessages" 
                :key="msg.id" 
                class="flex flex-col group/dm relative" 
                :class="msg.sender_id === authStore.user?.id ? 'items-end' : 'items-start'"
            >
                <div class="flex items-end gap-2 max-w-[88%] sm:max-w-[78%]">
                    <!-- Bulk Checkbox -->
                    <input 
                        v-if="isSelectionMode" 
                        type="checkbox" 
                        :checked="selectedMessageIds.has(msg.id)"
                        @change="toggleMessageSelection(msg.id)"
                        class="rounded text-blue-600 focus:ring-blue-500 w-4 h-4 mb-2 cursor-pointer shrink-0"
                    />

                    <!-- Bubble Container -->
                    <div class="relative flex flex-col min-w-0">
                        <!-- Quoted Message Header -->
                        <div v-if="msg.reply_to_content" class="mb-1 text-[11px] px-3 py-1 bg-gray-100/80 dark:bg-gray-800/80 border-l-3 border-blue-500 rounded-r-xl text-gray-500 dark:text-gray-400 truncate max-w-full font-serif italic">
                            <span class="font-bold text-gray-700 dark:text-gray-300 not-italic mr-1">{{ msg.reply_to_sender }}:</span>
                            "{{ msg.reply_to_content }}"
                        </div>

                        <!-- Speech Bubble -->
                        <div 
                            class="relative p-3.5 rounded-2xl text-sm leading-relaxed shadow-sm border transition-all"
                            :class="msg.sender_id === authStore.user?.id 
                                ? 'bg-gradient-to-br from-blue-600 to-indigo-600 text-white border-transparent rounded-br-xs' 
                                : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-200/80 dark:border-gray-700/80 rounded-bl-xs'"
                        >
                            <!-- Sender Name for Group Chats or AI -->
                            <div v-if="props.conversation.isGroup || msg.is_ai_generated" class="text-xs mb-1 font-bold flex items-center gap-1.5" :class="msg.sender_id === authStore.user?.id ? 'text-blue-200' : 'text-blue-600 dark:text-blue-400'">
                                <span>{{ msg.sender_username }}</span>
                                <span v-if="msg.is_ai_generated" class="text-[8px] bg-purple-200 dark:bg-purple-900/60 text-purple-800 dark:text-purple-300 px-1 rounded uppercase font-black">AI</span>
                            </div>

                            <!-- Content -->
                            <MessageContentRenderer :content="msg.content" class="break-words font-sans" :class="{'text-white': msg.sender_id === authStore.user?.id}" />

                            <!-- Legacy Images / Media Attachments -->
                            <div v-if="msg.image_references && msg.image_references.length > 0" class="mt-2.5 grid gap-2" :class="msg.image_references.length > 1 ? 'grid-cols-2' : 'grid-cols-1'">
                                <div v-for="img in msg.image_references" :key="img" class="relative group/img cursor-pointer rounded-xl overflow-hidden shadow-sm">
                                    <AuthenticatedImage :src="img" class="max-h-56 object-cover w-full hover:scale-105 transition-transform duration-300" @click.stop="openImageViewer(img)" />
                                </div>
                            </div>

                            <!-- Multi-modal Structured Media (Audio, Video, Files) -->
                            <div v-if="msg.media && msg.media.length > 0" class="mt-2.5 space-y-2">
                                <template v-for="(med, mIdx) in msg.media" :key="mIdx">
                                    <!-- Video Player -->
                                    <video v-if="med.type === 'video'" :src="med.url" controls class="rounded-xl max-h-52 w-full bg-black"></video>

                                    <!-- Audio Player / Voice Note -->
                                    <div v-else-if="med.type === 'audio'" class="p-2 rounded-xl bg-black/10 dark:bg-white/10 flex items-center gap-2">
                                        <span class="text-base">🎙️</span>
                                        <audio :src="med.url" controls class="w-full h-8"></audio>
                                    </div>

                                    <!-- Document File Download -->
                                    <a v-else :href="med.url" target="_blank" class="flex items-center gap-2 p-2 rounded-xl bg-black/10 dark:bg-white/10 hover:bg-black/20 text-xs font-bold truncate">
                                        <span>📄</span>
                                        <span class="truncate">{{ med.filename }}</span>
                                    </a>
                                </template>
                            </div>
                        </div>

                        <!-- Reactions Display Pills -->
                        <div v-if="msg.reactions && Object.keys(msg.reactions).length > 0" class="flex flex-wrap gap-1 mt-1">
                            <button 
                                v-for="(uids, emoji) in msg.reactions" 
                                :key="emoji"
                                @click="react(msg, emoji)"
                                class="px-1.5 py-0.5 rounded-full text-xs bg-gray-100 dark:bg-gray-800 border dark:border-gray-700 flex items-center gap-1 shadow-xs hover:scale-110 transition-transform"
                                :class="uids.includes(authStore.user?.id) ? 'ring-1 ring-blue-500 bg-blue-50 dark:bg-blue-900/30' : ''"
                            >
                                <span>{{ emoji }}</span>
                                <span class="text-[10px] font-bold opacity-70">{{ uids.length }}</span>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Timestamp & Quick Actions Bar (Hover) -->
                <div class="flex items-center gap-2 mt-1 px-1 opacity-60 group-hover/dm:opacity-100 transition-opacity">
                    <span class="text-[10px] font-mono text-gray-400">{{ formatTimestamp(msg.sent_at) }}</span>

                    <!-- Quick Emoji Hover Bar -->
                    <div class="hidden group-hover/dm:flex items-center gap-0.5 bg-white dark:bg-gray-800 p-0.5 rounded-full border dark:border-gray-700 shadow-sm animate-in fade-in">
                        <button v-for="em in quickEmojis" :key="em" @click="react(msg, em)" class="p-1 hover:scale-125 transition-transform text-xs">{{ em }}</button>
                        <button @click="startReply(msg)" class="p-1 text-gray-400 hover:text-blue-500 text-[10px] font-bold ml-1" title="Quote & Reply">↩</button>
                        <button v-if="msg.sender_id === authStore.user?.id || authStore.user?.is_admin" @click="socialStore.deleteMessage(msg.id)" class="p-1 text-gray-400 hover:text-red-500 text-[10px]" title="Delete Message">✕</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- ── INPUT WORKSTATION ── -->
        <div class="p-3 border-t dark:border-gray-800 bg-gray-50/90 dark:bg-gray-900/90 backdrop-blur-md shrink-0 space-y-2">

            <!-- Quoted Reply Banner -->
            <div v-if="replyingTo" class="p-2 bg-blue-50 dark:bg-blue-950/40 border-l-4 border-blue-500 rounded-r-xl flex items-center justify-between text-xs animate-in fade-in">
                <div class="min-w-0 pr-2">
                    <span class="font-bold text-blue-600 dark:text-blue-400">Replying to {{ replyingTo.sender_username }}:</span>
                    <p class="truncate text-gray-600 dark:text-gray-300 italic">"{{ replyingTo.content }}"</p>
                </div>
                <button @click="replyingTo = null" class="p-1 text-gray-400 hover:text-red-500"><IconXMark class="w-4 h-4"/></button>
            </div>

            <!-- Staged Attachments Strip -->
            <div v-if="stagedFiles.length > 0" class="flex gap-2 overflow-x-auto custom-scrollbar pb-1">
                <div v-for="(f, i) in stagedFiles" :key="i" class="relative px-2.5 py-1.5 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 text-xs flex items-center gap-2 shadow-xs shrink-0">
                    <span class="font-bold truncate max-w-[120px]">{{ f.name }}</span>
                    <button @click="removeStagedFile(i)" class="text-gray-400 hover:text-red-500"><IconXMark class="w-3.5 h-3.5"/></button>
                </div>
            </div>

            <!-- Controls Row -->
            <div class="flex items-center gap-2">
                <!-- File Picker Trigger -->
                <button @click="triggerFilePicker" class="btn-icon p-2 text-gray-500 hover:text-blue-500" title="Attach Photos, Videos or Audio">
                    <IconPhoto class="w-5 h-5"/>
                </button>
                <input type="file" ref="fileInput" class="hidden" multiple accept="image/*,video/*,audio/*" @change="handleFiles">

                <!-- Voice Recording Trigger -->
                <button 
                    @click="toggleVoiceRecording" 
                    class="btn-icon p-2 transition-colors"
                    :class="isRecordingVoice ? 'text-red-500 bg-red-50 dark:bg-red-950/40 animate-pulse' : 'text-gray-500 hover:text-blue-500'"
                    :title="isRecordingVoice ? 'Stop and Attach Voice Note' : 'Record Voice Note'"
                >
                    <IconStopCircle v-if="isRecordingVoice" class="w-5 h-5" />
                    <IconMicrophone v-else class="w-5 h-5" />
                </button>

                <!-- Input Textarea -->
                <input 
                    v-model="content" 
                    @input="handleInputChange"
                    @keyup.enter="send" 
                    class="input-field flex-1 !py-2 text-sm bg-white dark:bg-gray-800" 
                    placeholder="Write a message..." 
                    autocomplete="off" 
                />

                <!-- Send Button -->
                <button 
                    @click="send" 
                    class="btn btn-primary p-2.5 rounded-xl shadow-md flex items-center justify-center shrink-0" 
                    :disabled="isUploading || (!content.trim() && stagedFiles.length === 0)"
                >
                    <IconAnimateSpin v-if="isUploading" class="w-4 h-4 animate-spin" />
                    <IconSend v-else class="w-4 h-4"/>
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; height: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
.menu-item { @apply flex items-center w-full px-3 py-2 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left; }
.menu-divider { @apply my-1 border-t border-gray-100 dark:border-gray-700; }
</style>
