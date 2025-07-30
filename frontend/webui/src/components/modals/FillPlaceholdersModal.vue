<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import GenericModal from '../ui/GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';

const uiStore = useUiStore();
const modalProps = computed(() => uiStore.modalData('fillPlaceholders'));
const promptTemplate = computed(() => modalProps.value?.promptTemplate || '');
const onConfirm = computed(() => modalProps.value?.onConfirm);

const placeholders = ref([]);
const formData = ref({});
const finalPrompt = ref('');

const placeholderRegex = /@<([^:]+):([^:]+):([^:@]+)(?::([^@]+))?>@/g;

function parsePlaceholders() {
    const found = [];
    const initialFormData = {};
    if (promptTemplate.value) {
        let match;
        while ((match = placeholderRegex.exec(promptTemplate.value)) !== null) {
            const [fullMatch, name, type, defaultValue, optionsStr] = match;
            found.push({
                name,
                type,
                defaultValue,
                options: optionsStr ? optionsStr.split('|') : null,
            });
            initialFormData[name] = defaultValue;
        }
    }
    placeholders.value = found;
    formData.value = initialFormData;
}

function updateFinalPrompt() {
    if (!promptTemplate.value) {
        finalPrompt.value = '';
        return;
    }
    let updated = promptTemplate.value;
    for (const placeholder of placeholders.value) {
        const value = formData.value[placeholder.name] || '';
        const regex = new RegExp(`@<${placeholder.name}:.*?@`, 'g');
        updated = updated.replace(regex, value);
    }
    finalPrompt.value = updated;
}

watch(promptTemplate, () => {
    parsePlaceholders();
    updateFinalPrompt();
}, { immediate: true });

watch(formData, updateFinalPrompt, { deep: true });

function handleConfirm() {
    if (onConfirm.value) {
        onConfirm.value(finalPrompt.value);
    }
    uiStore.closeModal('fillPlaceholders');
}
</script>

<template>
    <GenericModal modal-name="fillPlaceholders" title="Fill Prompt Placeholders" maxWidthClass="max-w-3xl">
        <template #body>
            <div class="space-y-6">
                <div v-if="placeholders.length === 0" class="text-center text-gray-500">
                    No placeholders found in this prompt.
                </div>
                <form v-else @submit.prevent="handleConfirm" class="space-y-4">
                    <div v-for="p in placeholders" :key="p.name" class="space-y-1">
                        <label :for="`ph-${p.name}`" class="block text-sm font-medium capitalize">{{ p.name.replace(/_/g, ' ') }}</label>
                        <select v-if="p.options" v-model="formData[p.name]" :id="`ph-${p.name}`" class="input-field">
                            <option v-for="option in p.options" :key="option" :value="option">{{ option }}</option>
                        </select>
                        <textarea v-else-if="p.type === 'text'" v-model="formData[p.name]" :id="`ph-${p.name}`" rows="3" class="input-field"></textarea>
                        <input v-else :type="p.type" v-model="formData[p.name]" :id="`ph-${p.name}`" class="input-field" />
                    </div>
                </form>

                <div>
                    <h4 class="text-sm font-medium mb-2">Final Prompt Preview</h4>
                    <CodeMirrorEditor :model-value="finalPrompt" :options="{ readOnly: true }" class="text-sm max-h-60" />
                </div>
            </div>
        </template>
        <template #footer>
            <button type="button" @click="uiStore.closeModal('fillPlaceholders')" class="btn btn-secondary">Cancel</button>
            <button type="button" @click="handleConfirm" class="btn btn-primary">Use Prompt</button>
        </template>
    </GenericModal>
</template>