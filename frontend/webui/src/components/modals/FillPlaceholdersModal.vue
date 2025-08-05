<script setup>
import { ref, computed, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('fillPlaceholders'));

const placeholders = ref([]);
const values = ref({});
const templateWithoutDefs = ref('');

function parsePromptTemplate(template) {
    const parsedPlaceholders = {};
    
    const defRegex = /@<(\w+?)>@([\s\S]*?)@<\/\1>@/g;
    let remainingTemplate = template.replace(defRegex, (match, name, content) => {
        const details = {
            name: name,
            title: name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
            type: 'text',
            options: null,
            help: null,
            value: ''
        };
        
        content.split('\n').forEach(line => {
            const [key, ...valueParts] = line.split(':');
            const value = valueParts.join(':').trim();
            if (key && value) {
                const keyTrimmed = key.trim();
                if (keyTrimmed === 'title') details.title = value;
                if (keyTrimmed === 'type' && ['str', 'text', 'int', 'float'].includes(value)) details.type = value;
                if (keyTrimmed === 'options') details.options = value.split(',').map(s => s.trim());
                if (keyTrimmed === 'help') details.help = value;
            }
        });

        if (details.options && details.options.length > 0) {
            details.value = details.options[0];
        } else if (details.type === 'int' || details.type === 'float') {
            details.value = 0;
        }
        
        parsedPlaceholders[name] = details;
        return '';
    });

    const simpleRegex = /@<(\w+?)>@/g;
    let match;
    while ((match = simpleRegex.exec(remainingTemplate)) !== null) {
        const name = match[1];
        if (!parsedPlaceholders[name]) {
            parsedPlaceholders[name] = {
                name: name,
                title: name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                type: 'text',
                options: null,
                help: null,
                value: ''
            };
        }
    }
    
    return {
        placeholders: Object.values(parsedPlaceholders),
        templateWithoutDefs: remainingTemplate.trim()
    };
}

onMounted(() => {
    if (props.value?.promptTemplate) {
        const { placeholders: parsed, templateWithoutDefs: template } = parsePromptTemplate(props.value.promptTemplate);
        placeholders.value = parsed;
        templateWithoutDefs.value = template;
        values.value = parsed.reduce((acc, p) => {
            acc[p.name] = p.value;
            return acc;
        }, {});
    }
});

function handleConfirm() {
    let filledPrompt = templateWithoutDefs.value;
    for (const placeholder of placeholders.value) {
        const valueToInsert = values.value[placeholder.name] || '';
        const regex = new RegExp(`@<${placeholder.name}>@`, 'g');
        filledPrompt = filledPrompt.replace(regex, valueToInsert);
    }
    
    if (props.value?.onConfirm) {
        props.value.onConfirm(filledPrompt);
    }
    uiStore.closeModal('fillPlaceholders');
}

function getInputType(type) {
    if (type === 'int') return 'number';
    if (type === 'float') return 'number';
    return 'text';
}

function getStepForNumber(type) {
    return type === 'float' ? 'any' : '1';
}
</script>

<template>
    <GenericModal modalName="fillPlaceholders" title="Fill Prompt Placeholders">
        <template #body>
            <div v-if="placeholders.length > 0" class="space-y-4">
                <div v-for="p in placeholders" :key="p.name">
                    <label :for="`placeholder-${p.name}`" class="label">{{ p.title }}</label>
                    <p v-if="p.help" class="text-xs text-gray-500 mb-1">{{ p.help }}</p>
                    
                    <select v-if="p.options" v-model="values[p.name]" :id="`placeholder-${p.name}`" class="input-field">
                        <option v-for="option in p.options" :key="option" :value="option">{{ option }}</option>
                    </select>

                    <textarea v-else-if="p.type === 'text'" v-model="values[p.name]" :id="`placeholder-${p.name}`" rows="4" class="input-field"></textarea>
                    
                    <input v-else :type="getInputType(p.type)" :step="getStepForNumber(p.type)" v-model="values[p.name]" :id="`placeholder-${p.name}`" class="input-field">
                </div>
            </div>
            <div v-else class="text-center text-gray-500">
                <p>No placeholders were found in this prompt.</p>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('fillPlaceholders')" class="btn btn-secondary">Cancel</button>
            <button @click="handleConfirm" class="btn btn-primary">Confirm</button>
        </template>
    </GenericModal>
</template>