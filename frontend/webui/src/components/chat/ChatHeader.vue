<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import IconPlusCircle from '../../assets/icons/IconPlusCircle.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';
import UserAvatar from '../ui/UserAvatar.vue';
import TasksManagerButton from '../layout/TasksManagerButton.vue';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const activeDiscussion = computed(() => discussionsStore.activeDiscussion);
const generationInProgress = computed(() => discussionsStore.generationInProgress);
const activePersonality = computed(() => discussionsStore.activePersonality);

function newDiscussion() {
  discussionsStore.createNewDiscussion();
}
</script>

<template>
  <header class="flex-shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-3 flex items-center justify-between shadow-sm z-10">
    <!-- Left Side: Active Persona and Discussion Title -->
    <div class="flex items-center space-x-3 overflow-hidden">
        <div v-if="activePersonality" class="flex-shrink-0">
            <UserAvatar :icon="activePersonality.icon_base64" :username="activePersonality.name" size-class="h-9 w-9" />
        </div>
        <div v-else class="flex-shrink-0">
            <IconCpuChip class="h-9 w-9 text-gray-500" />
        </div>
        
        <div class="overflow-hidden">
            <p class="text-sm font-semibold text-gray-800 dark:text-gray-100 truncate" :title="activeDiscussion?.title || 'New Discussion'">
                {{ activeDiscussion?.title || 'New Discussion' }}
            </p>
            <p class="text-xs text-gray-500 dark:text-gray-400 truncate" :title="activePersonality?.name || 'Default Assistant'">
                {{ activePersonality?.name || 'Default Assistant' }}
            </p>
        </div>
    </div>

    <!-- Right Side: Action Buttons -->
    <div class="flex items-center space-x-2">
      <TasksManagerButton />

      <button @click="newDiscussion" class="btn btn-secondary" title="New Discussion">
        <IconPlusCircle class="w-5 h-5" />
        <span class="hidden sm:inline ml-2">New</span>
      </button>

      <button
        v-if="generationInProgress"
        @click="discussionsStore.stopGeneration()"
        class="btn btn-danger"
        title="Stop Generation"
      >
        <IconStopCircle class="w-5 h-5" />
        <span class="hidden sm:inline ml-2">Stop</span>
      </button>
      
      <button
        v-else
        @click="discussionsStore.regenerateLastMessage()"
        :disabled="!activeDiscussion?.messages?.length"
        class="btn btn-secondary"
        title="Regenerate last response"
      >
        <IconArrowPath class="w-5 h-5" />
      </button>
    </div>
  </header>
</template>