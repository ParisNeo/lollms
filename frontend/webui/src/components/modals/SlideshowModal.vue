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
      <div 
        v-if="isOpen" 
        ref="slideshowContainer"
        class="fixed inset-0 z-[100] bg-black flex h-full w-full text-white overflow-hidden" 
        @keydown.esc="close"
      >
        <!-- Sidebar Thumbnails -->
        <div v-if="showThumbnails" class="w-64 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col h-full z-20">
            <div class="p-4 border-b border-gray-800 flex justify-between items-center bg-gray-950">
                <h3 class="font-bold text-xs uppercase tracking-wider text-gray-400">Slide Deck</h3>
                <span class="text-[10px] font-mono opacity-50">{{ currentIndex + 1 }} / {{ slides.length }}</span>
            </div>
            <div class="flex-grow overflow-y-auto custom-scrollbar p-2 space-y-2">
                <div v-for="(slide, index) in slides" :key="index" 
                    @click="goToSlide(index)"
                    class="relative aspect-video rounded border-2 transition-all cursor-pointer overflow-hidden group"
                    :class="index === currentIndex ? 'border-blue-500 ring-2 ring-blue-500/50' : 'border-transparent hover:border-gray-600'"
                >
                    <AuthenticatedImage :src="slide.src" class="w-full h-full object-cover" />
                    <div class="absolute inset-0 bg-black/20 group-hover:bg-transparent"></div>
                    <div class="absolute bottom-1 left-1 bg-black/60 px-1 text-[9px] font-bold font-mono">{{ index + 1 }}</div>
                </div>
            </div>
        </div>

        <!-- Main Content -->
        <div class="flex-grow relative flex flex-col h-full bg-black min-w-0">
            <!-- Header Controls -->
            <div class="absolute top-0 left-0 right-0 p-6 flex justify-between items-start z-30 opacity-0 hover:opacity-100 transition-opacity duration-300">
                <div class="bg-black/40 backdrop-blur-md rounded-full px-4 py-2 text-sm font-black border border-white/10 shadow-xl">
                    {{ title || 'Presentation' }}
                </div>
                
                <div class="flex gap-2">
                    <button @click="showThumbnails = !showThumbnails" class="p-2.5 rounded-full bg-black/40 hover:bg-white/20 backdrop-blur-md border border-white/10">
                        <IconLayout class="w-6 h-6" :class="{'text-blue-400': showThumbnails}" />
                    </button>
                    <button @click="toggleFullScreen" class="p-2.5 rounded-full bg-black/40 hover:bg-white/20 backdrop-blur-md border border-white/10">
                        <IconMaximize v-if="!isFullScreenMode" class="w-6 h-6" />
                        <IconMinimize v-else class="w-6 h-6" />
                    </button>
                    <button @click="close" class="p-2.5 rounded-full bg-black/40 hover:bg-red-500/40 backdrop-blur-md border border-white/10">
                        <IconXMark class="w-6 h-6 text-red-100" />
                    </button>
                </div>
            </div>

            <!-- Central Image Display -->
            <div class="flex-grow flex items-center justify-center p-4 md:p-12 relative group">
                <button v-if="hasPrevious" @click.stop="prevSlide" class="absolute left-6 z-20 p-4 rounded-full bg-black/20 hover:bg-black/60 transition-all text-white/50 hover:text-white">
                    <IconArrowLeft class="w-10 h-10" />
                </button>
                
                <div class="relative max-w-full max-h-full shadow-2xl z-0 transition-all duration-500">
                     <AuthenticatedImage :src="currentSlide.src" class="max-w-full max-h-[95vh] object-contain rounded-lg" />
                </div>

                <button v-if="hasNext" @click.stop="nextSlide" class="absolute right-6 z-20 p-4 rounded-full bg-black/20 hover:bg-black/60 transition-all text-white/50 hover:text-white">
                    <IconChevronRight class="w-10 h-10" />
                </button>
            </div>

            <!-- Bottom Progress -->
            <div class="p-4 bg-black/40 border-t border-white/5 backdrop-blur-sm flex items-center justify-center gap-6 z-30 opacity-0 group-hover:opacity-100 transition-opacity">
                 <button @click="togglePlay" class="flex items-center gap-2 px-6 py-2 rounded-full border border-white/10 hover:bg-white/10 transition-colors">
                    <component :is="isPlaying ? IconStopCircle : IconPlayCircle" class="w-5 h-5 text-blue-400" />
                    <span class="text-xs font-black uppercase tracking-widest">{{ isPlaying ? 'Stop' : 'Autoplay' }}</span>
                 </button>
            </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';

// Icons
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../assets/icons/IconMinimize.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconLayout from '../../assets/icons/IconLayout.vue';

const uiStore = useUiStore();
const isOpen = computed(() => uiStore.slideshow.isOpen);
const slides = computed(() => uiStore.slideshow.slides || []);
const currentIndex = computed(() => uiStore.slideshow.startIndex || 0);
const title = computed(() => uiStore.slideshow.title);

const currentSlide = computed(() => slides.value[currentIndex.value] || {});
const hasNext = computed(() => currentIndex.value < slides.value.length - 1);
const hasPrevious = computed(() => currentIndex.value > 0);

const showThumbnails = ref(true);
const isPlaying = ref(false);
const slideshowContainer = ref(null);
const isFullScreenMode = ref(false);
let playbackTimer = null;

function close() { isPlaying.value = false; uiStore.closeSlideshow(); }
function goToSlide(idx) { uiStore.setSlideshowIndex(idx); }
function nextSlide() { hasNext.value ? goToSlide(currentIndex.value + 1) : close(); }
function prevSlide() { if (hasPrevious.value) goToSlide(currentIndex.value - 1); }

function togglePlay() {
    isPlaying.value = !isPlaying.value;
    if (isPlaying.value) runPlayback();
    else clearTimeout(playbackTimer);
}

function runPlayback() {
    if (!isPlaying.value) return;
    playbackTimer = setTimeout(() => {
        if (hasNext.value) { nextSlide(); runPlayback(); }
        else { isPlaying.value = false; }
    }, 5000);
}

function toggleFullScreen() {
    if (!document.fullscreenElement) slideshowContainer.value.requestFullscreen();
    else document.exitFullscreen();
}

function handleKeydown(e) {
    if (!isOpen.value) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowRight' || e.key === ' ') nextSlide();
    if (e.key === 'ArrowLeft') prevSlide();
    if (e.key === 'f') toggleFullScreen();
}

onMounted(() => window.addEventListener('keydown', handleKeydown));
onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown);
    clearTimeout(playbackTimer);
});
</script>
