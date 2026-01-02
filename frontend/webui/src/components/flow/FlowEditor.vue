<script setup>
import { ref, watch, onMounted, computed } from 'vue';
import { useFlowStore } from '../../stores/flow';
import { useAuthStore } from '../../stores/auth';
import { useDataStore } from '../../stores/data';
import NodeCreatorModal from './NodeCreatorModal.vue'; 
import FlowRunnerModal from './FlowRunnerModal.vue'; // IMPORTED
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

const props = defineProps({ flow: { type: Object, required: true } });
const flowStore = useFlowStore();
const authStore = useAuthStore();
const dataStore = useDataStore();

const nodes = ref([]);
const connections = ref([]);
const scale = ref(1);
const pan = ref({ x: 0, y: 0 });
const isDraggingCanvas = ref(false), isDraggingNode = ref(false), draggedNodeId = ref(null), lastMousePos = ref({ x: 0, y: 0 });
const isLinking = ref(false), linkStart = ref(null), mousePos = ref({ x: 0, y: 0 });

const showNodeEditor = ref(false);
const showRunnerModal = ref(false); // NEW
const nodeToEdit = ref(null);
const showTutorial = ref(false);

const isAdmin = computed(() => authStore.isAdmin);

watch(() => props.flow, (newFlow) => {
    if (newFlow && newFlow.data) {
        nodes.value = JSON.parse(JSON.stringify(newFlow.data.nodes || []));
        connections.value = JSON.parse(JSON.stringify(newFlow.data.edges || []));
    } else { nodes.value = []; connections.value = []; }
}, { immediate: true });

watch([nodes, connections], () => { if (props.flow) props.flow.data = { nodes: nodes.value, edges: connections.value }; }, { deep: true });

onMounted(() => {
    flowStore.fetchNodeDefinitions();
    dataStore.fetchAvailableLollmsModels();
    if (!localStorage.getItem('flow_tutorial_seen')) {
        showTutorial.value = true;
        localStorage.setItem('flow_tutorial_seen', 'true');
    }
});

const nodeDefinitionsMap = computed(() => {
    const map = {};
    flowStore.nodeDefinitions.forEach(d => { map[d.name] = d; });
    return map;
});

const nodeTypes = computed(() => {
    return flowStore.nodeDefinitions.map(def => ({
        ...def,
        type: def.name, 
        color: def.color || "bg-gray-100 border-gray-500",
    }));
});

function getTypeColor(typeName) {
    const map = {
        'string': 'bg-gray-400',
        'int': 'bg-green-500',
        'float': 'bg-green-400',
        'boolean': 'bg-orange-500',
        'image': 'bg-pink-500',
        'node_ref': 'bg-indigo-500',
        'list': 'bg-cyan-500',
        'model_selection': 'bg-purple-400',
        'any': 'bg-white border-2 border-gray-400'
    };
    return map[typeName] || map['any'];
}

function getNodeInputType(nodeType, inputName) {
    const def = nodeDefinitionsMap.value[nodeType];
    if (!def) return 'any';
    const inp = def.inputs.find(i => i.name === inputName);
    return inp ? inp.type : 'any';
}

function getNodeOutputType(nodeType, outputName) {
    const def = nodeDefinitionsMap.value[nodeType];
    if (!def) return 'any';
    const out = def.outputs.find(o => o.name === outputName);
    return out ? out.type : 'any';
}

function isInputConnected(nodeId, handleName) {
    return connections.value.some(c => c.target === nodeId && c.targetHandle === handleName);
}

function openEditNode(nodeDef) {
    nodeToEdit.value = JSON.parse(JSON.stringify(nodeDef));
    showNodeEditor.value = true;
}

function addNode(typeDef) {
    const viewCenterX = (-pan.value.x + (window.innerWidth / 2 - 200)) / scale.value; 
    const viewCenterY = (-pan.value.y + (window.innerHeight / 2)) / scale.value;

    nodes.value.push({
        id: `node_${Date.now()}`,
        type: typeDef.type,
        label: typeDef.label,
        x: viewCenterX > 0 ? viewCenterX : 50,
        y: viewCenterY > 0 ? viewCenterY : 50,
        data: {}, // Data will hold manual input values
        inputs: typeDef.inputs.map(i => i.name),
        outputs: typeDef.outputs.map(o => o.name),
        color: typeDef.color
    });
}

function deleteNode(id) {
    nodes.value = nodes.value.filter(n => n.id !== id);
    connections.value = connections.value.filter(c => c.source !== id && c.target !== id);
}

function onMouseDown(e) { if (e.button === 1 || (e.button === 0 && e.target.classList.contains('flow-canvas'))) { isDraggingCanvas.value = true; lastMousePos.value = { x: e.clientX, y: e.clientY }; } }
function onMouseMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    mousePos.value = { x: (e.clientX - rect.left - pan.value.x) / scale.value, y: (e.clientY - rect.top - pan.value.y) / scale.value };
    if (isDraggingCanvas.value) { pan.value.x += e.clientX - lastMousePos.value.x; pan.value.y += e.clientY - lastMousePos.value.y; lastMousePos.value = { x: e.clientX, y: e.clientY }; }
    else if (isDraggingNode.value && draggedNodeId.value) {
        const node = nodes.value.find(n => n.id === draggedNodeId.value);
        if (node) { node.x += (e.clientX - lastMousePos.value.x) / scale.value; node.y += (e.clientY - lastMousePos.value.y) / scale.value; lastMousePos.value = { x: e.clientX, y: e.clientY }; }
    }
}
function onMouseUp() { isDraggingCanvas.value = false; isDraggingNode.value = false; draggedNodeId.value = null; if (isLinking.value) { isLinking.value = false; linkStart.value = null; } }
function onWheel(e) { e.preventDefault(); const d = e.deltaY > 0 ? -0.1 : 0.1; scale.value = Math.min(Math.max(0.1, scale.value + d), 5); }
function startDragNode(e, id) { if (e.button !== 0) return; e.stopPropagation(); isDraggingNode.value = true; draggedNodeId.value = id; lastMousePos.value = { x: e.clientX, y: e.clientY }; }
function startLink(e, id, h, t) { e.stopPropagation(); isLinking.value = true; linkStart.value = { nodeId: id, handleId: h, type: t }; }
function endLink(e, id, h, t) {
    e.stopPropagation();
    if (!isLinking.value || !linkStart.value) return;
    const s = linkStart.value;
    if (s.nodeId !== id && s.type !== t) {
        const src = s.type === 'output' ? s : { nodeId: id, handleId: h };
        const tgt = s.type === 'input' ? s : { nodeId: id, handleId: h };
        if (s.type === t) return;
        const exists = connections.value.find(c => c.source === src.nodeId && c.sourceHandle === src.handleId && c.target === tgt.nodeId && c.targetHandle === tgt.handleId);
        if (!exists) connections.value.push({ id: `e_${Date.now()}`, source: src.nodeId, sourceHandle: src.handleId, target: tgt.nodeId, targetHandle: tgt.handleId });
    }
    isLinking.value = false; linkStart.value = null;
}
function deleteConnection(i) { connections.value.splice(i, 1); }

function getPortPos(nodeId, handleId, type) {
    const node = nodes.value.find(n => n.id === nodeId);
    if (!node) return { x: 0, y: 0 };
    const inputs = node.inputs || [];
    const outputs = node.outputs || [];
    const index = type === 'input' ? inputs.indexOf(handleId) : outputs.indexOf(handleId);
    const nodeWidth = 192; // w-48
    const headerHeight = 29; 
    const bodyPadding = 8;
    const rowHeight = 24; 
    const rowGap = 8; 
    const yOffset = headerHeight + bodyPadding + (index * (rowHeight + rowGap)) + (rowHeight / 2);
    const x = type === 'input' ? node.x : node.x + nodeWidth;
    const y = node.y + yOffset;
    return { x, y };
}

function getPathD(conn) {
    const s = getPortPos(conn.source, conn.sourceHandle, 'output');
    const e = getPortPos(conn.target, conn.targetHandle, 'input');
    const d = Math.abs(e.x - s.x) * 0.5;
    return `M ${s.x} ${s.y} C ${s.x + d} ${s.y}, ${e.x - d} ${e.y}, ${e.x} ${e.y}`;
}

const activeLinkPath = computed(() => {
    if (!isLinking.value || !linkStart.value) return '';
    const s = getPortPos(linkStart.value.nodeId, linkStart.value.handleId, linkStart.value.type);
    const e = mousePos.value;
    const d = Math.abs(e.x - s.x) * 0.5;
    return `M ${s.x} ${s.y} C ${s.x + (linkStart.value.type==='output'?d:-d)} ${s.y}, ${e.x - (linkStart.value.type==='output'?d:-d)} ${e.y}, ${e.x} ${e.y}`;
});

// Expose openRunner for the parent view to call
defineExpose({
    openRunner: () => showRunnerModal.value = true
});
</script>

<template>
    <div class="relative w-full h-full flex overflow-hidden">
        <!-- Palette -->
        <div class="w-60 bg-white dark:bg-gray-800 border-r dark:border-gray-700 flex flex-col z-10 flex-shrink-0">
            <div class="p-3 border-b dark:border-gray-700 flex justify-between items-center">
                <span class="font-bold text-xs uppercase text-gray-500 tracking-wider">Node Palette</span>
                <button @click="showTutorial = true" class="text-blue-500 hover:text-blue-600 transition-colors"><IconInfo class="w-4 h-4"/></button>
            </div>
            
            <div v-if="nodeTypes.length === 0" class="p-4 text-center text-gray-400 text-xs italic">
                No nodes defined.<br>Admins can create nodes.
            </div>

            <div class="p-2 space-y-2 overflow-y-auto custom-scrollbar flex-grow">
                <div v-for="nt in nodeTypes" :key="nt.id" 
                     class="group p-2 rounded border dark:border-gray-600 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 transition-all active:scale-95 border-l-4 shadow-sm relative overflow-hidden"
                     :class="nt.color.split(' ').find(c => c.startsWith('border-'))"
                     @dblclick="addNode(nt)"
                     draggable="true"
                     @dragend="addNode(nt)"
                     :title="nt.description"
                >
                    <div class="flex items-center justify-between">
                        <span class="text-xs font-bold truncate pr-2">{{ nt.label }}</span>
                        <div class="flex items-center gap-1">
                            <button v-if="isAdmin" @click.stop="openEditNode(nt)" class="text-gray-400 hover:text-blue-500 p-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity">
                                <IconPencil class="w-3.5 h-3.5" />
                            </button>
                            <IconPlus class="w-3.5 h-3.5 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                    </div>
                    <div class="text-[9px] text-gray-400 mt-1 line-clamp-1" v-if="nt.description">{{ nt.description }}</div>
                </div>
            </div>
            
            <div class="p-2 text-[9px] text-gray-400 text-center border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                Drag or Double-Click to Add
            </div>
        </div>

        <!-- Canvas -->
        <div 
            class="flex-grow relative bg-gray-100 dark:bg-gray-900 flow-canvas overflow-hidden cursor-grab active:cursor-grabbing pattern-grid"
            @mousedown="onMouseDown"
            @mousemove="onMouseMove"
            @mouseup="onMouseUp"
            @wheel="onWheel"
        >
            <div class="transform-origin-0-0 w-full h-full" :style="{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})` }">
                <!-- Links -->
                <svg class="absolute top-0 left-0 overflow-visible pointer-events-none w-full h-full" style="width:1px;height:1px"><g><path v-for="(c,i) in connections" :key="c.id" :d="getPathD(c)" class="stroke-gray-400 dark:stroke-gray-500 stroke-[3px] fill-none pointer-events-auto hover:stroke-blue-500 cursor-pointer" @click.stop="deleteConnection(i)" /><path v-if="isLinking" :d="activeLinkPath" class="stroke-blue-400 stroke-[3px] fill-none" stroke-dasharray="5,5" /></g></svg>
                
                <!-- Nodes -->
                <div v-for="n in nodes" :key="n.id" class="absolute w-48 rounded-lg shadow-lg border-2 bg-white dark:bg-gray-800 flex flex-col" :class="n.color" :style="{ transform: `translate(${n.x}px, ${n.y}px)` }" @mousedown.stop="startDragNode($event, n.id)">
                    <div class="px-2 py-1 border-b dark:border-gray-700/50 flex justify-between items-center bg-gray-50/50 dark:bg-gray-900/20 cursor-grab active:cursor-grabbing"><span class="text-xs font-bold truncate select-none">{{ n.label }}</span><button @click.stop="deleteNode(n.id)" class="text-gray-400 hover:text-red-500 rounded"><IconXMark class="w-3 h-3" /></button></div>
                    
                    <div class="p-2 space-y-2 relative">
                        <!-- Inputs -->
                        <div v-for="i in n.inputs" :key="i" class="flex items-center relative h-6">
                            <div 
                                class="w-3.5 h-3.5 rounded-full border-2 border-white dark:border-gray-800 absolute -left-[1.1rem] cursor-crosshair hover:scale-125 shadow-sm transition-transform"
                                :class="getTypeColor(getNodeInputType(n.type, i))"
                                @mousedown.stop="startLink($event, n.id, i, 'input')" 
                                @mouseup.stop="endLink($event, n.id, i, 'input')" 
                                :title="getNodeInputType(n.type, i)"
                            ></div>
                            <span class="text-[10px] text-gray-500 ml-1 truncate flex-1 select-none" :title="i">{{ i }}</span>
                            
                            <!-- [MODIFIED] Dynamic Input Rendering based on type -->
                            <template v-if="!isInputConnected(n.id, i)">
                                <!-- Model Selector -->
                                <select v-if="getNodeInputType(n.type, i) === 'model_selection'"
                                        v-model="n.data[i]"
                                        class="ml-auto w-24 h-5 text-[9px] border rounded px-0 bg-gray-50 dark:bg-gray-900 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                                        @mousedown.stop>
                                    <optgroup v-for="group in dataStore.availableLLMModelsGrouped" :key="group.label" :label="group.label">
                                        <option v-for="item in group.items" :key="item.id" :value="item.id">{{ item.name }}</option>
                                    </optgroup>
                                </select>
                                
                                <!-- Boolean Toggle -->
                                <input v-else-if="getNodeInputType(n.type, i) === 'boolean'"
                                       type="checkbox"
                                       v-model="n.data[i]"
                                       class="ml-auto w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                       @mousedown.stop
                                />
                                
                                <!-- Numeric Input -->
                                <input v-else-if="getNodeInputType(n.type, i) === 'int' || getNodeInputType(n.type, i) === 'float'"
                                       type="number"
                                       v-model.number="n.data[i]" 
                                       :step="getNodeInputType(n.type, i) === 'float' ? 'any' : '1'"
                                       class="ml-auto w-16 h-5 text-[9px] border rounded px-1 bg-gray-50 dark:bg-gray-900 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                                       placeholder="0" 
                                       @mousedown.stop 
                                />
                                
                                <!-- Generic Text Input (Default) -->
                                <input v-else
                                       v-model="n.data[i]" 
                                       class="ml-auto w-20 h-5 text-[9px] border rounded px-1 bg-gray-50 dark:bg-gray-900 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                                       placeholder="Val" 
                                       @mousedown.stop 
                                />
                            </template>
                        </div>

                        <!-- Outputs -->
                        <div v-for="o in n.outputs" :key="o" class="flex items-center justify-end relative h-6">
                            <span class="text-[10px] text-gray-500 mr-1 truncate select-none">{{ o }}</span>
                            <div 
                                class="w-3.5 h-3.5 rounded-full border-2 border-white dark:border-gray-800 absolute -right-[1.1rem] cursor-crosshair hover:scale-125 shadow-sm transition-transform"
                                :class="getTypeColor(getNodeOutputType(n.type, o))"
                                @mousedown.stop="startLink($event, n.id, o, 'output')" 
                                @mouseup.stop="endLink($event, n.id, o, 'output')" 
                                :title="getNodeOutputType(n.type, o)"
                            ></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Editor Modal -->
        <Teleport to="body">
            <NodeCreatorModal v-if="showNodeEditor" :nodeToEdit="nodeToEdit" @close="showNodeEditor = false; nodeToEdit = null;" />
        </Teleport>

        <!-- Runner Modal -->
        <Teleport to="body">
            <FlowRunnerModal 
                v-if="showRunnerModal" 
                :flowData="flow.data" 
                :flowId="flow.id" 
                :flowName="flow.name"
                @close="showRunnerModal = false" 
            />
        </Teleport>

        <!-- Tutorial Modal -->
        <Teleport to="body">
            <div v-if="showTutorial" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-lg w-full p-6 animate-in fade-in zoom-in-95 border dark:border-gray-700">
                    <h3 class="text-xl font-bold mb-4 text-gray-800 dark:text-gray-100">Welcome to Flow Studio</h3>
                    <div class="space-y-4 text-sm text-gray-600 dark:text-gray-300">
                        <p>Build powerful AI workflows visually.</p>
                        <ul class="list-disc pl-5 space-y-1">
                            <li><strong>Add Nodes:</strong> Drag items from the left palette onto the canvas.</li>
                            <li><strong>Connect:</strong> Drag from an output circle (right) to an input circle (left). Match colors for data types!</li>
                            <li><strong>Configure:</strong> Type values directly into input fields or use selectors on nodes. If a link is connected, the widget hides.</li>
                            <li><strong>Run:</strong> Click "Run Flow" in the top bar to test your flow with Auto-UI or as a Service.</li>
                            <li><strong>Admins:</strong> Can define custom node logic using Python by clicking the Pencil icon or "Define Node".</li>
                        </ul>
                    </div>
                    <div class="mt-6 flex justify-end">
                        <button @click="showTutorial = false" class="btn btn-primary px-6">Got it</button>
                    </div>
                </div>
            </div>
        </Teleport>
    </div>
</template>

<style scoped>
.transform-origin-0-0 { transform-origin: 0 0; }
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-600 rounded-full; }
.pattern-grid { background-image: radial-gradient(#888 1px, transparent 1px); background-size: 20px 20px; }
</style>
