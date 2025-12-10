<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconHardDrive from '../../assets/icons/IconHardDrive.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';

const adminStore = useAdminStore();
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
    refreshInterval = setInterval(refreshStatus, 5000);
});

onUnmounted(() => {
    if (refreshInterval) clearInterval(refreshInterval);
});

const formatBytes = (gb) => gb ? `${gb.toFixed(1)} GB` : '0 GB';
const formatPercent = (pct) => pct ? `${pct.toFixed(1)}%` : '0%';
</script>

<template>
    <div class="space-y-6">
        <div class="flex items-center justify-between">
            <h3 class="text-xl font-bold text-gray-900 dark:text-white">System Resources</h3>
            <button @click="refreshStatus" class="btn btn-secondary btn-sm" :disabled="isLoading">
                <IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isLoading}"/> Refresh
            </button>
        </div>

        <div v-if="systemStatus" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <!-- CPU RAM -->
            <div class="bg-white dark:bg-gray-800 p-5 rounded-xl shadow-sm border dark:border-gray-700">
                <div class="flex items-center mb-4 text-blue-600">
                    <IconCpuChip class="w-6 h-6 mr-2"/> <span class="font-semibold">System RAM</span>
                </div>
                <div class="space-y-4">
                    <div>
                        <div class="flex justify-between text-sm mb-1"><span>Usage</span><span class="font-bold">{{ formatPercent(systemStatus.cpu_ram_usage_percent) }}</span></div>
                        <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
                            <div class="bg-blue-600 h-2.5 rounded-full transition-all duration-500" :style="{width: systemStatus.cpu_ram_usage_percent+'%'}"></div>
                        </div>
                    </div>
                    <div class="grid grid-cols-2 gap-4 text-sm text-gray-600 dark:text-gray-400">
                        <div>
                            <span class="block text-xs uppercase text-gray-500">Used</span>
                            <span class="font-mono">{{ formatBytes(systemStatus.cpu_ram_used_gb) }}</span>
                        </div>
                        <div>
                            <span class="block text-xs uppercase text-gray-500">Total</span>
                            <span class="font-mono">{{ formatBytes(systemStatus.cpu_ram_total_gb) }}</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Disks -->
            <div v-for="disk in systemStatus.disks" :key="disk.mount_point" 
                 class="bg-white dark:bg-gray-800 p-5 rounded-xl shadow-sm border-l-4"
                 :class="{'border-green-500': disk.is_app_disk, 'border-purple-500': disk.is_data_disk, 'border-gray-300 dark:border-gray-600': !disk.is_app_disk && !disk.is_data_disk}">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center text-gray-700 dark:text-gray-200 min-w-0">
                        <IconHardDrive class="w-6 h-6 mr-2 flex-shrink-0"/> 
                        <span class="font-semibold truncate" :title="disk.mount_point">{{ disk.mount_point }}</span>
                    </div>
                    <div class="flex gap-1 flex-shrink-0 ml-2">
                        <span v-if="disk.is_app_disk" class="px-2 py-0.5 rounded bg-green-100 text-green-800 text-xs font-bold">APP</span>
                        <span v-if="disk.is_data_disk" class="px-2 py-0.5 rounded bg-purple-100 text-purple-800 text-xs font-bold">DATA</span>
                    </div>
                </div>
                <div class="space-y-4">
                    <div>
                        <div class="flex justify-between text-sm mb-1"><span>Used</span><span class="font-bold">{{ formatPercent(disk.usage_percent) }}</span></div>
                        <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
                            <div class="bg-gray-600 dark:bg-gray-400 h-2.5 rounded-full transition-all duration-500" :style="{width: disk.usage_percent+'%'}"></div>
                        </div>
                    </div>
                    <div class="grid grid-cols-2 gap-4 text-sm text-gray-600 dark:text-gray-400">
                        <div>
                            <span class="block text-xs uppercase text-gray-500">Free</span>
                            <span class="font-mono">{{ formatBytes(disk.available_gb) }}</span>
                        </div>
                        <div>
                            <span class="block text-xs uppercase text-gray-500">Total</span>
                            <span class="font-mono">{{ formatBytes(disk.total_gb) }}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div v-else class="text-center py-10 text-gray-500">
            Loading system status...
        </div>
    </div>
</template>
