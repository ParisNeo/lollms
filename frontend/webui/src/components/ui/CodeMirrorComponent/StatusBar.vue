<template>
    <div class="statusbar bg-gray-50 dark:bg-gray-700/50 p-1 border-t border-gray-300 dark:border-gray-600 flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 px-2 select-none">
        <div class="flex items-center gap-3">
            <div class="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 font-bold uppercase text-[9px] tracking-widest border border-blue-200 dark:border-blue-800" :title="`Active language: ${language}`">
                <span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                {{ language }}
            </div>
            <span>{{ charCount }} characters</span>
            
            <button @click="copyContent" class="ml-1 p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-all active:scale-90" title="Copy to clipboard">
                <svg v-if="!justCopied" xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg>
            </button>
        </div>
        
        <div v-if="allowedModes === 'both'" class="flex items-center rounded-md border border-gray-300 dark:border-gray-500 bg-gray-200 dark:bg-gray-900/50 p-0.5">
            <button @click="$emit('set-mode', 'edit')" title="Edit Mode" :class="['mode-button', currentMode === 'edit' ? 'active' : 'inactive']">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.5L14.732 3.732z"></path></svg>
                <span>Edit</span>
            </button>
            <button @click="$emit('set-mode', 'view')" title="Render Mode" :class="['mode-button', currentMode === 'view' ? 'active' : 'inactive']">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
                <span>Render</span>
            </button>
        </div>
        <div v-else class="text-[10px] uppercase font-bold tracking-tight opacity-50 px-2">
            {{ allowedModes === 'edit_only' ? 'Editor Only' : 'Render Only' }}
        </div>
    </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useUiStore } from '../../../stores/ui';

const props = defineProps({
    modelValue: { type: String, required: true },
    language: { type: String, default: 'markdown' },
    allowedModes: { type: String, default: 'both' },
    currentMode: { type: String, default: 'edit' }
});

defineEmits(['set-mode']);

const uiStore = useUiStore();
const justCopied = ref(false);

const charCount = computed(() => (props.modelValue || '').length);

async function copyContent() {
    const success = await uiStore.copyToClipboard(props.modelValue, null);
    if (success) {
        justCopied.value = true;
        setTimeout(() => justCopied.value = false, 2000);
    }
}
const wordCount = computed(() => {
    const text = props.modelValue || '';
    return text.trim() ? text.trim().split(/\s+/).length : 0;
});
</script>

<style scoped>
.mode-button {
    @apply px-2 py-0.5 text-xs rounded-md focus:outline-none focus:ring-1 focus:ring-blue-400 flex items-center gap-1.5;
}
.mode-button.active {
    @apply bg-white dark:bg-gray-600 text-gray-800 dark:text-gray-100 shadow-sm;
}
.mode-button.inactive {
    @apply bg-transparent text-gray-600 dark:text-gray-400 hover:bg-gray-300/50 dark:hover:bg-gray-700/50;
}
</style>