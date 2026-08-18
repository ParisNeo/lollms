<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import GenericModal from './GenericModal.vue';

// Icons
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconTerminal from '../../assets/icons/ui/IconTerminal.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconClock from '../../assets/icons/IconClock.vue';

const tasksStore = useTasksStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const { tasks, isLoadingTasks, activeTasksCount, isClearingTasks } = storeToRefs(tasksStore);

const selectedTaskId = ref(null);
const logsContainer = ref(null);
const ownerFilter = ref('all'); // 'all' | 'me'
const selectedUserFilter = ref('all'); // 'all' | username
const statusFilter = ref('all'); // 'all' | 'active' | 'completed' | 'failed'
const searchTerm = ref('');
const logSearchTerm = ref('');
const autoScroll = ref(true);
const nowTimestamp = ref(Date.now());

// Fetch tasks with the proper scope whenever owner filter changes or modal mounts
watch(ownerFilter, (newScope) => {
    tasksStore.fetchTasks(newScope);
}, { immediate: true });

let tickerInterval = null;

onMounted(() => {
    tickerInterval = setInterval(() => {
        nowTimestamp.value = Date.now();
    }, 1000);
});

onUnmounted(() => {
    if (tickerInterval) clearInterval(tickerInterval);
});

const uniqueTaskOwners = computed(() => {
    const owners = new Set();
    tasks.value.forEach(t => {
        if (t.owner_username) owners.add(t.owner_username);
    });
    return Array.from(owners).sort();
});

const filteredTasks = computed(() => {
    let list = [...tasks.value].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    // 1. Status Filter
    if (statusFilter.value === 'active') {
        list = list.filter(t => ['running', 'pending'].includes(t.status));
    } else if (statusFilter.value === 'completed') {
        list = list.filter(t => t.status === 'completed');
    } else if (statusFilter.value === 'failed') {
        list = list.filter(t => ['failed', 'cancelled'].includes(t.status));
    }

    // 2. Owner Filter
    if (ownerFilter.value === 'me' && authStore.user) {
        list = list.filter(t => t.owner_username === authStore.user.username);
    } else if (authStore.isAdmin && selectedUserFilter.value !== 'all') {
        list = list.filter(t => t.owner_username === selectedUserFilter.value);
    }

    // 3. Search Query
    if (searchTerm.value.trim()) {
        const term = searchTerm.value.toLowerCase().trim();
        list = list.filter(t => 
            (t.name || '').toLowerCase().includes(term) || 
            (t.id || '').toLowerCase().includes(term) ||
            (t.owner_username || '').toLowerCase().includes(term) ||
            (t.description || '').toLowerCase().includes(term)
        );
    }
    return list;
});

const selectedTask = computed(() => {
    return tasks.value.find(t => t.id === selectedTaskId.value) || filteredTasks.value[0] || null;
});

watch(filteredTasks, (newList) => {
    if (!selectedTaskId.value && newList.length > 0) {
        selectedTaskId.value = newList[0].id;
    }
}, { immediate: true });

// Auto-scroll terminal on new logs
watch(() => selectedTask.value?.logs?.length, () => {
    if (autoScroll.value) {
        nextTick(() => {
            if (logsContainer.value) {
                logsContainer.value.scrollTop = logsContainer.value.scrollHeight;
            }
        });
    }
});

const filteredLogs = computed(() => {
    if (!selectedTask.value?.logs) return [];
    if (!logSearchTerm.value.trim()) return selectedTask.value.logs;
    const term = logSearchTerm.value.toLowerCase().trim();
    return selectedTask.value.logs.filter(l => 
        (l.message || '').toLowerCase().includes(term) || 
        (l.level || '').toLowerCase().includes(term)
    );
});

function formatTime(iso) { 
    if (!iso) return '—';
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function calculateDuration(task) {
    if (!task?.started_at) return 'Queued';
    const start = new Date(task.started_at).getTime();
    const end = task.completed_at ? new Date(task.completed_at).getTime() : nowTimestamp.value;
    const diffSeconds = Math.max(0, Math.floor((end - start) / 1000));
    
    if (diffSeconds < 60) return `${diffSeconds}s`;
    const mins = Math.floor(diffSeconds / 60);
    const secs = diffSeconds % 60;
    return `${mins}m ${secs}s`;
}

async function handleCancelTask(task) {
    try {
        await tasksStore.cancelTask(task.id);
        uiStore.addNotification(`Task '${task.name}' cancelled.`, 'info');
    } catch (e) {
        uiStore.addNotification('Failed to cancel task.', 'error');
    }
}

async function handleCancelAllTasks() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Terminate All Active Tasks',
        message: `Are you sure you want to stop all ${activeTasksCount.value} active background processes immediately?`,
        confirmText: 'Terminate All',
        danger: true
    });
    if (confirmed.confirmed) {
        await tasksStore.cancelAllTasks();
    }
}

function copyTrace() {
    if (!selectedTask.value?.logs) return;
    const content = selectedTask.value.logs
        .map(l => `[${l.timestamp ? new Date(l.timestamp).toISOString() : 'LOG'}] [${(l.level || 'INFO').toUpperCase()}] ${l.message}`)
        .join('\n');
    uiStore.copyToClipboard(content, 'Trace logs copied to clipboard.');
}

function downloadLogs() {
    if (!selectedTask.value?.logs) return;
    const content = selectedTask.value.logs
        .map(l => `[${l.timestamp ? new Date(l.timestamp).toISOString() : 'LOG'}] [${(l.level || 'INFO').toUpperCase()}] ${l.message}`)
        .join('\n');
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `task_${selectedTask.value.id}_logs.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    uiStore.addNotification('Log file downloaded.', 'success', 1500);
}
</script>

<template>
    <GenericModal modal-name="tasksManager" title="Task Command Center" max-width-class="max-w-[96vw] xl:max-w-7xl">
        <template #body>
            <div class="h-[74vh] min-h-[550px] flex overflow-hidden rounded-2xl border border-gray-200/80 dark:border-gray-800 bg-white dark:bg-gray-950 shadow-2xl">

                <!-- ── LEFT NAVIGATION RAIL ── -->
                <aside class="w-72 sm:w-80 shrink-0 border-r border-gray-100 dark:border-gray-800/80 flex flex-col bg-gray-50/50 dark:bg-gray-900/40">
                    
                    <!-- Search & Filter Controls -->
                    <div class="p-3.5 space-y-3 border-b dark:border-gray-800">
                        <div class="relative">
                            <IconMagnifyingGlass class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                            <input 
                                v-model="searchTerm" 
                                type="text" 
                                placeholder="Filter tasks by name or ID..." 
                                class="input-field !py-1.5 !pl-8 !text-xs w-full bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-700 shadow-sm"
                            >
                            <button v-if="searchTerm" @click="searchTerm = ''" class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-red-500">
                                <IconXMark class="w-3.5 h-3.5" />
                            </button>
                        </div>

                        <!-- Status Filter Pills -->
                        <div class="flex items-center gap-1 bg-gray-200/60 dark:bg-gray-800/80 p-1 rounded-xl">
                            <button 
                                v-for="sf in [
                                    { id: 'all', label: 'All' },
                                    { id: 'active', label: `Active (${activeTasksCount})` },
                                    { id: 'completed', label: 'Done' },
                                    { id: 'failed', label: 'Failed' }
                                ]" 
                                :key="sf.id"
                                @click="statusFilter = sf.id"
                                class="flex-1 py-1 text-[9px] font-black uppercase tracking-wider rounded-lg transition-all"
                                :class="statusFilter === sf.id ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                            >
                                {{ sf.label }}
                            </button>
                        </div>

                        <!-- Admin Scope Switch & User Filter -->
                        <div v-if="authStore.isAdmin" class="space-y-2 px-1 pt-1 border-t dark:border-gray-800">
                            <div class="flex items-center justify-between text-[10px] font-bold text-gray-400">
                                <span class="uppercase tracking-widest text-[9px]">Scope</span>
                                <div class="flex gap-2">
                                    <button @click="ownerFilter = 'all'; selectedUserFilter = 'all'" :class="ownerFilter === 'all' && selectedUserFilter === 'all' ? 'text-blue-600 dark:text-blue-400 font-bold underline' : 'hover:text-gray-600'">All Users</button>
                                    <span>•</span>
                                    <button @click="ownerFilter = 'me'" :class="ownerFilter === 'me' ? 'text-blue-600 dark:text-blue-400 font-bold underline' : 'hover:text-gray-600'">Mine Only</button>
                                </div>
                            </div>

                            <!-- Specific User Filter Dropdown -->
                            <div v-if="ownerFilter === 'all' && uniqueTaskOwners.length > 1" class="flex items-center gap-2">
                                <span class="text-[9px] font-bold text-gray-400 uppercase tracking-tight shrink-0">User:</span>
                                <select 
                                    v-model="selectedUserFilter" 
                                    class="input-field !py-1 !text-[10px] w-full bg-white dark:bg-gray-900 border dark:border-gray-700"
                                >
                                    <option value="all">All Active Users ({{ uniqueTaskOwners.length }})</option>
                                    <option v-for="username in uniqueTaskOwners" :key="username" :value="username">
                                        👤 {{ username }}
                                    </option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <!-- Tasks List Stream -->
                    <div class="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1.5">
                        <div v-if="filteredTasks.length === 0" class="h-64 flex flex-col items-center justify-center text-gray-400 opacity-60">
                            <IconCpuChip class="w-10 h-10 mb-2 stroke-1" />
                            <p class="text-xs font-bold uppercase tracking-widest">No matching tasks</p>
                        </div>

                        <div 
                            v-for="task in filteredTasks" 
                            :key="task.id" 
                            @click="selectedTaskId = task.id"
                            class="task-card group"
                            :class="selectedTask?.id === task.id ? 'active' : ''"
                        >
                            <!-- Header Row -->
                            <div class="flex items-start justify-between gap-2 mb-1.5">
                                <span class="text-xs font-bold text-gray-800 dark:text-gray-100 truncate flex-1" :title="task.name">
                                    {{ task.name }}
                                </span>
                                
                                <!-- Status Badge -->
                                <span 
                                    class="status-pill shrink-0"
                                    :class="{
                                        'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300': task.status === 'running',
                                        'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300': task.status === 'pending',
                                        'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300': task.status === 'completed',
                                        'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300': ['failed', 'cancelled'].includes(task.status)
                                    }"
                                >
                                    <IconAnimateSpin v-if="task.status === 'running'" class="w-2.5 h-2.5 animate-spin" />
                                    {{ task.status }}
                                </span>
                            </div>

                            <!-- Progress Track -->
                            <div class="h-1.5 w-full bg-gray-200/80 dark:bg-gray-800 rounded-full overflow-hidden mb-2">
                                <div 
                                    class="h-full transition-all duration-500 rounded-full"
                                    :class="task.status === 'failed' ? 'bg-rose-500' : (task.status === 'completed' ? 'bg-emerald-500' : 'bg-blue-600')"
                                    :style="{ width: `${task.progress || 0}%` }"
                                ></div>
                            </div>

                            <!-- Meta Footer -->
                            <div class="flex items-center justify-between text-[9px] font-mono text-gray-400 dark:text-gray-500">
                                <span 
                                    class="truncate max-w-[120px] font-bold"
                                    :class="authStore.isAdmin && task.owner_username !== authStore.user?.username ? 'text-purple-600 dark:text-purple-400' : ''"
                                >
                                    👤 {{ task.owner_username || 'System' }}
                                </span>
                                <div class="flex items-center gap-1.5">
                                    <span class="font-bold text-gray-600 dark:text-gray-400">{{ task.progress }}%</span>
                                    <span>•</span>
                                    <span>{{ calculateDuration(task) }}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Left Rail Quick Clear -->
                    <div class="p-3 border-t dark:border-gray-800 bg-gray-100/50 dark:bg-gray-900/60 flex items-center justify-between">
                        <button @click="tasksStore.fetchTasks(ownerFilter)" class="text-[10px] font-bold text-gray-500 hover:text-blue-500 flex items-center gap-1 transition-colors">
                            <IconRefresh class="w-3 h-3" :class="{'animate-spin': isLoadingTasks}" />
                            <span>Sync</span>
                        </button>
                        <button 
                            @click="tasksStore.clearCompletedTasks" 
                            class="text-[10px] font-bold text-gray-500 hover:text-red-500 transition-colors"
                            :disabled="isClearingTasks"
                        >
                            Purge Inactive
                        </button>
                    </div>
                </aside>

                <!-- ── RIGHT INSPECTION PANEL ── -->
                <main class="flex-1 flex flex-col min-w-0 bg-white dark:bg-gray-950 overflow-hidden">
                    <div v-if="selectedTask" class="flex flex-col h-full overflow-hidden">
                        
                        <!-- 1. Task Header / Overview Strip -->
                        <div class="p-5 border-b dark:border-gray-800 bg-gray-50/40 dark:bg-gray-900/20 shrink-0 space-y-4">
                            <div class="flex items-start justify-between gap-4">
                                <div class="space-y-1 min-w-0 flex-1">
                                    <div class="flex items-center gap-2">
                                        <span class="text-[9px] font-black uppercase tracking-widest text-primary">Process Telemetry</span>
                                        <span 
                                            class="status-pill text-[10px]"
                                            :class="{
                                                'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300': selectedTask.status === 'running',
                                                'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300': selectedTask.status === 'pending',
                                                'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300': selectedTask.status === 'completed',
                                                'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300': ['failed', 'cancelled'].includes(selectedTask.status)
                                            }"
                                        >
                                            {{ selectedTask.status.toUpperCase() }}
                                        </span>
                                    </div>
                                    <h3 class="text-base font-bold text-gray-900 dark:text-gray-100 truncate" :title="selectedTask.name">
                                        {{ selectedTask.name }}
                                    </h3>
                                    <p v-if="selectedTask.description" class="text-xs text-gray-500 dark:text-gray-400 italic">
                                        "{{ selectedTask.description }}"
                                    </p>
                                </div>

                                <!-- Action Buttons -->
                                <div class="flex items-center gap-2 shrink-0">
                                    <button 
                                        v-if="['running', 'pending'].includes(selectedTask.status)" 
                                        @click="handleCancelTask(selectedTask)" 
                                        class="btn btn-danger btn-sm flex items-center gap-1.5 shadow-sm"
                                    >
                                        <IconStopCircle class="w-4 h-4" />
                                        <span>Cancel Task</span>
                                    </button>

                                    <button @click="copyTrace" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Copy Raw Logs">
                                        <IconCopy class="w-3.5 h-3.5" />
                                        <span class="hidden sm:inline">Copy Log</span>
                                    </button>

                                    <button @click="downloadLogs" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Download Log File">
                                        <IconArrowDownTray class="w-3.5 h-3.5" />
                                    </button>
                                </div>
                            </div>

                            <!-- Metrics Grid -->
                            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                                <div class="metric-box">
                                    <span class="metric-label">Execution Time</span>
                                    <span class="metric-value font-mono text-blue-600 dark:text-blue-400">{{ calculateDuration(selectedTask) }}</span>
                                </div>
                                <div class="metric-box">
                                    <span class="metric-label">Submitted</span>
                                    <span class="metric-value font-mono">{{ formatTime(selectedTask.created_at) }}</span>
                                </div>
                                <div class="metric-box">
                                    <span class="metric-label">Started</span>
                                    <span class="metric-value font-mono">{{ formatTime(selectedTask.started_at) }}</span>
                                </div>
                                <div class="metric-box">
                                    <span class="metric-label">Owner</span>
                                    <span class="metric-value font-bold truncate">{{ selectedTask.owner_username || 'System' }}</span>
                                </div>
                            </div>
                        </div>

                        <!-- 2. Execution Insights & Error Output (If failed) -->
                        <div v-if="selectedTask.error" class="p-4 bg-rose-50 dark:bg-rose-950/20 border-b border-rose-200 dark:border-rose-900/40 text-rose-800 dark:text-rose-200 text-xs shrink-0 flex items-start gap-3">
                            <IconXMark class="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                            <div class="min-w-0 space-y-1">
                                <span class="font-bold uppercase tracking-wider text-[9px] block text-rose-600 dark:text-rose-400">Process Error Encountered</span>
                                <p class="font-mono leading-relaxed">{{ selectedTask.error }}</p>
                            </div>
                        </div>

                        <!-- 3. Terminal Log Output Window -->
                        <div class="flex-1 flex flex-col min-h-0 bg-gray-950 text-gray-200 relative">
                            <!-- Terminal Sub-header Bar -->
                            <div class="px-4 py-2 bg-gray-900/90 border-b border-gray-800/80 flex items-center justify-between shrink-0">
                                <div class="flex items-center gap-3">
                                    <div class="flex gap-1.5">
                                        <div class="w-2.5 h-2.5 rounded-full bg-rose-500/80"></div>
                                        <div class="w-2.5 h-2.5 rounded-full bg-amber-500/80"></div>
                                        <div class="w-2.5 h-2.5 rounded-full bg-emerald-500/80"></div>
                                    </div>
                                    <span class="text-[10px] font-mono font-bold text-gray-400 uppercase tracking-widest flex items-center gap-1.5">
                                        <IconTerminal class="w-3.5 h-3.5 text-gray-500" />
                                        stdout trace
                                    </span>
                                </div>

                                <div class="flex items-center gap-3">
                                    <!-- Search Logs Inline -->
                                    <input 
                                        v-model="logSearchTerm" 
                                        type="text" 
                                        placeholder="Filter logs..." 
                                        class="bg-gray-800 text-gray-200 text-[10px] px-2.5 py-0.5 rounded-lg border border-gray-700 focus:outline-none focus:border-blue-500 w-32 sm:w-44"
                                    >

                                    <!-- Auto-Scroll Switch -->
                                    <label class="flex items-center gap-1.5 cursor-pointer select-none text-[10px] font-mono text-gray-400">
                                        <input type="checkbox" v-model="autoScroll" class="rounded bg-gray-800 border-gray-700 text-blue-600 focus:ring-0 w-3 h-3">
                                        <span>Stick to Bottom</span>
                                    </label>
                                </div>
                            </div>

                            <!-- Terminal Content Area -->
                            <div 
                                ref="logsContainer" 
                                class="flex-1 overflow-y-auto p-4 font-mono text-[11px] leading-relaxed custom-scrollbar space-y-1.5 selection:bg-blue-600 selection:text-white"
                            >
                                <div 
                                    v-for="(log, idx) in filteredLogs" 
                                    :key="idx" 
                                    class="flex gap-3 hover:bg-white/5 px-1 py-0.5 rounded transition-colors"
                                >
                                    <!-- Timestamp Index -->
                                    <span class="text-gray-600 select-none shrink-0 w-20">
                                        {{ log.timestamp ? new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : `00:${idx.toString().padStart(2, '0')}` }}
                                    </span>

                                    <!-- Log Message -->
                                    <span 
                                        class="min-w-0 break-words flex-1"
                                        :class="{
                                            'text-rose-400 font-bold': log.level === 'ERROR' || log.level === 'CRITICAL',
                                            'text-amber-400': log.level === 'WARNING',
                                            'text-emerald-400': log.level === 'SUCCESS',
                                            'text-gray-300': !log.level || log.level === 'INFO'
                                        }"
                                    >
                                        {{ log.message }}
                                    </span>
                                </div>

                                <div v-if="!selectedTask.logs?.length" class="h-full flex items-center justify-center text-gray-600 italic">
                                    No output emitted yet. Process in progress...
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Empty selection fallback -->
                    <div v-else class="h-full flex flex-col items-center justify-center text-gray-400 opacity-60">
                        <IconCpuChip class="w-16 h-16 mb-3 stroke-1" />
                        <p class="text-sm font-bold uppercase tracking-widest">Select a task to inspect</p>
                    </div>
                </main>
            </div>
        </template>
        
        <template #footer>
            <div class="flex items-center justify-between w-full px-2">
                <div class="flex items-center gap-4">
                    <button 
                        @click="handleCancelAllTasks" 
                        class="btn btn-danger-outline btn-sm"
                        :disabled="activeTasksCount === 0"
                    >
                        <IconStopCircle class="w-4 h-4 mr-1.5" />
                        Terminate All Active ({{ activeTasksCount }})
                    </button>
                    <button 
                        @click="tasksStore.clearCompletedTasks" 
                        class="text-xs font-bold text-gray-500 hover:text-red-500 transition-colors"
                        :disabled="isClearingTasks"
                    >
                        Clear Completed History
                    </button>
                </div>
                
                <button @click="uiStore.closeModal('tasksManager')" class="btn btn-primary px-10">
                    Done
                </button>
            </div>
        </template>
    </GenericModal>
</template>

<style scoped>
@reference "tailwindcss";

.task-card {
    @apply p-3 rounded-xl border transition-all duration-200 cursor-pointer bg-white dark:bg-gray-900 border-gray-200/80 dark:border-gray-800 shadow-sm hover:border-blue-400/60 dark:hover:border-blue-500/60;
}
.task-card.active {
    @apply border-blue-500 dark:border-blue-500 ring-2 ring-blue-500/20 bg-blue-50/30 dark:bg-blue-950/20 shadow-md;
}
.status-pill {
    @apply px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider inline-flex items-center gap-1;
}
.metric-box {
    @apply p-2.5 rounded-xl bg-white dark:bg-gray-900 border border-gray-200/70 dark:border-gray-800 shadow-sm flex flex-col min-w-0;
}
.metric-label {
    @apply text-[9px] font-black uppercase text-gray-400 tracking-widest leading-none mb-1;
}
.metric-value {
    @apply text-xs font-semibold text-gray-800 dark:text-gray-200 truncate;
}
.custom-scrollbar::-webkit-scrollbar { width: 5px; height: 5px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>