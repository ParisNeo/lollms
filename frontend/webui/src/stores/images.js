// frontend/webui/src/stores/images.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useTasksStore } from './tasks';

export const useImageStore = defineStore('images', () => {
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();

    // --- STATE ---
    const generatedImages = ref([]);
    const isLoadingImages = ref(false);
    const isLoadingGeneration = ref(false);

    // --- COMPUTED ---
    // No complex computed properties needed yet, but keeping structure for future.

    // --- ACTIONS ---

    /**
     * Fetches the user's previously generated images from the server.
     */
    async function fetchGeneratedImages() {
        if (isLoadingImages.value) return;
        isLoadingImages.value = true;
        try {
            const response = await apiClient.get('/api/image-studio/generated-images');
            generatedImages.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error("Failed to fetch generated images:", error);
            generatedImages.value = [];
        } finally {
            isLoadingImages.value = false;
        }
    }

    /**
     * Initiates an image generation task on the server.
     * @param {object} payload - The generation parameters.
     */
    async function generateImage(payload) {
        if (isLoadingGeneration.value) return;
        isLoadingGeneration.value = true;
        
        try {
            const response = await apiClient.post('/api/image-studio/generate', payload);
            const task = response.data;
            tasksStore.addTask(task);
            uiStore.addNotification('Image generation task started. Check Task Manager for progress.', 'info', 7000);
        } catch (error) {
            // Error handling is mostly done by the API interceptor
            console.error("Image generation failed:", error);
        } finally {
            isLoadingGeneration.value = false;
        }
    }

    /**
     * Deletes a previously generated image file.
     * @param {string} fileName - The file name of the image to delete.
     */
    async function deleteGeneratedImage(fileName) {
        try {
            await apiClient.delete(`/api/image-studio/generated-images/${fileName}`);
            generatedImages.value = generatedImages.value.filter(img => img.file_name !== fileName);
            uiStore.addNotification('Image deleted successfully.', 'success');
        } catch (error) {
            console.error("Failed to delete image:", error);
        }
    }
    
    /**
     * Resets the store state.
     */
    function $reset() {
        generatedImages.value = [];
        isLoadingImages.value = false;
        isLoadingGeneration.value = false;
    }

    return {
        // State
        generatedImages,
        isLoadingImages,
        isLoadingGeneration,
        
        // Actions
        fetchGeneratedImages,
        generateImage,
        deleteGeneratedImage,
        
        // Reset
        $reset,
    };
});