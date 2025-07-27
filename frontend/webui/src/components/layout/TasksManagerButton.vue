<script setup>
import { computed } from 'vue';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import IconTicket from '../../assets/icons/IconTicket.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const tasksStore = useTasksStore();
const uiStore = useUiStore();

const activeTasksCount = computed(() => tasksStore.activeTasksCount);

function openTasksManager() {
    uiStore.openModal('tasksManager');
}
</script>

<template>
    <button @click="openTasksManager"
        class="relative p-2 rounded-full text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-100 dark:focus:ring-offset-gray-800 focus:ring-blue-500">
        <span class="sr-only">View Tasks</span>
        
        <IconAnimateSpin v-if="activeTasksCount > 0" class="w-6 h-6 text-blue-500" />
        <IconTicket v-else class="w-6 h-6" />
        
        <span v-if="activeTasksCount > 0"
            class="absolute -top-1 -right-1 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-red-100 transform translate-x-1/2 -translate-y-1/2 bg-red-600 rounded-full">
            {{ activeTasksCount }}
        </span>
    </button>
</template>