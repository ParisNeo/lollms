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
    },
    selectionMode: Boolean,
    selectedIds: Object
});

const emit = defineEmits(['new-subgroup', 'edit-group', 'delete-group', 'note-click', 'delete-note', 'import-note', 'toggle-select']);

const isOpen = ref(false);
const activeNoteMenuId = ref(null);

function toggleNoteMenu(event, noteId) {
    event.stopPropagation();
    activeNoteMenuId.value = activeNoteMenuId.value === noteId ? null : noteId;
}

function closeNoteMenu() {
    activeNoteMenuId.value = null;
}
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
                :selection-mode="selectionMode"
                :selected-ids="selectedIds"
                @new-subgroup="emit('new-subgroup', $event)"
                @edit-group="emit('edit-group', $event)"
                @delete-group="emit('delete-group', $event)"
                @note-click="emit('note-click', $event)"
                @delete-note="emit('delete-note', $event)"
                @import-note="emit('import-note', $event)"
                @toggle-select="emit('toggle-select', $event)"
            />
            
            <!-- Notes in this group -->
            <div v-for="note in group.notes" :key="note.id" 
                 class="discussion-item-flat group ml-2"
                 :class="{ 'selected': activeNoteMenuId === note.id }"
                 @click="selectionMode ? emit('toggle-select', note.id) : emit('note-click', note)">
                
                <div v-if="selectionMode" class="flex-shrink-0 mr-2">
                    <input type="checkbox" :checked="selectedIds.has(note.id)" class="rounded border-gray-300">
                </div>

                <div class="flex items-center gap-3 min-w-0 flex-grow">
                    <IconPencil class="w-4 h-4 flex-shrink-0 text-amber-500" />
                    <p class="discussion-title">{{ note.title || 'Untitled' }}</p>
                </div>

                <div class="relative">
                    <button 
                        @click.stop="toggleNoteMenu($event, note.id)" 
                        class="menu-trigger opacity-0 group-hover:opacity-100 text-amber-500"
                        :class="{ 'opacity-100': activeNoteMenuId === note.id }"
                    >
                        <IconEllipsisVertical class="h-4 w-4" />
                    </button>

                    <div v-if="activeNoteMenuId === note.id" class="dropdown-menu" @click.stop>
                        <div class="menu-content relative">
                            <button @click="emit('import-note', note); closeNoteMenu()" class="menu-item">
                                <IconArrowUpTray class="w-4 h-4 mr-3 text-blue-500"/> Add to Discussion
                            </button>
                            <button @click="uiStore.openModal('shareResource', { id: note.id, name: note.title, type: 'note' }); closeNoteMenu()" class="menu-item">
                                <IconUserCircle class="w-4 h-4 mr-3 text-gray-400"/> Share with Friend
                            </button>
                            <button @click="uiStore.openModal('emailNotes', { noteIds: [note.id] }); closeNoteMenu()" class="menu-item">
                                <IconMail class="w-4 h-4 mr-3 text-blue-500"/> Email Note
                            </button>
                            <div class="menu-divider"></div>
                            <button @click="emit('delete-note', note); closeNoteMenu()" class="menu-item danger-item">
                                <IconTrash class="w-4 h-4 mr-3"/> Remove
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            <!-- Click-away overlay -->
            <div v-if="activeNoteMenuId" class="fixed inset-0 z-10" @click="closeNoteMenu"></div>
        </div>
    </div>
</template>
