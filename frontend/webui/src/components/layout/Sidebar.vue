<script setup>
import { computed } from 'vue';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import UserInfo from './UserInfo.vue';
import DiscussionList from './DiscussionList.vue';

import logoDefault from '../../assets/logo.png';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconHome from '../../assets/icons/IconHome.vue';
import IconSettings from '../../assets/icons/IconSettings.vue';
import IconMenu from '../../assets/icons/IconMenu.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue'; // NEW IMPORT
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const user = computed(() => authStore.user);
const isSidebarOpen = computed(() => uiStore.isSidebarOpen);
const logoSrc = computed(() => authStore.welcome_logo_url || logoDefault);

</script>

<template>
  <aside class="flex-shrink-0 flex flex-col h-full bg-gray-100 dark:bg-gray-800 border-r dark:border-gray-700 transition-all duration-300 ease-in-out" :class="isSidebarOpen ? 'w-80' : 'w-20'">
    
    <!-- Redesigned Persistent Header -->
    <header class="flex items-center p-3 border-b dark:border-gray-700 flex-shrink-0 h-16" :class="isSidebarOpen ? 'justify-between' : 'justify-center'">
        <div v-if="isSidebarOpen" class="flex items-center space-x-3 min-w-0">
            <img :src="logoSrc" alt="LoLLMs Logo" class="h-8 w-8 flex-shrink-0 object-contain" @error="($event.target.src=logoDefault)">
            <div class="min-w-0">
                <h1 class="text-lg font-bold text-gray-800 dark:text-gray-100 truncate">LoLLMs</h1>
                <p class="text-xs text-gray-500 truncate">One tool to rule them all</p>
            </div>
        </div>
        
        <button @click="uiStore.toggleSidebar" class="p-2 rounded-full text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors" :title="isSidebarOpen ? 'Collapse Sidebar' : 'Expand Sidebar'">
            <IconArrowLeft class="w-6 h-6 transition-transform duration-300" :class="{ 'rotate-180': isSidebarOpen }" />
        </button>
    </header>
    
    <!-- Main Content Area -->
    <div class="flex-1 min-h-0">
      <!-- Expanded Content -->
      <DiscussionList v-if="isSidebarOpen" class="h-full overflow-y-auto" />

      <!-- Collapsed Content -->
      <div v-else class="h-full flex flex-col items-center py-4 space-y-4">
        <button @click="discussionsStore.createNewDiscussion()" class="p-3 bg-blue-500 text-white rounded-full shadow-lg hover:bg-blue-600 transition-colors" title="New Discussion">
          <IconPlus class="w-6 h-6" />
        </button>
        <button v-if="user && user.user_ui_level >= 2" @click="uiStore.setMainView('feed')" class="p-3 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors" title="Feed">
          <IconHome class="w-6 h-6 text-gray-500 dark:text-gray-400" />
        </button>
        <router-link to="/help" class="block p-3 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors" title="Help">
          <IconBookOpen class="w-6 h-6 text-gray-500 dark:text-gray-400" />
        </router-link>
        <router-link to="/settings" class="block p-3 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors" title="Settings">
          <IconSettings class="w-6 h-6 text-gray-500 dark:text-gray-400" />
        </router-link>
      </div>
    </div>
    
    <!-- User Info Footer -->
    <div class="p-3 border-t dark:border-gray-700 flex-shrink-0">
      <UserInfo />
    </div>
  </aside>
</template>