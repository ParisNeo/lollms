<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';

const props = defineProps({
  discussion: {
    type: Object,
    required: true,
  },
});

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const isActive = computed(() => discussionsStore.currentDiscussionId === props.discussion.id);

function selectDiscussion() {
  uiStore.setMainView('chat');
  discussionsStore.selectDiscussion(props.discussion.id);
}

function deleteDiscussion() {
    discussionsStore.deleteDiscussion(props.discussion.id)
}

function renameDiscussion() { 
    uiStore.openModal('renameDiscussion', { discussionId: props.discussion.id });
}
function sendDiscussion() { 
    uiStore.addNotification('This feature is not yet implemented.', 'info');
    console.log('Send:', props.discussion.id); 
}
function toggleStar() { 
    discussionsStore.toggleStarDiscussion(props.discussion.id);
}
</script>

<template>
  <div
    @click="selectDiscussion"
    class="group p-2.5 rounded-lg cursor-pointer flex justify-between items-center text-sm transition-colors duration-150"
    :class="isActive ? 'bg-blue-600 font-medium text-white' : 'hover:bg-gray-100 dark:hover:bg-gray-700'"
  >
    <span class="truncate mr-2 flex-1 text-xs">{{ discussion.title || 'Untitled Discussion' }}</span>
    
    <div class="flex items-center flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" :class="{'opacity-100': isActive}">
      <!-- Actions: Send, Rename, Delete -->
      <button @click.stop="sendDiscussion" title="Send Discussion" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" /></svg>
      </button>
      <button @click.stop="renameDiscussion" title="Rename Discussion" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" /></svg>
      </button>
      <button @click.stop="deleteDiscussion" title="Delete Discussion" class="p-1 rounded hover:bg-red-200 dark:hover:bg-red-700 text-red-500">
         <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12.508 0A48.067 48.067 0 0 1 7.8 5.397m7.454 0M12 10.75h.008v.008H12v-.008Z" /></svg>
      </button>
       <button @click.stop="toggleStar" title="Star Discussion" class="p-1 ml-1 rounded" :class="discussion.is_starred ? 'text-yellow-400' : 'text-gray-400 dark:text-gray-500'">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" :fill="discussion.is_starred ? 'currentColor' : 'none'" class="w-4 h-4" :stroke="discussion.is_starred ? 'none' : 'currentColor'">
          <path fill-rule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.006 5.404.434c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.434 2.082-5.005Z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>
  </div>
</template>