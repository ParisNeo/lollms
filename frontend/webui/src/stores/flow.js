import { defineStore } from 'pinia';
import { ref } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useTasksStore } from './tasks';

export const useFlowStore = defineStore('flow', () => {
    const flows = ref([]);
    const currentFlow = ref(null);
    const nodeDefinitions = ref([]); 
    const isLoading = ref(false);
    
    const uiStore = useUiStore();
    const tasksStore = useTasksStore();

    async function fetchFlows() {
        isLoading.value = true;
        try {
            const response = await apiClient.get('/api/flows');
            flows.value = response.data;
        } finally {
            isLoading.value = false;
        }
    }

    async function fetchNodeDefinitions() {
        try {
            const response = await apiClient.get('/api/flows/nodes');
            nodeDefinitions.value = response.data;
        } catch (error) {
            console.error("Failed to fetch node definitions", error);
        }
    }

    async function createNodeDefinition(nodeData) {
        try {
            const response = await apiClient.post('/api/flows/nodes', nodeData);
            nodeDefinitions.value.push(response.data);
            uiStore.addNotification("Node type created", "success");
            return true;
        } catch (error) {
            uiStore.addNotification(error.response?.data?.detail || "Failed to create node", "error");
            return false;
        }
    }

    async function updateNodeDefinition(nodeId, nodeData) {
        try {
            const response = await apiClient.put(`/api/flows/nodes/${nodeId}`, nodeData);
            const index = nodeDefinitions.value.findIndex(n => n.id === nodeId);
            if (index !== -1) nodeDefinitions.value[index] = response.data;
            uiStore.addNotification("Node type updated", "success");
            return true;
        } catch (error) {
            uiStore.addNotification(error.response?.data?.detail || "Failed to update node", "error");
            return false;
        }
    }

    async function createFlow(name, description) {
        try {
            const response = await apiClient.post('/api/flows', { 
                name, 
                description,
                data: { nodes: [], edges: [] }
            });
            flows.value.unshift(response.data);
            currentFlow.value = response.data;
            return response.data;
        } catch (error) {
            uiStore.addNotification("Failed to create flow", "error");
        }
    }

    async function saveFlow(flowId, data) {
        try {
            const existing = flows.value.find(f => f.id === flowId);
            const payload = {
                name: existing ? existing.name : 'Untitled',
                description: existing ? existing.description : '',
                data: data
            };
            const response = await apiClient.put(`/api/flows/${flowId}`, payload);
            const index = flows.value.findIndex(f => f.id === flowId);
            if (index !== -1) flows.value[index] = response.data;
            if (currentFlow.value?.id === flowId) currentFlow.value = response.data;
            uiStore.addNotification("Flow saved.", "success");
        } catch (error) {
            uiStore.addNotification("Failed to save flow", "error");
        }
    }

    async function executeFlow(flowId, inputs = null) {
        try {
            const payload = { flow_id: flowId };
            if (inputs) {
                payload.inputs = inputs;
            }
            
            const response = await apiClient.post('/api/flows/execute', payload);
            tasksStore.addTask(response.data);
            uiStore.addNotification("Flow execution started", "info");
            return response.data;
        } catch (error) {
            uiStore.addNotification("Failed to execute flow", "error");
            console.error(error);
        }
    }

    async function deleteFlow(flowId) {
        try {
            await apiClient.delete(`/api/flows/${flowId}`);
            flows.value = flows.value.filter(f => f.id !== flowId);
            if (currentFlow.value?.id === flowId) currentFlow.value = null;
            uiStore.addNotification("Flow deleted", "success");
        } catch (error) {
            uiStore.addNotification("Failed to delete flow", "error");
        }
    }

    return {
        flows,
        currentFlow,
        nodeDefinitions,
        isLoading,
        fetchFlows,
        fetchNodeDefinitions,
        createNodeDefinition,
        updateNodeDefinition,
        createFlow,
        saveFlow,
        executeFlow,
        deleteFlow
    };
});
