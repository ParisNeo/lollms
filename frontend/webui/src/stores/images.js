import { defineStore } from 'pinia';
import { ref, watch } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useTasksStore } from './tasks';
import { useAuthStore } from './auth';
import useEventBus from '../services/eventBus';

export const useImageStore = defineStore('images', () => {
    const images = ref([]);
    const albums = ref([]);
    const selectedAlbumId = ref(null);
    const isLoading = ref(false);
    const isGenerating = ref(false);

    // --- Pagination State ---
    const currentPage = ref(1);
    const pageSize = ref(30);
    const totalImages = ref(0);
    const totalPages = ref(1);
    const searchQuery = ref('');
    
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();
    const authStore = useAuthStore();
    const { on, emit } = useEventBus();

    // --- State for Image Studio ---
    const prompt = ref('');
    const negativePrompt = ref('');
    const imageSize = ref('1024x1024');
    const nImages = ref(1);
    const seed = ref(-1);
    const generationParams = ref({});
    
    let saveDebounceTimer = null;

    // --- ACTIONS & METHODS (Declared BEFORE watchers & event listeners) ---
    async function fetchAlbums() {
        try {
            const response = await apiClient.get('/api/image-studio/albums');
            albums.value = response.data;
        } catch (error) {
            console.error("Failed to fetch albums:", error);
        }
    }

    async function createAlbum(name) {
        try {
            const response = await apiClient.post('/api/image-studio/albums', { name });
            albums.value.unshift(response.data);
            uiStore.addNotification(`Album '${name}' created.`, 'success');
            return response.data;
        } catch (error) {
            uiStore.addNotification('Failed to create album.', 'error');
        }
    }

    async function updateAlbum(id, name) {
        try {
            const response = await apiClient.put(`/api/image-studio/albums/${id}`, { name });
            const index = albums.value.findIndex(a => a.id === id);
            if (index !== -1) albums.value[index] = response.data;
            uiStore.addNotification('Album renamed.', 'success');
        } catch (error) {
            uiStore.addNotification('Failed to update album.', 'error');
        }
    }

    async function deleteAlbum(id) {
        try {
            await apiClient.delete(`/api/image-studio/albums/${id}`);
            albums.value = albums.value.filter(a => a.id !== id);
            if (selectedAlbumId.value === id) selectedAlbumId.value = null;
            fetchImages(); 
            uiStore.addNotification('Album deleted.', 'success');
        } catch (error) {
            uiStore.addNotification('Failed to delete album.', 'error');
        }
    }

    async function moveImageToAlbum(imageId, albumId) {
        try {
            await apiClient.put(`/api/image-studio/images/${imageId}/album`, { album_id: albumId });
            const imgIndex = images.value.findIndex(i => i.id === imageId);
            if (imgIndex !== -1) {
                images.value[imgIndex].album_id = albumId;
                if (selectedAlbumId.value && selectedAlbumId.value !== albumId) {
                    images.value.splice(imgIndex, 1);
                }
            }
            uiStore.addNotification('Image moved.', 'success');
        } catch (error) {
            uiStore.addNotification('Failed to move image.', 'error');
        }
    }

    async function fetchImages(page = 1, append = false) {
        isLoading.value = true;
        currentPage.value = page;
        try {
            const params = {
                page: page,
                page_size: pageSize.value
            };
            if (selectedAlbumId.value) params.album_id = selectedAlbumId.value;
            if (searchQuery.value && searchQuery.value.trim()) params.search = searchQuery.value.trim();
            
            const response = await apiClient.get('/api/image-studio', { params });
            const data = response.data;

            if (data && Array.isArray(data.items)) {
                totalImages.value = data.total;
                totalPages.value = data.total_pages;
                currentPage.value = data.page;
                
                if (append) {
                    const existingIds = new Set(images.value.map(i => i.id));
                    const newItems = data.items.filter(i => !existingIds.has(i.id));
                    images.value.push(...newItems);
                } else {
                    images.value = data.items;
                }
            } else if (Array.isArray(data)) {
                images.value = data;
                totalImages.value = data.length;
                totalPages.value = 1;
            }
        } catch (error) {
            console.error("Failed to fetch images:", error);
            if (!append) images.value = [];
        } finally {
            isLoading.value = false;
        }
    }

    async function generateImage(payload) {
        isGenerating.value = true;
        try {
            const response = await apiClient.post('/api/image-studio/generate', payload);
            tasksStore.addTask(response.data);
            uiStore.addNotification(`Image generation started for ${payload.n} image(s).`, 'info');
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
            uiStore.addNotification('Image edit task started...', 'info');
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
        
        if (selectedAlbumId.value) {
            formData.append('album_id', selectedAlbumId.value);
        }

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

    async function downloadBatch(imageIds) {
        if (!imageIds || imageIds.length === 0) return;
        uiStore.addNotification(`Preparing ZIP for ${imageIds.length} image(s)...`, 'info');
        try {
            const response = await apiClient.post('/api/image-studio/download-batch', {
                image_ids: imageIds
            }, { responseType: 'blob' });

            const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/zip' }));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `lollms_gallery_${Date.now()}.zip`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
            uiStore.addNotification('Download started.', 'success');
        } catch (error) {
            console.error("Batch download failed:", error);
            uiStore.addNotification('Failed to download batch.', 'error');
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

    async function moveImagesToDiscussionBatch(imageIds, discussionId) {
        try {
            const response = await apiClient.post(`/api/image-studio/move-to-discussion-batch`, {
                image_ids: imageIds,
                discussion_id: discussionId
            });
            uiStore.addNotification(response.data.message || 'Images added to discussion.', 'success');
        } catch (error) {
            console.error("Batch move failed:", error);
            uiStore.addNotification('Failed to send images to discussion.', 'error');
        }
    }

    async function enhanceImagePrompt(payload) {
        try {
            const response = await apiClient.post('/api/image-studio/enhance-prompt', payload);
            const task = response.data;
            tasksStore.addTask(task);
            return task;
        } catch (error) {
            console.error("Enhancement request failed", error);
            throw error;
        }
    }

    // --- WATCHERS & EVENT LISTENERS (Attached AFTER functions are defined) ---
    function handleTaskCompletion(task) {
        let result = task.result;
        if (typeof result === 'string') {
            try { result = JSON.parse(result); } catch (e) {}
        }

        const isImageTask = task.name && task.name.startsWith('Generating') && task.name.includes('image(s)');
        const isEditTask = task.name && task.name.startsWith('Editing image:');
        
        if ((isImageTask || isEditTask) && task.status === 'completed' && result) {
            const newItems = Array.isArray(result) ? result : [result];
            if (newItems.length > 0 && newItems[0]) {
                const reversedNewItems = [...newItems].reverse();
                images.value.unshift(...reversedNewItems);
                emit('image:generated', reversedNewItems[0]); 
                uiStore.addNotification(`${newItems.length} new image(s) added.`, 'success');
            }
        } else if ((isImageTask || isEditTask) && task.status === 'failed') {
            uiStore.addNotification('Image generation failed. Check task manager for details.', 'error');
        }
    }

    on('task:completed', handleTaskCompletion);

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

    return {
        images,
        albums,
        selectedAlbumId,
        isLoading,
        isGenerating,
        currentPage,
        pageSize,
        totalImages,
        totalPages,
        searchQuery,
        prompt,
        negativePrompt,
        imageSize,
        nImages,
        seed,
        generationParams,
        fetchAlbums,
        createAlbum,
        updateAlbum,
        deleteAlbum,
        moveImageToAlbum,
        fetchImages,
        generateImage,
        editImage,
        saveCanvasAsNewImage,
        uploadImages,
        deleteImage,
        downloadBatch,
        moveImageToDiscussion,
        moveImagesToDiscussionBatch,
        enhanceImagePrompt,
    };
});