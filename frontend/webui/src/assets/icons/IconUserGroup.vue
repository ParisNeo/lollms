<script setup>
defineProps({
class: {
type: String,
default: 'w-6 h-6'
}
});
</script>
<template>
<svg xmlns="http://www.w3.org/2000/svg" :class="class" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M15 21v-1.5a6.375 6.375 0 00-3.262-5.171M9 10a3 3 0 11-6 0 3 3 0 016 0zm3 2a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
</template>