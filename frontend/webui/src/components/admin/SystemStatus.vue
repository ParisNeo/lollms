<script setup>
import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconGpu from '../../assets/icons/IconGpu.vue';
import IconHardDrive from '../../assets/icons/IconHardDrive.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';

const adminStore = useAdminStore();
const { systemStatus, isLoadingSystemStatus } = storeToRefs(adminStore);

const gpus = computed(() => systemStatus.value?.gpus || []);
const totalVramUsedGb = computed(() => gpus.value.reduce((acc, gpu) => acc + gpu.vram_used_gb, 0));
const totalVramTotalGb = computed(() => gpus.value.reduce((acc, gpu) => acc + gpu.vram_total_gb, 0));
const totalVramUsagePercent = computed(() => {
    return totalVramTotalGb.value > 0 ? (totalVramUsedGb.value / totalVramTotalGb.value) * 100 : 0;
});

const dataDisk = computed(() => {
    if (!systemStatus.value || !systemStatus.value.disks) return null;
    let disk = systemStatus.value.disks.find(d => d.is_data_disk);
    if (!disk && systemStatus.value.disks.length > 0) {
        disk = systemStatus.value.disks[0];
    }
    return disk;
});

const formatBytes = (gb) => {
    if (gb === undefined || gb === null) return 'N/A';
    return `${gb.toFixed(1)} GB`;
};

const formatPercent = (percent) => {
    if (percent === undefined || percent === null) return 'N/A';
    return `${percent.toFixed(2)}%`;
};
</script>

<template>
    <div class="space-y-6">
        <div class="flex items-center justify-between">
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">System Status</h2>
            <button @click="adminStore.fetchSystemStatus" class="btn btn-secondary btn-sm" :disabled="isLoadingSystemStatus">
                <IconArrowPath class="w-4 h-4" :class="{'animate-spin': isLoadingSystemStatus}" />
            </button>
        </div>

        <div v-if="isLoadingSystemStatus && !systemStatus" class="text-center p-8">
            <p>Loading system status...</p>
        </div>

        <div v-else-if="systemStatus" class="space-y-6">
            <!-- Summary Cards -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <!-- GPU VRAM Summary -->
                <div class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md">
                    <div class="flex items-center">
                        <IconGpu class="w-6 h-6 mr-3 text-gray-400" />
                        <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">GPU VRAM</h3>
                    </div>
                    <p class="mt-2 text-2xl font-bold text-gray-900 dark:text-white">
                        {{ totalVramTotalGb > 0 ? `${formatBytes(totalVramUsedGb)} / ${formatBytes(totalVramTotalGb)}` : 'N/A' }}
                    </p>
                    <p class="text-sm text-gray-500 dark:text-gray-400">
                        {{ totalVramTotalGb > 0 ? `(${formatPercent(totalVramUsagePercent)})` : 'No compatible GPU found' }}
                    </p>
                </div>

                <!-- CPU RAM Summary -->
                <div class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md">
                    <div class="flex items-center">
                        <IconCpuChip class="w-6 h-6 mr-3 text-gray-400" />
                        <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">CPU RAM</h3>
                    </div>
                    <p class="mt-2 text-2xl font-bold text-gray-900 dark:text-white">
                        {{ formatBytes(systemStatus.cpu_ram_used_gb) }} / {{ formatBytes(systemStatus.cpu_ram_total_gb) }}
                    </p>
                     <p class="text-sm text-gray-500 dark:text-gray-400">({{ formatPercent(systemStatus.cpu_ram_usage_percent) }})</p>
                </div>

                <!-- Disk Summary (focused on Data disk) -->
                <div class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md">
                    <div class="flex items-center">
                        <IconHardDrive class="w-6 h-6 mr-3 text-gray-400" />
                        <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">Data Disk</h3>
                    </div>
                    <p v-if="dataDisk" class="mt-2 text-2xl font-bold text-gray-900 dark:text-white">
                        {{ formatBytes(dataDisk.used_gb) }} / {{ formatBytes(dataDisk.total_gb) }}
                    </p>
                     <p v-if="dataDisk" class="text-sm text-gray-500 dark:text-gray-400">({{ formatPercent(dataDisk.usage_percent) }})</p>
                     <p v-else class="mt-2 text-lg text-gray-500 dark:text-gray-400">No disk info</p>
                </div>
            </div>

            <!-- Detailed Sections -->
            <!-- CPU RAM Details -->
            <div class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md">
                <div class="flex items-center mb-2">
                     <IconCpuChip class="w-5 h-5 mr-2 text-gray-400" />
                     <h4 class="font-semibold text-gray-800 dark:text-gray-200">CPU RAM Usage Details</h4>
                </div>
                <div class="text-sm text-gray-600 dark:text-gray-300 space-y-1">
                    <p>Available: <span class="font-medium text-gray-900 dark:text-white">{{ formatBytes(systemStatus.cpu_ram_available_gb) }}</span></p>
                    <p>Usage: <span class="font-medium text-gray-900 dark:text-white">{{ formatBytes(systemStatus.cpu_ram_used_gb) }} / {{ formatBytes(systemStatus.cpu_ram_total_gb) }} ({{ formatPercent(systemStatus.cpu_ram_usage_percent) }})</span></p>
                </div>
                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 mt-3">
                    <div class="bg-gradient-to-r from-blue-400 to-purple-500 h-2.5 rounded-full" :style="{ width: systemStatus.cpu_ram_usage_percent + '%' }"></div>
                </div>
            </div>

            <!-- All Disks Details -->
            <div v-for="disk in systemStatus.disks" :key="disk.mount_point" 
                 class="p-4 rounded-lg shadow-md border-l-4"
                 :class="{
                    'bg-white dark:bg-gray-800 border-transparent': !disk.is_app_disk && !disk.is_data_disk,
                    'bg-blue-50 dark:bg-blue-900/20 border-blue-500': disk.is_data_disk && !disk.is_app_disk,
                    'bg-green-50 dark:bg-green-900/20 border-green-500': disk.is_app_disk && !disk.is_data_disk,
                    'bg-gradient-to-r from-green-50 to-blue-50 dark:from-green-900/20 dark:to-blue-900/20 border-purple-500': disk.is_app_disk && disk.is_data_disk
                 }">
                <div class="flex items-center mb-2">
                     <IconHardDrive class="w-5 h-5 mr-2 text-gray-400" />
                     <h4 class="font-semibold text-gray-800 dark:text-gray-200">Disk: {{ disk.mount_point }}</h4>
                     <span v-if="disk.is_data_disk" class="ml-3 text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300">Data</span>
                     <span v-if="disk.is_app_disk" class="ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300">App</span>
                </div>
                <div class="text-sm text-gray-600 dark:text-gray-300 space-y-1">
                    <p>Available: <span class="font-medium text-gray-900 dark:text-white">{{ formatBytes(disk.available_gb) }}</span></p>
                    <p>Usage: <span class="font-medium text-gray-900 dark:text-white">{{ formatBytes(disk.used_gb) }} / {{ formatBytes(disk.total_gb) }} ({{ formatPercent(disk.usage_percent) }})</span></p>
                </div>
                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 mt-3">
                    <div class="bg-gradient-to-r from-cyan-400 to-teal-500 h-2.5 rounded-full" :style="{ width: disk.usage_percent + '%' }"></div>
                </div>
            </div>
            
            <!-- GPU Details -->
            <div v-if="gpus.length > 0" v-for="(gpu, index) in gpus" :key="gpu.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md">
                <div class="flex items-center mb-2">
                     <IconGpu class="w-5 h-5 mr-2 text-gray-400" />
                     <h4 class="font-semibold text-gray-800 dark:text-gray-200">GPU {{ index + 1 }} Usage Details</h4>
                </div>
                 <div class="text-sm text-gray-600 dark:text-gray-300 space-y-1">
                    <p>Model: <span class="font-medium text-gray-900 dark:text-white">{{ gpu.name }}</span></p>
                    <p>Available VRAM: <span class="font-medium text-gray-900 dark:text-white">{{ formatBytes(gpu.vram_total_gb - gpu.vram_used_gb) }}</span></p>
                    <p>Usage: <span class="font-medium text-gray-900 dark:text-white">{{ formatBytes(gpu.vram_used_gb) }} / {{ formatBytes(gpu.vram_total_gb) }} ({{ formatPercent(gpu.vram_usage_percent) }})</span></p>
                </div>
                <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 mt-3">
                    <div class="bg-gradient-to-r from-indigo-500 to-pink-500 h-2.5 rounded-full" :style="{ width: gpu.vram_usage_percent + '%' }"></div>
                </div>
            </div>
             <div v-else class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md text-center text-gray-500 dark:text-gray-400">
                <p>No NVIDIA GPU detected or pynvml library not installed on the server.</p>
            </div>
        </div>

        <div v-else-if="!isLoadingSystemStatus" class="text-center p-8">
            <p class="text-red-500">Failed to load system status. Please check server logs.</p>
        </div>
    </div>
</template>