<template>
    <div class="w-full h-full relative border dark:border-gray-700 rounded-lg overflow-hidden group isolate select-none">
        <!-- Graph Container -->
        <div ref="networkContainer" class="w-full h-full bg-white dark:bg-gray-900 cursor-grab active:cursor-grabbing outline-none"></div>
        
        <!-- Custom Tooltip -->
        <div v-if="tooltip.visible && tooltip.node" 
             class="absolute pointer-events-none z-50 bg-white dark:bg-gray-800 p-3 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 max-w-sm transition-opacity duration-200 flex flex-col gap-2"
             :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px', transform: 'translate(-50%, -100%)', marginTop: '-15px' }">
            
            <div class="flex items-center gap-2 border-b border-gray-100 dark:border-gray-700 pb-2">
                 <span class="w-3 h-3 rounded-full shrink-0 shadow-sm" :style="{ backgroundColor: tooltip.color }"></span>
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
import { Network } from 'vis-network';
import { useUiStore } from '../../stores/ui';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconPause from '../../assets/icons/IconStopCircle.vue'; 
import IconPlay from '../../assets/icons/IconPlayCircle.vue';

const props = defineProps({
    nodes: { type: Array, default: () => [] },
    edges: { type: Array, default: () => [] },
    isLoading: { type: Boolean, default: false },
    owlSource: { type: String, default: null } // New: Support for OWL direct rendering
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

let cyInstance = null;
let baseIRI = 'http://example.org/onto#';
let ontoIRI = 'http://example.org/onto';
const elements = [];
const importedEntities = {};

const typeStyles = {
  class:      { shape:'ellipse',         fill:'#1a1730', stroke:'#7c6ff7', textColor:'#b3abfa', size:110 },
  property:   { shape:'round-rectangle', fill:'#0e2424', stroke:'#2dd4bf', textColor:'#7de8df', size:130 },
  dataprop:   { shape:'round-rectangle', fill:'#241d0a', stroke:'#fbbf24', textColor:'#fcd34d', size:130 },
  individual: { shape:'ellipse',         fill:'#0e2318', stroke:'#4ade80', textColor:'#86efac', size:110 },
  annprop:    { shape:'diamond',         fill:'#240e1c', stroke:'#f472b6', textColor:'#f9a8d4', size:110 },
};

const EDGE_COLORS = {
  subClassOf:'#7c6ff7', equivalentClass:'#e879f9', disjointWith:'#f87171',
  subPropertyOf:'#2dd4bf', domain:'#fbbf24', range:'#fb923c',
  type:'#4ade80', relation:'#7c8494',
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
  const cfg = typeStyles[type] || typeStyles.class;
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
  return [
    { selector:'node', style:{
        'shape':'data(shape)',
        'width':'data(w)',
        'height':'data(h)',
        'background-color':'data(fill)',
        'border-color':'data(stroke)',
        'border-width':1.5,
        'label':'data(label)',
        'color':'data(textColor)',
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
        'text-background-color':'#0b0d12',
        'text-background-opacity':1,
        'text-background-padding':'3px',
        'font-family':'"DM Sans",sans-serif',
        'edge-text-rotation':'autorotate',
        'min-zoomed-font-size':6,
    }},
    { selector:'edge[dashed]', style:{'line-style':'dashed','line-dash-pattern':[6,3]}},
  ];
}

function cleanName(term) {
  term = (term || '').trim();
  if (term.startsWith('<') && term.endsWith('>')) {
    return term.slice(1, -1).split(/[#/]/).pop();
  }
  term = term.replace(/^[a-zA-Z0-9_-]+:/, '');
  term = term.replace(/[<>]/g, '');
  if (term.startsWith('"') && term.endsWith('"')) {
    return term.slice(1, -1);
  }
  if (term.startsWith('"')) {
    const end = term.lastIndexOf('"');
    if (end > 0) return term.slice(1, end);
  }
  return term;
}

function declareEntity(name, type) {
  name = cleanName(name);
  if (!name) return;
  if (importedEntities[name]) {
    if (type === 'individual' && ['class', 'property', 'dataprop', 'annprop'].includes(importedEntities[name])) {
      return;
    }
  }
  importedEntities[name] = type;
  addNodeImport(type, name);
}

function addNodeImport(type, name) {
  name = cleanName(name);
  const exists = elements.some(el => el.group === 'nodes' && el.data.label === name);
  if (exists) {
    const oldNode = elements.find(el => el.group === 'nodes' && el.data.label === name);
    if (oldNode.data.type === 'individual' && type !== 'individual') {
      const cfg = typeStyles[type] || typeStyles.class;
      const dims = nodeDims(name, type);
      oldNode.data = {
        ...oldNode.data,
        type: type,
        shape: cfg.shape,
        fill: cfg.fill,
        stroke: cfg.stroke,
        textColor: cfg.textColor,
        ...dims
      };
    }
    return oldNode.data.id;
  }
  const id = type + '__' + name.replace(/\W+/g, '_') + '__' + Date.now() + '_' + Math.random().toString(36).slice(2, 5);
  const cfg = typeStyles[type] || typeStyles.class;
  const dims = nodeDims(name, type);
  elements.push({
    group: 'nodes',
    data: {
      id, label: name, type, shape: cfg.shape, fill: cfg.fill, stroke: cfg.stroke, textColor: cfg.textColor,
      iri: baseIRI + name, annotations: {}, ...dims
    }
  });
  return id;
}

function findNid(name) {
  const clean = cleanName(name);
  const n = elements.find(el => el.group === 'nodes' && el.data.label === clean);
  return n ? n.data.id : null;
}

function ensureN(type, name) {
  if (!findNid(name)) declareEntity(name, type);
}

function addEdgeSafe(relType, src, tgt) {
  if (!src || !tgt || src === tgt) return;
  const exists = elements.some(el => el.group === 'edges' && el.data.source === src && el.data.target === tgt && el.data.relType === relType);
  if (exists) return;

  const id = `e__${relType}__${src}__${tgt}__${Date.now()}_${Math.random().toString(36).slice(2, 5)}`;
  const isDashed = ['equivalentClass', 'disjointWith'].includes(relType);
  elements.push({
    group: 'edges',
    data: {
      id, source: src, target: tgt,
      label: relType, relType,
      ec: EDGE_COLORS[relType] || EDGE_COLORS.relation,
      ...(isDashed ? { dashed: true } : {})
    }
  });
}

function sp(s) { return cleanName(s); }
function parseTargets(s) { return s.split(',').map(x => sp(x.trim())).filter(Boolean); }

function parseManchester(text) {
  const lines = text.split('\n');
  let curType = null, curName = null;
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith('Prefix:') || line.startsWith('Ontology:')) continue;
    const cm = line.match(/^Class:\s+(\S+)/);
    const om = line.match(/^ObjectProperty:\s+(\S+)/);
    const dm = line.match(/^DataProperty:\s+(\S+)/);
    const am = line.match(/^AnnotationProperty:\s+(\S+)/);
    const im = line.match(/^Individual:\s+(\S+)/);
    if (cm) { curType = 'class'; curName = sp(cm[1]); declareEntity(curName, 'class'); continue; }
    if (om) { curType = 'property'; curName = sp(om[1]); declareEntity(curName, 'property'); continue; }
    if (dm) { curType = 'dataprop'; curName = sp(dm[1]); declareEntity(curName, 'dataprop'); continue; }
    if (am) { curType = 'annprop'; curName = sp(am[1]); declareEntity(curName, 'annprop'); continue; }
    if (im) { curType = 'individual'; curName = sp(im[1]); declareEntity(curName, 'individual'); continue; }
    if (!curName) continue;
    const srcId = findNid(curName);

    const restriction = line.match(/SubClassOf:\s+(\S+)\s+(some|only|value|min|max|exactly)\s+(\S+)/i);
    if (restriction) {
      const pred = sp(restriction[1]);
      const obj = sp(restriction[3]);
      if (pred && obj) {
        ensureN('class', curName);
        ensureN('class', obj);
        addEdgeSafe(pred, findNid(curName), findNid(obj));
        continue;
      }
    }

    const fa = line.match(/Facts:\s+(.+)/);
    if (fa) {
      const facts = fa[1].split(',');
      facts.forEach(fact => {
        const parts = fact.trim().split(/\s+/);
        if (parts.length >= 2) {
          const pred = sp(parts[0]);
          const obj = sp(parts[1]);
          if (pred && obj) {
            ensureN('individual', curName);
            ensureN('individual', obj);
            addEdgeSafe(pred, findNid(curName), findNid(obj));
          }
        }
      });
      continue;
    }

    const sc = line.match(/SubClassOf:\s+(.+)/), eq = line.match(/EquivalentTo:\s+(.+)/), dj = line.match(/DisjointWith:\s+(.+)/);
    const ty = line.match(/Types:\s+(.+)/), do_ = line.match(/Domain:\s+(.+)/), ra = line.match(/Range:\s+(.+)/);
    const la = line.match(/Annotations:.*rdfs:label\s+"([^"]+)"/), co = line.match(/Annotations:.*rdfs:comment\s+"([^"]+)"/);
    if (sc) parseTargets(sc[1]).forEach(t => { ensureN('class', t); addEdgeSafe('subClassOf', srcId, findNid(t)); });
    if (eq) parseTargets(eq[1]).forEach(t => { ensureN('class', t); addEdgeSafe('equivalentClass', srcId, findNid(t)); });
    if (dj) parseTargets(dj[1]).forEach(t => { ensureN('class', t); addEdgeSafe('disjointWith', srcId, findNid(t)); });
    if (ty) parseTargets(ty[1]).forEach(t => { ensureN('class', t); addEdgeSafe('type', srcId, findNid(t)); });
    if (do_) parseTargets(do_[1]).forEach(t => { ensureN('class', t); addEdgeSafe('domain', srcId, findNid(t)); });
    if (ra) parseTargets(ra[1]).forEach(t => { ensureN('class', t); addEdgeSafe('range', srcId, findNid(t)); });
    if (la) {
      const n2 = elements.find(el => el.group === 'nodes' && el.data.id === srcId);
      if (n2) n2.data.rdfsLabel = la[1];
    }
    if (co) {
      const n2 = elements.find(el => el.group === 'nodes' && el.data.id === srcId);
      if (n2) n2.data.comment = co[1];
    }
  }
}

function parseRDFXML(text) {
  let xmlText = text.replace(/(?:@prefix|PREFIX)\s+[\w-]*:?\s+<[^>]+>\s*\.?/gi, '').trim();

  // Auto-wrap unquoted QName values in attributes (e.g. rdf:about=:Love -> rdf:about=":Love")
  xmlText = xmlText.replace(/(\w+:\w+|\w+)=:([\w-]+)/g, '$1=":$2"');

  // Auto-wrap unquoted resource tags (e.g. <rdfs:domain :Entity> -> <rdfs:domain rdf:resource=":Entity"/>)
  xmlText = xmlText.replace(/<rdfs:(domain|range|subClassOf|subClass)\s+:([\w-]+)\s*>/gi, '<rdfs:$1 rdf:resource=":$2"/>');

  // Wrap in a parent <rdf:RDF> if not present
  if (!xmlText.startsWith('<?xml') && !xmlText.startsWith('<rdf:RDF') && !xmlText.startsWith('<rdf:rdf')) {
      xmlText = `<?xml version="1.0"?>
<rdf:RDF
  xml:base="http://example.org/ontology/love#"
  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
  xmlns:owl="http://www.w3.org/2002/07/owl#">
  ${xmlText}
</rdf:RDF>`;
  }

  const doc = new DOMParser().parseFromString(xmlText, 'application/xml');
  const parserError = doc.querySelector('parsererror');
  if (parserError) {
    throw new Error("XML Syntax Error: " + parserError.textContent);
  }

  const rdfRoot = doc.documentElement;
  const ln = uri => (uri || '').split(/[#/]/).pop();

  function getAttr(el, localName) {
    if (!el) return '';
    const nsRDF = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#';
    return el.getAttributeNS(nsRDF, localName) || 
           el.getAttribute('rdf:' + localName) || 
           el.getAttribute(localName) || 
           '';
  }

  function findElByLocalName(parent, localName) {
    if (!parent) return null;
    if (parent.localName === localName) return parent;
    for (let i = 0; i < parent.children.length; i++) {
      const res = findElByLocalName(parent.children[i], localName);
      if (res) return res;
    }
    return null;
  }

  // Recursively extract rdf:about or rdf:resource from any nested children
  function findNestedURI(el) {
    if (!el) return '';
    let uri = getAttr(el, 'resource') || getAttr(el, 'about');
    if (uri) return uri;
    for (let i = 0; i < el.children.length; i++) {
      const child = el.children[i];
      const childUri = findNestedURI(child);
      if (childUri) return childUri;
    }
    return '';
  }

  function collectDescendants(el, localNames, results = []) {
    if (localNames.includes(el.localName)) {
      results.push(el);
    }
    for (let i = 0; i < el.children.length; i++) {
      collectDescendants(el.children[i], localNames, results);
    }
    return results;
  }

  const children = rdfRoot.children;
  for (let i = 0; i < children.length; i++) {
    const subjectEl = children[i];
    if (subjectEl.localName === 'Ontology') continue;

    const subjectURI = getAttr(subjectEl, 'about') || getAttr(subjectEl, 'ID') || '';
    if (!subjectURI) continue;
    const subject = ln(subjectURI);

    const subjectTypeLocal = subjectEl.localName;
    let type = 'individual';
    if (subjectTypeLocal === 'Class') type = 'class';
    else if (subjectTypeLocal === 'ObjectProperty') type = 'property';
    else if (subjectTypeLocal === 'DatatypeProperty') type = 'dataprop';
    else if (subjectTypeLocal === 'AnnotationProperty') type = 'annprop';
    else if (subjectTypeLocal === 'NamedIndividual') type = 'individual';

    declareEntity(subject, type);

    const properties = subjectEl.children;
    for (let j = 0; j < properties.length; j++) {
      const propEl = properties[j];
      const predicate = propEl.localName;

      const restrictionEl = findElByLocalName(propEl, 'Restriction');
      if (restrictionEl) {
        const onPropEl = findElByLocalName(restrictionEl, 'onProperty');
        const targetEl = findElByLocalName(restrictionEl, 'someValuesFrom') || 
                         findElByLocalName(restrictionEl, 'allValuesFrom') || 
                         findElByLocalName(restrictionEl, 'hasValue');
        if (onPropEl && targetEl) {
          const relType = ln(findNestedURI(onPropEl));
          const targetObj = ln(findNestedURI(targetEl));
          if (relType && targetObj) {
            declareEntity(subject, 'class');
            declareEntity(targetObj, 'class');
            addEdgeSafe(relType, findNid(subject), findNid(targetObj));
            continue;
          }
        }
      }

      const unionEl = findElByLocalName(propEl, 'unionOf') || findElByLocalName(propEl, 'intersectionOf');
      if (unionEl) {
        const listClasses = collectDescendants(unionEl, ['Class', 'Description']);
        listClasses.forEach(clsEl => {
          const classURI = findNestedURI(clsEl);
          if (classURI) {
            const classObj = ln(classURI);
            declareEntity(subject, type);
            declareEntity(classObj, 'class');
            addEdgeSafe(predicate, findNid(subject), findNid(classObj));
          }
        });
        continue;
      }

      let objectURI = getAttr(propEl, 'resource') || getAttr(propEl, 'about') || '';
      if (!objectURI) {
        objectURI = findNestedURI(propEl);
      }

      if (objectURI) {
        const object = ln(objectURI);
        if (predicate === 'subClassOf' || predicate === 'subClass') {
          declareEntity(subject, 'class');
          declareEntity(object, 'class');
          addEdgeSafe('subClassOf', findNid(subject), findNid(object));
        } else if (predicate === 'equivalentClass') {
          declareEntity(subject, 'class');
          declareEntity(object, 'class');
          addEdgeSafe('equivalentClass', findNid(subject), findNid(object));
        } else if (predicate === 'disjointWith') {
          declareEntity(subject, 'class');
          declareEntity(object, 'class');
          addEdgeSafe('disjointWith', findNid(subject), findNid(object));
        } else if (predicate === 'domain') {
          declareEntity(subject, 'property');
          declareEntity(object, 'class');
          addEdgeSafe('domain', findNid(subject), findNid(object));
        } else if (predicate === 'range') {
          declareEntity(subject, 'property');
          declareEntity(object, 'class');
          addEdgeSafe('range', findNid(subject), findNid(object));
        } else if (predicate === 'subPropertyOf') {
          declareEntity(subject, 'property');
          declareEntity(object, 'property');
          addEdgeSafe('subPropertyOf', findNid(subject), findNid(object));
        } else if (predicate === 'type') {
          if (object === 'Class') {
            declareEntity(subject, 'class');
          } else if (object === 'ObjectProperty') {
            declareEntity(subject, 'property');
          } else if (object === 'DatatypeProperty') {
            declareEntity(subject, 'dataprop');
          } else if (object === 'AnnotationProperty') {
            declareEntity(subject, 'annprop');
          } else if (object === 'NamedIndividual') {
            declareEntity(subject, 'individual');
          } else {
            declareEntity(subject, 'individual');
            declareEntity(object, 'class');
            addEdgeSafe('type', findNid(subject), findNid(object));
          }
        } else {
          declareEntity(subject, type);
          declareEntity(object, 'individual');
          addEdgeSafe(predicate, findNid(subject), findNid(object));
        }
      } else {
        const literalVal = propEl.textContent.trim();
        if (literalVal) {
          const node = elements.find(el => el.group === 'nodes' && el.data.id === findNid(subject));
          if (node) {
            if (predicate === 'label') {
              node.data.rdfsLabel = literalVal;
            } else if (predicate === 'comment') {
              node.data.comment = literalVal;
            }
          }
        }
      }
    }
  }
}

function parseTurtle(text) {
  let clean = text.replace(/#.*$/gm, '');

  const prefixes = {};
  const prefixRegex = /(?:@prefix|PREFIX)\s+([\w-]*):?\s+<([^>]+)>\s*\.?/gi;
  let match;
  while ((match = prefixRegex.exec(clean)) !== null) {
    prefixes[match[1] || ''] = match[2];
  }

  clean = clean.replace(/(?:@prefix|PREFIX)\s+[\w-]*:?\s+<[^>]+>\s*\.?/gi, '');

  const tokens = [];
  let currentToken = '';
  let inString = false;
  let inUri = false;

  for (let i = 0; i < clean.length; i++) {
    const char = clean[i];
    if (char === '"' && clean[i-1] !== '\\') {
      inString = !inString;
      currentToken += char;
    } else if (char === '<' && !inString) {
      inUri = true;
      currentToken += char;
    } else if (char === '>' && !inString && inUri) {
      inUri = false;
      currentToken += char;
    } else if (!inString && !inUri && (char === ' ' || char === '\t' || char === '\n' || char === '\r' || char === ';' || char === ',' || char === '.')) {
      if (currentToken.trim()) {
        tokens.push(currentToken.trim());
        currentToken = '';
      }
      if (char === ';' || char === ',' || char === '.') {
        tokens.push(char);
      }
    } else {
      currentToken += char;
    }
  }
  if (currentToken.trim()) {
    tokens.push(currentToken.trim());
  }

  let subject = null;
  let predicate = null;
  let state = 'SUBJECT';

  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i];
    if (token === '.') {
      subject = null;
      predicate = null;
      state = 'SUBJECT';
    } else if (token === ';') {
      predicate = null;
      state = 'PREDICATE';
    } else if (token === ',') {
      state = 'OBJECT';
    } else {
      if (state === 'SUBJECT') {
        subject = token;
        state = 'PREDICATE';
      } else if (state === 'PREDICATE') {
        predicate = token;
        state = 'OBJECT';
      } else if (state === 'OBJECT') {
        const object = token;
        const s = cleanName(subject);
        const p = predicate;
        const o = cleanName(object);

        if (p === 'a' || p === 'rdf:type' || p === '<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>') {
          if (o === 'owl:Class' || o === 'rdfs:Class' || o === 'Class') {
            declareEntity(s, 'class');
          } else if (o === 'owl:ObjectProperty' || o === 'ObjectProperty') {
            declareEntity(s, 'property');
          } else if (o === 'owl:DatatypeProperty' || o === 'DatatypeProperty') {
            declareEntity(s, 'dataprop');
          } else if (o === 'owl:AnnotationProperty' || o === 'AnnotationProperty') {
            declareEntity(s, 'annprop');
          } else if (o === 'owl:NamedIndividual' || o === 'NamedIndividual') {
            declareEntity(s, 'individual');
          } else {
            declareEntity(s, 'individual');
            declareEntity(o, 'class');
            addEdgeSafe('type', findNid(s), findNid(o));
          }
        } else if (p === 'rdfs:subClassOf' || p === 'subClassOf') {
          declareEntity(s, 'class');
          declareEntity(o, 'class');
          addEdgeSafe('subClassOf', findNid(s), findNid(o));
        } else if (p === 'owl:equivalentClass' || p === 'equivalentClass') {
          declareEntity(s, 'class');
          declareEntity(o, 'class');
          addEdgeSafe('equivalentClass', findNid(s), findNid(o));
        } else if (p === 'owl:disjointWith' || p === 'disjointWith') {
          declareEntity(s, 'class');
          declareEntity(o, 'class');
          addEdgeSafe('disjointWith', findNid(s), findNid(o));
        } else if (p === 'rdfs:domain' || p === 'domain') {
          declareEntity(s, 'property');
          declareEntity(o, 'class');
          addEdgeSafe('domain', findNid(s), findNid(o));
        } else if (p === 'rdfs:range' || p === 'range') {
          declareEntity(s, 'property');
          declareEntity(o, 'class');
          addEdgeSafe('range', findNid(s), findNid(o));
        } else if (p === 'rdfs:subPropertyOf' || p === 'subPropertyOf') {
          declareEntity(s, 'property');
          declareEntity(o, 'property');
          addEdgeSafe('subPropertyOf', findNid(s), findNid(o));
        } else if (p === 'rdfs:label' || p === 'label') {
          const node = elements.find(el => el.group === 'nodes' && el.data.id === findNid(s));
          if (node) node.data.rdfsLabel = o;
        } else if (p === 'rdfs:comment' || p === 'comment') {
          const node = elements.find(el => el.group === 'nodes' && el.data.id === findNid(s));
          if (node) node.data.comment = o;
        } else {
          declareEntity(s, 'individual');
          declareEntity(o, 'individual');
          addEdgeSafe(cleanName(p), findNid(s), findNid(o));
        }
      }
    }
  }
}

function parseFunctionalStyle(text) {
  const cleanText = text.split('\n')
    .map(line => line.replace(/#.*$/, ''))
    .join(' ')
    .replace(/\s+/g, ' ');

  const prefixMatches = cleanText.matchAll(/Prefix\s*\(\s*(?:([\w-]*):)?\s*=\s*<([^>]+)>\s*\)/gi);
  for (const match of prefixMatches) {
    const prefix = match[1] || '';
    const iri = match[2];
    if (prefix === '') {
      baseIRI = iri;
      ontoIRI = baseIRI.replace(/#$/, '').replace(/\/$/, '');
    }
  }

  function extractEntity(str) {
    if (!str) return null;
    str = str.trim();
    if (str.includes('ObjectUnionOf') || str.includes('ObjectSomeValuesFrom') || str.includes('ObjectAllValuesFrom') || str.includes('ObjectIntersectionOf')) {
      return null;
    }
    if (str.startsWith('<') && str.endsWith('>')) {
      const iri = str.slice(1, -1);
      return iri.split(/[#/]/).pop();
    }
    if (str.includes(':')) {
      const parts = str.split(':');
      if (parts[0] === 'owl' || parts[0] === 'xsd' || parts[0] === 'rdfs' || parts[0] === 'rdf') {
        return str;
      }
      return parts[1];
    }
    return str.replace(/[()]/g, '').trim();
  }

  function parseUnionOf(str) {
    const classes = [];
    if (!str || typeof str !== 'string') return classes;
    const unionMatch = str.match(/ObjectUnionOf\(([^)]+(?:\([^)]*\)[^)]*)*)\)/i);
    if (unionMatch) {
      const inner = unionMatch[1];
      const entityRegex = /<([^>]+)>|(\w+):([\w-]+)|([\w-]+)/g;
      let entityMatch;
      while ((entityMatch = entityRegex.exec(inner)) !== null) {
        let ent = null;
        if (entityMatch[1]) {
          ent = entityMatch[1].split(/[#/]/).pop();
        } else if (entityMatch[2] && entityMatch[3]) {
          if (!['owl', 'xsd'].includes(entityMatch[2])) {
            ent = entityMatch[2] + ':' + entityMatch[3];
          }
        } else if (entityMatch[4]) {
          ent = entityMatch[4].trim();
        }
        if (ent && ent.length > 0 && ent !== 'ObjectUnionOf' && ent !== 'owl:Thing' && ent !== 'owl:Nothing') {
          classes.push(ent);
        }
      }
    }
    return classes;
  }

  function parseSomeValuesFrom(str) {
    const match = str.match(/ObjectSomeValuesFrom\(\s*(?:ObjectProperty\s*\(\s*([^\s()]+)\s*\)\s*|([^\s()]+))\s+(?:owl:Thing|owl:Nothing|Class\(\s*([^\s()]+)\s*\)|([^\s()]+))\s*\)/i);
    if (match) {
      const prop = extractEntity(match[1] || match[2]);
      const target = extractEntity(match[3] || match[4]);
      return { prop, target };
    }
    return null;
  }

  function parseDisjointClasses(str) {
    const classes = [];
    if (!str || typeof str !== 'string') return classes;
    const disjointMatch = str.match(/DisjointClasses\(([^)]+(?:\([^)]*\)[^)]*)*)\)/i);
    if (disjointMatch) {
      const inner = disjointMatch[1];
      const entityRegex = /<([^>]+)>|(\w+):(\w+)|([\w-]+)/g;
      let entityMatch;
      while ((entityMatch = entityRegex.exec(inner)) !== null) {
        let ent = null;
        if (entityMatch[1]) {
          ent = entityMatch[1].split(/[#/]/).pop();
        } else if (entityMatch[2] && entityMatch[3]) {
          if (!['owl', 'rdfs', 'rdf', 'xsd'].includes(entityMatch[2])) {
            ent = entityMatch[3];
          }
        } else if (entityMatch[4]) {
          ent = entityMatch[4].trim();
        }
        if (ent && ent.length > 0 && ent !== 'owl:Thing' && ent !== 'DisjointClasses') {
          classes.push(ent);
        }
      }
    }
    return classes;
  }

  const declRegex = /Declaration\(\s*(Class|ObjectProperty|DataProperty|AnnotationProperty|NamedIndividual)\(\s*([^\s()]+)\s*\)\s*\)/gi;
  let declMatch;
  while ((declMatch = declRegex.exec(cleanText)) !== null) {
    const typeMap = {
      class: 'class',
      objectproperty: 'property',
      dataproperty: 'dataprop',
      annotationproperty: 'annprop',
      namedindividual: 'individual'
    };
    const rawType = declMatch[1].toLowerCase();
    const type = typeMap[rawType];
    const name = sp(declMatch[2]);
    if (type && name) {
      addNodeImport(type, name);
    }
  }

  const subClassRegex = /SubClassOf\(\s*(?:Class\()?([^\s()]+)\)?\s+([^)]+(?:\([^)]*\)[^)]*)*)\s*\)/gi;
  let subMatch;
  while ((subMatch = subClassRegex.exec(cleanText)) !== null) {
    const child = extractEntity(subMatch[1]);
    const parentExpr = subMatch[2];

    if (child) {
      const unionClasses = parseUnionOf(parentExpr);
      if (unionClasses.length > 0) {
        unionClasses.forEach(pc => {
          ensureN('class', pc);
          addEdgeSafe('subClassOf', findNid(child), findNid(pc));
        });
        continue;
      }

      const restriction = parseSomeValuesFrom(parentExpr);
      if (restriction && restriction.prop && restriction.target) {
        ensureN('class', child);
        ensureN('class', restriction.target);
        ensureN('property', restriction.prop);
        addEdgeSafe(restriction.prop, findNid(child), findNid(restriction.target));
        continue;
      }

      if (parentExpr.includes('ObjectUnionOf') || parentExpr.includes('ObjectSomeValuesFrom') || parentExpr.includes('ObjectAllValuesFrom')) {
        continue;
      }

      const parent = extractEntity(parentExpr);
      if (parent && parent !== 'owl:Thing' && parent.length < 50) {
        ensureN('class', child);
        ensureN('class', parent);
        addEdgeSafe('subClassOf', findNid(child), findNid(parent));
      }
    }
  }

  const eqClassRegex = /EquivalentClasses\(\s*(?:Class\()?([^\s()]+)\)?\s+([^)]+(?:\([^)]*\)[^)]*)*)\s*\)/gi;
  let eqMatch;
  while ((eqMatch = eqClassRegex.exec(cleanText)) !== null) {
    const c1 = extractEntity(eqMatch[1]);
    const expr = eqMatch[2];

    if (c1) {
      const unionClasses = parseUnionOf(expr);
      if (unionClasses.length > 0) {
        ensureN('class', c1);
        unionClasses.forEach(uc => {
          ensureN('class', uc);
          addEdgeSafe('equivalentClass', findNid(c1), findNid(uc));
        });
        continue;
      }

      const c1UnionCheck = parseUnionOf(eqMatch[1]);
      if (c1UnionCheck.length > 0) {
        const c2 = extractEntity(expr);
        if (c2) {
          ensureN('class', c2);
          c1UnionCheck.forEach(uc => {
            ensureN('class', uc);
            addEdgeSafe('equivalentClass', findNid(uc), findNid(c2));
          });
          continue;
        }
      }

      if (expr.includes('ObjectUnionOf') || expr.includes('ObjectSomeValuesFrom')) {
        continue;
      }

      const c2 = extractEntity(expr);
      if (c2 && c2 !== c1 && c2.length < 50) {
        ensureN('class', c1);
        ensureN('class', c2);
        addEdgeSafe('equivalentClass', findNid(c1), findNid(c2));
      }
    }
  }

  const disjointWithRegex = /DisjointClasses\(([^)]+(?:\([^)]*\)[^)]*)*)\)/gi;
  let djMatch;
  while ((djMatch = disjointWithRegex.exec(cleanText)) !== null) {
    const classes = parseDisjointClasses(djMatch[0]);
    for (let i = 0; i < classes.length; i++) {
      for (let j = i + 1; j < classes.length; j++) {
        ensureN('class', classes[i]);
        ensureN('class', classes[j]);
        addEdgeSafe('disjointWith', findNid(classes[i]), findNid(classes[j]));
      }
    }
  }

  const classAssertRegex = /ClassAssertion\(\s*(?:Class\()?([^\s()]+)\)?\s+(?:NamedIndividual\()?([^\s()]+)\)?\s*\)/gi;
  let caMatch;
  while ((caMatch = classAssertRegex.exec(cleanText)) !== null) {
    const cls = extractEntity(caMatch[1]);
    const ind = extractEntity(caMatch[2]);
    if (cls && ind) {
      ensureN('class', cls);
      ensureN('individual', ind);
      addEdgeSafe('type', findNid(ind), findNid(cls));
    }
  }

  const opDomainRegex = /ObjectPropertyDomain\(\s*(?:ObjectProperty\()?([^\s()]+)\)?\s+(?:Class\()?([^\s()]+)\)?\s*\)/gi;
  let opdMatch;
  while ((opdMatch = opDomainRegex.exec(cleanText)) !== null) {
    const prop = extractEntity(opdMatch[1]);
    const cls = extractEntity(opdMatch[2]);
    if (prop && cls) {
      ensureN('property', prop);
      ensureN('class', cls);
      addEdgeSafe('domain', findNid(prop), findNid(cls));
    }
  }

  const opRangeRegex = /ObjectPropertyRange\(\s*(?:ObjectProperty\()?([^\s()]+)\)?\s+([^)]+(?:\([^)]*\)[^)]*)*)\s*\)/gi;
  let oprMatch;
  while ((oprMatch = opRangeRegex.exec(cleanText)) !== null) {
    const prop = extractEntity(oprMatch[1]);
    const rangeExpr = oprMatch[2];

    if (prop) {
      const unionClasses = parseUnionOf(rangeExpr);
      if (unionClasses.length > 0) {
        ensureN('property', prop);
        unionClasses.forEach(uc => {
          ensureN('class', uc);
          addEdgeSafe('range', findNid(prop), findNid(uc));
        });
        continue;
      }

      if (rangeExpr.includes('ObjectUnionOf') || rangeExpr.includes('ObjectSomeValuesFrom')) {
        continue;
      }

      const cls = extractEntity(rangeExpr);
      if (cls && cls.length < 50) {
        ensureN('property', prop);
        ensureN('class', cls);
        addEdgeSafe('range', findNid(prop), findNid(cls));
      }
    }
  }

  const dpDomainRegex = /DataPropertyDomain\(\s*(?:DataProperty\()?([^\s()]+)\)?\s+(?:Class\()?([^\s()]+)\)?\s*\)/gi;
  let dpdMatch;
  while ((dpdMatch = dpDomainRegex.exec(cleanText)) !== null) {
    const prop = extractEntity(dpdMatch[1]);
    const cls = extractEntity(dpdMatch[2]);
    if (prop && cls) {
      ensureN('dataprop', prop);
      ensureN('class', cls);
      addEdgeSafe('domain', findNid(prop), findNid(cls));
    }
  }

  const dpRangeRegex = /DataPropertyRange\(\s*(?:DataProperty\()?([^\s()]+)\)?\s+(?:Datatype\()?([^\s()]+)\)?\s*\)/gi;
  let dprMatch;
  while ((dprMatch = dpRangeRegex.exec(cleanText)) !== null) {
    const prop = extractEntity(dprMatch[1]);
    if (prop) {
      ensureN('dataprop', prop);
    }
  }

  const subPropRegex = /SubObjectPropertyOf\(\s*(?:ObjectProperty\()?([^\s()]+)\)?\s+(?:ObjectProperty\()?([^\s()]+)\)?\s*\)/gi;
  let sopMatch;
  while ((sopMatch = subPropRegex.exec(cleanText)) !== null) {
    const subP = extractEntity(sopMatch[1]);
    const superP = extractEntity(sopMatch[2]);
    if (subP && superP) {
      ensureN('property', subP);
      ensureN('property', superP);
      addEdgeSafe('subPropertyOf', findNid(subP), findNid(superP));
    }
  }

  const opAssertRegex = /ObjectPropertyAssertion\(\s*(?:ObjectProperty\()?([^\s()]+)\)?\s+(?:NamedIndividual\()?([^\s()]+)\)?\s+(?:NamedIndividual\()?([^\s()]+)\)?\s*\)/gi;
  let opaMatch;
  while ((opaMatch = opAssertRegex.exec(cleanText)) !== null) {
    const prop = extractEntity(opaMatch[1]);
    const src = extractEntity(opaMatch[2]);
    const tgt = extractEntity(opaMatch[3]);
    if (prop && src && tgt) {
      ensureN('individual', src);
      ensureN('individual', tgt);
      addEdgeSafe(prop, findNid(src), findNid(tgt));
    }
  }

  const sameIndRegex = /SameIndividual\(([^)]+)\)/gi;
  let siMatch;
  while ((siMatch = sameIndRegex.exec(cleanText)) !== null) {
    const inner = siMatch[1];
    const individuals = inner.match(/(<[^>]+>|[\w-]+)/g) || [];
    const extracted = individuals.map(extractEntity).filter(e => e);
    for (let i = 0; i < extracted.length; i++) {
      for (let j = i + 1; j < extracted.length; j++) {
        ensureN('individual', extracted[i]);
        ensureN('individual', extracted[j]);
        addEdgeSafe('sameAs', findNid(extracted[i]), findNid(extracted[j]));
      }
    }
  }

  const diffIndRegex = /DifferentIndividuals\(([^)]+)\)/gi;
  let diMatch;
  while ((diMatch = diffIndRegex.exec(cleanText)) !== null) {
    const inner = diMatch[1];
    const individuals = inner.match(/(<[^>]+>|[\w-]+)/g) || [];
    const extracted = individuals.map(extractEntity).filter(e => e);
    for (let i = 0; i < extracted.length; i++) {
      for (let j = i + 1; j < extracted.length; j++) {
        ensureN('individual', extracted[i]);
        ensureN('individual', extracted[j]);
        addEdgeSafe('differentFrom', findNid(extracted[i]), findNid(extracted[j]));
      }
    }
  }

  const annRegex = /AnnotationAssertion\(\s*(?:AnnotationProperty\()?([^\s()]+)\)?\s+(?:rdfs:label|rdfs:comment|[\w:]+)\s+(?:<[^>]+>|[\w:]+)\s+"([^"]+)"(?:@[a-zA-Z-]+)?\s*\)/gi;
  let annMatch;
  while ((annMatch = annRegex.exec(cleanText)) !== null) {
    const prop = extractEntity(annMatch[1]);
    const annFullRegex = /AnnotationAssertion\(\s*(?:AnnotationProperty\()?([^\s()]+)\)?\s+(?:rdfs:label|rdfs:comment|[\w:]*)?\s*(?:<([^>]+)>|([\w:]+))\s+"([^"]+)"(?:@[a-zA-Z-]+)?\s*\)/gi;
    const fullMatch = annFullRegex.exec(annMatch[0]);
    if (fullMatch) {
      const subjectIRI = fullMatch[2] || fullMatch[3];
      const subject = extractEntity(subjectIRI ? '<' + subjectIRI + '>' : subjectIRI);
      const annotationVal = fullMatch[4];

      const nid = findNid(subject);
      if (nid) {
        const node = elements.find(el => el.group === 'nodes' && el.data.id === nid);
        if (node) {
          const propLower = prop.toLowerCase();
          if (propLower === 'label' || propLower === 'rdfs:label') {
            node.data.rdfsLabel = annotationVal;
          } else if (propLower === 'comment' || propLower === 'rdfs:comment') {
            node.data.comment = annotationVal;
          }
        }
      }
    }
  }

  const annIRIRegex = /AnnotationAssertion\(\s*(?:AnnotationProperty\()?(rdfs:label|rdfs:comment)\)?\s+<([^>]+)>\s+"([^"]+)"(?:@[a-zA-Z-]+)?\s*\)/gi;
  let annIRIMatch;
  while ((annIRIMatch = annIRIRegex.exec(cleanText)) !== null) {
    const prop = annIRIMatch[1];
    const subjectIRI = annIRIMatch[2];
    const val = annIRIMatch[3];
    const subject = subjectIRI.split(/[#/]/).pop();

    const nid = findNid(subject);
    if (nid) {
      const node = elements.find(el => el.group === 'nodes' && el.data.id === nid);
      if (node) {
        if (prop.toLowerCase().includes('label')) {
          node.data.rdfsLabel = val;
        } else if (prop.toLowerCase().includes('comment')) {
          node.data.comment = val;
        }
      }
    }
  }
}

function autoDetectFormat(text) {
  const clean = text.trim();
  const lower = clean.toLowerCase();
  if (clean.startsWith('<?xml') || clean.includes('<rdf:RDF') || clean.includes('<owl:Ontology')) {
    return 'rdfxml';
  }
  if (lower.includes('@prefix') || lower.includes('prefix ') || lower.includes('base ') || clean.match(/a\s+owl:Ontology/i) || clean.match(/a\s+owl:Class/i) || clean.match(/a\s+owl:NamedIndividual/i)) {
    return 'turtle';
  }
  if (clean.match(/Prefix\s*\(/i) || clean.match(/Ontology\s*\(/i) || clean.match(/Declaration\s*\(/i)) {
    return 'functional';
  }
  return 'manchester';
}

function importOntology(text) {
  const fmt = autoDetectFormat(text);
  if (fmt === 'manchester') parseManchester(text);
  else if (fmt === 'rdfxml') parseRDFXML(text);
  else if (fmt === 'turtle') parseTurtle(text);
  else if (fmt === 'functional') parseFunctionalStyle(text);
}

async function renderOwlSource(sourceText) {
    if (!networkContainer.value) return;

    if (network) {
        network.destroy();
        network = null;
    }

    if (cyInstance) {
        cyInstance.destroy();
        cyInstance = null;
    }

    const cyMod = await loadCytoscape();

    // Clear and reset the parser state
    elements.length = 0;
    Object.keys(importedEntities).forEach(key => delete importedEntities[key]);

    try {
        importOntology(sourceText);
    } catch (e) {
        console.error("Failed to parse ontology:", e);
    }

    cyInstance = cyMod({
        container: networkContainer.value,
        style: buildCyStyle(),
        elements: elements,
        layout: { name: 'cose', padding: 30 },
        minZoom: 0.1,
        maxZoom: 5
    });

    if (elements.length > 0) {
        cyInstance.layout({
            name: 'cose',
            animate: true,
            animationDuration: 400,
            padding: 40,
            nodeRepulsion: 45000,
            idealEdgeLength: 100,
        }).run();
    }
}

function initializeOrUpdateGraph() {
    // CRITICAL GUARD: Ensure the container exists in the DOM
    if (!networkContainer.value || !networkContainer.value.offsetParent) return;

    // --- MODE 1: OWL Source Provided (Ontology Preview) ---
    if (props.owlSource) {
         // This logic remains similar to standard graph but we 
         // might want different visualization defaults for schema definitions.
         renderOwlSource(props.owlSource);
         return;
    }

    // --- MODE 2: Standard Graph Data (Knowledge explorer) ---
    const isDark = uiStore.currentTheme === 'dark';

    const data = {
        nodes: props.nodes.map(n => {
            const nodeType = n.label;
            const nodeLabel = String(n.properties?.identifying_value || n.properties?.name || n.properties?.label || n.label || n.id);
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
        edges: props.edges.map(e => {
            // Robustly find source/target keys from potential backend variations
            const source = e.source ?? e.source_id ?? e.from ?? e.start ?? e.start_node_id;
            const target = e.target ?? e.target_id ?? e.to ?? e.end ?? e.end_node_id;
            
            return { 
                id: e.id,
                from: String(source),
                to: String(target),
                label: e.label || e.type || '',
                properties: e.properties
            };
        }).filter(e => e.from && e.to && e.from !== 'undefined' && e.to !== 'undefined')
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
    if (cyInstance) {
        cyInstance.destroy();
        cyInstance = null;
    }
});

function focusNode(nodeId) {
    if (network) {
        network.focus(String(nodeId), {
            scale: 1.2,
            animation: { duration: 1000, easingFunction: 'easeInOutQuad' }
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

defineExpose({ resetView });

</script>

<style scoped>
/* Ensure the container handles z-indexing correctly */
:deep(.vis-network) {
    outline: none;
}
</style>
