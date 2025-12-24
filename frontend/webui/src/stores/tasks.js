// [UPDATE] frontend/webui/src/stores/tasks.js
import { defineStore } from 'pinia';
import { ref, computed, shallowRef } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useAuthStore } from './auth';
import useEventBus from '../services/eventBus';

export const useTasksStore = defineStore('tasks', () => {
    const uiStore = useUiStore();
    const { on, off, emit } = useEventBus();

    // --- STATE ---
    // Use shallowRef to prevent deep recursion performance issues on large task lists
    const tasks = shallowRef([]);
    const isLoadingTasks = ref(false);
    const isClearingTasks = ref(false);
    let isFetching = false;

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
        if (isFetching) return; 
        isFetching = true;
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
        } finally {
            isLoadingTasks.value = false;
            isFetching = false;
        }
    }

    function addTask(taskData) {
        if (!taskData || !taskData.id) return;
        const newTasks = [...tasks.value];
        const index = newTasks.findIndex(t => t.id === taskData.id);
        
        if (index !== -1) {
            newTasks[index] = { ...newTasks[index], ...taskData };
        } else {
            newTasks.unshift(taskData);
        }
        tasks.value = newTasks;

        if (['completed', 'failed', 'cancelled'].includes(taskData.status)) {
            emit('task:completed', taskData);
        }
    }
    
    // --- WebSocket Event Handlers ---
    function handleTaskUpdate(data) { addTask(data); }
    function handleTaskEnd(data) {
        addTask(data);
        if (data.status === 'failed') {
             uiStore.addNotification(`Task '${data.name}' failed: ${data.error || 'Unknown error'}`, 'error');
        }
    }

    function handleTasksCleared(data) {
        const authStore = useAuthStore();
        if (!authStore.user) return;
        if (data.username === null || data.username === authStore.user.username) {
            tasks.value = tasks.value.filter(task => !['completed', 'failed', 'cancelled'].includes(task.status));
        }
    }

    async function cancelTask(taskId) {
        try {
            const response = await apiClient.post(`/api/tasks/${taskId}/cancel`);
            addTask(response.data);
            uiStore.addNotification('Task cancellation processed.', 'info');
        } catch (error) {}
    }

    async function cancelAllTasks() {
        try {
            const response = await apiClient.post('/api/tasks/cancel-all');
            uiStore.addNotification(response.data.message || 'All active tasks cancelled.', 'success');
            fetchTasks();
        } catch (error) {}
    }

    async function clearCompletedTasks() {
        if (isClearingTasks.value) return;
        isClearingTasks.value = true;
        try {
            await apiClient.post('/api/tasks/clear-completed');
            fetchTasks();
        } catch (error) {
        } finally {
            isClearingTasks.value = false;
        }
    }

    function startListening() {
        const authStore = useAuthStore();
        const filter = authStore.isAdmin ? 'all' : 'me';
        
        // Initial fetch to get the current state
        fetchTasks(filter);
        
        // Setup push handlers from WebSocket
        on('task_update', handleTaskUpdate);
        on('task_end', handleTaskEnd);
        on('tasks_cleared', handleTasksCleared);
        
        // POLLING REMOVED: Relying entirely on WebSocket push events to reduce server load.
    }

    function stopListening() {
        off('task_update', handleTaskUpdate);
        off('task_end', handleTaskEnd);
        off('tasks_cleared', handleTasksCleared);
    }
    
    return {
        tasks, isLoadingTasks, isClearingTasks, activeTasksCount, mostRecentActiveTask,
        imageGenerationTasks, imageGenerationTasksCount,
        fetchTasks, addTask, cancelTask, cancelAllTasks, clearCompletedTasks,
        handleTasksCleared, startListening, stopListening,
        startPolling: startListening, stopPolling: stopListening,
        $reset: () => { tasks.value = []; stopListening(); }
    };
});
