<script setup>
import { computed, ref } from 'vue';
import { marked } from 'marked';

const props = defineProps({
  data: { type: [Object, Array, String, Number, Boolean, null], required: true },
  level: { type: Number, default: 0 }
});

const dataType = computed(() => {
  if (props.data === null) return 'null';
  if (Array.isArray(props.data)) return 'array';
  
  // Detect stringified JSON inside logs to auto-expand
  if (typeof props.data === 'string' && props.level <= 1) {
      const trimmed = props.data.trim();
      if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
          return 'json_string';
      }
  }
  
  return typeof props.data;
});

const isExpandable = computed(() => (dataType.value === 'object' || dataType.value === 'array' || dataType.value === 'json_string') && props.data !== null);
const isCollapsed = ref(props.level > 0); 

function toggleCollapse() {
  if (isExpandable.value) isCollapsed.value = !isCollapsed.value;
}

const summaryText = computed(() => {
    if (dataType.value === 'object') return `{ ${Object.keys(props.data).length} items }`;
    if (dataType.value === 'array') return `[ ${props.data.length} items ]`;
    if (dataType.value === 'json_string') return `{ Stringified JSON }`;
    return '';
});

const isBase64Image = computed(() => {
  return typeof props.data === 'string' && props.data.startsWith('data:image/');
});

const objectEntries = computed(() => {
    if (dataType.value !== 'object') return [];
    return Object.entries(props.data);
});

// Helper to check if a value is a JSON string and parse it
function tryParseJson(val) {
    if (typeof val !== 'string') return null;
    const trimmed = val.trim();
    try {
        const parsed = JSON.parse(trimmed);
        return (typeof parsed === 'object') ? parsed : null;
    } catch (e) {
        return null;
    }
}

const renderMarkdown = (text) => {
    if (typeof text !== 'string') return '';
    return marked.parse(text);
};

// Helper to determine if an object is an array of "sources" or "papers"
const isSourceList = computed(() => {
    if (!Array.isArray(props.data)) return false;
    return props.data.length > 0 && (props.data[0].title || props.data[0].source || props.data[0].authors);
});
</script>

<template>
  <div class="step-detail-node" :class="{ 'is-nested': level > 0 }">
    <!-- SPECIAL CASE: Source List (ArXiv, Web search results) -->
    <div v-if="isSourceList && !isCollapsed" class="mt-2 space-y-2">
        <div v-for="(item, idx) in data" :key="idx" class="p-2 bg-gray-50 dark:bg-gray-900/30 border dark:border-gray-800 rounded-lg text-xs">
            <div class="flex justify-between items-start">
                <span class="font-bold text-gray-700 dark:text-gray-300">{{ item.title || item.name }}</span>
                <span v-if="item.year || item.published" class="text-[10px] text-gray-500">{{ item.year || item.published }}</span>
            </div>
            <div v-if="item.authors" class="text-[10px] text-blue-500/80 mt-0.5">by {{ Array.isArray(item.authors) ? item.authors.join(', ') : item.authors }}</div>
            <div v-if="item.summary || item.snippet" class="mt-1 text-gray-500 dark:text-gray-400 line-clamp-2 italic">
                {{ item.summary || item.snippet }}
            </div>
        </div>
    </div>

    <!-- Standard rendering logic... -->
    <div v-if="isExpandable" class="collapsible-container">
      <div class="flex items-center gap-1.5 cursor-pointer select-none group/expand" @click="toggleCollapse">
        <div class="w-4 h-4 flex items-center justify-center text-gray-400 group-hover/expand:text-blue-500 transition-colors" :class="{'rotate-90': !isCollapsed}">
            <svg class="w-2.5 h-2.5 fill-current" viewBox="0 0 20 20"><path d="M6 5l8 5-8 5V5z"/></svg>
        </div>
        <span class="text-[10px] font-mono font-bold text-gray-500 dark:text-gray-400">{{ summaryText }}</span>
      </div>
      
      <div v-if="!isCollapsed" class="mt-1 pl-3 border-l border-gray-200 dark:border-gray-700 space-y-1">
        <!-- Render parsed JSON string -->
        <template v-if="dataType === 'json_string'">
            <StepDetail :data="tryParseJson(data)" :level="level + 1" />
        </template>

        <!-- Render Standard Object -->
        <template v-else-if="dataType === 'object'">
          <div v-for="([key, value]) in objectEntries" :key="key" class="flex flex-col gap-y-1 py-1 border-b border-gray-100 dark:border-gray-800 last:border-0">
            <div class="flex items-center gap-2">
                <span class="text-[9px] font-black text-blue-500 uppercase tracking-widest">{{ key }}</span>
                <div class="h-px flex-grow bg-gray-50 dark:bg-gray-800/50"></div>
            </div>
            
            <!-- Beautiful Rendering for 'content' key -->
            <div v-if="key === 'content' && value" class="flex-1 min-w-0 bg-gray-50 dark:bg-gray-900/50 rounded-lg p-3 shadow-inner">
                <div v-if="tryParseJson(value)">
                    <StepDetail :data="tryParseJson(value)" :level="level + 1" />
                </div>
                <div v-else class="prose prose-xs dark:prose-invert max-w-none" v-html="renderMarkdown(value)"></div>
            </div>

            <div v-else class="flex-1 min-w-0 pl-1">
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
