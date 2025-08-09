<template>
  <div ref="wrapperRef" class="w-full h-full relative bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700/50 overflow-hidden">
    <!-- Mount point for the Mermaid SVG -->
    <div ref="mountRef" class="w-full h-full mermaid-container"></div>

    <!-- Diagram type label -->
    <div v-if="detectedTypeLabel" class="absolute top-3 right-3 px-2 py-1 text-xs rounded-md bg-black/10 dark:bg-white/10 text-gray-800 dark:text-gray-100 backdrop-blur-sm">
      {{ detectedTypeLabel }}
    </div>

    <!-- Controls -->
    <div class="absolute left-3 top-3 flex gap-2 z-20">
      <button @click="resetView" class="px-2 py-1 text-xs rounded-md bg-white/80 dark:bg-gray-900/80 border border-gray-200 dark:border-gray-700 shadow-sm hover:opacity-90 backdrop-blur-sm">
        Reset View
      </button>
      <button @click="exportPNG()" class="px-2 py-1 text-xs rounded-md bg-white/80 dark:bg-gray-900/80 border border-gray-200 dark:border-gray-700 shadow-sm hover:opacity-90 backdrop-blur-sm">
        Export PNG
      </button>
      <button @click="exportSVG()" class="px-2 py-1 text-xs rounded-md bg-white/80 dark:bg-gray-900/80 border border-gray-200 dark:border-gray-700 shadow-sm hover:opacity-90 backdrop-blur-sm">
        Export SVG
      </button>
    </div>

    <!-- Interactive SVG Indicator -->
    <div v-if="isInteractive" class="absolute left-4 bottom-4 text-sm text-gray-600 dark:text-gray-400 flex items-center gap-2 z-10 p-1 rounded-md bg-white/50 dark:bg-black/50 backdrop-blur-sm">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5" /></svg>
      <span>Interactive SVG (Pan & Zoom enabled)</span>
    </div>

    <!-- Error Message Display -->
    <div v-if="errorMessage" class="absolute inset-0 flex items-center justify-center pointer-events-none z-30">
      <div class="pointer-events-auto bg-white/95 dark:bg-gray-900/95 border border-red-300 dark:border-red-700 rounded-lg p-4 max-w-2xl mx-4 shadow-2xl">
        <div class="flex items-start gap-3">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-red-500 dark:text-red-400 flex-none" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.6" d="M12 9v4m0 4h.01"/>
          </svg>
          <div class="flex-1">
            <div class="text-sm font-semibold text-red-800 dark:text-red-200 mb-1">Mermaid Rendering Error</div>
            <pre class="text-xs text-red-700 dark:text-red-400 whitespace-pre-wrap max-h-48 overflow-auto p-2 bg-red-50 dark:bg-red-900/20 rounded-md">{{ errorMessage }}</pre>
            <div class="mt-3">
              <button @click="copyErrorMessage" class="px-3 py-1 rounded-md bg-red-600 hover:bg-red-700 text-white text-sm text-left">{{ errorCopyLabel }}</button>
            </div>
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
import { useUiStore } from '../../stores/ui' // Assuming this store provides the current theme

const props = defineProps({
  mermaidCode: { type: String, required: true }
})

const emit = defineEmits(['error','ready'])

const wrapperRef = ref(null)
const mountRef = ref(null)
let panZoomInstance = null
let resizeObserver = null

const uiStore = useUiStore()
const errorMessage = ref('')
const errorCopyLabel = ref("Copy Error Message")
const detectedType = ref('')
const isInteractive = ref(false)

const detectedTypeLabel = computed(() => {
  if (!detectedType.value) return ''
  const type = detectedType.value.charAt(0).toUpperCase() + detectedType.value.slice(1);
  return `Mermaid: ${type}`
})

function cleanup() {
  isInteractive.value = false
  if (panZoomInstance) {
    panZoomInstance.destroy()
    panZoomInstance = null
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  if (mountRef.value) {
    mountRef.value.innerHTML = ''
  }
}

async function renderDiagram() {
  cleanup()
  errorMessage.value = ''
  if (!props.mermaidCode || !props.mermaidCode.trim()) return

  const mermaidId = `mermaid-svg-${Date.now()}`

  try {
    try {
      detectedType.value = mermaid.detectType(props.mermaidCode, { default: {type: 'flowchart'} });
    } catch (e) {
      detectedType.value = 'Unknown'
    }

    const { svg } = await mermaid.render(mermaidId, props.mermaidCode)
    if (mountRef.value) mountRef.value.innerHTML = svg

    const svgEl = mountRef.value?.querySelector('svg')
    if (!svgEl) throw new Error("Mermaid failed to produce an SVG element.")
    
    svgEl.setAttribute('xmlns', 'http://www.w3.org/2000/svg');

    // Dynamically trim the viewBox to fit the diagram content, removing excess whitespace.
    // This is crucial for the 'fit' functionality to work correctly.
    const mainGroup = svgEl.querySelector('g');
    if (mainGroup) {
        try {
            const bbox = mainGroup.getBBox();
            if (bbox.width > 0 && bbox.height > 0) {
                const padding = 20; // Visual padding
                svgEl.setAttribute('viewBox', `${bbox.x - padding} ${bbox.y - padding} ${bbox.width + (padding * 2)} ${bbox.height + (padding * 2)}`);
            }
        } catch (e) {
            console.warn("Could not get bounding box to trim SVG whitespace.", e);
        }
    }

    panZoomInstance = svgPanZoom(svgEl, {
      zoomEnabled: true,
      panEnabled: true,
      controlIconsEnabled: false,
      fit: true,
      center: true,
      minZoom: 0.1,
      maxZoom: 20,
    })

    resizeObserver = new ResizeObserver(() => {
      panZoomInstance?.resize()
      panZoomInstance?.fit()
      panZoomInstance?.center()
    })
    resizeObserver.observe(wrapperRef.value)
    
    isInteractive.value = true
    await nextTick()
    emit('ready', { panZoom: panZoomInstance, svg: svgEl })

  } catch (error) {
    let message = 'An unknown error occurred during rendering.'
    if (error instanceof Error) message = error.message;
    else if (typeof error === 'string') message = error;
    else if (error && typeof error.str === 'string') message = error.str; // Mermaid error object
    
    errorMessage.value = message
    emit('error', error)
  }
}

function copyErrorMessage() {
  navigator.clipboard.writeText(errorMessage.value).then(() => {
    errorCopyLabel.value = "Copied!"
    setTimeout(() => { errorCopyLabel.value = "Copy Error Message" }, 2000)
  })
}

/**
 * A robust helper to get a clean, cloned SVG element and its true dimensions.
 * It relies on the viewBox for accurate sizing, which is essential for high-quality exports.
 * @returns {{svg: SVGElement, width: number, height: number} | null}
 */
function getSvgForExport() {
    const svgEl = mountRef.value?.querySelector('svg');
    if (!svgEl) {
        console.error("Export failed: SVG element not found.");
        return null;
    }

    const clonedSvg = svgEl.cloneNode(true);
    let width = 0, height = 0;

    // The viewBox is the most reliable source for the diagram's intrinsic dimensions.
    const viewBox = clonedSvg.getAttribute('viewBox');
    if (viewBox) {
        const parts = viewBox.split(/\s+|,/).map(Number);
        if (parts.length === 4) {
            width = parts[2];
            height = parts[3];
        }
    } else {
        // Fallback for SVGs without a viewBox (less common for Mermaid).
        const rect = clonedSvg.getBoundingClientRect();
        width = rect.width;
        height = rect.height;
    }

    if (width === 0 || height === 0) {
        console.error("Export failed: SVG has zero dimensions.");
        return null;
    }
    
    // Set explicit width/height attributes for better compatibility with external tools.
    clonedSvg.setAttribute('width', Math.ceil(width));
    clonedSvg.setAttribute('height', Math.ceil(height));

    return { svg: clonedSvg, width: Math.ceil(width), height: Math.ceil(height) };
}

/**
 * Exports the diagram as a high-quality, readable PNG file.
 */
function exportPNG({ filename = 'diagram.png', scale = 2, bgColor = '#FFFFFF' } = {}) {
    const result = getSvgForExport();
    if (!result) return;
    const { svg, width, height } = result;

    if (bgColor) {
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('width', '100%');
        rect.setAttribute('height', '100%');
        rect.setAttribute('fill', bgColor);
        svg.insertBefore(rect, svg.firstChild);
    }

    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svg);
    const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);

    const img = new Image();
    img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = width * scale;
        canvas.height = height * scale;
        
        const ctx = canvas.getContext('2d');
        if (bgColor) {
          ctx.fillStyle = bgColor;
          ctx.fillRect(0, 0, canvas.width, canvas.height);
        }
        
        // This is the key to high-quality PNGs: drawing the SVG onto the canvas
        // at the target size, which forces the browser to re-render the vector
        // graphics at high resolution, preventing pixelation.
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        
        URL.revokeObjectURL(url);

        const a = document.createElement('a');
        a.href = canvas.toDataURL('image/png');
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };
    img.onerror = (err) => {
        console.error("Failed to load SVG into Image for PNG export.", err);
        URL.revokeObjectURL(url);
    };
    img.src = url;
}

/**
 * Exports the diagram as a clean, self-contained SVG file.
 */
function exportSVG({ filename = 'diagram.svg', bgColor = null } = {}) {
  const result = getSvgForExport();
  if (!result) return;
  const { svg } = result;

  if (bgColor) {
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
    rect.setAttribute('width', '100%');
    rect.setAttribute('height', '100%');
    rect.setAttribute('fill', bgColor);
    svg.insertBefore(rect, svg.firstChild);
  }

  const serializer = new XMLSerializer();
  const svgString = '<?xml version="1.0" standalone="no"?>\r\n' + serializer.serializeToString(svg);
  const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function resetView() {
  if (panZoomInstance) {
    panZoomInstance.reset();
    panZoomInstance.fit();
    panZoomInstance.center();
  }
}

onMounted(() => {
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'loose',
    theme: uiStore.currentTheme === 'dark' ? 'dark' : 'default',
    themeVariables: { fontSize: "15px" }
  });
  renderDiagram();
});

onUnmounted(() => {
  cleanup();
});

watch(() => props.mermaidCode, renderDiagram);
watch(() => uiStore.currentTheme, (newTheme) => {
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'loose',
    theme: newTheme === 'dark' ? 'dark' : 'default',
    themeVariables: { fontSize: "15px" }
  });
  renderDiagram();
});

defineExpose({ exportPNG, exportSVG, resetView });
</script>

<style>
/* Style the container and the SVG for proper scaling and interaction. */
.mermaid-container svg {
  width: 100%;
  height: 100%;
  display: block;
  margin: 0 auto;
}
</style>