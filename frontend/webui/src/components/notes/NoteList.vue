<script setup>
import { ref, computed } from 'vue';
import { useNotesStore } from '../../stores/notes';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import NoteGroupItem from './NoteGroupItem.vue';

import IconFileText from '../../assets/icons/IconFileText.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';

const props = defineProps({
  searchTerm: String
});

const notesStore = useNotesStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const notesTree = computed(() => notesStore.notesTree);

// Filter logic
const filteredTree = computed(() => {
    if (!props.searchTerm) return notesTree.value;
    const term = props.searchTerm.toLowerCase();

    const filterNotes = (notes) => notes.filter(n => n.title.toLowerCase().includes(term) || n.content.toLowerCase().includes(term));

    const filterGroups = (groups) => {
        return groups.map(group => {
            const filteredChildren = filterGroups(group.children || []);
            const filteredNotes = filterNotes(group.notes || []);
            if (group.name.toLowerCase().includes(term) || filteredChildren.length > 0 || filteredNotes.length > 0) {
                // If group name matches, show all content, else only filtered
                if (group.name.toLowerCase().includes(term)) return group;
                return { ...group, children: filteredChildren, notes: filteredNotes };
            }
            return null;
        }).filter(Boolean);
    };

    return {
        groups: filterGroups(notesTree.value.groups || []),
        ungrouped: filterNotes(notesTree.value.ungrouped || [])
    };
});

function handleNoteClick(note) {
    // Open Note Editor Modal
    uiStore.openModal('noteEditor', { note });
}

function handleNewSubgroup(parentGroup) {
    uiStore.openModal('noteGroup', { parentGroup });
}

function handleEditGroup(group) {
    uiStore.openModal('noteGroup', { group });
}

async function handleDeleteGroup(group) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Group "${group.name}"?`,
        message: 'Notes inside will be ungrouped.',
        confirmText: 'Delete'
    });
    if (confirmed.confirmed) {
        notesStore.deleteGroup(group.id);
    }
}

async function handleDeleteNote(note) {
     const confirmed = await uiStore.showConfirmation({
        title: `Delete Note "${note.title}"?`,
        confirmText: 'Delete'
    });
    if (confirmed.confirmed) {
        notesStore.deleteNote(note.id);
    }
}

async function handleImportNote(note) {
    if (!discussionsStore.currentDiscussionId) {
        uiStore.addNotification('No active discussion to import to.', 'warning');
        return;
    }
    await discussionsStore.appendToDataZone({ 
        discussionId: discussionsStore.currentDiscussionId, 
        content: note.content 
    });
}
</script>

<template>
  <div class="space-y-1">
      <NoteGroupItem 
        v-for="group in filteredTree.groups" 
        :key="group.id" 
        :group="group" 
        :level="0"
        @new-subgroup="handleNewSubgroup"
        @edit-group="handleEditGroup"
        @delete-group="handleDeleteGroup"
        @note-click="handleNoteClick"
        @delete-note="handleDeleteNote"
        @import-note="handleImportNote"
      />
      
      <div v-if="filteredTree.ungrouped && filteredTree.ungrouped.length > 0">
          <div class="px-2 py-1 text-xs font-semibold text-gray-500 uppercase mt-2">Ungrouped Notes</div>
          <div v-for="note in filteredTree.ungrouped" :key="note.id" 
                 class="flex items-center justify-between p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer group"
                 @click="handleNoteClick(note)">
                <div class="flex items-center gap-2 min-w-0">
                    <IconFileText class="w-4 h-4 text-blue-500 flex-shrink-0" />
                    <span class="text-sm truncate">{{ note.title || 'Untitled' }}</span>
                </div>
                 <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                     <button @click.stop="handleImportNote(note)" class="p-1 text-gray-500 hover:text-blue-500 hover:bg-gray-200 dark:hover:bg-gray-700 rounded" title="Import to Data Zone">
                        <IconArrowUpTray class="w-3 h-3" />
                    </button>
                    <button @click.stop="handleDeleteNote(note)" class="p-1 text-red-500 hover:bg-red-100 dark:hover:bg-red-900/30 rounded" title="Delete Note">
                        <IconTrash class="w-3 h-3" />
                    </button>
                </div>
            </div>
      </div>
      
      <div v-if="filteredTree.groups.length === 0 && filteredTree.ungrouped.length === 0" class="text-center py-8 text-gray-500 text-sm">
          No notes found.
      </div>
  </div>
</template>
