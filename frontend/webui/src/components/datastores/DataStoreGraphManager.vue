<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import InteractiveGraphViewer from './InteractiveGraphViewer.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

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

const graphViewer = ref(null);
const graphStats = ref({ nodes: 0, edges: 0 });
const graphData = ref({ nodes: [], edges: [] });
const isLoadingGraph = ref(false);
const ontologyFileInput = ref(null);

const defaultOntology = `{
  "entities": [
    {"name": "Person", "description": "Key individuals mentioned in the text"},
    {"name": "Organization", "description": "Companies, institutions, or groups"},
    {"name": "Location", "description": "Cities, countries, or physical places"},
    {"name": "Date", "description": "Specific points in time or durations"},
    {"name": "Concept", "description": "Abstract ideas, theories, or methodologies"},
    {"name": "Technology", "description": "Software, hardware, or tools"}
  ],
  "relationships": [
    {"source": "Person", "target": "Organization", "label": "WORKS_FOR"},
    {"source": "Person", "target": "Location", "label": "LOCATED_IN"},
    {"source": "Organization", "target": "Location", "label": "HEADQUARTERED_IN"},
    {"source": "Person", "target": "Person", "label": "KNOWS"},
    {"source": "Organization", "target": "Product", "label": "PRODUCES"},
    {"source": "Concept", "target": "Concept", "label": "RELATES_TO"}
  ]
}`;

const generationParams = ref({
    model_binding: '',
    model_name: '',
    chunk_size: 2048,
    overlap_size: 256,
    ontology: defaultOntology
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
        console.error("Failed to fetch graph:", error);
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
    if (confirmed.confirmed) {
        try {
            await dataStore.wipeDataStoreGraph(props.store.id);
            fetchGraph();
            uiStore.addNotification("Graph wiped successfully", "success");
        } catch(e) {
            uiStore.addNotification("Failed to wipe graph", "error");
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

// Updated Modal Calls using Component Names usually registered in GenericModal or similar
function openAddNodeModal() {
    uiStore.openModal('NodeEditModal', {
        onConfirm: async (nodeData) => {
            try {
                await dataStore.addGraphNode({ storeId: props.store.id, nodeData });
                uiStore.addNotification('Node added successfully', 'success');
                fetchGraph();
            } catch (error) {
                uiStore.addNotification('Failed to add node', 'error');
                console.error(error);
            }
        }
    });
}

function openAddEdgeModal() {
    uiStore.openModal('EdgeEditModal', {
        sourceId: selectedNode.value?.id || '',
        onConfirm: async (edgeData) => {
            try {
                await dataStore.addGraphEdge({ storeId: props.store.id, edgeData });
                uiStore.addNotification('Edge added successfully', 'success');
                fetchGraph();
            } catch (error) {
                uiStore.addNotification('Failed to add edge', 'error');
                console.error(error);
            }
        }
    });
}

function openEditNodeModal() {
    if (!selectedNode.value) return;
    uiStore.openModal('NodeEditModal', {
        node: selectedNode.value,
        onConfirm: async (nodeData) => {
             try {
                await dataStore.updateGraphNode({ storeId: props.store.id, nodeId: selectedNode.value.id, nodeData });
                uiStore.addNotification('Node updated successfully', 'success');
                fetchGraph();
            } catch (error) {
                uiStore.addNotification('Failed to update node', 'error');
                console.error(error);
            }
        }
    });
}

async function deleteSelectedNode() {
    if (!selectedNode.value) return;
    const { confirmed } = await uiStore.showConfirmation({ title: 'Delete Node?', message: `Delete node "${selectedNode.value.label}" (ID: ${selectedNode.value.id})? This will also delete connected edges.`});
    if (confirmed) {
        try {
            await dataStore.deleteGraphNode({ storeId: props.store.id, nodeId: selectedNode.value.id });
            uiStore.addNotification('Node deleted', 'success');
            fetchGraph();
        } catch (error) {
             uiStore.addNotification('Failed to delete node', 'error');
        }
    }
}

async function deleteSelectedEdge() {
    if (!selectedEdge.value) return;
    const { confirmed } = await uiStore.showConfirmation({ title: 'Delete Edge?', message: `Delete edge "${selectedEdge.value.label}"?`});
    if (confirmed) {
         try {
            await dataStore.deleteGraphEdge({ storeId: props.store.id, edgeId: selectedEdge.value.id });
            uiStore.addNotification('Edge deleted', 'success');
            fetchGraph();
        } catch (error) {
             uiStore.addNotification('Failed to delete edge', 'error');
        }
    }
}

function handleImportOntology() {
    ontologyFileInput.value.click();
}

async function onOntologyFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    uiStore.addNotification('Importing ontology file...', 'info');
    try {
        const textContent = await dataStore.extractTextFromFile(file);
        generationParams.value.ontology = textContent;
        uiStore.addNotification('Ontology file imported successfully.', 'success');
    } catch (error) {
        console.error("Ontology import failed:", error);
    } finally {
        if (ontologyFileInput.value) {
            ontologyFileInput.value.value = '';
        }
    }
}

function fitGraph() {
    if(graphViewer.value) {
        graphViewer.value.resetView();
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
        // Task finished
        fetchGraph();
    }
});

</script>

<template>
    <div class="h-full flex flex-col lg:flex-row gap-6">
        <!-- Controls Column -->
        <div class="w-full lg:w-96 lg:flex-shrink-0 space-y-6 h-full overflow-y-auto custom-scrollbar pr-4">
            <!-- Stats -->
            <div class="grid grid-cols-2 gap-4">
                <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center border dark:border-gray-600">
                    <h4 class="text-xs font-medium text-gray-500 dark:text-gray-400">Nodes</h4>
                    <p v-if="isLoadingGraph" class="text-xl font-bold animate-pulse">...</p>
                    <p v-else class="text-xl font-bold">{{ graphStats.nodes }}</p>
                </div>
                 <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center border dark:border-gray-600">
                    <h4 class="text-xs font-medium text-gray-500 dark:text-gray-400">Edges</h4>
                     <p v-if="isLoadingGraph" class="text-xl font-bold animate-pulse">...</p>
                    <p v-else class="text-xl font-bold">{{ graphStats.edges }}</p>
                </div>
            </div>

            <!-- Task Progress -->
             <div v-if="task" class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
                <h4 class="font-semibold text-blue-800 dark:text-blue-200 text-sm flex justify-between">
                    {{ task.name }}
                    <span class="text-xs opacity-75">{{ task.progress }}%</span>
                </h4>
                <p class="text-xs text-blue-700 dark:text-blue-300 mt-1">{{ task.description }}</p>
                <div class="w-full bg-blue-200 dark:bg-blue-800 rounded-full h-1.5 mt-2">
                    <div class="bg-blue-600 dark:bg-blue-400 h-1.5 rounded-full transition-all duration-500" :style="{ width: task.progress + '%' }"></div>
                </div>
            </div>
            
            <!-- Selection Details -->
            <div v-if="selectedNode" class="p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 space-y-3">
                <div class="flex justify-between items-start">
                    <h3 class="font-semibold text-lg">{{ selectedNode.label }}</h3>
                    <span class="px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-xs">{{ selectedNode.group }}</span>
                </div>
                <div class="text-xs text-gray-500 font-mono">ID: {{ selectedNode.id }}</div>
                
                <div class="bg-gray-50 dark:bg-gray-900 p-2 rounded max-h-40 overflow-auto custom-scrollbar">
                    <pre class="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{{ JSON.stringify(selectedNode.properties, null, 2) }}</pre>
                </div>
                
                <div class="flex gap-2 pt-2">
                    <button @click="openEditNodeModal" class="btn btn-secondary btn-sm flex-1">Edit Properties</button>
                    <button @click="deleteSelectedNode" class="btn btn-danger btn-sm flex-1">Delete</button>
                </div>
            </div>
            
            <div v-if="selectedEdge" class="p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 space-y-3">
                <h3 class="font-semibold text-lg border-b pb-2 dark:border-gray-700">Relationship</h3>
                <div class="flex items-center justify-between text-sm">
                    <span class="font-medium">{{ selectedEdge.label }}</span>
                </div>
                <div class="text-xs text-gray-500 space-y-1">
                    <div><span class="font-semibold">Source:</span> {{ selectedEdge.source }}</div>
                    <div><span class="font-semibold">Target:</span> {{ selectedEdge.target }}</div>
                </div>
                 <div class="flex gap-2 pt-2">
                    <button @click="deleteSelectedEdge" class="btn btn-danger btn-sm w-full">Delete Relationship</button>
                </div>
            </div>

            <!-- Graph Management Actions -->
            <div class="space-y-4 p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700">
                <h3 class="text-base font-semibold flex items-center gap-2">
                    <span class="w-1 h-4 bg-primary-500 rounded-full"></span>
                    Graph Actions
                </h3>
                
                <div class="flex gap-2">
                     <button @click="openAddNodeModal" :disabled="!!task" class="btn btn-secondary btn-sm flex-1">Add Node</button>
                     <button @click="openAddEdgeModal" :disabled="!!task" class="btn btn-secondary btn-sm flex-1">Add Edge</button>
                     <button @click="fitGraph" class="btn btn-ghost btn-sm px-2" title="Fit Graph"><IconMaximize class="w-4 h-4"/></button>
                </div>
                
                <hr class="dark:border-gray-700">
                
                <div class="space-y-2">
                     <div>
                        <label for="model-select" class="block text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">LLM Model</label>
                        <select id="model-select" v-model="selectedFullModel" class="input-field text-sm">
                            <option disabled value="">Select a model</option>
                            <optgroup v-for="group in availableLLMModelsGrouped" :key="group.label" :label="group.label">
                                <option v-for="model in group.items" :key="model.id" :value="model.id">{{ model.name }}</option>
                            </optgroup>
                        </select>
                    </div>

                    <div>
                        <div class="flex justify-between items-center mb-1">
                            <label class="block text-xs font-bold uppercase tracking-wider text-gray-500">Ontology Schema</label>
                            <button type="button" @click="handleImportOntology" class="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-1">
                                <IconArrowUpTray class="w-3 h-3" />
                                Import
                            </button>
                        </div>
                        <textarea v-model="generationParams.ontology" rows="6" class="input-field font-mono text-xs leading-relaxed" placeholder="Define entities and relationships..."></textarea>
                        <input type="file" ref="ontologyFileInput" @change="onOntologyFileSelected" class="hidden" accept=".owl,.rdf,.ttl,.jsonld,.pdf,.docx,.txt,.md,.json">
                        <p class="text-[10px] text-gray-400 mt-1">Defines the structure for the LLM to extract knowledge.</p>
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-3 pt-2">
                    <button @click="handleGenerateGraph" :disabled="!!task" class="btn btn-primary btn-sm">
                        {{ graphStats.nodes > 0 ? 'Re-Generate' : 'Generate Graph' }}
                    </button>
                    <button @click="handleUpdateGraph" :disabled="!!task || graphStats.nodes === 0" class="btn btn-secondary btn-sm">
                        Update Graph
                    </button>
                </div>
                
                 <div class="pt-2">
                    <button @click="handleWipeGraph" :disabled="!!task || graphStats.nodes === 0" class="btn btn-ghost text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 w-full btn-sm flex items-center justify-center gap-2">
                        <IconTrash class="w-4 h-4"/> Wipe All Data
                    </button>
                </div>
            </div>
            
            <!-- Query Section -->
            <div class="space-y-4 p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700">
                <h3 class="text-base font-semibold flex items-center gap-2">
                    <span class="w-1 h-4 bg-green-500 rounded-full"></span>
                    Query Graph
                </h3>
                <form @submit.prevent="handleQuery" class="flex gap-2">
                    <input v-model="query" type="text" placeholder="Search for concepts..." class="input-field flex-grow text-sm">
                    <button type="submit" :disabled="isQuerying || !query.trim()" class="btn btn-primary btn-sm px-4">Find</button>
                </form>
                
                <div v-if="isQuerying" class="flex justify-center p-4">
                    <IconAnimateSpin class="w-6 h-6 text-primary-500" />
                </div>
                
                <div v-if="queryResults.length > 0" class="space-y-2 max-h-60 overflow-y-auto custom-scrollbar bg-gray-50 dark:bg-gray-900 p-2 rounded-md">
                    <div v-for="(result, index) in queryResults" :key="index" class="p-2 bg-white dark:bg-gray-800 rounded border dark:border-gray-700 text-xs shadow-sm">
                       <pre class="whitespace-pre-wrap font-sans">{{ result }}</pre>
                    </div>
                </div>
                 <div v-else-if="!isQuerying && query && queryResults.length === 0" class="text-center text-gray-500 text-xs italic">
                    No results found.
                </div>
            </div>
        </div>

        <!-- Graph Viewer Column -->
        <div class="flex-grow h-[500px] lg:h-full lg:min-h-0 bg-white dark:bg-gray-900 rounded-lg shadow-inner border dark:border-gray-700 p-1">
            <InteractiveGraphViewer 
                ref="graphViewer"
                :nodes="graphData.nodes" 
                :edges="graphData.edges" 
                :is-loading="isLoadingGraph" 
                @node-select="handleNodeSelect" 
                @edge-select="handleEdgeSelect" 
                @deselect="handleDeselect"
            />
        </div>
    </div>
</template>
