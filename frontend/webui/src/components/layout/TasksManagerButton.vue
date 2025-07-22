<script setup>
import { computed } from 'vue';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import IconTicket from '../../assets/icons/IconTasks.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const tasksStore = useTasksStore();
const uiStore = useUiStore();

const activeCount = computed(() => tasksStore.activeTasksCount);

function openTasksModal() {
    uiStore.openModal('tasksManager');
}
</script>

<template>
    <button @click="openTasksModal" class="relative btn btn-secondary !p-2" title="View background tasks">
        <IconTicket v-if="activeCount === 0" class="w-5 h-5" />
        <IconAnimateSpin v-else class="w-5 h-5 text-blue-500" />
        <span v-if="activeCount > 0" class="absolute -top-1 -right-1 flex items-center justify-center h-4 w-4 rounded-full bg-blue-500 text-white text-[10px] font-bold">
            {{ activeCount }}
        </span>
    </button>
</template>