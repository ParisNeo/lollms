<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import TasksManagerButton from './TasksManagerButton.vue';
import ThemeToggle from '../ui/ThemeToggle.vue';
import IconPlusCircle from '../../assets/icons/IconPlusCircle.vue';
import IconDataZone from '../../assets/icons/IconDataZone.vue';
import logoUrl from '../../assets/logo.png';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const activeDiscussion = computed(() => discussionsStore.activeDiscussion);

function newDiscussion() {
  discussionsStore.createNewDiscussion();
}
</script>

<template>
  <header class="flex-shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-3 flex items-center justify-between shadow-sm z-10">
    <!-- Left Side: App Logo and Title -->
    <div class="flex items-center space-x-3">
        <img :src="logoUrl" alt="LoLLMs Logo" class="h-8 w-8">
        <h1 class="text-lg font-bold text-gray-800 dark:text-gray-100 hidden sm:block">LoLLMs</h1>
    </div>

    <!-- Right Side: Action Buttons -->
    <div class="flex items-center space-x-2">
      <ThemeToggle />
      <TasksManagerButton />

      <button v-if="activeDiscussion" @click="uiStore.toggleDataZone()" class="btn-icon" title="Toggle Data Zone">
        <IconDataZone class="w-5 h-5" />
      </button>

      <button @click="newDiscussion" class="btn btn-secondary" title="New Discussion">
        <IconPlusCircle class="w-5 h-5" />
        <span class="hidden sm:inline ml-2">New</span>
      </button>
      
      <!-- Slot for view-specific actions -->
      <slot name="actions"></slot>
    </div>
  </header>
</template>