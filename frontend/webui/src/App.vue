<script setup>
import { computed, onMounted, watch } from 'vue';
import { useAuthStore } from './stores/auth';
import { useUiStore } from './stores/ui';
import { usePyodideStore } from './stores/pyodide';
import { useSocialStore } from './stores/social';

import LoginModal from './components/modals/LoginModal.vue';
import RegisterModal from './components/modals/RegisterModal.vue';
import RenameDiscussionModal from './components/modals/RenameDiscussionModal.vue';
import PersonalityEditorModal from './components/modals/PersonalityEditorModal.vue';
import AdminUserEditModal from './components/modals/AdminUserEditModal.vue';
import ConfirmationModal from './components/ui/ConfirmationModal.vue';
import ImageViewerModal from './components/ui/ImageViewerModal.vue';
import SourceModal from './components/modals/SourceModal.vue';
import NotificationPanel from './components/ui/NotificationPanel.vue';
import DataStoresModal from './components/modals/DataStoresModal.vue';
import DataStoreEditorModal from './components/modals/DataStoreEditorModal.vue';
import ShareDataStoreModal from './components/modals/ShareDataStoreModal.vue';
import FileManagementModal from './components/modals/FileManagementModal.vue';
import ExportModal from './components/modals/ExportModal.vue';
import ImportModal from './components/modals/ImportModal.vue';
import InteractiveOutputModal from './components/modals/InteractiveOutputModal.vue';
import ShareDiscussionModal from './components/modals/ShareDiscussionModal.vue';
import ResetPasswordModal from './components/modals/ResetPasswordModal.vue';
import logoUrl from './assets/logo.png';

const authStore = useAuthStore();
const uiStore = useUiStore();
const pyodideStore = usePyodideStore();
const socialStore = useSocialStore();

const activeModal = computed(() => uiStore.activeModal);

onMounted(async () => {
    await authStore.attemptInitialAuth();
    uiStore.initializeTheme();
    if (authStore.isAuthenticated) {
        pyodideStore.initialize();
    }
});

watch(
  () => authStore.isAuthenticated,
  (isNowAuthenticated) => {
    const canUseChat = authStore.user?.chat_active && authStore.user?.user_ui_level >= 2;

    if (isNowAuthenticated && canUseChat) {
      console.log("User authenticated with chat permissions, connecting to real-time DM service...");
      socialStore.connectWebSocket();
    } else {
      console.log("User not authenticated or no chat permissions, disconnecting from real-time DM service...");
      socialStore.disconnectWebSocket();
    }
  },
  {
    immediate: true,
  }
);
</script>

<template>
  <div class="h-screen w-screen overflow-hidden font-sans antialiased text-gray-800 dark:text-gray-100 bg-gray-100 dark:bg-gray-900">
    <div v-if="authStore.isAuthenticating" class="fixed inset-0 z-[100] flex flex-col items-center justify-center text-center p-4 bg-gray-100 dark:bg-gray-900">
        <img :src="logoUrl" alt="Loading LoLLMs" class="h-20 w-20 md:h-24 md:w-24 mx-auto mb-6 animate-pulse" />
        <p class="text-2xl md:text-3xl font-bold mb-3 text-gray-800 dark:text-gray-100">Loading Application...</p>
        <p class="text-sm md:text-base text-gray-500">Please wait while we set things up.</p>
    </div>

    <router-view v-else />

    <LoginModal v-if="activeModal === 'login'" />
    <RegisterModal v-if="activeModal === 'register'" />
    <RenameDiscussionModal v-if="activeModal === 'renameDiscussion'" />
    <PersonalityEditorModal v-if="activeModal === 'personalityEditor'" />
    <AdminUserEditModal v-if="activeModal === 'adminUserEdit'" />
    <SourceModal v-if="activeModal === 'sourceViewer'" />
    <DataStoresModal v-if="activeModal === 'dataStores'" />
    <DataStoreEditorModal v-if="activeModal === 'dataStoreEditor'" />
    <ShareDataStoreModal v-if="activeModal === 'shareDataStore'" />
    <ShareDiscussionModal v-if="activeModal === 'shareDiscussion'" />
    <FileManagementModal v-if="activeModal === 'fileManagement'" />
    <ExportModal v-if="activeModal === 'export'" />
    <ImportModal v-if="activeModal === 'import'" />
    <InteractiveOutputModal v-if="activeModal === 'interactiveOutput'" />
    <ResetPasswordModal v-if="activeModal === 'resetPassword'" />
    
    <ImageViewerModal v-if="uiStore.isImageViewerOpen" />
    <NotificationPanel />
    <ConfirmationModal v-if="activeModal === 'confirmation'" />
  </div>
</template>