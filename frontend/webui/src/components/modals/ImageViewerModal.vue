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
          <div class="flex items-center gap-2">
            <button @click="resetView" class="p-2 rounded-full hover:bg-white/20 transition-colors" title="Reset View">
                <IconRefresh class="w-6 h-6" />
            </button>
            <button @click="handleEdit" class="p-2 rounded-full hover:bg-white/20 transition-colors" title="Edit Image">
              <IconPencil class="w-6 h-6" />
            </button>
            <button @click="downloadImage" class="p-2 rounded-full hover:bg-white/20 transition-colors" title="Download">
              <IconArrowDownTray class="w-6 h-6" />
            </button>
            <button @click="close" class="p-2 rounded-full hover:bg-white/20 transition-colors" title="Close (Esc)">
              <IconClose class="w-6 h-6" />
            </button>
          </div>
        </div>

        <!-- Main Content -->
        <div 
          ref="imageWrapperRef"
          class="flex-1 flex items-center justify-center min-h-0 relative overflow-hidden"
          @wheel="handleWheel"
          @mousedown="handleMouseDown"
          @mousemove="handleMouseMove"
          @mouseup="stopDragging"
          @mouseleave="stopDragging"
        >
          <!-- Image -->
          <div class="w-full h-full flex items-center justify-center p-4">
            <AuthenticatedImage 
              v-if="isApiUrl(currentImageSrc)"
              :key="currentImageSrc" 
              :src="currentImageSrc" 
              :style="imageStyle"
              class="object-contain transition-transform max-w-full max-h-full" 
            />
            <img 
              v-else-if="currentImageSrc"
              :key="currentImageSrc"
              :src="currentImageSrc" 
              :style="imageStyle"
              class="object-contain transition-transform max-w-full max-h-full" 
            />
          </div>

          <!-- Next/Prev Buttons -->
          <button v-if="hasPrevious" @click.stop="previous" class="absolute left-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-black/40 hover:bg-black/60 text-white transition-colors" title="Previous (←)">
            <IconArrowLeft class="w-6 h-6" />
          </button>
          <button v-if="hasNext" @click.stop="next" class="absolute right-4 top-1/2 -translate-y-1/2 p-3 rounded-full bg-black/40 hover:bg-black/60 text-white transition-colors" title="Next (→)">
            <IconChevronRight class="w-6 h-6" />
          </button>
        </div>

        <!-- Footer / Thumbnails -->
        <div class="flex-shrink-0 bg-black/20 p-2">
            <div class="overflow-x-auto py-2 custom-scrollbar">
                <div class="flex items-center gap-3 px-2 whitespace-nowrap">
                    <div v-for="(image, index) in imageList" :key="getImageKey(image)" @click="currentIndex = index"
                        class="w-16 h-16 rounded-md overflow-hidden cursor-pointer flex-shrink-0 border-2 transition-colors"
                        :class="index === currentIndex ? 'border-blue-500' : 'border-transparent hover:border-gray-400'">
                        <AuthenticatedImage v-if="isApiUrl(image.src)" :src="image.src" class="w-full h-full object-cover" />
                        <img v-else :src="image.src" class="w-full h-full object-cover" />
                    </div>
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
import apiClient from '../../services/api';

import IconClose from '../../assets/icons/IconClose.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';

const uiStore = useUiStore();
const currentIndex = ref(0);

// --- Pan & Zoom State ---
const scale = ref(1);
const translateX = ref(0);
const translateY = ref(0);
const isDragging = ref(false);
const lastX = ref(0);
const lastY = ref(0);
const imageWrapperRef = ref(null);

const imageList = computed(() => uiStore.imageViewer.imageList);
const currentImage = computed(() => imageList.value[currentIndex.value] || null);
const currentImageSrc = computed(() => currentImage.value?.src);

const hasNext = computed(() => currentIndex.value < imageList.value.length - 1);
const hasPrevious = computed(() => currentIndex.value > 0);

const imageStyle = computed(() => ({
  transform: `scale(${scale.value}) translate(${translateX.value}px, ${translateY.value}px)`,
  cursor: isDragging.value ? 'grabbing' : 'grab',
}));

watch(() => uiStore.imageViewer.isOpen, (isOpen) => {
    if (isOpen) {
        currentIndex.value = uiStore.imageViewer.startIndex;
        resetView(); // Reset view when opening
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
const next = () => { if (hasNext.value) currentIndex.value++; resetView(); };
const previous = () => { if (hasPrevious.value) currentIndex.value--; resetView(); };

function handleKeydown(e) {
  if (uiStore.imageViewer.isOpen) {
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowRight' && hasNext.value) next();
    if (e.key === 'ArrowLeft' && hasPrevious.value) previous();
  }
}

async function downloadImage() {
    if (!currentImageSrc.value) return;
    try {
        const response = await apiClient.get(currentImageSrc.value, {
            responseType: 'blob',
        });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', currentImage.value?.filename || 'image.png');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error('Download failed:', error);
        uiStore.addNotification('Failed to download image.', 'error');
    }
}

function handleEdit() {
    if (!currentImage.value) return;
    // The image object from the viewer's list should have the full data needed
    const imageToEdit = {
        id: currentImage.value.id,
        filename: currentImage.value.filename,
        prompt: currentImage.value.prompt,
        model: currentImage.value.model
    };
    close();
    uiStore.openModal('inpaintingEditor', { image: imageToEdit });
}


// --- Pan & Zoom Methods ---
function resetView() {
  scale.value = 1;
  translateX.value = 0;
  translateY.value = 0;
}

function handleWheel(event) {
  event.preventDefault();
  const scaleAmount = 0.1;
  if (!imageWrapperRef.value) return;
  const rect = imageWrapperRef.value.getBoundingClientRect();
  
  const mouseX = event.clientX - rect.left;
  const mouseY = event.clientY - rect.top;

  const oldScale = scale.value;
  const newScale = oldScale * (1 - Math.sign(event.deltaY) * scaleAmount);
  scale.value = Math.min(Math.max(0.1, 10), newScale);

  const newTx = translateX.value - (mouseX / oldScale - mouseX / scale.value);
  const newTy = translateY.value - (mouseY / oldScale - mouseY / scale.value);

  translateX.value = newTx;
  translateY.value = newTy;
}

function handleMouseDown(event) {
  if (event.button !== 0) return; // Only main button
  event.preventDefault();
  isDragging.value = true;
  lastX.value = event.clientX;
  lastY.value = event.clientY;
}

function handleMouseMove(event) {
  if (!isDragging.value) return;
  event.preventDefault();
  const dx = (event.clientX - lastX.value) / scale.value;
  const dy = (event.clientY - lastY.value) / scale.value;
  translateX.value += dx;
  translateY.value += dy;
  lastX.value = event.clientX;
  lastY.value = event.clientY;
}

function stopDragging() {
  isDragging.value = false;
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown);
});
</script>