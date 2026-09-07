<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useNotesStore } from '../stores/notes';
import { useDiscussionsStore } from '../stores/discussions';
import { useUiStore } from '../stores/ui';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import MessageContentRenderer from '../components/ui/MessageContentRenderer/MessageContentRenderer.vue';
import CodeMirrorComponent from '../components/ui/CodeMirrorComponent/index.vue';

// Icons
import IconPencil from '../assets/icons/IconPencil.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconFolder from '../assets/icons/IconFolder.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconCopy from '../assets/icons/IconCopy.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconEye from '../assets/icons/IconEye.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';

const route = useRoute();
const router = useRouter();
const notesStore = useNotesStore();
const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();

const { notes, groups, isLoading } = storeToRefs(notesStore);

const selectedNoteId = ref(null);
const isEditing = ref(true);
const isSaving = ref(false);

const form = ref({
    title: '',
    content: '',
    group_id: null
});

const selectedNote = computed(() => {
    if (!selectedNoteId.value) return null;
    return notes.value.find(n => n.id === selectedNoteId.value) || null;
});

function selectNote(note) {
    if (!note) return;
    selectedNoteId.value = note.id;
    notesStore.activeNoteId = note.id;
    form.value = {
        title: note.title || '',
        content: note.content || '',
        group_id: note.group_id || null
    };
    router.replace({ query: { ...route.query, noteId: note.id } });
}

function createNewNote() {
    selectedNoteId.value = null;
    form.value = {
        title: 'New Note',
        content: '',
        group_id: null
    };
    isEditing.value = true;
}

async function saveNote() {
    if (!form.value.title.trim()) {
        uiStore.addNotification('Note title is required.', 'warning');
        return;
    }

    isSaving.value = true;
    try {
        if (selectedNoteId.value) {
            await notesStore.updateNote(selectedNoteId.value, {
                title: form.value.title,
                content: form.value.content,
                group_id: form.value.group_id
            });
            uiStore.addNotification('Note updated successfully.', 'success');
        } else {
            const created = await notesStore.createNote({
                title: form.value.title,
                content: form.value.content,
                group_id: form.value.group_id
            });
            if (created && created.id) {
                selectedNoteId.value = created.id;
                notesStore.activeNoteId = created.id;
            }
        }
        await notesStore.fetchNotes();
    } catch (e) {
        uiStore.addNotification('Failed to save note.', 'error');
    } finally {
        isSaving.value = false;
    }
}

async function deleteCurrentNote() {
    if (!selectedNoteId.value) return;
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Note "${form.value.title}"?`,
        message: 'This note will be permanently deleted.',
        confirmText: 'Delete'
    });
    if (confirmed?.confirmed || confirmed === true) {
        await notesStore.deleteNote(selectedNoteId.value);
        if (notes.value.length > 0) {
            selectNote(notes.value[0]);
        } else {
            createNewNote();
        }
    }
}

async function addNoteToActiveDiscussion() {
    if (!selectedNote.value) return;
    if (!discussionsStore.currentDiscussionId) {
        uiStore.addNotification('Please open a discussion first.', 'warning');
        return;
    }
    await discussionsStore.addNoteAsArtefact(selectedNote.value);
    uiStore.addNotification(`Note inserted as artefact in active conversation.`, 'success');
}

async function copyMarkdown() {
    if (!form.value.content) return;
    try {
        await navigator.clipboard.writeText(`# ${form.value.title}\n\n${form.value.content}`);
        uiStore.addNotification('Copied note as Markdown.', 'success');
    } catch (e) {
        uiStore.addNotification('Failed to copy.', 'error');
    }
}

function handleExternalSelectEvent(event) {
    if (event.detail && event.detail.id) {
        const found = notes.value.find(n => String(n.id) === String(event.detail.id));
        if (found) selectNote(found);
    }
}

onMounted(async () => {
    window.addEventListener('lollms:select-note', handleExternalSelectEvent);
    if (notes.value.length === 0) {
        await notesStore.fetchNotes();
    }
    const qId = route.query.noteId || notesStore.activeNoteId;
    if (qId) {
        const found = notes.value.find(n => String(n.id) === String(qId));
        if (found) selectNote(found);
    } else if (notes.value.length > 0) {
        selectNote(notes.value[0]);
    } else {
        createNewNote();
    }
});

onUnmounted(() => {
    window.removeEventListener('lollms:select-note', handleExternalSelectEvent);
});

watch(() => route.query.noteId, (newId) => {
    if (newId && String(newId) !== String(selectedNoteId.value)) {
        const found = notes.value.find(n => String(n.id) === String(newId));
        if (found) selectNote(found);
    }
});
</script>

<template>
    <PageViewLayout title="Notes Studio" :title-icon="IconPencil" :show-sidebar="false">
        <template #main>
            <div class="h-full flex flex-col overflow-hidden bg-bg-app">
                <!-- Master Top Toolbar -->
                <div class="shrink-0 px-6 py-3.5 border-b border-border-main bg-bg-card/70 backdrop-blur-sm flex items-center justify-between gap-4 flex-wrap">
                    <div class="flex items-center gap-3 min-w-0">
                        <div class="w-8 h-8 rounded-xl bg-amber-50 dark:bg-amber-900/30 text-amber-600 flex items-center justify-center shrink-0 border border-amber-200 dark:border-amber-800">
                            <IconPencil class="w-4 h-4" />
                        </div>
                        <div class="flex items-center gap-3 min-w-0">
                            <input 
                                v-model="form.title" 
                                type="text" 
                                placeholder="Note Title..." 
                                class="input-field text-sm font-bold w-60 sm:w-80"
                            />
                            <select v-model="form.group_id" class="input-field text-xs w-40 hidden sm:block">
                                <option :value="null">📁 Ungrouped</option>
                                <option v-for="g in groups" :key="g.id" :value="g.id">📁 {{ g.name }}</option>
                            </select>
                        </div>
                    </div>

                    <!-- Actions -->
                    <div class="flex items-center gap-2 shrink-0">
                        <div class="flex items-center p-1 bg-gray-100 dark:bg-gray-800 rounded-xl text-xs font-bold mr-2">
                            <button 
                                @click="isEditing = true" 
                                class="px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5"
                                :class="isEditing ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-text-dim'"
                            >
                                <IconPencil class="w-3.5 h-3.5" />
                                <span>Editor</span>
                            </button>
                            <button 
                                @click="isEditing = false" 
                                class="px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5"
                                :class="!isEditing ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-text-dim'"
                            >
                                <IconEye class="w-3.5 h-3.5" />
                                <span>Markdown Preview</span>
                            </button>
                        </div>

                        <button @click="createNewNote" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Create a new note">
                            <IconPlus class="w-3.5 h-3.5" />
                            <span class="hidden md:inline">New</span>
                        </button>
                        <button v-if="selectedNoteId" @click="addNoteToActiveDiscussion" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Insert into discussion">
                            <IconArrowUpTray class="w-3.5 h-3.5 text-blue-500" />
                            <span class="hidden md:inline">To Chat</span>
                        </button>
                        <button @click="copyMarkdown" class="btn btn-secondary btn-sm flex items-center gap-1.5" title="Copy Markdown">
                            <IconCopy class="w-3.5 h-3.5" />
                            <span class="hidden md:inline">Copy</span>
                        </button>
                        <button v-if="selectedNoteId" @click="deleteCurrentNote" class="btn btn-secondary btn-sm text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/30" title="Delete Note">
                            <IconTrash class="w-3.5 h-3.5" />
                        </button>
                        <button @click="saveNote" class="btn btn-primary btn-sm flex items-center gap-1.5 shadow-sm" :disabled="isSaving">
                            <IconAnimateSpin v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
                            <IconCheckCircle v-else class="w-3.5 h-3.5" />
                            <span>{{ isSaving ? 'Saving...' : 'Save' }}</span>
                        </button>
                    </div>
                </div>

                <!-- Full Width Workspace (No duplicate list) -->
                <div class="grow overflow-hidden flex flex-col bg-bg-app">
                    <div v-if="isEditing" class="grow overflow-hidden p-4 sm:p-6">
                        <CodeMirrorComponent 
                            v-model="form.content" 
                            language="markdown"
                            class="h-full w-full rounded-2xl border border-border-main overflow-hidden shadow-xs"
                        />
                    </div>
                    <div v-else class="grow overflow-y-auto custom-scrollbar p-6 sm:p-12 prose dark:prose-invert max-w-4xl mx-auto w-full">
                        <MessageContentRenderer :content="form.content || '*Note is empty.*'" />
                    </div>
                </div>
            </div>
        </template>
    </PageViewLayout>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>