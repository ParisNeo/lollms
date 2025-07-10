import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useDataStore } from './data';

export const useAdminStore = defineStore('admin', () => {
    const uiStore = useUiStore();
    const dataStore = useDataStore();

    // --- STATE ---
    const allUsers = ref([]);
    const globalSettings = ref([]);
    const bindings = ref([]);
    const availableBindingTypes = ref([]);
    const isLoadingUsers = ref(false);
    const isLoadingSettings = ref(false);
    const isLoadingBindings = ref(false);
    const isImporting = ref(false);
    const isEnhancingEmail = ref(false);

    // --- GETTERS ---
    const settingsByCategory = computed(() => {
        if (!globalSettings.value.length) return {};
        return globalSettings.value.reduce((acc, setting) => {
            const category = setting.category || 'General';
            if (!acc[category]) {
                acc[category] = [];
            }
            acc[category].push(setting);
            return acc;
        }, {});
    });

    const isSmtpConfigured = computed(() => {
        const smtpHostSetting = globalSettings.value.find(s => s.key === 'smtp_host');
        return smtpHostSetting && smtpHostSetting.value;
    });

    // --- ACTIONS ---

    // -- Bindings Management --
    async function fetchBindings() {
        isLoadingBindings.value = true;
        try {
            const response = await apiClient.get('/api/admin/bindings');
            bindings.value = response.data;
        } catch (error) {
            uiStore.addNotification('Failed to fetch LLM bindings.', 'error');
        } finally {
            isLoadingBindings.value = false;
        }
    }

    async function fetchAvailableBindingTypes() {
        try {
            const response = await apiClient.get('/api/admin/bindings/available_types');
            availableBindingTypes.value = response.data;
        } catch (error) {
            uiStore.addNotification('Failed to fetch available binding types.', 'error');
        }
    }
    
    async function addBinding(bindingData) {
        try {
            await apiClient.post('/api/admin/bindings', bindingData);
            uiStore.addNotification('Binding created successfully.', 'success');
            await fetchBindings();
            await dataStore.fetchAvailableLollmsModels();
        } catch (error) {
            throw error;
        }
    }
    
    async function updateBinding(bindingId, updateData) {
        try {
            await apiClient.put(`/api/admin/bindings/${bindingId}`, updateData);
            uiStore.addNotification('Binding updated successfully.', 'success');
            await fetchBindings();
            await dataStore.fetchAvailableLollmsModels();
        } catch (error) {
            throw error;
        }
    }
    
    async function deleteBinding(bindingId) {
        try {
            await apiClient.delete(`/api/admin/bindings/${bindingId}`);
            uiStore.addNotification('Binding deleted successfully.', 'success');
            await fetchBindings();
            await dataStore.fetchAvailableLollmsModels();
        } catch (error) {
            throw error;
        }
    }


    // -- User Management --
    async function fetchAllUsers() {
        isLoadingUsers.value = true;
        try {
            const response = await apiClient.get('/api/admin/users');
            allUsers.value = response.data;
        } catch (error) {
            uiStore.addNotification('Failed to fetch users.', 'error');
            allUsers.value = [];
        } finally {
            isLoadingUsers.value = false;
        }
    }

    // -- Global Settings --
    async function fetchGlobalSettings() {
        isLoadingSettings.value = true;
        try {
            const response = await apiClient.get('/api/admin/settings');
            globalSettings.value = response.data;
        } catch (error) {
            uiStore.addNotification('Failed to load global settings.', 'error');
            globalSettings.value = [];
        } finally {
            isLoadingSettings.value = false;
        }
    }

    async function updateGlobalSettings(configsToUpdate) {
        isLoadingSettings.value = true;
        try {
            await apiClient.put('/api/admin/settings', { configs: configsToUpdate });
            await fetchGlobalSettings(); // Re-fetch to ensure consistency
            uiStore.addNotification('Global settings updated successfully.', 'success');
        } catch (error) {
            throw error;
        } finally {
            isLoadingSettings.value = false;
        }
    }
    
    // -- Data Import --
    async function importOpenWebUIData(file) {
        isImporting.value = true;
        const formData = new FormData();
        formData.append('file', file);
        try {
            const response = await apiClient.post('/api/admin/import-openwebui', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            uiStore.addNotification(response.data.message, 'info', 6000);
        } catch (error) {
            throw error;
        } finally {
            isImporting.value = false;
        }
    }


    // -- Mass Email --
    async function sendEmailToUsers(subject, body, userIds, backgroundColor, sendAsText = false) {
        try {
            const response = await apiClient.post('/api/admin/email-users', { 
                subject, 
                body, 
                user_ids: userIds,
                background_color: backgroundColor,
                send_as_text: sendAsText
            });
            uiStore.addNotification(response.data.message, 'success');
        } catch (error) {
            throw error;
        }
    }

    async function enhanceEmail(subject, body, backgroundColor, customPrompt = '') {
        isEnhancingEmail.value = true;
        try {
            const response = await apiClient.post('/api/admin/enhance-email', {
                subject: subject,
                body: body,
                background_color: backgroundColor,
                prompt: customPrompt
            });
            uiStore.addNotification('Email content enhanced by AI.', 'success');
            return response.data;
        } catch (error) {
            // Global handler will show the notification
            throw error;
        } finally {
            isEnhancingEmail.value = false;
        }
    }

    return {
        // State
        allUsers, globalSettings, bindings, availableBindingTypes, 
        isLoadingUsers, isLoadingSettings, isLoadingBindings, isImporting, isEnhancingEmail,
        // Getters
        settingsByCategory, isSmtpConfigured,
        // Actions
        fetchAllUsers, fetchGlobalSettings, updateGlobalSettings, 
        importOpenWebUIData, sendEmailToUsers, enhanceEmail,
        fetchBindings, fetchAvailableBindingTypes, addBinding, updateBinding, deleteBinding
    };
});