<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import AuthenticatedImage from './AuthenticatedImage.vue';
import apiClient from '../../services/api';

const uiStore = useUiStore();
const scale = ref(1);
const posX = ref(0);
const posY = ref(0);
let isDragging = false;
let startX = 0;
let startY = 0;

// NEW: Reactive computed property for the style
const imageStyle = computed(() => {
  return {
    transform: `translate(${posX.value}px, ${posY.value}px) scale(${scale.value})`
  };
});

const handleWheel = (event) => {
    event.preventDefault();
    const scaleAmount = 0.1;
    let newScale = scale.value + (event.deltaY > 0 ? -scaleAmount : scaleAmount);
    scale.value = Math.min(Math.max(1, newScale), 10); // Clamp scale
    
    if(scale.value === 1) { // Reset position when fully zoomed out
        resetZoom();
    }
};

const startDrag = (event) => {
    if (scale.value <= 1) return;
    event.preventDefault();
    isDragging = true;
    startX = event.clientX - posX.value;
    startY = event.clientY - posY.value;
    window.addEventListener('mousemove', drag);
    window.addEventListener('mouseup', stopDrag);
};

const drag = (event) => {
    if (isDragging) {
        event.preventDefault();
        posX.value = event.clientX - startX;
        posY.value = event.clientY - startY;
    }
};

const stopDrag = () => {
    isDragging = false;
    window.removeEventListener('mousemove', drag);
    window.removeEventListener('mouseup', stopDrag);
};

const zoomIn = () => {
    scale.value = Math.min(10, scale.value + 0.25);
}

const zoomOut = () => {
    let newScale = Math.max(1, scale.value - 0.25);
    if(newScale === 1) {
        resetZoom();
    } else {
        scale.value = newScale;
    }
}

const resetZoom = () => {
    scale.value = 1;
    posX.value = 0;
    posY.value = 0;
};

const handleDownload = async () => {
    try {
        const response = await apiClient.get(uiStore.imageViewerSrc, { responseType: 'blob' });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        link.href = url;
        const filename = uiStore.imageViewerSrc.split('/').pop() || 'download.jpg';
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        uiStore.addNotification('Failed to download image.', 'error');
    }
};

const keydownHandler = (e) => {
    if (e.key === 'Escape') {
        uiStore.closeImageViewer();
    }
};

onMounted(() => {
    window.addEventListener('keydown', keydownHandler);
});

onUnmounted(() => {
    window.removeEventListener('keydown', keydownHandler);
});

</script>

<template>
    <div class="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm" @click.self="uiStore.closeImageViewer">
        <!-- Image Container -->
        <div 
            :style="imageStyle"
            class="transition-transform duration-200 ease-out"
            :class="{ 'cursor-grab': scale > 1, 'active:cursor-grabbing': isDragging }"
            @wheel="handleWheel"
            @mousedown="startDrag"
        >
            <AuthenticatedImage 
                :src="uiStore.imageViewerSrc" 
                class="max-w-[90vw] max-h-[90vh] object-contain shadow-2xl" 
            />
        </div>

        <!-- Toolbar -->
        <div class="absolute bottom-5 left-1/2 -translate-x-1/2 flex items-center space-x-2 bg-gray-900/50 text-white p-2 rounded-lg backdrop-blur-md">
            <button @click="zoomOut" class="btn-viewer" title="Zoom Out">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" /></svg>
            </button>
            <span class="min-w-[50px] text-center text-sm">{{ Math.round(scale * 100) }}%</span>
            <button @click="zoomIn" class="btn-viewer" title="Zoom In">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" /></svg>
            </button>
            <button @click="resetZoom" class="btn-viewer" title="Reset Zoom">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h5M20 20v-5h-5M4 4l5 5M20 20l-5-5" /></svg>
            </button>
             <button @click="handleDownload" class="btn-viewer" title="Download Image">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
            </button>
        </div>

        <!-- Close Button -->
        <button @click="uiStore.closeImageViewer" class="absolute top-4 right-4 text-white/70 hover:text-white transition-colors" title="Close (Esc)">
             <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
    </div>
</template>

<style scoped>
.btn-viewer {
    @apply p-2 rounded-full hover:bg-white/20 transition-colors;
}
</style>