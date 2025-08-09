<script setup>
import { computed, ref, watch } from 'vue';
import { useUiStore } from '../../stores/ui';
import IconMaximize from '../../assets/icons/IconMaximize.vue';
import IconMinimize from '../../assets/icons/IconMinimize.vue';
import IconXMark from '../../assets/icons/IconXMark.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconMinus from '../../assets/icons/IconMinus.vue';
import IconArrowPath from '../../assets/icons/IconArrowPath.vue';
import IconArrowDownTray from '../../assets/icons/IconArrowDownTray.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import InteractiveMermaid from './InteractiveMermaid.vue'; 

const uiStore = useUiStore();
const isFullScreen = ref(false);

const scale = ref(1);
const posX = ref(0);
const posY = ref(0);
let isDragging = false;
let startX = 0;
let startY = 0;

const viewerRef = ref(null);
const mermaidInstance = ref(null);
const pngBgColor = ref(uiStore.currentTheme === 'dark' ? '#1F2937' : '#FFFFFF'); // Default based on theme

const isOpen = computed(() => uiStore.isModalOpen('interactiveOutput'));
const data = computed(() => uiStore.modalData('interactiveOutput'));
const isVisualContent = computed(() => data.value?.contentType === 'svg' || data.value?.contentType === 'mermaid');
const isInteractiveMermaid = computed(() => data.value?.contentType === 'mermaid' && data.value?.interactive);

const contentStyle = computed(() => {
    return {
        transform: `translate(${posX.value}px, ${posY.value}px) scale(${scale.value})`,
        cursor: isDragging.value ? 'grabbing' : (scale.value > 1 ? 'grab' : 'default')
    };
});

function closeModal() { uiStore.closeModal('interactiveOutput'); }
function toggleFullScreen() { isFullScreen.value = !isFullScreen.value; }
function resetView() { scale.value = 1; posX.value = 0; posY.value = 0; }

watch(isOpen, (newVal) => { if (!newVal) { isFullScreen.value = false; resetView(); }});
watch(() => uiStore.currentTheme, (newTheme) => {
    pngBgColor.value = newTheme === 'dark' ? '#1F2937' : '#FFFFFF';
});


const handleWheel = (event) => {
    if (!isVisualContent.value || isInteractiveMermaid.value) return;
    event.preventDefault();
    const scaleAmount = 0.1; const rect = viewerRef.value.getBoundingClientRect();
    const x = event.clientX - rect.left; const y = event.clientY - rect.top;
    const newScale = scale.value + (event.deltaY < 0 ? scaleAmount : -scaleAmount) * scale.value;
    const clampedScale = Math.min(Math.max(0.5, newScale), 10);
    const scaleChange = clampedScale - scale.value;
    posX.value -= (x - posX.value) * (scaleChange / scale.value);
    posY.value -= (y - posY.value) * (scaleChange / scale.value);
    scale.value = clampedScale;
};

const startDrag = (event) => {
    if (!isVisualContent.value || scale.value <= 1 || isInteractiveMermaid.value) return;
    event.preventDefault(); isDragging = true;
    startX = event.clientX - posX.value; startY = event.clientY - posY.value;
    window.addEventListener('mousemove', drag); window.addEventListener('mouseup', stopDrag);
};

const drag = (event) => { if (isDragging) { event.preventDefault(); posX.value = event.clientX - startX; posY.value = event.clientY - startY; } };
const stopDrag = () => { isDragging = false; window.removeEventListener('mousemove', drag); window.removeEventListener('mouseup', stopDrag); };
const zoomIn = () => { if (isVisualContent.value) scale.value = Math.min(10, scale.value + 0.25); };
const zoomOut = () => { if (isVisualContent.value) scale.value = Math.max(0.5, scale.value - 0.25); };

function downloadFile(content, filename, mimeType) { const blob = new Blob([content], { type: mimeType }); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url); }

function downloadSVG() {
    if (data.value?.htmlContent) {
        const match = /<svg[\s\S]*?<\/svg>/.exec(data.value.htmlContent);
        if (match) downloadFile(match[0], `${data.value.title || 'diagram'}.svg`, 'image/svg+xml');
    }
}

function downloadPNG() {
    if (mermaidInstance.value?.exportPNG) {
        const filename = `${data.value.title || 'diagram'}.png`;
        mermaidInstance.value.exportPNG(filename, pngBgColor.value);
    }
}

function downloadSource() { if (data.value?.sourceCode) downloadFile(data.value.sourceCode, `${data.value.title || 'source'}.md`, 'text/markdown'); }

const modalPanelClass = computed(() => isFullScreen.value ? 'w-screen h-screen rounded-none' : 'w-full max-w-4xl h-[80vh] rounded-lg shadow-2xl');
const modalBodyClass = computed(() => isFullScreen.value ? 'p-0' : 'p-4');

</script>

<template>
    <Teleport to="body">
        <Transition enter-active-class="transition-opacity ease-out duration-300" enter-from-class="opacity-0" enter-to-class="opacity-100" leave-active-class="transition-opacity ease-in duration-200" leave-from-class="opacity-100" leave-to-class="opacity-0">
            <div v-if="isOpen" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 flex items-center justify-center" @click.self="closeModal">
                <Transition enter-active-class="transition-all ease-out duration-300" enter-from-class="opacity-0 scale-95" enter-to-class="opacity-100 scale-100" leave-active-class="transition-all ease-in duration-200" leave-from-class="opacity-100 scale-100" leave-to-class="opacity-0 scale-95">
                    <div :class="modalPanelClass" class="bg-white dark:bg-gray-900 flex flex-col max-h-screen transition-all duration-300 ease-in-out">
                        <div v-if="isFullScreen" class="absolute inset-0 bg-gray-800 -z-10 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(120,119,198,0.3),rgba(255,255,255,0))]"></div>
                        <header class="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
                            <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ data?.title || 'Interactive Output' }}</h3>
                            <div class="flex items-center space-x-2">
                                <button @click="toggleFullScreen" class="modal-header-btn" :title="isFullScreen ? 'Exit Fullscreen' : 'Fullscreen'"><IconMinimize v-if="isFullScreen" class="w-5 h-5" /><IconMaximize v-else class="w-5 h-5" /></button>
                                <button @click="closeModal" class="modal-header-btn" title="Close"><IconXMark class="w-5 h-5" /></button>
                            </div>
                        </header>
                        <main class="flex-grow min-h-0 relative" :class="modalBodyClass">
                            <div ref="viewerRef" class="w-full h-full overflow-hidden" @wheel="handleWheel" @mousedown="startDrag">
                                <div v-if="data?.canvasId" class="w-full h-full rounded-md border border-gray-300 dark:border-gray-600 bg-black overflow-hidden"><canvas :id="data.canvasId" class="w-full h-full"></canvas></div>
                                <InteractiveMermaid v-else-if="isInteractiveMermaid" :mermaidCode="data.sourceCode" ref="mermaidInstance" />
                                <div v-else-if="data?.htmlContent" class="w-full h-full" :class="isVisualContent ? '' : 'bg-white rounded-md border border-gray-300 dark:border-gray-600 overflow-hidden'">
                                    <div v-if="isVisualContent" v-html="data.htmlContent" :style="contentStyle" class="w-full h-full transition-transform duration-75"></div>
                                    <iframe v-else :srcdoc="data.htmlContent" class="w-full h-full" sandbox="allow-scripts allow-same-origin"></iframe>
                                </div>
                                <div v-else class="flex items-center justify-center h-full text-gray-500"><p>No interactive content provided.</p></div>
                            </div>
                            <div v-if="isVisualContent" class="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-gray-900/60 text-white p-2 rounded-lg backdrop-blur-md shadow-lg">
                                <template v-if="!isInteractiveMermaid">
                                    <button @click="zoomOut" class="btn-viewer" title="Zoom Out"><IconMinus class="w-5 h-5" /></button>
                                    <button @click="resetView" class="btn-viewer px-3 text-sm font-mono" title="Reset View">{{ Math.round(scale * 100) }}%</button>
                                    <button @click="zoomIn" class="btn-viewer" title="Zoom In"><IconPlus class="w-5 h-5" /></button>
                                    <div class="w-px h-6 bg-white/20 mx-1"></div>
                                </template>
                                <template v-if="isInteractiveMermaid">
                                    <div class="flex items-center gap-2 pr-2">
                                        <label for="png-bg-color" class="text-xs font-medium" title="PNG Background Color">BG:</label>
                                        <input id="png-bg-color" type="color" v-model="pngBgColor" class="w-6 h-6 p-0 border-none rounded cursor-pointer bg-transparent">
                                    </div>
                                    <button @click="downloadPNG" class="btn-viewer" title="Download as PNG"><IconArrowDownTray class="w-5 h-5" /></button>
                                </template>
                                <button v-else @click="downloadSVG" class="btn-viewer" title="Download as SVG"><IconArrowDownTray class="w-5 h-5" /></button>
                                <button v-if="data?.contentType === 'mermaid'" @click="downloadSource" class="btn-viewer" title="Download Mermaid Source"><IconCode class="w-5 h-5" /></button>
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