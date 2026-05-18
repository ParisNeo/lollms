<script setup>
import { ref, computed, watch, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import GenericModal from './GenericModal.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconTerminal from '../../assets/icons/ui/IconTerminal.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconMagnifyingGlass from '../../assets/icons/IconMagnifyingGlass.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';

const tasksStore = useTasksStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

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
    if (ownerFilter.value === 'me' && authStore.user) {
        list = list.filter(t => t.owner_username === authStore.user.username);
    }
    return list;
});

// Set first task as selected by default if none selected
watch(filteredTasks, (newList) => {
    if (!selectedTask.value && newList.length > 0) {
        selectedTask.value = newList[0];
    }
}, { immediate: true });

// Auto-scroll logs
watch(() => selectedTask.value?.logs, () => {
    nextTick(() => {
        if (logsContainer.value) logsContainer.value.scrollTop = logsContainer.value.scrollHeight;
    });
}, { deep: true });

function formatDateTime(iso) { 
    if (!iso) return '—';
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

async function handleCancelAllTasks() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Terminate All Processes',
        message: `This will stop all ${activeTasksCount.value} active tasks immediately.`,
        confirmText: 'Terminate All',
        danger: true
    });
    if (confirmed.confirmed) await tasksStore.cancelAllTasks();
}

function copyLogs() {
    if (!selectedTask.value?.logs) return;
    const content = selectedTask.value.logs.map(l => `[${l.timestamp}] ${l.message}`).join('\n');
    uiStore.copyToClipboard(content, 'Logs copied to clipboard');
}
</script>

<template>
    <GenericModal modal-name="tasksManager" title="Command Center" max-width-class="max-w-[95vw]">
        <template #body>
            <!-- ── Centered Main Container (Crucial Fix: Removed negative margins) ── -->
            <div class="max-w-[1500px] mx-auto min-h-[700px] h-[80vh] flex overflow-hidden bg-white dark:bg-gray-950 rounded-2xl border border-gray-100 dark:border-gray-800 shadow-2xl">
                
                <!-- ── LEFT: Process Navigation Rail ── -->
                <aside class="w-72 shrink-0 border-r border-gray-100 dark:border-gray-800 flex flex-col bg-gray-50/40 dark:bg-gray-900/40">
                    <!-- Sidebar Search & Filter -->
                    <div class="p-5 space-y-4 border-b dark:border-gray-800">
                        <div class="relative">
                            <IconMagnifyingGlass class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                            <input 
                                v-model="searchTerm" 
                                type="text" 
                                placeholder="Search tasks..." 
                                class="input-field-sm pl-9 !bg-white dark:!bg-gray-950 border-gray-200 dark:border-gray-800 h-9"
                            >
                        </div>
                        <div v-if="authStore.isAdmin" class="flex p-0.5 bg-gray-200/50 dark:bg-gray-800 rounded-lg">
                            <button v-for="opt in ['all', 'me']" :key="opt" @click="ownerFilter = opt"
                                class="flex-1 py-1 text-[9px] font-black uppercase tracking-widest rounded-md transition-all"
                                :class="ownerFilter === opt ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500'">
                                {{ opt }}
                            </button>
                        </div>
                    </div>

                    <!-- Task List -->
                    <div class="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
                        <button 
                            v-for="task in filteredTasks" 
                            :key="task.id" 
                            @click="selectedTask = task"
                            class="task-sidebar-item"
                            :class="{ 'is-selected': selectedTask?.id === task.id }"
                        >
                            <div class="flex justify-between items-start mb-2">
                                <span class="text-[11px] font-bold text-gray-700 dark:text-gray-300 truncate pr-3">{{ task.name }}</span>
                                <div class="w-1.5 h-1.5 rounded-full shrink-0 mt-1" 
                                    :class="task.status === 'running' ? 'bg-blue-500 animate-pulse' : 'bg-gray-300 dark:bg-gray-600'"></div>
                            </div>
                            <div class="h-0.5 w-full bg-gray-200 dark:bg-gray-800 rounded-full overflow-hidden mb-1.5">
                                <div class="h-full bg-blue-500 transition-all duration-500" :style="{ width: task.progress + '%' }"></div>
                            </div>
                            <div class="flex justify-between items-center text-[8px] font-black uppercase text-gray-400 tracking-tighter">
                                <span>{{ task.owner_username || 'system' }}</span>
                                <span class="font-mono">{{ task.progress }}%</span>
                            </div>
                        </button>
                    </div>
                </aside>

                <!-- ── RIGHT: Task Insight Dashboard ── -->
                <main class="flex-1 flex flex-col min-w-0 bg-white dark:bg-gray-950">
                    <Transition mode="out-in" name="fade-slide">
                        <div v-if="selectedTask" :key="selectedTask.id" class="flex flex-col h-full overflow-hidden">
                            
                            <!-- 1. HUD Layer (Fixed Top) -->
                            <section class="p-8 pb-6 border-b border-gray-50 dark:border-gray-800 shrink-0">
                                <div class="flex items-start justify-between mb-6">
                                    <div class="flex-1 min-w-0">
                                        <div class="flex items-center gap-2 mb-2">
                                            <span class="modal-tag !mb-0">Process Insight</span>
                                            <div v-if="selectedTask.status === 'completed'" class="flex items-center gap-1 text-[9px] font-black uppercase text-green-500 bg-green-50 dark:bg-green-900/20 px-2 py-0.5 rounded-full border border-green-100 dark:border-green-800">
                                                <IconCheckCircle class="w-3 h-3" /> Success
                                            </div>
                                        </div>
                                        <h2 class="text-3xl font-bold font-serif text-gray-900 dark:text-white leading-tight truncate pr-10">
                                            {{ selectedTask.name }}
                                        </h2>
                                        <div class="flex items-center gap-2 mt-2">
                                            <code class="text-[9px] bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded text-gray-400 font-mono">ID: {{ selectedTask.id }}</code>
                                            <button @click="uiStore.copyToClipboard(selectedTask.id)" class="text-gray-400 hover:text-blue-500 transition-colors"><IconCopy class="w-3 h-3" /></button>
                                        </div>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <button @click="tasksStore.fetchTasks(ownerFilter)" class="p-2 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 transition-colors border border-transparent hover:border-gray-200 dark:hover:border-gray-700">
                                            <IconRefresh class="w-5 h-5" :class="{'animate-spin': isLoadingTasks}" />
                                        </button>
                                    </div>
                                </div>

                                <div class="grid grid-cols-4 gap-8">
                                    <div v-for="(val, label) in { 
                                        'State': selectedTask.status, 
                                        'Submitted': formatDateTime(selectedTask.created_at), 
                                        'Exec. Time': formatDateTime(selectedTask.started_at), 
                                        'User': selectedTask.owner_username || 'Admin' 
                                    }" :key="label">
                                        <span class="text-[9px] font-black uppercase tracking-widest text-gray-400 block mb-1">{{ label }}</span>
                                        <p class="text-xs font-bold text-gray-800 dark:text-gray-100 capitalize">{{ val }}</p>
                                    </div>
                                </div>
                            </section>

                            <!-- 2. Scrollable Analysis Pane -->
                            <section class="flex-1 overflow-y-auto p-8 pt-6 space-y-6 custom-scrollbar">
                                
                                <!-- Detailed Scope Callout -->
                                <div v-if="selectedTask.description" class="p-5 bg-blue-50/50 dark:bg-blue-900/10 rounded-2xl border border-blue-100/50 dark:border-blue-800/30">
                                    <p class="text-[13px] italic font-serif text-blue-800/70 dark:text-blue-300/70 leading-relaxed">
                                        "{{ selectedTask.description }}"
                                    </p>
                                </div>

                                <!-- Massive Log Viewport -->
                                <div class="terminal-log-window flex flex-col min-h-[500px] h-full bg-gray-950 rounded-2xl shadow-2xl border border-gray-800 overflow-hidden">
                                    <div class="px-5 py-3 bg-gray-900/50 border-b border-gray-800/50 flex items-center justify-between shrink-0">
                                        <div class="flex items-center gap-3">
                                            <div class="flex gap-1.5">
                                                <div class="w-2.5 h-2.5 rounded-full bg-red-500/40"></div>
                                                <div class="w-2.5 h-2.5 rounded-full bg-amber-500/40"></div>
                                                <div class="w-2.5 h-2.5 rounded-full bg-green-500/40"></div>
                                            </div>
                                            <div class="h-4 w-px bg-gray-800 mx-1"></div>
                                            <div class="flex items-center gap-2">
                                                <IconTerminal class="w-4 h-4 text-gray-500" />
                                                <span class="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Telemetry Stream</span>
                                            </div>
                                        </div>
                                        <button @click="copyLogs" class="text-[9px] font-black uppercase tracking-widest text-blue-500 hover:text-blue-400 transition-colors">
                                            Copy Trace
                                        </button>
                                    </div>
                                    <div ref="logsContainer" class="flex-1 overflow-y-auto p-6 font-mono text-[11px] leading-relaxed text-gray-400 custom-scrollbar">
                                        <div v-for="(log, i) in selectedTask.logs" :key="i" class="flex gap-6 mb-2 group">
                                            <span class="text-gray-700 shrink-0 select-none w-20">{{ new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }}</span>
                                            <span :class="{ 'text-red-400 font-bold': log.level === 'error', 'text-amber-400': log.level === 'warning' }">
                                                {{ log.message }}
                                            </span>
                                        </div>
                                        <div v-if="!selectedTask.logs?.length" class="h-full flex items-center justify-center italic opacity-20">
                                            Waiting for events...
                                        </div>
                                    </div>
                                </div>
                            </section>
                        </div>

                        <!-- ── Empty State ── -->
                        <div v-else class="flex-1 flex flex-col items-center justify-center p-20 text-center bg-white dark:bg-gray-950">
                            <div class="relative mb-8">
                                <IconCpuChip class="w-24 h-24 text-gray-100 dark:text-gray-800" />
                                <div class="absolute inset-0 blur-3xl bg-blue-500/5"></div>
                            </div>
                            <span class="modal-tag">Dashboard Idle</span>
                            <p class="text-xl font-serif text-gray-400 dark:text-gray-600 italic mt-2">Select a process from the navigation rail to inspect live data</p>
                        </div>
                    </Transition>
                </main>
            </div>
        </template>
        
        <template #footer>
            <div class="flex items-center gap-8 mr-auto pl-4">
                <button @click="handleCancelAllTasks" class="utility-link !text-red-500 hover:!text-red-600" :disabled="activeTasksCount === 0">
                    Terminate All ({{ activeTasksCount }})
                </button>
                <div class="w-px h-4 bg-gray-200 dark:border-gray-700"></div>
                <button @click="tasksStore.clearCompletedTasks" class="utility-link" :disabled="isClearingTasks">
                    Clear History
                </button>
            </div>
            <button @click="uiStore.closeModal('tasksManager')" class="welcome-btn !bg-gray-900 dark:!bg-white text-white dark:text-gray-900 !py-3 !px-12 shadow-xl active:scale-95 transition-all">
                Done
            </button>
        </template>
    </GenericModal>
</template>

<style scoped>
@reference "tailwindcss";

.task-sidebar-item {
    @apply w-full text-left p-3 rounded-xl transition-all duration-300 border border-transparent mb-0.5;
}
.task-sidebar-item:hover {
    @apply bg-white dark:bg-gray-800 shadow-sm border-gray-100 dark:border-gray-800;
}
.task-sidebar-item.is-selected {
    @apply bg-white dark:bg-gray-800 shadow-lg border-blue-500/30 ring-1 ring-blue-500/10;
}

/* Transitions */
.fade-slide-enter-active, .fade-slide-leave-active { transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.fade-slide-enter-from { opacity: 0; transform: translateY(10px); }
.fade-slide-leave-to { opacity: 0; transform: translateY(-10px); }
</style>
