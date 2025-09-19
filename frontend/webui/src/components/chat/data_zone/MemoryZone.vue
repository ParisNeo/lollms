<script setup>
import { computed, ref } from 'vue';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useMemoriesStore } from '../../../stores/memories';
import { useUiStore } from '../../../stores/ui';
import { storeToRefs } from 'pinia';
import MessageContentRenderer from '../../ui/MessageContentRenderer/MessageContentRenderer.vue';
import IconThinking from '../../../assets/icons/IconThinking.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';
import IconCheckCircle from '../../../assets/icons/IconCheckCircle.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';

const discussionsStore = useDiscussionsStore();
const memoriesStore = useMemoriesStore();
const uiStore = useUiStore();

const { memories, isLoading: isLoadingMemories } = storeToRefs(memoriesStore);
const memorySearchTerm = ref('');
const loadedMemoryTitles = ref(new Set());

const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const isMemorizing = computed(() => activeDiscussion.value && discussionsStore.activeAiTasks[activeDiscussion.value.id]?.type === 'memorize');

const memory = computed(() => {
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

function handleCreateMemory() {
    uiStore.openModal('memoryEditor');
}

function handleEditMemory(memory) {
    uiStore.openModal('memoryEditor', { memory });
}

async function handleDeleteMemory(memoryId) {
    const memoryToDelete = memories.value.find(m => m.id === memoryId);
    if (!memoryToDelete) return;

    const confirmed = await uiStore.showConfirmation({
        title: `Delete Memory '${memoryToDelete.title}'?`,
        message: 'This will permanently delete this memory from your memory bank.',
        confirmText: 'Delete'
    });
    
    if (confirmed) {
        await memoriesStore.deleteMemory(memoryId);
    }
}

function handleLoadMemory(memoryTitle) {
    loadedMemoryTitles.value.add(memoryTitle);
    uiStore.addNotification(`Memory "${memoryTitle}" loaded to context`, 'success');
}

function handleUnloadMemory(memoryTitle) {
    loadedMemoryTitles.value.delete(memoryTitle);
    uiStore.addNotification(`Memory "${memoryTitle}" removed from context`, 'info');
}
</script>

<template>
  <div class="flex-1 flex flex-col min-h-0">
    <div class="flex-shrink-0 px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between gap-4">
        <span class="text-sm font-medium text-gray-600 dark:text-gray-300">Long-Term Memory</span>
        <button @click="handleMemorize" class="btn btn-secondary btn-sm" title="Memorize Current Discussion">
            <IconSparkles class="w-4 h-4 mr-1.5" :class="{'animate-pulse': isMemorizing}"/>Memorize
        </button>
    </div>

    <div class="flex-grow min-h-0 flex">
        <!-- Memory Context Display -->
        <div class="flex-grow flex flex-col min-w-0 p-2">
            <div class="flex-grow min-h-0 border dark:border-gray-700 rounded-md overflow-hidden">
                <div class="rendered-prose-container h-full p-2"><MessageContentRenderer :content="memory" /></div>
            </div>
        </div>

        <!-- Memory Bank Sidebar -->
        <div class="w-64 flex-shrink-0 border-l border-gray-200 dark:border-gray-700 flex flex-col p-2">
            <div class="sidebar-section">
                <div class="section-header">
                    <h4 class="section-title"><IconThinking class="w-4 h-4" /> Memory Bank</h4>
                    <div class="section-actions">
                        <button @click="handleCreateMemory" class="action-btn-sm" title="Create New Memory"><IconPlus class="w-4 h-4" /></button>
                    </div>
                </div>
                <div class="px-1 pb-2">
                    <input type="text" v-model="memorySearchTerm" placeholder="Search memories..." class="w-full px-2 py-1.5 text-xs bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-md focus:ring-1 focus:ring-yellow-500 focus:border-yellow-500" />
                </div>
                <div class="section-content flex-grow min-h-0 overflow-y-auto">
                    <div v-if="isLoadingMemories" class="loading-state"><IconAnimateSpin class="w-6 h-6 text-gray-400 animate-spin mx-auto mb-2" /><p class="text-xs text-gray-500">Loading...</p></div>
                    <div v-else-if="filteredMemories.length === 0" class="empty-state"><IconThinking class="w-8 h-8 text-gray-400 mx-auto mb-2" /><p class="text-xs text-gray-500 mb-3">No memories</p></div>
                    <div v-else class="memories-list space-y-2">
                        <div v-for="mem in filteredMemories" :key="mem.id" class="memory-card">
                            <div class="memory-header"><div class="memory-info"><div class="memory-icon" :class="{ 'loaded': loadedMemoryTitles.has(mem.title) }"><IconThinking class="w-4 h-4" /></div><div class="memory-details"><h5 class="memory-title" :title="mem.title">{{ mem.title }}</h5></div></div><div class="memory-actions"><button @click="handleEditMemory(mem)" class="memory-action-btn" title="Edit Memory"><IconPencil class="w-3 h-3" /></button><button @click="handleDeleteMemory(mem.id)" class="memory-action-btn memory-action-btn-danger" title="Delete Memory"><IconTrash class="w-3 h-3" /></button></div></div>
                            <div class="memory-controls"><button v-if="loadedMemoryTitles.has(mem.title)" @click="handleUnloadMemory(mem.title)" class="memory-load-btn loaded" title="Remove from Context"><IconCheckCircle class="w-3 h-3" />In Context</button><button v-else @click="handleLoadMemory(mem.title)" class="memory-load-btn" title="Add to Context"><IconPlus class="w-3 h-3" />Add to Context</button></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
  </div>
</template>