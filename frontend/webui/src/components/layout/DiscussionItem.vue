<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';

// Import Icon Components
import IconStar from '../../assets/icons/IconStar.vue';
import IconStarFilled from '../../assets/icons/IconStarFilled.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconSend from '../../assets/icons/IconSend.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

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

async function handleSelect() {
  if (!isSelected.value) {
    await store.selectDiscussion(props.discussion.id);
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

function handleUnsubscribe(event) {
    event.stopPropagation();
    store.unsubscribeFromSharedDiscussion(props.discussion.share_id);
}

</script>

<template>
  <div @click="handleSelect" 
       :class="[
            'discussion-item group',
            { 'selected': isSelected },
            { 'active-generation': isActive }
       ]">
    
    <!-- Title Section - will shrink on hover -->
    <div class="flex-grow min-w-0">
      <div v-if="isTitleGenerating" class="flex items-center space-x-2">
        <svg class="animate-spin h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
        <span class="text-sm text-gray-500 italic">generating...</span>
      </div>
      <p v-else class="text-sm font-medium text-gray-800 dark:text-gray-100 truncate" :title="discussion.title">
        {{ discussion.title }}
      </p>
      <p v-if="discussion.owner_username" class="text-xs text-gray-500 dark:text-gray-400 truncate">
        from {{ discussion.owner_username }}
      </p>      
    </div>
    
    <!-- Action Buttons container animates its width -->
    <div class="action-buttons-container">
        <template v-if="!discussion.owner_username">
            <button @click.stop.prevent="handleStar" class="action-btn" :title="discussion.is_starred ? 'Unstar' : 'Star'">
                <IconStarFilled v-if="discussion.is_starred" class="h-4 w-4 text-yellow-400" />
                <IconStar v-else class="h-4 w-4" />
            </button>

            <button v-if="user && user.user_ui_level >= 4" @click.stop.prevent="handleAutoTitle" class="action-btn" title="Auto Title">
                <IconSparkles class="h-4 w-4" />
            </button>

            <button v-if="user && user.user_ui_level >= 4" @click.stop.prevent="handleSend" class="action-btn" title="Send Discussion">
                <IconSend class="h-4 w-4" />
            </button>
            
            <button @click.stop.prevent="handleRename" class="action-btn" title="Rename">
                <IconPencil class="h-4 w-4" />
            </button>

            <button @click.stop.prevent="handleDelete" class="action-btn-danger" title="Delete">
                <IconTrash class="h-4 w-4" />
            </button>
        </template>
        <template v-else>
            <button @click.stop.prevent="handleUnsubscribe" class="action-btn-danger" title="Unsubscribe">
                <IconTrash class="h-4 w-4" />
            </button>
        </template>
    </div>
  </div>
</template>

<style scoped>
.discussion-item {
  @apply w-full text-left p-2.5 rounded-lg cursor-pointer flex items-center justify-between transition-colors duration-150 overflow-hidden;
}
.discussion-item.selected {
  @apply bg-blue-100 dark:bg-blue-900/60;
}
.discussion-item.active-generation {
  animation: pulse-border 2s infinite;
  border: 1px solid;
}

.action-buttons-container {
  @apply flex items-center flex-shrink-0 space-x-0.5 pl-1
         max-w-0 opacity-0
         transition-all duration-300 ease-in-out;
}

/* On hover of the parent group, expand the button container */
.group:hover .action-buttons-container {
  max-width: 140px; /* Adjust this value if you add/remove buttons */
  @apply opacity-100;
}

.action-btn, .action-btn-danger {
    @apply p-1.5 rounded-full text-gray-500 dark:text-gray-400;
}
.action-btn:hover {
    @apply bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200;
}
.discussion-item.selected .action-btn:hover {
    @apply bg-blue-200 dark:bg-blue-800;
}

.action-btn-danger:hover {
    @apply bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-400;
}

@keyframes pulse-border {
  0% { border-color: transparent; }
  50% { border-color: theme('colors.blue.400'); }
  100% { border-color: transparent; }
}
</style>