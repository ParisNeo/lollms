<script setup>
import { ref, watch, computed } from 'vue';
import GenericModal from './GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';

const uiStore = useUiStore();
const adminStore = useAdminStore();

const modalProps = computed(() => uiStore.modalData('funFactCategory'));
const category = computed(() => modalProps.value?.category);
const onSave = computed(() => modalProps.value?.onSave);

const form = ref({ name: '', is_active: true, color: '#3B82F6' });
const isLoading = ref(false);
const isEditMode = computed(() => !!category.value);

watch(category, (newCategory) => {
    if (newCategory) {
        form.value = { ...newCategory };
    } else {
        form.value = { name: '', is_active: true, color: '#3B82F6' };
    }
}, { immediate: true });

async function handleSubmit() {
    isLoading.value = true;
    try {
        if (isEditMode.value) {
            await adminStore.updateFunFactCategory(category.value.id, form.value);
        } else {
            await adminStore.createFunFactCategory(form.value);
        }
        if (onSave.value) onSave.value();
        uiStore.closeModal('funFactCategory');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal modalName="funFactCategory" :title="isEditMode ? 'Edit Category' : 'Add Category'">
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-4">
                <div>
                    <label for="cat-name" class="label">Name</label>
                    <input id="cat-name" type="text" v-model="form.name" class="input-field" required>
                </div>
                <div class="flex items-center gap-4">
                    <label for="cat-color" class="label">Color</label>
                    <input id="cat-color" type="color" v-model="form.color" class="w-12 h-10 p-1 border rounded-md">
                </div>
                <div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <label for="cat-active" class="text-sm font-medium">Active</label>
                    <button @click="form.is_active = !form.is_active" type="button" class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors" :class="form.is_active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600'">
                        <span :class="form.is_active ? 'translate-x-5' : 'translate-x-0'" class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition"></span>
                    </button>
                </div>
            </form>
        </template>
        <template #footer>
            <button type="button" @click="uiStore.closeModal('funFactCategory')" class="btn btn-secondary">Cancel</button>
            <button type="button" @click="handleSubmit" class="btn btn-primary" :disabled="isLoading">{{ isLoading ? 'Saving...' : 'Save' }}</button>
        </template>
    </GenericModal>
</template>