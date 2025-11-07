<template>
    <div class="w-full h-full relative border dark:border-gray-700 rounded-lg overflow-hidden">
        <div ref="networkContainer" class="w-full h-full"></div>
        <div v-if="isLoading" class="absolute inset-0 bg-gray-500/30 flex items-center justify-center">
            <IconAnimateSpin class="w-10 h-10 text-white" />
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { Network } from 'vis-network/esnext';
import { useUiStore } from '../../stores/ui';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';

const props = defineProps({
    nodes: { type: Array, default: () => [] },
    edges: { type: Array, default: () => [] },
    isLoading: { type: Boolean, default: false }
});

const emit = defineEmits(['node-select', 'edge-select', 'deselect']);

const uiStore = useUiStore();
const networkContainer = ref(null);
let network = null;

const typeColorMap = {
    'Person': '#FFD700',       // Gold
    'Organization': '#87CEEB', // SkyBlue
    'Location': '#90EE90',     // LightGreen
    'Date': '#FFA07A',         // LightSalmon
    'Product': '#20B2AA',      // LightSeaGreen
    'Event': '#FF69B4',        // HotPink
    'default': '#D3D3D3'       // LightGray
};

function getNodeColor(nodeType) {
    return typeColorMap[nodeType] || typeColorMap['default'];
}

const getOptions = (theme) => {
    const isDark = theme === 'dark';
    return {
        nodes: {
            shape: 'dot',
            size: 20,
            font: {
                size: 14,
                color: isDark ? '#FFFFFF' : '#000000'
            },
            borderWidth: 2,
        },
        edges: {
            width: 1.5,
            color: { 
                color: isDark ? '#6B7280' : '#9CA3AF', // Static gray colors for visibility
                highlight: '#3B82F6',
                hover: '#60A5FA',
            },
            smooth: { type: 'continuous' },
            arrows: {
                to: { enabled: true, scaleFactor: 0.8 }
            },
            font: {
                align: 'middle',
                size: 12,
                color: isDark ? '#E2E8F0' : '#1F2937',
                strokeWidth: 2,
                strokeColor: isDark ? 'rgba(17, 24, 39, 0.7)' : 'rgba(255,255,255,0.7)'
            }
        },
        physics: {
            enabled: true,
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -50,
                centralGravity: 0.01,
                springLength: 150,
                springConstant: 0.08,
                avoidOverlap: 0.5
            },
            maxVelocity: 50,
            minVelocity: 0.1,
            stabilization: {
                enabled: true,
                iterations: 200,
                fit: true
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 300,
            dragNodes: true,
            dragView: true,
            zoomView: true
        },
        layout: {
            improvedLayout: true
        }
    };
};

function initializeOrUpdateGraph() {
    if (!networkContainer.value) return;

    const data = {
        nodes: props.nodes.map(n => {
            const nodeType = n.label;
            const nodeLabel = String(n.properties?.identifying_value || n.properties?.name || n.properties?.label || n.label);
            const color = getNodeColor(nodeType);
            
            return {
                id: n.id,
                label: nodeLabel,
                title: `Type: ${nodeType}\nID: ${n.id}\nProperties: ${JSON.stringify(n.properties, null, 2)}`,
                color: {
                    background: color,
                    border: color,
                    highlight: { background: color, border: '#2B7CE9' },
                    hover: { background: color, border: '#2B7CE9' }
                },
                group: nodeType
            }
        }),
        edges: props.edges.map(e => ({ 
            id: e.id,
            from: e.source, 
            to: e.target, 
            label: e.label,
            properties: e.properties
        }))
    };
    
    const options = getOptions(uiStore.currentTheme);

    if (!network) {
        network = new Network(networkContainer.value, data, options);
        network.on('selectNode', (params) => {
            if (params.nodes.length > 0) {
                const node = props.nodes.find(n => n.id === params.nodes[0]);
                emit('node-select', node);
            }
        });
        network.on('selectEdge', (params) => {
            if (params.edges.length > 0) {
                const edgeId = params.edges[0];
                const edge = props.edges.find(e => e.id === edgeId);
                if (edge) {
                    emit('edge-select', edge);
                }
            }
        });
        network.on('deselectNode', () => emit('deselect'));
        network.on('deselectEdge', () => emit('deselect'));
    } else {
        network.setOptions(options);
        network.setData(data);
    }
    network.fit();
}

watch(() => [props.nodes, props.edges], () => {
    nextTick(() => {
        initializeOrUpdateGraph();
    });
}, { deep: true });

watch(() => uiStore.currentTheme, (newTheme) => {
    if (network) {
        network.setOptions(getOptions(newTheme));
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
    network.fit();
  }
}

defineExpose({ resetView });

</script>