<script setup>
import { ref, defineAsyncComponent, computed } from 'vue';
import { useAuthStore } from '../stores/auth';

// --- Import new icons ---
import IconUserCircle from '../assets/icons/IconUserCircle.vue';
import IconSettings from '../assets/icons/IconSettings.vue';
import IconCog from '../assets/icons/IconCog.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconDatabase from '../assets/icons/IconDatabase.vue';
import IconWrenchScrewdriver from '../assets/icons/IconWrenchScrewdriver.vue';
import IconKey from '../assets/icons/IconKey.vue';
import IconArrowLeft from '../assets/icons/IconArrowLeft.vue';
import IconMenu from '../assets/icons/IconMenu.vue';
// --- End new icons ---

const AccountSettings = defineAsyncComponent(() => import('../components/settings/AccountSettings.vue'));
const GeneralSettings = defineAsyncComponent(() => import('../components/settings/GeneralSettings.vue'));
const LLMSettings = defineAsyncComponent(() => import('../components/settings/LLMSettings.vue'));
const PersonalitiesSettings = defineAsyncComponent(() => import('../components/settings/PersonalitiesSettings.vue'));
const RAGSettings = defineAsyncComponent(() => import('../components/settings/RAGSettings.vue'));
const MCPSettings = defineAsyncComponent(() => import('../components/settings/MCPSettings.vue'));
const ApiKeysSettings = defineAsyncComponent(() => import('../components/settings/ApiKeysSettings.vue'));

const authStore = useAuthStore();

const activeTab = ref('account');
const isSidebarOpen = ref(false);

const tabs = [
    { id: 'account', label: 'Account', icon: IconUserCircle, component: AccountSettings },
    { id: 'general', label: 'General', icon: IconSettings, component: GeneralSettings },
    { id: 'llmConfig', label: 'LLM Config', icon: IconCog, component: LLMSettings },
    { id: 'personalities', label: 'Personalities', icon: IconSparkles, component: PersonalitiesSettings },
    { id: 'rag', label: 'RAG', minLevel: 1, icon: IconDatabase, component: RAGSettings },
    { id: 'services', label: 'Services', minLevel: 3, icon: IconWrenchScrewdriver, component: MCPSettings },
    { id: 'apiKeys', label: 'API Keys', minLevel: 2, icon: IconKey, component: ApiKeysSettings }
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
            <component :is="tab.icon" class="w-5 h-5 flex-shrink-0" />
            <span>{{ tab.label }}</span>
          </button>
        </div>

        <!-- Back Button at the bottom -->
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
    
    <!-- Main Content Area -->
    <div class="flex flex-col flex-1 overflow-hidden">
        <!-- Header -->
        <header class="bg-white dark:bg-gray-800 border-b dark:border-gray-700 p-4 flex items-center shadow-sm flex-shrink-0">
            <!-- Mobile Menu Button -->
            <button @click="isSidebarOpen = !isSidebarOpen" class="md:hidden mr-4 text-gray-500 dark:text-gray-400">
                <IconMenu class="h-6 w-6" />
            </button>
            
            <div class="flex items-center space-x-3">
                <IconSettings class="w-6 h-6 text-gray-500 dark:text-gray-400" />
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