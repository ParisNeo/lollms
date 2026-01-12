<script setup>
const props = defineProps({
    data: { type: Object, required: true }
});

const stylePresets = [
    'Documentary', 'Vlog', 'Cinematic', 'Tutorial', 'News Report', 'Animation Script', 'Music Video', 'Custom'
];

function getSuggestedPrompt() {
    let final = "Develop a video script with timestamps, visual directions, and B-roll suggestions.";
    final += ` Target duration: around ${props.data.num_slides} scenes/minutes.`;
    final += ` Style: ${props.data.style_preset === 'Custom' ? props.data.custom_style : props.data.style_preset}.`;
    props.data.initialPrompt = final;
}
</script>

<template>
    <div class="h-full flex flex-col">
        <div class="text-center mb-6">
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Video Production Settings</h2>
        </div>

        <div class="mb-6 grid grid-cols-1 md:grid-cols-2 gap-6 bg-white dark:bg-gray-800 p-6 rounded-xl border dark:border-gray-700">
            <div>
                <label class="block text-xs font-bold uppercase text-gray-500 mb-2">Target Scenes</label>
                <div class="flex items-center gap-2">
                     <input type="number" v-model="data.num_slides" min="1" max="50" class="input-field w-24 text-center font-bold" />
                     <span class="text-sm text-gray-500">Scenes</span>
                </div>
            </div>
            <div>
                <label class="block text-xs font-bold uppercase text-gray-500 mb-2">Video Style</label>
                <select v-model="data.style_preset" class="input-field w-full">
                    <option v-for="s in stylePresets" :key="s" :value="s">{{ s }}</option>
                </select>
                <input v-if="data.style_preset === 'Custom'" v-model="data.custom_style" class="input-field w-full mt-2" placeholder="Describe style..." />
            </div>
        </div>

        <div class="flex-grow flex flex-col bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border dark:border-gray-700">
            <div class="flex justify-between items-center mb-2">
                 <label class="text-xs font-bold uppercase text-gray-500">Script Instructions</label>
                 <button @click="getSuggestedPrompt" class="text-xs text-blue-600 font-bold hover:underline">✨ Auto-Fill</button>
            </div>
            <textarea v-model="data.initialPrompt" class="input-field w-full min-h-[120px] p-4 text-base resize-none leading-relaxed" placeholder="Detailed instructions for the script writer..."></textarea>
        </div>
    </div>
</template>
