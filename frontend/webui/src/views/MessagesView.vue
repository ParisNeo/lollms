<script setup>
import { ref, computed, watch } from 'vue';
import { useSocialStore } from '../stores/social';
import ConversationList from '../components/dm/ConversationList.vue';
import DmWindow from '../components/dm/DmWindow.vue';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import IconMessage from '../assets/icons/IconMessage.vue';

const socialStore = useSocialStore();
const selectedUserId = ref(null);

const selectedConversation = computed(() => {
  if (!selectedUserId.value) return null;
  // Make sure the conversation object exists before trying to access it
  if (!socialStore.activeConversations[selectedUserId.value]) {
    // If it doesn't exist, it might be because the list hasn't updated yet.
    // We can try to find it in the main list as a fallback.
    const convoSummary = socialStore.conversations.find(c => c.partner_user_id === selectedUserId.value);
    if (convoSummary) {
      socialStore.openConversation({
        id: convoSummary.partner_user_id,
        username: convoSummary.partner_username,
        icon: convoSummary.partner_icon,
      });
      return socialStore.activeConversations[selectedUserId.value];
    }
    return null;
  }
  return socialStore.activeConversations[selectedUserId.value];
});

watch(selectedUserId, (newUserId, oldUserId) => {
    if (newUserId && newUserId !== oldUserId) {
        socialStore.markConversationAsRead(newUserId);
    }
});
</script>

<template>
  <PageViewLayout title="Direct Messages" :titleIcon="IconMessage">
    <template #sidebar>
        <ConversationList v-model="selectedUserId" />
    </template>
    <template #main>
        <div class="h-full">
            <DmWindow v-if="selectedConversation" :conversation="selectedConversation" />
            <div v-else class="h-full flex items-center justify-center bg-gray-100 dark:bg-gray-900">
                <div class="text-center">
                <h2 class="text-xl font-semibold text-gray-600 dark:text-gray-300">Select a conversation</h2>
                <p class="mt-1 text-gray-500">Choose a user from the list on the left to view messages.</p>
                </div>
            </div>
        </div>
    </template>
  </PageViewLayout>
</template>