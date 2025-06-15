<script setup>
import { ref } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import DiscussionList from './DiscussionList.vue';
import UserInfo from './UserInfo.vue';
import logoUrl from '../../assets/logo.png'; // <-- IMPORT THE LOGO

const discussionsStore = useDiscussionsStore();

function handleNewDiscussion() {
  discussionsStore.createNewDiscussion();
}
</script>

<template>
  <aside class="w-72 border-r dark:border-gray-700 flex flex-col shadow-lg bg-white dark:bg-gray-800">
    <!-- Header with Logo and New Discussion Button -->
    <div class="p-4 border-b dark:border-gray-700">
      <div class="flex items-center space-x-3 mb-4">
        <img :src="logoUrl" alt="Logo" class="h-10 w-10 rounded-full shadow"> <!-- <-- BIND THE SRC -->
        <div>
          <h2 class="text-xl font-semibold text-gray-800 dark:text-gray-100">Lollms Chat</h2>
          <p class="text-xs text-gray-500 dark:text-gray-400">Simplified Version</p>
        </div>
      </div>
      <button 
        @click="handleNewDiscussion"
        class="w-full btn btn-primary flex items-center justify-center text-sm"
      >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5 mr-2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
        </svg>
        <span>New Discussion</span>
      </button>
    </div>

    <!-- Discussion List (Main scrolling area) -->
    <DiscussionList class="flex-1 overflow-y-auto" />

    <!-- User Info and Menu at the bottom -->
    <div class="p-3 border-t dark:border-gray-700">
      <UserInfo />
    </div>
  </aside>
</template>