<script setup>
import { computed } from 'vue';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';
import { marked } from 'marked';

const uiStore = useUiStore();

const sourceData = computed(() => uiStore.modalData('sourceViewer'));

const modalTitle = computed(() => {
    return `Source: ${sourceData.value?.document || 'Details'}`;
});

const renderedContent = computed(() => {
  if (sourceData.value && sourceData.value.content) {
    return marked.parse(sourceData.value.content, { breaks: true, gfm: true });
  }
  return '<p class="italic text-gray-500">No content available.</p>';
});

</script>

<template>
  <GenericModal
    v-if="sourceData"
    modalName="sourceViewer"
    :title="modalTitle"
    maxWidthClass="max-w-3xl"
  >
    <template #body>
      <div class="space-y-4">
        <div v-if="sourceData.similarity" class="text-sm text-gray-600 dark:text-gray-400">
          <strong>Similarity Score:</strong>
          <span class="font-semibold text-gray-800 dark:text-gray-200">{{ Math.round(sourceData.similarity) }}%</span>
        </div>
        <div 
          class="prose prose-sm dark:prose-invert max-w-none p-4 border dark:border-gray-700 rounded-md bg-gray-50 dark:bg-gray-900/50"
          v-html="renderedContent"
        >
        </div>
      </div>
    </template>
    <template #footer>
        <button @click="uiStore.closeModal('sourceViewer')" class="btn btn-secondary">Close</button>
    </template>
  </GenericModal>
</template>