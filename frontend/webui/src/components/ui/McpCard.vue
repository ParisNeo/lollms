<!-- [UPDATE] frontend/webui/src/components/ui/McpCard.vue -->
<script setup>
import { ref } from 'vue';

const props = defineProps({
    /**
     * The MCP (or App) object.
     * Expected shape: {
     *   name: String,
     *   url: String,
     *   icon: String,
     *   active: Boolean,
     *   type: String, // 'user' or 'system'
     *   owner_username: String // Added for admin view
     * }
     */
    mcp: {
        type: Object,
        required: true
    },
    isEditable: {
        type: Boolean,
        default: false
    }
});

const emit = defineEmits(['edit', 'delete']);

const imageLoadFailed = ref(false);

function handleImageError() {
    imageLoadFailed.value = true;
}

function handleEdit() {
    emit('edit', props.mcp);
}

function handleDelete() {
    emit('delete', props.mcp);
}
</script>

<template>
    <div class="relative bg-white dark:bg-gray-800/80 shadow rounded-lg p-4 flex flex-col transition hover:shadow-md">
        <span 
            v-if="typeof mcp.active === 'boolean'" 
            class="absolute top-3 right-3 h-3 w-3 rounded-full"
            :class="mcp.active ? 'bg-green-500' : 'bg-gray-400 dark:bg-gray-600'"
            :title="mcp.active ? 'Active' : 'Inactive'">
        </span>

        <div class="flex-grow">
            <div class="flex items-center gap-x-4">
                <div class="h-12 w-12 rounded-md flex-shrink-0 bg-gray-200 dark:bg-gray-700 flex items-center justify-center overflow-hidden">
                    <img v-if="mcp.icon && !imageLoadFailed" 
                         :src="mcp.icon" 
                         @error="handleImageError" 
                         alt="Server Icon" 
                         class="h-full w-full object-cover">
                    <svg v-else 
                         class="w-7 h-7 text-gray-500 dark:text-gray-400" 
                         xmlns="http://www.w3.org/2000/svg" 
                         fill="none" 
                         viewBox="0 0 24 24" 
                         stroke-width="1.5" 
                         stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 17.25v-.228a4.5 4.5 0 0 0-.12-1.03l-2.268-9.64a3.375 3.375 0 0 0-3.285-2.602H7.923a3.375 3.375 0 0 0-3.285 2.602l-2.268 9.64a4.5 4.5 0 0 0-.12 1.03v.228m19.5 0a3 3 0 0 1-3 3H5.25a3 3 0 0 1-3-3m19.5 0a3 3 0 0 0-3-3H5.25a3 3 0 0 0-3 3m16.5 0h.008v.008h-.008v-.008Z" />
                    </svg>
                </div>
                
                <div class="truncate">
                    <p class="font-semibold text-gray-900 dark:text-white truncate pr-6" :title="mcp.name">{{ mcp.name }}</p>
                    <p class="text-xs text-gray-500 dark:text-gray-400 font-mono truncate" :title="mcp.url">{{ mcp.url }}</p>
                </div>
            </div>

            <div class="mt-3 flex items-center gap-x-3 flex-wrap">
                <div class="flex items-center gap-x-1 px-2 py-0.5 rounded-full text-xs"
                     :class="mcp.type === 'system' ? 'bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300' : 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300'">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3 h-3">
                        <path d="M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM12.735 14c.618 0 1.093-.561.872-1.139a6.002 6.002 0 0 0-11.215 0c-.22.578.254 1.139.872 1.139h9.47Z" />
                    </svg>
                    <span class="capitalize">{{ mcp.owner_username || mcp.type }}</span>
                </div>
            </div>
        </div>

        <div v-if="isEditable" class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 flex justify-end items-center gap-x-3 text-sm">
            <button @click="handleEdit" class="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-500 dark:hover:text-blue-400">Edit</button>
            <button @click="handleDelete" class="font-medium text-red-600 hover:text-red-500 dark:text-red-500 dark:hover:text-red-400">Delete</button>
        </div>
    </div>
</template>