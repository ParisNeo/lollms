<script setup>
import { ref, computed, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useUiStore } from '../../../stores/ui';
import { useDiscussionsStore } from '../../../stores/discussions';
import DiscussionZone from './DiscussionZone.vue';
import PersonalityZone from './PersonalityZone.vue';
import MemoryZone from './MemoryZone.vue';
import IconMaximize from '../../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../../assets/icons/IconMinimize.vue';
import IconChevronDown from '../../../assets/icons/IconChevronDown.vue';
import IconXMark from '../../../assets/icons/IconXMark.vue';
import IconDataZone from '../../../assets/icons/IconDataZone.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconThinking from '../../../assets/icons/IconThinking.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();
const { liveDataZoneTokens } = storeToRefs(discussionsStore);

const dataZoneWidth = ref(450);
const isResizing = ref(false);

const isDataZoneExpanded = computed(() => uiStore.isDataZoneExpanded);

const collapsed = ref({
    discussion: true, // Collapsed by default
    personality: true,
    memory: true
});

function startResize(event) {
    isResizing.value = true;
    const startX = event.clientX;
    const startWidth = dataZoneWidth.value;
    const handleResize = (e) => {
        if (!isResizing.value) return;
        dataZoneWidth.value = Math.max(320, startWidth - (e.clientX - startX));
    };
    const stopResize = () => {
        isResizing.value = false;
        window.removeEventListener('mousemove', handleResize);
        window.removeEventListener('mouseup', stopResize);
        localStorage.setItem('lollms_dataZoneWidth', dataZoneWidth.value);
    };
    window.addEventListener('mousemove', handleResize);
    window.addEventListener('mouseup', stopResize);
}

onMounted(() => {
    const savedWidth = localStorage.getItem('lollms_dataZoneWidth');
    if (savedWidth) dataZoneWidth.value = parseInt(savedWidth, 10);
});
</script>

<template>
    <div class="relative h-full flex flex-shrink-0 border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 z-10 shadow-2xl" 
         :class="[isDataZoneExpanded ? 'absolute inset-0 w-full' : '']" 
         :style="isDataZoneExpanded ? {} : { width: `${dataZoneWidth}px` }">
        
        <!-- Resizer Handle -->
        <div @mousedown.prevent="startResize" 
             class="absolute top-0 bottom-0 -left-1 w-2 cursor-col-resize z-20 hover:bg-blue-500/30 transition-colors" 
             v-if="!isDataZoneExpanded"></div>

        <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
            <!-- Header -->
            <div class="flex-shrink-0 bg-gray-50 dark:bg-gray-800/80 backdrop-blur-sm border-b border-gray-200 dark:border-gray-700 flex justify-between items-center p-2 h-12">
                <div class="flex items-center gap-2 px-2">
                    <IconDataZone class="w-4 h-4 text-gray-400" />
                    <h3 class="text-[10px] font-black text-gray-500 dark:text-gray-400 uppercase tracking-widest">Context Explorer</h3>
                </div>
                <div class="flex items-center gap-1">
                    <button @click="uiStore.toggleDataZoneExpansion()" class="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 transition-colors" :title="isDataZoneExpanded ? 'Shrink' : 'Expand'">
                        <IconMinimize v-if="isDataZoneExpanded" class="w-4 h-4" />
                        <IconMaximize v-else class="w-4 h-4" />
                    </button>
                    <button @click="uiStore.toggleDataZone()" class="p-1.5 rounded-lg hover:bg-red-500 hover:text-white text-gray-500 transition-colors" title="Close Sidebar">
                        <IconXMark class="w-4 h-4" />
                    </button>
                </div>
            </div>

            <!-- Scrollable Content -->
            <div class="flex-1 overflow-y-auto custom-scrollbar flex flex-col bg-gray-50/30 dark:bg-gray-900/30">
                
                <!-- Discussion Section -->
                <div class="flex flex-col border-b border-gray-200 dark:border-gray-800 transition-all">
                    <button @click="collapsed.discussion = !collapsed.discussion" 
                            class="flex-shrink-0 w-full flex items-center justify-between p-4 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors group">
                        <div class="flex items-center gap-3">
                            <div class="p-1.5 rounded-md bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">
                                <IconDataZone class="w-4 h-4" />
                            </div>
                            <span class="text-sm font-bold text-gray-700 dark:text-gray-200">Discussion Zone</span>
                             <span class="text-xs text-gray-400 font-mono" v-if="liveDataZoneTokens.discussion > 0">({{ liveDataZoneTokens.discussion }} tok)</span>
                        </div>
                        <IconChevronDown class="w-4 h-4 text-gray-400 transition-transform duration-300" :class="{'rotate-180': !collapsed.discussion}" />
                    </button>
                    <div v-show="!collapsed.discussion" class="h-96 p-2 pt-0">
                        <DiscussionZone />
                    </div>
                </div>

                <!-- Personality Section -->
                <div class="flex flex-col border-b border-gray-200 dark:border-gray-800 transition-all">
                    <button @click="collapsed.personality = !collapsed.personality" 
                            class="flex-shrink-0 w-full flex items-center justify-between p-4 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors group">
                        <div class="flex items-center gap-3">
                            <div class="p-1.5 rounded-md bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400">
                                <IconSparkles class="w-4 h-4" />
                            </div>
                            <span class="text-sm font-bold text-gray-700 dark:text-gray-200">AI Personality</span>
                            <span class="text-xs text-gray-400 font-mono" v-if="liveDataZoneTokens.personality > 0">({{ liveDataZoneTokens.personality }} tok)</span>
                        </div>
                        <IconChevronDown class="w-4 h-4 text-gray-400 transition-transform duration-300" :class="{'rotate-180': !collapsed.personality}" />
                    </button>
                    <div v-show="!collapsed.personality" class="h-64 p-2 pt-0">
                        <PersonalityZone />
                    </div>
                </div>

                <!-- Memory Section -->
                <div class="flex flex-col flex-1 min-h-0">
                    <button @click="collapsed.memory = !collapsed.memory" 
                            class="flex-shrink-0 w-full flex items-center justify-between p-4 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition-colors group">
                        <div class="flex items-center gap-3">
                            <div class="p-1.5 rounded-md bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400">
                                <IconThinking class="w-4 h-4" />
                            </div>
                            <span class="text-sm font-bold text-gray-700 dark:text-gray-200">Long-Term Memory</span>
                            <span class="text-xs text-gray-400 font-mono" v-if="liveDataZoneTokens.memory > 0">({{ liveDataZoneTokens.memory }} tok)</span>
                        </div>
                        <IconChevronDown class="w-4 h-4 text-gray-400 transition-transform duration-300" :class="{'rotate-180': !collapsed.memory}" />
                    </button>
                    <div v-show="!collapsed.memory" class="flex-1 p-2 pt-0 min-h-[300px]">
                        <MemoryZone />
                    </div>
                </div>

            </div>
        </div>
    </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>
