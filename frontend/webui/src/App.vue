<!-- frontend/webui/src/App.vue -->
<script setup>
import { computed, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { useAuthStore } from './stores/auth';
import { useUiStore } from './stores/ui';
import { usePyodideStore } from './stores/pyodide';
import { useTasksStore } from './stores/tasks';
import { useDiscussionsStore } from './stores/discussions'; 

// Import Layouts
import Sidebar from './components/layout/Sidebar.vue';
import GlobalHeader from './components/layout/GlobalHeader.vue';

// Import all modals
import LoginModal from './components/modals/LoginModal.vue';
import RegisterModal from './components/modals/RegisterModal.vue';
import ForgotPasswordModal from './components/modals/ForgotPasswordModal.vue';
import PasswordResetLinkModal from './components/modals/PasswordResetLinkModal.vue';
import RenameDiscussionModal from './components/modals/RenameDiscussionModal.vue';
import PersonalityEditorModal from './components/modals/PersonalityEditorModal.vue';
import AdminUserEditModal from './components/modals/AdminUserEditModal.vue';
import ForceSettingsModal from './components/modals/ForceSettingsModal.vue';
import ConfirmationModal from './components/ui/ConfirmationModal.vue';
import ImageViewerModal from './components/ui/ImageViewerModal.vue';
import SourceModal from './components/modals/SourceModal.vue';
import NotificationPanel from './components/ui/NotificationPanel.vue';
import ShareDataStoreModal from './components/modals/ShareDataStoreModal.vue';
import ExportModal from './components/modals/ExportModal.vue';
import ImportModal from './components/modals/ImportModal.vue';
import InteractiveOutputModal from './components/modals/InteractiveOutputModal.vue';
import ShareDiscussionModal from './components/modals/ShareDiscussionModal.vue';
import ResetPasswordModal from './components/modals/ResetPasswordModal.vue';
import EmailAllUsersModal from './components/modals/EmailAllUsersModal.vue';
import EmailListModal from './components/modals/EmailListModal.vue';
import EmailUserModal from './components/modals/EmailUserModal.vue';
import InsertImageModal from './components/modals/InsertImageModal.vue';
import NewApiKeyModal from './components/modals/NewApiKeyModal.vue'; 
import WhatsNextModal from './components/modals/WhatsNextModal.vue';
import AppInstallModal from './components/modals/AppInstallModal.vue';
import AppDetailsModal from './components/modals/AppDetailsModal.vue';
import AppConfigModal from './components/modals/AppConfigModal.vue';
import CreateFirstAdminModal from './components/modals/CreateFirstAdminModal.vue';
import GeneratePersonalityModal from './components/modals/GeneratePersonalityModal.vue';
import TasksManagerModal from './components/modals/TasksManagerModal.vue';
import EnhancePersonalityPromptModal from './components/modals/EnhancePersonalityPromptModal.vue';
import ContextViewModal from './components/modals/ContextViewModal.vue';
import DataZonePromptManagementModal from './components/modals/DataZonePromptManagementModal.vue';
import FillPlaceholdersModal from './components/modals/FillPlaceholdersModal.vue'; // <-- ADDED IMPORT

const authStore = useAuthStore();
const uiStore = useUiStore();
const pyodideStore = usePyodideStore();
const tasksStore = useTasksStore();
const discussionsStore = useDiscussionsStore();
const route = useRoute();

const activeModal = computed(() => uiStore.activeModal);

const showMainContentOrLoading = computed(() => {
    if (activeModal.value === 'firstAdminSetup') {
        return 'modal_only'; 
    }
    if (authStore.isAuthenticating) {
        return 'loading';
    }
    return 'main_content';
});

const pageLayoutRoutes = ['Settings', 'Admin', 'DataStores', 'Friends', 'Help', 'Profile', 'Messages'];
const isHomePageLayout = computed(() => !pageLayoutRoutes.includes(route.name));


onMounted(async () => {
    uiStore.initializeTheme();
    await authStore.attemptInitialAuth();
    uiStore.initializeSidebarState();
    if (authStore.isAuthenticated) {
        pyodideStore.initialize();
        tasksStore.startPolling();
        discussionsStore.initialize();
    }
});
</script>

<template>
  <div class="h-screen w-screen overflow-hidden font-sans antialiased text-gray-800 dark:text-gray-100 bg-gray-100 dark:bg-gray-900">
    
    <!-- Loading Screen -->
    <div v-if="showMainContentOrLoading === 'loading'" class="fixed inset-0 z-[100] flex flex-col items-center justify-center text-center p-4 bg-gray-100 dark:bg-gray-900">
        <div class="w-full max-w-lg mx-auto">
            <h1 class="text-6xl md:text-7xl font-bold text-yellow-600 dark:text-yellow-400 drop-shadow-lg" style="font-family: 'Exo 2', sans-serif;">LoLLMs</h1>
            <p class="mt-2 text-xl md:text-2xl text-gray-600 dark:text-gray-300">One tool to rule them all</p>
            <p class="mt-4 text-sm text-gray-500 dark:text-gray-400">by ParisNeo</p>
            <div v-if="authStore.funFact" class="mt-8 mx-auto max-w-md p-3 bg-gray-200 dark:bg-white/10 border border-gray-300 dark:border-white/20 rounded-lg text-sm text-left text-gray-700 dark:text-gray-200">
                <span class="font-bold text-yellow-600 dark:text-yellow-300">🤓 Fun Fact:</span> {{ authStore.funFact }}
            </div>
            <div class="mt-12 w-full px-4">
                <div class="h-2.5 w-full rounded-full bg-gray-200 dark:bg-gray-600">
                    <div class="h-2.5 rounded-full bg-gradient-to-r from-cyan-400 to-blue-500 transition-all duration-500" :style="{ width: `${authStore.loadingProgress}%` }"></div>
                </div>
                <p class="mt-3 text-sm text-gray-600 dark:text-gray-300">{{ authStore.loadingMessage }}</p>
                <p class="mt-1 text-lg font-semibold text-gray-700 dark:text-gray-200">{{ authStore.loadingProgress }}%</p>
            </div>
        </div>
    </div>

    <!-- Main App Layout -->
    <div v-else-if="showMainContentOrLoading === 'main_content'" class="flex h-full w-full relative">
      <Sidebar v-if="isHomePageLayout" />
      <div class="flex-1 flex flex-col overflow-hidden">
        <GlobalHeader v-if="isHomePageLayout" />
        <main class="flex-1" :class="isHomePageLayout ? 'overflow-y-auto' : ''">
            <router-view />
        </main>
      </div>
    </div>

    <!-- Modals -->
    <ResetPasswordModal v-if="activeModal === 'resetPassword'" />
    <LoginModal v-if="activeModal === 'login'" />
    <RegisterModal v-if="activeModal === 'register'" />
    <ForgotPasswordModal v-if="activeModal === 'forgotPassword'" />
    <PasswordResetLinkModal v-if="activeModal === 'passwordResetLink'" />
    <RenameDiscussionModal v-if="activeModal === 'renameDiscussion'" />
    <PersonalityEditorModal v-if="activeModal === 'personalityEditor'" />
    <AdminUserEditModal v-if="activeModal === 'adminUserEdit'" />
    <ForceSettingsModal v-if="activeModal === 'forceSettings'" />
    <ConfirmationModal v-if="activeModal === 'confirmation'" />
    <ImageViewerModal v-if="uiStore.isImageViewerOpen" />
    <SourceModal v-if="activeModal === 'sourceViewer'" />
    <NotificationPanel />
    <ShareDataStoreModal v-if="activeModal === 'shareDataStore'" />
    <ExportModal v-if="activeModal === 'export'" />
    <ImportModal v-if="activeModal === 'import'" />
    <InteractiveOutputModal v-if="activeModal === 'interactiveOutput'" />
    <ShareDiscussionModal v-if="activeModal === 'shareDiscussion'" />
    <ResetPasswordModal v-if="activeModal === 'resetPassword'" />
    <EmailAllUsersModal v-if="activeModal === 'emailAllUsers'" />
    <EmailListModal v-if="activeModal === 'emailList'" />
    <EmailUserModal v-if="activeModal === 'adminUserEmail'" />
    <InsertImageModal v-if="activeModal === 'insertImage'" />
    <NewApiKeyModal v-if="activeModal === 'newApiKey'" />
    <WhatsNextModal v-if="activeModal === 'whatsNext'" />
    <AppInstallModal v-if="activeModal === 'appInstall'" />
    <AppDetailsModal v-if="activeModal === 'appDetails'" />
    <AppConfigModal v-if="activeModal === 'appConfig'" />
    <CreateFirstAdminModal v-if="activeModal === 'firstAdminSetup'" /> 
    <GeneratePersonalityModal v-if="activeModal === 'generatePersonality'" />
    <TasksManagerModal v-if="activeModal === 'tasksManager'" />
    <EnhancePersonalityPromptModal v-if="activeModal === 'enhancePersonalityPrompt'" />
    <ContextViewModal v-if="activeModal === 'contextViewer'" />
    <DataZonePromptManagementModal v-if="activeModal === 'dataZonePromptManagement'" />
    <FillPlaceholdersModal v-if="activeModal === 'fillPlaceholders'" /> <!-- <-- ADDED COMPONENT -->
    
    <ImageViewerModal v-if="uiStore.isImageViewerOpen" />
    <NotificationPanel />
    <ConfirmationModal v-if="activeModal === 'confirmation'" />
  </div>
</template>