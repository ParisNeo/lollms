<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import GenericModal from './GenericModal.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
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
const { tasks, isLoadingTasks, activeTasksCount, isClearingTasks } = storeToRefs(tasksStore);

const selectedTask = ref(null);
const logsContainer = ref(null);
const ownerFilter = ref('all');
const searchTerm = ref('');

const filteredTasks = computed(() => {
    let list = [...tasks.value].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    if (searchTerm.value) {
        const term = searchTerm.value.toLowerCase();
        list = list.filter(t => t.name?.toLowerCase().includes(term) || t.id?.toLowerCase().includes(term));
    }
    return list;
});

// Auto-scroll logs
watch(() => selectedTask.value?.logs, () => {
    nextTick(() => {
        if (logsContainer.value) logsContainer.value.scrollTop = logsContainer.value.scrollHeight;
    });
}, { deep: true });

function formatDateTime(iso) { return iso ? new Date(iso).toLocaleString() : '—'; }

async function handleCancelAllTasks() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Terminate All Processes',
        message: `This will stop all ${activeTasksCount.value} active tasks immediately.`,
        confirmText: 'Terminate All'
    });
    if (confirmed.confirmed) await tasksStore.cancelAllTasks();
}

function copyLogs() {
    if (!selectedTask.value?.logs) return;
    const content = selectedTask.value.logs.map(l => `[${l.timestamp}] ${l.message}`).join('\n');
    uiStore.copyToClipboard(content, 'Logs copied');
}
</script>

<template>
    <GenericModal modal-name="tasksManager" title="Command Center" max-width-class="max-w-7xl">
        <template #body>
            <div class="flex h-[70vh] -m-10 overflow-hidden">
                <!-- Sidebar: Task List -->
                <aside class="dashboard-sidebar">
                    <div class="p-6 border-b border-gray-100 dark:border-gray-800 space-y-4">
                        <div class="relative">
                            <IconMagnifyingGlass class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                            <input v-model="searchTerm" type="text" placeholder="Search processes..." class="w-full bg-gray-100 dark:bg-gray-800 border-none rounded-xl py-2.5 pl-10 pr-4 text-xs focus:ring-2 focus:ring-blue-500/20">
                        </div>
                        
                        <div v-if="authStore.isAdmin" class="flex items-center gap-1 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg">
                            <button v-for="opt in ['all', 'me']" :key="opt" @click="ownerFilter = opt" 
                                class="flex-1 py-1 text-[9px] font-black uppercase tracking-widest rounded-md transition-all"
                                :class="ownerFilter === opt ? 'bg-white dark:bg-gray-700 shadow-sm text-blue-600' : 'text-gray-400'">
                                {{ opt }}
                            </button>
                        </div>
                    </div>

                    <div class="flex-1 overflow-y-auto custom-scrollbar">
                        <button v-for="task in filteredTasks" :key="task.id" 
                            @click="selectedTask = task"
                            class="task-item-card group"
                            :class="{ 'selected': selectedTask?.id === task.id }">
                            <div class="flex justify-between items-start mb-2">
                                <span class="text-[11px] font-bold text-gray-800 dark:text-gray-200 truncate pr-4">{{ task.name }}</span>
                                <span class="shrink-0 w-2 h-2 rounded-full mt-1" 
                                    :class="task.status === 'running' ? 'bg-blue-500 animate-pulse' : 'bg-gray-300 dark:bg-gray-600'"></span>
                            </div>
                            <div class="h-1 w-full bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden mb-2">
                                <div class="h-full bg-blue-500 transition-all duration-500" :style="{ width: task.progress + '%' }"></div>
                            </div>
                            <div class="flex items-center justify-between">
                                <span class="text-[9px] font-black uppercase tracking-widest text-gray-400">{{ task.owner_username || 'system' }}</span>
                                <span class="text-[9px] font-mono text-gray-300">{{ task.progress }}%</span>
                            </div>
                        </button>
                    </div>
                </aside>

                <!-- Detail Pane -->
                <main class="dashboard-content">
                    <div v-if="selectedTask" class="flex flex-col h-full p-8">
                        <!-- Header & Info -->
                        <div class="flex items-start justify-between mb-8">
                            <div class="flex-1 min-w-0">
                                <span class="modal-tag">Process Insight</span>
                                <h2 class="text-2xl font-bold font-serif mb-2">{{ selectedTask.name }}</h2>
                                <div class="flex items-center gap-3 text-[10px] text-gray-400 font-mono">
                                    <span>ID: {{ selectedTask.id }}</span>
                                    <button @click="uiStore.copyToClipboard(selectedTask.id)" class="hover:text-blue-500"><IconCopy class="w-3 h-3" /></button>
                                </div>
                            </div>
                            
                            <div class="flex gap-2">
                                <button @click="tasksStore.fetchTasks(ownerFilter)" class="modal-close-btn"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingTasks}" /></button>
                                <button v-if="selectedTask.status === 'running'" @click="tasksStore.cancelTask(selectedTask.id)" class="welcome-btn !py-2 !px-4 !bg-red-500 text-white">Cancel</button>
                            </div>
                        </div>

                        <!-- Stats Grid -->
                        <div class="grid grid-cols-4 gap-6 mb-8 border-y border-gray-50 dark:border-gray-800 py-6">
                            <div v-for="(val, label) in { 'Status': selectedTask.status, 'Created': formatDateTime(selectedTask.created_at), 'Started': formatDateTime(selectedTask.started_at), 'User': selectedTask.owner_username || 'System' }" :key="label">
                                <span class="modal-tag !mb-1">{{ label }}</span>
                                <span class="text-xs font-bold text-gray-700 dark:text-gray-300 capitalize">{{ val }}</span>
                            </div>
                        </div>

                        <!-- Log Terminal -->
                        <div class="terminal-log-window">
                            <div class="terminal-header">
                                <div class="flex items-center gap-2">
                                    <IconTerminal class="w-3 h-3 text-gray-400" />
                                    <span class="text-[9px] font-black uppercase tracking-widest text-gray-400">Stream Output</span>
                                </div>
                                <button @click="copyLogs" class="text-[9px] font-black uppercase tracking-widest text-blue-500 hover:text-blue-600 transition-colors">Copy Logs</button>
                            </div>
                            <div ref="logsContainer" class="terminal-body">
                                <div v-for="(log, i) in selectedTask.logs" :key="i" class="flex gap-4 mb-1.5 group/log">
                                    <span class="text-gray-300 dark:text-gray-700 shrink-0 select-none w-16">{{ new Date(log.timestamp).toLocaleTimeString() }}</span>
                                    <span class="text-gray-600 dark:text-gray-400" :class="{ 'text-red-500': log.level === 'error' }">{{ log.message }}</span>
                                </div>
                                <div v-if="!selectedTask.logs?.length" class="text-gray-400 italic">No activity recorded...</div>
                            </div>
                        </div>
                    </div>

                    <div v-else class="flex-1 flex flex-col items-center justify-center opacity-30">
                        <IconCpuChip class="w-16 h-16 mb-4" />
                        <span class="modal-tag">Select a process to inspect</span>
                    </div>
                </main>
            </div>
        </template>
        <template #footer>
            <div class="flex items-center gap-4 mr-auto">
                <button @click="handleCancelAllTasks" class="utility-link !text-red-500" :disabled="activeTasksCount === 0">Terminate All ({{ activeTasksCount }})</button>
                <button @click="tasksStore.clearCompletedTasks" class="utility-link" :disabled="isClearingTasks">Clear Completed History</button>
            </div>
            <button @click="uiStore.closeModal('tasksManager')" class="welcome-btn !bg-gray-100 dark:!bg-gray-800 text-gray-900 dark:text-white">Done</button>
        </template>
    </GenericModal>
</template>

<style scoped>
@reference "tailwindcss";

/* Scrollbar is now handled globally in main.css via the .custom-scrollbar class used in the template */
</style>