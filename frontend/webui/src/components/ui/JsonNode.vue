<script setup>
import { ref, computed, defineAsyncComponent } from 'vue';

// Use defineAsyncComponent for the recursive component to prevent infinite loops
const JsonRenderer = defineAsyncComponent(() => import('./JsonRenderer.vue'));

const props = defineProps({
  itemKey: {
    type: [String, Number],
    required: true
  },
  itemValue: {
    required: true
  },
  level: {
    type: Number,
    default: 0
  }
});

// State for expanding/collapsing this specific node.
// Auto-expands the first two levels for a better initial view.
const isExpanded = ref(props.level < 2);

// Helper function to check if a string is a base64 image
const isBase64Image = (str) => {
  return typeof str === 'string' && str.startsWith('data:image/') && str.includes(';base64,');
};

const valueType = computed(() => {
  if (props.itemValue === null) return 'null';
  if (Array.isArray(props.itemValue)) return 'array';
  if (isBase64Image(props.itemValue)) return 'image';
  if (typeof props.itemValue === 'object') return 'object';
  return typeof props.itemValue;
});

// A node is collapsible if it's an object or array with content
const isCollapsible = computed(() => {
  return (valueType.value === 'object' && Object.keys(props.itemValue).length > 0) ||
         (valueType.value === 'array' && props.itemValue.length > 0);
});

// Show a preview of the content when collapsed
const collapsedPreview = computed(() => {
    if (valueType.value === 'array') {
        return `[... ${props.itemValue.length} items]`;
    }
    if (valueType.value === 'object') {
        return '{...}';
    }
    return '';
})

function toggleExpansion() {
  if (isCollapsible.value) {
    isExpanded.value = !isExpanded.value;
  }
}
</script>

<template>
  <div class="json-node">
    <div class="flex items-start">
      <!-- Key and Toggle Button -->
      <div class="flex-shrink-0 flex items-center" style="min-width: 150px;">
        <button v-if="isCollapsible" @click.prevent="toggleExpansion" class="w-6 h-6 mr-1 flex items-center justify-center text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-600 rounded">
          <span class="font-bold text-lg">{{ isExpanded ? '−' : '+' }}</span>
        </button>
        <span v-else class="w-6 h-6 mr-1 flex-shrink-0"></span> <!-- Placeholder for alignment -->
        <strong class="text-gray-800 dark:text-gray-200 select-all break-all">{{ itemKey }}:</strong>
      </div>

      <!-- Value -->
      <div class="ml-2 flex-grow">
        <!-- Render Collapsed Preview if not expanded -->
        <span v-if="isCollapsible && !isExpanded" @click="toggleExpansion" class="text-gray-500 cursor-pointer hover:underline">
          {{ collapsedPreview }}
        </span>

        <!-- Render Expanded Content or Primitive Values -->
        <template v-else>
          <!-- Nested Object/Array -->
          <JsonRenderer v-if="isCollapsible" :json="itemValue" :level="level + 1" />
          
          <!-- Base64 Image -->
          <img v-else-if="valueType === 'image'" :src="itemValue" alt="Base64 Image" class="max-w-xs max-h-48 rounded-md border border-gray-200 dark:border-gray-700 mt-1" />

          <!-- Boolean -->
          <span v-else-if="valueType === 'boolean'"
                :class="itemValue ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300' : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'"
                class="px-2 py-0.5 text-xs font-semibold rounded-full">
            {{ itemValue }}
          </span>

          <!-- Null -->
          <span v-else-if="valueType === 'null'" class="text-gray-500 italic">null</span>

          <!-- Empty Object/Array -->
          <span v-else-if="valueType === 'object' || valueType === 'array'" class="text-gray-500 italic">
            {{ valueType === 'object' ? '{} (empty object)' : '[] (empty array)' }}
          </span>

          <!-- String or Number -->
          <span v-else class="text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words select-all">
            {{ itemValue }}
          </span>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.json-node {
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.875rem; /* 14px */
}
</style>