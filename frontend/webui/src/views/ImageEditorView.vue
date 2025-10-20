<!-- [UPDATE] frontend/webui/src/views/ImageEditorView.vue -->
<template>
    <Teleport to="#global-header-actions-target">
        <div class="flex items-center gap-2">
            <button @click="handleSaveAs" class="btn btn-secondary" :disabled="imageStore.isGenerating">
                <IconSave class="w-5 h-5 mr-2" /> Save As New Image
            </button>
            <button @click="handleGenerate" class="btn btn-primary" :disabled="imageStore.isGenerating || !prompt.trim()">
                <IconAnimateSpin v-if="imageStore.isGenerating" class="w-5 h-5 mr-2 animate-spin" />
                Apply
            </button>
        </div>
    </Teleport>
    <div class="h-full flex flex-col bg-gray-50 dark:bg-gray-900">
        <!-- Main Content -->
        <div class="flex-grow min-h-0 flex">
            <!-- Controls Column -->
            <div class="w-80 flex-shrink-0 bg-white dark:bg-gray-800 border-r dark:border-gray-700 flex flex-col">
                <div class="flex-grow p-4 space-y-4 overflow-y-auto custom-scrollbar">
                    <!-- Prompts Section -->
                    <div class="space-y-4">
                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label for="inpainting-prompt" class="block text-sm font-medium">Prompt</label>
                                <div class="flex gap-1">
                                    <button v-if="originalImage" @click="reuseOriginalPrompt" class="btn btn-secondary btn-xs" title="Reuse original image prompt and settings">Reuse</button>
                                    <button @click="handleEnhance('prompt')" class="btn-icon-xs" title="Enhance prompt with AI" :disabled="imageStore.isEnhancing"><IconSparkles class="w-4 h-4" /></button>
                                </div>
                            </div>
                            <div class="relative min-h-[72px]">
                                <div v-if="enhancingTarget === 'prompt' || enhancingTarget === 'both'" class="absolute inset-0 bg-gray-100 dark:bg-gray-700/50 rounded-md flex items-center justify-center">
                                    <IconAnimateSpin class="w-6 h-6 text-gray-500 animate-spin" />
                                </div>
                                <textarea v-else id="inpainting-prompt" v-model="prompt" rows="3" class="input-field w-full" placeholder="Describe the edit..."></textarea>
                            </div>
                        </div>
                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label for="inpainting-neg-prompt" class="block text-sm font-medium">Negative Prompt</label>
                                <button @click="handleEnhance('negative_prompt')" class="btn-icon-xs" title="Enhance negative prompt with AI" :disabled="imageStore.isEnhancing"><IconSparkles class="w-4 h-4" /></button>
                            </div>
                            <div class="relative min-h-[48px]">
                                <div v-if="enhancingTarget === 'negative_prompt' || enhancingTarget === 'both'" class="absolute inset-0 bg-gray-100 dark:bg-gray-700/50 rounded-md flex items-center justify-center">
                                    <IconAnimateSpin class="w-6 h-6 text-gray-500 animate-spin" />
                                </div>
                                <textarea v-else id="inpainting-neg-prompt" v-model="negativePrompt" rows="2" class="input-field w-full" placeholder="ugly, blurry, bad anatomy..."></textarea>
                            </div>
                        </div>
                        <div>
                            <label for="enhancement-instructions" class="block text-sm font-medium mb-1">Enhancement Instructions</label>
                            <textarea id="enhancement-instructions" v-model="enhancementInstructions" rows="2" class="input-field w-full" placeholder="Optional: Guide the AI... e.g., 'make it more cinematic'"></textarea>
                            <button @click="handleEnhance('both')" class="btn btn-secondary w-full mt-2" :disabled="imageStore.isEnhancing">
                                <IconSparkles class="w-4 h-4 mr-2" /> Enhance Both Prompts
                            </button>
                        </div>
                    </div>

                    <!-- Tools & Properties Section -->
                    <div class="p-4 bg-gray-100 dark:bg-gray-700/50 rounded-lg space-y-4 border dark:border-gray-600">
                        <h3 class="font-semibold text-sm">Tools & Properties</h3>
                        <div>
                            <label class="block text-sm font-medium">Mode</label>
                            <div class="flex gap-2 mt-1">
                                <button @click="editorMode = 'mask'" :class="['btn btn-secondary btn-icon flex-1', { 'btn-primary': editorMode === 'mask' }]" title="Inpainting Mask">
                                    <IconLayout class="w-5 h-5" />
                                </button>
                                <button @click="editorMode = 'brush'" :class="['btn btn-secondary btn-icon flex-1', { 'btn-primary': editorMode === 'brush' }]" title="Drawing Brush">
                                    <IconPencil class="w-5 h-5" />
                                </button>
                            </div>
                        </div>
                        <div>
                            <label class="block text-sm font-medium">Tool</label>
                            <div class="flex gap-2 mt-1">
                                <button @click="tool = 'brush'" :class="['btn btn-secondary btn-icon flex-1', { 'btn-primary': tool === 'brush' }]" title="Draw Tool">
                                    <IconPencil class="w-5 h-5" />
                                </button>
                                <button @click="tool = 'eraser'" :class="['btn btn-secondary btn-icon flex-1', { 'btn-primary': tool === 'eraser' }]" title="Eraser Tool">
                                    <IconMinusCircle class="w-5 h-5" />
                                </button>
                            </div>
                        </div>
                        <div>
                            <label class="block text-sm font-medium">Brush Size: {{ brushSize }}</label>
                            <input type="range" min="1" max="150" v-model.number="brushSize" class="w-full">
                        </div>
                        <div v-if="editorMode === 'brush'">
                             <label class="block text-sm font-medium">Brush Color & Opacity</label>
                            <div class="flex items-center gap-2 mt-1">
                                <input type="color" v-model="brushColor" class="w-10 h-10 p-1 bg-white dark:bg-gray-800 border dark:border-gray-600 rounded cursor-pointer">
                                <div class="grid grid-cols-6 gap-1 flex-1">
                                    <button v-for="color in colorPalette" :key="color" @click="brushColor = color" class="w-6 h-6 rounded-full border-2" :style="{ backgroundColor: color, borderColor: brushColor === color ? 'blue' : 'transparent' }"></button>
                                </div>
                            </div>
                            <div>
                                <label class="block text-sm font-medium mt-2">Opacity: {{ Math.round(brushOpacity * 100) }}%</label>
                                <input type="range" min="0.01" max="1" step="0.01" v-model.number="brushOpacity" class="w-full">
                            </div>
                        </div>
                    </div>

                    <!-- Actions Section -->
                    <div class="p-4 bg-gray-100 dark:bg-gray-700/50 rounded-lg space-y-2 border dark:border-gray-600">
                        <h3 class="font-semibold text-sm mb-2">Actions</h3>
                        <div class="flex gap-2">
                            <button @click="undo" class="btn btn-secondary btn-icon flex-1" :disabled="!canUndo" title="Undo"><IconUndo class="w-5 h-5" /></button>
                            <button @click="redo" class="btn btn-secondary btn-icon flex-1" :disabled="!canRedo" title="Redo"><IconRedo class="w-5 h-5" /></button>
                        </div>
                        <div class="flex gap-2">
                            <button @click="clearCanvas" class="btn btn-danger-outline btn-icon flex-1" title="Clear Canvas"><IconTrash class="w-5 h-5" /></button>
                            <button @click="resetView" class="btn btn-secondary btn-icon flex-1" title="Reset View"><IconRefresh class="w-5 h-5" /></button>
                        </div>
                    </div>

                    <!-- Generation Settings Section -->
                    <div class="pt-4 border-t dark:border-gray-600">
                        <div class="flex items-center justify-between">
                            <h3 class="text-sm font-semibold">Generation Settings</h3>
                            <button @click="isConfigVisible = !isConfigVisible" class="btn-icon-flat" :title="isConfigVisible ? 'Hide Settings' : 'Show Settings'">
                                <IconAdjustmentsHorizontal class="w-5 h-5" />
                            </button>
                        </div>
                        <div v-if="isConfigVisible" class="mt-4 space-y-4">
                            <div><label for="seed" class="block text-sm font-medium">Seed</label><input id="seed" v-model.number="seed" type="number" class="input-field mt-1" placeholder="-1 for random"></div>
                            <div v-for="param in modelConfigurableParameters" :key="param.name">
                                <label :for="`param-${param.name}`" class="block text-sm font-medium capitalize">{{ param.name.replace(/_/g, ' ') }}</label>
                                <input :type="param.type === 'str' ? 'text' : 'number'" :step="param.type === 'float' ? '0.1' : '1'" :id="`param-${param.name}`" v-model="generationParams[param.name]" class="input-field mt-1" :placeholder="param.default">
                            </div>
                        </div>
                    </div>
                </div>
                <div class="p-4 border-t dark:border-gray-700 flex-shrink-0 space-y-2">
                    <button @click="handleGenerate" class="btn btn-primary w-full" :disabled="imageStore.isGenerating || !prompt.trim()">
                        <IconAnimateSpin v-if="imageStore.isGenerating" class="w-5 h-5 mr-2 animate-spin" />
                        Apply
                    </button>
                    <router-link to="/image-studio" class="btn btn-secondary w-full flex items-center justify-center" title="Back to Image Studio">
                        <IconArrowLeft class="w-5 h-5 mr-2" />
                        <span>Back to Studio</span>
                    </router-link>
                </div>
            </div>
            
            <!-- Canvas Column -->
            <div class="flex-grow min-w-0 flex items-center justify-center bg-gray-100 dark:bg-gray-900/50 p-4">
                <div 
                    class="relative aspect-auto overflow-hidden bg-gray-200 dark:bg-gray-900 rounded-lg shadow-inner" 
                    ref="canvasContainerRef"
                    @wheel="handleWheel" @mousedown="handleMouseDown" @mousemove="handleMouseMove" @mouseup="stopDragging" @mouseleave="stopDragging"
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
        </div>
    </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick, markRaw } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useUiStore } from '../stores/ui';
import { useImageStore } from '../stores/images';
import { useDataStore } from '../stores/data';
import { useAuthStore } from '../stores/auth';
import AuthenticatedImage from '../components/ui/AuthenticatedImage.vue';

// --- Icons ---
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';
import IconSave from '../assets/icons/IconSave.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconMaximize from '../assets/icons/IconMaximize.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconLayout from '../assets/icons/ui/IconLayout.vue';
import IconMinusCircle from '../assets/icons/ui/IconMinusCircle.vue';
import IconUndo from '../assets/icons/IconUndo.vue';
import IconRedo from '../assets/icons/IconRedo.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';
import IconAdjustmentsHorizontal from '../assets/icons/IconAdjustmentsHorizontal.vue';
import IconPlus from '../assets/icons/IconPlus.vue';

const uiStore = useUiStore();
const imageStore = useImageStore();
const dataStore = useDataStore();
const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const props = defineProps({
    id: String,
    newImage: Boolean,
});

const originalImage = ref(null);
const internalImage = ref(null);
const imageUrl = ref(null);
const newCanvas = ref({ width: 1024, height: 1024, bgColor: '#FFFFFF' });

const pageTitle = computed(() => `Image Editor: ${internalImage.value?.filename || 'New Drawing'}`);

watch(pageTitle, (newTitle) => {
    uiStore.setPageTitle({ title: newTitle, icon: markRaw(IconPencil) });
}, { immediate: true });


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
const isConfigVisible = ref(false);
const enhancingTarget = ref(null);
const enhancementInstructions = ref('');

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
    if (history.value.length === 0) {
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

function undo() { if (canUndo.value) { historyIndex.value--; const state = history.value[historyIndex.value]; maskCtx.value.putImageData(state.maskData, 0, 0); drawingCtx.value.putImageData(state.drawingData, 0, 0); } }
function redo() { if (canRedo.value) { historyIndex.value++; const state = history.value[historyIndex.value]; maskCtx.value.putImageData(state.maskData, 0, 0); drawingCtx.value.putImageData(state.drawingData, 0, 0); } }
function clearCanvas() { const activeCtx = editorMode.value === 'mask' ? maskCtx.value : drawingCtx.value; activeCtx.clearRect(0, 0, activeCtx.canvas.width, activeCtx.canvas.height); saveState(); }
function isCanvasEmpty(canvas) { if (!canvas) return true; const context = canvas.getContext('2d', { willReadFrequently: true }); try { const pixelBuffer = new Uint32Array(context.getImageData(0, 0, canvas.width, canvas.height).data.buffer); return !pixelBuffer.some(color => color !== 0); } catch(e) { return false; } }

async function getBaseImageB64() {
    if (!internalImage.value || !imageRef.value) return null;
    const imageEl = imageRef.value.$el.querySelector('img');
    if (imageEl && imageEl.src && !imageEl.src.startsWith('data:')) {
        const response = await fetch(imageEl.src);
        const blob = await response.blob();
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result.split(','));
            reader.readAsDataURL(blob);
        });
    }
    return imageUrl.value ? imageUrl.value.split(',') : null;
}

async function handleSaveAs() {
    const payload = {
        base_image_b64: await getBaseImageB64(),
        drawing_b64: isCanvasEmpty(drawingCanvasRef.value) ? null : drawingCanvasRef.value.toDataURL('image/png').split(','),
        prompt: prompt.value,
        model: selectedModel.value,
        width: internalImage.value?.width || newCanvas.value.width,
        height: internalImage.value?.height || newCanvas.value.height,
        bg_color: internalImage.value?.bgColor || newCanvas.value.bgColor
    };
    const newImage = await imageStore.saveCanvasAsNewImage(payload);
    if(newImage){
        router.replace(`/image-studio/edit/${newImage.id}`);
    }
}

async function handleGenerate() {
    if (!internalImage.value || imageStore.isGenerating) return;
    const isMaskEmpty = isCanvasEmpty(canvasRef.value);
    const payload = {
        prompt: prompt.value,
        negative_prompt: negativePrompt.value,
        model: selectedModel.value,
        mask: isMaskEmpty ? null : canvasRef.value.toDataURL('image/png').split(','),
        seed: seed.value,
        ...generationParams.value,
        image_ids: [internalImage.value.id],
        width: internalImage.value.width,
        height: internalImage.value.height
    };
    await imageStore.editImage(payload);
}

async function handleEnhance(type) {
    if (type !== 'negative_prompt' && !prompt.value.trim()) { uiStore.addNotification('Please enter a prompt to enhance.', 'warning'); return; }
    
    enhancingTarget.value = type;
    
    const payload = {
        prompt: prompt.value,
        negative_prompt: negativePrompt.value,
        target: type,
        model: authStore.user?.lollms_model_name,
        instructions: enhancementInstructions.value,
    };

    try {
        const result = await imageStore.enhanceImagePrompt(payload);
        if (result) {
            if (result.prompt) prompt.value = result.prompt;
            if (result.negative_prompt) negativePrompt.value = result.negative_prompt;
        }
    } finally {
        enhancingTarget.value = null;
    }
}

function openImageViewer() { uiStore.openImageViewer({ imageList: [{ src: imageUrl.value, prompt: internalImage.value.prompt }], startIndex: 0 }); }
function resetView() { scale.value = 1; translateX.value = 0; translateY.value = 0; }
function handleWheel(event) { event.preventDefault(); const scaleAmount = 0.1; if (!canvasContainerRef.value) return; const rect = canvasContainerRef.value.getBoundingClientRect(); const mouseX = event.clientX - rect.left; const mouseY = event.clientY - rect.top; const oldScale = scale.value; const newScale = oldScale * (1 - Math.sign(event.deltaY) * scaleAmount); scale.value = Math.min(Math.max(0.1, 10), newScale); const newTx = translateX.value - (mouseX / oldScale - mouseX / scale.value) * scale.value; const newTy = translateY.value - (mouseY / oldScale - mouseY / scale.value) * scale.value; translateX.value = newTx; translateY.value = newTy; }
function handleMouseDown(event) { if (event.target !== canvasRef.value) { if (event.button !== 0 || isDrawing.value) return; event.preventDefault(); isDragging.value = true; lastX.value = event.clientX; lastY.value = event.clientY; } }
function handleMouseMove(event) { if (isDrawing.value) { draw(event); return; } if (!isDragging.value) return; event.preventDefault(); const dx = event.clientX - lastX.value; const dy = event.clientY - lastY.value; translateX.value += dx; translateY.value += dy; lastX.value = event.clientX; lastY.value = event.clientY; }
function stopDragging() { isDragging.value = false; }
function reuseOriginalPrompt() { if (originalImage.value) { prompt.value = originalImage.value.prompt || ''; negativePrompt.value = originalImage.value.negative_prompt || ''; seed.value = originalImage.value.seed || -1; uiStore.addNotification('Original prompt and settings restored.', 'success'); } }

onMounted(async () => {
    if (props.newImage) {
        const canvas = document.createElement('canvas');
        canvas.width = newCanvas.value.width;
        canvas.height = newCanvas.value.height;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = newCanvas.value.bgColor;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        imageUrl.value = canvas.toDataURL('image/png');
        internalImage.value = { id: null, filename: 'New Drawing.png', prompt: '', model: user.value?.tti_binding_model_name || '', width: newCanvas.value.width, height: newCanvas.value.height, bgColor: newCanvas.value.bgColor };
        editorMode.value = 'brush';
    } else {
        const foundImage = imageStore.images.find(img => img.id === props.id);
        if (foundImage) {
            originalImage.value = { ...foundImage };
            internalImage.value = { ...foundImage };
            imageUrl.value = `/api/image-studio/${foundImage.id}/file`;
            prompt.value = foundImage.prompt || '';
            negativePrompt.value = foundImage.negative_prompt || '';
            seed.value = foundImage.seed || -1;
        }
    }
    
    window.addEventListener('mouseup', stopDrawing);
    window.addEventListener('mouseup', stopDragging);
    if(dataStore.availableTtiModels.length === 0) dataStore.fetchAvailableTtiModels();
});

onUnmounted(() => {
    uiStore.setPageTitle({ title: '' });
    if (resizeObserver && canvasContainerRef.value) resizeObserver.unobserve(canvasContainerRef.value);
    window.removeEventListener('mouseup', stopDrawing);
    window.removeEventListener('mouseup', stopDragging);
});
</script>