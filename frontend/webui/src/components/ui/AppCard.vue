<script setup>
import { computed } from 'vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconArrowUpCircle from '../../assets/icons/IconArrowUpCircle.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconStar from '../../assets/icons/IconStar.vue';
import IconStarFilled from '../../assets/icons/IconStarFilled.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue'; // IMPORTED

const props = defineProps({
    app: {
        type: Object,
        required: true,
    },
    task: { // Optional: background task associated with this app (e.g., installation task)
        type: Object,
        default: null,
    },
    isStarred: {
        type: Boolean,
        default: false,
    }
});

const emit = defineEmits(['install', 'update', 'details', 'help', 'star', 'cancel-install']);

const isInstallable = computed(() => !props.app.is_installed && !props.task);
const isInstalled = computed(() => props.app.is_installed);
const isRunning = computed(() => props.app.status === 'running');
const isLoading = computed(() => props.task && (props.task.status === 'running' || props.task.status === 'pending'));

function handleAction(action) {
    if (action === 'install') emit('install', props.app);
    if (action === 'update') emit('update', props.app);
    if (action === 'details') emit('details', props.app);
    if (action === 'help') emit('help', props.app);
    if (action === 'star') emit('star', props.app.name);
    if (action === 'cancel-install') emit('cancel-install', props.task.id);
}
</script>

<template>
    <div class="relative bg-white dark:bg-gray-800 rounded-lg shadow-sm p-4 flex flex-col justify-between">
        <button @click="handleAction('star')" class="absolute top-2 right-2 text-gray-400 hover:text-yellow-500 z-10" :title="isStarred ? 'Unstar App' : 'Star App'">
            <IconStarFilled v-if="isStarred" class="w-5 h-5 text-yellow-400" />
            <IconStar v-else class="w-5 h-5" />
        </button>

        <div class="flex items-center space-x-3 mb-4 flex-grow-0">
            <img v-if="app.icon" :src="app.icon" class="h-14 w-14 rounded-md object-cover flex-shrink-0" alt="App Icon">
            <div class="flex-grow min-w-0">
                <h3 class="font-semibold text-lg text-gray-900 dark:text-white truncate" :title="app.name">{{ app.name }}</h3>
                <p v-if="app.author" class="text-xs text-gray-500 dark:text-gray-400 truncate" :title="app.author">by {{ app.author }}</p>
                <p v-else class="text-xs text-gray-500 dark:text-gray-400">No author</p>
            </div>
        </div>

        <p v-if="app.description" class="text-sm text-gray-600 dark:text-gray-300 mb-4 flex-grow line-clamp-3">{{ app.description }}</p>
        <p v-else class="text-sm text-gray-500 dark:text-gray-400 mb-4 flex-grow italic">No description available.</p>

        <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-4">
            <span v-if="app.category" class="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700">{{ app.category }}</span>
            <span v-if="app.version" class="ml-auto">v{{ app.version }}</span>
        </div>

        <div class="flex flex-col space-y-2 flex-shrink-0">
            <div v-if="isLoading" class="flex items-center text-blue-600 dark:text-blue-400 text-sm">
                <IconAnimateSpin class="w-5 h-5 mr-2" /> <!-- ADDED -->
                <span class="flex-grow truncate">{{ task.name.split(':')[0] }}... ({{ task.progress }}%)</span>
                <button @click="handleAction('cancel-install')" class="btn btn-warning btn-sm ml-2 !p-1" title="Cancel Installation">
                    <IconStopCircle class="w-4 h-4" />
                </button>
            </div>
            <div v-else class="flex items-center space-x-2">
                <button @click="handleAction('details')" class="btn btn-secondary btn-sm flex-1">Details</button>
                <button v-if="app.has_readme" @click="handleAction('help')" class="btn btn-secondary btn-sm flex-1">Help</button>
                <button v-if="isInstallable" @click="handleAction('install')" class="btn btn-primary btn-sm flex-1">Install</button>
                <button v-if="isInstalled && app.update_available" @click="handleAction('update')" class="btn btn-warning btn-sm flex-1">
                    <IconArrowUpCircle class="w-4 h-4 mr-1"/> Update
                </button>
                 <span v-if="isInstalled && !app.update_available" class="px-2 py-1 text-xs font-semibold rounded-full" :class="{
                    'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300': isRunning,
                    'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300': !isRunning,
                }">
                    {{ isRunning ? 'Running' : 'Installed' }}
                </span>
            </div>
        </div>
    </div>
</template>
