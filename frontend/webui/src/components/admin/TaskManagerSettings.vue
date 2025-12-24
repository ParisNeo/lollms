<!-- [UPDATE] frontend/webui/src/components/admin/TaskManagerSettings.vue -->
<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const form = ref({
    tasks_auto_cleanup: true,
    tasks_retention_days: 7,
    com_hub_port: 8042
});

const isLoading = ref(false);
const isPruning = ref(false);
const hasChanges = ref(false);
let pristineState = '{}';

const taskSettings = computed(() => {
    return adminStore.globalSettings.filter(s => s.category === 'Task Manager');
});

onMounted(() => {
    if (adminStore.globalSettings.length === 0) {
        adminStore.fetchGlobalSettings();
    } else {
        populateForm();
    }
});

watch(() => adminStore.globalSettings, populateForm, { deep: true });

watch(form, (newValue) => {
    hasChanges.value = JSON.stringify(newValue) !== pristineState;
}, { deep: true });

function populateForm() {
    if (taskSettings.value.length > 0) {
        const settingsMap = taskSettings.value.reduce((acc, s) => {
            acc[s.key] = s.value;
            return acc;
        }, {});
        
        form.value = {
            tasks_auto_cleanup: settingsMap.tasks_auto_cleanup ?? true,
            tasks_retention_days: settingsMap.tasks_retention_days ?? 7,
            com_hub_port: settingsMap.com_hub_port ?? 8042
        };
        pristineState = JSON.stringify(form.value);
        hasChanges.value = false;
    }
}

async function handleSave() {
    isLoading.value = true;
    try {
        await adminStore.updateGlobalSettings({ ...form.value });
        uiStore.addNotification('Task Manager settings saved.', 'success');
    } finally {
        isLoading.value = false;
    }
}

async function triggerManualPrune() {
    if(!confirm("This will manually delete all finished tasks older than the current retention setting. Continue?")) return;
    
    isPruning.value = true;
    try {
        await apiClient.post('/api/admin/tasks/prune');
        uiStore.addNotification('Manual task pruning started.', 'info');
    } catch (e) {
        uiStore.addNotification('Failed to trigger pruning.', 'error');
    } finally {
        isPruning.value = false;
    }
}
</script>

<template>
    <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
        <div class="p-6 border-b border-gray-200 dark:border-gray-700">
            <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                Task Manager Configuration
            </h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Configure how the system handles background task history and inter-worker synchronization.
            </p>
        </div>
        
        <form @submit.prevent="handleSave" class="p-6">
            <div class="space-y-8">
                <!-- Auto-cleanup Toggle -->
                <div class="toggle-container">
                    <span class="toggle-label">
                        Automated Daily Cleanup
                        <span class="toggle-description">Enable background deletion of old finished task records (Runs daily at 4:00 AM).</span>
                    </span>
                    <button @click="form.tasks_auto_cleanup = !form.tasks_auto_cleanup" type="button" :class="[form.tasks_auto_cleanup ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'toggle-switch']">
                        <span :class="[form.tasks_auto_cleanup ? 'translate-x-5' : 'translate-x-0', 'toggle-knob']"></span>
                    </button>
                </div>

                <!-- Retention Days -->
                <div>
                    <label for="retention-days" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Finished Task Retention (Days)</label>
                    <input 
                        id="retention-days" 
                        v-model.number="form.tasks_retention_days" 
                        type="number" 
                        min="1"
                        max="365"
                        class="input-field mt-1" 
                    />
                    <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Tasks in 'completed', 'failed', or 'cancelled' status older than this value will be purged.</p>
                </div>

                <!-- Hub Port -->
                <div class="pt-6 border-t dark:border-gray-600">
                    <h4 class="text-lg font-medium mb-4">Worker Synchronization</h4>
                    <div>
                        <label for="hub-port" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Communication Hub Port</label>
                        <input 
                            id="hub-port" 
                            v-model.number="form.com_hub_port" 
                            type="number" 
                            min="1024"
                            max="65535"
                            class="input-field mt-1" 
                        />
                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">The internal port used for pushing updates between LoLLMs worker processes. Requires a restart to change.</p>
                    </div>
                </div>

                <!-- Manual Maintenance -->
                <div class="pt-6 border-t dark:border-gray-600">
                    <h4 class="text-lg font-medium mb-4">Manual Maintenance</h4>
                    <div class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg flex items-center justify-between">
                        <div>
                            <p class="text-sm font-medium text-gray-900 dark:text-white">Trigger Pruning Now</p>
                            <p class="text-xs text-gray-500">Run the cleanup logic immediately instead of waiting for the schedule.</p>
                        </div>
                        <button type="button" @click="triggerManualPrune" class="btn btn-secondary btn-sm" :disabled="isPruning">
                            <IconAnimateSpin v-if="isPruning" class="w-4 h-4 mr-2 animate-spin" />
                            <IconTrash v-else class="w-4 h-4 mr-2" />
                            Prune Old Tasks
                        </button>
                    </div>
                </div>
            </div>

            <!-- Footer Actions -->
            <div class="mt-8 pt-5 border-t border-gray-200 dark:border-gray-700 flex justify-end">
                <button type="submit" class="btn btn-primary" :disabled="isLoading || !hasChanges">
                    <IconAnimateSpin v-if="isLoading" class="w-5 h-5 mr-2 animate-spin" />
                    {{ isLoading ? 'Saving...' : 'Save Configuration' }}
                </button>
            </div>
        </form>
    </div>
</template>

<style scoped>
.toggle-container { @apply flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg; }
.toggle-label { @apply flex-grow flex flex-col text-sm font-medium text-gray-900 dark:text-gray-100; }
.toggle-description { @apply text-xs text-gray-500 dark:text-gray-400 font-normal mt-1; }
.toggle-switch { @apply relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500; }
.toggle-knob { @apply pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out; }
</style>
