<script setup>
import { computed } from 'vue';
import { useAuthStore } from './stores/auth';
import { useUiStore } from './stores/ui';
import HomeView from './views/HomeView.vue';
import LoginModal from './components/modals/LoginModal.vue';
import SettingsModal from './components/modals/SettingsModal.vue';
import RenameDiscussionModal from './components/modals/RenameDiscussionModal.vue';
import PersonalityEditorModal from './components/modals/PersonalityEditorModal.vue';
import ConfirmationModal from './components/ui/ConfirmationModal.vue';
import ImageViewerModal from './components/ui/ImageViewerModal.vue';
import SourceModal from './components/modals/SourceModal.vue';
import NotificationPanel from './components/ui/NotificationPanel.vue';

// Import RAG management modals
import DataStoresModal from './components/modals/DataStoresModal.vue';
import DataStoreEditorModal from './components/modals/DataStoreEditorModal.vue';
import ShareDataStoreModal from './components/modals/ShareDataStoreModal.vue';
import FileManagementModal from './components/modals/FileManagementModal.vue';

// Import new Data modals
import ExportModal from './components/modals/ExportModal.vue';
import ImportModal from './components/modals/ImportModal.vue';

import logoUrl from './assets/logo.png';

const authStore = useAuthStore();
const uiStore = useUiStore();

// Reactive check for which modals are open
const isLoginOpen = computed(() => uiStore.isModalOpen('login'));
const isSettingsOpen = computed(() => uiStore.isModalOpen('settings'));
const isRenameOpen = computed(() => uiStore.isModalOpen('renameDiscussion'));
const isPersonalityEditorOpen = computed(() => uiStore.isModalOpen('personalityEditor'));
const isSourceViewerOpen = computed(() => uiStore.isModalOpen('sourceViewer'));

// RAG modals
const isDataStoresOpen = computed(() => uiStore.isModalOpen('dataStores'));
const isDataStoreEditorOpen = computed(() => uiStore.isModalOpen('dataStoreEditor'));
const isShareDataStoreOpen = computed(() => uiStore.isModalOpen('shareDataStore'));
const isFileManagementOpen = computed(() => uiStore.isModalOpen('fileManagement'));

// Import/Export modals
const isExportOpen = computed(() => uiStore.isModalOpen('export'));
const isImportOpen = computed(() => uiStore.isModalOpen('import'));


// Initial check for authentication and theme
authStore.attemptInitialAuth();
uiStore.initializeTheme();

</script>

<template>
  <div class="h-screen w-screen overflow-hidden font-sans antialiased text-gray-800 dark:text-gray-100 bg-gray-100 dark:bg-gray-900">
    <!-- Main App Loading Screen -->
    <div v-if="authStore.isAuthenticating" class="fixed inset-0 z-[100] flex flex-col items-center justify-center text-center p-4 bg-gray-100 dark:bg-gray-900">
        <img :src="logoUrl" alt="Loading LoLLMs" class="h-20 w-20 md:h-24 md:w-24 mx-auto mb-6 animate-pulse" />
        <p class="text-2xl md:text-3xl font-bold mb-3 text-gray-800 dark:text-gray-100">Loading Application...</p>
        <p class="text-sm md:text-base text-gray-500">Please wait while we set things up.</p>
    </div>

    <!-- Main App View -->
    <HomeView v-else />

    <!-- Global Modals -->
    <LoginModal v-if="isLoginOpen" />
    <SettingsModal v-if="isSettingsOpen" />
    <RenameDiscussionModal v-if="isRenameOpen" />
    <PersonalityEditorModal v-if="isPersonalityEditorOpen" />
    <SourceModal v-if="isSourceViewerOpen" />

    <!-- RAG Modals -->
    <DataStoresModal v-if="isDataStoresOpen" />
    <DataStoreEditorModal v-if="isDataStoreEditorOpen" />
    <ShareDataStoreModal v-if="isShareDataStoreOpen" />
    <FileManagementModal v-if="isFileManagementOpen" />

    <!-- Data Modals -->
    <ExportModal v-if="isExportOpen" />
    <ImportModal v-if="isImportOpen" />

    <!-- UI Components -->
    <ConfirmationModal v-if="uiStore.isConfirmationVisible" />
    <ImageViewerModal v-if="uiStore.isImageViewerOpen" />
    <NotificationPanel />
  </div>
</template>

<style>
/* Base application styles are in src/assets/css/main.css */
</style>