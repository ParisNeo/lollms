<template>
    <Teleport to="#global-header-actions-target">
        <div class="flex items-center gap-2">
            <button @click="handleGenerateOrApply" class="btn btn-primary" :disabled="isGenerating || enhancingTarget">
                <IconAnimateSpin v-if="isGenerating || enhancingTarget" class="w-5 h-5 mr-2 animate-spin" />
                {{ isSelectionMode ? 'Apply' : 'Generate' }}
            </button>
        </div>
    </Teleport>
    <div 
        class="h-full flex flex-col bg-gray-50 dark:bg-gray-900" 
        @dragover.prevent="handleDragOver"
        @dragleave.prevent="handleDragLeave"
        @drop.prevent="handleDrop"
    >
        <div v-if="isDraggingOver" class="absolute inset-0 bg-blue-500/20 border-4 border-dashed border-blue-500 rounded-lg z-20 flex items-center justify-center m-4 pointer-events-none">
            <p class="text-2xl font-bold text-blue-600">Drop images anywhere to upload</p>
        </div>
        
        <div class="flex-grow min-h-0 flex">
            <!-- Controls Sidebar -->
            <div class="w-96 flex-shrink-0 bg-white dark:bg-gray-800 border-r dark:border-gray-700 flex flex-col">
                <div class="flex-grow p-4 space-y-4 overflow-y-auto custom-scrollbar">
                    <div>
                        <div class="flex justify-between items-center mb-1">
                            <label for="prompt" class="block text-sm font-medium">Prompt</label>
                            <button @click="openEnhanceModal('prompt')" class="btn-icon" title="Enhance prompt with AI" :disabled="enhancingTarget"><IconSparkles class="w-4 h-4" /></button>
                        </div>
                        <div class="relative mt-1"><textarea id="prompt" v-model="prompt" rows="4" class="input-field" placeholder="A photorealistic image of..."></textarea></div>
                    </div>
                    <div>
                         <div class="flex justify-between items-center mb-1">
                            <label for="negative-prompt" class="block text-sm font-medium">Negative Prompt</label>
                            <button @click="openEnhanceModal('negative_prompt')" class="btn-icon" title="Enhance negative prompt with AI" :disabled="enhancingTarget"><IconSparkles class="w-4 h-4" /></button>
                        </div>
                        <div class="relative mt-1"><textarea id="negative-prompt" v-model="negativePrompt" rows="3" class="input-field" placeholder="ugly, blurry, bad anatomy..."></textarea></div>
                    </div>
                    
                    <div class="pt-4 border-t dark:border-gray-600 space-y-2">
                        <button @click="openEnhanceModal('both')" class="btn btn-secondary w-full" :disabled="enhancingTarget">
                            <IconSparkles class="w-4 h-4 mr-2" /> Enhance Both Prompts
                        </button>
                    </div>

                    <div class="pt-4 border-t dark:border-gray-600">
                        <div class="flex items-center justify-between">
                            <h3 class="text-sm font-semibold">Generation Settings</h3>
                            <button @click="isConfigVisible = !isConfigVisible" class="btn-icon-flat" :title="isConfigVisible ? 'Hide Settings' : 'Show Settings'">
                                <IconAdjustmentsHorizontal class="w-5 h-5" />
                            </button>
                        </div>
                        <div v-if="isConfigVisible" class="mt-4 grid grid-cols-2 gap-4 items-end">
                            <div v-if="!isSelectionMode">
                                <label for="n" class="block text-sm font-medium">Number</label>
                                <input id="n" v-model.number="nImages" type="number" min="1" max="10" class="input-field mt-1">
                            </div>
                            <div>
                                <label for="size" class="block text-sm font-medium">Size</label>
                                <select id="size" v-model="imageSize" class="input-field mt-1">
                                    <option value="1024x1024">1024x1024 (Square 1:1)</option>
                                    <option value="1152x896">1152x896 (Landscape ~4:3)</option>
                                    <option value="896x1152">896x1152 (Portrait ~3:4)</option>
                                    <option value="1216x832">1216x832 (Landscape ~3:2)</option>
                                    <option value="832x1216">832x1216 (Portrait ~2:3)</option>
                                    <option value="1344x768">1344x768 (Widescreen 16:9)</option>
                                    <option value="768x1344">768x1344 (Tall 9:16)</option>
                                    <option value="1536x640">1536x640 (Cinematic ~2.4:1)</option>
                                    <option value="640x1536">640x1536 (Tall Cinematic ~1:2.4)</option>
                                    <option value="512x512">512x512 (Small Square)</option>
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
                    </div>
                </div>
                <div class="p-4 border-t dark:border-gray-700 flex-shrink-0">
                    <router-link to="/" class="w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors" title="Back to Main App">
                        <IconArrowLeft class="w-5 h-5" />
                        <span>Back to App</span>
                    </router-link>
                </div>
            </div>

            <!-- Image Grid -->
            <div class="flex-grow overflow-y-auto p-4 sm:p-6 flex flex-col">
                <div class="flex-grow min-h-0 bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md flex flex-col">
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
                        <div class="flex items-center gap-2">
                            <button @click="handleRefresh" class="btn btn-secondary btn-sm">
                                <IconRefresh class="w-4 h-4 mr-2" /> Refresh
                            </button>
                            <button @click="openCameraModal" class="btn btn-secondary btn-sm">
                                <IconCamera class="w-4 h-4 mr-2" /> Take Photo
                            </button>
                            <button @click="handleNewBlankImage" class="btn btn-secondary btn-sm">
                                <IconPlus class="w-4 h-4 mr-2" /> Create Blank Image
                            </button>
                            <label for="upload-image-btn" class="btn btn-secondary btn-sm cursor-pointer">
                                <IconArrowDownTray class="w-4 h-4 mr-2" /> Upload
                                <input id="upload-image-btn" type="file" @change="handleUpload" class="hidden" accept="image/*" multiple>
                            </label>
                        </div>
                    </div>

                    <!-- Active Tasks Section -->
                    <div v-if="imageGenerationTasksCount > 0" class="flex-shrink-0 mb-4">
                        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                            <div v-for="task in imageGenerationTasks" :key="task.id" class="relative aspect-square rounded-lg bg-gray-200 dark:bg-gray-700/50 flex flex-col items-center justify-center p-2 text-center overflow-hidden">
                                <div class="absolute inset-0 bg-blue-500/10 animate-pulse"></div>
                                <IconAnimateSpin class="w-8 h-8 text-blue-500 mb-2 animate-spin" />
                                <p class="text-xs font-medium text-gray-600 dark:text-gray-300 truncate w-full" :title="task.name">{{ task.name }}</p>
                                <div class="w-full bg-gray-300 dark:bg-gray-600 rounded-full h-1 mt-2">
                                    <div class="bg-blue-500 h-1 rounded-full" :style="{ width: task.progress + '%' }"></div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div v-if="isLoading" class="flex-grow flex items-center justify-center"><IconAnimateSpin class="w-8 h-8 text-gray-500 animate-spin" /></div>
                    <div v-else-if="images.length === 0 && imageGenerationTasksCount === 0" class="flex-grow flex items-center justify-center text-center text-gray-500">
                        <div><p>No images yet.</p><p class="text-sm">Drop, paste, or use the form to generate some!</p></div>
                    </div>
                    <div v-else class="flex-grow overflow-y-auto custom-scrollbar -m-2 p-2">
                        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
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
        </div>
    </div>
</template>

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
import apiClient from '../services/api';

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
import IconPlus from '../assets/icons/IconPlus.vue';
import IconCamera from '../assets/icons/IconCamera.vue';

const imageStore = useImageStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const tasksStore = useTasksStore();
const router = useRouter();

const { 
    images, isLoading, isGenerating,
    prompt, negativePrompt, imageSize, nImages, seed, generationParams 
} = storeToRefs(imageStore);
const { user } = storeToRefs(authStore);
const { imageGenerationTasks, imageGenerationTasksCount } = storeToRefs(tasksStore);
const { currentModelVisionSupport } = storeToRefs(discussionsStore);

const isConfigVisible = ref(false);
const enhancingTarget = ref(null);
const enhancementInstructions = ref('');
const enhancementMode = ref('description');

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
    if (details) {
        modelConfigurableParameters.value.forEach(param => {
            if (!(param.name in generationParams.value)) {
                 generationParams.value[param.name] = param.default;
            }
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
        seed: seed.value,
        ...generationParams.value
    };

    if (isSelectionMode.value) {
        const [width, height] = imageSize.value.split('x').map(Number);
        await imageStore.editImage({ 
            ...commonPayload, 
            image_ids: selectedImages.value,
            width: width,
            height: height
        });
    } else {
        await imageStore.generateImage({ 
            ...commonPayload, 
            size: imageSize.value,
            n: nImages.value 
        });
    }
}

async function handleEnhance(type, options = {}) {
    if (type !== 'negative_prompt' && !prompt.value.trim()) {
        uiStore.addNotification('Please enter a prompt to enhance.', 'warning');
        return;
    }
    
    const payload = { 
        prompt: prompt.value, 
        negative_prompt: negativePrompt.value, 
        target: type,
        model: authStore.user?.lollms_model_name,
        instructions: options.instructions || '',
        mode: options.mode || 'description'
    };

    if (isSelectionMode.value && currentModelVisionSupport.value && selectedImages.value.length > 0) {
        uiStore.addNotification('Enhancing prompt with image context...', 'info');
        const image_b64s = [];
        for (const imageId of selectedImages.value) {
            try {
                const response = await apiClient.get(`/api/image-studio/${imageId}/file`, { responseType: 'blob' });
                const b64 = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                    reader.onerror = reject;
                    reader.readAsDataURL(response.data);
                });
                image_b64s.push(b64);
            } catch (error) {
                console.error(`Failed to fetch and encode image ${imageId}`, error);
                uiStore.addNotification(`Could not load image ${imageId} for context.`, 'warning');
            }
        }
        if (image_b64s.length > 0) {
            payload.image_b64s = image_b64s;
        }
    }
    
    await imageStore.enhanceImagePrompt(payload);
}

function openEnhanceModal(target) {
    uiStore.openModal('enhancePrompt', {
        instructions: enhancementInstructions.value,
        mode: enhancementMode.value,
        onConfirm: ({ instructions, mode }) => {
            enhancementInstructions.value = instructions;
            enhancementMode.value = mode;
            handleEnhance(target, { instructions, mode });
        }
    });
}

function handleNewBlankImage() {
    router.push('/image-studio/edit/new');
}


function reusePrompt(image) {
    prompt.value = image.prompt;
    negativePrompt.value = image.negative_prompt;
    seed.value = image.seed;
    uiStore.addNotification('Prompt and parameters have been reused.', 'success');
}

function openInpaintingEditor(image) { 
    router.push(`/image-studio/edit/${image.id}`);
}

function openImageViewer(image, index) {
    uiStore.openImageViewer({
        imageList: images.value.map(img => ({ ...img, src: `/api/image-studio/${img.id}/file`})),
        startIndex: index
    });
}
async function handleUpload(event) {
    const files = Array.from(event.target.files);
    if (files.length > 0) {
        uiStore.addNotification(`Uploading ${files.length} image(s)...`, 'info');
        await imageStore.uploadImages(files);
    }
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
        uiStore.addNotification(`Uploading ${files.length} image(s)...`, 'info');
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
        uiStore.addNotification(`Pasting ${imageFiles.length} image(s)...`, 'info');
        await imageStore.uploadImages(imageFiles); 
    }
}

function openCameraModal() {
    uiStore.openModal('cameraCapture');
}

async function handleRefresh() {
    await imageStore.fetchImages();
    uiStore.addNotification('Image gallery refreshed.', 'success');
}
</script>
