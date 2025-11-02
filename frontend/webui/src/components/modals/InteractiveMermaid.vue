<template>
  <div ref="wrapperRef" class="w-full h-full relative bg-gray-50 dark:bg-gray-800/50 overflow-hidden">
    <!-- Mount point for the Mermaid SVG -->
    <div ref="mountRef" class="w-full h-full mermaid-container"></div>
    
    <!-- Diagram type label -->
    <div v-if="detectedTypeLabel" class="absolute top-3 right-3 px-2 py-1 text-xs rounded-md bg-black/10 dark:bg-white/10 text-gray-800 dark:text-gray-100 backdrop-blur-sm">
      {{ detectedTypeLabel }}
    </div>
    
    <!-- Interactive SVG Indicator -->
    <div v-if="isInteractive" class="absolute left-4 bottom-4 text-sm text-gray-600 dark:text-gray-400 flex items-center gap-2 z-10 p-1 rounded-md bg-white/50 dark:bg-black/50 backdrop-blur-sm">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5" />
      </svg>
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
import { useUiStore } from '../../stores/ui'
import { Canvg } from 'canvg';

const props = defineProps({
  mermaidCode: {
    type: String,
    required: true
  }
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

const getBaseMermaidConfig = (theme) => ({
  startOnLoad: false,
  securityLevel: 'loose',
  theme: theme,
  themeVariables: {
    fontSize: "15px"
  }
});

const detectedTypeLabel = computed(() => {
  if (!detectedType.value) return ''
  const type = detectedType.value.charAt(0).toUpperCase() + detectedType.value.slice(1);
  return `Mermaid: ${type}`
})

function cleanup() {
  isInteractive.value = false
  if (panZoomInstance) {
    panZoomInstance.destroy();
    panZoomInstance = null;
  }
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (mountRef.value) {
    mountRef.value.innerHTML = '';
  }
}

// Enhanced text sanitization for nested brackets and parentheses
function sanitizeMermaidText(text) {
  if (!text) return text;
  
  // Replace problematic characters with HTML entities
  return text
    .replace(/\[/g, '&#91;')   // Escape [
    .replace(/\]/g, '&#93;')   // Escape ]
    .replace(/\(/g, '&#40;')   // Escape (
    .replace(/\)/g, '&#41;')   // Escape )
    .replace(/{/g, '&#123;')   // Escape {
    .replace(/}/g, '&#125;');  // Escape }
}

function processMermaidCode(code) {
  if (!code) return code;
  
  const lines = code.split('\n');
  const processedLines = lines.map(line => {
    // Handle node definitions with labels containing brackets/parentheses
    // This regex matches: nodeId[any content] or nodeId(any content) or nodeId{any content}
    return line.replace(
      /(\b[A-Za-z0-9_]+\s*)([[({])([^\]})]*)([\]})])/g,
      (match, nodeId, openDelim, content, closeDelim) => {
        const sanitizedContent = sanitizeMermaidText(content);
        return `${nodeId}${openDelim}${sanitizedContent}${closeDelim}`;
      }
    );
  });
  
  return processedLines.join('\n');
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

    // Process the code to handle nested brackets/parentheses
    const processedCode = processMermaidCode(props.mermaidCode);
    
    const config = getBaseMermaidConfig(uiStore.currentTheme === 'dark' ? 'dark' : 'default');
    const { svg } = await mermaid.render(mermaidId, processedCode)

    if (mountRef.value) mountRef.value.innerHTML = svg

    const svgEl = mountRef.value?.querySelector('svg')
    if (!svgEl) throw new Error("Mermaid failed to produce an SVG element.")

    svgEl.removeAttribute('style');
    svgEl.setAttribute('xmlns', 'http://www.w3.org/2000/svg');

    const mainGroup = svgEl.querySelector('g');
    if (mainGroup) {
      try {
        const bbox = mainGroup.getBBox();
        if (bbox.width > 0 && bbox.height > 0) {
          const padding = 20;
          svgEl.setAttribute('viewBox', `${bbox.x - padding} ${bbox.y - padding} ${bbox.width + (padding * 2)} ${bbox.height + (padding * 2)}`);
        }
      } catch (e) {
        console.warn("Could not get bounding box to trim SVG whitespace.", e)
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
      panZoomInstance?.resize();
      panZoomInstance?.fit();
      panZoomInstance?.center();
    })
    
    resizeObserver.observe(wrapperRef.value)
    isInteractive.value = true

    await nextTick()
    emit('ready', { panZoom: panZoomInstance, svg: svgEl })
    
  } catch (error) {
    let message = 'An unknown error occurred during rendering.'
    if (error instanceof Error) message = error.message;
    else if (typeof error === 'string') message = error;
    else if (error && typeof error.str === 'string') message = error.str;
    
    errorMessage.value = message
    emit('error', error)
  }
}

function copyErrorMessage() {
  navigator.clipboard.writeText(errorMessage.value).then(() => {
    errorCopyLabel.value = "Copied!"
    setTimeout(() => {
      errorCopyLabel.value = "Copy Error Message"
    }, 2000)
  })
}

// Enhanced SVG export with proper text handling
async function getSvgForExport() {
  const originalTheme = uiStore.currentTheme === 'dark' ? 'dark' : 'default';
  
  try {
    // Use base theme for export
    mermaid.initialize(getBaseMermaidConfig('base'));
    
    // Process the code for export as well
    const processedCode = processMermaidCode(props.mermaidCode);
    const { svg: exportSvgString } = await mermaid.render(`export-${Date.now()}`, processedCode);

    // Restore original theme
    mermaid.initialize(getBaseMermaidConfig(originalTheme));

    // Create temporary container to parse SVG
    const tempDiv = document.createElement('div');
    tempDiv.style.position = 'absolute';
    tempDiv.style.left = '-9999px';
    tempDiv.innerHTML = exportSvgString;
    const svgEl = tempDiv.querySelector('svg');
    
    if (!svgEl) throw new Error("Failed to create temporary SVG for export.");
    document.body.appendChild(tempDiv);

    // Enhanced style inlining for better text rendering
    const elements = svgEl.querySelectorAll('*');
    elements.forEach(el => {
      const computedStyle = window.getComputedStyle(el);
      let styleString = '';
      
      // Comprehensive list of styles needed for text rendering
      const cssPropsToInline = [
        'fill', 'stroke', 'stroke-width', 'stroke-dasharray',
        'font-family', 'font-size', 'font-weight', 'font-style',
        'text-anchor', 'dominant-baseline', 'alignment-baseline',
        'letter-spacing', 'word-spacing', 'line-height',
        'opacity', 'visibility', 'display'
      ];
      
      for (const prop of cssPropsToInline) {
        const value = computedStyle.getPropertyValue(prop);
        if (value && value !== 'none' && value !== 'normal') {
          styleString += `${prop}: ${value}; `;
        }
      }
      
      if (styleString) {
        el.setAttribute('style', styleString);
      }
      
      // Ensure text elements have explicit fill
      if (el.tagName === 'text' || el.tagName === 'tspan') {
        const fill = computedStyle.getPropertyValue('fill');
        if (!fill || fill === 'none') {
          el.setAttribute('fill', '#000');
        }
      }
    });

    // Calculate bounding box
    const mainGroup = svgEl.querySelector('g');
    if (!mainGroup) throw new Error("Main group not found in temp SVG.");
    
    const bbox = mainGroup.getBBox();
    document.body.removeChild(tempDiv);

    const padding = 20;
    const finalWidth = Math.ceil(bbox.width + padding * 2);
    const finalHeight = Math.ceil(bbox.height + padding * 2);
    
    svgEl.setAttribute('viewBox', `${bbox.x - padding} ${bbox.y - padding} ${finalWidth} ${finalHeight}`);
    svgEl.setAttribute('width', finalWidth);
    svgEl.setAttribute('height', finalHeight);
    svgEl.setAttribute('style', 'font-family: Arial, sans-serif;'); // Ensure font fallback

    return { svg: svgEl, width: finalWidth, height: finalHeight };
    
  } catch(err) {
    mermaid.initialize(getBaseMermaidConfig(originalTheme));
    throw err;
  }
}

async function exportPNG({ filename = 'diagram.png', scale = 3, bgColor = '#FFFFFF' } = {}) {
  try {
    const { svg, width, height } = await getSvgForExport();
    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svg);

    const canvas = document.createElement('canvas');
    canvas.width = width * scale;
    canvas.height = height * scale;
    
    const ctx = canvas.getContext('2d');
    
    // Set background
    if (bgColor) {
      ctx.fillStyle = bgColor;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    // Use Canvg with better rendering options
    const v = await Canvg.from(ctx, svgString, {
      ignoreClear: true,
      ignoreAnimation: true,
      scaleX: scale,
      scaleY: scale,
      renderOptions: {
        enableRedraw: false,
        ignoreDimensions: false,
        ignoreClear: true,
        offsetX: 0,
        offsetY: 0
      }
    });
    
    await v.render();
    
    const a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    
  } catch (error) {
    console.error("PNG Export failed:", error);
    throw error;
  }
}

async function exportSVG({ filename = 'diagram.svg', bgColor = null } = {}) {
  try {
    const { svg } = await getSvgForExport();
    
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
    
  } catch (error) {
    console.error("SVG Export failed:", error);
    throw error;
  }
}

function resetView() {
  if (panZoomInstance) {
    panZoomInstance.reset();
    panZoomInstance.fit();
    panZoomInstance.center();
  }
}

onMounted(() => {
  mermaid.initialize(getBaseMermaidConfig(uiStore.currentTheme === 'dark' ? 'dark' : 'default'));
  renderDiagram();
});

onUnmounted(cleanup);

watch(() => props.mermaidCode, renderDiagram);

watch(() => uiStore.currentTheme, (newTheme) => {
  mermaid.initialize(getBaseMermaidConfig(newTheme === 'dark' ? 'dark' : 'default'));
  renderDiagram();
});

defineExpose({
  exportPNG,
  exportSVG,
  resetView
});
</script>

<style>
.mermaid-container svg {
  width: 100%;
  height: 100%;
  display: block;
  margin: 0 auto;
}
</style>