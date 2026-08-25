<template>
    <div class="w-full h-full relative border dark:border-gray-800 rounded-2xl overflow-hidden group isolate select-none bg-white dark:bg-gray-950">
        <!-- Search & Filter Bar -->
        <div class="absolute top-4 left-4 z-20 flex items-center gap-2 bg-white/90 dark:bg-gray-900/90 backdrop-blur-md p-1.5 rounded-xl border border-gray-200 dark:border-gray-800 shadow-lg max-w-sm w-full">
            <input 
                type="text" 
                v-model="searchFilter" 
                placeholder="Search nodes by label or property..." 
                class="bg-transparent text-xs px-2.5 py-1.5 outline-none grow text-gray-800 dark:text-gray-200 placeholder-gray-400"
            />
            <span v-if="filteredStats.matchedCount > 0" class="text-[10px] font-mono font-bold bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded-md">
                {{ filteredStats.matchedCount }} matches
            </span>
            <button v-if="searchFilter" @click="searchFilter = ''" class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                <IconXMark class="w-3.5 h-3.5" />
            </button>
        </div>

        <!-- Graph Container -->
        <div ref="networkContainer" class="w-full h-full cursor-grab active:cursor-grabbing outline-none"></div>
        
        <!-- Custom Tooltip -->
        <div v-if="tooltip.visible && tooltip.node" 
             class="absolute pointer-events-none z-50 bg-white/95 dark:bg-gray-900/95 backdrop-blur-md p-4 rounded-2xl shadow-2xl border border-gray-100 dark:border-gray-800 max-w-xs transition-opacity duration-200 flex flex-col gap-2.5"
             :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px', transform: 'translate(-50%, -100%)', marginTop: '-15px' }">
            
            <div class="flex items-center gap-2 border-b border-gray-100 dark:border-gray-800 pb-2">
                 <span class="w-3.5 h-3.5 rounded-full shrink-0 shadow-sm" :style="{ backgroundColor: tooltip.color }"></span>
                 <span class="font-bold text-sm text-gray-900 dark:text-gray-100 break-words leading-tight">{{ tooltip.node.label }}</span>
            </div>
            
            <div class="space-y-1.5 text-xs text-gray-600 dark:text-gray-300">
                <div class="flex gap-2">
                    <span class="font-bold text-gray-400 text-[10px] uppercase w-10">Type:</span> 
                    <span class="font-semibold bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-md text-[10px] uppercase tracking-wide">{{ tooltip.node.group }}</span>
                </div>
                <div class="flex gap-2">
                    <span class="font-bold text-gray-400 text-[10px] uppercase w-10">ID:</span> 
                    <span class="font-mono text-[11px] opacity-75">{{ tooltip.node.id }}</span>
                </div>
                
                <div v-if="tooltip.node.properties && Object.keys(tooltip.node.properties).length > 0" class="mt-2">
                     <span class="font-bold text-gray-400 text-[10px] uppercase block mb-1">Properties:</span>
                     <div class="bg-gray-50 dark:bg-gray-950 p-2.5 rounded-xl border border-gray-100 dark:border-gray-800/80 overflow-hidden max-h-32 overflow-y-auto custom-scrollbar">
                        <pre class="whitespace-pre-wrap font-mono text-[10px] leading-relaxed text-gray-700 dark:text-gray-300 break-all">{{ JSON.stringify(tooltip.node.properties, null, 2) }}</pre>
                     </div>
                </div>
            </div>
            
            <div class="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-full w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[6px] border-t-white dark:border-t-gray-900 drop-shadow-sm"></div>
        </div>

        <!-- Controls Overlay -->
        <div class="absolute bottom-4 right-4 flex gap-2 z-20">
            <button @click="resetView" class="p-2.5 bg-white/90 dark:bg-gray-900/90 backdrop-blur-md rounded-xl shadow-lg hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-800 transition-all active:scale-95" title="Fit to View">
                <IconMaximize class="w-4 h-4"/>
            </button>
            <button @click="togglePhysics" class="p-2.5 bg-white/90 dark:bg-gray-900/90 backdrop-blur-md rounded-xl shadow-lg hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-200 border border-gray-200 dark:border-gray-800 transition-all active:scale-95" :title="physicsEnabled ? 'Freeze Graph Layout' : 'Enable Live Physics'">
                <IconPause v-if="physicsEnabled" class="w-4 h-4 text-amber-500"/>
                <IconPlay v-else class="w-4 h-4 text-emerald-500"/>
            </button>
        </div>

        <!-- Loading Overlay -->
        <div v-if="isLoading" class="absolute inset-0 bg-white/60 dark:bg-gray-950/60 backdrop-blur-sm flex items-center justify-center z-30">
            <div class="bg-white dark:bg-gray-900 p-6 rounded-2xl shadow-2xl border border-gray-100 dark:border-gray-800 flex flex-col items-center gap-3">
                <IconAnimateSpin class="w-8 h-8 text-blue-500 animate-spin" />
                <span class="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-widest">Processing Graph...</span>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue';
import { Network } from 'vis-network';
import { useUiStore } from '../../stores/ui';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconPause from '../../assets/icons/IconStopCircle.vue'; 
import IconPlay from '../../assets/icons/IconPlayCircle.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';

const props = defineProps({
    nodes: { type: Array, default: () => [] },
    edges: { type: Array, default: () => [] },
    isLoading: { type: Boolean, default: false }
});

const emit = defineEmits(['node-select', 'edge-select', 'deselect']);

const uiStore = useUiStore();
const networkContainer = ref(null);
let network = null;
const physicsEnabled = ref(true);
const searchFilter = ref('');

const tooltip = ref({
    visible: false,
    x: 0,
    y: 0,
    node: null,
    color: ''
});

const typeColorMap = {
    'Person': '#38bdf8',       
    'Organization': '#818cf8', 
    'Location': '#4ade80',     
    'Date': '#fb923c',         
    'Product': '#2dd4bf',      
    'Event': '#f472b6',        
    'Concept': '#a78bfa',      
    'Technology': '#94a3b8',
    'Entity': '#60a5fa',
    'class': '#7c6ff7',
    'individual': '#4ade80',
    'default': '#94a3b8'       
};

function generateColor(str, isDark) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = Math.abs(hash) % 360;
    const s = 65; 
    const l = isDark ? 60 : 45; 
    return `hsl(${h}, ${s}%, ${l}%)`;
}

function getNodeColor(nodeType, isDark) {
    if (typeColorMap[nodeType]) return typeColorMap[nodeType];
    return generateColor(nodeType || 'default', isDark);
}

const filteredStats = computed(() => {
    if (!searchFilter.value.trim()) return { matchedCount: 0 };
    const query = searchFilter.value.toLowerCase().trim();
    const count = props.nodes.filter(n => {
        const label = String(n.properties?.identifying_value || n.properties?.name || n.properties?.label || n.label || n.id).toLowerCase();
        return label.includes(query) || JSON.stringify(n.properties || {}).toLowerCase().includes(query);
    }).length;
    return { matchedCount: count };
});

const getOptions = (theme) => {
    const isDark = theme === 'dark';
    const textColor = isDark ? '#f1f5f9' : '#0f172a';
    
    return {
        nodes: {
            shape: 'dot',
            size: 24,
            font: {
                size: 13,
                color: textColor,
                strokeWidth: 3, 
                strokeColor: isDark ? '#020617' : '#ffffff'
            },
            borderWidth: 2,
            shadow: {
                enabled: true,
                color: 'rgba(0,0,0,0.15)',
                size: 6,
                x: 2,
                y: 2
            }
        },
        edges: {
            width: 1.5,
            color: { 
                color: isDark ? '#475569' : '#94a3b8',
                highlight: '#3b82f6',
                hover: '#60a5fa',
                opacity: 0.85,
                inherit: false 
            },
            smooth: { 
                type: 'continuous',
                roundness: 0.5 
            },
            arrows: {
                to: { enabled: true, scaleFactor: 0.75 }
            },
            font: {
                align: 'middle',
                size: 10,
                color: isDark ? '#94a3b8' : '#64748b',
                strokeWidth: 2,
                strokeColor: isDark ? '#020617' : '#ffffff',
                background: 'transparent'
            },
            selectionWidth: 3
        },
        physics: {
            enabled: physicsEnabled.value,
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -35,
                centralGravity: 0.006,
                springLength: 180,
                springConstant: 0.08,
                damping: 0.45,
                avoidOverlap: 0.6
            },
            maxVelocity: 40,
            minVelocity: 0.5,
            stabilization: {
                enabled: true,
                iterations: 400,
                updateInterval: 50,
                onlyDynamicEdges: false
            }
        },
        interaction: {
            hover: true,
            hoverConnectedEdges: true,
            dragNodes: true,
            dragView: true,
            zoomView: true,
            selectable: true,
            selectConnectedEdges: true
        }
    };
};

function initializeOrUpdateGraph() {
    if (!networkContainer.value || !networkContainer.value.offsetParent) return;

    const isDark = uiStore.currentTheme === 'dark';
    const query = searchFilter.value.toLowerCase().trim();

    const data = {
        nodes: props.nodes.map(n => {
            const nodeType = n.label || 'Entity';
            const nodeLabel = String(n.properties?.identifying_value || n.properties?.name || n.properties?.label || n.label || n.id);
            const color = getNodeColor(nodeType, isDark);
            
            const matchesSearch = !query || 
                nodeLabel.toLowerCase().includes(query) || 
                JSON.stringify(n.properties || {}).toLowerCase().includes(query);

            return {
                id: String(n.id),
                label: nodeLabel.length > 28 ? nodeLabel.substring(0, 26) + '...' : nodeLabel,
                color: {
                    background: color,
                    border: matchesSearch ? color : (isDark ? '#334155' : '#cbd5e1'),
                    highlight: { background: color, border: '#ffffff' },
                    hover: { background: color, border: '#ffffff' }
                },
                opacity: matchesSearch ? 1.0 : 0.2,
                group: nodeType,
                _raw: n 
            };
        }),
        edges: props.edges.map(e => {
            const source = e.source ?? e.source_id ?? e.from ?? e.start ?? e.start_node_id;
            const target = e.target ?? e.target_id ?? e.to ?? e.end ?? e.end_node_id;
            
            return { 
                id: e.id,
                from: String(source),
                to: String(target),
                label: e.label || e.type || '',
                properties: e.properties,
                _raw: e
            };
        }).filter(e => e.from && e.to && e.from !== 'undefined' && e.to !== 'undefined')
    };
    
    const options = getOptions(uiStore.currentTheme);

    if (!network) {
        network = new Network(networkContainer.value, data, options);
        
        network.on('click', (params) => {
            if (params.nodes.length > 0) {
                const nodeId = params.nodes[0];
                const node = props.nodes.find(n => String(n.id) === String(nodeId));
                if (node) emit('node-select', node);
            } else if (params.edges.length > 0) {
                const edgeId = params.edges[0];
                const edge = props.edges.find(e => e.id === edgeId);
                if (edge) emit('edge-select', edge);
            } else {
                emit('deselect');
            }
        });

        network.on('hoverNode', (params) => {
            const nodeId = params.node;
            const positions = network.getPositions([nodeId]);
            const canvasPos = positions[nodeId];
            if (!canvasPos) return;

            const domPos = network.canvasToDOM(canvasPos);
            const nodeData = props.nodes.find(n => String(n.id) === String(nodeId));
            const nodeType = nodeData?.label || 'Entity';
            
            if (nodeData) {
                tooltip.value = {
                    visible: true,
                    x: domPos.x,
                    y: domPos.y,
                    node: {
                        id: nodeData.id,
                        label: String(nodeData.properties?.identifying_value || nodeData.properties?.name || nodeData.properties?.label || nodeData.label || nodeData.id),
                        group: nodeType,
                        properties: nodeData.properties
                    },
                    color: getNodeColor(nodeType, isDark)
                };
            }
        });

        network.on('blurNode', () => { tooltip.value.visible = false; });
        network.on('dragStart', () => { tooltip.value.visible = false; });
        network.on('zoom', () => { tooltip.value.visible = false; });
    } else {
        network.setOptions(options);
        network.setData(data);
    }
}

watch(() => [props.nodes, props.edges, searchFilter.value], () => {
    nextTick(() => {
        initializeOrUpdateGraph();
    });
}, { deep: true });

watch(() => uiStore.currentTheme, (newTheme) => {
    if (network) {
        network.setOptions(getOptions(newTheme));
        initializeOrUpdateGraph();
    }
});

onMounted(() => {
    initializeOrUpdateGraph();
});

onUnmounted(() => {
    if (network) {
        network.destroy();
        network = null;
    }
});

function focusNode(nodeId) {
    if (network) {
        network.focus(String(nodeId), {
            scale: 1.3,
            animation: { duration: 800, easingFunction: 'easeInOutQuad' }
        });
        network.selectNodes([String(nodeId)]);
    }
}

function resetView() {
    if (network) {
        network.fit({ 
            animation: { duration: 500, easingFunction: 'easeInOutQuad' } 
        });
    }
}

function togglePhysics() {
    if (!network) return;
    physicsEnabled.value = !physicsEnabled.value;
    network.setOptions({ physics: { enabled: physicsEnabled.value } });
}

defineExpose({ resetView, focusNode });
</script>

<style scoped>
:deep(.vis-network) {
    outline: none !important;
}
</style>