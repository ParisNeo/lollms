<!-- frontend/webui/src/components/layout/VideoProjectList.vue -->
<script setup>
import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useVideoStore } from '../../stores/video';
import { useUiStore } from '../../stores/ui';
import IconVideoCamera from '../../assets/icons/IconVideoCamera.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconClock from '../../assets/icons/IconClock.vue';

// Project list rendered inside the global Sidebar when in the video context.
// Mirrors the surface of DiscussionList / NoteList / AlbumList — a header with
// a "+" action and a scrollable list. All editing controls live in the studio
// workbench itself (see VideoStudioView's dock), matching how the Image Studio
// keeps its parameters in its own sidebar dock.
const store = useVideoStore();
const uiStore = useUiStore();
const { projects, isLoading, activeProjectId } = storeToRefs(store);

const count = computed(() => projects.value.length);

function selectProject(id) {
    activeProjectId.value = id;
}

function requestNewProject() {
    window.dispatchEvent(new CustomEvent('lollms:new-video-project'));
}

async function deleteProject(p) {
    const { confirmed } = await uiStore.showConfirmation({
        title: `Delete "${p.title}"?`,
        message: 'This will permanently remove the project and any rendered video.',
        confirmText: 'Delete',
        danger: true,
    });
    if (confirmed) {
        await store.deleteProject(p.id);
        if (activeProjectId.value === p.id) {
            activeProjectId.value = projects.value[0]?.id ?? null;
        }
    }
}
</script>

<template>
  <div class="h-full flex flex-col min-h-0">
    <div class="p-3 border-b border-border-main flex items-center justify-between shrink-0">
      <div>
        <p class="text-[10px] font-black uppercase tracking-widest text-gray-400">Projects</p>
        <p class="text-xs text-gray-500">
          {{ count }} {{ count === 1 ? 'project' : 'projects' }}
        </p>
      </div>
      <button
        @click="requestNewProject"
        class="p-1.5 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-md transition-colors"
        title="New Project"
      >
        <IconPlus class="w-4 h-4" />
      </button>
    </div>

    <div class="grow overflow-y-auto p-2 space-y-1 custom-scrollbar">
      <div v-if="isLoading && count === 0" class="p-4 text-center text-xs text-gray-400">
        Loading projects…
      </div>
      <div v-else-if="count === 0" class="p-4 text-center text-xs text-gray-400">
        <IconVideoCamera class="w-8 h-8 mx-auto mb-2 opacity-30" />
        No projects yet.<br />Click <strong>New Project</strong> to start.
      </div>

      <div
        v-for="p in projects"
        :key="p.id"
        @click="selectProject(p.id)"
        class="group w-full text-left p-2.5 rounded-xl transition-colors border cursor-pointer"
        :class="activeProjectId === p.id
          ? 'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800'
          : 'border-transparent hover:bg-gray-100 dark:hover:bg-gray-800'"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0 flex-1">
            <p class="text-xs font-bold text-gray-800 dark:text-gray-200 truncate">{{ p.title }}</p>
            <p class="text-[10px] text-gray-400 truncate uppercase tracking-wider mt-0.5">
              {{ p.source_type }} • {{ p.width }}×{{ p.height }}
            </p>
            <div class="flex items-center gap-2 mt-1 flex-wrap">
              <span
                v-if="p.video_filename"
                class="inline-flex items-center gap-1 text-[10px] text-emerald-600 dark:text-emerald-400"
              >
                <IconCheckCircle class="w-3 h-3" /> {{ (p.videos?.length || 1) }} take{{ (p.videos?.length || 1) === 1 ? '' : 's' }}
              </span>
              <span v-else class="inline-flex items-center gap-1 text-[10px] text-gray-400">
                <IconClock class="w-3 h-3" /> not rendered
              </span>
              <span v-if="p.composition" class="text-[10px] text-purple-600 dark:text-purple-400 font-black">🎬 film</span>
            </div>
          </div>
          <button
            @click.stop="deleteProject(p)"
            class="p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
            title="Delete"
          >
            <IconTrash class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
</style>