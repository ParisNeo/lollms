<script setup>
defineProps({
    isOpen: {
        type: Boolean,
        required: true
    },
    title: {
        type: String,
        default: 'Compressing Discussion...'
    }
});
</script>

<template>
  <Teleport to="body">
    <Transition 
      enter-active-class="transition ease-out duration-300" 
      enter-from-class="transform opacity-0 scale-95" 
      enter-to-class="transform opacity-100 scale-100" 
      leave-active-class="transition ease-in duration-75" 
      leave-from-class="transform opacity-100 scale-100" 
      leave-to-class="transform opacity-0 scale-95">
      
      <!-- Backdrop -->
      <div v-if="isOpen" 
        class="fixed inset-0 bg-black/40 backdrop-blur-sm z-[60] flex items-center justify-center pointer-events-none"
        aria-hidden="true"></div>

      <!-- Modal Panel -->
      <div v-if="isOpen" 
        class="fixed inset-0 z-[70] flex items-center justify-center pointer-events-none">
        
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 p-8 max-w-sm w-full mx-4 flex flex-col items-center gap-4 text-center relative overflow-hidden backdrop-blur-md bg-opacity-90 dark:bg-opacity-80">
          <!-- Animated Icon Container -->
          <div class="relative w-20 h-20 flex items-center justify-center mb-2">
             <div class="absolute inset-0 bg-blue-100 dark:bg-blue-900/50 rounded-full animate-pulse opacity-70"></div>
             <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-wand-sparkles text-blue-600 dark:text-blue-400 animate-bounce"><path d="m12 3 1.9 5.06a4.9 4.9 0 0 0 4.7-1.83l.4-7.47-1.9-5.06a3.6 3.6 0 0 0-4.7-1.83l-.4 7.47z"/><path d="M22 12l-5.5 1.56-3.2.63a7.2 7.2 0 0 1 1.1 2.4L9 20l-5.5 1.56-3.2.63a7.2 7.2 0 0 1 1.1 2.4l-5.14 4.12c1.9-.5 4.9-.4 7.8-1.3l.3-1.4c-2.5 1.5-4.5 2.8-4.8A7.2 7.2 0 0 1 1.7 21l.3 1.4c1.9.5 4.9.4 7.8-1.3l.3-1.4c2.5-1.5 4.5-2.8 4.8 2.8-.5 4.9-.4 7.8-1.3l.3-1.4"/><path d="M4 22 1 15.5 2.6 14a5.8 5.8 0 0 0 0-7.4L3 2l5.5-5L12 3l.5-5L17 3l.5-5-3.2-1.37a5.8 5.8 0 0 0-4-.4l-1.6.7z"/></svg>
          </div>

          <h3 class="text-lg font-bold text-gray-900 dark:text-white mb-1">{{ title }}</h3>
          <p class="text-sm text-gray-500 dark:text-gray-400">Waiting for the AI to summarize the context...</p>
          
          <!-- Simple Progress Bar Skeleton -->
          <div class="w-full h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden mt-2">
            <div class="h-full bg-gradient-to-r from-blue-500 to-indigo-500 w-[60%] animate-[shimmer_2s_infinite] rounded-full"></div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Fallback animations for shimmer if tailwind config is missing it */
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.animate-shimmer {
  animation: shimmer 2s infinite;
}
</style>