<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  data: { type: [Object, Array, String, Number, Boolean, null], required: true },
  level: { type: Number, default: 0 }
});

const dataType = computed(() => {
  if (props.data === null) return 'null';
  if (Array.isArray(props.data)) return 'array';
  return typeof props.data;
});

const isExpandable = computed(() => (dataType.value === 'object' || dataType.value === 'array') && props.data !== null);
const isCollapsed = ref(props.level > 0); 

function toggleCollapse() {
  if (isExpandable.value) isCollapsed.value = !isCollapsed.value;
}

const summaryText = computed(() => {
    if (dataType.value === 'object') return `{ ${Object.keys(props.data).length} items }`;
    if (dataType.value === 'array') return `[ ${props.data.length} items ]`;
    return '';
});

const isBase64Image = computed(() => {
  return typeof props.data === 'string' && props.data.startsWith('data:image/');
});

const objectEntries = computed(() => {
    if (dataType.value !== 'object') return [];
    return Object.entries(props.data);
});
</script>

<template>
  <div class="step-detail-node" :class="{ 'is-nested': level > 0 }">
    <div v-if="isExpandable" class="collapsible-container">
      <div class="flex items-center gap-1.5 cursor-pointer select-none group/expand" @click="toggleCollapse">
        <div class="w-4 h-4 flex items-center justify-center text-gray-400 group-hover/expand:text-blue-500 transition-colors" :class="{'rotate-90': !isCollapsed}">
            <svg class="w-2.5 h-2.5 fill-current" viewBox="0 0 20 20"><path d="M6 5l8 5-8 5V5z"/></svg>
        </div>
        <span class="text-[10px] font-mono font-bold text-gray-500 dark:text-gray-400">{{ summaryText }}</span>
      </div>
      
      <div v-if="!isCollapsed" class="mt-1 pl-3 border-l border-gray-200 dark:border-gray-700 space-y-1">
        <template v-if="dataType === 'object'">
          <div v-for="([key, value]) in objectEntries" :key="key" class="flex flex-col sm:flex-row sm:items-baseline gap-x-2">
            <span class="text-[10px] font-black text-gray-400 dark:text-gray-500 uppercase tracking-tighter whitespace-nowrap">{{ key }}:</span>
            <div class="flex-1 min-w-0">
                <StepDetail :data="value" :level="level + 1" />
            </div>
          </div>
        </template>
        <template v-else-if="dataType === 'array'">
          <div v-for="(item, index) in data" :key="index" class="flex items-baseline gap-2">
            <span class="text-[9px] font-mono text-gray-300 dark:text-gray-600 shrink-0">{{ index }}</span>
            <StepDetail :data="item" :level="level + 1" />
          </div>
        </template>
      </div>
    </div>

    <div v-else class="min-w-0">
      <img v-if="isBase64Image" :src="data" class="max-h-32 rounded border dark:border-gray-700 shadow-sm" />
      <div v-else class="text-xs break-words" :class="`type-${dataType}`">
          <span v-if="dataType === 'string'" class="text-green-700 dark:text-green-400">"{{ data }}"</span>
          <span v-else-if="dataType === 'number'" class="text-blue-600 dark:text-blue-400 font-mono">{{ data }}</span>
          <span v-else-if="dataType === 'boolean'" class="text-amber-600 dark:text-amber-400 font-bold italic">{{ data }}</span>
          <span v-else-if="dataType === 'null'" class="text-gray-400 italic">null</span>
          <span v-else>{{ data }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.step-detail-node { @apply w-full; }
.type-string { @apply leading-relaxed; }
</style>
