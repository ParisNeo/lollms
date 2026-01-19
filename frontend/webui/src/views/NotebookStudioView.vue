<script setup>
import { computed, onMounted, watch, ref } from 'vue';
import { useRoute } from 'vue-router';
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
        await notebookStore.selectNotebook(id);
    } else {
        notebookStore.setActiveNotebook(null);
    }
};

// REACTIVITY: Watch for tasks finishing related to this notebook
watch(tasks, (newVal, oldVal) => {
    if (!activeNotebook.value || !oldVal) return;
    const nbId = activeNotebook.value.id || activeNotebook.value._id;
    
    // Detect tasks that just moved to 'finished' or 'failed'
    const justFinished = newVal.find(t => 
        (t.description === nbId || (t.name && t.name.includes(activeNotebook.value.title))) &&
        (t.status === 'finished' || t.status === 'failed') &&
        oldVal.some(ot => ot.id === t.id && (ot.status === 'running' || ot.status === 'pending'))
    );

    if (justFinished) {
        console.log(`[NotebookStudio] Task ${justFinished.name} ended. Refreshing content...`);
        notebookStore.selectNotebook(nbId);
    }
}, { deep: true });

watch(() => route.params.id, loadCurrentNotebook, { immediate: true });

onMounted(() => {
    notebookStore.fetchNotebooks();
});
</script>

<template>
    <div class="flex-grow h-full w-full flex flex-col overflow-hidden bg-white dark:bg-gray-900 relative">
        
        <!-- Loading Overlay -->
        <div v-if="isLoading && !activeNotebook" class="absolute inset-0 flex flex-col items-center justify-center bg-white/80 dark:bg-gray-900/80 z-50 backdrop-blur-sm">
            <IconAnimateSpin class="w-10 h-10 text-blue-500 animate-spin mb-4" />
            <p class="text-[10px] font-black uppercase tracking-widest text-gray-400">Syncing Production...</p>
        </div>

        <!-- Render View -->
        <div v-if="activeNotebook" class="flex-grow h-full w-full overflow-hidden">
            <component 
                :is="currentViewComponent" 
                :notebook="activeNotebook"
                :key="activeNotebook.id || activeNotebook._id"
            />
        </div>
        
        <!-- Empty State -->
        <div v-else-if="!isLoading" class="flex-grow h-full flex flex-col items-center justify-center text-center p-12">
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
