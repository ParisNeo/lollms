<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, defineAsyncComponent } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconPlay from '../../assets/icons/IconPlayCircle.vue';

// Async import for interactive graph to avoid initial load block
const InteractiveGraphViewer = defineAsyncComponent({
  loader: () => import('./InteractiveGraphViewer.vue'),
  loadingComponent: null,
  delay: 200,
  errorComponent: null,
  timeout: 3000
});

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
const isComponentMounted = ref(true);
const viewMode = ref('graph'); // 'graph' or 'ontology'

onBeforeUnmount(() => {
    isComponentMounted.value = false;
});
const ontologyEditorMode = ref('edit'); // 'edit' or 'view'

const defaultOntology = `@prefix : <http://lollms.com/ontology#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:MainConcept rdf:type owl:Class ;
             rdfs:label "Base Entity" .

:relatedTo rdf:type owl:ObjectProperty ;
           rdfs:domain :MainConcept ;
           rdfs:range :MainConcept .`;

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

const ontologyLanguage = ref('json');
const presets = ref([]);
const selectedPreset = ref(null);

const ontologyAsTag = computed(() => `<owl>${generationParams.value.ontology}</owl>`);

// [FIX] Persistence implementation
watch(() => generationParams.value.ontology, (newCode) => {
    if (props.store?.id) {
        dataStore.persistOntology(props.store.id, newCode);
    }
});

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
    if (!isComponentMounted.value) return;
    isLoadingGraph.value = true;
    selectedNode.value = null;
    selectedEdge.value = null;
    try {
        const data = await dataStore.fetchDataStoreGraph(props.store.id);
        if (!isComponentMounted.value) return;
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
        // Simple heuristic for language detection
        if (file.name.endsWith('.json')) ontologyLanguage.value = 'json';
        else if (file.name.endsWith('.yaml') || file.name.endsWith('.yml')) ontologyLanguage.value = 'yaml';
        else if (file.name.endsWith('.xml') || file.name.endsWith('.owl') || file.name.endsWith('.rdf')) ontologyLanguage.value = 'xml';
        else if (file.name.endsWith('.ttl')) ontologyLanguage.value = 'python'; // Approx for turtle
        else ontologyLanguage.value = 'markdown';
        
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

function loadPresets() {
    const defaults = [
        { name: 'Default (JSON)', language: 'json', content: defaultOntology },
        { name: 'Simple (YAML)', language: 'yaml', content: "entities:\n  - Person\n  - Place\nrelationships:\n  - visited" },
        { name: 'OWL/RDF (Turtle)', language: 'python', content: "@prefix : <http://example.org/> .\n:Person a :Class .\n:knows a :ObjectProperty ." },
        { name: 'Free Text (Markdown)', language: 'markdown', content: "Define Entities:\n- Person\n- Location\n\nDefine Relations:\n- Person lives in Location" }
    ];
    try {
        const stored = JSON.parse(localStorage.getItem('lollms_graph_presets') || '[]');
        presets.value = [...defaults, ...stored];
    } catch (e) {
        presets.value = defaults;
    }
}

function applyPreset() {
    if(selectedPreset.value) {
        generationParams.value.ontology = selectedPreset.value.content;
        ontologyLanguage.value = selectedPreset.value.language || 'json';
    }
}

async function savePreset() {
    // Simple prompt for now
    // Ideally use a modal
    const name = prompt("Enter a name for this ontology preset:");
    if(name) {
        const newPreset = {
            name,
            language: ontologyLanguage.value,
            content: generationParams.value.ontology
        };
        try {
            const stored = JSON.parse(localStorage.getItem('lollms_graph_presets') || '[]');
            stored.push(newPreset);
            localStorage.setItem('lollms_graph_presets', JSON.stringify(stored));
            loadPresets();
            // Select the newly created preset
            selectedPreset.value = presets.value[presets.value.length - 1];
            uiStore.addNotification("Preset saved", "success");
        } catch(e) {
            console.error(e);
            uiStore.addNotification("Failed to save preset", "error");
        }
    }
}

onMounted(() => {
    fetchGraph();
    loadPresets();
    
    // [FIX] Guard against accessing storeOntologies if not initialized or if store ID missing
    if (props.store?.id && dataStore.storeOntologies && dataStore.storeOntologies[props.store.id]) {
        generationParams.value.ontology = dataStore.storeOntologies[props.store.id];
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

=======
<template>
    <div class="h-full flex flex-col overflow-hidden">
        <!-- ── Navigation Header ── -->
        <div class="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800 border-b dark:border-gray-700 z-10 flex-shrink-0">
            <div class="flex gap-1 p-1 bg-gray-200 dark:bg-gray-900 rounded-xl">
                <button @click="viewMode = 'graph'" :class="['px-6 py-2 text-xs font-black uppercase tracking-widest rounded-lg transition-all', viewMode === 'graph' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700']">
                    Knowledge Graph
                </button>
                <button @click="viewMode = 'ontology'" :class="['px-6 py-2 text-xs font-black uppercase tracking-widest rounded-lg transition-all', viewMode === 'ontology' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700']">
                    Ontology Designer
                </button>
            </div>
            
            <div class="flex items-center gap-3">
                <button @click="handleUpdateGraph" :disabled="!!task || graphStats.nodes === 0" class="btn btn-secondary btn-sm h-9">
                    <IconRefresh class="w-4 h-4 mr-2" /> Sync Changes
                </button>
                <button @click="handleGenerateGraph" :disabled="!!task || !selectedFullModel" class="btn btn-primary btn-sm h-9 shadow-lg shadow-blue-500/20">
                    <IconPlay class="w-4 h-4 mr-2" /> {{ graphStats.nodes > 0 ? 'Full Rebuild' : 'Initialize Graph' }}
                </button>
            </div>
        </div>

        <div class="flex-grow flex flex-col lg:flex-row gap-0 overflow-hidden">
            <!-- ── Left Sidebar (Dynamic Content) ── -->
            <div class="w-full lg:w-80 lg:flex-shrink-0 space-y-6 h-full overflow-y-auto custom-scrollbar p-4 border-r dark:border-gray-700 bg-white dark:bg-gray-900">
                
                <!-- View-Specific Context Info -->
                <div class="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-100 dark:border-blue-800">
                    <h4 class="text-[10px] font-black uppercase text-blue-600 dark:text-blue-400 mb-1">Current Workspace</h4>
                    <p class="text-xs font-bold">{{ viewMode === 'graph' ? 'Semantic Explorer' : 'Schema Designer' }}</p>
                </div>

                <!-- Stats (Always relevant) -->
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center border dark:border-gray-600 shadow-inner">
                        <h4 class="text-[10px] font-black uppercase text-gray-500 dark:text-gray-400">Total Nodes</h4>
                        <p class="text-xl font-bold">{{ graphStats.nodes }}</p>
                    </div>
                    <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3 text-center border dark:border-gray-600 shadow-inner">
                        <h4 class="text-[10px] font-black uppercase text-gray-500 dark:text-gray-400">Total Edges</h4>
                        <p class="text-xl font-bold">{{ graphStats.edges }}</p>
                    </div>
                </div>

                <!-- Task Progress (Always relevant) -->
                <div v-if="task" class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800 animate-pulse">
                    <h4 class="font-semibold text-blue-800 dark:text-blue-200 text-sm flex justify-between">
                        {{ task.name }}
                        <span class="text-xs opacity-75">{{ task.progress }}%</span>
                    </h4>
                    <div class="w-full bg-blue-200 dark:bg-blue-800 rounded-full h-1.5 mt-2">
                        <div class="bg-blue-600 dark:bg-blue-400 h-1.5 rounded-full transition-all duration-500" :style="{ width: task.progress + '%' }"></div>
                    </div>
                </div>

                <!-- ── SIDEBAR CONTENT: GRAPH MODE ── -->
                <template v-if="viewMode === 'graph'">
                    <!-- Node Selection Info -->
                    <div v-if="selectedNode" class="p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border-2 border-blue-500 space-y-3 animate-in fade-in zoom-in-95">
                        <div class="flex justify-between items-start">
                            <h3 class="font-semibold text-lg">{{ selectedNode.label }}</h3>
                            <span class="px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-[10px] font-black uppercase">{{ selectedNode.group }}</span>
                        </div>
                        <div class="text-[10px] text-gray-500 font-mono opacity-50">#{{ selectedNode.id }}</div>
                        
                        <div class="bg-gray-50 dark:bg-gray-900 p-2 rounded border dark:border-gray-700 max-h-40 overflow-auto custom-scrollbar">
                            <JsonRenderer :json="selectedNode.properties" />
                        </div>
                        
                        <div class="flex gap-2 pt-2">
                            <button @click="openEditNodeModal" class="btn btn-secondary btn-xs flex-1">Edit</button>
                            <button @click="deleteSelectedNode" class="btn btn-danger btn-xs flex-1">Delete</button>
                        </div>
                    </div>
                    
                    <div v-else-if="selectedEdge" class="p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border-2 border-indigo-500 space-y-3 animate-in fade-in zoom-in-95">
                        <h3 class="text-[10px] font-black uppercase text-indigo-500 tracking-widest border-b pb-2 dark:border-gray-700">Semantic Relationship</h3>
                        <div class="font-bold text-sm text-gray-700 dark:text-gray-200">{{ selectedEdge.label }}</div>
                        <div class="text-[10px] text-gray-500 space-y-1 bg-gray-50 dark:bg-gray-950 p-2 rounded">
                            <div class="truncate"><span class="font-bold text-indigo-400">FROM:</span> {{ selectedEdge.source }}</div>
                            <div class="truncate"><span class="font-bold text-indigo-400">TO:</span> {{ selectedEdge.target }}</div>
                        </div>
                        <button @click="deleteSelectedEdge" class="btn btn-danger btn-xs w-full">Delete Link</button>
                    </div>

                    <!-- Graph Exploration Tools -->
                    <div class="space-y-4 p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700">
                        <h3 class="text-xs font-black uppercase text-gray-500 tracking-widest">Exploration Tools</h3>
                        <form @submit.prevent="handleQuery" class="flex gap-1">
                            <input v-model="query" type="text" placeholder="Search concepts..." class="input-field flex-grow text-xs h-8">
                            <button type="submit" :disabled="isQuerying || !query.trim()" class="btn btn-primary btn-xs px-3">Find</button>
                        </form>
                        
                        <div v-if="isQuerying" class="flex justify-center p-4">
                            <IconAnimateSpin class="w-5 h-5 text-blue-500 animate-spin" />
                        </div>
                        
                        <div v-if="queryResults.length > 0" class="space-y-2 max-h-60 overflow-y-auto custom-scrollbar bg-gray-50 dark:bg-gray-950 p-2 rounded-md shadow-inner">
                            <div v-for="(result, index) in queryResults" :key="index" class="p-2 bg-white dark:bg-gray-800 rounded border dark:border-gray-700 text-[10px] leading-relaxed shadow-sm">
                               {{ result }}
                            </div>
                        </div>
                        
                        <div class="flex gap-2 pt-2 border-t dark:border-gray-700">
                             <button @click="openAddNodeModal" class="btn btn-secondary btn-xs flex-1">New Node</button>
                             <button @click="fitGraph" class="btn btn-ghost btn-xs px-2" title="Fit to screen"><IconMaximize class="w-3.5 h-3.5"/></button>
                        </div>
                    </div>
                </template>

                <!-- ── SIDEBAR CONTENT: ONTOLOGY MODE ── -->
                <template v-else>
                    <div class="space-y-6">
                        <!-- Model Selection -->
                        <div class="p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700">
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400 mb-2">Generation Model</label>
                            <select v-model="selectedFullModel" class="input-field text-xs">
                                <option disabled value="">Select engine...</option>
                                <optgroup v-for="group in availableLLMModelsGrouped" :key="group.label" :label="group.label">
                                    <option v-for="model in group.items" :key="model.id" :value="model.id">{{ model.name }}</option>
                                </optgroup>
                            </select>
                            <p class="text-[9px] text-gray-500 mt-2 italic">This model will be used to extract relationships from your files using the schema defined on the right.</p>
                        </div>

                        <!-- Presets -->
                        <div class="p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm border dark:border-gray-700 space-y-3">
                            <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400">Ontology Presets</label>
                            <select v-model="selectedPreset" @change="applyPreset" class="input-field text-xs">
                                <option :value="null" disabled>Load specialized preset...</option>
                                <option v-for="(p, i) in presets" :key="i" :value="p">{{ p.name }}</option>
                            </select>
                            <button @click="savePreset" class="btn btn-secondary btn-xs w-full flex items-center justify-center gap-2">
                                <IconSave class="w-3.5 h-3.5" /> Save Current as Preset
                            </button>
                        </div>

                        <!-- Dangerous Zone -->
                         <div class="p-4 bg-red-50 dark:bg-red-950/20 rounded-lg border border-red-100 dark:border-red-900/40">
                             <h4 class="text-[10px] font-black uppercase text-red-600 tracking-widest mb-3">Maintenance</h4>
                             <button @click="handleWipeGraph" :disabled="!!task || graphStats.nodes === 0" class="btn btn-ghost text-red-600 hover:bg-red-100 dark:hover:bg-red-900/30 w-full btn-xs flex items-center justify-center gap-2 border border-red-200 dark:border-red-800">
                                <IconTrash class="w-3.5 h-3.5"/> Wipe Graph Data
                            </button>
                         </div>
                    </div>
                </template>
            </div>

            <!-- ── Main Workspace ── -->
            <div class="flex-grow h-full bg-white dark:bg-gray-950 relative overflow-hidden">
                
                <!-- MODE: GRAPH VIEW -->
                <div v-if="viewMode === 'graph'" class="h-full w-full relative">
                    <!-- Empty State Overlay -->
                    <div v-if="graphStats.nodes === 0 && !isLoadingGraph" class="absolute inset-0 flex flex-col items-center justify-center bg-gray-50/80 dark:bg-gray-900/80 z-10 p-6 text-center">
                        <div class="bg-white dark:bg-gray-800 p-10 rounded-3xl shadow-2xl border dark:border-gray-700 max-w-lg animate-in zoom-in-95 duration-500">
                            <div class="w-20 h-20 bg-blue-100 dark:bg-blue-900/50 rounded-full flex items-center justify-center mx-auto mb-6 text-blue-600 dark:text-blue-400">
                                <IconDatabase class="w-10 h-10" />
                            </div>
                            <h3 class="text-2xl font-black text-gray-900 dark:text-white mb-3 tracking-tight">Graph is Offline</h3>
                            <p class="text-gray-500 dark:text-gray-400 text-sm mb-8 leading-relaxed">
                                No semantic map has been built for this Data Store yet. Switch to the <strong>Ontology Designer</strong> to define your schema and start the extraction process.
                            </p>
                            <button @click="viewMode = 'ontology'" class="btn btn-primary px-10 py-3 rounded-2xl shadow-xl shadow-blue-500/20 flex items-center justify-center gap-2 mx-auto">
                                Open Designer &rarr;
                            </button>
                        </div>
                    </div>

                    <InteractiveGraphViewer 
                        v-if="graphStats.nodes > 0 || isLoadingGraph"
                        ref="graphViewer"
                        :nodes="graphData.nodes" 
                        :edges="graphData.edges" 
                        :is-loading="isLoadingGraph" 
                        @node-select="handleNodeSelect" 
                        @edge-select="handleEdgeSelect" 
                        @deselect="handleDeselect"
                    />
                </div>

                <!-- MODE: ONTOLOGY DESIGNER -->
                <div v-else class="h-full flex flex-col">
                    <div class="flex-shrink-0 p-4 border-b dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50 flex justify-between items-center h-14">
                        <div class="flex items-center gap-4">
                            <div class="flex items-center gap-2 px-1 py-1 bg-gray-200 dark:bg-gray-800 rounded-lg">
                                <button @click="ontologyEditorMode = 'edit'" :class="['px-4 py-1 rounded-md text-[10px] font-black uppercase tracking-widest transition-all', ontologyEditorMode === 'edit' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700']">Code Editor</button>
                                <button @click="ontologyEditorMode = 'view'" :class="['px-4 py-1 rounded-md text-[10px] font-black uppercase tracking-widest transition-all', ontologyEditorMode === 'view' ? 'bg-white dark:bg-gray-700 text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700']">Visualizer</button>
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                            <button @click="handleImportOntology" class="btn btn-secondary btn-xs flex items-center gap-2 px-4 h-8 border-gray-300 dark:border-gray-700 shadow-sm">
                                <IconArrowUpTray class="w-3.5 h-3.5" /> 
                                <span class="hidden sm:inline">Import OWL</span>
                            </button>
                        </div>
                    </div>
                    <div class="flex-grow relative bg-white dark:bg-gray-950">
                        <CodeMirrorEditor 
                            v-if="ontologyEditorMode === 'edit'"
                            v-model="generationParams.ontology" 
                            :language="'python'" 
                            class="absolute inset-0 h-full w-full" 
                            placeholder="Define your classes and properties using OWL/Turtle syntax..."
                        />
                        <div v-else class="h-full p-10 overflow-auto custom-scrollbar flex justify-center bg-gray-50 dark:bg-gray-950/40">
                             <div class="w-full max-w-4xl h-full shadow-2xl rounded-3xl overflow-hidden bg-white dark:bg-gray-950 border dark:border-gray-800">
                                 <MessageContentRenderer :content="ontologyAsTag" />
                             </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
