<script setup>
import { computed } from 'vue';
import IconStar from '../../assets/icons/IconStar.vue';
import IconStarFilled from '../../assets/icons/IconStarFilled.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconArrowUpCircle from '../../assets/icons/IconArrowUpCircle.vue';
import TaskProgressIndicator from './TaskProgressIndicator.vue'; // NEW IMPORT

const props = defineProps({
    app: { type: Object, required: true },
    task: { type: Object, default: null }, // NEW PROP
    isStarred: { type: Boolean, default: false }
});

const emit = defineEmits(['install', 'update', 'details', 'help', 'star', 'view-task', 'cancel-install']); // UPDATED EMITS

const canInstall = computed(() => !props.app.is_installed && !props.task);

function handleAction(action) {
    emit(action, props.app);
}

function handleViewTask(taskId) {
    emit('view-task', taskId);
}

function handleCancelInstall(taskId) {
    emit('cancel-install', taskId);
}
</script>

<template>
    <div class="relative flex flex-col h-full bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow transition-all hover:shadow-lg">
        <div class="flex-grow p-4">
            <button @click.stop="emit('star')" class="absolute top-2 right-2 p-1 rounded-full text-gray-400 hover:text-yellow-400 z-10">
                <IconStarFilled v-if="isStarred" class="w-5 h-5 text-yellow-400" />
                <IconStar v-else class="w-5 h-5" />
            </button>
            <div @click="handleAction('details')" class="cursor-pointer">
                <div class="flex items-start gap-4 mb-3">
                    <img v-if="app.icon" :src="app.icon" class="h-12 w-12 rounded-md flex-shrink-0 object-cover" alt="App Icon">
                    <div class="flex-grow min-w-0">
                        <h3 class="font-semibold text-gray-900 dark:text-white truncate" :title="app.name">{{ app.name }}</h3>
                        <p class="text-xs text-gray-500 dark:text-gray-400 truncate">by {{ app.author || 'Unknown' }}</p>
                    </div>
                </div>
                <p class="text-sm text-gray-600 dark:text-gray-300 line-clamp-2 h-10">{{ app.description }}</p>
            </div>
        </div>
        <div class="px-4 py-3 bg-gray-50 dark:bg-gray-700/50 border-t dark:border-gray-700 rounded-b-lg">
             <!-- Task Progress Indicator -->
            <TaskProgressIndicator 
                v-if="task" 
                :task="task" 
                @view="handleViewTask" 
                @cancel="handleCancelInstall" 
            />
            <!-- Action Buttons -->
            <div v-else class="flex items-center justify-between">
                <div class="flex items-center gap-1">
                     <button @click="handleAction('details')" class="btn btn-secondary btn-sm !p-1.5" title="More Info">
                        <IconInfo class="w-4 h-4" />
                    </button>
                    <button v-if="app.has_readme" @click="handleAction('help')" class="btn btn-secondary btn-sm !p-1.5" title="View README">
                        <IconBookOpen class="w-4 h-4" />
                    </button>
                </div>
                <div class="flex items-center gap-2">
                    <span v-if="app.is_installed" class="flex items-center text-sm text-green-600 dark:text-green-400">
                        <IconCheckCircle class="w-5 h-5 mr-1" />
                        Installed
                    </span>
                    <button v-if="app.update_available" @click="handleAction('update')" class="btn btn-warning btn-sm">
                        <IconArrowUpCircle class="w-4 h-4 mr-1"/>
                        Update
                    </button>
                    <button v-if="canInstall" @click="handleAction('install')" class="btn btn-primary btn-sm">Install</button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.line-clamp-2 {
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
}
</style>