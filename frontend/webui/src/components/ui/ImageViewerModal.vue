<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-md select-none" @click.self="close">
    <div class="relative w-full h-full max-h-screen flex flex-col justify-between p-4 sm:p-6">
      
      <!-- Top Control Bar -->
      <div class="flex items-center justify-between w-full z-20 text-white">
        <div class="flex items-center gap-3">
            <span class="px-3 py-1 rounded-full bg-white/10 backdrop-blur text-xs font-mono font-bold tracking-wider">
                {{ currentIndex + 1 }} / {{ imageList.length }}
            </span>
            <span v-if="currentImage?.width && currentImage?.height" class="text-[10px] font-mono text-gray-400">
                {{ currentImage.width }}×{{ currentImage.height }}
            </span>
            <span v-if="currentImage?.seed && currentImage.seed !== -1" class="text-[10px] font-mono text-gray-400 hidden sm:inline">
                Seed: {{ currentImage.seed }}
            </span>
        </div>

        <div class="flex items-center gap-2">
            <button @click="zoomIn" class="p-2 hover:bg-white/10 rounded-full transition-colors" title="Zoom In (+)">
                <IconPlus class="w-5 h-5" />
            </button>
            <button @click="zoomOut" class="p-2 hover:bg-white/10 rounded-full transition-colors" title="Zoom Out (-)">
                <IconMinus class="w-5 h-5" />
            </button>
            <button @click="resetZoom" class="p-2 hover:bg-white/10 rounded-full transition-colors text-xs font-mono font-bold" title="Reset Zoom">
                1:1
            </button>
            <div class="h-4 w-px bg-white/20 mx-1"></div>
            <button @click="download" class="p-2 hover:bg-white/10 rounded-full transition-colors" title="Download Image">
                <IconArrowDownTray class="w-5 h-5" />
            </button>
            <button @click="copyPrompt" v-if="currentImage?.prompt" class="p-2 hover:bg-white/10 rounded-full transition-colors" title="Copy Prompt">
                <IconCopy class="w-5 h-5" />
            </button>
            <button @click="close" class="p-2 hover:bg-red-500 rounded-full transition-colors ml-2" title="Close (Esc)">
                <IconXMark class="w-6 h-6" />
            </button>
        </div>
      </div>

      <!-- Main Central Viewport -->
      <div class="grow relative overflow-hidden flex items-center justify-center my-2 max-h-[70vh] sm:max-h-[75vh]">
        <AuthenticatedImage 
          v-if="currentImage?.src"
          :src="currentImage.src" 
          :alt="currentImage.prompt || 'Full view'" 
          class="max-h-full max-w-full object-contain transition-transform duration-100 ease-out shadow-2xl rounded-2xl cursor-grab active:cursor-grabbing"
          :style="{ transform: `scale(${zoom}) translate(${pan.x}px, ${pan.y}px)` }"
          @wheel.prevent="handleWheel"
          @mousedown="startPan"
          @mousemove="doPan"
          @mouseup="endPan"
          @mouseleave="endPan"
        />

        <!-- Left Navigation Button -->
        <button 
          v-if="imageList.length > 1" 
          @click.stop="prev" 
          class="absolute left-4 p-4 rounded-full bg-black/40 hover:bg-blue-600 text-white transition-all backdrop-blur-md transform hover:scale-110 active:scale-95 shadow-xl"
          title="Previous Image (Left Arrow)"
        >
          <IconChevronLeft class="w-7 h-7" />
        </button>

        <!-- Right Navigation Button -->
        <button 
          v-if="imageList.length > 1" 
          @click.stop="next" 
          class="absolute right-4 p-4 rounded-full bg-black/40 hover:bg-blue-600 text-white transition-all backdrop-blur-md transform hover:scale-110 active:scale-95 shadow-xl"
          title="Next Image (Right Arrow)"
        >
          <IconChevronRight class="w-7 h-7" />
        </button>
      </div>

      <!-- Bottom Caption & Scrubbing Thumbnail Strip -->
      <div class="flex flex-col items-center gap-3 w-full max-w-4xl mx-auto z-20">
        <!-- Caption -->
        <div v-if="currentImage?.prompt" class="text-center text-white max-w-2xl px-4">
          <p class="text-xs sm:text-sm font-medium line-clamp-2 opacity-90 font-serif italic drop-shadow">
            "{{ currentImage.prompt }}"
          </p>
        </div>

        <!-- Interactive Thumbnail Strip -->
        <div v-if="imageList.length > 1" class="flex items-center gap-2 overflow-x-auto max-w-full p-2 rounded-2xl bg-black/40 backdrop-blur-md custom-scrollbar border border-white/10">
            <button 
                v-for="(img, idx) in imageList" 
                :key="'strip-'+idx"
                @click="goToIndex(idx)"
                class="relative w-12 h-12 shrink-0 rounded-xl overflow-hidden border-2 transition-all"
                :class="currentIndex === idx ? 'border-blue-500 scale-105 shadow-lg shadow-blue-500/30' : 'border-transparent opacity-50 hover:opacity-100'"
            >
                <AuthenticatedImage :src="img.thumbnail || img.src" class="w-full h-full object-cover pointer-events-none" />
            </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import AuthenticatedImage from './AuthenticatedImage.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconChevronLeft from '../../assets/icons/IconChevronLeft.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconMinus from '../../assets/icons/IconMinus.vue';

const uiStore = useUiStore();

const isOpen = computed(() => uiStore.isImageViewerOpen);
const data = computed(() => uiStore.imageViewerData);

const imageList = computed(() => data.value?.imageList || []);
const currentIndex = ref(0);

const currentImage = computed(() => imageList.value[currentIndex.value] || null);

// Zoom and Pan
const zoom = ref(1);
const pan = ref({ x: 0, y: 0 });
const isPanning = ref(false);
const startPos = ref({ x: 0, y: 0 });

watch(() => data.value, (newData) => {
  if (newData) {
    currentIndex.value = newData.startIndex || 0;
    resetZoom();
  }
}, { immediate: true });

function resetZoom() {
  zoom.value = 1;
  pan.value = { x: 0, y: 0 };
}

function zoomIn() {
    zoom.value = Math.min(zoom.value + 0.25, 4);
}

function zoomOut() {
    zoom.value = Math.max(zoom.value - 0.25, 0.5);
    if (zoom.value <= 1) pan.value = { x: 0, y: 0 };
}

function goToIndex(idx) {
    if (idx >= 0 && idx < imageList.value.length) {
        currentIndex.value = idx;
        resetZoom();
    }
}

function next() {
  if (currentIndex.value < imageList.value.length - 1) {
    currentIndex.value++;
    resetZoom();
  } else if (imageList.value.length > 1) {
    currentIndex.value = 0; // Wrap around
    resetZoom();
  }
}

function prev() {
  if (currentIndex.value > 0) {
    currentIndex.value--;
    resetZoom();
  } else if (imageList.value.length > 1) {
    currentIndex.value = imageList.value.length - 1; // Wrap around
    resetZoom();
  }
}

function close() {
  uiStore.closeImageViewer();
  resetZoom();
}

function copyPrompt() {
  if (currentImage.value?.prompt) {
    uiStore.copyToClipboard(currentImage.value.prompt);
  }
}

function download() {
  if (!currentImage.value?.src) return;
  const link = document.createElement('a');
  link.href = currentImage.value.src;
  link.download = `${currentImage.value.id || 'image'}_${Date.now()}.png`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  uiStore.addNotification('Image download started.', 'success', 1500);
}

// Pan & Zoom handlers
function handleWheel(e) {
  const delta = e.deltaY * -0.0015;
  zoom.value = Math.min(Math.max(0.5, zoom.value + delta), 4);
  if (zoom.value <= 1) pan.value = { x: 0, y: 0 };
}

function startPan(e) {
  if (zoom.value > 1) {
    isPanning.value = true;
    startPos.value = { x: e.clientX - pan.value.x, y: e.clientY - pan.value.y };
  }
}

function doPan(e) {
  if (isPanning.value && zoom.value > 1) {
    pan.value = {
      x: e.clientX - startPos.value.x,
      y: e.clientY - startPos.value.y
    };
  }
}

function endPan() {
  isPanning.value = false;
}

// Keyboard shortcuts
function handleKeyDown(e) {
  if (!isOpen.value) return;
  if (e.key === 'Escape') close();
  if (e.key === 'ArrowRight') next();
  if (e.key === 'ArrowLeft') prev();
  if (e.key === '+' || e.key === '=') zoomIn();
  if (e.key === '-') zoomOut();
  if (e.key === '0') resetZoom();
}

onMounted(() => window.addEventListener('keydown', handleKeyDown));
onUnmounted(() => window.removeEventListener('keydown', handleKeyDown));
</script>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { height: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-white/20 rounded-full; }
</style>