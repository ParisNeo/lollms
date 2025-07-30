<script setup>
import { computed, ref } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import { storeToRefs } from 'pinia';
import GenericModal from '../ui/GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();
const { activeDiscussionContextStatus: contextStatus, activeDiscussion } = storeToRefs(discussionsStore);
const isRefreshing = ref(false);

const formatZoneName = (name) => {
    return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
};

const formatNumber = (num) => {
    return num ? num.toLocaleString() : '0';
};

const totalTokens = computed(() => contextStatus.value?.current_tokens || 0);
const maxTokens = computed(() => contextStatus.value?.max_tokens || 1);
const totalPercentage = computed(() => {
    if (maxTokens.value <= 0) return 0;
    return (totalTokens.value / maxTokens.value) * 100;
});
const progressColorClass = computed(() => {
    const percentage = totalPercentage.value;
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 75) return 'bg-yellow-500';
    return 'bg-blue-500';
});

const sortedZones = computed(() => {
    if (!contextStatus.value?.zones) return [];
    return Object.entries(contextStatus.value.zones).sort(([keyA], [keyB]) => {
        if (keyA === 'system_context') return -1;
        if (keyB === 'system_context') return 1;
        return 0;
    });
});

async function refreshContext() {
    if (discussionsStore.activeDiscussion && !isRefreshing.value) {
        isRefreshing.value = true;
        try {
            await discussionsStore.fetchContextStatus(discussionsStore.activeDiscussion.id);
        } finally {
            isRefreshing.value = false;
        }
    }
}
</script>

<template>
    <GenericModal modal-name="contextViewer" title="Context Breakdown" maxWidthClass="max-w-4xl">
        <template #body>
            <div v-if="contextStatus" class="space-y-6">
                <!-- Overall Progress Bar -->
                <div>
                    <div class="flex justify-between items-center mb-1 text-sm font-mono text-gray-700 dark:text-gray-300">
                        <span>Total Tokens</span>
                        <span>{{ formatNumber(totalTokens) }} / {{ formatNumber(maxTokens) }}</span>
                    </div>
                    <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4 relative overflow-hidden">
                        <div class="h-full rounded-full transition-all duration-300" 
                             :class="progressColorClass" 
                             :style="{ width: `${Math.min(totalPercentage, 100)}%` }">
                        </div>
                    </div>
                </div>

                <!-- Zones -->
                <div class="space-y-4">
                    <details v-for="([zoneKey, zoneData]) in sortedZones" :key="zoneKey" class="bg-gray-50 dark:bg-gray-800/50 border dark:border-gray-700 rounded-lg" open>
                        <summary class="flex items-center justify-between p-3 cursor-pointer select-none">
                            <div class="flex items-center gap-3">
                                <IconChevronRight class="w-5 h-5 text-gray-500 transition-transform details-arrow" />
                                <h3 class="font-semibold text-gray-800 dark:text-gray-200">{{ formatZoneName(zoneKey) }}</h3>
                                <span v-if="zoneData.message_count" class="text-xs text-gray-500">({{ zoneData.message_count }} messages)</span>
                            </div>
                            <span class="font-mono text-sm text-gray-600 dark:text-gray-400">{{ formatNumber(zoneData.tokens) }} tokens</span>
                        </summary>
                        <div class="p-4 border-t dark:border-gray-700">
                            <!-- Breakdown for System Context -->
                            <div v-if="zoneData.breakdown" class="space-y-3">
                                <details v-for="([breakdownKey, breakdownData]) in Object.entries(zoneData.breakdown)" :key="breakdownKey" class="bg-white dark:bg-gray-800 border dark:border-gray-600 rounded-md">
                                    <summary class="flex items-center justify-between p-2 cursor-pointer select-none">
                                        <div class="flex items-center gap-2">
                                            <IconChevronRight class="w-4 h-4 text-gray-400 transition-transform details-arrow" />
                                            <h4 class="text-sm font-medium">{{ formatZoneName(breakdownKey) }}</h4>
                                        </div>
                                        <span class="font-mono text-xs text-gray-500 dark:text-gray-400">{{ formatNumber(breakdownData.tokens) }} tokens</span>
                                    </summary>
                                    <div class="p-2 border-t dark:border-gray-600">
                                        <CodeMirrorEditor :model-value="breakdownData.content" :options="{ readOnly: true }" class="text-xs max-h-60" />
                                    </div>
                                </details>
                            </div>
                            <!-- Full Content for other zones -->
                            <CodeMirrorEditor v-else :model-value="zoneData.content" :options="{ readOnly: true }" class="text-xs max-h-96" />
                        </div>
                    </details>
                </div>
            </div>
            <div v-else class="text-center py-10">
                <p class="text-gray-500">Context information is not available.</p>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-between items-center w-full">
                <button @click="refreshContext" class="btn btn-secondary" :disabled="isRefreshing">
                    <IconRefresh class="w-4 h-4 mr-2" :class="{'animate-spin': isRefreshing}" />
                    {{ isRefreshing ? 'Refreshing...' : 'Refresh' }}
                </button>
                <button @click="uiStore.closeModal('contextViewer')" class="btn btn-primary">Close</button>
            </div>
        </template>
    </GenericModal>
</template>

<style scoped>
details > summary {
  list-style: none;
}
details > summary::-webkit-details-marker {
  display: none;
}
details[open] > summary .details-arrow {
  transform: rotate(90deg);
}
</style>