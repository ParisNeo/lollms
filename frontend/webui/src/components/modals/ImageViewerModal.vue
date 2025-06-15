<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import AuthenticatedImage from './AuthenticatedImage.vue';

const uiStore = useUiStore();

const src = computed(() => uiStore.imageViewerSrc);

function close() {
    uiStore.closeImageViewer();
}
</script>

<template>
  <div 
    class="modal-overlay flex items-center justify-center p-4" 
    :class="{'active-modal': src}"
    @click.self="close"
  >
    <div v-if="src" class="relative w-full h-full flex items-center justify-center">
      <!-- Close Button -->
      <button @click="close" class="absolute top-2 right-2 z-20 p-2 rounded-full bg-black/50 text-white hover:bg-black/75 transition-colors" aria-label="Close image viewer">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      <!-- Image Container -->
      <div class="max-w-[95vw] max-h-[95vh]">
          <AuthenticatedImage 
            :src="src" 
            alt="Full-size view" 
            class="object-contain w-full h-full shadow-2xl rounded-lg" 
          />
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s ease;
}
.modal-overlay.active-modal {
    opacity: 1;
    pointer-events: auto;
}
</style>