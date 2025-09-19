<script setup>
import { ref, watchEffect } from 'vue';

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
  collection: {
    type: String,
    default: 'ui',
  },
});

function toPascalCase(str) {
  // Converts strings like 'r-project' or 'file-text' to 'RProject' or 'FileText'
  return str
    .toLowerCase()
    .replace(new RegExp(/[-_]+/, 'g'), ' ')
    .replace(new RegExp(/[^\w\s]/, 'g'), '')
    .replace(
      new RegExp(/\s+(.)(\w*)/, 'g'),
      ($1, $2, $3) => `${$2.toUpperCase() + $3}`
    )
    .replace(new RegExp(/\w/), s => s.toUpperCase());
}


// Use Vite's glob import to get all possible icons as raw text
const iconModules = import.meta.glob('/src/assets/icons/**/*.vue', { as: 'raw' });
const svgContent = ref('');

watchEffect(async () => {
  if (props.name) {
    const componentName = `Icon${toPascalCase(props.name)}.vue`;
    const pathKeyWithCollection = `/src/assets/icons/${props.collection}/${componentName}`;
    const pathKeyWithoutCollection = `/src/assets/icons/${componentName}`;
    
    let pathKeyToUse = null;

    if (iconModules[pathKeyWithCollection]) {
      pathKeyToUse = pathKeyWithCollection;
    } else if (iconModules[pathKeyWithoutCollection]) {
      pathKeyToUse = pathKeyWithoutCollection;
    }

    let rawVueFile = null;
    if (pathKeyToUse) {
      rawVueFile = await iconModules[pathKeyToUse]();
    } else {
      console.warn(`Icon '${props.name}' (expected as ${componentName}) not found. Using fallback.`);
      const fallbackPath = '/src/assets/icons/IconCode.vue';
      if (iconModules[fallbackPath]) {
        rawVueFile = await iconModules[fallbackPath]();
      }
    }

    if (rawVueFile) {
        const templateMatch = rawVueFile.match(/<template>([\s\S]*)<\/template>/);
        if (templateMatch && templateMatch[1]) {
            svgContent.value = templateMatch[1];
        } else {
            svgContent.value = '<!-- template tag not found -->';
        }
    } else {
        svgContent.value = '<!-- Icon not found -->';
    }
  }
});
</script>

<template>
  <span v-html="svgContent" class="inline-flex items-center justify-center"></span>
</template>