<!-- frontend/webui/src/App.vue -->
<script setup>
import { computed, onMounted } from 'vue';
import { useAuthStore } from './stores/auth';
import { useUiStore } from './stores/ui';
import { usePyodideStore } from './stores/pyodide';
import { useTasksStore } from './stores/tasks';
import { useDiscussionsStore } from './stores/discussions'; // NEW

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

const authStore = useAuthStore();
const uiStore = useUiStore();
const pyodideStore = usePyodideStore();
const tasksStore = useTasksStore();
const discussionsStore = useDiscussionsStore(); // NEW

const activeModal = computed(() => uiStore.activeModal);

// NEW computed property: determines if the main content (router-view) or the loading screen should be shown
// This ensures the first admin modal can appear on top during initial load.
const showMainContentOrLoading = computed(() => {
    // If the first admin setup modal is active, we render nothing else but the modal itself
    // The modal is handled directly in the template.
    if (activeModal.value === 'firstAdminSetup') {
        return 'modal_only'; 
    }
    // If we're still authenticating and the first admin modal is not active, show loading screen
    if (authStore.isAuthenticating) {
        return 'loading';
    }
    // Otherwise, show the main content (router-view)
    return 'main_content';
});


onMounted(async () => {
    uiStore.initializeTheme();
    await authStore.attemptInitialAuth();
    uiStore.initializeSidebarState();
    // Pyodide and Tasks initialization should only happen if authentication is successful
    // and we're not stuck in a setup flow.
    if (authStore.isAuthenticated) {
        pyodideStore.initialize();
        tasksStore.startPolling();
        discussionsStore.initialize(); // NEW
    }
});
</script>

<template>
  <div class="h-screen w-screen overflow-hidden font-sans antialiased text-gray-800 dark:text-gray-100 bg-gray-100 dark:bg-gray-900">
    
    <!-- Conditional rendering based on showMainContentOrLoading -->
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

    <!-- Render router-view only if not loading and not in admin setup -->
    <router-view v-else-if="showMainContentOrLoading === 'main_content'" />

    <!-- Modals are rendered always, but only visible when activeModal matches -->
    <!-- This ensures the firstAdminSetup modal can appear even if isAuthenticating is still true -->
    <ResetPasswordModal v-if="activeModal === 'resetPassword'" />
    <LoginModal v-if="activeModal === 'login'" />
    <RegisterModal v-if="activeModal === 'register'" />
    <ForgotPasswordModal v-if="activeModal === 'forgotPassword'" />
    <PasswordResetLinkModal v-if="activeModal === 'passwordResetLink'" />
    <RenameDiscussionModal v-if="activeModal === 'renameDiscussion'" />
    <PersonalityEditorModal v-if="activeModal === 'personalityEditor'" />
    <AdminUserEditModal v-if="activeModal === 'adminUserEdit'" />
    <ForceSettingsModal v-if="activeModal === 'forceSettings'" />
    <SourceModal v-if="activeModal === 'sourceViewer'" />
    <ContextViewModal v-if="activeModal === 'contextViewer'" />
    <ShareDataStoreModal v-if="activeModal === 'shareDataStore'" />
    <ShareDiscussionModal v-if="activeModal === 'shareDiscussion'" />
    <ExportModal v-if="activeModal === 'export'" />
    <ImportModal v-if="activeModal === 'import'" />
    <InteractiveOutputModal v-if="activeModal === 'interactiveOutput'" />
    <EmailAllUsersModal v-if="activeModal === 'emailAllUsers'" />
    <EmailUserModal v-if="activeModal === 'adminUserEmail'" />
    <InsertImageModal v-if="activeModal === 'insertImage'" />
    <NewApiKeyModal v-if="activeModal === 'newApiKey'" />
    <AppInstallModal v-if="activeModal === 'appInstall'" />
    <AppDetailsModal v-if="activeModal === 'appDetails'" />
    <AppConfigModal v-if="activeModal === 'appConfig'" />
    <WhatsNextModal v-if="activeModal === 'whatsNext'" />
    <!-- Ensure CreateFirstAdminModal is rendered if it's the active modal, regardless of loading state -->
    <CreateFirstAdminModal v-if="activeModal === 'firstAdminSetup'" /> 
    <GeneratePersonalityModal v-if="activeModal === 'generatePersonality'" />
    <EnhancePersonalityPromptModal v-if="activeModal === 'enhancePersonalityPrompt'" />
    <TasksManagerModal v-if="activeModal === 'tasksManager'" />
    
    <ImageViewerModal v-if="uiStore.isImageViewerOpen" />
    <NotificationPanel />
    <ConfirmationModal v-if="activeModal === 'confirmation'" />
  </div>
</template>