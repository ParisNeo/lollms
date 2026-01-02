<template>
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
        <div class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col border dark:border-gray-700 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            
            <!-- Header -->
            <div class="p-4 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-800/80">
                <div class="flex items-center gap-4">
                    <button v-if="step === 'results'" @click="step = 'inputs'" class="p-2 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-full transition-colors text-gray-500" title="Back to Inputs">
                        <IconArrowLeft class="w-5 h-5" />
                    </button>
                    <div>
                        <h3 class="text-xl font-bold text-gray-800 dark:text-gray-100 flex items-center gap-2">
                            <IconPlayCircle class="w-6 h-6 text-green-500" />
                            {{ flowName }}
                        </h3>
                        <div class="flex items-center gap-2 mt-0.5">
                            <span class="text-[10px] font-black uppercase px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-600">
                                {{ step === 'inputs' ? 'Step 1: Configuration' : 'Step 2: Execution' }}
                            </span>
                            <span class="text-[10px] text-gray-400 font-mono" v-if="taskId">Task: {{ taskId.split('-')[0] }}</span>
                        </div>
                    </div>
                </div>
                <button @click="$emit('close')" class="text-gray-400 hover:text-red-500 transition-colors p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full">
                    <IconXMark class="w-6 h-6"/>
                </button>
            </div>

            <!-- Main Content Area -->
            <div class="flex-grow flex flex-col min-h-0 bg-gray-50 dark:bg-gray-900">
                
                <!-- STEP 1: INPUTS -->
                <div v-if="step === 'inputs'" class="flex-grow overflow-y-auto p-6 space-y-6">
                    <div class="max-w-3xl mx-auto">
                        <div class="flex items-center gap-3 mb-6">
                            <div class="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600">
                                <IconSettings class="w-6 h-6" />
                            </div>
                            <div>
                                <h4 class="font-bold text-gray-800 dark:text-white">Workflow Inputs</h4>
                                <p class="text-xs text-gray-500">Configure the variables for this run.</p>
                            </div>
                        </div>

                        <div v-if="requiredInputs.length === 0" class="p-10 text-center border-2 border-dashed dark:border-gray-800 rounded-3xl">
                            <IconCheckCircle class="w-12 h-12 text-green-500 mx-auto mb-3 opacity-20" />
                            <p class="text-gray-500">This workflow is self-contained and requires no manual inputs.</p>
                        </div>
                        
                        <div v-else class="grid grid-cols-1 gap-4">
                            <div v-for="inp in requiredInputs" :key="inp.key" class="bg-white dark:bg-gray-800 p-5 rounded-2xl border dark:border-gray-700 shadow-sm transition-all focus-within:ring-2 focus-within:ring-blue-500/20">
                                <div class="flex justify-between items-center mb-3">
                                    <label class="block text-[10px] font-black uppercase text-gray-400 tracking-widest">
                                        {{ inp.nodeLabel }} <span class="text-gray-300 dark:text-gray-600 mx-1">/</span> {{ inp.inputName }}
                                    </label>
                                    <span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 uppercase">{{ inp.type }}</span>
                                </div>
                                
                                <textarea v-if="inp.type === 'string' && (inputValues[inp.nodeId][inp.inputName].length > 50 || inp.inputName.toLowerCase().includes('prompt'))" 
                                    v-model="inputValues[inp.nodeId][inp.inputName]" 
                                    class="input-field w-full h-32 resize-none" 
                                    placeholder="Enter long text or prompt..."></textarea>
                                
                                <input v-else-if="inp.type === 'int' || inp.type === 'float'" 
                                    type="number" v-model.number="inputValues[inp.nodeId][inp.inputName]" 
                                    class="input-field w-full font-mono" :step="inp.type === 'float' ? 'any' : '1'">
                                
                                <div v-else-if="inp.type === 'boolean'" class="flex items-center gap-3 py-2">
                                    <button @click="inputValues[inp.nodeId][inp.inputName] = !inputValues[inp.nodeId][inp.inputName]" 
                                        class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200" 
                                        :class="inputValues[inp.nodeId][inp.inputName] ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-700'">
                                        <span class="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200" :class="inputValues[inp.nodeId][inp.inputName] ? 'translate-x-5' : 'translate-x-0'"></span>
                                    </button>
                                    <span class="text-sm font-medium">{{ inputValues[inp.nodeId][inp.inputName] ? 'Enabled' : 'Disabled' }}</span>
                                </div>
                                
                                <input v-else v-model="inputValues[inp.nodeId][inp.inputName]" class="input-field w-full" placeholder="Enter value...">
                            </div>
                        </div>
                    </div>
                </div>

                <!-- STEP 2: RESULTS -->
                <div v-if="step === 'results'" class="flex-grow flex flex-col min-h-0">
                    
                    <!-- Progress Bar (Always visible during run) -->
                    <div v-if="isRunning" class="px-6 py-4 bg-white dark:bg-gray-800 border-b dark:border-gray-700">
                        <div class="flex justify-between items-center mb-2">
                            <span class="text-xs font-bold text-blue-600 animate-pulse">WORKFLOW IN PROGRESS...</span>
                            <span class="text-xs font-mono text-gray-500">{{ overallProgress }}%</span>
                        </div>
                        <div class="h-1.5 w-full bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                            <div class="h-full bg-blue-500 transition-all duration-500" :style="{ width: overallProgress + '%' }"></div>
                        </div>
                    </div>

                    <div class="flex-grow overflow-y-auto p-6">
                        <div class="max-w-4xl mx-auto space-y-6">
                            
                            <!-- Error Alert -->
                            <div v-if="executionError" class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-5 animate-in slide-in-from-top-2">
                                <div class="flex items-start gap-4">
                                    <IconError class="w-6 h-6 text-red-500 mt-1" />
                                    <div class="flex-grow min-w-0">
                                        <h4 class="font-bold text-red-700 dark:text-red-400">Execution Error</h4>
                                        <pre class="mt-3 text-xs font-mono whitespace-pre-wrap overflow-x-auto bg-black/5 dark:bg-black/40 p-4 rounded-xl border dark:border-red-900/30 text-red-900 dark:text-red-300 max-h-80">{{ executionError }}</pre>
                                        <button @click="step = 'inputs'" class="mt-4 btn btn-secondary btn-sm">Adjust Inputs & Retry</button>
                                    </div>
                                </div>
                            </div>

                            <!-- Success/Results Grid -->
                            <div v-if="executionResult" class="grid grid-cols-1 gap-6">
                                <div v-for="node in displayNodes" :key="node.id" class="bg-white dark:bg-gray-800 rounded-3xl border dark:border-gray-700 overflow-hidden shadow-sm hover:shadow-md transition-shadow">
                                    <div class="px-6 py-4 bg-gray-50 dark:bg-gray-800/50 border-b dark:border-gray-700 flex justify-between items-center">
                                        <div class="flex items-center gap-3">
                                            <IconCheckCircle class="w-5 h-5 text-green-500" />
                                            <span class="font-bold text-sm tracking-tight">{{ node.label }}</span>
                                        </div>
                                        <span class="text-[10px] text-gray-400 font-mono bg-gray-100 dark:bg-gray-900 px-2 py-0.5 rounded-full">{{ node.id }}</span>
                                    </div>
                                    
                                    <div class="p-6">
                                        <div v-if="getNodeResult(node.id)" class="space-y-8">
                                            <div v-for="(val, outKey) in getNodeResult(node.id)" :key="outKey" class="group">
                                                <div class="flex items-center gap-2 mb-3">
                                                    <div class="h-px flex-grow bg-gray-100 dark:bg-gray-700"></div>
                                                    <span class="text-[9px] font-black uppercase text-gray-400 tracking-[0.2em] whitespace-nowrap">{{ outKey }}</span>
                                                    <div class="h-px flex-grow bg-gray-100 dark:bg-gray-700"></div>
                                                </div>
                                                
                                                <!-- IMAGE RENDERER (ENHANCED) -->
                                                <div v-if="getOutputType(node, outKey) === 'image' || isDataImage(val)" class="relative group/img max-w-2xl mx-auto">
                                                    <div class="rounded-2xl overflow-hidden shadow-2xl border-4 border-white dark:border-gray-700 bg-gray-100 dark:bg-gray-900 ring-1 ring-black/5">
                                                        <img :src="val" class="w-full h-auto block" />
                                                    </div>
                                                    <!-- Image Actions Overlay -->
                                                    <div class="absolute top-4 right-4 flex gap-2 opacity-0 group-hover/img:opacity-100 transition-opacity">
                                                        <button @click="openFullScreen(val)" class="p-2.5 bg-black/60 hover:bg-blue-600 text-white rounded-xl backdrop-blur-md shadow-lg transition-all active:scale-90" title="Full Screen">
                                                            <IconMaximize class="w-5 h-5" />
                                                        </button>
                                                        <button @click="downloadOutputImage(val, outKey)" class="p-2.5 bg-black/60 hover:bg-green-600 text-white rounded-xl backdrop-blur-md shadow-lg transition-all active:scale-90" title="Save Image">
                                                            <IconArrowDownTray class="w-5 h-5" />
                                                        </button>
                                                    </div>
                                                </div>

                                                <!-- MARKDOWN RENDERER -->
                                                <div v-else-if="getOutputType(node, outKey) === 'markdown'" class="prose dark:prose-invert max-w-none bg-white dark:bg-gray-900/50 p-6 rounded-2xl border dark:border-gray-700 shadow-inner">
                                                    <MessageContentRenderer :content="val" />
                                                </div>

                                                <!-- RAW FALLBACK -->
                                                <div v-else class="bg-gray-100 dark:bg-black/40 p-4 rounded-xl font-mono text-xs whitespace-pre-wrap border dark:border-gray-800 break-all overflow-x-auto">
                                                    {{ formatRaw(val) }}
                                                </div>
                                            </div>
                                        </div>
                                        <div v-else class="flex flex-col items-center py-10 text-gray-400 opacity-50">
                                            <IconInfo class="w-8 h-8 mb-2" />
                                            <p class="text-xs uppercase font-black tracking-widest">No Output Data</p>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- Run Logic Placeholder -->
                            <div v-if="isRunning && !executionResult" class="flex flex-col items-center justify-center py-20 text-gray-400">
                                <IconAnimateSpin class="w-12 h-12 text-blue-500 animate-spin mb-4" />
                                <p class="text-sm font-medium animate-pulse">Processing nodes...</p>
                            </div>

                        </div>
                    </div>
                </div>

            </div>

            <!-- Footer Action Bar -->
            <div class="p-4 border-t dark:border-gray-700 bg-white dark:bg-gray-800 flex justify-between items-center shrink-0">
                <div class="flex items-center gap-2">
                    <!-- Progress / Status discrete -->
                     <button v-if="step === 'results' && !isRunning" @click="step = 'inputs'" class="btn btn-secondary flex items-center gap-2">
                        <IconRefresh class="w-4 h-4"/> Refine Inputs
                    </button>
                </div>
                <div class="flex gap-3">
                    <button v-if="step === 'inputs'" @click="runFlow" class="btn btn-primary px-10 py-3 shadow-xl flex items-center gap-2 rounded-2xl transform hover:scale-105 active:scale-95 transition-all" :disabled="isRunning">
                        <IconPlayCircle class="w-6 h-6"/> 
                        <span class="text-base font-black uppercase tracking-widest">Execute Workflow</span>
                    </button>
                    <button v-if="step === 'results' && !isRunning" @click="runFlow" class="btn btn-primary px-8 py-2.5 shadow-lg flex items-center gap-2" :disabled="isRunning">
                        <IconRefresh class="w-5 h-5"/> Run Again
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useFlowStore } from '../../stores/flow';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconCheckCircle from '../../assets/icons/IconCheckCircle.vue';
import IconError from '../../assets/icons/IconError.vue';
import IconCopy from '../../assets/icons/IconCopy.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';
import IconSettings from '../../assets/icons/IconSettings.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';
import { json } from '@codemirror/lang-json';
import { oneDark } from '@codemirror/theme-one-dark';

const props = defineProps({
    flowData: { type: Object, required: true },
    flowId: { type: String, required: true },
    flowName: { type: String, default: 'Untitled Flow' }
});

const emit = defineEmits(['close']);
const flowStore = useFlowStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();

const step = ref('inputs'); // 'inputs' | 'results'
const isRunning = ref(false);
const taskId = ref(null);
const executionResult = ref(null);
const executionError = ref(null);
const inputValues = ref({});
const overallProgress = ref(0);

const jsonExtensions = [json(), oneDark];

const requiredInputs = computed(() => {
    const nodes = props.flowData.nodes || [];
    const edges = props.flowData.edges || [];
    const inputs = [];
    nodes.forEach(node => {
        const nodeInputs = node.inputs || [];
        nodeInputs.forEach(inputName => {
            const isConnected = edges.some(e => e.target === node.id && e.targetHandle === inputName);
            if (!isConnected) {
                const def = flowStore.nodeDefinitions.find(d => d.name === node.type);
                const inputDef = def?.inputs.find(i => i.name === inputName);
                const type = inputDef?.type || 'string';
                if (!inputValues.value[node.id]) inputValues.value[node.id] = {};
                if (inputValues.value[node.id][inputName] === undefined) {
                    const existingVal = node.data?.[inputName];
                    inputValues.value[node.id][inputName] = existingVal !== undefined ? existingVal : (type === 'int' || type === 'float' ? 0 : type === 'boolean' ? false : '');
                }
                inputs.push({ key: `${node.id}-${inputName}`, nodeId: node.id, nodeLabel: node.label || node.id, inputName: inputName, type: type });
            }
        });
    });
    return inputs;
});

const displayNodes = computed(() => {
    const nodes = props.flowData.nodes || [];
    const edges = props.flowData.edges || [];
    return nodes.filter(node => {
        const nodeOutputs = node.outputs || [];
        if (nodeOutputs.length === 0) return true;
        return !nodeOutputs.some(outName => edges.some(e => e.source === node.id && e.sourceHandle === outName));
    });
});

function isDataImage(val) {
    return typeof val === 'string' && val.startsWith('data:image/');
}

function getOutputType(node, key) {
    const def = flowStore.nodeDefinitions.find(d => d.name === node.type);
    const outputDef = def?.outputs.find(o => o.name.toLowerCase() === key.toLowerCase());
    return outputDef?.type || 'any';
}

function formatRaw(val) {
    if (typeof val === 'object') return JSON.stringify(val, null, 2);
    return val;
}

async function runFlow() {
    if (isRunning.value) return;
    isRunning.value = true;
    executionResult.value = null;
    executionError.value = null;
    overallProgress.value = 0;
    
    // Switch to results page immediately
    step.value = 'results';

    try {
        const taskInfo = await flowStore.executeFlow(props.flowId, inputValues.value);
        if (taskInfo?.id) {
            taskId.value = taskInfo.id;
            monitorTask(taskId.value);
        }
    } catch (e) {
        executionError.value = "Failed to start workflow: " + e.message;
        isRunning.value = false;
    }
}

function monitorTask(id) {
    const unwatch = watch(() => tasksStore.tasks.find(t => t.id === id), (task) => {
        if (!task) return;
        overallProgress.value = task.progress || 0;
        if (task.status === 'completed') {
            executionResult.value = task.result;
            isRunning.value = false; unwatch();
        } else if (['failed', 'cancelled'].includes(task.status)) {
            executionError.value = task.error || "Workflow failed.";
            isRunning.value = false; unwatch();
        }
    }, { immediate: true, deep: true });
}

function getNodeResult(nodeId) {
    if (!executionResult.value) return null;
    return executionResult.value[nodeId];
}

function openFullScreen(src) {
    uiStore.openImageViewer({
        imageList: [{ src, prompt: 'Workflow Output' }],
        startIndex: 0
    });
}

function downloadOutputImage(src, name) {
    const link = document.createElement('a');
    link.href = src;
    link.download = `${name}_${Date.now()}.png`;
    link.click();
}

onMounted(() => {
    // Determine if we should start on results if a task is already running for this flow
    // (Optional enhancement, for now always start on inputs)
});
</script>

<style scoped>
.input-field {
    @apply bg-gray-50 dark:bg-gray-900/50 border-gray-200 dark:border-gray-700 rounded-xl focus:ring-blue-500 focus:border-blue-500;
}
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>
