<!-- [UPDATE] frontend/webui/src/views/ImageEditorView.vue -->
<template>
    <div class="h-full flex flex-col bg-gray-100 dark:bg-gray-950 overflow-hidden relative select-none">
        <!-- Top Toolbar (Full Responsive) -->
        <div class="h-16 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between px-2 sm:px-4 z-20 shadow-sm gap-2 sm:gap-4 overflow-x-auto no-scrollbar">
            <div class="flex items-center gap-1 sm:gap-2 shrink-0">
                <button @click="goBack" class="btn-icon" title="Back"><IconArrowLeft class="w-5 h-5" /></button>
                <div class="h-6 w-px bg-gray-300 dark:bg-gray-600 mx-1 sm:mx-2"></div>
                
                <!-- Full Tool Palette -->
                <div class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5 sm:p-1 gap-0.5 sm:gap-1">
                    <button v-for="t in tools" :key="t.id" 
                        @click="setTool(t.id)" 
                        class="p-1.5 sm:p-2 rounded-md transition-colors"
                        :class="tool === t.id ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                        :title="t.name"
                    >
                        <component :is="t.icon" class="w-5 h-5" />
                    </button>
                </div>
            </div>

            <!-- Dynamic Settings -->
            <div class="flex items-center gap-2 sm:gap-4 flex-grow justify-center whitespace-nowrap px-2">
                <div class="flex items-center gap-2" title="Color">
                    <input type="color" v-model="color" class="w-7 h-7 sm:w-8 sm:h-8 rounded-lg cursor-pointer border-0 p-0 bg-transparent">
                </div>

                <div class="flex items-center gap-2" v-if="['brush', 'eraser', 'line', 'rect', 'circle', 'text'].includes(tool)">
                    <span class="hidden sm:inline text-[10px] font-black text-gray-400 uppercase tracking-tighter">{{ tool === 'text' ? 'Font' : 'Size' }}</span>
                    <input type="range" v-model.number="brushSize" min="1" max="400" class="w-16 sm:w-24 h-2 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer">
                    <span class="text-[10px] font-mono w-6">{{ brushSize }}</span>
                </div>

                <!-- Layer Switcher -->
                <div class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-1 gap-1">
                    <button @click="activeLayer = 'image'" class="px-2 sm:px-3 py-1 text-[10px] sm:text-xs font-black rounded transition-colors uppercase" :class="activeLayer === 'image' ? 'bg-white dark:bg-gray-700 shadow-sm text-blue-600 dark:text-blue-400' : 'text-gray-500'">Image</button>
                    <button @click="activeLayer = 'mask'" class="px-2 sm:px-3 py-1 text-[10px] sm:text-xs font-black rounded transition-colors uppercase" :class="activeLayer === 'mask' ? 'bg-white dark:bg-gray-700 shadow-sm text-blue-600 dark:text-blue-400' : 'text-gray-500'">Mask</button>
                </div>
            </div>

            <!-- Main Actions -->
            <div class="flex items-center gap-1 sm:gap-2 shrink-0">
                <button @click="undo" :disabled="historyIndex <= 0" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-20 transition-opacity"><IconUndo class="w-5 h-5" /></button>
                <button @click="redo" :disabled="historyIndex >= history.length - 1" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-20 transition-opacity"><IconRedo class="w-5 h-5" /></button>
                <button @click="saveCanvas" class="btn btn-primary btn-sm gap-2"><IconSave class="w-4 h-4" /> <span class="hidden sm:inline">Save</span></button>
                <button @click="showMobileSidebar = !showMobileSidebar" class="lg:hidden btn btn-secondary p-2 ml-1"><IconAdjustmentsHorizontal class="w-5 h-5" /></button>
            </div>
        </div>

        <div class="flex-grow flex min-h-0 relative overflow-hidden">
            <!-- Central Paint Canvas -->
            <main ref="containerRef" class="flex-grow bg-gray-200 dark:bg-black relative overflow-hidden flex items-center justify-center cursor-crosshair pattern-grid" @wheel="handleWheel" @mousedown="startAction" @mousemove="handleMove" @mouseup="endAction" @mouseleave="endAction">
                <div :style="combinedCanvasStyle" class="relative shadow-2xl origin-center canvas-stack transition-transform duration-75">
                    <canvas ref="imageCanvasRef" class="block bg-white layer-canvas"></canvas>
                    <canvas ref="maskCanvasRef" class="absolute inset-0 opacity-60 layer-canvas" :class="{'pointer-events-none': activeLayer !== 'mask'}"></canvas>
                    <canvas ref="previewCanvasRef" class="absolute inset-0 pointer-events-none layer-canvas"></canvas>
                    
                    <!-- Brush Cursor -->
                    <div v-show="showCursor" class="absolute pointer-events-none rounded-full border border-black/50 bg-white/20 z-50 transform -translate-x-1/2 -translate-y-1/2 shadow-sm" :style="{ width: `${brushSize}px`, height: `${brushSize}px`, left: `${cursorX}px`, top: `${cursorY}px` }"></div>
                </div>

                <!-- HUD Controls -->
                <div class="absolute bottom-4 left-4 bg-white/90 dark:bg-gray-900/90 backdrop-blur rounded-xl shadow-lg p-1 sm:p-2 flex items-center gap-1 sm:gap-2 z-10 border dark:border-gray-800">
                    <button @click="zoomOut" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><IconMinus class="w-4 h-4" /></button>
                    <span class="text-[10px] font-black font-mono w-10 text-center">{{ Math.round(zoom * 100) }}%</span>
                    <button @click="zoomIn" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><IconPlus class="w-4 h-4" /></button>
                    <button @click="fitToScreen" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded ml-1"><IconMaximize class="w-4 h-4" /></button>
                </div>
            </main>

            <!-- Tools & Inspector Sidebar -->
            <aside class="absolute inset-y-0 right-0 z-30 w-72 sm:w-80 bg-white dark:bg-gray-900 border-l dark:border-gray-800 transform transition-transform duration-300 lg:relative lg:translate-x-0 flex flex-col shadow-xl" :class="showMobileSidebar ? 'translate-x-0' : 'translate-x-full'">
                <div class="p-4 border-b dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50 flex justify-between items-center">
                    <h3 class="font-black text-[10px] uppercase tracking-widest text-gray-500">Editor Inspector</h3>
                    <button @click="showMobileSidebar = false" class="lg:hidden p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"><IconXMark class="w-5 h-5" /></button>
                </div>
                
                <div class="flex-grow overflow-y-auto custom-scrollbar p-1">
                    <div v-for="(group, key) in editLibrary" :key="key" class="p-4 border-b dark:border-gray-800 space-y-4">
                        <div class="flex items-center justify-between cursor-pointer group" @click="collapsedGroups[key] = !collapsedGroups[key]">
                            <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest group-hover:text-blue-500 transition-colors">{{ key }}</span>
                            <IconChevronUp class="w-3 h-3 transition-transform text-gray-500" :class="{'rotate-180': collapsedGroups[key]}" />
                        </div>
                        
                        <div v-show="!collapsedGroups[key]" class="space-y-4 animate-in fade-in slide-in-from-top-1">
                            <template v-if="key === 'Adjustments'">
                                <div class="space-y-3">
                                    <div><div class="flex justify-between text-[9px] font-bold text-gray-500 mb-1"><span>BRIGHTNESS</span><span>{{ Math.round(brightness * 100) }}%</span></div><input type="range" v-model.number="brightness" min="0" max="2" step="0.05" class="w-full h-1.5 bg-gray-200 dark:bg-gray-800 rounded-lg appearance-none cursor-pointer"></div>
                                    <div><div class="flex justify-between text-[9px] font-bold text-gray-500 mb-1"><span>CONTRAST</span><span>{{ Math.round(contrast * 100) }}%</span></div><input type="range" v-model.number="contrast" min="0" max="2" step="0.05" class="w-full h-1.5 bg-gray-200 dark:bg-gray-800 rounded-lg appearance-none cursor-pointer"></div>
                                    <div class="grid grid-cols-2 gap-2">
                                        <button @click="transformImage('greyscale')" class="btn btn-secondary text-[10px] py-1 font-bold">Greyscale</button>
                                        <button @click="transformImage('invert')" class="btn btn-secondary text-[10px] py-1 font-bold">Invert</button>
                                    </div>
                                    <button @click="applyAdjustments" class="btn btn-primary w-full text-[10px] py-2 font-black uppercase tracking-widest">Apply Filters</button>
                                </div>
                            </template>

                            <template v-else-if="key === 'Canvas & Geometry'">
                                <div class="grid grid-cols-2 gap-2">
                                    <button @click="handleZoomOut(0.75)" class="btn btn-secondary text-[10px] py-1.5 font-bold uppercase" title="Scale image down and add blank canvas padding">Outpaint Pad</button>
                                    <button @click="reset3DRotation" class="btn btn-secondary text-[10px] py-1.5 font-bold uppercase">Reset 3D</button>
                                </div>
                                <div class="space-y-2 p-3 bg-gray-50 dark:bg-black/40 rounded-xl border dark:border-gray-800">
                                    <div class="flex justify-between text-[9px] text-gray-400 font-bold uppercase"><span>Tilt X</span><span>{{ rotationX }}°</span></div>
                                    <input type="range" v-model.number="rotationX" min="-45" max="45" class="w-full h-1 bg-gray-200 dark:bg-gray-800 rounded-lg appearance-none cursor-pointer">
                                    <div class="flex justify-between text-[9px] text-gray-400 font-bold uppercase"><span>Swing Y</span><span>{{ rotationY }}°</span></div>
                                    <input type="range" v-model.number="rotationY" min="-45" max="45" class="w-full h-1 bg-gray-200 dark:bg-gray-800 rounded-lg appearance-none cursor-pointer">
                                </div>
                                <div class="grid grid-cols-3 gap-2 pt-2 border-t dark:border-gray-800">
                                    <button @click="transformImage('flip-h')" class="btn btn-secondary p-2" title="Flip Horizontal"><IconArrowsRightLeft class="w-4 h-4 mx-auto" /></button>
                                    <button @click="transformImage('flip-v')" class="btn btn-secondary p-2" title="Flip Vertical"><IconArrowsUpDown class="w-4 h-4 mx-auto" /></button>
                                    <button @click="transformImage('rotate-cw')" class="btn btn-secondary p-2" title="Rotate 90°"><IconArrowPath class="w-4 h-4 mx-auto" /></button>
                                </div>
                            </template>

                            <template v-else>
                                <div class="flex flex-wrap gap-1.5">
                                    <button v-for="p in group" :key="p.name" @click="applyInpaintPreset(p.prompt)" class="px-2 py-1 bg-gray-50 dark:bg-gray-800 text-[9px] border dark:border-gray-700 rounded-lg hover:border-blue-500 transition-all uppercase font-black text-gray-600 dark:text-gray-300">{{ p.name }}</button>
                                </div>
                            </template>
                        </div>
                    </div>
                    
                    <!-- AI Prompt Context -->
                    <div class="p-4 space-y-4">
                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest">AI Context Prompt</label>
                                <button @click="initiateEnhancement('prompt')" class="text-blue-500 hover:scale-110 transition-transform" :disabled="isProcessingTask"><IconSparkles class="w-4 h-4" /></button>
                            </div>
                            <textarea v-model="prompt" rows="3" class="input-field w-full text-xs resize-none shadow-inner" placeholder="Instructions for the AI..."></textarea>
                        </div>
                        <div>
                            <label class="text-[10px] font-black text-gray-400 uppercase tracking-widest">Model</label>
                            <select v-model="selectedModel" class="input-field w-full text-xs mt-1">
                                <option v-for="m in compatibleModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- Primary Action Button -->
                <div class="p-4 border-t dark:border-gray-800 bg-gray-50 dark:bg-gray-900/80">
                    <button @click="generateEdit" class="btn btn-primary w-full py-3 shadow-xl transform active:scale-95 transition-all" :disabled="isProcessingTask">
                        <template v-if="isProcessingTask"><IconAnimateSpin class="w-5 h-5 mr-2 animate-spin" /> GENERATING...</template>
                        <template v-else><IconSparkles class="w-5 h-5 mr-2" /> {{ activeLayer === 'mask' ? 'INPAINT MASK' : 'FULL GENERATE' }}</template>
                    </button>
                </div>
            </aside>

            <!-- Interaction Shield -->
            <div v-if="showMobileSidebar" @click="showMobileSidebar = false" class="absolute inset-0 bg-black/50 z-20 lg:hidden backdrop-blur-xs"></div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, h, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useImageStore } from '../stores/images';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import apiClient from '../services/api';
import useEventBus from '../services/eventBus';

import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';
import IconHand from '../assets/icons/IconHand.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconEraser from '../assets/icons/IconEraser.vue';
import IconUndo from '../assets/icons/IconUndo.vue';
import IconRedo from '../assets/icons/IconRedo.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconSave from '../assets/icons/IconSave.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconMinus from '../assets/icons/IconMinus.vue';
import IconMaximize from '../assets/icons/IconMaximize.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconType from '../assets/icons/IconType.vue';
import IconChevronUp from '../assets/icons/IconChevronUp.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconAdjustmentsHorizontal from '../assets/icons/IconAdjustmentsHorizontal.vue';
import IconCircle from '../assets/icons/IconCircle.vue';

// Functional Icons
const IconArrowsRightLeft = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M17 3l4 4-4 4' }), h('path', { d: 'M3 7h18' }), h('path', { d: 'M7 13l-4 4 4 4' }), h('path', { d: 'M3 17h18' })]) };
const IconArrowsUpDown = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M7 17l4 4 4-4' }), h('path', { d: 'M11 3v18' }), h('path', { d: 'M17 7l-4-4-4 4' }), h('path', { d: 'M13 3v18' })]) };
const IconArrowPath = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M20 11a8.1 8.1 0 0 0-15.5-2m-.5 5v-5h5' }), h('path', { d: 'M4 13a8.1 8.1 0 0 0 15.5 2m.5-5v5h-5' })]) };
const IconRect = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('rect', { x: '3', y: '3', width: '18', height: '18', rx: '2' })]) };
const IconLine = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2', 'stroke-linecap': 'round' }, [h('path', { d: 'M5 19L19 5' })]) };
const IconWand = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M15 4V2M15 16V14M8 9h2M20 9h2M17.8 11.8L19 13M10.6 5.2L12 6.6M11.6 12.2l-8.4 8.6' })]) };

const props = defineProps({ id: { type: String, default: null } });
const router = useRouter();
const imageStore = useImageStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const { on, off } = useEventBus();

const isComponentMounted = ref(false), showMobileSidebar = ref(false);
const containerRef = ref(null), imageCanvasRef = ref(null), maskCanvasRef = ref(null), previewCanvasRef = ref(null);
const ctxImage = ref(null), ctxMask = ref(null), ctxPreview = ref(null);

const collapsedGroups = ref({ 'Adjustments': false, 'Canvas & Geometry': false, 'Style Presets': true, 'Hair & Color': true, 'AI Retouch': true });
const editLibrary = {
    'Adjustments': [], 'Canvas & Geometry': [],
    'AI Retouch': [
        { name: 'Skin Smooth', prompt: 'retouch skin, smooth texture, highly detailed facial features' },
        { name: 'Sharpen', prompt: 'ultra sharp details, enhance micro texture, high resolution' },
        { name: 'Remove Object', prompt: 'fill area seamlessly with background context, inpaint' }
    ],
    'Style Presets': [
        { name: 'Watercolor', prompt: 'transform area into watercolor painting style, soft paper texture' },
        { name: 'Oil Paint', prompt: 'transform area into thick oil painting brushstrokes, classical art style' },
        { name: 'Anime', prompt: 'transform area into vibrant 2d anime art style, cel shaded' }
    ],
    'Hair & Color': [
        { name: 'Mohawk', prompt: 'a sharp mohawk haircut, highly detailed hair' },
        { name: 'Bob Cut', prompt: 'a stylish bob haircut, chin-length' },
        { name: 'Bald', prompt: 'a clean bald head' },
        { name: 'Crimson Hair', prompt: 'vibrant crimson red hair color' },
        { name: 'Neon Green', prompt: 'glowing neon green hair color' }
    ]
};

const activeLayer = ref('image'), tool = ref('brush'), color = ref('#000000'), brushSize = ref(40), opacity = ref(1.0), tolerance = ref(10), brightness = ref(1.0), contrast = ref(1.0), rotationX = ref(0), rotationY = ref(0), zoom = ref(1), panX = ref(0), panY = ref(0), prompt = ref(''), strength = ref(0.75), seed = ref(-1), selectedModel = ref(''), isProcessingTask = ref(false), isEnhancing = ref(false), activeTaskId = ref(null), isDragging = ref(false), lastX = ref(0), lastY = ref(0), cursorX = ref(0), cursorY = ref(0), startX = ref(0), startY = ref(0), history = ref([]), historyIndex = ref(-1);

const tools = [ { id: 'pan', name: 'Pan', icon: IconHand }, { id: 'brush', name: 'Brush', icon: IconPencil }, { id: 'eraser', name: 'Eraser', icon: IconEraser }, { id: 'text', name: 'Text', icon: IconType }, { id: 'wand', name: 'Wand', icon: IconWand }, { id: 'line', name: 'Line', icon: IconLine }, { id: 'rect', name: 'Rect', icon: IconRect }, { id: 'circle', name: 'Circle', icon: IconCircle } ];
const compatibleModels = computed(() => dataStore.availableTtiModels);
const showCursor = computed(() => ['brush', 'eraser', 'circle', 'text'].includes(tool.value) && tool.value !== 'pan');
const combinedCanvasStyle = computed(() => ({ transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value}) perspective(1000px) rotateX(${rotationX.value}deg) rotateY(${rotationY.value}deg)` }));

function setTool(t) { tool.value = t; }
function applyInpaintPreset(p) { activeLayer.value = 'mask'; prompt.value = p; uiStore.addNotification("Preset applied to prompt.", "info"); }
function reset3DRotation() { rotationX.value = 0; rotationY.value = 0; }

onMounted(async () => {
    isComponentMounted.value = true; on('prompt:enhanced', onPromptEnhanced); on('image:generated', onImageGenerated); on('task:completed', onTaskCompleted);
    if (imageCanvasRef.value) ctxImage.value = imageCanvasRef.value.getContext('2d', { willReadFrequently: true });
    if (maskCanvasRef.value) ctxMask.value = maskCanvasRef.value.getContext('2d', { willReadFrequently: true });
    if (previewCanvasRef.value) ctxPreview.value = previewCanvasRef.value.getContext('2d');
    if (props.id === 'new') promptForNewCanvas(); else if (props.id) await loadImage(props.id);
    if (authStore.user) selectedModel.value = authStore.user.iti_binding_model_name || authStore.user.tti_binding_model_name || '';
    window.addEventListener('keydown', handleKeydown); window.addEventListener('resize', fitToScreen);
});

onUnmounted(() => { isComponentMounted.value = false; off('prompt:enhanced', onPromptEnhanced); off('image:generated', onImageGenerated); off('task:completed', onTaskCompleted); window.removeEventListener('keydown', handleKeydown); window.removeEventListener('resize', fitToScreen); });

async function promptForNewCanvas() {
    const { confirmed, value } = await uiStore.showConfirmation({ title: 'Canvas Size', inputType: 'select', inputOptions: [{ text: '1:1', value: '1024x1024' }, { text: '16:9', value: '1344x768' }, { text: '9:16', value: '768x1344' }], inputValue: '1024x1024' });
    if (confirmed && value) { const [w, h] = value.split('x').map(Number); initializeBlankCanvas(w, h); } else router.push('/image-studio');
}

function initializeBlankCanvas(w, h) { resizeCanvases(w, h); ctxImage.value.fillStyle = '#FFFFFF'; ctxImage.value.fillRect(0, 0, w, h); saveState(); fitToScreen(); }
async function loadImage(id) { try { const res = await apiClient.get(`/api/image-studio/${id}/file`, { responseType: 'blob' }); const img = new Image(); await new Promise((r, j) => { img.onload = r; img.onerror = j; img.src = URL.createObjectURL(res.data); }); resizeCanvases(img.naturalWidth, img.naturalHeight); ctxImage.value.drawImage(img, 0, 0); saveState(); fitToScreen(); } catch (e) { router.push('/image-studio'); } }
function resizeCanvases(w, h) { [imageCanvasRef, maskCanvasRef, previewCanvasRef].forEach(r => { if (r.value) { r.value.width = w; r.value.height = h; } }); }

function getPointerPos(e) { const r = imageCanvasRef.value.getBoundingClientRect(); const sX = imageCanvasRef.value.width / r.width, sY = imageCanvasRef.value.height / r.height; return { x: (e.clientX - r.left) * sX, y: (e.clientY - r.top) * sY }; }
function startAction(e) { if (e.button !== 0) return; isDragging.value = true; const { x, y } = getPointerPos(e); lastX.value = e.clientX; lastY.value = e.clientY; startX.value = x; startY.value = y; if (tool.value === 'text') { const t = prompt("Text:"); if (t) { const c = getActiveCtx(); configureCtx(c); c.font = `bold ${brushSize.value}px sans-serif`; c.textBaseline = 'middle'; c.fillText(t, x, y); saveState(); } isDragging.value = false; } else if (['brush', 'eraser'].includes(tool.value)) { getActiveCtx().beginPath(); getActiveCtx().moveTo(x, y); draw(x, y); } }
function handleMove(e) { const { x, y } = getPointerPos(e); cursorX.value = x; cursorY.value = y; if (!isDragging.value) return; if (tool.value === 'pan') { panX.value += e.clientX - lastX.value; panY.value += e.clientY - lastY.value; lastX.value = e.clientX; lastY.value = e.clientY; } else if (['brush', 'eraser'].includes(tool.value)) draw(x, y); else if (['line', 'rect', 'circle'].includes(tool.value)) drawPreviewShape(x, y); }
function endAction() { if (!isDragging.value) return; isDragging.value = false; if (['line', 'rect', 'circle'].includes(tool.value)) commitShape(getPointerPos({ clientX: lastX.value, clientY: lastY.value })); if (!['pan', 'text'].includes(tool.value)) saveState(); }

function getActiveCtx() { return activeLayer.value === 'image' ? ctxImage.value : ctxMask.value; }
function configureCtx(c) { c.lineCap = 'round'; c.lineJoin = 'round'; c.lineWidth = brushSize.value; if (tool.value === 'eraser') c.globalCompositeOperation = 'destination-out'; else { c.globalCompositeOperation = 'source-over'; c.globalAlpha = opacity.value; c.fillStyle = activeLayer.value === 'mask' ? '#FFF' : color.value; c.strokeStyle = activeLayer.value === 'mask' ? '#FFF' : color.value; } }
function draw(x, y) { const c = getActiveCtx(); configureCtx(c); c.lineTo(x, y); c.stroke(); c.beginPath(); c.moveTo(x, y); }
function drawPreviewShape(x, y) { const c = ctxPreview.value; c.clearRect(0, 0, c.canvas.width, c.canvas.height); configureCtx(c); c.beginPath(); if (tool.value === 'line') { c.moveTo(startX.value, startY.value); c.lineTo(x, y); } else if (tool.value === 'rect') c.rect(startX.value, startY.value, x - startX.value, y - startY.value); else if (tool.value === 'circle') c.arc(startX.value, startY.value, Math.sqrt(Math.pow(x - startX.value, 2) + Math.pow(y - startY.value, 2)), 0, 2 * Math.PI); c.stroke(); if (tool.value !== 'line') c.fill(); }
function commitShape(pos) { ctxPreview.value.clearRect(0, 0, previewCanvasRef.value.width, previewCanvasRef.value.height); const c = getActiveCtx(); configureCtx(c); c.beginPath(); if (tool.value === 'line') { c.moveTo(startX.value, startY.value); c.lineTo(pos.x, pos.y); c.stroke(); } else if (tool.value === 'rect') { c.rect(startX.value, startY.value, pos.x - startX.value, pos.y - startY.value); c.fill(); c.stroke(); } else if (tool.value === 'circle') { c.arc(startX.value, startY.value, Math.sqrt(Math.pow(pos.x - startX.value, 2) + Math.pow(pos.y - startY.value, 2)), 0, 2 * Math.PI); c.fill(); c.stroke(); } c.globalAlpha = 1.0; c.globalCompositeOperation = 'source-over'; }

function applyAdjustments() { const c = ctxImage.value; const d = c.getImageData(0,0,c.canvas.width,c.canvas.height); const data = d.data, b = brightness.value, con = contrast.value, intercept = 128 * (1 - con); for (let i = 0; i < data.length; i += 4) { data[i] = data[i] * b * con + intercept; data[i+1] = data[i+1] * b * con + intercept; data[i+2] = data[i+2] * b * con + intercept; } c.putImageData(d, 0, 0); saveState(); uiStore.addNotification("Adjustments applied.", "success"); }
function handleZoomOut(f) { const c = ctxImage.value; const w = c.canvas.width, h = c.canvas.height; const temp = document.createElement('canvas'); temp.width = w; temp.height = h; const t = temp.getContext('2d'); t.fillStyle = '#FFF'; t.fillRect(0,0,w,h); const nw = w * f, nh = h * f; t.drawImage(c.canvas, (w-nw)/2, (h-nh)/2, nw, nh); c.clearRect(0,0,w,h); c.drawImage(temp, 0,0); ctxMask.value.fillStyle = '#FFF'; ctxMask.value.fillRect(0,0,w,(h-nh)/2); ctxMask.value.fillRect(0,h-(h-nh)/2,w,(h-nh)/2); ctxMask.value.fillRect(0,(h-nh)/2,(w-nw)/2,nh); ctxMask.value.fillRect(w-(w-nw)/2,(h-nh)/2,(w-nw)/2,nh); activeLayer.value = 'mask'; saveState(); }
function transformImage(a) { const c = getActiveCtx(); const canvas = c.canvas; const temp = document.createElement('canvas'); temp.width = canvas.width; temp.height = canvas.height; const t = temp.getContext('2d'); if (a === 'flip-h') { t.scale(-1, 1); t.drawImage(canvas, -canvas.width, 0); } else if (a === 'flip-v') { t.scale(1, -1); t.drawImage(canvas, 0, -canvas.height); } else if (a === 'rotate-cw') { temp.width = canvas.height; temp.height = canvas.width; t.translate(temp.width/2, temp.height/2); t.rotate(Math.PI/2); t.drawImage(canvas, -canvas.width/2, -canvas.height/2); resizeCanvases(temp.width, temp.height); } else if (a === 'greyscale' || a === 'invert') { const d = c.getImageData(0,0,canvas.width,canvas.height); for (let i = 0; i < d.data.length; i += 4) { if (a === 'greyscale') { const avg = (d.data[i]+d.data[i+1]+d.data[i+2])/3; d.data[i]=avg; d.data[i+1]=avg; d.data[i+2]=avg; } else { d.data[i]=255-d.data[i]; d.data[i+1]=255-d.data[i+1]; d.data[i+2]=255-d.data[i+2]; } } c.putImageData(d,0,0); saveState(); return; } c.clearRect(0,0,canvas.width,canvas.height); c.drawImage(temp,0,0); saveState(); }

async function generateEdit() { isProcessingTask.value = true; try { const b64 = imageCanvasRef.value.toDataURL('image/png').split(',')[1]; const temp = document.createElement('canvas'); temp.width = maskCanvasRef.value.width; temp.height = maskCanvasRef.value.height; const t = temp.getContext('2d'); t.fillStyle = '#000'; t.fillRect(0,0,temp.width,temp.height); t.drawImage(maskCanvasRef.value,0,0); const m64 = temp.toDataURL('image/png').split(',')[1]; const tsk = await imageStore.editImage({ base_image_b64: b64, mask: m64, prompt: prompt.value, strength: strength.value, seed: seed.value, model: selectedModel.value, width: imageCanvasRef.value.width, height: imageCanvasRef.value.height }); if (tsk?.id) activeTaskId.value = tsk.id; } catch (e) { isProcessingTask.value = false; } }
async function generateDepthMap() { isProcessingTask.value = true; const b64 = imageCanvasRef.value.toDataURL('image/png').split(',')[1]; const tsk = await imageStore.editImage({ base_image_b64: b64, prompt: "depth map, grayscale", model: selectedModel.value, width: imageCanvasRef.value.width, height: imageCanvasRef.value.height }); if (tsk?.id) activeTaskId.value = tsk.id; }
function initiateEnhancement(t) { uiStore.openModal('enhancePrompt', { onConfirm: (o) => { isEnhancing.value = true; isProcessingTask.value = true; imageStore.enhanceImagePrompt({ prompt: prompt.value, target: t, model: authStore.user?.lollms_model_name, ...o, image_b64s: [imageCanvasRef.value.toDataURL().split(',')[1]] }).then(tsk => { if(tsk?.id) activeTaskId.value = tsk.id; }); } }); }

function saveCanvas() { const b64 = imageCanvasRef.value.toDataURL('image/png').split(',')[1]; imageStore.saveCanvasAsNewImage({ base_image_b64: b64, prompt: prompt.value || "Edited", width: imageCanvasRef.value.width, height: imageCanvasRef.value.height, model: selectedModel.value }); }
function fitToScreen() { if (!containerRef.value || !imageCanvasRef.value) return; const cw = containerRef.value.clientWidth, ch = containerRef.value.clientHeight, iw = imageCanvasRef.value.width, ih = imageCanvasRef.value.height; if (!iw) return; zoom.value = Math.min((cw-40)/iw, (ch-40)/ih, 1); panX.value=0; panY.value=0; }
function handleWheel(e) { if (e.ctrlKey || tool.value === 'pan') { e.preventDefault(); zoom.value = Math.min(Math.max(0.1, zoom.value - Math.sign(e.deltaY)*0.1), 5); } }
function zoomIn() { zoom.value = Math.min(5, zoom.value + 0.1); }
function zoomOut() { zoom.value = Math.max(0.1, zoom.value - 0.1); }
function goBack() { router.push('/image-studio'); }
function saveState() { if (historyIndex.value < history.value.length - 1) history.value = history.value.slice(0, historyIndex.value + 1); history.value.push({ image: imageCanvasRef.value.toDataURL(), mask: maskCanvasRef.value.toDataURL() }); historyIndex.value++; if (history.value.length > 20) { history.value.shift(); historyIndex.value--; } }
function onPromptEnhanced(d) { if (isComponentMounted.value) { prompt.value = d.prompt || prompt.value; isEnhancing.value = false; isProcessingTask.value = false; } }
function onImageGenerated(i) { if (isComponentMounted.value && i) { loadImage(i.id); isProcessingTask.value = false; } }
function onTaskCompleted(t) { if (isComponentMounted.value && t.id === activeTaskId.value) { isProcessingTask.value = false; isEnhancing.value = false; } }
function handleKeydown(e) { if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return; const m = { ' ': 'pan', 'b': 'brush', 'e': 'eraser', 't': 'text', 'w': 'wand', 'l': 'line', 'r': 'rect', 'c': 'circle' }; if (m[e.key.toLowerCase()]) tool.value = m[e.key.toLowerCase()]; if ((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==='z') undo(); if ((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==='y') redo(); }
</script>

<style scoped>
.pattern-grid { background-image: linear-gradient(45deg, #e5e7eb 25%, transparent 25%), linear-gradient(-45deg, #e5e7eb 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #e5e7eb 75%), linear-gradient(-45deg, transparent 75%, #e5e7eb 75%); background-size: 20px 20px; background-position: 0 0, 0 10px, 10px -10px, -10px 0px; }
.dark .pattern-grid { background-image: linear-gradient(45deg, #1f2937 25%, transparent 25%), linear-gradient(-45deg, #1f2937 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #1f2937 75%), linear-gradient(-45deg, transparent 75%, #1f2937 75%); }
.layer-canvas { image-rendering: pixelated; transition: transform 0.1s ease-out; }
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background-color: rgba(156, 163, 175, 0.5); border-radius: 20px; }
.no-scrollbar::-webkit-scrollbar { display: none; }
.no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
</style>
