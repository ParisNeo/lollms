<script setup>
import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';
import { useTasksStore } from '../../../stores/tasks';
import MessageContentRenderer from '../../ui/MessageContentRenderer/MessageContentRenderer.vue';

// Icons
import IconCopy from '../../../assets/icons/IconCopy.vue';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';
import IconWrenchScrewdriver from '../../../assets/icons/IconWrenchScrewdriver.vue';
import IconFileText from '../../../assets/icons/IconFileText.vue';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();

const { activeDiscussion } = storeToRefs(discussionsStore);
const { tasks } = storeToRefs(tasksStore);

const discussionDataZone = computed(() => activeDiscussion.value?.discussion_data_zone || '');

const isTaskRunning = computed(() => {
    if (!activeDiscussion.value) return false;
    const taskInfo = discussionsStore.activeAiTasks[activeDiscussion.value.id];
    if (!taskInfo || !taskInfo.taskId) return false;
    const task = tasks.value.find(t => t.id === taskInfo.taskId);
    return task ? (task.status === 'running' || task.status === 'pending') : false;
});

const activeTask = computed(() => {
    if (!activeDiscussion.value) return null;
    const taskInfo = discussionsStore.activeAiTasks[activeDiscussion.value.id];
    if (!taskInfo || !taskInfo.taskId) return null;
    return tasks.value.find(t => t.id === taskInfo.taskId);
});
</script>

<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- Toolbar -->
    <div class="flex-shrink-0 flex items-center justify-between gap-2 p-1.5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-t-lg">
        <div class="flex items-center gap-0.5" v-if="activeDiscussion">
            <button @click="discussionsStore.cleanDataZone(activeDiscussion.id)" 
                    class="p-1.5 rounded hover:bg-blue-50 dark:hover:bg-blue-900/30 text-blue-600 disabled:opacity-30 flex items-center gap-1.5" 
                    title="Clean & Re-format Zone" 
                    :disabled="isTaskRunning">
                <IconWrenchScrewdriver class="w-3.5 h-3.5" />
                <span class="text-[9px] font-black uppercase">Clean</span>
            </button>
            
            <div class="w-px h-4 bg-gray-200 dark:bg-gray-700 mx-1"></div>
            
            <button @click="discussionsStore.cloneDiscussion(activeDiscussion.id)" class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30" title="Clone Context to New Discussion" :disabled="isTaskRunning"><IconCopy class="w-4 h-4" /></button>
            <button @click="discussionsStore.refreshDataZones(activeDiscussion.id)" class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30" title="Sync from Server" :disabled="isTaskRunning"><IconRefresh class="w-4 h-4" /></button>
            <button @click="discussionsStore.updateDataZone({ discussionId: activeDiscussion.id, content: '' })" class="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-red-500 disabled:opacity-30" title="Clear All Context" :disabled="isTaskRunning"><IconTrash class="w-4 h-4" /></button>
        </div>
        
        <div v-if="isTaskRunning" class="flex items-center gap-2 pr-2">
            <IconAnimateSpin class="w-3.5 h-3.5 text-blue-500 animate-spin" />
            <span class="text-[10px] font-bold text-blue-500">{{ activeTask?.progress }}%</span>
        </div>
    </div>

    <!-- Viewer (Read-only) -->
    <div class="flex-1 min-h-0 border-x border-b border-gray-200 dark:border-gray-700 rounded-b-lg bg-gray-50/30 dark:bg-gray-800/30 overflow-y-auto custom-scrollbar p-4">
        <div v-if="!discussionDataZone" class="h-full flex flex-col items-center justify-center opacity-30 text-gray-500">
             <IconFileText class="w-12 h-12 mb-2" />
             <p class="text-[10px] font-black uppercase tracking-widest">No Active Context</p>
        </div>
        <MessageContentRenderer v-else :content="discussionDataZone" />
    </div>
  </div>
</template>