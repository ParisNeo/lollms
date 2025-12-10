<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import SystemLogModal from '../modals/SystemLogModal.vue';

const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();

const lastAnalysisReport = ref(null);
const isAnalyzing = ref(false);

const analysisTasks = computed(() => {
    return tasksStore.tasks.filter(t => t.name === "Analyze System Logs").sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
});

watch(analysisTasks, (tasks) => {
    const latest = tasks[0];
    if (latest) {
        if (latest.status === 'running' || latest.status === 'pending') {
            isAnalyzing.value = true;
        } else {
            isAnalyzing.value = false;
            if (latest.status === 'completed' && latest.result?.report) {
                lastAnalysisReport.value = latest.result;
            }
        }
    } else {
        isAnalyzing.value = false;
        lastAnalysisReport.value = null;
    }
}, { immediate: true, deep: true });

onMounted(() => {
    tasksStore.fetchTasks();
});

async function analyzeLogs() {
    try {
        await adminStore.analyzeSystemLogs();
        // Force refresh tasks to pick up the new one immediately
        setTimeout(() => tasksStore.fetchTasks(), 500); 
    } catch (e) {
        // Error handled in store
    }
}

function openLogModal() {
    uiStore.openModal('systemLog');
}
</script>

<template>
    <div class="space-y-6">
        <div class="flex items-center justify-between">
            <h3 class="text-xl font-bold text-gray-900 dark:text-white">System Logs & Analysis</h3>
            <button 
                @click="openLogModal" 
                class="btn btn-secondary btn-sm flex items-center gap-2"
            >
                <IconFileText class="w-4 h-4"/>
                View Raw Logs
            </button>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border dark:border-gray-700 overflow-hidden">
            <div class="p-6 border-b dark:border-gray-700 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h4 class="text-lg font-bold text-gray-900 dark:text-white">AI Log Analysis</h4>
                    <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        Use the AI to scan recent tasks and logs for errors, warnings, and potential issues.
                    </p>
                </div>
                <button 
                    @click="analyzeLogs" 
                    :disabled="isAnalyzing"
                    class="btn btn-primary flex items-center gap-2"
                >
                    <IconAnimateSpin v-if="isAnalyzing" class="w-5 h-5 animate-spin"/>
                    <IconPlayCircle v-else class="w-5 h-5"/>
                    {{ isAnalyzing ? 'Analyzing...' : 'Regenerate Analysis' }}
                </button>
            </div>

            <div class="p-6">
                <div v-if="isAnalyzing" class="flex flex-col items-center justify-center py-12 text-blue-600 dark:text-blue-400">
                    <IconAnimateSpin class="w-10 h-10 animate-spin mb-3"/>
                    <p class="font-medium">Analyzing system logs...</p>
                </div>
                
                <div v-else-if="lastAnalysisReport" class="space-y-4">
                    <div class="flex items-center gap-2 text-sm text-green-600 dark:text-green-400 mb-2">
                        <IconCheckCircle class="w-5 h-5"/>
                        <span class="font-semibold">Analysis Complete</span>
                        <span class="text-gray-400 mx-2">|</span>
                        <span class="text-gray-500">{{ new Date(lastAnalysisReport.generated_at).toLocaleString() }}</span>
                    </div>
                    
                    <div class="prose dark:prose-invert max-w-none bg-gray-50 dark:bg-gray-900/50 p-6 rounded-lg border dark:border-gray-700">
                        <MessageContentRenderer :content="lastAnalysisReport.report"/>
                    </div>
                </div>

                <div v-else class="text-center py-12 text-gray-500 dark:text-gray-400 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg">
                    <IconFileText class="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-3"/>
                    <p>No analysis report available.</p>
                    <button @click="analyzeLogs" class="text-blue-600 hover:underline mt-2">Start Analysis</button>
                </div>
            </div>
        </div>
        
        <!-- Modal mount point handled by App.vue but triggered here -->
    </div>
</template>
