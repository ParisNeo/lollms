<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useMemoriesStore } from '../../stores/memories';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const memoriesStore = useMemoriesStore();

const modalData = computed(() => uiStore.modalData('memoryEditor'));
const memoryToEdit = computed(() => modalData.value?.memory);
const isEditing = computed(() => !!memoryToEdit.value);

const title = ref('');
const content = ref('');
const isLoading = ref(false);

watch(modalData, (newData) => {
    if (newData && newData.memory) {
        title.value = newData.memory.title || '';
        content.value = newData.memory.content || '';
    } else {
        title.value = '';
        content.value = '';
    }
}, { immediate: true });

async function handleSubmit() {
    if (!title.value.trim() || !content.value.trim()) {
        uiStore.addNotification('Title and content are required.', 'warning');
        return;
    }
    
    isLoading.value = true;
    try {
        if (isEditing.value) {
            await memoriesStore.updateMemory(memoryToEdit.value.id, {
                title: title.value,
                content: content.value
            });
        } else {
            await memoriesStore.addMemory({
                title: title.value,
                content: content.value
            });
        }
        uiStore.closeModal('memoryEditor');
    } catch (error) {
        // Error handled in store
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal
        modalName="memoryEditor"
        :title="isEditing ? 'Edit Memory' : 'New Memory'"
        maxWidthClass="max-w-2xl"
    >
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-4 p-1">
                <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Title</label>
                    <input 
                        v-model="title" 
                        type="text" 
                        class="input-field w-full" 
                        placeholder="Memory Title (e.g. User Preferences)"
                        required
                        autofocus
                    >
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Content</label>
                    <textarea 
                        v-model="content" 
                        rows="6" 
                        class="input-field w-full resize-y" 
                        placeholder="Memory content..."
                        required
                    ></textarea>
                </div>
            </form>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('memoryEditor')" class="btn btn-secondary">Cancel</button>
            <button @click="handleSubmit" class="btn btn-primary" :disabled="isLoading">
                {{ isEditing ? 'Save Changes' : 'Create Memory' }}
            </button>
        </template>
    </GenericModal>
</template>
