<!-- [UPDATE] frontend/webui/src/App.vue -->
<script setup>
import { computed, onMounted, watch, defineAsyncComponent } from 'vue';
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
import NotificationPanel from './components/ui/NotificationPanel.vue';

// Define Async Components for Modals
const LoginModal = defineAsyncComponent(() => import('./components/modals/LoginModal.vue'));
const RegisterModal = defineAsyncComponent(() => import('./components/modals/RegisterModal.vue'));
const ForgotPasswordModal = defineAsyncComponent(() => import('./components/modals/ForgotPasswordModal.vue'));
const PasswordResetLinkModal = defineAsyncComponent(() => import('./components/modals/PasswordResetLinkModal.vue'));
const RenameDiscussionModal = defineAsyncComponent(() => import('./components/modals/RenameDiscussionModal.vue'));
const PersonalityEditorModal = defineAsyncComponent(() => import('./components/modals/PersonalityEditorModal.vue'));
const AdminUserEditModal = defineAsyncComponent(() => import('./components/modals/AdminUserEditModal.vue'));
const ForceSettingsModal = defineAsyncComponent(() => import('./components/modals/ForceSettingsModal.vue'));
const ConfirmationModal = defineAsyncComponent(() => import('./components/ui/ConfirmationModal.vue'));
const ImageViewerModal = defineAsyncComponent(() => import('./components/modals/ImageViewerModal.vue'));
const ArtefactEditorModal = defineAsyncComponent(() => import('./components/modals/ArtefactEditorModal.vue'));
const ArtefactViewerModal = defineAsyncComponent(() => import('./components/modals/ArtefactViewerModal.vue'));
const SourceViewerModal = defineAsyncComponent(() => import('./components/modals/SourceViewerModal.vue'));
const AllSourcesSearchModal = defineAsyncComponent(() => import('./components/modals/AllSourcesSearchModal.vue'));
const MemoryEditorModal = defineAsyncComponent(() => import('./components/modals/MemoryEditorModal.vue'));
const ShareDataStoreModal = defineAsyncComponent(() => import('./components/modals/ShareDataStoreModal.vue'));
const EditDataStoreModal = defineAsyncComponent(() => import('./components/modals/EditDataStoreModal.vue'));
const ExportModal = defineAsyncComponent(() => import('./components/modals/ExportModal.vue'));
const ImportModal = defineAsyncComponent(() => import('./components/modals/ImportModal.vue'));
const InteractiveOutputModal = defineAsyncComponent(() => import('./components/modals/InteractiveOutputModal.vue'));
const ShareDiscussionModal = defineAsyncComponent(() => import('./components/modals/ShareDiscussionModal.vue'));
const ResetPasswordModal = defineAsyncComponent(() => import('./components/modals/ResetPasswordModal.vue'));
const EmailAllUsersModal = defineAsyncComponent(() => import('./components/modals/EmailAllUsersModal.vue'));
const EmailListModal = defineAsyncComponent(() => import('./components/modals/EmailListModal.vue'));
const EmailUserModal = defineAsyncComponent(() => import('./components/modals/EmailUserModal.vue'));
const InsertImageModal = defineAsyncComponent(() => import('./components/modals/InsertImageModal.vue'));
const NewApiKeyModal = defineAsyncComponent(() => import('./components/modals/NewApiKeyModal.vue')); 
const WhatsNextModal = defineAsyncComponent(() => import('./components/modals/WhatsNextModal.vue'));
const AppInstallModal = defineAsyncComponent(() => import('./components/modals/AppInstallModal.vue'));
const AppDetailsModal = defineAsyncComponent(() => import('./components/modals/AppDetailsModal.vue'));
const AppConfigModal = defineAsyncComponent(() => import('./components/modals/AppConfigModal.vue'));
const AppEnvConfigModal = defineAsyncComponent(() => import('./components/modals/AppEnvConfigModal.vue'));
const AppLogModal = defineAsyncComponent(() => import('./components/modals/AppLogModal.vue'));
const CreateFirstAdminModal = defineAsyncComponent(() => import('./components/modals/CreateFirstAdminModal.vue'));
const GeneratePersonalityModal = defineAsyncComponent(() => import('./components/modals/GeneratePersonalityModal.vue'));
const TasksManagerModal = defineAsyncComponent(() => import('./components/modals/TasksManagerModal.vue'));
const EnhancePersonalityPromptModal = defineAsyncComponent(() => import('./components/modals/EnhancePersonalityPromptModal.vue'));
const ContextToArtefactModal = defineAsyncComponent(() => import('./components/modals/ContextToArtefactModal.vue'));
const ContextViewModal = defineAsyncComponent(() => import('./components/modals/ContextViewModal.vue'));
const DataZonePromptManagementModal = defineAsyncComponent(() => import('./components/modals/DataZonePromptManagementModal.vue'));
const FillPlaceholdersModal = defineAsyncComponent(() => import('./components/modals/FillPlaceholdersModal.vue'));
const ServiceRegistrationModal = defineAsyncComponent(() => import('./components/modals/ServiceRegistrationModal.vue'));
const GeneratePromptModal = defineAsyncComponent(() => import('./components/modals/GeneratePromptModal.vue'));
const ManageModelsModal = defineAsyncComponent(() => import('./components/modals/ManageModelsModal.vue'));
const ModelCardModal = defineAsyncComponent(() => import('./components/modals/ModelCardModal.vue'));
const DiscussionTreeModal = defineAsyncComponent(() => import('./components/modals/DiscussionTreeModal.vue'));
const EditPromptModal = defineAsyncComponent(() => import('./components/modals/EditPromptModal.vue'));
const FunFactCategoryModal = defineAsyncComponent(() => import('./components/modals/FunFactCategoryModal.vue'));
const FunFactModal = defineAsyncComponent(() => import('./components/modals/FunFactModal.vue'));
const GenerateFunFactsModal = defineAsyncComponent(() => import('./components/modals/GenerateFunFactsModal.vue'));
const SharePersonalityModal = defineAsyncComponent(() => import('./components/modals/SharePersonalityModal.vue'));
const DiscussionGroupModal = defineAsyncComponent(() => import('./components/modals/DiscussionGroupModal.vue'));
const MoveDiscussionModal = defineAsyncComponent(() => import('./components/modals/MoveDiscussionModal.vue'));
const EnhancePromptModal = defineAsyncComponent(() => import('./components/modals/EnhancePromptModal.vue'));
const CameraCaptureModal = defineAsyncComponent(() => import('./components/modals/CameraCaptureModal.vue'));
const ImageEditorSettingsModal = defineAsyncComponent(() => import('./components/modals/ImageEditorSettingsModal.vue'));
const NoteEditorModal = defineAsyncComponent(() => import('./components/modals/NoteEditorModal.vue'));
const NoteGroupModal = defineAsyncComponent(() => import('./components/modals/NoteGroupModal.vue'));
const SystemLogModal = defineAsyncComponent(() => import('./components/modals/SystemLogModal.vue'));

const ChatSidebar = defineAsyncComponent(() => import('./components/chat/ChatSidebar.vue'));

const authStore = useAuthStore();
const uiStore = useUiStore();
const pyodideStore = usePyodideStore();
const tasksStore = useTasksStore();
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
    const noMainSidebarPaths = [
        '/settings',
        '/admin',
        '/datastores',
        '/friends',
        '/help',
        '/profile',
        '/messages',
        '/voices-studio',
        '/image-studio'
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
        tasksStore.startPolling();
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
    
    <div v-if="layoutState === 'loading'" class="fixed inset-0 z-50 flex flex-col items-center justify-center text-center p-4 bg-gray-100 dark:bg-gray-900">
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
            
            <div v-if="authStore.funFact" class="mt-8 mx-auto max-w-md">
                <div 
                     :title="funFactCategory ? `Category: ${funFactCategory}` : 'Fun Fact'" 
                     class="p-4 border-l-4 rounded-lg text-sm text-left text-gray-900 dark:text-gray-100" 
                     :style="funFactStyle">
                    <span class="font-bold" :style="funFactTextStyle">🤓 {{ funFactCategory || 'Fun Fact' }}:</span> {{ authStore.funFact }}
                </div>
                <div class="mt-4">
                    <button @click="authStore.fetchNewFunFact()" class="btn btn-secondary btn-sm">Next Fun Fact</button>
                </div>
            </div>
            
            <!-- Glassmorphism Progress Bar -->
            <div class="mt-12 w-full px-4">
                <div class="h-4 w-full rounded-full bg-gray-200/20 backdrop-blur-md border border-white/20 dark:border-gray-600/30 overflow-hidden shadow-inner relative">
                    <div class="h-full rounded-full bg-gradient-to-r from-cyan-400/90 to-blue-500/90 backdrop-blur-sm transition-all duration-500 relative" 
                         :style="{ width: `${authStore.loadingProgress}%` }">
                         <!-- Shine effect -->
                         <div class="absolute top-0 left-0 bottom-0 right-0 bg-gradient-to-b from-white/30 to-transparent"></div>
                         <!-- Striped animation (optional css class or inline) -->
                         <div class="absolute inset-0 w-full h-full progress-bar-animated opacity-30"></div>
                    </div>
                </div>
                <p class="mt-3 text-sm text-gray-600 dark:text-gray-300 font-medium tracking-wide">{{ authStore.loadingMessage }}</p>
                <p class="mt-1 text-lg font-bold text-gray-700 dark:text-gray-200">{{ authStore.loadingProgress }}%</p>
            </div>

        </div>
        <footer class="absolute bottom-4 w-full text-center text-xs text-gray-500 dark:text-gray-400">
            Powered by <a href="https://github.com/ParisNeo/lollms-webui" target="_blank" class="font-semibold hover:underline">LoLLMs</a> by <a href="https://github.com/ParisNeo" target="_blank" class="font-semibold hover:underline">ParisNeo</a>
        </footer>    
    </div>

    <!-- Authenticated App Layout -->
    <div v-else-if="layoutState === 'authenticated'" class="flex flex-col flex-grow min-h-0 relative overflow-hidden">
      <div class="flex flex-grow min-h-0 relative w-full h-full">
        <div v-if="showMainSidebar" class="absolute md:relative inset-y-0 left-0 z-40 md:z-auto transition-transform duration-300 ease-in-out h-full" :class="isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'">
            <Sidebar/>
        </div>
        <div v-if="showMainSidebar && isSidebarOpen" @click="uiStore.toggleSidebar" class="absolute inset-0 bg-black/30 z-30 md:hidden"></div>

        <div class="flex-1 flex flex-col overflow-hidden h-full relative">
          <GlobalHeader />
          <main class="flex-1 overflow-hidden relative">
              <router-view />
          </main>
        </div>
        
        <!-- Global Chat Sidebar -->
        <ChatSidebar />
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
    <SourceViewerModal v-if="activeModal === 'sourceViewer'" />
    <AllSourcesSearchModal v-if="activeModal === 'allSourcesSearch'" />
    <MemoryEditorModal v-if="activeModal === 'memoryEditor'" />
    
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
    <AppEnvConfigModal v-if="activeModal === 'appEnvConfig'" />
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
    <GenerateFunFactsModal v-if="activeModal === 'generateFunFacts'" />
    <SharePersonalityModal v-if="activeModal === 'sharePersonality'" />
    <DiscussionGroupModal v-if="activeModal === 'discussionGroup'" />
    <MoveDiscussionModal v-if="activeModal === 'moveDiscussion'" />
    <EnhancePromptModal v-if="activeModal === 'enhancePrompt'" />
    <CameraCaptureModal v-if="activeModal === 'cameraCapture'" />
    <ImageEditorSettingsModal v-if="activeModal === 'imageEditorSettings'" />
    <NoteEditorModal v-if="activeModal === 'noteEditor'" />
    <NoteGroupModal v-if="activeModal === 'noteGroup'" />
    <SystemLogModal v-if="activeModal === 'systemLog'" />
    
    <!-- Always rendered panels -->
    <NotificationPanel />
    <AudioPlayer />
  </div>
</template>

<style>
@keyframes progress-animation {
  0% { background-position: 1rem 0; }
  100% { background-position: 0 0; }
}
.progress-bar-animated {
  background-image: linear-gradient(45deg, rgba(255, 255, 255, .15) 25%, transparent 25%, transparent 50%, rgba(255, 255, 255, .15) 50%, rgba(255, 255, 255, .15) 75%, transparent 75%, transparent);
  background-size: 1rem 1rem;
  animation: progress-animation 1s linear infinite;
}
</style>
