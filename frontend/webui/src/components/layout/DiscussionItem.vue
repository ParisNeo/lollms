<script setup>
import { computed, ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
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
import IconFolder from '../../assets/icons/IconFolder.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';

const props = defineProps({
  discussion: {
    type: Object,
    required: true,
  },
});

const store = useDiscussionsStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

const user = computed(() => authStore.user);
const showMenu = ref(false);

const isSelected = computed(() => store.currentDiscussionId === props.discussion.id);
const isActive = computed(() => store.generationInProgress && isSelected.value);
const isTitleGenerating = computed(() => store.titleGenerationInProgressId === props.discussion.id);

async function handleSelect() {
  // Ensure we are on the main chat view
  if (route.path !== '/') {
      await router.push('/');
  }
  
  if (uiStore.mainView !== 'chat') {
      uiStore.setMainView('chat');
  }  
  
  if (!isSelected.value) {
    await store.selectDiscussion(props.discussion.id);
  }

  // Auto-close sidebar on mobile
  if (window.innerWidth < 768) {
      uiStore.closeSidebar();
  }
}

function handleDragStart(event) {
  if (props.discussion.owner_username) {
    event.preventDefault();
    return;
  }
  event.currentTarget.classList.add('dragging-item');
  event.dataTransfer.setData('application/lollms-item', JSON.stringify({type: 'discussion', id: props.discussion.id}));
  event.dataTransfer.effectAllowed = 'move';
}

function handleDragEnd(event) {
  event.currentTarget.classList.remove('dragging-item');
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

function handleShare(event) {
  event.stopPropagation();
  uiStore.openModal('shareDiscussion', {
    discussionId: props.discussion.id,
    title: props.discussion.title
  });
  closeMenu();
}

function handleClone(event) {
  event.stopPropagation();
  store.cloneDiscussion(props.discussion.id);
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

function handleMoveToGroupModal(event) {
    event.stopPropagation();
    closeMenu();
    uiStore.openModal('moveDiscussion', { 
        discussionId: props.discussion.id,
        currentTitle: props.discussion.title,
        currentGroupId: props.discussion.group_id
    });
}

function handleClickOutside() {
  closeMenu();
}
</script>

<template>
  <div @click="handleSelect" 
       :draggable="!discussion.owner_username"
       @dragstart.stop="handleDragStart"
       @dragend="handleDragEnd"
       :class="[
            'discussion-item-flat group',
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
        <div class="flex items-center space-x-2 mt-1">
          <p v-if="discussion.owner_username" class="owner-info">
            <span class="owner-badge">{{ discussion.owner_username }}</span>
          </p>
          <p v-if="discussion.permission_level === 'shared_by_me'" class="owner-info">
            <span class="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300">Shared</span>
          </p>
        </div>
      </div>
    </div>
    
    <!-- Three Dot Menu -->
    <div class="relative">
      <button 
        @click="toggleMenu" 
        class="menu-trigger opacity-0 group-hover:opacity-100 transition-opacity duration-200"
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
        <div class="menu-content relative">
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

            <button @click="handleMoveToGroupModal" class="menu-item">
                <IconFolder class="h-4 w-4" />
                <span>Move to...</span>
            </button>

            <button v-if="user && user.user_ui_level >= 4" @click="handleAutoTitle" class="menu-item">
              <IconSparkles class="h-4 w-4" />
              <span>Generate Title</span>
            </button>

            <button v-if="user && user.user_ui_level >= 4" @click="handleShare" class="menu-item">
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
            <button @click="handleClone" class="menu-item">
              <IconCopy class="h-4 w-4" />
              <span>Clone Discussion</span>
            </button>
            <div class="menu-divider"></div>
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
.dragging-item {
  opacity: 0.5;
}
</style>
