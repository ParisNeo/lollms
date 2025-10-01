<template>
    <PageViewLayout title="Image Studio" :title-icon="IconPhoto">
        <template #sidebar>
            <div class="p-4 space-y-4">
                <div>
                    <label for="tti-model" class="block text-sm font-medium mb-1">Image Model</label>
                    <select id="tti-model" v-model="selectedTtiModel" class="input-field w-full">
                        <option v-if="isLoadingTtiModels" disabled>Loading models...</option>
                        <optgroup v-for="group in availableTtiModelsGrouped" :key="group.label" :label="group.label">
                            <option v-for="model in group.items" :key="model.id" :value="model.id">
                                {{ model.name }}
                            </option>
                        </optgroup>
                    </select>
                </div>

                <div>
                    <label for="prompt" class="block text-sm font-medium mb-1">Prompt</label>
                    <textarea id="prompt" v-model="generationPrompt" rows="6" class="input-field w-full" placeholder="A futuristic cityscape at sunset..."></textarea>
                </div>
                <div v-if="selectedImageIds.size === 0">
                    <label for="num-images" class="block text-sm font-medium mb-1">Number of Images</label>
                    <input type="number" id="num-images" v-model.number="numberOfImages" min="1" max="4" class="input-field w-full">
                </div>
                 <button @click="handleGenerate" class="btn btn-primary w-full" :disabled="isGenerating || !generationPrompt.trim()">
                    <IconAnimateSpin v-if="isGenerating" class="w-5 h-5 mr-2" />
                    {{ generateButtonText }}
                </button>
                <button v-if="selectedImageIds.size > 0" @click="clearSelection" class="btn btn-secondary w-full">
                    Clear Selection ({{ selectedImageIds.size }})
                </button>
            </div>
            <div class="mt-4 p-4 border-t dark:border-gray-700">
                <label for="upload-image" class="btn btn-secondary w-full">
                    <IconArrowUpTray class="w-5 h-5 mr-2" />
                    Upload Image
                </label>
                <input type="file" id="upload-image" @change="handleUpload" class="hidden" accept="image/*" />
            </div>
        </template>
        <template #main>
            <div class="h-full overflow-y-auto p-6">
                <div v-if="isLoading" class="text-center py-20">
                    <IconAnimateSpin class="w-10 h-10 mx-auto text-gray-400" />
                    <p class="mt-2 text-sm text-gray-500">Loading images...</p>
                </div>
                <div v-else-if="images.length === 0" class="text-center py-20">
                    <IconPhoto class="w-16 h-16 mx-auto text-gray-300 dark:text-gray-600" />
                    <h3 class="mt-4 text-lg font-semibold">Your gallery is empty</h3>
                    <p class="mt-1 text-sm text-gray-500">Generate or upload your first image to get started.</p>
                </div>
                <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                    <div v-for="(image, index) in images" :key="image.id" 
                         class="relative group aspect-square bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden cursor-pointer" 
                         @click="toggleSelection(image.id)">
                        <AuthenticatedImage :src="`/api/image-studio/${image.id}/file`" class="w-full h-full object-cover transition-transform group-hover:scale-105" :class="{'ring-4 ring-blue-500 ring-inset': isSelected(image.id)}" />
                        <div class="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent"></div>
                        <div class="absolute top-2 right-2 flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button @click.stop="openInpaintingEditor(image)" class="p-1.5 bg-white/20 rounded-full hover:bg-white/40 text-white" title="Inpaint/Edit Image">
                                <IconPencil class="w-4 h-4" />
                            </button>
                            <button @click.stop="openImageViewer(index)" class="p-1.5 bg-white/20 rounded-full hover:bg-white/40 text-white" title="View image">
                                <IconMaximize class="w-4 h-4" />
                            </button>
                        </div>
                        <div class="absolute bottom-2 left-2 right-2 text-white">
                            <p class="text-xs font-mono line-clamp-2 opacity-0 group-hover:opacity-100 transition-opacity" :title="image.prompt">{{ image.prompt }}</p>
                            <div class="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button @click.stop="handleMoveToDiscussion(image)" class="p-1.5 bg-white/20 rounded-full hover:bg-white/40" title="Move to active discussion">
                                    <IconSend class="w-4 h-4" />
                                </button>
                                <button @click.stop="handleDelete(image)" class="p-1.5 bg-red-500/80 rounded-full hover:bg-red-600" title="Delete image">
                                    <IconTrash class="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                        <div v-if="isSelected(image.id)" class="absolute top-2 left-2 w-6 h-6 bg-blue-500 rounded-full border-2 border-white flex items-center justify-center">
                            <IconCheckCircle class="w-4 h-4 text-white" />
                        </div>
                    </div>
                </div>
            </div>
        </template>
    </PageViewLayout>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useImageStore } from '../stores/images';
import { useDataStore } from '../stores/data';
import { useUiStore } from '../stores/ui';
import { useAuthStore } from '../stores/auth';
import { useDiscussionsStore } from '../stores/discussions';

import PageViewLayout from '../components/layout/PageViewLayout.vue';
import AuthenticatedImage from '../components/ui/AuthenticatedImage.vue';
import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconAnimateSpin from '../assets/icons/IconAnimateSpin.vue';
import IconArrowUpTray from '../assets/icons/IconArrowUpTray.vue';
import IconTrash from '../assets/icons/IconTrash.vue';
import IconSend from '../assets/icons/IconSend.vue';
import IconMaximize from '../assets/icons/IconMaximize.vue';
import IconCheckCircle from '../assets/icons/IconCheckCircle.vue';
import IconPencil from '../assets/icons/IconPencil.vue';

const imageStore = useImageStore();
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const discussionsStore = useDiscussionsStore();

const { images, isLoading, isGenerating } = storeToRefs(imageStore);
const { availableTtiModelsGrouped, isLoadingTtiModels } = storeToRefs(dataStore);
const { user } = storeToRefs(authStore);

const generationPrompt = ref('');
const numberOfImages = ref(1);
const selectedTtiModel = ref(user.value?.tti_binding_model_name || '');
const selectedImageIds = ref(new Set());

const isSelected = (id) => selectedImageIds.value.has(id);

const generateButtonText = computed(() => {
    if (isGenerating.value) return 'Generating...';
    if (selectedImageIds.value.size > 0) return `Edit ${selectedImageIds.value.size} Image(s)`;
    return 'Generate';
});

function toggleSelection(imageId) {
    if (selectedImageIds.value.has(imageId)) {
        selectedImageIds.value.delete(imageId);
    } else {
        selectedImageIds.value.add(imageId);
    }
}

function clearSelection() {
    selectedImageIds.value.clear();
}

onMounted(() => {
    imageStore.fetchImages();
    if (dataStore.availableTtiModels.length === 0) {
        dataStore.fetchAvailableTtiModels();
    }
});

function handleGenerate() {
    if (selectedImageIds.value.size > 0) {
        imageStore.editImage({
            image_ids: Array.from(selectedImageIds.value),
            prompt: generationPrompt.value,
            model: selectedTtiModel.value
        });
        clearSelection();
    } else {
        imageStore.generateImage({
            prompt: generationPrompt.value,
            model: selectedTtiModel.value,
            n: numberOfImages.value
        });
    }
}

function handleUpload(event) {
    const file = event.target.files[0];
    if (file) {
        imageStore.uploadImage(file);
    }
}

async function handleDelete(image) {
    const confirmed = await uiStore.showConfirmation({
        title: 'Delete Image',
        message: 'Are you sure you want to permanently delete this image?',
        confirmText: 'Delete'
    });
    if (confirmed.confirmed) {
        imageStore.deleteImage(image.id);
    }
}

function handleMoveToDiscussion(image) {
    if (!discussionsStore.currentDiscussionId) {
        uiStore.addNotification('Please select a discussion first.', 'warning');
        return;
    }
    imageStore.moveImageToDiscussion(image.id, discussionsStore.currentDiscussionId);
}

function openImageViewer(index) {
    uiStore.openImageViewer({
        imageList: images.value.map(img => ({
            ...img,
            src: `/api/image-studio/${img.id}/file`
        })),
        startIndex: index
    });
}

function openInpaintingEditor(image) {
    uiStore.openModal('inpaintingEditor', { image });
}
</script>
