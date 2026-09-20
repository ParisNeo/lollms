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
import IconFileText from '../../../assets/icons/IconFileText.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();
const { liveDataZoneTokens } = storeToRefs(discussionsStore);

const dataZoneWidth = ref(550);
const isResizing = ref(false);

const isDataZoneExpanded = computed(() => uiStore.isDataZoneExpanded);
const activeTab = computed({
    get: () => {
        const tab = uiStore.dataZoneTab;
        return tab === 'context' ? 'discussion' : tab;
    },
    set: (val) => {
        uiStore.dataZoneTab = val;
    }
});

// Title and Subtitle dynamically resolving per active tab
const headerTitle = computed(() => {
    switch (activeTab.value) {
        case 'files': return 'Workspace Files';
        case 'workspace': return 'Active Workspace';
        case 'discussion': return 'Discussion Instructions';
        case 'personality': return 'AI Logic & Persona';
        case 'memory': return 'Long-Term Facts';
        default: return 'Context Explorer';
    }
});

const headerSubtitle = computed(() => {
    switch (activeTab.value) {
        case 'files': return 'Repository & Artefacts';
        case 'workspace': return 'Project Editor';
        case 'discussion': return 'Session Directives';
        case 'personality': return 'Persona Directives';
        case 'memory': return 'Cognitive Memory Bank';
        default: return 'Intelligence Context';
    }
});

// Automatically switch to Workspace tab when a file is selected
watch(() => uiStore.activeSplitArtefactTitle, (newTitle) => {
    if (newTitle) {
        uiStore.dataZoneTab = 'workspace';
    }
}, { immediate: true });

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
    <div class="relative h-full flex shrink-0 border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-950 z-10 shadow-2xl transition-[width] duration-300" 
         :class="[isDataZoneExpanded ? 'absolute inset-0 w-full' : '']" 
         :style="isDataZoneExpanded ? {} : { width: `${dataZoneWidth}px` }">

        <!-- Resizer Handle -->
        <div @mousedown.prevent="startResize" 
             class="absolute top-0 bottom-0 -left-1.5 w-3 cursor-col-resize z-20 hover:bg-blue-500/30 transition-colors" 
             v-if="!isDataZoneExpanded"></div>

        <!-- Vertical Navigation Rail (5 Distinct First-Class Tabs, Zero Accordions) -->
        <div class="w-14 shrink-0 border-r dark:border-gray-800 bg-gray-50/70 dark:bg-black flex flex-col items-center py-4 gap-3 select-none">
            <!-- 1. Workspace Files -->
            <button @click="activeTab = 'files'" 
                    class="p-2.5 rounded-2xl transition-all relative group cursor-pointer"
                    :class="activeTab === 'files' ? 'bg-amber-500 text-white shadow-lg shadow-amber-500/30 scale-105' : 'text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800/60'">
                <IconFolder class="w-5 h-5" />
                <span class="absolute left-16 px-2.5 py-1 bg-gray-900 text-white text-[10px] font-bold uppercase tracking-wider rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                    Workspace Files
                </span>
            </button>

            <!-- 2. Active Workspace Editor -->
            <button @click="activeTab = 'workspace'" 
                    class="p-2.5 rounded-2xl transition-all relative group cursor-pointer"
                    :class="activeTab === 'workspace' ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/30 scale-105' : 'text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800/60'">
                <IconPencil class="w-5 h-5" />
                <div v-if="discussionsStore.activeUpdatingArtefacts && discussionsStore.activeUpdatingArtefacts.size > 0" class="absolute -top-1 -right-1 flex h-3 w-3">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </div>
                <span class="absolute left-16 px-2.5 py-1 bg-gray-900 text-white text-[10px] font-bold uppercase tracking-wider rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                    Active Workspace
                </span>
            </button>

            <div class="h-px w-8 bg-gray-200 dark:border-gray-800 my-1"></div>

            <!-- 3. Discussion Instructions (Directives) -->
            <button @click="activeTab = 'discussion'" 
                    class="p-2.5 rounded-2xl transition-all relative group cursor-pointer"
                    :class="activeTab === 'discussion' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/30 scale-105' : 'text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800/60'">
                <IconDataZone class="w-5 h-5" />
                <span class="absolute left-16 px-2.5 py-1 bg-gray-900 text-white text-[10px] font-bold uppercase tracking-wider rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                    Discussion Directives
                </span>
            </button>

            <!-- 4. AI Persona & Logic -->
            <button @click="activeTab = 'personality'" 
                    class="p-2.5 rounded-2xl transition-all relative group cursor-pointer"
                    :class="activeTab === 'personality' ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/30 scale-105' : 'text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800/60'">
                <IconSparkles class="w-5 h-5" />
                <span class="absolute left-16 px-2.5 py-1 bg-gray-900 text-white text-[10px] font-bold uppercase tracking-wider rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                    AI Logic & Persona
                </span>
            </button>

            <!-- 5. Long-Term Facts (Memory) -->
            <button @click="activeTab = 'memory'" 
                    class="p-2.5 rounded-2xl transition-all relative group cursor-pointer"
                    :class="activeTab === 'memory' ? 'bg-teal-600 text-white shadow-lg shadow-teal-500/30 scale-105' : 'text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800/60'">
                <IconThinking class="w-5 h-5" />
                <span class="absolute left-16 px-2.5 py-1 bg-gray-900 text-white text-[10px] font-bold uppercase tracking-wider rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50">
                    Long-Term Facts
                </span>
            </button>
        </div>

        <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
            <!-- Unified Header -->
            <div class="shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center px-4 h-14 shadow-sm">
                <div class="flex flex-col min-w-0">
                    <span class="text-[9px] font-black uppercase tracking-widest text-gray-400 truncate">
                        {{ headerSubtitle }}
                    </span>
                    <h3 class="text-sm font-bold text-gray-800 dark:text-gray-100 truncate">
                        {{ headerTitle }}
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

            <!-- Full-Height Body Content per Tab (Zero Accordions) -->
            <div class="flex-1 overflow-hidden relative">

                <!-- TAB 1: WORKSPACE FILES LIST -->
                <div v-if="activeTab === 'files'" class="h-full overflow-hidden bg-white dark:bg-gray-900">
                    <ArtefactZone />
                </div>

                <!-- TAB 2: ACTIVE WORKSPACE EDITOR -->
                <div v-else-if="activeTab === 'workspace'" class="h-full overflow-hidden bg-white dark:bg-gray-950">
                    <div v-if="!uiStore.activeSplitArtefactTitle" class="h-full flex flex-col items-center justify-center p-12 text-center opacity-40">
                         <IconPencil class="w-16 h-16 mb-4 text-gray-400" />
                         <h4 class="text-lg font-bold uppercase tracking-widest text-gray-500">Editor Offline</h4>
                         <p class="text-xs mt-2">Select a document from the "Workspace Files" tab to open the workspace editor.</p>
                    </div>
                    <ArtefactSplitView v-else />
                </div>

                <!-- TAB 3: DISCUSSION INSTRUCTIONS (Full Height) -->
                <div v-else-if="activeTab === 'discussion'" class="h-full overflow-y-auto custom-scrollbar p-3 bg-gray-50/30 dark:bg-gray-900/30">
                    <DiscussionZone />
                </div>

                <!-- TAB 4: AI LOGIC & PERSONA (Full Height) -->
                <div v-else-if="activeTab === 'personality'" class="h-full overflow-y-auto custom-scrollbar p-3 bg-gray-50/30 dark:bg-gray-900/30">
                    <PersonalityZone />
                </div>

                <!-- TAB 5: LONG-TERM FACTS / MEMORY (Full Height) -->
                <div v-else-if="activeTab === 'memory'" class="h-full overflow-y-auto custom-scrollbar p-3 bg-gray-50/30 dark:bg-gray-900/30">
                    <MemoryZone />
                </div>

            </div>
        </div>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>