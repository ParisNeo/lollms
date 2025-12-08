<template>
    <Teleport to="#global-header-actions-target">
        <div class="flex items-center gap-2">
            <button @click="handleGenerateOrApply" class="btn btn-primary" :disabled="isGenerating || enhancingTarget">
                <IconAnimateSpin v-if="isGenerating || enhancingTarget" class="w-5 h-5 mr-2 animate-spin" />
                {{ isSelectionMode ? 'Apply Edit' : 'Generate' }}
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
        
        <div class="flex-grow min-h-0 flex overflow-hidden">
            <!-- Controls Sidebar -->
            <div class="w-80 md:w-96 flex-shrink-0 bg-white dark:bg-gray-800 border-r dark:border-gray-700 flex flex-col overflow-hidden">
                <div class="flex-grow p-4 space-y-5 overflow-y-auto custom-scrollbar">
                    
                    <!-- Prompt Section -->
                    <div class="space-y-3">
                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label for="prompt" class="text-sm font-semibold text-gray-700 dark:text-gray-200">Prompt</label>
                                <button @click="openEnhanceModal('prompt')" class="text-blue-600 dark:text-blue-400 hover:text-blue-700 p-1 rounded hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors" title="Enhance prompt with AI" :disabled="enhancingTarget">
                                    <IconSparkles class="w-4 h-4" />
                                </button>
                            </div>
                            <textarea id="prompt" v-model="prompt" rows="4" class="input-field w-full resize-none shadow-sm" placeholder="Describe your image..."></textarea>
                        </div>
                        <div>
                             <div class="flex justify-between items-center mb-1">
                                <label for="negative-prompt" class="text-sm font-semibold text-gray-700 dark:text-gray-200">Negative Prompt</label>
                                <button @click="openEnhanceModal('negative_prompt')" class="text-red-600 dark:text-red-400 hover:text-red-700 p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors" title="Enhance negative prompt with AI" :disabled="enhancingTarget">
                                    <IconSparkles class="w-4 h-4" />
                                </button>
                            </div>
                            <textarea id="negative-prompt" v-model="negativePrompt" rows="3" class="input-field w-full resize-none shadow-sm" placeholder="Things to avoid..."></textarea>
                        </div>
                        <button @click="openEnhanceModal('both')" class="btn btn-secondary w-full text-xs py-1.5" :disabled="enhancingTarget">
                            <IconSparkles class="w-3 h-3 mr-1.5" /> Enhance All
                        </button>
                    </div>

                    <!-- Generation Settings -->
                    <div class="pt-4 border-t dark:border-gray-700">
                        <div class="flex items-center justify-between cursor-pointer" @click="isConfigVisible = !isConfigVisible">
                            <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-200">Settings</h3>
                            <IconChevronUp class="w-4 h-4 text-gray-500 transition-transform duration-200" :class="{'rotate-180': !isConfigVisible}" />
                        </div>
                        
                        <div v-show="isConfigVisible" class="mt-4 space-y-4">
                            <div class="grid grid-cols-2 gap-4">
                                <div v-if="!isSelectionMode">
                                    <label class="label text-xs">Count</label>
                                    <div class="flex items-center mt-1">
                                        <input type="range" v-model.number="nImages" min="1" max="8" class="flex-grow mr-2 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700">
                                        <span class="text-sm font-medium w-4 text-center">{{ nImages }}</span>
                                    </div>
                                </div>
                                <div class="col-span-2">
                                    <label for="size" class="label text-xs">Size</label>
                                    <select id="size" v-model="imageSize" class="input-field mt-1 w-full text-sm">
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
                            </div>
                            
                            <div>
                                <label for="seed" class="label text-xs">Seed</label>
                                <div class="flex gap-2 mt-1">
                                    <input id="seed" v-model.number="seed" type="number" class="input-field flex-grow text-sm" placeholder="-1 (Random)">
                                    <button @click="seed = -1" class="btn btn-secondary px-2" title="Randomize Seed"><IconRefresh class="w-4 h-4" /></button>
                                </div>
                            </div>

                            <div v-if="modelConfigurableParameters.length > 0" class="space-y-3 pt-2 border-t dark:border-gray-700/50">
                                <p class="text-xs font-semibold text-gray-500 uppercase">Model Parameters</p>
                                <div v-for="param in modelConfigurableParameters" :key="param.name">
                                    <label :for="`param-${param.name}`" class="label text-xs capitalize">{{ param.name.replace(/_/g, ' ') }}</label>
                                    <select v-if="param.options && param.options.length > 0" :id="`param-${param.name}`" v-model="generationParams[param.name]" class="input-field mt-1 w-full text-sm">
                                        <option v-for="option in parseOptions(param.options)" :key="option" :value="option">{{ option }}</option>
                                    </select>
                                    <input v-else :type="param.type === 'str' ? 'text' : 'number'" :step="param.type === 'float' ? '0.1' : '1'" :id="`param-${param.name}`" v-model="generationParams[param.name]" class="input-field mt-1 w-full text-sm" :placeholder="param.default">
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="p-4 border-t dark:border-gray-700 flex-shrink-0 bg-gray-50 dark:bg-gray-800/50">
                    <router-link to="/" class="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors">
                        <IconArrowLeft class="w-4 h-4" /> Back to App
                    </router-link>
                </div>
            </div>

            <!-- Main Content Area -->
            <div class="flex-grow flex flex-col min-w-0 h-full relative">
                <!-- Toolbar -->
                <div class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-3 flex items-center justify-between flex-shrink-0 z-10 shadow-sm">
                    <div class="flex items-center gap-4">
                        <div class="flex items-center gap-2">
                            <input type="checkbox" v-model="areAllSelected" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer" title="Select All" />
                            <h2 class="font-semibold text-gray-800 dark:text-gray-200">Gallery <span class="text-gray-500 font-normal ml-1">({{ images.length }})</span></h2>
                        </div>
                        <div class="h-6 w-px bg-gray-300 dark:bg-gray-600 mx-2"></div>
                        <div class="flex items-center gap-2">
                            <button @click="handleRefresh" class="btn-icon text-gray-500 hover:text-blue-600" title="Refresh Gallery">
                                <IconRefresh class="w-5 h-5" />
                            </button>
                            <label class="btn-icon text-gray-500 hover:text-blue-600 cursor-pointer" title="Upload Images">
                                <IconArrowDownTray class="w-5 h-5" />
                                <input type="file" @change="handleUpload" class="hidden" accept="image/*" multiple>
                            </label>
                            <button @click="openCameraModal" class="btn-icon text-gray-500 hover:text-blue-600" title="Take Photo">
                                <IconCamera class="w-5 h-5" />
                            </button>
                            <button @click="handleNewBlankImage" class="btn-icon text-gray-500 hover:text-blue-600" title="Create Blank Canvas">
                                <IconPlus class="w-5 h-5" />
                            </button>
                        </div>
                    </div>

                    <div v-if="isSelectionMode" class="flex items-center gap-3 bg-blue-50 dark:bg-blue-900/30 px-3 py-1.5 rounded-lg border border-blue-100 dark:border-blue-800 transition-all">
                        <span class="text-sm font-medium text-blue-800 dark:text-blue-200">{{ selectedImages.length }} selected</span>
                        <div class="h-4 w-px bg-blue-200 dark:bg-blue-700"></div>
                        <button @click="handleMoveToDiscussion" class="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200" title="Send to Chat">
                            <IconSend class="w-5 h-5" />
                        </button>
                        <button @click="handleDeleteSelected" class="text-red-500 hover:text-red-700" title="Delete">
                            <IconTrash class="w-5 h-5" />
                        </button>
                    </div>
                </div>

                <!-- Scrollable Gallery Area -->
                <div class="flex-grow overflow-y-auto p-4 custom-scrollbar bg-gray-50 dark:bg-gray-900">
                    <!-- Tasks Section (Pinned to top if active) -->
                    <div v-if="imageGenerationTasksCount > 0" class="mb-6">
                        <h3 class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Active Generations</h3>
                        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                            <div v-for="task in imageGenerationTasks" :key="task.id" class="relative aspect-square rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm flex flex-col items-center justify-center p-4 text-center overflow-hidden group">
                                <div class="absolute inset-0 bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 animate-pulse"></div>
                                <div class="relative z-10">
                                    <IconAnimateSpin class="w-8 h-8 text-blue-500 mb-3 animate-spin mx-auto" />
                                    <p class="text-xs font-semibold text-gray-700 dark:text-gray-200 truncate w-full px-2" :title="task.name">{{ task.name }}</p>
                                    <p class="text-[10px] text-gray-500 mt-1">{{ task.progress }}%</p>
                                </div>
                                <div class="absolute bottom-0 left-0 right-0 h-1 bg-gray-200 dark:bg-gray-700">
                                    <div class="h-full bg-blue-500 transition-all duration-300" :style="{ width: task.progress + '%' }"></div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Images Grid -->
                    <div v-if="isLoading && images.length === 0" class="h-64 flex flex-col items-center justify-center text-gray-400">
                        <IconAnimateSpin class="w-10 h-10 mb-3 text-blue-500" />
                        <p>Loading gallery...</p>
                    </div>
                    
                    <div v-else-if="images.length === 0 && imageGenerationTasksCount === 0" class="h-full flex flex-col items-center justify-center text-gray-400 opacity-60">
                        <IconPhoto class="w-24 h-24 mb-4" />
                        <p class="text-lg font-medium">Your gallery is empty</p>
                        <p class="text-sm mt-1">Start generating or upload images to get started!</p>
                    </div>

                    <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 pb-10">
                        <div v-for="(image, index) in images" :key="image.id" 
                            @click="toggleSelection(image.id)" 
                            class="relative aspect-square rounded-xl overflow-hidden group cursor-pointer border-2 transition-all duration-200 shadow-sm hover:shadow-md bg-gray-200 dark:bg-gray-800" 
                            :class="isSelected(image.id) ? 'border-blue-500 ring-2 ring-blue-500 ring-offset-2 dark:ring-offset-gray-900' : 'border-transparent hover:border-gray-300 dark:hover:border-gray-600'">
                            
                            <AuthenticatedImage :src="`/api/image-studio/${image.id}/file`" class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
                            
                            <!-- Overlay Information -->
                            <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex flex-col justify-end p-3">
                                <p class="text-white text-xs line-clamp-2 drop-shadow-md">{{ image.prompt || 'No prompt' }}</p>
                                <div class="flex items-center justify-between mt-2 pt-2 border-t border-white/20">
                                    <span class="text-[10px] text-gray-300 font-mono">{{ image.width }}x{{ image.height }}</span>
                                    <div class="flex gap-1">
                                        <button @click.stop="reusePrompt(image)" class="p-1.5 bg-white/20 hover:bg-white/40 rounded text-white backdrop-blur-sm transition-colors" title="Reuse Settings"><IconRefresh class="w-3.5 h-3.5" /></button>
                                        <button @click.stop="openInpaintingEditor(image)" class="p-1.5 bg-white/20 hover:bg-white/40 rounded text-white backdrop-blur-sm transition-colors" title="Edit"><IconPencil class="w-3.5 h-3.5" /></button>
                                        <button @click.stop="openImageViewer(image, index)" class="p-1.5 bg-white/20 hover:bg-white/40 rounded text-white backdrop-blur-sm transition-colors" title="View"><IconMaximize class="w-3.5 h-3.5" /></button>
                                    </div>
                                </div>
                            </div>

                            <!-- Selection Checkbox -->
                            <div v-if="isSelected(image.id)" class="absolute top-2 left-2 bg-blue-500 text-white rounded-full p-0.5 shadow-sm z-10 animate-bounce-in">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>
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
import IconRefresh from '../assets/icons/IconRefresh.vue'; 
import IconChevronUp from '../assets/icons/IconChevronUp.vue';
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
    images, isLoading, isGenerating, isEnhancing,
    prompt, negativePrompt, imageSize, nImages, seed, generationParams 
} = storeToRefs(imageStore);
const { user } = storeToRefs(authStore);
const { imageGenerationTasks, imageGenerationTasksCount } = storeToRefs(tasksStore);
const { currentModelVisionSupport } = storeToRefs(discussionsStore);

const isConfigVisible = ref(true);
const enhancingTarget = computed(() => isEnhancing.value);
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
        // Edit mode logic here
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

<style scoped>
/* Custom Scrollbar for Sidebar */
.custom-scrollbar::-webkit-scrollbar {
    width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
    background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
    background-color: rgba(156, 163, 175, 0.5);
    border-radius: 20px;
}
.dark .custom-scrollbar::-webkit-scrollbar-thumb {
    background-color: rgba(75, 85, 99, 0.5);
}

@keyframes bounce-in {
  0% { transform: scale(0); opacity: 0; }
  50% { transform: scale(1.2); }
  100% { transform: scale(1); opacity: 1; }
}
.animate-bounce-in {
  animation: bounce-in 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
}
</style>
