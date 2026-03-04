import { defineStore } from 'pinia';
import { ref } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useSkillsStore = defineStore('skills', () => {
    const uiStore = useUiStore();
    
    const skills = ref([]);
    const isLoading = ref(false);

    async function fetchSkills() {
        isLoading.value = true;
        try {
            const response = await apiClient.get('/api/skills');
            skills.value = response.data;
        } catch (error) {
            console.error("Failed to fetch skills:", error);
            uiStore.addNotification('Could not load skills.', 'error');
        } finally {
            isLoading.value = false;
        }
    }

    async function createSkill(skillData) {
        try {
            const response = await apiClient.post('/api/skills', skillData);
            skills.value.push(response.data);
            skills.value.sort((a, b) => a.name.localeCompare(b.name));
            uiStore.addNotification('Skill created successfully.', 'success');
            return response.data;
        } catch (error) {
            uiStore.addNotification('Failed to create skill.', 'error');
            throw error;
        }
    }

    async function updateSkill(id, skillData) {
        try {
            const response = await apiClient.put(`/api/skills/${id}`, skillData);
            const index = skills.value.findIndex(s => s.id === id);
            if (index !== -1) {
                skills.value[index] = response.data;
                skills.value.sort((a, b) => a.name.localeCompare(b.name));
            }
            uiStore.addNotification('Skill updated successfully.', 'success');
            return response.data;
        } catch (error) {
            uiStore.addNotification('Failed to update skill.', 'error');
            throw error;
        }
    }

    async function deleteSkill(id) {
        try {
            await apiClient.delete(`/api/skills/${id}`);
            skills.value = skills.value.filter(s => s.id !== id);
            uiStore.addNotification('Skill deleted successfully.', 'success');
        } catch (error) {
            uiStore.addNotification('Failed to delete skill.', 'error');
            throw error;
        }
    }

    async function exportSkill(id, format) {
        try {
            const response = await apiClient.post(`/api/skills/${id}/export`, { format }, { responseType: 'blob' });
            const blob = new Blob([response.data]);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const contentDisposition = response.headers['content-disposition'];
            let filename = `skill_export.${format === 'xml' ? 'xml' : 'md'}`;
            if (contentDisposition) {
                const match = contentDisposition.match(/filename="([^"]+)"/);
                if (match && match[1]) filename = match[1];
            }
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            uiStore.addNotification('Export successful!', 'success');
        } catch (error) {
            uiStore.addNotification('Failed to export skill.', 'error');
        }
    }

    async function importSkill(file) {
        const formData = new FormData();
        formData.append('file', file);
        try {
            const response = await apiClient.post('/api/skills/import', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            skills.value.push(response.data);
            skills.value.sort((a, b) => a.name.localeCompare(b.name));
            uiStore.addNotification('Skill imported successfully.', 'success');
            return response.data;
        } catch (error) {
            const msg = error.response?.data?.detail || 'Failed to import skill.';
            uiStore.addNotification(msg, 'error');
            throw error;
        }
    }

    return {
        skills,
        isLoading,
        fetchSkills,
        createSkill,
        updateSkill,
        deleteSkill,
        exportSkill,
        importSkill
    };
});