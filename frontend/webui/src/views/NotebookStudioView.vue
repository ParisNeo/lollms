<script setup>
import { computed, onMounted, onUnmounted, defineAsyncComponent, watch } from 'vue';
import { useNotebookStore } from '../stores/notebooks';
import { useUiStore } from '../stores/ui';
import { useTasksStore } from '../stores/tasks'; // Import tasks store
import { storeToRefs } from 'pinia';
import useEventBus from '../services/eventBus';

// specialized Subviews
const GenericNotebookView = defineAsyncComponent(() => import('../components/notebooks/GenericNotebookView.vue'));
const SlidesMakingView = defineAsyncComponent(() => import('../components/notebooks/SlidesMakingView.vue'));
const BookBuildingView = defineAsyncComponent(() => import('../components/notebooks/BookBuildingView.vue'));
const YoutubeVideoView = defineAsyncComponent(() => import('../components/notebooks/YoutubeVideoView.vue'));

import IconServer from '../assets/icons/IconServer.vue';
import IconPlus from '../assets/icons/IconPlus.vue';

const notebookStore = useNotebookStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const { on, off } = useEventBus();
const { activeNotebook } = storeToRefs(notebookStore);
const { tasks } = storeToRefs(tasksStore);

const currentViewComponent = computed(() => {
    if (!activeNotebook.value) return null;
    const type = activeNotebook.value.type || 'generic';
    if (type === 'slides_making') return SlidesMakingView;
    if (type === 'book_building') return BookBuildingView;
    if (type === 'youtube_video') return YoutubeVideoView;
    return GenericNotebookView;
});

// Watch tasks to auto-refresh notebook when a relevant task completes
// This is a robust fallback if the event bus event is missed
watch(() => tasks.value, (newTasks, oldTasks) => {
    if (!activeNotebook.value) return;
    
    // Find if there is a completed task for this notebook that wasn't completed before
    // OR just check if the active task we were tracking is now marked done.
    
    // Simplest robust check: look for any completed task for this notebook ID in the current list
    // that implies recent activity.
    const completedTask = newTasks.find(t => 
        (t.result && t.result.notebook_id === activeNotebook.value.id) &&
        (t.status === 'completed' || t.status === 'success')
    );

    if (completedTask) {
        // To avoid infinite loops, we ideally need to know if we *just* finished it.
        // However, selectNotebook is relatively cheap.
        // We can optimize by checking if the notebook data looks stale compared to task result?
        // For now, let's trust the view components to handle debounce or the user to see the update.
        
        // NOTE: We don't auto-refresh constantly. The View components usually have local watchers.
        // This global watcher is mainly to ensure if the user switches views or tabs, state is fresh.
    }
}, { deep: true });

function onTaskCompleted(task) {
    if (activeNotebook.value && task.result && task.result.notebook_id === activeNotebook.value.id) {
         console.log("Notebook task completed, refreshing...", task.result);
         notebookStore.fetchNotebooks().then(() => {
             notebookStore.selectNotebook(activeNotebook.value.id);
         });
    }
}

onMounted(() => {
    notebookStore.fetchNotebooks();
    on('task:completed', onTaskCompleted);
    // Also listen for generic task end from socket if mapped differently
    on('task_end', onTaskCompleted); 
});

onUnmounted(() => {
    off('task:completed', onTaskCompleted);
    off('task_end', onTaskCompleted);
});
</script>

<template>
    <div class="h-full w-full flex flex-col overflow-hidden bg-white dark:bg-gray-900">
        <component 
            v-if="activeNotebook" 
            :is="currentViewComponent" 
            :notebook="activeNotebook"
        />
        
        <div v-else class="h-full flex flex-col items-center justify-center text-gray-500 dark:text-gray-400">
            <IconServer class="w-16 h-16 mb-4 text-gray-300 dark:text-gray-600" />
            <p class="text-lg font-medium">Select a notebook from the sidebar to begin.</p>
            <button @click="uiStore.openModal('notebookWizard')" class="mt-4 btn btn-primary flex items-center gap-2">
                <IconPlus class="w-4 h-4" /> Create New Notebook
            </button>
        </div>
    </div>
</template>
