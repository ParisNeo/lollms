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
                    <h3 class="font-semibold pt-4 border-t dark:border-gray-600">Prompt</h3>
                    <textarea v-model="prompt" rows="5" class="input-field w-full" placeholder="Describe what you want to generate in the masked area..."></textarea>
                </div>

                <!-- Canvas Column -->
                <div class="md:col-span-2 relative aspect-auto" ref="canvasContainerRef">
                    <AuthenticatedImage ref="imageRef" :src="imageUrl" @load="setupCanvas" class="absolute inset-0 w-full h-full object-contain pointer-events-none" />
                    <canvas ref="canvasRef" class="absolute inset-0 w-full h-full cursor-crosshair"></canvas>
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
import { ref, computed, watch, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useImageStore } from '../../stores/images';
import GenericModal from './GenericModal.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import AuthenticatedImage from '../ui/AuthenticatedImage.vue';

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

const brushSize = ref(20);
const tool = ref('brush');
const prompt = ref('');

const history = ref([]);
const historyIndex = ref(-1);

function setTool(newTool) {
    tool.value = newTool;
    if (ctx.value) {
        ctx.value.globalCompositeOperation = newTool === 'eraser' ? 'destination-out' : 'source-over';
    }
}

function setupCanvas() {
    if (!canvasRef.value || !imageRef.value?.$el) return;
    const canvas = canvasRef.value;
    const imageEl = imageRef.value.$el.querySelector('img');
    if (!imageEl || !imageEl.complete) return;

    const container = canvasContainerRef.value;
    const containerRatio = container.clientWidth / container.clientHeight;
    const imageRatio = imageEl.naturalWidth / imageEl.naturalHeight;

    let canvasWidth, canvasHeight;
    if (containerRatio > imageRatio) {
        canvasHeight = container.clientHeight;
        canvasWidth = canvasHeight * imageRatio;
    } else {
        canvasWidth = container.clientWidth;
        canvasHeight = canvasWidth / imageRatio;
    }

    canvas.width = canvasWidth;
    canvas.height = canvasHeight;

    ctx.value = canvas.getContext('2d');
    ctx.value.lineCap = 'round';
    ctx.value.lineJoin = 'round';

    canvas.addEventListener('mousedown', startDrawing);
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', stopDrawing);
    canvas.addEventListener('mouseout', stopDrawing);

    canvas.addEventListener('touchstart', startDrawing);
    canvas.addEventListener('touchmove', draw);
    canvas.addEventListener('touchend', stopDrawing);
    
    saveState();
}

function getEventCoordinates(event) {
    const canvas = canvasRef.value;
    const rect = canvas.getBoundingClientRect();
    if (event.touches) {
        return {
            x: event.touches[0].clientX - rect.left,
            y: event.touches[0].clientY - rect.top
        };
    }
    return {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top
    };
}

function startDrawing(event) {
    event.preventDefault();
    isDrawing.value = true;
    const { x, y } = getEventCoordinates(event);
    ctx.value.beginPath();
    ctx.value.moveTo(x, y);
}

function draw(event) {
    if (!isDrawing.value) return;
    event.preventDefault();
    const { x, y } = getEventCoordinates(event);
    ctx.value.lineWidth = brushSize.value;
    ctx.value.strokeStyle = 'black';
    ctx.value.lineTo(x, y);
    ctx.value.stroke();
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
    const imageEl = imageRef.value.$el.querySelector('img');
    maskCanvas.width = imageEl.naturalWidth;
    maskCanvas.height = imageEl.naturalHeight;
    const maskCtx = maskCanvas.getContext('2d');
    
    maskCtx.drawImage(canvasRef.value, 0, 0, maskCanvas.width, maskCanvas.height);
    
    const maskBase64 = maskCanvas.toDataURL('image/png').split(',')[1];
    
    await imageStore.editImage({
        image_ids: [image.value.id],
        prompt: prompt.value,
        model: image.value.model,
        mask: maskBase64
    });

    uiStore.closeModal('inpaintingEditor');
}

watch(image, () => {
    if(image.value) {
        prompt.value = image.value?.prompt || '';
    }
});
</script>