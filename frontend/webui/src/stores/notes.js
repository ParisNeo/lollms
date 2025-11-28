// frontend/webui/src/stores/notes.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useNotesStore = defineStore('notes', () => {
    const notes = ref([]);
    const groups = ref([]);
    const isLoading = ref(false);
    const activeNoteId = ref(null);
    const activeGroupId = ref(null); // null means "All Notes" or root
    const uiStore = useUiStore();

    const activeNote = computed(() => {
        if (!Array.isArray(notes.value)) return null;
        return notes.value.find(n => n.id === activeNoteId.value);
    });
    
    // Organize notes into a tree structure
    const notesTree = computed(() => {
        // Safeguard: Ensure data sources are arrays
        const safeGroups = Array.isArray(groups.value) ? groups.value : [];
        const safeNotes = Array.isArray(notes.value) ? notes.value : [];

        const groupMap = new Map(safeGroups.map(g => [g.id, { ...g, children: [], notes: [] }]));
        
        // Nest groups
        const nestedGroups = [];
        safeGroups.forEach(g => {
            if (g.parent_id && groupMap.has(g.parent_id)) {
                groupMap.get(g.parent_id).children.push(groupMap.get(g.id));
            } else if (!g.parent_id) {
                nestedGroups.push(groupMap.get(g.id));
            }
        });

        // Assign notes to groups
        const ungroupedNotes = [];
        safeNotes.forEach(n => {
            if (n.group_id && groupMap.has(n.group_id)) {
                groupMap.get(n.group_id).notes.push(n);
            } else {
                ungroupedNotes.push(n);
            }
        });

        return {
            groups: nestedGroups,
            ungrouped: ungroupedNotes
        };
    });

    async function fetchNotes() {
        isLoading.value = true;
        try {
            const [notesRes, groupsRes] = await Promise.all([
                apiClient.get('/api/notes'),
                apiClient.get('/api/notes/groups')
            ]);
            notes.value = Array.isArray(notesRes.data) ? notesRes.data : [];
            groups.value = Array.isArray(groupsRes.data) ? groupsRes.data : [];
        } catch (error) {
            console.error("Error fetching notes:", error);
            uiStore.addNotification("Failed to fetch notes.", "error");
            notes.value = [];
            groups.value = [];
        } finally {
            isLoading.value = false;
        }
    }

    async function createNote(noteData) {
        try {
            const res = await apiClient.post('/api/notes', noteData);
            notes.value.unshift(res.data);
            activeNoteId.value = res.data.id;
            uiStore.addNotification("Note created.", "success");
            return res.data;
        } catch (error) {
            uiStore.addNotification("Failed to create note.", "error");
        }
    }

    async function updateNote(id, noteData) {
        try {
            const res = await apiClient.put(`/api/notes/${id}`, noteData);
            const index = notes.value.findIndex(n => n.id === id);
            if (index !== -1) notes.value[index] = res.data;
            uiStore.addNotification("Note saved.", "success");
        } catch (error) {
            uiStore.addNotification("Failed to update note.", "error");
        }
    }

    async function deleteNote(id) {
        try {
            await apiClient.delete(`/api/notes/${id}`);
            notes.value = notes.value.filter(n => n.id !== id);
            if (activeNoteId.value === id) activeNoteId.value = null;
            uiStore.addNotification("Note deleted.", "success");
        } catch (error) {
            uiStore.addNotification("Failed to delete note.", "error");
        }
    }

    async function createGroup(name, parentId = null) {
        try {
            const res = await apiClient.post('/api/notes/groups', { name, parent_id: parentId });
            groups.value.push(res.data);
            uiStore.addNotification("Group created.", "success");
        } catch (error) {
            uiStore.addNotification("Failed to create group.", "error");
        }
    }

    async function updateGroup(id, name, parentId = null) {
        try {
            const res = await apiClient.put(`/api/notes/groups/${id}`, { name, parent_id: parentId });
            const index = groups.value.findIndex(g => g.id === id);
            if (index !== -1) groups.value[index] = res.data;
            uiStore.addNotification("Group updated.", "success");
        } catch (error) {
            uiStore.addNotification("Failed to update group.", "error");
        }
    }

    async function deleteGroup(id) {
        try {
            await apiClient.delete(`/api/notes/groups/${id}`);
            groups.value = groups.value.filter(g => g.id !== id);
            // Move orphaned notes to ungrouped locally
            notes.value.forEach(n => {
                if (n.group_id === id) n.group_id = null;
            });
            uiStore.addNotification("Group deleted.", "success");
        } catch (error) {
            uiStore.addNotification("Failed to delete group.", "error");
        }
    }

    return {
        notes, groups, isLoading, activeNoteId, activeGroupId, activeNote, notesTree,
        fetchNotes, createNote, updateNote, deleteNote,
        createGroup, updateGroup, deleteGroup
    };
});
