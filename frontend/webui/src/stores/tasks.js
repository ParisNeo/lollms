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
    // Use regular ref instead of shallowRef to ensure deep reactivity
    const tasks = ref([]);
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
            const newTasks = Array.isArray(response.data) ? response.data : [];
            
            console.log(`[TasksStore] Fetched ${newTasks.length} tasks`);
            
            // Replace entire array to trigger reactivity
            tasks.value = newTasks;
            
        } catch (error) {
            console.error("Failed to fetch tasks:", error);
        } finally {
            isLoadingTasks.value = false;
            isFetching = false;
        }
    }

    function addTask(taskData) {
        if (!taskData || !taskData.id) return;
        
        console.log(`[TasksStore] Adding/updating task: ${taskData.id} - ${taskData.name} (${taskData.status})`);
        
        // Create a new array to ensure Vue detects the change
        const currentTasks = [...tasks.value];
        const existingIndex = currentTasks.findIndex(t => t.id === taskData.id);
        
        if (existingIndex !== -1) {
            // Preserve logs if not provided in update
            const existingLogs = currentTasks[existingIndex].logs || [];
            const newLogs = taskData.logs || existingLogs;
            
            // Merge the task data
            currentTasks[existingIndex] = { 
                ...currentTasks[existingIndex], 
                ...taskData, 
                logs: newLogs 
            };
        } else {
            // Add new task at the beginning
            currentTasks.unshift(taskData);
        }
        
        // Replace the entire array to trigger reactivity
        tasks.value = currentTasks;

        // Emit events for important state changes
        if (['completed', 'failed', 'cancelled'].includes(taskData.status)) {
            console.log(`[TasksStore] Task ${taskData.id} ended with status: ${taskData.status}`);
            emit('task:completed', taskData);
        }
    }
    
    // --- WebSocket Event Handlers ---
    function handleTaskUpdate(data) { 
        console.log(`[TasksStore] WebSocket task_update received: ${data.id} - ${data.status}`);
        addTask(data); 
    }
    
    function handleTaskEnd(data) {
        console.log(`[TasksStore] WebSocket task_end received: ${data.id} - ${data.status}`);
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
            console.log(`[TasksStore] Cancelled task ${taskId}:`, response.data);
            addTask(response.data);
            uiStore.addNotification('Task cancellation processed.', 'info');
            return response.data;
        } catch (error) {
            console.error(`[TasksStore] Failed to cancel task ${taskId}:`, error);
            throw error;
        }
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
        
        console.log('[TasksStore] Started listening for task events');
    }

    function stopListening() {
        off('task_update', handleTaskUpdate);
        off('task_end', handleTaskEnd);
        off('tasks_cleared', handleTasksCleared);
        console.log('[TasksStore] Stopped listening for task events');
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
