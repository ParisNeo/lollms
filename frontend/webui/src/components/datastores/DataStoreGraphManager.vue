<template>
    <div class="h-full flex flex-col overflow-hidden bg-white dark:bg-gray-950">
        <!-- Top Toolbar & Navigation -->
        <header class="px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 flex flex-wrap items-center justify-between gap-3 shrink-0 z-20">
            <!-- Mode Tabs (TBox Summary / TBox Raw / ABox Instances) -->
            <div class="flex items-center gap-1 p-1 bg-gray-200/80 dark:bg-gray-800 rounded-xl">
                <button @click="switchGraphMode('tbox_summary')" 
                        :class="['px-4 py-1.5 text-xs font-black uppercase tracking-wider rounded-lg transition-all', 
                                 currentGraphMode === 'tbox_summary' ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200']">
                    TBox · Summary
                </button>
                <button @click="switchGraphMode('tbox')" 
                        :class="['px-4 py-1.5 text-xs font-black uppercase tracking-wider rounded-lg transition-all', 
                                 currentGraphMode === 'tbox' ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200']">
                    TBox · Terminology
                </button>
                <button @click="switchGraphMode('abox')" 
                        :class="['px-4 py-1.5 text-xs font-black uppercase tracking-wider rounded-lg transition-all', 
                                 currentGraphMode === 'abox' ? 'bg-white dark:bg-gray-700 text-emerald-600 dark:text-emerald-400 shadow-sm' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200']">
                    ABox · Instances
                </button>
            </div>

            <!-- Layout & Visual Toggles -->
            <div class="flex items-center gap-2">
                <select v-model="currentLayout" @change="applyLayout(currentLayout)" class="input-field !py-1 !px-2.5 text-xs font-bold bg-white dark:bg-gray-800">
                    <option value="concentric">Concentric Layout</option>
                    <option value="breadthfirst">Hierarchical (DAG)</option>
                    <option value="cose">Force-Directed (CoSE)</option>
                    <option value="circle">Circle Layout</option>
                    <option value="grid">Grid Layout</option>
                </select>

                <label class="flex items-center gap-1.5 text-xs font-bold text-gray-500 cursor-pointer select-none">
                    <input type="checkbox" v-model="showLabels" class="rounded text-blue-600" />
                    <span>Labels</span>
                </label>
            </div>

            <!-- Action Panel Toggles & Rebuild Controls -->
            <div class="flex items-center gap-2">
                <button @click="toggleAside('sparql')" :class="['btn btn-sm px-3 h-8 text-xs font-bold', activeAside === 'sparql' ? 'btn-primary' : 'btn-secondary']">
                    SPARQL 1.1
                </button>
                <button @click="toggleAside('path')" :class="['btn btn-sm px-3 h-8 text-xs font-bold', activeAside === 'path' ? 'btn-primary' : 'btn-secondary']">
                    Shortest Path
                </button>
                <button @click="toggleAside('inspector')" :class="['btn btn-sm px-3 h-8 text-xs font-bold', activeAside === 'inspector' ? 'btn-primary' : 'btn-secondary']">
                    Inspector
                </button>

                <div class="h-4 w-px bg-gray-300 dark:bg-gray-700 mx-1"></div>

                <button @click="handleAutoExtractOntology" :disabled="isExtractingOntology" class="btn btn-secondary btn-sm h-8 text-purple-600 dark:text-purple-300 border-purple-200 dark:border-purple-800" title="Extract schema from documents">
                    <IconAnimateSpin v-if="isExtractingOntology" class="w-3.5 h-3.5 mr-1 animate-spin" />
                    <IconSparkles v-else class="w-3.5 h-3.5 mr-1 text-purple-500" />
                    <span>Auto-Extract</span>
                </button>
                <button @click="handleGenerateGraph" :disabled="!!task" class="btn btn-primary btn-sm h-8 shadow-sm">
                    <IconPlay class="w-3.5 h-3.5 mr-1" />
                    <span>{{ graphStats.nodes > 0 ? 'Full Rebuild' : 'Initialize Graph' }}</span>
                </button>
            </div>
        </header>

        <!-- Sub-Bar Info -->
        <div class="px-4 py-1.5 bg-gray-100/70 dark:bg-gray-900/40 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between text-xs text-gray-500 shrink-0">
            <span class="font-medium truncate">{{ modeDescriptions[currentGraphMode] }}</span>
            <div class="flex items-center gap-3 shrink-0 font-mono text-[11px]">
                <span class="text-blue-500 font-bold">{{ graphStats.nodes }} nodes</span>
                <span>/</span>
                <span class="text-purple-500 font-bold">{{ graphStats.edges }} edges</span>
            </div>
        </div>

        <div class="grow flex flex-row overflow-hidden relative">
            <!-- Main Cytoscape Canvas Viewport -->
            <div class="grow h-full relative overflow-hidden bg-white dark:bg-gray-950 flex flex-col">
                <div ref="cyContainer" class="absolute inset-0 h-full w-full outline-none"></div>

                <!-- Custom Hover Tooltip -->
                <div v-if="tooltip.visible && tooltip.data"
                     class="absolute pointer-events-none z-40 bg-white/95 dark:bg-gray-900/95 backdrop-blur-md p-4 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-800 max-w-xs transition-opacity duration-200"
                     :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px', transform: 'translate(-50%, -100%)', marginTop: '-15px' }">
                    <div class="font-bold text-sm text-gray-900 dark:text-white flex items-center gap-2 border-b dark:border-gray-800 pb-1.5 mb-2">
                        <span>{{ tooltip.data.label }}</span>
                        <span class="text-[9px] px-1.5 py-0.5 rounded font-mono uppercase bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">{{ tooltip.data.box || 'tbox' }}</span>
                    </div>
                    <div class="text-xs space-y-1 text-gray-600 dark:text-gray-300">
                        <div><span class="font-bold text-gray-400 text-[10px] uppercase">Type:</span> <span class="font-semibold">{{ tooltip.data.type }}</span></div>
                        <div v-if="tooltip.data.instance_count !== undefined"><span class="font-bold text-gray-400 text-[10px] uppercase">Instances:</span> <span class="font-mono text-emerald-500 font-bold">{{ tooltip.data.instance_count }}</span> (double-click to expand)</div>
                        <div v-if="tooltip.data.uri" class="truncate font-mono text-[10px] opacity-60">{{ tooltip.data.uri }}</div>
                    </div>
                </div>

                <!-- Floating Canvas Controls -->
                <div class="absolute bottom-4 left-4 flex gap-2 z-20">
                    <button @click="cyInstance?.fit(null, 40)" class="btn btn-secondary btn-xs h-8 px-3 rounded-xl shadow-md font-bold">Fit View</button>
                    <button @click="applyLayout(currentLayout)" class="btn btn-secondary btn-xs h-8 px-3 rounded-xl shadow-md font-bold">Re-layout</button>
                </div>
            </div>

            <!-- Right Slide-Over Panels (Inspector, SPARQL, Shortest Path) -->
            <!-- 1. Inspector Panel -->
            <aside v-if="activeAside === 'inspector'" class="w-80 lg:w-96 shrink-0 h-full border-l border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col z-30 p-4 space-y-4 overflow-y-auto custom-scrollbar">
                <div class="flex items-center justify-between border-b dark:border-gray-800 pb-2">
                    <h3 class="font-black text-sm uppercase tracking-wider text-gray-700 dark:text-gray-300">Inspector</h3>
                    <button @click="activeAside = null" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">✕</button>
                </div>

                <div v-if="selectedElementData" class="space-y-4">
                    <div>
                        <label class="text-[10px] font-bold uppercase text-gray-400">Label</label>
                        <div class="font-bold text-base text-gray-900 dark:text-white mt-0.5">{{ selectedElementData.label }}</div>
                    </div>

                    <div v-if="selectedElementData.uri">
                        <label class="text-[10px] font-bold uppercase text-gray-400">Resource URI</label>
                        <div class="font-mono text-xs text-blue-600 dark:text-blue-400 break-all mt-0.5">{{ selectedElementData.uri }}</div>
                    </div>

                    <div v-if="selectedElementData.expandable" class="p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/40 rounded-xl space-y-2">
                        <span class="text-xs font-bold text-amber-800 dark:text-amber-300 block">Class Instances: {{ selectedElementData.instance_count }}</span>
                        <button @click="expandSelectedClass" class="btn btn-primary btn-xs w-full py-1.5 rounded-lg">Expand Individuals on Canvas</button>
                    </div>

                    <!-- Literal Properties -->
                    <div v-if="selectedElementData.properties && Object.keys(selectedElementData.properties).length > 0">
                        <label class="text-[10px] font-bold uppercase text-gray-400 block mb-2">Properties</label>
                        <JsonRenderer :json="selectedElementData.properties" class="p-2.5 bg-gray-50 dark:bg-gray-950 rounded-xl border dark:border-gray-800 text-[10px]" />
                    </div>

                    <!-- Connect / Relationship Tools -->
                    <div class="pt-4 border-t border-gray-100 dark:border-gray-800 space-y-2">
                        <label class="text-[10px] font-black uppercase text-gray-400">Quick Actions</label>
                        <button @click="setPathNode('source')" class="btn btn-secondary btn-xs w-full text-left py-2">Set as Path Source</button>
                        <button @click="setPathNode('target')" class="btn btn-secondary btn-xs w-full text-left py-2">Set as Path Target</button>
                    </div>
                </div>
                <div v-else class="text-center py-20 text-xs text-gray-400 italic">Click any node or edge on the canvas to inspect its axioms and properties.</div>
            </aside>

            <!-- 2. SPARQL 1.1 Panel -->
            <aside v-if="activeAside === 'sparql'" class="w-80 lg:w-96 shrink-0 h-full border-l border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col z-30 p-4 space-y-3 overflow-hidden">
                <div class="flex items-center justify-between border-b dark:border-gray-800 pb-2 shrink-0">
                    <h3 class="font-black text-sm uppercase tracking-wider text-gray-700 dark:text-gray-300">SPARQL 1.1 Console</h3>
                    <button @click="activeAside = null" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">✕</button>
                </div>

                <div class="flex gap-1 shrink-0 overflow-x-auto pb-1">
                    <button @click="applySparqlSnippet('all')" class="btn btn-secondary btn-xs text-[10px]">All Triples</button>
                    <button @click="applySparqlSnippet('counts')" class="btn btn-secondary btn-xs text-[10px]">Type Counts</button>
                    <button @click="applySparqlSnippet('construct')" class="btn btn-secondary btn-xs text-[10px]">Construct</button>
                </div>

                <textarea v-model="sparqlQuery" class="input-field font-mono text-xs h-32 shrink-0 resize-none" spellcheck="false"></textarea>

                <div class="flex justify-end gap-2 shrink-0">
                    <button @click="runSPARQLQuery" :disabled="isExecutingSparql" class="btn btn-primary btn-xs px-4 h-7">
                        <IconAnimateSpin v-if="isExecutingSparql" class="w-3.5 h-3.5 mr-1 animate-spin" />
                        <span>Run Query</span>
                    </button>
                </div>

                <div class="grow overflow-y-auto custom-scrollbar bg-gray-50 dark:bg-gray-950 rounded-xl border dark:border-gray-800 p-2 text-xs">
                    <div v-if="!sparqlResultData" class="text-center py-10 text-gray-400 italic">Execute a query to inspect results table.</div>
                    <table v-else-if="sparqlResultData.rows" class="w-full text-[11px] font-mono text-left">
                        <thead>
                            <tr class="border-b dark:border-gray-800 text-gray-400">
                                <th v-for="c in sparqlResultData.columns" :key="c" class="p-1.5">{{ c }}</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr v-for="(r, idx) in sparqlResultData.rows" :key="idx" class="border-b dark:border-gray-900 hover:bg-blue-500/5">
                                <td v-for="(val, cIdx) in r" :key="cIdx" class="p-1.5 truncate max-w-[120px]" :title="val">{{ val }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </aside>

            <!-- 3. Shortest Path Panel -->
            <aside v-if="activeAside === 'path'" class="w-80 lg:w-96 shrink-0 h-full border-l border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex flex-col z-30 p-4 space-y-4 overflow-y-auto custom-scrollbar">
                <div class="flex items-center justify-between border-b dark:border-gray-800 pb-2">
                    <h3 class="font-black text-sm uppercase tracking-wider text-gray-700 dark:text-gray-300">Shortest Path Finder</h3>
                    <button @click="activeAside = null" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">✕</button>
                </div>

                <div class="space-y-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-xl border dark:border-gray-800 text-xs">
                    <div>
                        <span class="font-bold text-gray-400 block mb-1">Source Resource</span>
                        <div class="font-mono p-2 bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 truncate">{{ pathSource?.label || '(Select node & click "Set as Source")' }}</div>
                    </div>
                    <div>
                        <span class="font-bold text-gray-400 block mb-1">Target Resource</span>
                        <div class="font-mono p-2 bg-white dark:bg-gray-900 rounded-lg border dark:border-gray-700 truncate">{{ pathTarget?.label || '(Select node & click "Set as Target")' }}</div>
                    </div>
                </div>

                <div class="flex gap-2">
                    <button @click="findShortestPath" :disabled="!pathSource || !pathTarget || isFindingPath" class="btn btn-primary btn-xs flex-1 py-2">
                        <IconAnimateSpin v-if="isFindingPath" class="w-3.5 h-3.5 mr-1 animate-spin" />
                        <span>Find Path</span>
                    </button>
                    <button @click="clearPathHighlight" class="btn btn-secondary btn-xs py-2">Clear</button>
                </div>

                <div v-if="pathResult" class="p-3 bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800/40 rounded-xl text-xs">
                    <span class="font-bold text-blue-600 dark:text-blue-400 block mb-1">Path Found: {{ pathResult.length }} hop(s)</span>
                    <ul class="list-disc list-inside space-y-1 font-mono text-[11px] text-gray-600 dark:text-gray-300">
                        <li v-for="(p, idx) in pathResult.nodes" :key="idx">{{ p.data.label }}</li>
                    </ul>
                </div>
            </aside>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { storeToRefs } from 'pinia';
import JsonRenderer from '../ui/JsonRenderer.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconPlay from '../../assets/icons/IconPlayCircle.vue';

const props = defineProps({
    store: { type: Object, required: true },
    task: { type: Object, default: null }
});

const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const { user } = storeToRefs(authStore);

const cyContainer = ref(null);
let cyInstance = null;

const currentGraphMode = ref('tbox_summary'); // 'tbox_summary' | 'tbox' | 'abox'
const currentLayout = ref('concentric');
const showLabels = ref(true);
const activeAside = ref(null); // 'inspector' | 'sparql' | 'path' | null

const graphStats = ref({ nodes: 0, edges: 0 });
const selectedElementData = ref(null);
const tooltip = ref({ visible: false, x: 0, y: 0, data: null });

const isExtractingOntology = ref(false);
const isExecutingSparql = ref(false);
const isFindingPath = ref(false);

const sparqlQuery = ref('SELECT ?subject ?predicate ?object\nWHERE {\n  ?subject ?predicate ?object .\n}\nLIMIT 25');
const sparqlResultData = ref(null);

const pathSource = ref(null);
const pathTarget = ref(null);
const pathResult = ref(null);

const modeDescriptions = {
    tbox_summary: 'Aggregated class-to-class schema overview. Double-click classes with gold borders to expand instances.',
    tbox: 'Raw Terminology Graph: Classes, Object Properties, Domain, Range, and SubClassOf hierarchy.',
    abox: 'Raw Assertion Graph: Individual instances and direct factual relationships.'
};

const COLORS = {
    class: '#4f7cff',
    individual: '#33b679',
    property: '#e07b39',
    blank: '#9aa0a6',
    resource: '#b06fd6'
};

function nodeColor(ele) {
    const type = ele.data('type') || 'resource';
    return COLORS[type] || '#4f7cff';
}

function styleSheet() {
    const isDark = uiStore.currentTheme === 'dark';
    return [
        {
            selector: 'node',
            style: {
                'background-color': ele => nodeColor(ele),
                'label': showLabels.value ? 'data(label)' : '',
                'color': isDark ? '#e8e9ec' : '#1e293b',
                'font-size': 10,
                'text-valign': 'bottom',
                'text-margin-y': 4,
                'width': 26,
                'height': 26,
                'border-width': 1.5,
                'border-color': 'rgba(255,255,255,0.4)',
                'min-zoomed-font-size': 6
            }
        },
        { selector: 'node[type = "class"]', style: { 'shape': 'round-rectangle', 'width': 32, 'height': 32 } },
        { selector: 'node[type = "class"][?expandable]', style: { 'border-width': 2.5, 'border-color': '#ffd166', 'border-style': 'double' } },
        { selector: 'node[type = "property"]', style: { 'shape': 'diamond', 'width': 28, 'height': 28 } },
        { selector: 'node:selected', style: { 'border-width': 3.5, 'border-color': '#ffffff', 'label': 'data(label)' } },
        {
            selector: 'edge',
            style: {
                'width': 1.5,
                'line-color': isDark ? '#4a5064' : '#94a3b8',
                'target-arrow-color': isDark ? '#4a5064' : '#94a3b8',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier',
                'label': showLabels.value ? 'data(label)' : '',
                'font-size': 8,
                'color': isDark ? '#9aa0ac' : '#64748b',
                'text-background-color': isDark ? '#0f1115' : '#ffffff',
                'text-background-opacity': 0.9,
                'text-background-padding': 2
            }
        },
        { selector: 'edge[kind = "hierarchy"]', style: { 'line-color': '#4f7cff', 'target-arrow-color': '#4f7cff', 'width': 2 } },
        { selector: 'edge[kind = "data"]', style: { 'line-color': '#33b679', 'target-arrow-color': '#33b679' } },
        { selector: '.faded', style: { 'opacity': 0.15 } },
        { selector: '.path-highlight', style: { 'background-color': '#ffd166', 'line-color': '#ffd166', 'target-arrow-color': '#ffd166', 'width': 3.5, 'z-index': 999 } }
    ];
}

function loadCytoscape() {
    return new Promise((resolve) => {
        if (window.cytoscape) {
            resolve(window.cytoscape);
            return;
        }
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js';
        script.onload = () => resolve(window.cytoscape);
        document.head.appendChild(script);
    });
}

async function initCytoscape() {
    if (!cyContainer.value) return;

    if (cyInstance) {
        cyInstance.destroy();
        cyInstance = null;
    }

    const cyMod = await loadCytoscape();

    cyInstance = cyMod({
        container: cyContainer.value,
        style: styleSheet(),
        wheelSensitivity: 0.25,
        hideEdgesOnViewport: true,
        textureOnViewport: true
    });

    cyInstance.on('mouseover', 'node', (evt) => {
        const d = evt.target.data();
        tooltip.value = {
            visible: true,
            x: evt.renderedPosition.x,
            y: evt.renderedPosition.y,
            data: d
        };
        cyInstance.elements().not(evt.target.closedNeighborhood()).addClass('faded');
    });

    cyInstance.on('mouseout', 'node', () => {
        tooltip.value.visible = false;
        cyInstance.elements().removeClass('faded');
    });

    cyInstance.on('tap', 'node', (evt) => {
        selectedElementData.value = evt.target.data();
        activeAside.value = 'inspector';
    });

    cyInstance.on('tap', 'edge', (evt) => {
        selectedElementData.value = evt.target.data();
        activeAside.value = 'inspector';
    });

    cyInstance.on('tap', (evt) => {
        if (evt.target === cyInstance) {
            selectedElementData.value = null;
        }
    });

    cyInstance.on('dblclick', 'node[type = "class"]', (evt) => {
        if (currentGraphMode.value === 'tbox_summary') {
            expandClassNode(evt.target);
        }
    });
}

function applyLayout(layoutName = 'concentric') {
    if (!cyInstance || cyInstance.nodes().length === 0) return;
    const opts = { name: layoutName, animate: true, animationDuration: 400, padding: 40, fit: true };
    if (layoutName === 'cose') {
        opts.nodeRepulsion = 12000;
        opts.idealEdgeLength = 100;
    }
    if (layoutName === 'breadthfirst') {
        opts.directed = true;
        opts.spacingFactor = 1.2;
    }
    cyInstance.layout(opts).run();
}

async function loadGraphData(mode = currentGraphMode.value) {
    currentGraphMode.value = mode;
    try {
        const data = await dataStore.fetchDataStoreGraph(props.store.id, mode);
        if (!cyInstance) await initCytoscape();
        if (!cyInstance) return;

        cyInstance.elements().remove();
        if (data.nodes && data.nodes.length > 0) {
            cyInstance.add([...data.nodes, ...(data.edges || [])]);
            graphStats.value = {
                nodes: data.nodes.length,
                edges: (data.edges || []).length
            };
            applyLayout(currentLayout.value);
        } else {
            graphStats.value = { nodes: 0, edges: 0 };
        }
    } catch (e) {
        console.error("Failed to load graph:", e);
    }
}

function switchGraphMode(mode) {
    loadGraphData(mode);
}

async function expandClassNode(node) {
    const classUri = node.data('uri') || node.data('label');
    uiStore.addNotification(`Expanding instances for ${node.data('label')}...`, 'info');
    try {
        const data = await dataStore.expandClassInstances({
            storeId: props.store.id,
            classUri: classUri,
            offset: 0,
            limit: 100
        });

        if (data.nodes && data.nodes.length > 0) {
            const existingIds = new Set(cyInstance.nodes().map(n => n.id()));
            const newNodes = data.nodes.filter(n => !existingIds.has(n.data.id));
            cyInstance.add([...newNodes, ...(data.edges || [])]);
            applyLayout('breadthfirst');
            uiStore.addNotification(`Loaded ${newNodes.length} individuals.`, 'success');
        } else {
            uiStore.addNotification('No direct individuals found for this class.', 'info');
        }
    } catch (e) {
        uiStore.addNotification('Failed to expand class.', 'error');
    }
}

function expandSelectedClass() {
    if (selectedElementData.value) {
        const node = cyInstance.getElementById(selectedElementData.value.id);
        if (node.length) expandClassNode(node);
    }
}

function toggleAside(panel) {
    activeAside.value = activeAside.value === panel ? null : panel;
}

function setPathNode(type) {
    if (!selectedElementData.value) return;
    if (type === 'source') {
        pathSource.value = { ...selectedElementData.value };
        uiStore.addNotification(`Source set to ${selectedElementData.value.label}`, 'info');
    } else {
        pathTarget.value = { ...selectedElementData.value };
        uiStore.addNotification(`Target set to ${selectedElementData.value.label}`, 'info');
    }
    activeAside.value = 'path';
}

async function findShortestPath() {
    if (!pathSource.value || !pathTarget.value) return;
    isFindingPath.value = true;
    try {
        const res = await dataStore.findGraphPath({
            storeId: props.store.id,
            sourceUri: pathSource.value.uri || pathSource.value.id,
            targetUri: pathTarget.value.uri || pathTarget.value.id
        });

        pathResult.value = res;
        clearPathHighlight();

        const pathNodeIds = res.nodes.map(n => n.data.id);
        const coll = cyInstance.collection();
        pathNodeIds.forEach(id => {
            const n = cyInstance.getElementById(id);
            if (n.length) coll.merge(n);
        });
        coll.connectedEdges().forEach(e => {
            if (pathNodeIds.includes(e.data('source')) && pathNodeIds.includes(e.data('target'))) {
                coll.merge(e);
            }
        });
        coll.addClass('path-highlight');
        cyInstance.fit(coll, 60);
        uiStore.addNotification(`Shortest path found (${res.path_length} hops).`, 'success');
    } catch (e) {
        uiStore.addNotification(e.response?.data?.detail || 'No path found.', 'warning');
    } finally {
        isFindingPath.value = false;
    }
}

function clearPathHighlight() {
    if (cyInstance) cyInstance.elements().removeClass('path-highlight');
    pathResult.value = null;
}

function applySparqlSnippet(type) {
    if (type === 'all') sparqlQuery.value = `SELECT ?subject ?predicate ?object\nWHERE {\n  ?subject ?predicate ?object .\n}\nLIMIT 25`;
    if (type === 'counts') sparqlQuery.value = `SELECT ?type (COUNT(?s) AS ?count)\nWHERE {\n  ?s a ?type .\n}\nGROUP BY ?type`;
    if (type === 'construct') sparqlQuery.value = `CONSTRUCT { ?s ?p ?o }\nWHERE { ?s ?p ?o }\nLIMIT 50`;
}

async function runSPARQLQuery() {
    if (!sparqlQuery.value.trim()) return;
    isExecutingSparql.value = true;
    try {
        const res = await dataStore.querySparqlGraph({
            storeId: props.store.id,
            query: sparqlQuery.value
        });
        
        if (res.results?.bindings) {
            const columns = res.head?.vars || Object.keys(res.results.bindings[0] || {});
            const rows = res.results.bindings.map(b => columns.map(c => b[c]?.value ?? ''));
            sparqlResultData.value = { columns, rows };
        } else {
            sparqlResultData.value = { columns: ['Result'], rows: [[JSON.stringify(res)]] };
        }
        uiStore.addNotification("SPARQL query executed.", "success");
    } catch (e) {
        uiStore.addNotification(`SPARQL Error: ${e.response?.data?.detail || e.message}`, "error");
    } finally {
        isExecutingSparql.value = false;
    }
}

async function handleAutoExtractOntology() {
    isExtractingOntology.value = true;
    try {
        const res = await dataStore.extractStoreOntology(props.store.id);
        if (res.nodes) {
            loadGraphData('tbox');
            uiStore.addNotification("Domain schema auto-extracted from documents!", "success");
        }
    } catch (e) {
        uiStore.addNotification(e.response?.data?.detail || "Extraction failed.", "error");
    } finally {
        isExtractingOntology.value = false;
    }
}

function handleGenerateGraph() {
    dataStore.generateDataStoreGraph({
        storeId: props.store.id,
        graphData: {
            graph_type: 'knowledge_graph',
            ontology: dataStore.storeOntologies?.[props.store.id] || ''
        }
    });
}

onMounted(() => {
    nextTick(async () => {
        await initCytoscape();
        loadGraphData();
    });
});

onUnmounted(() => {
    if (cyInstance) {
        cyInstance.destroy();
        cyInstance = null;
    }
});

watch(showLabels, () => {
    if (cyInstance) {
        cyInstance.style(styleSheet()).update();
    }
});

watch(() => props.store.id, () => {
    loadGraphData();
});
</script>

<style scoped>
:deep(.vis-network) {
    outline: none !important;
}
</style>