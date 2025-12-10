<template>
    <GenericModal modal-name="enhancePrompt" title="Enhance Prompt" max-width-class="max-w-lg">
        <template #body>
            <div class="space-y-4">
                <p class="text-sm text-gray-600 dark:text-gray-300">
                    Configure how the AI should enhance your prompt.
                </p>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Instructions (Optional)</label>
                    <textarea 
                        v-model="localInstructions" 
                        rows="3" 
                        class="input-field w-full text-sm" 
                        placeholder="e.g. 'Make it more cinematic', 'Add cyberpunk elements', 'Focus on lighting'"
                    ></textarea>
                </div>

                <div>
                    <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Mode</label>
                    <div class="flex gap-4">
                        <label class="flex items-center gap-2 cursor-pointer">
                            <input type="radio" v-model="localMode" value="description" class="text-blue-600 focus:ring-blue-500">
                            <span class="text-sm">Description (Enhance details)</span>
                        </label>
                        <label class="flex items-center gap-2 cursor-pointer">
                            <input type="radio" v-model="localMode" value="update" class="text-blue-600 focus:ring-blue-500">
                            <span class="text-sm">Update (Apply instructions)</span>
                        </label>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('enhancePrompt')" class="btn btn-secondary">Cancel</button>
            <button @click="handleConfirm" class="btn btn-primary">Enhance</button>
        </template>
    </GenericModal>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from './GenericModal.vue';

const uiStore = useUiStore();
const props = computed(() => uiStore.modalData('enhancePrompt'));

const localInstructions = ref('');
const localMode = ref('description');

// Sync with props when modal opens
watch(props, (newProps) => {
    if (newProps) {
        localInstructions.value = newProps.instructions || '';
        localMode.value = newProps.mode || 'description';
    }
}, { immediate: true });

function handleConfirm() {
    if (props.value?.onConfirm) {
        props.value.onConfirm({
            instructions: localInstructions.value,
            mode: localMode.value
        });
    }
    uiStore.closeModal('enhancePrompt');
}
</script>
