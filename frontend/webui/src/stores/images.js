// [UPDATE] frontend/webui/src/stores/images.js
import { defineStore } from 'pinia';
import { ref, onMounted, onUnmounted, watch } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useTasksStore } from './tasks';
import { useAuthStore } from './auth';
import useEventBus from '../services/eventBus';

export const useImageStore = defineStore('images', () => {
    const images = ref([]);
    const isLoading = ref(false);
    const isGenerating = ref(false); 
    const isEnhancing = ref(false);
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();
    const authStore = useAuthStore();
    const { on, off, emit } = useEventBus();

    // --- State for Image Studio ---
    const prompt = ref('');
    const negativePrompt = ref('');
    const imageSize = ref('1024x1024');
    const nImages = ref(1);
    const seed = ref(-1);
    const generationParams = ref({});
    
    let saveDebounceTimer = null;

    watch(() => authStore.user, (newUser) => {
        if (newUser) {
            prompt.value = newUser.image_studio_prompt || '';
            negativePrompt.value = newUser.image_studio_negative_prompt || '';
            imageSize.value = newUser.image_studio_image_size || '1024x1024';
            nImages.value = newUser.image_studio_n_images || 1;
            seed.value = newUser.image_studio_seed ?? -1;
            generationParams.value = newUser.image_studio_generation_params || {};
        }
    }, { immediate: true });

    watch([prompt, negativePrompt, imageSize, nImages, seed, generationParams], () => {
        if (!authStore.isAuthenticated) return;
        
        clearTimeout(saveDebounceTimer);
        saveDebounceTimer = setTimeout(() => {
            const payload = {
                image_studio_prompt: prompt.value,
                image_studio_negative_prompt: negativePrompt.value,
                image_studio_image_size: imageSize.value,
                image_studio_n_images: nImages.value,
                image_studio_seed: seed.value,
                image_studio_generation_params: generationParams.value,
            };
            authStore.updateUserPreferences(payload);
        }, 1500); 
    }, { deep: true });

    function handleTaskCompletion(task) {
        // Safe parsing of the result
        let result = task.result;
        if (typeof result === 'string') {
            try {
                result = JSON.parse(result);
            } catch (e) {
                console.error("Failed to parse task result JSON:", e);
                // If parsing fails but it's an enhancement task, it might just be the text prompt directly?
                // But normally our backend returns JSON. Proceeding with raw string if parse fails.
            }
        }

        const isImageTask = task.name.startsWith('Generating') && task.name.includes('image(s)');
        const isEditTask = task.name.startsWith('Editing image:');
        const isEnhanceTask = task.name.startsWith('Enhancing prompt:');

        if (isEnhanceTask) {
            if (task.status === 'completed' && result) {
                // Update state directly
                if (result.prompt) prompt.value = result.prompt;
                if (result.negative_prompt) negativePrompt.value = result.negative_prompt;
                
                emit('prompt:enhanced', result);
                uiStore.addNotification('Prompt enhanced successfully!', 'success');
            } else if (task.status === 'failed') {
                uiStore.addNotification('Prompt enhancement failed.', 'error');
            }
            isEnhancing.value = false;
            return;
        }

        if ((isImageTask || isEditTask) && task.status === 'completed' && result) {
            const newItems = Array.isArray(result) ? result : [result];
            
            if (newItems.length > 0 && newItems[0]) {
                const reversedNewItems = [...newItems].reverse();
                // Add to the beginning of the list
                images.value.unshift(...reversedNewItems);
                uiStore.addNotification(`${newItems.length} new image(s) added.`, 'success');
            }
        } else if ((isImageTask || isEditTask) && task.status === 'failed') {
            uiStore.addNotification('Image generation failed. Check task manager for details.', 'error');
        }
    }

    onMounted(() => {
        on('task:completed', handleTaskCompletion);
    });

    onUnmounted(() => {
        off('task:completed', handleTaskCompletion);
    });

    async function fetchImages() {
        isLoading.value = true;
        try {
            const response = await apiClient.get('/api/image-studio');
            images.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error("Failed to fetch images:", error);
            images.value = [];
        } finally {
            isLoading.value = false;
        }
    }

    async function generateImage(payload) {
        isGenerating.value = true;
        try {
            const response = await apiClient.post('/api/image-studio/generate', payload);
            tasksStore.addTask(response.data);
            uiStore.addNotification(`Image generation started for ${payload.n} image(s). Check task manager for progress.`, 'info');
            return response.data;
        } finally {
            isGenerating.value = false;
        }
    }

    async function editImage(payload) {
        isGenerating.value = true;
        try {
            const response = await apiClient.post('/api/image-studio/edit', payload);
            tasksStore.addTask(response.data);
            uiStore.addNotification('Image edit task started. Check task manager for progress.', 'info');
            return response.data;
        } finally {
            isGenerating.value = false;
        }
    }

    async function saveCanvasAsNewImage(payload) {
        isGenerating.value = true;
        try {
            const response = await apiClient.post('/api/image-studio/save-canvas', payload);
            images.value.unshift(response.data);
            uiStore.addNotification('Image saved successfully!', 'success');
            return response.data;
        } catch (error) {
            // Error is handled globally
            return null;
        } finally {
            isGenerating.value = false;
        }
    }

    async function uploadImages(files) {
        if (!Array.isArray(files) || files.length === 0) return;

        const formData = new FormData();
        files.forEach(file => {
            formData.append('files', file);
        });

        isGenerating.value = true;
        try {
            const response = await apiClient.post('/api/image-studio/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            if (Array.isArray(response.data) && response.data.length > 0) {
                images.value.unshift(...response.data.reverse());
                uiStore.addNotification(`${response.data.length} image(s) uploaded successfully!`, 'success');
            }
        } catch (error) {
            // Handled globally
        } finally {
            isGenerating.value = false;
        }
    }

    async function deleteImage(imageId) {
        try {
            await apiClient.delete(`/api/image-studio/${imageId}`);
            images.value = images.value.filter(img => img.id !== imageId);
            uiStore.addNotification('Image deleted.', 'success');
        } catch (error) {
            // Handled globally
        }
    }

    async function moveImageToDiscussion(imageId, discussionId) {
        try {
            await apiClient.post(`/api/image-studio/${imageId}/move-to-discussion`, {
                discussion_id: discussionId
            });
            uiStore.addNotification('Image added to the active discussion.', 'success');
        } catch (error) {
            // Handled globally
        }
    }

    async function enhanceImagePrompt(payload) {
        isEnhancing.value = true;
        try {
            const response = await apiClient.post('/api/image-studio/enhance-prompt', payload);
            tasksStore.addTask(response.data);
            uiStore.addNotification('Prompt enhancement started...', 'info');
            return response.data;
        } catch (error) {
            isEnhancing.value = false;
            // Handled globally
            return null;
        }
    }

    return {
        images,
        isLoading,
        isGenerating,
        isEnhancing,
        // Persistent state
        prompt,
        negativePrompt,
        imageSize,
        nImages,
        seed,
        generationParams,
        // Actions
        fetchImages,
        generateImage,
        editImage,
        saveCanvasAsNewImage,
        uploadImages,
        deleteImage,
        moveImageToDiscussion,
        enhanceImagePrompt,
    };
});
