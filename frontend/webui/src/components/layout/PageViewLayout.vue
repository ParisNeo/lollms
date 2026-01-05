<script setup>
import { ref, onUnmounted, watch, markRaw } from 'vue';
import { useUiStore } from '../../stores/ui';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';

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
const uiStore = useUiStore();

watch(() => [props.title, props.titleIcon], () => {
    // Sets the title in the global store, which GlobalHeader displays
    uiStore.setPageTitle({ title: props.title, icon: props.titleIcon ? markRaw(props.titleIcon) : null });
}, { immediate: true });

onUnmounted(() => {
    uiStore.setPageTitle({ title: '' });
});
</script>

<template>
  <div class="flex h-full bg-gray-100 dark:bg-gray-900 overflow-hidden relative">
    <!-- Mobile Sidebar Overlay -->
    <div v-if="isSidebarOpen" @click="isSidebarOpen = false" class="fixed inset-0 bg-black/30 z-20 md:hidden"></div>

    <!-- Sidebar Navigation -->
    <!-- Added md:flex to ensure it shows on desktop, hidden on mobile by default -->
    <nav class="fixed inset-y-0 left-0 z-30 w-64 bg-white dark:bg-gray-800 border-r dark:border-gray-700 flex flex-col transform transition-transform md:relative md:translate-x-0"
         :class="{'-translate-x-full': !isSidebarOpen, 'translate-x-0': isSidebarOpen}">
        
        <div class="p-4 space-y-1 overflow-y-auto flex-grow custom-scrollbar">
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
    
    <!-- Mobile Toggle Button (Floating) -->
    <button @click="isSidebarOpen = !isSidebarOpen" class="md:hidden absolute bottom-4 left-4 z-40 p-3 bg-blue-600 text-white rounded-full shadow-lg">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
    </button>

    <div class="flex flex-col flex-1 overflow-hidden min-w-0">
        <!-- 
            Updated: Added 'flex flex-col' to main to allow children to use h-full effectively. 
            This fixes the issue where DataStoresView content collapsed to 0 height.
        -->
        <main class="flex-1 overflow-y-auto custom-scrollbar flex flex-col">
            <slot name="main"></slot>
        </main>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>
