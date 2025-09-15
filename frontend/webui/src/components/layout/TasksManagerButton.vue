<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import IconTasks from '../../assets/icons/IconTasks.vue';

const uiStore = useUiStore();
const tasksStore = useTasksStore();

const { activeTasksCount, mostRecentActiveTask } = storeToRefs(tasksStore);

const circumference = 2 * Math.PI * 15.9155; // 2 * pi * r

const strokeDashoffset = computed(() => {
    if (!mostRecentActiveTask.value) return circumference;
    const progress = Math.max(0, Math.min(100, mostRecentActiveTask.value.progress));
    return circumference - (progress / 100) * circumference;
});


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
            ? 'bg-gray-200 dark:bg-gray-700 rounded-full px-2 py-1 h-9 text-sm' 
            : 'btn-icon'">
        
        <template v-if="mostRecentActiveTask">
            <div class="relative w-6 h-6 flex-shrink-0">
                <svg class="w-full h-full" viewBox="0 0 36 36">
                    <circle
                        class="text-gray-300 dark:text-gray-600"
                        stroke-width="3"
                        stroke="currentColor"
                        fill="transparent"
                        r="15.9155"
                        cx="18"
                        cy="18"
                    />
                    <circle
                        class="text-blue-500 transition-all duration-300 ease-linear"
                        stroke-width="3"
                        :stroke-dasharray="circumference"
                        :stroke-dashoffset="strokeDashoffset"
                        stroke-linecap="round"
                        stroke="currentColor"
                        fill="transparent"
                        r="15.9155"
                        cx="18"
                        cy="18"
                        transform="rotate(-90 18 18)"
                    />
                </svg>
                <div class="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-blue-600 dark:text-blue-400">
                    {{ activeTasksCount }}
                </div>
            </div>
            <div class="flex flex-col items-start min-w-0">
                <span class="text-xs font-semibold text-gray-800 dark:text-gray-200 truncate max-w-[120px]">{{ mostRecentActiveTask.name }}</span>
                <span class="text-xs font-mono text-gray-500 dark:text-gray-400">{{ mostRecentActiveTask.progress }}%</span>
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