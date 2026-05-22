<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconScissors from '../../assets/icons/IconScissors.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('artefactVersionManager'));
const artefactTitle = computed(() => modalData.value?.artefactTitle);
const discussionId = computed(() => modalData.value?.discussionId || discussionsStore.currentDiscussionId);

const history = ref([]);
const isLoading = ref(false);
const isActionRunning = ref(false);
const tagToRevert = ref('');

async function loadHistory() {
    if (!artefactTitle.value) return;
    isLoading.value = true;
    try {
        // Fetch rich commit log instead of basic history
        history.value = await discussionsStore.fetchArtefactLog(discussionId.value, artefactTitle.value);
    } catch (e) {
        // Fallback to basic history if log method fails
        history.value = await discussionsStore.fetchArtefactHistory(discussionId.value, artefactTitle.value);
    } finally {
        isLoading.value = false;
    }
}

async function handleRevertToTag() {
    if (!tagToRevert.value.trim() || !artefactTitle.value) return;
    isActionRunning.value = true;
    try {
        await discussionsStore.revertArtefactToTag({
            discussionId: discussionId.value,
            artefactTitle: artefactTitle.value,
            tag: tagToRevert.value.trim()
        });
        tagToRevert.value = '';
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

watch(artefactTitle, loadHistory, { immediate: true });

async function handleDeleteVersion(version) {
    const confirmed = await uiStore.showConfirmation({
        title: 'Delete Version',
        message: `Permanently delete version ${version}? This cannot be undone.`,
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

const formatDate = (iso) => new Date(iso).toLocaleString();
</script>

<template>
    <GenericModal modalName="artefactVersionManager" :title="`Manage Versions: ${artefactTitle}`" maxWidthClass="max-w-3xl">
        <template #body>
            <div class="space-y-4 p-1">
                <div class="flex items-center gap-4 bg-blue-50/50 dark:bg-blue-900/10 p-5 rounded-[2rem] border border-blue-100 dark:border-blue-800/30">
                    <div class="w-12 h-12 rounded-full bg-white dark:bg-gray-800 shadow-sm flex items-center justify-center shrink-0">
                        <IconRefresh class="w-6 h-6 text-blue-500" />
                    </div>
                    <div class="grow min-w-0">
                        <h4 class="text-sm font-bold text-gray-900 dark:text-gray-100 uppercase tracking-widest">History Optimization</h4>
                        <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">Version control allows you to re-baseline your document or purge unwanted revisions.</p>
                    </div>
                    <button @click="handleCleanup" class="btn btn-primary btn-sm px-6 h-10 shadow-lg shadow-blue-500/20" :disabled="isActionRunning || history.length < 5">
                        <IconScissors class="w-4 h-4 mr-2" />
                        Prune History
                    </button>
                </div>


                <!-- Tag & Bundle Operations Control Bar -->
                <div class="flex flex-col sm:flex-row items-center gap-3 bg-gray-50/50 dark:bg-gray-900/30 p-4 rounded-2xl border border-gray-150 dark:border-gray-800 shadow-inner">
                    <div class="grow relative w-full sm:w-auto">
                        <input 
                            v-model="tagToRevert" 
                            placeholder="Type tag to revert (e.g. stable-v1)..." 
                            class="w-full px-3 py-1.5 pl-8 text-xs bg-white dark:bg-gray-850 border border-gray-200 dark:border-gray-700 rounded-xl focus:outline-none focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 dark:text-white transition-all h-9" 
                        />
                        <div class="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none">
                            <IconGitBranch class="w-4 h-4 text-gray-400" />
                        </div>
                    </div>
                    <button 
                        @click="handleRevertToTag" 
                        :disabled="!tagToRevert.trim() || isActionRunning" 
                        class="px-4 py-1.5 text-xs font-semibold rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 transition-all border border-gray-200 dark:border-gray-700 h-9 w-full sm:w-auto flex items-center justify-center disabled:opacity-50"
                    >
                        Revert to Tag
                    </button>
                    <button 
                        @click="handleExportBundle" 
                        class="px-4 py-1.5 text-xs font-semibold rounded-lg bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 transition-all border border-gray-200 dark:border-gray-700 h-9 w-full sm:w-auto flex items-center justify-center gap-1.5 disabled:opacity-50" 
                        title="Export this complete multimodal bundle"
                    >
                        <IconArrowDownTray class="w-3.5 h-3.5" />
                        Export Bundle
                    </button>
                </div>
                <div v-if="isLoading" class="flex justify-center py-12">
                    <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
                </div>

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
                                        <div class="flex flex-wrap gap-1 mt-1" v-if="v.tags && v.tags.length > 0">
                                            <span v-for="tag in v.tags" :key="tag" class="px-1.5 py-0.5 bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400 rounded text-[9px] font-mono">
                                                {{ tag }}
                                            </span>
                                        </div>
                                    </div>
                                </td>
                                <td class="px-4 py-3 text-xs text-gray-500">{{ formatDate(v.created_at) }}</td>
                                <td class="px-4 py-3 text-xs font-mono text-gray-400">{{ v.size_chars || v.content_size || 0 }} chars</td>
                                <td class="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                                    <button 
                                        @click="handleSquashToTarget(v.version)" 
                                        class="p-1.5 rounded bg-blue-50 dark:bg-blue-900/30 text-blue-500 hover:bg-blue-100 dark:hover:bg-blue-800 transition-all" 
                                        title="Set as baseline (Delete others)"
                                    >
                                        <IconRefresh class="w-4 h-4" />
                                    </button>
                                    <button 
                                        v-if="!v.is_active"
                                        @click="handleDeleteVersion(v.version)" 
                                        class="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 opacity-0 group-hover:opacity-100 transition-opacity" 
                                        title="Delete specific version"
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
