<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import IconGpu from '../../assets/icons/IconGpu.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const systemStatus = computed(() => adminStore.systemStatus);
const isLoading = ref(false);
let refreshInterval = null;

async function refreshStatus() {
    isLoading.value = true;
    try {
        await adminStore.fetchSystemStatus();
    } finally {
        isLoading.value = false;
    }
}

onMounted(() => {
    refreshStatus();
    refreshInterval = setInterval(refreshStatus, 3000); // Faster polling for GPU
});

onUnmounted(() => {
    if (refreshInterval) clearInterval(refreshInterval);
});

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
    <div class="space-y-6">
        <div class="flex items-center justify-between">
            <h3 class="text-xl font-bold text-gray-900 dark:text-white">GPU Status</h3>
            <button @click="refreshStatus" class="btn btn-secondary btn-sm" :disabled="isLoading">
                <IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isLoading}"/> Refresh
            </button>
        </div>

        <div v-if="systemStatus?.gpus && systemStatus.gpus.length" class="space-y-6">
            <div v-for="gpu in systemStatus.gpus" :key="gpu.id" class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border dark:border-gray-700 overflow-hidden">
                <div class="p-6 border-b dark:border-gray-700">
                    <div class="flex flex-col md:flex-row md:items-center justify-between gap-6">
                        <div class="flex items-center gap-4 min-w-[200px]">
                            <div class="p-3 bg-green-100 dark:bg-green-900/30 rounded-full text-green-600 dark:text-green-400">
                                <IconGpu class="w-8 h-8"/>
                            </div>
                            <div>
                                <h4 class="font-bold text-lg text-gray-900 dark:text-white">{{ gpu.name }}</h4>
                                <p class="text-sm text-gray-500 font-mono">ID: {{ gpu.id }}</p>
                            </div>
                        </div>
                        
                        <div class="flex-grow grid grid-cols-1 sm:grid-cols-2 gap-6">
                            <!-- Compute Load -->
                            <div>
                                <div class="flex justify-between text-xs mb-1 font-medium text-gray-600 dark:text-gray-300">
                                    <span>Compute Load</span>
                                    <span>{{ gpu.gpu_utilization }}%</span>
                                </div>
                                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
                                    <div class="bg-orange-500 h-2.5 rounded-full transition-all duration-500" :style="{width: gpu.gpu_utilization + '%'}"></div>
                                </div>
                            </div>
                            <!-- VRAM Usage -->
                            <div>
                                <div class="flex justify-between text-xs mb-1 font-medium text-gray-600 dark:text-gray-300">
                                    <span>VRAM Usage</span>
                                    <span>{{ formatPercent(gpu.vram_usage_percent) }}</span>
                                </div>
                                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 mb-1">
                                    <div class="bg-indigo-500 h-2.5 rounded-full transition-all duration-500" :style="{width: gpu.vram_usage_percent + '%'}"></div>
                                </div>
                                <div class="text-xs text-gray-500 text-right">{{ formatBytes(gpu.vram_used_gb) }} / {{ formatBytes(gpu.vram_total_gb) }}</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Process Table -->
                <div class="bg-gray-50 dark:bg-gray-900/30 p-4">
                    <h5 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 px-2">Active Processes</h5>
                    <div v-if="gpu.processes && gpu.processes.length" class="overflow-x-auto rounded-lg border dark:border-gray-700 bg-white dark:bg-gray-800">
                        <table class="w-full text-sm text-left">
                            <thead class="text-xs text-gray-500 uppercase bg-gray-100 dark:bg-gray-700">
                                <tr>
                                    <th class="px-4 py-2 font-semibold">PID</th>
                                    <th class="px-4 py-2 font-semibold">Process Name</th>
                                    <th class="px-4 py-2 font-semibold">VRAM</th>
                                    <th class="px-4 py-2 text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
                                <tr v-for="proc in gpu.processes" :key="proc.pid" class="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                                    <td class="px-4 py-2 font-mono text-gray-600 dark:text-gray-400">{{ proc.pid }}</td>
                                    <td class="px-4 py-2 font-medium text-gray-900 dark:text-white">{{ proc.name }}</td>
                                    <td class="px-4 py-2 text-gray-600 dark:text-gray-400">{{ proc.memory_used.toFixed(0) }} MB</td>
                                    <td class="px-4 py-2 text-right">
                                        <button @click="killProcess(proc.pid, gpu.name)" class="btn btn-danger btn-xs" title="Kill Process">
                                            <IconTrash class="w-3 h-3 mr-1"/> Kill
                                        </button>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    <div v-else class="text-sm text-gray-500 italic px-2">No active processes detected on this GPU.</div>
                </div>
            </div>
        </div>
        <div v-else-if="systemStatus" class="p-8 text-center bg-white dark:bg-gray-800 rounded-xl shadow-sm border dark:border-gray-700">
            <IconGpu class="w-12 h-12 mx-auto text-gray-400 mb-3"/>
            <h3 class="text-lg font-medium text-gray-900 dark:text-white">No GPU Detected</h3>
            <p class="text-gray-500 dark:text-gray-400 mt-1">NVIDIA drivers might not be installed or no compatible GPU was found.</p>
        </div>
        <div v-else class="text-center py-10 text-gray-500">
            Loading GPU status...
        </div>
    </div>
</template>
