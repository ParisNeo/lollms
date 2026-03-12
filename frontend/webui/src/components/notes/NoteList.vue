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
const activeMenuId = ref(null); // Track which note's menu is open

function toggleMenu(event, noteId) {
    event.stopPropagation();
    activeMenuId.value = activeMenuId.value === noteId ? null : noteId;
}

function closeMenu() {
    activeMenuId.value = null;
}

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
    // Clear any active artefact split to avoid confusion
    uiStore.activeSplitArtefactTitle = null;
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
async function toggleNoteInContext(note) {
    if (!discussionsStore.currentDiscussionId) {
        uiStore.addNotification('Please select or start a discussion first.', 'warning');
        return;
    }
    const isLoaded = discussionsStore.loadedContextItems.some(item => item.title === note.title && item.type === 'note');
    if (isLoaded) {
        await discussionsStore.removeContextItem(note.title, 'note');
    } else {
        const formattedContent = `\n--- Note: ${note.title} ---\n${note.content}\n--- End Note ---\n`;
        await discussionsStore.appendToDataZone({
            discussionId: discussionsStore.currentDiscussionId,
            content: formattedContent
        });
    }
}
async function handleImportNote(note) {
    if (!discussionsStore.currentDiscussionId) {
        uiStore.addNotification('Please select or start a discussion first.', 'warning');
        return;
    }

    // Call the structured artefact creation method
    await discussionsStore.addNoteAsArtefact(note);
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
          <div class="px-2 py-1 text-[10px] font-black uppercase text-gray-400 tracking-widest mt-4 mb-2">Ungrouped Notes</div>
            <div v-for="note in filteredTree.ungrouped" :key="note.id" 
                 class="discussion-item-flat group"
                 :class="{ 'selected': activeMenuId === note.id }"
                 @click="handleNoteClick(note)">
                
                <div class="flex items-center gap-3 min-w-0 flex-grow">
                    <IconPencil class="w-4 h-4 flex-shrink-0 text-amber-500" />
                    <p class="discussion-title">{{ note.title || 'Untitled' }}</p>
                </div>

                <!-- Three Dot Menu (Parity with DiscussionItem) -->
                <div class="relative">
                    <button 
                        @click.stop="toggleMenu($event, note.id)" 
                        class="menu-trigger opacity-0 group-hover:opacity-100 text-amber-500"
                        :class="{ 'opacity-100': activeMenuId === note.id }"
                    >
                        <IconEllipsisVertical class="h-4 w-4" />
                    </button>

                    <div v-if="activeMenuId === note.id" class="dropdown-menu" @click.stop>
                        <div class="menu-content relative">
                            <button @click="handleImportNote(note); closeMenu()" class="menu-item">
                                <IconArrowUpTray class="w-4 h-4 mr-3 text-blue-500"/> 
                                <span>Add to Discussion</span>
                            </button>
                            <button @click="uiStore.openModal('shareResource', { id: note.id, name: note.title, type: 'note' }); closeMenu()" class="menu-item">
                                <IconUserCircle class="w-4 h-4 mr-3 text-gray-400"/> 
                                <span>Share with Friend</span>
                            </button>
                            <div class="menu-divider"></div>
                            <button @click="handleDeleteNote(note); closeMenu()" class="menu-item danger-item">
                                <IconTrash class="w-4 h-4 mr-3"/> 
                                <span>Remove</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            <!-- Click-away overlay -->
            <div v-if="activeMenuId" class="fixed inset-0 z-10" @click="closeMenu"></div>
      </div>
      
      <div v-if="filteredTree.groups.length === 0 && filteredTree.ungrouped.length === 0" class="text-center py-8 text-gray-500 text-sm">
          No notes found.
      </div>
  </div>
</template>
