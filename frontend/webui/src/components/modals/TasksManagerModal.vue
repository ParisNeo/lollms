<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui'; // Import useUiStore
import GenericModal from '../ui/GenericModal.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconCopy from '../../assets/icons/IconCopy.vue'; // Import IconCopy

const tasksStore = useTasksStore();
const uiStore = useUiStore();

const props = computed(() => uiStore.modalData('tasksManager'));
const initialTaskId = computed(() => props.value?.initialTaskId);

const { tasks, isLoadingTasks, activeTasksCount } = storeToRefs(tasksStore);

const selectedTask = ref(null);
const logsContainer = ref(null);

const sortedTasks = computed(() => {
    // Sorts tasks by creation date, newest first
    return [...tasks.value].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
});

// Select initial task when modal opens
watch(() => uiStore.isModalOpen('tasksManager'), (isOpen) => {
    if (isOpen) {
        if (initialTaskId.value && sortedTasks.value.length > 0) {
            selectedTask.value = sortedTasks.value.find(t => t.id === initialTaskId.value) || sortedTasks.value[0];
        } else if (sortedTasks.value.length > 0) {
            selectedTask.value = sortedTasks.value[0];
        } else {
            selectedTask.value = null;
        }
    }
});

// Keep selected task updated or handle its removal
watch(sortedTasks, (newTasks) => {
    if (selectedTask.value) {
        const updatedTask = newTasks.find(t => t.id === selectedTask.value.id);
        if (updatedTask) {
            selectedTask.value = updatedTask;
        } else {
            selectedTask.value = newTasks.length > 0 ? newTasks[0] : null;
        }
    } else if (newTasks.length > 0) {
        selectedTask.value = newTasks[0];
    }
});

// Auto-scroll logs to the bottom
watch(() => selectedTask.value?.logs, () => {
    nextTick(() => {
        if (logsContainer.value) {
            logsContainer.value.scrollTop = logsContainer.value.scrollHeight;
        }
    });
}, { deep: true });

function formatDateTime(isoString) {
    if (!isoString) return 'N/A';
    return new Date(isoString).toLocaleString();
}

function getStatusInfo(status) {
    switch (status) {
        case 'running': return { text: 'Running' };
        case 'completed': return { text: 'Completed' };
        case 'failed': return { text: 'Failed' };
        case 'cancelled': return { text: 'Cancelled' };
        case 'pending':
        default: return { text: 'Pending' };
    }
}

function getLogLevelClass(level) {
    switch (level.toUpperCase()) {
        case 'ERROR':
        case 'CRITICAL':
            return 'text-red-500 dark:text-red-400';
        case 'WARNING':
            return 'text-yellow-500 dark:text-yellow-400';
        default:
            return 'text-gray-600 dark:text-gray-300';
    }
}

async function handleCancelAllTasks() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Cancel All Active Tasks',
        message: `Are you sure you want to cancel all ${activeTasksCount.value} active background tasks?`,
        confirmText: 'Cancel All'
    });
    if (confirmed) {
        await tasksStore.cancelAllTasks();
    }
}

function copyLogs() {
    if (!selectedTask.value || !selectedTask.value.logs) return;
    const logsContent = selectedTask.value.logs.map(log => {
        const time = new Date(log.timestamp).toLocaleTimeString();
        const level = log.level.toUpperCase();
        return `[${time}] [${level}] ${log.message}`;
    }).join('\n');
    uiStore.copyToClipboard(logsContent, 'Logs copied to clipboard!');
}
</script>

<template>
    <GenericModal modal-name="tasksManager" title="Background Tasks" max-width-class="max-w-4xl">
        <template #body>
            <div class="space-y-4">
                <div class="flex items-center justify-between">
                    <p class="text-sm text-gray-500">Monitor your background processes.</p>
                    <div class="flex items-center gap-2">
                        <button @click="tasksStore.fetchTasks" class="btn btn-secondary btn-sm" :disabled="isLoadingTasks">
                            <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingTasks}" />
                        </button>
                        <button @click="handleCancelAllTasks" class="btn btn-warning btn-sm" :disabled="activeTasksCount === 0">
                            <IconXMark class="w-4 h-4 mr-1" /> Cancel All ({{ activeTasksCount }})
                        </button>
                        <button @click="tasksStore.clearCompletedTasks" class="btn btn-danger btn-sm">
                            <IconTrash class="w-4 h-4 mr-1" /> Clear Completed
                        </button>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-6 h-[60vh]">
                    <!-- Task List -->
                    <div class="md:col-span-1 bg-white dark:bg-gray-800 rounded-lg shadow-sm overflow-hidden flex flex-col">
                        <div class="p-4 border-b dark:border-gray-700 flex-shrink-0">
                            <h3 class="font-semibold">Tasks</h3>
                        </div>
                        <div class="flex-grow overflow-y-auto">
                            <div v-if="isLoadingTasks && sortedTasks.length === 0" class="p-4 text-center text-gray-500">Loading...</div>
                            <div v-else-if="sortedTasks.length === 0" class="p-4 text-center text-gray-500">No tasks found.</div>
                            <ul v-else class="divide-y dark:divide-gray-700">
                                <li v-for="task in sortedTasks" :key="task.id">
                                    <button @click="selectedTask = task" 
                                            class="w-full text-left p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
                                            :class="{'bg-blue-50 dark:bg-blue-900/30': selectedTask && selectedTask.id === task.id}">
                                        <div class="flex justify-between items-center mb-1">
                                            <p class="font-medium truncate" :title="task.name">{{ task.name }}</p>
                                            <span class="text-xs px-2 py-0.5 rounded-full"
                                                  :class="{
                                                    'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300': task.status === 'running' || task.status === 'pending',
                                                    'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300': task.status === 'completed',
                                                    'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300': task.status === 'failed',
                                                    'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300': task.status === 'cancelled',
                                                  }">
                                                {{ getStatusInfo(task.status).text }}
                                            </span>
                                        </div>
                                        <div class="w-full bg-gray-200 rounded-full h-1.5 dark:bg-gray-600">
                                            <div class="h-1.5 rounded-full" 
                                                 :class="{'bg-blue-500': task.status==='running' || task.status==='pending', 'bg-green-500': task.status==='completed', 'bg-red-500': task.status==='failed', 'bg-yellow-500': task.status==='cancelled'}"
                                                 :style="{ width: task.progress + '%' }"></div>
                                        </div>
                                    </button>
                                </li>
                            </ul>
                        </div>
                    </div>

                    <!-- Task Details -->
                    <div class="md:col-span-2 bg-white dark:bg-gray-800 rounded-lg shadow-sm flex flex-col h-full overflow-hidden">
                        <div v-if="!selectedTask" class="h-full flex items-center justify-center">
                            <p class="text-gray-500">Select a task to view its details and logs.</p>
                        </div>
                        <div v-else class="flex flex-col h-full">
                            <div class="p-4 border-b dark:border-gray-700 flex-shrink-0">
                                <h3 class="font-semibold truncate">{{ selectedTask.name }}</h3>
                                <p class="text-xs text-gray-500 dark:text-gray-400">ID: {{ selectedTask.id }}</p>
                            </div>
                            <div class="p-4 space-y-2 text-sm flex-shrink-0">
                                <div class="grid grid-cols-2 gap-2">
                                    <p><strong>Status:</strong> {{ getStatusInfo(selectedTask.status).text }}</p>
                                    <p><strong>Owner:</strong> {{ selectedTask.owner_username || 'System' }}</p>
                                    <p><strong>Created:</strong> {{ formatDateTime(selectedTask.created_at) }}</p>
                                    <p><strong>Started:</strong> {{ formatDateTime(selectedTask.started_at) }}</p>
                                </div>
                                <div v-if="selectedTask.status === 'running' || selectedTask.status === 'pending'" class="flex justify-end">
                                    <button @click="tasksStore.cancelTask(selectedTask.id)" class="btn btn-warning btn-sm">
                                        <IconStopCircle class="w-4 h-4 mr-1" />
                                        Cancel Task
                                    </button>
                                </div>
                                <div v-if="selectedTask.error" class="text-red-500 p-2 bg-red-50 dark:bg-red-900/20 rounded">
                                    <strong>Error:</strong> <pre class="whitespace-pre-wrap font-mono text-xs">{{ selectedTask.error }}</pre>
                                </div>
                                 <div v-if="selectedTask.result" class="text-green-700 dark:text-green-300 p-2 bg-green-50 dark:bg-green-900/20 rounded max-h-48 overflow-y-auto">
                                    <strong>Result:</strong> <pre class="whitespace-pre-wrap font-mono text-xs">{{ JSON.stringify(selectedTask.result, null, 2) }}</pre>
                                </div>
                            </div>
                            <div class="flex-grow p-4 border-t dark:border-gray-700 overflow-hidden flex flex-col">
                                 <h4 class="font-semibold mb-2 flex-shrink-0 flex items-center justify-between">
                                    <span>Logs</span>
                                    <button @click="copyLogs" class="btn btn-secondary btn-sm" title="Copy Logs">
                                        <IconCopy class="w-4 h-4" />
                                    </button>
                                </h4>
                                <div ref="logsContainer" class="flex-grow bg-gray-100 dark:bg-gray-900 rounded p-2 overflow-y-auto font-mono text-xs">
                                   <p v-for="(log, index) in selectedTask.logs" :key="index" :class="getLogLevelClass(log.level)">
                                       <span class="text-gray-400 mr-2 select-none">{{ new Date(log.timestamp).toLocaleTimeString() }}</span>
                                       <span>{{ log.message }}</span>
                                   </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('tasksManager')" class="btn btn-primary">Close</button>
        </template>
    </GenericModal>
</template>