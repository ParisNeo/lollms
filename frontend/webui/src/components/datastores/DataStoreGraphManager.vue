<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { useTasksStore } from '../../stores/tasks'; // NEW: Import tasks store
import { storeToRefs } from 'pinia';
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
const tasksStore = useTasksStore(); // NEW: Instantiate tasks store
const { user } = storeToRefs(authStore);
const { availableLLMModelsGrouped } = storeToRefs(dataStore);

const graphStats = ref({ nodes: 0, edges: 0 });
const graphData = ref(null);
const isLoadingGraph = ref(false);

const generationParams = ref({
    model_binding: '',
    model_name: '',
    chunk_size: 2048,
    overlap_size: 256
});

const selectedFullModel = ref('');

const query = ref('');
const queryResults = ref([]);
const isQuerying = ref(false);

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
    try {
        const data = await dataStore.fetchDataStoreGraph(props.store.id);
        graphData.value = data;
        graphStats.value = {
            nodes: data?.nodes?.length || 0,
            edges: data?.edges?.length || 0
        };
    } catch (error) {
        graphData.value = null;
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

function viewRawJson() {
    uiStore.openModal('interactiveOutput', {
        title: 'Graph Raw JSON',
        contentType: 'json',
        sourceCode: JSON.stringify(graphData.value, null, 2)
    });
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
    <div class="space-y-8">
        <!-- Stats and Info -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4 text-center">
                <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400">Nodes</h4>
                <p v-if="isLoadingGraph" class="text-2xl font-bold animate-pulse">...</p>
                <p v-else class="text-2xl font-bold">{{ graphStats.nodes }}</p>
            </div>
             <div class="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4 text-center">
                <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400">Edges</h4>
                 <p v-if="isLoadingGraph" class="text-2xl font-bold animate-pulse">...</p>
                <p v-else class="text-2xl font-bold">{{ graphStats.edges }}</p>
            </div>
            <div class="flex items-center justify-center">
                <button @click="viewRawJson" :disabled="!graphData || isLoadingGraph" class="btn btn-secondary">View Graph JSON</button>
            </div>
        </div>

        <!-- Task Progress -->
        <div v-if="task" class="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
            <h4 class="font-semibold text-blue-800 dark:text-blue-200">{{ task.name }}</h4>
            <p class="text-sm text-blue-700 dark:text-blue-300">{{ task.description }} ({{ task.progress }}%)</p>
            <div class="w-full bg-blue-200 rounded-full h-2 mt-2">
                <div class="bg-blue-600 h-2 rounded-full" :style="{ width: task.progress + '%' }"></div>
            </div>
        </div>

        <!-- Generation/Update Controls -->
        <div class="space-y-4 p-6 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <h3 class="text-lg font-semibold">Graph Management</h3>
             <div>
                <label for="model-select" class="block text-sm font-medium mb-1">Model for Generation</label>
                <select id="model-select" v-model="selectedFullModel" class="input-field">
                    <option disabled value="">Select a model</option>
                    <optgroup v-for="group in availableLLMModelsGrouped" :key="group.label" :label="group.label">
                        <option v-for="model in group.items" :key="model.id" :value="model.id">
                            {{ model.name }}
                        </option>
                    </optgroup>
                </select>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                 <div>
                    <label for="chunk-size" class="block text-sm font-medium mb-1">Chunk Size</label>
                    <input id="chunk-size" type="number" v-model.number="generationParams.chunk_size" class="input-field">
                </div>
                 <div>
                    <label for="overlap-size" class="block text-sm font-medium mb-1">Overlap Size</label>
                    <input id="overlap-size" type="number" v-model.number="generationParams.overlap_size" class="input-field">
                </div>
            </div>
            <div class="flex items-center gap-4 pt-4 border-t dark:border-gray-600">
                <button @click="handleGenerateGraph" :disabled="!!task" class="btn btn-primary">
                    {{ graphStats.nodes > 0 ? 'Re-Generate Graph' : 'Generate Graph' }}
                </button>
                <button @click="handleUpdateGraph" :disabled="!!task || graphStats.nodes === 0" class="btn btn-secondary">
                    Update Graph
                </button>
            </div>
        </div>
        
        <!-- Query Interface -->
        <div class="space-y-4 p-6 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <h3 class="text-lg font-semibold">Query Graph</h3>
            <form @submit.prevent="handleQuery" class="flex gap-4">
                <input v-model="query" type="text" placeholder="Enter your query..." class="input-field flex-grow">
                <button type="submit" :disabled="isQuerying || !query.trim()" class="btn btn-primary">
                    {{ isQuerying ? 'Querying...' : 'Query' }}
                </button>
            </form>
            <div v-if="isQuerying" class="text-center p-4">
                <IconAnimateSpin class="w-6 h-6 animate-spin mx-auto"/>
            </div>
            <div v-if="queryResults.length > 0" class="mt-4 space-y-2 max-h-96 overflow-y-auto">
                <div v-for="(result, index) in queryResults" :key="index" class="p-3 bg-white dark:bg-gray-800 rounded-md shadow-sm">
                   <pre class="whitespace-pre-wrap text-sm">{{ result }}</pre>
                </div>
            </div>
        </div>
    </div>
</template>