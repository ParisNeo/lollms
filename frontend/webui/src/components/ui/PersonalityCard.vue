<script setup>
import UserAvatar from './UserAvatar.vue';
import IconStar from '../../assets/icons/IconStar.vue';
import IconStarFilled from '../../assets/icons/IconStarFilled.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconSend from '../../assets/icons/IconSend.vue';

const props = defineProps({
    personality: { type: Object, required: true },
    isUserPersonality: { type: Boolean, default: false },
    isActive: { type: Boolean, default: false },
    isSaving: { type: Boolean, default: false },
    isStarred: { type: Boolean, default: false },
    isShared: { type: Boolean, default: false },
    sharedBy: { type: String, default: '' }
});

const emit = defineEmits(['edit', 'delete', 'clone', 'select', 'toggle-star', 'share']);

function handleEdit(event) {
    event.stopPropagation();
    emit(props.isUserPersonality ? 'edit' : 'clone', props.personality);
}

function handleDelete(event) {
    event.stopPropagation();
    emit('delete', props.personality);
}

function handleToggleStar(event) {
    event.stopPropagation();
    emit('toggle-star', props.personality);
}

function handleShare(event) {
    event.stopPropagation();
    emit('share', props.personality);
}

function handleSelect() {
    emit('select', props.personality);
}
</script>

<template>
    <div
        class="relative flex flex-col h-full bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow p-4 transition-all hover:shadow-lg cursor-pointer overflow-hidden"
        :class="{
            'ring-2 ring-offset-2 ring-green-500 dark:ring-offset-gray-900 !border-green-500': isActive,
            'opacity-50 pointer-events-none': isSaving
        }"
        @click="handleSelect"
        :title="isShared ? `Shared by ${sharedBy}` : `Select personality: ${personality.name}`"
    >
        <!-- NEW: Shared Banner with a more specific title -->
        <div v-if="isShared" class="shared-banner" :title="`This personality was sent to you by ${sharedBy}`">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor"><path d="M15 8a3 3 0 10-2.977-2.63l-4.94 2.47a3 3 0 100 4.319l4.94 2.47a3 3 0 10.895-1.789l-4.94-2.47a3.027 3.027 0 000-.74l4.94-2.47C13.456 7.68 14.19 8 15 8z" /></svg>
        </div>

        <button
            @click="handleToggleStar"
            class="absolute top-2 right-2 p-1 rounded-full text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-yellow-500 z-10"
            :title="isStarred ? 'Unstar personality' : 'Star personality'"
        >
            <svg v-if="isStarred" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 hover:text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
            </svg>
        </button>

        <div v-if="isSaving" class="absolute inset-0 bg-gray-500/30 dark:bg-gray-900/50 flex items-center justify-center rounded-lg z-10">
            <svg class="animate-spin h-8 w-8 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
        </div>

        <div class="flex items-start space-x-3 mb-2 pr-8">
            <div class="flex-shrink-0 w-10 h-10 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center overflow-hidden" :title="personality.name">
                <img v-if="personality.icon_base64" :src="personality.icon_base64" alt="icon" class="w-full h-full object-cover" />
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
            </div>
            <div class="flex-grow">
                <h6 class="font-semibold text-gray-800 dark:text-gray-100" :title="personality.name">{{ personality.name }}</h6>
                <p v-if="!isUserPersonality && !isShared" class="text-xs text-gray-500 dark:text-gray-400" :title="`Author: ${personality.author || 'System'}`">by {{ personality.author || 'System' }}</p>
                <p v-if="isShared" class="text-xs text-gray-500 dark:text-gray-400" :title="`Sent by: ${sharedBy}`">from {{ sharedBy }}</p>
                <p v-if="personality.category" class="text-xs text-blue-500 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/50 px-1.5 py-0.5 rounded-full inline-block mt-1" :title="`Category: ${personality.category}`">{{ personality.category }}</p>
            </div>
        </div>

        <p class="text-sm text-gray-600 dark:text-gray-300 mb-4 line-clamp-3" :title="personality.description">
            {{ personality.description || 'No description provided.' }}
        </p>

        <div class="mt-auto flex justify-end items-center space-x-3 border-t dark:border-gray-600 pt-3">
            <button v-if="isUserPersonality" @click="handleShare" class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200" title="Send to User">
                <IconSend class="h-4 w-4" />
            </button>
            <div class="flex-grow"></div>
            <template v-if="isUserPersonality">
                <button @click="handleEdit" class="font-medium text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300" title="Edit this personality">Edit</button>
                <button @click="handleDelete" class="font-medium text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300" title="Delete this personality">Delete</button>
            </template>
            <template v-else>
                <button @click="handleEdit" class="font-medium text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300" title="Make a copy and edit it">Clone & Edit</button>
            </template>
        </div>
    </div>
</template>

<style scoped>
.line-clamp-3 {
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
}
.shared-banner {
  @apply absolute top-0 left-0 flex items-center gap-1 px-2 py-0.5 bg-blue-500 text-white text-[10px] font-bold uppercase tracking-wider rounded-br-lg z-10;
}
</style>