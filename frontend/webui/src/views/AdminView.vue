<script setup>
import { ref, defineAsyncComponent, onMounted } from 'vue';
import { useAdminStore } from '../stores/admin';
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

const AdminPanel = defineAsyncComponent(() => import('../components/admin/AdminPanel.vue'));
const adminStore = useAdminStore();

const activeTab = ref('dashboard');

const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: IconHome },
    { id: 'users', label: 'User Management', icon: IconUserGroup },
    { id: 'tasks', label: 'Tasks', icon: IconTicket },
    { id: 'https', label: 'Server/HTTPS', icon: IconCpuChip },
    { id: 'bindings', label: 'LLM Bindings', icon: IconLink },
    { id: 'services', label: 'Services', icon: IconWrenchScrewdriver },
    { id: 'apps', label: 'Apps Management', icon: IconSquares2x2 },
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