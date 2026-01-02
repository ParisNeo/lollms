<template>
    <!-- TELEPORT EDITOR TOOLBAR TO GLOBAL HEADER -->
    <Teleport to="#global-header-title-target" v-if="isComponentMounted && hasHeaderTarget">
        <div class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5 sm:p-1 gap-0.5 sm:gap-1 pointer-events-auto shadow-inner border dark:border-gray-700">
            <button v-for="t in tools" :key="t.id" 
                @click="setTool(t.id)" 
                class="p-1.5 sm:p-2 rounded-md transition-all transform active:scale-90 relative z-10"
                :class="tool === t.id ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                :title="t.name"
            >
                <component :is="t.icon" class="w-4 h-4 sm:w-5 sm:h-5" />
            </button>
        </div>
    </Teleport>

    <Teleport to="#global-header-actions-target" v-if="isComponentMounted && hasHeaderTarget">
        <div class="flex items-center gap-1 sm:gap-2 shrink-0 pointer-events-auto">
            <!-- Undo/Redo -->
            <button @click="undo" :disabled="historyIndex <= 0" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-20 transition-opacity" title="Undo (Ctrl+Z)"><IconUndo class="w-5 h-5" /></button>
            <button @click="redo" :disabled="historyIndex >= history.length - 1" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded disabled:opacity-20 transition-opacity" title="Redo (Ctrl+Y)"><IconRedo class="w-5 h-5" /></button>
            
            <div class="h-6 w-px bg-gray-300 dark:bg-gray-600 mx-1"></div>

            <!-- Global Actions -->
            <div class="flex items-center gap-1">
                <button @click="saveProject" class="btn btn-secondary btn-sm" title="Save Multi-Layer Project">
                    <IconFolder class="w-4 h-4 mr-1"/> <span class="hidden sm:inline">Project</span>
                </button>
                <button @click="saveCanvas" class="btn btn-primary btn-sm" title="Flatten and Save PNG">
                    <IconSave class="w-4 h-4 mr-1" /> <span class="hidden sm:inline">PNG</span>
                </button>
            </div>
            
            <button @click="showMobileSidebar = !showMobileSidebar" class="lg:hidden btn btn-secondary p-2 ml-1"><IconAdjustmentsHorizontal class="w-5 h-5" /></button>
        </div>
    </Teleport>

    <div class="h-full flex flex-col bg-gray-100 dark:bg-gray-950 overflow-hidden relative select-none">
        
        <!-- Tool Settings Bar -->
        <div class="absolute top-4 left-1/2 -translate-x-1/2 z-30 flex items-center gap-4 bg-white/90 dark:bg-gray-900/90 backdrop-blur px-4 py-2 rounded-2xl shadow-xl border dark:border-gray-800">
            <!-- Color Picker -->
            <div class="flex items-center gap-2" v-if="['brush', 'line', 'rect', 'circle', 'text'].includes(tool)">
                <input type="color" v-model="color" class="w-6 h-6 rounded cursor-pointer border-0 p-0 bg-transparent">
            </div>
            
            <!-- Size / Font Slider -->
            <div class="flex items-center gap-2" v-if="['brush', 'eraser', 'line', 'rect', 'circle', 'text', 'clone', 'wand'].includes(tool)">
                <span class="text-[9px] font-black text-gray-400 uppercase tracking-tighter">
                    {{ tool === 'text' ? 'Font' : (tool === 'wand' ? 'Tolerance' : 'Size') }}
                </span>
                <input type="range" v-model.number="brushSize" :min="tool === 'wand' ? 0 : 1" :max="tool === 'wand' ? 100 : 400" class="w-24 sm:w-32 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-lg appearance-none cursor-pointer">
                <span class="text-[10px] font-mono w-6 text-center">{{ brushSize }}</span>
            </div>

            <!-- Clone Tool Anchor Actions -->
            <div v-if="tool === 'clone'" class="flex items-center gap-2 border-l dark:border-gray-700 pl-4">
                <button @click="settingCloneAnchor = true" class="btn btn-xs" :class="settingCloneAnchor ? 'btn-primary' : 'btn-secondary'">
                    Set Anchor
                </button>
            </div>
        </div>

        <div class="flex-grow flex min-h-0 relative overflow-hidden">
            <!-- Central Viewport -->
            <main ref="containerRef" class="flex-grow bg-gray-200 dark:bg-black relative overflow-hidden flex items-center justify-center cursor-crosshair pattern-grid" 
                @wheel="handleWheel" 
                @mousedown="startAction" 
                @mousemove="handleMove" 
                @mouseup="endAction" 
                @mouseleave="endAction">
                
                <!-- PROGRESS OVERLAY -->
                <transition name="fade">
                    <div v-if="isProcessingTask" class="absolute inset-0 z-[100] flex flex-col items-center justify-center bg-gray-900/40 backdrop-blur-[2px]">
                        <div class="w-64 bg-white/10 p-4 rounded-2xl border border-white/20 shadow-2xl">
                             <div class="flex justify-between items-center mb-2">
                                 <span class="text-[10px] font-black text-white uppercase tracking-[0.2em] animate-pulse">Processing...</span>
                                 <span class="text-xs font-mono text-white">{{ activeTask?.progress || 0 }}%</span>
                             </div>
                             <div class="h-2 w-full bg-black/40 rounded-full overflow-hidden">
                                 <div class="h-full bg-blue-500 transition-all duration-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]" :style="{ width: `${activeTask?.progress || 0}%` }"></div>
                             </div>
                             <p class="mt-3 text-[10px] text-gray-300 italic text-center truncate">{{ activeTask?.description }}</p>
                        </div>
                    </div>
                </transition>

                <!-- Layer Composition Container -->
                <div :style="combinedCanvasStyle" class="relative shadow-2xl origin-center canvas-stack">
                    <!-- Base Layer (Always Bottom) -->
                    <canvas ref="imageCanvasRef" class="block bg-white layer-canvas"></canvas>
                    
                    <!-- Dynamic User Layers -->
                    <div v-for="layer in layers" :key="layer.id" v-show="layer.visible">
                         <canvas :ref="el => layer.el = el" class="absolute inset-0 layer-canvas" :style="{ zIndex: layer.order, opacity: layer.opacity }"></canvas>
                    </div>

                    <!-- AI Mask Layer (Inpaint Selection) -->
                    <canvas ref="maskCanvasRef" class="absolute inset-0 opacity-40 layer-canvas pointer-events-none" style="z-index: 999"></canvas>
                    
                    <!-- Drawing Tool Preview Layer -->
                    <canvas ref="previewCanvasRef" class="absolute inset-0 pointer-events-none layer-canvas" style="z-index: 1000"></canvas>
                    
                    <!-- Brush Cursor -->
                    <div v-show="showCursor" class="absolute pointer-events-none rounded-full border border-black/50 bg-white/20 z-[1100] transform -translate-x-1/2 -translate-y-1/2" :style="{ width: `${brushSize}px`, height: `${brushSize}px`, left: `${cursorX}px`, top: `${cursorY}px` }"></div>
                    
                    <!-- Clone Anchor Marker -->
                    <div v-if="cloneAnchor" class="absolute pointer-events-none z-[1100] flex items-center justify-center transform -translate-x-1/2 -translate-y-1/2" :style="{ left: `${cloneAnchor.x}px`, top: `${cloneAnchor.y}px` }">
                        <div class="w-4 h-4 border-2 border-green-500 rounded-full animate-ping"></div>
                        <div class="absolute w-px h-6 bg-green-500"></div>
                        <div class="absolute h-px w-6 bg-green-500"></div>
                    </div>
                </div>

                <!-- HUD -->
                <div class="absolute bottom-4 left-4 bg-white/90 dark:bg-gray-900/90 backdrop-blur rounded-xl shadow-lg p-2 flex items-center gap-2 z-10 border dark:border-gray-800">
                    <button @click="zoomOut" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><IconMinus class="w-4 h-4" /></button>
                    <span class="text-[10px] font-black font-mono w-10 text-center">{{ Math.round(zoom * 100) }}%</span>
                    <button @click="zoomIn" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><IconPlus class="w-4 h-4" /></button>
                    <button @click="fitToScreen" class="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded ml-1" title="Fit to Screen"><IconMaximize class="w-4 h-4" /></button>
                </div>
            </main>

            <!-- Inspector Sidebar -->
            <aside class="absolute inset-y-0 right-0 z-30 w-72 sm:w-80 bg-white dark:bg-gray-900 border-l dark:border-gray-800 transform transition-transform lg:relative lg:translate-x-0 flex flex-col shadow-xl" :class="showMobileSidebar ? 'translate-x-0' : 'translate-x-full'">
                <div class="p-4 border-b dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
                    <h3 class="font-black text-[10px] uppercase tracking-widest text-gray-500">Layers & Timeline</h3>
                </div>
                
                <div class="flex-grow overflow-y-auto custom-scrollbar">
                    
                    <!-- LAYER MANAGER -->
                    <div class="p-4 border-b dark:border-gray-800 space-y-3">
                        <div class="flex items-center justify-between">
                            <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest">Workspace Layers</span>
                            <button @click="addNewLayer" class="text-blue-500 hover:scale-110 transition-transform"><IconPlus class="w-4 h-4"/></button>
                        </div>
                        
                        <div class="space-y-1">
                             <div @click="activeLayerId = 'mask'" class="layer-item group" :class="{'active': activeLayerId === 'mask'}">
                                <IconPhoto class="w-3.5 h-3.5 opacity-50"/>
                                <span class="text-xs font-bold truncate flex-grow">Selection Mask</span>
                            </div>

                            <div v-for="layer in sortedLayers" :key="layer.id" @click="activeLayerId = layer.id" class="layer-item group" :class="{'active': activeLayerId === layer.id}">
                                <button @click.stop="layer.visible = !layer.visible" class="p-1">
                                    <IconEye v-if="layer.visible" class="w-3.5 h-3.5 text-blue-500"/>
                                    <IconEyeOff v-else class="w-3.5 h-3.5 text-gray-500"/>
                                </button>
                                <span class="text-xs truncate flex-grow" :class="layer.id === 'base' ? 'font-black' : ''">{{ layer.name }}</span>
                                <button v-if="layer.id !== 'base'" @click.stop="deleteLayer(layer.id)" class="opacity-0 group-hover:opacity-100 p-1 text-red-400 hover:text-red-500"><IconTrash class="w-3.5 h-3.5"/></button>
                            </div>
                        </div>
                    </div>

                    <!-- AI LAYER GENERATOR -->
                    <div class="p-4 border-b dark:border-gray-800 space-y-4">
                        <div class="flex items-center justify-between">
                            <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest">Generate Element</span>
                            <button @click="initiateEnhancement" class="text-blue-500 hover:scale-110 transition-transform"><IconSparkles class="w-4 h-4"/></button>
                        </div>
                        <textarea v-model="prompt" rows="3" class="input-field w-full text-xs resize-none" placeholder="Describe the element to add to current layer..."></textarea>
                        
                        <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-800 p-2 rounded-lg border dark:border-gray-700">
                             <span class="text-[9px] font-black uppercase text-gray-500">Remove BG</span>
                             <button @click="aiRemoveBg = !aiRemoveBg" :class="aiRemoveBg ? 'bg-green-500' : 'bg-gray-400'" class="w-8 h-4 rounded-full relative transition-colors">
                                 <div class="absolute top-0.5 w-3 h-3 bg-white rounded-full transition-all" :style="{ left: aiRemoveBg ? '16px' : '2px' }"></div>
                             </button>
                        </div>

                        <select v-model="selectedModel" class="input-field w-full text-xs">
                            <option v-for="m in compatibleModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                        </select>
                        
                        <button @click="generateNewLayerElement" class="btn btn-primary w-full py-2 shadow-md flex items-center justify-center gap-2" :disabled="isProcessingTask">
                            <IconPlus class="w-4 h-4"/> <span>Generate To New Layer</span>
                        </button>
                    </div>

                    <!-- ADJUSTMENTS -->
                    <div class="p-4 space-y-4">
                        <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest">Active Layer Opacity</span>
                        <input type="range" v-model.number="activeLayer.opacity" min="0" max="1" step="0.05" class="w-full h-1.5 bg-gray-200 dark:bg-gray-800 rounded-lg appearance-none cursor-pointer">
                    </div>
                </div>

                <div class="p-4 border-t dark:border-gray-800 bg-gray-50 dark:bg-gray-900/80">
                    <button @click="generateFlattenedEdit" class="btn btn-primary w-full py-3 shadow-xl transform active:scale-95 transition-all" :disabled="isProcessingTask">
                        <IconSparkles class="w-5 h-5 mr-2" /> {{ activeLayerId === 'mask' ? 'INPAINT SELECTION' : 'RENDER COMPOSITION' }}
                    </button>
                </div>
            </aside>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, h, watch, nextTick, markRaw } from 'vue';
import { useRouter } from 'vue-router';
import { useImageStore } from '../stores/images';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import { useTasksStore } from '../stores/tasks';
import apiClient from '../services/api';
import useEventBus from '../services/eventBus';

import IconHand from '../assets/icons/IconHand.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconEraser from '../assets/icons/IconEraser.vue';
import IconUndo from '../assets/icons/IconUndo.vue';
import IconRedo from '../assets/icons/IconRedo.vue';
import IconSave from '../assets/icons/IconSave.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconMinus from '../assets/icons/IconMinus.vue';
import IconMaximize from '../assets/icons/IconMaximize.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconType from '../assets/icons/IconType.vue';
import IconEye from '../assets/icons/IconEye.vue';
import IconEyeOff from '../assets/icons/IconEyeOff.vue';
import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconXMark from '../assets/icons/IconXMark.vue';
import IconAdjustmentsHorizontal from '../assets/icons/IconAdjustmentsHorizontal.vue';
import IconChevronUp from '../assets/icons/IconChevronUp.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconArrowPath from '../assets/icons/IconArrowPath.vue';
import IconCircle from '../assets/icons/IconCircle.vue';
import IconFolder from '../assets/icons/IconFolder.vue';

const IconLine = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M5 19L19 5' })]) };
const IconRect = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('rect', { x: '3', y: '3', width: '18', height: '18', rx: '2' })]) };
const IconWand = { render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M15 4V2M15 16V14M8 9h2M20 9h2M17.8 11.8L19 13M10.6 5.2L12 6.6M11.6 12.2l-8.4 8.6' })]) };

const props = defineProps({ id: { type: String, default: null } });
const router = useRouter();
const imageStore = useImageStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const tasksStore = useTasksStore();
const { on, off } = useEventBus();

const isComponentMounted = ref(false), hasHeaderTarget = ref(false), isLoadingImage = ref(false), showMobileSidebar = ref(false);
const containerRef = ref(null), imageCanvasRef = ref(null), maskCanvasRef = ref(null), previewCanvasRef = ref(null);
const ctxMask = ref(null), ctxPreview = ref(null);

const activeLayerId = ref('base'), tool = ref('brush'), color = ref('#000000'), brushSize = ref(40), zoom = ref(1), panX = ref(0), panY = ref(0), prompt = ref(''), selectedModel = ref(''), isProcessingTask = ref(false), activeTaskId = ref(null), aiRemoveBg = ref(true);
const brightness = ref(1.0), contrast = ref(1.0);

const layers = ref([
    { id: 'base', name: 'Original Plate', visible: true, order: 0, el: null, ctx: null, opacity: 1.0 }
]);
const sortedLayers = computed(() => [...layers.value].sort((a, b) => b.order - a.order));
const activeLayer = computed(() => layers.value.find(l => l.id === activeLayerId.value) || layers.value[0]);

const cloneAnchor = ref(null), settingCloneAnchor = ref(false);
let isDragging = false, lastX = 0, lastY = 0, startX = 0, startY = 0;
const cursorX = ref(0), cursorY = ref(0), history = ref([]), historyIndex = ref(-1);

const tools = [ 
    { id: 'pan', name: 'Pan / Move', icon: IconHand }, 
    { id: 'brush', name: 'Brush', icon: IconPencil }, 
    { id: 'eraser', name: 'Eraser', icon: IconEraser }, 
    { id: 'wand', name: 'Magic Wand (Transparency)', icon: IconWand },
    { id: 'clone', name: 'Clone Stamp', icon: IconArrowPath },
    { id: 'text', name: 'Text Tool', icon: IconType }, 
    { id: 'line', name: 'Line', icon: IconLine }, 
    { id: 'rect', name: 'Rect', icon: IconRect }, 
    { id: 'circle', name: 'Circle', icon: IconCircle } 
];

const compatibleModels = computed(() => dataStore.availableTtiModels);
const showCursor = computed(() => ['brush', 'eraser', 'circle', 'text', 'clone', 'wand'].includes(tool.value));
const combinedCanvasStyle = computed(() => ({ transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})` }));
const activeTask = computed(() => tasksStore.tasks.find(t => t.id === activeTaskId.value));

onMounted(async () => {
    isComponentMounted.value = true;
    nextTick(() => hasHeaderTarget.value = !!document.getElementById('global-header-title-target'));
    
    on('task:completed', onTaskCompleted);
    
    // REMOVED uiStore.setPageTitle to prevent the overlap issue.
    // The teleport will now be the only thing in the title area.
    
    if (maskCanvasRef.value) ctxMask.value = maskCanvasRef.value.getContext('2d');
    if (previewCanvasRef.value) ctxPreview.value = previewCanvasRef.value.getContext('2d');
    
    if (props.id) await loadImage(props.id);
    if (authStore.user) selectedModel.value = authStore.user.iti_binding_model_name || authStore.user.tti_binding_model_name || '';
    
    window.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => { isComponentMounted.value = false; off('task:completed', onTaskCompleted); window.removeEventListener('keydown', handleKeydown); });

async function loadImage(id) {
    isLoadingImage.value = true;
    try {
        const res = await apiClient.get(`/api/image-studio/${id}/file`, { responseType: 'blob' });
        const img = new Image();
        await new Promise((r, j) => { img.onload = r; img.onerror = j; img.src = URL.createObjectURL(res.data); });
        imageCanvasRef.value.width = img.naturalWidth; imageCanvasRef.value.height = img.naturalHeight;
        const base = layers.value.find(l => l.id === 'base');
        base.ctx = imageCanvasRef.value.getContext('2d'); base.ctx.drawImage(img, 0, 0);
        [maskCanvasRef, previewCanvasRef].forEach(c => { c.value.width = img.naturalWidth; c.value.height = img.naturalHeight; });
        saveState(); fitToScreen();
    } catch (e) { router.push('/image-studio'); }
    finally { isLoadingImage.value = false; }
}

function addNewLayer(name = null) {
    const id = `layer_${Date.now()}`;
    layers.value.push({ id, name: name || `Layer ${layers.value.length}`, visible: true, order: layers.value.length, el: null, ctx: null, opacity: 1.0 });
    activeLayerId.value = id;
    nextTick(() => {
        const l = layers.value.find(x => x.id === id);
        l.el.width = imageCanvasRef.value.width; l.el.height = imageCanvasRef.value.height;
        l.ctx = l.el.getContext('2d');
    });
}

function deleteLayer(id) { if (id === 'base') return; layers.value = layers.value.filter(l => l.id !== id); if (activeLayerId.value === id) activeLayerId.value = 'base'; }

function getPointerPos(e) {
    const r = imageCanvasRef.value.getBoundingClientRect();
    const sX = imageCanvasRef.value.width / r.width, sY = imageCanvasRef.value.height / r.height;
    return { x: (e.clientX - r.left) * sX, y: (e.clientY - r.top) * sY };
}

function startAction(e) {
    if (e.button !== 0) return;
    const { x, y } = getPointerPos(e);
    if (tool.value === 'clone' && settingCloneAnchor.value) { cloneAnchor.value = { x, y }; settingCloneAnchor.value = false; return; }
    if (tool.value === 'wand') { magicWandTransparency(x, y); return; }
    isDragging = true; lastX = e.clientX; lastY = e.clientY; startX = x; startY = y;
    if (tool.value === 'text') {
        const t = prompt("Text:");
        if (t) { const c = getActiveContext(); c.fillStyle = color.value; c.font = `bold ${brushSize.value}px sans-serif`; c.fillText(t, x, y); saveState(); }
        isDragging = false;
    } else if (['brush', 'eraser', 'clone'].includes(tool.value)) {
        const c = getActiveContext(); c.beginPath(); c.moveTo(x, y);
    }
}

function handleMove(e) {
    const { x, y } = getPointerPos(e); cursorX.value = x; cursorY.value = y;
    if (!isDragging) return;
    if (tool.value === 'pan' && activeLayerId.value !== 'base' && activeLayerId.value !== 'mask') {
        const c = getActiveContext(); const t = document.createElement('canvas');
        t.width = c.canvas.width; t.height = c.canvas.height; t.getContext('2d').drawImage(c.canvas, 0, 0);
        c.clearRect(0,0,t.width,t.height); c.drawImage(t, (x - startX), (y - startY));
    } else if (tool.value === 'pan') { panX.value += e.clientX - lastX; panY.value += e.clientY - lastY; lastX = e.clientX; lastY = e.clientY; }
    else if (['brush', 'eraser'].includes(tool.value)) draw(x, y);
    else if (tool.value === 'clone') drawClone(x, y);
    else if (['line', 'rect', 'circle'].includes(tool.value)) drawPreviewShape(x, y);
}

function endAction() { if (!isDragging) return; isDragging = false; if (['line', 'rect', 'circle'].includes(tool.value)) commitShape(getPointerPos({ clientX: lastX, clientY: lastY })); saveState(); }

function getActiveContext() { if (activeLayerId.value === 'mask') return ctxMask.value; return activeLayer.value.ctx; }

function draw(x, y) {
    const c = getActiveContext(); c.lineCap = 'round'; c.lineJoin = 'round'; c.lineWidth = brushSize.value;
    c.globalCompositeOperation = tool.value === 'eraser' ? 'destination-out' : 'source-over';
    c.strokeStyle = activeLayerId.value === 'mask' ? '#FFF' : color.value;
    c.lineTo(x, y); c.stroke(); c.beginPath(); c.moveTo(x, y);
}

function drawClone(x, y) {
    if (!cloneAnchor.value) return;
    const c = getActiveContext(); c.save(); c.beginPath(); c.arc(x, y, brushSize.value/2, 0, Math.PI*2); c.clip();
    c.drawImage(imageCanvasRef.value, cloneAnchor.value.x+(x-startX)-brushSize.value/2, cloneAnchor.value.y+(y-startY)-brushSize.value/2, brushSize.value, brushSize.value, x-brushSize.value/2, y-brushSize.value/2, brushSize.value, brushSize.value);
    c.restore();
}

function drawPreviewShape(x, y) {
    const c = ctxPreview.value; c.clearRect(0,0,c.canvas.width,c.canvas.height);
    c.strokeStyle = color.value; c.lineWidth = 2; c.beginPath();
    if (tool.value === 'line') { c.moveTo(startX, startY); c.lineTo(x, y); }
    else if (tool.value === 'rect') c.rect(startX, startY, x-startX, y-startY);
    else if (tool.value === 'circle') c.arc(startX, startY, Math.sqrt(Math.pow(x-startX,2)+Math.pow(y-startY,2)), 0, Math.PI*2);
    c.stroke();
}

function commitShape(pos) {
    ctxPreview.value.clearRect(0,0,previewCanvasRef.value.width,previewCanvasRef.value.height);
    const c = getActiveContext(); c.strokeStyle = color.value; c.fillStyle = color.value; c.lineWidth = brushSize.value; c.beginPath();
    if (tool.value === 'line') { c.moveTo(startX, startY); c.lineTo(pos.x, pos.y); c.stroke(); }
    else if (tool.value === 'rect') { c.rect(startX, startY, pos.x-startX, pos.y-startY); c.fill(); }
    else if (tool.value === 'circle') { c.arc(startX, startY, Math.sqrt(Math.pow(pos.x-startX,2)+Math.pow(pos.y-startY,2)), 0, Math.PI*2); c.fill(); }
}

function magicWandTransparency(startX, startY) {
    const c = getActiveContext(); const w = c.canvas.width, h = c.canvas.height;
    const imgData = c.getImageData(0,0,w,h); const data = imgData.data;
    const pos = (Math.floor(startY) * w + Math.floor(startX)) * 4;
    const tr = data[pos], tg = data[pos+1], tb = data[pos+2], tol = brushSize.value * 2.55;
    
    for (let i = 0; i < data.length; i += 4) {
        if (Math.abs(data[i]-tr) < tol && Math.abs(data[i+1]-tg) < tol && Math.abs(data[i+2]-tb) < tol) data[i+3] = 0;
    }
    c.putImageData(imgData, 0, 0); saveState();
}

async function generateNewLayerElement() {
    isProcessingTask.value = true;
    const fullPrompt = aiRemoveBg.value ? `${prompt.value} on a solid bright magenta background, isolated element` : prompt.value;
    try {
        const tsk = await imageStore.generateImage({
            prompt: fullPrompt, model: selectedModel.value, 
            width: imageCanvasRef.value.width, height: imageCanvasRef.value.height, n: 1
        });
        if (tsk?.id) {
            activeTaskId.value = tsk.id;
            const unwatch = watch(() => tasksStore.tasks.find(t => t.id === tsk.id), (t) => {
                if (t?.status === 'completed' && t.result) {
                    const res = Array.isArray(t.result) ? t.result[0] : t.result;
                    loadGeneratedAssetToLayer(res.id);
                    unwatch();
                }
            }, { deep: true });
        }
    } catch (e) { isProcessingTask.value = false; }
}

async function loadGeneratedAssetToLayer(id) {
    const res = await apiClient.get(`/api/image-studio/${id}/file`, { responseType: 'blob' });
    const img = new Image();
    img.onload = () => {
        addNewLayer("AI Element");
        nextTick(() => {
            const l = activeLayer.value;
            l.ctx.drawImage(img, 0, 0);
            if (aiRemoveBg.value) magicWandTransparency(0, 0); // Attempt keying out top-left pixel color (magenta)
            saveState(); isProcessingTask.value = false;
        });
    };
    img.src = URL.createObjectURL(res.data);
}

async function generateFlattenedEdit() {
    isProcessingTask.value = true;
    const comp = document.createElement('canvas'); comp.width = imageCanvasRef.value.width; comp.height = imageCanvasRef.value.height;
    const cc = comp.getContext('2d');
    layers.value.filter(l => l.visible).forEach(l => { cc.globalAlpha = l.opacity; if(l.el) cc.drawImage(l.el, 0, 0); });
    const b64 = comp.toDataURL('image/png').split(',')[1];
    const m64 = maskCanvasRef.value.toDataURL('image/png').split(',')[1];
    const tsk = await imageStore.editImage({ base_image_b64: b64, mask: m64, prompt: prompt.value, model: selectedModel.value, width: comp.width, height: comp.height });
    if (tsk?.id) activeTaskId.value = tsk.id;
}

function saveProject() {
    const projectData = {
        meta: { prompt: prompt.value, width: imageCanvasRef.value.width, height: imageCanvasRef.value.height },
        layers: layers.value.map(l => ({ id: l.id, name: l.name, opacity: l.opacity, visible: l.visible, data: l.el?.toDataURL() }))
    };
    const blob = new Blob([JSON.stringify(projectData)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `lollms_project_${Date.now()}.json`; a.click();
}

function saveCanvas() {
    const comp = document.createElement('canvas'); comp.width = imageCanvasRef.value.width; comp.height = imageCanvasRef.value.height;
    const cc = comp.getContext('2d');
    layers.value.filter(l => l.visible).forEach(l => { cc.globalAlpha = l.opacity; cc.drawImage(l.el, 0, 0); });
    imageStore.saveCanvasAsNewImage({ base_image_b64: comp.toDataURL('image/png').split(',')[1], prompt: prompt.value || "Composition", width: comp.width, height: comp.height, model: selectedModel.value });
}

function saveState() {
    const s = layers.value.map(l => ({ id: l.id, data: l.el?.toDataURL(), v: l.visible, o: l.opacity }));
    if (historyIndex.value < history.value.length - 1) history.value = history.value.slice(0, historyIndex.value+1);
    history.value.push(s); historyIndex.value++;
    if (history.value.length > 20) { history.value.shift(); historyIndex.value--; }
}

function undo() { if (historyIndex.value > 0) { historyIndex.value--; applyHistory(history.value[historyIndex.value]); } }
function redo() { if (historyIndex.value < history.value.length - 1) { historyIndex.value++; applyHistory(history.value[historyIndex.value]); } }
function applyHistory(state) {
    state.forEach(s => {
        const l = layers.value.find(x => x.id === s.id);
        if (l && l.ctx) { const i = new Image(); i.onload = () => { l.ctx.clearRect(0,0,l.el.width,l.el.height); l.ctx.drawImage(i, 0, 0); }; i.src = s.data; l.visible = s.v; l.opacity = s.o; }
    });
}

function fitToScreen() {
    if (!containerRef.value || !imageCanvasRef.value) return;
    const cw = containerRef.value.clientWidth, ch = containerRef.value.clientHeight;
    const iw = imageCanvasRef.value.width, ih = imageCanvasRef.value.height;
    zoom.value = Math.min((cw - 40) / iw, (ch - 40) / ih, 1);
}

function zoomIn() { zoom.value = Math.min(10, zoom.value + 0.1); }
function zoomOut() { zoom.value = Math.max(0.05, zoom.value - 0.1); }
function handleWheel(e) { if (e.ctrlKey || tool.value === 'pan') { e.preventDefault(); zoom.value = Math.min(Math.max(0.05, zoom.value - Math.sign(e.deltaY)*0.1), 10); } }

function onTaskCompleted(t) { if (t.id === activeTaskId.value) { isProcessingTask.value = false; } }

function handleKeydown(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); undo(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 'y') { e.preventDefault(); redo(); }
}
</script>

<style scoped>
.pattern-grid { background-image: linear-gradient(45deg, #e5e7eb 25%, transparent 25%), linear-gradient(-45deg, #e5e7eb 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #e5e7eb 75%), linear-gradient(-45deg, transparent 75%, #e5e7eb 75%); background-size: 20px 20px; background-position: 0 0, 0 10px, 10px -10px, -10px 0px; }
.dark .pattern-grid { background-image: linear-gradient(45deg, #1f2937 25%, transparent 25%), linear-gradient(-45deg, #1f2937 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #1f2937 75%), linear-gradient(-45deg, transparent 75%, #1f2937 75%); }
.layer-canvas { image-rendering: pixelated; }
.layer-item { @apply flex items-center gap-3 p-2.5 rounded-xl cursor-pointer border-2 border-transparent transition-all hover:bg-gray-100 dark:hover:bg-gray-800; }
.layer-item.active { @apply border-blue-500 bg-blue-50 dark:bg-blue-900/30; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
