<script setup>
defineProps({
  class: {
    type: String,
    default: 'w-6 h-6'
  }
});
</script>
<template>
  <svg 
    xmlns="http://www.w3.org/2000/svg" 
    :class="class" 
    fill="none" 
    viewBox="0 0 24 24" 
    stroke-width="1.5" 
    stroke="currentColor"
  >
    <path stroke-linecap="round" stroke-linejoin="round" d="m4.5 15.75 7.5-7.5 7.5 7.5" />
  </svg>
</template>