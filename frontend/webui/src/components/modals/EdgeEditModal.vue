<template>
    <GenericModal modalName="edgeEdit" :title="isEditMode ? 'Edit Edge' : 'Create Edge'">
        <template #body>
            <form @submit.prevent="handleSubmit" class="space-y-4">
                <div>
                    <label for="edge-label" class="block text-sm font-medium">Label</label>
                    <input id="edge-label" v-model="formData.label" type="text" class="input-field mt-1" required>
                </div>
                 <div>
                    <label for="edge-source" class="block text-sm font-medium">Source Node ID</label>
                    <input id="edge-source" v-model.number="formData.source_id" type="number" class="input-field mt-1" required>
                </div>
                 <div>
                    <label for="edge-target" class="block text-sm font-medium">Target Node ID</label>
                    <input id="edge-target" v-model.number="formData.target_id" type="number" class="input-field mt-1" required>
                </div>
                <div>
                    <label for="edge-properties" class="block text-sm font-medium">Properties (JSON)</label>
                    <textarea id="edge-properties" v-model="propertiesJson" rows="4" class="input-field mt-1 font-mono"></textarea>
                    <p v-if="jsonError" class="text-xs text-red-500 mt-1">{{ jsonError }}</p>
                </div>
            </form>
        </template>
        <template #footer>
            <button type="button" @click="uiStore.closeModal('edgeEdit')" class="btn btn-secondary">Cancel</button>
            <button type="button" @click="handleSubmit" :disabled="!!jsonError" class="btn btn-primary">{{ isEditMode ? 'Save Changes' : 'Create Edge' }}</button>
        </template>
    </GenericModal>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('edgeEdit'));
const isEditMode = computed(() => !!props.value?.edge);

const formData = ref({
    id: null,
    label: '',
    source_id: '',
    target_id: '',
    properties: {}
});
const propertiesJson = ref('{}');
const jsonError = ref('');

watch(() => props.value, (newProps) => {
    if (newProps) {
        if (newProps.edge) { // Editing existing edge
            formData.value = {
                id: newProps.edge.id,
                label: newProps.edge.label || '',
                source_id: newProps.edge.source,
                target_id: newProps.edge.target,
                properties: newProps.edge.properties || {}
            };
        } else { // Creating new edge, possibly with pre-filled nodes
            formData.value = {
                id: null,
                label: '',
                source_id: newProps.sourceId || '',
                target_id: newProps.targetId || '',
                properties: {}
            };
        }
        propertiesJson.value = JSON.stringify(formData.value.properties, null, 2);
    } else { // Reset when modal is closed
        formData.value = { id: null, label: '', source_id: '', target_id: '', properties: {} };
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
    uiStore.closeModal('edgeEdit');
}
</script>