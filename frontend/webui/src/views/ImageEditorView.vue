<template>
    <div class="h-full flex flex-col bg-gray-100 dark:bg-gray-900 overflow-hidden relative">
        <!-- Top Toolbar -->
        <div class="h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-4 z-20 shadow-sm">
            <div class="flex items-center gap-4">
                <button @click="goBack" class="btn-icon" title="Back to Gallery">
                    <IconArrowLeft class="w-5 h-5" />
                </button>
                <div class="h-6 w-px bg-gray-300 dark:bg-gray-600"></div>
                <div class="flex items-center gap-2">
                    <button @click="tool = 'pan'" class="btn-icon" :class="{ 'bg-blue-100 dark:bg-blue-900/50 text-blue-600': tool === 'pan' }" title="Pan Tool (Space)">
                        <IconHand class="w-5 h-5" />
                    </button>
                    <button @click="tool = 'brush'" class="btn-icon" :class="{ 'bg-blue-100 dark:bg-blue-900/50 text-blue-600': tool === 'brush' }" title="Brush Tool (B)">
                        <IconPencil class="w-5 h-5" />
                    </button>
                    <button @click="tool = 'eraser'" class="btn-icon" :class="{ 'bg-blue-100 dark:bg-blue-900/50 text-blue-600': tool === 'eraser' }" title="Eraser Tool (E)">
                        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20H7L3 16C2 15 2 13 3 12L13 2L22 11L20 20Z"/><path d="M11 11L20 20"/></svg>
                    </button>
                </div>
                
                <div class="flex items-center gap-2 ml-4" v-if="tool !== 'pan'">
                    <span class="text-xs font-medium text-gray-500 uppercase">Size</span>
                    <input type="range" v-model.number="brushSize" min="5" max="100" class="w-32 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700">
                    <span class="text-xs w-6">{{ brushSize }}</span>
                </div>
            </div>

            <div class="flex items-center gap-2">
                <button @click="undo" :disabled="historyIndex <= 0" class="btn-icon" title="Undo (Ctrl+Z)">
                    <IconUndo class="w-5 h-5" />
                </button>
                <button @click="redo" :disabled="historyIndex >= history.length - 1" class="btn-icon" title="Redo (Ctrl+Y)">
                    <IconRedo class="w-5 h-5" />
                </button>
                <div class="h-6 w-px bg-gray-300 dark:bg-gray-600 mx-2"></div>
                <button @click="clearMask" class="btn-icon text-red-500 hover:text-red-600" title="Clear Mask">
                    <IconTrash class="w-5 h-5" />
                </button>
                <button @click="saveCanvas" class="btn btn-secondary btn-sm gap-2">
                    <IconSave class="w-4 h-4" /> Save Copy
                </button>
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
                <!-- Canvas Container -->
                <div 
                    :style="{ transform: `translate(${panX}px, ${panY}px) scale(${zoom})` }" 
                    class="relative shadow-2xl origin-center transition-transform duration-75"
                >
                    <!-- Base Image Canvas -->
                    <canvas ref="imageCanvasRef" class="block bg-white"></canvas>
                    
                    <!-- Mask Canvas (Drawing Layer) -->
                    <canvas ref="maskCanvasRef" class="absolute inset-0 opacity-60"></canvas>
                    
                    <!-- Brush Cursor Overlay (Only visible when brushing) -->
                    <div 
                        v-show="tool !== 'pan' && isHoveringCanvas"
                        class="absolute pointer-events-none rounded-full border border-white bg-black/10 z-50 transform -translate-x-1/2 -translate-y-1/2"
                        :style="{ 
                            width: `${brushSize}px`, 
                            height: `${brushSize}px`, 
                            left: `${cursorX}px`, 
                            top: `${cursorY}px` 
                        }"
                    ></div>
                </div>

                <!-- Zoom Controls Overlay -->
                <div class="absolute bottom-4 left-4 bg-white/90 dark:bg-gray-800/90 backdrop-blur rounded-lg shadow p-2 flex items-center gap-2 z-10">
                    <button @click="zoomOut" class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><IconMinus class="w-4 h-4" /></button>
                    <span class="text-xs font-mono w-12 text-center">{{ Math.round(zoom * 100) }}%</span>
                    <button @click="zoomIn" class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"><IconPlus class="w-4 h-4" /></button>
                    <button @click="fitToScreen" class="p-1 hover:bg-gray-100 dark:hover:bg-gray-700 rounded ml-1" title="Fit to Screen"><IconMaximize class="w-4 h-4" /></button>
                </div>
            </div>

            <!-- Settings Sidebar -->
            <div class="w-80 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 flex flex-col z-20 shadow-xl">
                <div class="p-4 border-b dark:border-gray-700 flex justify-between items-center bg-gray-50 dark:bg-gray-800/50">
                    <h3 class="font-semibold">Edit Settings</h3>
                    <div v-if="isGenerating" class="flex items-center text-xs text-blue-500 animate-pulse">
                        <IconAnimateSpin class="w-3 h-3 mr-1" /> Generating...
                    </div>
                </div>
                
                <div class="flex-grow overflow-y-auto p-4 space-y-5 custom-scrollbar">
                    <div>
                        <div class="flex justify-between items-center mb-1">
                            <label class="label">Prompt</label>
                            <button @click="enhancePrompt" class="text-blue-500 hover:text-blue-600 text-xs flex items-center gap-1" :disabled="isGenerating">
                                <IconSparkles class="w-3 h-3" /> Enhance
                            </button>
                        </div>
                        <textarea v-model="prompt" rows="3" class="input-field w-full text-sm" placeholder="What to generate..."></textarea>
                    </div>

                    <div>
                        <label class="label">Negative Prompt</label>
                        <textarea v-model="negativePrompt" rows="2" class="input-field w-full text-sm" placeholder="What to avoid..."></textarea>
                    </div>

                    <div class="space-y-4 pt-2 border-t dark:border-gray-700/50">
                        <div>
                            <label class="label flex justify-between">
                                <span>Strength (Denoising)</span>
                                <span class="text-gray-500">{{ strength }}</span>
                            </label>
                            <input type="range" v-model.number="strength" min="0.1" max="1.0" step="0.05" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700">
                            <p class="text-[10px] text-gray-500 mt-1">Lower = closer to original, Higher = more creative.</p>
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
                                <optgroup label="Compatible Models">
                                    <option v-for="m in compatibleModels" :key="m.id" :value="m.id">{{ m.name }}</option>
                                </optgroup>
                            </select>
                        </div>
                        
                        <div>
                            <label class="label">Seed</label>
                            <div class="flex gap-2">
                                <input v-model.number="seed" type="number" class="input-field flex-grow text-sm" placeholder="-1">
                                <button @click="seed = -1" class="btn btn-secondary px-2" title="Randomize"><IconRefresh class="w-4 h-4" /></button>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="p-4 border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                    <button @click="generateEdit" class="btn btn-primary w-full py-3 shadow-lg hover:shadow-xl transform active:scale-95 transition-all" :disabled="isGenerating">
                        <template v-if="isGenerating">
                            <IconAnimateSpin class="w-5 h-5 mr-2 animate-spin" /> Processing...
                        </template>
                        <template v-else>
                            <IconSparkles class="w-5 h-5 mr-2" /> Generate Edit
                        </template>
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useImageStore } from '../stores/images';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import apiClient from '../services/api';

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

const props = defineProps({
    id: { type: String, default: null } // 'new' or UUID
});

const route = useRoute();
const router = useRouter();
const imageStore = useImageStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

// --- Refs for Canvas ---
const containerRef = ref(null);
const imageCanvasRef = ref(null);
const maskCanvasRef = ref(null);
const ctxImage = ref(null);
const ctxMask = ref(null);

// --- State ---
const tool = ref('brush'); // 'pan', 'brush', 'eraser'
const brushSize = ref(40);
const zoom = ref(1);
const panX = ref(0);
const panY = ref(0);
const isDragging = ref(false);
const lastX = ref(0);
const lastY = ref(0);
const cursorX = ref(0);
const cursorY = ref(0);
const isHoveringCanvas = ref(false);

// --- Edit Settings ---
const prompt = ref('');
const negativePrompt = ref('');
const strength = ref(0.75);
const cfgScale = ref(7.5);
const seed = ref(-1);
const selectedModel = ref('');
const isGenerating = ref(false);

// --- History ---
const history = ref([]);
const historyIndex = ref(-1);

const compatibleModels = computed(() => dataStore.availableTtiModels);

let currentObjectUrl = null;

onMounted(async () => {
    // Initialize Canvas Contexts
    if (imageCanvasRef.value && maskCanvasRef.value) {
        ctxImage.value = imageCanvasRef.value.getContext('2d');
        ctxMask.value = maskCanvasRef.value.getContext('2d');
    }

    if (props.id === 'new') {
        initializeBlankCanvas();
    } else if (props.id) {
        await loadImage(props.id);
    }

    // Load user preferences
    if (authStore.user) {
        selectedModel.value = authStore.user.iti_binding_model_name || authStore.user.tti_binding_model_name || '';
    }
    
    window.addEventListener('keydown', handleKeydown);
    window.addEventListener('resize', fitToScreen);
});

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown);
    window.removeEventListener('resize', fitToScreen);
    if (currentObjectUrl) {
        URL.revokeObjectURL(currentObjectUrl);
    }
});

// --- Initialization ---

function initializeBlankCanvas(width = 1024, height = 1024) {
    resizeCanvases(width, height);
    ctxImage.value.fillStyle = '#FFFFFF';
    ctxImage.value.fillRect(0, 0, width, height);
    saveState();
    fitToScreen();
}

async function loadImage(imageId) {
    try {
        // Fetch using apiClient to handle authentication headers
        const response = await apiClient.get(`/api/image-studio/${imageId}/file`, {
            responseType: 'blob'
        });
        
        if (currentObjectUrl) {
            URL.revokeObjectURL(currentObjectUrl);
        }
        currentObjectUrl = URL.createObjectURL(response.data);

        const img = new Image();
        await new Promise((resolve, reject) => {
            img.onload = resolve;
            img.onerror = reject;
            img.src = currentObjectUrl;
        });

        resizeCanvases(img.naturalWidth, img.naturalHeight);
        ctxImage.value.drawImage(img, 0, 0);
        
        // Find image details for prompts
        const imgDetails = imageStore.images.find(i => i.id === imageId);
        if (imgDetails) {
            prompt.value = imgDetails.prompt || '';
            negativePrompt.value = imgDetails.negative_prompt || '';
        }

        saveState();
        fitToScreen();
    } catch (e) {
        console.error("Failed to load image", e);
        uiStore.addNotification("Failed to load image for editing (Authentication or Network error).", "error");
        router.push('/image-studio');
    }
}

function resizeCanvases(width, height) {
    if (!imageCanvasRef.value || !maskCanvasRef.value) return;
    imageCanvasRef.value.width = width;
    imageCanvasRef.value.height = height;
    maskCanvasRef.value.width = width;
    maskCanvasRef.value.height = height;
}

// --- Canvas Interactions ---

function getPointerPos(e) {
    if (!maskCanvasRef.value) return { x: 0, y: 0 };
    const rect = maskCanvasRef.value.getBoundingClientRect();
    const scaleX = maskCanvasRef.value.width / rect.width;
    const scaleY = maskCanvasRef.value.height / rect.height;
    return {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY,
        rawX: e.clientX,
        rawY: e.clientY
    };
}

function startAction(e) {
    // Only left click
    if (e.button !== 0) return;
    
    isDragging.value = true;
    lastX.value = e.clientX;
    lastY.value = e.clientY;

    if (tool.value === 'brush' || tool.value === 'eraser') {
        const { x, y } = getPointerPos(e);
        draw(x, y);
    }
}

function handleMove(e) {
    // Cursor Tracking
    const { x, y } = getPointerPos(e);
    // Convert canvas coords back to pixel offset within the scaled container for the cursor div
    // But cursor div is relative to the transformed container div? 
    // Actually simpler: The cursor overlay is inside the same container as canvases
    cursorX.value = x;
    cursorY.value = y;
    isHoveringCanvas.value = true;

    if (!isDragging.value) return;

    if (tool.value === 'pan') {
        const dx = e.clientX - lastX.value;
        const dy = e.clientY - lastY.value;
        panX.value += dx;
        panY.value += dy;
        lastX.value = e.clientX;
        lastY.value = e.clientY;
    } else {
        draw(x, y);
    }
}

function endAction() {
    if (isDragging.value && (tool.value === 'brush' || tool.value === 'eraser')) {
        saveState();
    }
    isDragging.value = false;
    isHoveringCanvas.value = false;
}

function draw(x, y) {
    if (!ctxMask.value) return;
    
    ctxMask.value.globalCompositeOperation = tool.value === 'eraser' ? 'destination-out' : 'source-over';
    ctxMask.value.beginPath();
    ctxMask.value.arc(x, y, brushSize.value / 2, 0, Math.PI * 2);
    ctxMask.value.fillStyle = 'rgba(0, 0, 0, 1)'; // Alpha channel is what matters for mask usually, but visually black
    // For visualization, maybe use a color? 
    // The backend expects a mask image where white is masked or black is masked depending on model.
    // Usually standard is: White = Edit this area, Black = Keep.
    // Let's draw White on the mask canvas for "Edit".
    ctxMask.value.fillStyle = 'rgba(255, 255, 255, 1)'; 
    ctxMask.value.fill();
    ctxMask.value.closePath();
}

function fitToScreen() {
    if (!containerRef.value || !imageCanvasRef.value) return;
    const containerW = containerRef.value.clientWidth;
    const containerH = containerRef.value.clientHeight;
    const imgW = imageCanvasRef.value.width;
    const imgH = imageCanvasRef.value.height;
    
    if (imgW === 0 || imgH === 0) return;

    const scaleW = (containerW - 40) / imgW;
    const scaleH = (containerH - 40) / imgH;
    zoom.value = Math.min(scaleW, scaleH, 1); // Max zoom 1 initially
    panX.value = 0;
    panY.value = 0;
}

function handleWheel(e) {
    if (e.ctrlKey || tool.value === 'pan') {
        e.preventDefault();
        const delta = -Math.sign(e.deltaY) * 0.1;
        zoom.value = Math.min(Math.max(0.1, zoom.value + delta), 5);
    }
}

// --- History (Undo/Redo) ---

function saveState() {
    // Limit history stack size
    if (historyIndex.value < history.value.length - 1) {
        history.value = history.value.slice(0, historyIndex.value + 1);
    }
    
    const maskData = maskCanvasRef.value.toDataURL();
    // Optimization: If base image changes (e.g. after generation), save it too.
    // For now, assuming base image doesn't change unless generated.
    history.value.push({ mask: maskData });
    historyIndex.value++;
    if (history.value.length > 20) {
        history.value.shift();
        historyIndex.value--;
    }
}

function undo() {
    if (historyIndex.value > 0) {
        historyIndex.value--;
        restoreState(history.value[historyIndex.value]);
    } else {
        // Clear if at start
        clearMask(); 
    }
}

function redo() {
    if (historyIndex.value < history.value.length - 1) {
        historyIndex.value++;
        restoreState(history.value[historyIndex.value]);
    }
}

function restoreState(state) {
    const img = new Image();
    img.src = state.mask;
    img.onload = () => {
        ctxMask.value.clearRect(0, 0, maskCanvasRef.value.width, maskCanvasRef.value.height);
        ctxMask.value.drawImage(img, 0, 0);
    };
}

function clearMask() {
    ctxMask.value.clearRect(0, 0, maskCanvasRef.value.width, maskCanvasRef.value.height);
    saveState();
}

// --- Actions ---

async function generateEdit() {
    if (!prompt.value || !selectedModel.value) {
        uiStore.addNotification("Prompt and Model are required.", "warning");
        return;
    }
    
    isGenerating.value = true;
    try {
        // 1. Get Base Image
        const base64Image = imageCanvasRef.value.toDataURL('image/png').split(',')[1];
        
        // 2. Get Mask
        // Ensure mask is strictly black/white if needed, currently alpha.
        // Some backends need pure B&W mask. Let's composite it on black background.
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = maskCanvasRef.value.width;
        tempCanvas.height = maskCanvasRef.value.height;
        const tempCtx = tempCanvas.getContext('2d');
        
        // Fill black (keep)
        tempCtx.fillStyle = '#000000';
        tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
        // Draw mask (white = change)
        tempCtx.drawImage(maskCanvasRef.value, 0, 0);
        
        const base64Mask = tempCanvas.toDataURL('image/png').split(',')[1];

        // 3. Send
        const payload = {
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
        };

        const result = await imageStore.editImage(payload);
        
        // If immediate result (sync mode or fast task), we could load it.
        // But usually it's async task. The store handles task notification.
        // We could listen for task completion to auto-update the canvas?
        // For now, let's just notify.
        
    } catch (e) {
        console.error(e);
        uiStore.addNotification("Generation failed.", "error");
    } finally {
        isGenerating.value = false;
    }
}

async function saveCanvas() {
    // Composite mask + image or just image? Usually user wants the result image.
    // If saving the workspace, we need layers. 
    // For now, let's save the visible image (base).
    const base64Image = imageCanvasRef.value.toDataURL('image/png').split(',')[1];
    await imageStore.saveCanvasAsNewImage({
        base_image_b64: base64Image,
        prompt: prompt.value || "Edited Image",
        width: imageCanvasRef.value.width,
        height: imageCanvasRef.value.height,
        model: selectedModel.value
    });
}

async function enhancePrompt() {
    if (!prompt.value) return;
    const res = await imageStore.enhanceImagePrompt({ 
        prompt: prompt.value, 
        target: 'prompt', 
        model: authStore.user?.lollms_model_name 
    });
    // Task started notification handled by store
}

function goBack() {
    router.push('/image-studio');
}

function handleKeydown(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    
    if (e.key === ' ' || e.code === 'Space') { tool.value = 'pan'; }
    if (e.key.toLowerCase() === 'b') { tool.value = 'brush'; }
    if (e.key.toLowerCase() === 'e') { tool.value = 'eraser'; }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); undo(); }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); redo(); }
}
</script>

<style scoped>
.pattern-grid {
    background-image: linear-gradient(45deg, #e5e7eb 25%, transparent 25%), 
                      linear-gradient(-45deg, #e5e7eb 25%, transparent 25%), 
                      linear-gradient(45deg, transparent 75%, #e5e7eb 75%), 
                      linear-gradient(-45deg, transparent 75%, #e5e7eb 75%);
    background-size: 20px 20px;
    background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
}
.dark .pattern-grid {
    background-image: linear-gradient(45deg, #1f2937 25%, transparent 25%), 
                      linear-gradient(-45deg, #1f2937 25%, transparent 25%), 
                      linear-gradient(45deg, transparent 75%, #1f2937 75%), 
                      linear-gradient(-45deg, transparent 75%, #1f2937 75%);
}
.custom-scrollbar::-webkit-scrollbar {
    width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
    background-color: rgba(156, 163, 175, 0.5);
    border-radius: 20px;
}
</style>
