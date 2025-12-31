<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';
import JsonRenderer from '../ui/JsonRenderer.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('commandOutput'));

const output = computed(() => props.value?.output);
const outputType = computed(() => props.value?.outputType || 'text'); // 'json', 'text'
const title = computed(() => props.value?.title || 'Command Output');

const isJson = computed(() => outputType.value === 'json' || (typeof output.value === 'object' && output.value !== null));

</script>

<template>
    <GenericModal modal-name="commandOutput" :title="title" max-width-class="max-w-4xl">
        <template #body>
            <div class="p-4">
                <div v-if="isJson" class="max-h-[70vh] overflow-auto custom-scrollbar">
                    <JsonRenderer :json="output" />
                </div>
                <div v-else class="prose dark:prose-invert max-w-none">
                     <pre class="whitespace-pre-wrap bg-gray-100 dark:bg-gray-900 p-4 rounded-lg text-sm font-mono border dark:border-gray-700">{{ output }}</pre>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('commandOutput')" class="btn btn-primary">Close</button>
        </template>
    </GenericModal>
</template>
