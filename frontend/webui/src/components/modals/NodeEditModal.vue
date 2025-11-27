<template>
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" @click.self="close">
        <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-lg mx-4 flex flex-col max-h-[90vh]">
            <!-- Header -->
            <div class="flex items-center justify-between p-4 border-b dark:border-gray-700">
                <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
                    {{ isEditing ? 'Edit Node' : 'Add New Node' }}
                </h3>
                <button @click="close" class="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors">
                    <IconX class="w-5 h-5" />
                </button>
            </div>

            <!-- Body -->
            <div class="p-6 overflow-y-auto custom-scrollbar flex-1 space-y-4">
                <!-- Node Type (Label) -->
                <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Node Type (Label) <span class="text-red-500">*</span>
                    </label>
                    <div class="flex gap-2">
                        <select v-model="formData.label" class="input-field flex-1">
                            <option value="" disabled>Select Type</option>
                            <option v-for="type in commonTypes" :key="type" :value="type">{{ type }}</option>
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
                            <input type="text" v-model="prop.key" placeholder="Key (e.g. name)" class="input-field w-1/3 text-xs" />
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
                    {{ isEditing ? 'Update Node' : 'Create Node' }}
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
    node: { type: Object, default: null }, // If provided, we are editing
    onConfirm: { type: Function, required: true },
    onCancel: { type: Function, default: () => {} },
    // Injected by modal system usually, but we handle close manually via emits/props if needed
    // Assuming GenericModal style wrapper might not be used here if direct invoke, 
    // but typically this is rendered inside a wrapper. We just emit events.
    modalId: { type: [String, Number], default: null } 
});

const emit = defineEmits(['close']);

const commonTypes = ['Person', 'Organization', 'Location', 'Date', 'Product', 'Event', 'Concept', 'Technology'];
const isEditing = computed(() => !!props.node);

const formData = ref({
    label: '',
    customLabel: '',
    properties: []
});

onMounted(() => {
    if (props.node) {
        formData.value.label = props.node.label || '';
        if (!commonTypes.includes(formData.value.label)) {
            formData.value.customLabel = formData.value.label;
        }
        
        // Convert properties object to array for editor
        if (props.node.properties) {
            formData.value.properties = Object.entries(props.node.properties).map(([key, value]) => ({ key, value }));
        }
    } else {
        // Defaults
        addProperty('name', '');
    }
});

function addProperty(key = '', value = '') {
    formData.value.properties.push({ key, value });
}

function removeProperty(index) {
    formData.value.properties.splice(index, 1);
}

const isValid = computed(() => {
    return formData.value.label.trim().length > 0;
});

function save() {
    if (!isValid.value) return;

    const finalLabel = formData.value.customLabel.trim() || formData.value.label;
    
    // Convert array back to object
    const finalProps = {};
    formData.value.properties.forEach(p => {
        if (p.key.trim()) {
            finalProps[p.key.trim()] = p.value;
        }
    });

    const payload = {
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
