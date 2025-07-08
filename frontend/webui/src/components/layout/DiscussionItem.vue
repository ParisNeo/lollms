<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';

const props = defineProps({
  discussion: {
    type: Object,
    required: true,
  },
});

const store = useDiscussionsStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const user = computed(() => authStore.user);

const isSelected = computed(() => store.currentDiscussionId === props.discussion.id);
const isActive = computed(() => store.generationInProgress && isSelected.value);
const isTitleGenerating = computed(() => store.titleGenerationInProgressId === props.discussion.id);

function handleSelect() {
  if (!isSelected.value) {
    store.selectDiscussion(props.discussion.id);
  }
}

function handleStar(event) {
    event.stopPropagation();
    store.toggleStarDiscussion(props.discussion.id);
}

function handleDelete(event) {
    event.stopPropagation();
    store.deleteDiscussion(props.discussion.id);
}

function handleRename(event) {
    event.stopPropagation();
    uiStore.openModal('renameDiscussion', {
        discussionId: props.discussion.id,
        currentTitle: props.discussion.title
    });
}

function handleSend(event) {
    event.stopPropagation();
    uiStore.openModal('shareDiscussion', {
        discussionId: props.discussion.id,
        title: props.discussion.title
    });
}

function handleAutoTitle(event) {
    event.stopPropagation();
    store.generateAutoTitle(props.discussion.id);
}

</script>

<template>
  <div @click="handleSelect" 
       :class="[
            'discussion-item group',
            { 'selected': isSelected },
            { 'active-generation': isActive }
       ]">
    <div class="flex-grow truncate pr-2">
      <div v-if="isTitleGenerating" class="flex items-center space-x-2">
        <svg class="animate-spin h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
        <span class="text-sm text-gray-500 italic">generating...</span>
      </div>
      <p v-else class="text-sm font-medium text-gray-800 dark:text-gray-100 truncate" :title="discussion.title">
        {{ discussion.title }}
      </p>
    </div>
    
    <div class="flex items-center space-x-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
         :class="{ 'opacity-100': isSelected }">
        
        <button @click.stop.prevent="handleStar" class="p-1.5 rounded text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700" :title="discussion.is_starred ? 'Unstar' : 'Star'">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" :class="discussion.is_starred ? 'text-yellow-400' : 'text-gray-400'" viewBox="0 0 20 20" fill="currentColor">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
        </button>

        <button v-if="user && user.user_ui_level >= 4" @click.stop.prevent="handleAutoTitle" class="p-1.5 rounded text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-600 dark:hover:text-gray-300" title="Auto Title">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.898 20.572L16.5 21.75l-.398-1.178a3.375 3.375 0 00-2.3-2.3L12.75 18l1.178-.398a3.375 3.375 0 002.3-2.3L16.5 14.25l.398 1.178a3.375 3.375 0 002.3 2.3l1.178.398-1.178.398a3.375 3.375 0 00-2.3 2.3z" />
            </svg>
        </button>

        <button v-if="user && user.user_ui_level >= 4" @click.stop.prevent="handleSend" class="p-1.5 rounded text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-600 dark:hover:text-gray-300" title="Send Discussion">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.125A59.769 59.769 0 0121.485 12 59.768 59.768 0 013.27 20.875L5.999 12zm0 0h7.5" />
            </svg>
        </button>
        
        <button @click.stop.prevent="handleRename" class="p-1.5 rounded text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-600 dark:hover:text-gray-300" title="Rename">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
        </button>

        <button @click.stop.prevent="handleDelete" class="p-1.5 rounded text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-red-500 dark:hover:text-red-400" title="Delete">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
        </button>
    </div>
  </div>
</template>

<style scoped>
.discussion-item {
  @apply w-full text-left p-2.5 rounded-lg cursor-pointer flex justify-between items-center transition-colors duration-150
         hover:bg-gray-100 dark:hover:bg-gray-700/80;
}
.discussion-item.selected {
  @apply bg-blue-100 dark:bg-blue-900/60;
}
.discussion-item.active-generation {
  animation: pulse-border 2s infinite;
  border: 1px solid;
}
@keyframes pulse-border {
  0% { border-color: transparent; }
  50% { border-color: theme('colors.blue.400'); }
  100% { border-color: transparent; }
}
</style>