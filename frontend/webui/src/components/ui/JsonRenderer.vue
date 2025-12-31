<script setup>
import JsonNode from './JsonNode.vue';

defineProps({
  json: {
    type: [Object, Array, String, Number, Boolean, null],
    required: true
  }
});
</script>

<template>
  <div class="json-renderer bg-white dark:bg-gray-900 rounded-lg p-2 overflow-x-auto border border-gray-200 dark:border-gray-700">
    <JsonNode :name="null" :value="json" :is-last="true" />
  </div>
</template>
