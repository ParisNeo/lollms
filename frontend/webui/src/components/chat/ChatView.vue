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
    if (event.dataTransfer.types.includes('Files') && currentModelVisionSupport.value) {
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
    if (!currentModelVisionSupport.value) return;

    const files = Array.from(event.dataTransfer.files).filter(file => file.type.startsWith('image/'));
    if (files.length > 0) {
        emit('files-dropped-in-chat', files);
    }
}
</script>

<template>
    <div class="h-full flex flex-row overflow-hidden relative"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop"
    >
        <div v-if="isDraggingOver" class="absolute inset-0 bg-blue-500/20 border-4 border-dashed border-blue-500 rounded-lg z-30 flex items-center justify-center m-4 pointer-events-none">
            <p class="text-2xl font-bold text-blue-600">Drop images to attach</p>
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