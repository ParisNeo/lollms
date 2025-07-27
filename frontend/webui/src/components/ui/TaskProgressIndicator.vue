<script setup>
import { computed } from 'vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconTicket from '../../assets/icons/IconTicket.vue';

const props = defineProps({
    task: {
        type: Object,
        required: true
    },
    showName: {
        type: Boolean,
        default: false
    }
});

const emit = defineEmits(['cancel', 'view']);

const statusText = computed(() => {
    if (!props.task) return '...';
    if (props.task.name.startsWith('Installing app:')) {
        return `Installing... (${props.task.progress}%)`;
    }
    if (props.task.name.startsWith('Start app:')) {
        return 'Starting...';
    }
    // Add other task name prefixes here for custom text
    return `${props.task.status.charAt(0).toUpperCase() + props.task.status.slice(1)} (${props.task.progress}%)`;
});
</script>

<template>
    <div v-if="task" class="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400 w-full">
        <IconAnimateSpin class="w-4 h-4 flex-shrink-0" />
        <div class="flex-grow">
            <p v-if="showName" class="font-semibold truncate">{{ task.name }}</p>
            <p class="text-xs truncate">{{ statusText }}</p>
        </div>
        <div class="flex-shrink-0 flex items-center gap-1">
            <button @click.stop="$emit('view', task.id)" class="btn btn-secondary btn-sm !p-1" title="View Task Details">
                <IconTicket class="w-4 h-4" />
            </button>
            <button @click.stop="$emit('cancel', task.id)" class="btn btn-warning btn-sm !p-1" title="Cancel Task">
                <IconStopCircle class="w-4 h-4" />
            </button>
        </div>
    </div>
</template>