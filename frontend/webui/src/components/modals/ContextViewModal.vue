<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useDiscussionsStore } from '../../stores/discussions';
import { storeToRefs } from 'pinia';
import GenericModal from './GenericModal.vue';

// Icons
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import IconThinking from '../../assets/icons/IconThinking.vue';
import IconDataZone from '../../assets/icons/IconDataZone.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconMessage from '../../assets/icons/IconMessage.vue';
import IconPhoto from '../../assets/icons/IconPhoto.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const status = computed(() => discussionsStore.activeDiscussionContextStatus);

// Constants from documentation
const IMAGE_TOKEN_COST = 256;

// --- Data Mapping ---

const systemBreakdown = computed(() => status.value?.zones?.system_context?.breakdown || {});
const historyBreakdown = computed(() => status.value?.zones?.message_history?.breakdown || {});
const globalImages = computed(() => status.value?.zones?.discussion_images?.tokens || 0);

const usagePercent = computed(() => status.value?.percent || 0);

/**
 * Helper to generate a flat list for the visual progress bar and cards
 * SYNCED with ChatInput.vue colors and labels
 */
const contextParts = computed(() => {
    if (!status.value) return [];
    const sys = systemBreakdown.value;
    const history = historyBreakdown.value;
    
    const parts = [];

    // 1. Directives (Indigo): System Prompt + Pruning Summaries
    const directiveTokens = (sys.system_prompt?.tokens || 0) + (sys.pruning_summary?.tokens || 0);
    if (directiveTokens > 0) parts.push({ 
        label: 'Directives', 
        val: directiveTokens, 
        color: 'bg-indigo-600', 
        text: 'text-indigo-600', 
        border: 'border-indigo-200 dark:border-indigo-900/50', 
        bg: 'bg-indigo-50/30 dark:bg-indigo-900/10',
        icon: IconCpuChip 
    });

    // 2. Memory Bank (Teal): Long-term facts
    const memoryTokens = sys.memory?.tokens || 0;
    if (memoryTokens > 0) parts.push({ 
        label: 'Memory Bank', 
        val: memoryTokens, 
        color: 'bg-teal-500', 
        text: 'text-teal-600', 
        border: 'border-teal-200 dark:border-teal-900/50', 
        bg: 'bg-teal-50/30 dark:bg-teal-900/10',
        icon: IconThinking 
    });

    // 3. Context Zones (Amber): User Prefs + Discussion Zone + Personality data
    const zoneTokens = (sys.user_data_zone?.tokens || 0) + (sys.discussion_data_zone?.tokens || 0) + (sys.personality_data_zone?.tokens || 0);
    if (zoneTokens > 0) parts.push({ 
        label: 'Context Zones', 
        val: zoneTokens, 
        color: 'bg-amber-500', 
        text: 'text-amber-600', 
        border: 'border-amber-200 dark:border-amber-900/50', 
        bg: 'bg-amber-50/30 dark:bg-amber-900/10',
        icon: IconDataZone 
    });

    // 4. Workspace Artefacts (Blue): Active documents in workspace
    const artefactTokens = sys.artefacts?.tokens || 0;
    if (artefactTokens > 0) parts.push({ 
        label: 'Workspace Files', 
        val: artefactTokens, 
        color: 'bg-blue-600', 
        text: 'text-blue-600', 
        border: 'border-blue-200 dark:border-blue-900/50', 
        bg: 'bg-blue-50/30 dark:bg-blue-900/10',
        icon: IconFileText 
    });

    // 5. Conversation History (Emerald): Previous conversation text
    const historyTextTokens = history.text_tokens || 0;
    if (historyTextTokens > 0) parts.push({ 
        label: 'Chat History', 
        val: historyTextTokens, 
        color: 'bg-emerald-600', 
        text: 'text-emerald-600', 
        border: 'border-emerald-200 dark:border-emerald-900/50', 
        bg: 'bg-emerald-50/30 dark:bg-emerald-900/10',
        icon: IconMessage 
    });

    // 6. Visual Data (Rose): Message attachments + Global images
    const totalImageTokens = (history.image_tokens || 0) + globalImages.value;
    if (totalImageTokens > 0) parts.push({ 
        label: 'Visual Data', 
        val: totalImageTokens, 
        color: 'bg-rose-500', 
        text: 'text-rose-600', 
        border: 'border-rose-200 dark:border-rose-900/50', 
        bg: 'bg-rose-50/30 dark:bg-rose-900/10',
        icon: IconPhoto 
    });

    // 7. Agentic Scratchpad (Slate): Plan and thoughts
    const scratchpadTokens = sys.scratchpad?.tokens || 0;
    if (scratchpadTokens > 0) parts.push({ 
        label: 'Agent Scratchpad', 
        val: scratchpadTokens, 
        color: 'bg-slate-500', 
        text: 'text-slate-600', 
        border: 'border-slate-200 dark:border-slate-900/50', 
        bg: 'bg-slate-50/30 dark:bg-slate-900/10',
        icon: IconSparkles 
    });

    return parts;
});

function formatTokens(val) {
    return (val || 0).toLocaleString();
}
</script>

<template>
    <GenericModal modalName="contextViewer" title="Context Diagnostic" maxWidthClass="max-w-4xl">
        <template #body>
            <div class="space-y-6" v-if="status">
                
                <!-- ── Visual Summary Card ── -->
                <div class="p-6 bg-white dark:bg-gray-800 rounded-3xl border dark:border-gray-700 shadow-xl overflow-hidden relative">
                    <div class="flex justify-between items-end mb-6">
                        <div class="space-y-1">
                            <h3 class="text-3xl font-black tracking-tighter dark:text-white">
                                {{ formatTokens(status.current_tokens) }} 
                                <span class="text-gray-400 font-medium text-lg">/ {{ formatTokens(status.max_tokens) }}</span>
                            </h3>
                            <p class="text-[10px] font-black uppercase tracking-widest text-blue-500">Total Context Allocation</p>
                        </div>
                        <div class="text-right">
                            <span class="text-5xl font-black italic opacity-20 transition-all duration-500" :class="usagePercent > 80 ? 'text-red-500 opacity-100 scale-110' : ''">
                                {{ usagePercent.toFixed(0) }}%
                            </span>
                        </div>
                    </div>

                    <!-- Multi-colored Segmented Progress Bar (Synced with Input Bar) -->
                    <div class="h-7 w-full bg-gray-100 dark:bg-gray-900 rounded-full overflow-hidden flex border-2 border-gray-100 dark:border-gray-700 shadow-inner">
                        <div v-for="part in contextParts" :key="part.label"
                             :class="[part.color, 'h-full transition-all duration-1000 border-r border-black/10 last:border-0 shadow-lg']"
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

                <!-- ── Diagnostic Grid ── -->
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div v-for="part in contextParts" :key="part.label" 
                         class="p-4 rounded-2xl border transition-all hover:shadow-md flex flex-col justify-between"
                         :class="[part.border, part.bg]">
                        
                        <div class="flex items-center justify-between mb-4">
                            <div class="p-2 rounded-lg bg-white dark:bg-gray-900 shadow-sm" :class="part.text">
                                <component :is="part.icon" class="w-4 h-4" />
                            </div>
                            <span class="text-[10px] font-black uppercase tracking-widest opacity-60">
                                {{ Math.round((part.val / status.max_tokens) * 100) }}%
                            </span>
                        </div>

                        <div>
                            <p class="text-[9px] font-black uppercase tracking-widest opacity-50 mb-1">{{ part.label }}</p>
                            <div class="flex items-baseline gap-1.5">
                                <span class="text-2xl font-black" :class="part.text">{{ formatTokens(part.val) }}</span>
                                <span class="text-[10px] font-bold opacity-40">tok</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- ── Breakdown Details ── -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4">
                    
                    <!-- File Type Specifics -->
                    <div v-if="systemBreakdown.artefacts?.tokens" class="space-y-3">
                        <h4 class="px-2 text-[10px] font-black uppercase tracking-[0.2em] text-gray-400">File Type Distribution</h4>
                        <div class="p-5 bg-white dark:bg-gray-800/50 border dark:border-gray-700 rounded-3xl shadow-sm">
                            <div class="space-y-4">
                                <div v-for="(data, type) in systemBreakdown.artefacts?.types" :key="type" class="space-y-1">
                                    <div class="flex items-center justify-between text-[10px] font-bold uppercase tracking-tight">
                                        <span class="text-gray-500">{{ type }}s ({{ data.count }})</span>
                                        <span class="text-blue-500 font-mono">{{ formatTokens(data.tokens) }} tok</span>
                                    </div>
                                    <div class="h-2 w-full bg-gray-100 dark:bg-gray-900 rounded-full overflow-hidden">
                                        <div class="h-full bg-blue-600 rounded-full transition-all duration-1000" 
                                             :style="{ width: `${(data.tokens / systemBreakdown.artefacts.tokens) * 100}%` }">
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- History Stats -->
                    <div class="space-y-3">
                        <h4 class="px-2 text-[10px] font-black uppercase tracking-[0.2em] text-gray-400">Conversation Metadata</h4>
                        <div class="grid grid-cols-2 gap-3 h-full">
                            <div class="p-4 bg-white dark:bg-gray-800/50 border dark:border-gray-700 rounded-3xl flex flex-col justify-center items-center text-center group">
                                <span class="text-3xl font-black text-emerald-600 dark:text-emerald-500 group-hover:scale-110 transition-transform">
                                    {{ historyBreakdown.message_count || 0 }}
                                </span>
                                <span class="text-[9px] font-black uppercase tracking-widest text-gray-400 mt-2">Total Turns</span>
                            </div>
                            <div class="p-4 bg-white dark:bg-gray-800/50 border dark:border-gray-700 rounded-3xl flex flex-col justify-center items-center text-center group">
                                <span class="text-3xl font-black text-rose-600 dark:text-rose-500 group-hover:scale-110 transition-transform">
                                    {{ IMAGE_TOKEN_COST }}
                                </span>
                                <span class="text-[9px] font-black uppercase tracking-widest text-gray-400 mt-2">Tok / Image</span>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </template>
        <template #footer>
            <div class="w-full flex justify-between px-4">
                <p class="text-[10px] text-gray-400 italic self-center">Values are calculated in real-time before each generation turn.</p>
                <button @click="uiStore.closeModal('contextViewer')" class="btn btn-primary px-8 py-2.5 rounded-xl shadow-lg shadow-blue-500/20">Close Analysis</button>
            </div>
        </template>
    </GenericModal>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }

.animate-fade-in {
    animation: fadeIn 0.5s ease-out forwards;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>