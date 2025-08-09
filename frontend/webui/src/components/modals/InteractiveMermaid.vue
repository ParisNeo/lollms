<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import mermaid from 'mermaid';
import { useUiStore } from '../../stores/ui';

const props = defineProps({
    mermaidCode: {
        type: String,
        required: true
    }
});

const emit = defineEmits(['error', 'ready']);

const cyRef = ref(null);
const errorMessage = ref('');
let cy = null;

const uiStore = useUiStore();

cytoscape.use(dagre);

function transformMermaidToCytoscape(diagram) {
    const elements = [];
    
    if (!diagram || !diagram.db) {
        throw new Error('Could not find diagram database in parsed Mermaid data. The data structure might be invalid or from an unsupported version.');
    }

    const vertices = diagram.db.getVertices();
    const edges = diagram.db.getEdges();

    for (const id in vertices) {
        const vertex = vertices[id];
        const labelText = (vertex.text || '')
            .replace(/<br\s*\/?>/gi, '\n')
            .replace(/\\n/g, '\n');

        elements.push({
            group: 'nodes',
            data: {
                id: vertex.id,
                label: labelText,
                shape: getShape(vertex.type)
            }
        });
    }

    edges.forEach((edge, index) => {
        elements.push({
            group: 'edges',
            data: {
                id: `e${index}`,
                source: edge.start,
                target: edge.end,
                label: edge.text || ''
            }
        });
    });

    return elements;
}

function getShape(type) {
    switch(type) {
        case 'stadium': return 'round-rectangle';
        case 'circle': return 'ellipse';
        case 'rhombus': return 'diamond';
        default: return 'rectangle';
    }
}

async function updateGraph() {
    errorMessage.value = '';
    if (!cy) return;

    try {
        let diagram;
        if (typeof mermaid.getDiagramFromText === 'function') {
            diagram = await mermaid.getDiagramFromText(props.mermaidCode);
        } else if (mermaid.mermaidAPI && typeof mermaid.mermaidAPI.getDiagramFromText === 'function') {
            console.warn("Using fallback mermaid.mermaidAPI.getDiagramFromText. Your dependencies may be out of date. Please run 'npm install'.");
            diagram = await mermaid.mermaidAPI.getDiagramFromText(props.mermaidCode);
        } else {
            throw new Error("Compatible Mermaid parsing function not found. Your Mermaid.js version is too old or improperly installed. Please clear node_modules and reinstall.");
        }
        
        const elements = transformMermaidToCytoscape(diagram);

        cy.json({ elements });
        cy.layout({
            name: 'dagre',
            padding: 30,
            spacingFactor: 1.25,
            rankDir: 'TB',
        }).run();
        emit('ready', cy);
    } catch (error) {
        console.error("Mermaid parsing error:", error);
        errorMessage.value = error.message || 'Failed to parse Mermaid diagram.';
        emit('error', errorMessage.value);
    }
}

// NEW: Export function
function exportPNG(filename = 'diagram.png', bgColor = '#FFFFFF') {
    if (!cy) return;
    const pngContent = cy.png({ output: 'base64', bg: bgColor, full: true, scale: 2 });
    const a = document.createElement('a');
    a.href = `data:image/png;base64,${pngContent}`;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

onMounted(() => {
    console.log("DEBUG: Loaded mermaid object:", mermaid);
    if (typeof mermaid.version === 'function') {
        console.log("DEBUG: Mermaid version found:", mermaid.version());
    } else {
        console.log("DEBUG: mermaid.version() function not found, indicating a very old version.");
    }

    mermaid.initialize({ startOnLoad: false });
    
    cy = cytoscape({
        container: cyRef.value,
        style: [
            {
                selector: 'node',
                style: {
                    'background-color': uiStore.currentTheme === 'dark' ? '#374151' : '#F3F4F6',
                    'border-color': uiStore.currentTheme === 'dark' ? '#9CA3AF' : '#6B7280',
                    'border-width': 1,
                    'label': 'data(label)',
                    'text-wrap': 'wrap',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'shape': 'data(shape)',
                    'color': uiStore.currentTheme === 'dark' ? '#F9FAFB' : '#111827',
                    'font-size': '14px',
                    'padding': '15px',
                    'width': 'label',
                    'height': 'label',
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': 2,
                    'line-color': '#9CA3AF',
                    'target-arrow-color': '#9CA3AF',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier',
                    'label': 'data(label)',
                    'font-size': '12px',
                    'color': uiStore.currentTheme === 'dark' ? '#D1D5DB' : '#374151',
                    'text-background-color': uiStore.currentTheme === 'dark' ? '#1F2937' : '#FFFFFF',
                    'text-background-opacity': 1,
                    'text-background-padding': '3px',
                    'text-background-shape': 'round-rectangle',
                }
            }
        ],
        layout: { name: 'grid' }
    });
    updateGraph();
});

onUnmounted(() => {
    if (cy) {
        cy.destroy();
    }
});

watch(() => props.mermaidCode, updateGraph);

defineExpose({ cy, exportPNG });
</script>

<template>
    <div class="w-full h-full relative">
        <div ref="cyRef" class="w-full h-full"></div>
        <div v-if="errorMessage" class="absolute inset-0 bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-200 p-4 rounded-md overflow-y-auto">
            <h4 class="font-bold mb-2">Mermaid Parsing Error</h4>
            <pre class="whitespace-pre-wrap font-mono text-sm">{{ errorMessage }}</pre>
        </div>
    </div>
</template>