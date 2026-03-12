<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';

// Icons
import IconToken from '../../assets/icons/IconToken.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconHistory from '../../assets/icons/IconClock.vue'; // Using clock for history
import IconFolder from '../../assets/icons/IconFolder.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const status = computed(() => discussionsStore.activeDiscussionContextStatus);

// Constants from documentation
const IMAGE_TOKEN_COST = 256;

// --- Data Mapping ---

const systemBreakdown = computed(() => status.value?.zones?.system_context?.breakdown || {});
const historyBreakdown = computed(() => status.value?.zones?.message_history?.breakdown || {});

const usagePercent = computed(() => status.value?.percent || 0);

/**
 * Helper to generate a flat list for the visual progress bar
 */
const progressParts = computed(() => {
    if (!status.value) return [];
    const b = systemBreakdown.value;
    const h = historyBreakdown.value;
    
    return [
        { label: 'System', val: b.system_prompt?.tokens, color: 'bg-indigo-500' },
        { label: 'Memory', val: b.memory?.tokens, color: 'bg-teal-500' },
        { label: 'Instructions', val: b.user_data_zone?.tokens + b.discussion_data_zone?.tokens, color: 'bg-amber-500' },
        { label: 'Artefacts', val: b.artefacts?.tokens, color: 'bg-blue-500' },
        { label: 'History', val: h.text_tokens, color: 'bg-green-500' },
        { label: 'Images', val: h.image_tokens + (status.value.zones.discussion_images?.tokens || 0), color: 'bg-cyan-500' },
        { label: 'Scratchpad', val: b.scratchpad?.tokens, color: 'bg-orange-400' },
    ].filter(p => p.val > 0);
});

function formatTokens(val) {
    return (val || 0).toLocaleString();
}
</script>

<template>
    <GenericModal modalName="contextViewer" title="Context Diagnostic" maxWidthClass="max-w-4xl">
        <template #body>
            <div class="space-y-6" v-if="status">
                
                <!-- Visual Summary Card -->
                <div class="p-6 bg-white dark:bg-gray-800 rounded-3xl border dark:border-gray-700 shadow-xl overflow-hidden relative">
                    <div class="flex justify-between items-end mb-6">
                        <div class="space-y-1">
                            <h3 class="text-2xl font-black tracking-tighter dark:text-white">
                                {{ formatTokens(status.current_tokens) }} 
                                <span class="text-gray-400 font-medium text-lg">/ {{ formatTokens(status.max_tokens) }}</span>
                            </h3>
                            <p class="text-[10px] font-black uppercase tracking-widest text-blue-500">Total Context Allocation</p>
                        </div>
                        <div class="text-right">
                            <span class="text-4xl font-black italic opacity-20" :class="usagePercent > 80 ? 'text-red-500 opacity-100' : ''">
                                {{ usagePercent.toFixed(0) }}%
                            </span>
                        </div>
                    </div>

                    <!-- Layered Progress Bar -->
                    <div class="h-6 w-full bg-gray-100 dark:bg-gray-900 rounded-xl overflow-hidden flex border-2 border-gray-100 dark:border-gray-700">
                        <div v-for="part in progressParts" :key="part.label"
                             :class="[part.color, 'h-full transition-all duration-1000 border-r border-black/5 last:border-0']"
                             :style="{ width: `${(part.val / status.max_tokens) * 100}%` }"
                             :title="`${part.label}: ${part.val} tokens`"
                        ></div>
                    </div>

                    <!-- Pressure Warning -->
                    <div v-if="usagePercent > 80" class="mt-4 flex items-center gap-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800 rounded-xl animate-pulse">
                        <IconInfo class="w-5 h-5 text-red-500 flex-shrink-0" />
                        <span class="text-xs font-bold text-red-700 dark:text-red-300 uppercase tracking-tight">Warning: High Context Pressure. Auto-pruning imminent.</span>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    
                    <!-- 1. Directives & Knowledge -->
                    <div class="space-y-3">
                        <h4 class="px-2 text-[10px] font-black uppercase tracking-[0.2em] text-gray-400">Directives & Knowledge</h4>
                        <div class="space-y-2">
                            <div class="stat-row bg-indigo-50/30 dark:bg-indigo-900/10 border-indigo-100 dark:border-indigo-800">
                                <span class="label">System Prompt</span>
                                <span class="value">{{ formatTokens(systemBreakdown.system_prompt?.tokens) }}</span>
                            </div>
                            <div class="stat-row bg-teal-50/30 dark:bg-teal-900/10 border-teal-100 dark:border-teal-800">
                                <span class="label">User Memory Bank</span>
                                <span class="value">{{ formatTokens(systemBreakdown.memory?.tokens) }}</span>
                            </div>
                            <div class="stat-row bg-amber-50/30 dark:bg-amber-900/10 border-amber-100 dark:border-amber-800">
                                <span class="label">Task & Prefs (Zones)</span>
                                <span class="value">{{ formatTokens(systemBreakdown.user_data_zone?.tokens + systemBreakdown.discussion_data_zone?.tokens) }}</span>
                            </div>
                            <div v-if="systemBreakdown.pruning_summary?.tokens" class="stat-row bg-rose-50/30 dark:bg-rose-900/10 border-rose-100 dark:border-rose-800">
                                <span class="label">Compression Summary</span>
                                <span class="value">{{ formatTokens(systemBreakdown.pruning_summary?.tokens) }}</span>
                            </div>
                        </div>
                    </div>

                    <!-- 2. Active Workspace (Artefacts) -->
                    <div class="space-y-3">
                        <h4 class="px-2 text-[10px] font-black uppercase tracking-[0.2em] text-gray-400">Workspace Artefacts</h4>
                        <div class="p-4 bg-blue-50/30 dark:bg-blue-900/10 border border-blue-100 dark:border-blue-800 rounded-2xl">
                            <div class="flex justify-between items-center mb-4">
                                <span class="text-sm font-bold text-blue-700 dark:text-blue-300">Active Files</span>
                                <span class="font-mono font-bold text-blue-600">{{ formatTokens(systemBreakdown.artefacts?.tokens) }} tok</span>
                            </div>
                            <div class="space-y-3">
                                <div v-for="(data, type) in systemBreakdown.artefacts?.types" :key="type" class="flex items-center gap-3">
                                    <div class="w-2 h-2 rounded-full bg-blue-400"></div>
                                    <span class="text-xs capitalize flex-grow font-medium text-gray-600 dark:text-gray-400">{{ type }}s ({{ data.count }})</span>
                                    <div class="h-1.5 w-20 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                        <div class="h-full bg-blue-500" :style="{ width: `${(data.tokens / systemBreakdown.artefacts.tokens) * 100}%` }"></div>
                                    </div>
                                    <span class="text-[10px] font-mono text-gray-500 w-10 text-right">{{ formatTokens(data.tokens) }}</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 3. Message History -->
                    <div class="space-y-3 md:col-span-2">
                        <h4 class="px-2 text-[10px] font-black uppercase tracking-[0.2em] text-gray-400">Conversation History</h4>
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <div class="p-4 bg-green-50/30 dark:bg-green-900/10 border border-green-100 dark:border-green-800 rounded-2xl flex flex-col items-center text-center">
                                <IconHistory class="w-5 h-5 text-green-600 mb-2" />
                                <span class="text-[10px] font-black uppercase text-gray-400 mb-1">Messages</span>
                                <span class="text-xl font-black text-green-700 dark:text-green-400">{{ historyBreakdown.message_count }}</span>
                            </div>
                            <div class="p-4 bg-green-50/30 dark:bg-green-900/10 border border-green-100 dark:border-green-800 rounded-2xl flex flex-col items-center text-center">
                                <IconFileText class="w-5 h-5 text-green-600 mb-2" />
                                <span class="text-[10px] font-black uppercase text-gray-400 mb-1">Text Data</span>
                                <span class="text-xl font-black text-green-700 dark:text-green-400">{{ formatTokens(historyBreakdown.text_tokens) }}</span>
                            </div>
                            <div class="p-4 bg-cyan-50/30 dark:bg-cyan-900/10 border border-cyan-100 dark:border-cyan-800 rounded-2xl flex flex-col items-center text-center">
                                <IconPhoto class="w-5 h-5 text-cyan-600 mb-2" />
                                <span class="text-[10px] font-black uppercase text-gray-400 mb-1">Vision Tokens</span>
                                <span class="text-xl font-black text-cyan-700 dark:text-cyan-400">{{ formatTokens(historyBreakdown.image_tokens + (status.zones.discussion_images?.tokens || 0)) }}</span>
                                <p class="text-[8px] text-gray-400 mt-1 uppercase tracking-widest">{{ IMAGE_TOKEN_COST }} tok per image</p>
                            </div>
                        </div>
                    </div>

                    <!-- 4. Transient Data (Scratchpad) -->
                    <div v-if="systemBreakdown.scratchpad?.tokens" class="space-y-3 md:col-span-2">
                        <div class="p-4 bg-orange-50/30 dark:bg-orange-900/10 border border-orange-100 dark:border-orange-800 rounded-2xl flex items-center justify-between">
                            <div class="flex items-center gap-3">
                                <div class="p-2 bg-orange-500 text-white rounded-lg"><IconSparkles class="w-4 h-4" /></div>
                                <div>
                                    <h5 class="text-sm font-bold text-orange-700 dark:text-orange-400 leading-none">Agentic Scratchpad</h5>
                                    <p class="text-[10px] text-gray-500 mt-1 uppercase tracking-widest">Volatile Tool Results & Thoughts</p>
                                </div>
                            </div>
                            <span class="text-xl font-black font-mono text-orange-600">{{ formatTokens(systemBreakdown.scratchpad.tokens) }}</span>
                        </div>
                    </div>

                </div>
            </div>
        </template>
        <template #footer>
            <div class="w-full flex justify-between px-4">
                <p class="text-[10px] text-gray-400 italic self-center">Values are calculated in real-time before each generation turn.</p>
                <button @click="uiStore.closeModal('contextViewer')" class="btn btn-primary px-8">Close Analysis</button>
            </div>
        </template>
    </GenericModal>
</template>

<style scoped>
.stat-row {
    @apply flex items-center justify-between p-3 rounded-xl border transition-all;
}
.stat-row .label {
    @apply text-xs font-bold text-gray-700 dark:text-gray-300;
}
.stat-row .value {
    @apply font-mono text-xs font-black text-blue-500;
}
</style>