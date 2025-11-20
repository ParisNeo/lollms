<script setup>
import { ref, computed, onMounted, onUnmounted, markRaw } from 'vue';
import { useSocialStore } from '../stores/social';
import { useUiStore } from '../stores/ui';
import ConversationList from '../components/dm/ConversationList.vue';
import DmWindow from '../components/dm/DmWindow.vue';
import IconMessage from '../assets/icons/IconMessage.vue';

const socialStore = useSocialStore();
const uiStore = useUiStore();

const activeConversationUserId = computed(() => socialStore.activeConversationUserId);

// If there is an active conversation ID, find it in activeConversations.
const selectedConversation = computed(() => {
    if (activeConversationUserId.value) {
        return socialStore.activeConversations[activeConversationUserId.value];
    }
    return null;
});

function handleConversationSelect(userId) {
    // Find the partner info from the summary list
    const partnerSummary = socialStore.conversations.find(c => c.partner_user_id === userId);
    
    if (partnerSummary) {
        socialStore.openConversation({
            id: partnerSummary.partner_user_id,
            username: partnerSummary.partner_username,
            icon: partnerSummary.partner_icon
        });
    }
}

onMounted(() => {
    uiStore.setPageTitle({ title: 'Messages', icon: markRaw(IconMessage) });
    socialStore.fetchConversations();
});

onUnmounted(() => {
    uiStore.setPageTitle({ title: '' });
});
</script>

<template>
    <div class="flex h-full bg-white dark:bg-gray-900 overflow-hidden">
        <!-- Sidebar List -->
        <div class="w-80 flex-shrink-0 border-r border-gray-200 dark:border-gray-700 h-full overflow-hidden">
            <ConversationList 
                :model-value="activeConversationUserId"
                @update:model-value="handleConversationSelect"
            />
        </div>
        
        <!-- Main Message Area -->
        <div class="flex-1 min-w-0 h-full flex flex-col relative">
            <DmWindow 
                v-if="selectedConversation" 
                :conversation="selectedConversation" 
                class="h-full"
            />
            
            <!-- Empty State -->
            <div v-else class="h-full flex flex-col items-center justify-center text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50">
                <div class="p-6 rounded-full bg-gray-100 dark:bg-gray-700 mb-4">
                    <IconMessage class="w-12 h-12 text-gray-400 dark:text-gray-500" />
                </div>
                <h3 class="text-lg font-medium text-gray-900 dark:text-gray-200">Your Messages</h3>
                <p class="mt-1 text-sm">Select a conversation from the list to start chatting.</p>
            </div>
        </div>
    </div>
</template>
