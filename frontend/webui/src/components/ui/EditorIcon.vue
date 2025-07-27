<script setup>
import { shallowRef, watchEffect } from 'vue';

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


// Use Vite's glob import to get all possible icons
const iconModules = import.meta.glob('/src/assets/icons/**/*.vue');
const icon = shallowRef(null);

watchEffect(async () => {
  if (props.name) {
    const componentName = `Icon${toPascalCase(props.name)}.vue`;
    const pathKey = `/src/assets/icons/${props.collection}/${componentName}`;
    
    if (iconModules[pathKey]) {
      const module = await iconModules[pathKey]();
      icon.value = module.default;
    } else {
      console.warn(`Icon '${props.name}' (expected as ${componentName}) not found at ${pathKey}. Using fallback.`);
      const fallbackModule = await import('../../assets/icons/ui/IconCode.vue');
      icon.value = fallbackModule.default;
    }
  }
});
</script>

<template>
  <component :is="icon" v-if="icon" />
</template>