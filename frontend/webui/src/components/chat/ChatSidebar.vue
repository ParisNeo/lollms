<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useSocialStore } from '../../stores/social';
import { useUiStore } from '../../stores/ui';
import ConversationList from '../dm/ConversationList.vue';
import DmWindow from '../dm/DmWindow.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const socialStore = useSocialStore();
const uiStore = useUiStore();

const isOpen = computed(() => uiStore.isChatSidebarOpen);
const activeConversationUserId = computed(() => socialStore.activeConversationUserId);
const selectedConversation = computed(() => {
    if (activeConversationUserId.value) {
        return socialStore.activeConversations[activeConversationUserId.value];
    }
    return null;
});

function handleConversationSelect(userId) {
    const partnerSummary = socialStore.conversations.find(c => c.partner_user_id === userId);
    if (partnerSummary) {
        socialStore.openConversation({
            id: partnerSummary.partner_user_id,
            username: partnerSummary.partner_username,
            icon: partnerSummary.partner_icon
        });
    }
}

function closeSidebar() {
    uiStore.isChatSidebarOpen = false;
}

function goBackToList() {
    socialStore.activeConversationUserId = null;
}

onMounted(() => {
    // Ensure initial fetch if opening
    if (isOpen.value) {
        socialStore.fetchConversations();
    }
});

watch(isOpen, (val) => {
    if (val) socialStore.fetchConversations();
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
        <div v-if="isOpen" class="fixed inset-y-0 right-0 z-50 w-full sm:w-96 bg-white dark:bg-gray-900 shadow-2xl flex flex-col border-l dark:border-gray-700">
            <div class="flex items-center justify-between p-3 border-b dark:border-gray-700">
                <h2 class="font-semibold text-lg">Messages</h2>
                <button @click="closeSidebar" class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800">
                    <IconXMark class="w-6 h-6" />
                </button>
            </div>

            <div class="flex-grow overflow-hidden relative">
                <div v-if="selectedConversation" class="absolute inset-0 z-10 bg-white dark:bg-gray-900">
                    <DmWindow :conversation="selectedConversation" :compact="true" @back="goBackToList" class="h-full" />
                </div>
                <div class="h-full">
                    <ConversationList :model-value="activeConversationUserId" @update:model-value="handleConversationSelect" />
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
