// frontend/webui/src/stores/images.js
import { defineStore } from 'pinia';
import { ref } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useImageStore = defineStore('images', () => {
    const images = ref([]);
    const isLoading = ref(false);
    const isGenerating = ref(false);
    const isEnhancing = ref(false);
    const uiStore = useUiStore();

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
            if (Array.isArray(response.data)) {
                images.value.unshift(...response.data);
            }
            uiStore.addNotification(`${response.data?.length || 0} image(s) generated successfully!`, 'success');
        } catch (error) {
            // Handled globally
        } finally {
            isGenerating.value = false;
        }
    }

    async function editImage(payload) {
        isGenerating.value = true;
        try {
            const response = await apiClient.post('/api/image-studio/edit', payload);
            if (response.data) {
                images.value.unshift(response.data);
            }
            uiStore.addNotification(`Image edited successfully!`, 'success');
        } catch (error) {
            // Handled by global interceptor
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
            uiStore.addNotification('Prompt enhanced successfully!', 'success');
            return response.data;
        } catch (error) {
            // Handled globally
            return null;
        } finally {
            isEnhancing.value = false;
        }
    }

    return {
        images,
        isLoading,
        isGenerating,
        isEnhancing,
        fetchImages,
        generateImage,
        editImage,
        uploadImages,
        deleteImage,
        moveImageToDiscussion,
        enhanceImagePrompt,
    };
});