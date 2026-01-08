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
const loadedMemoryTitles = ref(new Set());

// Function to estimate token count (rough approximation: 1 token ~= 4 chars)
function estimateTokens(text) {
    if (!text) return 0;
    return Math.ceil(text.length / 4);
}

const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const isMemorizing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'memorize');

// Sorted memories to maintain consistent indexing display (must match backend sort order)
const sortedMemories = computed(() => {
    return [...memories.value].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
});

const memoryContext = computed(() => {
    // Reconstruct context text similar to backend to show realistic preview
    // Using simple indexing #1, #2 based on sorted list
    const activeMems = sortedMemories.value.filter(m => loadedMemoryTitles.value.has(m.title));
    if (activeMems.length === 0) return '';
    
    return activeMems.map((m) => {
        // Find the index in the FULL sorted list for consistent reference
        const fullIndex = sortedMemories.value.findIndex(sm => sm.id === m.id) + 1;
        return `[Memory #${fullIndex}] ${m.title}: ${m.content}`;
    }).join('\n\n');
});

const contextTokenCount = computed(() => estimateTokens(memoryContext.value));

const filteredMemories = computed(() => {
    if (!memorySearchTerm.value) return sortedMemories.value;
    const term = memorySearchTerm.value.toLowerCase();
    return sortedMemories.value.filter(m => 
        m.title.toLowerCase().includes(term) || 
        m.content.toLowerCase().includes(term)
    );
});

function handleMemorize() {
    if (!activeDiscussion.value) return;
    discussionsStore.memorizeLTM(activeDiscussion.value.id);
}

function handleCreateMemory() { uiStore.openModal('memoryEditor'); }
function handleEditMemory(memory) { uiStore.openModal('memoryEditor', { memory }); }

async function handleDeleteMemory(memoryId) {
    const memoryToDelete = memories.value.find(m => m.id === memoryId);
    if (!memoryToDelete) return;

    const confirmed = await uiStore.showConfirmation({
        title: `Delete Memory?`,
        message: `Permanently delete "${memoryToDelete.title}"?`,
        confirmText: 'Delete'
    });
    
    if (confirmed && confirmed.confirmed) {
        // Optimistically remove from UI (so animation can start) before the store refreshes
        // This also removes the title from the loaded set if it was selected
        loadedMemoryTitles.value.delete(memoryToDelete.title);
        loadedMemoryTitles.value = new Set(loadedMemoryTitles.value); // trigger reactivity

        await memoriesStore.deleteMemory(memoryId);
    }
}

function handleLoadMemory(title) { 
    loadedMemoryTitles.value.add(title);
    // Force reactivity for the Set
    loadedMemoryTitles.value = new Set(loadedMemoryTitles.value);
}

function handleUnloadMemory(title) { 
    loadedMemoryTitles.value.delete(title);
    // Force reactivity for the Set
    loadedMemoryTitles.value = new Set(loadedMemoryTitles.value);
}

async function refreshMemories() {
    await memoriesStore.fetchMemories();
    // Auto-select all new memories if set is empty (first load)
    if (loadedMemoryTitles.value.size === 0 && memories.value.length > 0) {
        memories.value.forEach(m => loadedMemoryTitles.value.add(m.title));
        loadedMemoryTitles.value = new Set(loadedMemoryTitles.value);
    }
}

// Watch for changes in memories list to prune titles that no longer exist (deleted via AI or manually)
watch(memories, (newMemories) => {
    const currentTitles = new Set(newMemories.map(m => m.title));
    let changed = false;
    for (const title of loadedMemoryTitles.value) {
        if (!currentTitles.has(title)) {
            loadedMemoryTitles.value.delete(title);
            changed = true;
        }
    }
    if (changed) {
        loadedMemoryTitles.value = new Set(loadedMemoryTitles.value);
    }
}, { deep: true });

onMounted(() => {
    refreshMemories();
});
</script>

<template>
  <div class="flex flex-col h-full gap-3 overflow-hidden">
    <!-- Header with Actions -->
    <div class="flex items-center justify-between bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-2 rounded-lg shadow-sm flex-shrink-0">
        <input type="text" v-model="memorySearchTerm" placeholder="Filter bank..." 
               class="w-32 px-2 py-1 text-xs bg-gray-50 dark:bg-gray-900 border-none focus:ring-1 focus:ring-blue-500 rounded" />
        <button @click="handleMemorize" class="btn btn-primary btn-xs py-1 px-3 shadow-sm" :disabled="isMemorizing">
            <IconAnimateSpin v-if="isMemorizing" class="w-3.5 h-3.5 mr-1 animate-spin"/>
            <IconSparkles v-else class="w-3.5 h-3.5 mr-1"/>
            Memorize Chat
        </button>
    </div>

    <!-- Main Vertical Stack -->
    <div class="flex-1 flex flex-col gap-3 min-h-0">
        
        <!-- Rendered Context (What's being sent) -->
        <div class="flex-1 flex flex-col min-h-[150px] border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900/50 shadow-inner overflow-hidden">
            <div class="p-2 border-b dark:border-gray-700 flex items-center justify-between bg-gray-50 dark:bg-gray-800/30">
                <span class="text-[9px] font-black uppercase text-gray-400 tracking-tighter">Active Context Preview</span>
                <div class="flex gap-2">
                    <span class="text-[9px] font-mono text-gray-500" v-if="memoryContext">{{ memoryContext.length }} chars</span>
                    <span class="text-[9px] font-mono text-blue-500" v-if="memoryContext">~{{ contextTokenCount }} tokens</span>
                </div>
            </div>
            <div class="flex-1 overflow-y-auto custom-scrollbar p-3">
                <div v-if="!memoryContext" class="h-full flex flex-col items-center justify-center text-gray-400 opacity-40">
                    <IconThinking class="w-10 h-10 mb-2" />
                    <p class="text-[10px] uppercase font-black tracking-widest">No Active Memories</p>
                </div>
                <MessageContentRenderer v-else :content="memoryContext" class="prose-xs" />
            </div>
        </div>

        <!-- Bank List -->
        <div class="h-64 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 flex flex-col shadow-sm overflow-hidden flex-shrink-0">
            <div class="p-2 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50/50 dark:bg-gray-800/30">
                <span class="text-[10px] font-black uppercase text-gray-500">Memory Bank ({{ filteredMemories.length }})</span>
                <button @click="handleCreateMemory" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-blue-500" title="Manual Memory Entry"><IconPlus class="w-4 h-4" /></button>
            </div>
            <div class="flex-1 overflow-y-auto custom-scrollbar p-1">
                <div v-if="isLoadingMemories" class="text-center py-6"><IconAnimateSpin class="w-6 h-6 text-gray-300 animate-spin mx-auto" /></div>
                <div v-else-if="filteredMemories.length === 0" class="text-center py-6 text-xs text-gray-400">Empty</div>
                <transition-group name="mem" tag="div" class="space-y-1" v-else>
                    <div v-for="(mem, index) in filteredMemories" :key="mem.id"
                         class="group p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 flex items-center justify-between transition-all border border-transparent"
                         :class="{'border-green-500/20 bg-green-50/10 dark:bg-green-900/5': loadedMemoryTitles.has(mem.title)}">
                        
                        <div class="flex items-center gap-3 min-w-0">
                            <!-- Index Badge -->
                            <span class="text-[10px] font-mono text-gray-400 font-bold w-5 text-center shrink-0">#{{ index + 1 }}</span>
                            
                            <button @click="loadedMemoryTitles.has(mem.title) ? handleUnloadMemory(mem.title) : handleLoadMemory(mem.title)" 
                                    class="flex-shrink-0 transition-colors" :class="loadedMemoryTitles.has(mem.title) ? 'text-green-500' : 'text-gray-300 hover:text-gray-400'">
                                <IconCheckCircle v-if="loadedMemoryTitles.has(mem.title)" class="w-5 h-5" />
                                <IconCircle v-else class="w-5 h-5" />
                            </button>
                            
                            <div class="flex flex-col min-w-0">
                                <span class="text-xs font-bold truncate text-gray-700 dark:text-gray-200" :title="mem.title">{{ mem.title }}</span>
                                <span class="text-[10px] truncate text-gray-400">{{ estimateTokens(mem.content) }} tokens</span>
                            </div>
                        </div>

                        <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button @click="handleEditMemory(mem)" class="p-1.5 rounded hover:bg-white dark:hover:bg-gray-700 shadow-sm text-blue-500" title="Edit"><IconPencil class="w-3.5 h-3.5" /></button>
                            <button @click="handleDeleteMemory(mem.id)" class="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/30 shadow-sm text-red-500" title="Delete"><IconTrash class="w-3.5 h-3.5" /></button>
                        </div>
                    </div>
                </transition-group>
            </div>
        </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
.prose-xs { @apply text-xs leading-relaxed text-gray-600 dark:text-gray-400; }

/* Transition for memory list items */
.mem-enter-active,
.mem-leave-active {
  transition: all 0.25s ease;
}
.mem-enter-from,
.mem-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
