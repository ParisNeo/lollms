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
                                    <label class="block text-[10px] font-bold uppercase text-gray-500 mb-1">Category (Group)</label>
                                    <div class="flex gap-1">
                                        <select v-model="form.category" class="input-field w-full text-xs">
                                            <option v-for="cat in existingCategories" :key="cat" :value="cat">{{ cat }}</option>
                                            <option value="NEW_CAT">+ New Category</option>
                                        </select>
                                        <input v-if="form.category === 'NEW_CAT'" v-model="newCategoryName" class="input-field w-full text-xs" placeholder="Category name..." />
                                    </div>
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

                        <!-- Requirements Group -->
                        <div class="space-y-2">
                             <div class="flex justify-between items-center border-b dark:border-gray-700 pb-1">
                                <h4 class="text-xs font-black uppercase text-gray-400 tracking-widest">Library Dependencies</h4>
                                <button @click="addRequirement" class="text-orange-500 hover:text-orange-600 text-xs font-bold flex items-center gap-1"><IconPlus class="w-3 h-3"/> Add</button>
                            </div>
                            <div class="space-y-1">
                                <div v-for="(req, idx) in form.requirements" :key="'req'+idx" class="flex gap-1 items-center">
                                    <input v-model="form.requirements[idx]" placeholder="e.g. opencv-python" class="input-field-sm flex-1 !text-xs font-mono" />
                                    <button @click="form.requirements.splice(idx,1)" class="text-gray-400 hover:text-red-500"><IconTrash class="w-3 h-3" /></button>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Inputs Group -->
                        <div class="space-y-2">
                            <div class="flex justify-between items-center border-b dark:border-gray-700 pb-1">
                                <h4 class="text-xs font-black uppercase text-gray-400 tracking-widest">Inputs</h4>
                                <button @click="addInput" class="text-blue-500 hover:text-blue-600 text-xs font-bold flex items-center gap-1"><IconPlus class="w-3 h-3"/> Add</button>
                            </div>
                            <div class="space-y-2">
                                <div v-for="(inp, idx) in form.inputs" :key="'in'+idx" class="flex gap-2 items-center bg-white dark:bg-gray-800 p-2 rounded border dark:border-gray-700 shadow-sm group">
                                    <input v-model="inp.name" placeholder="key_name" class="input-field-sm flex-1 !text-xs font-mono" />
                                    <select v-model="inp.type" class="input-field-sm w-28 !text-xs">
                                        <option value="string">String</option><option value="int">Int</option>
                                        <option value="float">Float</option><option value="boolean">Bool</option>
                                        <option value="image">Image</option><option value="node_ref">NodeRef</option>
                                        <option value="model_selection">Model Sel</option><option value="any">Any</option>
                                    </select>
                                    <button @click="form.inputs.splice(idx,1)" class="text-gray-400 hover:text-red-500"><IconTrash class="w-3.5 h-3.5" /></button>
                                </div>
                            </div>
                        </div>

                        <!-- Outputs Group -->
                        <div class="space-y-2">
                            <div class="flex justify-between items-center border-b dark:border-gray-700 pb-1">
                                <h4 class="text-xs font-black uppercase text-gray-400 tracking-widest">Outputs</h4>
                                <button @click="addOutput" class="text-green-500 hover:text-green-600 text-xs font-bold flex items-center gap-1"><IconPlus class="w-3 h-3"/> Add</button>
                            </div>
                            <div class="space-y-2">
                                <div v-for="(out, idx) in form.outputs" :key="'out'+idx" class="flex gap-2 items-center bg-white dark:border-gray-800 p-2 rounded border dark:border-gray-700 shadow-sm group">
                                    <input v-model="out.name" placeholder="key_name" class="input-field-sm flex-1 !text-xs font-mono" />
                                    <select v-model="out.type" class="input-field-sm w-24 !text-xs">
                                        <option value="string">String</option><option value="int">Integer</option>
                                        <option value="float">Float</option><option value="boolean">Boolean</option>
                                        <option value="image">Image</option><option value="list">List</option><option value="any">Any</option>
                                    </select>
                                    <button @click="form.outputs.splice(idx,1)" class="text-gray-400 hover:text-red-500"><IconTrash class="w-3.5 h-3.5" /></button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Panel: Editor & Tools -->
                <div class="w-full md:w-2/3 flex flex-col h-full bg-gray-900 text-gray-200 relative">
                    <div class="flex-shrink-0 p-2 bg-gray-800 border-b border-gray-700 flex justify-between items-center">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-mono text-blue-400 font-bold px-2">node_logic.py</span>
                            <div class="h-4 w-px bg-gray-600"></div>
                            <button @click="activeTab = 'code'" class="px-3 py-1 rounded text-xs font-medium" :class="activeTab === 'code' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'">Editor</button>
                            <button @click="activeTab = 'test'" class="px-3 py-1 rounded text-xs font-medium" :class="activeTab === 'test' ? 'bg-green-600 text-white' : 'text-gray-400 hover:text-white'">Test / Debug</button>
                        </div>
                        <div class="flex items-center gap-2" v-if="activeTab === 'code'">
                            <input v-model="aiPrompt" @keydown.enter="generateCode" class="bg-gray-900 border border-gray-600 text-xs text-gray-200 rounded-l-md px-2 py-1 w-48 focus:w-64" placeholder="e.g. Node for video cropping" />
                            <button @click="generateCode" class="bg-blue-600 hover:bg-blue-500 text-white text-xs px-3 py-1 rounded-r-md" :disabled="isGenerating"><IconSparkles class="w-3 h-3 inline mr-1" /> AI Design</button>
                        </div>
                    </div>

                    <div v-show="activeTab === 'code'" class="flex-grow relative flex flex-col min-h-0">
                        <CodeMirrorEditor v-model="form.code" class="absolute inset-0 h-full w-full text-sm" :extensions="extensions" />
                    </div>

                    <div v-show="activeTab === 'test'" class="flex-grow flex flex-col p-4 space-y-4 bg-gray-900 overflow-y-auto">
                        <div class="grid grid-cols-2 gap-4 h-1/2 min-h-[200px]">
                            <div class="flex flex-col"><label class="text-xs font-bold text-gray-400 mb-2 uppercase">Test Inputs (JSON)</label><CodeMirrorEditor v-model="testInputsJson" :extensions="jsonExtensions" class="flex-grow border border-gray-700 rounded bg-gray-800" /></div>
                            <div class="flex flex-col"><label class="text-xs font-bold text-gray-400 mb-2 uppercase">Output Result</label><div class="flex-grow border border-gray-700 rounded bg-black/50 p-2 font-mono text-xs overflow-auto text-green-400 whitespace-pre-wrap">{{ testOutput }}</div></div>
                        </div>
                        <div class="flex justify-end pt-2 border-t border-gray-800">
                             <div class="text-xs text-red-400 font-mono flex-grow pr-4" v-if="testError">{{ testError }}</div>
                             <button @click="runTest" class="btn btn-primary btn-sm" :disabled="isTesting"><IconAnimateSpin v-if="isTesting" class="w-4 h-4 mr-2 animate-spin" />{{ isTesting ? 'Running...' : 'Run Test' }}</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="p-4 border-t dark:border-gray-700 flex justify-end gap-3 bg-gray-50 dark:bg-gray-800 rounded-b-lg">
                <button @click="$emit('close')" class="btn btn-secondary">Cancel</button>
                <button @click="submit" class="btn btn-primary px-6 shadow-lg">{{ isEditing ? 'Update Node' : 'Create Node' }}</button>
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

const props = defineProps({ nodeToEdit: { type: Object, default: null } });
const emit = defineEmits(['close']);
const flowStore = useFlowStore();
const uiStore = useUiStore();

const extensions = [python(), oneDark];
const jsonExtensions = [json(), oneDark];

const activeTab = ref('code'), showHelp = ref(false), isGenerating = ref(false), isTesting = ref(false), aiPrompt = ref(''), testInputsJson = ref('{\n  "input": "test"\n}'), testOutput = ref(''), testError = ref(''), newCategoryName = ref('');

const form = ref({ id: null, name: '', label: '', category: 'General', description: '', color: 'bg-indigo-100 border-indigo-500', inputs: [{ name: 'input', type: 'string' }], outputs: [{ name: 'output', type: 'string' }], requirements: [], code: 'class CustomNode:\n    def execute(self, inputs, context):\n        return {"output": inputs.get("input")}' });

const isEditing = computed(() => !!props.nodeToEdit);
const existingCategories = computed(() => {
    const cats = new Set(flowStore.nodeDefinitions.map(d => d.category));
    cats.add("General"); cats.add("AI Generation"); cats.add("Video Generation"); cats.add("Audio Effects"); cats.add("Image Effects"); cats.add("Transformers"); cats.add("Logic");
    return Array.from(cats).sort();
});

onMounted(() => {
    if (props.nodeToEdit) {
        form.value = JSON.parse(JSON.stringify(props.nodeToEdit));
        if (!form.value.requirements) form.value.requirements = [];
    }
});

function addRequirement() { form.value.requirements.push(''); }
function addInput() { form.value.inputs.push({ name: 'new_input', type: 'string' }); }
function addOutput() { form.value.outputs.push({ name: 'new_output', type: 'string' }); }

async function generateCode() {
    if (!aiPrompt.value.trim() || isGenerating.value) return;
    isGenerating.value = true;
    try {
        const res = await apiClient.post('/api/flows/generate_code', { prompt: aiPrompt.value });
        const design = res.data;
        if (design) {
            form.value.name = design.name || form.value.name;
            form.value.label = design.label || form.value.label;
            form.value.category = design.category || form.value.category;
            form.value.description = design.description || form.value.description;
            if (design.color) form.value.color = design.color;
            if (design.inputs) form.value.inputs = design.inputs;
            if (design.outputs) form.value.outputs = design.outputs;
            if (design.requirements) form.value.requirements = design.requirements;
            await nextTick();
            if (design.code) form.value.code = design.code;
            uiStore.addNotification("Node designed!", "success");
            aiPrompt.value = '';
        }
    } catch (e) { uiStore.addNotification("Failed to design node.", "error"); } finally { isGenerating.value = false; }
}

async function runTest() {
    if (isTesting.value) return;
    isTesting.value = true; testError.value = ''; testOutput.value = '';
    try {
        const inputs = JSON.parse(testInputsJson.value);
        const res = await apiClient.post('/api/flows/test_code', { code: form.value.code, inputs: inputs, requirements: form.value.requirements });
        if (res.data.status === 'success') testOutput.value = JSON.stringify(res.data.output, null, 2);
        else testError.value = res.data.error;
    } catch (e) { testError.value = "Test failed."; } finally { isTesting.value = false; }
}

async function submit() {
    if (!form.value.name || !form.value.code) return uiStore.addNotification("Missing required fields", "warning");
    if (form.value.category === 'NEW_CAT') form.value.category = newCategoryName.value || 'General';
    const success = isEditing.value ? await flowStore.updateNodeDefinition(form.value.id, form.value) : await flowStore.createNodeDefinition(form.value);
    if (success) { await flowStore.fetchNodeDefinitions(); emit('close'); }
}
</script>
