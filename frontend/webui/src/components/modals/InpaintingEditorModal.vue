<template>
    <GenericModal modal-name="inpaintingEditor" :title="modalTitle" maxWidthClass="max-w-7xl">
        <template #body>
            <!-- New Drawing Setup -->
            <div v-if="isNewDrawingSetup" class="p-6 space-y-4">
                <h3 class="text-lg font-medium">Create New Drawing</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label for="canvas-width" class="block text-sm font-medium">Width (px)</label>
                        <input id="canvas-width" type="number" v-model.number="newCanvas.width" class="input-field mt-1">
                    </div>
                    <div>
                        <label for="canvas-height" class="block text-sm font-medium">Height (px)</label>
                        <input id="canvas-height" type="number" v-model.number="newCanvas.height" class="input-field mt-1">
                    </div>
                </div>
                <div>
                    <label for="canvas-bg" class="block text-sm font-medium">Background Color</label>
                    <input id="canvas-bg" type="color" v-model="newCanvas.bgColor" class="mt-1 w-full h-10 p-1 rounded-md">
                </div>
                <div class="flex justify-end pt-4">
                    <button @click="createBlankCanvas" class="btn btn-primary">Create Canvas</button>
                </div>
            </div>

            <!-- Main Editor -->
            <div v-else class="grid grid-cols-1 md:grid-cols-4 gap-6">
                <!-- Controls Column -->
                <div class="md:col-span-1 space-y-4">
                    <!-- Mode Selector -->
                    <div>
                        <h3 class="font-semibold mb-2">Mode</h3>
                        <div class="flex gap-2">
                            <button @click="editorMode = 'mask'" :class="['btn btn-secondary flex-1', { 'btn-primary': editorMode === 'mask' }]">Mask</button>
                            <button @click="editorMode = 'brush'" :class="['btn btn-secondary flex-1', { 'btn-primary': editorMode === 'brush' }]">Brush</button>
                        </div>
                    </div>

                    <!-- Brush Controls -->
                    <div class="p-4 bg-gray-100 dark:bg-gray-700/50 rounded-lg space-y-4">
                        <h3 class="font-semibold text-sm">Tool Settings</h3>
                        <div>
                            <label class="block text-sm font-medium">Brush Size: {{ brushSize }}</label>
                            <input type="range" min="1" max="150" v-model.number="brushSize" class="w-full">
                        </div>
                        <div class="flex gap-2">
                            <button @click="tool = 'brush'" :class="['btn btn-secondary flex-1', { 'btn-primary': tool === 'brush' }]">Draw</button>
                            <button @click="tool = 'eraser'" :class="['btn btn-secondary flex-1', { 'btn-primary': tool === 'eraser' }]">Eraser</button>
                        </div>
                    </div>
                    
                    <div v-if="editorMode === 'brush'" class="p-4 bg-gray-100 dark:bg-gray-700/50 rounded-lg space-y-4">
                        <h3 class="font-semibold text-sm">Brush Color & Opacity</h3>
                         <div>
                            <div class="flex items-center gap-2">
                                <input type="color" v-model="brushColor" class="w-10 h-10 p-1 bg-white dark:bg-gray-800 border dark:border-gray-600 rounded cursor-pointer">
                                <div class="grid grid-cols-6 gap-1 flex-1">
                                    <button v-for="color in colorPalette" :key="color" @click="brushColor = color" class="w-6 h-6 rounded-full border-2" :style="{ backgroundColor: color, borderColor: brushColor === color ? 'blue' : 'transparent' }"></button>
                                </div>
                            </div>
                        </div>
                        <div>
                            <label class="block text-sm font-medium">Opacity: {{ Math.round(brushOpacity * 100) }}%</label>
                            <input type="range" min="0.01" max="1" step="0.01" v-model.number="brushOpacity" class="w-full">
                        </div>
                    </div>
                    
                    <div class="p-4 bg-gray-100 dark:bg-gray-700/50 rounded-lg space-y-2">
                        <div class="flex gap-2">
                            <button @click="undo" class="btn btn-secondary flex-1" :disabled="!canUndo">Undo</button>
                            <button @click="redo" class="btn btn-secondary flex-1" :disabled="!canRedo">Redo</button>
                        </div>
                        <button @click="clearCanvas" class="btn btn-danger-outline w-full">Clear {{ editorMode === 'mask' ? 'Mask' : 'Drawing' }}</button>
                        <button @click="resetView" class="btn btn-secondary w-full">Reset View</button>
                    </div>

                    <div class="pt-4 border-t dark:border-gray-600">
                         <div class="flex justify-between items-center mb-1">
                            <label for="inpainting-prompt" class="block text-sm font-medium">Prompt</label>
                            <button v-if="originalImage" @click="reuseOriginalPrompt" class="btn btn-secondary btn-xs" title="Reuse original image prompt and settings">Reuse Prompt</button>
                         </div>
                        <div class="relative">
                            <textarea id="inpainting-prompt" v-model="prompt" rows="3" class="input-field w-full" placeholder="Describe the edit..."></textarea>
                            <button @click="handleEnhance('prompt')" class="absolute top-1 right-1 btn-icon" title="Enhance prompt with AI" :disabled="imageStore.isEnhancing"><IconSparkles class="w-4 h-4" /></button>
                        </div>
                    </div>
                     <div>
                        <label for="inpainting-neg-prompt" class="block text-sm font-medium mb-1">Negative Prompt</label>
                        <div class="relative">
                            <textarea id="inpainting-neg-prompt" v-model="negativePrompt" rows="2" class="input-field w-full" placeholder="ugly, blurry, bad anatomy..."></textarea>
                            <button @click="handleEnhance('negative_prompt')" class="absolute top-1 right-1 btn-icon" title="Enhance negative prompt with AI" :disabled="imageStore.isEnhancing"><IconSparkles class="w-4 h-4" /></button>
                        </div>
                    </div>
                    <!-- Generation Settings -->
                    <div class="pt-4 border-t dark:border-gray-600 space-y-4">
                        <h3 class="text-sm font-semibold">Generation Settings</h3>
                        <div>
                            <label for="seed" class="block text-sm font-medium">Seed</label>
                            <input id="seed" v-model.number="seed" type="number" class="input-field mt-1" placeholder="-1 for random">
                        </div>
                        <div v-for="param in modelConfigurableParameters" :key="param.name">
                            <label :for="`param-${param.name}`" class="block text-sm font-medium capitalize">{{ param.name.replace(/_/g, ' ') }}</label>
                            <input :type="param.type === 'str' ? 'text' : 'number'" :step="param.type === 'float' ? '0.1' : '1'" :id="`param-${param.name}`" v-model="generationParams[param.name]" class="input-field mt-1" :placeholder="param.default">
                        </div>
                    </div>
                </div>

                <!-- Canvas Column -->
                <div 
                    class="md:col-span-3 relative aspect-auto min-h-[400px] overflow-hidden bg-gray-200 dark:bg-gray-900 rounded-lg" 
                    ref="canvasContainerRef"
                    @wheel="handleWheel"
                    @mousedown="handleMouseDown"
                    @mousemove="handleMouseMove"
                    @mouseup="stopDragging"
                    @mouseleave="stopDragging"
                >
                    <div ref="transformContainerRef" :style="transformStyle">
                        <AuthenticatedImage ref="imageRef" :src="imageUrl" @load="onImageLoad" class="absolute top-0 left-0 pointer-events-none" />
                        <canvas ref="drawingCanvasRef" class="absolute top-0 left-0 pointer-events-none"></canvas>
                        <canvas ref="canvasRef" class="absolute top-0 left-0 cursor-crosshair"></canvas>
                    </div>
                    <div class="absolute top-2 right-2 flex flex-col gap-2">
                        <button @click="openImageViewer" class="p-2 bg-black/50 text-white rounded-full hover:bg-black/70 transition-colors" title="View Full Size"><IconMaximize class="w-5 h-5"/></button>
                    </div>
                </div>
            </div>
        </template>
        <template #footer v-if="!isNewDrawingSetup">
            <button @click="uiStore.closeModal('inpaintingEditor')" class="btn btn-secondary">Cancel</button>
            <button @click="handleGenerate" class="btn btn-primary" :disabled="imageStore.isGenerating || !prompt.trim()">
                <IconAnimateSpin v-if="imageStore.isGenerating" class="w-5 h-5 mr-2" />
                Generate
            </button>
        </template>
    </GenericModal>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useImageStore } from '../../stores/images';
import { useDataStore } from '../../stores/data';
import { useAuthStore } from '../../stores/auth';
import GenericModal from './GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';

const uiStore = useUiStore();
const imageStore = useImageStore();
const dataStore = useDataStore();
const authStore = useAuthStore();

const props = computed(() => uiStore.modalData('inpaintingEditor'));
const originalImage = computed(() => props.value?.image);

const internalImage = ref(null);
const imageUrl = ref(null);
const isNewDrawingSetup = ref(false);
const newCanvas = ref({ width: 1024, height: 1024, bgColor: '#FFFFFF' });

const modalTitle = computed(() => isNewDrawingSetup.value ? 'New Drawing' : `Image Editor: ${internalImage.value?.filename}`);

const canvasContainerRef = ref(null);
const canvasRef = ref(null);
const drawingCanvasRef = ref(null);
const imageRef = ref(null);
const transformContainerRef = ref(null);
const maskCtx = ref(null);
const drawingCtx = ref(null);

const editorMode = ref('mask');
const brushSize = ref(40);
const tool = ref('brush');
const prompt = ref('');
const negativePrompt = ref('');
const brushColor = ref('#000000');
const brushOpacity = ref(1.0);
const colorPalette = ['#FFFFFF', '#000000', '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF'];
const seed = ref(-1);
const generationParams = ref({});

const history = ref([]);
const historyIndex = ref(-1);
let resizeObserver = null;

const scale = ref(1);
const translateX = ref(0);
const translateY = ref(0);
const isDragging = ref(false);
const isDrawing = ref(false);
const lastX = ref(0);
const lastY = ref(0);

const canUndo = computed(() => historyIndex.value > 0);
const canRedo = computed(() => historyIndex.value < history.value.length - 1);

const transformStyle = computed(() => ({
  transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value})`,
  transformOrigin: 'top left',
  cursor: isDragging.value ? 'grabbing' : 'crosshair',
}));

const user = computed(() => authStore.user);
const selectedModel = computed(() => internalImage.value?.model || user.value?.tti_binding_model_name);
const selectedModelDetails = computed(() => {
    if (!selectedModel.value || dataStore.availableTtiModels.length === 0) return null;
    return dataStore.availableTtiModels.find(m => m.id === selectedModel.value);
});
const modelConfigurableParameters = computed(() => {
    if (!selectedModelDetails.value?.binding_params) return [];
    const params = selectedModelDetails.value.binding_params.edit_parameters || [];
    const excluded = ['prompt', 'negative_prompt', 'image', 'mask', 'width', 'height', 'n', 'seed', 'size'];
    return params.filter(p => !excluded.includes(p.name));
});

watch(selectedModelDetails, (details) => {
    generationParams.value = {};
    if (details) {
        modelConfigurableParameters.value.forEach(param => {
            generationParams.value[param.name] = param.default;
        });
    }
}, { immediate: true, deep: true });

function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function setTool(newTool) { tool.value = newTool; }

function onImageLoad() {
    nextTick().then(() => {
        setupCanvas();
        if (canvasContainerRef.value) {
            resizeObserver = new ResizeObserver(setupCanvas);
            resizeObserver.observe(canvasContainerRef.value);
        }
    });
}

function setupCanvas() {
    if (!canvasRef.value || !drawingCanvasRef.value || !transformContainerRef.value) return;
    
    const imageEl = imageRef.value?.$el?.querySelector('img');
    const hasImageElement = imageEl && imageEl.complete && imageEl.naturalWidth > 0;
    
    const canvasWidth = hasImageElement ? imageEl.naturalWidth : newCanvas.value.width;
    const canvasHeight = hasImageElement ? imageEl.naturalHeight : newCanvas.value.height;

    transformContainerRef.value.style.width = `${canvasWidth}px`;
    transformContainerRef.value.style.height = `${canvasHeight}px`;

    [canvasRef.value, drawingCanvasRef.value].forEach(canvas => {
        canvas.width = canvasWidth;
        canvas.height = canvasHeight;
    });

    maskCtx.value = canvasRef.value.getContext('2d', { willReadFrequently: true });
    Object.assign(maskCtx.value, { lineCap: 'round', lineJoin: 'round' });

    drawingCtx.value = drawingCanvasRef.value.getContext('2d', { willReadFrequently: true });
    Object.assign(drawingCtx.value, { lineCap: 'round', lineJoin: 'round' });

    canvasRef.value.removeEventListener('mousedown', startDrawing);
    canvasRef.value.addEventListener('mousedown', startDrawing);
    
    resetView();
    if (history.value.length === 0) { // Only save initial state once
      saveState();
    }
}

function getCanvasCoordinates(event) {
    const canvas = canvasRef.value;
    const rect = canvas.getBoundingClientRect();
    const clientX = event.touches ? event.touches[0].clientX : event.clientX;
    const clientY = event.touches ? event.touches[0].clientY : event.clientY;
    return {
        x: (clientX - rect.left) / scale.value,
        y: (clientY - rect.top) / scale.value
    };
}

function startDrawing(event) {
    if (isDragging.value) return;
    event.preventDefault();
    event.stopPropagation();
    isDrawing.value = true;
    const { x, y } = getCanvasCoordinates(event);
    const activeCtx = editorMode.value === 'mask' ? maskCtx.value : drawingCtx.value;
    activeCtx.beginPath();
    activeCtx.moveTo(x, y);
    draw(event);
}

function draw(event) {
    if (!isDrawing.value) return;
    event.preventDefault();
    const { x, y } = getCanvasCoordinates(event);
    const activeCtx = editorMode.value === 'mask' ? maskCtx.value : drawingCtx.value;
    
    activeCtx.globalCompositeOperation = tool.value === 'eraser' ? 'destination-out' : 'source-over';
    activeCtx.lineWidth = brushSize.value;
    
    if (editorMode.value === 'mask') {
        activeCtx.strokeStyle = 'rgba(0,0,0,1)';
        activeCtx.fillStyle = 'rgba(0,0,0,1)';
    } else {
        const color = hexToRgba(brushColor.value, brushOpacity.value);
        activeCtx.strokeStyle = color;
        activeCtx.fillStyle = color;
    }
    
    activeCtx.lineTo(x, y);
    activeCtx.stroke();
    activeCtx.beginPath();
    activeCtx.arc(x, y, brushSize.value / 2, 0, Math.PI * 2);
    activeCtx.fill();
    activeCtx.beginPath();
    activeCtx.moveTo(x, y);
}

function stopDrawing() {
    if (!isDrawing.value) return;
    isDrawing.value = false;
    const activeCtx = editorMode.value === 'mask' ? maskCtx.value : drawingCtx.value;
    activeCtx.closePath();
    saveState();
}

function saveState() {
    if (!maskCtx.value || !drawingCtx.value) return;
    const maskData = maskCtx.value.getImageData(0, 0, canvasRef.value.width, canvasRef.value.height);
    const drawingData = drawingCtx.value.getImageData(0, 0, drawingCanvasRef.value.width, drawingCanvasRef.value.height);
    history.value.splice(historyIndex.value + 1);
    history.value.push({ maskData, drawingData });
    historyIndex.value++;
}

function undo() {
    if (canUndo.value) {
        historyIndex.value--;
        const state = history.value[historyIndex.value];
        maskCtx.value.putImageData(state.maskData, 0, 0);
        drawingCtx.value.putImageData(state.drawingData, 0, 0);
    }
}

function redo() {
    if (canRedo.value) {
        historyIndex.value++;
        const state = history.value[historyIndex.value];
        maskCtx.value.putImageData(state.maskData, 0, 0);
        drawingCtx.value.putImageData(state.drawingData, 0, 0);
    }
}

function clearCanvas() {
    const activeCtx = editorMode.value === 'mask' ? maskCtx.value : drawingCtx.value;
    activeCtx.clearRect(0, 0, activeCtx.canvas.width, activeCtx.canvas.height);
    saveState();
}

function isCanvasEmpty(canvas) {
    if (!canvas) return true;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    try {
        const pixelBuffer = new Uint32Array(context.getImageData(0, 0, canvas.width, canvas.height).data.buffer);
        return !pixelBuffer.some(color => color !== 0);
    } catch(e) { return false; }
}

async function mergeImageAndDrawing() {
    const tempCanvas = document.createElement('canvas');
    const tempCtx = tempCanvas.getContext('2d');
    const imageEl = imageRef.value.$el.querySelector('img');
    tempCanvas.width = imageEl.naturalWidth;
    tempCanvas.height = imageEl.naturalHeight;
    tempCtx.drawImage(imageEl, 0, 0);
    tempCtx.drawImage(drawingCanvasRef.value, 0, 0);
    return tempCanvas.toDataURL('image/png');
}

async function handleGenerate() {
    if (!internalImage.value || imageStore.isGenerating) return;
    const isMaskEmpty = isCanvasEmpty(canvasRef.value);
    const isDrawingEmpty = isCanvasEmpty(drawingCanvasRef.value);
    const isNewImage = !internalImage.value.id;

    const payload = {
        prompt: prompt.value,
        negative_prompt: negativePrompt.value,
        model: internalImage.value.model,
        mask: isMaskEmpty ? null : canvasRef.value.toDataURL('image/png').split(',')[1],
        seed: seed.value,
        ...generationParams.value
    };

    if (!isDrawingEmpty) {
        const mergedImageB64 = await mergeImageAndDrawing();
        payload.base_image_b64 = mergedImageB64.split(',')[1];
    } else if (isNewImage) {
        const canvas = document.createElement('canvas');
        canvas.width = internalImage.value.width;
        canvas.height = internalImage.value.height;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = internalImage.value.bgColor;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        payload.base_image_b64 = canvas.toDataURL('image/png').split(',')[1];
        payload.width = canvas.width;
        payload.height = canvas.height;
    } else {
        payload.image_ids = [internalImage.value.id];
    }
    
    await imageStore.editImage(payload);
    uiStore.closeModal('inpaintingEditor');
}


async function handleEnhance(type) { /* ... */ }
function openImageViewer() { uiStore.openImageViewer({ imageList: [{ src: imageUrl.value, prompt: internalImage.value.prompt }], startIndex: 0 }); }
function resetView() { /* ... */ }
function handleWheel(event) { /* ... */ }
function handleMouseDown(event) {
    if (event.target !== canvasRef.value) {
        if (event.button !== 0 || isDrawing.value) return;
        event.preventDefault();
        isDragging.value = true;
        lastX.value = event.clientX;
        lastY.value = event.clientY;
    }
}
function handleMouseMove(event) {
    if (isDrawing.value) { draw(event); return; }
    if (!isDragging.value) return;
    event.preventDefault();
    const dx = event.clientX - lastX.value;
    const dy = event.clientY - lastY.value;
    translateX.value += dx;
    translateY.value += dy;
    lastX.value = event.clientX;
    lastY.value = event.clientY;
}
function stopDragging() { isDragging.value = false; }

function reuseOriginalPrompt() {
    if (originalImage.value) {
        prompt.value = originalImage.value.prompt || '';
        negativePrompt.value = originalImage.value.negative_prompt || '';
        seed.value = originalImage.value.seed || -1;
        uiStore.addNotification('Original prompt and settings restored.', 'success');
    }
}

function createBlankCanvas() {
    const canvas = document.createElement('canvas');
    canvas.width = newCanvas.value.width;
    canvas.height = newCanvas.value.height;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = newCanvas.value.bgColor;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    imageUrl.value = canvas.toDataURL('image/png');
    internalImage.value = {
        id: null,
        filename: 'New Drawing.png',
        prompt: '',
        model: user.value?.tti_binding_model_name || '',
        width: newCanvas.value.width,
        height: newCanvas.value.height,
        bgColor: newCanvas.value.bgColor
    };
    isNewDrawingSetup.value = false;
    editorMode.value = 'brush';
}

watch(props, (newProps) => {
    const propImage = newProps?.image;
    if (propImage) {
        internalImage.value = { ...propImage };
        imageUrl.value = `/api/image-studio/${propImage.id}/file`;
        prompt.value = propImage.prompt || '';
        negativePrompt.value = propImage.negative_prompt || '';
        seed.value = propImage.seed || -1;
        isNewDrawingSetup.value = false;
    } else {
        internalImage.value = null;
        imageUrl.value = null;
        prompt.value = '';
        negativePrompt.value = '';
        isNewDrawingSetup.value = true;
        newCanvas.value.width = newProps?.width || 1024;
        newCanvas.value.height = newProps?.height || 1024;
    }
    history.value = [];
    historyIndex.value = -1;
}, { immediate: true });

onMounted(() => {
    window.addEventListener('mouseup', stopDrawing);
    window.addEventListener('mouseup', stopDragging);
    if(dataStore.availableTtiModels.length === 0) dataStore.fetchAvailableTtiModels();
});

onUnmounted(() => {
    if (resizeObserver && canvasContainerRef.value) resizeObserver.unobserve(canvasContainerRef.value);
    window.removeEventListener('mouseup', stopDrawing);
    window.removeEventListener('mouseup', stopDragging);
});
</script>