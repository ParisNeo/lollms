import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';

export const useTasksStore = defineStore('tasks', () => {
    const uiStore = useUiStore();

    // --- STATE ---
    const tasks = ref([]);
    const isLoadingTasks = ref(false);
    let pollInterval = null;

    // --- COMPUTED ---
    const activeTasksCount = computed(() => {
        return tasks.value.filter(t => t.status === 'running' || t.status === 'pending').length;
    });

    // --- ACTIONS ---
    async function fetchTasks() {
        isLoadingTasks.value = true;
        try {
            const response = await apiClient.get('/api/tasks');
            tasks.value = response.data;
        } catch (error) {
            console.error("Failed to fetch tasks:", error);
            // Optionally notify user on fetch failure, but can be noisy with polling
        } finally {
            isLoadingTasks.value = false;
        }
    }

    async function cancelTask(taskId) {
        try {
            await apiClient.post(`/api/tasks/${taskId}/cancel`);
            uiStore.addNotification('Task cancellation requested.', 'info');
            await fetchTasks();
        } catch (error) {
            // Error is handled by global interceptor
        }
    }

    async function clearCompletedTasks() {
        try {
            const response = await apiClient.post('/api/tasks/clear-completed');
            uiStore.addNotification(response.data.message || 'Completed tasks cleared.', 'success');
            await fetchTasks();
        } catch (error) {
            // Error is handled by global interceptor
        }
    }

    function startPolling() {
        if (pollInterval) return; // Prevent multiple intervals
        fetchTasks(); // Initial fetch
        pollInterval = setInterval(fetchTasks, 5000); // Poll every 5 seconds
    }

    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    function $reset() {
        stopPolling();
        tasks.value = [];
        isLoadingTasks.value = false;
    }

    return {
        tasks,
        isLoadingTasks,
        activeTasksCount,
        fetchTasks,
        cancelTask,
        clearCompletedTasks,
        startPolling,
        stopPolling,
        $reset
    };
});