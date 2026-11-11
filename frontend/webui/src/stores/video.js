// frontend/webui/src/stores/video.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useVideoStore = defineStore('video', () => {
    const projects = ref([]);
    const isLoading = ref(false);
    const capabilities = ref({ ttv_available: false, tti_available: false });
    const activeProjectId = ref(null);

    const activeProject = computed(() =>
        projects.value.find(p => p.id === activeProjectId.value) || null
    );

    async function fetchProjects() {
        isLoading.value = true;
        try {
            const { data } = await apiClient.get('/api/video-studio/projects');
            projects.value = Array.isArray(data) ? data : [];
        } catch (e) {
            console.error('Failed to load video projects:', e);
        } finally {
            isLoading.value = false;
        }
    }

    async function fetchCapabilities() {
        try {
            const { data } = await apiClient.get('/api/video-studio/capabilities');
            capabilities.value = data || { ttv_available: false, tti_available: false };
        } catch (e) {
            capabilities.value = { ttv_available: false, tti_available: false };
        }
    }

    async function createProject(payload) {
        const { data } = await apiClient.post('/api/video-studio/projects', payload);
        projects.value.unshift(data);
        activeProjectId.value = data.id;
        return data;
    }

    async function updateProject(id, payload) {
        const { data } = await apiClient.put(`/api/video-studio/projects/${id}`, payload);
        const idx = projects.value.findIndex(p => p.id === id);
        if (idx !== -1) projects.value[idx] = data;
        return data;
    }

    async function deleteProject(id) {
        await apiClient.delete(`/api/video-studio/projects/${id}`);
        projects.value = projects.value.filter(p => p.id !== id);
        if (activeProjectId.value === id) activeProjectId.value = null;
    }

    async function renderProject(id, modelOverride = null) {
        const form = new FormData();
        if (modelOverride) form.append('model_override', modelOverride);
        const { data } = await apiClient.post(`/api/video-studio/projects/${id}/render`, form);
        return data;
    }

    async function uploadFirstImage(id, file) {
        const form = new FormData();
        form.append('file', file);
        const { data } = await apiClient.post(`/api/video-studio/projects/${id}/first-image`, form);
        return data;
    }

    async function uploadLastImage(id, file) {
        const form = new FormData();
        form.append('file', file);
        const { data } = await apiClient.post(`/api/video-studio/projects/${id}/last-image`, form);
        return data;
    }

    async function generateReferenceImage(payload) {
        const { data } = await apiClient.post('/api/video-studio/generate-image', payload);
        return data.b64_image;
    }

    async function downloadVideo(project) {
        if (!project?.video_filename) {
            const ui = useUiStore();
            ui.addNotification('Render the video before downloading.', 'warning');
            return;
        }
        try {
            const res = await apiClient.get(`/api/video-studio/projects/${project.id}/video`, { responseType: 'blob' });
            const url = URL.createObjectURL(res.data);
            const link = document.createElement('a');
            link.href = url;
            link.download = `${project.title || 'video'}.mp4`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error('Download failed:', e);
        }
    }

    return {
        projects, isLoading, capabilities, activeProjectId, activeProject,
        fetchProjects, fetchCapabilities, createProject, updateProject, deleteProject,
        renderProject, uploadFirstImage, uploadLastImage, generateReferenceImage,
        downloadVideo,
    };
});