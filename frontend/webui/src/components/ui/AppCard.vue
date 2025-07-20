<script setup>
import { ref, computed } from 'vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconTag from '../../assets/icons/IconTag.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconStar from '../../assets/icons/IconStar.vue';
import IconStarFilled from '../../assets/icons/IconStarFilled.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';

const props = defineProps({
    app: {
        type: Object,
        required: true
    },
    isStarred: {
        type: Boolean,
        default: false
    },
    task: {
        type: Object,
        default: null
    }
});

defineEmits(['install', 'star', 'details', 'help', 'update', 'cancel-install']);

const imageLoadFailed = ref(false);

const isInstalling = computed(() => props.task && props.task.status === 'running');

function handleImageError() {
    imageLoadFailed.value = true;
}

function truncateDescription(text, length = 100) {
    if (!text) return '';
    if (text.length <= length) return text;
    return text.substring(0, length) + '...';
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md transition-shadow hover:shadow-lg flex flex-col h-full relative">
        <button @click="$emit('star')" class="absolute top-3 right-3 p-1 text-gray-400 hover:text-yellow-500 dark:hover:text-yellow-400 transition-colors z-10">
            <IconStarFilled v-if="isStarred" class="w-6 h-6 text-yellow-500 dark:text-yellow-400" />
            <IconStar v-else class="w-6 h-6" />
        </button>
        <div class="p-4 flex-grow">
            <div class="flex items-start gap-4 mb-3">
                <div class="h-16 w-16 rounded-md flex-shrink-0 bg-gray-200 dark:bg-gray-700 flex items-center justify-center overflow-hidden">
                    <img v-if="app.icon && !imageLoadFailed" 
                         :src="app.icon" 
                         @error="handleImageError" 
                         alt="App Icon" 
                         class="h-full w-full object-cover">
                    <svg v-else 
                         class="w-9 h-9 text-gray-500 dark:text-gray-400"
                         xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25A2.25 2.25 0 0 1 13.5 18v-2.25Z" />
                    </svg>
                </div>
                <div class="flex-grow min-w-0">
                    <h3 class="font-bold text-lg text-gray-900 dark:text-white truncate pr-8" :title="app.name">{{ app.name }}</h3>
                    <p class="text-sm text-gray-600 dark:text-gray-400 truncate" :title="`by ${app.author}`">by {{ app.author || 'Unknown' }}</p>
                </div>
            </div>
            
            <p class="text-sm text-gray-500 dark:text-gray-400 leading-relaxed min-h-[60px]">
                {{ truncateDescription(app.description) }}
            </p>
        </div>
        
        <div class="px-4 pb-4 mt-auto">
             <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-3">
                <div class="flex items-center gap-1" v-if="app.version">
                    <IconTag class="w-3.5 h-3.5" />
                    <span>v{{ app.version }}</span>
                </div>
                <div class="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 font-medium">
                    {{ app.category || 'General' }}
                </div>
            </div>

            <div class="flex items-center gap-2 mb-2">
                <button @click="$emit('details')" class="btn btn-secondary flex-1 flex items-center justify-center gap-1.5 text-xs">
                    <IconInfo class="w-4 h-4" /> Details
                </button>
                <button v-if="app.has_readme" @click="$emit('help')" class="btn btn-secondary flex-1 flex items-center justify-center gap-1.5 text-xs">
                    <IconBookOpen class="w-4 h-4" /> Help
                </button>
            </div>
            
             <div v-if="isInstalling" class="space-y-2">
                <div class="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-600">
                    <div class="bg-blue-500 h-2.5 rounded-full" :style="{ width: `${task.progress}%` }"></div>
                </div>
                 <button @click="$emit('cancel-install', task.id)" class="btn btn-danger w-full text-xs">Cancel</button>
            </div>
            <button v-else-if="app.update_available" 
                    @click="$emit('update')"
                    class="btn btn-warning w-full flex items-center justify-center gap-2">
                <IconArrowPath class="w-4 h-4" />
                <span>Update Available</span>
            </button>
            <button v-else-if="!app.is_installed" 
                    @click="$emit('install')"
                    class="btn btn-primary w-full flex items-center justify-center gap-2">
                <IconArrowDownTray class="w-4 h-4" />
                <span>Install</span>
            </button>
            <div v-else
                 class="w-full text-center px-4 py-2 rounded-md bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 font-semibold flex items-center justify-center gap-2">
                 <IconCheckCircle class="w-5 h-5" />
                <span>Installed</span>
            </div>
        </div>
    </div>
</template>