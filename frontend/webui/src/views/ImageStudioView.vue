<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from '../stores/auth';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useImageStore } from '../stores/images';
import { useTasksStore } from '../stores/tasks';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconChevronDown from '../assets/icons/IconChevronDown.vue';
import IconChevronRight from '../assets/icons/IconChevronRight.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconPlus from '../assets/icons/IconPlus.vue';
import IconSave from '../assets/icons/IconSave.vue';
import IconRefresh from '../assets/icons/IconRefresh.vue';

const authStore = useAuthStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const imageStore = useImageStore(); 
const tasksStore = useTasksStore();

const { user } = storeToRefs(authStore);
const { availableTtiModelsGrouped, availableTtiModels } = storeToRefs(dataStore);
const { generatedImages, isLoadingImages, isLoadingGeneration, currentCanvasImage } = storeToRefs(imageStore);
const { tasks } = storeToRefs(tasksStore);

const localFileInputRef = ref(null);

// --- Form State ---
const form = ref({
    prompt: '',
    model_name: user.value?.tti_binding_model_name || '',
    size: '1024x1024',
    quality: 'standard',
    style: 'vivid',
    steps: null,
    sampler_name: null,
    cfg_scale: null,
    seed: null,
});

const isFormValid = computed(() => form.value.prompt.trim() !== '' && form.value.model_name.trim() !== '');

const isGenerationDisabled = computed(() => isLoadingGeneration.value || !isFormValid.value);

const isParametersCollapsed = ref(true);

const selectedModelDetails = computed(() => {
    if (!form.value.model_name) return null;
    return availableTtiModels.value.find(m => m.id === form.value.model_name);
});

// --- Parameter Fields (Dynamic) ---
const modelConfigurableParameters = computed(() => {
    const params = selectedModelDetails.value?.binding_params?.parameters || [];
    const excluded = ['prompt', 'size', 'quality', 'style', 'model_name', 'model', 'url', 'n', 'response_format', 'user']; // Exclude common and pre-filled fields
    return params.filter(p => !excluded.includes(p.name));
});

// --- Lifecycle & Data Fetching ---
onMounted(async () => {
    if (availableTtiModels.value.length === 0) {
        await dataStore.fetchAvailableTtiModels();
    }
    await imageStore.fetchGeneratedImages();
    if (!form.value.model_name && availableTtiModels.value.length > 0) {
        form.value.model_name = availableTtiModels.value[0].id;
    }
});

// --- Actions ---
async function handleGenerate() {
    if (!isFormValid.value || isLoadingGeneration.value) return;

    const payload = Object.entries(form.value).reduce((acc, [key, value]) => {
        if (value !== null && value !== '' && value !== undefined) {
            acc[key] = value;
        }
        return acc;
    }, {});
    
    await imageStore.generateImage(payload);
}

async function handleDeleteImage(fileName) {
    const confirmed = await uiStore.showConfirmation({
        title: 'Delete Image',
        message: 'Are you sure you want to permanently delete this image?',
        confirmText: 'Delete'
    });
    if (confirmed) {
        await imageStore.deleteGeneratedImage(fileName);
    }
}

function openImageViewer(src) {
    uiStore.openImageViewer(src);
}

function downloadImage(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

watch(tasks, (newTasks, oldTasks) => {
    const completedImageTasks = newTasks.filter(task => 
        (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') &&
        task.name.startsWith("Image Studio Gen:") &&
        !oldTasks.some(oldTask => oldTask.id === task.id && oldTask.status === task.status)
    );

    if (completedImageTasks.length > 0) {
        const successfulTask = completedImageTasks.find(t => t.status === 'completed');
        if (successfulTask) {
            imageStore.fetchGeneratedImages();
            
            if (successfulTask.result?.seed) {
                form.value.seed = successfulTask.result.seed;
            }
            
            if (successfulTask.result?.image_url && successfulTask.result?.file_name) {
                imageStore.setCurrentCanvasImage(successfulTask.result.image_url, successfulTask.result.file_name);
            }
        }
    }
}, { deep: true });

function triggerLocalFileUpload() {
    localFileInputRef.value.click();
}

function handleLocalFileChange(event) {
    const file = event.target.files[0];
    if (file) {
        if (!file.type.startsWith('image/')) {
            uiStore.addNotification('Only image files are allowed for the canvas.', 'warning');
            return;
        }
        const url = URL.createObjectURL(file);
        imageStore.setCurrentCanvasImage(url, file.name); 
        event.target.value = '';
    }
}

function handleSidebarImageSelection(image) {
    imageStore.setCurrentCanvasImage(image.image_url, image.file_name);
}
</script>

<template>
    <PageViewLayout title="Image Studio" :title-icon="IconPhoto">
        <template #sidebar>
            <div class="p-3">
                <h3 class="text-sm font-semibold uppercase text-gray-500 dark:text-gray-400">Gallery (History)</h3>
            </div>
            <div v-if="isLoadingImages" class="p-4 text-center">
                <IconAnimateSpin class="w-6 h-6 text-gray-400 mx-auto" />
            </div>
            <div v-else class="flex-1 overflow-y-auto custom-scrollbar">
                <ul class="space-y-2 p-2">
                    <li v-for="image in generatedImages" :key="image?.file_name" 
                        class="group flex items-center bg-gray-50 dark:bg-gray-800/50 rounded-lg p-2 transition-colors"
                        :class="{ 'border-2 border-blue-500 ring-1 ring-blue-500': currentCanvasImage?.filename === image?.file_name, 'hover:bg-gray-100 dark:hover:bg-gray-700/50': currentCanvasImage?.filename !== image?.file_name }">
                        
                        <div v-if="image" @click="handleSidebarImageSelection(image)" class="cursor-pointer flex items-center gap-2 flex-grow min-w-0">
                            <img :src="image.image_url" alt="Generated thumbnail" class="w-10 h-10 object-cover rounded-md flex-shrink-0">
                            <div class="min-w-0">
                                <span class="block text-xs font-medium truncate" :title="image.file_name">{{ image.file_name }}</span>
                                <span class="block text-xs text-gray-500">{{ new Date(image.timestamp).toLocaleTimeString() }}</span>
                            </div>
                        </div>
                        
                        <div v-if="image" class="flex-shrink-0 flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <a :href="image.image_url" :download="image.file_name" class="p-1 rounded-full text-gray-400 hover:text-blue-500" title="Download">
                                <IconArrowDownTray class="w-4 h-4" />
                            </a>
                            <button @click="handleDeleteImage(image.file_name)" class="p-1 rounded-full text-gray-400 hover:text-red-500" title="Delete">
                                <IconTrash class="w-4 h-4" />
                            </button>
                        </div>
                    </li>
                </ul>
                <div v-if="generatedImages.length === 0" class="text-center p-4 text-sm text-gray-500">No images generated yet.</div>
            </div>
            <button @click="imageStore.fetchGeneratedImages" class="w-full btn btn-secondary btn-sm mt-2">
                <IconRefresh class="w-4 h-4 mr-2" /> Refresh
            </button>
        </template>
        <template #main>
            <div class="h-full flex flex-col p-4 sm:p-6 space-y-6">
                
                <!-- Main Canvas Area (Centered) - Flex-1 ensures it takes all available vertical space -->
                <div class="flex-1 flex flex-col items-center justify-center min-h-[300px] bg-gray-100 dark:bg-gray-900 rounded-lg overflow-hidden relative">
                    <div v-if="isLoadingGeneration" class="text-center p-6 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-blue-800 dark:text-blue-200">
                        <IconAnimateSpin class="w-12 h-12 text-blue-500 mx-auto mb-3" />
                        <p class="font-semibold text-lg">Image generation in progress...</p>
                        <p class="text-sm mt-1">Check the Task Manager for progress.</p>
                    </div>
                    
                    <div v-else-if="currentCanvasImage?.url" class="relative max-w-full max-h-full">
                        <img :src="currentCanvasImage.url" alt="Image Canvas" class="object-contain max-h-[70vh] max-w-full rounded-lg shadow-2xl transition-all duration-300">
                        
                        <div class="absolute top-2 right-2 flex items-center space-x-2 opacity-0 hover:opacity-100 transition-opacity">
                            <button @click="openImageViewer(currentCanvasImage.url)" class="p-2 rounded-full bg-black/50 text-white hover:bg-black/70" title="View Fullscreen">
                                <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5v-4m0 4h-4m4 0l-5-5" /></svg>
                            </button>
                            <button v-if="currentCanvasImage.filename" @click="downloadImage(currentCanvasImage.url, currentCanvasImage.filename)" class="p-2 rounded-full bg-black/50 text-white hover:bg-black/70" title="Download">
                                <IconArrowDownTray class="w-6 h-6" />
                            </button>
                        </div>
                    </div>
                    
                    <div v-else class="text-center p-6 text-gray-500 dark:text-gray-400">
                        <IconPhoto class="w-12 h-12 mx-auto mb-3" />
                        <p class="text-lg font-medium">No image loaded on canvas.</p>
                        <p class="text-sm">Generate a new image or load one from your computer.</p>
                        <input type="file" ref="localFileInputRef" @change="handleLocalFileChange" class="hidden" accept="image/*">
                         <button @click="triggerLocalFileUpload" class="btn btn-secondary btn-sm mt-4">
                            <IconPlus class="w-4 h-4 mr-2" /> Load Local Image
                        </button>
                    </div>
                </div>

                <!-- Controls & Form at the Bottom -->
                <div class="flex-shrink-0 bg-white dark:bg-gray-800 p-6 rounded-lg shadow-md space-y-4">
                     <h3 class="text-xl font-semibold text-gray-900 dark:text-white">Generation Controls</h3>
                    
                    <div>
                        <label for="prompt-input" class="block text-sm font-medium">Prompt</label>
                        <textarea id="prompt-input" v-model="form.prompt" rows="3" class="input-field mt-1" placeholder="Enter your detailed prompt here..."></textarea>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label for="model-select-controls" class="block text-sm font-medium">Model</label>
                            <select id="model-select-controls" v-model="form.model_name" class="input-field mt-1" :disabled="availableTtiModels.length === 0">
                                <option v-if="availableTtiModels.length === 0" disabled value="">No TTI models available</option>
                                <optgroup v-for="group in availableTtiModelsGrouped" :key="group.label" :label="group.label">
                                    <option v-for="model in group.items" :key="model.id" :value="model.id">
                                        {{ model.name }}
                                    </option>
                                </optgroup>
                            </select>
                        </div>
                        <div>
                            <label for="size" class="block text-sm font-medium">Size</label>
                            <select id="size" v-model="form.size" class="input-field mt-1">
                                <option value="1024x1024">1024x1024</option>
                                <option value="1792x1024">1792x1024</option>
                                <option value="1024x1792">1024x1792</option>
                            </select>
                        </div>
                    </div>
                    
                    <button @click="isParametersCollapsed = !isParametersCollapsed" class="flex items-center text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline">
                        <IconChevronRight class="w-4 h-4 mr-1 transition-transform" :class="{'rotate-90': !isParametersCollapsed}"/>
                        Advanced Parameters
                    </button>

                    <transition enter-active-class="transition ease-out duration-200" enter-from-class="opacity-0 -translate-y-2" enter-to-class="opacity-100 translate-y-0" leave-active-class="transition ease-in duration-150" leave-from-class="opacity-100 translate-y-0" leave-to-class="opacity-0 -translate-y-2">
                        <div v-if="!isParametersCollapsed" class="grid grid-cols-2 md:grid-cols-3 gap-4 border-t dark:border-gray-700 pt-4">
                            <!-- Standard Fields -->
                            <div>
                                <label for="quality" class="block text-sm font-medium">Quality</label>
                                <select id="quality" v-model="form.quality" class="input-field mt-1">
                                    <option value="standard">Standard</option>
                                    <option value="hd">HD</option>
                                </select>
                            </div>
                            <div>
                                <label for="style" class="block text-sm font-medium">Style</label>
                                <select id="style" v-model="form.style" class="input-field mt-1">
                                    <option value="vivid">Vivid</option>
                                    <option value="natural">Natural</option>
                                </select>
                            </div>
                            <div v-if="form.seed !== null">
                                <label for="seed" class="block text-sm font-medium">Seed</label>
                                <input type="number" id="seed" v-model.number="form.seed" class="input-field mt-1" placeholder="Optional seed">
                            </div>

                            <!-- Dynamic Fields -->
                            <div v-for="param in modelConfigurableParameters" :key="param.name" :title="param.description">
                                <label :for="param.name" class="block text-sm font-medium capitalize">{{ param.name.replace(/_/g, ' ') }}</label>
                                <select v-if="param.type === 'str' && param.options" :id="param.name" v-model="form[param.name]" class="input-field mt-1">
                                    <option v-for="opt in param.options.split(',')" :key="opt" :value="opt.trim()">{{ opt.trim() }}</option>
                                </select>
                                <input v-else :type="param.type === 'int' ? 'number' : param.type === 'float' ? 'number' : 'text'" 
                                       :step="param.type === 'float' ? '0.01' : '1'"
                                       :id="param.name" v-model.number="form[param.name]" class="input-field mt-1" :placeholder="param.default" />
                            </div>
                        </div>
                    </transition>

                    <div class="flex justify-end pt-4 border-t dark:border-gray-700">
                        <button @click="handleGenerate" class="btn btn-primary" :disabled="isGenerationDisabled">
                            <IconAnimateSpin v-if="isLoadingGeneration" class="w-5 h-5 mr-2" />
                            <IconPhoto v-else class="w-5 h-5 mr-2" />
                            {{ isLoadingGeneration ? 'Generating...' : 'Generate Image' }}
                        </button>
                    </div>
                </div>
            </div>
        </template>
    </PageViewLayout>
</template>