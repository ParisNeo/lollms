<script setup>
import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useDiscussionsStore } from '../../../stores/discussions';
import { useUiStore } from '../../../stores/ui';
import { useTasksStore } from '../../../stores/tasks';
import useEventBus from '../../../services/eventBus';
import CodeMirrorEditor from '../../ui/CodeMirrorComponent/index.vue';
import apiClient from '../../../services/api';

import IconUndo from '../../../assets/icons/IconUndo.vue';
import IconRedo from '../../../assets/icons/IconRedo.vue';
import IconCopy from '../../../assets/icons/IconCopy.vue';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconAnimateSpin from '../../../assets/icons/IconAnimateSpin.vue';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const { on, off } = useEventBus();

const { activeDiscussion } = storeToRefs(discussionsStore);
const { tasks } = storeToRefs(tasksStore);

const codeMirrorView = ref(null);
const isProgrammaticChange = ref(false);
const discussionHistory = ref([]);
const discussionHistoryIndex = ref(-1);
let discussionHistoryDebounceTimer = null;
let saveDebounceTimer = null;

const discussionDataZone = computed({
    get: () => activeDiscussion.value?.discussion_data_zone || '',
    set: (newVal) => {
        if (activeDiscussion.value) {
            discussionsStore.setDiscussionDataZoneContent(activeDiscussion.value.id, newVal);

            clearTimeout(saveDebounceTimer);
            saveDebounceTimer = setTimeout(() => {
                if (activeDiscussion.value) {
                    apiClient.put(`/api/discussions/${activeDiscussion.value.id}/data_zone`, { content: newVal })
                        .then(() => {
                            discussionsStore.fetchContextStatus(activeDiscussion.value.id);
                        });
                }
            }, 1500);
        }
    }
});

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

const canUndoDiscussion = computed(() => discussionHistoryIndex.value > 0);
const canRedoDiscussion = computed(() => discussionHistoryIndex.value < discussionHistory.value.length - 1);

function recordHistory(content) {
    clearTimeout(discussionHistoryDebounceTimer);
    discussionHistoryDebounceTimer = setTimeout(() => {
        if (discussionHistory.value[discussionHistoryIndex.value] === content) return;
        if (discussionHistoryIndex.value < discussionHistory.value.length - 1) {
            discussionHistory.value.splice(discussionHistoryIndex.value + 1);
        }
        discussionHistory.value.push(content);
        discussionHistoryIndex.value++;
    }, 750);
}

async function handleUndoDiscussion() {
    if (!canUndoDiscussion.value) return;
    isProgrammaticChange.value = true;
    discussionHistoryIndex.value--;
    discussionDataZone.value = discussionHistory.value[discussionHistoryIndex.value];
    await nextTick();
    isProgrammaticChange.value = false;
}

async function handleRedoDiscussion() {
    if (!canRedoDiscussion.value) return;
    isProgrammaticChange.value = true;
    discussionHistoryIndex.value++;
    discussionDataZone.value = discussionHistory.value[discussionHistoryIndex.value];
    await nextTick();
    isProgrammaticChange.value = false;
}

watch(discussionDataZone, (newVal, oldVal) => {
    if (!isProgrammaticChange.value && newVal !== oldVal) recordHistory(newVal);
}, { flush: 'post' });

watch(activeDiscussion, (newDiscussion, oldDiscussion) => {
    if (newDiscussion && (!oldDiscussion || newDiscussion.id !== oldDiscussion.id)) {
        discussionHistory.value = [newDiscussion.discussion_data_zone || ''];
        discussionHistoryIndex.value = 0;
    }
}, { immediate: true });

function handleEditorReady(payload) { codeMirrorView.value = payload.view; }
function handleCloneDiscussion() { if (activeDiscussion.value) discussionsStore.cloneDiscussion(activeDiscussion.value.id); }
function refreshDataZones() { if (activeDiscussion.value) discussionsStore.refreshDataZones(activeDiscussion.value.id); }

async function handleDrop(event) {
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0 && activeDiscussion.value) {
        uiStore.addNotification(`Extracting text from ${files.length} file(s)...`, 'info');
        await discussionsStore.uploadAndEmbedFilesToDataZone(activeDiscussion.value.id, files, false);
    }
}
</script>

<template>
  <div class="flex flex-col h-full overflow-hidden">
    <!-- Toolbar -->
    <div class="flex-shrink-0 flex items-center justify-between gap-2 p-1.5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-t-lg">
        <div class="flex items-center gap-0.5">
            <button @click="handleUndoDiscussion" class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30" title="Undo" :disabled="!canUndoDiscussion || isTaskRunning"><IconUndo class="w-4 h-4" /></button>
            <button @click="handleRedoDiscussion" class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30" title="Redo" :disabled="!canRedoDiscussion || isTaskRunning"><IconRedo class="w-4 h-4" /></button>
            <div class="w-px h-4 bg-gray-200 dark:bg-gray-700 mx-1"></div>
            <button @click="handleCloneDiscussion" class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30" title="Clone Data Zone" :disabled="isTaskRunning"><IconCopy class="w-4 h-4" /></button>
            <button @click="refreshDataZones" class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30" title="Refresh" :disabled="isTaskRunning"><IconRefresh class="w-4 h-4" /></button>
            <button @click="discussionDataZone = ''" class="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-red-500 disabled:opacity-30" title="Clear Context" :disabled="isTaskRunning"><IconTrash class="w-4 h-4" /></button>
        </div>
        
        <div v-if="isTaskRunning" class="flex items-center gap-2 pr-2">
            <IconAnimateSpin class="w-3.5 h-3.5 text-blue-500 animate-spin" />
            <span class="text-[10px] font-bold text-blue-500">{{ activeTask?.progress }}%</span>
        </div>
    </div>

    <!-- Editor -->
    <div 
        @dragover.prevent 
        @drop.prevent="handleDrop"
        class="flex-1 min-h-0 border-x border-b border-gray-200 dark:border-gray-700 rounded-b-lg overflow-hidden relative"
    >
        <CodeMirrorEditor 
            ref="discussionCodeMirrorEditor" 
            v-model="discussionDataZone" 
            class="h-full" 
            :read-only="isTaskRunning"
            :renderable="true"
            @ready="handleEditorReady"
        />
    </div>
  </div>
</template>
