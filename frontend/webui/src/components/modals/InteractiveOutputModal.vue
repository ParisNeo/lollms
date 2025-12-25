<!-- [UPDATE] frontend/webui/src/components/modals/InteractiveOutputModal.vue -->
<script setup>
import { computed, ref, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../assets/icons/IconMinimize.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconMinus from '../../assets/icons/IconMinus.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue'; 
import InteractiveMermaid from './InteractiveMermaid.vue'; 

const uiStore = useUiStore();
const isFullScreen = ref(false);
const viewerRef = ref(null);
const mermaidInstance = ref(null); 
const pngBgColor = ref(uiStore.currentTheme === 'dark' ? '#1F2937' : '#FFFFFF');

const isOpen = computed(() => uiStore.isModalOpen('interactiveOutput'));
const data = computed(() => uiStore.modalData('interactiveOutput'));
const isInteractiveMermaid = computed(() => data.value?.contentType === 'mermaid');
const isPlainSvg = computed(() => data.value?.contentType === 'svg');
const isVisualContent = computed(() => isPlainSvg.value || isInteractiveMermaid.value);

// --- State and functions for PLAIN SVG pan/zoom ---
const scale = ref(1);
const posX = ref(0);
const posY = ref(0);
let isDragging = false;
let startX = 0;
let startY = 0;

const contentStyle = computed(() => ({
    transform: `translate(${posX.value}px, ${posY.value}px) scale(${scale.value})`,
    cursor: isDragging.value ? 'grabbing' : (scale.value > 1 ? 'grab' : 'default')
}));

function resetPlainSvgView() { scale.value = 1; posX.value = 0; posY.value = 0; }
const handleWheel = (event) => {
    if (!isPlainSvg.value) return;
    const scaleAmount = 0.1;
    const rect = viewerRef.value.getBoundingClientRect();
    const x = event.clientX - rect.left; const y = event.clientY - rect.top;
    const newScale = scale.value + (event.deltaY < 0 ? scaleAmount : -scaleAmount) * scale.value;
    const clampedScale = Math.min(Math.max(0.5, newScale), 10);
    const scaleChange = clampedScale - scale.value;
    posX.value -= (x - posX.value) * (scaleChange / scale.value);
    posY.value -= (y - posY.value) * (scaleChange / scale.value);
    scale.value = clampedScale;
};
const startDrag = (event) => {
    if (!isPlainSvg.value || scale.value <= 1) return;
    event.preventDefault(); isDragging = true;
    startX = event.clientX - posX.value; startY = event.clientY - posY.value;
    window.addEventListener('mousemove', drag); window.addEventListener('mouseup', stopDrag);
};
const drag = (event) => { if (isDragging) { event.preventDefault(); posX.value = event.clientX - startX; posY.value = event.clientY - startY; } };
const stopDrag = () => { isDragging = false; window.removeEventListener('mousemove', drag); window.removeEventListener('mouseup', stopDrag); };
const zoomIn = () => { if (isPlainSvg.value) scale.value = Math.min(10, scale.value + 0.25); };
const zoomOut = () => { if (isPlainSvg.value) scale.value = Math.max(0.5, scale.value - 0.25); };
// --- End of Plain SVG logic ---

function closeModal() { uiStore.closeModal('interactiveOutput'); }

function toggleFullScreen() {
    if (!viewerRef.value) return;
    
    if (!document.fullscreenElement) {
        viewerRef.value.requestFullscreen().then(() => {
            isFullScreen.value = true;
        }).catch(err => {
            console.warn(`Fullscreen error: ${err.message}`);
            // Fallback to CSS only if API fails
            isFullScreen.value = !isFullScreen.value;
        });
    } else {
        document.exitFullscreen();
    }
}

// Watch for native fullscreen changes (e.g. user pressing Esc)
if (typeof document !== 'undefined') {
    document.addEventListener('fullscreenchange', () => {
        isFullScreen.value = !!document.fullscreenElement;
    });
}

function resetView() {
    if (isInteractiveMermaid.value) {
        mermaidInstance.value?.resetView();
    } else if (isPlainSvg.value) {
        resetPlainSvgView();
    }
}

watch(isOpen, (newVal) => { 
    if (!newVal) { 
        if (document.fullscreenElement) document.exitFullscreen();
        isFullScreen.value = false; 
        resetPlainSvgView(); 
    }
});
watch(() => uiStore.currentTheme, (newTheme) => { pngBgColor.value = newTheme === 'dark' ? '#1F2937' : '#FFFFFF'; });

// --- UNIFIED Download Functions ---
function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url);
}

function handleDownloadSVG() {
    if (isInteractiveMermaid.value) {
        mermaidInstance.value?.exportSVG({ filename: `${data.value.title || 'diagram'}.svg` });
    } else if (isPlainSvg.value && data.value?.htmlContent) {
        const match = /<svg[\s\S]*?<\/svg>/.exec(data.value.htmlContent);
        if (match) downloadFile(match[0], `${data.value.title || 'diagram'}.svg`, 'image/svg+xml');
    }
}

function handleDownloadPNG() {
    if (isInteractiveMermaid.value) {
        mermaidInstance.value?.exportPNG({ filename: `${data.value.title || 'diagram'}.png`, bgColor: pngBgColor.value });
    }
}

function handleDownloadSource() {
    if (isInteractiveMermaid.value && data.value?.sourceCode) {
        downloadFile(data.value.sourceCode, `${data.value.title || 'source'}.md`, 'text/markdown');
    }
}

const modalPanelClass = computed(() => isFullScreen.value ? 'w-screen h-screen rounded-none' : 'w-full max-w-5xl h-[85vh] rounded-lg shadow-2xl');
const modalBodyClass = computed(() => isFullScreen.value ? 'p-0' : 'p-4');
</script>

<template>
    <Teleport to="body">
        <Transition enter-active-class="transition-opacity ease-out duration-300" enter-from-class="opacity-0" enter-to-class="opacity-100" leave-active-class="transition-opacity ease-in duration-200" leave-from-class="opacity-100" leave-to-class="opacity-0">
            <div v-if="isOpen" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 flex items-center justify-center" @click.self="closeModal">
                <Transition enter-active-class="transition-all ease-out duration-300" enter-from-class="opacity-0 scale-95" enter-to-class="opacity-100 scale-100" leave-active-class="transition-all ease-in duration-200" leave-from-class="opacity-100 scale-100" leave-to-class="opacity-0 scale-95">
                    <div :class="modalPanelClass" class="bg-white dark:bg-gray-900 flex flex-col max-h-screen transition-all duration-300 ease-in-out">
                        <header v-if="!isFullScreen" class="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
                            <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ data?.title || 'Interactive Output' }}</h3>
                            <div class="flex items-center space-x-2">
                                <button @click="toggleFullScreen" class="modal-header-btn" :title="isFullScreen ? 'Exit Fullscreen' : 'Fullscreen'"><IconMinimize v-if="isFullScreen" class="w-5 h-5" /><IconMaximize v-else class="w-5 h-5" /></button>
                                <button @click="closeModal" class="modal-header-btn" title="Close"><IconXMark class="w-5 h-5" /></button>
                            </div>
                        </header>
                        <main class="flex-grow min-h-0 relative" :class="modalBodyClass">
                            <div ref="viewerRef" class="absolute inset-0 overflow-hidden bg-gray-100 dark:bg-gray-800/50" @wheel.prevent="handleWheel" @mousedown="startDrag">
                                <InteractiveMermaid v-if="isInteractiveMermaid" :mermaid-code="data.sourceCode" ref="mermaidInstance" />
                                
                                <div v-else-if="data?.htmlContent" class="w-full h-full">
                                    <div v-if="isPlainSvg" v-html="data.htmlContent" :style="contentStyle" class="w-full h-full transition-transform duration-75"></div>
                                    <iframe v-else :srcdoc="data.htmlContent" class="w-full h-full border-0" sandbox="allow-scripts allow-same-origin"></iframe>
                                </div>
                                <div v-else class="flex items-center justify-center h-full text-gray-500"><p>No content provided.</p></div>
                            </div>

                            <!-- UNIFIED CONTROL BAR -->
                            <div v-if="isVisualContent" class="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-gray-900/60 text-white p-2 rounded-lg backdrop-blur-md shadow-lg z-50">
                                <template v-if="isFullScreen">
                                    <button @click="toggleFullScreen" class="btn-viewer" title="Exit Fullscreen"><IconMinimize class="w-5 h-5" /></button>
                                    <div class="w-px h-6 bg-white/20 mx-1"></div>
                                </template>

                                <!-- Controls for Plain SVG -->
                                <template v-if="isPlainSvg">
                                    <button @click="zoomOut" class="btn-viewer" title="Zoom Out"><IconMinus class="w-5 h-5" /></button>
                                    <button @click="resetView" class="btn-viewer px-3 text-sm font-mono" title="Reset View">{{ Math.round(scale * 100) }}%</button>
                                    <button @click="zoomIn" class="btn-viewer" title="Zoom In"><IconPlus class="w-5 h-5" /></button>
                                </template>
                                
                                <!-- Controls for Interactive Mermaid -->
                                <template v-if="isInteractiveMermaid">
                                    <button @click="resetView" class="btn-viewer" title="Reset View"><IconArrowPath class="w-5 h-5" /></button>
                                    <div class="w-px h-6 bg-white/20 mx-1"></div>
                                    <div class="flex items-center gap-2 pr-2">
                                        <label for="png-bg-color" class="text-xs font-medium" title="PNG Background Color">BG:</label>
                                        <input id="png-bg-color" type="color" v-model="pngBgColor" class="w-6 h-6 p-0 border-none rounded cursor-pointer bg-transparent">
                                    </div>
                                    <button @click="handleDownloadPNG" class="btn-viewer" title="Download as PNG">PNG</button>
                                    <button @click="handleDownloadSVG" class="btn-viewer" title="Download as SVG">SVG</button>
                                    <div class="w-px h-6 bg-white/20 mx-1"></div>
                                    <button @click="handleDownloadSource" class="btn-viewer" title="Download Mermaid Source"><IconCode class="w-5 h-5" /></button>
                                </template>

                                <!-- Controls for Plain SVG (Download only) -->
                                <template v-if="isPlainSvg">
                                     <div class="w-px h-6 bg-white/20 mx-1"></div>
                                     <button @click="handleDownloadSVG" class="btn-viewer" title="Download as SVG"><IconArrowDownTray class="w-5 h-5" /></button>
                                </template>
                            </div>
                        </main>
                    </div>
                </Transition>
            </div>
        </Transition>
    </Teleport>
</template>

<style scoped>
.modal-header-btn { @apply p-2 rounded-full text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors; }
.btn-viewer { @apply p-2 rounded-md hover:bg-white/20 transition-colors flex items-center justify-center; }
input[type="color"]::-webkit-color-swatch-wrapper { padding: 0; }
input[type="color"]::-webkit-color-swatch { border: 1px solid rgba(255, 255, 255, 0.5); border-radius: 4px; }
</style>
