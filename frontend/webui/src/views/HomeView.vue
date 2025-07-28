<script setup>
import { computed } from 'vue';
import ChatView from '../components/chat/ChatView.vue';
import FeedComponent from '../components/social/FeedComponent.vue';
import DmWindow from '../components/dm/DmWindow.vue';
import { useUiStore } from '../stores/ui';
import { useDiscussionsStore } from '../stores/discussions';
import { useSocialStore } from '../stores/social';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();
const socialStore = useSocialStore();

const mainView = computed(() => uiStore.mainView);
const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const activeConversations = computed(() => Object.values(socialStore.activeConversations));

// This computed property determines if the chat view should be displayed.
const showChatView = computed(() => {
    return mainView.value === 'chat' && activeDiscussion.value !== null;
});

</script>

<template>
  <div class="h-full w-full relative">
    <div class="flex-grow flex flex-col min-h-0 h-full">
      <!-- Render ChatView only when it's explicitly the correct state -->
      <ChatView v-if="showChatView" class="flex-grow" />
      
      <!-- Render FeedComponent for all other cases (feed view, or chat view with no active discussion) -->
      <FeedComponent v-else class="flex-grow" />
    </div>

    <!-- Floating DM Windows Container -->
    <div class="fixed bottom-0 right-0 flex items-end space-x-4 pr-4 z-30 pointer-events-none">
      <DmWindow 
        v-for="(convo, index) in activeConversations"
        :key="convo.partner.id"
        :conversation="convo"
        :style="{ right: `${(index * 336) + 16}px` }"
        class="pointer-events-auto"
      />
    </div>
  </div>
</template>