import { defineStore } from 'pinia';
import { ref, computed, watch } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import useEventBus from '../services/eventBus';
import { useDiscussionsStore } from './discussions'; // NEW: Import discussions store

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
        // Prevent setting loading state on every poll to avoid UI flicker
        const wasLoading = isLoadingTasks.value;
        if (!wasLoading) {
            isLoadingTasks.value = true;
        }
        try {
            const oldTasks = new Map(tasks.value.map(t => [t.id, t]));
            const response = await apiClient.get('/api/tasks');
            const newTasks = response.data;
            tasks.value = newTasks;
            
            // NEW: Get discussions store instance
            const discussionsStore = useDiscussionsStore();

            // Check for newly completed tasks and emit an event
            newTasks.forEach(newTask => {
                const oldTask = oldTasks.get(newTask.id);
                const justFinished = oldTask && (oldTask.status === 'running' || oldTask.status === 'pending') && ['completed', 'failed', 'cancelled'].includes(newTask.status);
                
                if (justFinished) {
                    emit('task:completed', newTask);

                    // NEW: Directly clear the active task from discussionsStore
                    let discussionIdForTask = null;
                    for (const [discussionId, activeTaskInfo] of Object.entries(discussionsStore.activeAiTasks)) {
                        if (activeTaskInfo && activeTaskInfo.taskId === newTask.id) {
                            discussionIdForTask = discussionId;
                            break;
                        }
                    }
                    if (discussionIdForTask) {
                        discussionsStore._clearActiveAiTask(discussionIdForTask);
                    }
                }
            });

        } catch (error) {
            console.error("Failed to fetch tasks:", error);
            // Don't show a notification on silent polling failures
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
            tasks.value.unshift(task); // Add to the top of the list
        } else {
            tasks.value[index] = task; // Update existing task
        }
    }

    async function cancelTask(taskId) {
        try {
            const response = await apiClient.post(`/api/tasks/${taskId}/cancel`);
            addTask(response.data); // Immediately update the task state with the final state from the API
            uiStore.addNotification('Task cancellation processed.', 'info');
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
        pollInterval = setInterval(fetchTasks, 3000); // Poll every 3 seconds
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
        clearCompletedTasks,
        startPolling,
        stopPolling,
        $reset
    };
});
