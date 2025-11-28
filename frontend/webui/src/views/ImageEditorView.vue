<template>
    <Teleport to="#global-header-actions-target">
        <div class="flex items-center gap-2">
            <button @click="handleSaveAs" class="btn btn-secondary" :disabled="isActionInProgress">
                <IconSave class="w-5 h-5 mr-2" /> Save As New Image
            </button>
            <button @click="handleGenerate" class="btn btn-primary" :disabled="isActionInProgress || !prompt.trim()">
                <IconAnimateSpin v-if="isGenerating" class="w-5 h-5 mr-2 animate-spin" />
                Apply Prompt
            </button>
        </div>
    </Teleport>
    <div 
        class="h-full flex flex-col bg-gray-50 dark:bg-gray-900 relative"
        @paste="handlePaste"
    >
        <div class="flex-grow min-h-0 flex">
            <!-- Left Toolbar -->
            <div class="w-16 flex-shrink-0 bg-white dark:bg-gray-800 border-r dark:border-gray-700 flex flex-col items-center py-4 space-y-2">
                <button v-for="t in tools" :key="t.id" @click="activeTool = t.id" class="btn-icon p-2.5 rounded-lg" :class="{'bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400': activeTool === t.id}" :title="t.name">
                    <component :is="t.icon" class="w-6 h-6" />
                </button>
            </div>

            <!-- Controls Column (Sidebar) -->
            <div class="w-80 flex-shrink-0 bg-white dark:bg-gray-800 border-r dark:border-gray-700 flex flex-col">
                <div class="flex-grow p-4 space-y-6 overflow-y-auto custom-scrollbar">
                    
                    <button @click="openSettingsModal" class="btn btn-secondary w-full"><IconCog class="w-5 h-5 mr-2" /> Generation Settings</button>

                    <div>
                        <h3 class="font-semibold text-lg border-b dark:border-gray-600 pb-2 mb-4">Tool Properties</h3>
                        <div v-if="['brush', 'eraser'].includes(activeTool)" class="space-y-4">
                            <div><label class="block text-sm font-medium">Brush Size: {{ toolProps.brushSize }}</label><input type="range" min="1" max="200" v-model.number="toolProps.brushSize" class="w-full"></div>
                            <div v-if="activeTool === 'brush'"><label class="block text-sm font-medium">Opacity: {{ Math.round(toolProps.opacity * 100) }}%</label><input type="range" min="0.01" max="1" step="0.01" v-model.number="toolProps.opacity" class="w-full"></div>
                        </div>
                        <div v-if="['rect', 'circle'].includes(activeTool)" class="space-y-4">
                            <div><label class="block text-sm font-medium">Stroke Width: {{ toolProps.strokeWidth }}</label><input type="range" min="0" max="100" v-model.number="toolProps.strokeWidth" class="w-full"></div>
                        </div>
                        <div v-if="['brush', 'rect', 'circle'].includes(activeTool)" class="space-y-4 mt-4">
                            <div><label class="block text-sm font-medium">Color</label><div class="flex items-center gap-2 mt-1"><input type="color" v-model="toolProps.color" class="w-10 h-10 p-1 bg-white dark:bg-gray-800 border dark:border-gray-600 rounded cursor-pointer"><div class="grid grid-cols-6 gap-1 flex-1"><button v-for="color in colorPalette" :key="color" @click="toolProps.color = color" class="w-6 h-6 rounded-full border-2" :style="{ backgroundColor: color, borderColor: toolProps.color.toLowerCase() === color.toLowerCase() ? 'blue' : 'transparent' }"></button></div></div></div>
                        </div>
                        <div v-if="['select', 'pan', 'zoom'].includes(activeTool)" class="text-sm text-gray-500">
                           <p v-if="activeTool === 'select'">Click on an object to select, resize, and rotate it.</p>
                           <p v-if="activeTool === 'pan'">Click and drag the canvas to move your view.</p>
                           <p v-if="activeTool === 'zoom'">Use your mouse wheel to zoom in and out.</p>
                        </div>
                    </div>
                </div>

                <div class="p-4 border-t dark:border-gray-700 flex-shrink-0 h-1/3 flex flex-col">
                    <div class="flex justify-between items-center mb-2">
                         <h3 class="font-semibold text-lg">Layers</h3>
                        <button @click="deleteSelectedLayer" class="btn-icon p-1.5" title="Delete Selected Layer" :disabled="!selectedNodeId"><IconTrash class="w-5 h-5" /></button>
                    </div>
                    <div class="flex-grow overflow-y-auto custom-scrollbar bg-gray-100 dark:bg-gray-900/50 rounded-md p-1">
                        <div v-for="layer in layers" :key="layer.id" @click="selectNode(layer.konvaNode)" class="p-2 rounded-md cursor-pointer flex items-center gap-2 text-sm" :class="{'bg-blue-100 dark:bg-blue-900/50': selectedNodeId === layer.id}">
                            <IconEye v-if="layer.visible" @click.stop="toggleLayerVisibility(layer.id)" class="w-4 h-4 text-gray-600 dark:text-gray-300 hover:text-black dark:hover:text-white" />
                            <IconEyeOff v-else @click.stop="toggleLayerVisibility(layer.id)" class="w-4 h-4 text-gray-400 dark:text-gray-500 hover:text-black dark:hover:text-white" />
                            <span class="flex-grow truncate">{{ layer.name }}</span>
                        </div>
                    </div>
                </div>
                <div class="p-4 border-t dark:border-gray-700 flex-shrink-0">
                    <router-link to="/image-studio" class="w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors">
                        <IconArrowLeft class="w-5 h-5" />
                        <span>Back to Studio</span>
                    </router-link>
                </div>
            </div>
            
            <div class="flex-grow min-h-0 flex items-center justify-center p-4 relative" ref="stageContainerRef" :style="stageBackgroundStyle">
                <div id="image-editor-stage" class="absolute shadow-lg"></div>
                <FloatingPromptPanel v-model:prompt="prompt" v-model:negativePrompt="negativePrompt" @enhance="openEnhanceModal"/>
                <div v-if="isGenerating" class="absolute inset-0 bg-black/50 backdrop-blur-sm z-30 flex flex-col items-center justify-center text-white"><IconAnimateSpin class="w-12 h-12 animate-spin mb-4" /><p class="text-lg font-semibold">Applying prompt...</p></div>
                <div v-if="['brush', 'eraser'].includes(activeTool)" ref="customCursorRef" class="custom-cursor" :style="customCursorStyle"></div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick, markRaw, reactive } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useUiStore } from '../stores/ui';
import { useImageStore } from '../stores/images';
import { useDataStore } from '../stores/data';
import { useAuthStore } from '../stores/auth';
import apiClient from '../services/api';
import useEventBus from '../services/eventBus';
import Konva from 'konva';
import FloatingPromptPanel from '../components/image_editor/FloatingPromptPanel.vue';

// Icons
import IconSave from '../assets/icons/IconSave.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconEye from '../assets/icons/IconEye.vue';
import IconEyeOff from '../assets/icons/IconEyeOff.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';
import IconHand from '../assets/icons/IconHand.vue';
import IconCursorArrow from '../assets/icons/IconCursorArrow.vue';
import IconCircle from '../assets/icons/IconCircle.vue';
import IconRectangle from '../assets/icons/IconRectangle.vue';
import IconMinusCircle from '../assets/icons/ui/IconMinusCircle.vue';
import IconMaximize from '../assets/icons/IconMaximize.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconCog from '../assets/icons/IconCog.vue';

const uiStore = useUiStore();
const imageStore = useImageStore();
const dataStore = useDataStore();
const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();
const { on, off } = useEventBus();

const { user } = storeToRefs(authStore);
const props = defineProps({ id: String });

const originalImage = ref(null);
const prompt = ref('');
const negativePrompt = ref('');
const isGenerating = ref(false);
const isSaving = ref(false);
const isActionInProgress = computed(() => isGenerating.value || isSaving.value);
const activeGenerationTaskId = ref(null);

const generationSettings = reactive({
    selectedModel: '',
    imageSize: '1024x1024',
    seed: -1,
    params: { strength: 0.75 }
});

const stageContainerRef = ref(null);
const customCursorRef = ref(null);
let stage = null; let baseLayer = null; let drawLayer = null; let imageLayer = null; let transformer = null;
const layers = ref([]);
const selectedNodeId = ref(null);
const activeTool = ref('brush');
const toolProps = ref({ brushSize: 20, opacity: 1.0, color: '#000000', strokeWidth: 5 });
const colorPalette = ['#FFFFFF', '#000000', '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF'];
let isDrawing = false; let lastLine;

const history = ref([]);
const historyIndex = ref(-1);

const tools = [
    { id: 'select', name: 'Select & Move', icon: markRaw(IconCursorArrow) }, { id: 'pan', name: 'Pan View', icon: markRaw(IconHand) },
    { id: 'zoom', name: 'Zoom Tool', icon: markRaw(IconMaximize) }, { id: 'brush', name: 'Brush', icon: markRaw(IconPencil) },
    { id: 'eraser', name: 'Eraser', icon: markRaw(IconMinusCircle) }, { id: 'rect', name: 'Rectangle', icon: markRaw(IconRectangle) },
    { id: 'circle', name: 'Circle', icon: markRaw(IconCircle) },
];

const stageBackgroundStyle = computed(() => ({ backgroundImage: `linear-gradient(45deg, #ccc 25%, transparent 25%), linear-gradient(-45deg, #ccc 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #ccc 75%), linear-gradient(-45deg, transparent 75%, #ccc 75%)`, backgroundSize: '20px 20px', backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px' }));
const customCursorStyle = computed(() => ({ width: `${toolProps.value.brushSize}px`, height: `${toolProps.value.brushSize}px` }));

onMounted(async () => {
    uiStore.setPageTitle({ title: 'Image Editor', icon: markRaw(IconPencil) });
    dataStore.fetchAvailableTtiModels();

    if (props.id && props.id !== 'new') {
        let foundImage = imageStore.images.find(img => img.id === props.id);
        if (!foundImage) { await imageStore.fetchImages(); foundImage = imageStore.images.find(img => img.id === props.id); }
        if (!foundImage) { uiStore.addNotification('Image not found.', 'error'); router.push('/image-studio'); return; }
        
        originalImage.value = { ...foundImage };
        prompt.value = foundImage.prompt || '';
        negativePrompt.value = foundImage.negative_prompt || '';
        
        generationSettings.selectedModel = foundImage.model || user.value?.iti_binding_model_name || user.value?.tti_binding_model_name || '';
        if (foundImage.width && foundImage.height) generationSettings.imageSize = `${foundImage.width}x${foundImage.height}`;
        generationSettings.seed = foundImage.seed ?? -1;
        generationSettings.params = { ...(foundImage.generation_params || { strength: 0.75 }) };
        if(!generationSettings.params.strength) generationSettings.params.strength = 0.75;

    } else {
        prompt.value = imageStore.prompt;
        negativePrompt.value = imageStore.negativePrompt;
        generationSettings.selectedModel = user.value?.iti_binding_model_name || user.value?.tti_binding_model_name || imageStore.selectedModel || '';
        generationSettings.imageSize = imageStore.imageSize;
        generationSettings.seed = imageStore.seed;
        generationSettings.params = { ...imageStore.generationParams };
    }

    await initEditor();
    window.addEventListener('resize', fitStageIntoParent);
    window.addEventListener('keydown', handleKeyDown);
    on('task:completed', handleTaskCompletion);
    on('prompt:enhanced', handlePromptEnhanced);
});
onUnmounted(() => { uiStore.setPageTitle({ title: '' }); window.removeEventListener('resize', fitStageIntoParent); window.removeEventListener('keydown', handleKeyDown); off('task:completed', handleTaskCompletion); off('prompt:enhanced', handlePromptEnhanced); stage?.destroy(); });

function handlePromptEnhanced(result) {
    if (result) {
        if (result.prompt) prompt.value = result.prompt;
        if (result.negative_prompt) negativePrompt.value = result.negative_prompt;
    }
}

async function initEditor() {
    await nextTick(); if (!stageContainerRef.value) return;
    stage = new Konva.Stage({ container: 'image-editor-stage', width: 1024, height: 1024 });
    baseLayer = new Konva.Layer({ id: 'base' }); drawLayer = new Konva.Layer({ id: 'draw' }); imageLayer = new Konva.Layer({ id: 'images' });
    stage.add(baseLayer, drawLayer, imageLayer);
    layers.value = [ { id: 'images', name: 'Objects', visible: true, layer: imageLayer }, { id: 'draw', name: 'Drawing', visible: true, layer: drawLayer }, { id: 'base', name: 'Background', visible: true, layer: baseLayer, konvaNode: null } ];
    transformer = new Konva.Transformer({ keepRatio: true, centeredScaling: true }); imageLayer.add(transformer);
    await loadImageAndSetup(); fitStageIntoParent(); setupStageEvents();
}
async function loadImageAndSetup(imageUrl, newImageEntry = null) {
    let canvasWidth = 1024, canvasHeight = 1024;
    const urlToLoad = imageUrl || (originalImage.value ? `/api/image-studio/${originalImage.value.id}/file` : null);

    if (newImageEntry) {
        canvasWidth = newImageEntry.width || 1024; canvasHeight = newImageEntry.height || 1024;
    } else if (originalImage.value) {
        canvasWidth = originalImage.value.width || 1024; canvasHeight = originalImage.value.height || 1024;
    }
    
    stage.width(canvasWidth); stage.height(canvasHeight);
    baseLayer.destroyChildren();

    if (urlToLoad) {
        try {
            const response = await apiClient.get(urlToLoad, { responseType: 'blob' });
            const localUrl = URL.createObjectURL(response.data);
            const image = new Image(); image.src = localUrl;
            image.onload = () => {
                const imgNode = new Konva.Image({ image, id: 'baseImage', name: 'Base Image', x: 0, y: 0, width: canvasWidth, height: canvasHeight });
                baseLayer.add(imgNode);
                const baseLayerInfo = layers.value.find(l=>l.id==='base');
                if(baseLayerInfo) baseLayerInfo.konvaNode = imgNode;
                fitStageIntoParent();
                URL.revokeObjectURL(localUrl); // Clean up object URL
            };
        } catch (error) { uiStore.addNotification('Failed to load base image.', 'error'); }
    } else {
        const bgRect = new Konva.Rect({ x: 0, y: 0, width: canvasWidth, height: canvasHeight, fill: '#FFFFFF', name: 'background-color' });
        baseLayer.add(bgRect);
    }
    if (history.value[historyIndex.value] !== urlToLoad) { history.value.splice(historyIndex.value + 1); history.value.push(urlToLoad); historyIndex.value++; }
}
function fitStageIntoParent() {
    if (!stage || !stageContainerRef.value) return;
    const { offsetWidth: cw, offsetHeight: ch } = stageContainerRef.value;
    if (cw === 0 || ch === 0) return;
    const { width: sw, height: sh } = stage;
    const scale = Math.min(cw / sw, ch / sh) * 0.95;
    if (!isFinite(scale) || scale <= 0) return;
    stage.scale({ x: scale, y: scale });
    stage.position({ x: (cw - sw * scale) / 2, y: (ch - sh * scale) / 2 });
}
function getActiveLayer() { if (['rect', 'circle'].includes(activeTool.value)) return imageLayer; if (['brush', 'eraser'].includes(activeTool.value)) return drawLayer; return imageLayer; }
function setupStageEvents() {
    stage.on('mousedown touchstart', (e) => {
        if (activeTool.value === 'pan') { stage.container().style.cursor = 'grabbing'; return; }
        if (activeTool.value === 'select') { const n = e.target; if (n === stage || n.getLayer().id() === 'base' || n.getLayer().id() === 'draw') { transformer.nodes([]); selectedNodeId.value = null; return; } if (n.getParent() instanceof Konva.Transformer) return; transformer.nodes([n]); selectedNodeId.value = n.id(); return; }
        isDrawing = true;
        const pos = stage.getRelativePointerPosition(); if (!pos || isNaN(pos.x) || isNaN(pos.y)) return;
        const layer = getActiveLayer();
        if (['brush', 'eraser'].includes(activeTool.value)) { const color = activeTool.value === 'brush' ? hexToRgba(toolProps.value.color, toolProps.value.opacity) : 'rgba(0,0,0,1)'; lastLine = new Konva.Line({ stroke: color, strokeWidth: toolProps.value.brushSize, globalCompositeOperation: activeTool.value === 'eraser' ? 'destination-out' : 'source-over', lineCap: 'round', lineJoin: 'round', points: [pos.x, pos.y, pos.x, pos.y] }); layer.add(lastLine);
        } else if (['rect', 'circle'].includes(activeTool.value)) { const conf = { x: pos.x, y: pos.y, width: 0, height: 0, fill: toolProps.value.color, stroke: toolProps.value.color, strokeWidth: toolProps.value.strokeWidth, draggable: false, name: 'shape' }; lastLine = activeTool.value === 'rect' ? new Konva.Rect(conf) : new Konva.Circle({ ...conf, radius: 0 }); layer.add(lastLine); }
    });
    stage.on('mousemove touchmove', (e) => { if (!isDrawing || !lastLine) return; const pos = stage.getRelativePointerPosition(); if (!pos) return; if (['brush', 'eraser'].includes(activeTool.value)) { lastLine.points(lastLine.points().concat([pos.x, pos.y])); } else if (['rect', 'circle'].includes(activeTool.value)) { const w = pos.x - lastLine.x(), h = pos.y - lastLine.y(); if(activeTool.value === 'rect') { lastLine.width(w); lastLine.height(h); } else { lastLine.radius(Math.sqrt(w**2 + h**2)); } } });
    stage.on('mouseup touchend', () => {
        if (activeTool.value === 'pan') stage.container().style.cursor = 'grab';
        if (isDrawing) { isDrawing = false; if (lastLine && ['rect', 'circle'].includes(activeTool.value)) { lastLine.draggable(true); const id = `s_${Konva.Util.getRandomColor()}`; lastLine.id(id); layers.value.unshift({ id, name: `${activeTool.value} ${imageLayer.getChildren(n=>n.hasName('shape')).length}`, visible: true, konvaNode: lastLine }); selectNode(lastLine); } lastLine = null; }
    });
    stage.on('wheel', (e) => { e.evt.preventDefault(); const scaleBy = 1.05; const oldScale = stage.scaleX(); const pointer = stage.getPointerPosition(); if (!pointer) return; const mousePointTo = { x: (pointer.x - stage.x()) / oldScale, y: (pointer.y - stage.y()) / oldScale }; const newScale = e.evt.deltaY > 0 ? oldScale / scaleBy : oldScale * scaleBy; stage.scale({ x: newScale, y: newScale }); const newPos = { x: pointer.x - mousePointTo.x * newScale, y: pointer.y - mousePointTo.y * newScale }; stage.position(newPos); });
    stage.on('mouseenter', () => { if (customCursorRef.value) customCursorRef.value.style.display = 'block'; });
    stage.on('mouseleave', () => { if (customCursorRef.value) customCursorRef.value.style.display = 'none'; });
    stage.on('mousemove', (e) => {
        if (customCursorRef.value) {
            // The cursor has position:fixed, so it's relative to the viewport.
            // e.evt contains the original DOM event. clientX/Y are viewport-relative coordinates.
            customCursorRef.value.style.left = `${e.evt.clientX}px`;
            customCursorRef.value.style.top = `${e.evt.clientY}px`;
        }
    });
}
function hexToRgba(hex, alpha) { const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16); return `rgba(${r}, ${g}, ${b}, ${alpha})`; }
function selectNode(node) { if (!node) { transformer.nodes([]); selectedNodeId.value = null; return; } transformer.nodes([node]); selectedNodeId.value = node.id(); }
function toggleLayerVisibility(id) { const l = layers.value.find(l => l.id === id); if(l && (l.konvaNode || l.layer)) { const node = l.konvaNode || l.layer; const isVisible = !node.visible(); node.visible(isVisible); l.visible = isVisible; } }
function deleteSelectedLayer() { if (selectedNodeId.value) { const node = stage.findOne(`#${selectedNodeId.value}`); if (node && node.getParent() !== baseLayer) { node.destroy(); transformer.nodes([]); selectedNodeId.value = null; layers.value = layers.value.filter(l => l.id !== selectedNodeId.value); } } }
async function handlePaste(event) {
    const items = event.clipboardData.items;
    for (const item of items) {
        if (item.type.includes('image')) {
            const file = item.getAsFile();
            const reader = new FileReader();
            reader.onload = (e) => Konva.Image.fromURL(e.target.result, (imgNode) => {
                const id = `img_${Konva.Util.getRandomColor()}`;
                imgNode.setAttrs({ id, x: 20, y: 20, draggable: true, name: 'image_paste' });
                imageLayer.add(imgNode);
                layers.value.unshift({ id, name: `Pasted ${imageLayer.getChildren(n=>n.hasName('image_paste')).length}`, visible: true, konvaNode: imgNode });
                selectNode(imgNode);
            });
            reader.readAsDataURL(file); event.preventDefault(); break; 
        }
    }
}
async function handleSaveAs() {
    isSaving.value = true;
    try {
        transformer?.nodes([]);
        const payload = { drawing_b64: stage.toDataURL({ pixelRatio: 1 }).split(',')[1], prompt: prompt.value, model: generationSettings.selectedModel, width: stage.width(), height: stage.height() };
        const newImage = await imageStore.saveCanvasAsNewImage(payload);
        if(newImage) router.replace(`/image-studio`);
    } finally { isSaving.value = false; }
}
async function handleGenerate() {
    isGenerating.value = true;
    try {
        transformer?.nodes([]);
        const [w, h] = generationSettings.imageSize.split('x').map(Number);
        const payload = { base_image_b64: stage.toDataURL({ pixelRatio: 1 }).split(',')[1], prompt: prompt.value, negative_prompt: negativePrompt.value, model: generationSettings.selectedModel, width: w, height: h, seed: generationSettings.seed, ...generationSettings.params };
        const task = await imageStore.editImage(payload);
        if(task) activeGenerationTaskId.value = task.id;
    } catch (e) { isGenerating.value = false; }
}
function handleTaskCompletion(task) {
    if (task && task.id === activeGenerationTaskId.value && task.status === 'completed' && task.result) {
        const newImage = task.result;
        originalImage.value = newImage;
        const newImageUrl = `/api/image-studio/${newImage.id}/file`;
        loadImageAndSetup(newImageUrl, newImage);
        isGenerating.value = false;
        activeGenerationTaskId.value = null;
    } else if (task && task.id === activeGenerationTaskId.value) {
        isGenerating.value = false; activeGenerationTaskId.value = null;
    }
}
function handleKeyDown(event) { if (event.ctrlKey && event.key.toLowerCase() === 'z') { event.preventDefault(); undo(); } }
function undo() { if (historyIndex.value > 0) { historyIndex.value--; loadImageAndSetup(history.value[historyIndex.value]); } }
function openEnhanceModal(target) { uiStore.openModal('enhancePrompt', { onConfirm: async ({ instructions, mode }) => { const payload = { prompt: prompt.value, negative_prompt: negativePrompt.value, target: target, instructions, mode }; imageStore.enhanceImagePrompt(payload); } }); }
function openSettingsModal() { uiStore.openModal('imageEditorSettings', { settings: generationSettings }); }
watch(activeTool, (newTool) => { if (!stage) return; const c = stage.container(); stage.draggable(newTool === 'pan'); const cursors = { brush: 'none', eraser: 'none', rect: 'crosshair', circle: 'crosshair', pan: 'grab', zoom: 'zoom-in', select: 'default' }; c.style.cursor = cursors[newTool] || 'default'; [...imageLayer.getChildren(), ...drawLayer.getChildren()].forEach(node => { if (node instanceof Konva.Stage || node instanceof Konva.Transformer) return; node.draggable(newTool === 'select' && (node.hasName('shape') || node.hasName('image_paste'))); }); if (newTool !== 'select') transformer?.nodes([]); });
</script>

<style scoped>
.custom-cursor {
    position: fixed;
    border-radius: 50%;
    border: 1px solid rgba(0, 0, 0, 0.5);
    background-color: rgba(255, 255, 255, 0.2);
    pointer-events: none;
    transform: translate(-50%, -50%);
    display: none;
    z-index: 1000;
}
</style>
