<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import apiClient from '../../services/api';

// Icons
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconArchiveBox from '../../assets/icons/IconArchiveBox.vue';
import IconClock from '../../assets/icons/IconClock.vue';
import IconLock from '../../assets/icons/IconLock.vue';
import IconWrenchScrewdriver from '../../assets/icons/IconWrenchScrewdriver.vue';
import IconPower from '../../assets/icons/IconPower.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();

// --- Maintenance Mode State ---
const maintenanceMode = ref(false);
const maintenanceMessage = ref("");
const isSavingMaintenance = ref(false);

const maintenanceSetting = computed(() => adminStore.globalSettings.find(s => s.key === 'maintenance_mode'));
const messageSetting = computed(() => adminStore.globalSettings.find(s => s.key === 'maintenance_message'));

// --- Server Action State ---
const isActionInProgress = ref(false);
const actionStatus = ref(''); // 'rebooting', 'updating', 'reconnecting', 'success'
const pingInterval = ref(null);
const backupPassword = ref('');

// --- Initialization ---
onMounted(() => {
    if (adminStore.globalSettings.length === 0) {
        adminStore.fetchGlobalSettings();
    } else {
        syncMaintenanceState();
    }
});

watch(() => adminStore.globalSettings, syncMaintenanceState, { deep: true });

function syncMaintenanceState() {
    if (maintenanceSetting.value) maintenanceMode.value = maintenanceSetting.value.value;
    if (messageSetting.value) maintenanceMessage.value = messageSetting.value.value;
}

// --- Maintenance Mode Actions ---
async function saveMaintenanceSettings() {
    isSavingMaintenance.value = true;
    try {
        await adminStore.updateGlobalSettings({
            maintenance_mode: maintenanceMode.value,
            maintenance_message: maintenanceMessage.value
        });
        uiStore.addNotification('Maintenance settings updated.', 'success');
    } catch (e) {
        uiStore.addNotification('Failed to save maintenance settings.', 'error');
    } finally {
        isSavingMaintenance.value = false;
    }
}

// --- Server Actions ---

async function handleReboot() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Reboot Server?',
        message: 'This will restart the application process. All current connections will be dropped.',
        confirmText: 'Reboot Now',
        isDanger: true
    });
    
    if (confirmed.confirmed) {
        performServerAction('/api/admin/system/reboot', 'rebooting');
    }
}

async function handleUpdate() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Update & Restart?',
        message: 'This will pull the latest code from Git, reinstall dependencies, and restart the server. This may take several minutes.',
        confirmText: 'Update Now',
        isDanger: true
    });

    if (confirmed.confirmed) {
        performServerAction('/api/admin/system/update', 'updating');
    }
}

async function handlePurge() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Purge Temporary Files?',
        message: 'This will delete unused temporary uploads older than 24 hours. This is safe to run.',
        confirmText: 'Purge'
    });

    if (confirmed.confirmed) {
        try {
            await apiClient.post('/api/admin/purge-unused-uploads');
            uiStore.addNotification('Purge task started.', 'success');
        } catch (error) {
            uiStore.addNotification('Failed to start purge task.', 'error');
        }
    }
}

async function handlePruneTasks() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Prune Task History?',
        message: 'This will delete records of finished tasks older than the retention period (default 7 days).',
        confirmText: 'Prune'
    });

    if (confirmed.confirmed) {
        try {
            await apiClient.post('/api/admin/tasks/prune');
            uiStore.addNotification('Pruning task started.', 'success');
        } catch (error) {
            uiStore.addNotification('Failed to start pruning.', 'error');
        }
    }
}

async function handleBackup() {
    if (!backupPassword.value) {
        uiStore.addNotification('Please set a password for the backup archive.', 'warning');
        return;
    }

    try {
        await apiClient.post('/api/admin/backup/create', { password: backupPassword.value });
        uiStore.addNotification('Backup task started. Check the Tasks tab for progress.', 'success');
        backupPassword.value = ''; // Clear password
    } catch (error) {
        uiStore.addNotification('Failed to start backup.', 'error');
    }
}

// --- Helpers ---

async function performServerAction(endpoint, mode) {
    isActionInProgress.value = true;
    actionStatus.value = mode;
    
    try {
        // The server might not respond if it restarts immediately, so catch error but assume success if network fails
        try {
            await apiClient.post(endpoint, {}, { timeout: 5000 });
        } catch (e) {
            console.log("Server likely restarting...", e);
        }
        
        actionStatus.value = 'reconnecting';
        startPinging();
    } catch (error) {
        uiStore.addNotification(`Action failed: ${error.message}`, 'error');
        isActionInProgress.value = false;
        actionStatus.value = '';
    }
}

function startPinging() {
    if (pingInterval.value) clearInterval(pingInterval.value);
    
    // Wait 5 seconds before first ping to allow server to shut down
    setTimeout(() => {
        pingInterval.value = setInterval(async () => {
            try {
                // Try a lightweight public endpoint
                await apiClient.get('/api/public/version', { timeout: 2000 });
                
                // If successful, we are back!
                clearInterval(pingInterval.value);
                actionStatus.value = 'success';
                uiStore.addNotification('Server is back online!', 'success');
                
                // Reload page after a brief moment to refresh state
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } catch (e) {
                // Still down, keep waiting
                console.log("Waiting for server...");
            }
        }, 3000);
    }, 5000);
}

onUnmounted(() => {
    if (pingInterval.value) clearInterval(pingInterval.value);
});
</script>

<template>
    <div class="space-y-8">
        
        <!-- SECTION 1: MAINTENANCE MODE -->
        <div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-orange-200 dark:border-orange-900/50 overflow-hidden">
            <div class="p-6 bg-orange-50 dark:bg-orange-900/20 border-b border-orange-100 dark:border-orange-900/30">
                <div class="flex items-center gap-4">
                    <div class="p-3 bg-orange-100 dark:bg-orange-900/50 rounded-full text-orange-600">
                        <IconWrenchScrewdriver class="w-8 h-8" />
                    </div>
                    <div>
                        <h4 class="text-lg font-bold text-gray-900 dark:text-white">Maintenance Mode</h4>
                        <p class="text-sm text-gray-600 dark:text-gray-300">
                            Block access for non-admin users and show a maintenance page.
                        </p>
                    </div>
                    <div class="ml-auto">
                         <button @click="maintenanceMode = !maintenanceMode" type="button" :class="[maintenanceMode ? 'bg-orange-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-8 w-14 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out']">
                            <span :class="[maintenanceMode ? 'translate-x-6' : 'translate-x-0', 'pointer-events-none inline-block h-7 w-7 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Conditional Settings Area -->
            <div v-if="maintenanceMode || (maintenanceSetting && maintenanceMode !== maintenanceSetting.value)" class="p-6 space-y-4 animate-in fade-in slide-in-from-top-2">
                <div v-if="maintenanceMode">
                    <label class="block text-sm font-medium mb-1">Maintenance Message</label>
                    <textarea v-model="maintenanceMessage" rows="3" class="input-field w-full" placeholder="We are performing maintenance..."></textarea>
                    <p class="text-xs text-gray-500 mt-1">This message will be displayed to users on the splash screen.</p>
                </div>
                <div class="flex justify-end">
                    <button @click="saveMaintenanceSettings" class="btn btn-primary" :disabled="isSavingMaintenance">
                        {{ isSavingMaintenance ? 'Saving...' : 'Save Changes' }}
                    </button>
                </div>
            </div>
        </div>

        <!-- SECTION 2: SERVER CONTROL -->
        <div>
            <h3 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                <IconPower class="w-5 h-5 text-red-500"/> Server Control
            </h3>
            
            <!-- Progress Overlay (Only visible during Reboot/Update) -->
            <div v-if="isActionInProgress" class="flex flex-col items-center justify-center p-12 bg-gray-50 dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 text-center animate-fade-in mb-6">
                <div class="mb-6 relative">
                    <div v-if="actionStatus === 'success'" class="p-4 bg-green-100 dark:bg-green-900/30 rounded-full text-green-600">
                        <IconCheckCircle class="w-16 h-16" />
                    </div>
                    <div v-else class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-full text-blue-600 relative">
                        <IconServer class="w-16 h-16 opacity-50" />
                        <div class="absolute inset-0 flex items-center justify-center">
                            <IconAnimateSpin class="w-10 h-10 animate-spin text-blue-600" />
                        </div>
                    </div>
                </div>
                <h3 class="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                    <span v-if="actionStatus === 'rebooting'">Rebooting Server...</span>
                    <span v-if="actionStatus === 'updating'">Updating System...</span>
                    <span v-if="actionStatus === 'reconnecting'">Waiting for Connection...</span>
                    <span v-if="actionStatus === 'success'">Server Online!</span>
                </h3>
                <p class="text-gray-500 dark:text-gray-400 max-w-md">
                    <span v-if="actionStatus === 'rebooting'">The application process is restarting. This usually takes 5-10 seconds.</span>
                    <span v-if="actionStatus === 'updating'">Downloading updates and reinstalling requirements. This may take a few minutes.</span>
                    <span v-if="actionStatus === 'reconnecting'">The server is starting up. We are pinging it automatically.</span>
                    <span v-if="actionStatus === 'success'">Redirecting you to the dashboard...</span>
                </p>
            </div>

            <!-- Action Buttons -->
            <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- Reboot -->
                <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 flex flex-col items-start gap-4">
                    <div class="p-3 rounded-full bg-orange-100 dark:bg-orange-900/30 text-orange-600">
                        <IconRefresh class="w-8 h-8" />
                    </div>
                    <div>
                        <h4 class="text-lg font-bold text-gray-900 dark:text-white">Reboot Server</h4>
                        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                            Restarts the python application process. Useful for applying configuration changes or clearing memory leaks.
                        </p>
                    </div>
                    <button @click="handleReboot" class="btn btn-secondary w-full mt-auto">
                        Reboot Now
                    </button>
                </div>

                <!-- Update -->
                <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 flex flex-col items-start gap-4">
                    <div class="p-3 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-600">
                        <IconArrowDownTray class="w-8 h-8" />
                    </div>
                    <div>
                        <h4 class="text-lg font-bold text-gray-900 dark:text-white">Update & Restart</h4>
                        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">
                            Pulls latest code from Git, updates dependencies, and restarts. 
                            <span class="text-yellow-600 dark:text-yellow-500 font-semibold">Service will be unavailable during update.</span>
                        </p>
                    </div>
                    <button @click="handleUpdate" class="btn btn-primary w-full mt-auto">
                        Update System
                    </button>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <!-- MAINTENANCE SECTION -->
            <div>
                <h3 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                    <IconArchiveBox class="w-5 h-5 text-purple-500"/> Data Operations
                </h3>
                <div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 divide-y divide-gray-200 dark:divide-gray-700">
                    <div class="p-5 flex items-center justify-between">
                        <div>
                            <h4 class="font-medium text-gray-900 dark:text-white">Purge Temporary Files</h4>
                            <p class="text-xs text-gray-500 mt-1">Deletes uploads older than 24h that are not in use.</p>
                        </div>
                        <button @click="handlePurge" class="btn btn-secondary btn-sm flex items-center gap-2">
                            <IconTrash class="w-4 h-4"/> Purge
                        </button>
                    </div>
                    <div class="p-5 flex items-center justify-between">
                        <div>
                            <h4 class="font-medium text-gray-900 dark:text-white">Prune Task History</h4>
                            <p class="text-xs text-gray-500 mt-1">Cleans up logs from old completed/failed background tasks.</p>
                        </div>
                        <button @click="handlePruneTasks" class="btn btn-secondary btn-sm flex items-center gap-2">
                            <IconClock class="w-4 h-4"/> Prune
                        </button>
                    </div>
                </div>
            </div>

            <!-- BACKUP SECTION -->
            <div>
                <h3 class="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                    <IconLock class="w-5 h-5 text-green-500"/> Backup & Security
                </h3>
                <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
                    <h4 class="font-medium text-gray-900 dark:text-white mb-2">Create Secure Backup</h4>
                    <p class="text-sm text-gray-500 mb-4">
                        Creates an AES-256 encrypted zip archive of the `data/` folder (databases, configs, and personal files).
                    </p>
                    <div class="space-y-3">
                        <div>
                            <label class="text-xs font-medium text-gray-700 dark:text-gray-300">Archive Password</label>
                            <input 
                                type="password" 
                                v-model="backupPassword" 
                                class="input-field w-full mt-1" 
                                placeholder="Enter a strong password"
                            >
                        </div>
                        <button 
                            @click="handleBackup" 
                            :disabled="!backupPassword"
                            class="btn btn-primary w-full flex items-center justify-center gap-2"
                        >
                            <IconArrowDownTray class="w-4 h-4"/> Create Backup
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.animate-fade-in { animation: fadeIn 0.5s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
</style>
