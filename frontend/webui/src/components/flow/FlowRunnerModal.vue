<template>
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
        <div class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-4xl h-[85vh] flex flex-col border dark:border-gray-700 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <!-- Header -->
            <div class="p-4 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-800/80">
                <div>
                    <h3 class="text-xl font-bold text-gray-800 dark:text-gray-100 flex items-center gap-2">
                        <IconPlayCircle class="w-6 h-6 text-green-500" />
                        Run Flow: {{ flowName }}
                    </h3>
                    <p class="text-xs text-gray-500 mt-1" v-if="taskId">Task ID: {{ taskId }}</p>
                </div>
                <div class="flex items-center gap-2">
                    <button @click="$emit('close')" class="text-gray-400 hover:text-red-500 transition-colors p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full">
                        <IconXMark class="w-6 h-6"/>
                    </button>
                </div>
            </div>

            <!-- Tabs -->
            <div class="flex border-b dark:border-gray-700 bg-gray-100 dark:bg-gray-900">
                <button @click="activeTab = 'auto'" class="flex-1 py-3 text-sm font-medium transition-colors border-b-2" :class="activeTab === 'auto' ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-white dark:bg-gray-800' : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'">Auto UI</button>
                <button @click="activeTab = 'service'" class="flex-1 py-3 text-sm font-medium transition-colors border-b-2" :class="activeTab === 'service' ? 'border-purple-500 text-purple-600 dark:text-purple-400 bg-white dark:bg-gray-800' : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'">Service Mode</button>
            </div>
            
            <div class="flex-grow flex flex-col min-h-0 overflow-y-auto p-6 bg-gray-50 dark:bg-gray-900">
                
                <!-- AUTO UI TAB -->
                <div v-if="activeTab === 'auto'" class="space-y-6">
                    <div v-if="requiredInputs.length === 0" class="p-4 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-300 rounded-lg text-sm">
                        This flow takes no external inputs. Click Run to execute.
                    </div>
                    
                    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div v-for="inp in requiredInputs" :key="inp.key" class="bg-white dark:bg-gray-800 p-4 rounded-lg border dark:border-gray-700 shadow-sm">
                            <label class="block text-xs font-bold uppercase text-gray-500 mb-2">
                                {{ inp.nodeLabel }} <span class="text-gray-300 font-normal">({{ inp.inputName }})</span>
                            </label>
                            
                            <textarea v-if="inp.type === 'string' && (inp.value && inp.value.length > 50)" v-model="inputValues[inp.nodeId][inp.inputName]" class="input-field w-full h-24" placeholder="Enter text..."></textarea>
                            
                            <input v-else-if="inp.type === 'int' || inp.type === 'float'" type="number" v-model.number="inputValues[inp.nodeId][inp.inputName]" class="input-field w-full" :step="inp.type === 'float' ? 'any' : '1'">
                            
                            <div v-else-if="inp.type === 'boolean'" class="flex items-center gap-2">
                                <button @click="inputValues[inp.nodeId][inp.inputName] = !inputValues[inp.nodeId][inp.inputName]" class="relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2" :class="inputValues[inp.nodeId][inp.inputName] ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-700'">
                                    <span class="translate-x-0 pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out" :class="inputValues[inp.nodeId][inp.inputName] ? 'translate-x-5' : 'translate-x-0'"></span>
                                </button>
                                <span class="text-sm">{{ inputValues[inp.nodeId][inp.inputName] ? 'True' : 'False' }}</span>
                            </div>
                            
                            <input v-else v-model="inputValues[inp.nodeId][inp.inputName]" class="input-field w-full" placeholder="Enter value...">
                        </div>
                    </div>

                    <!-- Outputs Section (Only show if results exist) -->
                    <div v-if="executionResult" class="mt-8 border-t dark:border-gray-700 pt-6">
                        <h4 class="text-lg font-bold mb-4 flex items-center gap-2"><IconCheckCircle class="w-5 h-5 text-green-500"/> Execution Results</h4>
                        
                        <div v-if="outputNodes.length === 0" class="text-gray-500 italic">No explicit output nodes found. Showing all terminal results:</div>
                        
                        <div class="grid grid-cols-1 gap-4 mt-2">
                            <div v-for="node in displayNodes" :key="node.id" class="bg-white dark:bg-gray-800 rounded-lg border dark:border-gray-700 overflow-hidden shadow-sm">
                                <div class="px-4 py-2 bg-gray-100 dark:bg-gray-800 border-b dark:border-gray-700 font-bold text-sm flex justify-between">
                                    <span>{{ node.label }}</span>
                                    <span class="text-xs text-gray-500 font-mono">{{ node.id }}</span>
                                </div>
                                <div class="p-4 overflow-auto max-h-60 bg-gray-50 dark:bg-gray-900/50 font-mono text-xs">
                                    <pre>{{ getNodeResult(node.id) }}</pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- SERVICE TAB -->
                <div v-if="activeTab === 'service'" class="h-full flex flex-col space-y-4">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 h-full">
                        <div class="flex flex-col">
                            <label class="text-xs font-bold text-gray-500 uppercase mb-2">Request Payload (JSON)</label>
                            <div class="flex-grow border dark:border-gray-700 rounded-lg overflow-hidden relative">
                                <CodeMirrorEditor v-model="servicePayloadJson" :extensions="jsonExtensions" class="h-full" />
                                <button @click="copyPayload" class="absolute top-2 right-2 p-1 bg-white/10 hover:bg-white/20 rounded text-gray-400 hover:text-white" title="Copy"><IconCopy class="w-4 h-4"/></button>
                            </div>
                            <div class="mt-2 text-xs text-gray-500">
                                Endpoint: <code class="bg-gray-200 dark:bg-gray-800 px-1 rounded">POST /api/flows/execute</code>
                            </div>
                        </div>
                        <div class="flex flex-col">
                            <label class="text-xs font-bold text-gray-500 uppercase mb-2">Response Output</label>
                            <div class="flex-grow bg-black text-green-400 p-4 rounded-lg font-mono text-xs overflow-auto border dark:border-gray-700">
                                <pre v-if="executionResult">{{ JSON.stringify(executionResult, null, 2) }}</pre>
                                <div v-else class="text-gray-600 italic">Run the flow to see output...</div>
                            </div>
                        </div>
                    </div>
                </div>

            </div>

            <!-- Footer Action Bar -->
            <div class="p-4 border-t dark:border-gray-700 bg-white dark:bg-gray-800 flex justify-between items-center">
                <div class="flex items-center gap-2">
                    <div v-if="isRunning" class="flex items-center gap-2 text-blue-500 text-sm font-bold animate-pulse">
                        <IconAnimateSpin class="w-4 h-4 animate-spin"/> Running...
                    </div>
                    <div v-if="executionError" class="text-red-500 text-sm font-bold flex items-center gap-1">
                        <IconError class="w-4 h-4"/> Execution Failed
                    </div>
                </div>
                <button @click="runFlow" class="btn btn-primary px-8 py-2.5 shadow-lg flex items-center gap-2" :disabled="isRunning">
                    <IconPlayCircle class="w-5 h-5"/> Run Flow
                </button>
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
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
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

const activeTab = ref('auto');
const isRunning = ref(false);
const taskId = ref(null);
const executionResult = ref(null);
const executionError = ref(null);
const inputValues = ref({}); // { nodeId: { inputName: val } }
const servicePayloadJson = ref('');

const jsonExtensions = [json(), oneDark];

// Analysis of flow structure
const requiredInputs = computed(() => {
    const nodes = props.flowData.nodes || [];
    const edges = props.flowData.edges || [];
    
    const inputs = [];
    
    nodes.forEach(node => {
        // Assume all defined inputs on the node need values unless connected
        // or if node has internal data that satisfies it (simplified logic: check connections)
        const nodeInputs = node.inputs || []; // List of input names
        
        nodeInputs.forEach(inputName => {
            const isConnected = edges.some(e => e.target === node.id && e.targetHandle === inputName);
            
            if (!isConnected) {
                // Determine type from node definition if available, otherwise assume string
                // We rely on FlowStore's loaded definitions
                const def = flowStore.nodeDefinitions.find(d => d.name === node.type);
                const inputDef = def?.inputs.find(i => i.name === inputName);
                const type = inputDef?.type || 'string';
                
                // Initialize value model if missing
                if (!inputValues.value[node.id]) inputValues.value[node.id] = {};
                if (inputValues.value[node.id][inputName] === undefined) {
                    // Check if node data already has a value (manual input from editor)
                    const existingVal = node.data?.[inputName];
                    inputValues.value[node.id][inputName] = existingVal !== undefined ? existingVal : getDefaultValue(type);
                }

                inputs.push({
                    key: `${node.id}-${inputName}`,
                    nodeId: node.id,
                    nodeLabel: node.label || node.id,
                    inputName: inputName,
                    type: type,
                    value: inputValues.value[node.id][inputName]
                });
            }
        });
    });
    
    return inputs;
});

const outputNodes = computed(() => {
    const nodes = props.flowData.nodes || [];
    const edges = props.flowData.edges || [];
    // Heuristic: Nodes with outputs that are NOT connected to anything are likely final outputs.
    // Or nodes with no outputs defined (sinks).
    return nodes.filter(node => {
        const nodeOutputs = node.outputs || [];
        if (nodeOutputs.length === 0) return true; // Sink node
        
        // Check if any output is connected
        const hasConnection = nodeOutputs.some(outName => edges.some(e => e.source === node.id && e.sourceHandle === outName));
        return !hasConnection;
    });
});

const displayNodes = computed(() => {
    // If output nodes found, show them. Else show all nodes that have results.
    if (outputNodes.value.length > 0) return outputNodes.value;
    return props.flowData.nodes;
});

function getDefaultValue(type) {
    if (type === 'int' || type === 'float') return 0;
    if (type === 'boolean') return false;
    return '';
}

function updateServiceJson() {
    const payload = {
        flow_id: props.flowId,
        inputs: inputValues.value
    };
    servicePayloadJson.value = JSON.stringify(payload, null, 2);
}

// Watch inputs to update JSON
watch(inputValues, updateServiceJson, { deep: true });

async function runFlow() {
    if (isRunning.value) return;
    isRunning.value = true;
    executionResult.value = null;
    executionError.value = null;
    taskId.value = null;

    try {
        let inputsToSend = {};
        
        if (activeTab.value === 'auto') {
            inputsToSend = inputValues.value;
        } else {
            try {
                const parsed = JSON.parse(servicePayloadJson.value);
                inputsToSend = parsed.inputs || {};
            } catch (e) {
                uiStore.addNotification("Invalid JSON in Service Mode", "error");
                isRunning.value = false;
                return;
            }
        }

        const taskInfo = await flowStore.executeFlow(props.flowId, inputsToSend);
        if (taskInfo && taskInfo.id) {
            taskId.value = taskInfo.id;
            monitorTask(taskId.value);
        } else {
            throw new Error("Failed to start task");
        }
    } catch (e) {
        console.error(e);
        executionError.value = "Failed to start flow execution.";
        isRunning.value = false;
    }
}

function monitorTask(id) {
    const unwatch = watch(() => tasksStore.tasks.find(t => t.id === id), (task) => {
        if (!task) return;
        if (task.status === 'completed') {
            executionResult.value = typeof task.result === 'string' ? JSON.parse(task.result) : task.result;
            isRunning.value = false;
            unwatch();
        } else if (task.status === 'failed' || task.status === 'cancelled') {
            executionError.value = task.error || "Task failed or cancelled.";
            isRunning.value = false;
            unwatch();
        }
    }, { immediate: true, deep: true });
}

function getNodeResult(nodeId) {
    if (!executionResult.value) return null;
    // The backend returns results keyed by node ID
    const res = executionResult.value[nodeId];
    if (typeof res === 'object') return JSON.stringify(res, null, 2);
    return res;
}

function copyPayload() {
    uiStore.copyToClipboard(servicePayloadJson.value, "Service payload copied");
}

onMounted(() => {
    // Force compute inputs to init model
    const _ = requiredInputs.value;
    updateServiceJson();
});
</script>
