<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const adminStore = useAdminStore();
const { tasks, isLoadingTasks } = storeToRefs(adminStore);

const selectedTask = ref(null);
let pollInterval;

onMounted(() => {
    adminStore.fetchTasks();
    pollInterval = setInterval(adminStore.fetchTasks, 5000); // Poll every 5 seconds
});

onUnmounted(() => {
    clearInterval(pollInterval);
});

const sortedTasks = computed(() => {
    return [...tasks.value].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
});

function formatDateTime(isoString) {
    if (!isoString) return 'N/A';
    return new Date(isoString).toLocaleString();
}

function getStatusInfo(status) {
    switch (status) {
        case 'running':
            return { color: 'blue', text: 'Running' };
        case 'completed':
            return { color: 'green', text: 'Completed' };
        case 'failed':
            return { color: 'red', text: 'Failed' };
        case 'pending':
        default:
            return { color: 'gray', text: 'Pending' };
    }
}
</script>

<template>
    <div class="space-y-6">
        <div class="flex items-center justify-between">
            <div>
                <h2 class="text-xl font-bold">Background Task Manager</h2>
                <p class="text-sm text-gray-500">Monitor and manage background processes like installations.</p>
            </div>
            <div>
                <button @click="adminStore.fetchTasks" class="btn btn-secondary mr-2" :disabled="isLoadingTasks">
                    <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingTasks}" />
                </button>
                 <button @click="adminStore.clearCompletedTasks" class="btn btn-danger">
                    <IconTrash class="w-4 h-4 mr-2" /> Clear Completed
                </button>
            </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <!-- Task List -->
            <div class="md:col-span-1 bg-white dark:bg-gray-800 rounded-lg shadow-sm overflow-hidden">
                <div class="p-4 border-b dark:border-gray-700">
                    <h3 class="font-semibold">Tasks</h3>
                </div>
                <div class="max-h-[60vh] overflow-y-auto">
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
                                            'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300': task.status === 'running',
                                            'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300': task.status === 'completed',
                                            'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300': task.status === 'failed',
                                            'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300': task.status === 'pending'
                                          }">
                                        {{ getStatusInfo(task.status).text }}
                                    </span>
                                </div>
                                <div class="w-full bg-gray-200 rounded-full h-1.5 dark:bg-gray-600">
                                    <div class="h-1.5 rounded-full" 
                                         :class="{'bg-blue-500': task.status==='running', 'bg-green-500': task.status==='completed', 'bg-red-500': task.status==='failed'}"
                                         :style="{ width: task.progress + '%' }"></div>
                                </div>
                            </button>
                        </li>
                    </ul>
                </div>
            </div>

            <!-- Task Details -->
            <div class="md:col-span-2 bg-white dark:bg-gray-800 rounded-lg shadow-sm">
                <div v-if="!selectedTask" class="h-full flex items-center justify-center">
                    <p class="text-gray-500">Select a task to view its details and logs.</p>
                </div>
                <div v-else class="flex flex-col h-full">
                    <div class="p-4 border-b dark:border-gray-700">
                        <h3 class="font-semibold truncate">{{ selectedTask.name }}</h3>
                        <p class="text-xs text-gray-500 dark:text-gray-400">ID: {{ selectedTask.id }}</p>
                    </div>
                    <div class="p-4 space-y-2 text-sm">
                        <p><strong>Status:</strong> {{ getStatusInfo(selectedTask.status).text }}</p>
                        <p><strong>Created:</strong> {{ formatDateTime(selectedTask.created_at) }}</p>
                        <p><strong>Started:</strong> {{ formatDateTime(selectedTask.started_at) }}</p>
                        <p><strong>Completed:</strong> {{ formatDateTime(selectedTask.completed_at) }}</p>
                        <div v-if="selectedTask.error" class="text-red-500 p-2 bg-red-50 dark:bg-red-900/20 rounded">
                            <strong>Error:</strong> {{ selectedTask.error }}
                        </div>
                    </div>
                    <div class="flex-grow p-4 border-t dark:border-gray-700 overflow-hidden flex flex-col">
                         <h4 class="font-semibold mb-2 flex-shrink-0">Logs</h4>
                        <div class="flex-grow bg-gray-100 dark:bg-gray-900 rounded p-2 overflow-y-auto font-mono text-xs">
                           <p v-for="(log, index) in selectedTask.logs" :key="index" :class="{'text-red-500': log.level === 'CRITICAL' || log.level === 'ERROR'}">
                               <span class="text-gray-400 mr-2">{{ new Date(log.timestamp).toLocaleTimeString() }}</span>
                               <span>{{ log.message }}</span>
                           </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>