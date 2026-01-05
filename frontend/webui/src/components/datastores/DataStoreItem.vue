<script setup>
import { computed } from 'vue';
import IconShare from '../../assets/icons/IconShare.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconSignOut from '../../assets/icons/IconSignOut.vue';

const props = defineProps({
    store: { type: Object, required: true },
    isSelected: { type: Boolean, default: false },
});

const emit = defineEmits(['select', 'share', 'delete', 'leave']);

const isOwner = computed(() => props.store.permission_level === 'owner');

function handleSelect() {
    emit('select', props.store);
}

function onShare(e) { e.stopPropagation(); emit('share', props.store); }
function onDelete(e) { e.stopPropagation(); emit('delete', props.store); }
function onLeave(e) { e.stopPropagation(); emit('leave', props.store); }
</script>

<template>
    <div 
        @click="handleSelect"
        class="group flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors cursor-pointer relative"
        :class="isSelected ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'"
    >
        <div class="flex items-center min-w-0 flex-grow">
            <span class="truncate">{{ store.name }}</span>
            <span v-if="isOwner" class="ml-2 text-xs px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 flex-shrink-0">Owner</span>
            <span v-else class="ml-2 text-xs px-2 py-0.5 rounded-full flex-shrink-0" :class="{ 
                'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300': store.permission_level === 'revectorize', 
                'bg-purple-100 text-purple-800 dark:bg-purple-900/50 dark:text-purple-300': store.permission_level === 'read_write', 
                'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300': store.permission_level === 'read_query' 
            }">
                {{ store.permission_level.replace('_', ' ') }}
            </span>
        </div>

        <!-- Action Buttons (Visible on Hover) -->
        <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity ml-2">
            <button 
                v-if="isOwner" 
                @click="onShare" 
                class="p-1.5 rounded-md hover:bg-white dark:hover:bg-gray-600 text-gray-500 hover:text-blue-600 transition-colors"
                title="Share"
            >
                <IconShare class="w-4 h-4" />
            </button>
            
            <button 
                v-if="isOwner" 
                @click="onDelete" 
                class="p-1.5 rounded-md hover:bg-white dark:hover:bg-gray-600 text-gray-500 hover:text-red-600 transition-colors"
                title="Delete"
            >
                <IconTrash class="w-4 h-4" />
            </button>

            <button 
                v-if="!isOwner" 
                @click="onLeave" 
                class="p-1.5 rounded-md hover:bg-white dark:hover:bg-gray-600 text-gray-500 hover:text-red-600 transition-colors"
                title="Leave"
            >
                <IconSignOut class="w-4 h-4" />
            </button>
        </div>
    </div>
</template>
