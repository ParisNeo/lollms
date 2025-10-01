import { defineStore } from 'pinia';
import { ref } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';
import useEventBus from '../services/eventBus';

export const useVoicesStore = defineStore('voices', () => {
    const voices = ref([]);
    const isLoading = ref(false);
    const uiStore = useUiStore();
    const authStore = useAuthStore();
    const { emit } = useEventBus();

    async function fetchVoices() {
        isLoading.value = true;
        try {
            const response = await apiClient.get('/api/voices-studio');
            voices.value = response.data;
        } catch (error) {
            console.error("Failed to fetch voices:", error);
            voices.value = [];
        } finally {
            isLoading.value = false;
        }
    }

    async function fetchVoiceAudio(voiceId) {
        try {
            const response = await apiClient.get(`/api/voices-studio/${voiceId}/audio`, {
                responseType: 'blob'
            });
            return URL.createObjectURL(response.data);
        } catch (error) {
            console.error(`Failed to fetch audio for voice ${voiceId}:`, error);
            uiStore.addNotification('Could not load voice audio.', 'error');
            return null;
        }
    }

    async function uploadVoice(formData) {
        try {
            const response = await apiClient.post('/api/voices-studio/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            voices.value.push(response.data);
            emit('user-voices-changed');
            uiStore.addNotification('Voice created successfully!', 'success');
            return response.data;
        } catch (error) {
            // Handled globally
        }
    }

    async function updateVoice(voiceId, formData) {
        try {
            const response = await apiClient.put(`/api/voices-studio/${voiceId}`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            const index = voices.value.findIndex(v => v.id === voiceId);
            if (index !== -1) {
                voices.value[index] = response.data;
            }
            emit('user-voices-changed');
            uiStore.addNotification('Voice updated successfully!', 'success');
        } catch (error) {
            // Handled globally
        }
    }

    async function replaceVoiceAudio(voiceId, audioBlob) {
        const formData = new FormData();
        formData.append('file', audioBlob, 'new_reference.wav');
        try {
            await apiClient.post(`/api/voices-studio/${voiceId}/replace_audio`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            await fetchVoices();
            emit('user-voices-changed');
            uiStore.addNotification('Voice reference audio updated.', 'success');
        } catch (error) {
            // Handled globally
        }
    }

    async function deleteVoice(voiceId) {
        try {
            await apiClient.delete(`/api/voices-studio/${voiceId}`);
            voices.value = voices.value.filter(v => v.id !== voiceId);
            emit('user-voices-changed');
            uiStore.addNotification('Voice deleted.', 'success');
        } catch (error) {
            // Handled globally
        }
    }

    async function setActiveVoice(voiceId) {
        try {
            const response = await apiClient.post(`/api/voices-studio/set-active/${voiceId}`);
            if (authStore.user) {
                authStore.user.active_voice_id = response.data.active_voice_id;
            }
            uiStore.addNotification('Active voice set.', 'success');
        } catch (error) {
            // Handled globally
        }
    }

    async function testVoice(payload) {
        try {
            const response = await apiClient.post('/api/voices-studio/test', payload);
            return response.data;
        } catch (error) {
            return null;
        }
    }

    async function applyEffects(payload) {
        try {
            const response = await apiClient.post('/api/voices-studio/apply-effects', payload);
            return response.data;
        } catch (error) {
            return null;
        }
    }

    async function duplicateVoice(voiceId) {
        try {
            const response = await apiClient.post(`/api/voices-studio/${voiceId}/duplicate`);
            voices.value.push(response.data);
            emit('user-voices-changed');
            uiStore.addNotification('Voice duplicated!', 'success');
        } catch (error) {
            // Handled globally
        }
    }

    return {
        voices,
        isLoading,
        fetchVoices,
        fetchVoiceAudio,
        uploadVoice,
        updateVoice,
        replaceVoiceAudio,
        deleteVoice,
        setActiveVoice,
        testVoice,
        applyEffects,
        duplicateVoice,
    };
});