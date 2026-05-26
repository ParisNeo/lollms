<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useMemoriesStore } from '../../../stores/memories';
import { useUiStore } from '../../../stores/ui';
import { storeToRefs } from 'pinia';
import MessageContentRenderer from '../../ui/MessageContentRenderer/MessageContentRenderer.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconCircle from '../../../assets/icons/IconCircle.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconThinking from '../../../assets/icons/IconThinking.vue';

const discussionsStore = useDiscussionsStore();
const memoriesStore = useMemoriesStore();
const uiStore = useUiStore();

const { memories, isLoading: isLoadingMemories } = storeToRefs(memoriesStore);
const memorySearchTerm = ref('');
const isDreaming = ref(false);

const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const activeTab = ref('working'); // 'working', 'deep', 'archived'

const activeMemories = computed(() => {
    let level = 1;
    if (activeTab.value === 'deep') level = 2;
    if (activeTab.value === 'archived') level = 3;
    
    let list = memories.value.filter(m => m.level === level);
    if (memorySearchTerm.value) {
        const query = memorySearchTerm.value.toLowerCase();
        list = list.filter(m => m.content.toLowerCase().includes(query));
    }
    return list;
});

async function triggerDream() {
    if (isDreaming.value) return;
    isDreaming.value = true;
    try {
        const report = await memoriesStore.triggerDream();
        if (report) {
            uiStore.openModal('interactiveOutput', {
                title: 'Consolidation Report (Subconscious Dream)',
                content: `### Dream Summary\n* **Reinforced Memories**: ${report.reinforced || 0}\n* **Decayed Memories**: ${report.decayed || 0}\n* **Forgotten Memories**: ${report.forgotten || 0}\n* **Retained by Dreamer**: ${report.retained_by_dreamer || 0}\n* **Processing Duration**: ${report.duration_seconds || 0} seconds.`
            });
        }
    } finally {
        isDreaming.value = false;
    }
}

async function updateMemoryLevel(memory, newLevel) {
    await memoriesStore.updateMemory(memory.id, { level: newLevel });
}

async function updateMemoryWeight(memory, weight) {
    await memoriesStore.updateMemory(memory.id, { importance: weight });
}

async function forgetMemory(memoryId) {
    const confirmed = await uiStore.showConfirmation({
        title: 'Forget Memory?',
        message: 'This will permanently erase this fact from your persistent cognitive layers.',
        confirmText: 'Erase'
    });
    if (confirmed.confirmed) {
        await memoriesStore.deleteMemory(memoryId);
    }
}

async function addManualFact() {
    const { confirmed, value } = await uiStore.showConfirmation({
        title: 'New Memory Fact',
        message: 'Enter a key personal fact, rule, or preference to persist in your cognitive layer:',
        inputType: 'text',
        confirmText: 'Save Fact'
    });
    if (confirmed && value) {
        await memoriesStore.addMemory(value);
    }
}

onMounted(() => {
    memoriesStore.fetchMemories();
});
</script>

<template>
  <div class="flex flex-col h-full gap-3 overflow-hidden">
    <!-- Header with Search & Dreaming -->
    <div class="flex items-center justify-between bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-2 rounded-lg shadow-sm shrink-0">
        <input v-model="memorySearchTerm" type="text" placeholder="Filter memories..." 
               class="w-32 px-2 py-1 text-xs bg-gray-50 dark:bg-gray-900 border-none focus:ring-1 focus:ring-blue-500 rounded" />
        <div class="flex gap-2">
            <button @click="triggerDream" class="btn btn-secondary btn-xs py-1 px-3 shadow-sm flex items-center gap-1.5" :disabled="isDreaming">
                <IconAnimateSpin v-if="isDreaming" class="w-3.5 h-3.5 animate-spin" />
                <span v-else>💤 Dream</span>
            </button>
            <button @click="addManualFact" class="btn btn-primary btn-xs py-1 px-3 shadow-sm flex items-center gap-1.5">
                <IconPlus class="w-3.5 h-3.5"/>
                <span>Add Fact</span>
            </button>
        </div>
    </div>

    <!-- Tier Tabs -->
    <div class="flex border-b dark:border-gray-800 p-1 bg-gray-50 dark:bg-gray-900/50 rounded-lg shrink-0">
        <button @click="activeTab = 'working'" class="flex-1 py-1 px-2 text-[9px] font-black uppercase tracking-widest rounded-md transition-all"
                :class="activeTab === 'working' ? 'bg-white dark:bg-gray-800 text-blue-600 shadow-sm' : 'text-gray-400'">
            Working (L1)
        </button>
        <button @click="activeTab = 'deep'" class="flex-1 py-1 px-2 text-[9px] font-black uppercase tracking-widest rounded-md transition-all"
                :class="activeTab === 'deep' ? 'bg-white dark:bg-gray-800 text-amber-500 shadow-sm' : 'text-gray-400'">
            Deep (L2)
        </button>
        <button @click="activeTab = 'archived'" class="flex-1 py-1 px-2 text-[9px] font-black uppercase tracking-widest rounded-md transition-all"
                :class="activeTab === 'archived' ? 'bg-white dark:bg-gray-800 text-red-500 shadow-sm' : 'text-gray-400'">
            Archived (L3)
        </button>
    </div>

    <!-- Active List -->
    <div class="flex-1 overflow-y-auto custom-scrollbar bg-white dark:bg-gray-950 rounded-lg p-2 border dark:border-gray-800">
        <div v-if="isLoadingMemories" class="flex justify-center items-center py-20">
            <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
        </div>
        <div v-else-if="activeMemories.length === 0" class="flex flex-col items-center justify-center py-20 text-gray-400 italic">
            <IconThinking class="w-10 h-10 opacity-20 mb-2" />
            <span class="text-[9px] font-black uppercase tracking-widest">No matching memories</span>
        </div>
        <div v-else class="space-y-3">
            <div v-for="mem in activeMemories" :key="mem.id" class="p-3 rounded-xl border border-gray-150 dark:border-gray-800 bg-gray-50/30 dark:bg-gray-900/20 group/item relative">
                <!-- Header Stats/Actions -->
                <div class="flex items-center justify-between mb-2">
                    <span class="font-mono text-[9px] text-gray-400">Handle: [{{ mem.id.substring(0, 8) }}]</span>
                    
                    <!-- Manual level switches -->
                    <div class="flex gap-1">
                        <button v-if="mem.level !== 1" @click="updateMemoryLevel(mem, 1)" class="px-1.5 py-0.5 rounded text-[8px] font-bold bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-400">Promote to L1</button>
                        <button v-if="mem.level !== 2" @click="updateMemoryLevel(mem, 2)" class="px-1.5 py-0.5 rounded text-[8px] font-bold bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400">Demote to L2</button>
                        <button v-if="mem.level !== 3" @click="updateMemoryLevel(mem, 3)" class="px-1.5 py-0.5 rounded text-[8px] font-bold bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-400">Archive to L3</button>
                    </div>
                </div>

                <p class="text-xs text-gray-800 dark:text-gray-200 leading-relaxed break-words pr-8 font-serif italic">
                    "{{ mem.content }}"
                </p>

                <!-- Footer Weights & Actions -->
                <div class="mt-3 flex items-center justify-between border-t dark:border-gray-800 pt-2">
                    <div class="flex items-center gap-3">
                        <span class="text-[9px] font-bold text-gray-400 uppercase">Importance: {{ Math.round(mem.importance * 100) }}%</span>
                        <input type="range" :value="mem.importance" @change="updateMemoryWeight(mem, parseFloat($event.target.value))" min="0" max="1" step="0.05" class="w-20 accent-blue-500">
                    </div>
                    
                    <div class="flex items-center gap-2">
                        <span class="text-[9px] font-mono text-gray-400">Used {{ mem.use_count }}x</span>
                        <button @click="forgetMemory(mem.id)" class="p-1 text-gray-400 hover:text-red-500 rounded" title="Forget completely">
                            <IconTrash class="w-3.5 h-3.5" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>