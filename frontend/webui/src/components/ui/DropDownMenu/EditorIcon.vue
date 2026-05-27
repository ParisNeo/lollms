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
    const targetWithCollection = `/${props.collection}/${componentName}`.toLowerCase();
    const targetWithoutCollection = `/${componentName}`.toLowerCase();

    let pathKeyToUse = Object.keys(iconModules).find(key => {
        const lowerKey = key.toLowerCase();
        return lowerKey.endsWith(targetWithCollection);
    });

    if (!pathKeyToUse) {
        pathKeyToUse = Object.keys(iconModules).find(key => {
            const lowerKey = key.toLowerCase();
            return lowerKey.endsWith(targetWithoutCollection);
        });
    }

    let rawVueFile = null;
    if (pathKeyToUse) {
      rawVueFile = await iconModules[pathKeyToUse]();
    } else {
      console.warn(`Icon '${props.name}' (expected as ${componentName}) not found. Using fallback.`);
      const fallbackKey = Object.keys(iconModules).find(key => key.toLowerCase().endsWith('/iconcode.vue'));
      if (fallbackKey) {
        rawVueFile = await iconModules[fallbackKey]();
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

<style scoped>
span :deep(svg) {
  width: 100%;
  height: 100%;
}
</style>