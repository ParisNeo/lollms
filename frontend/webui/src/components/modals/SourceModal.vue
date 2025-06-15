<script setup>
import { computed } from 'vue';
import { marked } from 'marked';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';
import hljs from 'highlight.js';

const uiStore = useUiStore();
const source = computed(() => uiStore.modalData('sourceViewer'));

// Configure marked to use highlight.js for code blocks within the source content
marked.setOptions({
  highlight: function (code, lang) {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext';
    try {
        return hljs.highlight(code, { language, ignoreIllegals: true }).value;
    } catch (e) {
        return hljs.highlight(code, { language: 'plaintext', ignoreIllegals: true }).value;
    }
  },
  gfm: true,
  breaks: true,
});

const renderedContent = computed(() => {
  if (source.value && source.value.content) {
    return marked.parse(source.value.content);
  }
  return '<p class="italic text-gray-500">No content available.</p>';
});

const similarityColorClass = computed(() => {
  if (!source.value) return 'bg-gray-500';
  const score = source.value.similarity || 0;
  if (score >= 85) return 'bg-green-500 text-green-500';
  if (score >= 70) return 'bg-yellow-500 text-yellow-500';
  return 'bg-red-500 text-red-500';
});

const similarityTextColor = computed(() => similarityColorClass.value.split(' ')[1]);
</script>

<template>
  <GenericModal 
    v-if="source"
    :modalName="'sourceViewer'" 
    :title="source.document"
    maxWidthClass="max-w-4xl"
  >
    <template #body>
      <div class="space-y-4">
        <!-- Similarity Score -->
        <div class="flex items-center space-x-2 text-sm">
          <span class="font-medium text-gray-700 dark:text-gray-300">Similarity:</span>
          <div class="w-32 bg-gray-200 dark:bg-gray-600 rounded-full h-2.5">
            <div 
              class="h-2.5 rounded-full transition-all duration-500" 
              :class="similarityColorClass.split(' ')[0]" 
              :style="{ width: `${source.similarity || 0}%` }"
            ></div>
          </div>
          <span class="font-semibold" :class="similarityTextColor">{{ Math.round(source.similarity || 0) }}%</span>
        </div>
        
        <!-- Source Content -->
        <div 
          class="prose prose-sm max-w-none dark:prose-invert border-t dark:border-gray-600 pt-4 mt-4"
          v-html="renderedContent"
        >
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="uiStore.closeModal('sourceViewer')" class="btn btn-secondary">
        Close
      </button>
    </template>
  </GenericModal>
</template>

<style>
/* Ensure the prose styles for code blocks are handled correctly within the modal */
.prose pre {
  @apply bg-gray-100 dark:bg-gray-900/50 p-4 rounded-md overflow-x-auto;
}
.prose code {
    @apply text-sm;
}
</style>
--- END OF FILE ---