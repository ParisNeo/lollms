<template>
    <div v-if="renderable" class="statusbar bg-gray-50 dark:bg-gray-700/50 p-1 border-t border-gray-300 dark:border-gray-600 text-xs text-gray-500 dark:text-gray-400 text-right px-2 select-none">
        <span>{{ charCount }} characters, {{ wordCount }} words</span>
    </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
    modelValue: { type: String, required: true },
    renderable: { type: Boolean, default: false }
});

const charCount = computed(() => props.modelValue.length);
const wordCount = computed(() => props.modelValue.trim() ? props.modelValue.trim().split(/\s+/).length : 0);
</script>