<script setup>
import { ref, computed } from 'vue';
import IconFolder from '../../assets/icons/IconFolder.vue';
import IconChevronRight from '../../assets/icons/IconChevronRight.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconEllipsisVertical from '../../assets/icons/IconEllipsisVertical.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import DropdownMenu from '../ui/DropdownMenu/DropdownMenu.vue';

const props = defineProps({
    group: {
        type: Object,
        required: true
    },
    level: {
        type: Number,
        default: 0
    }
});

const emit = defineEmits(['new-subgroup', 'edit-group', 'delete-group', 'note-click', 'delete-note', 'import-note']);

const isOpen = ref(false);
const paddingLeft = computed(() => `${props.level * 0.75}rem`);

function toggle() {
    isOpen.value = !isOpen.value;
}
</script>

<template>
    <div>
        <div class="flex items-center justify-between p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer group" :style="{ paddingLeft }">
            <div class="flex items-center gap-2 flex-grow min-w-0" @click="toggle">
                <IconFolder class="w-4 h-4 text-yellow-500" />
                <span class="text-sm font-medium truncate">{{ group.name }}</span>
                <span class="text-xs text-gray-500 bg-gray-200 dark:bg-gray-700 px-1.5 rounded-full">{{ group.notes.length }}</span>
            </div>
            <div class="flex items-center">
                <div class="opacity-0 group-hover:opacity-100 transition-opacity mr-1">
                    <DropdownMenu icon="ellipsis-vertical" buttonClass="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700">
                        <button @click="emit('new-subgroup', group)" class="menu-item"><IconFolder class="w-4 h-4 mr-2"/>New Subgroup</button>
                        <button @click="emit('edit-group', group)" class="menu-item"><IconPencil class="w-4 h-4 mr-2"/>Rename</button>
                        <button @click="emit('delete-group', group)" class="menu-item text-red-500"><IconTrash class="w-4 h-4 mr-2"/>Delete</button>
                    </DropdownMenu>
                </div>
                <button @click="toggle" class="p-1 text-gray-400">
                    <IconChevronRight class="w-4 h-4 transition-transform" :class="{'rotate-90': isOpen}" />
                </button>
            </div>
        </div>
        <div v-if="isOpen" class="ml-2 border-l border-gray-200 dark:border-gray-700">
            <!-- Recursive Call -->
            <NoteGroupItem 
                v-for="child in group.children" 
                :key="child.id" 
                :group="child" 
                :level="level + 1"
                @new-subgroup="emit('new-subgroup', $event)"
                @edit-group="emit('edit-group', $event)"
                @delete-group="emit('delete-group', $event)"
                @note-click="emit('note-click', $event)"
                @delete-note="emit('delete-note', $event)"
                @import-note="emit('import-note', $event)"
            />
            
            <!-- Notes in this group -->
            <div v-for="note in group.notes" :key="note.id" 
                 class="flex items-center justify-between p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer group ml-2"
                 @click="emit('note-click', note)">
                <div class="flex items-center gap-2 min-w-0">
                    <IconFileText class="w-4 h-4 text-blue-500 flex-shrink-0" />
                    <span class="text-sm truncate">{{ note.title || 'Untitled' }}</span>
                </div>
                <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                     <button @click.stop="emit('import-note', note)" class="p-1 text-gray-500 hover:text-blue-500 hover:bg-gray-200 dark:hover:bg-gray-700 rounded" title="Import to Data Zone">
                        <IconArrowUpTray class="w-3 h-3" />
                    </button>
                    <button @click.stop="emit('delete-note', note)" class="p-1 text-red-500 hover:bg-red-100 dark:hover:bg-red-900/30 rounded" title="Delete Note">
                        <IconTrash class="w-3 h-3" />
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>
