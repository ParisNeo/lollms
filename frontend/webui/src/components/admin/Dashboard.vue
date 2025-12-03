<script setup>
import { ref, onMounted, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { useTasksStore } from '../../stores/tasks';
import { useSocialStore } from '../../stores/social';
import { storeToRefs } from 'pinia';
import apiClient from '../../services/api';
import SystemStatus from './SystemStatus.vue';
import GlobalStatsChart from './GlobalStatsChart.vue';
import ModelUsageChart from './ModelUsageChart.vue';
import UserAvatar from '../ui/Cards/UserAvatar.vue';
import PendingUsersModal from '../modals/PendingUsersModal.vue';

import IconTrash from '../../assets/icons/IconTrash.vue';
import IconArchiveBox from '../../assets/icons/IconArchiveBox.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconUserGroup from '../../assets/icons/IconUserGroup.vue';
import IconLock from '../../assets/icons/IconLock.vue';
import IconLockOpen from '../../assets/icons/IconLockOpen.vue';

const stats = ref(null);
const isLoading = ref(true);
const uiStore = useUiStore();
const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const socialStore = useSocialStore();

const { connectedUsers, serverInfo, allUsers, globalGenerationStats, isLoadingGlobalGenerationStats } = storeToRefs(adminStore);
const { tasks } = storeToRefs(tasksStore);

const quickBroadcastMessage = ref('');
const isBroadcasting = ref(false);

const connectedUsersWithDetails = computed(() => {
    // Map connected user IDs to full user objects and add load mock/real data
    if (!allUsers.value.length) return [];
    return connectedUsers.value.map(cu => {
        const fullUser = allUsers.value.find(u => u.id === cu.id) || cu;
        // Mock load: map task_count to a % or use a random fluctuation for liveness if no real metric
        const activeUserTasks = tasks.value.filter(t => t.owner_username === fullUser.username && t.status === 'running').length;
        // Normalize load 0-100 based on active tasks (max 5 tasks = 100%)
        const load = Math.min(activeUserTasks * 20, 100); 
        return { ...fullUser, current_load: load };
    });
});

const pendingCount = computed(() => stats.value?.pending_approval || 0);

async function fetchDashboardData() {
    isLoading.value = true;
    try {
        await Promise.all([
            adminStore.fetchAllUsers(), 
            adminStore.fetchDashboardStats(),
            adminStore.fetchSystemStatus(),
            adminStore.fetchServerInfo(),
            adminStore.fetchGlobalGenerationStats(),
            adminStore.fetchConnectedUsers(),
            tasksStore.fetchTasks()
        ]);
        stats.value = adminStore.dashboardStats;
    } finally {
        isLoading.value = false;
    }
}

async function handlePurge() {
  const confirmed = await uiStore.showConfirmation({
    title: 'Purge Temporary Files?',
    message: 'Delete temporary files older than 24 hours?',
    confirmText: 'Purge',
    cancelText: 'Cancel'
  });
  if (confirmed && confirmed.confirmed) {
    adminStore.purgeUnusedUploads();
    uiStore.addNotification('Purge started.', 'info');
  }
}

async function handleBackup() {
    const { confirmed, value } = await uiStore.showConfirmation({
        title: 'Secure System Backup',
        message: 'Enter a MANDATORY password to encrypt the backup.',
        confirmText: 'Backup',
        inputType: 'password',
        inputPlaceholder: 'Encryption Password'
    });

    if (confirmed) {
        if (!value) {
            uiStore.addNotification('Password is required for backup.', 'error');
            return;
        }
        try {
            await adminStore.createBackup(value);
            uiStore.addNotification('Secure backup task started.', 'info');
        } catch (e) {
            uiStore.addNotification('Failed to start backup.', 'error');
        }
    }
}

async function handleQuickBroadcast() {
    if (!quickBroadcastMessage.value.trim()) return;
    isBroadcasting.value = true;
    try {
        await adminStore.broadcastMessage(quickBroadcastMessage.value);
        uiStore.addNotification('Broadcast sent.', 'success');
        quickBroadcastMessage.value = '';
    } finally { isBroadcasting.value = false; }
}

function openPendingModal() {
    if(pendingCount.value > 0) uiStore.openModal('pendingUsers');
}

function sendDm(user) {
    socialStore.openConversation({ id: user.id, username: user.username, icon: user.icon });
}

onMounted(fetchDashboardData);
</script>

<template>
    <div class="space-y-8 animate-fade-in p-2">
        <!-- Top Header -->
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
                <h2 class="text-2xl font-bold text-gray-900 dark:text-white">System Dashboard</h2>
                <div v-if="serverInfo" class="flex items-center gap-4 mt-1 text-sm text-gray-500 dark:text-gray-400">
                    <span class="flex items-center gap-1">
                        <span class="w-2 h-2 rounded-full" :class="serverInfo.https_enabled ? 'bg-green-500' : 'bg-yellow-500'"></span>
                        {{ serverInfo.url }}
                    </span>
                    <span v-if="serverInfo.https_enabled" class="flex items-center gap-1 text-green-600 dark:text-green-400"><IconLock class="w-3 h-3"/> HTTPS Active</span>
                    <span v-else class="flex items-center gap-1 text-yellow-600 dark:text-yellow-400"><IconLockOpen class="w-3 h-3"/> HTTP Only</span>
                </div>
            </div>
            <button @click="fetchDashboardData" class="btn btn-secondary btn-sm" :disabled="isLoading">
                <IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isLoading}" /> Refresh
            </button>
        </div>

        <!-- Metric Cards -->
        <div v-if="stats" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <div class="metric-card">
                <div><p class="metric-label">Total Users</p><p class="metric-value">{{ stats.total_users }}</p></div>
                <div class="metric-icon bg-blue-100 dark:bg-blue-900/30 text-blue-600"><IconUserGroup class="w-6 h-6"/></div>
            </div>
            
            <!-- Pending Users Card (Clickable) -->
            <div 
                class="metric-card cursor-pointer hover:ring-2 ring-orange-400 transition-all"
                @click="openPendingModal"
                title="Click to manage pending users"
            >
                <div><p class="metric-label">Pending Approval</p><p class="metric-value">{{ pendingCount }}</p></div>
                <div class="metric-icon bg-orange-100 dark:bg-orange-900/30 text-orange-600">
                    <IconUserGroup class="w-6 h-6"/>
                    <span v-if="pendingCount > 0" class="absolute top-0 right-0 -mt-1 -mr-1 flex h-3 w-3"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span><span class="relative inline-flex rounded-full h-3 w-3 bg-orange-500"></span></span>
                </div>
            </div>

            <div class="metric-card">
                <div><p class="metric-label">Active (24h)</p><p class="metric-value">{{ stats.active_users_24h }}</p></div>
                <div class="metric-icon bg-green-100 dark:bg-green-900/30 text-green-600"><IconCheckCircle class="w-6 h-6"/></div>
            </div>
        </div>

        <!-- Charts Row -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <GlobalStatsChart :stats="globalGenerationStats" :is-loading="isLoadingGlobalGenerationStats" />
            <ModelUsageChart />
        </div>

        <!-- Quick Actions & Connected Users -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Quick Actions -->
            <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-100 dark:border-gray-700">
                <h3 class="font-semibold mb-4 text-gray-900 dark:text-white">System Actions</h3>
                <div class="grid grid-cols-2 gap-4 mb-6">
                    <button @click="handleBackup" class="action-btn border-blue-200 hover:bg-blue-50 dark:border-blue-800 dark:hover:bg-blue-900/20">
                        <IconArchiveBox class="w-6 h-6 text-blue-500 mb-2"/>
                        <span class="text-sm font-medium">Secure Backup</span>
                    </button>
                    <button @click="handlePurge" class="action-btn border-red-200 hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-900/20">
                        <IconTrash class="w-6 h-6 text-red-500 mb-2"/>
                        <span class="text-sm font-medium">Purge Temp</span>
                    </button>
                </div>
                <div>
                    <label class="text-xs font-medium text-gray-500 uppercase mb-2 block">Quick Broadcast</label>
                    <div class="flex gap-2">
                        <input v-model="quickBroadcastMessage" type="text" class="input-field text-sm" placeholder="Message to all..." @keyup.enter="handleQuickBroadcast">
                        <button @click="handleQuickBroadcast" :disabled="!quickBroadcastMessage || isBroadcasting" class="btn btn-primary btn-sm"><IconSend class="w-4 h-4"/></button>
                    </div>
                </div>
            </div>

            <!-- Connected Users List -->
            <div class="lg:col-span-2 bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-100 dark:border-gray-700 flex flex-col">
                <h3 class="font-semibold mb-4 text-gray-900 dark:text-white flex justify-between">
                    <span>Live Users ({{ connectedUsersWithDetails.length }})</span>
                </h3>
                <div class="flex-grow overflow-y-auto max-h-64 space-y-3">
                    <div v-if="connectedUsersWithDetails.length === 0" class="text-center text-gray-500 py-4">No active users.</div>
                    <div v-for="user in connectedUsersWithDetails" :key="user.id" class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/30 rounded-lg">
                        <div class="flex items-center gap-3 w-1/3">
                            <UserAvatar :icon="user.icon" :username="user.username" size-class="h-8 w-8" />
                            <span class="font-medium text-sm truncate">{{ user.username }}</span>
                        </div>
                        <div class="w-1/3 px-4">
                            <div class="flex justify-between text-xs text-gray-500 mb-1"><span>Load</span><span>{{ user.current_load }}%</span></div>
                            <div class="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-1.5">
                                <div class="bg-blue-500 h-1.5 rounded-full transition-all duration-500" :style="{ width: user.current_load + '%' }"></div>
                            </div>
                        </div>
                        <button @click="sendDm(user)" class="btn btn-secondary btn-xs">DM</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Full System Status -->
        <SystemStatus />
        
        <!-- Modals -->
        <PendingUsersModal v-if="uiStore.activeModal === 'pendingUsers'" />
    </div>
</template>

<style scoped>
.metric-card { @apply bg-white dark:bg-gray-800 rounded-xl shadow-sm p-6 border border-gray-100 dark:border-gray-700 flex items-center justify-between; }
.metric-label { @apply text-sm font-medium text-gray-500 dark:text-gray-400; }
.metric-value { @apply text-3xl font-bold text-gray-900 dark:text-white mt-1; }
.metric-icon { @apply p-3 rounded-full relative; }
.action-btn { @apply flex flex-col items-center justify-center p-4 rounded-xl border-2 border-dashed transition-all cursor-pointer; }
.animate-fade-in { animation: fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
</style>
