<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useUiStore } from '../../../stores/ui';
import { useDiscussionsStore } from '../../../stores/discussions';
import { storeToRefs } from 'pinia';

import DiscussionZone from './DiscussionZone.vue';
import UserZone from './UserZone.vue';
import PersonalityZone from './PersonalityZone.vue';
import MemoryZone from './MemoryZone.vue';

import IconDataZone from '../../../assets/icons/IconDataZone.vue';
import IconUserCircle from '../../../assets/icons/IconUserCircle.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconThinking from '../../../assets/icons/IconThinking.vue';
import IconMaximize from '../../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../../assets/icons/IconMinimize.vue';

const uiStore = useUiStore();
const discussionsStore = useDiscussionsStore();

const { liveDataZoneTokens } = storeToRefs(discussionsStore);

const activeDataZoneTab = ref('discussion');
const dataZoneWidth = ref(768);
const isResizing = ref(false);

const isDataZoneExpanded = computed(() => uiStore.isDataZoneExpanded);

const formatTokens = (tokens) => tokens > 1000 ? `${(tokens/1000).toFixed(1)}K` : tokens.toString();

const dataTabs = computed(() => [
    { id: 'discussion', label: 'Discussion', icon: IconDataZone, tokenCount: liveDataZoneTokens.value.discussion },
    { id: 'user', label: 'User', icon: IconUserCircle, tokenCount: liveDataZoneTokens.value.user },
    { id: 'personality', label: 'Personality', icon: IconSparkles, tokenCount: liveDataZoneTokens.value.personality },
    { id: 'ltm', label: 'Memory', icon: IconThinking, tokenCount: liveDataZoneTokens.value.memory }
]);

function startResize(event) {
    isResizing.value = true;
    const startX = event.clientX;
    const startWidth = dataZoneWidth.value;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    function handleResize(e) {
        if (!isResizing.value) return;
        const dx = e.clientX - startX;
        const newWidth = startWidth - dx;
        const minWidth = 320;
        const maxWidth = window.innerWidth * 0.75;
        dataZoneWidth.value = Math.max(minWidth, Math.min(newWidth, maxWidth));
    }

    function stopResize() {
        isResizing.value = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        window.removeEventListener('mousemove', handleResize);
        window.removeEventListener('mouseup', stopResize);
        localStorage.setItem('lollms_dataZoneWidth', dataZoneWidth.value);
    }

    window.addEventListener('mousemove', handleResize);
    window.addEventListener('mouseup', stopResize);
}

onMounted(() => {
    const savedWidth = localStorage.getItem('lollms_dataZoneWidth');
    if (savedWidth) dataZoneWidth.value = parseInt(savedWidth, 10);
});
</script>

<template>
    <div class="relative h-full flex" :class="[isDataZoneExpanded ? 'w-full' : 'flex-shrink-0']" :style="isDataZoneExpanded ? {} : { width: `${dataZoneWidth}px` }">
        <!-- Resizer -->
        <div @mousedown.prevent="startResize" class="flex-shrink-0 w-2 cursor-col-resize bg-gray-200 dark:bg-gray-700 hover:bg-blue-400 transition-colors duration-200"></div>

        <!-- Data Zone Content -->
        <aside class="h-full flex flex-col bg-white dark:bg-gray-800 shadow-xl flex-grow min-w-0">
            <!-- Tab Navigation -->
            <div class="flex-shrink-0 bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
                <div class="flex items-center justify-between px-2">
                    <nav class="flex space-x-1" aria-label="Data Zone Tabs">
                        <button v-for="tab in dataTabs" :key="tab.id" @click="activeDataZoneTab = tab.id"
                                :class="[
                                    'flex items-center gap-2 px-3 py-2.5 text-sm font-medium rounded-t-md border-b-2',
                                    activeDataZoneTab === tab.id ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-white dark:bg-gray-800' : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                                ]">
                            <component :is="tab.icon" class="w-4 h-4" />
                            <span>{{ tab.label }}</span>
                            <span v-if="tab.tokenCount > 0" class="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-600 text-xs rounded-full font-mono">{{ formatTokens(tab.tokenCount) }}</span>
                        </button>
                    </nav>
                    <button @click="uiStore.toggleDataZoneExpansion()" class="action-btn" :title="isDataZoneExpanded ? 'Shrink' : 'Expand'">
                        <IconMinimize v-if="isDataZoneExpanded" class="w-5 h-5" />
                        <IconMaximize v-else class="w-5 h-5" />
                    </button>
                </div>
            </div>

            <!-- Tab Content -->
            <DiscussionZone v-if="activeDataZoneTab === 'discussion'" />
            <UserZone v-if="activeDataZoneTab === 'user'" />
            <PersonalityZone v-if="activeDataZoneTab === 'personality'" />
            <MemoryZone v-if="activeDataZoneTab === 'ltm'" />
        </aside>
    </div>
</template>