<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import IconGpu from '../../assets/icons/IconGpu.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconHardDrive from '../../assets/icons/IconHardDrive.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';

const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();
const systemStatus = computed(() => adminStore.systemStatus);

const lastAnalysisReport = ref(null);
const isAnalyzing = ref(false);

const analysisTasks = computed(() => {
    return tasksStore.tasks.filter(t => t.name === "Analyze System Logs").sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
});

// Watch for changes in analysis tasks to update the report view
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
}, { immediate: true });

async function analyzeLogs() {
    try {
        await adminStore.analyzeSystemLogs();
        isAnalyzing.value = true;
    } catch (e) {
        // Error handled in store
    }
}

async function killProcess(pid, gpuName) {
    const confirmed = await uiStore.showConfirmation({
        title: 'Kill Process?',
        message: `Are you sure you want to kill process ${pid} on ${gpuName}? This might crash running generations.`,
        confirmText: 'Kill',
        isDanger: true
    });
    if(confirmed.confirmed) {
        await adminStore.killProcess(pid);
    }
}

const formatBytes = (gb) => gb ? `${gb.toFixed(1)} GB` : '0 GB';
const formatPercent = (pct) => pct ? `${pct.toFixed(1)}%` : '0%';
</script>

<template>
    <div v-if="systemStatus" class="space-y-6">
        <h3 class="text-xl font-bold text-gray-900 dark:text-white">Hardware Status</h3>
        
        <!-- Resources Summary -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <!-- CPU RAM -->
            <div class="bg-white dark:bg-gray-800 p-5 rounded-xl shadow-sm border dark:border-gray-700">
                <div class="flex items-center mb-4 text-blue-600">
                    <IconCpuChip class="w-6 h-6 mr-2"/> <span class="font-semibold">System RAM</span>
                </div>
                <div class="space-y-2">
                    <div class="flex justify-between text-sm"><span>Usage</span><span>{{ formatPercent(systemStatus.cpu_ram_usage_percent) }}</span></div>
                    <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2"><div class="bg-blue-600 h-2 rounded-full" :style="{width: systemStatus.cpu_ram_usage_percent+'%'}"></div></div>
                    <div class="text-xs text-gray-500 text-right">{{ formatBytes(systemStatus.cpu_ram_used_gb) }} / {{ formatBytes(systemStatus.cpu_ram_total_gb) }}</div>
                </div>
            </div>

            <!-- Disks -->
            <div v-for="disk in systemStatus.disks" :key="disk.mount_point" 
                 class="bg-white dark:bg-gray-800 p-5 rounded-xl shadow-sm border-l-4"
                 :class="{'border-green-500': disk.is_app_disk, 'border-purple-500': disk.is_data_disk, 'border-gray-300 dark:border-gray-600': !disk.is_app_disk && !disk.is_data_disk}">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center text-gray-700 dark:text-gray-200">
                        <IconHardDrive class="w-6 h-6 mr-2"/> 
                        <span class="font-semibold truncate max-w-[120px]" :title="disk.mount_point">{{ disk.mount_point }}</span>
                    </div>
                    <div class="flex gap-1">
                        <span v-if="disk.is_app_disk" class="px-2 py-0.5 rounded bg-green-100 text-green-800 text-xs font-bold">CODE</span>
                        <span v-if="disk.is_data_disk" class="px-2 py-0.5 rounded bg-purple-100 text-purple-800 text-xs font-bold">DATA</span>
                    </div>
                </div>
                <div class="space-y-2">
                    <div class="flex justify-between text-sm"><span>Used</span><span>{{ formatPercent(disk.usage_percent) }}</span></div>
                    <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2"><div class="bg-gray-600 dark:bg-gray-400 h-2 rounded-full" :style="{width: disk.usage_percent+'%'}"></div></div>
                    <div class="text-xs text-gray-500 text-right">{{ formatBytes(disk.used_gb) }} / {{ formatBytes(disk.total_gb) }}</div>
                </div>
            </div>
        </div>

        <!-- GPU Details Table -->
        <div v-if="systemStatus.gpus && systemStatus.gpus.length" class="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden border dark:border-gray-700">
            <div class="p-4 bg-gray-50 dark:bg-gray-700/30 border-b dark:border-gray-700 font-semibold">GPU Details</div>
            <div v-for="gpu in systemStatus.gpus" :key="gpu.id" class="p-6 border-b last:border-0 dark:border-gray-700">
                <div class="flex flex-col md:flex-row md:items-center justify-between mb-6 gap-6">
                    <div class="flex items-center gap-3 min-w-[200px]">
                        <IconGpu class="w-8 h-8 text-green-500"/>
                        <div>
                            <h4 class="font-bold text-lg">{{ gpu.name }} <span class="text-sm font-normal text-gray-500">[ID: {{ gpu.id }}]</span></h4>
                        </div>
                    </div>
                    
                    <div class="flex-grow space-y-3">
                        <!-- Compute Load -->
                        <div>
                            <div class="flex justify-between text-xs mb-1"><span>Compute Load</span><span class="font-bold">{{ gpu.gpu_utilization }}%</span></div>
                            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                                <div class="bg-orange-500 h-2 rounded-full transition-all duration-500" :style="{width: gpu.gpu_utilization + '%'}"></div>
                            </div>
                        </div>
                        <!-- VRAM Usage -->
                        <div>
                            <div class="flex justify-between text-xs mb-1">
                                <span>VRAM</span>
                                <span>{{ formatBytes(gpu.vram_used_gb) }} / {{ formatBytes(gpu.vram_total_gb) }} ({{ formatPercent(gpu.vram_usage_percent) }})</span>
                            </div>
                            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                                <div class="bg-indigo-500 h-2 rounded-full transition-all duration-500" :style="{width: gpu.vram_usage_percent + '%'}"></div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Process Table -->
                <div v-if="gpu.processes && gpu.processes.length" class="mt-4 border dark:border-gray-600 rounded-lg overflow-hidden">
                    <table class="w-full text-sm text-left">
                        <thead class="text-xs text-gray-500 uppercase bg-gray-50 dark:bg-gray-900/50">
                            <tr>
                                <th class="px-4 py-2">PID</th>
                                <th class="px-4 py-2">Process Name</th>
                                <th class="px-4 py-2">VRAM Usage</th>
                                <th class="px-4 py-2 text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="proc in gpu.processes" :key="proc.pid" class="border-t dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                                <td class="px-4 py-2 font-mono">{{ proc.pid }}</td>
                                <td class="px-4 py-2">{{ proc.name }}</td>
                                <td class="px-4 py-2">{{ proc.memory_used.toFixed(0) }} MB</td>
                                <td class="px-4 py-2 text-right">
                                    <button @click="killProcess(proc.pid, gpu.name)" class="text-red-500 hover:text-red-700 px-2 py-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20" title="Kill Process">
                                        <IconTrash class="w-4 h-4"/>
                                    </button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <div v-else class="mt-2 text-xs text-gray-500 italic">No active processes detected on this GPU.</div>
            </div>
        </div>

        <!-- Log Analysis Zone -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border dark:border-gray-700 p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-bold text-gray-900 dark:text-white">AI Log Analysis</h3>
                <div class="flex gap-2">
                    <button 
                        @click="uiStore.openModal('systemLog')" 
                        class="btn btn-secondary btn-sm flex items-center gap-2"
                    >
                        <IconFileText class="w-4 h-4"/>
                        View Logs
                    </button>
                    <button 
                        @click="analyzeLogs" 
                        :disabled="isAnalyzing"
                        class="btn btn-secondary btn-sm flex items-center gap-2"
                    >
                        <IconAnimateSpin v-if="isAnalyzing" class="w-4 h-4 animate-spin"/>
                        <IconPlayCircle v-else class="w-4 h-4"/>
                        {{ isAnalyzing ? 'Analyzing...' : (lastAnalysisReport ? 'Regenerate Analysis' : 'Analyze Logs') }}
                    </button>
                </div>
            </div>

            <div v-if="lastAnalysisReport" class="bg-gray-50 dark:bg-gray-900/50 rounded-lg p-4 text-sm border dark:border-gray-700">
                <div class="flex justify-between items-center mb-3 text-xs text-gray-500">
                    <span class="font-semibold">Analysis Report</span>
                    <span>Generated: {{ new Date(lastAnalysisReport.generated_at).toLocaleString() }}</span>
                </div>
                <MessageContentRenderer :content="lastAnalysisReport.report" class="prose dark:prose-invert prose-sm max-w-none"/>
            </div>
            <div v-else class="text-center py-8 text-gray-500 dark:text-gray-400 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg">
                <p>Click "Analyze Logs" to have the AI scan recent system tasks and identify potential issues.</p>
            </div>
        </div>
    </div>
</template>
