<script setup>
import { computed, ref } from 'vue';
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
import IconEllipsisVertical from '../../assets/icons/IconEllipsisVertical.vue';

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
const showMenu = ref(false);

const isSelected = computed(() => store.currentDiscussionId === props.discussion.id);
const isActive = computed(() => store.generationInProgress && isSelected.value);
const isTitleGenerating = computed(() => store.titleGenerationInProgressId === props.discussion.id);

async function handleSelect() {
  if (!isSelected.value) {
    await store.selectDiscussion(props.discussion.id);
  }
}

function toggleMenu(event) {
  event.stopPropagation();
  showMenu.value = !showMenu.value;
}

function closeMenu() {
  showMenu.value = false;
}

function handleStar(event) {
  event.stopPropagation();
  store.toggleStarDiscussion(props.discussion.id);
  closeMenu();
}

function handleDelete(event) {
  event.stopPropagation();
  store.deleteDiscussion(props.discussion.id);
  closeMenu();
}

function handleRename(event) {
  event.stopPropagation();
  uiStore.openModal('renameDiscussion', {
    discussionId: props.discussion.id,
    currentTitle: props.discussion.title
  });
  closeMenu();
}

function handleSend(event) {
  event.stopPropagation();
  uiStore.openModal('shareDiscussion', {
    discussionId: props.discussion.id,
    title: props.discussion.title
  });
  closeMenu();
}

function handleAutoTitle(event) {
  event.stopPropagation();
  store.generateAutoTitle(props.discussion.id);
  closeMenu();
}

function handleUnsubscribe(event) {
  event.stopPropagation();
  store.unsubscribeFromSharedDiscussion(props.discussion.share_id);
  closeMenu();
}

function handleClickOutside() {
  closeMenu();
}
</script>

<template>
  <div @click="handleSelect" 
       :class="[
            'discussion-item-flat',
            { 'selected': isSelected },
            { 'active-generation': isActive }
       ]">
    
    <!-- Content Section -->
    <div class="flex-grow min-w-0">
      <div v-if="isTitleGenerating" class="flex items-center space-x-2">
        <div class="generating-spinner"></div>
        <span class="text-sm text-blue-600 dark:text-blue-400 font-medium">Generating title...</span>
      </div>
      <div v-else>
        <p class="discussion-title" :title="discussion.title">
          {{ discussion.title }}
        </p>
        <p v-if="discussion.owner_username" class="owner-info">
          <span class="owner-badge">{{ discussion.owner_username }}</span>
        </p>
      </div>
    </div>
    
    <!-- Three Dot Menu -->
    <div class="relative">
      <button 
        @click="toggleMenu" 
        class="menu-trigger opacity-0 hover:opacity-100 transition-opacity duration-200"
        :class="{ 'opacity-100': showMenu }"
        title="More actions"
      >
        <IconEllipsisVertical class="h-4 w-4" />
      </button>

      <!-- Dropdown Menu -->
      <div 
        v-if="showMenu" 
        class="dropdown-menu"
        @click.stop
      >
        <div class="menu-content">
          <template v-if="!discussion.owner_username">
            <button @click="handleStar" class="menu-item star-item">
              <IconStarFilled v-if="discussion.is_starred" class="h-4 w-4 text-yellow-500" />
              <IconStar v-else class="h-4 w-4" />
              <span>{{ discussion.is_starred ? 'Unstar' : 'Star' }}</span>
            </button>

            <button @click="handleRename" class="menu-item">
              <IconPencil class="h-4 w-4" />
              <span>Rename</span>
            </button>

            <button 
              v-if="user && user.user_ui_level >= 4" 
              @click="handleAutoTitle" 
              class="menu-item"
            >
              <IconSparkles class="h-4 w-4" />
              <span>Generate Title</span>
            </button>

            <button 
              v-if="user && user.user_ui_level >= 4" 
              @click="handleSend" 
              class="menu-item"
            >
              <IconSend class="h-4 w-4" />
              <span>Share</span>
            </button>

            <div class="menu-divider"></div>

            <button @click="handleDelete" class="menu-item danger-item">
              <IconTrash class="h-4 w-4" />
              <span>Delete</span>
            </button>
          </template>
          
          <template v-else>
            <button @click="handleUnsubscribe" class="menu-item danger-item">
              <IconTrash class="h-4 w-4" />
              <span>Unsubscribe</span>
            </button>
          </template>
        </div>
      </div>

      <!-- Overlay to close menu when clicking outside -->
      <div 
        v-if="showMenu" 
        class="fixed inset-0 z-10" 
        @click="handleClickOutside"
      ></div>
    </div>
  </div>
</template>

<style scoped>
.discussion-item-flat {
  @apply relative w-full text-left p-3 rounded-md cursor-pointer flex items-center transition-colors duration-150 hover:bg-slate-50 dark:hover:bg-gray-700/50;
}

.discussion-item-flat.selected {
  @apply bg-blue-50 dark:bg-blue-900/20;
}

.discussion-item-flat.active-generation {
  @apply border-l-2 border-blue-500;
}

.discussion-item-flat:hover .menu-trigger {
  @apply opacity-100;
}

.discussion-title {
  @apply text-sm font-medium text-slate-900 dark:text-gray-100 truncate leading-5;
}

.owner-info {
  @apply mt-1;
}

.owner-badge {
  @apply inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-gray-300;
}

.generating-spinner {
  @apply w-4 h-4 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin;
}

.menu-trigger {
  @apply p-1.5 rounded text-slate-400 dark:text-gray-500 hover:bg-slate-100 dark:hover:bg-gray-600 hover:text-slate-600 dark:hover:text-gray-300 transition-all duration-150;
}

.dropdown-menu {
  @apply absolute right-0 top-full mt-1 z-20;
}

.menu-content {
  @apply bg-white dark:bg-gray-800 rounded-md shadow-lg border border-slate-200 dark:border-gray-600 py-1 min-w-[160px];
}

.menu-item {
  @apply w-full flex items-center space-x-3 px-3 py-2 text-sm text-slate-700 dark:text-gray-200 hover:bg-slate-50 dark:hover:bg-gray-700 transition-colors duration-150;
}

.menu-item:hover {
  @apply text-slate-900 dark:text-gray-100;
}

.star-item:hover {
  @apply bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-300;
}

.danger-item {
  @apply text-red-600 dark:text-red-400;
}

.danger-item:hover {
  @apply bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300;
}

.menu-divider {
  @apply border-t border-slate-200 dark:border-gray-600 mx-1 my-1;
}
</style>
