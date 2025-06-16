<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import DiscussionList from './DiscussionList.vue';
import UserInfo from './UserInfo.vue';
import logoUrl from '../../assets/logo.png';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

</script>

<template>
  <aside class="w-72 border-r dark:border-gray-700 flex flex-col shadow-lg bg-white dark:bg-gray-800">
    <!-- Header with Logo -->
    <div class="p-4 border-b dark:border-gray-700">
      <div class="flex items-center space-x-3">
        <img :src="logoUrl" alt="Logo" class="h-10 w-10 rounded-full shadow">
        <div>
          <h2 class="text-xl font-semibold text-gray-800 dark:text-gray-100">Lollms Chat</h2>
          <p class="text-xs text-gray-500 dark:text-gray-400">One tool to rule them all</p>
        </div>
      </div>
    </div>

    <!-- Discussion List (Main scrolling area) -->
    <DiscussionList class="flex-1 overflow-y-auto" />

    <!-- User Info and Menu at the bottom -->
    <div class="p-3 border-t dark:border-gray-700">
      <UserInfo />
    </div>
  </aside>
</template>