<script setup>
import { ref, onMounted, computed } from 'vue';
import apiClient from '../../services/api';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import SystemStatus from './SystemStatus.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import IconUserCircle from '../../assets/icons/IconUserCircle.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';

const stats = ref(null);
const isLoading = ref(true);
const uiStore = useUiStore();
const adminStore = useAdminStore();

const connectedUsers = computed(() => adminStore.connectedUsers);
const isLoadingConnectedUsers = computed(() => adminStore.isLoadingConnectedUsers);
const serverInfo = computed(() => adminStore.serverInfo);
const isLoadingServerInfo = computed(() => adminStore.isLoadingServerInfo);


const statItems = ref([
  { key: 'total_users', label: 'Total Users', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z' },
  { key: 'active_users_24h', label: 'Active in 24h', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
  { key: 'new_users_7d', label: 'New in 7d', icon: 'M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z' },
  { key: 'pending_approval', label: 'Pending Approval', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  { key: 'pending_password_resets', label: 'Password Resets', icon: 'M15 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' }
]);

async function fetchDashboardData() {
    isLoading.value = true;
    try {
        const [statsResponse] = await Promise.all([
            apiClient.get('/api/admin/stats'),
            adminStore.fetchSystemStatus(),
            adminStore.fetchConnectedUsers(),
            adminStore.fetchServerInfo()
        ]);
        stats.value = statsResponse.data;
    } catch (error) {
        uiStore.addNotification('Could not load dashboard statistics.', 'error');
    } finally {
        isLoading.value = false;
    }
}

async function handlePurge() {
  const confirmed = await uiStore.showConfirmation({
    title: 'Purge Temporary Files?',
    message: 'This will permanently delete temporary files from all users that are older than 24 hours. This action cannot be undone. Check the Task Manager for progress.',
    confirmText: 'Purge Now',
    cancelText: 'Cancel'
  });
  if (confirmed && confirmed.confirmed) {
    adminStore.purgeUnusedUploads();
    uiStore.addNotification('Purge task has been started.', 'info');
  }
}

onMounted(fetchDashboardData);
</script>

<template>
    <div class="space-y-12">
        <div class="space-y-6">
            <div class="flex items-center justify-between">
                <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                    Application Overview
                </h3>
                <button @click="fetchDashboardData" class="btn btn-secondary btn-sm" :disabled="isLoading">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" :class="{'animate-spin': isLoading}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h5M20 20v-5h-5M4 4l16 16" />
                    </svg>
                    <span class="ml-2">Refresh</span>
                </button>
            </div>

            <div v-if="isLoading" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
                <div v-for="i in 5" :key="i" class="bg-white dark:bg-gray-800/50 rounded-lg shadow p-5 animate-pulse">
                    <div class="h-6 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-4"></div>
                    <div class="h-10 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                </div>
            </div>

            <div v-else-if="stats" class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-5">
                <div v-for="item in statItems" :key="item.key" class="bg-white dark:bg-gray-800 rounded-lg shadow p-5 flex flex-col justify-between">
                    <div>
                        <div class="flex items-center">
                            <div class="flex-shrink-0">
                                <svg class="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="item.icon" />
                                </svg>
                            </div>
                            <div class="ml-5 w-0 flex-1">
                                <dl>
                                    <dt class="text-sm font-medium text-gray-500 dark:text-gray-400 truncate">
                                        {{ item.label }}
                                    </dt>
                                    <dd>
                                        <div class="text-2xl font-bold text-gray-900 dark:text-white">
                                            {{ stats[item.key] }}
                                        </div>
                                    </dd>
                                </dl>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div v-else class="text-center p-10 bg-white dark:bg-gray-800 rounded-lg shadow">
                <p class="text-gray-500">Could not load dashboard data.</p>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div class="space-y-6">
                <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                    Server Information
                </h3>
                <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-5">
                    <div v-if="isLoadingServerInfo" class="text-center py-4"><p>Loading server info...</p></div>
                    <div v-else-if="serverInfo" class="space-y-4 text-sm">
                        <div class="flex items-center gap-3">
                            <IconServer class="w-5 h-5 text-gray-400" />
                            <span class="font-semibold">Address:</span>
                            <span class="font-mono text-gray-700 dark:text-gray-300">{{ serverInfo.host }}:{{ serverInfo.port }}</span>
                            <span class="px-2 py-0.5 text-xs rounded-full" :class="serverInfo.https_enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'">{{ serverInfo.https_enabled ? 'HTTPS' : 'HTTP' }}</span>
                        </div>
                        <div v-if="serverInfo.host === '0.0.0.0' && serverInfo.local_ips && serverInfo.local_ips.length > 0" class="pl-8">
                            <h4 class="font-semibold text-gray-600 dark:text-gray-300 mb-1">Accessible Addresses:</h4>
                            <ul class="space-y-1 list-disc list-inside">
                                <li v-for="ip in serverInfo.local_ips" :key="ip">
                                    <a :href="`${serverInfo.https_enabled ? 'https' : 'http'}://${ip}:${serverInfo.port}`" target="_blank" class="font-mono text-blue-600 dark:text-blue-400 hover:underline">
                                        {{ ip }}:{{ serverInfo.port }}
                                    </a>
                                </li>
                            </ul>
                        </div>
                        <div class="flex items-center gap-3">
                            <IconGlobeAlt class="w-5 h-5 text-gray-400" />
                            <span class="font-semibold">CORS Origins:</span>
                            <span class="font-mono text-gray-700 dark:text-gray-300">{{ serverInfo.cors_origins.join(', ') || 'None' }}</span>
                        </div>
                        <div v-if="serverInfo.active_ports.length > 0">
                            <h4 class="font-semibold mt-4 mb-2">Active App Ports:</h4>
                            <ul class="space-y-1 pl-8 list-disc list-inside">
                                <li v-for="app in serverInfo.active_ports" :key="app.app_id">
                                    <span class="font-mono">{{ app.port }}</span> - {{ app.app_name }}
                                </li>
                            </ul>
                        </div>
                        <div class="pt-4 border-t dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400">
                           LoLLMs v{{ serverInfo.lollms_version }} | Python {{ serverInfo.python_version.split(' ')[0] }}
                        </div>
                    </div>
                </div>
            </div>

            <div class="space-y-6">
                <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                    Live Connections
                </h3>
                <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-5">
                    <div class="flex items-center justify-between mb-4">
                        <div>
                            <h4 class="font-semibold text-gray-800 dark:text-gray-100">Currently Connected Users</h4>
                            <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                                Users with an active WebSocket connection.
                            </p>
                        </div>
                        <span v-if="!isLoadingConnectedUsers" class="text-lg font-bold text-gray-700 dark:text-gray-200">{{ connectedUsers.length }}</span>
                    </div>

                    <div v-if="isLoadingConnectedUsers" class="text-center py-4">
                        <p class="text-gray-500">Loading connected users...</p>
                    </div>
                    <div v-else-if="connectedUsers.length === 0" class="text-center py-4 text-gray-500">
                        No users are currently connected.
                    </div>
                    <ul v-else class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-2 xl:grid-cols-3 gap-4">
                        <li v-for="user in connectedUsers" :key="user.id" class="flex items-center space-x-3 p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                            <UserAvatar :icon="user.icon" :username="user.username" size-class="h-8 w-8" />
                            <span class="font-medium text-sm truncate" :title="user.username">{{ user.username }}</span>
                        </li>
                    </ul>
                </div>
            </div>
        </div>

        <div class="space-y-6">
            <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                Maintenance Actions
            </h3>
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow p-5">
                <div class="flex items-center justify-between">
                    <div>
                        <h4 class="font-semibold text-gray-800 dark:text-gray-100">Purge Temporary Files</h4>
                        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                            Delete all user-uploaded files in temporary folders that are older than 24 hours. 
                            This does not affect discussions, artefacts, or data stores.
                        </p>
                    </div>
                    <button @click="handlePurge" class="btn btn-danger flex items-center">
                        <IconTrash class="w-4 h-4 mr-2" />
                        <span>Purge Now</span>
                    </button>
                </div>
            </div>
        </div>

        <SystemStatus />
    </div>
</template>