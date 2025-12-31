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
      <div v-if="isOpen" class="fixed inset-0 z-[100] bg-black/90 backdrop-blur-md flex flex-col md:flex-row h-full w-full text-white overflow-hidden" @keydown.esc="close">
        
        <!-- Sidebar Thumbnails -->
        <div class="w-full md:w-64 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col h-full z-20">
             <div class="p-4 border-b border-gray-800 flex justify-between items-center bg-gray-950">
                 <h3 class="font-bold text-sm uppercase tracking-wider text-gray-400">Slides</h3>
                 <span class="text-xs text-gray-500 font-mono">{{ currentIndex + 1 }} / {{ slides.length }}</span>
             </div>
             <div class="flex-grow overflow-y-auto custom-scrollbar p-2 space-y-2">
                 <div v-for="(slide, index) in slides" :key="index" 
                      @click="goToSlide(index)"
                      class="relative aspect-video rounded-md overflow-hidden cursor-pointer border-2 transition-all group"
                      :class="index === currentIndex ? 'border-blue-500 ring-2 ring-blue-500/50' : 'border-transparent hover:border-gray-600'"
                 >
                     <img :src="slide.src" class="w-full h-full object-cover" loading="lazy" />
                     <div class="absolute inset-0 bg-black/20 group-hover:bg-transparent transition-colors"></div>
                     <div class="absolute bottom-1 left-1 bg-black/60 px-1.5 py-0.5 rounded text-[10px] font-bold font-mono">{{ index + 1 }}</div>
                 </div>
             </div>
             
             <!-- Mobile Close (only visible on small screens when sidebar wraps, though layout is flex-row on md) -->
             <div class="md:hidden p-2 border-t border-gray-800">
                 <button @click="close" class="w-full py-2 bg-gray-800 rounded text-sm">Close</button>
             </div>
        </div>

        <!-- Main Stage -->
        <div class="flex-grow relative flex flex-col h-full bg-black">
            <!-- Top Bar -->
            <div class="absolute top-0 left-0 right-0 p-4 flex justify-between items-start z-30 pointer-events-none">
                <div class="pointer-events-auto bg-black/40 backdrop-blur-md rounded-full px-4 py-1.5 text-sm font-medium border border-white/10">
                    {{ title || 'Presentation' }}
                </div>
                
                <div class="pointer-events-auto flex gap-2">
                    <button @click="toggleFullScreen" class="p-2 rounded-full bg-black/40 hover:bg-white/20 backdrop-blur-md border border-white/10 transition-colors" title="Fullscreen">
                        <IconMaximize v-if="!isFullScreen" class="w-5 h-5" />
                        <IconMinimize v-else class="w-5 h-5" />
                    </button>
                    <button @click="close" class="p-2 rounded-full bg-black/40 hover:bg-red-500/20 hover:text-red-400 backdrop-blur-md border border-white/10 transition-colors" title="Close">
                        <IconXMark class="w-5 h-5" />
                    </button>
                </div>
            </div>

            <!-- Slide View -->
            <div class="flex-grow flex items-center justify-center p-4 md:p-10 overflow-hidden relative group" @wheel="handleWheel">
                <!-- Navigation Buttons -->
                <button v-if="hasPrevious" @click="prevSlide" class="absolute left-4 z-20 p-3 rounded-full bg-black/20 hover:bg-black/60 hover:scale-110 transition-all backdrop-blur text-white/70 hover:text-white">
                    <IconArrowLeft class="w-8 h-8" />
                </button>
                <button v-if="hasNext" @click="nextSlide" class="absolute right-4 z-20 p-3 rounded-full bg-black/20 hover:bg-black/60 hover:scale-110 transition-all backdrop-blur text-white/70 hover:text-white">
                    <IconChevronRight class="w-8 h-8" />
                </button>

                <Transition name="slide-fade" mode="out-in">
                    <div :key="currentIndex" class="relative max-w-full max-h-full shadow-2xl">
                         <img :src="currentSlide.src" class="max-w-full max-h-[85vh] object-contain rounded-lg shadow-black/50" />
                    </div>
                </Transition>
            </div>

            <!-- Bottom Control Bar -->
            <div class="p-4 border-t border-white/10 bg-gray-900/80 backdrop-blur flex justify-center gap-4 z-30">
                 <button @click="handleExport('pptx')" class="btn-action">
                    <IconPresentationChartBar class="w-5 h-5 text-orange-400" />
                    <span>Export PPTX</span>
                 </button>
                 <button @click="handleExport('pdf')" class="btn-action">
                    <IconFileText class="w-5 h-5 text-red-400" />
                    <span>Export PDF</span>
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
import { useDiscussionsStore } from '../../stores/discussions';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../assets/icons/IconMinimize.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const isOpen = computed(() => uiStore.slideshow.isOpen);
const slides = computed(() => uiStore.slideshow.slides || []);
const currentIndex = computed(() => uiStore.slideshow.startIndex || 0);
const title = computed(() => uiStore.slideshow.title);
const messageId = computed(() => uiStore.slideshow.messageId);

const currentSlide = computed(() => slides.value[currentIndex.value] || {});
const hasNext = computed(() => currentIndex.value < slides.value.length - 1);
const hasPrevious = computed(() => currentIndex.value > 0);
const isFullScreen = ref(false);

function close() {
    uiStore.closeSlideshow();
}

function goToSlide(index) {
    uiStore.setSlideshowIndex(index);
}

function nextSlide() {
    if (hasNext.value) goToSlide(currentIndex.value + 1);
}

function prevSlide() {
    if (hasPrevious.value) goToSlide(currentIndex.value - 1);
}

function toggleFullScreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
        isFullScreen.value = true;
    } else {
        document.exitFullscreen();
        isFullScreen.value = false;
    }
}

function handleWheel(e) {
    if (e.deltaY > 0) nextSlide();
    else prevSlide();
}

function handleKeydown(e) {
    if (!isOpen.value) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === 'Space') nextSlide();
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') prevSlide();
}

async function handleExport(format) {
    if (!messageId.value) return;
    // Export functionality calls the discussion store action directly
    // Ideally, exportMessage should handle 'slideshow' mode logic if needed,
    // but standard exportMessage exports the whole message.
    // The backend update ensures that if we export a message with slides, 
    // it detects the slide items and exports ONLY images.
    await discussionsStore.exportMessage({
        discussionId: discussionsStore.currentDiscussionId,
        messageId: messageId.value,
        format: format
    });
}

onMounted(() => window.addEventListener('keydown', handleKeydown));
onUnmounted(() => window.removeEventListener('keydown', handleKeydown));

</script>

<style scoped>
.btn-action {
    @apply flex items-center gap-2 px-4 py-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors text-sm font-medium border border-white/10;
}
.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.3s ease;
}
.slide-fade-enter-from {
  opacity: 0;
  transform: translateX(20px);
}
.slide-fade-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}
</style>
