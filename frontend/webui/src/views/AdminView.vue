<script setup>
import { ref, defineAsyncComponent, computed, onMounted } from 'vue';
import { useAdminStore } from '../stores/admin';

import IconHome from '../assets/icons/IconHome.vue';
import IconUserGroup from '../assets/icons/IconUserGroup.vue';
import IconCpuChip from '../assets/icons/IconCpuChip.vue';
import IconLink from '../assets/icons/IconLink.vue';
import IconWrenchScrewdriver from '../assets/icons/IconWrenchScrewdriver.vue';
import IconCog from '../assets/icons/IconCog.vue';
import IconMessage from '../assets/icons/IconMessage.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';
import IconMenu from '../assets/icons/IconMenu.vue';

const AdminPanel = defineAsyncComponent(() => import('../components/admin/AdminPanel.vue'));
const adminStore = useAdminStore();

const activeTab = ref('dashboard');
const isSidebarOpen = ref(false);

const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: IconHome },
    { id: 'users', label: 'User Management', icon: IconUserGroup },
    { id: 'https', label: 'Server/HTTPS', icon: IconCpuChip },
    { id: 'bindings', label: 'LLM Bindings', icon: IconLink },
    { id: 'services', label: 'Services', icon: IconWrenchScrewdriver },
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
  <div class="flex h-screen bg-gray-100 dark:bg-gray-900 overflow-hidden">
    <!-- Mobile Sidebar Overlay -->
    <div v-if="isSidebarOpen" @click="isSidebarOpen = false" class="fixed inset-0 bg-black/30 z-20 md:hidden"></div>

    <!-- Sidebar Navigation -->
    <nav class="fixed inset-y-0 left-0 z-30 w-64 bg-white dark:bg-gray-800 border-r dark:border-gray-700 flex flex-col transform transition-transform md:relative md:translate-x-0"
         :class="{'-translate-x-full': !isSidebarOpen}">
        
        <div class="p-4 border-b dark:border-gray-700 flex-shrink-0">
          <div class="flex items-center space-x-3">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-gray-500 dark:text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M15 21v-1.5a6.375 6.375 0 00-3.262-5.171M9 10a3 3 0 11-6 0 3 3 0 016 0zm3 2a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">Admin Panel</h1>
          </div>
        </div>
        
        <div class="p-4 space-y-1 overflow-y-auto flex-grow">
          <button 
            v-for="tab in tabs" 
            :key="tab.id"
            @click="activeTab = tab.id; isSidebarOpen = false;" 
            :class="{ 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300': activeTab === tab.id }" 
            class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <component :is="tab.icon" class="w-5 h-5 flex-shrink-0" />
            <span>{{ tab.label }}</span>
          </button>
        </div>

        <div class="mt-auto p-4 border-t dark:border-gray-700">
            <router-link 
                to="/" 
                class="flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
                <IconArrowLeft class="w-5 h-5" />
                <span>Back to App</span>
            </router-link>
        </div>
    </nav>
    
    <div class="flex flex-col flex-1 overflow-hidden">
        <header class="bg-white dark:bg-gray-800 border-b dark:border-gray-700 p-4 flex items-center shadow-sm flex-shrink-0 md:hidden">
            <button @click="isSidebarOpen = !isSidebarOpen" class="text-gray-500 dark:text-gray-400">
                <IconMenu class="h-6 w-6" />
            </button>
            <h1 class="ml-4 text-xl font-bold text-gray-900 dark:text-gray-100">Admin Panel</h1>
        </header>

        <main class="flex-grow overflow-y-auto p-6">
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
        </main>
    </div>
  </div>
</template>