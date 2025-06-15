<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import ThemeToggle from '../ui/ThemeToggle.vue';

const store = useDiscussionsStore();
const activeDiscussion = computed(() => store.activeDiscussion);
</script>

<template>
  <header v-if="activeDiscussion" class="border-b dark:border-gray-700 shadow-sm flex flex-col relative">
    <div class="p-3 flex items-center justify-between min-h-[65px] w-full">
      <!-- Discussion Title -->
      <h3 class="text-lg font-semibold truncate px-2 text-gray-800 dark:text-gray-100">
        {{ activeDiscussion.title }}
      </h3>

      <!-- Right-side Controls -->
      <div class="flex items-center space-x-3">
        <!-- RAG Controls have been moved to ChatInput.vue for better context -->
        
        <!-- Theme Toggle -->
        <ThemeToggle />
      </div>
    </div>
    <!-- Branch tabs would be rendered here if the backend supports it -->
  </header>
</template>