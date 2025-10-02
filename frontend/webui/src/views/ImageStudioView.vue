<!-- frontend/webui/src/views/ImageStudioView.vue -->
<script setup>
import { ref, onMounted, onUnmounted, computed, watch, markRaw } from 'vue';
import { useRouter } from 'vue-router';
import { useImageStore } from '../stores/images';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import { useDiscussionsStore } from '../stores/discussions';
import { storeToRefs } from 'pinia';
import AuthenticatedImage from '../components/ui/AuthenticatedImage.vue';
import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconSend from '../assets/icons/IconSend.vue';
import IconPencil from '../assets/icons/IconPencil.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconMaximize from '../assets/icons/IconMaximize.vue';
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';

const imageStore = useImageStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();
const router = useRouter();

const { images, isLoading, isGenerating, isEnhancing } = storeToRefs(imageStore);
const { user } = storeToRefs(authStore);
const { availableTtiModelsGrouped } = storeToRefs(dataStore);

const prompt = ref('');
const negativePrompt = ref('');
const selectedModel = ref(null);
const imageSize = ref('1024x1024');
const nImages = ref(1);
const seed = ref(-1); // New state for seed

const selectedImages = ref([]);
const isSelectionMode = computed(() => selectedImages.value.length > 0);
const areAllSelected = computed({
    get: () => images.value.length > 0 && selectedImages.value.length === images.value.length,
    set: (value) => {
        selectedImages.value = value ? images.value.map(img => img.id) : [];
    }
});

watch(user, (newUser) => {
    if (newUser && !selectedModel.value) {
        selectedModel.value = newUser.tti_binding_model_name;
    }
}, { immediate: true });

onMounted(() => {
    uiStore.setPageTitle({ title: 'Image Studio', icon: markRaw(IconPhoto) });
    imageStore.fetchImages();
    if (dataStore.availableTtiModels.length === 0) {
        dataStore.fetchAvailableTtiModels();
    }
    if(Object.keys(discussionsStore.discussions).length === 0){
        discussionsStore.loadDiscussions();
    }
});

onUnmounted(() => {
    uiStore.setPageTitle({ title: '' });
});


function isSelected(imageId) {
    return selectedImages.value.includes(imageId);
}

function toggleSelection(imageId) {
    const index = selectedImages.value.indexOf(imageId);
    if (index > -1) {
        selectedImages.value.splice(index, 1);
    } else {
        selectedImages.value.push(imageId);
    }
}

async function handleGenerate() {
    if (!prompt.value.trim() || !selectedModel.value) {
        uiStore.addNotification('A prompt and model are required.', 'warning');
        return;
    }
    await imageStore.generateImage({
        prompt: prompt.value,
        negative_prompt: negativePrompt.value,
        model: selectedModel.value,
        size: imageSize.value,
        n: nImages.value,
        seed: seed.value, // Include seed in the payload
    });
}

async function handleEnhance(type) {
    const payload = {
        prompt: prompt.value,
        negative_prompt: negativePrompt.value,
        target: type
    };

    if (type !== 'negative_prompt' && !payload.prompt.trim()) {
        uiStore.addNotification('Please enter a prompt to enhance.', 'warning');
        return;
    }

    const result = await imageStore.enhanceImagePrompt(payload);
    if (result) {
        if (result.prompt) {
            prompt.value = result.prompt;
        }
        if (result.negative_prompt) {
            negativePrompt.value = result.negative_prompt;
        }
    }
}


function openInpaintingEditor(image) {
    uiStore.openModal('inpaintingEditor', { image });
}

function openImageViewer(image, index) {
    uiStore.openImageViewer({
        imageList: images.value.map(img => ({
            src: `/api/image-studio/${img.id}/file`,
            prompt: img.prompt,
            model: img.model,
            filename: img.filename,
        })),
        startIndex: index
    });
}

function handleUpload(event) {
    const file = event.target.files[0];
    if (file) {
        imageStore.uploadImage(file);
    }
}

async function handleDeleteSelected() {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete ${selectedImages.value.length} Images?`,
        message: 'This action cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed.confirmed) {
        await Promise.all(selectedImages.value.map(id => imageStore.deleteImage(id)));
        selectedImages.value = [];
    }
}

async function handleMoveToDiscussion() {
    if (selectedImages.value.length === 0) return;
    const { confirmed, value: discussionId } = await uiStore.showConfirmation({
        title: `Move ${selectedImages.value.length} Images to Discussion`,
        message: 'Select a discussion to move the image(s) to:',
        confirmText: 'Move',
        inputType: 'select',
        inputOptions: discussionsStore.sortedDiscussions.map(d => ({ text: d.title, value: d.id })),
        inputValue: discussionsStore.currentDiscussionId
    });
    if (confirmed && discussionId) {
        await Promise.all(selectedImages.value.map(id => imageStore.moveImageToDiscussion(id, discussionId)));
        selectedImages.value = [];
    }
}

function goBack() {
    router.push('/');
}
</script>

<template>
    <div class="h-full flex flex-col">
        <!-- New Header for Back Button -->
        <div class="flex-shrink-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 p-2 flex items-center">
             <button @click="goBack" class="btn btn-secondary btn-icon" title="Back to Main App">
                <IconArrowLeft class="w-5 h-5" />
            </button>
        </div>
        
        <div class="flex-grow overflow-y-auto">
            <div class="h-full flex flex-col p-4 sm:p-6">
                <div class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md mb-6 flex-shrink-0">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label for="prompt" class="block text-sm font-medium">Prompt</label>
                            <div class="relative mt-1">
                                <textarea id="prompt" v-model="prompt" rows="3" class="input-field pr-10" placeholder="A photorealistic image of..."></textarea>
                                <button @click="handleEnhance('prompt')" class="absolute top-1 right-1 btn-icon" title="Enhance prompt with AI" :disabled="isEnhancing">
                                    <IconSparkles class="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                        <div>
                            <label for="negative-prompt" class="block text-sm font-medium">Negative Prompt</label>
                            <div class="relative mt-1">
                                <textarea id="negative-prompt" v-model="negativePrompt" rows="3" class="input-field pr-10" placeholder="ugly, blurry, bad anatomy..."></textarea>
                                <button @click="handleEnhance('negative_prompt')" class="absolute top-1 right-1 btn-icon" title="Enhance negative prompt with AI" :disabled="isEnhancing">
                                    <IconSparkles class="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    </div>
                    <div class="mt-4 grid grid-cols-2 md:grid-cols-5 gap-4 items-end">
                        <div>
                            <label for="model" class="block text-sm font-medium">Model</label>
                            <select id="model" v-model="selectedModel" class="input-field mt-1">
                                <option :value="null" disabled>Select a model</option>
                                <optgroup v-for="group in availableTtiModelsGrouped" :key="group.label" :label="group.label">
                                    <option v-for="model in group.items" :key="model.id" :value="model.id">{{ model.name }}</option>
                                </optgroup>
                            </select>
                        </div>
                        <div>
                            <label for="size" class="block text-sm font-medium">Size</label>
                            <select id="size" v-model="imageSize" class="input-field mt-1">
                                <option value="1024x1024">1024x1024</option>
                                <option value="1792x1024">1792x1024</option>
                                <option value="1024x1792">1024x1792</option>
                                <option value="1024x1024">512x512</option>
                            </select>
                        </div>
                        <div>
                            <label for="n" class="block text-sm font-medium">Number of Images</label>
                            <input id="n" v-model.number="nImages" type="number" min="1" max="10" class="input-field mt-1">
                        </div>
                        <div>
                            <label for="seed" class="block text-sm font-medium">Seed</label>
                            <input id="seed" v-model.number="seed" type="number" class="input-field mt-1" placeholder="-1 for random">
                        </div>
                        <div class="flex items-center gap-2">
                             <button @click="handleEnhance('both')" class="btn btn-secondary p-2.5" :disabled="isGenerating || isEnhancing" title="Enhance both prompts with AI">
                                <IconAnimateSpin v-if="isEnhancing" class="w-5 h-5" />
                                <IconSparkles v-else class="w-5 h-5" />
                            </button>
                            <button @click="handleGenerate" class="btn btn-primary w-full" :disabled="isGenerating || isEnhancing">
                                <IconAnimateSpin v-if="isGenerating" class="w-5 h-5 mr-2" />
                                Generate
                            </button>
                        </div>
                    </div>
                </div>

                <div class="flex-grow min-h-0 bg-white dark:bg-gray-800 p-4 rounded-lg shadow-md flex flex-col">
                    <div class="flex justify-between items-center mb-4 flex-shrink-0 flex-wrap gap-2">
                        <div class="flex items-center gap-2">
                            <input type="checkbox" v-model="areAllSelected" class="h-4 w-4 rounded" />
                            <h3 class="text-lg font-semibold">Your Images ({{ images.length }})</h3>
                        </div>
                        <div v-if="isSelectionMode" class="flex items-center gap-2">
                            <span class="text-sm text-gray-500">{{ selectedImages.length }} selected</span>
                            <button @click="handleMoveToDiscussion" class="btn btn-secondary btn-sm" title="Move to Discussion">
                                <IconSend class="w-4 h-4" />
                            </button>
                            <button @click="handleDeleteSelected" class="btn btn-danger btn-sm" title="Delete Selected">
                                <IconTrash class="w-4 h-4" />
                            </button>
                        </div>
                        <label for="upload-image-btn" class="btn btn-secondary btn-sm cursor-pointer">
                            <IconArrowDownTray class="w-4 h-4 mr-2" />
                            Upload
                            <input id="upload-image-btn" type="file" @change="handleUpload" class="hidden" accept="image/*">
                        </label>
                    </div>

                    <div v-if="isLoading" class="flex-grow flex items-center justify-center">
                        <IconAnimateSpin class="w-8 h-8 text-gray-500" />
                    </div>
                    <div v-else-if="images.length === 0" class="flex-grow flex items-center justify-center text-center text-gray-500">
                        <div>
                            <p>No images yet.</p>
                            <p class="text-sm">Use the form above to generate some!</p>
                        </div>
                    </div>
                    <div v-else class="flex-grow overflow-y-auto custom-scrollbar -m-2 p-2">
                        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                            <div v-for="(image, index) in images" :key="image.id" @click="toggleSelection(image.id)" class="relative aspect-square rounded-lg overflow-hidden group cursor-pointer border-2" :class="isSelected(image.id) ? 'border-blue-500' : 'border-transparent'">
                                <AuthenticatedImage :src="`/api/image-studio/${image.id}/file`" class="w-full h-full object-cover transition-transform group-hover:scale-105" />
                                <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-between p-2 text-white">
                                    <div class="flex justify-end">
                                        <div class="w-5 h-5 rounded-full border-2 flex items-center justify-center" :class="isSelected(image.id) ? 'bg-blue-500 border-white' : 'bg-black/30 border-white/50'">
                                            <svg v-if="isSelected(image.id)" class="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
                                        </div>
                                    </div>
                                    <p class="text-xs line-clamp-3" :title="image.prompt">{{ image.prompt }}</p>
                                </div>
                                <div class="absolute bottom-1 right-1 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button @click.stop="openImageViewer(image, index)" class="p-1.5 bg-black/50 rounded-full hover:bg-black/80" title="View Full Size">
                                        <IconMaximize class="w-4 h-4 text-white" />
                                    </button>
                                    <button @click.stop="openInpaintingEditor(image)" class="p-1.5 bg-black/50 rounded-full hover:bg-black/80" title="Inpaint/Edit">
                                        <IconPencil class="w-4 h-4 text-white" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>