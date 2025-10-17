<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import GenericModal from './GenericModal.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconError from '../../assets/icons/IconError.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconUser from '../../assets/icons/IconUser.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';

const tasksStore = useTasksStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const props = computed(() => uiStore.modalData('tasksManager'));
const initialTaskId = computed(() => props.value?.initialTaskId);

const { tasks, isLoadingTasks, activeTasksCount, isClearingTasks } = storeToRefs(tasksStore);

const selectedTask = ref(null);
const logsContainer = ref(null);
const ownerFilter = ref('all');
const searchTerm = ref('');

const sortedTasks = computed(() => {
    return [...tasks.value].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
});

const filteredTasks = computed(() => {
    if (!searchTerm.value) {
        return sortedTasks.value;
    }
    const lowerCaseSearch = searchTerm.value.toLowerCase();
    return sortedTasks.value.filter(task =>
        (task.name && task.name.toLowerCase().includes(lowerCaseSearch)) ||
        (task.id && task.id.toLowerCase().includes(lowerCaseSearch)) ||
        (task.owner_username && task.owner_username.toLowerCase().includes(lowerCaseSearch))
    );
});

watch(() => uiStore.isModalOpen('tasksManager'), (isOpen) => {
    if (isOpen) {
        tasksStore.fetchTasks(ownerFilter.value);
        if (initialTaskId.value && sortedTasks.value.length > 0) {
            selectedTask.value = sortedTasks.value.find(t => t.id === initialTaskId.value) || sortedTasks.value[0];
        } else if (sortedTasks.value.length > 0) {
            selectedTask.value = sortedTasks.value[0];
        } else {
            selectedTask.value = null;
        }
    }
});

watch(ownerFilter, (newFilter) => {
    tasksStore.fetchTasks(newFilter);
});

watch(sortedTasks, (newTasks) => {
    if (selectedTask.value) {
        const updatedTask = newTasks.find(t => t.id === selectedTask.value.id);
        if (updatedTask) {
            if (JSON.stringify(selectedTask.value.logs) !== JSON.stringify(updatedTask.logs)) {
                selectedTask.value = updatedTask;
            } else {
                Object.assign(selectedTask.value, updatedTask);
            }
        } else {
            selectedTask.value = newTasks.length > 0 ? newTasks[0] : null;
        }
    } else if (newTasks.length > 0) {
        selectedTask.value = newTasks[0];
    }
});

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
        case 'completed': return { text: 'Completed', icon: IconCheckCircle, color: 'text-green-500' };
        case 'failed': return { text: 'Failed', icon: IconError, color: 'text-red-500' };
        case 'cancelled': return { text: 'Cancelled', icon: IconXMark, color: 'text-yellow-500' };
        case 'pending':
        default: return { text: 'Pending' };
    }
}

function getLogLevelClass(level) {
    switch (level?.toUpperCase()) {
        case 'ERROR':
        case 'CRITICAL':
            return 'text-red-500 dark:text-red-400';
        case 'WARNING':
            return 'text-yellow-500 dark:text-yellow-400';
        default:
            return 'text-gray-600 dark:text-gray-300';
    }
}

const getLogLevelIcon = (level) => {
    switch (level?.toUpperCase()) {
        case 'ERROR':
        case 'CRITICAL':
            return IconError;
        case 'WARNING':
            return IconInfo; // Replace with a specific warning icon if available
        default:
            return IconInfo;
    }
};

async function handleCancelAllTasks() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Cancel All Active Tasks',
        message: `Are you sure you want to cancel all ${activeTasksCount.value} active background tasks?`,
        confirmText: 'Cancel All'
    });
    if (confirmed.confirmed) {
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
    <GenericModal modal-name="tasksManager" title="Background Tasks" max-width-class="max-w-6xl">
        <template #body>
            <div class="space-y-4">
                <div class="flex items-center justify-between flex-wrap gap-2">
                    <p class="text-sm text-gray-500">Monitor your background processes.</p>
                    <div class="flex items-center gap-2">
                        <button @click="tasksStore.fetchTasks(ownerFilter)" class="btn btn-secondary btn-sm" :disabled="isLoadingTasks">
                            <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingTasks}" />
                        </button>
                        <button @click="handleCancelAllTasks" class="btn btn-warning btn-sm" :disabled="activeTasksCount === 0 || isClearingTasks">
                            <IconXMark class="w-4 h-4 mr-1" /> Cancel All ({{ activeTasksCount }})
                        </button>
                        <button @click="tasksStore.clearCompletedTasks" class="btn btn-danger btn-sm" :disabled="isClearingTasks">
                            <IconAnimateSpin v-if="isClearingTasks" class="w-4 h-4 mr-1" />
                            <IconTrash v-else class="w-4 h-4 mr-1" />
                            Clear Completed
                        </button>
                    </div>
                </div>

                <div v-if="authStore.isAdmin" class="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg border dark:border-gray-600">
                    <div class="flex items-center justify-start space-x-6">
                        <span class="text-sm font-medium">Show tasks for:</span>
                        <div class="flex items-center space-x-4">
                            <label class="flex items-center text-sm"><input type="radio" v-model="ownerFilter" value="all" class="form-radio"><span class="ml-2">All Users</span></label>
                            <label class="flex items-center text-sm"><input type="radio" v-model="ownerFilter" value="me" class="form-radio"><span class="ml-2">My Tasks</span></label>
                            <label class="flex items-center text-sm"><input type="radio" v-model="ownerFilter" value="others" class="form-radio"><span class="ml-2">Other Users</span></label>
                        </div>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-6 h-[60vh]">
                    <div class="md:col-span-1 bg-white dark:bg-gray-800 rounded-lg shadow-sm overflow-hidden flex flex-col">
                        <div class="p-4 border-b dark:border-gray-700 flex-shrink-0 space-y-3">
                            <h3 class="font-semibold">Tasks</h3>
                            <div class="relative">
                                <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3"><IconMagnifyingGlass class="h-4 w-4 text-gray-400" /></div>
                                <input type="text" v-model="searchTerm" placeholder="Search tasks..." class="w-full text-sm pl-9 pr-4 py-1.5 rounded-md border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700">
                            </div>
                        </div>
                        <div class="flex-grow overflow-y-auto">
                            <div v-if="isLoadingTasks && sortedTasks.length === 0" class="p-4 text-center text-gray-500">Loading...</div>
                            <div v-else-if="filteredTasks.length === 0" class="p-4 text-center text-gray-500">No tasks found.</div>
                            <ul v-else class="divide-y dark:divide-gray-700">
                                <li v-for="task in filteredTasks" :key="task.id">
                                    <button @click="selectedTask = task" class="w-full text-left p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors" :class="{'bg-blue-50 dark:bg-blue-900/30': selectedTask && selectedTask.id === task.id}">
                                        <div class="flex justify-between items-center mb-1">
                                            <p class="font-medium truncate text-sm" :title="task.name">{{ task.name }}</p>
                                            <span class="text-xs px-2 py-0.5 rounded-full" :class="{ 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300': task.status === 'running' || task.status === 'pending', 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300': task.status === 'completed', 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300': task.status === 'failed', 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300': task.status === 'cancelled' }">{{ getStatusInfo(task.status).text }}</span>
                                        </div>
                                        <div class="w-full bg-gray-200 rounded-full h-1.5 dark:bg-gray-600 mb-2"><div class="h-1.5 rounded-full" :class="{'bg-blue-500': task.status==='running' || task.status==='pending', 'bg-green-500': task.status==='completed', 'bg-red-500': task.status==='failed', 'bg-yellow-500': task.status==='cancelled'}" :style="{ width: task.progress + '%' }"></div></div>
                                        <div v-if="authStore.isAdmin" class="flex items-center text-xs text-gray-500 dark:text-gray-400"><IconUser class="w-3 h-3 mr-1.5" /><span>{{ task.owner_username || 'System' }}</span></div>
                                    </button>
                                </li>
                            </ul>
                        </div>
                    </div>

                    <div class="md:col-span-2 bg-white dark:bg-gray-800 rounded-lg shadow-sm flex flex-col h-full overflow-hidden">
                        <div v-if="!selectedTask" class="h-full flex items-center justify-center text-center p-4"><p class="text-gray-500">Select a task to view its details and logs.</p></div>
                        <div v-else class="flex flex-col h-full">
                            <div class="p-4 border-b dark:border-gray-700 flex-shrink-0">
                                <h3 class="font-semibold truncate">{{ selectedTask.name }}</h3>
                                <div class="text-xs text-gray-500 dark:text-gray-400 flex items-center">ID: <code class="ml-1 mr-2">{{ selectedTask.id }}</code><button @click="uiStore.copyToClipboard(selectedTask.id)" class="p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600"><IconCopy class="w-3 h-3" /></button></div>
                            </div>
                            <div class="p-4 space-y-3 text-sm flex-shrink-0">
                                <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2">
                                    <div class="flex items-center"><strong>Status:</strong> <component v-if="getStatusInfo(selectedTask.status).icon" :is="getStatusInfo(selectedTask.status).icon" class="w-4 h-4 ml-2" :class="getStatusInfo(selectedTask.status).color" /> <span class="ml-1">{{ getStatusInfo(selectedTask.status).text }}</span></div>
                                    <p><strong>Owner:</strong> {{ selectedTask.owner_username || 'System' }}</p>
                                    <p><strong>Created:</strong> {{ formatDateTime(selectedTask.created_at) }}</p>
                                    <p><strong>Started:</strong> {{ formatDateTime(selectedTask.started_at) }}</p>
                                </div>
                                <div v-if="(selectedTask.status === 'running' || selectedTask.status === 'pending') && (authStore.isAdmin || selectedTask.owner_username === authStore.user.username)" class="flex justify-end pt-2"><button @click="tasksStore.cancelTask(selectedTask.id)" class="btn btn-warning btn-sm"><IconStopCircle class="w-4 h-4 mr-1" />Cancel Task</button></div>
                                <details v-if="selectedTask.error" class="info-details error"><summary>Error Details</summary><pre>{{ selectedTask.error }}</pre></details>
                                <details v-if="selectedTask.result" class="info-details success"><summary>Result Data</summary><pre>{{ JSON.stringify(selectedTask.result, null, 2) }}</pre></details>
                            </div>
                            <div class="flex-grow p-4 border-t dark:border-gray-700 overflow-hidden flex flex-col">
                                <h4 class="font-semibold mb-2 flex-shrink-0 flex items-center justify-between"><span>Logs</span><button @click="copyLogs" class="btn btn-secondary btn-sm"><IconCopy class="w-4 h-4" /></button></h4>
                                <div ref="logsContainer" class="flex-grow bg-gray-100 dark:bg-gray-900 rounded p-2 overflow-y-auto font-mono text-xs">
                                   <div v-for="(log, index) in selectedTask.logs" :key="index" class="log-entry" :class="getLogLevelClass(log.level)">
                                       <span class="log-timestamp">{{ new Date(log.timestamp).toLocaleTimeString() }}</span>
                                       <component :is="getLogLevelIcon(log.level)" class="log-icon" />
                                       <span class="log-message">{{ log.message }}</span>
                                   </div>
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

<style scoped>
.info-details { @apply text-xs; }
.info-details summary { @apply font-semibold cursor-pointer select-none; }
.info-details pre { @apply whitespace-pre-wrap font-mono text-xs mt-1 p-2 bg-gray-100 dark:bg-gray-900 rounded; }
.info-details.error pre { @apply text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-900/20; }
.info-details.success pre { @apply text-green-700 dark:text-green-300 bg-green-50 dark:bg-green-900/20; }
.log-entry { @apply flex items-start gap-2; }
.log-timestamp { @apply text-gray-400 select-none flex-shrink-0; }
.log-icon { @apply w-4 h-4 mt-0.5 flex-shrink-0; }
.log-message { @apply flex-grow; }
</style>