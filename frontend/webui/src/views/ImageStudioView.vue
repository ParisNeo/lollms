<!-- [UPDATE] lollms/frontend/webui/src/views/ImageStudioView.vue -->
<script setup>
import { ref, onMounted, onUnmounted, computed, watch, markRaw } from 'vue';
import { useRouter } from 'vue-router';
import { useImageStore } from '../stores/images';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import { useDiscussionsStore } from '../stores/discussions';
import { useTasksStore } from '../stores/tasks';
import { storeToRefs } from 'pinia';
import AuthenticatedImage from '../components/ui/AuthenticatedImage.vue';
import TaskProgressIndicator from '../components/ui/TaskProgressIndicator.vue';

// Icons
import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconSend from '../assets/icons/IconSend.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconMaximize from '../assets/icons/IconMaximize.vue';
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue'; // For reuse prompt
import IconAdjustmentsHorizontal from '../assets/icons/IconAdjustmentsHorizontal.vue';

const imageStore = useImageStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const tasksStore = useTasksStore();
const router = useRouter();

const { images, isLoading, isGenerating, isEnhancing } = storeToRefs(imageStore);
const { user } = storeToRefs(authStore);
const { imageGenerationTasks, imageGenerationTasksCount } = storeToRefs(tasksStore);

const prompt = ref('');
const negativePrompt = ref('');
const imageSize = ref('1024x1024');
const nImages = ref(1);
const seed = ref(-1);
const generationParams = ref({});
const isConfigVisible = ref(false);

const selectedImages = ref([]);
const isSelectionMode = computed(() => selectedImages.value.length > 0);
const areAllSelected = computed({
    get: () => images.value.length > 0 && selectedImages.value.length === images.value.length,
    set: (value) => {
        selectedImages.value = value ? images.value.map(img => img.id) : [];
    }
});
const isDraggingOver = ref(false);

const selectedModel = computed(() => user.value?.tti_binding_model_name);

const selectedModelDetails = computed(() => {
    if (!selectedModel.value || dataStore.availableTtiModels.length === 0) return null;
    return dataStore.availableTtiModels.find(m => m.id === selectedModel.value);
});

const modelConfigurableParameters = computed(() => {
    if (!selectedModelDetails.value?.binding_params) return [];
    
    const params = isSelectionMode.value
        ? (selectedModelDetails.value.binding_params.edit_parameters || [])
        : (selectedModelDetails.value.binding_params.generation_parameters || []);
        
    const excluded = ['prompt', 'negative_prompt', 'image', 'mask', 'width', 'height', 'n', 'seed', 'size'];
    return params.filter(p => !excluded.includes(p.name));
});

function parseOptions(options) {
    if (typeof options === 'string') {
        return options.split(',').map(o => o.trim()).filter(o => o);
    }
    if (Array.isArray(options)) {
        return options.filter(o => o);
    }
    return [];
}

watch(selectedModelDetails, (details) => {
    generationParams.value = {};
    if (details) {
        modelConfigurableParameters.value.forEach(param => {
            generationParams.value[param.name] = param.default;
        });
    }
}, { immediate: true, deep: true });

onMounted(() => {
    uiStore.setPageTitle({ title: 'Image Studio', icon: markRaw(IconPhoto) });
    imageStore.fetchImages();
    if (dataStore.availableTtiModels.length === 0) dataStore.fetchAvailableTtiModels();
    if (Object.keys(discussionsStore.discussions).length === 0) discussionsStore.loadDiscussions();
    window.addEventListener('paste', handlePaste);
});

onUnmounted(() => {
    uiStore.setPageTitle({ title: '' });
    window.removeEventListener('paste', handlePaste);
});

function isSelected(imageId) { return selectedImages.value.includes(imageId); }
function toggleSelection(imageId) {
    const index = selectedImages.value.indexOf(imageId);
    if (index > -1) selectedImages.value.splice(index, 1);
    else selectedImages.value.push(imageId);
}

async function handleGenerateOrApply() {
    if (!prompt.value.trim() || !selectedModel.value) {
        uiStore.addNotification('A prompt and model are required.', 'warning');
        return;
    }

    const commonPayload = {
        prompt: prompt.value,
        negative_prompt: negativePrompt.value,
        model: selectedModel.value,
        size: imageSize.value,
        seed: seed.value,
        ...generationParams.value
    };

    if (isSelectionMode.value) {
        await imageStore.editImage({ ...commonPayload, image_ids: selectedImages.value });
    } else {
        await imageStore.generateImage({ ...commonPayload, n: nImages.value });
    }
}

async function handleEnhance(type) {
    if (type !== 'negative_prompt' && !prompt.value.trim()) {
        uiStore.addNotification('Please enter a prompt to enhance.', 'warning');
        return;
    }
    const result = await imageStore.enhanceImagePrompt({ prompt: prompt.value, negative_prompt: negativePrompt.value, target: type });
    if (result) {
        if (result.prompt) prompt.value = result.prompt;
        if (result.negative_prompt) negativePrompt.value = result.negative_prompt;
    }
}

function reusePrompt(image) {
    prompt.value = image.prompt;
    negativePrompt.value = image.negative_prompt;
    seed.value = image.seed;
    uiStore.addNotification('Prompt and parameters have been reused.', 'success');
}

function openInpaintingEditor(image) { uiStore.openModal('inpaintingEditor', { image }); }
function openImageViewer(image, index) {
    uiStore.openImageViewer({
        imageList: images.value.map(img => ({ src: `/api/image-studio/${img.id}/file`, prompt: img.prompt, model: img.model, filename: img.filename })),
        startIndex: index
    });
}
function handleUpload(event) {
    const files = Array.from(event.target.files);
    if (files.length > 0) imageStore.uploadImages(files);
}
async function handleDeleteSelected() {
    const confirmed = await uiStore.showConfirmation({ title: `Delete ${selectedImages.value.length} Images?`, message: 'This action cannot be undone.', confirmText: 'Delete' });
    if (confirmed.confirmed) {
        await Promise.all(selectedImages.value.map(id => imageStore.deleteImage(id)));
        selectedImages.value = [];
    }
}
async function handleMoveToDiscussion() {
    if (!isSelectionMode.value) return;
    const { confirmed, value: discussionId } = await uiStore.showConfirmation({
        title: `Move ${selectedImages.value.length} Images to Discussion`,
        message: 'Select a discussion:', confirmText: 'Move', inputType: 'select',
        inputOptions: discussionsStore.sortedDiscussions.map(d => ({ text: d.title, value: d.id })),
        inputValue: discussionsStore.currentDiscussionId
    });
    if (confirmed && discussionId) {
        await Promise.all(selectedImages.value.map(id => imageStore.moveImageToDiscussion(id, discussionId)));
        selectedImages.value = [];
    }
}
function goBack() { router.push('/'); }

function handleDragOver(event) {
    event.preventDefault();
    isDraggingOver.value = true;
}

function handleDragLeave(event) {
    if (!event.currentTarget.contains(event.relatedTarget)) {
        isDraggingOver.value = false;
    }
}

async function handleDrop(event) {
    event.preventDefault();
    isDraggingOver.value = false;
    const files = Array.from(event.dataTransfer.files).filter(file => file.type.startsWith('image/'));
    if (files.length > 0) {
        await imageStore.uploadImages(files);
    }
}

async function handlePaste(event) {
    const items = (event.clipboardData || window.clipboardData).items;
    if (!items) return;
    
    const imageFiles = [];
    for (const item of items) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
            const file = item.getAsFile();
            if (file) {
                const extension = (file.type.split('/')[1] || 'png').toLowerCase().replace('jpeg', 'jpg');
                imageFiles.push(new File([file], `pasted_image_${Date.now()}_${Math.random().toString(36).substr(2, 9)}.${extension}`, { type: file.type }));
            }
        }
    }
    
    if (imageFiles.length > 0) { 
        event.preventDefault();
        await imageStore.uploadImages(imageFiles); 
    }
}
</script>

<template>
    <div 
        class="h-full flex flex-col bg-gray-50 dark:bg-gray-900 relative" 
        @dragover.prevent="handleDragOver"
        @dragleave.prevent="handleDragLeave"
        @drop.prevent="handleDrop"
    >
        <div v-if="isDraggingOver" class="absolute inset-0 bg-blue-500/20 border-4 border-dashed border-blue-500 rounded-lg z-20 flex items-center justify-center m-4 pointer-events-none">
            <p class="text-2xl font-bold text-blue-600">Drop images anywhere to upload</p>
        </div>
        <div class="flex-shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-2 flex items-center">
            <button @click="goBack" class="btn btn-secondary btn-icon" title="Back to Main App">
                <IconArrowLeft class="w-5 h-5" />
            </button>
        </div>

        <div class="flex-grow overflow-y-auto p-4 sm:p-6 flex flex-col">
            <div 
                class="flex-grow min-h-0 bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md flex flex-col"
            >
                <div class="flex justify-between items-center mb-4 flex-shrink-0 flex-wrap gap-2">
                    <div class="flex items-center gap-2">
                        <input type="checkbox" v-model="areAllSelected" class="h-4 w-4 rounded" title="Select All" />
                        <h3 class="text-lg font-semibold">Your Images ({{ images.length }})</h3>
                    </div>
                    <div v-if="isSelectionMode" class="flex items-center gap-2">
                        <span class="text-sm text-gray-500">{{ selectedImages.length }} selected</span>
                        <button @click="handleMoveToDiscussion" class="btn btn-secondary btn-sm" title="Move to Discussion"><IconSend class="w-4 h-4" /></button>
                        <button @click="handleDeleteSelected" class="btn btn-danger btn-sm" title="Delete Selected"><IconTrash class="w-4 h-4" /></button>
                    </div>
                    <label for="upload-image-btn" class="btn btn-secondary btn-sm cursor-pointer">
                        <IconArrowDownTray class="w-4 h-4 mr-2" /> Upload
                        <input id="upload-image-btn" type="file" @change="handleUpload" class="hidden" accept="image/*" multiple>
                    </label>
                </div>

                <!-- NEW: Active Tasks Section -->
                <div v-if="imageGenerationTasksCount > 0" class="flex-shrink-0 mb-4">
                    <h4 class="text-md font-semibold mb-2 text-gray-700 dark:text-gray-300">Generations in Progress ({{ imageGenerationTasksCount }})</h4>
                    <div class="space-y-2 max-h-40 overflow-y-auto custom-scrollbar p-2 bg-gray-100 dark:bg-gray-700/50 rounded-lg">
                        <div v-for="task in imageGenerationTasks" :key="task.id" class="bg-white dark:bg-gray-800 p-2 rounded-md shadow-sm">
                            <TaskProgressIndicator 
                                :task="task" 
                                show-name 
                                @cancel="tasksStore.cancelTask(task.id)" 
                                @view="uiStore.openModal('tasksManager', { initialTaskId: task.id })"
                            />
                        </div>
                    </div>
                </div>

                <div v-if="isLoading" class="flex-grow flex items-center justify-center"><IconAnimateSpin class="w-8 h-8 text-gray-500" /></div>
                <div v-else-if="images.length === 0" class="flex-grow flex items-center justify-center text-center text-gray-500">
                    <div><p>No images yet.</p><p class="text-sm">Drop, paste, or use the form below to generate some!</p></div>
                </div>
                <div v-else class="flex-grow overflow-y-auto custom-scrollbar -m-2 p-2">
                    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                        <div v-for="(image, index) in images" :key="image.id" @click="toggleSelection(image.id)" 
                             class="relative aspect-square rounded-lg overflow-hidden group cursor-pointer border-4" 
                             :class="isSelected(image.id) ? 'border-red-500' : 'border-transparent'">
                            <AuthenticatedImage :src="`/api/image-studio/${image.id}/file`" class="w-full h-full object-cover transition-transform group-hover:scale-105" />
                            <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-between p-2 text-white">
                                <div class="flex justify-end">
                                    <div class="w-5 h-5 rounded-full border-2 flex items-center justify-center" :class="isSelected(image.id) ? 'bg-red-500 border-white' : 'bg-black/30 border-white/50'">
                                        <svg v-if="isSelected(image.id)" class="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
                                    </div>
                                </div>
                                <p class="text-xs line-clamp-3" :title="image.prompt">{{ image.prompt }}</p>
                            </div>
                            <div v-if="isSelected(image.id)" class="absolute top-1 left-1 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center z-10">
                                {{ selectedImages.indexOf(image.id) + 1 }}
                            </div>
                            <div class="absolute bottom-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button @click.stop="reusePrompt(image)" class="p-1.5 bg-black/50 rounded-full hover:bg-black/80" title="Reuse Prompt & Settings"><IconRefresh class="w-4 h-4 text-white" /></button>
                                <button @click.stop="openImageViewer(image, index)" class="p-1.5 bg-black/50 rounded-full hover:bg-black/80" title="View Full Size"><IconMaximize class="w-4 h-4 text-white" /></button>
                                <button @click.stop="openInpaintingEditor(image)" class="p-1.5 bg-black/50 rounded-full hover:bg-black/80" title="Inpaint/Edit"><IconPencil class="w-4 h-4 text-white" /></button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="flex-shrink-0 bg-white dark:bg-gray-800 p-4 border-t dark:border-gray-700 shadow-top">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label for="prompt" class="block text-sm font-medium">Prompt</label>
                    <div class="relative mt-1"><textarea id="prompt" v-model="prompt" rows="3" class="input-field pr-10" placeholder="A photorealistic image of..."></textarea><button @click="handleEnhance('prompt')" class="absolute top-1 right-1 btn-icon" title="Enhance prompt with AI" :disabled="isEnhancing"><IconSparkles class="w-4 h-4" /></button></div>
                </div>
                <div>
                    <label for="negative-prompt" class="block text-sm font-medium">Negative Prompt</label>
                    <div class="relative mt-1"><textarea id="negative-prompt" v-model="negativePrompt" rows="3" class="input-field pr-10" placeholder="ugly, blurry, bad anatomy..."></textarea><button @click="handleEnhance('negative_prompt')" class="absolute top-1 right-1 btn-icon" title="Enhance negative prompt with AI" :disabled="isEnhancing"><IconSparkles class="w-4 h-4" /></button></div>
                </div>
            </div>
            
            <div v-if="isConfigVisible" class="mt-4 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4 items-end">
                <div v-if="!isSelectionMode">
                    <label for="n" class="block text-sm font-medium">Number</label>
                    <input id="n" v-model.number="nImages" type="number" min="1" max="10" class="input-field mt-1">
                </div>
                <div>
                    <label for="size" class="block text-sm font-medium">Size</label>
                    <select id="size" v-model="imageSize" class="input-field mt-1">
                        <option value="1024x1024">1024x1024</option><option value="1792x1024">1792x1024</option><option value="1024x1792">1024x1792</option><option value="512x512">512x512</option>
                    </select>
                </div>
                <div>
                    <label for="seed" class="block text-sm font-medium">Seed</label>
                    <input id="seed" v-model.number="seed" type="number" class="input-field mt-1" placeholder="-1 for random">
                </div>
                <div v-for="param in modelConfigurableParameters" :key="param.name">
                    <label :for="`param-${param.name}`" class="block text-sm font-medium capitalize">{{ param.name.replace(/_/g, ' ') }}</label>
                    <select v-if="param.options && param.options.length > 0" :id="`param-${param.name}`" v-model="generationParams[param.name]" class="input-field mt-1">
                        <option v-for="option in parseOptions(param.options)" :key="option" :value="option">{{ option }}</option>
                    </select>
                    <input v-else :type="param.type === 'str' ? 'text' : 'number'" :step="param.type === 'float' ? '0.1' : '1'" :id="`param-${param.name}`" v-model="generationParams[param.name]" class="input-field mt-1" :placeholder="param.default">
                </div>
            </div>
            
            <div class="mt-4 flex justify-end items-center gap-2">
                <button @click="isConfigVisible = !isConfigVisible" class="btn btn-secondary p-2.5" :title="isConfigVisible ? 'Hide Settings' : 'Show Settings'">
                    <IconAdjustmentsHorizontal class="w-5 h-5" />
                </button>
                <button @click="handleEnhance('both')" class="btn btn-secondary p-2.5" :disabled="isGenerating || isEnhancing" title="Enhance both prompts">
                    <IconSparkles class="w-5 h-5" />
                </button>
                <button @click="handleGenerateOrApply" class="btn btn-primary flex-grow sm:flex-grow-0" :disabled="isEnhancing">
                    <IconAnimateSpin v-if="isGenerating" class="w-5 h-5 mr-2" />
                    {{ isSelectionMode ? 'Apply' : 'Generate' }}
                </button>
            </div>
        </div>
    </div>
</template>

<style scoped>
.shadow-top {
    box-shadow: 0 -4px 6px -1px rgb(0 0 0 / 0.1), 0 -2px 4px -2px rgb(0 0 0 / 0.1);
}
</style>