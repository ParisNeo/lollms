<script setup>
import { ref, computed } from 'vue';
import { useNotesStore } from '../../stores/notes';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import NoteGroupItem from './NoteGroupItem.vue';

import IconFileText from '../../assets/icons/IconFileText.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconShare from '../../assets/icons/IconShare.vue';
import DropdownMenu from '../ui/DropDownMenu/DropdownMenu.vue';

const props = defineProps({
  searchTerm: String
});

const notesStore = useNotesStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const isSelectionMode = ref(false);
const selectedNoteIds = ref(new Set());

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
    // Open the editor modal to allow reading/updating without force-adding to context
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
        uiStore.addNotification('Please select or start a discussion first.', 'warning');
        return;
    }
    await discussionsStore.addNoteAsArtefact(note);
}

function toggleSelection(noteId) {
    if (selectedNoteIds.value.has(noteId)) selectedNoteIds.value.delete(noteId);
    else selectedNoteIds.value.add(noteId);
}

function handleBulkEmail() {
    if (selectedNoteIds.value.size === 0) return;
    uiStore.openModal('emailNotes', { noteIds: Array.from(selectedNoteIds.value) });
}
</script>

<template>
  <div class="space-y-1">
      <!-- Selection Toolbar -->
      <div v-if="notesStore.notes.length > 0" class="flex items-center justify-between px-2 py-1 mb-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <button @click="isSelectionMode = !isSelectionMode" class="text-[10px] font-black uppercase tracking-widest" :class="isSelectionMode ? 'text-blue-600' : 'text-gray-500'">
              {{ isSelectionMode ? 'Cancel Selection' : 'Select Multiple' }}
          </button>
          <div v-if="isSelectionMode && selectedNoteIds.size > 0" class="flex gap-2">
              <button @click="handleBulkEmail" class="btn btn-primary btn-xs flex items-center gap-1">
                  <IconMail class="w-3 h-3" /> Email ({{ selectedNoteIds.size }})
              </button>
          </div>
      </div>

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
        :selection-mode="isSelectionMode"
        :selected-ids="selectedNoteIds"
        @toggle-select="toggleSelection"
      />
      
      <div v-if="filteredTree.ungrouped && filteredTree.ungrouped.length > 0">
          <div class="px-2 py-1 text-[10px] font-black uppercase text-gray-400 tracking-widest mt-4 mb-2">Ungrouped Notes</div>

          <div v-for="note in filteredTree.ungrouped" :key="note.id"
               class="group flex items-center gap-3 p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors mb-1"
               @click="isSelectionMode ? toggleSelection(note.id) : handleNoteClick(note)">
              
              <div v-if="isSelectionMode" class="flex-shrink-0">
                  <input type="checkbox" :checked="selectedNoteIds.has(note.id)" class="rounded border-gray-300">
              </div>

              <div class="flex items-center gap-2 min-w-0 flex-grow">
                  <div class="p-1.5 rounded bg-amber-50 dark:bg-amber-900/30 text-amber-600 flex-shrink-0 border border-amber-100 dark:border-amber-800">
                      <IconPencil class="w-3.5 h-3.5" />
                  </div>
                  <div class="flex flex-col min-w-0 leading-tight">
                      <span class="text-xs font-bold text-slate-700 dark:text-gray-200 truncate">{{ note.title || 'Untitled' }}</span>
                      <span class="text-[9px] text-gray-500 truncate uppercase tracking-tighter">{{ note.group || 'Ungrouped' }}</span>
                  </div>
              </div>

              <!-- Compact Menu at end of row -->
              <div @click.stop class="opacity-30 group-hover:opacity-100 transition-opacity">
                  <DropdownMenu title="Note options" buttonClass="p-1 text-amber-400 hover:text-amber-600">
                      <template #icon>
                          <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                              <circle cx="12" cy="5" r="1.5"/>
                              <circle cx="12" cy="12" r="1.5"/>
                              <circle cx="12" cy="19" r="1.5"/>
                          </svg>
                      </template>
                      <button @click="handleImportNote(note)" class="menu-item text-blue-600">
                          <IconArrowUpTray class="w-4 h-4 mr-2"/> Add to Discussion
                      </button>
                      <button @click="uiStore.openModal('shareResource', { id: note.id, name: note.title, type: 'note' })" class="menu-item">
                          <IconShare class="w-4 h-4 mr-2"/> Share with Friend
                      </button>
                      <button @click="uiStore.openModal('emailNotes', { noteIds: [note.id] })" class="menu-item">
                          <IconMail class="w-4 h-4 mr-2"/> Email Note
                      </button>
                      <div class="menu-divider"></div>
                      <button @click="handleDeleteNote(note)" class="menu-item text-red-500 font-bold">
                          <IconTrash class="w-4 h-4 mr-2"/> Remove
                      </button>
                  </DropdownMenu>
              </div>
          </div>
      </div>
      
      <div v-if="filteredTree.groups.length === 0 && filteredTree.ungrouped.length === 0" class="text-center py-8 text-gray-500 text-sm">
          No notes found.
      </div>
  </div>
</template>