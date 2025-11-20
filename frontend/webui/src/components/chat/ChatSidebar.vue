<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useUiStore } from '../../stores/ui';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import DmWindow from '../dm/DmWindow.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const socialStore = useSocialStore();
const uiStore = useUiStore();
const activeTab = ref('chats'); // 'chats' or 'friends'

const isOpen = computed(() => uiStore.isChatSidebarOpen);
const activeConvoId = computed(() => socialStore.activeConversationId);
const activeConversation = computed(() => 
    activeConvoId.value ? socialStore.activeConversations[activeConvoId.value] : null
);

const friends = computed(() => socialStore.friends);
const conversations = computed(() => socialStore.conversations);

// New Group State
const showNewGroupForm = ref(false);
const newGroupName = ref('');
const selectedFriendsForGroup = ref([]);

function openChat(item) {
    socialStore.openConversation(item);
}

function backToList() {
    socialStore.activeConversationId = null;
}

async function createGroup() {
    if(!newGroupName.value || selectedFriendsForGroup.value.length === 0) return;
    await socialStore.createGroupConversation(newGroupName.value, selectedFriendsForGroup.value);
    showNewGroupForm.value = false;
    newGroupName.value = '';
    selectedFriendsForGroup.value = [];
}

// Status Indicator Logic
function getStatusColor(status) {
    if (status === 'connected') return 'bg-green-500';
    if (status === 'absent') return 'bg-yellow-500';
    return 'bg-gray-400'; // disconnected
}

function getStatusTitle(status) {
    if (status === 'connected') return 'Online';
    if (status === 'absent') return 'Absent';
    return 'Offline';
}

onMounted(() => {
    if(isOpen.value) {
        socialStore.fetchFriends();
        socialStore.fetchConversations();
    }
});

watch(isOpen, (val) => {
    if (val) {
        socialStore.fetchFriends();
        socialStore.fetchConversations();
    }
});
</script>

<template>
    <Transition
        enter-active-class="transform transition ease-in-out duration-300 sm:duration-500"
        enter-from-class="translate-x-full"
        enter-to-class="translate-x-0"
        leave-active-class="transform transition ease-in-out duration-300 sm:duration-500"
        leave-from-class="translate-x-0"
        leave-to-class="translate-x-full"
    >
        <div v-if="isOpen" class="fixed inset-y-0 right-0 z-50 w-80 sm:w-96 bg-white dark:bg-gray-900 shadow-2xl flex flex-col border-l dark:border-gray-700">
            <!-- Header -->
            <div class="flex items-center justify-between p-3 border-b dark:border-gray-700">
                <h2 class="font-semibold text-lg">Messaging</h2>
                <button @click="uiStore.isChatSidebarOpen = false"><IconXMark class="w-5 h-5"/></button>
            </div>

            <!-- Active Conversation View -->
            <div v-if="activeConversation" class="flex-grow flex flex-col overflow-hidden">
                 <DmWindow :conversation="activeConversation" :compact="true" @back="backToList" />
            </div>

            <!-- List View -->
            <div v-else class="flex-grow flex flex-col overflow-hidden">
                <!-- Tabs -->
                <div class="flex border-b dark:border-gray-700">
                    <button @click="activeTab='chats'" class="flex-1 py-2 text-sm font-medium" :class="activeTab==='chats'?'border-b-2 border-blue-500 text-blue-600':'text-gray-500'">Chats</button>
                    <button @click="activeTab='friends'" class="flex-1 py-2 text-sm font-medium" :class="activeTab==='friends'?'border-b-2 border-blue-500 text-blue-600':'text-gray-500'">Friends</button>
                </div>

                <!-- Chats List -->
                <div v-if="activeTab==='chats'" class="flex-1 overflow-y-auto p-2 space-y-1">
                    <button @click="showNewGroupForm = !showNewGroupForm" class="w-full py-2 px-3 mb-2 bg-blue-50 dark:bg-blue-900/20 text-blue-600 rounded flex items-center justify-center gap-2 text-sm">
                        <IconPlus class="w-4 h-4"/> New Group
                    </button>
                    
                    <div v-if="showNewGroupForm" class="p-3 bg-gray-100 dark:bg-gray-800 rounded mb-2">
                        <input v-model="newGroupName" placeholder="Group Name" class="input-field mb-2 w-full text-sm" />
                        <div class="max-h-32 overflow-y-auto mb-2 border rounded p-1">
                            <label v-for="f in friends" :key="f.id" class="flex items-center gap-2 p-1">
                                <input type="checkbox" :value="f.id" v-model="selectedFriendsForGroup">
                                <span>{{f.username}}</span>
                            </label>
                        </div>
                        <button @click="createGroup" class="btn btn-primary btn-sm w-full">Create</button>
                    </div>

                    <div v-for="c in conversations" :key="c.id || c.partner_user_id" @click="openChat(c)" class="flex items-center gap-3 p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded cursor-pointer">
                        <div v-if="c.is_group" class="w-10 h-10 bg-gray-300 rounded-full flex items-center justify-center text-gray-600 font-bold">{{ c.name ? c.name[0] : 'G' }}</div>
                        <UserAvatar v-else :username="c.partner_username" :icon="c.partner_icon" size-class="w-10 h-10" />
                        
                        <div class="flex-1 min-w-0">
                            <div class="font-medium truncate">{{ c.is_group ? c.name : c.partner_username }}</div>
                            <div class="text-xs text-gray-500 truncate">{{ c.last_message }}</div>
                        </div>
                    </div>
                </div>

                <!-- Friends List -->
                <div v-if="activeTab==='friends'" class="flex-1 overflow-y-auto p-2 space-y-1">
                    <div v-for="f in friends" :key="f.id" @click="openChat(f)" class="flex items-center gap-3 p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded cursor-pointer relative">
                        <div class="relative">
                            <UserAvatar :username="f.username" :icon="f.icon" size-class="w-10 h-10" />
                            <div 
                                class="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 border-2 border-white dark:border-gray-800 rounded-full"
                                :class="getStatusColor(f.status)"
                                :title="getStatusTitle(f.status)"
                            ></div>
                        </div>
                        <span class="font-medium">{{ f.username }}</span>
                    </div>
                </div>
            </div>
        </div>
    </Transition>
    
    <!-- Overlay for mobile -->
    <Transition
        enter-active-class="opacity-0 transition-opacity duration-300"
        enter-to-class="opacity-100"
        leave-active-class="opacity-100 transition-opacity duration-300"
        leave-to-class="opacity-0"
    >
        <div v-if="isOpen" @click="closeSidebar" class="fixed inset-0 bg-black/20 z-40 sm:hidden"></div>
    </Transition>
</template>
