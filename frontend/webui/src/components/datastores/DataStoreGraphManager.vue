<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, defineAsyncComponent, nextTick } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { useTasksStore } from '../../stores/tasks';
import { storeToRefs } from 'pinia';
import apiClient from '../../services/api';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
import JsonRenderer from '../ui/JsonRenderer.vue';
import MessageContentRenderer from '../ui/MessageContentRenderer/MessageContentRenderer.vue';

// Icon imports
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconArrowUpTray from '../../assets/icons/IconArrowUpTray.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconSave from '../../assets/icons/IconSave.vue';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconPlay from '../../assets/icons/IconPlayCircle.vue';

// Async import for Interactive Graph Viewer
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

const isComponentMounted = ref(true);
const viewMode = ref('graph'); // 'graph' or 'ontology'

// --- Graph Visualization State ---
const graphViewer = ref(null);
const graphStats = ref({ nodes: 0, edges: 0 });
const graphData = ref({ nodes: [], edges: [] });
const isLoadingGraph = ref(false);

// --- Ontology Designer State ---
const cyContainer = ref(null);
let cyInstance = null;
const baseIRI = ref('http://example.org/onto#');
const ontoIRI = ref('http://example.org/onto');
const ontoLabel = ref('Untitled');
const curCT = ref('turtle'); // turtle, jsonld, skos, manchester, rdfxml, sparql
const curIT = ref('d'); // details, style, annotations, ai
const selEl = ref(null);
const selectedNodeData = ref(null);
const selectedEdgeData = ref(null);
const hideOrphans = ref(false);
const highlightConnectionsMode = ref(false);
const showCodeDrawer = ref(false);

const sparqlQueryInput = ref('');
const sparqlResults = ref(null);

// Interactive connection state
const relationTargetId = ref(null);
const relationType = ref('relation');
const owlFileInputRef = ref(null);

const sparqlQueryMode = ref('SELECT'); // 'SELECT', 'CONSTRUCT', 'DESCRIBE'
const isFilterActive = ref(false);
const ontologyElements = ref([]); // Caches the TBox Schema elements on-the-fly

const ontologyClasses = computed(() => {
    // If we are currently in ontology mode, read directly from the canvas
    if (cyInstance && viewMode.value === 'ontology') {
        return cyInstance.nodes()
            .filter(n => n.data('type') === 'class')
            .map(n => n.data('label'));
    }
    // If not, read from the cached elements array
    return ontologyElements.value
        .filter(el => el.group === 'nodes' && el.data?.type === 'class')
        .map(el => el.data.label);
});

function addIndividualOfClass(className) {
    if (!cyInstance) return;
    
    const timestamp = Date.now().toString().slice(-4);
    const instanceName = `${className}_${timestamp}`;
    
    // Resolve matching display color based on class name
    const color = getNodeColor(className, uiStore.currentTheme === 'dark');
    const dims = nodeDims(instanceName, 'individual');
    const id = `individual__${instanceName}__${Date.now()}`;
    
    const node = cyInstance.add({
        group: 'nodes',
        data: {
            id, 
            label: instanceName, 
            type: 'individual',
            shape: 'ellipse',
            fill: color + '15', // translucent fill matching the schema class color
            stroke: color,
            textColor: uiStore.currentTheme === 'dark' ? '#e2e5f0' : '#111318',
            iri: baseIRI.value + instanceName,
            annotations: { "rdf:type": className },
            ...dims
        },
        position: { x: 200 + Math.random() * 200, y: 200 + Math.random() * 200 }
    });
    
    cyInstance.animate({ center: { eles: node } }, { duration: 300 });
    uiStore.addNotification(`Created individual of type ${className}: ${instanceName}`, 'success');
}

const otherNodesList = computed(() => {
    if (!cyInstance || !selectedNodeData.value) return [];
    return cyInstance.nodes().toArray()
        .filter(n => n.id() !== selectedNodeData.value.id)
        .map(n => ({ id: n.id(), label: n.data('label'), type: n.data('type') }));
});

function drawManualRelation() {
    if (!selectedNodeData.value || !relationTargetId.value) return;
    addEdgeDirect(relationType.value, selectedNodeData.value.id, relationTargetId.value);
    relationTargetId.value = null; // Reset selection
    uiStore.addNotification("Relation link drawn successfully.", "success");
}

function triggerOWLImport() {
    owlFileInputRef.value?.click();
}

async function handleOWLImport(event) {
    const file = event.target.files[0];
    if (!file || !cyInstance) return;

    try {
        const text = await file.text();
        const ext = file.name.split('.').pop().toLowerCase();

        // Clear existing canvas elements
        cyInstance.elements().remove();

        if (ext === 'ttl' || ext === 'owl' || ext === 'txt') {
            parseAndLoadTurtle(text);
        } else {
            // Fallback: parse as generic XML/RDF
            parseAndLoadRDFXML(text);
        }

        runCoseLayout();
        uiStore.addNotification(`Ontology file '${file.name}' loaded successfully!`, 'success');
    } catch (e) {
        console.error(e);
        uiStore.addNotification("Failed to parse the ontology file.", "error");
    } finally {
        event.target.value = '';
    }
}

function parseAndLoadTurtle(text) {
    const lines = text.split('\n');
    const prefixes = {};

    // Default base IRI
    let base = baseIRI.value;

    // Parse prefixes and base
    lines.forEach(line => {
        const cleanLine = line.trim();
        if (cleanLine.toLowerCase().startsWith('@prefix') || cleanLine.toLowerCase().startsWith('prefix')) {
            const match = cleanLine.match(/(?:@prefix|prefix)\s+(\w*):?\s*<([^>]+)>/i);
            if (match) {
                const prefix = match[1] || '';
                const uri = match[2];
                prefixes[prefix] = uri;
                if (prefix === '') base = uri;
            }
        }
    });

    baseIRI.value = base;

    // Helper to resolve prefixed values to full IRIs and local names
    function resolveNode(val) {
        if (!val) return null;
        let clean = val.trim();
        if (clean.startsWith('<') && clean.endsWith('>')) {
            const uri = clean.slice(1, -1);
            const name = uri.split(/[#/]/).pop();
            return { uri, name };
        }
        if (clean.includes(':')) {
            const [prefix, name] = clean.split(':', 2);
            const ns = prefixes[prefix] || base;
            return { uri: ns + name, name };
        }
        return { uri: base + clean, name: clean };
    }

    // Process triples
    let currentSubject = null;

    lines.forEach(line => {
        let cleanLine = line.trim();
        if (!cleanLine || cleanLine.startsWith('#') || cleanLine.startsWith('@prefix') || cleanLine.startsWith('prefix')) return;

        // Remove trailing dot if it's the end of a statement
        const isEnd = cleanLine.endsWith('.');
        if (isEnd) cleanLine = cleanLine.slice(0, -1).trim();

        const semicolonSplit = cleanLine.split(';');
        semicolonSplit.forEach((part, partIdx) => {
            const segment = part.trim();
            if (!segment) return;

            const words = segment.match(/(?:[^\s"]+|"[^"]*")+/g);
            if (!words) return;

            let s, p, o;
            if (partIdx === 0 && words.length >= 3) {
                s = resolveNode(words[0]);
                p = words[1];
                o = words[2];
                currentSubject = s;
            } else if (currentSubject && words.length >= 2) {
                s = currentSubject;
                p = words[0];
                o = words[1];
            } else {
                return;
            }

            if (!s || !p || !o) return;

            const pClean = p.toLowerCase();
            const oRes = resolveNode(o);

            // Ensure subject node is created
            let sNode = cyInstance.getElementById(`class__${s.name}`) || cyInstance.getElementById(`property__${s.name}`) || cyInstance.getElementById(`individual__${s.name}`);
            if (sNode.length === 0) {
                // Default to class, will refine if we see rdf:type individual or property
                addNodeDirect('class', s.name);
                sNode = cyInstance.nodes().filter(n => n.data('label') === s.name);
            }

            if (pClean === 'a' || pClean === 'rdf:type') {
                const oType = oRes.name.toLowerCase();
                if (oType === 'class') {
                    sNode.data('type', 'class');
                } else if (oType === 'objectproperty') {
                    sNode.data('type', 'property');
                } else if (oType === 'datatypeproperty') {
                    sNode.data('type', 'dataprop');
                } else if (oType === 'namedindividual') {
                    sNode.data('type', 'individual');
                } else if (oType === 'concept') {
                    sNode.data('type', 'concept');
                } else {
                    // It's an individual of some class
                    sNode.data('type', 'individual');
                    const targetClassNode = cyInstance.nodes().filter(n => n.data('label') === oRes.name);
                    if (targetClassNode.length > 0) {
                        addEdgeDirect('type', sNode.id(), targetClassNode.id());
                    }
                }
            } else if (pClean === 'rdfs:subclassof') {
                let targetNode = cyInstance.nodes().filter(n => n.data('label') === oRes.name);
                if (targetNode.length === 0) {
                    addNodeDirect('class', oRes.name);
                    targetNode = cyInstance.nodes().filter(n => n.data('label') === oRes.name);
                }
                addEdgeDirect('subClassOf', sNode.id(), targetNode.id());
            } else if (pClean === 'rdfs:subpropertyof') {
                let targetNode = cyInstance.nodes().filter(n => n.data('label') === oRes.name);
                if (targetNode.length === 0) {
                    addNodeDirect('property', oRes.name);
                    targetNode = cyInstance.nodes().filter(n => n.data('label') === oRes.name);
                }
                addEdgeDirect('subPropertyOf', sNode.id(), targetNode.id());
            } else if (pClean === 'rdfs:domain') {
                let targetNode = cyInstance.nodes().filter(n => n.data('label') === oRes.name);
                if (targetNode.length === 0) {
                    addNodeDirect('class', oRes.name);
                    targetNode = cyInstance.nodes().filter(n => n.data('label') === oRes.name);
                }
                addEdgeDirect('domain', sNode.id(), targetNode.id());
            } else if (pClean === 'rdfs:range') {
                let targetNode = cyInstance.nodes().filter(n => n.data('label') === oRes.name);
                if (targetNode.length === 0) {
                    addNodeDirect('class', oRes.name);
                    targetNode = cyInstance.nodes().filter(n => n.data('label') === oRes.name);
                }
                addEdgeDirect('range', sNode.id(), targetNode.id());
            } else if (pClean === 'rdfs:label') {
                sNode.data('rdfsLabel', o.replace(/"/g, ''));
            } else if (pClean === 'rdfs:comment') {
                sNode.data('comment', o.replace(/"/g, ''));
            }
        });
    });
}

function parseAndLoadRDFXML(text) {
    try {
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(text, "text/xml");

        // Simple XML parser looking for Class, ObjectProperty, DatatypeProperty tags
        const classes = xmlDoc.getElementsByTagName("owl:Class");
        for (let i = 0; i < classes.length; i++) {
            const el = classes[i];
            const about = el.getAttribute("rdf:about") || el.getAttribute("rdf:ID") || '';
            const name = about.split(/[#/]/).pop();
            if (name) {
                addNodeDirect('class', name);
                const node = cyInstance.nodes().filter(n => n.data('label') === name);

                const labelEl = el.getElementsByTagName("rdfs:label")[0];
                if (labelEl) node.data('rdfsLabel', labelEl.textContent);

                const commentEl = el.getElementsByTagName("rdfs:comment")[0];
                if (commentEl) node.data('comment', commentEl.textContent);

                const subClassEl = el.getElementsByTagName("rdfs:subClassOf")[0];
                if (subClassEl) {
                    const resource = subClassEl.getAttribute("rdf:resource");
                    if (resource) {
                        const parentName = resource.split(/[#/]/).pop();
                        if (parentName) {
                            let parentNode = cyInstance.nodes().filter(n => n.data('label') === parentName);
                            if (parentNode.length === 0) {
                                addNodeDirect('class', parentName);
                                parentNode = cyInstance.nodes().filter(n => n.data('label') === parentName);
                            }
                            addEdgeDirect('subClassOf', node.id(), parentNode.id());
                        }
                    }
                }
            }
        }
    } catch (e) {
        console.error("RDF/XML Parsing failed:", e);
        throw e;
    }
}

// AI Assistant
const aiPrompt = ref('');
const isAIGenerating = ref(false);

const selectedFullModel = ref('');
const generationParams = ref({
    model_binding: '',
    model_name: '',
    chunk_size: 2048,
    overlap_size: 256,
    ontology: ''
});

// Per-type visual config
const typeStyles = ref({
  class:      { shape:'ellipse',         fill:'#1a1730', stroke:'#7c6ff7', textColor:'#b3abfa', size:110 },
  property:   { shape:'round-rectangle', fill:'#0e2424', stroke:'#2dd4bf', textColor:'#7de8df', size:130 },
  dataprop:   { shape:'round-rectangle', fill:'#241d0a', stroke:'#fbbf24', textColor:'#fcd34d', size:130 },
  individual: { shape:'ellipse',         fill:'#0e2318', stroke:'#4ade80', textColor:'#86efac', size:110 },
  concept:    { shape:'hexagon',         fill:'#240e1c', stroke:'#f472b6', textColor:'#f9a8d4', size:120 },
});

const EDGE_COLORS = {
  subClassOf:'#7c6ff7', equivalentClass:'#e879f9', disjointWith:'#f87171',
  subPropertyOf:'#2dd4bf', domain:'#fbbf24', range:'#fb923c',
  type:'#4ade80', relation:'#7c8494', broader:'#f472b6', narrower:'#f472b6',
};

const SHAPES = [
  {id:'ellipse',label:'Ellipse'},
  {id:'round-rectangle',label:'Rect'},
  {id:'rectangle',label:'Sharp Rect'},
  {id:'diamond',label:'Diamond'},
  {id:'hexagon',label:'Hexagon'},
  {id:'pentagon',label:'Pentagon'},
  {id:'triangle',label:'Triangle'},
  {id:'barrel',label:'Barrel'},
];

const PALETTE = [
  {c:'#7c6ff7',bg:'#1a1730'},{c:'#2dd4bf',bg:'#0e2424'},{c:'#4ade80',bg:'#0e2318'},
  {c:'#fbbf24',bg:'#241d0a'},{c:'#f87171',bg:'#240e0e'},{c:'#f472b6',bg:'#240e1c'},
  {c:'#38bdf8',bg:'#0c1e2a'},{c:'#fb923c',bg:'#221408'},{c:'#a3e635',bg:'#121e0a'},
  {c:'#e879f9',bg:'#21092a'},{c:'#94a3b8',bg:'#161b22'},{c:'#fde68a',bg:'#221e0a'},
];

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

function nodeDims(label, type){
  const cfg = typeStyles.value[type] || typeStyles.value.class;
  const baseSize = cfg.size;
  const chars = (label||'').length;
  const minW = baseSize;
  const perChar = 7.5;
  const labW = chars * perChar + 28;
  const w = Math.max(minW, labW);
  const wrapCols = Math.floor(w / 8);
  const lines = Math.ceil(chars / Math.max(wrapCols, 1));
  const h = Math.max(cfg.shape === 'ellipse' ? 48 : 40, lines * 18 + 16);
  const tw = w - 16;
  const fs = chars > 18 ? 11 : 12;
  return { w: Math.round(w), h: Math.round(h), tw: Math.round(tw), fs };
}

function buildCyStyle(){
  const isDark = uiStore.currentTheme === 'dark';
  const labelColor = isDark ? '#e2e5f0' : '#111318';
  
  return [
    { selector:'node', style:{
        'shape':'data(shape)',
        'width':'data(w)',
        'height':'data(h)',
        'background-color':'data(fill)',
        'border-color':'data(stroke)',
        'border-width':1.5,
        'label':'data(label)',
        'color': 'data(textColor)',
        'font-family':'"DM Sans",sans-serif',
        'font-size':'data(fs)',
        'font-weight':500,
        'text-valign':'center',
        'text-halign':'center',
        'text-wrap':'wrap',
        'text-max-width':'data(tw)',
        'text-overflow-wrap':'anywhere',
        'min-zoomed-font-size':6,
        'transition-property': 'background-color, border-color, opacity',
        'transition-duration': '0.18s'
    }},
    { selector:'node:selected', style:{
        'border-width':2.5,
        'border-color':'#ffffff',
        'overlay-opacity':0.06,
    }},
    { selector:'edge', style:{
        'width':1.5,
        'line-color':'data(ec)',
        'target-arrow-color':'data(ec)',
        'target-arrow-shape':'triangle',
        'curve-style':'bezier',
        'label':'data(label)',
        'font-size':9,
        'color':'#5e6680',
        'text-background-color': isDark ? '#0b0d12' : '#ffffff',
        'text-background-opacity':1,
        'text-background-padding':'3px',
        'font-family':'"DM Sans",sans-serif',
        'edge-text-rotation':'autorotate',
        'min-zoomed-font-size':6,
    }},
    { selector:'edge[dashed]', style:{'line-style':'dashed','line-dash-pattern':[6,3]}},
    { selector:'edge:selected', style:{'line-color':'#ffffff','target-arrow-color':'#ffffff','overlay-opacity':0.08}},
    { selector:'.hidden-element', style:{'display':'none'}},
    { selector:'.orphan-hidden', style:{'display':'none'}},
    { selector:'node.dimmed', style:{'opacity':0.15, 'events':'no'}},
    { selector:'edge.dimmed', style:{'opacity':0.15, 'events':'no'}},
    { selector:'node.highlighted-node', style:{'border-width':3.5, 'border-color':'#ffffff'}},
    { selector:'edge.highlighted-edge', style:{'width':3, 'line-color':'#ffffff', 'target-arrow-color':'#ffffff'}},
  ];
}

async function initCytoscape() {
    if (!cyContainer.value) return;

    // Safety check: destroy previous instances to prevent rendering overlay conflicts
    if (cyInstance) {
        cyInstance.destroy();
        cyInstance = null;
    }

    const cyMod = await loadCytoscape();

    cyInstance = cyMod({
        container: cyContainer.value,
        style: buildCyStyle(),
        layout: { name: 'cose', padding: 30 },
        minZoom: 0.1,
        maxZoom: 5
    });

    cyInstance.on('select', 'node, edge', e => {
        selEl.value = e.target;
        if (selEl.value.isNode()) {
            selectedNodeData.value = selEl.value.data();
            selectedEdgeData.value = null;
            relationTargetId.value = null; // Reset relation target on node selection change
        } else {
            selectedEdgeData.value = selEl.value.data();
            selectedNodeData.value = null;
        }
        applyHighlighting();
    });

    cyInstance.on('unselect', 'node, edge', () => {
        if (cyInstance.$(':selected').length === 0) {
            selEl.value = null;
            selectedNodeData.value = null;
            selectedEdgeData.value = null;
        }
        applyHighlighting();
    });

    // --- TBox & ABox UNIFICATION: Ingest both schema and live document data onto the same canvas ---
    const isDark = uiStore.currentTheme === 'dark';

    // 1. Ingest Data Instances (ABox)
    if (props.nodes && props.nodes.length > 0) {
        props.nodes.forEach(n => {
            const type = 'individual';
            const label = n.properties?.identifying_value || n.properties?.name || n.properties?.label || n.label || n.id;
            const color = getNodeColor(n.label, isDark);
            const dims = nodeDims(label, type);

            cyInstance.add({
                group: 'nodes',
                data: {
                    id: String(n.id),
                    label: label,
                    type: type,
                    shape: 'ellipse',
                    fill: color + '20', // Translucent tinted fill for instances
                    stroke: color,
                    textColor: isDark ? '#e2e5f0' : '#111318',
                    iri: baseIRI.value + label,
                    annotations: n.properties || {},
                    ...dims
                }
            });
        });

        props.edges.forEach(e => {
            const source = e.source ?? e.source_id ?? e.from ?? e.start ?? e.start_node_id;
            const target = e.target ?? e.target_id ?? e.to ?? e.end ?? e.end_node_id;
            if (!source || !target) return;

            cyInstance.add({
                group: 'edges',
                data: {
                    id: e.id,
                    source: String(source),
                    target: String(target),
                    label: e.label || e.type || '',
                    relType: 'relation',
                    ec: '#7c8494'
                }
            });
        });
    }

    // 2. Populate default Initial Schema Node if canvas remains completely empty
    if (cyInstance.elements().length === 0) {
        addNodeDirect('class', 'Entity');
    }

    runCoseLayout();
    syncOntologyToParams();
}

function runCoseLayout() {
    if (!cyInstance || cyInstance.nodes().length === 0) return;
    cyInstance.layout({
        name: 'cose',
        animate: true,
        animationDuration: 400,
        padding: 40,
        nodeRepulsion: 45005,
        idealEdgeLength: 100,
    }).run();
}

// Node and Edge Manipulation
function addNodeDirect(type, name, parentId = null) {
  if (!cyInstance) return;
  const id = `${type}__${name.replace(/\W+/g,'_')}__${Date.now()}`;
  const cfg = typeStyles.value[type] || typeStyles.value.class;
  const dims = nodeDims(name, type);

  const node = cyInstance.add({
    group: 'nodes',
    data: {
      id, label: name, type,
      shape: cfg.shape, fill: cfg.fill, stroke: cfg.stroke, textColor: cfg.textColor,
      iri: baseIRI.value + name, annotations: {},
      ...dims,
    },
    position: { x: 200 + Math.random() * 200, y: 200 + Math.random() * 200 }
  });

  if (parentId) {
      addEdgeDirect('subClassOf', parentId, id);
  }

  // Smoothly center the canvas viewport on the newly created node
  cyInstance.animate({ center: { eles: node } }, { duration: 300 });

  syncOntologyToParams();
}

function addEdgeDirect(relType, srcId, tgtId) {
  if (!cyInstance || !srcId || !tgtId) return;
  const id = `e__${relType}__${srcId}__${tgtId}__${Date.now()}`;
  const isDashed = ['equivalentClass','disjointWith'].includes(relType);
  
  cyInstance.add({
    group: 'edges',
    data: {
      id, source: srcId, target: tgtId,
      label: relType, relType,
      ec: EDGE_COLORS[relType] || EDGE_COLORS.relation,
      ...(isDashed ? { dashed: true } : {}),
    }
  });
  
  syncOntologyToParams();
}

function deleteSelectedElement() {
    if (!selEl.value) return;
    selEl.value.remove();
    selEl.value = null;
    selectedNodeData.value = null;
    selectedEdgeData.value = null;
    syncOntologyToParams();
}

function updateNodeProp(key, value) {
    if (!selEl.value || !selEl.value.isNode()) return;
    selEl.value.data(key, value);
    if (key === 'label') {
        const dims = nodeDims(value, selEl.value.data('type'));
        selEl.value.data('w', dims.w);
        selEl.value.data('h', dims.h);
        selEl.value.data('tw', dims.tw);
        selEl.value.data('fs', dims.fs);
    }
    selectedNodeData.value = { ...selEl.value.data() };
    syncOntologyToParams();
}

function applyHighlighting() {
  if (!cyInstance) return;
  if (!highlightConnectionsMode.value) {
    cyInstance.elements().removeClass('dimmed').removeClass('highlighted-edge').removeClass('highlighted-node');
    return;
  }
  const selected = cyInstance.$(':selected');
  if (selected.length === 0) {
    cyInstance.elements().removeClass('dimmed').removeClass('highlighted-edge').removeClass('highlighted-node');
    return;
  }
  
  cyInstance.elements().addClass('dimmed').removeClass('highlighted-edge').removeClass('highlighted-node');
  
  selected.forEach(ele => {
    ele.removeClass('dimmed');
    if (ele.isNode()) {
      ele.closedNeighborhood().removeClass('dimmed');
      ele.connectedEdges().addClass('highlighted-edge').removeClass('dimmed');
      ele.neighborhood().addClass('highlighted-node').removeClass('dimmed');
    } else {
      ele.source().removeClass('dimmed');
      ele.target().removeClass('dimmed');
      ele.addClass('highlighted-edge').removeClass('dimmed');
    }
  });
}

function toggleOrphans() {
  hideOrphans.value = !hideOrphans.value;
  applyOrphansFilter();
}

function applyOrphansFilter() {
  if (!cyInstance) return;
  if (hideOrphans.value) {
    cyInstance.nodes().forEach(n => {
      if (n.connectedEdges().length === 0) {
        n.addClass('orphan-hidden');
      } else {
        n.removeClass('orphan-hidden');
      }
    });
  } else {
    cyInstance.nodes().removeClass('orphan-hidden');
  }
}

function changeNodeShape(shape) {
    if (!selEl.value || !selEl.value.isNode()) return;
    selEl.value.data('shape', shape);
    selectedNodeData.value = { ...selEl.value.data() };
    syncOntologyToParams();
}

function changeNodeColor(stroke, fill) {
    if (!selEl.value || !selEl.value.isNode()) return;
    selEl.value.data('stroke', stroke);
    selEl.value.data('fill', fill);
    
    // text light adaptation
    const r=parseInt(stroke.slice(1,3),16), g=parseInt(stroke.slice(3,5),16), b=parseInt(stroke.slice(5,7),16);
    const lr=Math.min(255,r+Math.round((255-r)*0.35));
    const lg=Math.min(255,g+Math.round((255-g)*0.35));
    const lb=Math.min(255,b+Math.round((255-b)*0.35));
    const textColor = '#' + [lr,lg,lb].map(x=>x.toString(16).padStart(2,'0')).join('');
    
    selEl.value.data('textColor', textColor);
    selectedNodeData.value = { ...selEl.value.data() };
    syncOntologyToParams();
}

// --- Serializations (Turtle, JSON-LD, SKOS, Manchester, RDF/XML) ---
function genTurtle() {
  if (!cyInstance) return '';
  const n = cyInstance.nodes(), e = cyInstance.edges();
  let t = `@prefix : <${baseIRI.value}> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<${ontoIRI.value}> a owl:Ontology .\n\n`;

  n.filter(c => c.data('type') === 'class').forEach(c => {
    const lines = [];
    if (c.data('rdfsLabel')) lines.push(`    rdfs:label "${c.data('rdfsLabel')}"@en`);
    if (c.data('comment'))   lines.push(`    rdfs:comment "${c.data('comment')}"@en`);
    e.filter(x => x.data('source') === c.id() && x.data('relType') === 'subClassOf')
      .forEach(x => { lines.push(`    rdfs:subClassOf :${cyInstance.getElementById(x.data('target')).data('label')}`); });
    t += `:${c.data('label')} a owl:Class`;
    t += lines.length ? ' ;\n' + lines.join(' ;\n') + ' .\n\n' : ' .\n\n';
  });
  return t.trim();
}

function genJSONLD() {
  if (!cyInstance) return '';
  const n = cyInstance.nodes(), e = cyInstance.edges();
  
  const graph = [];
  n.forEach(node => {
      const item = {
          "@id": `${baseIRI.value}${node.data('label')}`,
          "@type": node.data('type') === 'class' ? "owl:Class" : "owl:Individual",
          "rdfs:label": node.data('rdfsLabel') || node.data('label')
      };
      if (node.data('comment')) {
          item["rdfs:comment"] = node.data('comment');
      }
      graph.push(item);
  });
  
  e.forEach(edge => {
      const sourceLabel = cyInstance.getElementById(edge.data('source')).data('label');
      const targetLabel = cyInstance.getElementById(edge.data('target')).data('label');
      graph.push({
          "@id": `${baseIRI.value}${sourceLabel}`,
          [`rdfs:${edge.data('relType') || 'related'}`]: {
              "@id": `${baseIRI.value}${targetLabel}`
          }
      });
  });

  const output = {
      "@context": {
          "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
          "owl": "http://www.w3.org/2002/07/owl#",
          "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
          "skos": "http://www.w3.org/2004/02/skos/core#",
          "@vocab": baseIRI.value
      },
      "@graph": graph
  };
  return JSON.stringify(output, null, 2);
}

function genSKOS() {
  if (!cyInstance) return '';
  const n = cyInstance.nodes(), e = cyInstance.edges();
  let s = `@prefix : <${baseIRI.value}> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

<${ontoIRI.value}> a skos:ConceptScheme .\n\n`;

  n.filter(c => c.data('type') === 'concept' || c.data('type') === 'class').forEach(c => {
      const lines = [`    skos:prefLabel "${c.data('rdfsLabel') || c.data('label')}"@en`];
      if (c.data('comment')) {
          lines.push(`    skos:definition "${c.data('comment')}"@en`);
      }
      e.filter(x => x.data('source') === c.id()).forEach(x => {
          const tgt = cyInstance.getElementById(x.data('target')).data('label');
          if (x.data('relType') === 'broader') lines.push(`    skos:broader :${tgt}`);
          else if (x.data('relType') === 'narrower') lines.push(`    skos:narrower :${tgt}`);
          else lines.push(`    skos:related :${tgt}`);
      });
      s += `:${c.data('label')} a skos:Concept ;\n${lines.join(' ;\n')} .\n\n`;
  });
  return s.trim();
}

function genManchester() {
  if (!cyInstance) return '';
  const n = cyInstance.nodes(), e = cyInstance.edges();
  let o = `Prefix: owl: <http://www.w3.org/2002/07/owl#>
Prefix: rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
Prefix: rdfs: <http://www.w3.org/2000/01/rdf-schema#>
Prefix: : <${baseIRI.value}>\n
Ontology: <${ontoIRI.value}>\n\n`;

  n.filter(x => x.data('type') === 'class').forEach(c => {
    o += `Class: :${c.data('label')}\n`;
    if (c.data('rdfsLabel')) o += `    Annotations: rdfs:label "${c.data('rdfsLabel')}"\n`;
    e.filter(x => x.data('source') === c.id() && x.data('relType') === 'subClassOf')
      .forEach(x => { o += `    SubClassOf: :${cyInstance.getElementById(x.data('target')).data('label')}\n`; });
    o += '\n';
  });
  return o.trim();
}

function genRDFXML() {
  if (!cyInstance) return '';
  const n = cyInstance.nodes(), e = cyInstance.edges();
  let x = `<?xml version="1.0"?>
<rdf:RDF
  xml:base="${baseIRI.value}"
  xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
  xmlns:owl="http://www.w3.org/2002/07/owl#"
  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">

  <owl:Ontology rdf:about="${ontoIRI.value}"/>\n\n`;

  n.filter(c => c.data('type') === 'class').forEach(c => {
    x += `  <owl:Class rdf:about="${baseIRI.value}${c.data('label')}">\n`;
    if (c.data('rdfsLabel')) x += `    <rdfs:label xml:lang="en">${c.data('rdfsLabel')}</rdfs:label>\n`;
    x += `  </owl:Class>\n\n`;
  });
  x += `</rdf:RDF>`;
  return x;
}

function syncOntologyToParams() {
    let output = '';
    if (curCT.value === 'turtle') output = genTurtle();
    else if (curCT.value === 'jsonld') output = genJSONLD();
    else if (curCT.value === 'skos') output = genSKOS();
    else if (curCT.value === 'manchester') output = genManchester();
    else if (curCT.value === 'rdfxml') output = genRDFXML();
    
    generationParams.value.ontology = output;
}

// SPARQL local engine queries
function runSPARQLQuery() {
  const query = sparqlQueryInput.value;
  if (!query) return;
  try {
      isFilterActive.value = false;

      // Clean query and determine type
      const cleanQuery = query
        .replace(/#.*$/gm, '') // Remove comments
        .replace(/\s+/g, ' ')
        .trim();

      const isConstruct = /CONSTRUCT\s*\{/i.test(cleanQuery);
      const isDescribe = /DESCRIBE\s+/i.test(cleanQuery);

      if (isConstruct) {
          sparqlQueryMode.value = 'CONSTRUCT';
          executeConstructQuery(cleanQuery);
      } else if (isDescribe) {
          sparqlQueryMode.value = 'DESCRIBE';
          executeDescribeQuery(cleanQuery);
      } else {
          sparqlQueryMode.value = 'SELECT';
          executeSelectQuery(cleanQuery);
      }
  } catch (err) {
      uiStore.addNotification(`SPARQL Error: ${err.message}`, 'error');
  }
}

function getOntologyTriples() {
    if (!cyInstance) return [];
    const triples = [];

    // Add Node type triples (e.g. :Main a owl:Class)
    cyInstance.nodes().forEach(node => {
        const label = node.data('label');
        const type = node.data('type') || 'class';

        // Map individual classes natively if tagged in annotations
        if (type === 'individual' && node.data('annotations')?.['rdf:type']) {
            triples.push({ s: `:${label}`, p: 'rdf:type', o: `:${node.data('annotations')['rdf:type']}`, elementId: node.id() });
        } else {
            triples.push({ s: `:${label}`, p: 'rdf:type', o: `owl:${type.charAt(0).toUpperCase() + type.slice(1)}`, elementId: node.id() });
        }

        if (node.data('rdfsLabel')) {
            triples.push({ s: `:${label}`, p: 'rdfs:label', o: `"${node.data('rdfsLabel')}"`, elementId: node.id() });
        }
        if (node.data('comment')) {
            triples.push({ s: `:${label}`, p: 'rdfs:comment', o: `"${node.data('comment')}"`, elementId: node.id() });
        }
    });

    // Add Edge triples (e.g. :Main rdfs:subClassOf :Entity)
    cyInstance.edges().forEach(edge => {
        const src = cyInstance.getElementById(edge.data('source')).data('label');
        const tgt = cyInstance.getElementById(edge.data('target')).data('label');
        const rel = edge.data('label') || 'relation';

        triples.push({ s: `:${src}`, p: `rdfs:${rel}`, o: `:${tgt}`, elementId: edge.id() });
    });

    return triples;
}

function executeSelectQuery(query) {
    const selectMatch = query.match(/SELECT\s+([\s\S]+?)\s+WHERE/i);
    if (!selectMatch) throw new Error("Missing SELECT clause");
    const selectVars = selectMatch[1].trim().split(/\s+/).map(v => v.trim());

    const whereMatch = query.match(/WHERE\s*\{([\s\S]+?)\}/i);
    if (!whereMatch) throw new Error("Missing WHERE clause block");
    const whereBody = whereMatch[1].trim();

    const patterns = parseTriplePatterns(whereBody);
    const db = getOntologyTriples();
    const rows = evaluatePatterns(patterns, db, selectVars);

    sparqlResults.value = { vars: selectVars, rows, matchedElementIds: [] };
}

function executeConstructQuery(query) {
    const constructMatch = query.match(/CONSTRUCT\s*\{([\s\S]+?)\}\s*WHERE\s*\{([\s\S]+?)\}/i);
    if (!constructMatch) throw new Error("Malformed CONSTRUCT query");

    const templateBody = constructMatch[1].trim();
    const whereBody = constructMatch[2].trim();

    const templatePatterns = parseTriplePatterns(templateBody);
    const wherePatterns = parseTriplePatterns(whereBody);

    // Extract all variables used in template and where
    const allVars = new Set();
    templatePatterns.forEach(p => {
        if (p.s.startsWith('?')) allVars.add(p.s);
        if (p.p.startsWith('?')) allVars.add(p.p);
        if (p.o.startsWith('?')) allVars.add(p.o);
    });
    wherePatterns.forEach(p => {
        if (p.s.startsWith('?')) allVars.add(p.s);
        if (p.p.startsWith('?')) allVars.add(p.p);
        if (p.o.startsWith('?')) allVars.add(p.o);
    });

    const db = getOntologyTriples();
    const matches = evaluatePatterns(wherePatterns, db, Array.from(allVars));

    // Bind template patterns with matched solutions to build the subgraph
    const subgraphTriples = [];
    const matchedElementIds = new Set();

    matches.forEach(solution => {
        templatePatterns.forEach(pat => {
            const s = pat.s.startsWith('?') ? solution[pat.s] : pat.s;
            const p = pat.p.startsWith('?') ? solution[pat.p] : pat.p;
            const o = pat.o.startsWith('?') ? solution[pat.o] : pat.o;

            if (s && p && o) {
                subgraphTriples.push({ s, p, o });

                // Track source & target element IDs to draw them
                const sLabel = s.startsWith(':') ? s.slice(1) : s;
                const oLabel = o.startsWith(':') ? o.slice(1) : o;

                const sNode = cyInstance.nodes().filter(n => n.data('label') === sLabel);
                const oNode = cyInstance.nodes().filter(n => n.data('label') === oLabel);

                if (sNode.length) matchedElementIds.add(sNode.id());
                if (oNode.length) matchedElementIds.add(oNode.id());
            }
        });
        if (solution._elementIds) {
            solution._elementIds.forEach(id => matchedElementIds.add(id));
        }
    });

    sparqlResults.value = { 
        vars: ['Subject', 'Predicate', 'Object'], 
        rows: subgraphTriples.map(t => ({ 'Subject': t.s, 'Predicate': t.p, 'Object': t.o })),
        matchedElementIds: Array.from(matchedElementIds)
    };

    uiStore.addNotification(`CONSTRUCT matched subgraph with ${subgraphTriples.length} triples. Click 'Filter Canvas' to isolate.`, 'info');
}

function executeDescribeQuery(query) {
    const describeMatch = query.match(/DESCRIBE\s+(\?\w+)\s*WHERE\s*\{([\s\S]+?)\}/i);
    if (!describeMatch) throw new Error("Malformed DESCRIBE query");

    const targetVar = describeMatch[1].trim();
    const whereBody = describeMatch[2].trim();

    const wherePatterns = parseTriplePatterns(whereBody);
    const db = getOntologyTriples();
    const matches = evaluatePatterns(wherePatterns, db, [targetVar]);

    const targetValues = new Set(matches.map(sol => sol[targetVar]).filter(Boolean));
    const subgraphTriples = db.filter(t => targetValues.has(t.s) || targetValues.has(t.o));
    const matchedElementIds = new Set(subgraphTriples.map(t => t.elementId).filter(Boolean));

    subgraphTriples.forEach(t => {
        const sLabel = t.s.startsWith(':') ? t.s.slice(1) : t.s;
        const oLabel = t.o.startsWith(':') ? t.o.slice(1) : t.o;
        const sNode = cyInstance.nodes().filter(n => n.data('label') === sLabel);
        const oNode = cyInstance.nodes().filter(n => n.data('label') === oLabel);
        if (sNode.length) matchedElementIds.add(sNode.id());
        if (oNode.length) matchedElementIds.add(oNode.id());
    });

    sparqlResults.value = {
        vars: ['Subject', 'Predicate', 'Object'],
        rows: subgraphTriples.map(t => ({ 'Subject': t.s, 'Predicate': t.p, 'Object': t.o })),
        matchedElementIds: Array.from(matchedElementIds)
    };
}

function parseTriplePatterns(bodyText) {
    const patterns = [];
    const rawPatterns = bodyText.split(/\.(?=(?:[^"]|"[^"]*")*$)/);
    rawPatterns.forEach(pat => {
        const parts = pat.trim().match(/(?:[^\s"]+|"[^"]*")+/g);
        if (parts && parts.length >= 3) {
            patterns.push({ s: parts[0], p: parts[1], o: parts[2] });
        }
    });
    return patterns;
}

function evaluatePatterns(patterns, db, selectVars) {
    const results = [];

    function matchPattern(patternIdx, env, matchedIds) {
        if (patternIdx === patterns.length) {
            const resultRow = {};
            selectVars.forEach(v => {
                resultRow[v] = env[v] !== undefined ? env[v] : '';
            });
            resultRow._elementIds = Array.from(matchedIds);
            results.push(resultRow);
            return;
        }

        const pat = patterns[patternIdx];
        const sVal = pat.s.startsWith('?') ? env[pat.s] : pat.s;
        const pVal = pat.p.startsWith('?') ? env[pat.p] : pat.p;
        const oVal = pat.o.startsWith('?') ? env[pat.o] : pat.o;

        for (const triple of db) {
            const newEnv = { ...env };

            if (pat.s.startsWith('?')) {
                if (sVal !== undefined && sVal !== triple.s) continue;
                newEnv[pat.s] = triple.s;
            } else {
                if (pat.s !== triple.s) continue;
            }

            if (pat.p.startsWith('?')) {
                if (pVal !== undefined && pVal !== triple.p) continue;
                newEnv[pat.p] = triple.p;
            } else {
                if (pat.p !== triple.p) continue;
            }

            if (pat.o.startsWith('?')) {
                if (oVal !== undefined && oVal !== triple.o) continue;
                newEnv[pat.o] = triple.o;
            } else {
                if (pat.o !== triple.o) continue;
            }

            const nextMatched = new Set(matchedIds);
            if (triple.elementId) {
                nextMatched.add(triple.elementId);
            }

            matchPattern(patternIdx + 1, newEnv, nextMatched);
        }
    }

    matchPattern(0, {}, new Set());

    // Deduplicate solutions
    const uniqueResults = [];
    const seen = new Set();
    results.forEach(row => {
        const temp = { ...row };
        delete temp._elementIds;
        const str = JSON.stringify(temp);
        if (!seen.has(str)) {
            seen.add(str);
            uniqueResults.push(row);
        }
    });

    return uniqueResults;
}

function toggleCanvasFilter() {
    if (!cyInstance || !sparqlResults.value?.matchedElementIds) return;

    isFilterActive.value = !isFilterActive.value;

    if (isFilterActive.value) {
        const activeIds = new Set(sparqlResults.value.matchedElementIds);
        cyInstance.elements().forEach(el => {
            if (!activeIds.has(el.id())) {
                el.addClass('hidden-element');
            } else {
                el.removeClass('hidden-element');
            }
        });
        uiStore.addNotification("Canvas filtered to matched SPARQL subgraph.", "info");
    } else {
        cyInstance.elements().removeClass('hidden-element');
    }
}

function selectSPARQLRow(idx) {
  if (!sparqlResults.value || !sparqlResults.value.rows[idx] || !cyInstance) return;
  const row = sparqlResults.value.rows[idx];
  cyInstance.elements().unselect();

  const idsToSelect = new Set(row._elementIds || []);
  sparqlResults.value.vars.forEach(v => {
    const val = row[v];
    if (val && val.startsWith(':')) {
      const label = val.slice(1);
      const node = cyInstance.nodes().filter(n => n.data('label') === label);
      if (node.length) idsToSelect.add(node.id());
    }
  });

  const targetElements = cyInstance.elements().filter(el => idsToSelect.has(el.id()));
  if (targetElements.length) {
    targetElements.select();
    cyInstance.animate({ center: { eles: targetElements } }, { duration: 300 });
  }
}

// --- AI Assisted Building ---
async function generateAIExtensions() {
    if (!aiPrompt.value.trim() || !cyInstance) return;
    isAIGenerating.value = true;
    
    const schema = genTurtle();
    const sysPrompt = `You are an expert Semantic Ontologist. Process the user's request and extend the OWL/Turtle schema with new concepts.
    You MUST respond with a strictly valid JSON object inside a single markdown code block starting with \`\`\`json.
    
    The schema format is:
    {
      "nodes": [
        { "type": "class|property|dataprop|individual|concept", "name": "UniqueName", "rdfsLabel": "Human readable label", "comment": "Definition" }
      ],
      "edges": [
        { "source": "SourceNodeName", "target": "TargetNodeName", "relType": "subClassOf|domain|range|equivalentClass|disjointWith|type|broader|narrower" }
      ]
    }`;

    const prompt = `Current Ontology Schema:\n${schema}\n\nUser request: ${aiPrompt.value}`;

    try {
        const response = await apiClient.post('/api/lollms/generate', {
            prompt: `${sysPrompt}\n\n${prompt}`,
            max_new_tokens: 1536,
            temperature: 0.2
        });
        
        const rawText = response.data.generated_text || response.data;
        const jsonMatch = rawText.match(/```json\s*([\s\S]+?)\s*```/);
        
        if (jsonMatch) {
            const result = JSON.parse(jsonMatch[1]);
            
            if (result.nodes) {
                result.nodes.forEach(n => {
                    addNodeDirect(n.type, n.name);
                });
            }
            if (result.edges) {
                await nextTick();
                result.edges.forEach(e => {
                    const srcId = cyInstance.nodes().filter(n => n.data('label') === e.source).id();
                    const tgtId = cyInstance.nodes().filter(n => n.data('label') === e.target).id();
                    if (srcId && tgtId) {
                        addEdgeDirect(e.relType, srcId, tgtId);
                    }
                });
            }
            
            runCoseLayout();
            aiPrompt.value = '';
            uiStore.addNotification("Ontology extended successfully by AI Assistant!", "success");
        } else {
            throw new Error("AI did not respond with a valid JSON block.");
        }
    } catch (e) {
        console.error(e);
        uiStore.addNotification("Failed to execute AI ontology extension.", "error");
    } finally {
        isAIGenerating.value = false;
    }
}

// Standard datastore actions
async function fetchGraph() {
    if (!isComponentMounted.value) return;
    isLoadingGraph.value = true;
    try {
        const data = await dataStore.fetchDataStoreGraph(props.store.id);
        if (!isComponentMounted.value) return;
        graphData.value = data || { nodes: [], edges: [] };
        graphStats.value = {
            nodes: data?.nodes?.length || 0,
            edges: data?.edges?.length || 0
        };
    } catch (error) {
        graphData.value = { nodes: [], edges: [] };
        graphStats.value = { nodes: 0, edges: 0 };
    } finally {
        isLoadingGraph.value = false;
    }
}

function handleGenerateGraph() {
    const binding = generationParams.value.model_binding || user.value?.default_binding;
    const name = generationParams.value.model_name || user.value?.default_model;

    if (!binding || !name) {
        uiStore.addNotification('Please select a model for generation.', 'warning');
        return;
    }

    generationParams.value.model_binding = binding;
    generationParams.value.model_name = name;

    syncOntologyToParams();
    dataStore.generateDataStoreGraph({
        storeId: props.store.id,
        graphData: generationParams.value
    });
}

function handleUpdateGraph() {
    const binding = generationParams.value.model_binding || user.value?.default_binding;
    const name = generationParams.value.model_name || user.value?.default_model;

    if (!binding || !name) {
        uiStore.addNotification('Please select a model for update.', 'warning');
        return;
    }

    generationParams.value.model_binding = binding;
    generationParams.value.model_name = name;

    syncOntologyToParams();
    dataStore.updateDataStoreGraph({
        storeId: props.store.id,
        graphData: generationParams.value
    });
}

async function handleWipeGraph() {
    const confirmed = await uiStore.showConfirmation({
        title: 'Wipe Knowledge Graph?',
        message: 'This will permanently delete all nodes and edges from this datastore\'s graph.',
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

onMounted(() => {
    fetchGraph();
    if (viewMode.value === 'ontology') {
        nextTick(() => initCytoscape());
    }
});

watch(viewMode, (newMode) => {
    if (newMode === 'ontology') {
        nextTick(() => initCytoscape());
    } else {
        if (cyInstance) {
            cyInstance.destroy();
            cyInstance = null;
        }
    }
});

watch(() => props.store.id, fetchGraph);
</script>

<template>
    <div class="h-full flex flex-col overflow-hidden">
        <!-- Tab Sub-Header -->
        <div class="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800 border-b dark:border-gray-700 z-10 shrink-0">
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

        <div class="grow flex flex-col lg:flex-row gap-0 overflow-hidden">
            <!-- Left Sidebar Navigation -->
            <div class="w-full lg:w-80 lg:shrink-0 h-full overflow-y-auto custom-scrollbar p-4 border-r dark:border-gray-700 bg-white dark:bg-gray-900 flex flex-col gap-4">
                
                <div class="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-100 dark:border-blue-800">
                    <h4 class="text-[10px] font-black uppercase text-blue-600 dark:text-blue-400 mb-1">Current Workspace</h4>
                    <p class="text-xs font-bold">{{ viewMode === 'graph' ? 'Semantic Explorer' : 'Visual Designer' }}</p>
                </div>

                <!-- Type Selector Quick Actions (Ontology mode only) -->
                <div v-if="viewMode === 'ontology'" class="space-y-4">
                    <h3 class="text-[10px] font-black uppercase tracking-wider text-gray-400 dark:text-gray-500">Ontology Elements</h3>
                    <div class="flex flex-col gap-1.5">
                        <button @click="addNodeDirect('class', 'Class_' + Date.now().toString().slice(-4))" class="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-xs font-semibold hover:bg-gray-200 dark:hover:bg-gray-700">
                            <span class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full bg-[#7c6ff7]"></span>Class</span>
                            <span class="text-[10px] opacity-50">+ Add</span>
                        </button>
                        <button @click="addNodeDirect('property', 'prop_' + Date.now().toString().slice(-4))" class="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-xs font-semibold hover:bg-gray-200 dark:hover:bg-gray-700">
                            <span class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full bg-[#2dd4bf]"></span>Object Property</span>
                            <span class="text-[10px] opacity-50">+ Add</span>
                        </button>
                        <button @click="addNodeDirect('dataprop', 'data_' + Date.now().toString().slice(-4))" class="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-xs font-semibold hover:bg-gray-200 dark:hover:bg-gray-700">
                            <span class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full bg-[#fbbf24]"></span>Data Property</span>
                            <span class="text-[10px] opacity-50">+ Add</span>
                        </button>
                        <button @click="addNodeDirect('concept', 'Concept_' + Date.now().toString().slice(-4))" class="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-xs font-semibold hover:bg-gray-200 dark:hover:bg-gray-700">
                            <span class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full bg-[#f472b6]"></span>SKOS Concept</span>
                            <span class="text-[10px] opacity-50">+ Add</span>
                        </button>
                        <button @click="addNodeDirect('individual', 'ind_' + Date.now().toString().slice(-4))" class="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-xs font-semibold hover:bg-gray-200 dark:hover:bg-gray-700">
                            <span class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full bg-[#4ade80]"></span>Individual</span>
                            <span class="text-[10px] opacity-50">+ Add</span>
                        </button>
                    </div>
                </div>

                <!-- Type Selector Quick Actions (Knowledge Graph mode) -->
                <div v-else class="space-y-4">
                    <h3 class="text-[10px] font-black uppercase tracking-wider text-gray-400 dark:text-gray-500">Graph Instances</h3>
                    <div class="flex flex-col gap-1.5">
                        <!-- Generic Individual Spawner -->
                        <button @click="addNodeDirect('individual', 'Entity_' + Date.now().toString().slice(-4))" class="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-xs font-semibold hover:bg-gray-200 dark:hover:bg-gray-700">
                            <span class="flex items-center gap-2">
                                <span class="w-2.5 h-2.5 rounded-full bg-[#94a3b8]"></span>
                                Generic Individual
                            </span>
                            <span class="text-[10px] opacity-50">+ Add</span>
                        </button>

                        <!-- Dynamic Class-Specific Spawner Buttons -->
                        <button 
                            v-for="className in ontologyClasses" 
                            :key="className"
                            @click="addIndividualOfClass(className)" 
                            class="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-800 text-xs font-semibold hover:bg-gray-200 dark:hover:bg-gray-700 border border-transparent hover:border-emerald-500/20"
                        >
                            <span class="flex items-center gap-2">
                                <span 
                                    class="w-2.5 h-2.5 rounded-full" 
                                    :style="{ backgroundColor: getNodeColor(className, uiStore.currentTheme === 'dark') }"
                                ></span>
                                Individual ({{ className }})
                            </span>
                            <span class="text-[10px] opacity-50">+ Add</span>
                        </button>
                    </div>
                </div>

                <!-- LLM Model Config -->
                <div class="p-4 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 space-y-3">
                    <label class="block text-[10px] font-black uppercase tracking-widest text-gray-400">Generation Model</label>
                    <select v-model="selectedFullModel" class="input-field text-xs">
                        <option disabled value="">Select engine...</option>
                        <optgroup v-for="group in availableLLMModelsGrouped" :key="group.label" :label="group.label">
                            <option v-for="model in group.items" :key="model.id" :value="`${group.label}/${model.id}`">{{ model.name }}</option>
                        </optgroup>
                    </select>
                </div>

                <!-- Danger / Wipe Zone -->
                <div class="mt-auto p-4 bg-red-50 dark:bg-red-950/20 rounded-xl border border-red-100 dark:border-red-900/40">
                    <h4 class="text-[10px] font-black uppercase text-red-600 dark:text-red-400 tracking-widest mb-3">Maintenance</h4>
                    <button @click="handleWipeGraph" :disabled="!!task || graphStats.nodes === 0" class="btn btn-ghost text-red-600 hover:bg-red-100 dark:hover:bg-red-900/30 w-full btn-xs flex items-center justify-center gap-2 border border-red-200 dark:border-red-800">
                        <IconTrash class="w-3.5 h-3.5"/> Wipe Graph Data
                    </button>
                </div>
            </div>

            <!-- Main Canvas / Graph View Workspace -->
            <div class="grow h-full bg-white dark:bg-gray-950 relative overflow-hidden flex flex-col">
                <div class="grow relative min-h-0">
                    
                    <!-- Graph Exploration Mode -->
                    <div v-if="viewMode === 'graph'" class="h-full w-full">
                        <div v-if="graphStats.nodes === 0 && !isLoadingGraph" class="absolute inset-0 flex flex-col items-center justify-center bg-gray-50/80 dark:bg-gray-900/80 z-10 p-6 text-center">
                            <div class="bg-white dark:bg-gray-800 p-10 rounded-3xl shadow-2xl border dark:border-gray-700 max-w-lg">
                                <h3 class="text-2xl font-black text-gray-900 dark:text-white mb-3">Graph is Offline</h3>
                                <p class="text-gray-500 dark:text-gray-400 text-sm mb-8 leading-relaxed">
                                    No semantic map has been built yet. Switch to the <strong>Ontology Designer</strong> to model your schema and start.
                                </p>
                                <button @click="viewMode = 'ontology'" class="btn btn-primary px-10 py-3 rounded-2xl shadow-xl">
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
                        />
                    </div>

                    <!-- Ontology Canvas Mode -->
                    <div v-else class="h-full w-full relative">
                        <!-- Cytoscape Target Container (Main designer) -->
                        <div ref="cyContainer" class="absolute inset-0 h-full w-full bg-white dark:bg-gray-950"></div>
                        
                        <!-- Floating HUD Controls -->
                        <div class="absolute top-4 left-4 flex gap-2 z-20">
                            <button @click="cyInstance.zoom(cyInstance.zoom() * 1.25)" class="p-2 bg-white dark:bg-gray-800 rounded-md shadow-md text-gray-700 dark:text-gray-200 hover:bg-gray-50 border dark:border-gray-700" title="Zoom in">Zoom In</button>
                            <button @click="cyInstance.zoom(cyInstance.zoom() * 0.8)" class="p-2 bg-white dark:bg-gray-800 rounded-md shadow-md text-gray-700 dark:text-gray-200 hover:bg-gray-50 border dark:border-gray-700" title="Zoom out">Zoom Out</button>
                            <button @click="cyInstance.fit(null, 40)" class="p-2 bg-white dark:bg-gray-800 rounded-md shadow-md text-gray-700 dark:text-gray-200 hover:bg-gray-50 border dark:border-gray-700" title="Fit all">Fit View</button>
                            <button @click="runCoseLayout" class="p-2 bg-white dark:bg-gray-800 rounded-md shadow-md text-gray-700 dark:text-gray-200 hover:bg-gray-50 border dark:border-gray-700" title="Format Layout">Re-arrange Layout</button>
                        </div>

                        <div class="absolute top-4 right-4 flex gap-2 z-20">
                            <button @click="toggleOrphans" :class="['p-2 rounded-md shadow-md border text-xs font-bold transition-all', hideOrphans ? 'bg-blue-500 border-blue-600 text-white' : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200']">
                                Orphans Filter
                            </button>
                            <button @click="highlightConnectionsMode = !highlightConnectionsMode; applyHighlighting();" :class="['p-2 rounded-md shadow-md border text-xs font-bold transition-all', highlightConnectionsMode ? 'bg-blue-500 border-blue-600 text-white' : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200']">
                                Highlight Connections
                            </button>
                            <button @click="showCodeDrawer = !showCodeDrawer" :class="['p-2 rounded-md shadow-md border text-xs font-bold transition-all', showCodeDrawer ? 'bg-emerald-500 border-emerald-600 text-white' : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200']">
                                {{ showCodeDrawer ? 'Hide Code' : 'View Code' }}
                            </button>
                        </div>
                    </div>

                </div>

                <!-- Collapsible Bottom Code Drawer -->
                <div v-if="viewMode === 'ontology' && showCodeDrawer" class="h-64 border-t dark:border-gray-800 bg-gray-50 dark:bg-gray-900 flex flex-col shrink-0">
                    <div class="h-10 border-b dark:border-gray-800 px-4 flex items-center justify-between shrink-0">
                        <div class="flex gap-2">
                            <button @click="curCT = 'turtle'; syncOntologyToParams()" :class="['px-3 py-1 text-xs rounded font-bold transition-all', curCT === 'turtle' ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400' : 'text-gray-500']">Turtle</button>
                            <button @click="curCT = 'jsonld'; syncOntologyToParams()" :class="['px-3 py-1 text-xs rounded font-bold transition-all', curCT === 'jsonld' ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400' : 'text-gray-500']">JSON-LD</button>
                            <button @click="curCT = 'skos'; syncOntologyToParams()" :class="['px-3 py-1 text-xs rounded font-bold transition-all', curCT === 'skos' ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400' : 'text-gray-500']">SKOS</button>
                            <button @click="curCT = 'manchester'; syncOntologyToParams()" :class="['px-3 py-1 text-xs rounded font-bold transition-all', curCT === 'manchester' ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400' : 'text-gray-500']">Manchester OWL</button>
                            <button @click="curCT = 'rdfxml'; syncOntologyToParams()" :class="['px-3 py-1 text-xs rounded font-bold transition-all', curCT === 'rdfxml' ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400' : 'text-gray-500']">RDF/XML</button>
                            <button @click="curCT = 'sparql'" :class="['px-3 py-1 text-xs rounded font-bold transition-all', curCT === 'sparql' ? 'bg-blue-500/10 text-blue-600 dark:text-blue-400' : 'text-gray-500']">SPARQL Query</button>
                        </div>
                    </div>
                    
                    <div class="grow min-h-0 relative">
                        <!-- Code Serialization Panel -->
                        <CodeMirrorEditor 
                            v-if="curCT !== 'sparql'"
                            v-model="generationParams.ontology" 
                            :language="'python'" 
                            class="absolute inset-0 h-full w-full" 
                            placeholder="Generate ontology configuration..."
                        />
                        
                        <!-- SPARQL Local Playground -->
                        <div v-else class="absolute inset-0 flex h-full w-full overflow-hidden divide-x dark:divide-gray-800">
                            <div class="w-1/2 flex flex-col p-3 gap-2">
                                <div class="flex justify-between items-center">
                                    <span class="text-[10px] font-black uppercase text-gray-400">Playground Query</span>
                                    <div class="flex gap-1.5">
                                        <button 
                                            v-if="sparqlResults?.matchedElementIds?.length > 0"
                                            @click="toggleCanvasFilter" 
                                            :class="['btn btn-xs px-3 h-7 font-bold', isFilterActive ? 'btn-danger' : 'btn-secondary']"
                                        >
                                            {{ isFilterActive ? 'Clear Filter' : 'Filter Canvas' }}
                                        </button>
                                        <button @click="runSPARQLQuery" class="btn btn-primary btn-xs px-4 h-7">Run</button>
                                    </div>
                                </div>
                                <textarea v-model="sparqlQueryInput" class="grow w-full bg-white dark:bg-gray-950 p-2 font-mono text-xs rounded border dark:border-gray-800 outline-none resize-none"></textarea>
                            </div>
                            
                            <div class="w-1/2 flex flex-col p-3 gap-2 overflow-hidden">
                                <span class="text-[10px] font-black uppercase text-gray-400">Local Axiom Triples Match</span>
                                <div class="grow overflow-y-auto custom-scrollbar bg-white dark:bg-gray-950 rounded border dark:border-gray-800">
                                    <div v-if="!sparqlResults" class="p-4 text-center text-xs text-gray-400 italic">Run a query to fetch graph instances.</div>
                                    <table v-else class="w-full text-xs font-mono text-left">
                                        <thead>
                                            <tr class="bg-gray-50 dark:bg-gray-900 border-b dark:border-gray-800 text-gray-400">
                                                <th class="p-2">#</th>
                                                <th v-for="v in sparqlResults.vars" :key="v" class="p-2">{{ v }}</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr v-for="(row, idx) in sparqlResults.rows" :key="idx" @click="selectSPARQLRow(idx)" class="hover:bg-blue-500/5 cursor-pointer border-b dark:border-gray-900">
                                                <td class="p-2 text-gray-500">{{ idx + 1 }}</td>
                                                <td v-for="v in sparqlResults.vars" :key="v" class="p-2 text-blue-600 dark:text-blue-400">{{ row[v] }}</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Inspector / Right Sidebar -->
            <div class="w-full lg:w-80 lg:shrink-0 h-full border-l dark:border-gray-700 bg-white dark:bg-gray-900 flex flex-col overflow-hidden">
                <div class="flex border-b dark:border-gray-800 shrink-0">
                    <button @click="curIT = 'd'" :class="['flex-1 py-3 text-xs font-black uppercase tracking-wider text-center border-b-2 transition-all', curIT === 'd' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500']">Details</button>
                    <button @click="curIT = 's'" :class="['flex-1 py-3 text-xs font-black uppercase tracking-wider text-center border-b-2 transition-all', curIT === 's' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500']">Style</button>
                    <button @click="curIT = 'ai'" :class="['flex-1 py-3 text-xs font-black uppercase tracking-wider text-center border-b-2 transition-all', curIT === 'ai' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500']">AI Builder</button>
                </div>
                
                <div class="grow overflow-y-auto custom-scrollbar p-4">
                    <!-- Tab: Details -->
                    <div v-if="curIT === 'd'" class="space-y-4">
                        <div v-if="selectedNodeData" class="space-y-4">
                            <h3 class="text-sm font-black uppercase text-gray-400">Node Properties</h3>
                            <div>
                                <label class="text-xs font-semibold">Local Label</label>
                                <input :value="selectedNodeData.label" @input="updateNodeProp('label', $event.target.value)" type="text" class="input-field mt-1 text-sm">
                            </div>
                            <div>
                                <label class="text-xs font-semibold">Base IRI URL</label>
                                <input :value="selectedNodeData.iri" @input="updateNodeProp('iri', $event.target.value)" type="text" class="input-field mt-1 text-xs font-mono">
                            </div>
                            <div>
                                <label class="text-xs font-semibold">Description (rdfs:comment)</label>
                                <textarea :value="selectedNodeData.comment" @input="updateNodeProp('comment', $event.target.value)" rows="3" class="input-field mt-1 text-sm" placeholder="rdfs:comment..."></textarea>
                            </div>

                            <!-- ── [NEW] Manual Relation Connection UI ── -->
                            <div class="pt-4 border-t dark:border-gray-800 space-y-3">
                                <h4 class="text-xs font-black uppercase text-gray-400">Connect to another Node</h4>

                                <div v-if="otherNodesList.length > 0">
                                    <div class="space-y-3">
                                        <div>
                                            <label class="text-[10px] font-bold text-gray-500 uppercase">Target Node</label>
                                            <select v-model="relationTargetId" class="input-field mt-1 text-xs">
                                                <option :value="null" disabled>-- Select Target Node --</option>
                                                <option 
                                                    v-for="node in otherNodesList" 
                                                    :key="node.id" 
                                                    :value="node.id"
                                                >
                                                    {{ node.label }} ({{ node.type }})
                                                </option>
                                            </select>
                                        </div>

                                        <div>
                                            <label class="text-[10px] font-bold text-gray-500 uppercase">Relation Type</label>
                                            <select v-model="relationType" class="input-field mt-1 text-xs">
                                                <option v-for="(color, type) in EDGE_COLORS" :key="type" :value="type">
                                                    {{ type }}
                                                </option>
                                            </select>
                                        </div>

                                        <button 
                                            @click="drawManualRelation" 
                                            :disabled="!relationTargetId"
                                            class="btn btn-primary btn-xs w-full py-1.5 h-8 flex items-center justify-center gap-1.5"
                                        >
                                            <span>Draw Relation Link</span>
                                        </button>
                                    </div>
                                </div>
                                <div v-else class="text-center py-2 text-[10px] text-gray-500 italic">
                                    Add at least one more node to connect them.
                                </div>
                            </div>

                            <div class="pt-4 border-t dark:border-gray-800">
                                <button @click="deleteSelectedElement" class="btn btn-danger btn-xs w-full">Delete Node</button>
                            </div>
                        </div>
                        <div v-else-if="selectedEdgeData" class="space-y-4">
                             <h3 class="text-sm font-black uppercase text-gray-400">Edge Axiom</h3>
                             <div class="p-3 bg-gray-100 dark:bg-gray-800 rounded-lg text-xs space-y-1.5 font-mono">
                                  <div><span class="font-bold text-blue-500">Source:</span> {{ selectedEdgeData.source }}</div>
                                  <div><span class="font-bold text-blue-500">Target:</span> {{ selectedEdgeData.target }}</div>
                                  <div><span class="font-bold text-blue-500">Relation:</span> {{ selectedEdgeData.label }}</div>
                             </div>
                             <div class="pt-4 border-t dark:border-gray-800">
                                <button @click="deleteSelectedElement" class="btn btn-danger btn-xs w-full">Delete Edge Relation</button>
                            </div>
                        </div>
                        <div v-else class="space-y-4">
                            <h3 class="text-sm font-black uppercase text-gray-400">Ontology Settings</h3>
                            <div>
                                <label class="text-xs font-semibold">Ontology Label</label>
                                <input v-model="ontoLabel" type="text" class="input-field mt-1 text-sm" @input="syncOntologyToParams">
                            </div>
                            <div>
                                <label class="text-xs font-semibold">Base IRI Namespace</label>
                                <input v-model="baseIRI" type="text" class="input-field mt-1 text-xs font-mono" @input="syncOntologyToParams">
                            </div>
                            <div>
                                <label class="text-xs font-semibold">Ontology URI</label>
                                <input v-model="ontoIRI" type="text" class="input-field mt-1 text-xs font-mono" @input="syncOntologyToParams">
                            </div>

                            <div class="pt-4 border-t dark:border-gray-800 space-y-3">
                                <h4 class="text-xs font-black uppercase text-gray-400">Import Schema File</h4>
                                <p class="text-[10px] text-gray-500 leading-normal">Load a local Turtle (.ttl), RDF/XML (.rdf), or OWL file to parse and visualize it.</p>
                                <input type="file" ref="owlFileInputRef" class="hidden" accept=".ttl,.owl,.rdf,.xml" @change="handleOWLImport">
                                <button @click="triggerOWLImport" class="btn btn-secondary btn-xs w-full py-1.5 h-8 flex items-center justify-center gap-1.5">
                                    <IconArrowUpTray class="w-4 h-4"/>
                                    <span>Load OWL / Turtle file</span>
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Tab: Visual Customization -->
                    <div v-else-if="curIT === 's'" class="space-y-4">
                        <div v-if="selectedNodeData" class="space-y-4">
                            <h3 class="text-sm font-black uppercase text-gray-400">Style Overrides</h3>
                            
                            <div>
                                <label class="text-xs font-semibold block mb-2">Element Shape</label>
                                <div class="grid grid-cols-4 gap-1.5">
                                    <button v-for="s in SHAPES" :key="s.id" @click="changeNodeShape(s.id)" :class="['p-1.5 border rounded-lg text-[10px] text-center transition-all', selectedNodeData.shape === s.id ? 'border-blue-500 bg-blue-500/10 text-blue-600' : 'border-gray-200 dark:border-gray-700']">
                                        {{ s.label }}
                                    </button>
                                </div>
                            </div>

                            <div>
                                <label class="text-xs font-semibold block mb-2">Palette Colour</label>
                                <div class="flex flex-wrap gap-1.5">
                                    <button v-for="p in PALETTE" :key="p.c" @click="changeNodeColor(p.c, p.bg)" :style="{ backgroundColor: p.c }" :class="['w-6 h-6 rounded-md border-2 transition-all', selectedNodeData.stroke === p.c ? 'border-white scale-110 shadow-md' : 'border-transparent']"></button>
                                </div>
                            </div>
                        </div>
                        <div v-else class="text-center py-20 text-gray-400 italic text-xs">Styles can be overridden per individual node instance.</div>
                    </div>

                    <!-- Tab: AI Ontology Assisted Building -->
                    <div v-else-if="curIT === 'ai'" class="space-y-4">
                        <h3 class="text-sm font-black uppercase text-gray-400">AI Prompt Assistant</h3>
                        <p class="text-xs text-gray-500 leading-relaxed">The AI Builder adds classes, properties, and axioms directly into the workspace from free-text descriptions.</p>
                        <textarea v-model="aiPrompt" rows="5" class="input-field text-sm" placeholder="e.g. Generate an e-commerce model with classes like Order, Customer, and Product and object properties..."></textarea>
                        
                        <button @click="generateAIExtensions" :disabled="isAIGenerating || !aiPrompt.trim()" class="btn btn-primary w-full flex items-center justify-center gap-2 h-9 shadow-lg shadow-blue-500/20">
                            <IconAnimateSpin v-if="isAIGenerating" class="w-4 h-4 animate-spin" />
                            <span>{{ isAIGenerating ? 'Analyzing Concepts...' : 'Extend Ontology' }}</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style>
/* Clean visual defaults for ontology canvas element */
.vis-network {
    outline: none !important;
}
</style>
