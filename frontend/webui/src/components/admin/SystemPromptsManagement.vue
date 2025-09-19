<script setup>
import { ref, onMounted, computed } from 'vue';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';
import GenericModal from '../ui/GenericModal.vue';
import CodeMirrorEditor from '../ui/CodeMirrorComponent/index.vue';
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