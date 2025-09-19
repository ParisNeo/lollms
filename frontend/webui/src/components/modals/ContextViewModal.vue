<script setup>
import { computed, ref } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import { storeToRefs } from 'pinia';
import GenericModal from './GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();
const { activeDiscussionContextStatus: contextStatus } = storeToRefs(discussionsStore);
const isRefreshing = ref(false);

const formatZoneName = (name) => name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
const formatNumber = (num) => num ? num.toLocaleString() : '0';

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
    const zones = Object.entries(contextStatus.value.zones);
    const order = ['system_context', 'message_history'];
    return zones.sort(([keyA], [keyB]) => order.indexOf(keyA) - order.indexOf(keyB));
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
                        <div class="p-4 border-t dark:border-gray-700 space-y-3">
                            <!-- System Context Breakdown -->
                            <template v-if="zoneKey === 'system_context' && typeof zoneData.breakdown === 'object' && zoneData.breakdown">
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
                            </template>
                            <!-- Message History Breakdown -->
                            <template v-else-if="zoneKey === 'message_history' && zoneData.breakdown">
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                                    <div class="p-3 bg-white dark:bg-gray-800 border dark:border-gray-600 rounded-md flex items-center gap-3">
                                        <IconFileText class="w-6 h-6 text-blue-500 flex-shrink-0" />
                                        <div><div class="font-semibold">Text Tokens</div><div class="font-mono text-gray-600 dark:text-gray-400">{{ formatNumber(zoneData.breakdown.text_tokens) }}</div></div>
                                    </div>
                                    <div class="p-3 bg-white dark:bg-gray-800 border dark:border-gray-600 rounded-md flex items-center gap-3">
                                        <IconPhoto class="w-6 h-6 text-green-500 flex-shrink-0" />
                                        <div><div class="font-semibold">Image Tokens</div><div class="font-mono text-gray-600 dark:text-gray-400">{{ formatNumber(zoneData.breakdown.image_tokens) }}</div></div>
                                    </div>
                                </div>
                                <details v-if="zoneData.breakdown.image_details && zoneData.breakdown.image_details.length > 0" class="bg-white dark:bg-gray-800 border dark:border-gray-600 rounded-md">
                                    <summary class="flex items-center justify-between p-2 cursor-pointer select-none">
                                        <div class="flex items-center gap-2"><IconChevronRight class="w-4 h-4 text-gray-400 transition-transform details-arrow" /><h4 class="text-sm font-medium">Image Details</h4></div>
                                    </summary>
                                    <div class="p-2 border-t dark:border-gray-600 max-h-60 overflow-y-auto">
                                        <ul class="text-xs font-mono divide-y dark:divide-gray-700">
                                            <li v-for="img in zoneData.breakdown.image_details" :key="`${img.message_id}-${img.index}`" class="py-1.5 flex justify-between items-center">
                                                <span>Msg: {{ img.message_id.substring(0, 8) }}... (Img #{{ img.index + 1 }})</span>
                                                <span class="font-semibold">{{ formatNumber(img.tokens) }} tokens</span>
                                            </li>
                                        </ul>
                                    </div>
                                </details>
                            </template>
                             <!-- Fallback for other zones -->
                            <div v-else class="flex items-start gap-3 p-3 bg-white dark:bg-gray-800 border dark:border-gray-600 rounded-md">
                                <IconInfo class="w-5 h-5 mt-0.5 text-gray-500 flex-shrink-0" />
                                <p class="text-sm text-gray-700 dark:text-gray-300">This zone contains the full text content, which is used for context but has no further breakdown available.</p>
                            </div>
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
                    <IconAnimateSpin v-if="isRefreshing" class="w-4 h-4 mr-2" />
                    <IconRefresh v-else class="w-4 h-4 mr-2" />
                    {{ isRefreshing ? 'Refreshing...' : 'Refresh' }}
                </button>
                <button @click="uiStore.closeModal('contextViewer')" class="btn btn-primary">Close</button>
            </div>
        </template>
    </GenericModal>
</template>

<style scoped>
details > summary { list-style: none; }
details > summary::-webkit-details-marker { display: none; }
details[open] > summary .details-arrow { transform: rotate(90deg); }
</style>