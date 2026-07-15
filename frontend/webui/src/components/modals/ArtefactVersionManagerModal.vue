<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconScissors from '../../assets/icons/IconScissors.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('artefactVersionManager'));
const artefactTitle = computed(() => modalData.value?.artefactTitle);
const discussionId = computed(() => modalData.value?.discussionId || discussionsStore.currentDiscussionId);

const history = ref([]);
const isLoading = ref(false);
const isActionRunning = ref(false);

async function loadHistory() {
    if (!artefactTitle.value) return;
    isLoading.value = true;
    try {
        // Fetch detailed version and commit history
        history.value = await discussionsStore.fetchArtefactLog(discussionId.value, artefactTitle.value);
    } catch (e) {
        // Fallback to basic history list
        history.value = await discussionsStore.fetchArtefactHistory(discussionId.value, artefactTitle.value);
    } finally {
        isLoading.value = false;
    }
}

async function handleActivateVersion(version) {
    isActionRunning.value = true;
    try {
        await discussionsStore.updateArtefactVisibility({
            discussionId: discussionId.value,
            artefactTitle: artefactTitle.value,
            visibility: 'FULL',
            version: version
        });
        await loadHistory();
        uiStore.addNotification(`Version ${version} set as active.`, 'success');
    } catch (e) {
        console.error(e);
    } finally {
        isActionRunning.value = false;
    }
}

watch(artefactTitle, loadHistory, { immediate: true });

async function handleDeleteVersion(version, isActive) {
    let confirmMsg = `Are you sure you want to permanently delete version ${version}? This action cannot be undone.`;
    if (isActive) {
        confirmMsg = `⚠️ WARNING: You are deleting the CURRENT ACTIVE version. If you delete it, the system will automatically promote the previous highest version to be the active one. Do you wish to proceed?`;
    }

    const confirmed = await uiStore.showConfirmation({
        title: isActive ? 'Delete Active Version' : 'Delete Version',
        message: confirmMsg,
        confirmText: 'Delete',
        danger: true
    });
    
    if (confirmed.confirmed) {
        isActionRunning.value = true;
        try {
            await discussionsStore.deleteArtefactVersion({ 
                discussionId: discussionId.value, 
                artefactTitle: artefactTitle.value, 
                version 
            });
            await loadHistory();
            uiStore.addNotification(`Version ${version} deleted successfully.`, 'success');
        } finally {
            isActionRunning.value = false;
        }
    }
}

async function handleSquashToTarget(version) {
    const confirmed = await uiStore.showConfirmation({
        title: 'Squash History',
        message: `Delete ALL other versions and make version ${version} the new baseline (v1)?`,
        confirmText: 'Squash All',
        danger: true
    });
    if (confirmed.confirmed) {
        isActionRunning.value = true;
        try {
            await discussionsStore.squashArtefactVersions({
                discussionId: discussionId.value,
                artefactTitle: artefactTitle.value,
                params: { target_version: version }
            });
            await loadHistory();
        } finally {
            isActionRunning.value = false;
        }
    }
}

async function handleCleanup() {
    isActionRunning.value = true;
    try {
        await discussionsStore.squashArtefactVersions({
            discussionId: discussionId.value,
            artefactTitle: artefactTitle.value,
            params: { keep_last_n: 5 }
        });
        await loadHistory();
    } finally {
        isActionRunning.value = false;
    }
}

async function handleExportBundle() {
    if (!artefactTitle.value) return;
    await discussionsStore.exportArtefactBundle({
        discussionId: discussionId.value,
        artefactTitle: artefactTitle.value
    });
}

const formatDate = (iso) => {
    if (!iso) return 'Unknown';
    return new Date(iso).toLocaleString();
};
</script>

<template>
    <GenericModal modalName="artefactVersionManager" :title="`Version History: ${artefactTitle}`" maxWidthClass="max-w-4xl">
        <template #body>
            <div class="space-y-4 p-1">
                <!-- Top Info Section -->
                <div class="flex items-center gap-4 bg-blue-50/50 dark:bg-blue-900/10 p-5 rounded-[2rem] border border-blue-100 dark:border-blue-800/30">
                    <div class="w-12 h-12 rounded-full bg-white dark:bg-gray-800 shadow-sm flex items-center justify-center shrink-0">
                        <IconRefresh class="w-6 h-6 text-blue-500" />
                    </div>
                    <div class="grow min-w-0">
                        <h4 class="text-sm font-bold text-gray-900 dark:text-gray-100 uppercase tracking-widest">History Optimization</h4>
                        <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Version control allows you to re-baseline your document, set old versions as active, or purge unwanted revisions.</p>
                    </div>
                    <button @click="handleCleanup" class="btn btn-primary btn-sm px-6 h-10 shadow-lg shadow-blue-500/20" :disabled="isActionRunning || history.length < 5">
                        <IconScissors class="w-4 h-4 mr-2" />
                        Prune History
                    </button>
                </div>

                <!-- Export Options -->
                <div class="flex justify-end">
                    <button 
                        @click="handleExportBundle" 
                        class="px-4 py-1.5 text-xs font-semibold rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 transition-all border border-gray-200 dark:border-gray-700 h-9 flex items-center gap-1.5" 
                    >
                        <IconArrowDownTray class="w-3.5 h-3.5" />
                        Export .laa Bundle
                    </button>
                </div>

                <!-- Loading State -->
                <div v-if="isLoading" class="flex justify-center py-12">
                    <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
                </div>

                <!-- History Table -->
                <div v-else class="overflow-hidden border dark:border-gray-700 rounded-xl bg-white dark:bg-gray-900">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-gray-50 dark:bg-gray-800 text-[10px] font-black uppercase tracking-widest text-gray-400">
                            <tr>
                                <th class="px-4 py-3">Version</th>
                                <th class="px-4 py-3">Commit & Tags</th>
                                <th class="px-4 py-3">Created</th>
                                <th class="px-4 py-3">Size</th>
                                <th class="px-4 py-3 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y dark:divide-gray-800">
                            <tr v-for="v in history" :key="v.version" class="group hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                                <td class="px-4 py-3">
                                    <div class="flex items-center gap-2">
                                        <span class="font-mono font-bold">v{{ v.version }}</span>
                                        <span v-if="v.is_active" class="px-1.5 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-[9px] font-black uppercase">Active</span>
                                    </div>
                                </td>
                                <td class="px-4 py-3 text-xs">
                                    <div class="flex flex-col gap-1 max-w-sm">
                                        <span class="font-mono text-gray-400 dark:text-gray-500 text-[10px]" v-if="v.commit_hash">
                                            Hash: {{ v.commit_hash.slice(0, 8) }}
                                        </span>
                                        <span class="font-medium text-gray-700 dark:text-gray-300 italic" v-if="v.commit_message">
                                            "{{ v.commit_message }}"
                                        </span>
                                    </div>
                                </td>
                                <td class="px-4 py-3 text-xs text-gray-500">{{ formatDate(v.created_at) }}</td>
                                <td class="px-4 py-3 text-xs font-mono text-gray-400">{{ v.size_chars || v.content_size || 0 }} chars</td>
                                <td class="px-4 py-3 text-right space-x-1.5 whitespace-nowrap">
                                    <!-- Activate Action -->
                                    <button 
                                        v-if="!v.is_active"
                                        @click="handleActivateVersion(v.version)"
                                        :disabled="isActionRunning"
                                        class="p-1.5 rounded bg-green-50 dark:bg-green-900/30 text-green-600 hover:bg-green-100 dark:hover:bg-green-800 transition-all text-xs font-bold"
                                        title="Make Active Version"
                                    >
                                        Activate
                                    </button>
                                    
                                    <!-- Active Confirmation Indicator -->
                                    <span v-else class="inline-flex items-center gap-1 p-1.5 text-xs text-green-500 font-bold bg-green-500/10 rounded">
                                        <IconCheckCircle class="w-3.5 h-3.5" />
                                        Active
                                    </span>

                                    <!-- Squash Baseline Action -->
                                    <button 
                                        @click="handleSquashToTarget(v.version)" 
                                        :disabled="isActionRunning"
                                        class="p-1.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-500 hover:bg-blue-100 dark:hover:bg-blue-800 transition-all" 
                                        title="Set as baseline (Delete others)"
                                    >
                                        <IconRefresh class="w-4 h-4" />
                                    </button>

                                    <!-- Delete Action (Allowed for all, with auto-fallback) -->
                                    <button 
                                        @click="handleDeleteVersion(v.version, v.is_active)" 
                                        :disabled="isActionRunning"
                                        class="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 transition-opacity" 
                                        title="Delete this version"
                                    >
                                        <IconTrash class="w-4 h-4" />
                                    </button>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('artefactVersionManager')" class="btn btn-primary px-8">Done</button>
        </template>
    </GenericModal>
</template>
```