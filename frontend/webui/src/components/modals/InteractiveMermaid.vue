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

function getShape(type) {
    switch (type?.toLowerCase()) {
        case 'stadium': return 'round-rectangle';
        case 'circle': return 'ellipse';
        case 'rhombus': return 'diamond';
        case 'hexagon': return 'hexagon';
        case 'ellipse': return 'ellipse';
        case 'roundrect':
        case 'round-rectangle': return 'round-rectangle';
        default: return 'rectangle';
    }
}

function parseShapeAndColor(node) {
    let shape = getShape(node.type);
    let color = uiStore.currentTheme === 'dark' ? '#374151' : '#F3F4F6';
    let textColor = uiStore.currentTheme === 'dark' ? '#F9FAFB' : '#111827';

    if (node.styles && node.styles.length) {
        node.styles.forEach(styleStr => {
            if (styleStr.includes('fill:')) {
                const match = styleStr.match(/fill:\s*([^;]+)/);
                if (match) color = match[1].trim();
            }
            if (styleStr.includes('color:')) {
                const match = styleStr.match(/color:\s*([^;]+)/);
                if (match) textColor = match[1].trim();
            }
            if (styleStr.includes('shape:')) {
                const match = styleStr.match(/shape:\s*([^;]+)/);
                if (match) shape = getShape(match[1].trim());
            }
        });
    }
    return { shape, color, textColor };
}

function transformMermaidToCytoscape(diagram) {
    const elements = [];

    // Flowchart / Graph (Mermaid >= 10.x)
    if (typeof diagram.getNodes === 'function' && typeof diagram.getLinks === 'function') {
        const nodes = diagram.getNodes();
        const links = diagram.getLinks();
        nodes.forEach(node => {
            const { shape, color, textColor } = parseShapeAndColor(node);
            elements.push({
                group: 'nodes',
                data: {
                    id: node.id,
                    label: (node.text || '').replace(/<br\s*\/?>/gi, '\n').replace(/\\n/g, '\n'),
                    shape,
                    backgroundColor: color,
                    textColor
                }
            });
        });
        links.forEach((link, index) => {
            elements.push({
                group: 'edges',
                data: {
                    id: `e${index}`,
                    source: link.source,
                    target: link.target,
                    label: link.text || '',
                    color: link.style?.includes('stroke:')
                        ? link.style.match(/stroke:\s*([^;]+)/)?.[1].trim()
                        : '#9CA3AF'
                }
            });
        });
        return elements;
    }

    // Flowchart / Graph (Mermaid <= 9.x)
    if (diagram.db?.getVertices && diagram.db?.getEdges) {
        const vertices = diagram.db.getVertices();
        const edges = diagram.db.getEdges();
        for (const id in vertices) {
            const vertex = vertices[id];
            const { shape, color, textColor } = parseShapeAndColor(vertex);
            elements.push({
                group: 'nodes',
                data: {
                    id: vertex.id,
                    label: (vertex.text || '').replace(/<br\s*\/?>/gi, '\n').replace(/\\n/g, '\n'),
                    shape,
                    backgroundColor: color,
                    textColor
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
                    label: edge.text || '',
                    color: edge.style?.includes('stroke:')
                        ? edge.style.match(/stroke:\s*([^;]+)/)?.[1].trim()
                        : '#9CA3AF'
                }
            });
        });
        return elements;
    }

    // Class Diagram
    if (diagram.db?.getClasses && diagram.db?.getRelations) {
        const classes = diagram.db.getClasses();
        const relations = diagram.db.getRelations();
        Object.keys(classes).forEach(classId => {
            const cls = classes[classId];
            elements.push({
                group: 'nodes',
                data: {
                    id: classId,
                    label: cls.id || classId,
                    shape: 'round-rectangle',
                    backgroundColor: uiStore.currentTheme === 'dark' ? '#1E3A8A' : '#BFDBFE',
                    textColor: uiStore.currentTheme === 'dark' ? '#F9FAFB' : '#111827'
                }
            });
        });
        relations.forEach((rel, i) => {
            elements.push({
                group: 'edges',
                data: {
                    id: `classRel${i}`,
                    source: rel.id1,
                    target: rel.id2,
                    label: rel.relation?.type || '',
                    color: '#9CA3AF'
                }
            });
        });
        return elements;
    }

    // Sequence Diagram
    if (diagram.db?.actors && diagram.db?.messages) {
        Object.keys(diagram.db.actors).forEach(actorId => {
            elements.push({
                group: 'nodes',
                data: {
                    id: actorId,
                    label: diagram.db.actors[actorId].description || actorId,
                    shape: 'rectangle',
                    backgroundColor: uiStore.currentTheme === 'dark' ? '#047857' : '#A7F3D0',
                    textColor: uiStore.currentTheme === 'dark' ? '#F9FAFB' : '#111827'
                }
            });
        });
        diagram.db.messages.forEach((msg, i) => {
            elements.push({
                group: 'edges',
                data: {
                    id: `seq${i}`,
                    source: msg.from,
                    target: msg.to,
                    label: msg.message || '',
                    color: '#9CA3AF'
                }
            });
        });
        return elements;
    }

    // State Diagram
    if (diagram.db?.states && diagram.db?.transitions) {
        Object.keys(diagram.db.states).forEach(stateId => {
            elements.push({
                group: 'nodes',
                data: {
                    id: stateId,
                    label: stateId,
                    shape: 'round-rectangle',
                    backgroundColor: uiStore.currentTheme === 'dark' ? '#6B21A8' : '#E9D5FF',
                    textColor: uiStore.currentTheme === 'dark' ? '#F9FAFB' : '#111827'
                }
            });
        });
        diagram.db.transitions.forEach((t, i) => {
            elements.push({
                group: 'edges',
                data: {
                    id: `state${i}`,
                    source: t.from,
                    target: t.to,
                    label: t.label || '',
                    color: '#9CA3AF'
                }
            });
        });
        return elements;
    }

    // Fallback: Show one node saying "Unsupported diagram type"
    elements.push({
        group: 'nodes',
        data: {
            id: 'unsupported',
            label: 'Unsupported Mermaid diagram type',
            shape: 'rectangle',
            backgroundColor: '#F87171',
            textColor: '#FFFFFF'
        }
    });
    return elements;
}

async function updateGraph() {
    errorMessage.value = '';
    if (!cy) return;
    try {
        let diagram;
        if (typeof mermaid.getDiagramFromText === 'function') {
            diagram = await mermaid.getDiagramFromText(props.mermaidCode);
        } else if (mermaid.mermaidAPI?.getDiagramFromText) {
            console.warn("Using fallback mermaid.mermaidAPI.getDiagramFromText. Please update Mermaid.");
            diagram = await mermaid.mermaidAPI.getDiagramFromText(props.mermaidCode);
        } else {
            throw new Error("No compatible Mermaid parser found.");
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
    mermaid.initialize({ startOnLoad: false });
    cy = cytoscape({
        container: cyRef.value,
        style: [
            {
                selector: 'node',
                style: {
                    'background-color': 'data(backgroundColor)',
                    'border-color': uiStore.currentTheme === 'dark' ? '#9CA3AF' : '#6B7280',
                    'border-width': 1,
                    'label': 'data(label)',
                    'text-wrap': 'wrap',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'shape': 'data(shape)',
                    'color': 'data(textColor)',
                    'font-size': '14px',
                    'padding': '15px',
                    'width': 'label',
                    'height': 'label'
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': 2,
                    'line-color': 'data(color)',
                    'target-arrow-color': 'data(color)',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier',
                    'label': 'data(label)',
                    'font-size': '12px',
                    'color': uiStore.currentTheme === 'dark' ? '#D1D5DB' : '#374151',
                    'text-background-color': uiStore.currentTheme === 'dark' ? '#1F2937' : '#FFFFFF',
                    'text-background-opacity': 1,
                    'text-background-padding': '3px',
                    'text-background-shape': 'round-rectangle'
                }
            }
        ],
        layout: { name: 'grid' }
    });
    updateGraph();
});

onUnmounted(() => {
    if (cy) cy.destroy();
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
