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

const isExpandable = computed(() => dataType.value === 'object' || dataType.value === 'array');

const isCollapsed = ref(props.level > 0); 

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
    <div v-if="isExpandable && level > 0" class="collapsible-wrapper">
      <div class="collapsible-header" @click="toggleCollapse">
        <span class="toggle-icon" :class="{'is-open': !isCollapsed}">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4-4a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>
        </span>
        <span class="summary-text">{{ summaryText }}</span>
      </div>
      <div v-if="!isCollapsed" class="collapsible-content">
        <StepDetail :data="data" :level="level" />
      </div>
    </div>
    
    <div v-else-if="dataType === 'object'" class="overflow-container">
      <div v-for="([key, value]) in objectEntries" :key="key" class="ui-entry" :class="{ 'error-entry': isErrorKey(key) || isErrorValue(value) }">
        <div class="ui-key">{{ key }}</div>
        <div class="ui-value">
          <StepDetail :data="value" :level="level + 1" />
        </div>
      </div>
    </div>

    <div v-else-if="dataType === 'array'" class="overflow-container">
      <div v-for="(item, index) in data" :key="index" class="ui-entry">
        <div class="ui-key is-array-key">[{{ index }}]</div>
        <div class="ui-value">
          <StepDetail :data="item" :level="level + 1" />
        </div>
      </div>
    </div>

    <div v-else>
      <div v-if="isBase64Image" class="image-field">
        <img :src="data" alt="Embedded image content" class="embedded-image" />
      </div>
      <span v-else :class="`value-${dataType}`">{{ data }}</span>
    </div>
  </div>
</template>