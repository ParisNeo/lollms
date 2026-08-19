<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconUserGroup from '../../assets/icons/IconUserGroup.vue';
import IconEllipsisVertical from '../../assets/icons/IconEllipsisVertical.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconSignOut from '../../assets/icons/IconSignOut.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const props = defineProps({
    modelValue: { type: [Number, String], default: null }
});

const emit = defineEmits(['update:modelValue']);

const socialStore = useSocialStore();
const authStore = useAuthStore();
const uiStore = useUiStore();

const searchQuery = ref('');
const showCreateGroup = ref(false);
const newGroupName = ref('');
const selectedFriendsForGroup = ref([]);

const conversations = computed(() => socialStore.conversations);
const isLoading = computed(() => socialStore.isLoadingConversations);
const friends = computed(() => socialStore.friends);

const filteredConversations = computed(() => {
    if (!searchQuery.value.trim()) return conversations.value;
    const q = searchQuery.value.toLowerCase().trim();
    return conversations.value.filter(c => 
        (c.name || '').toLowerCase().includes(q) || 
        (c.partner_username || '').toLowerCase().includes(q) ||
        (c.last_message || '').toLowerCase().includes(q)
    );
});

function formatTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    return isToday ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : date.toLocaleDateString();
}

function selectConversation(convo) {
    socialStore.openConversation(convo);
    const id = convo.is_group ? convo.id : convo.partner_user_id; 
    emit('update:modelValue', id);
}

async function createGroup() {
    if (!newGroupName.value.trim()) return;
    await socialStore.createGroupConversation(newGroupName.value.trim(), selectedFriendsForGroup.value);
    showCreateGroup.value = false;
    newGroupName.value = '';
    selectedFriendsForGroup.value = [];
}

const activeMenuId = ref(null);
function toggleMenu(convoId) {
    activeMenuId.value = activeMenuId.value === convoId ? null : convoId;
}

function closeMenu(e) {
    if (!e.target.closest('.menu-trigger') && !e.target.closest('.menu-dropdown')) {
        activeMenuId.value = null;
    }
}

onMounted(() => {
    document.addEventListener('click', closeMenu);
    socialStore.fetchFriends();
});

onUnmounted(() => {
    document.removeEventListener('click', closeMenu);
});

async function handleDeleteConversation(convo) {
    const isGroup = !!convo.is_group;
    const confirmTitle = isGroup ? `Leave "${convo.name}"?` : `Delete chat with ${convo.partner_username}?`;
    const confirmMsg = isGroup ? "You will be removed from this group." : "This will delete your copy of the message history.";

    const confirmed = await uiStore.showConfirmation({
        title: confirmTitle,
        message: confirmMsg,
        confirmText: isGroup ? 'Leave' : 'Delete',
        danger: true
    });

    if (confirmed.confirmed) {
        const id = isGroup ? convo.id : convo.partner_user_id;
        await socialStore.deleteConversation(id, isGroup);
        activeMenuId.value = null;
        if (props.modelValue === id) {
            emit('update:modelValue', null);
        }
    }
}
</script>

<template>
    <div class="flex flex-col h-full bg-white dark:bg-gray-900">
        <!-- Header -->
        <div class="p-4 border-b border-gray-200 dark:border-gray-800 flex justify-between items-center shrink-0">
            <div>
                <h2 class="font-black text-lg text-gray-900 dark:text-gray-100 tracking-tight">Messages</h2>
                <p class="text-[10px] text-gray-400 font-mono">Private & Group Channels</p>
            </div>
            <button @click="showCreateGroup = !showCreateGroup" class="p-2 rounded-xl bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 transition-all shadow-xs" title="New Group Conversation">
                <IconPlus class="w-4 h-4" />
            </button>
        </div>

        <!-- Search Bar -->
        <div class="p-3 border-b dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/30 shrink-0">
            <div class="relative">
                <IconMagnifyingGlass class="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input 
                    v-model="searchQuery" 
                    type="text" 
                    placeholder="Search conversations..." 
                    class="input-field !py-1.5 !pl-8 !text-xs w-full bg-white dark:bg-gray-800"
                />
                <button v-if="searchQuery" @click="searchQuery = ''" class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-red-500">
                    <IconXMark class="w-3.5 h-3.5" />
                </button>
            </div>
        </div>

        <!-- Create Group Form -->
        <div v-if="showCreateGroup" class="p-4 border-b border-gray-200 dark:border-gray-800 bg-blue-50/40 dark:bg-blue-950/20 space-y-3 animate-in fade-in">
            <h4 class="text-xs font-black uppercase text-blue-600 tracking-widest">New Group Chat</h4>
            <input v-model="newGroupName" type="text" placeholder="Group Name" class="input-field w-full text-xs bg-white dark:bg-gray-800">

            <div class="space-y-1 max-h-32 overflow-y-auto custom-scrollbar">
                <span class="text-[9px] font-bold text-gray-400 uppercase">Select Friends:</span>
                <div v-for="f in friends" :key="f.id" class="flex items-center gap-2 text-xs">
                    <input type="checkbox" :value="f.id" v-model="selectedFriendsForGroup" class="rounded text-blue-600">
                    <span class="truncate">{{ f.username }}</span>
                </div>
            </div>

            <div class="flex justify-end gap-2 pt-2">
                <button @click="showCreateGroup = false" class="btn btn-secondary btn-xs">Cancel</button>
                <button @click="createGroup" :disabled="!newGroupName.trim()" class="btn btn-primary btn-xs">Create Group</button>
            </div>
        </div>

        <!-- List -->
        <div class="flex-1 overflow-y-auto custom-scrollbar">
            <div v-if="isLoading" class="p-6 text-center text-gray-400 text-xs">Loading conversations...</div>
            <div v-else-if="filteredConversations.length === 0" class="p-8 text-center text-gray-400 space-y-1">
                <p class="text-xs font-bold uppercase tracking-widest">{{ searchQuery ? 'No matching conversations' : 'No conversations yet' }}</p>
                <p class="text-[10px] text-gray-500">Start a chat directly from your Friends tab.</p>
            </div>
            <ul v-else class="divide-y divide-gray-100 dark:divide-gray-800/60">
                <li v-for="convo in filteredConversations" :key="convo.id + (convo.is_group ? '_g' : '_u')" 
                    class="group flex items-center hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors"
                    :class="{ 'bg-blue-50/80 dark:bg-blue-900/20 border-l-3 border-blue-600': modelValue === (convo.is_group ? convo.id : convo.partner_user_id) }"
                >
                    <button 
                        @click="selectConversation(convo)"
                        class="flex-1 p-3 flex items-start gap-3 text-left min-w-0"
                    >
                        <div class="relative shrink-0">
                            <div v-if="convo.is_group" class="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center text-blue-600 dark:text-blue-300 font-bold border dark:border-gray-700">
                                <IconUserGroup class="w-5 h-5" />
                            </div>
                            <UserAvatar v-else :username="convo.partner_username" :icon="convo.partner_icon" size-class="w-10 h-10" />

                            <span v-if="convo.unread_count > 0" class="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-[10px] font-black rounded-full flex items-center justify-center ring-2 ring-white dark:ring-gray-900 shadow-sm">
                                {{ convo.unread_count > 9 ? '9+' : convo.unread_count }}
                            </span>
                        </div>

                        <div class="flex-1 min-w-0">
                            <div class="flex justify-between items-baseline mb-0.5">
                                <div class="flex items-center gap-1.5 truncate pr-2">
                                    <h3 class="font-bold text-xs text-gray-900 dark:text-gray-100 truncate">
                                        {{ convo.name || convo.partner_username }}
                                    </h3>
                                    <span v-if="convo.partner_username?.toLowerCase() === 'lollms'" class="text-[8px] bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 px-1 rounded font-black uppercase">
                                        AI
                                    </span>
                                </div>
                                <span class="text-[9px] text-gray-400 shrink-0 font-mono">{{ formatTime(convo.last_message_at) }}</span>
                            </div>
                            <p class="text-xs text-gray-500 dark:text-gray-400 truncate h-4 leading-tight font-serif italic">
                                <span v-if="convo.last_message" class="opacity-90">{{ convo.last_message }}</span>
                                <span v-else class="opacity-40">No messages yet</span>
                            </p>
                        </div>
                    </button>

                    <!-- Quick Delete / Leave Action -->
                    <div class="px-2 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button 
                            @click.stop="handleDeleteConversation(convo)" 
                            class="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/20"
                            :title="convo.is_group ? 'Leave Group' : 'Clear Chat History'"
                        >
                            <IconTrash v-if="!convo.is_group" class="w-3.5 h-3.5" />
                            <IconSignOut v-else class="w-3.5 h-3.5" />
                        </button>
                    </div>
                </li>
            </ul>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>
