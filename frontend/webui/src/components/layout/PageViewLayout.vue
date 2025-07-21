<script setup>
import { ref } from 'vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconMenu from '../../assets/icons/IconMenu.vue';

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  titleIcon: {
    type: Object, // Vue component
    default: null
  }
});

const isSidebarOpen = ref(false);
</script>

<template>
  <div class="flex h-screen bg-gray-100 dark:bg-gray-900 overflow-hidden">
    <!-- Mobile Sidebar Overlay -->
    <div v-if="isSidebarOpen" @click="isSidebarOpen = false" class="fixed inset-0 bg-black/30 z-20 md:hidden"></div>

    <!-- Sidebar Navigation -->
    <nav class="fixed inset-y-0 left-0 z-30 w-64 bg-white dark:bg-gray-800 border-r dark:border-gray-700 flex flex-col transform transition-transform md:relative md:translate-x-0"
         :class="{'-translate-x-full': !isSidebarOpen}">
        
        <div class="p-4 space-y-1 overflow-y-auto flex-grow">
            <slot name="sidebar"></slot>
        </div>

        <div class="mt-auto p-4 border-t dark:border-gray-700 flex-shrink-0">
            <router-link 
                to="/" 
                class="flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
                <IconArrowLeft class="w-5 h-5" />
                <span>Back to App</span>
            </router-link>
        </div>
    </nav>
    
    <div class="flex flex-col flex-1 overflow-hidden">
        <header class="bg-white dark:bg-gray-800 border-b dark:border-gray-700 p-4 flex items-center shadow-sm flex-shrink-0">
            <button @click="isSidebarOpen = !isSidebarOpen" class="md:hidden mr-4 text-gray-500 dark:text-gray-400">
                <IconMenu class="h-6 w-6" />
            </button>
            
            <div class="flex items-center space-x-3">
                <component v-if="titleIcon" :is="titleIcon" class="w-6 h-6 text-gray-500 dark:text-gray-400" />
                <h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">{{ title }}</h1>
            </div>
        </header>

        <main class="flex-grow overflow-y-auto p-6">
            <slot name="main"></slot>
        </main>
    </div>
  </div>
</template>