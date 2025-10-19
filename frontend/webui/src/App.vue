<!-- frontend/webui/src/App.vue -->
<script setup>
import { computed, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useAuthStore } from './stores/auth';
import { useUiStore } from './stores/ui';
import { usePyodideStore } from './stores/pyodide';
import { useTasksStore } from './stores/tasks';
import { useDiscussionsStore } from './stores/discussions';
import { useImageStore } from './stores/images'; 
import logoDefault from './assets/logo.png';

// Import Layouts
import Sidebar from './components/layout/Sidebar.vue';
import GlobalHeader from './components/layout/GlobalHeader.vue';
import AudioPlayer from './components/chat/AudioPlayer.vue';

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
import ImageViewerModal from './components/modals/ImageViewerModal.vue';
import ArtefactEditorModal from './components/modals/ArtefactEditorModal.vue';
import ArtefactViewerModal from './components/modals/ArtefactViewerModal.vue';
import MemoryEditorModal from './components/modals/MemoryEditorModal.vue';
import NotificationPanel from './components/ui/NotificationPanel.vue';
import ShareDataStoreModal from './components/modals/ShareDataStoreModal.vue';
import EditDataStoreModal from './components/modals/EditDataStoreModal.vue';
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
import AppLogModal from './components/modals/AppLogModal.vue';
import CreateFirstAdminModal from './components/modals/CreateFirstAdminModal.vue';
import GeneratePersonalityModal from './components/modals/GeneratePersonalityModal.vue';
import TasksManagerModal from './components/modals/TasksManagerModal.vue';
import EnhancePersonalityPromptModal from './components/modals/EnhancePersonalityPromptModal.vue';
import ContextToArtefactModal from './components/modals/ContextToArtefactModal.vue';
import ContextViewModal from './components/modals/ContextViewModal.vue';
import DataZonePromptManagementModal from './components/modals/DataZonePromptManagementModal.vue';
import FillPlaceholdersModal from './components/modals/FillPlaceholdersModal.vue';
import ServiceRegistrationModal from './components/modals/ServiceRegistrationModal.vue';
import GeneratePromptModal from './components/modals/GeneratePromptModal.vue';
import ManageModelsModal from './components/modals/ManageModelsModal.vue';
import ModelCardModal from './components/modals/ModelCardModal.vue';
import DiscussionTreeModal from './components/modals/DiscussionTreeModal.vue';
import EditPromptModal from './components/modals/EditPromptModal.vue';
import FunFactCategoryModal from './components/modals/FunFactCategoryModal.vue';
import FunFactModal from './components/modals/FunFactModal.vue';
import SharePersonalityModal from './components/modals/SharePersonalityModal.vue';
import DiscussionGroupModal from './components/modals/DiscussionGroupModal.vue';
import MoveDiscussionModal from './components/modals/MoveDiscussionModal.vue';

const authStore = useAuthStore();
const uiStore = useUiStore();
const pyodideStore = usePyodideStore();
const tasksStore = useTasksStore();
const discussionsStore = useDiscussionsStore();
const imageStore = useImageStore();
const route = useRoute();
const { message_font_size } = storeToRefs(uiStore);

const activeModal = computed(() => uiStore.activeModal);
const isAuthenticating = computed(() => authStore.isAuthenticating);
const isAuthenticated = computed(() => authStore.isAuthenticated);
const isSidebarOpen = computed(() => uiStore.isSidebarOpen);

const logoSrc = computed(() => authStore.welcome_logo_url || logoDefault);
const funFactColor = computed(() => authStore.welcome_fun_fact_color || '#3B82F6');
const funFactCategory = computed(() => authStore.welcome_fun_fact_category);

const funFactStyle = computed(() => ({
    '--fun-fact-color': funFactColor.value,
    'backgroundColor': `${funFactColor.value}15`,
    'borderColor': funFactColor.value,
}));

const funFactTextStyle = computed(() => ({
    color: funFactColor.value
}));

const layoutState = computed(() => {
    if (isAuthenticating.value) {
        return 'loading';
    }
    if (isAuthenticated.value) {
        return 'authenticated';
    }
    return 'guest';
});

const showMainSidebar = computed(() => {
    if (!isAuthenticated.value) return false;
    // Views that have their own full-screen layouts and do not need the main sidebar
    const noMainSidebarPaths = [
        '/settings',
        '/admin',
        '/datastores',
        '/friends',
        '/help',
        '/profile',
        '/messages',
        '/voices-studio',
        '/image-studio' // This covers both /image-studio and /image-studio/edit/...
    ];
    return !noMainSidebarPaths.some(path => route.path.startsWith(path));
});


onMounted(async () => {
    uiStore.initializeTheme();
    await authStore.attemptInitialAuth();
    
    const isFirstVisit = !localStorage.getItem('sidebarOpen');
    uiStore.initializeSidebarState();
    if (isFirstVisit && window.innerWidth > 768) {
        uiStore.closeSidebar();
    }

    if (isAuthenticated.value) {
        pyodideStore.initialize();
        tasksStore.fetchTasks();
    }
});

watch(message_font_size, (newSize) => {
  if (newSize && newSize > 0) {
    document.documentElement.style.setProperty('--message-font-size', `${newSize}px`);
  }
}, { immediate: true });
</script>

<template>
  <div class="h-screen w-screen overflow-hidden font-sans antialiased text-gray-800 dark:text-gray-100 bg-gray-100 dark:bg-gray-900 flex flex-col">
    
    <div v-if="layoutState === 'loading'" class="fixed inset-0 z- flex flex-col items-center justify-center text-center p-4 bg-gray-100 dark:bg-gray-900">
        <div class="w-full max-w-lg mx-auto">
            <div class="flex justify-center mb-6">
                <img :src="logoSrc" alt="Logo" class="h-24 sm:h-28 w-auto object-contain" />
            </div>
            <h1 class="text-5xl sm:text-6xl md:text-7xl font-bold text-yellow-600 dark:text-yellow-400 drop-shadow-lg" style="font-family: 'Exo 2', sans-serif;">
                {{ authStore.welcomeText || 'LoLLMs' }}
            </h1>
            <p class="mt-2 text-lg sm:text-xl md:text-2xl text-gray-600 dark:text-gray-300">
                {{ authStore.welcomeSlogan || 'One tool to rule them all' }}
            </p>
            
            <div v-if="authStore.funFact" 
                 :title="funFactCategory ? `Category: ${funFactCategory}` : 'Fun Fact'" 
                 class="mt-8 mx-auto max-w-md p-4 border-l-4 rounded-lg text-sm text-left text-gray-900 dark:text-gray-100" 
                 :style="funFactStyle">
                <span class="font-bold" :style="funFactTextStyle">🤓 Fun Fact:</span> {{ authStore.funFact }}
            </div>
            <div class="mt-12 w-full px-4">
                <div class="h-2.5 w-full rounded-full bg-gray-200 dark:bg-gray-600">
                    <div class="h-2.5 rounded-full bg-gradient-to-r from-cyan-400 to-blue-500 transition-all duration-500" :style="{ width: `${authStore.loadingProgress}%` }"></div>
                </div>
                <p class="mt-3 text-sm text-gray-600 dark:text-gray-300">{{ authStore.loadingMessage }}</p>
                <p class="mt-1 text-lg font-semibold text-gray-700 dark:text-gray-200">{{ authStore.loadingProgress }}%</p>
            </div>
        </div>
        <footer class="absolute bottom-4 w-full text-center text-xs text-gray-500 dark:text-gray-400">
            Powered by <a href="https://github.com/ParisNeo/lollms-webui" target="_blank" class="font-semibold hover:underline">LoLLMs</a> by <a href="https://github.com/ParisNeo" target="_blank" class="font-semibold hover:underline">ParisNeo</a>
        </footer>    
    </div>

    <!-- Authenticated App Layout -->
    <div v-else-if="layoutState === 'authenticated'" class="flex flex-col flex-grow min-h-0">
      <div class="flex flex-grow min-h-0 relative">
        <div v-if="showMainSidebar" class="absolute md:relative inset-y-0 left-0 z-40 md:z-auto transition-transform duration-300 ease-in-out" :class="isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'">
            <Sidebar/>
        </div>
        <div v-if="showMainSidebar && isSidebarOpen" @click="uiStore.toggleSidebar" class="absolute inset-0 bg-black/30 z-30 md:hidden"></div>

        <div class="flex-1 flex flex-col overflow-hidden">
          <GlobalHeader />
          <main class="flex-1 overflow-hidden">
              <router-view />
          </main>
        </div>
      </div>
    </div>

    <!-- Guest/Unauthenticated View -->
    <div v-else-if="layoutState === 'guest'" class="flex flex-col flex-grow min-h-0">
        <router-view />
    </div>

    <!-- Modals -->
    <CreateFirstAdminModal v-if="activeModal === 'firstAdminSetup'" />
    <LoginModal v-if="activeModal === 'login'" />
    <RegisterModal v-if="activeModal === 'register'" />
    <ForgotPasswordModal v-if="activeModal === 'forgotPassword'" />
    <PasswordResetLinkModal v-if="activeModal === 'passwordResetLink'" />
    <RenameDiscussionModal v-if="activeModal === 'renameDiscussion'" />
    <PersonalityEditorModal v-if="activeModal === 'personalityEditor'" />
    <AdminUserEditModal v-if="activeModal === 'adminUserEdit'" />
    <ForceSettingsModal v-if="activeModal === 'forceSettings'" />
    <ConfirmationModal v-if="activeModal === 'confirmation'" />
    <ImageViewerModal />
    <ArtefactEditorModal v-if="activeModal === 'artefactEditor'" />
    <ArtefactViewerModal v-if="activeModal === 'artefactViewer'" />
    <MemoryEditorModal v-if="activeModal === 'memoryEditor'" />
    <NotificationPanel />
    <ShareDataStoreModal v-if="activeModal === 'shareDataStore'" />
    <EditDataStoreModal v-if="activeModal === 'editDataStore'" />
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
    <AppLogModal v-if="activeModal === 'appLog'" />
    <GeneratePersonalityModal v-if="activeModal === 'generatePersonality'" />
    <TasksManagerModal v-if="activeModal === 'tasksManager'" />
    <EnhancePersonalityPromptModal v-if="activeModal === 'enhancePersonalityPrompt'" />
    <ContextToArtefactModal v-if="activeModal === 'contextToArtefact'" />
    <ContextViewModal v-if="activeModal === 'contextViewer'" />
    <DataZonePromptManagementModal v-if="activeModal === 'dataZonePromptManagement'" />
    <FillPlaceholdersModal v-if="activeModal === 'fillPlaceholders'" />
    <ServiceRegistrationModal v-if="activeModal === 'serviceRegistration'" />
    <GeneratePromptModal v-if="activeModal === 'generatePrompt'" />
    <ManageModelsModal v-if="activeModal === 'manageModels'" />
    <ModelCardModal v-if="activeModal === 'modelCard'" />
    <DiscussionTreeModal v-if="activeModal === 'discussionTree'" />
    <EditPromptModal v-if="activeModal === 'editPrompt'" />
    <FunFactCategoryModal v-if="activeModal === 'funFactCategory'" />
    <FunFactModal v-if="activeModal === 'funFact'" />
    <SharePersonalityModal v-if="activeModal === 'sharePersonality'" />
    <DiscussionGroupModal v-if="activeModal === 'discussionGroup'" />
    <MoveDiscussionModal v-if="activeModal === 'moveDiscussion'" />
    
    <!-- Always rendered panels -->
    <NotificationPanel />
    <AudioPlayer />
  </div>
</template>