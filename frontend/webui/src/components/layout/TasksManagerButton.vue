<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import IconTasks from '../../assets/icons/IconTasks.vue';

const uiStore = useUiStore();
const tasksStore = useTasksStore();

const { activeTasksCount, mostRecentActiveTask } = storeToRefs(tasksStore);

// Geometric constant for the circular progress svg
const circumference = 2 * Math.PI * 15.9155; 

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
        class="task-indicator-btn"
        :class="mostRecentActiveTask ? 'is-active' : 'is-idle'"
    >
        <!-- Expanded Progress Pill -->
        <template v-if="mostRecentActiveTask">
            <div class="relative w-7 h-7 shrink-0">
                <svg class="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                    <!-- Background path -->
                    <circle
                        class="text-gray-100 dark:text-gray-800"
                        stroke-width="3.5"
                        stroke="currentColor"
                        fill="transparent"
                        r="15.9155"
                        cx="18"
                        cy="18"
                    />
                    <!-- Progress path -->
                    <circle
                        class="text-blue-500 transition-all duration-700 ease-in-out"
                        stroke-width="3.5"
                        :stroke-dasharray="circumference"
                        :stroke-dashoffset="strokeDashoffset"
                        stroke-linecap="round"
                        stroke="currentColor"
                        fill="transparent"
                        r="15.9155"
                        cx="18"
                        cy="18"
                    />
                </svg>
                <!-- Centered Count -->
                <div class="absolute inset-0 flex items-center justify-center text-[10px] font-black text-blue-600 dark:text-blue-400">
                    {{ activeTasksCount }}
                </div>
            </div>
            
            <div class="flex flex-col items-start min-w-0 pr-2 leading-none">
                <span class="text-[10px] font-bold text-gray-800 dark:text-gray-200 truncate max-w-[110px] mb-0.5">
                    {{ mostRecentActiveTask.name }}
                </span>
                <span class="text-[9px] font-black uppercase tracking-[0.1em] text-gray-400 dark:text-gray-500">
                    {{ mostRecentActiveTask.progress }}% In Progress
                </span>
            </div>
        </template>
        
        <!-- Standard Idle Icon -->
        <template v-else>
            <IconTasks class="w-5 h-5" />
            <span v-if="activeTasksCount > 0" class="absolute -top-1 -right-1 flex h-4 w-4">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                <span class="relative inline-flex rounded-full h-4 w-4 bg-blue-500 text-white text-[9px] font-black items-center justify-center border border-white dark:border-gray-800">
                    {{ activeTasksCount }}
                </span>
            </span>
        </template>
    </button>
</template>

<style scoped>
@reference "tailwindcss";

.task-indicator-btn {
    @apply relative flex items-center gap-2.5 transition-all duration-300 ease-in-out cursor-pointer focus:outline-none active:scale-95;
}

/* Idle state matches standard header icons */
.task-indicator-btn.is-idle {
    @apply p-2 rounded-xl text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700/50 hover:text-gray-700 dark:hover:text-gray-200;
}

/* Active state becomes an editorial pill */
.task-indicator-btn.is-active {
    @apply bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-xl px-1.5 py-1 shadow-sm hover:shadow-md hover:border-gray-200 dark:hover:border-gray-700;
    /* Smooth entrance for the pill */
    animation: slideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideIn {
    from { opacity: 0; transform: translateX(10px); }
    to { opacity: 1; transform: translateX(0); }
}
</style>
