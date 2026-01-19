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
        
        <!-- Processing Mode Toggle -->
        <div class="mb-6 bg-blue-50 dark:bg-blue-900/20 rounded-xl p-4 border border-blue-100 dark:border-blue-800">
            <label class="flex items-center gap-3 cursor-pointer">
                <input 
                    type="checkbox" 
                    v-model="data.delay_processing" 
                    class="w-5 h-5 rounded text-blue-600 focus:ring-blue-500"
                />
                <div>
                    <span class="text-sm font-bold text-gray-900 dark:text-white">Manual Mode (Create Empty Notebook)</span>
                    <p class="text-xs text-gray-600 dark:text-gray-400 mt-1">
                        Just collect sources and create the notebook skeleton. You'll interact with the AI manually later using action buttons.
                    </p>
                </div>
            </label>
        </div>
        
        <div class="flex-grow flex flex-col bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border dark:border-gray-700">
            <div class="flex justify-between items-center mb-2">
                 <label class="text-xs font-bold uppercase text-gray-500">
                    Instructions for AI (Optional)
                 </label>
                 <button 
                    @click="getSuggestedPrompt" 
                    class="text-xs text-blue-600 font-bold hover:underline"
                >
                    ✨ Auto-Fill
                </button>
            </div>
            <textarea 
                v-model="data.initialPrompt" 
                class="input-field w-full h-full min-h-[200px] p-4 text-base resize-none leading-relaxed" 
                placeholder="Optional: Tell the AI what kind of analysis or report you want to start building immediately (e.g. 'Analyze the life and contributions of Alan Turing')"
            ></textarea>
            <p class="text-[10px] text-gray-500 mt-2">
                If left blank, the notebook will be created with empty tabs ready for your manual input.
            </p>
        </div>
    </div>
</template>
