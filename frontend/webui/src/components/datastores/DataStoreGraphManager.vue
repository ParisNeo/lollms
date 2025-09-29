<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import InteractiveGraphViewer from './InteractiveGraphViewer.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconCpuChip from '../../assets/icons/IconCpuChip.vue';

const props = defineProps({
    store: {
        type: Object,
        required: true
    },
    task: {
        type: Object,
        default: null
    }
});

const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const tasksStore = useTasksStore();
const { user } = storeToRefs(authStore);
const { availableLLMModelsGrouped } = storeToRefs(dataStore);

const graphStats = ref({ nodes: 0, edges: 0 });
const graphData = ref({ nodes: [], edges: [] });
const isLoadingGraph = ref(false);

const generationParams = ref({
    model_binding: '',
    model_name: '',
    chunk_size: 2048,
    overlap_size: 256,
    ontology: '{\n  "entities": ["Person", "Organization", "Location", "Date", "Product", "Event"],\n  "relationships": [\n    {"source": "Person", "target": "Organization", "label": "WORKS_FOR"},\n    {"source": "Person", "target": "Location", "label": "LIVES_IN"},\n    {"source": "Organization", "target": "Location", "label": "LOCATED_IN"},\n    {"source": "Event", "target": "Date", "label": "OCCURRED_ON"}\n  ]\n}'
});

const selectedFullModel = ref('');
const query = ref('');
const queryResults = ref([]);
const isQuerying = ref(false);

const selectedNode = ref(null);
const selectedEdge = ref(null);

watch(selectedFullModel, (newVal) => {
    if (newVal) {
        const [binding, ...modelParts] = newVal.split('/');
        generationParams.value.model_binding = binding;
        generationParams.value.model_name = modelParts.join('/');
    } else {
        generationParams.value.model_binding = '';
        generationParams.value.model_name = '';
    }
});

async function fetchGraph() {
    isLoadingGraph.value = true;
    selectedNode.value = null;
    selectedEdge.value = null;
    try {
        const data = await dataStore.fetchDataStoreGraph(props.store.id);
        graphData.value = data || { nodes: [], edges: [] };
        graphStats.value = {
            nodes: data?.nodes?.length || 0,
            edges: data?.edges?.length || 0
        };
    } catch (error) {
        graphData.value = { nodes: [], edges: [] };
        graphStats.value = { nodes: 0, edges: 0 };
    } finally {
        isLoadingGraph.value = false;
    }
}

function handleGenerateGraph() {
    if (!generationParams.value.model_binding || !generationParams.value.model_name) {
        uiStore.addNotification('Please select a model for generation.', 'warning');
        return;
    }
    dataStore.generateDataStoreGraph({
        storeId: props.store.id,
        graphData: generationParams.value
    });
}

function handleUpdateGraph() {
     if (!generationParams.value.model_binding || !generationParams.value.model_name) {
        uiStore.addNotification('Please select a model for update.', 'warning');
        return;
    }
    dataStore.updateDataStoreGraph({
        storeId: props.store.id,
        graphData: generationParams.value
    });
}

async function handleWipeGraph() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Wipe Knowledge Graph?',
        message: 'This will permanently delete all nodes and edges from this datastore\'s graph. This action cannot be undone.',
        confirmText: 'Wipe Graph'
    });
    if (confirmed) {
        try {
            await dataStore.wipeDataStoreGraph(props.store.id);
            fetchGraph();
        } catch(e) {
            // error handled by store
        }
    }
}

async function handleQuery() {
    if (!query.value.trim()) return;
    isQuerying.value = true;
    try {
        queryResults.value = await dataStore.queryDataStoreGraph({
            storeId: props.store.id,
            query: query.value,
            max_k: 10
        });
    } finally {
        isQuerying.value = false;
    }
}

function handleNodeSelect(node) {
    selectedNode.value = node;
    selectedEdge.value = null;
}

function handleEdgeSelect(edge) {
    selectedEdge.value = edge;
    selectedNode.value = null;
}

function handleDeselect() {
    selectedNode.value = null;
    selectedEdge.value = null;
}

function openAddNodeModal() {
    uiStore.openModal('nodeEdit', {
        onConfirm: async (nodeData) => {
            await dataStore.addGraphNode({ storeId: props.store.id, nodeData });
            fetchGraph();
        }
    });
}

function openAddEdgeModal() {
    uiStore.openModal('edgeEdit', {
        sourceId: selectedNode.value?.id || '',
        onConfirm: async (edgeData) => {
            await dataStore.addGraphEdge({ storeId: props.store.id, edgeData });
            fetchGraph();
        }
    });
}

function openEditNodeModal() {
    if (!selectedNode.value) return;
    uiStore.openModal('nodeEdit', {
        node: selectedNode.value,
        onConfirm: async (nodeData) => {
            await dataStore.updateGraphNode({ storeId: props.store.id, nodeId: selectedNode.value.id, nodeData });
            fetchGraph();
        }
    });
}

async function deleteSelectedNode() {
    if (!selectedNode.value) return;
    const confirmed = await uiStore.showConfirmation({ title: 'Delete Node?', message: `Delete node "${selectedNode.value.label}" (ID: ${selectedNode.value.id})? This will also delete connected edges.`});
    if (confirmed) {
        await dataStore.deleteGraphNode({ storeId: props.store.id, nodeId: selectedNode.value.id });
        fetchGraph();
    }
}

async function deleteSelectedEdge() {
    if (!selectedEdge.value) return;
    const confirmed = await uiStore.showConfirmation({ title: 'Delete Edge?', message: `Delete edge "${selectedEdge.value.label}"?`});
    if (confirmed) {
        await dataStore.deleteGraphEdge({ storeId: props.store.id, edgeId: selectedEdge.value.id });
        fetchGraph();
    }
}


onMounted(() => {
    fetchGraph();
    if (user.value?.lollms_model_name) {
        selectedFullModel.value = user.value.lollms_model_name;
    }
    if(availableLLMModelsGrouped.value.length === 0) {
        dataStore.fetchAvailableLollmsModels();
    }
});

watch(() => props.store.id, fetchGraph);
watch(() => props.task, (newTask, oldTask) => {
    const wasRunning = oldTask && (oldTask.status === 'running' || oldTask.status === 'pending');
    if (wasRunning && !newTask) {
        const lastTaskState = tasksStore.tasks.find(t => t.id === oldTask.id);
        if (lastTaskState && ['completed', 'failed', 'cancelled'].includes(lastTaskState.status)) {
            fetchGraph();
        }
    }
});

</script>

<template>
    <div class="h-full flex flex-col lg:flex-row gap-6">
        <!-- Controls Column -->
        <div class="w-full lg:w-96 lg:flex-shrink-0 space-y-6 h-full overflow-y-auto custom-scrollbar pr-4">
            <div class="grid grid-cols-2 gap-4">
                <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center">
                    <h4 class="text-xs font-medium text-gray-500 dark:text-gray-400">Nodes</h4>
                    <p v-if="isLoadingGraph" class="text-xl font-bold animate-pulse">...</p>
                    <p v-else class="text-xl font-bold">{{ graphStats.nodes }}</p>
                </div>
                 <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center">
                    <h4 class="text-xs font-medium text-gray-500 dark:text-gray-400">Edges</h4>
                     <p v-if="isLoadingGraph" class="text-xl font-bold animate-pulse">...</p>
                    <p v-else class="text-xl font-bold">{{ graphStats.edges }}</p>
                </div>
            </div>
             <div v-if="task" class="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <h4 class="font-semibold text-blue-800 dark:text-blue-200 text-sm">{{ task.name }}</h4>
                <p class="text-xs text-blue-700 dark:text-blue-300">{{ task.description }} ({{ task.progress }}%)</p>
                <div class="w-full bg-blue-200 rounded-full h-1.5 mt-1">
                    <div class="bg-blue-600 h-1.5 rounded-full" :style="{ width: task.progress + '%' }"></div>
                </div>
            </div>
            
            <div v-if="selectedNode" class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg space-y-3">
                <h3 class="font-semibold">Node: {{ selectedNode.label }} <span class="font-mono text-xs">(ID: {{ selectedNode.id }})</span></h3>
                <pre class="text-xs bg-white dark:bg-gray-800 p-2 rounded max-h-40 overflow-auto">{{ JSON.stringify(selectedNode.properties, null, 2) }}</pre>
                <div class="flex gap-2">
                    <button @click="openEditNodeModal" class="btn btn-secondary btn-sm">Edit</button>
                    <button @click="deleteSelectedNode" class="btn btn-danger btn-sm">Delete</button>
                </div>
            </div>
             <div v-if="selectedEdge" class="p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg space-y-3">
                <h3 class="font-semibold">Edge: {{ selectedEdge.label }}</h3>
                <p class="text-sm">From: {{ selectedEdge.source }} To: {{ selectedEdge.target }}</p>
                <div class="flex gap-2">
                    <button @click="deleteSelectedEdge" class="btn btn-danger btn-sm">Delete Edge</button>
                </div>
            </div>

            <div class="space-y-4 p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <h3 class="text-base font-semibold">Graph Management</h3>
                <div class="flex gap-2">
                     <button @click="openAddNodeModal" :disabled="!!task" class="btn btn-secondary btn-sm flex-1">Add Node</button>
                     <button @click="openAddEdgeModal" :disabled="!!task || !selectedNode" class="btn btn-secondary btn-sm flex-1">Add Edge</button>
                </div>
                <hr class="dark:border-gray-600">
                <div>
                    <label class="block text-sm font-medium mb-1">Ontology / Guidance</label>
                    <textarea v-model="generationParams.ontology" rows="5" class="input-field font-mono text-xs"></textarea>
                </div>
                 <div>
                    <label for="model-select" class="block text-sm font-medium mb-1">Model</label>
                    <select id="model-select" v-model="selectedFullModel" class="input-field">
                        <option disabled value="">Select a model</option>
                        <optgroup v-for="group in availableLLMModelsGrouped" :key="group.label" :label="group.label">
                            <option v-for="model in group.items" :key="model.id" :value="model.id">{{ model.name }}</option>
                        </optgroup>
                    </select>
                </div>
                <div class="grid grid-cols-2 gap-4 pt-2">
                    <button @click="handleGenerateGraph" :disabled="!!task" class="btn btn-primary btn-sm">
                        {{ graphStats.nodes > 0 ? 'Re-Generate' : 'Generate' }}
                    </button>
                    <button @click="handleUpdateGraph" :disabled="!!task || graphStats.nodes === 0" class="btn btn-secondary btn-sm">
                        Update
                    </button>
                </div>
                 <div class="pt-2 border-t dark:border-gray-600">
                    <button @click="handleWipeGraph" :disabled="!!task || graphStats.nodes === 0" class="btn btn-danger w-full btn-sm">
                        Wipe Graph
                    </button>
                </div>
            </div>
            
            <div class="space-y-4 p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <h3 class="text-base font-semibold">Query Graph</h3>
                <form @submit.prevent="handleQuery" class="flex gap-2">
                    <input v-model="query" type="text" placeholder="Query..." class="input-field flex-grow">
                    <button type="submit" :disabled="isQuerying || !query.trim()" class="btn btn-primary">Query</button>
                </form>
                <div v-if="isQuerying" class="text-center p-2"><IconAnimateSpin class="w-5 h-5 animate-spin mx-auto"/></div>
                <div v-if="queryResults.length > 0" class="space-y-2 max-h-60 overflow-y-auto">
                    <div v-for="(result, index) in queryResults" :key="index" class="p-2 bg-white dark:bg-gray-800 rounded-md text-xs">
                       <pre class="whitespace-pre-wrap">{{ result }}</pre>
                    </div>
                </div>
            </div>
        </div>
        <!-- Graph Viewer Column -->
        <div class="flex-grow h-full min-h-[400px] lg:min-h-0">
            <InteractiveGraphViewer :nodes="graphData.nodes" :edges="graphData.edges" :is-loading="isLoadingGraph" @node-select="handleNodeSelect" @edge-select="handleEdgeSelect" @deselect="handleDeselect"/>
        </div>
    </div>
</template>