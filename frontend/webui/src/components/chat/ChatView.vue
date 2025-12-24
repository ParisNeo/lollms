<!-- [UPDATE] frontend/webui/src/components/chat/ChatView.vue -->
<script setup>
import { computed, defineAsyncComponent, ref } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import { storeToRefs } from 'pinia';
import MessageArea from './MessageArea.vue';
import ChatInput from './ChatInput.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import useEventBus from '../../services/eventBus';

const DataZone = defineAsyncComponent(() => import('./data_zone/DataZone.vue'));

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const { isLoadingMessages, currentModelVisionSupport } = storeToRefs(discussionsStore);
const isDataZoneVisible = computed(() => uiStore.isDataZoneVisible);
const { emit } = useEventBus();
const isDraggingOver = ref(false);

function handleDragOver(event) {
    event.preventDefault();
    if (event.dataTransfer.types.includes('Files')) {
        isDraggingOver.value = true;
    }
}

function handleDragLeave(event) {
    if (!event.currentTarget.contains(event.relatedTarget)) {
        isDraggingOver.value = false;
    }
}

function handleDrop(event) {
    event.preventDefault();
    isDraggingOver.value = false;

    // Pass all dropped files to the event bus.
    // The Input component handles separating images from documents.
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) {
        emit('files-dropped-in-chat', files);
    }
}

async function handlePaste(event) {
    // If vision is not supported, we don't try to intercept images at the view level.
    if (!currentModelVisionSupport.value) return;
    
    const items = (event.clipboardData || window.clipboardData).items;
    if (!items) return;
    
    const imageFiles = [];
    for (const item of items) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
            const file = item.getAsFile();
            if (file) {
                const extension = (file.type.split('/')[1] || 'png').toLowerCase().replace('jpeg', 'jpg');
                imageFiles.push(new File([file], `pasted_image_${Date.now()}.${extension}`, { type: file.type }));
            }
        }
    }
    
    if (imageFiles.length > 0) {
        // Only prevent default if we actually found images to process.
        // This allows text paste to work normally via bubbling if no images are present.
        event.preventDefault();
        emit('files-pasted-in-chat', imageFiles);
    }
}
</script>

<template>
    <div class="h-full flex flex-row overflow-hidden relative"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop"
        @paste="handlePaste"
    >
        <div v-if="isDraggingOver" class="absolute inset-0 bg-blue-500/20 border-4 border-dashed border-blue-500 rounded-lg z-30 flex items-center justify-center m-4 pointer-events-none">
            <p class="text-2xl font-bold text-blue-600">Drop files to attach</p>
        </div>
        <div class="flex-1 flex flex-col h-full overflow-hidden relative">
            <div v-if="isLoadingMessages" class="absolute inset-0 bg-white dark:bg-gray-800/80 backdrop-blur-sm z-20 flex flex-col items-center justify-center">
                <IconAnimateSpin class="w-16 h-16 text-blue-500 animate-spin" />
                <p class="mt-4 text-lg font-semibold text-gray-600 dark:text-gray-300">Loading Discussion...</p>
            </div>
            
            <div v-show="!isLoadingMessages" class="flex-1 flex flex-col min-h-0 h-full">
                <MessageArea class="flex-1 overflow-y-auto" />
                <ChatInput />
            </div>
        </div>
        <DataZone v-if="isDataZoneVisible" />
    </div>
</template>
