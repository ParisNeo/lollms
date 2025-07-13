<script setup>
defineProps({
class: {
type: String,
default: 'w-6 h-6'
}
});
</script>
<template>
<svg xmlns="http://www.w3.org/2000/svg" :class="class" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
<path stroke-linecap="round" stroke-linejoin="round" d="M11 15l-3-3m0 0l3-3m-3 3h8a5 5 0 000-10H6" />
</svg>
</template>