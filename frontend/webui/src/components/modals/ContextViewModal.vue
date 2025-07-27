<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';

const uiStore = useUiStore();
const modalProps = computed(() => uiStore.modalData('contextViewer'));
const contextContent = computed(() => modalProps.value?.content || 'Loading context...');

function copyContent() {
    uiStore.copyToClipboard(contextContent.value);
}
</script>

<template>
    <GenericModal modal-name="contextViewer" title="Full Discussion Context" maxWidthClass="max-w-4xl">
        <template #body>
            <div class="relative">
                <button @click="copyContent" class="absolute top-2 right-2 btn btn-secondary btn-sm p-1.5" title="Copy context">
                    <IconCopy class="w-4 h-4" />
                </button>
                <pre class="w-full max-h-[70vh] overflow-auto bg-gray-100 dark:bg-gray-900 p-4 rounded-md text-sm whitespace-pre-wrap break-words font-mono">{{ contextContent }}</pre>
            </div>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('contextViewer')" class="btn btn-secondary">Close</button>
        </template>
    </GenericModal>
</template>