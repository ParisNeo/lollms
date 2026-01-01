<template>
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
        <div class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-7xl h-[90vh] flex flex-col border dark:border-gray-700 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <!-- Header -->
            <div class="p-4 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-800/80">
                <div class="flex items-center gap-3">
                    <h3 class="text-xl font-bold text-gray-800 dark:text-gray-100">{{ isEditing ? 'Edit Node' : 'Create Node' }}</h3>
                    <div v-if="isGenerating" class="flex items-center gap-2 text-xs text-blue-500 font-medium bg-blue-50 dark:bg-blue-900/30 px-2 py-1 rounded-full">
                        <IconAnimateSpin class="w-3.5 h-3.5 animate-spin"/> Designing node...
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <button @click="showHelp = !showHelp" class="btn btn-secondary btn-sm" :class="{'bg-blue-100 text-blue-600': showHelp}">
                        <IconInfo class="w-4 h-4 mr-1"/> API Docs
                    </button>
                    <button @click="$emit('close')" class="text-gray-400 hover:text-red-500 transition-colors p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full">
                        <IconXMark class="w-6 h-6"/>
                    </button>
                </div>
            </div>
            
            <div class="flex-grow flex min-h-0 relative">
                
                <!-- Left Panel: Configuration (Scrollable) -->
                <div class="w-full md:w-1/3 flex flex-col border-r dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/50">
                    <div class="p-4 flex-grow overflow-y-auto custom-scrollbar space-y-6">
                        
                        <!-- Metadata Group -->
                        <div class="space-y-3">
                            <h4 class="text-xs font-black uppercase text-gray-400 tracking-widest border-b dark:border-gray-700 pb-1">Metadata</h4>
                            <div class="grid grid-cols-1 gap-3">
                                <div>
                                    <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">ID (Internal)</label>
                                    <input v-model="form.name" class="input-field w-full text-xs font-mono" placeholder="unique_node_id" :disabled="isEditing" />
                                </div>
                                <div>
                                    <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Label (Display)</label>
                                    <input v-model="form.label" class="input-field w-full text-xs" placeholder="My Custom Node" />
                                </div>
                                <div>
                                    <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Color (Tailwind)</label>
                                    <input v-model="form.color" class="input-field w-full text-xs font-mono" placeholder="bg-blue-100 border-blue-500" />
                                </div>
                                <div>
                                    <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Description</label>
                                    <textarea v-model="form.description" class="input-field w-full text-xs h-16 resize-none" placeholder="What does this node do?"></textarea>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Inputs Group -->
                        <div class="space-y-2">
                            <div class="flex justify-between items-center border-b dark:border-gray-700 pb-1">
                                <h4 class="text-xs font-black uppercase text-gray-400 tracking-widest">Inputs</h4>
                                <button @click="addInput" class="text-blue-500 hover:text-blue-600 text-xs font-bold flex items-center gap-1"><IconPlus class="w-3 h-3"/> Add</button>
                            </div>
                            <div v-if="form.inputs.length === 0" class="text-center py-4 text-xs text-gray-400 italic bg-gray-100 dark:bg-gray-800 rounded">No inputs defined</div>
                            <div v-else class="space-y-2">
                                <div v-for="(inp, idx) in form.inputs" :key="'in'+idx" class="flex gap-2 items-center bg-white dark:bg-gray-800 p-2 rounded border dark:border-gray-700 shadow-sm group">
                                    <input v-model="inp.name" placeholder="key_name" class="input-field-sm flex-1 !text-xs font-mono" />
                                    <select v-model="inp.type" class="input-field-sm w-28 !text-xs">
                                        <option value="string">String</option>
                                        <option value="int">Int</option>
                                        <option value="float">Float</option>
                                        <option value="boolean">Bool</option>
                                        <option value="image">Image</option>
                                        <option value="node_ref">NodeRef</option>
                                        <option value="model_selection">Model Sel</option>
                                        <option value="any">Any</option>
                                    </select>
                                    <button @click="form.inputs.splice(idx,1)" class="text-gray-400 hover:text-red-500 transition-colors"><IconTrash class="w-3.5 h-3.5" /></button>
                                </div>
                            </div>
                        </div>

                        <!-- Outputs Group -->
                        <div class="space-y-2">
                            <div class="flex justify-between items-center border-b dark:border-gray-700 pb-1">
                                <h4 class="text-xs font-black uppercase text-gray-400 tracking-widest">Outputs</h4>
                                <button @click="addOutput" class="text-green-500 hover:text-green-600 text-xs font-bold flex items-center gap-1"><IconPlus class="w-3 h-3"/> Add</button>
                            </div>
                            <div v-if="form.outputs.length === 0" class="text-center py-4 text-xs text-gray-400 italic bg-gray-100 dark:bg-gray-800 rounded">No outputs defined</div>
                            <div v-else class="space-y-2">
                                <div v-for="(out, idx) in form.outputs" :key="'out'+idx" class="flex gap-2 items-center bg-white dark:bg-gray-800 p-2 rounded border dark:border-gray-700 shadow-sm group">
                                    <input v-model="out.name" placeholder="key_name" class="input-field-sm flex-1 !text-xs font-mono" />
                                    <select v-model="out.type" class="input-field-sm w-24 !text-xs">
                                        <option value="string">String</option>
                                        <option value="int">Integer</option>
                                        <option value="float">Float</option>
                                        <option value="boolean">Boolean</option>
                                        <option value="image">Image</option>
                                        <option value="list">List</option>
                                        <option value="any">Any</option>
                                    </select>
                                    <button @click="form.outputs.splice(idx,1)" class="text-gray-400 hover:text-red-500 transition-colors"><IconTrash class="w-3.5 h-3.5" /></button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Panel: Editor & Tools -->
                <div class="w-full md:w-2/3 flex flex-col h-full bg-gray-900 text-gray-200 relative">
                    
                    <!-- Code Toolbar -->
                    <div class="flex-shrink-0 p-2 bg-gray-800 border-b border-gray-700 flex justify-between items-center">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-mono text-blue-400 font-bold px-2">code.py</span>
                            <div class="h-4 w-px bg-gray-600"></div>
                            <button @click="activeTab = 'code'" class="px-3 py-1 rounded text-xs font-medium transition-colors" :class="activeTab === 'code' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'">Editor</button>
                            <button @click="activeTab = 'test'" class="px-3 py-1 rounded text-xs font-medium transition-colors" :class="activeTab === 'test' ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-white'">Test / Debug</button>
                        </div>
                        
                        <div class="flex items-center gap-2" v-if="activeTab === 'code'">
                            <div class="relative group">
                                <input v-model="aiPrompt" @keydown.enter="generateCode" class="bg-gray-900 border border-gray-600 text-xs text-gray-200 rounded-l-md px-2 py-1 w-48 focus:w-64 transition-all focus:outline-none focus:border-blue-500" placeholder="e.g. Node that takes text and reverses it" />
                                <button @click="generateCode" class="bg-blue-600 hover:bg-blue-500 text-white text-xs px-3 py-1 rounded-r-md font-medium border-t border-b border-r border-blue-600" :disabled="isGenerating">
                                    <IconSparkles class="w-3 h-3 inline mr-1" /> AI Design
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- EDITOR TAB -->
                    <div v-show="activeTab === 'code'" class="flex-grow relative flex flex-col min-h-0">
                        <div class="flex-grow relative overflow-hidden">
                            <CodeMirrorEditor 
                                v-model="form.code" 
                                class="absolute inset-0 h-full w-full text-sm"
                                :extensions="extensions"
                            />
                        </div>
                        <!-- Help Overlay -->
                        <transition enter-active-class="transition ease-out duration-200" enter-from-class="opacity-0 translate-y-4" enter-to-class="opacity-100 translate-y-0" leave-active-class="transition ease-in duration-150" leave-from-class="opacity-100 translate-y-0" leave-to-class="opacity-0 translate-y-4">
                            <div v-if="showHelp" class="absolute bottom-0 left-0 right-0 bg-gray-800/95 backdrop-blur border-t border-gray-700 p-4 shadow-xl z-20 max-h-[60%] overflow-y-auto custom-scrollbar">
                                <div class="flex justify-between items-start mb-2">
                                    <h4 class="text-sm font-bold text-blue-400">Context API Reference</h4>
                                    <button @click="showHelp = false" class="text-gray-400 hover:text-white"><IconXMark class="w-4 h-4"/></button>
                                </div>
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-gray-300">
                                    <div>
                                        <p class="font-bold text-white mb-1">Structure</p>
                                        <pre class="bg-black/50 p-2 rounded mb-2 overflow-x-auto">class CustomNode:
    def execute(self, inputs, context):
        # inputs: dict
        # return dict (keys match outputs)</pre>
                                        <p class="font-bold text-white mb-1">Text Generation</p>
                                        <code class="block bg-black/50 p-1 rounded mb-1">context.lollms_client.generate_text(prompt, system_prompt=None)</code>
                                        <p class="font-bold text-white mb-1">Get Specific Model Client</p>
                                        <code class="block bg-black/50 p-1 rounded mb-1">client = context.get_client(model_name="binding/model")</code>
                                    </div>
                                    <div>
                                        <p class="font-bold text-white mb-1">Image Generation (TTI)</p>
                                        <code class="block bg-black/50 p-1 rounded mb-1">img_bytes = context.lollms_client.tti.generate_image(prompt, width=512, height=512)</code>
                                        <p class="text-gray-500 mb-2">Returns bytes. Convert to base64 string for output.</p>
                                        
                                        <p class="font-bold text-white mb-1">Audio (TTS)</p>
                                        <code class="block bg-black/50 p-1 rounded mb-1">wav_bytes = context.lollms_client.tts.tts_audio(text)</code>
                                    </div>
                                </div>
                            </div>
                        </transition>
                    </div>

                    <!-- TEST/DEBUG TAB -->
                    <div v-show="activeTab === 'test'" class="flex-grow flex flex-col p-4 space-y-4 bg-gray-900 overflow-y-auto">
                        <div class="grid grid-cols-2 gap-4 h-1/2 min-h-[200px]">
                            <div class="flex flex-col">
                                <label class="text-xs font-bold text-gray-400 mb-2 uppercase">Test Inputs (JSON)</label>
                                <CodeMirrorEditor v-model="testInputsJson" :extensions="jsonExtensions" class="flex-grow border border-gray-700 rounded bg-gray-800" />
                            </div>
                            <div class="flex flex-col">
                                <label class="text-xs font-bold text-gray-400 mb-2 uppercase">Output Result</label>
                                <div class="flex-grow border border-gray-700 rounded bg-black/50 p-2 font-mono text-xs overflow-auto text-green-400 whitespace-pre-wrap">{{ testOutput }}</div>
                            </div>
                        </div>
                        <div class="flex justify-between items-center pt-2 border-t border-gray-800">
                             <div class="text-xs text-red-400 font-mono flex-grow pr-4 max-h-20 overflow-y-auto" v-if="testError">{{ testError }}</div>
                             <div v-else class="flex-grow"></div>
                             <button @click="runTest" class="btn btn-primary btn-sm" :disabled="isTesting">
                                 <IconAnimateSpin v-if="isTesting" class="w-4 h-4 mr-2 animate-spin" />
                                 {{ isTesting ? 'Running...' : 'Run Test' }}
                             </button>
                        </div>
                    </div>

                </div>
            </div>

            <!-- Footer -->
            <div class="p-4 border-t dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-800 rounded-b-lg">
                <div class="text-xs text-gray-500 italic">
                    All inputs and outputs are dictionary keys.
                </div>
                <div class="flex gap-3">
                    <button @click="$emit('close')" class="btn btn-secondary">Cancel</button>
                    <button @click="submit" class="btn btn-primary px-6 shadow-lg">{{ isEditing ? 'Update Node' : 'Create Node' }}</button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';
import { useFlowStore } from '../../stores/flow';
import { useUiStore } from '../../stores/ui';
import apiClient from '../../services/api';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import { python } from '@codemirror/lang-python';
import { json } from '@codemirror/lang-json';
import { oneDark } from '@codemirror/theme-one-dark';

const props = defineProps({
    nodeToEdit: { type: Object, default: null }
});

const emit = defineEmits(['close']);
const flowStore = useFlowStore();
const uiStore = useUiStore();

const extensions = [python(), oneDark];
const jsonExtensions = [json(), oneDark];

const activeTab = ref('code'); 
const showHelp = ref(false);
const isGenerating = ref(false);
const isTesting = ref(false);
const aiPrompt = ref('');
const testInputsJson = ref('{\n  "input": "test value"\n}');
const testOutput = ref('');
const testError = ref('');

const form = ref({
    id: null,
    name: '',
    label: '',
    description: '',
    color: 'bg-indigo-100 dark:bg-indigo-900 border-indigo-500',
    inputs: [{ name: 'input', type: 'string' }],
    outputs: [{ name: 'output', type: 'string' }],
    code: `import json
import base64

class CustomNode:
    def execute(self, inputs, context):
        # Your logic here
        # inputs: dict of values from connected nodes
        # context.lollms_client: access to AI services
        
        val = inputs.get("input", "default")
        
        # Example: Generate Text
        # res = context.lollms_client.generate_text(f"Process {val}")
        
        return {"output": val}
`
});

const isEditing = computed(() => !!props.nodeToEdit);

onMounted(() => {
    if (props.nodeToEdit) {
        form.value = JSON.parse(JSON.stringify(props.nodeToEdit));
        if (!form.value.description) form.value.description = '';
        
        const demoInputs = {};
        form.value.inputs.forEach(i => demoInputs[i.name] = i.type === 'int' ? 0 : "test");
        testInputsJson.value = JSON.stringify(demoInputs, null, 2);
    }
});

function addInput() { form.value.inputs.push({ name: 'new_input', type: 'string' }); }
function addOutput() { form.value.outputs.push({ name: 'new_output', type: 'string' }); }

async function generateCode() {
    if (!aiPrompt.value.trim() || isGenerating.value) return;
    
    isGenerating.value = true;
    try {
        const res = await apiClient.post('/api/flows/generate_code', {
            prompt: aiPrompt.value,
        });
        
        const design = res.data;
        if (design) {
            // SAFE UPDATE LOGIC:
            // 1. Update metadata first (labels/desc/colors)
            form.value.name = design.name || form.value.name;
            form.value.label = design.label || form.value.label;
            form.value.description = design.description || form.value.description;
            if (design.color) form.value.color = design.color;
            
            // 2. Update Schema (Inputs/Outputs)
            if (design.inputs) form.value.inputs = design.inputs;
            if (design.outputs) form.value.outputs = design.outputs;
            
            // 3. Update Python code with a small delay to avoid CodeMirror thrashing
            await nextTick();
            if (design.code) {
                form.value.code = design.code;
            }
            
            // 4. Update Test UI
            const demoInputs = {};
            (design.inputs || []).forEach(i => {
                if (i.type === 'int') demoInputs[i.name] = 0;
                else if (i.type === 'boolean') demoInputs[i.name] = false;
                else demoInputs[i.name] = "test";
            });
            testInputsJson.value = JSON.stringify(demoInputs, null, 2);

            uiStore.addNotification("Node design updated by AI!", "success");
            aiPrompt.value = ''; // Clear prompt
        }
    } catch (e) {
        console.error("Design generation failed:", e);
        uiStore.addNotification("Design generation failed. Check console for details.", "error");
    } finally {
        isGenerating.value = false;
    }
}

async function runTest() {
    if (isTesting.value) return;
    isTesting.value = true;
    testError.value = '';
    testOutput.value = '';
    
    let inputs = {};
    try {
        inputs = JSON.parse(testInputsJson.value);
    } catch (e) {
        testError.value = "Invalid JSON in inputs";
        isTesting.value = false;
        return;
    }

    try {
        const res = await apiClient.post('/api/flows/test_code', {
            code: form.value.code,
            inputs: inputs
        });
        
        if (res.data.status === 'success') {
            testOutput.value = JSON.stringify(res.data.output, null, 2);
        } else {
            testError.value = res.data.error + (res.data.traceback ? `\n\n${res.data.traceback}` : '');
        }
    } catch (e) {
        testError.value = "Network or server error during test.";
    } finally {
        isTesting.value = false;
    }
}

async function submit() {
    if (!form.value.name || !form.value.code) {
        uiStore.addNotification("Name and Code are required", "warning");
        return;
    }
    
    let success;
    if (isEditing.value) {
        success = await flowStore.updateNodeDefinition(form.value.id, form.value);
    } else {
        success = await flowStore.createNodeDefinition(form.value);
    }
    
    if (success) {
        await flowStore.fetchNodeDefinitions(); 
        emit('close');
    }
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }

/* Fixed CodeMirror CSS to ensure it respects parent height and doesn't expand infinitely */
:deep(.cm-editor) {
    height: 100% !important;
    max-height: 100%;
}
:deep(.cm-scroller) {
    overflow: auto;
}
</style>
