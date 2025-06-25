<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  data: {
    type: [Object, Array, String, Number, Boolean, null],
    required: true,
  },
  level: {
    type: Number,
    default: 0,
  }
});

const dataType = computed(() => {
  if (props.data === null) return 'null';
  if (Array.isArray(props.data)) return 'array';
  return typeof props.data;
});

// This is no longer the primary logic for rendering, but kept for clarity
const isExpandable = computed(() => dataType.value === 'object' || dataType.value === 'array');

const isCollapsed = ref(props.level > 0); // Collapse all but the top level by default

function toggleCollapse() {
  if (isExpandable.value) {
    isCollapsed.value = !isCollapsed.value;
  }
}

const summaryText = computed(() => {
    if (dataType.value === 'object') {
        const keyCount = Object.keys(props.data).length;
        return `Object (${keyCount} key${keyCount === 1 ? '' : 's'})`;
    }
    if (dataType.value === 'array') {
        const itemCount = props.data.length;
        return `Array (${itemCount} item${itemCount === 1 ? '' : 's'})`;
    }
    return '';
});

const isBase64Image = computed(() => {
  if (dataType.value !== 'string') return false;
  return props.data.startsWith('data:image/') && props.data.includes(';base64,');
});

function isErrorKey(key) {
    const lowerKey = key.toLowerCase();
    return lowerKey.includes('error') || lowerKey.includes('fail');
}

function isErrorValue(value) {
    if (typeof value !== 'string') return false;
    const lowerValue = value.toLowerCase();
    return lowerValue === 'error' || lowerValue === 'failed' || lowerValue === 'failure';
}

const objectEntries = computed(() => {
    if (dataType.value !== 'object') return [];
    return Object.entries(props.data);
});
</script>

<template>
  <div class="step-ui-container" :class="{'is-root': level === 0}">
    <!-- Expandable/Collapsible Wrapper (for nested elements) -->
    <div v-if="isExpandable && level > 0" class="collapsible-wrapper">
      <div class="collapsible-header" @click="toggleCollapse">
        <span class="toggle-icon" :class="{'is-open': !isCollapsed}">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4-4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
        </span>
        <span class="summary-text">{{ summaryText }}</span>
      </div>
      <div v-if="!isCollapsed" class="collapsible-content">
        <!-- The actual renderer is now inside the collapsible content -->
        <StepDetail :data="data" :level="level" />
      </div>
    </div>
    
    <!-- Object Renderer -->
    <div v-else-if="dataType === 'object'" class="overflow-container">
      <div v-for="([key, value]) in objectEntries" :key="key" class="ui-entry" :class="{ 'error-entry': isErrorKey(key) || isErrorValue(value) }">
        <div class="ui-key">{{ key }}</div>
        <div class="ui-value">
          <!-- Recursive call for nested data -->
          <StepDetail :data="value" :level="level + 1" />
        </div>
      </div>
    </div>

    <!-- Array Renderer -->
    <div v-else-if="dataType === 'array'" class="overflow-container">
      <div v-for="(item, index) in data" :key="index" class="ui-entry">
        <div class="ui-key is-array-key">[{{ index }}]</div>
        <div class="ui-value">
          <!-- Recursive call for nested data -->
          <StepDetail :data="item" :level="level + 1" />
        </div>
      </div>
    </div>

    <!-- Primitive Value Renderer -->
    <div v-else>
      <div v-if="isBase64Image" class="image-field">
        <img :src="data" alt="Embedded image content" class="embedded-image" />
      </div>
      <span v-else :class="`value-${dataType}`">{{ data }}</span>
    </div>
  </div>
</template>


<style scoped>
.step-ui-container {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 0.85rem;
  width: 100%;
}
.step-ui-container.is-root {
  background-color: rgba(0,0,0,0.05);
  border: 1px solid rgba(0,0,0,0.1);
  border-radius: 8px;
  padding: 0.5rem;
}
/* This is the key fix: The container for the grid now handles its own overflow. */
.overflow-container {
  overflow-x: auto;
  /* Add some subtle scrollbar styling */
  scrollbar-width: thin;
  scrollbar-color: rgba(0,0,0,0.2) transparent;
}
.overflow-container::-webkit-scrollbar {
  height: 6px;
}
.overflow-container::-webkit-scrollbar-track {
  background: transparent;
}
.overflow-container::-webkit-scrollbar-thumb {
  background-color: rgba(0,0,0,0.2);
  border-radius: 10px;
}

.ui-entry {
  display: grid;
  grid-template-columns: minmax(120px, max-content) 1fr; /* Give key enough space */
  gap: 1rem;
  padding: 0.5rem;
  border-bottom: 1px solid rgba(0,0,0,0.08);
}
.ui-entry:last-child {
  border-bottom: none;
}

.ui-key {
  font-weight: 500;
  color: #4a5568;
  white-space: nowrap; /* Key itself should not wrap */
  align-self: start;
}
.is-array-key {
  color: #718096;
  font-family: 'Fira Code', monospace;
}
.ui-value {
  min-width: 0; /* Important for grid/flex items */
  word-break: break-word;
}

/* Value styling */
.value-string { 
  color: #2d3748;
}
.value-number { 
  color: #dd6b20; 
  font-family: 'Fira Code', monospace;
}
.value-boolean { 
  color: #b7791f; 
  font-weight: bold;
}
.value-null { 
  color: #718096; 
  font-style: italic;
}

.image-field {
  background-color: rgba(0,0,0,0.03);
  padding: 0.5rem;
  border-radius: 6px;
  max-width: fit-content;
}
.embedded-image {
  display: block;
  max-width: 100%;
  max-height: 250px;
  border-radius: 4px;
}

.collapsible-wrapper {
  border-left: 2px solid rgba(0,0,0,0.1);
  padding-left: 0.75rem;
}

.step-ui-container > div[class^="value-"], .step-ui-container > .image-field {
  padding: 0.25rem 0.5rem;
}

.ui-value > .step-ui-container.is-root {
    background: none;
    border: none;
    padding: 0;
}

.collapsible-header {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  transition: background-color 0.2s;
  margin-left: -0.75rem;
}
.collapsible-header:hover {
  background-color: rgba(0,0,0,0.05);
}
.toggle-icon {
  transition: transform 0.2s ease-in-out;
  color: #718096;
}
.toggle-icon.is-open {
  transform: rotate(90deg);
}
.summary-text {
  font-style: italic;
  font-size: 0.8rem;
  color: #718096;
}
.collapsible-content {
  padding-top: 0.5rem;
}

/* --- DARK MODE STYLES --- */
.dark .step-ui-container.is-root {
  background-color: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.1);
}
.dark .overflow-container {
   scrollbar-color: rgba(255,255,255,0.2) transparent;
}
.dark .overflow-container::-webkit-scrollbar-thumb {
  background-color: rgba(255,255,255,0.2);
}
.dark .ui-entry {
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.dark .ui-key {
  color: #a0aec0;
}
.dark .value-string { 
  color: #e2e8f0;
}
.dark .value-number { 
  color: #f6ad55;
}
.dark .value-boolean { 
  color: #d69e2e;
}
.dark .error-entry .ui-key,
.dark .error-entry .ui-value {
    color: #f56565 !important;
}
.dark .image-field {
  background-color: rgba(255,255,255,0.05);
}
.dark .collapsible-wrapper {
  border-left-color: rgba(255,255,255,0.1);
}
.dark .collapsible-header:hover {
  background-color: rgba(255,255,255,0.1);
}
</style>