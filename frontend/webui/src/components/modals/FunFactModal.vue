<script setup>
import { ref, watch, computed } from 'vue';
import GenericModal from './GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { storeToRefs } from 'pinia';

const uiStore = useUiStore();
const adminStore = useAdminStore();
const { funFactCategories } = storeToRefs(adminStore);

const modalProps = computed(() => uiStore.modalData('funFact'));
const fact = computed(() => modalProps.value?.fact);
const onSave = computed(() => modalProps.value?.onSave);

const form = ref({ content: '', category_id: null });
const isLoading = ref(false);
const isEditMode = computed(() => !!fact.value);

watch(fact, (newFact) => {
    if (newFact) {
        form.value = { content: newFact.content, category_id: newFact.category_id };
    } else {
        form.value = { content: '', category_id: funFactCategories.value[0]?.id || null };
    }
}, { immediate: true });

async function handleSubmit() {
    if (!form.value.category_id) {
        uiStore.addNotification('Please select a category.', 'warning');
        return;
    }
    isLoading.value = true;
    try {
        if (isEditMode.value) {
            await adminStore.updateFunFact(fact.value.id, form.value);
        } else {
            await adminStore.createFunFact(form.value);
        }
        if (onSave.value) onSave.value();
        uiStore.closeModal('funFact');
    } finally {
        isLoading.value = false;
    }
}
</script>

<template>
    <GenericModal modalName="funFact" :title="isEditMode ? 'Edit Fun Fact' : 'Add Fun Fact'">
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-4">
                <div><label for="fact-content" class="label">Content</label><textarea id="fact-content" v-model="form.content" rows="4" class="input-field" required></textarea></div>
                <div><label for="fact-category" class="label">Category</label><select id="fact-category" v-model="form.category_id" class="input-field" required><option v-for="cat in funFactCategories" :key="cat.id" :value="cat.id">{{ cat.name }}</option></select></div>
            </form>
        </template>
        <template #footer>
            <button type="button" @click="uiStore.closeModal('funFact')" class="btn btn-secondary">Cancel</button>
            <button type="button" @click="handleSubmit" class="btn btn-primary" :disabled="isLoading">{{ isLoading ? 'Saving...' : 'Save' }}</button>
        </template>
    </GenericModal>
</template>