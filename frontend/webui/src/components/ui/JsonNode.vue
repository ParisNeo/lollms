<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  name: { type: [String, Number], default: null },
  value: { type: [Object, Array, String, Number, Boolean, null], default: null },
  isLast: { type: Boolean, default: true },
  initialDepth: { type: Number, default: 0 }
});

const isOpen = ref(false);

const isObject = computed(() => props.value !== null && typeof props.value === 'object' && !Array.isArray(props.value));
const isArray = computed(() => Array.isArray(props.value));
const isExpandable = computed(() => isObject.value || isArray.value);

const typeClass = computed(() => {
    if (props.value === null) return 'text-gray-500 italic';
    switch (typeof props.value) {
        case 'string': return 'text-green-600 dark:text-green-400';
        case 'number': return 'text-orange-600 dark:text-orange-400';
        case 'boolean': return 'text-blue-600 dark:text-blue-400 font-bold';
        default: return 'text-gray-700 dark:text-gray-300';
    }
});

const formattedValue = computed(() => {
    if (props.value === null) return 'null';
    if (typeof props.value === 'string') return `"${props.value}"`;
    return String(props.value);
});

const itemCount = computed(() => {
    if (isObject.value) return Object.keys(props.value).length;
    if (isArray.value) return props.value.length;
    return 0;
});

const summary = computed(() => {
    if (isArray.value) return `Array(${itemCount.value})`;
    if (isObject.value) return `Object{${itemCount.value}}`;
    return '';
});

function toggle() {
    isOpen.value = !isOpen.value;
}
</script>

<template>
  <div class="json-node font-mono text-xs sm:text-sm leading-relaxed">
    <div class="flex items-start hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded px-1 -ml-1 transition-colors">
      <!-- Toggler -->
      <button 
        v-if="isExpandable" 
        @click.stop="toggle" 
        class="w-4 h-4 mt-0.5 mr-1 flex items-center justify-center text-gray-400 hover:text-blue-500 transition-colors focus:outline-none"
      >
        <span v-if="isOpen" class="text-[10px]">▼</span>
        <span v-else class="text-[10px]">▶</span>
      </button>
      <span v-else class="w-4 h-4 mr-1 inline-block"></span> <!-- Spacer -->

      <!-- Key -->
      <span v-if="name !== null" class="mr-1.5 text-purple-700 dark:text-purple-400 font-medium select-text">
        {{ name }}:
      </span>

      <!-- Value or Summary -->
      <span v-if="!isExpandable" :class="['select-text break-all', typeClass]">
        {{ formattedValue }}<span v-if="!isLast" class="text-gray-400">,</span>
      </span>
      
      <span v-else class="text-gray-500 cursor-pointer select-none" @click="toggle">
        <span v-if="isOpen" class="text-gray-400">{{ isArray ? '[' : '{' }}</span>
        <span v-else class="italic opacity-80 hover:opacity-100 hover:text-blue-500 hover:underline decoration-dashed decoration-1 underline-offset-2 transition-all">
          {{ isArray ? '[ ... ]' : '{ ... }' }} 
          <span class="text-xs ml-1 opacity-70">{{ itemCount }} items</span>
        </span>
      </span>
    </div>

    <!-- Children -->
    <div v-if="isExpandable && isOpen" class="pl-2 ml-2 border-l border-gray-200 dark:border-gray-700">
      <template v-if="isArray">
        <div v-for="(item, index) in value" :key="index">
          <JsonNode :name="null" :value="item" :is-last="index === value.length - 1" :initial-depth="initialDepth + 1" />
        </div>
      </template>
      <template v-else>
        <div v-for="(val, key, index) in value" :key="key">
          <JsonNode :name="key" :value="val" :is-last="index === Object.keys(value).length - 1" :initial-depth="initialDepth + 1" />
        </div>
      </template>
      <div class="pl-2 text-gray-400 select-none">
        {{ isArray ? ']' : '}' }}<span v-if="!isLast">,</span>
      </div>
    </div>
  </div>
</template>
