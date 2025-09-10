<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue';
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
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconArrowLeft from '../../assets/icons/IconArrowLeft.vue';

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const user = computed(() => authStore.user);
const isSidebarOpen = computed(() => uiStore.isSidebarOpen);
const logoSrc = computed(() => authStore.welcome_logo_url || logoDefault);

const activityTimeout = ref(null);
const sidebarRef = ref(null);

function goToFeed() {
    console.log("Feed button clicked in Sidebar.");
    uiStore.setMainView('feed');
}

const resetActivityTimer = () => {
    clearTimeout(activityTimeout.value);
    if (isSidebarOpen.value) {
        activityTimeout.value = setTimeout(() => {
            // Do not auto-close on mobile where it's an overlay
            if (window.innerWidth > 768) {
                uiStore.closeSidebar();
            }
        }, 30000); // 30 seconds
    }
};

watch(isSidebarOpen, (isOpen) => {
    if (isOpen) {
        resetActivityTimer();
    } else {
        clearTimeout(activityTimeout.value);
    }
});

onMounted(() => {
    const sidebarElement = sidebarRef.value;
    if (sidebarElement) {
        sidebarElement.addEventListener('mousemove', resetActivityTimer);
        sidebarElement.addEventListener('mousedown', resetActivityTimer);
    }
    resetActivityTimer(); // Initial timer start
});

onUnmounted(() => {
    const sidebarElement = sidebarRef.value;
    if (sidebarElement) {
        sidebarElement.removeEventListener('mousemove', resetActivityTimer);
        sidebarElement.removeEventListener('mousedown', resetActivityTimer);
    }
    clearTimeout(activityTimeout.value);
});
</script>

<template>
  <aside ref="sidebarRef" class="flex-shrink-0 flex flex-col h-full bg-white dark:bg-gray-900 border-r border-slate-200 dark:border-gray-700 transition-all duration-300 ease-in-out" 
         :class="isSidebarOpen ? 'w-80' : 'w-16'">
    
    <!-- Main Content Area -->
    <div class="flex-1 min-h-0">
      <!-- Expanded Content -->
      <DiscussionList v-if="isSidebarOpen" class="h-full" />

      <!-- Collapsed Content -->
      <div v-else class="h-full flex flex-col items-center py-4 space-y-3">
        <!-- Collapsed Toggle -->
        <button 
          @click="uiStore.toggleSidebar" 
          class="p-2 rounded-lg text-slate-500 dark:text-gray-400 hover:bg-slate-100 dark:hover:bg-gray-700 transition-colors mb-2" 
          title="Expand Sidebar"
        >
          <IconMenu class="w-5 h-5" />
        </button>

        <!-- Quick Actions -->
        <button 
          @click="discussionsStore.createNewDiscussion()" 
          class="p-3 bg-blue-600 text-white rounded-lg shadow-sm hover:bg-blue-700 transition-colors" 
          title="New Discussion"
        >
          <IconPlus class="w-5 h-5" />
        </button>

        <button 
          v-if="user && user.user_ui_level >= 2" 
          @click="goToFeed" 
          class="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-gray-700 transition-colors" 
          title="Feed"
        >
          <IconHome class="w-5 h-5 text-slate-500 dark:text-gray-400" />
        </button>

        <router-link 
          to="/help" 
          class="block p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-gray-700 transition-colors" 
          title="Help"
        >
          <IconBookOpen class="w-5 h-5 text-slate-500 dark:text-gray-400" />
        </router-link>

        <router-link 
          to="/settings" 
          class="block p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-gray-700 transition-colors" 
          title="Settings"
        >
          <IconSettings class="w-5 h-5 text-slate-500 dark:text-gray-400" />
        </router-link>
      </div>
    </div>
    
    <!-- Compact User Info Footer -->
    <div class="border-t border-slate-200 dark:border-gray-700 flex-shrink-0" :class="isSidebarOpen ? 'p-3' : 'p-2'">
      <UserInfo />
    </div>
  </aside>
</template>