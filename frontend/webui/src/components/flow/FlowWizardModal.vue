<template>
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
        <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-4xl h-[70vh] flex flex-col border dark:border-gray-700 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <!-- Header -->
            <div class="p-6 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800/80 flex justify-between items-center">
                <div>
                    <h3 class="text-2xl font-black text-gray-800 dark:text-gray-100 flex items-center gap-3">
                        <IconMagic class="w-8 h-8 text-blue-500" />
                        Create New Workflow
                    </h3>
                    <p class="text-sm text-gray-500 mt-1">Start from scratch or choose a pre-built template.</p>
                </div>
                <button @click="$emit('close')" class="text-gray-400 hover:text-red-500 transition-colors">
                    <IconXMark class="w-8 h-8"/>
                </button>
            </div>

            <!-- Content -->
            <div class="flex-grow overflow-y-auto p-8 custom-scrollbar">
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <!-- Blank Template -->
                    <div @click="createBlank" class="template-card border-dashed border-2 hover:border-blue-500 group">
                        <div class="w-12 h-12 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center mb-4 group-hover:bg-blue-100 dark:group-hover:bg-blue-900 transition-colors">
                            <IconPlus class="w-6 h-6 text-gray-400 group-hover:text-blue-600" />
                        </div>
                        <h4 class="font-bold text-lg mb-2">Blank Canvas</h4>
                        <p class="text-sm text-gray-500 leading-relaxed">Start with a clean slate and build your logic node by node.</p>
                    </div>

                    <!-- Pre-defined Templates -->
                    <div v-for="temp in templates" :key="temp.id" @click="createFromTemplate(temp)" class="template-card hover:shadow-xl hover:-translate-y-1 transition-all border-blue-100 dark:border-blue-900/30">
                        <div class="w-12 h-12 rounded-2xl flex items-center justify-center mb-4 text-2xl shadow-sm" :class="temp.bg">
                            {{ temp.emoji }}
                        </div>
                        <h4 class="font-bold text-lg mb-2">{{ temp.name }}</h4>
                        <p class="text-sm text-gray-500 leading-relaxed">{{ temp.description }}</p>
                        <div class="mt-4 flex flex-wrap gap-1">
                            <span v-for="tag in temp.tags" :key="tag" class="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-[10px] font-bold text-gray-400 uppercase tracking-tighter">{{ tag }}</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="p-4 border-t dark:border-gray-700 text-center text-xs text-gray-400 bg-gray-50 dark:bg-gray-900/50">
                Templates automatically configure your nodes and connections to save time.
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue';
import { useFlowStore } from '../../stores/flow';
import { useUiStore } from '../../stores/ui';
import IconMagic from '../../assets/icons/IconMagic.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';

const emit = defineEmits(['close']);
const flowStore = useFlowStore();
const uiStore = useUiStore();

const templates = [
    {
        id: 'ai-illustrator',
        name: 'AI Illustrator',
        emoji: '🎨',
        bg: 'bg-pink-100 text-pink-600 dark:bg-pink-900/30',
        description: 'Input a topic, AI enhances it into a prompt, and generates a visual masterpiece.',
        tags: ['Generation', 'Image', 'LLM'],
        nodes: [
            { id: 'n1', type: 'input_text', label: 'Idea', x: 50, y: 150, data: { value: 'A futuristic floating city' } },
            { id: 'n2', type: 'llm_generate', label: 'Prompt Maker', x: 300, y: 150, data: { system_prompt: 'Turn the input into a detailed Stable Diffusion prompt.' } },
            { id: 'n3', type: 'text_to_image', label: 'Artist', x: 550, y: 150, data: { width: 1024, height: 1024 } }
        ],
        edges: [
            { id: 'e1', source: 'n1', sourceHandle: 'text', target: 'n2', targetHandle: 'prompt' },
            { id: 'e2', source: 'n2', sourceHandle: 'generated_text', target: 'n3', targetHandle: 'prompt' }
        ]
    },
    {
        id: 'doc-qa',
        name: 'Research Buddy',
        emoji: '📚',
        bg: 'bg-green-100 text-green-600 dark:bg-green-900/30',
        description: 'Queries your local data stores and summarizes findings in markdown.',
        tags: ['Knowledge', 'RAG', 'Markdown'],
        nodes: [
            { id: 'n1', type: 'input_text', label: 'Question', x: 50, y: 150, data: { value: 'Summary of recent reports?' } },
            { id: 'n2', type: 'datastore_query', label: 'Vault Query', x: 300, y: 150, data: { top_k: 5 } },
            { id: 'n3', type: 'llm_generate', label: 'Summarizer', x: 550, y: 150, data: { system_prompt: 'Synthesize a markdown report based on the context.' } }
        ],
        edges: [
            { id: 'e1', source: 'n1', sourceHandle: 'text', target: 'n2', targetHandle: 'query' },
            { id: 'e2', source: 'n2', sourceHandle: 'context', target: 'n3', targetHandle: 'prompt' }
        ]
    },
    {
        id: 'web-summarizer',
        name: 'Web Digest',
        emoji: '🌐',
        bg: 'bg-cyan-100 text-cyan-600 dark:bg-cyan-900/30',
        description: 'Scrapes a URL and converts the content into a high-level summary.',
        tags: ['Web', 'Tool', 'Summary'],
        nodes: [
            { id: 'n1', type: 'input_text', label: 'URL', x: 50, y: 150, data: { value: 'https://news.ycombinator.com' } },
            { id: 'n2', type: 'url_scrape', label: 'Scraper', x: 300, y: 150 },
            { id: 'n3', type: 'llm_generate', label: 'Reporter', x: 550, y: 150, data: { system_prompt: 'Summarize the following markdown content from a webpage.' } }
        ],
        edges: [
            { id: 'e1', source: 'n1', sourceHandle: 'text', target: 'n2', targetHandle: 'url' },
            { id: 'e2', source: 'n2', sourceHandle: 'markdown', target: 'n3', targetHandle: 'prompt' }
        ]
    }
];

async function createBlank() {
    const { confirmed, value } = await uiStore.showConfirmation({
        title: 'New Workflow',
        message: 'Enter a name for your blank workflow:',
        confirmText: 'Create',
        inputType: 'text',
        inputValue: 'My Workflow'
    });
    if (confirmed && value) {
        await flowStore.createFlow(value);
        emit('close');
    }
}

async function createFromTemplate(temp) {
    const flow = await flowStore.createFlow(`${temp.name} - ${Date.now().toString().slice(-4)}`);
    if (flow) {
        await flowStore.saveFlow(flow.id, {
            nodes: temp.nodes,
            edges: temp.edges
        });
        uiStore.addNotification(`Template "${temp.name}" applied!`, 'success');
        emit('close');
    }
}
</script>

<style scoped>
.template-card {
    @apply p-6 rounded-2xl bg-white dark:bg-gray-800 border-2 cursor-pointer flex flex-col items-start text-left;
}
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>
