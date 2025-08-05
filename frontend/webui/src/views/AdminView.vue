<script setup>
import { ref, defineAsyncComponent, onMounted, computed } from 'vue';
import { useAdminStore } from '../stores/admin';
import { useUiStore } from '../stores/ui';
import { useTasksStore } from '../stores/tasks';
import { storeToRefs } from 'pinia';
import PageViewLayout from '../components/layout/PageViewLayout.vue';

import IconHome from '../assets/icons/IconHome.vue';
import IconUserGroup from '../assets/icons/IconUserGroup.vue';
import IconCpuChip from '../assets/icons/IconCpuChip.vue';
import IconLink from '../assets/icons/IconLink.vue';
import IconWrenchScrewdriver from '../assets/icons/IconWrenchScrewdriver.vue';
import IconCog from '../assets/icons/IconCog.vue';
import IconMessage from '../assets/icons/IconMessage.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconSquares2x2 from '../assets/icons/IconSquares2x2.vue';
import IconTicket from '../assets/icons/IconTicket.vue';
import IconTasks from '../assets/icons/IconTasks.vue';
import IconMcp from '../assets/icons/IconMcp.vue';
import IconPrompt from '../assets/icons/IconTicket.vue';

const AdminPanel = defineAsyncComponent(() => import('../components/admin/AdminPanel.vue'));
const adminStore = useAdminStore();
const uiStore = useUiStore();
const tasksStore = useTasksStore();

const { activeTasksCount } = storeToRefs(tasksStore);

const activeTab = ref('dashboard');

const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: IconHome },
    { id: 'users', label: 'User Management', icon: IconUserGroup },
    { id: 'tasks', label: 'Tasks', icon: IconTicket },
    { id: 'https', label: 'Server/HTTPS', icon: IconCpuChip },
    { id: 'bindings', label: 'LLM Bindings', icon: IconLink },
    { id: 'apps', label: 'Apps', icon: IconSquares2x2 },
    { id: 'mcps', label: 'MCPs', icon: IconMcp },
    { id: 'prompts', label: 'Prompts', icon: IconPrompt },
    { id: 'global_settings', label: 'Global Settings', icon: IconCog },
    { id: 'email', label: 'Email Settings', icon: IconMessage },
    { id: 'import', label: 'Import', icon: IconArrowDownTray }
];

onMounted(() => {
    adminStore.fetchAllUsers();
    adminStore.fetchGlobalSettings();
});
</script>

<template>
  <PageViewLayout title="Admin Panel" :title-icon="IconWrenchScrewdriver">
    <template #header-actions>
      <button @click="uiStore.openModal('tasksManager')" class="btn btn-secondary relative">
        <IconTasks class="w-5 h-5" />
        <span class="ml-2">Task Manager</span>
        <span v-if="activeTasksCount > 0" class="absolute -top-1 -right-1 flex h-4 w-4">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-4 w-4 bg-blue-500 text-white text-xs items-center justify-center">{{ activeTasksCount }}</span>
        </span>
      </button>
    </template>
    <template #sidebar>
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        @click="activeTab = tab.id" 
        :class="{ 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300': activeTab === tab.id }" 
        class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
      >
        <component :is="tab.icon" class="w-5 h-5 flex-shrink-0" />
        <span>{{ tab.label }}</span>
      </button>
    </template>
    <template #main>
      <Suspense>
        <template #default>
            <AdminPanel :active-tab="activeTab" />
        </template>
        <template #fallback>
            <div class="flex items-center justify-center h-full">
                <p class="text-lg text-gray-500 dark:text-gray-400 italic">Loading admin section...</p>
            </div>
        </template>
      </Suspense>
    </template>
  </PageViewLayout>
</template>