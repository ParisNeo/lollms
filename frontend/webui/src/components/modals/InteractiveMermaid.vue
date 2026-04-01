<template>
  <!-- Fullscreen Teleport Overlay -->
  <Teleport to="body">
    <div
      v-if="isFullscreen"
      class="fixed inset-0 z-[9999] bg-gray-950 flex flex-col"
      @keydown.esc="isFullscreen = false"
      tabindex="-1"
      ref="fullscreenOverlayRef"
    >
      <!-- Fullscreen toolbar -->
      <div class="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-700 flex-shrink-0">
        <span class="text-xs font-semibold text-gray-300">{{ detectedTypeLabel || 'Mermaid Diagram' }} — Fullscreen</span>
        <div class="flex items-center gap-2">
          <button @click="showSource = !showSource" class="px-3 py-1 text-xs rounded bg-gray-700 hover:bg-gray-600 text-gray-200 font-medium transition-colors">
            {{ showSource ? 'Hide Source' : 'View Source' }}
          </button>
          <button @click="exportSVG()" class="px-3 py-1 text-xs rounded bg-blue-600 hover:bg-blue-700 text-white font-semibold transition-colors">SVG</button>
          <button @click="exportPNG()" class="px-3 py-1 text-xs rounded bg-green-600 hover:bg-green-700 text-white font-semibold transition-colors">PNG</button>
          <button @click="isFullscreen = false" class="px-3 py-1 text-xs rounded bg-red-600 hover:bg-red-700 text-white font-semibold transition-colors flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
            Close
          </button>
        </div>
      </div>
      <!-- Fullscreen body: source pane + diagram -->
      <div class="flex flex-1 min-h-0">
        <!-- Source pane -->
        <div v-if="showSource" class="w-96 flex-shrink-0 bg-gray-950 border-r border-gray-700 overflow-auto">
          <pre class="text-xs text-green-300 p-4 leading-relaxed whitespace-pre-wrap">{{ mermaidCode }}</pre>
        </div>
        <!-- Diagram pane — solid dark background so SVG renders correctly -->
        <div class="mermaid-fullscreen-pane flex-1 relative min-w-0 bg-gray-950">
          <div ref="fullscreenMountRef" class="w-full h-full mermaid-container"></div>
          <div v-if="fullscreenError" class="absolute inset-0 flex items-center justify-center">
            <div class="bg-red-900/80 text-red-200 text-xs p-4 rounded-lg max-w-lg">{{ fullscreenError }}</div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Normal inline viewer -->
  <div ref="wrapperRef" class="w-full h-full relative bg-gray-50 dark:bg-gray-800/50 overflow-hidden">
    <div ref="mountRef" class="w-full h-full mermaid-container"></div>

    <!-- Top-left: diagram type label -->
    <div v-if="detectedTypeLabel" class="absolute top-3 left-3 px-2 py-1 text-xs rounded-md bg-black/10 dark:bg-white/10 text-gray-800 dark:text-gray-100 backdrop-blur-sm pointer-events-none z-10">
      {{ detectedTypeLabel }}
    </div>

    <!-- Top-right: action buttons (always visible so you can access source even on error) -->
    <div class="absolute top-3 right-3 flex gap-1.5 z-20">
      <!-- AI Refinement Trigger -->
      <button
        @click="showRefinement = !showRefinement"
        class="px-2.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded shadow-md transition-colors flex items-center gap-1"
        title="Edit diagram with AI"
      >
        <IconSparkles class="h-3.5 w-3.5" />
        <span>AI Edit</span>
      </button>

      <!-- View Source toggle -->
      <button
        @click="showSource = !showSource"
        class="px-2.5 py-1.5 bg-gray-600 hover:bg-gray-700 text-white text-xs font-semibold rounded shadow-md transition-colors flex items-center gap-1"
        title="View / hide mermaid source"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
        </svg>
        {{ showSource ? 'Hide' : 'Code' }}
      </button>
      <!-- Fullscreen -->
      <button
        @click="openFullscreen"
        class="px-2.5 py-1.5 bg-gray-600 hover:bg-gray-700 text-white text-xs font-semibold rounded shadow-md transition-colors flex items-center gap-1"
        title="Open fullscreen"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5"/>
        </svg>
        Fullscreen
      </button>
      <!-- Export buttons — only when rendered successfully -->
      <template v-if="isInteractive">
        <button @click="exportSVG()" class="px-2.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded shadow-md transition-colors flex items-center gap-1" title="Save as SVG">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
          SVG
        </button>
        <button @click="exportPNG()" class="px-2.5 py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-semibold rounded shadow-md transition-colors flex items-center gap-1" title="Save as PNG">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
          PNG
        </button>
      </template>
    </div>

    <!-- AI Refinement Overlay -->
    <div v-if="showRefinement" class="absolute inset-x-0 top-0 z-30 p-3 animate-in fade-in slide-in-from-top-2">
        <div class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl border-2 border-blue-500 p-3 space-y-3">
            <div class="flex justify-between items-center">
                <span class="text-[10px] font-black uppercase tracking-widest text-blue-500">AI Refinement</span>
                <button @click="showRefinement = false" class="text-gray-400 hover:text-red-500"><IconXMark class="w-4 h-4"/></button>
            </div>
            <textarea 
                v-model="refinementInstruction" 
                placeholder="How should I change this diagram? (e.g. 'Add a database node', 'Make it top-down')"
                class="w-full text-xs input-field h-20 resize-none"
                @keyup.enter.ctrl="handleRefinement"
            ></textarea>
            <div class="flex justify-end">
                <button @click="handleRefinement" class="btn btn-primary btn-xs py-1.5 px-4 flex items-center gap-2" :disabled="!refinementInstruction.trim() || isProcessing">
                    <IconAnimateSpin v-if="isProcessing" class="w-3.5 h-3.5 animate-spin" />
                    <IconSend v-else class="w-3.5 h-3.5" />
                    <span>Update Diagram</span>
                </button>
            </div>
        </div>
    </div>

    <!-- Source overlay (inline) -->
    <div v-if="showSource" class="absolute inset-0 z-25 bg-gray-950/97 overflow-auto">
      <pre class="text-xs text-green-300 p-4 leading-relaxed whitespace-pre-wrap">{{ mermaidCode }}</pre>
    </div>

    <!-- Pan/zoom hint -->
    <div v-if="isInteractive && !showSource" class="absolute left-3 bottom-3 text-xs text-gray-600 dark:text-gray-400 flex items-center gap-1.5 z-10 px-2 py-1 rounded-md bg-white/50 dark:bg-black/50 backdrop-blur-sm pointer-events-none">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5"/>
      </svg>
      <span>Pan & Zoom</span>
    </div>

    <!-- Error display -->
    <div v-if="errorMessage && !showSource" class="absolute inset-0 flex items-center justify-center pointer-events-none z-30">
      <div class="pointer-events-auto bg-white/95 dark:bg-gray-900/95 border border-red-300 dark:border-red-700 rounded-lg p-4 max-w-2xl mx-4 shadow-2xl">
        <div class="flex items-start gap-3">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-7 w-7 text-red-500 flex-none mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M12 9v4m0 4h.01"/>
          </svg>
          <div class="flex-1 min-w-0">
            <div class="text-sm font-semibold text-red-800 dark:text-red-200 mb-1">Mermaid Rendering Error</div>
            <pre class="text-xs text-red-700 dark:text-red-400 whitespace-pre-wrap max-h-40 overflow-auto p-2 bg-red-50 dark:bg-red-900/20 rounded-md">{{ errorMessage }}</pre>
            <div class="mt-3 flex flex-wrap gap-2">
              <button @click="handleAiFix" :disabled="isProcessing" class="px-3 py-1 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold shadow-sm flex items-center gap-2 transition-all active:scale-95">
                <IconAnimateSpin v-if="isProcessing" class="w-3 h-3 animate-spin" />
                <IconSparkles v-else class="w-3 h-3" />
                Fix with AI
              </button>
              <button @click="copyErrorMessage" class="px-3 py-1 rounded-md bg-red-600/20 hover:bg-red-600/30 text-red-600 dark:text-red-400 text-xs font-medium">{{ errorCopyLabel }}</button>
              <button @click="showProcessed = !showProcessed" class="px-3 py-1 rounded-md bg-gray-600/20 hover:bg-gray-600/30 text-gray-600 dark:text-gray-400 text-xs font-medium">
                {{ showProcessed ? 'Hide' : 'Show' }} Processed Code
              </button>
              <button @click="showSource = true" class="px-3 py-1 rounded-md bg-gray-600/20 hover:bg-gray-600/30 text-gray-600 dark:text-gray-400 text-xs font-medium">
                View Raw Source
              </button>
            </div>
            <pre v-if="showProcessed" class="mt-2 text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap max-h-64 overflow-auto p-2 bg-gray-100 dark:bg-gray-800 rounded-md">{{ lastProcessedCode }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import mermaid from 'mermaid'
import svgPanZoom from 'svg-pan-zoom'
import { useUiStore } from '../../stores/ui'
import { useDiscussionsStore } from '../../stores/discussions'
import { Canvg } from 'canvg'
import IconSparkles from '../../assets/icons/IconSparkles.vue'
import IconSend from '../../assets/icons/IconSend.vue'
import IconXMark from '../../assets/icons/IconXMark.vue'

const props = defineProps({
  mermaidCode: { type: String, required: true },
  messageId: { type: String, default: null } // Link to context if available
})

const emit = defineEmits(['error', 'ready', 'refine'])

const wrapperRef = ref(null)
const mountRef = ref(null)
const fullscreenMountRef = ref(null)
const fullscreenOverlayRef = ref(null)
let panZoomInstance = null
let resizeObserver = null
const uiStore = useUiStore()

const errorMessage = ref('')
const errorCopyLabel = ref('Copy Error Message')
const detectedType = ref('')
const isInteractive = ref(false)
const lastProcessedCode = ref('')
const showProcessed = ref(false)
const showSource = ref(false)
const isFullscreen = ref(false)
const fullscreenError = ref('')
const showRefinement = ref(false)
const refinementInstruction = ref('')
const isProcessing = ref(false)
const discussionsStore = useDiscussionsStore()

async function handleAiFix() {
    if (isProcessing.value) return;
    
    isProcessing.value = true;
    try {
        const prompt = `The Mermaid diagram code you provided has syntax errors and failed to render.
**Error from Parser:**
${errorMessage.value}

**Problematic Code:**
\`\`\`mermaid
${props.mermaidCode}
\`\`\`

**Instructions:**
1. Fix all syntax errors (check for nested quotes, unescaped brackets, or reserved words).
2. Ensure labels with special characters (like quotes or question marks) are correctly wrapped in [" "].
3. Return ONLY the corrected code block.`;

        await discussionsStore.sendMessage({
            prompt: prompt,
            parent_message_id: props.messageId,
            is_resend: false
        });
        
        uiStore.addNotification("Repairing diagram via AI...", "info");
    } finally {
        isProcessing.value = false;
    }
}

async function handleRefinement() {
    if (!refinementInstruction.value.trim() || isProcessing.value) return;
    
    isProcessing.value = true;
    try {
        // Send a targeted prompt to the AI
        const prompt = `Please update this Mermaid diagram based on the following instruction: "${refinementInstruction.value}"
Current Mermaid Code:
\`\`\`mermaid
${props.mermaidCode}
\`\`\`
Return only the updated mermaid code block.`;

        await discussionsStore.sendMessage({
            prompt: prompt,
            parent_message_id: props.messageId,
            is_resend: false // This will create a new turn refining the diagram
        });
        
        showRefinement.value = false;
        refinementInstruction.value = '';
    } finally {
        isProcessing.value = false;
    }
}

const getBaseMermaidConfig = (theme) => ({
  startOnLoad: false,
  securityLevel: 'loose',
  theme,
  themeVariables: { fontSize: '15px' }
})

const detectedTypeLabel = computed(() => {
  if (!detectedType.value) return ''
  return `Mermaid: ${detectedType.value.charAt(0).toUpperCase()}${detectedType.value.slice(1)}`
})

function cleanup() {
  isInteractive.value = false
  showProcessed.value = false
  if (panZoomInstance) { panZoomInstance.destroy(); panZoomInstance = null }
  if (resizeObserver) { resizeObserver.disconnect(); resizeObserver = null }
  if (mountRef.value) mountRef.value.innerHTML = ''
}

// ─────────────────────────────────────────────────────────────────────────────
// processMermaidCode — THE KEY FIX IS alreadyQuoted() guard in step 7
// ─────────────────────────────────────────────────────────────────────────────
function processMermaidCode(code) {
  if (!code) return code

  // 1. Strip fences and basic cleanup
  let processed = code.replace(/^```mermaid\n?|```$/g, '')
  
  // 1.1 Aggressive Sanitization: Fix triple quotes and multi-quotes
  processed = processed.replace(/"{3,}/g, '"')
  processed = processed.replace(/'{3,}/g, "'")

  processed = processed.split('\n').map(l => l.trimEnd()).join('\n')

  // 2. Fix subgraph quoted titles → unquoted
  processed = processed.replace(
    /^(\s*subgraph\s+\w*\s*)\[["'](.+?)["']\]/gm,
    '$1[$2]'
  )

  // 3. Strip stroke-dasharray from classDef (unquoted spaces break parser)
  processed = processed.replace(/,?\s*stroke-dasharray:\s*[^,;}]+/gm, '')

  // 4. Move :::class from INSIDE brackets to OUTSIDE
  processed = processed.replace(/(\[["']?)([^[\]"']*?)(:::[\w-]+)(["']?\])/g, '$1$2$4$3')
  processed = processed.replace(/\((["']?)([^()"']*?)(:::[\w-]+)(["']?)\)/g, '($1$2$4)$3')

  // 5. Remove trailing hallucinated brackets after :::class
  processed = processed.replace(/(:::[a-zA-Z0-9_-]+)[)\]\s]+$/gm, '$1')
  
  // 5.1 Fix labels containing unescaped parentheses which break mermaid
  processed = processed.replace(/\[(.*?\s?\(.*?\).*?)\]/g, '["$1"]')

  // 6. Line-by-line normalization — only for nodes with UNQUOTED labels outside subgraphs
  const reserved = new Set([
    'flowchart','graph','subgraph','end','classdef','click','style','direction',
    'class','statediagram','sequencediagram','pie','gantt','erdiagram',
    'journey','gitgraph','mindmap','timeline','linkstyle'
  ])

  const skipLine = (t) =>
    t.startsWith('%%') ||
    t.startsWith('classDef') ||
    t.startsWith('class ') ||
    t.startsWith('subgraph') ||
    t.startsWith('end') ||
    t.startsWith('direction') ||
    t.startsWith('linkStyle') ||
    t.startsWith('style ') ||
    t.startsWith('click ')

  const alreadyQuoted = (line) => /[A-Za-z0-9_]+\s*[\[\(\{]{1,3}["']/.test(line)

  const isPureEdge = (t) =>
    /^[A-Za-z0-9_]+\s*(?:-->|-.->|==>|--o|--x|~~~|<-->|--\s)/.test(t) &&
    !/^[A-Za-z0-9_]+\s*[\[\(\{]/.test(t)

  // ★ SUBGRAPH STRATEGY:
  // Mermaid does NOT allow quoted labels (STR tokens) OR :::class inline on nodes
  // inside subgraph blocks in most versions. The safe approach:
  // 1. Strip :::class from ALL node definitions inside subgraphs
  // 2. Collect them as deferred `class nodeId className` statements
  // 3. Append those statements after the diagram — mermaid accepts them globally
  let subgraphDepth = 0
  const deferredClasses = [] // { nodeId, className }

  const lines = processed.split('\n')
  const normalized = lines.map(line => {
    const trimmed = line.trim()

    // Track subgraph nesting
    if (/^subgraph(\s|$)/.test(trimmed)) { subgraphDepth++; return line }
    if (trimmed === 'end' && subgraphDepth > 0) { subgraphDepth--; return line }

    if (!trimmed) return line
    if (skipLine(trimmed)) return line

    if (subgraphDepth > 0) {
      // Inside subgraph: strip :::class suffix from ANY node line and defer it
      const nodeId = trimmed.match(/^([A-Za-z0-9_]+)/)?.[1]
      const classSuffix = trimmed.match(/(:::[a-zA-Z0-9_-]+)\s*$/)?.[1]
      if (nodeId && classSuffix) {
        deferredClasses.push({ nodeId, className: classSuffix.replace(':::', '') })
        // Return line with :::class stripped
        return line.replace(/\s*:::[a-zA-Z0-9_-]+\s*$/, '')
      }
      return line
    }

    if (alreadyQuoted(trimmed)) return line
    if (isPureEdge(trimmed)) return line

    // Quote unquoted multi-word labels outside subgraphs
    const m = line.match(
      /^(\s*)([A-Za-z0-9_]+)\s*([\[\(\{]{1,3})((?:[^"'\[\]\(\)\{\}])*)([\]\)\}]{1,3})(:::[\w-]+)?(\s*(?:-->|-.->|==>|--o|--x|~~~|<-->|--\s).*)?\s*$/
    )
    if (!m) return line

    const [, indent, id, open, content, close, classSuffix, edgePart] = m
    if (reserved.has(id.toLowerCase())) return line

    let clean = content.trim()
    if (!clean) return line

    let changed = true
    while (changed) {
      const prev = clean.length
      clean = clean.replace(/^[\s"']+|[\s"']+$/g, '').trim()
      changed = clean.length !== prev
    }

    // 6.5 Fix internal quotes within labels (Escape them for Mermaid)
    const safeLabel = clean.replace(/"/g, '#quot;').replace(/<br\s*\/?>/gi, '<br/>')

    let op = '["', cl = '"]'
    if (open.startsWith('(')) {
      if (open.includes('['))    { op = '(["'; cl = '"])' }
      else if (open.length >= 2) { op = '(("'; cl = '"))' }
      else                       { op = '("';  cl = '")'  }
    } else if (open.startsWith('{')) {
      if (open.length >= 2)      { op = '{{"'; cl = '"}}' }
      else                       { op = '{"';  cl = '"}'  }
    } else if (open.startsWith('[')) {
      if (open.includes('('))    { op = '[("'; cl = '")]' }
      else if (open.length >= 2) { op = '[["'; cl = '"]]' }
    }

    return `${indent}${id}${op}${safeLabel}${cl}${classSuffix || ''}${edgePart || ''}`
  })

  // Flush deferred class assignments (from subgraph nodes) as `class id className` statements
  let result = normalized.join('\n')
  if (deferredClasses.length > 0) {
    const byClass = {}
    deferredClasses.forEach(({ nodeId, className }) => {
      if (!byClass[className]) byClass[className] = []
      byClass[className].push(nodeId)
    })
    const classLines = Object.entries(byClass)
      .map(([cls, ids]) => `    class ${ids.join(',')} ${cls}`)
    result = result.trimEnd() + '\n' + classLines.join('\n')
  }
  return result
}

// ─────────────────────────────────────────────────────────────────────────────
// SVG mount helper
// ─────────────────────────────────────────────────────────────────────────────
async function mountSvg(svgString, containerEl) {
  containerEl.innerHTML = svgString
  const svgEl = containerEl.querySelector('svg')
  if (!svgEl) return null
  svgEl.removeAttribute('style')
  svgEl.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  await nextTick()
  try {
    const bbox = svgEl.querySelector('g')?.getBBox()
    if (bbox?.width > 0 && bbox?.height > 0) {
      const p = 20
      svgEl.setAttribute('viewBox', `${bbox.x - p} ${bbox.y - p} ${bbox.width + p * 2} ${bbox.height + p * 2}`)
    }
  } catch (e) { /* ignore */ }
  const pz = svgPanZoom(svgEl, {
    zoomEnabled: true, panEnabled: true, controlIconsEnabled: false,
    fit: true, center: true, minZoom: 0.1, maxZoom: 20,
  })
  return { svgEl, pz }
}

async function renderDiagram() {
  cleanup()
  errorMessage.value = ''
  if (!props.mermaidCode?.trim()) return
  try {
    try { detectedType.value = mermaid.detectType(props.mermaidCode, { default: { type: 'flowchart' } }) }
    catch { detectedType.value = 'Unknown' }

    const processedCode = processMermaidCode(props.mermaidCode)
    lastProcessedCode.value = processedCode
    mermaid.initialize(getBaseMermaidConfig(uiStore.currentTheme === 'dark' ? 'dark' : 'default'))
    const { svg } = await mermaid.render(`mermaid-svg-${Date.now()}`, processedCode)

    if (!mountRef.value) return
    const result = await mountSvg(svg, mountRef.value)
    if (!result) throw new Error('Mermaid failed to produce an SVG element.')

    panZoomInstance = result.pz
    resizeObserver = new ResizeObserver(() => {
      panZoomInstance?.resize(); panZoomInstance?.fit(); panZoomInstance?.center()
    })
    if (wrapperRef.value) resizeObserver.observe(wrapperRef.value)
    isInteractive.value = true
    emit('ready', { panZoom: panZoomInstance, svg: result.svgEl })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : (error?.str ?? String(error))
    emit('error', error)
  }
}

async function openFullscreen() {
  isFullscreen.value = true
  showSource.value = false
  fullscreenError.value = ''
  await nextTick()
  fullscreenOverlayRef.value?.focus()
  if (!fullscreenMountRef.value) return
  try {
    const processedCode = processMermaidCode(props.mermaidCode)
    // Fullscreen is always dark — always render with dark theme
    mermaid.initialize(getBaseMermaidConfig('dark'))
    const { svg } = await mermaid.render(`mermaid-fs-${Date.now()}`, processedCode)
    // Restore original theme for the inline diagram
    mermaid.initialize(getBaseMermaidConfig(uiStore.currentTheme === 'dark' ? 'dark' : 'default'))
    await mountSvg(svg, fullscreenMountRef.value)
  } catch (e) {
    fullscreenError.value = e instanceof Error ? e.message : String(e)
    // Restore theme on error too
    mermaid.initialize(getBaseMermaidConfig(uiStore.currentTheme === 'dark' ? 'dark' : 'default'))
  }
}

async function getSvgForExport() {
  const originalTheme = uiStore.currentTheme === 'dark' ? 'dark' : 'default'
  try {
    // 1. Initialize with 'default' theme for export (best for white backgrounds/documents)
    mermaid.initialize(getBaseMermaidConfig('default'))
    const { svg: s } = await mermaid.render(`export-${Date.now()}`, processMermaidCode(props.mermaidCode))
    
    // 2. Restore UI theme immediately to prevent UI flicker
    mermaid.initialize(getBaseMermaidConfig(originalTheme))
    
    const tempDiv = document.createElement('div')
    // CRITICAL: Use visibility:hidden + position:fixed instead of display:none.
    // Elements must be in the layout flow for getComputedStyle and getBBox to work.
    tempDiv.style.cssText = 'position:fixed; top:0; left:0; width:100%; height:100%; visibility:hidden; pointer-events:none; z-index:-9999;'
    tempDiv.innerHTML = s
    document.body.appendChild(tempDiv)
    
    const svgEl = tempDiv.querySelector('svg')
    if (!svgEl) { 
        document.body.removeChild(tempDiv)
        throw new Error('No SVG element produced during export render.') 
    }

    // 3. Inline all computed styles into the SVG elements
    // This embeds colors and fonts directly into the file for standalone viewing.
    const cssProps = [
        'fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'stroke-opacity', 'fill-opacity',
        'font-family', 'font-size', 'font-weight', 'font-style', 'text-anchor', 
        'dominant-baseline', 'alignment-baseline', 'letter-spacing', 'opacity'
    ]
    
    svgEl.querySelectorAll('*').forEach(el => {
      const cs = window.getComputedStyle(el)
      let styleString = ''
      for (const p of cssProps) { 
          const v = cs.getPropertyValue(p)
          if (v && v !== 'normal') {
              styleString += `${p}:${v};` 
          }
      }
      
      // Explicit fix for text: ensure black fill if the detected style is transparent/empty.
      // This prevents text from disappearing when exporting from Dark Mode.
      if (el.tagName === 'text' || el.tagName === 'tspan') {
          const fill = cs.getPropertyValue('fill')
          if (!fill || fill === 'none' || fill === 'rgba(0, 0, 0, 0)' || fill === 'transparent') {
              styleString += 'fill:#000000;'
          }
      }
      
      if (styleString) el.setAttribute('style', styleString)
    })

    // 4. Calculate bounding box for precise cropping
    const contentGroup = svgEl.querySelector('g')
    const bbox = contentGroup ? contentGroup.getBBox() : svgEl.getBBox()
    
    // Cleanup temporary DOM elements
    document.body.removeChild(tempDiv)

    if (!bbox || bbox.width === 0) throw new Error('Exported diagram bounding box is empty.')

    // 5. Final SVG geometry setup
    const padding = 20
    const w = Math.ceil(bbox.width + padding * 2)
    const h = Math.ceil(bbox.height + padding * 2)
    
    // Set viewBox to wrap the diagram content exactly with a small margin
    svgEl.setAttribute('viewBox', `${bbox.x - padding} ${bbox.y - padding} ${w} ${h}`)
    svgEl.setAttribute('width', String(w))
    svgEl.setAttribute('height', String(h))
    svgEl.setAttribute('style', 'background-color: transparent; font-family: Arial, sans-serif;')
    
    // Ensure valid XML namespace
    svgEl.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
    
    return { svg: svgEl, width: w, height: h }
  } catch (err) { 
    mermaid.initialize(getBaseMermaidConfig(originalTheme))
    console.error("Failed to prepare SVG for export:", err)
    throw err 
  }
}

async function exportPNG({ filename = 'diagram.png', scale = 3, bgColor = '#FFFFFF' } = {}) {
  const { svg, width, height } = await getSvgForExport()
  const svgString = new XMLSerializer().serializeToString(svg)
  const canvas = document.createElement('canvas')
  canvas.width = width * scale; canvas.height = height * scale
  const ctx = canvas.getContext('2d')
  if (bgColor) { ctx.fillStyle = bgColor; ctx.fillRect(0, 0, canvas.width, canvas.height) }
  const v = await Canvg.from(ctx, svgString, { ignoreClear: true, ignoreAnimation: true, scaleX: scale, scaleY: scale })
  await v.render()
  const a = document.createElement('a'); a.href = canvas.toDataURL('image/png'); a.download = filename
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
}

async function exportSVG({ filename = 'diagram.svg', bgColor = null } = {}) {
  const { svg } = await getSvgForExport()
  if (bgColor) {
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
    rect.setAttribute('width', '100%'); rect.setAttribute('height', '100%'); rect.setAttribute('fill', bgColor)
    svg.insertBefore(rect, svg.firstChild)
  }
  const url = URL.createObjectURL(new Blob(
    ['<?xml version="1.0" standalone="no"?>\r\n' + new XMLSerializer().serializeToString(svg)],
    { type: 'image/svg+xml;charset=utf-8' }
  ))
  const a = document.createElement('a'); a.href = url; a.download = filename
  document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url)
}

function copyErrorMessage() {
  navigator.clipboard.writeText(errorMessage.value).then(() => {
    errorCopyLabel.value = 'Copied!'
    setTimeout(() => { errorCopyLabel.value = 'Copy Error Message' }, 2000)
  })
}

function resetView() { panZoomInstance?.reset(); panZoomInstance?.fit(); panZoomInstance?.center() }

onMounted(() => {
  mermaid.initialize(getBaseMermaidConfig(uiStore.currentTheme === 'dark' ? 'dark' : 'default'))
  renderDiagram()
})
onUnmounted(cleanup)
watch(() => props.mermaidCode, renderDiagram)
watch(() => uiStore.currentTheme, (t) => {
  mermaid.initialize(getBaseMermaidConfig(t === 'dark' ? 'dark' : 'default'))
  renderDiagram()
})

defineExpose({ exportPNG, exportSVG, resetView })
</script>

<style>
.mermaid-container svg {
  width: 100%;
  height: 100%;
  display: block;
  margin: 0 auto;
}

/* In fullscreen the diagram pane is always dark — kill any baked-in light background */
.mermaid-fullscreen-pane .mermaid-container svg {
  background: transparent !important;
}
.mermaid-fullscreen-pane .mermaid-container svg > rect:first-child {
  fill: transparent !important;
}
</style>