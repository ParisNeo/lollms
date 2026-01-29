<script setup>
import { computed, onMounted, watch, nextTick, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useNotebookStore } from '../stores/notebooks';
import { useUiStore } from '../stores/ui';
import { useTasksStore } from '../stores/tasks';
import { storeToRefs } from 'pinia';

// Direct imports
import GenericNotebookView from '../components/notebooks/GenericNotebookView.vue';
import SlidesMakingView from '../components/notebooks/SlidesMakingView.vue';
import BookBuildingView from '../components/notebooks/BookBuildingView.vue';
import YoutubeVideoView from '../components/notebooks/YoutubeVideoView.vue';

import IconServer from '../assets/icons/IconServer.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';

const notebookStore = useNotebookStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const route = useRoute();
const router = useRouter();

// Use storeToRefs for proper reactivity
const { activeNotebook, isLoading } = storeToRefs(notebookStore);
const { tasks } = storeToRefs(tasksStore);

const currentViewComponent = computed(() => {
    if (!activeNotebook.value) return null;
    const type = activeNotebook.value.type || 'generic';
    if (type === 'slides_making') return SlidesMakingView;
    if (type === 'book_building') return BookBuildingView;
    if (type === 'youtube_video') return YoutubeVideoView;
    return GenericNotebookView;
});

const loadCurrentNotebook = async () => {
    const id = route.params.id;
    
    if (id) {
        console.log(`[NotebookStudioView] Loading notebook: ${id}`);
        await notebookStore.selectNotebook(id);
    } else {
        console.log('[NotebookStudioView] No notebook ID, clearing active notebook');
        notebookStore.setActiveNotebook(null);
    }
};

// Track running tasks for this notebook to detect completion
const runningTaskIds = ref(new Set());

// REACTIVITY: Watch for tasks finishing related to this notebook
watch(tasks, (newTasks) => {
    if (!activeNotebook.value) return;
    const nbId = activeNotebook.value.id || activeNotebook.value._id;
    const nbTitle = activeNotebook.value.title;
    
    // Find tasks related to this notebook
    const relevantTasks = newTasks.filter(t => {
        const descMatch = t.description === nbId;
        const nameMatch = t.name && nbTitle && t.name.includes(nbTitle);
        return descMatch || nameMatch;
    });
    
    // Track currently running tasks
    const currentlyRunning = new Set();
    for (const t of relevantTasks) {
        if (t.status === 'running' || t.status === 'pending') {
            currentlyRunning.add(t.id);
        }
    }
    
    // Check for tasks that just finished (were running, now not)
    for (const taskId of runningTaskIds.value) {
        if (!currentlyRunning.has(taskId)) {
            // This task was running but is no longer running - it finished!
            const finishedTask = newTasks.find(t => t.id === taskId);
            if (finishedTask && (finishedTask.status === 'finished' || finishedTask.status === 'failed' || finishedTask.status === 'cancelled')) {
                console.log(`[NotebookStudio] Task ${finishedTask.name} finished with status ${finishedTask.status}. Refreshing content...`);
                // Refresh the notebook data
                notebookStore.selectNotebook(nbId);
                // Also refresh the notebooks list to show updated titles/status
                notebookStore.fetchNotebooks();
            }
        }
    }
    
    // Update tracking set
    runningTaskIds.value = currentlyRunning;
}, { deep: true, immediate: true });

// Also watch for route changes
watch(() => route.params.id, (newId, oldId) => {
    if (newId !== oldId) {
        loadCurrentNotebook();
    }
}, { immediate: true });

// Watch for notebook ID changes to reset task tracking
watch(() => activeNotebook.value?.id, (newId, oldId) => {
    if (newId !== oldId) {
        runningTaskIds.value.clear();
    }
});

onMounted(() => {
    notebookStore.fetchNotebooks();
});
</script>

<template>
    <div class="flex-grow h-full w-full flex flex-col overflow-hidden bg-white dark:bg-gray-900 relative">
        
        <!-- Loading Overlay -->
        <div v-if="isLoading" class="absolute inset-0 flex flex-col items-center justify-center bg-white/80 dark:bg-gray-900/80 z-50 backdrop-blur-sm">
            <IconAnimateSpin class="w-10 h-10 text-blue-500 animate-spin mb-4" />
            <p class="text-[10px] font-black uppercase tracking-widest text-gray-400">Syncing Production...</p>
        </div>

        <!-- Render View when activeNotebook exists - simple check -->
        <div v-else-if="activeNotebook" class="flex-grow h-full w-full overflow-hidden">
            <component 
                :is="currentViewComponent" 
                :notebook="activeNotebook"
                :key="activeNotebook.id || activeNotebook._id"
            />
        </div>
        
        <!-- Empty State - only when no active notebook -->
        <div v-else class="flex-grow h-full flex flex-col items-center justify-center text-center p-12">
            <div class="max-w-md">
                <div class="w-20 h-20 bg-gray-100 dark:bg-gray-800 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-inner">
                    <IconServer class="w-10 h-10 text-gray-300" />
                </div>
                <h2 class="text-xl font-black text-gray-800 dark:text-white uppercase mb-2">Notebook Studio</h2>
                <p class="text-sm text-gray-500 mb-8">Select a production from the sidebar or start a new one to begin.</p>
                <button @click="uiStore.openModal('notebookWizard')" class="btn btn-primary px-8 py-3 rounded-2xl shadow-xl">
                    <IconPlus class="w-4 h-4 mr-2" /> New Production
                </button>
            </div>
        </div>
    </div>
</template>
