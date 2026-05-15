<!-- [UPDATE] frontend/webui/src/components/chat/ChatView.vue -->
<script setup>
import { computed, ref } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import { storeToRefs } from 'pinia';
import MessageArea from './MessageArea.vue';
import ChatInput from './ChatInput.vue';
import DataZone from './data_zone/DataZone.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import useEventBus from '../../services/eventBus';

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
        @dragover.prevent="handleDragOver"
        @dragleave="handleDragLeave"
        @drop.stop="handleDrop"
        @paste="handlePaste"
    >
        <!-- Editorial Drop Zone -->
        <div v-if="isDraggingOver" class="absolute inset-0 bg-white/60 dark:bg-gray-900/60 backdrop-blur-md border-2 border-dashed border-blue-500/50 rounded-2xl z-30 flex items-center justify-center m-6 pointer-events-none transition-all duration-500">
            <div class="text-center">
                <span class="modal-tag">Workspace</span>
                <p class="text-3xl font-serif text-gray-900 dark:text-white">Release to attach files</p>
            </div>
        </div>

        <div class="flex-1 flex flex-row h-full overflow-hidden relative">
            <!-- Main Chat Area -->
            <div class="flex-1 flex flex-col h-full overflow-hidden relative border-r border-gray-100 dark:border-gray-800 transition-all duration-300"
                 :class="{ 'border-r-0': isDataZoneVisible }">
                
                <!-- Editorial Loading State -->
                <div v-if="isLoadingMessages" class="absolute inset-0 bg-white dark:bg-gray-900 z-20 flex flex-col items-center justify-center">
                    <div class="relative mb-8">
                        <IconAnimateSpin class="w-12 h-12 text-blue-500 animate-spin" />
                        <div class="absolute inset-0 blur-xl bg-blue-500/20 animate-pulse"></div>
                    </div>
                    <span class="modal-tag">Synchronization</span>
                    <p class="text-xl font-serif text-gray-600 dark:text-gray-400 italic">Preparing discussion...</p>
                </div>
                
                <div v-show="!isLoadingMessages" class="flex-1 flex flex-col min-h-0 h-full relative">
                    <MessageArea class="flex-1 overflow-y-auto" />
                    
                    <!-- New Messages FAB (Editorial Style) -->
                    <Transition
                        enter-active-class="transition-all duration-500 ease-out"
                        enter-from-class="opacity-0 translate-y-4 scale-95"
                        enter-to-class="opacity-100 translate-y-0 scale-100"
                        leave-active-class="transition-all duration-300 ease-in"
                        leave-from-class="opacity-100 translate-y-0"
                        leave-to-class="opacity-0 translate-y-4 scale-95"
                    >
                        <button 
                            v-if="uiStore.showNewMessagesButton" 
                            @click="emit('scroll-chat-to-bottom')" 
                            class="fab-editorial absolute bottom-28 left-1/2 -translate-x-1/2"
                        >
                            <span class="fab-label">Go to bottom</span>
                            <div class="fab-icon-container">
                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
                                    <path fill-rule="evenodd" d="M10 3a.75.75 0 01.75.75v10.638l3.96-4.158a.75.75 0 111.08 1.04l-5.25 5.5a.75.75 0 01-1.08 0l-5.25-5.5a.75.75 0 111.08-1.04l3.96 4.158V3.75A.75.75 0 0110 3z" clip-rule="evenodd" />
                                </svg>
                            </div>
                        </button>
                    </Transition>

                    <ChatInput />
                </div>
            </div>

            <!-- Unified Sidebar (Knowledge & Workspace) -->
            <Transition
                enter-active-class="transition-all duration-300 ease-out"
                enter-from-class="opacity-0 translate-x-full w-0"
                enter-to-class="opacity-100 translate-x-0"
                leave-active-class="transition-all duration-200 ease-in"
                leave-from-class="opacity-100 translate-x-0"
                leave-to-class="opacity-0 translate-x-full w-0"
            >
                <DataZone v-if="isDataZoneVisible" />
            </Transition>
        </div>
    </div>
</template>
