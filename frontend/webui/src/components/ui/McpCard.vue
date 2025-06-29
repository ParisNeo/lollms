<script setup>
import { ref } from 'vue';

const props = defineProps({
    mcp: {
        type: Object,
        required: true
    },
    // A flag to determine if the card should show action buttons
    isEditable: {
        type: Boolean,
        default: false
    }
});

const emit = defineEmits(['edit', 'delete']);

// This state will track if an image URL fails to load
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
    <div class="bg-white dark:bg-gray-800/80 shadow rounded-lg p-4 flex flex-col transition hover:shadow-md">
        <!-- Card Body -->
        <div class="flex-grow flex items-center gap-x-4">
            <!-- Icon Display Logic -->
            <div class="h-12 w-12 rounded-md flex-shrink-0 bg-gray-200 dark:bg-gray-700 flex items-center justify-center overflow-hidden">
                <!-- Attempt to show the image if an icon exists and it hasn't failed to load -->
                <img v-if="mcp.icon && !imageLoadFailed" 
                     :src="mcp.icon" 
                     @error="handleImageError" 
                     alt="Server Icon" 
                     class="h-full w-full object-cover">
                <!-- Otherwise, show the placeholder SVG -->
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
                <p class="font-semibold text-gray-900 dark:text-white truncate">{{ mcp.name }}</p>
                <p class="text-xs text-gray-500 dark:text-gray-400 font-mono truncate">{{ mcp.url }}</p>
            </div>
        </div>

        <!-- Card Footer with Actions (only for user-editable cards) -->
        <div v-if="isEditable" class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 flex justify-end items-center gap-x-3 text-sm">
            <button @click="handleEdit" class="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-500 dark:hover:text-blue-400">Edit</button>
            <button @click="handleDelete" class="font-medium text-red-600 hover:text-red-500 dark:text-red-500 dark:hover:text-red-400">Delete</button>
        </div>
    </div>
</template>