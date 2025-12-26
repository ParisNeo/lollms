<!-- [UPDATE] frontend/webui/src/components/ui/ImageViewerModal.vue -->
<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import { useImageStore } from '../../stores/images';
import AuthenticatedImage from './AuthenticatedImage.vue';
import apiClient from '../../services/api';

import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../assets/icons/IconMinimize.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconMinus from '../../assets/icons/IconMinus.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconSend from '../../assets/icons/IconSend.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();
const imageStore = useImageStore();

const scale = ref(1);
const posX = ref(0);
const posY = ref(0);
const isFullScreen = ref(false);
const imageWrapperRef = ref(null);
let isDragging = false;
let startX = 0;
let startY = 0;

const isOpen = computed(() => uiStore.imageViewer.isOpen);

const imageStyle = computed(() => {
  return {
    transform: `translate(${posX.value}px, ${posY.value}px) scale(${scale.value})`
  };
});

const handleWheel = (event) => {
    event.preventDefault();
    const scaleAmount = 0.1;
    let newScale = scale.value + (event.deltaY > 0 ? -scaleAmount : scaleAmount);
    // [FIX] Allow zoom under 100% (down to 10%)
    scale.value = Math.min(Math.max(0.1, newScale), 10); 
    
    if(scale.value === 1) {
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
    // [FIX] Allow zoom under 100% via UI buttons
    let newScale = Math.max(0.1, scale.value - 0.25);
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

const toggleFullScreen = () => {
    if (!imageWrapperRef.value) return;
    
    if (!document.fullscreenElement) {
        imageWrapperRef.value.requestFullscreen().then(() => {
            isFullScreen.value = true;
        }).catch(err => {
            uiStore.addNotification(`Fullscreen failed: ${err.message}`, 'error');
        });
    } else {
        document.exitFullscreen();
    }
};

const onFullscreenChange = () => {
    isFullScreen.value = !!document.fullscreenElement;
};

const handleDownload = async () => {
    try {
        let downloadUrl;
        let filename = 'download.png';
        const src = uiStore.imageViewerSrc;

        if (src.startsWith('data:')) {
            downloadUrl = src;
            const mimeMatch = src.match(/data:([^;]+);/);
            if (mimeMatch && mimeMatch[1]) {
                const ext = mimeMatch[1].split('/')[1] || 'png';
                filename = `pasted_image_${Date.now()}.${ext}`;
            }
        } else {
            const response = await apiClient.get(src, { responseType: 'blob' });
            downloadUrl = window.URL.createObjectURL(new Blob([response.data]));
            
            // Extract filename from URL or use MimeType
            const urlParts = src.split('/');
            const lastPart = urlParts.pop();
            
            if (lastPart && lastPart !== 'file' && lastPart.includes('.')) {
                filename = lastPart;
            } else {
                const blobType = response.data.type; // e.g. "image/png"
                const ext = blobType.split('/')[1] || 'png';
                filename = `image_${Date.now()}.${ext}`;
            }
        }
        
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        if (!src.startsWith('data:')) {
            window.URL.revokeObjectURL(downloadUrl);
        }
    } catch (error) {
        console.error("Download error:", error);
        uiStore.addNotification('Failed to download image.', 'error');
    }
};

const handleSendToDiscussion = async () => {
    const currentItem = uiStore.imageViewer.imageList[uiStore.imageViewer.startIndex];
    if (!currentItem) return;

    const { confirmed, value: discussionId } = await uiStore.showConfirmation({
        title: 'Send to Discussion',
        message: 'Select a discussion context to receive this image:',
        confirmText: 'Send',
        inputType: 'select',
        inputOptions: discussionsStore.sortedDiscussions.map(d => ({ text: d.title, value: d.id })),
        inputValue: discussionsStore.currentDiscussionId
    });

    if (confirmed && discussionId) {
        try {
            let imageId = currentItem.id;
            if (!imageId && currentItem.src) {
                const match = currentItem.src.match(/\/api\/image-studio\/([^/]+)\/file/);
                if (match) imageId = match[1];
            }

            if (imageId) {
                await imageStore.moveImageToDiscussion(imageId, discussionId);
            } else {
                const response = await apiClient.get(currentItem.src, { responseType: 'blob' });
                const file = new File([response.data], "image_transfer.png", { type: response.data.type });
                
                const originalId = discussionsStore.currentDiscussionId;
                discussionsStore.currentDiscussionId = discussionId;
                try {
                    await discussionsStore.uploadDiscussionImage(file);
                } finally {
                    discussionsStore.currentDiscussionId = originalId;
                }
            }
            uiStore.addNotification('Image sent to discussion gallery.', 'success');
        } catch (error) {
            console.error("Failed to send image:", error);
            uiStore.addNotification('Failed to send image to discussion.', 'error');
        }
    }
};

const keydownHandler = (e) => {
    if (e.key === 'Escape') {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            uiStore.closeImageViewer();
        }
    }
};

onMounted(() => {
    window.addEventListener('keydown', keydownHandler);
    document.addEventListener('fullscreenchange', onFullscreenChange);
});

onUnmounted(() => {
    window.removeEventListener('keydown', keydownHandler);
    document.removeEventListener('fullscreenchange', onFullscreenChange);
});

watch(isOpen, (newVal) => {
    if (!newVal && document.fullscreenElement) {
        document.exitFullscreen();
    }
});
</script>

<template>
    <div v-if="isOpen" class="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm" @click.self="uiStore.closeImageViewer">
        <!-- Image Container -->
        <div 
            ref="imageWrapperRef"
            :style="imageStyle"
            class="transition-transform duration-200 ease-out flex items-center justify-center bg-black"
            :class="{ 'cursor-grab': scale > 1, 'active:cursor-grabbing': isDragging, 'w-screen h-screen': isFullScreen }"
            @wheel="handleWheel"
            @mousedown="startDrag"
        >
            <AuthenticatedImage 
                :src="uiStore.imageViewerSrc" 
                class="max-w-[95vw] max-h-[95vh] object-contain shadow-2xl" 
                :class="{ 'max-w-full max-h-full': isFullScreen }"
            />
        </div>

        <!-- Toolbar -->
        <div class="absolute bottom-5 left-1/2 -translate-x-1/2 flex items-center space-x-2 bg-gray-900/60 text-white p-2 rounded-xl backdrop-blur-md border border-white/10 shadow-2xl z-[110]">
            <button @click="zoomOut" class="btn-viewer" title="Zoom Out">
                <IconMinus class="w-5 h-5" />
            </button>
            <span class="min-w-[50px] text-center text-xs font-mono">{{ Math.round(scale * 100) }}%</span>
            <button @click="zoomIn" class="btn-viewer" title="Zoom In">
                <IconPlus class="w-5 h-5" />
            </button>
            <div class="w-px h-6 bg-white/20 mx-1"></div>
            <button @click="resetZoom" class="btn-viewer" title="Reset View">
                <IconRefresh class="w-5 h-5" />
            </button>
            <button @click="toggleFullScreen" class="btn-viewer" :title="isFullScreen ? 'Exit Fullscreen' : 'Fullscreen'">
                <IconMinimize v-if="isFullScreen" class="w-5 h-5" />
                <IconMaximize v-else class="w-5 h-5" />
            </button>
             <button @click="handleSendToDiscussion" class="btn-viewer text-blue-400 hover:text-blue-300" title="Send to Discussion">
                <IconSend class="w-5 h-5" />
            </button>
             <button @click="handleDownload" class="btn-viewer" title="Download Image">
                <IconArrowDownTray class="w-5 h-5" />
            </button>
        </div>

        <!-- Close Button -->
        <button @click="uiStore.closeImageViewer" class="absolute top-4 right-4 p-2 rounded-full bg-black/20 text-white/70 hover:text-white hover:bg-black/40 transition-all z-[110]" title="Close (Esc)">
             <IconXMark class="w-8 h-8" />
        </button>
    </div>
</template>

<style scoped>
.btn-viewer {
    @apply p-2 rounded-lg hover:bg-white/20 transition-all active:scale-95 flex items-center justify-center;
}
:fullscreen .max-w-\[95vw\] {
    max-width: 100vw;
    max-height: 100vh;
}
</style>
