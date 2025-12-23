import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';
import useEventBus from '../services/eventBus';

export const useTasksStore = defineStore('tasks', () => {
    const uiStore = useUiStore();
    const { on, off, emit } = useEventBus();

    // --- STATE ---
    const tasks = ref([]);
    const isLoadingTasks = ref(false);
    const isClearingTasks = ref(false);

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
                t.name.startsWith('Editing image:') ||
                t.name.startsWith('Generating Timelapse')
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
            tasks.value = [];
        } finally {
            isLoadingTasks.value = false;
        }
    }

    function addTask(taskData) {
        if (!taskData || !taskData.id) return;
        const index = tasks.value.findIndex(t => t.id === taskData.id);
        
        if (index !== -1) {
            // Vue 3 reactivity best practice: Replace object properties or the object itself
            // To ensure reactivity in deep watchers, we assign a new object merging old and new
            tasks.value[index] = { ...tasks.value[index], ...taskData };
        } else {
            tasks.value.unshift(taskData);
        }

        const isFinished = ['completed', 'failed', 'cancelled'].includes(taskData.status);

        // Always emit completion for finished tasks so subscribers (like ImageStore) 
        // can handle the result, even if the 'running' state was missed.
        if (isFinished) {
            emit('task:completed', taskData);
        }
    }
    
    // --- WebSocket Event Handlers ---
    function handleTaskUpdate(data) {
        addTask(data);
    }

    function handleTaskEnd(data) {
        addTask(data);
        if (data.status === 'failed') {
             uiStore.addNotification(`Task '${data.name}' failed: ${data.error || 'Unknown error'}`, 'error');
        } else if (data.status === 'completed') {
             // Optional: Add success notification if desired, but might be spammy for frequent tasks
             // uiStore.addNotification(`Task '${data.name}' completed.`, 'success');
        }
    }

    function handleTasksCleared(data) {
        const authStore = useAuthStore();
        const currentUser = authStore.user;
        if (!currentUser) return;

        // If username is null (admin cleared all) or matches current user
        if (data.username === null || data.username === currentUser.username) {
            tasks.value = tasks.value.filter(task => !['completed', 'failed', 'cancelled'].includes(task.status));
        }
    }

    async function cancelTask(taskId) {
        try {
            const response = await apiClient.post(`/api/tasks/${taskId}/cancel`);
            addTask(response.data);
            uiStore.addNotification('Task cancellation processed.', 'info');
        } catch (error) {
            // Error handled globally
        }
    }

    async function cancelAllTasks() {
        try {
            const response = await apiClient.post('/api/tasks/cancel-all');
            uiStore.addNotification(response.data.message || 'All active tasks cancelled.', 'success');
            // Refresh logic handled via WS updates usually, but fetch once to be sure
            const authStore = useAuthStore();
            const filter = authStore.isAdmin ? 'all' : 'me';
            await fetchTasks(filter);
        } catch (error) {
            // Error handled globally
        }
    }

    async function clearCompletedTasks() {
        if (isClearingTasks.value) return;
        isClearingTasks.value = true;
        try {
            const response = await apiClient.post('/api/tasks/clear-completed');
            uiStore.addNotification(response.data.message || 'Completed tasks cleared.', 'success');
            
            // Optimistic update (backup to WS event)
            const authStore = useAuthStore();
            if (authStore.isAdmin) {
                tasks.value = tasks.value.filter(task => !['completed', 'failed', 'cancelled'].includes(task.status));
            } else {
                const username = authStore.user?.username;
                tasks.value = tasks.value.filter(task => {
                    const isCompleted = ['completed', 'failed', 'cancelled'].includes(task.status);
                    if (!isCompleted) return true;
                    return task.owner_username !== username;
                });
            }
        } catch (error) {
            // Error handled globally
        } finally {
            isClearingTasks.value = false;
        }
    }

    function startListening() {
        const authStore = useAuthStore();
        const filter = authStore.isAdmin ? 'all' : 'me';
        // Initial fetch to populate state
        fetchTasks(filter);

        // Subscribe to WebSocket events
        on('task_update', handleTaskUpdate);
        on('task_end', handleTaskEnd);
        on('tasks_cleared', handleTasksCleared);
    }

    function stopListening() {
        off('task_update', handleTaskUpdate);
        off('task_end', handleTaskEnd);
        off('tasks_cleared', handleTasksCleared);
    }
    
    // Alias for backward compatibility if components use startPolling
    const startPolling = startListening;
    const stopPolling = stopListening;

    function $reset() {
        tasks.value = [];
        isLoadingTasks.value = false;
        isClearingTasks.value = false;
        stopListening();
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
        startListening,
        stopListening,
        $reset
    };
});
