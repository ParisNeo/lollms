<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import IconTasks from '../../assets/icons/IconTasks.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const tasksStore = useTasksStore();

const { activeTasksCount, mostRecentActiveTask } = storeToRefs(tasksStore);

function openTasksManager() {
    uiStore.openModal('tasksManager');
}
</script>

<template>
    <button 
        @click="openTasksManager" 
        :title="mostRecentActiveTask ? `${activeTasksCount} active task(s): ${mostRecentActiveTask.name} (${mostRecentActiveTask.progress}%)` : 'Task Manager'"
        class="relative flex items-center gap-2 transition-all duration-300 ease-in-out"
        :class="mostRecentActiveTask 
            ? 'bg-gray-200 dark:bg-gray-700 rounded-full px-2 py-1.5 h-9 text-sm' 
            : 'btn-icon'">
        
        <template v-if="mostRecentActiveTask">
            <IconAnimateSpin class="w-5 h-5 text-blue-500 flex-shrink-0" />
            <div class="w-12 h-1.5 bg-gray-300 dark:bg-gray-600 rounded-full overflow-hidden flex-shrink-0">
                <div class="h-full bg-blue-500 rounded-full" :style="{ width: `${mostRecentActiveTask.progress}%` }"></div>
            </div>
            <div class="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500 text-white text-xs font-bold">
                {{ activeTasksCount }}
            </div>
        </template>
        
        <template v-else>
            <IconTasks class="w-5 h-5" />
            <span v-if="activeTasksCount > 0" class="absolute -top-1 -right-1 flex h-4 w-4">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-4 w-4 bg-blue-500 text-white text-xs items-center justify-center">{{ activeTasksCount }}</span>
            </span>
        </template>
    </button>
</template>