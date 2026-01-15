<script setup>
import { computed, defineAsyncComponent } from 'vue';
import { useUiStore } from '../../stores/ui';

const uiStore = useUiStore();
const activeModal = computed(() => uiStore.activeModal);

// Lazy-loaded modal definitions
const LoginModal = defineAsyncComponent(() => import('./LoginModal.vue'));
const RegisterModal = defineAsyncComponent(() => import('./RegisterModal.vue'));
const ForgotPasswordModal = defineAsyncComponent(() => import('./ForgotPasswordModal.vue'));
const PasswordResetLinkModal = defineAsyncComponent(() => import('./PasswordResetLinkModal.vue'));
const RenameDiscussionModal = defineAsyncComponent(() => import('./RenameDiscussionModal.vue'));
const PersonalityEditorModal = defineAsyncComponent(() => import('./PersonalityEditorModal.vue'));
const AdminUserEditModal = defineAsyncComponent(() => import('./AdminUserEditModal.vue'));
const ForceSettingsModal = defineAsyncComponent(() => import('./ForceSettingsModal.vue'));
const ConfirmationModal = defineAsyncComponent(() => import('../ui/ConfirmationModal.vue'));
const ImageViewerModal = defineAsyncComponent(() => import('./ImageViewerModal.vue'));
const ArtefactEditorModal = defineAsyncComponent(() => import('./ArtefactEditorModal.vue'));
const ArtefactViewerModal = defineAsyncComponent(() => import('./ArtefactViewerModal.vue'));
const SourceViewerModal = defineAsyncComponent(() => import('./SourceViewerModal.vue'));
const AllSourcesSearchModal = defineAsyncComponent(() => import('./AllSourcesSearchModal.vue'));
const MemoryEditorModal = defineAsyncComponent(() => import('./MemoryEditorModal.vue'));
const ShareDataStoreModal = defineAsyncComponent(() => import('./ShareDataStoreModal.vue'));
const EditDataStoreModal = defineAsyncComponent(() => import('./EditDataStoreModal.vue'));
const ExportModal = defineAsyncComponent(() => import('./ExportModal.vue'));
const ImportModal = defineAsyncComponent(() => import('./ImportModal.vue'));
const InteractiveOutputModal = defineAsyncComponent(() => import('./InteractiveOutputModal.vue'));
const ShareDiscussionModal = defineAsyncComponent(() => import('./ShareDiscussionModal.vue'));
const ResetPasswordModal = defineAsyncComponent(() => import('./ResetPasswordModal.vue'));
const EmailAllUsersModal = defineAsyncComponent(() => import('./EmailAllUsersModal.vue'));
const EmailListModal = defineAsyncComponent(() => import('./EmailListModal.vue'));
const EmailUserModal = defineAsyncComponent(() => import('./EmailUserModal.vue'));
const InsertImageModal = defineAsyncComponent(() => import('./InsertImageModal.vue'));
const NewApiKeyModal = defineAsyncComponent(() => import('./NewApiKeyModal.vue')); 
const WhatsNextModal = defineAsyncComponent(() => import('./WhatsNextModal.vue'));
const AppInstallModal = defineAsyncComponent(() => import('./AppInstallModal.vue'));
const AppDetailsModal = defineAsyncComponent(() => import('./AppDetailsModal.vue'));
const AppConfigModal = defineAsyncComponent(() => import('./AppConfigModal.vue'));
const AppEnvConfigModal = defineAsyncComponent(() => import('./AppEnvConfigModal.vue'));
const AppLogModal = defineAsyncComponent(() => import('./AppLogModal.vue'));
const CreateFirstAdminModal = defineAsyncComponent(() => import('./CreateFirstAdminModal.vue'));
const GeneratePersonalityModal = defineAsyncComponent(() => import('./GeneratePersonalityModal.vue'));
const TasksManagerModal = defineAsyncComponent(() => import('./TasksManagerModal.vue'));
const EnhancePersonalityPromptModal = defineAsyncComponent(() => import('./EnhancePersonalityPromptModal.vue'));
const ContextToArtefactModal = defineAsyncComponent(() => import('./ContextToArtefactModal.vue'));
const ContextViewModal = defineAsyncComponent(() => import('./ContextViewModal.vue'));
const DataZonePromptManagementModal = defineAsyncComponent(() => import('./DataZonePromptManagementModal.vue'));
const FillPlaceholdersModal = defineAsyncComponent(() => import('./FillPlaceholdersModal.vue'));
const ServiceRegistrationModal = defineAsyncComponent(() => import('./ServiceRegistrationModal.vue'));
const GeneratePromptModal = defineAsyncComponent(() => import('./GeneratePromptModal.vue'));
const ManageModelsModal = defineAsyncComponent(() => import('./ManageModelsModal.vue'));
const ModelCardModal = defineAsyncComponent(() => import('./ModelCardModal.vue'));
const DiscussionTreeModal = defineAsyncComponent(() => import('./DiscussionTreeModal.vue'));
const EditPromptModal = defineAsyncComponent(() => import('./EditPromptModal.vue'));
const FunFactCategoryModal = defineAsyncComponent(() => import('./FunFactCategoryModal.vue'));
const FunFactModal = defineAsyncComponent(() => import('./FunFactModal.vue'));
const GenerateFunFactsModal = defineAsyncComponent(() => import('./GenerateFunFactsModal.vue'));
const SharePersonalityModal = defineAsyncComponent(() => import('./SharePersonalityModal.vue'));
const DiscussionGroupModal = defineAsyncComponent(() => import('./DiscussionGroupModal.vue'));
const MoveDiscussionModal = defineAsyncComponent(() => import('./MoveDiscussionModal.vue'));
const EnhancePromptModal = defineAsyncComponent(() => import('./EnhancePromptModal.vue'));
const CameraCaptureModal = defineAsyncComponent(() => import('./CameraCaptureModal.vue'));
const ImageEditorSettingsModal = defineAsyncComponent(() => import('./ImageEditorSettingsModal.vue'));
const NoteEditorModal = defineAsyncComponent(() => import('./NoteEditorModal.vue'));
const NoteGroupModal = defineAsyncComponent(() => import('./NoteGroupModal.vue'));
const SystemLogModal = defineAsyncComponent(() => import('./SystemLogModal.vue'));
const ScrapeUrlModal = defineAsyncComponent(() => import('./ScrapeUrlModal.vue'));
const ArtefactImportWizardModal = defineAsyncComponent(() => import('./ArtefactImportWizardModal.vue'));
// Registered the NotebookWizardModal here
const NotebookWizardModal = defineAsyncComponent(() => import('./NotebookWizardModal.vue'));

</script>

<template>
  <div id="modal-container">
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
    <ImageViewerModal v-if="activeModal === 'imageViewer'" />
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
    <ScrapeUrlModal v-if="activeModal === 'scrapeUrl'" />
    <ArtefactImportWizardModal v-if="activeModal === 'artefactImportWizard'" />
    <!-- Added the modal here -->
    <NotebookWizardModal v-if="activeModal === 'notebookWizard'" />
  </div>
</template>
