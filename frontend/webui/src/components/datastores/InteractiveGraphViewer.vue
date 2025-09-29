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

const options = {
    nodes: {
        shape: 'dot',
        size: 16,
        font: { color: '#fff' }
    },
    edges: {
        width: 2,
        color: { inherit: 'from' },
        smooth: { type: 'continuous' }
    },
    physics: {
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: {
            gravitationalConstant: -26,
            centralGravity: 0.005,
            springLength: 230,
            springConstant: 0.18
        },
        maxVelocity: 146,
        minVelocity: 0.1,
        stabilization: {
            enabled: true,
            iterations: 200,
            fit: true
        }
    },
    interaction: {
        hover: true,
        tooltipDelay: 300
    },
    layout: {
        improvedLayout: true
    }
};

function initializeOrUpdateGraph() {
    if (!networkContainer.value) return;

    const data = {
        nodes: props.nodes.map(n => ({ id: n.id, label: n.label, title: JSON.stringify(n.properties, null, 2) })),
        edges: props.edges.map(e => ({ from: e.source, to: e.target, label: e.label, arrows: 'to' }))
    };

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
                const edge = props.edges.find(e => e.id === params.edges[0]);
                 emit('edge-select', edge);
            }
        });
        network.on('deselectNode', () => emit('deselect'));
        network.on('deselectEdge', () => emit('deselect'));
    } else {
        network.setData(data);
    }
    network.fit();
}

watch(() => [props.nodes, props.edges], () => {
    nextTick(() => {
        initializeOrUpdateGraph();
    });
}, { deep: true });

onMounted(() => {
    initializeOrUpdateGraph();
});

onUnmounted(() => {
    if (network) {
        network.destroy();
        network = null;
    }
});
</script>