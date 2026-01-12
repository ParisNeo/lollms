<script setup>
const props = defineProps({
    data: { type: Object, required: true }
});

function getSuggestedPrompt() {
    props.data.initialPrompt = "Create a comprehensive research summary with key findings, methodology, and detailed analysis based on the provided sources.";
}
</script>

<template>
    <div class="h-full flex flex-col">
        <div class="text-center mb-6">
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Research Settings</h2>
        </div>
        
        <div class="flex-grow flex flex-col bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border dark:border-gray-700">
            <div class="flex justify-between items-center mb-2">
                 <label class="text-xs font-bold uppercase text-gray-500">Research Instructions</label>
                 <button @click="getSuggestedPrompt" class="text-xs text-blue-600 font-bold hover:underline">✨ Auto-Fill</button>
            </div>
            <textarea v-model="data.initialPrompt" class="input-field w-full h-full min-h-[200px] p-4 text-base resize-none leading-relaxed" placeholder="Detailed instructions for the AI research assistant..."></textarea>
        </div>
    </div>
</template>
