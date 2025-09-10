<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { usePromptsStore } from '../../stores/prompts';
import GenericModal from '../ui/GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import IconUploader from '../ui/IconUploader.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import IconTicket from '../../assets/icons/IconTicket.vue';

const uiStore = useUiStore();
const adminStore = useAdminStore();
const promptsStore = usePromptsStore();

const props = computed(() => uiStore.modalData('editPrompt'));
const isSystemPrompt = computed(() => props.value?.isSystemPrompt || false);
const isEditMode = computed(() => props.value?.prompt?.id);

const getInitialState = () => ({
    name: '',
    content: '',
    category: '',
    author: '',
    description: '',
    icon: null
});

const formState = ref(getInitialState());

watch(props, (newProps) => {
    if (newProps && uiStore.isModalOpen('editPrompt')) {
        formState.value = { ...getInitialState(), ...(newProps.prompt || {}) };
    }
}, { immediate: true, deep: true });


const title = computed(() => {
    const action = isEditMode.value ? 'Edit' : 'New';
    const type = isSystemPrompt.value ? 'System' : 'Personal';
    return `${action} ${type} Prompt`;
});

async function handleSavePrompt() {
    if (!formState.value.name || !formState.value.content) {
        uiStore.addNotification('Name and Content are required.', 'warning');
        return;
    }

    try {
        const { id, ...data } = formState.value;
        if (isSystemPrompt.value) {
            if (id) {
                await adminStore.updateSystemPrompt(id, data);
            } else {
                await adminStore.createSystemPrompt(data);
            }
        } else {
            if (id) {
                await promptsStore.updatePrompt(id, data);
            } else {
                await promptsStore.createPrompt(data);
            }
        }
        uiStore.closeModal('editPrompt');
    } catch (e) {
        // Error is handled globally by the API client
    }
}
</script>

<template>
    <GenericModal modal-name="editPrompt" :title="title" max-width-class="max-w-4xl">
        <template #body>
            <form v-if="formState" @submit.prevent="handleSavePrompt" class="space-y-4">
                <div class="flex items-start gap-4">
                    <IconUploader v-model="formState.icon" default-icon-component="IconTicket" />
                    <div class="flex-grow space-y-4">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label for="prompt-name" class="block text-sm font-medium">Name <span class="text-red-500">*</span></label>
                                <input id="prompt-name" v-model="formState.name" type="text" class="input-field mt-1" required>
                            </div>
                            <div>
                                <label for="prompt-category" class="block text-sm font-medium">Category</label>
                                <input id="prompt-category" v-model="formState.category" type="text" class="input-field mt-1" placeholder="e.g., Writing, Coding">
                            </div>
                        </div>
                        <div>
                            <label for="prompt-author" class="block text-sm font-medium">Author</label>
                            <input id="prompt-author" v-model="formState.author" type="text" class="input-field mt-1">
                        </div>
                    </div>
                </div>

                <div>
                    <label for="prompt-description" class="block text-sm font-medium">Description</label>
                    <textarea id="prompt-description" v-model="formState.description" rows="2" class="input-field mt-1"></textarea>
                </div>
                <div>
                    <label for="prompt-content" class="block text-sm font-medium">Content <span class="text-red-500">*</span></label>
                    <CodeMirrorEditor v-model="formState.content" class="mt-1 h-64" />
                </div>
                <div class="p-3 bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500 text-blue-800 dark:text-blue-200">
                    <div class="flex items-center">
                        <IconInfo class="h-5 w-5 mr-2" />
                        <h4 class="font-bold">Placeholder Help</h4>
                    </div>
                    <div class="mt-2 text-xs space-y-1">
                        <p><code class="font-mono bg-blue-200 dark:bg-blue-800/50 px-1 rounded">@&lt;name&gt;@</code>: Simple text replacement.</p>
                        <p>For advanced options with a user-friendly form:</p>
                        <pre class="whitespace-pre-wrap font-mono text-xs bg-blue-100 dark:bg-blue-900/40 p-2 rounded">@&lt;name&gt;@
title (optional): Display Title
type (optional): str | text | int | float | bool
options (optional, only use if you want to fix the value to a restricted subset): comma, separated, list
default (optional): default value
help (optional): A helpful tip for the user.
@&lt;/name&gt;@</pre>
                    </div>
                </div>
            </form>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('editPrompt')" class="btn btn-secondary">Cancel</button>
            <button @click="handleSavePrompt" class="btn btn-primary">{{ isEditMode ? 'Save Changes' : 'Create' }}</button>
        </template>
    </GenericModal>
</template>