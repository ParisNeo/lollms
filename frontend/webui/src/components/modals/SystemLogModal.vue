<script setup>
import { onMounted, ref, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const logs = computed(() => adminStore.systemLogs);
const isLoading = computed(() => adminStore.isLoadingSystemLogs);

function refreshLogs() {
    adminStore.fetchSystemLogs();
}

function copyLogs() {
    const text = logs.value.map(l => `[${l.timestamp}] [${l.level}] [${l.task_name}] ${l.message}`).join('\n');
    uiStore.copyToClipboard(text, 'Logs copied to clipboard');
}

function getLevelClass(level) {
    switch (level.toUpperCase()) {
        case 'ERROR': return 'text-red-600 dark:text-red-400 font-bold';
        case 'CRITICAL': return 'text-red-700 dark:text-red-500 font-bold underline';
        case 'WARNING': return 'text-yellow-600 dark:text-yellow-400';
        default: return 'text-gray-700 dark:text-gray-300';
    }
}

function formatTime(iso) {
    return new Date(iso).toLocaleString();
}

onMounted(() => {
    refreshLogs();
});
</script>

<template>
    <GenericModal modal-name="systemLog" title="System Logs (Recent Tasks)" max-width-class="max-w-5xl">
        <template #body>
            <div class="flex flex-col h-[70vh]">
                <div class="flex justify-between items-center mb-2 px-1">
                    <span class="text-sm text-gray-500">Aggregated logs from recent background tasks.</span>
                    <div class="flex gap-2">
                        <button @click="copyLogs" class="btn btn-secondary btn-sm" title="Copy to Clipboard">
                            <IconCopy class="w-4 h-4"/>
                        </button>
                        <button @click="refreshLogs" class="btn btn-secondary btn-sm" :disabled="isLoading">
                            <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoading}"/>
                        </button>
                    </div>
                </div>
                
                <div class="flex-grow overflow-y-auto bg-gray-50 dark:bg-gray-900 rounded-md border dark:border-gray-700 p-4 font-mono text-xs">
                    <div v-if="isLoading && logs.length === 0" class="text-center py-4 text-gray-500">Loading logs...</div>
                    <div v-else-if="logs.length === 0" class="text-center py-4 text-gray-500">No logs found.</div>
                    <div v-else>
                        <div v-for="(log, idx) in logs" :key="idx" class="mb-1 border-b border-gray-100 dark:border-gray-800 pb-1 last:border-0 hover:bg-gray-100 dark:hover:bg-gray-800/50 px-2 rounded">
                            <div class="flex gap-2">
                                <span class="text-gray-400 whitespace-nowrap min-w-[140px]">{{ formatTime(log.timestamp) }}</span>
                                <span :class="getLevelClass(log.level)" class="w-16 flex-shrink-0">{{ log.level }}</span>
                                <span class="text-blue-500 dark:text-blue-400 w-32 truncate flex-shrink-0" :title="log.task_name">{{ log.task_name }}</span>
                                <span class="break-all whitespace-pre-wrap">{{ log.message }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('systemLog')" class="btn btn-primary">Close</button>
        </template>
    </GenericModal>
</template>
