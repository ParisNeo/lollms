<script setup>
import { computed, ref } from 'vue';
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
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconThinking from '../../../assets/icons/IconThinking.vue';

const discussionsStore = useDiscussionsStore();
const memoriesStore = useMemoriesStore();
const uiStore = useUiStore();

const { memories, isLoading: isLoadingMemories } = storeToRefs(memoriesStore);
const memorySearchTerm = ref('');
const loadedMemoryTitles = ref(new Set());

const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const isMemorizing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'memorize');

const memoryContext = computed(() => {
    return memories.value
        .filter(m => loadedMemoryTitles.value.has(m.title))
        .map(m => `--- Memory: ${m.title} ---\n${m.content}\n--- End Memory: ${m.title} ---`)
        .join('\n\n');
});

const filteredMemories = computed(() => {
    if (!memorySearchTerm.value) return memories.value;
    const term = memorySearchTerm.value.toLowerCase();
    return memories.value.filter(m => 
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
    
    if (confirmed) {
        await memoriesStore.deleteMemory(memoryId);
    }
}

function handleLoadMemory(memoryTitle) { loadedMemoryTitles.value.add(memoryTitle); }
function handleUnloadMemory(memoryTitle) { loadedMemoryTitles.value.delete(memoryTitle); }
</script>

<template>
  <div class="flex flex-col h-full gap-3 overflow-hidden">
    <!-- Header with Actions -->
    <div class="flex items-center justify-between bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-2 rounded-lg shadow-sm">
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
                <span class="text-[9px] font-mono text-gray-500" v-if="memoryContext">{{ memoryContext.length }} chars</span>
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
        <div class="h-64 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 flex flex-col shadow-sm overflow-hidden">
            <div class="p-2 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50/50 dark:bg-gray-800/30">
                <span class="text-[10px] font-black uppercase text-gray-500">Memory Bank ({{ filteredMemories.length }})</span>
                <button @click="handleCreateMemory" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-blue-500" title="Manual Memory Entry"><IconPlus class="w-4 h-4" /></button>
            </div>
            <div class="flex-1 overflow-y-auto custom-scrollbar p-1">
                <div v-if="isLoadingMemories" class="text-center py-6"><IconAnimateSpin class="w-6 h-6 text-gray-300 animate-spin mx-auto" /></div>
                <div v-else class="space-y-1">
                    <div v-for="mem in filteredMemories" :key="mem.id" 
                         class="group p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 flex items-center justify-between transition-all border border-transparent"
                         :class="{'border-green-500/20 bg-green-50/10 dark:bg-green-900/5': loadedMemoryTitles.has(mem.title)}">
                        
                        <div class="flex items-center gap-3 min-w-0">
                            <button @click="loadedMemoryTitles.has(mem.title) ? handleUnloadMemory(mem.title) : handleLoadMemory(mem.title)" 
                                    class="flex-shrink-0 transition-colors" :class="loadedMemoryTitles.has(mem.title) ? 'text-green-500' : 'text-gray-300 hover:text-gray-400'">
                                <IconCheckCircle v-if="loadedMemoryTitles.has(mem.title)" class="w-5 h-5" />
                                <IconCircle v-else class="w-5 h-5" />
                            </button>
                            <span class="text-xs font-bold truncate text-gray-700 dark:text-gray-200">{{ mem.title }}</span>
                        </div>

                        <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button @click="handleEditMemory(mem)" class="p-1.5 rounded hover:bg-white dark:hover:bg-gray-700 shadow-sm text-blue-500" title="Edit"><IconPencil class="w-3.5 h-3.5" /></button>
                            <button @click="handleDeleteMemory(mem.id)" class="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/30 shadow-sm text-red-500" title="Delete"><IconTrash class="w-3.5 h-3.5" /></button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 3px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
.prose-xs { @apply text-xs leading-relaxed text-gray-600 dark:text-gray-400; }
</style>
