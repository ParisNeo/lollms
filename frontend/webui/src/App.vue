<script setup>
import { computed, onMounted } from 'vue';
import { useAuthStore } from './stores/auth';
import { useUiStore } from './stores/ui';
import { usePyodideStore } from './stores/pyodide';

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

const authStore = useAuthStore();
const uiStore = useUiStore();
const pyodideStore = usePyodideStore();

const activeModal = computed(() => uiStore.activeModal);

onMounted(async () => {
    await authStore.attemptInitialAuth();
    uiStore.initializeTheme();
    uiStore.initializeSidebarState();
    if (authStore.isAuthenticated) {
        pyodideStore.initialize();
    }
});
</script>

<template>
  <div class="h-screen w-screen overflow-hidden font-sans antialiased text-gray-800 dark:text-gray-100 bg-gray-100 dark:bg-gray-900">
    
    <div v-if="authStore.isAuthenticating" class="fixed inset-0 z-[100] flex flex-col items-center justify-center text-center p-4 bg-[#2c3e50] text-white">
        <div class="w-full max-w-lg mx-auto">
            <h1 class="text-6xl md:text-7xl font-bold text-yellow-400 drop-shadow-lg" style="font-family: 'Exo 2', sans-serif;">LoLLMs</h1>
            <p class="mt-2 text-xl md:text-2xl text-gray-300">One tool to rule them all</p>
            <p class="mt-4 text-sm text-gray-400">by ParisNeo</p>
            
            <div v-if="authStore.funFact" class="mt-8 mx-auto max-w-md p-3 bg-white/10 border border-white/20 rounded-lg text-sm text-left">
                <span class="font-bold text-yellow-300">🤓 Fun Fact:</span> {{ authStore.funFact }}
            </div>

            <div class="mt-12 w-full px-4">
                <div class="h-2.5 w-full rounded-full bg-gray-600">
                    <div class="h-2.5 rounded-full bg-gradient-to-r from-cyan-400 to-blue-500 transition-all duration-500" :style="{ width: `${authStore.loadingProgress}%` }"></div>
                </div>
                <p class="mt-3 text-sm text-gray-300">{{ authStore.loadingMessage }}</p>
                <p class="mt-1 text-lg font-semibold">{{ authStore.loadingProgress }}%</p>
            </div>
        </div>
    </div>

    <router-view v-else />

    <LoginModal v-if="activeModal === 'login'" />
    <RegisterModal v-if="activeModal === 'register'" />
    <ForgotPasswordModal v-if="activeModal === 'forgotPassword'" />
    <PasswordResetLinkModal v-if="activeModal === 'passwordResetLink'" />
    <RenameDiscussionModal v-if="activeModal === 'renameDiscussion'" />
    <PersonalityEditorModal v-if="activeModal === 'personalityEditor'" />
    <AdminUserEditModal v-if="activeModal === 'adminUserEdit'" />
    <ForceSettingsModal v-if="activeModal === 'forceSettings'" />
    <SourceModal v-if="activeModal === 'sourceViewer'" />
    <ShareDataStoreModal v-if="activeModal === 'shareDataStore'" />
    <ShareDiscussionModal v-if="activeModal === 'shareDiscussion'" />
    <ExportModal v-if="activeModal === 'export'" />
    <ImportModal v-if="activeModal === 'import'" />
    <InteractiveOutputModal v-if="activeModal === 'interactiveOutput'" />
    <ResetPasswordModal v-if="activeModal === 'resetPassword'" />
    <EmailAllUsersModal v-if="activeModal === 'emailAllUsers'" />
    <EmailUserModal v-if="activeModal === 'adminUserEmail'" />
    <InsertImageModal v-if="activeModal === 'insertImage'" />
    <NewApiKeyModal v-if="activeModal === 'newApiKey'" />
    
    <ImageViewerModal v-if="uiStore.isImageViewerOpen" />
    <NotificationPanel />
    <ConfirmationModal v-if="activeModal === 'confirmation'" />
  </div>
</template>