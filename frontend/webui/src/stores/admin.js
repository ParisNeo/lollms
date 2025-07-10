import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useAdminStore = defineStore('admin', () => {
    const uiStore = useUiStore();

    // --- STATE ---
    const allUsers = ref([]);
    const globalSettings = ref([]);
    const isLoadingUsers = ref(false);
    const isLoadingSettings = ref(false);
    const isImporting = ref(false);

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
    async function sendEmailToAllUsers(subject, body) {
        try {
            const response = await apiClient.post('/api/admin/email-all-users', { subject, body });
            uiStore.addNotification(response.data.message, 'success');
        } catch (error) {
            throw error;
        }
    }

    return {
        // State
        allUsers, globalSettings, isLoadingUsers, isLoadingSettings, isImporting,
        // Getters
        settingsByCategory, isSmtpConfigured,
        // Actions
        fetchAllUsers, fetchGlobalSettings, updateGlobalSettings, importOpenWebUIData, sendEmailToAllUsers
    };
});