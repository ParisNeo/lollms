<script setup>
import { computed, onMounted, onUnmounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useNotebookStore } from '../../stores/notebooks';
import { useUiStore } from '../../stores/ui';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPresentationChartBar from '../../assets/icons/IconPresentationChartBar.vue';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';

const notebookStore = useNotebookStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();
const router = useRouter();
const route = useRoute();

// Use storeToRefs for proper reactivity
const { notebooks, activeNotebook } = storeToRefs(notebookStore);
const { tasks } = storeToRefs(tasksStore);

const activeId = computed(() => route.params.id);

function getIcon(type) {
    if (type === 'slides_making') return IconPresentationChartBar;
    if (type === 'youtube_video') return IconVideoCamera;
    if (type === 'book_building') return IconBookOpen;
    return IconServer;
}

function selectNotebook(id) {
    router.push(`/notebooks/${id}`);
}

async function deleteNotebook(id, title) {
    const { confirmed } = await uiStore.showConfirmation({
        title: 'Delete Project?',
        message: `Are you sure you want to delete "${title}"? This cannot be undone.`,
        confirmText: 'Delete'
    });
    if (confirmed) {
        await notebookStore.deleteNotebook(id);
        if (activeId.value === id) router.push('/notebooks');
    }
}

// Watch for task completions to refresh the list
// This ensures notebook titles/contents update when tasks finish
let taskWatcher = null;

onMounted(() => {
    notebookStore.fetchNotebooks();
    
    // Set up watcher for task changes to refresh notebooks
    taskWatcher = tasksStore.$subscribe((mutation, state) => {
        // Check if any task just finished
        const finishedTask = state.tasks.find(t => {
            // Look for tasks that finished in the last second
            if (t.status !== 'finished' && t.status !== 'failed') return false;
            if (!t.updated_at) return false;
            const updatedAt = new Date(t.updated_at).getTime();
            const now = Date.now();
            return (now - updatedAt) < 2000; // Finished in last 2 seconds
        });
        
        if (finishedTask) {
            // Refresh notebooks to get updated titles/status
            notebookStore.fetchNotebooks();
            
            // If we have an active notebook, refresh it too
            if (activeNotebook.value) {
                const activeId = activeNotebook.value.id || activeNotebook.value._id;
                if (finishedTask.description === activeId || 
                    (finishedTask.name && activeNotebook.value.title && finishedTask.name.includes(activeNotebook.value.title))) {
                    notebookStore.selectNotebook(activeId);
                }
            }
        }
    });
});

onUnmounted(() => {
    // Clean up subscription
    if (taskWatcher) {
        taskWatcher();
    }
});
</script>

<template>
  <div class="flex flex-col h-full bg-white dark:bg-gray-900">
    <!-- Header -->
    <div class="p-4 border-b dark:border-gray-800 flex items-center justify-between">
      <h2 class="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400">Productions</h2>
      <button 
        @click="uiStore.openModal('notebookWizard')" 
        class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg text-blue-500 transition-colors"
        title="New Production"
      >
        <IconPlus class="w-4 h-4" />
      </button>
    </div>

    <!-- List -->
    <div class="flex-grow overflow-y-auto custom-scrollbar p-2 space-y-1">
      <div v-if="notebooks.length === 0" class="py-10 text-center px-4">
          <IconServer class="w-8 h-8 text-gray-200 dark:text-gray-800 mx-auto mb-2" />
          <p class="text-[10px] font-bold text-gray-400 uppercase">No projects yet</p>
      </div>

      <div 
        v-for="nb in notebooks" 
        :key="nb.id"
        @click="selectNotebook(nb.id)"
        class="group flex items-center gap-3 p-3 rounded-xl cursor-pointer transition-all border-2"
        :class="activeId === nb.id 
            ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-500 shadow-sm' 
            : 'bg-transparent border-transparent hover:bg-gray-50 dark:hover:bg-gray-800'"
      >
        <div class="p-2 rounded-lg" :class="activeId === nb.id ? 'bg-blue-500 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-400 group-hover:text-blue-500'">
            <component :is="getIcon(nb.type)" class="w-4 h-4" />
        </div>
        
        <div class="flex-grow min-w-0">
          <p class="text-xs font-black truncate" :class="activeId === nb.id ? 'text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'">
            {{ nb.title || 'Untitled Project' }}
          </p>
          <p class="text-[9px] font-bold uppercase text-gray-400 opacity-60">
            {{ nb.type.replace('_', ' ') }}
          </p>
        </div>

        <button 
          @click.stop="deleteNotebook(nb.id, nb.title)" 
          class="opacity-0 group-hover:opacity-100 p-1.5 hover:text-red-500 text-gray-400 transition-all"
        >
          <IconTrash class="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-200 dark:bg-gray-800 rounded-full; }
</style>
