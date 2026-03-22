<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useUiStore } from '../../../stores/ui';
import { useDiscussionsStore } from '../../../stores/discussions';

// Views
import DiscussionZone from './DiscussionZone.vue';
import PersonalityZone from './PersonalityZone.vue';
import MemoryZone from './MemoryZone.vue';
import ArtefactZone from './ArtefactZone.vue';
import ArtefactSplitView from '../ArtefactSplitView.vue';

// Icons
import IconMaximize from '../../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../../assets/icons/IconMinimize.vue';
import IconChevronDown from '../../../assets/icons/IconChevronDown.vue';
import IconXMark from '../../../assets/icons/IconXMark.vue';
import IconDataZone from '../../../assets/icons/IconDataZone.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconThinking from '../../../assets/icons/IconThinking.vue';
import IconFolder from '../../../assets/icons/IconFolder.vue';
import IconPencil from '../../../assets/icons/IconPencil.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();
const { liveDataZoneTokens } = storeToRefs(discussionsStore);

const dataZoneWidth = ref(550);
const isResizing = ref(false);

const isDataZoneExpanded = computed(() => uiStore.isDataZoneExpanded);
const activeTab = computed({
    get: () => uiStore.dataZoneTab,
    set: (val) => uiStore.dataZoneTab = val
});

const collapsed = ref({
    discussion: false, 
    personality: true,
    memory: true
});

// Automatically switch to Workspace tab when a file is selected
watch(() => uiStore.activeSplitArtefactTitle, (newTitle) => {
    if (newTitle) {
        activeTab.value = 'workspace';
    }
});

function startResize(event) {
    isResizing.value = true;
    const startX = event.clientX;
    const startWidth = dataZoneWidth.value;
    const handleResize = (e) => {
        if (!isResizing.value) return;
        dataZoneWidth.value = Math.max(350, startWidth - (e.clientX - startX));
    };
    const stopResize = () => {
        isResizing.value = false;
        window.removeEventListener('mousemove', handleResize);
        window.removeEventListener('mouseup', stopResize);
        localStorage.setItem('lollms_unifiedWidth', dataZoneWidth.value);
    };
    window.addEventListener('mousemove', handleResize);
    window.addEventListener('mouseup', stopResize);
}

onMounted(() => {
    const savedWidth = localStorage.getItem('lollms_unifiedWidth');
    if (savedWidth) dataZoneWidth.value = parseInt(savedWidth, 10);
});
</script>

<template>
    <div class="relative h-full flex flex-shrink-0 border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 z-10 shadow-2xl transition-[width] duration-300" 
         :class="[isDataZoneExpanded ? 'absolute inset-0 w-full' : '']" 
         :style="isDataZoneExpanded ? {} : { width: `${dataZoneWidth}px` }">
        
        <!-- Resizer Handle -->
        <div @mousedown.prevent="startResize" 
             class="absolute top-0 bottom-0 -left-1.5 w-3 cursor-col-resize z-20 hover:bg-blue-500/30 transition-colors" 
             v-if="!isDataZoneExpanded"></div>

        <!-- Vertical Navigation Rail -->
        <div class="w-14 flex-shrink-0 border-r dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900 flex flex-col items-center py-4 gap-4">
            <button @click="activeTab = 'context'" 
                    class="p-2.5 rounded-xl transition-all relative group"
                    :class="activeTab === 'context' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-200'">
                <IconDataZone class="w-6 h-6" />
                <span class="absolute left-16 px-2 py-1 bg-gray-800 text-white text-[10px] rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">Context Zones</span>
            </button>

            <button @click="activeTab = 'files'" 
                    class="p-2.5 rounded-xl transition-all relative group"
                    :class="activeTab === 'files' ? 'bg-amber-500 text-white shadow-lg shadow-amber-500/20' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-200'">
                <IconFolder class="w-6 h-6" />
                <span class="absolute left-16 px-2 py-1 bg-gray-800 text-white text-[10px] rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">Artefacts List</span>
            </button>

            <button @click="activeTab = 'workspace'" 
                    class="p-2.5 rounded-xl transition-all relative group"
                    :class="activeTab === 'workspace' ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/20' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-200'">
                    <IconPencil class="w-6 h-6" />
                    <div v-if="discussionsStore.activeUpdatingArtefacts && discussionsStore.activeUpdatingArtefacts.size > 0" class="absolute -top-1 -right-1 flex h-3 w-3">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                    </div>
                    <span class="absolute left-16 px-2 py-1 bg-gray-800 text-white text-[10px] rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">Active Workspace</span>
            </button>
        </div>

        <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
            <!-- Unified Header -->
            <div class="flex-shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center px-4 h-14 shadow-sm">
                <div class="flex flex-col">
                    <span class="text-[9px] font-black uppercase tracking-widest text-gray-400">
                        {{ activeTab === 'context' ? 'Intelligence Context' : activeTab === 'files' ? 'Knowledge Management' : 'Active Project' }}
                    </span>
                    <h3 class="text-sm font-bold text-gray-800 dark:text-gray-100">
                         {{ activeTab === 'context' ? 'Context Explorer' : activeTab === 'files' ? 'Artefacts List' : 'Workspace' }}
                    </h3>
                </div>
                <div class="flex items-center gap-1">
                    <button @click="uiStore.toggleDataZoneExpansion()" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 transition-colors" :title="isDataZoneExpanded ? 'Shrink' : 'Expand'">
                        <IconMinimize v-if="isDataZoneExpanded" class="w-5 h-5" />
                        <IconMaximize v-else class="w-5 h-5" />
                    </button>
                    <button @click="uiStore.toggleDataZone()" class="p-2 rounded-lg hover:bg-red-500 hover:text-white text-gray-500 transition-colors" title="Close Panel">
                        <IconXMark class="w-5 h-5" />
                    </button>
                </div>
            </div>

            <!-- Dynamic Body Content -->
            <div class="flex-1 overflow-hidden relative">
                
                <!-- TAB 1: CONTEXT ZONES -->
                <div v-show="activeTab === 'context'" class="h-full overflow-y-auto custom-scrollbar flex flex-col bg-gray-50/30 dark:bg-gray-900/30">
                    <div class="flex flex-col border-b border-gray-200 dark:border-gray-800">
                        <button @click="collapsed.discussion = !collapsed.discussion" 
                                class="w-full flex items-center justify-between p-4 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors group">
                            <div class="flex items-center gap-3">
                                <div class="p-1.5 rounded-md bg-blue-100 dark:bg-blue-900/30 text-blue-600">
                                    <IconDataZone class="w-4 h-4" />
                                </div>
                                <span class="text-sm font-bold text-gray-700 dark:text-gray-200">Discussion Instructions</span>
                            </div>
                            <IconChevronDown class="w-4 h-4 text-gray-400 transition-transform duration-300" :class="{'rotate-180': !collapsed.discussion}" />
                        </button>
                        <div v-show="!collapsed.discussion" class="h-80 p-2 pt-0"><DiscussionZone /></div>
                    </div>

                    <div class="flex flex-col border-b border-gray-200 dark:border-gray-800">
                        <button @click="collapsed.personality = !collapsed.personality" 
                                class="w-full flex items-center justify-between p-4 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors group">
                            <div class="flex items-center gap-3">
                                <div class="p-1.5 rounded-md bg-purple-100 dark:bg-purple-900/30 text-purple-600">
                                    <IconSparkles class="w-4 h-4" />
                                </div>
                                <span class="text-sm font-bold text-gray-700 dark:text-gray-200">AI Logic & Persona</span>
                            </div>
                            <IconChevronDown class="w-4 h-4 text-gray-400 transition-transform duration-300" :class="{'rotate-180': !collapsed.personality}" />
                        </button>
                        <div v-show="!collapsed.personality" class="h-64 p-2 pt-0"><PersonalityZone /></div>
                    </div>

                    <div class="flex flex-col flex-grow min-h-0">
                        <button @click="collapsed.memory = !collapsed.memory" 
                                class="w-full flex items-center justify-between p-4 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors group">
                            <div class="flex items-center gap-3">
                                <div class="p-1.5 rounded-md bg-green-100 dark:bg-green-900/30 text-green-600">
                                    <IconThinking class="w-4 h-4" />
                                </div>
                                <span class="text-sm font-bold text-gray-700 dark:text-gray-200">Long-Term Facts</span>
                            </div>
                            <IconChevronDown class="w-4 h-4 text-gray-400 transition-transform duration-300" :class="{'rotate-180': !collapsed.memory}" />
                        </button>
                        <div v-show="!collapsed.memory" class="flex-grow p-2 pt-0"><MemoryZone /></div>
                    </div>
                </div>

                <!-- TAB 2: ARTEFACTS LIST -->
                <div v-show="activeTab === 'files'" class="h-full overflow-hidden bg-white dark:bg-gray-900">
                    <ArtefactZone />
                </div>

                <!-- TAB 3: WORKSPACE EDITOR -->
                <div v-show="activeTab === 'workspace'" class="h-full overflow-hidden bg-white dark:bg-gray-950">
                    <div v-if="!uiStore.activeSplitArtefactTitle" class="h-full flex flex-col items-center justify-center p-12 text-center opacity-40">
                         <IconPencil class="w-16 h-16 mb-4 text-gray-400" />
                         <h4 class="text-lg font-bold uppercase tracking-widest text-gray-500">Editor Offline</h4>
                         <p class="text-xs mt-2">Select a file from the "Files" tab to open the active workspace.</p>
                    </div>
                    <ArtefactSplitView v-else />
                </div>

            </div>
        </div>
    </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>