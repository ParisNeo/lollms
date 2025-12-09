<template>
    <div class="h-full flex flex-col bg-gray-100 dark:bg-gray-900 overflow-hidden relative select-none">
        <!-- Top Toolbar -->
        <div class="h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-4 z-20 shadow-sm gap-4">
            <div class="flex items-center gap-2">
                <button @click="goBack" class="btn-icon" title="Back to Gallery">
                    <IconArrowLeft class="w-5 h-5" />
                </button>
                <div class="h-6 w-px bg-gray-300 dark:bg-gray-600 mx-2"></div>
                
                <!-- Tool Selector -->
                <div class="flex items-center bg-gray-100 dark:bg-gray-700 rounded-lg p-1 gap-1">
                    <button v-for="t in tools" :key="t.id" 
                        @click="setTool(t.id)" 
                        class="p-2 rounded-md transition-colors relative group"
                        :class="tool === t.id ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
                        :title="t.name"
                    >
                        <component :is="t.icon" class="w-5 h-5" />
                    </button>
                </div>
            </div>

            <!-- Tool Options -->
            <div class="flex items-center gap-4 flex-grow justify-center">
                <!-- Color Picker -->
                <div class="flex items-center gap-2" title="Primary Color">
                    <input type="color" v-model="color" class="w-8 h-8 rounded cursor-pointer border-0 p-0 bg-transparent">
                </div>

                <!-- Size Slider -->
                <div class="flex items-center gap-2" v-if="['brush', 'eraser', 'line', 'rect', 'circle'].includes(tool)">
                    <span class="text-xs font-medium uppercase text-gray-500">Size</span>
                    <input type="range" v-model.number="brushSize" min="1" max="200" class="w-24 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-600">
                    <span class="text-xs w-6 font-mono">{{ brushSize }}</span>
                </div>

                <!-- Opacity Slider -->
                <div class="flex items-center gap-2" v-if="tool !== 'eraser' && tool !== 'wand' && tool !== 'pan' && tool !== 'pipette'">
                    <span class="text-xs font-medium uppercase text-gray-500">Opacity</span>
                    <input type="range" v-model.number="opacity" min="0" max="1" step="0.05" class="w-24 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-600">
                    <span class="text-xs w-8 font-mono">{{ Math.round(opacity * 100) }}%</span>
                </div>

                <!-- Tolerance Slider (Fill/Wand) -->
                <div class="flex items-center gap-2" v-if="['fill', 'wand'].includes(tool)">
                    <span class="text-xs font-medium uppercase text-gray-500">Tolerance</span>
                    <input type="range" v-model.number="tolerance" min="0" max="100" class="w-24 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-600">
                    <span class="text-xs w-6 font-mono">{{ tolerance }}</span>
                </div>

                <div class="h-6 w-px bg-gray-300 dark:bg-gray-600 mx-2"></div>

                <!-- Layer Selector -->
                <div class="flex items-center bg-gray-100 dark:bg-gray-700 rounded-lg p-1 gap-1">
                    <button @click="activeLayer = 'image'" class="px-3 py-1.5 text-xs font-medium rounded transition-colors" :class="activeLayer === 'image' ? 'bg-white dark:bg-gray-600 shadow-sm' : 'text-gray-500'">Image</button>
                    <button @click="activeLayer = 'mask'" class="px-3 py-1.5 text-xs font-medium rounded transition-colors" :class="activeLayer === 'mask' ? 'bg-white dark:bg-gray-600 shadow-sm' : 'text-gray-500'">Mask</button>
                </div>
            </div>

            <!-- Actions -->
            <div class="flex items-center gap-2">
                <button @click="undo" :disabled="historyIndex <= 0" class="btn-icon" title="Undo (Ctrl+Z)"><IconUndo class="w-5 h-5" /></button>
                <button @click="redo" :disabled="historyIndex >= history.length - 1" class="btn-icon" title="Redo (Ctrl+Y)"><IconRedo class="w-5 h-5" /></button>
                <button @click="clearActiveLayer" class="btn-icon text-red-500 hover:text-red-600" :title="`Clear ${activeLayer === 'mask' ? 'Mask' : 'Image'}`"><IconTrash class="w-5 h-5" /></button>
                <button @click="saveCanvas" class="btn btn-secondary btn-sm gap-2"><IconSave class="w-4 h-4" /> Save</button>
            </div>
        </div>

        <div class="flex-grow flex min-h-0 relative">
            <!-- Canvas Area -->
            <div 
                ref="containerRef"
                class="flex-grow bg-gray-200 dark:bg-gray-900 relative overflow-hidden flex items-center justify-center cursor-crosshair pattern-grid"
                @wheel="handleWheel"
                @mousedown="startAction"
                @mousemove="handleMove"
                @mouseup="endAction"
                @mouseleave="endAction"
            >
                <div :style="{ transform: `translate(${panX}px, ${panY}px) scale(${zoom})` }" class="relative shadow-2xl origin-center transition-transform duration-75 canvas-stack">
                    <canvas ref="imageCanvasRef" class="block bg-white layer-canvas"></canvas>
                    <canvas ref="maskCanvasRef" class="absolute inset-0 opacity-60 layer-canvas" :class="{'pointer-events-none': activeLayer !== 'mask'}"></canvas>
                    <canvas ref="previewCanvasRef" class="absolute inset-0 pointer-events-none layer-canvas"></canvas> <!-- For shapes preview -->
                    
                    <!-- Brush Cursor -->
                    <div v-show="showCursor" class="absolute pointer-events-none rounded-full border border-black/50 bg-white/20 z-50 transform -translate-x-1/2 -translate-y-1/2"
                        :style="{ width: `${brushSize}px`, height: `${brushSize}px`, left: `${cursorX}px`, top: `${cursorY}px` }"></div>
                </div>

                <!-- Zoom Controls -->
                <div class="absolute bottom-4 left-4 bg-white/90 dark:bg-gray-800/90 backdrop-blur rounded-lg shadow p-2 flex items-center gap-2 z-10 border border-gray-200 dark:border-gray-700">
                    <button @click="zoomOut" class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><IconMinus class="w-4 h-4" /></button>
                    <span class="text-xs font-mono w-12 text-center">{{ Math.round(zoom * 100) }}%</span>
                    <button @click="zoomIn" class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><IconPlus class="w-4 h-4" /></button>
                    <button @click="fitToScreen" class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded ml-1" title="Fit"><IconMaximize class="w-4 h-4" /></button>
                </div>
            </div>

            <!-- Settings Sidebar -->
            <div class="w-80 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 flex flex-col z-20 shadow-xl">
                <div class="p-4 border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 flex justify-between items-center">
                    <h3 class="font-semibold text-sm">Generation Settings</h3>
                    <div v-if="isGenerating" class="flex items-center text-xs text-blue-500 animate-pulse">
                        <IconAnimateSpin class="w-3 h-3 mr-1" /> Busy...
                    </div>
                </div>
                
                <div class="flex-grow overflow-y-auto p-4 space-y-5 custom-scrollbar">
                    <div class="space-y-3">
                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label class="text-xs font-bold text-gray-500 uppercase">Prompt</label>
                                <button @click="enhancePrompt('prompt')" class="text-blue-500 hover:text-blue-600 p-1" title="Enhance Prompt" :disabled="isEnhancing">
                                    <IconSparkles class="w-4 h-4" :class="{'animate-pulse': isEnhancing}" />
                                </button>
                            </div>
                            <textarea v-model="prompt" rows="4" class="input-field w-full text-sm resize-none" placeholder="Describe the result..."></textarea>
                        </div>
                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label class="text-xs font-bold text-gray-500 uppercase">Negative Prompt</label>
                                <button @click="enhancePrompt('negative_prompt')" class="text-red-500 hover:text-red-600 p-1" title="Enhance Negative" :disabled="isEnhancing">
                                    <IconSparkles class="w-4 h-4" :class="{'animate-pulse': isEnhancing}" />
                                </button>
                            </div>
                            <textarea v-model="negativePrompt" rows="3" class="input-field w-full text-sm resize-none" placeholder="What to avoid..."></textarea>
                        </div>
                    </div>

                    <div class="space-y-4 pt-4 border-t dark:border-gray-700">
                        <div>
                            <label class="label flex justify-between">
                                <span>Denoising Strength</span>
                                <span class="text-gray-500">{{ strength }}</span>
                            </label>
                            <input type="range" v-model.number="strength" min="0.05" max="1.0" step="0.05" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700">
                        </div>
                        <div>
                            <label class="label flex justify-between">
                                <span>Guidance Scale</span>
                                <span class="text-gray-500">{{ cfgScale }}</span>
                            </label>
                            <input type="range" v-model.number="cfgScale" min="1" max="20" step="0.5" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700">
                        </div>
                        <div>
                            <label class="label">Model</label>
                            <select v-model="selectedModel" class="input-field w-full text-sm mt-1">
                                <option disabled value="">Select Model</option>
                                <option v-for="m in compatibleModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                            </select>
                        </div>
                        <div>
                            <label class="label">Seed</label>
                            <div class="flex gap-2">
                                <input v-model.number="seed" type="number" class="input-field flex-grow text-sm" placeholder="-1">
                                <button @click="seed = -1" class="btn btn-secondary px-2"><IconRefresh class="w-4 h-4" /></button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="p-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                    <button @click="generateEdit" class="btn btn-primary w-full py-3" :disabled="isGenerating">
                        <template v-if="isGenerating"><IconAnimateSpin class="w-5 h-5 mr-2 animate-spin" /> Processing...</template>
                        <template v-else><IconSparkles class="w-5 h-5 mr-2" /> {{ activeLayer === 'mask' ? 'Inpaint Masked' : 'Generate from Img' }}</template>
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, shallowRef } from 'vue';
import { useRouter } from 'vue-router';
import { useImageStore } from '../stores/images';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import apiClient from '../services/api';
import useEventBus from '../services/eventBus';

// Icons
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';
import IconHand from '../assets/icons/IconHand.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
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
import IconStopCircle from '../assets/icons/IconStopCircle.vue'; // For Circle
import IconRectangle from '../assets/icons/IconRectangle.vue'; // Need to ensure exists or use generic
import IconMinusCircle from '../assets/icons/IconMinusCircle.vue'; // For Line? Or use SVG

// Inline SVG Components for tools without existing icons
const IconLine = { template: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 19L19 5"/></svg>' };
const IconCircle = { template: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/></svg>' };
const IconRect = { template: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>' };
const IconFill = { template: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 11L12 17L5 11"/><path d="M12 17V3"/></svg>' }; // Placeholder bucket
const IconWand = { template: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 4V2"/><path d="M15 16V14"/><path d="M8 9h2"/><path d="M20 9h2"/><path d="M17.8 11.8L19 13"/><path d="M10.6 5.2L12 6.6"/><path d="M11.6 12.2l-8.4 8.6"/></svg>' }; // Placeholder wand
const IconPipette = { template: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 4l6 6-11 11-6 1L4 16 15 5z"/><path d="M14 4l-4 4"/></svg>' };
const IconEraser = { template: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 20H7L3 16C2 15 2 13 3 12L13 2L22 11L20 20Z"/><path d="M11 11L20 20"/></svg>' };

const props = defineProps({ id: { type: String, default: null } });
const router = useRouter();
const imageStore = useImageStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const { on, off } = useEventBus();

// Canvas Refs
const containerRef = ref(null);
const imageCanvasRef = ref(null);
const maskCanvasRef = ref(null);
const previewCanvasRef = ref(null);
const ctxImage = ref(null);
const ctxMask = ref(null);
const ctxPreview = ref(null);

// State
const activeLayer = ref('image'); // 'image' or 'mask'
const tool = ref('brush');
const color = ref('#000000');
const brushSize = ref(40);
const opacity = ref(1.0);
const tolerance = ref(10);
const zoom = ref(1);
const panX = ref(0);
const panY = ref(0);
const prompt = ref('');
const negativePrompt = ref('');
const strength = ref(0.75);
const cfgScale = ref(7.5);
const seed = ref(-1);
const selectedModel = ref('');
const isGenerating = ref(false);
const isEnhancing = ref(false);

const isDragging = ref(false);
const lastX = ref(0);
const lastY = ref(0);
const cursorX = ref(0);
const cursorY = ref(0);
const startX = ref(0); // For shapes
const startY = ref(0); // For shapes

// History
const history = ref([]);
const historyIndex = ref(-1);

const tools = [
    { id: 'pan', name: 'Pan (Space)', icon: IconHand },
    { id: 'brush', name: 'Brush (B)', icon: IconPencil },
    { id: 'eraser', name: 'Eraser (E)', icon: IconEraser },
    { id: 'fill', name: 'Fill (F)', icon: IconFill },
    { id: 'wand', name: 'Magic Wand (W)', icon: IconWand },
    { id: 'line', name: 'Line (L)', icon: IconLine },
    { id: 'rect', name: 'Rectangle (R)', icon: IconRect },
    { id: 'circle', name: 'Circle (C)', icon: IconCircle },
    { id: 'pipette', name: 'Pipette (I)', icon: IconPipette },
];

const compatibleModels = computed(() => dataStore.availableTtiModels);
const showCursor = computed(() => ['brush', 'eraser', 'circle'].includes(tool.value) && tool.value !== 'pan');

function setTool(t) { tool.value = t; }

// --- Event Listeners for Prompt Enhancement ---
function onPromptEnhanced(data) {
    if (data.prompt) prompt.value = data.prompt;
    if (data.negative_prompt) negativePrompt.value = data.negative_prompt;
    isEnhancing.value = false;
}

onMounted(async () => {
    on('prompt:enhanced', onPromptEnhanced);
    
    if (imageCanvasRef.value) ctxImage.value = imageCanvasRef.value.getContext('2d', { willReadFrequently: true });
    if (maskCanvasRef.value) ctxMask.value = maskCanvasRef.value.getContext('2d', { willReadFrequently: true });
    if (previewCanvasRef.value) ctxPreview.value = previewCanvasRef.value.getContext('2d');

    if (props.id === 'new') initializeBlankCanvas();
    else if (props.id) await loadImage(props.id);

    if (authStore.user) {
        selectedModel.value = authStore.user.iti_binding_model_name || authStore.user.tti_binding_model_name || '';
    }
    
    window.addEventListener('keydown', handleKeydown);
    window.addEventListener('resize', fitToScreen);
});

onUnmounted(() => {
    off('prompt:enhanced', onPromptEnhanced);
    window.removeEventListener('keydown', handleKeydown);
    window.removeEventListener('resize', fitToScreen);
});

function initializeBlankCanvas(width = 1024, height = 1024) {
    resizeCanvases(width, height);
    ctxImage.value.fillStyle = '#FFFFFF';
    ctxImage.value.fillRect(0, 0, width, height);
    saveState();
    fitToScreen();
}

async function loadImage(imageId) {
    try {
        const response = await apiClient.get(`/api/image-studio/${imageId}/file`, { responseType: 'blob' });
        const url = URL.createObjectURL(response.data);
        const img = new Image();
        await new Promise((resolve, reject) => {
            img.onload = resolve;
            img.onerror = reject;
            img.src = url;
        });
        
        resizeCanvases(img.naturalWidth, img.naturalHeight);
        ctxImage.value.drawImage(img, 0, 0);
        
        const details = imageStore.images.find(i => i.id === imageId);
        if (details) {
            prompt.value = details.prompt || '';
            negativePrompt.value = details.negative_prompt || '';
        }
        
        URL.revokeObjectURL(url);
        saveState();
        fitToScreen();
    } catch (e) {
        console.error("Load failed", e);
        uiStore.addNotification("Failed to load image.", "error");
        router.push('/image-studio');
    }
}

function resizeCanvases(w, h) {
    [imageCanvasRef, maskCanvasRef, previewCanvasRef].forEach(ref => {
        if (ref.value) { ref.value.width = w; ref.value.height = h; }
    });
}

function getPointerPos(e) {
    if (!imageCanvasRef.value) return { x: 0, y: 0 };
    const rect = imageCanvasRef.value.getBoundingClientRect();
    const scaleX = imageCanvasRef.value.width / rect.width;
    const scaleY = imageCanvasRef.value.height / rect.height;
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
}

function startAction(e) {
    if (e.button !== 0) return; // Left click only
    isDragging.value = true;
    const { x, y } = getPointerPos(e);
    lastX.value = e.clientX; 
    lastY.value = e.clientY;
    startX.value = x; 
    startY.value = y;

    if (tool.value === 'pipette') {
        pickColor(x, y);
        isDragging.value = false;
        return;
    }
    if (tool.value === 'fill') {
        floodFill(Math.floor(x), Math.floor(y));
        saveState();
        isDragging.value = false;
        return;
    }
    if (tool.value === 'wand') {
        magicWand(Math.floor(x), Math.floor(y));
        saveState();
        isDragging.value = false;
        return;
    }
    
    // For drawing tools, start the path
    if (['brush', 'eraser'].includes(tool.value)) {
        const ctx = activeLayer.value === 'image' ? ctxImage.value : ctxMask.value;
        ctx.beginPath();
        ctx.moveTo(x, y);
        draw(x, y);
    }
}

function handleMove(e) {
    const { x, y } = getPointerPos(e);
    cursorX.value = x; cursorY.value = y;

    if (!isDragging.value) return;

    if (tool.value === 'pan') {
        panX.value += e.clientX - lastX.value;
        panY.value += e.clientY - lastY.value;
        lastX.value = e.clientX; lastY.value = e.clientY;
        return;
    }

    if (['brush', 'eraser'].includes(tool.value)) {
        draw(x, y);
    } else if (['line', 'rect', 'circle'].includes(tool.value)) {
        drawPreviewShape(x, y);
    }
}

function endAction(e) {
    if (!isDragging.value) return;
    isDragging.value = false;
    
    if (['line', 'rect', 'circle'].includes(tool.value)) {
        const { x, y } = getPointerPos(e);
        commitShape(x, y);
    }
    
    if (tool.value !== 'pan' && tool.value !== 'pipette') {
        saveState();
    }
}

function getActiveCtx() {
    return activeLayer.value === 'image' ? ctxImage.value : ctxMask.value;
}

function configureCtx(ctx) {
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.lineWidth = brushSize.value;
    
    if (tool.value === 'eraser') {
        ctx.globalCompositeOperation = 'destination-out';
    } else {
        ctx.globalCompositeOperation = 'source-over';
        ctx.globalAlpha = opacity.value;
        // For mask layer, we usually want white to indicate "masked/edit here" for visualization in editor?
        // Actually, backend usually expects white pixels = edit. 
        // If editing mask, user sees white. 
        ctx.fillStyle = activeLayer.value === 'mask' ? `rgba(255,255,255,${opacity.value})` : color.value;
        ctx.strokeStyle = activeLayer.value === 'mask' ? `rgba(255,255,255,${opacity.value})` : color.value;
    }
}

function draw(x, y) {
    const ctx = getActiveCtx();
    configureCtx(ctx);
    ctx.lineTo(x, y);
    ctx.stroke();
    // For smooth continuous drawing, we don't clear path until mouseup logic (simplified here)
    // Actually standard canvas painting usually requires beginPath per stroke or managing points.
    // Simple implementation:
    ctx.beginPath();
    ctx.moveTo(x, y);
}

function drawPreviewShape(x, y) {
    const ctx = ctxPreview.value;
    const w = previewCanvasRef.value.width;
    const h = previewCanvasRef.value.height;
    ctx.clearRect(0, 0, w, h);
    
    configureCtx(ctx);
    ctx.beginPath();
    
    if (tool.value === 'line') {
        ctx.moveTo(startX.value, startY.value);
        ctx.lineTo(x, y);
    } else if (tool.value === 'rect') {
        ctx.rect(startX.value, startY.value, x - startX.value, y - startY.value);
    } else if (tool.value === 'circle') {
        const radius = Math.sqrt(Math.pow(x - startX.value, 2) + Math.pow(y - startY.value, 2));
        ctx.arc(startX.value, startY.value, radius, 0, 2 * Math.PI);
    }
    
    // Preview uses stroke for line/circle outline, fill for rect/circle body?
    // Let's stick to stroke + fill based on standard paint tools behavior logic
    ctx.stroke();
    if (tool.value !== 'line') ctx.fill();
}

function commitShape(x, y) {
    // Clear preview
    ctxPreview.value.clearRect(0, 0, previewCanvasRef.value.width, previewCanvasRef.value.height);
    
    // Draw to active layer
    const ctx = getActiveCtx();
    configureCtx(ctx);
    ctx.beginPath();
    
    if (tool.value === 'line') {
        ctx.moveTo(startX.value, startY.value);
        ctx.lineTo(x, y);
        ctx.stroke();
    } else if (tool.value === 'rect') {
        ctx.rect(startX.value, startY.value, x - startX.value, y - startY.value);
        ctx.fill();
        ctx.stroke();
    } else if (tool.value === 'circle') {
        const radius = Math.sqrt(Math.pow(x - startX.value, 2) + Math.pow(y - startY.value, 2));
        ctx.arc(startX.value, startY.value, radius, 0, 2 * Math.PI);
        ctx.fill();
        ctx.stroke();
    }
    ctx.globalAlpha = 1.0; // Reset
    ctx.globalCompositeOperation = 'source-over';
}

function pickColor(x, y) {
    // Pick from image canvas always? Or active? Usually image.
    const p = ctxImage.value.getImageData(x, y, 1, 1).data;
    const hex = "#" + ("000000" + ((p[0] << 16) | (p[1] << 8) | p[2]).toString(16)).slice(-6);
    color.value = hex;
}

// --- Flood Fill & Magic Wand ---
// Simple stack-based flood fill implementation
function floodFill(x, y) {
    const ctx = getActiveCtx();
    const w = ctx.canvas.width;
    const h = ctx.canvas.height;
    if (x < 0 || y < 0 || x >= w || y >= h) return;

    const imageData = ctx.getImageData(0, 0, w, h);
    const data = imageData.data;
    const targetIdx = (y * w + x) * 4;
    
    const targetR = data[targetIdx], targetG = data[targetIdx+1], targetB = data[targetIdx+2], targetA = data[targetIdx+3];
    
    // Parse current fill color
    let fillR, fillG, fillB;
    const hex = color.value.replace('#', '');
    fillR = parseInt(hex.substring(0, 2), 16);
    fillG = parseInt(hex.substring(2, 4), 16);
    fillB = parseInt(hex.substring(4, 6), 16);
    const fillA = Math.round(opacity.value * 255);

    // If active layer is mask, we usually fill with white (255,255,255, alpha) for editing
    if (activeLayer.value === 'mask') {
        fillR=255; fillG=255; fillB=255;
    }

    if (matches(targetR, targetG, targetB, targetA, fillR, fillG, fillB, fillA, 0)) return; // Already same color

    const stack = [[x, y]];
    const tol = tolerance.value;

    while (stack.length) {
        const [cx, cy] = stack.pop();
        const idx = (cy * w + cx) * 4;
        
        if (cx < 0 || cy < 0 || cx >= w || cy >= h) continue;
        if (!matches(data[idx], data[idx+1], data[idx+2], data[idx+3], targetR, targetG, targetB, targetA, tol)) continue;

        // Fill
        data[idx] = fillR;
        data[idx+1] = fillG;
        data[idx+2] = fillB;
        data[idx+3] = fillA;

        stack.push([cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]);
    }
    ctx.putImageData(imageData, 0, 0);
}

function magicWand(x, y) {
    // Selects from IMAGE, draws on MASK
    const srcCtx = ctxImage.value;
    const destCtx = ctxMask.value;
    const w = srcCtx.canvas.width;
    const h = srcCtx.canvas.height;
    
    const srcData = srcCtx.getImageData(0,0,w,h).data;
    const destImageData = destCtx.getImageData(0,0,w,h);
    const destData = destImageData.data;
    
    const startIdx = (y * w + x) * 4;
    const tr = srcData[startIdx], tg = srcData[startIdx+1], tb = srcData[startIdx+2], ta = srcData[startIdx+3];
    const tol = tolerance.value;
    
    const stack = [[x,y]];
    const visited = new Uint8Array(w*h); // Track visited to avoid loops
    
    while(stack.length) {
        const [cx, cy] = stack.pop();
        const i = cy * w + cx;
        if (visited[i]) continue;
        visited[i] = 1;
        
        const idx = i * 4;
        if (matches(srcData[idx], srcData[idx+1], srcData[idx+2], srcData[idx+3], tr, tg, tb, ta, tol)) {
            // Mark on mask
            destData[idx] = 255; 
            destData[idx+1] = 255;
            destData[idx+2] = 255;
            destData[idx+3] = 255; // Full opacity mask
            
            if(cx+1<w) stack.push([cx+1,cy]);
            if(cx-1>=0) stack.push([cx-1,cy]);
            if(cy+1<h) stack.push([cx,cy+1]);
            if(cy-1>=0) stack.push([cx,cy-1]);
        }
    }
    destCtx.putImageData(destImageData, 0, 0);
}

function matches(r,g,b,a, r2,g2,b2,a2, tol) {
    return Math.abs(r-r2) <= tol && Math.abs(g-g2) <= tol && Math.abs(b-b2) <= tol && Math.abs(a-a2) <= tol;
}

// --- State Mgmt ---
function saveState() {
    if (historyIndex.value < history.value.length - 1) {
        history.value = history.value.slice(0, historyIndex.value + 1);
    }
    history.value.push({ 
        image: imageCanvasRef.value.toDataURL(), 
        mask: maskCanvasRef.value.toDataURL() 
    });
    historyIndex.value++;
    if (history.value.length > 20) { history.value.shift(); historyIndex.value--; }
}

function restoreState(state) {
    const iImg = new Image(); iImg.onload = () => { ctxImage.value.clearRect(0,0,imageCanvasRef.value.width, imageCanvasRef.value.height); ctxImage.value.drawImage(iImg,0,0); }; iImg.src = state.image;
    const mImg = new Image(); mImg.onload = () => { ctxMask.value.clearRect(0,0,maskCanvasRef.value.width, maskCanvasRef.value.height); ctxMask.value.drawImage(mImg,0,0); }; mImg.src = state.mask;
}

function undo() { if(historyIndex.value > 0) { historyIndex.value--; restoreState(history.value[historyIndex.value]); } }
function redo() { if(historyIndex.value < history.value.length-1) { historyIndex.value++; restoreState(history.value[historyIndex.value]); } }

function clearActiveLayer() {
    const ctx = getActiveCtx();
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    saveState();
}

// --- API Actions ---
async function generateEdit() {
    isGenerating.value = true;
    try {
        const base64Image = imageCanvasRef.value.toDataURL('image/png').split(',')[1];
        
        // Prepare Mask: Black bg, White mask
        const temp = document.createElement('canvas');
        temp.width = maskCanvasRef.value.width; temp.height = maskCanvasRef.value.height;
        const tCtx = temp.getContext('2d');
        tCtx.fillStyle = '#000000'; tCtx.fillRect(0,0,temp.width,temp.height);
        tCtx.drawImage(maskCanvasRef.value, 0, 0);
        const base64Mask = temp.toDataURL('image/png').split(',')[1];

        await imageStore.editImage({
            base_image_b64: base64Image,
            mask: base64Mask,
            prompt: prompt.value,
            negative_prompt: negativePrompt.value,
            strength: strength.value,
            cfg_scale: cfgScale.value,
            seed: seed.value,
            model: selectedModel.value,
            width: imageCanvasRef.value.width,
            height: imageCanvasRef.value.height
        });
    } catch (e) {
        uiStore.addNotification("Generation failed", "error");
    } finally {
        isGenerating.value = false;
    }
}

async function enhancePrompt(target) {
    isEnhancing.value = true;
    await imageStore.enhanceImagePrompt({ 
        prompt: prompt.value, 
        negative_prompt: negativePrompt.value,
        target, 
        model: authStore.user?.lollms_model_name 
    });
}

function goBack() { router.push('/image-studio'); }
function saveCanvas() {
    // Composite: Draw Mask onto Image for preview or just save Image?
    // User expects to save the visible result.
    // If masking was used for inpainting, the result will come from backend.
    // If user painted on Image layer, they want to save that.
    const base64Image = imageCanvasRef.value.toDataURL('image/png').split(',')[1];
    imageStore.saveCanvasAsNewImage({
        base_image_b64: base64Image,
        prompt: prompt.value || "Edited",
        width: imageCanvasRef.value.width,
        height: imageCanvasRef.value.height,
        model: selectedModel.value
    });
}

// Helpers
function fitToScreen() {
    if(!containerRef.value || !imageCanvasRef.value) return;
    const cw = containerRef.value.clientWidth, ch = containerRef.value.clientHeight;
    const iw = imageCanvasRef.value.width, ih = imageCanvasRef.value.height;
    if(iw===0) return;
    const scale = Math.min((cw-40)/iw, (ch-40)/ih, 1);
    zoom.value = scale; panX.value=0; panY.value=0;
}
function handleWheel(e) {
    if(e.ctrlKey || tool.value === 'pan') {
        e.preventDefault();
        zoom.value = Math.min(Math.max(0.1, zoom.value - Math.sign(e.deltaY)*0.1), 5);
    }
}
function zoomIn() { zoom.value = Math.min(5, zoom.value + 0.1); }
function zoomOut() { zoom.value = Math.max(0.1, zoom.value - 0.1); }
function handleKeydown(e) {
    if(e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    const map = { ' ': 'pan', 'b': 'brush', 'e': 'eraser', 'f': 'fill', 'w': 'wand', 'l': 'line', 'r': 'rect', 'c': 'circle', 'i': 'pipette' };
    if(map[e.key.toLowerCase()]) tool.value = map[e.key.toLowerCase()];
    if((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==='z') undo();
    if((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==='y') redo();
}
</script>

<style scoped>
.pattern-grid {
    background-image: linear-gradient(45deg, #e5e7eb 25%, transparent 25%), linear-gradient(-45deg, #e5e7eb 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #e5e7eb 75%), linear-gradient(-45deg, transparent 75%, #e5e7eb 75%);
    background-size: 20px 20px;
    background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
}
.dark .pattern-grid {
    background-image: linear-gradient(45deg, #1f2937 25%, transparent 25%), linear-gradient(-45deg, #1f2937 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #1f2937 75%), linear-gradient(-45deg, transparent 75%, #1f2937 75%);
}
.layer-canvas { image-rendering: pixelated; }
.custom-scrollbar::-webkit-scrollbar { width: 6px; }
.custom-scrollbar::-webkit-scrollbar-thumb { background-color: rgba(156, 163, 175, 0.5); border-radius: 20px; }
</style>
