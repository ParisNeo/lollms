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

const props = defineProps({
    modelValue: { type: Number, default: null }
});

const emit = defineEmits(['update:modelValue']);

const socialStore = useSocialStore();
const authStore = useAuthStore();
const uiStore = useUiStore();

const conversations = computed(() => socialStore.conversations);
const isLoading = computed(() => socialStore.isLoadingConversations);
const user = computed(() => authStore.user);

const showCreateGroup = ref(false);
const newGroupName = ref('');
const selectedFriendsForGroup = ref([]);

// Helper to format time
function formatTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    return isToday ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : date.toLocaleDateString();
}

function selectConversation(convo) {
    // For legacy DMs, use partner ID. For groups, use group ID.
    const id = convo.partner_user_id || convo.id; 
    emit('update:modelValue', id);
}

async function createGroup() {
    if (!newGroupName.value.trim()) return;
    await socialStore.createGroupConversation(newGroupName.value, selectedFriendsForGroup.value);
    showCreateGroup.value = false;
    newGroupName.value = '';
    selectedFriendsForGroup.value = [];
}

// --- Context Menu Logic ---
const activeMenuId = ref(null);

function toggleMenu(convoId) {
    activeMenuId.value = activeMenuId.value === convoId ? null : convoId;
}

function closeMenu(e) {
    // Close menu if clicking outside. This handler is attached to document.
    if (!e.target.closest('.menu-trigger') && !e.target.closest('.menu-dropdown')) {
        activeMenuId.value = null;
    }
}

onMounted(() => {
    document.addEventListener('click', closeMenu);
});

onUnmounted(() => {
    document.removeEventListener('click', closeMenu);
});

async function handleDeleteConversation(convo) {
    const isGroup = !!convo.is_group;
    const confirmTitle = isGroup ? `Leave "${convo.name}"?` : `Delete conversation with ${convo.partner_username}?`;
    const confirmMsg = isGroup ? "You will be removed from this group." : "This will delete the conversation history for you.";
    
    const { confirmed } = await uiStore.showConfirmation({
        title: confirmTitle,
        message: confirmMsg,
        confirmText: isGroup ? 'Leave' : 'Delete'
    });

    if (confirmed) {
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
        <div class="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center shrink-0">
            <h2 class="font-bold text-lg text-gray-800 dark:text-gray-200">Messages</h2>
            <button @click="showCreateGroup = !showCreateGroup" class="p-1.5 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 text-blue-600 dark:text-blue-400" title="New Group">
                <IconPlus class="w-5 h-5" />
            </button>
        </div>

        <!-- Create Group Form -->
        <div v-if="showCreateGroup" class="p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
            <input v-model="newGroupName" type="text" placeholder="Group Name" class="input-field w-full mb-2 text-sm">
            <div class="flex justify-end gap-2">
                <button @click="showCreateGroup = false" class="btn btn-secondary btn-sm">Cancel</button>
                <button @click="createGroup" class="btn btn-primary btn-sm">Create</button>
            </div>
        </div>

        <!-- List -->
        <div class="flex-1 overflow-y-auto custom-scrollbar">
            <div v-if="isLoading" class="p-4 text-center text-gray-500 text-sm">Loading conversations...</div>
            <div v-else-if="conversations.length === 0" class="p-8 text-center text-gray-500">
                <p>No conversations yet.</p>
                <p class="text-xs mt-1">Start a chat from your Friends list.</p>
            </div>
            <ul v-else class="divide-y divide-gray-100 dark:divide-gray-800">
                <li v-for="convo in conversations" :key="convo.id + (convo.is_group ? '_g' : '_u')" 
                    class="group flex items-center border-b dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors"
                    :class="{ 'bg-blue-50 dark:bg-blue-900/10': modelValue === (convo.partner_user_id || convo.id) }"
                >
                    <!-- Main Clickable Area -->
                    <button 
                        @click="selectConversation(convo)"
                        class="flex-1 p-3 flex items-start gap-3 text-left min-w-0"
                    >
                        <div class="relative shrink-0">
                            <div v-if="convo.is_group" class="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-blue-600 dark:text-blue-300">
                                <IconUserGroup class="w-6 h-6" />
                            </div>
                            <UserAvatar v-else :username="convo.partner_username" :icon="convo.partner_icon" size-class="w-10 h-10" />
                            
                            <span v-if="convo.unread_count > 0" class="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center ring-2 ring-white dark:ring-gray-900 shadow-sm">
                                {{ convo.unread_count > 9 ? '9+' : convo.unread_count }}
                            </span>
                        </div>

                        <div class="flex-1 min-w-0">
                            <div class="flex justify-between items-baseline mb-0.5">
                                <h3 class="font-bold text-sm text-gray-900 dark:text-gray-100 truncate pr-2">
                                    {{ convo.name || convo.partner_username }}
                                </h3>
                                <span class="text-[10px] text-gray-400 shrink-0 font-medium">{{ formatTime(convo.last_message_at) }}</span>
                            </div>
                            <p class="text-xs text-gray-500 dark:text-gray-400 truncate h-4">
                                <span v-if="convo.last_message" class="opacity-90">{{ convo.last_message }}</span>
                                <span v-else class="italic opacity-50">No messages</span>
                            </p>
                        </div>
                    </button>

                    <!-- Actions Area (Always Visible) -->
                    <div class="px-2 flex items-center gap-1 flex-shrink-0 border-l dark:border-gray-700 ml-1">
                        <button 
                            @click.stop="handleDeleteConversation(convo)" 
                            class="p-2.5 rounded-lg text-red-500 bg-red-50/50 dark:bg-red-900/10 hover:bg-red-100 dark:hover:bg-red-900/30 transition-all border border-red-100 dark:border-red-900/30"
                            :title="convo.is_group ? 'Leave Group' : 'Delete Chat History'"
                        >
                            <IconTrash v-if="!convo.is_group" class="w-4 h-4" />
                            <IconSignOut v-else class="w-4 h-4" />
                        </button>
                        
                        <div class="relative">
                            <button @click.stop="toggleMenu(convo.partner_user_id || convo.id)" class="menu-trigger p-1.5 rounded-lg text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors">
                                <IconEllipsisVertical class="w-4 h-4" />
                            </button>
                            
                            <!-- Submenu (Z-indexed) -->
                            <div v-if="activeMenuId === (convo.partner_user_id || convo.id)" class="menu-dropdown absolute right-0 mt-1 w-32 bg-white dark:bg-gray-800 rounded shadow-xl border dark:border-gray-700 z-[100] py-1">
                                <button @click.stop="handleDeleteConversation(convo)" class="w-full text-left px-3 py-2 text-xs hover:bg-red-50 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400 flex items-center gap-2">
                                    <IconTrash class="w-3 h-3" />
                                    <span>Clear History</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </li>
            </ul>
        </div>
    </div>
</template>
