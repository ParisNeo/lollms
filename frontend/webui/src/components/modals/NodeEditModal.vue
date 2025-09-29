<template>
    <GenericModal modalName="nodeEdit" :title="isEditMode ? 'Edit Node' : 'Create Node'">
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-4">
                <div>
                    <label for="node-label" class="block text-sm font-medium">Label</label>
                    <input id="node-label" v-model="formData.label" type="text" class="input-field mt-1" required>
                </div>
                <div>
                    <label for="node-properties" class="block text-sm font-medium">Properties (JSON)</label>
                    <textarea id="node-properties" v-model="propertiesJson" rows="6" class="input-field mt-1 font-mono"></textarea>
                    <p v-if="jsonError" class="text-xs text-red-500 mt-1">{{ jsonError }}</p>
                </div>
            </form>
        </template>
        <template #footer>
            <button type="button" @click="uiStore.closeModal('nodeEdit')" class="btn btn-secondary">Cancel</button>
            <button type="button" @click="handleSubmit" :disabled="!!jsonError" class="btn btn-primary">{{ isEditMode ? 'Save Changes' : 'Create Node' }}</button>
        </template>
    </GenericModal>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('nodeEdit'));
const isEditMode = computed(() => !!props.value?.node);

const formData = ref({
    id: null,
    label: '',
    properties: {}
});
const propertiesJson = ref('{}');
const jsonError = ref('');

watch(() => props.value, (newProps) => {
    if (newProps?.node) {
        formData.value = { ...newProps.node };
        propertiesJson.value = JSON.stringify(newProps.node.properties || {}, null, 2);
    } else {
        formData.value = { id: null, label: '', properties: {} };
        propertiesJson.value = '{}';
    }
    jsonError.value = '';
}, { immediate: true });

watch(propertiesJson, (newJson) => {
    try {
        formData.value.properties = JSON.parse(newJson);
        jsonError.value = '';
    } catch (e) {
        jsonError.value = 'Invalid JSON format.';
    }
});

function handleSubmit() {
    if (jsonError.value) return;
    if (props.value?.onConfirm) {
        props.value.onConfirm(formData.value);
    }
    uiStore.closeModal('nodeEdit');
}
</script>