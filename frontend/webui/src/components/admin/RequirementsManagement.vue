<script setup>
import { onMounted, computed, ref } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconError from '../../assets/icons/IconError.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconWrenchScrewdriver from '../../assets/icons/IconWrenchScrewdriver.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { systemRequirements, isLoadingRequirements } = storeToRefs(adminStore);
const searchTerm = ref('');
const installingPackage = ref(null);
const isFixingAll = ref(false);

onMounted(() => {
    adminStore.fetchRequirements();
});

const filteredRequirements = computed(() => {
    if (!searchTerm.value) return systemRequirements.value;
    const lowerQuery = searchTerm.value.toLowerCase();
    return systemRequirements.value.filter(req => req.name.toLowerCase().includes(lowerQuery));
});

const hasRequirementsToFix = computed(() => {
    return systemRequirements.value.some(req => req.status !== 'ok');
});

async function handleInstall(req, version) {
    installingPackage.value = req.name;
    try {
        await adminStore.installRequirement(req.name, version);
        uiStore.addNotification(`Installation task started for ${req.name}`, 'info');
    } catch (e) {
        console.error(e);
        uiStore.addNotification('Installation failed to start', 'error');
    } finally {
        installingPackage.value = null;
    }
}

async function handleFixAll() {
    if (!hasRequirementsToFix.value) {
        uiStore.addNotification('All requirements are already satisfied.', 'info');
        return;
    }

    isFixingAll.value = true;
    try {
        await adminStore.fixAllRequirements();
        uiStore.addNotification('Fix all requirements task started. Check tasks for progress.', 'info');
    } catch (e) {
        console.error(e);
        uiStore.addNotification('Failed to start fix all requirements task', 'error');
    } finally {
        isFixingAll.value = false;
    }
}

function getStatusColor(status) {
    switch (status) {
        case 'ok': return 'text-green-600 bg-green-100 dark:bg-green-900/30 dark:text-green-400';
        case 'newer': return 'text-orange-600 bg-orange-100 dark:bg-orange-900/30 dark:text-orange-400';
        case 'older': return 'text-red-600 bg-red-100 dark:bg-red-900/30 dark:text-red-400';
        case 'missing': return 'text-red-600 bg-red-100 dark:bg-red-900/30 dark:text-red-400';
        default: return 'text-gray-600 bg-gray-100 dark:bg-gray-700 dark:text-gray-400';
    }
}

function getStatusLabel(status) {
    switch (status) {
        case 'ok': return 'Match';
        case 'newer': return 'Newer';
        case 'older': return 'Outdated';
        case 'missing': return 'Missing';
        default: return 'Unknown';
    }
}

</script>

<template>
    <div class="space-y-6">
        <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
                <h3 class="text-xl font-bold text-gray-900 dark:text-white">System Requirements</h3>
                <p class="text-sm text-gray-500 dark:text-gray-400">Monitor and manage python dependencies.</p>
            </div>
            <div class="flex items-center gap-2">
                 <input
                    type="text"
                    v-model="searchTerm"
                    placeholder="Search libraries..."
                    class="input-field-sm w-48"
                />
                <button @click="adminStore.fetchRequirements()" class="btn btn-secondary btn-sm" :disabled="isLoadingRequirements">
                    <IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isLoadingRequirements}" /> Refresh
                </button>
                <button
                    @click="handleFixAll"
                    class="btn btn-primary btn-sm"
                    :disabled="isFixingAll || !hasRequirementsToFix"
                    title="Install correct versions for all requirements that are not satisfied"
                >
                    <IconWrenchScrewdriver v-if="!isFixingAll" class="w-4 h-4 mr-2" />
                    <IconAnimateSpin v-else class="w-4 h-4 mr-2 animate-spin" />
                    {{ isFixingAll ? 'Fixing...' : 'Fix All' }}
                </button>
            </div>
        </div>

        <div class="bg-white dark:bg-gray-800 shadow-sm rounded-lg overflow-hidden border dark:border-gray-700">
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead class="bg-gray-50 dark:bg-gray-700/50">
                        <tr>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Library</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Required</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Installed</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Status</th>
                            <th scope="col" class="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actions</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                        <tr v-if="isLoadingRequirements">
                            <td colspan="5" class="px-6 py-10 text-center text-gray-500">Loading requirements...</td>
                        </tr>
                        <tr v-else-if="filteredRequirements.length === 0">
                            <td colspan="5" class="px-6 py-10 text-center text-gray-500">No libraries found.</td>
                        </tr>
                        <tr v-else v-for="req in filteredRequirements" :key="req.name" class="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">{{ req.name }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400 font-mono">{{ req.required_version }}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400 font-mono">{{ req.installed_version }}</td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full" :class="getStatusColor(req.status)">
                                    {{ getStatusLabel(req.status) }}
                                </span>
                                <div v-if="req.status === 'newer'" class="text-[10px] text-orange-500 mt-1 flex items-center">
                                    <IconInfo class="w-3 h-3 mr-1"/> Potential incompatibility
                                </div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                <div class="flex justify-end gap-2">
                                     <button
                                        v-if="req.status !== 'ok' && req.required_version !== 'Any'"
                                        @click="handleInstall(req, req.required_version)"
                                        :disabled="installingPackage === req.name"
                                        class="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300 disabled:opacity-50"
                                        title="Install Required Version"
                                    >
                                        <IconAnimateSpin v-if="installingPackage === req.name" class="w-5 h-5 animate-spin" />
                                        <span v-else>Fix Version</span>
                                    </button>

                                    <button
                                        @click="handleInstall(req, null)"
                                        :disabled="installingPackage === req.name"
                                        class="text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-300 disabled:opacity-50 ml-2"
                                        title="Update to Latest (May be incompatible)"
                                    >
                                        <IconArrowDownTray class="w-5 h-5" />
                                    </button>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</template>
