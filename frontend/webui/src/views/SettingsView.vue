<script setup>
import { ref, defineAsyncComponent, computed } from 'vue';
import { useAuthStore } from '../stores/auth';

const AccountSettings = defineAsyncComponent(() => import('../components/settings/AccountSettings.vue'));
const GeneralSettings = defineAsyncComponent(() => import('../components/settings/GeneralSettings.vue'));
const LLMSettings = defineAsyncComponent(() => import('../components/settings/LLMSettings.vue'));
const PersonalitiesSettings = defineAsyncComponent(() => import('../components/settings/PersonalitiesSettings.vue'));
const RAGSettings = defineAsyncComponent(() => import('../components/settings/RAGSettings.vue'));
const MCPSettings = defineAsyncComponent(() => import('../components/settings/MCPSettings.vue'));
const AdminPanel = defineAsyncComponent(() => import('../components/admin/AdminPanel.vue'));

const authStore = useAuthStore();

const activeTab = ref('account');
const isSidebarOpen = ref(false);

const tabs = [
    { id: 'account', label: 'Account', icon: '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>', component: AccountSettings },
    { id: 'general', label: 'General', icon: '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 0 1 1.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.108 1.204.165.397.505.71.93.78l.893.15c.543.09.94.56.94 1.11v1.093c0 .55-.397 1.02-.94 1.11l-.893.149c-.425.07-.765.383-.93.78-.165.398-.143.854.108 1.204l.527.738c.32.447.27.96-.12 1.45l-.774.773a1.125 1.125 0 0 1-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.108-.397.165-.71.505-.78.93l-.15.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.149-.894c-.07-.424-.384-.764-.78-.93-.398-.164-.855-.142-1.205.108l-.737.527a1.125 1.125 0 0 1-1.45-.12l-.773-.774a1.125 1.125 0 0 1-.12-1.45l.527-.737c.25-.35.272.806.108 1.204-.165-.397-.505.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.11v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.765-.383.93-.78.165-.398.143.854-.108-1.204l-.527-.738a1.125 1.125 0 0 1 .12-1.45l.773-.773a1.125 1.125 0 0 1 1.45-.12l.737.527c.35.25.806.272 1.203.108.397-.165.71.505.78-.93l.15-.894Z" /></svg>', component: GeneralSettings },
    { id: 'llmConfig', label: 'LLM Config', icon: '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>', component: LLMSettings },
    { id: 'personalities', label: 'Personalities', icon: '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0zm6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>', component: PersonalitiesSettings },
    { id: 'rag', label: 'RAG', minLevel: 1, icon: '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>', component: RAGSettings },
    { id: 'services', label: 'Services', minLevel: 3, icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5"><path d="M12.25 10a.75.75 0 0 0-.75-.75H3.143a.75.75 0 0 1 0-1.5h8.357a.75.75 0 0 0 0-1.5H3.143a.75.75 0 0 1 0-1.5h8.357a.75.75 0 0 0 0-1.5H3.143a.75.75 0 0 1 0-1.5h8.357a.75.75 0 0 0 .75-.75V1.25a.75.75 0 0 0-1.5 0v.513a4.49 4.49 0 0 0-3.337 2.237 1.99 1.99 0 0 0-1.732 0 4.49 4.49 0 0 0-3.337-2.237V1.25a.75.75 0 0 0-1.5 0v.513A4.5 4.5 0 0 0 4.3 4.987a1.99 1.99 0 0 0 0 1.732 4.5 4.5 0 0 0-2.513 2.725V10l-1.06.002a.75.75 0 0 0 0 1.5l1.06.002v.268a4.5 4.5 0 0 0 2.513 2.725 1.99 1.99 0 0 0 0 1.732 4.5 4.5 0 0 0-2.513 2.725v.513a.75.75 0 0 0 1.5 0v-.513a4.49 4.49 0 0 0 3.337-2.237 1.99 1.99 0 0 0 1.732 0 4.49 4.49 0 0 0 3.337 2.237v.513a.75.75 0 0 0 1.5 0v-.513a4.5 4.5 0 0 0 2.513-2.725 1.99 1.99 0 0 0 0-1.732 4.5 4.5 0 0 0 2.513-2.725V11.5l1.06-.002a.75.75 0 0 0 0-1.5l-1.06-.002V10Z" /></svg>', component: MCPSettings },
    { id: 'admin', label: 'Administration', icon: '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M15 21v-1.5a6.375 6.375 0 00-3.262-5.171M9 10a3 3 0 11-6 0 3 3 0 016 0zm3 2a3 3 0 11-6 0 3 3 0 016 0z" /></svg>', adminOnly: true, component: AdminPanel }
];

const user = computed(() => authStore.user);

const visibleTabs = computed(() => {
    if (!user.value) return [];
    return tabs.filter(tab => {
        if (tab.adminOnly && !user.value.is_admin) return false;
        if (tab.minLevel && user.value.user_ui_level < tab.minLevel) return false;
        return true;
    });
});

const activeComponent = computed(() => {
    const active = visibleTabs.value.find(t => t.id === activeTab.value);
    return active ? active.component : null;
});
</script>

<template>
  <div class="flex h-screen bg-gray-100 dark:bg-gray-900 overflow-hidden">
    <!-- Mobile Sidebar Overlay -->
    <div v-if="isSidebarOpen" @click="isSidebarOpen = false" class="fixed inset-0 bg-black/30 z-20 md:hidden"></div>

    <!-- Sidebar Navigation -->
    <nav class="fixed inset-y-0 left-0 z-30 w-64 bg-white dark:bg-gray-800 border-r dark:border-gray-700 flex flex-col transform transition-transform md:relative md:translate-x-0"
         :class="{'-translate-x-full': !isSidebarOpen}">
        
        <!-- Main Tab Links -->
        <div class="p-4 space-y-1 overflow-y-auto">
          <button 
            v-for="tab in visibleTabs" 
            :key="tab.id"
            @click="activeTab = tab.id; isSidebarOpen = false;" 
            :class="{ 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300': activeTab === tab.id }" 
            class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <span v-html="tab.icon" class="w-5 h-5 flex-shrink-0"></span>
            <span>{{ tab.label }}</span>
          </button>
        </div>

        <!-- Back Button at the bottom -->
        <div class="mt-auto p-4 border-t dark:border-gray-700">
            <router-link 
                to="/" 
                class="flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
                <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M11 15l-3-3m0 0l3-3m-3 3h8a5 5 0 000-10H6" />
                </svg>
                <span>Back to App</span>
            </router-link>
        </div>
    </nav>
    
    <!-- Main Content Area -->
    <div class="flex flex-col flex-1 overflow-hidden">
        <!-- Header -->
        <header class="bg-white dark:bg-gray-800 border-b dark:border-gray-700 p-4 flex items-center shadow-sm flex-shrink-0">
            <!-- Mobile Menu Button -->
            <button @click="isSidebarOpen = !isSidebarOpen" class="md:hidden mr-4 text-gray-500 dark:text-gray-400">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
            </button>
            
            <div class="flex items-center space-x-3">
                <!-- Cleaner "Settings" Icon -->
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6 text-gray-500 dark:text-gray-400"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 0 1 0 1.255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.063-.374-.313-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 0 1 0-1.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>
                <h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">Settings</h1>
            </div>
        </header>

        <!-- Selected Tab Content -->
        <main class="flex-grow overflow-y-auto p-6">
            <Suspense>
                <template #default>
                    <component v-if="activeComponent" :is="activeComponent" />
                    <div v-else class="text-center text-gray-500 dark:text-gray-400">
                        <p>Select a category to view settings.</p>
                    </div>
                </template>
                <template #fallback>
                    <div class="flex items-center justify-center h-full">
                        <p class="text-lg text-gray-500 dark:text-gray-400 italic">Loading settings...</p>
                    </div>
                </template>
            </Suspense>
        </main>
    </div>
  </div>
</template>