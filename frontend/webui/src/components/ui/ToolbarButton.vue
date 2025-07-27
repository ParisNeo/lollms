<script setup>
import { computed } from 'vue';
import { uiIconMap, languageIconMap } from '../../assets/icons/icon-maps';

const props = defineProps({
  title: { type: String, required: true },
  icon: { type: String, required: true },
  collection: { type: String, default: 'ui' }, // 'ui' or 'languages'
  buttonClass: { type: [String, Object, Array], default: '' }
});

const iconComponent = computed(() => {
  const map = props.collection === 'languages' ? languageIconMap : uiIconMap;
  return map[props.icon] || null;
});
</script>

<template>
  <button :title="title" :class="buttonClass">
    <component v-if="iconComponent" :is="iconComponent" class="w-4 h-4 flex-shrink-0" />
    <slot></slot>
  </button>
</template>