<script setup>
import { computed } from 'vue';

const props = defineProps({
  data: {
    type: [Object, Array, String, Number, Boolean, null],
    required: true,
  },
  level: {
    type: Number,
    default: 0,
  },
  isRoot: {
    type: Boolean,
    default: true,
  }
});

const dataType = computed(() => {
  if (props.data === null) return 'null';
  if (Array.isArray(props.data)) return 'array';
  return typeof props.data;
});

const isExpandable = computed(() => dataType.value === 'object' || dataType.value === 'array');

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

const indentation = computed(() => ({
  'padding-left': `${props.level * 1.5}rem`
}));

const objectEntries = computed(() => {
    if (dataType.value !== 'object') return [];
    return Object.entries(props.data);
});

</script>

<template>
  <div class="json-viewer" :class="{'root-viewer': isRoot}">
    <!-- Object Renderer -->
    <div v-if="dataType === 'object'" class="json-object">
      <div 
        v-for="([key, value], index) in objectEntries" 
        :key="key" 
        class="json-pair" 
        :style="indentation"
        :class="{ 'error-entry': isErrorKey(key) || isErrorValue(value) }"
      >
        <span class="json-key">{{ key }}:</span>
        <span class="json-value">
          <StepDetail :data="value" :level="level + 1" :is-root="false" />
        </span>
      </div>
    </div>

    <!-- Array Renderer -->
    <div v-else-if="dataType === 'array'" class="json-array">
      <div 
        v-for="(item, index) in data" 
        :key="index" 
        class="json-item" 
        :style="indentation"
      >
        <span class="json-value">
           <StepDetail :data="item" :level="level + 1" :is-root="false" />
        </span>
      </div>
    </div>

    <!-- Primitive Renderers -->
    <div v-else :style="indentation">
        <!-- Base64 Image -->
        <div v-if="isBase64Image" class="json-image-container">
            <img :src="data" alt="Embedded image" class="json-image" />
        </div>
        <!-- String -->
        <span v-else-if="dataType === 'string'" class="json-string">"{{ data }}"</span>
        <!-- Number -->
        <span v-else-if="dataType === 'number'" class="json-number">{{ data }}</span>
        <!-- Boolean -->
        <span v-else-if="dataType === 'boolean'" class="json-boolean">{{ data }}</span>
        <!-- Null -->
        <span v-else-if="dataType === 'null'" class="json-null">null</span>
    </div>
  </div>
</template>

<style scoped>
.json-viewer {
  font-family: 'Fira Code', 'Courier New', monospace;
  font-size: 0.8rem;
  line-height: 1.5;
  color: #abb2bf; /* Default text color for dark themes */
}
.root-viewer {
  background-color: #282c34; /* Dark background for the root element */
  border-radius: 6px;
  padding: 0.5rem 0;
  border: 1px solid #3e4451;
}
.json-pair, .json-item {
  display: flex;
  align-items: flex-start;
  white-space: pre-wrap;
  word-break: break-all;
}
.json-key {
  color: #e06c75; /* Reddish for keys */
  margin-right: 0.5em;
  font-weight: 500;
  flex-shrink: 0;
}
.json-value {
  flex-grow: 1;
}
.json-string {
  color: #98c379; /* Green for strings */
}
.json-number {
  color: #d19a66; /* Orange for numbers */
}
.json-boolean {
  color: #56b6c2; /* Cyan for booleans */
}
.json-null {
  color: #c678dd; /* Purple for null */
}
.json-image-container {
    padding: 0.5rem 0;
}
.json-image {
    max-width: 100%;
    max-height: 300px;
    height: auto;
    border-radius: 4px;
    background-color: white;
    border: 1px solid #4a505c;
}

/* Error Styling */
.error-entry .json-key,
.error-entry .json-string,
.error-entry .json-number {
    color: #f87171; /* Bright red for errors */
}

/* Light theme overrides */
.prose.dark\:prose-invert .json-viewer {
  /* Keep dark theme for JSON viewer even in light mode for consistency */
  /* Or define light theme colors if preferred */
}
</style>