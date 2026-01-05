<script setup>
import { computed, ref, onMounted, onUnmounted, watch, defineAsyncComponent } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useDiscussionsStore } from '../../stores/discussions';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import { useImageStore } from '../../stores/images';
import DiscussionList from './DiscussionList.vue';

import logoDefault from '../../assets/logo.png';
import IconPlus from '../../assets/icons/IconPlus.vue';
import IconHome from '../../assets/icons/IconHome.vue';
import IconSettings from '../../assets/icons/IconSettings.vue';
import IconMenu from '../../assets/icons/IconMenu.vue';
import IconBookOpen from '../../assets/icons/IconBookOpen.vue';
import IconFileText from '../../assets/icons/IconFileText.vue';
import IconServer from '../../assets/icons/IconServer.vue';
import IconDatabase from '../../assets/icons/IconDatabase.vue';
import IconShare from '../../assets/icons/IconShare.vue';

// Async import for Flow Wizard
const FlowWizardModal = defineAsyncComponent(() => import('../flow/FlowWizardModal.vue'));

const discussionsStore = useDiscussionsStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const imageStore = useImageStore();
const route = useRoute();
const router = useRouter();

const user = computed(() => authStore.user);
const isSidebarOpen = computed(() => uiStore.isSidebarOpen);
const logoSrc = computed(() => authStore.welcome_logo_url || logoDefault);

const activityTimeout = ref(null);
const sidebarRef = ref(null);
const isFlowWizardOpen = ref(false);

function goToFeed() {
    uiStore.setMainView('feed');
}

const resetActivityTimer = () => {
    clearTimeout(activityTimeout.value);
    if (isSidebarOpen.value) {
        activityTimeout.value = setTimeout(() => {
            // Automatically collapse sidebar after inactivity
            uiStore.closeSidebar();
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
        // Desktop interactions
        sidebarElement.addEventListener('mousemove', resetActivityTimer);
        sidebarElement.addEventListener('mousedown', resetActivityTimer);
        sidebarElement.addEventListener('wheel', resetActivityTimer, { passive: true });
        
        // Mobile interactions
        sidebarElement.addEventListener('touchstart', resetActivityTimer, { passive: true });
        sidebarElement.addEventListener('touchmove', resetActivityTimer, { passive: true });
        sidebarElement.addEventListener('scroll', resetActivityTimer, { passive: true });
        
        // Keyboard interactions
        sidebarElement.addEventListener('keydown', resetActivityTimer);
    }
    resetActivityTimer();
});

onUnmounted(() => {
    const sidebarElement = sidebarRef.value;
    if (sidebarElement) {
        sidebarElement.removeEventListener('mousemove', resetActivityTimer);
        sidebarElement.removeEventListener('mousedown', resetActivityTimer);
        sidebarElement.removeEventListener('wheel', resetActivityTimer);
        sidebarElement.removeEventListener('touchstart', resetActivityTimer);
        sidebarElement.removeEventListener('touchmove', resetActivityTimer);
        sidebarElement.removeEventListener('scroll', resetActivityTimer);
        sidebarElement.removeEventListener('keydown', resetActivityTimer);
    }
    clearTimeout(activityTimeout.value);
});

// Context-aware logic for the Plus button in collapsed mode
const currentContext = computed(() => {
    const path = route.path;
    if (path.startsWith('/notebooks')) return 'notebooks';
    if (path.startsWith('/datastores')) return 'data';
    if (path.startsWith('/flow-studio')) return 'flows';
    if (path.startsWith('/image-studio')) return 'images';
    return 'chat';
});

const plusButtonTitle = computed(() => {
    switch (currentContext.value) {
        case 'notebooks': return 'New Notebook';
        case 'data': return 'New Data Store';
        case 'flows': return 'New Workflow';
        case 'images': return 'New Album';
        default: return 'New Discussion';
    }
});

async function handlePlusClick() {
    switch (currentContext.value) {
        case 'notebooks':
            uiStore.openModal('notebookWizard');
            break;
        case 'data':
            if (route.path !== '/datastores') await router.push('/datastores');
            setTimeout(() => window.dispatchEvent(new CustomEvent('lollms:open-new-datastore')), 100);
            break;
        case 'flows':
            isFlowWizardOpen.value = true;
            break;
        case 'images':
            const { confirmed, value } = await uiStore.showConfirmation({
                title: 'New Album',
                message: 'Enter a name for your new album:',
                confirmText: 'Create',
                inputType: 'text',
                inputPlaceholder: 'Album Name'
            });
            if (confirmed && value) {
                await imageStore.createAlbum(value);
            }
            break;
        case 'chat':
        default:
            discussionsStore.createNewDiscussion();
            break;
    }
}
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
          @click="handlePlusClick" 
          class="p-3 bg-blue-600 text-white rounded-lg shadow-sm hover:bg-blue-700 transition-colors" 
          :title="plusButtonTitle"
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
          to="/notebooks"
          class="block p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-gray-700 transition-colors" 
          title="Notebook Studio"
        >
            <IconServer class="w-5 h-5 text-purple-500" />
        </router-link>

        <router-link
          to="/datastores"
          class="block p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-gray-700 transition-colors" 
          title="Data Studio"
        >
            <IconDatabase class="w-5 h-5 text-green-500" />
        </router-link>

        <router-link
          to="/flow-studio"
          class="block p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-gray-700 transition-colors" 
          title="Flow Studio"
        >
            <IconShare class="w-5 h-5 text-cyan-500" />
        </router-link>

        <router-link
          to="/news"
          class="block p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-gray-700 transition-colors" 
          title="News"
        >
            <IconFileText class="w-5 h-5 text-slate-500 dark:text-gray-400" />
        </router-link>

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

    <!-- Modals for Collapsed State -->
    <Teleport to="body">
        <FlowWizardModal v-if="isFlowWizardOpen" @close="isFlowWizardOpen = false" />
    </Teleport>
  </aside>
</template>
