<!-- [UPDATE] frontend/webui/src/components/admin/Operations.vue -->
<script setup>
import { ref, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import { storeToRefs } from 'pinia';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconWrenchScrewdriver from '../../assets/icons/IconWrenchScrewdriver.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const { adminAvailableLollmsModels, isLoadingLollmsModels } = storeToRefs(adminStore);
const { availableTtiModels, availableTtsModels, availableSttModels, availableItiModels } = storeToRefs(dataStore);

const isPurging = ref(false);
const isForcingConfig = ref(false);
const isRebuildingCache = ref(false);

const forceForm = ref({
    lollms_model_name: '',
    tti_binding_model_name: '',
    tts_binding_model_name: '',
    stt_binding_model_name: '',
    iti_binding_model_name: ''
});

onMounted(() => {
    adminStore.fetchAdminAvailableLollmsModels();
    dataStore.fetchAdminAvailableTtiModels();
    dataStore.fetchAdminAvailableTtsModels();
    dataStore.fetchAdminAvailableSttModels();
});

async function handlePurge() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Purge Temporary Files?',
        message: 'This will delete all temporary uploaded files older than 24 hours. This action cannot be undone.',
        confirmText: 'Yes, Purge'
    });
    if (confirmed.confirmed) {
        isPurging.value = true;
        try {
            await adminStore.purgeUnusedUploads();
            uiStore.addNotification('Purge task started.', 'info');
        } finally {
            isPurging.value = false;
        }
    }
}

async function handleRebuildZooCache() {
    isRebuildingCache.value = true;
    try {
        await adminStore.refreshZooCache();
        uiStore.addNotification('Zoo cache rebuild task started.', 'info');
    } finally {
        isRebuildingCache.value = false;
    }
}

async function handleForceAll() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Force Global Configuration?',
        message: 'This will instantly change the model settings for EVERY user in the system. Active sessions will be refreshed. Continue?',
        confirmText: 'Yes, Force All',
        isDanger: true
    });

    if (confirmed.confirmed) {
        isForcingConfig.value = true;
        try {
            // Only send fields that have a value
            const payload = Object.fromEntries(
                Object.entries(forceForm.value).filter(([_, v]) => v !== '')
            );
            
            if (Object.keys(payload).length === 0) {
                uiStore.addNotification('Please select at least one model to force.', 'warning');
                return;
            }

            await adminStore.forceAllUsersConfig(payload);
        } finally {
            isForcingConfig.value = false;
        }
    }
}
</script>

<template>
    <div class="space-y-8 pb-20">
        <!-- Force Config Tool -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg overflow-hidden border border-red-200 dark:border-red-900/30">
            <div class="p-6 bg-red-50 dark:bg-red-950/20 border-b border-red-200 dark:border-red-900/30">
                <div class="flex items-center gap-3">
                    <IconWrenchScrewdriver class="w-6 h-6 text-red-600 dark:text-red-400" />
                    <h3 class="text-xl font-bold text-red-900 dark:text-red-100">Force Global AI Configuration</h3>
                </div>
                <p class="mt-2 text-sm text-red-700 dark:text-red-300">
                    Instantly override the model settings for <b>every registered user</b>. Use this to migrate the whole server to new models or enforce specific bindings.
                </p>
            </div>
            
            <div class="p-6 space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <!-- LLM -->
                    <div>
                        <label class="block text-sm font-bold mb-1">Force LLM Model</label>
                        <select v-model="forceForm.lollms_model_name" class="input-field" :disabled="isLoadingLollmsModels">
                            <option value="">-- No Change --</option>
                            <option v-for="m in adminAvailableLollmsModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                        </select>
                    </div>

                    <!-- TTI -->
                    <div>
                        <label class="block text-sm font-bold mb-1">Force TTI (Images)</label>
                        <select v-model="forceForm.tti_binding_model_name" class="input-field">
                            <option value="">-- No Change --</option>
                            <option v-for="m in availableTtiModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                        </select>
                    </div>

                    <!-- TTS -->
                    <div>
                        <label class="block text-sm font-bold mb-1">Force TTS (Speech)</label>
                        <select v-model="forceForm.tts_binding_model_name" class="input-field">
                            <option value="">-- No Change --</option>
                            <option v-for="m in availableTtsModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                        </select>
                    </div>

                    <!-- STT -->
                    <div>
                        <label class="block text-sm font-bold mb-1">Force STT (Voice-to-Text)</label>
                        <select v-model="forceForm.stt_binding_model_name" class="input-field">
                            <option value="">-- No Change --</option>
                            <option v-for="m in availableSttModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                        </select>
                    </div>
                </div>

                <div class="flex justify-end pt-4 border-t dark:border-gray-700">
                    <button @click="handleForceAll" class="btn btn-danger flex items-center gap-2" :disabled="isForcingConfig">
                        <IconAnimateSpin v-if="isForcingConfig" class="w-5 h-5 animate-spin" />
                        <IconSparkles v-else class="w-5 h-5" />
                        Apply to All Users
                    </button>
                </div>
            </div>
        </div>

        <!-- Maintenance Operations -->
        <div class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
            <div class="p-6 border-b border-gray-200 dark:border-gray-700">
                <h3 class="text-xl font-semibold text-gray-900 dark:text-white">Maintenance Operations</h3>
            </div>
            
            <div class="divide-y divide-gray-200 dark:divide-gray-700">
                <!-- Purge -->
                <div class="p-6 flex items-center justify-between gap-4">
                    <div>
                        <h4 class="font-bold text-gray-800 dark:text-gray-200">Purge Unused Uploads</h4>
                        <p class="text-sm text-gray-500 dark:text-gray-400">Deletes temporary files older than 24 hours that aren't attached to active discussions.</p>
                    </div>
                    <button @click="handlePurge" class="btn btn-danger-outline whitespace-nowrap" :disabled="isPurging">
                         <IconAnimateSpin v-if="isPurging" class="w-4 h-4 mr-2 animate-spin" />
                        Start Purge
                    </button>
                </div>

                <!-- Rebuild Cache -->
                <div class="p-6 flex items-center justify-between gap-4">
                    <div>
                        <h4 class="font-bold text-gray-800 dark:text-gray-200">Refresh Zoo Cache</h4>
                        <p class="text-sm text-gray-500 dark:text-gray-400">Force a background rescan of all Zoo repositories to update metadata and availability.</p>
                    </div>
                    <button @click="handleRebuildZooCache" class="btn btn-secondary whitespace-nowrap" :disabled="isRebuildingCache">
                        <IconAnimateSpin v-if="isRebuildingCache" class="w-4 h-4 mr-2 animate-spin" />
                        <IconRefresh v-else class="w-4 h-4 mr-2" />
                        Refresh Zoo
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>
