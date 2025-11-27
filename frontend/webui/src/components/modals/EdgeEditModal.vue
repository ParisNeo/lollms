<template>
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" @click.self="close">
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-lg mx-4 flex flex-col max-h-[90vh]">
            <!-- Header -->
            <div class="flex items-center justify-between p-4 border-b dark:border-gray-700">
                <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
                    {{ isEditing ? 'Edit Relationship' : 'Add New Relationship' }}
                </h3>
                <button @click="close" class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors">
                    <IconX class="w-5 h-5" />
                </button>
            </div>

            <!-- Body -->
            <div class="p-6 overflow-y-auto custom-scrollbar flex-1 space-y-4">
                
                <!-- Source & Target -->
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Source Node ID <span class="text-red-500">*</span></label>
                        <input type="text" v-model="formData.source" :disabled="isEditing" class="input-field font-mono text-xs" placeholder="Source ID" />
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Target Node ID <span class="text-red-500">*</span></label>
                        <input type="text" v-model="formData.target" :disabled="isEditing" class="input-field font-mono text-xs" placeholder="Target ID" />
                    </div>
                </div>

                <!-- Relationship Label -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Relationship (Label) <span class="text-red-500">*</span>
                    </label>
                    <div class="flex gap-2">
                        <select v-model="formData.label" class="input-field flex-1">
                            <option value="" disabled>Select Type</option>
                            <option v-for="type in commonRelations" :key="type" :value="type">{{ type }}</option>
                        </select>
                        <input type="text" v-model="formData.customLabel" placeholder="Custom" class="input-field w-1/3" @input="formData.label = $event.target.value" />
                    </div>
                </div>

                <!-- Properties -->
                <div>
                    <div class="flex justify-between items-center mb-2">
                        <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Properties</label>
                        <button type="button" @click="addProperty" class="text-xs text-blue-600 hover:text-blue-500 font-medium flex items-center gap-1">
                            <IconPlus class="w-3 h-3" /> Add Property
                        </button>
                    </div>
                    
                    <div class="space-y-2">
                        <div v-for="(prop, index) in formData.properties" :key="index" class="flex gap-2 items-start">
                            <input type="text" v-model="prop.key" placeholder="Key" class="input-field w-1/3 text-xs" />
                            <input type="text" v-model="prop.value" placeholder="Value" class="input-field flex-1 text-xs" />
                            <button @click="removeProperty(index)" class="p-2 text-gray-400 hover:text-red-500 transition-colors">
                                <IconTrash class="w-4 h-4" />
                            </button>
                        </div>
                         <div v-if="formData.properties.length === 0" class="text-center py-4 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-dashed dark:border-gray-700">
                            <span class="text-xs text-gray-500">No properties defined</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Footer -->
            <div class="p-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 rounded-b-lg flex justify-end gap-2">
                <button type="button" @click="close" class="btn btn-ghost btn-sm">Cancel</button>
                <button type="button" @click="save" :disabled="!isValid" class="btn btn-primary btn-sm px-4">
                    {{ isEditing ? 'Update Relationship' : 'Create Relationship' }}
                </button>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import IconX from '../../assets/icons/IconClose.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

const props = defineProps({
    edge: { type: Object, default: null },
    sourceId: { type: String, default: '' },
    onConfirm: { type: Function, required: true },
    onCancel: { type: Function, default: () => {} },
});

const emit = defineEmits(['close']);

const commonRelations = ['WORKS_FOR', 'LOCATED_IN', 'HAS', 'PART_OF', 'KNOWS', 'RELATED_TO', 'OCCURRED_ON'];
const isEditing = computed(() => !!props.edge);

const formData = ref({
    source: '',
    target: '',
    label: '',
    customLabel: '',
    properties: []
});

onMounted(() => {
    if (props.edge) {
        formData.value.source = props.edge.source;
        formData.value.target = props.edge.target;
        formData.value.label = props.edge.label;
        if (!commonRelations.includes(props.edge.label)) {
            formData.value.customLabel = props.edge.label;
        }
        if (props.edge.properties) {
            formData.value.properties = Object.entries(props.edge.properties).map(([key, value]) => ({ key, value }));
        }
    } else {
        formData.value.source = props.sourceId || '';
    }
});

function addProperty(key = '', value = '') {
    formData.value.properties.push({ key, value });
}

function removeProperty(index) {
    formData.value.properties.splice(index, 1);
}

const isValid = computed(() => {
    return formData.value.source.trim() && formData.value.target.trim() && formData.value.label.trim();
});

function save() {
    if (!isValid.value) return;

    const finalLabel = formData.value.customLabel.trim() || formData.value.label;
    
    const finalProps = {};
    formData.value.properties.forEach(p => {
        if (p.key.trim()) {
            finalProps[p.key.trim()] = p.value;
        }
    });

    const payload = {
        source: formData.value.source.trim(),
        target: formData.value.target.trim(),
        label: finalLabel,
        properties: finalProps
    };

    props.onConfirm(payload);
    close();
}

function close() {
    if (props.onCancel) props.onCancel();
    emit('close');
}
</script>
