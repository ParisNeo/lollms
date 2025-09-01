<script setup>
import { computed, watch } from 'vue';
import { useUiStore } from '../stores/ui';
import FeedComponent from '../components/social/FeedComponent.vue';
import ChatView from '../components/chat/ChatView.vue';
import DmWindow from '../components/dm/DmWindow.vue';
import { useSocialStore } from '../stores/social';

const uiStore = useUiStore();
const socialStore = useSocialStore();

const mainView = computed(() => uiStore.mainView);
const activeDmWindows = computed(() => socialStore.activeConversations);

watch(activeDmWindows, (newVal) => {
  console.log("Active DM Windows changed:", Object.keys(newVal));
}, { deep: true });
</script>

<template>
  <div class="h-full w-full relative">
    <div class="h-full w-full">
        <FeedComponent v-if="mainView === 'feed'" />
        <ChatView v-else />
    </div>
    
    <!-- DM Windows will float over the main view -->
    <div class="absolute bottom-0 right-0 z-30 flex items-end space-x-4 pr-4">
      <DmWindow 
        v-for="convo in activeDmWindows"
        :key="convo.partner.id"
        :conversation="convo"
      />
    </div>
  </div>
</template>