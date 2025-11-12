// [UPDATE] frontend/webui/src/stores/tasks.js
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';
import useEventBus from '../services/eventBus';

export const useTasksStore = defineStore('tasks', () => {
    const uiStore = useUiStore();
    const { emit } = useEventBus();

    // --- STATE ---
    const tasks = ref([]);
    const isLoadingTasks = ref(false);
    const isClearingTasks = ref(false);
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

    const imageGenerationTasks = computed(() => {
        return tasks.value.filter(t =>
            (t.status === 'running' || t.status === 'pending') &&
            (
                (t.name.startsWith('Generating') && t.name.includes('image(s)')) ||
                t.name.startsWith('Editing image:')
            )
        );
    });

    const imageGenerationTasksCount = computed(() => imageGenerationTasks.value.length);


    // --- ACTIONS ---
    async function fetchTasks(ownerFilter = 'all') {
        isLoadingTasks.value = true;
        try {
            const authStore = useAuthStore();
            const params = {};
            if (authStore.isAdmin) {
                params.owner_filter = ownerFilter;
            }
            const response = await apiClient.get('/api/tasks', { params });
            tasks.value = Array.isArray(response.data) ? response.data : [];
        } catch (error) {
            console.error("Failed to fetch tasks:", error);
            tasks.value = []; // Ensure it's an array on failure
        } finally {
            isLoadingTasks.value = false;
        }
    }

    function addTask(taskData) {
        const index = tasks.value.findIndex(t => t.id === taskData.id);
        const oldTask = index !== -1 ? { ...tasks.value[index] } : null;

        if (index !== -1) {
            tasks.value[index] = { ...tasks.value[index], ...taskData };
        } else {
            tasks.value.unshift(taskData);
        }

        const wasActive = oldTask && (oldTask.status === 'running' || oldTask.status === 'pending');
        const isNowFinished = ['completed', 'failed', 'cancelled'].includes(taskData.status);

        if (wasActive && isNowFinished) {
            emit('task:completed', taskData);
        }
    }
    
    function handleTasksCleared(data) {
        const authStore = useAuthStore();
        const currentUser = authStore.user;
        if (!currentUser) return;

        // If username is null, it's a global clear for admins.
        // If it matches the current user, it's a personal clear.
        if (data.username === null || data.username === currentUser.username) {
            tasks.value = tasks.value.filter(task => !['completed', 'failed', 'cancelled'].includes(task.status));
        }
    }


    async function cancelTask(taskId) {
        try {
            const response = await apiClient.post(`/api/tasks/${taskId}/cancel`);
            addTask(response.data); // Update the task with the 'cancelled' state from the backend
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
        if (isClearingTasks.value) return;
        isClearingTasks.value = true;
        try {
            const response = await apiClient.post('/api/tasks/clear-completed');
            uiStore.addNotification(response.data.message || 'Completed tasks cleared.', 'success');
            
            // Perform local update for immediate UI feedback
            const authStore = useAuthStore();
            if (authStore.isAdmin) {
                // Admin clears all completed tasks
                tasks.value = tasks.value.filter(task => !['completed', 'failed', 'cancelled'].includes(task.status));
            } else {
                // Regular user clears only their own completed tasks
                const username = authStore.user?.username;
                tasks.value = tasks.value.filter(task => {
                    const isCompleted = ['completed', 'failed', 'cancelled'].includes(task.status);
                    if (!isCompleted) return true; // Keep active tasks
                    return task.owner_username !== username;
                });
            }
        } catch (error) {
            // Error is handled by global interceptor
        } finally {
            isClearingTasks.value = false;
        }
    }

    function startPolling() {
        if (pollInterval) return;
        const authStore = useAuthStore();
        const filter = authStore.isAdmin ? 'all' : 'me';
        fetchTasks(filter);
        pollInterval = setInterval(() => {
            const authStore = useAuthStore();
            const currentFilter = authStore.isAdmin ? 'all' : 'me';
            fetchTasks(currentFilter);
        }, 5000); // Poll every 5 seconds
    }

    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }
    
    function $reset() {
        tasks.value = [];
        isLoadingTasks.value = false;
        isClearingTasks.value = false;
        stopPolling();
    }

    return {
        tasks,
        isLoadingTasks,
        isClearingTasks,
        activeTasksCount,
        mostRecentActiveTask,
        imageGenerationTasks,
        imageGenerationTasksCount,
        fetchTasks,
        addTask,
        cancelTask,
        cancelAllTasks,
        clearCompletedTasks,
        handleTasksCleared,
        startPolling,
        stopPolling,
        $reset
    };
});