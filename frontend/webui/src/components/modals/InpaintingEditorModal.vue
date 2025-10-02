<template>
    <GenericModal modal-name="inpaintingEditor" :title="`Inpainting Editor: ${image?.filename}`" maxWidthClass="max-w-6xl">
        <template #body>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <!-- Controls Column -->
                <div class="md:col-span-1 space-y-4">
                    <h3 class="font-semibold">Controls</h3>
                    <div class="p-4 bg-gray-100 dark:bg-gray-700/50 rounded-lg space-y-4">
                        <div>
                            <label class="block text-sm font-medium">Brush Size: {{ brushSize }}</label>
                            <input type="range" min="5" max="100" v-model.number="brushSize" class="w-full">
                        </div>
                        <div class="flex gap-2">
                            <button @click="setTool('brush')" :class="['btn btn-secondary flex-1', { 'btn-primary': tool === 'brush' }]">Brush</button>
                            <button @click="setTool('eraser')" :class="['btn btn-secondary flex-1', { 'btn-primary': tool === 'eraser' }]">Eraser</button>
                        </div>
                        <div class="flex gap-2">
                            <button @click="undo" class="btn btn-secondary flex-1" :disabled="history.length <= 1">Undo</button>
                            <button @click="clearCanvas" class="btn btn-danger flex-1">Clear</button>
                        </div>
                    </div>
                    <div class="pt-4 border-t dark:border-gray-600">
                        <label for="inpainting-prompt" class="block text-sm font-medium mb-1">Prompt</label>
                        <div class="relative">
                            <textarea id="inpainting-prompt" v-model="prompt" rows="4" class="input-field w-full" placeholder="Describe what to generate..."></textarea>
                            <button @click="handleEnhance('prompt')" class="absolute top-1 right-1 btn-icon" title="Enhance prompt with AI" :disabled="imageStore.isEnhancing">
                                <IconSparkles class="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                     <div>
                        <label for="inpainting-neg-prompt" class="block text-sm font-medium mb-1">Negative Prompt</label>
                        <div class="relative">
                            <textarea id="inpainting-neg-prompt" v-model="negativePrompt" rows="3" class="input-field w-full" placeholder="ugly, blurry, bad anatomy..."></textarea>
                            <button @click="handleEnhance('negative_prompt')" class="absolute top-1 right-1 btn-icon" title="Enhance negative prompt with AI" :disabled="imageStore.isEnhancing">
                                <IconSparkles class="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Canvas Column -->
                <div class="md:col-span-2 relative aspect-auto min-h-[400px]" ref="canvasContainerRef">
                    <AuthenticatedImage ref="imageRef" :src="imageUrl" @load="onImageLoad" class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 max-w-full max-h-full object-contain pointer-events-none" />
                    <canvas ref="canvasRef" class="absolute cursor-crosshair"></canvas>
                    <div class="absolute top-2 right-2 flex flex-col gap-2">
                        <button @click="openImageViewer" class="p-2 bg-black/50 text-white rounded-full hover:bg-black/70 transition-colors" title="View Full Size">
                            <IconMaximize class="w-5 h-5"/>
                        </button>
                    </div>
                </div>
            </div>
        </template>
        <template #footer>
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
import GenericModal from './GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';
import IconMaximize from '../../assets/icons/IconMaximize.vue';

const uiStore = useUiStore();
const imageStore = useImageStore();
const props = computed(() => uiStore.modalData('inpaintingEditor'));
const image = computed(() => props.value?.image);
const imageUrl = computed(() => image.value ? `/api/image-studio/${image.value.id}/file` : null);

const canvasContainerRef = ref(null);
const canvasRef = ref(null);
const imageRef = ref(null);
const ctx = ref(null);
const isDrawing = ref(false);

const brushSize = ref(40);
const tool = ref('brush');
const prompt = ref('');
const negativePrompt = ref('');

const history = ref([]);
const historyIndex = ref(-1);

let resizeObserver = null;

function setTool(newTool) {
    tool.value = newTool;
    if (ctx.value) {
        ctx.value.globalCompositeOperation = newTool === 'eraser' ? 'destination-out' : 'source-over';
    }
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
    if (!canvasRef.value || !imageRef.value?.$el) return;
    const canvas = canvasRef.value;
    const imageEl = imageRef.value.$el.querySelector('img');
    if (!imageEl || !imageEl.complete || imageEl.naturalWidth === 0) return;

    const imgRect = imageEl.getBoundingClientRect();
    const containerRect = canvasContainerRef.value.getBoundingClientRect();
    
    canvas.style.top = `${imgRect.top - containerRect.top}px`;
    canvas.style.left = `${imgRect.left - containerRect.left}px`;
    canvas.style.width = `${imgRect.width}px`;
    canvas.style.height = `${imgRect.height}px`;

    canvas.width = imageEl.naturalWidth;
    canvas.height = imageEl.naturalHeight;

    ctx.value = canvas.getContext('2d');
    ctx.value.lineCap = 'round';
    ctx.value.lineJoin = 'round';
    ctx.value.fillStyle = 'rgba(0, 0, 0, 0.7)';

    canvas.removeEventListener('mousedown', startDrawing);
    canvas.addEventListener('mousedown', startDrawing);
    window.removeEventListener('mousemove', draw);
    window.addEventListener('mousemove', draw);
    window.removeEventListener('mouseup', stopDrawing);
    window.addEventListener('mouseup', stopDrawing);
    
    saveState();
}


function getEventCoordinates(event) {
    const canvas = canvasRef.value;
    const rect = canvas.getBoundingClientRect();
    const clientX = event.touches ? event.touches[0].clientX : event.clientX;
    const clientY = event.touches ? event.touches[0].clientY : event.clientY;

    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    return {
        x: (clientX - rect.left) * scaleX,
        y: (clientY - rect.top) * scaleY
    };
}

function startDrawing(event) {
    const canvas = canvasRef.value;
    const rect = canvas.getBoundingClientRect();
    const clientX = event.touches ? event.touches[0].clientX : event.clientX;
    const clientY = event.touches ? event.touches[0].clientY : event.clientY;

    if(clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom) {
        return;
    }

    event.preventDefault();
    isDrawing.value = true;
    const { x, y } = getEventCoordinates(event);
    ctx.value.beginPath();
    ctx.value.moveTo(x, y);
    draw(event); // Start drawing immediately
}

function draw(event) {
    if (!isDrawing.value) return;
    event.preventDefault();
    const { x, y } = getEventCoordinates(event);
    ctx.value.lineWidth = brushSize.value;
    ctx.value.strokeStyle = 'rgba(0, 0, 0, 0.7)';

    if (tool.value === 'eraser') {
        ctx.value.globalCompositeOperation = 'destination-out';
    } else {
        ctx.value.globalCompositeOperation = 'source-over';
    }
    
    ctx.value.lineTo(x, y);
    ctx.value.stroke();
    
    ctx.value.beginPath();
    ctx.value.moveTo(x, y);
}

function stopDrawing() {
    if (!isDrawing.value) return;
    isDrawing.value = false;
    ctx.value.closePath();
    saveState();
}

function saveState() {
    if (!ctx.value) return;
    const data = ctx.value.getImageData(0, 0, canvasRef.value.width, canvasRef.value.height);
    history.value.splice(historyIndex.value + 1);
    history.value.push(data);
    historyIndex.value++;
}

function undo() {
    if (historyIndex.value > 0) {
        historyIndex.value--;
        ctx.value.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height);
        ctx.value.putImageData(history.value[historyIndex.value], 0, 0);
    }
}

function clearCanvas() {
    ctx.value.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height);
    saveState();
}

async function handleGenerate() {
    if (!image.value || imageStore.isGenerating) return;

    const maskCanvas = document.createElement('canvas');
    maskCanvas.width = canvasRef.value.width;
    maskCanvas.height = canvasRef.value.height;
    const maskCtx = maskCanvas.getContext('2d');
    
    maskCtx.drawImage(canvasRef.value, 0, 0);
    
    const maskBase64 = maskCanvas.toDataURL('image/png').split(',')[1];
    
    await imageStore.editImage({
        image_ids: [image.value.id],
        prompt: prompt.value,
        negative_prompt: negativePrompt.value,
        model: image.value.model,
        mask: maskBase64
    });

    uiStore.closeModal('inpaintingEditor');
}

async function handleEnhance(type) {
    const result = await imageStore.enhanceImagePrompt({
        prompt: prompt.value,
        negative_prompt: negativePrompt.value
    });
    if (result) {
        if (type === 'prompt' && result.prompt) {
            prompt.value = result.prompt;
        }
        if (type === 'negative_prompt' && result.negative_prompt) {
            negativePrompt.value = result.negative_prompt;
        }
    }
}

function openImageViewer() {
    uiStore.openImageViewer({
        imageList: [{ src: imageUrl.value, prompt: image.value.prompt }],
        startIndex: 0
    });
}

watch(image, (newImage) => {
    if (newImage) {
        prompt.value = newImage.prompt || '';
        negativePrompt.value = '';
    }
});

onMounted(() => {
    // Initial setup is now triggered by onImageLoad
});

onUnmounted(() => {
    if (resizeObserver && canvasContainerRef.value) {
        resizeObserver.unobserve(canvasContainerRef.value);
    }
    window.removeEventListener('mousemove', draw);
    window.removeEventListener('mouseup', stopDrawing);
});
</script>