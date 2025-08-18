<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { storeToRefs } from 'pinia';
import GenericModal from '../ui/GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();
const { promptToEdit: currentPrompt } = storeToRefs(adminStore);

const title = computed(() => {
    return currentPrompt.value && currentPrompt.value.id ? 'Edit System Prompt' : 'Create System Prompt';
});

async function handleSavePrompt() {
    if (!currentPrompt.value) return;
    const { id, ...data } = currentPrompt.value;
    try {
        if (id) {
            await adminStore.updateSystemPrompt(id, data);
        } else {
            const newPrompt = await adminStore.createSystemPrompt(data);
            // Re-open with the new prompt to continue editing if desired
            adminStore.setPromptToEdit(newPrompt); 
        }
        uiStore.closeModal('editSystemPrompt');
    } catch (e) {
        // Error is handled globally
    }
}
</script>

<template>
    <GenericModal modal-name="editSystemPrompt" :title="title" max-width-class="max-w-4xl">
        <template #body>
            <form v-if="currentPrompt" @submit.prevent="handleSavePrompt" class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="label">Name</label>
                        <input v-model="currentPrompt.name" type="text" class="input-field" required>
                    </div>
                    <div>
                        <label class="label">Category</label>
                        <input v-model="currentPrompt.category" type="text" class="input-field">
                    </div>
                </div>
                <div>
                    <label class="label">Author</label>
                    <input v-model="currentPrompt.author" type="text" class="input-field">
                </div>
                <div>
                    <label class="label">Description</label>
                    <textarea v-model="currentPrompt.description" rows="2" class="input-field"></textarea>
                </div>
                <div>
                    <label class="label">Content</label>
                    <CodeMirrorEditor v-model="currentPrompt.content" class="h-64" />
                </div>
            </form>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('editSystemPrompt')" class="btn btn-secondary">Cancel</button>
            <button @click="handleSavePrompt" class="btn btn-primary">{{ currentPrompt && currentPrompt.id ? 'Save Changes' : 'Create' }}</button>
        </template>
    </GenericModal>
</template>