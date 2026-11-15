<template>
    <GenericModal modal-name="imageEditorSettings" title="Generation Settings" max-width-class="max-w-xl">
        <template #body>
            <div v-if="settings" class="p-4 space-y-6">
                <div>
                    <label for="model-select" class="block text-sm font-medium">Model</label>
                    <select id="model-select" v-model="settings.selectedModel" class="input-field mt-1">
                        <option disabled value="">Select a model</option>
                        <optgroup v-for="group in dataStore.availableTtiModelsGrouped" :key="group.label" :label="group.label">
                            <option v-for="model in group.items" :key="model.id" :value="model.id">{{ model.name }}</option>
                        </optgroup>
                    </select>
                </div>
                <div>
                    <label for="size" class="block text-sm font-medium">Image Size</label>
                    <select id="size" v-model="settings.imageSize" class="input-field mt-1">
                        <optgroup v-for="group in imageSizeGroups" :key="group.label" :label="group.label">
                            <option v-for="size in group.items" :key="size.value" :value="size.value">{{ size.label }}</option>
                        </optgroup>
                    </select>
                </div>
                <div>
                    <label for="seed" class="block text-sm font-medium">Seed</label>
                    <input id="seed" v-model.number="settings.seed" type="number" class="input-field mt-1" placeholder="-1 for random">
                </div>
                <div>
                    <label class="block text-sm font-medium">Strength: {{ settings.params.strength || 'Default' }}</label>
                    <input type="range" min="0" max="1" step="0.01" v-model.number="settings.params.strength" class="w-full">
                </div>
                
                <div v-for="param in modelConfigurableParameters" :key="param.name">
                    <label :for="`param-${param.name}`" class="block text-sm font-medium capitalize">{{ param.name.replace(/_/g, ' ') }}</label>
                    <select v-if="param.options && param.options.length > 0" :id="`param-${param.name}`" v-model="settings.params[param.name]" class="input-field mt-1">
                        <option v-for="option in parseOptions(param.options)" :key="option" :value="option">{{ option }}</option>
                    </select>
                    <input v-else :type="param.type === 'str' ? 'text' : 'number'" :step="param.type === 'float' ? '0.1' : '1'" :id="`param-${param.name}`" v-model="settings.params[param.name]" class="input-field mt-1" :placeholder="param.default">
                </div>
            </div>
            <div v-else class="p-4 text-center text-gray-500">
                Loading settings...
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('imageEditorSettings')" class="btn btn-primary">Close</button>
        </template>
    </GenericModal>
</template>

<script setup>
import { computed } from 'vue';
import GenericModal from './GenericModal.vue';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';

const uiStore = useUiStore();
const dataStore = useDataStore();

const settings = computed(() => uiStore.modalData('imageEditorSettings')?.settings);

const imageSizeGroups = [
    {
        label: 'Screen / Display',
        items: [
            { value: '1024x1024', label: '1024×1024 (Square 1:1)' },
            { value: '1152x896', label: '1152×896 (Landscape ~4:3)' },
            { value: '896x1152', label: '896×1152 (Portrait ~3:4)' },
            { value: '1216x832', label: '1216×832 (Landscape ~3:2)' },
            { value: '832x1216', label: '832×1216 (Portrait ~2:3)' },
            { value: '1344x768', label: '1344×768 (Widescreen 16:9)' },
            { value: '768x1344', label: '768×1344 (Tall 9:16)' },
            { value: '1536x640', label: '1536×640 (Cinematic ~2.4:1)' },
            { value: '640x1536', label: '640×1536 (Tall Cinematic ~1:2.4)' },
            { value: '512x512', label: '512×512 (Small Square)' },
        ]
    },
    {
        label: 'Print · ISO A-Series (1:√2)',
        items: [
            { value: '640x896', label: 'A6 Portrait (640×896)' },
            { value: '896x1280', label: 'A5 Portrait (896×1280)' },
            { value: '1088x1536', label: 'A4 Portrait (1088×1536)' },
            { value: '1248x1760', label: 'A3 Portrait (1248×1760)' },
            { value: '896x640', label: 'A6 Landscape (896×640)' },
            { value: '1280x896', label: 'A5 Landscape (1280×896)' },
            { value: '1536x1088', label: 'A4 Landscape (1536×1088)' },
            { value: '1760x1248', label: 'A3 Landscape (1760×1248)' },
        ]
    },
    {
        label: 'Print · US Standard',
        items: [
            { value: '1088x1408', label: 'Letter Portrait (1088×1408)' },
            { value: '1408x1088', label: 'Letter Landscape (1408×1088)' },
            { value: '896x1472', label: 'Legal Portrait (896×1472)' },
            { value: '1472x896', label: 'Legal Landscape (1472×896)' },
        ]
    }
];

const modelConfigurableParameters = computed(() => {
    if (!settings.value) return [];
    const modelDetails = dataStore.availableTtiModels.find(m => m.id === settings.value.selectedModel);
    if (!modelDetails?.binding_params) return [];
    
    const params = modelDetails.binding_params.edit_parameters || [];
    const excluded = ['prompt', 'negative_prompt', 'image', 'mask', 'width', 'height', 'seed', 'strength'];
    return params.filter(p => !excluded.includes(p.name));
});

function parseOptions(options) {
    if (typeof options === 'string') {
        return options.split(',').map(o => o.trim()).filter(o => o);
    }
    if (Array.isArray(options)) {
        return options.filter(o => o);
    }
    return [];
}
</script>