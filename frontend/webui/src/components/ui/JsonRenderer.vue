<script setup>
import { computed } from 'vue';
import JsonNode from './JsonNode.vue';

const props = defineProps({
  json: {
    type: [Object, Array],
    required: true
  },
  level: {
    type: Number,
    default: 0
  }
});

const entries = computed(() => {
  if (props.json === null || typeof props.json !== 'object') {
    return [];
  }
  if (Array.isArray(props.json)) {
    // For arrays, map to a consistent key/value structure
    return props.json.map((value, index) => ({ key: index, value }));
  }
  // For objects, map to a consistent key/value structure
  return Object.entries(props.json).map(([key, value]) => ({ key, value }));
});

const indentationStyle = computed(() => {
    // Apply indentation for nested levels
    return props.level > 0 ? { paddingLeft: `20px` } : {};
});
</script>

<template>
  <div class="json-renderer-container w-full" 
       :style="indentationStyle" 
       :class="{'border-l border-gray-200 dark:border-gray-700': level > 0}">
    <div v-for="entry in entries" :key="entry.key" class="json-entry py-1">
      <JsonNode 
        :item-key="entry.key" 
        :item-value="entry.value" 
        :level="level"
      />
    </div>
  </div>
</template>