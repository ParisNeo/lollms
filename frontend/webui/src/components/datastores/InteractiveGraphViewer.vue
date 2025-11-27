<template>
    <div class="w-full h-full relative border dark:border-gray-700 rounded-lg overflow-hidden group isolate select-none">
        <!-- Graph Container -->
        <div ref="networkContainer" class="w-full h-full bg-white dark:bg-gray-900 cursor-grab active:cursor-grabbing outline-none"></div>
        
        <!-- Custom Tooltip -->
        <div v-if="tooltip.visible && tooltip.node" 
             class="absolute pointer-events-none z-50 bg-white dark:bg-gray-800 p-3 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 max-w-sm transition-opacity duration-200 flex flex-col gap-2"
             :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px', transform: 'translate(-50%, -100%)', marginTop: '-15px' }">
            
            <div class="flex items-center gap-2 border-b border-gray-100 dark:border-gray-700 pb-2">
                 <span class="w-3 h-3 rounded-full flex-shrink-0 shadow-sm" :style="{ backgroundColor: tooltip.color }"></span>
                 <span class="font-bold text-sm text-gray-800 dark:text-gray-100 break-words leading-tight">{{ tooltip.node.label }}</span>
            </div>
            
            <div class="space-y-1.5 text-xs text-gray-600 dark:text-gray-300">
                <div class="flex gap-2">
                    <span class="font-semibold text-gray-500 dark:text-gray-400 w-8">Type:</span> 
                    <span class="font-medium bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wide">{{ tooltip.node.group }}</span>
                </div>
                <div class="flex gap-2">
                    <span class="font-semibold text-gray-500 dark:text-gray-400 w-8">ID:</span> 
                    <span class="font-mono opacity-75">{{ tooltip.node.id }}</span>
                </div>
                
                <div v-if="tooltip.node.properties && Object.keys(tooltip.node.properties).length > 0" class="mt-1">
                     <span class="font-semibold text-gray-500 dark:text-gray-400 block mb-1">Properties:</span>
                     <div class="bg-gray-50 dark:bg-gray-900/50 p-2 rounded border border-gray-100 dark:border-gray-800/50 overflow-hidden">
                        <pre class="whitespace-pre-wrap font-mono text-[10px] leading-relaxed text-gray-600 dark:text-gray-400 break-all">{{ JSON.stringify(tooltip.node.properties, null, 2) }}</pre>
                     </div>
                </div>
            </div>
            
            <!-- Tooltip Arrow -->
            <div class="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-full w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[6px] border-t-white dark:border-t-gray-800 drop-shadow-sm"></div>
        </div>

        <!-- Controls Overlay -->
        <div class="absolute bottom-4 right-4 flex gap-2 opacity-50 group-hover:opacity-100 transition-opacity z-10">
            <button @click="resetView" class="p-2 bg-white dark:bg-gray-800 rounded-md shadow-md hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 border dark:border-gray-700 transition-colors" title="Fit to View">
                <IconMaximize class="w-5 h-5"/>
            </button>
            <button @click="togglePhysics" class="p-2 bg-white dark:bg-gray-800 rounded-md shadow-md hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 border dark:border-gray-700 transition-colors" :title="physicsEnabled ? 'Freeze Layout' : 'Enable Physics'">
                <IconPause v-if="physicsEnabled" class="w-5 h-5"/>
                <IconPlay v-else class="w-5 h-5"/>
            </button>
        </div>

        <!-- Loading State -->
        <div v-if="isLoading" class="absolute inset-0 bg-gray-500/20 backdrop-blur-sm flex items-center justify-center z-20">
            <div class="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-2xl border dark:border-gray-700 flex flex-col items-center gap-3">
                <div class="animate-spin">
                    <IconAnimateSpin class="w-8 h-8 text-blue-500 dark:text-blue-400" />
                </div>
                <span class="text-sm font-semibold text-gray-700 dark:text-gray-200 animate-pulse">Processing Graph...</span>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { Network } from 'vis-network/esnext';
import { useUiStore } from '../../stores/ui';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconPause from '../../assets/icons/IconStopCircle.vue'; 
import IconPlay from '../../assets/icons/IconPlayCircle.vue';

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

const tooltip = ref({
    visible: false,
    x: 0,
    y: 0,
    node: null,
    color: ''
});

const typeColorMap = {
    'Person': '#FFD700',       
    'Organization': '#87CEEB', 
    'Location': '#90EE90',     
    'Date': '#FFA07A',         
    'Product': '#20B2AA',      
    'Event': '#FF69B4',        
    'Concept': '#9370DB',      
    'Technology': '#A9A9A9',   
    'default': '#D3D3D3'       
};

// Generate consistent HSL colors
function generateColor(str, isDark) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = Math.abs(hash) % 360;
    const s = 70; 
    const l = isDark ? 65 : 45; 
    return `hsl(${h}, ${s}%, ${l}%)`;
}

function getNodeColor(nodeType, isDark) {
    if (typeColorMap[nodeType]) return typeColorMap[nodeType];
    return generateColor(nodeType || 'default', isDark);
}

const getOptions = (theme) => {
    const isDark = theme === 'dark';
    const textColor = isDark ? '#E5E7EB' : '#374151';
    
    return {
        nodes: {
            shape: 'dot',
            size: 25,
            font: {
                size: 14,
                color: textColor,
                strokeWidth: 3, 
                strokeColor: isDark ? '#111827' : '#FFFFFF'
            },
            borderWidth: 2,
            shadow: {
                enabled: true,
                color: 'rgba(0,0,0,0.2)',
                size: 5,
                x: 2,
                y: 2
            }
        },
        edges: {
            width: 2,
            color: { 
                // Force a visible color
                color: isDark ? '#6B7280' : '#9CA3AF',
                highlight: '#3B82F6',
                hover: '#60A5FA',
                opacity: 0.9,
                inherit: false 
            },
            smooth: { 
                type: 'continuous',
                roundness: 0.5 
            },
            arrows: {
                to: { enabled: true, scaleFactor: 0.8 }
            },
            font: {
                align: 'middle',
                size: 11,
                color: isDark ? '#9CA3AF' : '#4B5563',
                strokeWidth: 2,
                strokeColor: isDark ? '#111827' : '#FFFFFF',
                background: 'transparent'
            },
            selectionWidth: 3
        },
        physics: {
            enabled: true,
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -30,
                centralGravity: 0.005,
                springLength: 200,
                springConstant: 0.1,
                damping: 0.4,
                avoidOverlap: 0.5
            },
            maxVelocity: 40,
            minVelocity: 0.5,
            stabilization: {
                enabled: true,
                iterations: 500, // Stabilize before showing
                updateInterval: 50,
                onlyDynamicEdges: false
            }
        },
        interaction: {
            hover: true,
            hoverConnectedEdges: true,
            tooltipDelay: 0, // Instant custom tooltip
            dragNodes: true,
            dragView: true,
            zoomView: true,
            selectable: true,
            selectConnectedEdges: true
        }
    };
};

function initializeOrUpdateGraph() {
    if (!networkContainer.value) return;

    const isDark = uiStore.currentTheme === 'dark';

    const data = {
        nodes: props.nodes.map(n => {
            const nodeType = n.label;
            const nodeLabel = String(n.properties?.identifying_value || n.properties?.name || n.properties?.label || n.label);
            const color = getNodeColor(nodeType, isDark);
            
            return {
                id: String(n.id),
                label: nodeLabel.length > 25 ? nodeLabel.substring(0, 24) + '...' : nodeLabel,
                // Remove standard title to prevent default tooltip
                title: undefined, 
                color: {
                    background: color,
                    border: color,
                    highlight: { background: color, border: isDark ? '#FFFFFF' : '#000000' },
                    hover: { background: color, border: isDark ? '#FFFFFF' : '#000000' }
                },
                group: nodeType,
                // Store raw data for custom tooltip access
                _raw: n 
            }
        }),
        edges: props.edges.map(e => ({ 
            id: e.id,
            from: String(e.source),
            to: String(e.target),
            label: e.label,
            properties: e.properties
        }))
    };
    
    const options = getOptions(uiStore.currentTheme);

    if (!network) {
        network = new Network(networkContainer.value, data, options);
        
        // --- Interactions ---

        // Click / Select
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

        // Hover Node - Show Custom Tooltip
        network.on('hoverNode', (params) => {
            const nodeId = params.node;
            // Get position in DOM coordinates
            const positions = network.getPositions([nodeId]);
            const canvasPos = positions[nodeId];
            if(!canvasPos) return;

            const domPos = network.canvasToDOM(canvasPos);
            
            const nodeData = props.nodes.find(n => String(n.id) === String(nodeId));
            const nodeType = nodeData?.label || 'default';
            
            if (nodeData) {
                tooltip.value = {
                    visible: true,
                    x: domPos.x,
                    y: domPos.y,
                    node: nodeData,
                    color: getNodeColor(nodeType, isDark)
                };
            }
        });

        // Blur Node - Hide Tooltip
        network.on('blurNode', () => {
            tooltip.value.visible = false;
        });

        // Drag start (hide tooltip)
        network.on('dragStart', () => {
             tooltip.value.visible = false;
        });
        
        // Zoom/Pan (update tooltip position or hide)
        network.on('zoom', () => tooltip.value.visible = false);
        network.on('dragEnd', () => tooltip.value.visible = false);

        // Cursor handling
        network.on("hoverNode", function () {
             networkContainer.value.style.cursor = "pointer";
        });
        network.on("blurNode", function () {
            networkContainer.value.style.cursor = "default";
        });

    } else {
        network.setOptions(options);
        network.setData(data);
    }
}

watch(() => [props.nodes, props.edges], () => {
    nextTick(() => {
        initializeOrUpdateGraph();
    });
}, { deep: true });

watch(() => uiStore.currentTheme, (newTheme) => {
    if (network) {
        const options = getOptions(newTheme);
        network.setOptions(options);
        // We need to re-process data to update colors in the dataset
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

defineExpose({ resetView });

</script>

<style scoped>
/* Ensure the container handles z-indexing correctly */
:deep(.vis-network) {
    outline: none;
}
</style>
