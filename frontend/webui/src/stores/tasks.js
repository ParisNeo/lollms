import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import useEventBus from '../services/eventBus';

export const useTasksStore = defineStore('tasks', () => {
    const uiStore = useUiStore();
    const { emit } = useEventBus();

    // --- STATE ---
    const tasks = ref([]);
    const isLoadingTasks = ref(false);
    let pollInterval = null;

    // --- COMPUTED ---
    const activeTasksCount = computed(() => {
        return tasks.value.filter(t => t.status === 'running' || t.status === 'pending').length;
    });

    const mostRecentActiveTask = computed(() => {
        const activeTasks = tasks.value
            .filter(t => t.status === 'running' || t.status === 'pending')
            .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        return activeTasks.length > 0 ? activeTasks[0] : null;
    });

    const getTaskById = computed(() => {
        return (taskId) => tasks.value.find(t => t.id === taskId);
    });

    // --- ACTIONS ---
    async function fetchTasks() {
        const wasLoading = isLoadingTasks.value;
        if (!wasLoading) {
            isLoadingTasks.value = true;
        }
        try {
            const oldTasks = new Map(tasks.value.map(t => [t.id, t]));
            const response = await apiClient.get('/api/tasks');
            const newTasks = response.data;
            tasks.value = newTasks;
            
            newTasks.forEach(newTask => {
                const oldTask = oldTasks.get(newTask.id);
                const justFinished = oldTask && (oldTask.status === 'running' || oldTask.status === 'pending') && ['completed', 'failed', 'cancelled'].includes(newTask.status);

                if (justFinished) {
                    emit('task:completed', newTask);
                }
            });

        } catch (error) {
            console.error("Failed to fetch tasks:", error);
        } finally {
            if (!wasLoading) {
                isLoadingTasks.value = false;
            }
        }
    }

    async function fetchTask(taskId) {
        try {
            const response = await apiClient.get(`/api/tasks/${taskId}`);
            addTask(response.data);
        } catch (error) {
            console.error(`Failed to fetch task ${taskId}:`, error);
        }
    }

    function addTask(task) {
        const index = tasks.value.findIndex(t => t.id === task.id);
        if (index === -1) {
            tasks.value.unshift(task);
        } else {
            tasks.value[index] = task;
        }
    }

    async function cancelTask(taskId) {
        try {
            const response = await apiClient.post(`/api/tasks/${taskId}/cancel`);
            addTask(response.data);
            uiStore.addNotification('Task cancellation processed.', 'info');
        } catch (error) {
            // Error is handled by global interceptor
        }
    }

    async function cancelAllTasks() {
        try {
            const response = await apiClient.post('/api/tasks/cancel-all');
            uiStore.addNotification(response.data.message || 'All active tasks cancelled.', 'success');
            await fetchTasks(); // Refresh list to show updated statuses
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
        if (pollInterval) return;
        fetchTasks();
        pollInterval = setInterval(fetchTasks, 3000);
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
        mostRecentActiveTask,
        getTaskById,
        fetchTasks,
        fetchTask,
        addTask,
        cancelTask,
        cancelAllTasks, // Export the new action
        clearCompletedTasks,
        startPolling,
        stopPolling,
        $reset
    };
});