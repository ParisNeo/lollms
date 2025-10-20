<script setup>
import { ref, computed } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import DiscussionItem from './DiscussionItem.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';

import IconFolder from '../../assets/icons/IconFolder.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

const props = defineProps({
  group: {
    type: Object,
    required: true,
  },
  indentationLevel: {
    type: Number,
    default: 0,
  },
});

const store = useDiscussionsStore();
const uiStore = useUiStore();

const isOpen = ref(false);
const isDragOver = ref(false);

const paddingLeft = computed(() => `${props.indentationLevel * 1}rem`);

function toggleGroup() {
  isOpen.value = !isOpen.value;
}

function handleNewSubgroup(event) {
    event.stopPropagation();
    uiStore.openModal('discussionGroup', { parentGroup: props.group });
}

function handleEditGroup(event) {
  event.stopPropagation();
  uiStore.openModal('discussionGroup', { group: props.group });
}

async function handleDeleteGroup(event) {
  event.stopPropagation();
  const confirmed = await uiStore.showConfirmation({
    title: `Delete Group "${props.group.name}"?`,
    message: 'Discussions will become ungrouped, and subgroups will become top-level groups. This action cannot be undone.',
    confirmText: 'Delete'
  });
  if (confirmed) {
    store.deleteGroup(props.group.id);
  }
}

function handleNewDiscussionInGroup(event) {
  event.stopPropagation();
  store.createNewDiscussion(props.group.id);
}

function handleDragStart(event) {
  event.stopPropagation();
  event.currentTarget.classList.add('dragging-item');
  event.dataTransfer.setData('application/lollms-item', JSON.stringify({type: 'group', id: props.group.id}));
  event.dataTransfer.effectAllowed = 'move';
}

function handleDragEnd(event) {
  event.currentTarget.classList.remove('dragging-item');
}

function handleDragOver(event) {
  event.preventDefault();
  event.stopPropagation();
  event.dataTransfer.dropEffect = 'move';
  isDragOver.value = true;
}

function handleDragLeave(event) {
  event.stopPropagation();
  isDragOver.value = false;
}

async function handleDrop(event) {
  event.stopPropagation();
  isDragOver.value = false;
  const data = event.dataTransfer.getData('application/lollms-item');
  if (!data) return;
  
  try {
    const { type, id } = JSON.parse(data);

    if (type === 'discussion') {
      const discussion = store.discussions[id];
      if (discussion && discussion.group_id === props.group.id) return; // Already in this group
      await store.moveDiscussionToGroup(id, props.group.id);
    } else if (type === 'group') {
      const draggedGroup = store.discussionGroups.find(g => g.id === id);
      if (draggedGroup && draggedGroup.id !== props.group.id) {
        await store.updateGroup(id, draggedGroup.name, props.group.id);
      }
    }
  } catch(e) {
    console.error("Drop failed:", e);
    uiStore.addNotification("The requested move is not possible.", "error");
  }
}
</script>

<template>
  <div class="discussion-group">
    <div 
      class="discussion-group-header group flex items-center justify-between p-2 rounded-lg transition-colors hover:bg-gray-100/50 dark:hover:bg-gray-800/50" 
      :style="{ paddingLeft }"
      :draggable="true"
      @dragstart="handleDragStart"
      @dragend="handleDragEnd"
      @dragover.prevent="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
      :class="{ 'bg-slate-100 dark:bg-slate-800/50 border-2 border-dashed border-slate-400': isDragOver }"
      >
      <button @click="toggleGroup" class="flex items-center space-x-2 flex-grow min-w-0 h-full text-left">
        <IconFolder class="w-4 h-4 flex-shrink-0 text-slate-500 dark:text-gray-400" />
        <span class="font-medium text-slate-700 dark:text-gray-300 truncate">{{ group.name }}</span>
        <div class="px-1.5 py-0.5 bg-slate-200 dark:bg-gray-700 text-slate-600 dark:text-gray-400 rounded text-xs font-medium">
          {{ group.discussions.length }}
        </div>
      </button>
      <div class="flex items-center flex-shrink-0">
        <div @click.stop class="opacity-0 group-hover:opacity-100 transition-opacity">
          <DropdownMenu icon="menu" buttonClass="btn-icon-flat p-1" title="Group actions">
            <button @click="handleNewSubgroup" class="menu-item"><IconFolder class="h-4 w-4" /><span>New Subgroup</span></button>
            <button @click="handleNewDiscussionInGroup" class="menu-item"><IconPlus class="h-4 w-4" /><span>New Chat in Group</span></button>
            <div class="menu-divider"></div>
            <button @click="handleEditGroup" class="menu-item"><IconPencil class="h-4 w-4" /><span>Rename Group</span></button>
            <button @click="handleDeleteGroup" class="menu-item danger-item"><IconTrash class="h-4 w-4" /><span>Delete Group</span></button>
          </DropdownMenu>
        </div>
        <button @click="toggleGroup" class="btn-icon-flat p-1">
          <IconChevronRight class="w-4 h-4 transition-transform duration-200 text-slate-400" :class="{'rotate-90': isOpen}" />
        </button>
      </div>
    </div>

    <div v-if="isOpen" class="pl-2 space-y-1 mt-1 border-l-2 border-slate-200 dark:border-gray-700" :style="{ marginLeft: paddingLeft }">
      <!-- Recursively render subgroups -->
      <DiscussionGroupItem
        v-for="subgroup in group.children"
        :key="subgroup.id"
        :group="subgroup"
        :indentationLevel="indentationLevel + 1"
      />
      <!-- Render discussions in this group -->
      <DiscussionItem
        v-for="discussion in group.discussions"
        :key="discussion.id"
        :discussion="discussion"
      />
    </div>
  </div>
</template>

<style scoped>
.dragging-item {
  opacity: 0.5;
}
</style>