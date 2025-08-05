<script setup>
import { ref, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';
import GenericModal from '../ui/GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorEditor.vue';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();
const { systemPrompts, isLoadingSystemPrompts } = storeToRefs(adminStore);

const isModalOpen = ref(false);
const isEditing = ref(false);
const currentPrompt = ref({ id: null, name: '', content: '' });
const searchTerm = ref('');

onMounted(() => {
    adminStore.fetchSystemPrompts();
});

const filteredPrompts = computed(() => {
    if (!searchTerm.value) {
        return systemPrompts.value;
    }
    const lowerSearch = searchTerm.value.toLowerCase();
    return systemPrompts.value.filter(p =>
        p.name.toLowerCase().includes(lowerSearch) ||
        p.content.toLowerCase().includes(lowerSearch)
    );
});

function openAddModal() {
    isEditing.value = false;
    currentPrompt.value = { id: null, name: '', content: '' };
    isModalOpen.value = true;
}

function openEditModal(prompt) {
    isEditing.value = true;
    currentPrompt.value = { ...prompt };
    isModalOpen.value = true;
}

async function handleDelete(prompt) {
    const confirmed = await uiStore.showConfirmation({
        title: 'Delete System Prompt',
        message: `Are you sure you want to delete the prompt "${prompt.name}"? This cannot be undone.`,
        confirmText: 'Delete'
    });
    if (confirmed) {
        adminStore.deleteSystemPrompt(prompt.id);
    }
}

async function handleSubmit() {
    if (!currentPrompt.value.name || !currentPrompt.value.content) {
        uiStore.addNotification('Name and content are required.', 'warning');
        return;
    }

    try {
        if (isEditing.value) {
            await adminStore.updateSystemPrompt(currentPrompt.value.id, {
                name: currentPrompt.value.name,
                content: currentPrompt.value.content
            });
        } else {
            await adminStore.addSystemPrompt({
                name: currentPrompt.value.name,
                content: currentPrompt.value.content
            });
        }
        isModalOpen.value = false;
    } catch (error) {
        // Error notification is handled by the API client interceptor
    }
}
</script>

<template>
    <div>
        <div class="flex justify-between items-center mb-4">
            <h3 class="text-xl font-semibold">System Prompts</h3>
            <div class="flex items-center gap-2">
                <input v-model="searchTerm" type="text" placeholder="Search prompts..." class="input-field-sm" />
                <button @click="openAddModal" class="btn btn-primary btn-sm">
                    <IconPlus class="w-4 h-4 mr-1" />
                    Add Prompt
                </button>
            </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
            <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead class="bg-gray-50 dark:bg-gray-700">
                    <tr>
                        <th scope="col" class="table-header">Name</th>
                        <th scope="col" class="table-header">Content</th>
                        <th scope="col" class="relative py-3.5 px-4"><span class="sr-only">Actions</span></th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
                    <tr v-if="isLoadingSystemPrompts">
                        <td colspan="3" class="text-center p-4 text-gray-500">Loading...</td>
                    </tr>
                    <tr v-else-if="filteredPrompts.length === 0">
                        <td colspan="3" class="text-center p-4 text-gray-500">No system prompts found.</td>
                    </tr>
                    <tr v-for="prompt in filteredPrompts" :key="prompt.id" class="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                        <td class="table-cell font-medium">{{ prompt.name }}</td>
                        <td class="table-cell">
                            <p class="truncate max-w-lg" :title="prompt.content">{{ prompt.content }}</p>
                        </td>
                        <td class="table-cell text-right space-x-2">
                            <button @click="openEditModal(prompt)" class="btn-icon" title="Edit Prompt">
                                <IconPencil class="w-4 h-4" />
                            </button>
                            <button @click="handleDelete(prompt)" class="btn-icon-danger" title="Delete Prompt">
                                <IconTrash class="w-4 h-4" />
                            </button>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>

        <GenericModal :modalName="'systemPromptModal'" :title="isEditing ? 'Edit System Prompt' : 'Add System Prompt'" :isOpen="isModalOpen" @close="isModalOpen = false">
            <template #body>
                <form @submit.prevent="handleSubmit" class="space-y-4">
                    <div>
                        <label for="prompt-name" class="label">Prompt Name</label>
                        <input id="prompt-name" type="text" v-model="currentPrompt.name" class="input-field" required>
                    </div>
                    <div>
                        <label for="prompt-content" class="label">Prompt Content</label>
                        <CodeMirrorEditor v-model="currentPrompt.content" class="h-64" />
                    </div>
                </form>
            </template>
            <template #footer>
                <button type="button" @click="isModalOpen = false" class="btn btn-secondary">Cancel</button>
                <button type="button" @click="handleSubmit" class="btn btn-primary">{{ isEditing ? 'Save Changes' : 'Create Prompt' }}</button>
            </template>
        </GenericModal>
    </div>
</template>
```

#### `[UPDATE]` `frontend/webui/src/views/AdminView.vue`

```vue
<script setup>
import { ref, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import PageViewLayout from '../components/layout/PageViewLayout.vue';
import UserTable from '../components/admin/UserTable.vue';
import BindingsSettings from '../components/admin/BindingsSettings.vue';
import GlobalSettings from '../components/admin/GlobalSettings.vue';
import ImportTools from '../components/admin/ImportTools.vue';
import HttpsSettings from '../components/admin/HttpsSettings.vue';
import EmailSettings from '../components/admin/EmailSettings.vue';
import AppsManagement from '../components/admin/AppsManagement.vue';
import McpsManagement from '../components/admin/McpsManagement.vue';
import Dashboard from '../components/admin/Dashboard.vue';
import SystemStatus from '../components/admin/SystemStatus.vue';
import TaskManager from '../components/admin/TaskManager.vue';
import SystemPromptsManagement from '../components/admin/SystemPromptsManagement.vue';

import IconDashboard from '../assets/icons/IconDashboard.vue';
import IconUserGroup from '../assets/icons/IconUserGroup.vue';
import IconCpuChip from '../assets/icons/IconCpuChip.vue';
import IconCog from '../assets/icons/IconCog.vue';
import IconKey from '../assets/icons/IconKey.vue';
import IconMail from '../assets/icons/IconMail.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconSquares2x2 from '../assets/icons/IconSquares2x2.vue';
import IconMcp from '../assets/icons/IconMcp.vue';
import IconHardDrive from '../assets/icons/IconHardDrive.vue';
import IconTasks from '../assets/icons/IconTasks.vue';
import IconTag from '../assets/icons/IconTag.vue';

const route = useRoute();
const router = useRouter();

const sections = [
  { id: 'dashboard', name: 'Dashboard', icon: IconDashboard },
  { id: 'users', name: 'User Management', icon: IconUserGroup },
  { id: 'bindings', name: 'LLM Bindings', icon: IconCpuChip },
  { id: 'settings', name: 'Global Settings', icon: IconCog },
  { id: 'system-prompts', name: 'System Prompts', icon: IconTag },
  { id: 'https-settings', name: 'HTTPS Settings', icon: IconKey },
  { id: 'email-settings', name: 'Email Settings', icon: IconMail },
  { id: 'apps-management', name: 'Apps Management', icon: IconSquares2x2 },
  { id: 'mcps-management', name: 'MCPs Management', icon: IconMcp },
  { id: 'system-status', name: 'System Status', icon: IconHardDrive },
  { id: 'task-manager', name: 'Task Manager', icon: IconTasks },
  { id: 'import-tools', name: 'Import Tools', icon: IconArrowDownTray },
];

const activeSection = computed({
    get: () => route.query.section || 'dashboard',
    set: (section) => {
        router.push({ query: { ...route.query, section } });
    }
});
</script>

<template>
    <PageViewLayout title="Admin Panel" :titleIcon="IconCog">
        <template #sidebar>
            <a v-for="section in sections"
               :key="section.id"
               href="#"
               @click.prevent="activeSection = section.id"
               class="flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors"
               :class="activeSection === section.id ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'"
            >
                <component :is="section.icon" class="w-5 h-5" />
                <span>{{ section.name }}</span>
            </a>
        </template>
        <template #main>
            <div class="p-4">
                <Dashboard v-if="activeSection === 'dashboard'" />
                <UserTable v-if="activeSection === 'users'" />
                <BindingsSettings v-if="activeSection === 'bindings'" />
                <GlobalSettings v-if="activeSection === 'settings'" />
                <SystemPromptsManagement v-if="activeSection === 'system-prompts'" />
                <HttpsSettings v-if="activeSection === 'https-settings'" />
                <EmailSettings v-if="activeSection === 'email-settings'" />
                <AppsManagement v-if="activeSection === 'apps-management'" />
                <McpsManagement v-if="activeSection === 'mcps-management'" />
                <SystemStatus v-if="activeSection === 'system-status'" />
                <TaskManager v-if="activeSection === 'task-manager'" />
                <ImportTools v-if="activeSection === 'import-tools'" />
            </div>
        </template>
    </PageViewLayout>
</template>
```

#### `[UPDATE]` `frontend/webui/src/stores/admin.js`

```js
import { defineStore } from 'pinia';
import { ref } from 'vue';
import apiClient from '../services/api';
import { useUiStore } from './ui';
import { useTasksStore } from './tasks'; // Import the new tasks store

export const useAdminStore = defineStore('admin', () => {
    const uiStore = useUiStore();
    const tasksStore = useTasksStore(); // Get instance of tasks store

    // --- State ---
    const allUsers = ref([]);
    const isLoadingUsers = ref(false);

    const bindings = ref([]);
    const isLoadingBindings = ref(false);
    const availableBindingTypes = ref([]);

    const globalSettings = ref([]);
    const isLoadingSettings = ref(false);

    const isImporting = ref(false);
    
    const mcps = ref([]);
    const apps = ref([]);
    const isLoadingServices = ref(false);

    const isEnhancingEmail = ref(false);
    
    const adminAvailableLollmsModels = ref([]);
    const isLoadingLollmsModels = ref(false);

    const zooRepositories = ref([]);
    const isLoadingZooRepositories = ref(false);
    const mcpZooRepositories = ref([]);
    const isLoadingMcpZooRepositories = ref(false);


    const zooApps = ref({ items: [], total: 0, pages: 1 });
    const isLoadingZooApps = ref(false);
    const zooMcps = ref({ items: [], total: 0, pages: 1 });
    const isLoadingZooMcps = ref(false);

    const installedApps = ref([]);
    const isLoadingInstalledApps = ref(false);

    const systemStatus = ref(null);
    const isLoadingSystemStatus = ref(false);

    const systemPrompts = ref([]);
    const isLoadingSystemPrompts = ref(false);

    // --- Actions ---
    async function fetchSystemStatus() {
        isLoadingSystemStatus.value = true;
        try {
            const response = await apiClient.get('/api/admin/system-status');
            systemStatus.value = response.data;
        } catch (error) {
            systemStatus.value = null; // Clear on error
            uiStore.addNotification('Could not load system status.', 'error');
        } finally {
            isLoadingSystemStatus.value = false;
        }
    }

    async function fetchSystemPrompts() {
        isLoadingSystemPrompts.value = true;
        try {
            const response = await apiClient.get('/api/admin/system-prompts');
            systemPrompts.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load system prompts.', 'error');
        } finally {
            isLoadingSystemPrompts.value = false;
        }
    }

    async function addSystemPrompt(payload) {
        const response = await apiClient.post('/api/admin/system-prompts', payload);
        systemPrompts.value.push(response.data);
        systemPrompts.value.sort((a, b) => a.name.localeCompare(b.name));
        uiStore.addNotification('System prompt created.', 'success');
    }

    async function updateSystemPrompt(id, payload) {
        const response = await apiClient.put(`/api/admin/system-prompts/${id}`, payload);
        const index = systemPrompts.value.findIndex(p => p.id === id);
        if (index !== -1) {
            systemPrompts.value[index] = response.data;
        }
        systemPrompts.value.sort((a, b) => a.name.localeCompare(b.name));
        uiStore.addNotification('System prompt updated.', 'success');
    }

    async function deleteSystemPrompt(id) {
        await apiClient.delete(`/api/admin/system-prompts/${id}`);
        systemPrompts.value = systemPrompts.value.filter(p => p.id !== id);
        uiStore.addNotification('System prompt deleted.', 'success');
    }


    // Purge Task - an admin-only action
    async function purgeUnusedUploads() {
        try {
            const response = await apiClient.post('/api/admin/purge-unused-uploads');
            const task = response.data;
            uiStore.addNotification(`Task '${task.name}' started.`, 'info');
            tasksStore.addTask(task); // Use the tasks store to refresh
            return task;
        } catch (error) {
            throw error;
        }
    }

    // Users
    async function fetchAllUsers() {
        isLoadingUsers.value = true;
        try {
            const response = await apiClient.get('/api/admin/users');
            allUsers.value = response.data;
        } catch (error) {
            console.error("Failed to fetch users:", error);
            uiStore.addNotification('Could not load user list.', 'error');
        } finally {
            isLoadingUsers.value = false;
        }
    }
    
    async function sendEmailToUsers(subject, body, user_ids, backgroundColor, sendAsText) {
        try {
            const payload = {
                subject,
                body,
                user_ids,
                background_color: backgroundColor,
                send_as_text: sendAsText
            };
            const response = await apiClient.post('/api/admin/email-users', payload);
            const task = response.data;
            uiStore.addNotification(`Email task '${task.name}' started.`, 'success');
            tasksStore.addTask(task);
            return true;
        } catch (error) {
            return false;
        }
    }
    
    async function enhanceEmail(subject, body, backgroundColor, prompt) {
        isEnhancingEmail.value = true;
        try {
            const response = await apiClient.post('/api/admin/enhance-email', { subject, body, background_color: backgroundColor, prompt });
            uiStore.addNotification('Email content enhanced by AI.', 'success');
            return response.data;
        } catch (error) {
            // Error handled by global interceptor
            return null;
        } finally {
            isEnhancingEmail.value = false;
        }
    }

    async function batchUpdateUsers(payload) {
        try {
            const response = await apiClient.post('/api/admin/users/batch-update-settings', payload);
            uiStore.addNotification(response.data.message || 'Settings applied successfully.', 'success');
            await fetchAllUsers();
        } catch (error) {
            throw error;
        }
    }
    
    async function fetchAdminAvailableLollmsModels() {
        if (adminAvailableLollmsModels.value.length > 0) return;
        isLoadingLollmsModels.value = true;
        try {
            const response = await apiClient.get('/api/admin/available-models');
            adminAvailableLollmsModels.value = response.data;
        } catch (error) {
            uiStore.addNotification("Could not fetch available LLM models for admin.", 'error');
            adminAvailableLollmsModels.value = [];
        } finally {
            isLoadingLollmsModels.value = false;
        }
    }

    // Bindings
    async function fetchBindings() {
        isLoadingBindings.value = true;
        try {
            const response = await apiClient.get('/api/admin/bindings');
            bindings.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load LLM bindings.', 'error');
        } finally {
            isLoadingBindings.value = false;
        }
    }
    async function fetchAvailableBindingTypes() {
        try {
            const response = await apiClient.get('/api/admin/bindings/available_types');
            availableBindingTypes.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load available binding types.', 'error');
        }
    }
    async function addBinding(payload) {
        const response = await apiClient.post('/api/admin/bindings', payload);
        bindings.value.push(response.data);
        uiStore.addNotification(`Binding '${response.data.alias}' created.`, 'success');
    }
    async function updateBinding(id, payload) {
        const response = await apiClient.put(`/api/admin/bindings/${id}`, payload);
        const index = bindings.value.findIndex(b => b.id === id);
        if (index !== -1) {
            bindings.value[index] = response.data;
        }
        uiStore.addNotification(`Binding '${response.data.alias}' updated.`, 'success');
    }
    async function deleteBinding(id) {
        await apiClient.delete(`/api/admin/bindings/${id}`);
        bindings.value = bindings.value.filter(b => b.id !== id);
        uiStore.addNotification('Binding deleted successfully.', 'success');
    }

    // Global Settings
    async function fetchGlobalSettings() {
        isLoadingSettings.value = true;
        try {
            const response = await apiClient.get('/api/admin/settings');
            globalSettings.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load global settings.', 'error');
        } finally {
            isLoadingSettings.value = false;
        }
    }
    async function updateGlobalSettings(configs) {
        const response = await apiClient.put('/api/admin/settings', { configs });
        await fetchGlobalSettings();
        uiStore.addNotification(response.data.message, 'success');
    }

    // Import
    async function importOpenWebUIData(file) {
        isImporting.value = true;
        const formData = new FormData();
        formData.append('file', file);
        try {
            const response = await apiClient.post('/api/admin/import-openwebui', formData);
            uiStore.addNotification(response.data.message, 'success', { duration: 5000 });
        } finally {
            isImporting.value = false;
        }
    }
    
    // MCPs
    async function fetchMcps() {
        isLoadingServices.value = true;
        try {
            const response = await apiClient.get('/api/mcps');
            mcps.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load MCPs.', 'error');
        } finally {
            isLoadingServices.value = false;
        }
    }
    async function addMcp(payload) {
        const response = await apiClient.post('/api/mcps', payload);
        mcps.value.push(response.data);
        uiStore.addNotification(`MCP '${response.data.name}' created successfully.`, 'success');
    }
    async function updateMcp(id, payload) {
        const response = await apiClient.put(`/api/mcps/${id}`, payload);
        const index = mcps.value.findIndex(m => m.id === id);
        if (index !== -1) mcps.value[index] = response.data;
        uiStore.addNotification(`MCP '${response.data.name}' updated successfully.`, 'success');
    }
    async function deleteMcp(id) {
        await apiClient.delete(`/api/mcps/${id}`);
        mcps.value = mcps.value.filter(m => m.id !== id);
        uiStore.addNotification('MCP deleted successfully.', 'success');
    }
    async function generateMcpSsoSecret(id) {
        try {
            const response = await apiClient.post(`/api/mcps/${id}/generate-sso-secret`);
            await fetchMcps();
            return response.data.sso_secret;
        } catch (error) {
            throw error;
        }
    }

    // Apps
    async function fetchApps() {
        isLoadingServices.value = true;
        try {
            const response = await apiClient.get('/api/apps');
            apps.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load Apps.', 'error');
        } finally {
            isLoadingServices.value = false;
        }
    }
    async function addApp(payload) {
        const response = await apiClient.post('/api/apps', payload);
        apps.value.push(response.data);
        uiStore.addNotification(`App '${response.data.name}' created successfully.`, 'success');
    }
    async function updateApp(id, payload) {
        const response = await apiClient.put(`/api/apps/${id}`, payload);
        const index = apps.value.findIndex(a => a.id === id);
        if (index !== -1) apps.value[index] = response.data;
        uiStore.addNotification(`App '${response.data.name}' updated successfully.`, 'success');
    }
    async function deleteApp(id) {
        await apiClient.delete(`/api/apps/${id}`);
        apps.value = apps.value.filter(a => a.id !== id);
        uiStore.addNotification('App deleted successfully.', 'success');
    }
    async function generateAppSsoSecret(id) {
        try {
            const response = await apiClient.post(`/api/apps/${id}/generate-sso-secret`);
            await fetchApps();
            return response.data.sso_secret;
        } catch (error) {
            throw error;
        }
    }

    // App Zoo Repositories
    async function fetchZooRepositories() {
        isLoadingZooRepositories.value = true;
        try {
            const response = await apiClient.get('/api/apps_zoo/repositories');
            zooRepositories.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load App Zoo repositories.', 'error');
        } finally {
            isLoadingZooRepositories.value = false;
        }
    }
    async function addZooRepository(name, url) {
        try {
            const response = await apiClient.post('/api/apps_zoo/repositories', { name, url });
            zooRepositories.value.push(response.data);
            uiStore.addNotification(`Repository '${name}' added.`, 'success');
        } catch (error) {
            throw error;
        }
    }
    async function deleteZooRepository(repoId) {
        try {
            await apiClient.delete(`/api/apps_zoo/repositories/${repoId}`);
            zooRepositories.value = zooRepositories.value.filter(r => r.id !== repoId);
            uiStore.addNotification('Repository deleted.', 'success');
        } catch (error) {
            throw error;
        }
    }
    async function pullZooRepository(repoId) {
        try {
            const response = await apiClient.post(`/api/apps_zoo/repositories/${repoId}/pull`);
            const task = response.data;
            uiStore.addNotification(task.name + ' started.', 'info', { duration: 5000 });
            tasksStore.addTask(task);
            return task;
        } catch (error) {
            throw error;
        }
    }
    async function pullAllZooRepositories() {
        if (zooRepositories.value.length === 0) {
            uiStore.addNotification('No repositories to pull.', 'info');
            return;
        }
        uiStore.addNotification('Starting to pull all repositories...', 'info');
        for (const repo of zooRepositories.value) {
            try {
                await pullZooRepository(repo.id);
            } catch (error) {
                console.error(`Failed to start pull task for repository: ${repo.name}`, error);
            }
        }
    }

    // MCP Zoo Repositories
    async function fetchMcpZooRepositories() {
        isLoadingMcpZooRepositories.value = true;
        try {
            const response = await apiClient.get('/api/mcps_zoo/repositories');
            mcpZooRepositories.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load MCP Zoo repositories.', 'error');
        } finally {
            isLoadingMcpZooRepositories.value = false;
        }
    }
    async function addMcpZooRepository(name, url) {
        try {
            const response = await apiClient.post('/api/mcps_zoo/repositories', { name, url });
            mcpZooRepositories.value.push(response.data);
            uiStore.addNotification(`MCP Repository '${name}' added.`, 'success');
        } catch (error) {
            throw error;
        }
    }
    async function deleteMcpZooRepository(repoId) {
        try {
            await apiClient.delete(`/api/mcps_zoo/repositories/${repoId}`);
            mcpZooRepositories.value = mcpZooRepositories.value.filter(r => r.id !== repoId);
            uiStore.addNotification('MCP Repository deleted.', 'success');
        } catch (error) {
            throw error;
        }
    }
    async function pullMcpZooRepository(repoId) {
        try {
            const response = await apiClient.post(`/api/mcps_zoo/repositories/${repoId}/pull`);
            const task = response.data;
            uiStore.addNotification(task.name + ' started.', 'info', { duration: 5000 });
            tasksStore.addTask(task);
            return task;
        } catch (error) {
            throw error;
        }
    }
    async function pullAllMcpZooRepositories() {
        if (mcpZooRepositories.value.length === 0) {
            uiStore.addNotification('No MCP repositories to pull.', 'info');
            return;
        }
        uiStore.addNotification('Starting to pull all MCP repositories...', 'info');
        for (const repo of mcpZooRepositories.value) {
            try {
                await pullMcpZooRepository(repo.id);
            } catch (error) {
                console.error(`Failed to start pull task for MCP repository: ${repo.name}`, error);
            }
        }
    }

    // Available Zoo Apps
    async function fetchZooApps(params = {}) {
        isLoadingZooApps.value = true;
        try {
            const response = await apiClient.get('/api/apps_zoo/available', { params });
            zooApps.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load available apps from the zoo.', 'error');
        } finally {
            isLoadingZooApps.value = false;
        }
    }

    // Available Zoo MCPs
    async function fetchZooMcps(params = {}) {
        isLoadingZooMcps.value = true;
        try {
            const response = await apiClient.get('/api/mcps_zoo/available', { params });
            zooMcps.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load available MCPs from the zoo.', 'error');
        } finally {
            isLoadingZooMcps.value = false;
        }
    }


    async function fetchAppReadme(repository, folder_name) {
        try {
            const response = await apiClient.get('/api/apps_zoo/readme', {
                params: { repository, folder_name }
            });
            return response.data;
        } catch (error) {
            throw error;
        }
    }

    async function fetchMcpReadme(repository, folder_name) {
        try {
            const response = await apiClient.get('/api/mcps_zoo/readme', {
                params: { repository, folder_name }
            });
            return response.data;
        } catch (error) {
            throw error;
        }
    }

    async function installZooApp(payload) {
        try {
            const response = await apiClient.post('/api/apps_zoo/install', payload);
            const task = response.data;
            uiStore.addNotification(task.name + ' started.', 'info', { duration: 5000 });
            await fetchInstalledApps(); // Refresh installed list
            tasksStore.addTask(task);
            return task;
        } catch (error) {
            throw error;
        }
    }
    
    async function installZooMcp(payload) {
        try {
            const response = await apiClient.post('/api/mcps_zoo/install', payload);
            const task = response.data;
            uiStore.addNotification(task.name + ' started.', 'info', { duration: 5000 });
            await fetchInstalledApps(); // Refresh installed list
            tasksStore.addTask(task);
            return task;
        } catch (error) {
            throw error;
        }
    }

    // Installed Apps Management
    async function fetchInstalledApps() {
        isLoadingInstalledApps.value = true;
        try {
            const response = await apiClient.get('/api/apps_zoo/installed');
            installedApps.value = response.data;
        } catch (error) {
            uiStore.addNotification('Could not load installed apps.', 'error');
        } finally {
            isLoadingInstalledApps.value = false;
        }
    }

    async function fetchNextAvailablePort(port = null) {
        try {
            const params = port ? { port } : {};
            const response = await apiClient.get('/api/apps_zoo/get-next-available-port', { params });
            return response.data.port;
        } catch (error) {
            if (port) throw error; // Re-throw for specific port checks
            uiStore.addNotification('Could not determine an available port.', 'warning');
            return 9601; // Fallback
        }
    }

    async function startApp(appId) {
        const response = await apiClient.post(`/api/apps_zoo/installed/${appId}/start`);
        const task = response.data;
        uiStore.addNotification(`Task '${task.name}' started.`, 'info');
        tasksStore.addTask(task);
    }
    async function stopApp(appId) {
        const response = await apiClient.post(`/api/apps_zoo/installed/${appId}/stop`);
        const task = response.data;
        uiStore.addNotification(`Task '${task.name}' started.`, 'info');
        tasksStore.addTask(task);
    }
    async function uninstallApp(appId) {
        const response = await apiClient.delete(`/api/apps_zoo/installed/${appId}`);
        uiStore.addNotification(response.data.message, 'success');
        await fetchInstalledApps();
        // No need to fetch Zoo apps here, their status is determined on the fly
    }

    async function updateInstalledApp(appId, payload) {
        try {
            const response = await apiClient.put(`/api/apps_zoo/installed/${appId}`, payload);
            uiStore.addNotification(`App '${response.data.name}' updated successfully.`, 'success');
            const index = installedApps.value.findIndex(app => app.id === appId);
            if (index !== -1) {
                installedApps.value[index] = response.data;
            }
            return response.data;
        } catch (error) {
            throw error;
        }
    }

    async function fetchAppLog(appId) {
        try {
            const response = await apiClient.get(`/api/apps_zoo/installed/${appId}/logs`);
            return response.data.log_content;
        } catch (error) {
            throw error;
        }
    }

    // NEW App Config Actions
    async function fetchAppConfigSchema(appId) {
        const response = await apiClient.get(`/api/apps_zoo/installed/${appId}/config-schema`);
        return response.data;
    }
    async function fetchAppConfig(appId) {
        const response = await apiClient.get(`/api/apps_zoo/installed/${appId}/config`);
        return response.data;
    }
    async function updateAppConfig(appId, configData) {
        const response = await apiClient.put(`/api/apps_zoo/installed/${appId}/config`, configData);
        uiStore.addNotification(response.data.message || 'Configuration saved.', 'success');
    }

    return {
        allUsers, isLoadingUsers, fetchAllUsers, sendEmailToUsers,
        bindings, isLoadingBindings, availableBindingTypes, fetchBindings, fetchAvailableBindingTypes, addBinding, updateBinding, deleteBinding,
        globalSettings, isLoadingSettings, fetchGlobalSettings, updateGlobalSettings,
        isImporting, importOpenWebUIData,
        mcps, apps, isLoadingServices,
        fetchMcps, addMcp, updateMcp, deleteMcp, generateMcpSsoSecret,
        fetchApps, addApp, updateApp, deleteApp, generateAppSsoSecret,
        adminAvailableLollmsModels, isLoadingLollmsModels, fetchAdminAvailableLollmsModels,
        batchUpdateUsers,
        isEnhancingEmail, enhanceEmail,
        zooRepositories, isLoadingZooRepositories, fetchZooRepositories, addZooRepository, deleteZooRepository, pullZooRepository, pullAllZooRepositories,
        mcpZooRepositories, isLoadingMcpZooRepositories, fetchMcpZooRepositories, addMcpZooRepository, deleteMcpZooRepository, pullMcpZooRepository, pullAllMcpZooRepositories,
        zooApps, isLoadingZooApps, fetchZooApps,
        zooMcps, isLoadingZooMcps, fetchZooMcps, fetchMcpReadme, installZooMcp,
        installedApps, isLoadingInstalledApps, fetchInstalledApps, startApp, stopApp, uninstallApp, fetchNextAvailablePort,
        purgeUnusedUploads,
        updateInstalledApp, fetchAppLog,
        systemStatus, isLoadingSystemStatus, fetchSystemStatus,
        fetchAppConfigSchema, fetchAppConfig, updateAppConfig,
        installZooApp, fetchAppReadme,
        systemPrompts, isLoadingSystemPrompts, fetchSystemPrompts, addSystemPrompt, updateSystemPrompt, deleteSystemPrompt
    };
});