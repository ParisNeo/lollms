<script setup>
const props = defineProps({
    data: { type: Object, required: true }
});

const slideFormats = [
    { id: 'TitleImageBody', label: 'Standard Hybrid', desc: 'Balanced text, bullets, and images.' },
    { id: 'ImageOnly', label: 'Full Image', desc: 'Cinematic full-screen visuals. Note: Most AI tools struggle with embedded text.' },
    { id: 'TextOnly', label: 'Text Heavy', desc: 'Detailed slides with titles and bullets.' },
    { id: 'HTML_Graph', label: 'Data & Graphs', desc: 'Dynamic HTML-based data visualizations.' },
    { id: 'TwoColumn', label: 'Comparison', desc: 'Dual column layout for side-by-side analysis.' }
];

const stylePresets = [
    'Photorealistic', 'Corporate Vector', 'Hand Drawn Illustration', 'Minimalist Flat', 'Cyberpunk / Neon', 'Watercolor', 'Abstract 3D', 'Custom'
];

function getSuggestedPrompt() {
    let final = `Create a ${props.data.num_slides}-slide deck about the topic.`;
    final += ` Use the '${props.data.style_preset === 'Custom' ? props.data.custom_style : props.data.style_preset}' visual style.`;
    props.data.initialPrompt = final;
}
</script>

<template>
    <div class="h-full flex flex-col">
        <div class="text-center mb-6">
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Presentation Settings</h2>
        </div>

        <div class="mb-6 grid grid-cols-1 md:grid-cols-2 gap-6 bg-white dark:bg-gray-800 p-6 rounded-xl border dark:border-gray-700">
            <div>
                <label class="block text-xs font-bold uppercase text-gray-500 mb-2">Target Quantity</label>
                <div class="flex items-center gap-2">
                     <input type="number" v-model="data.num_slides" min="1" max="50" class="input-field w-24 text-center font-bold" />
                     <span class="text-sm text-gray-500">Slides</span>
                </div>
            </div>
            <div>
                <label class="block text-xs font-bold uppercase text-gray-500 mb-2">Visual Style</label>
                <select v-model="data.style_preset" class="input-field w-full">
                    <option v-for="s in stylePresets" :key="s" :value="s">{{ s }}</option>
                </select>
                <input v-if="data.style_preset === 'Custom'" v-model="data.custom_style" class="input-field w-full mt-2" placeholder="Describe style..." />
            </div>
            <div class="md:col-span-2">
                <label class="block text-xs font-bold uppercase text-gray-500 mb-2">Structure Format</label>
                <div class="grid grid-cols-2 lg:grid-cols-3 gap-3">
                    <div v-for="fmt in slideFormats" :key="fmt.id" 
                         @click="data.slide_format = fmt.id"
                         class="p-3 border rounded-lg cursor-pointer transition-all hover:bg-gray-50 dark:hover:bg-gray-700"
                         :class="data.slide_format === fmt.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-gray-700'">
                        <div class="font-bold text-sm mb-1">{{ fmt.label }}</div>
                        <div class="text-[10px] text-gray-500 leading-tight">{{ fmt.desc }}</div>
                    </div>
                </div>
                <div v-if="data.slide_format === 'ImageOnly'" class="mt-3 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg flex items-start gap-2">
                    <span class="text-amber-600 font-bold">⚠️</span>
                    <p class="text-[10px] text-amber-700 dark:text-amber-300 italic">Full image templates require high-end TTI models (e.g., Gemini 3, Midjourney) for legible embedded text. Standard models may produce gibberish.</p>
                </div>
            </div>
        </div>

        <div class="flex-grow flex flex-col bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 border dark:border-gray-700">
            <div class="flex justify-between items-center mb-2">
                 <label class="text-xs font-bold uppercase text-gray-500">Instructions for AI</label>
                 <button @click="getSuggestedPrompt" class="text-xs text-blue-600 font-bold hover:underline">✨ Auto-Fill</button>
            </div>
            <textarea v-model="data.initialPrompt" class="input-field w-full min-h-[120px] p-4 text-base resize-none leading-relaxed" placeholder="Detailed instructions..."></textarea>
        </div>
    </div>
</template>
