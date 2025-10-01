<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity ease-out duration-300"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity ease-in duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-if="uiStore.imageViewer.isOpen" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex flex-col" @click.self="close">
        <!-- Header -->
        <div class="flex-shrink-0 flex items-center justify-between p-4 text-white">
          <div class="min-w-0">
            <p class="text-sm font-semibold truncate">{{ currentImage?.prompt || 'Image' }}</p>
            <p v-if="currentImage?.model" class="text-xs text-gray-300 font-mono truncate">{{ currentImage.model }}</p>
          </div>
          <div class="flex items-center gap-4">
            <a :href="currentImageSrc" :download="currentImage?.filename || 'image.png'" class="p-2 rounded-full hover:bg-white/20 transition-colors" title="Download">
              <IconArrowDownTray class="w-6 h-6" />
            </a>
            <button @click="close" class="p-2 rounded-full hover:bg-white/20 transition-colors" title="Close (Esc)">
              <IconClose class="w-6 h-6" />
            </button>
          </div>
        </div>

        <!-- Main Content -->
        <div class="flex-1 flex items-center justify-center min-h-0 relative">
          <!-- Previous Button -->
          <button v-if="hasPrevious" @click="previous" class="absolute left-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-black/40 hover:bg-black/60 text-white transition-colors" title="Previous (←)">
            <IconArrowLeft class="w-6 h-6" />
          </button>
          
          <!-- Image -->
          <div class="w-full h-full flex items-center justify-center p-4">
            <AuthenticatedImage v-if="isApiUrl(currentImageSrc)" :src="currentImageSrc" class="max-w-full max-h-full object-contain" />
            <img v-else-if="currentImageSrc" :src="currentImageSrc" class="max-w-full max-h-full object-contain" />
          </div>

          <!-- Next Button -->
          <button v-if="hasNext" @click="next" class="absolute right-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-black/40 hover:bg-black/60 text-white transition-colors" title="Next (→)">
            <IconChevronRight class="w-6 h-6" />
          </button>
        </div>

        <!-- Footer / Thumbnails -->
        <div class="flex-shrink-0 p-4 overflow-x-auto">
          <div class="flex justify-center gap-2">
            <div v-for="(image, index) in imageList" :key="getImageKey(image)" @click="currentIndex = index"
                 class="w-16 h-16 rounded-md overflow-hidden cursor-pointer flex-shrink-0 border-2 transition-colors"
                 :class="index === currentIndex ? 'border-blue-500' : 'border-transparent hover:border-gray-400'">
              <AuthenticatedImage v-if="isApiUrl(image.src)" :src="image.src" class="w-full h-full object-cover" />
              <img v-else :src="image.src" class="w-full h-full object-cover" />
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';

import IconClose from '../../assets/icons/IconClose.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';

const uiStore = useUiStore();
const currentIndex = ref(0);

const imageList = computed(() => uiStore.imageViewer.imageList);
const currentImage = computed(() => imageList.value[currentIndex.value] || null);
const currentImageSrc = computed(() => currentImage.value?.src);

const hasNext = computed(() => currentIndex.value < imageList.value.length - 1);
const hasPrevious = computed(() => currentIndex.value > 0);

watch(() => uiStore.imageViewer.isOpen, (isOpen) => {
    if (isOpen) {
        currentIndex.value = uiStore.imageViewer.startIndex;
    }
});

function isApiUrl(src) {
    return src && src.startsWith('/api/');
}

function getImageKey(image) {
    if (image && image.src) {
        return image.id || image.src.substring(image.src.length - 30);
    }
    return Math.random();
}

const close = () => uiStore.closeImageViewer();
const next = () => { if (hasNext.value) currentIndex.value++; };
const previous = () => { if (hasPrevious.value) currentIndex.value--; };

function handleKeydown(e) {
  if (uiStore.imageViewer.isOpen) {
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowRight' && hasNext.value) next();
    if (e.key === 'ArrowLeft' && hasPrevious.value) previous();
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown);
});
</script>