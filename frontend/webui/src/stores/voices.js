// frontend/webui/src/stores/voices.js
import { defineStore } from 'pinia';
import { ref } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';

export const useVoicesStore = defineStore('voices', () => {
    const uiStore = useUiStore();
    const authStore = useAuthStore();

    const voices = ref([]);
    const isLoading = ref(false);

    async function fetchVoices() {
        isLoading.value = true;
        try {
            const response = await apiClient.get('/api/voices-studio');
            voices.value = response.data;
        } catch (error) {
            console.error("Failed to fetch voices:", error);
            uiStore.addNotification('Could not load your voices.', 'error');
        } finally {
            isLoading.value = false;
        }
    }

    async function uploadVoice(formData) {
        try {
            const response = await apiClient.post('/api/voices-studio/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            voices.value.push(response.data);
            uiStore.addNotification(`Voice '${response.data.alias}' uploaded successfully.`, 'success');
        } catch (error) {
            throw error;
        }
    }
    
    async function updateVoice(voiceId, formData) {
        try {
            const response = await apiClient.put(`/api/voices-studio/${voiceId}`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            const index = voices.value.findIndex(v => v.id === voiceId);
            if (index !== -1) {
                voices.value[index] = response.data;
            }
            uiStore.addNotification(`Voice '${response.data.alias}' updated successfully.`, 'success');
        } catch (error) {
            throw error;
        }
    }

    async function deleteVoice(voiceId) {
        try {
            await apiClient.delete(`/api/voices-studio/${voiceId}`);
            voices.value = voices.value.filter(v => v.id !== voiceId);
            uiStore.addNotification('Voice deleted successfully.', 'success');
        } catch (error) {
            // Error handled by global interceptor
        }
    }

    async function setActiveVoice(voiceId) {
        try {
            await apiClient.post(`/api/voices-studio/set-active/${voiceId}`);
            await authStore.refreshUser(); 
            uiStore.addNotification('Active voice set successfully.', 'success');
        } catch (error) {
            // Error handled by global interceptor
        }
    }

    async function testVoice(payload) {
        try {
            const response = await apiClient.post('/api/voices-studio/test', payload);
            return response.data; // Now returns { audio_b64: "..." }
        } catch (error) {
            uiStore.addNotification('Failed to generate test audio.', 'error');
            return null;
        }
    }

    async function duplicateVoice(voiceId) {
        try {
            const response = await apiClient.post(`/api/voices-studio/${voiceId}/duplicate`);
            voices.value.push(response.data);
            uiStore.addNotification(`Voice duplicated successfully.`, 'success');
        } catch (error) {
            // Handled globally
        }
    }

    async function applyEffects(payload) {
        try {
            const response = await apiClient.post('/api/voices-studio/apply-effects', payload);
            return response.data; // { audio_b64: "..." }
        } catch (error) {
            uiStore.addNotification('Failed to apply effects to audio.', 'error');
            throw error;
        }
    }

    return {
        voices,
        isLoading,
        fetchVoices,
        uploadVoice,
        updateVoice,
        deleteVoice,
        setActiveVoice,
        testVoice,
        duplicateVoice,
        applyEffects
    };
});