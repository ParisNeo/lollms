<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useNotesStore } from '../../stores/notes';
import { useDiscussionsStore } from '../../stores/discussions';
import GenericModal from './GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';

const uiStore = useUiStore();
const notesStore = useNotesStore();
const discussionsStore = useDiscussionsStore();

const modalData = computed(() => uiStore.modalData('noteEditor'));
const note = computed(() => modalData.value?.note);
// Check modalData.value?.content OR modalData.value?.note?.content
const prefillContent = computed(() => modalData.value?.content || modalData.value?.note?.content); 
const prefillTitle = computed(() => modalData.value?.title || modalData.value?.note?.title);

const title = ref('');
const content = ref('');
const groupId = ref(null);
const isLoading = ref(false);

function initForm() {
    if (note.value && note.value.id) {
        // Editing an existing note
        title.value = note.value.title;
        content.value = note.value.content;
        groupId.value = note.value.group_id;
    } else {
        // Creating a new note (possibly from AI generation)
        title.value = prefillTitle.value || 'New Note';
        content.value = prefillContent.value || '';
        groupId.value = null;
    }
}

watch(() => uiStore.isModalOpen('noteEditor'), (isOpen) => {
    if (isOpen) {
        initForm();
    }
});

onMounted(() => {
    if (uiStore.isModalOpen('noteEditor')) {
        initForm();
    }
});

const groupOptions = computed(() => {
    const flatten = (groups, prefix = '') => {
        let opts = [];
        for (const g of groups) {
            opts.push({ value: g.id, text: prefix + g.name });
            if (g.children && g.children.length > 0) {
                opts = opts.concat(flatten(g.children, prefix + '- '));
            }
        }
        return opts;
    };
    return [{ value: null, text: 'None (Top Level)' }, ...flatten(notesStore.notesTree.groups)];
});

async function handleSave() {
    if (!title.value.trim()) {
        uiStore.addNotification('Title is required.', 'warning');
        return;
    }
    isLoading.value = true;
    try {
        if (note.value && note.value.id) {
            await notesStore.updateNote(note.value.id, { title: title.value, content: content.value, group_id: groupId.value });
        } else {
            await notesStore.createNote({ title: title.value, content: content.value, group_id: groupId.value });
        }
        uiStore.closeModal('noteEditor');
    } finally {
        isLoading.value = false;
    }
}

async function handleImportToDataZone() {
    if (!discussionsStore.currentDiscussionId) {
        uiStore.addNotification('No active discussion.', 'warning');
        return;
    }
    await discussionsStore.appendToDataZone({
        discussionId: discussionsStore.currentDiscussionId,
        content: content.value
    });
}
</script>

<template>
    <GenericModal modalName="noteEditor" :title="note && note.id ? 'Edit Note' : 'New Note'" maxWidthClass="max-w-4xl">
        <template #body>
            <div class="space-y-4 h-[70vh] flex flex-col">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium mb-1">Title</label>
                        <input type="text" v-model="title" class="input-field w-full" placeholder="Note Title">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-1">Group</label>
                        <select v-model="groupId" class="input-field w-full">
                            <option v-for="opt in groupOptions" :key="opt.value" :value="opt.value">{{ opt.text }}</option>
                        </select>
                    </div>
                </div>
                <div class="flex-grow min-h-0 border rounded-md overflow-hidden dark:border-gray-700">
                     <CodeMirrorEditor v-model="content" class="h-full" />
                </div>
            </div>
        </template>
        <template #footer>
            <div class="flex justify-between items-center w-full">
                 <button @click="handleImportToDataZone" class="btn btn-secondary flex items-center gap-2" :disabled="!content || !content.trim()">
                    <IconArrowUpTray class="w-4 h-4" />
                    Import to Data Zone
                </button>
                <div class="flex gap-2">
                    <button @click="uiStore.closeModal('noteEditor')" class="btn btn-secondary">Cancel</button>
                    <button @click="handleSave" class="btn btn-primary" :disabled="isLoading">
                        {{ isLoading ? 'Saving...' : 'Save' }}
                    </button>
                </div>
            </div>
        </template>
    </GenericModal>
</template>
