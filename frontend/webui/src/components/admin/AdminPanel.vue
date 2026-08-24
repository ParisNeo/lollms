<script setup>
import { computed, defineAsyncComponent, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';

const props = defineProps({
    activeTab: {
        type: String,
        default: 'dashboard'
    }
});

const emit = defineEmits(['navigate']);

const adminStore = useAdminStore();
const uiStore = useUiStore();
const { allUsers, isLoadingUsers } = storeToRefs(adminStore);

// Lazy Loaded Administration Components
const Dashboard = defineAsyncComponent(() => import('./Dashboard.vue'));
const UserTable = defineAsyncComponent(() => import('./UserTable.vue'));
const EmailSettings = defineAsyncComponent(() => import('./EmailSettings.vue'));
const Operations = defineAsyncComponent(() => import('./Operations.vue'));
const SystemStatus = defineAsyncComponent(() => import('./SystemStatus.vue'));
const SystemLoad = defineAsyncComponent(() => import('./SystemLoad.vue'));
const GPULoad = defineAsyncComponent(() => import('./GPULoad.vue'));
const SecurityTools = defineAsyncComponent(() => import('./SecurityTools.vue'));
const ModelUsageChart = defineAsyncComponent(() => import('./ModelUsageChart.vue'));
const GlobalStatsChart = defineAsyncComponent(() => import('./GlobalStatsChart.vue'));
const ModerationQueue = defineAsyncComponent(() => import('./ModerationQueue.vue'));
const WelcomeSettings = defineAsyncComponent(() => import('./WelcomeSettings.vue'));
const BuildersSettings = defineAsyncComponent(() => import('./BuildersSettings.vue'));
const NewsFeedSettings = defineAsyncComponent(() => import('./NewsFeedSettings.vue'));
const NewsManagement = defineAsyncComponent(() => import('./NewsManagement.vue'));
const RequirementsManagement = defineAsyncComponent(() => import('./RequirementsManagement.vue'));
const RssManagement = defineAsyncComponent(() => import('./RssManagement.vue'));
const SCIMSettings = defineAsyncComponent(() => import('./SCIMSettings.vue'));
const SSOClientSettings = defineAsyncComponent(() => import('./SSOClientSettings.vue'));
const HttpsSettings = defineAsyncComponent(() => import('./HttpsSettings.vue'));
const AiBotSettings = defineAsyncComponent(() => import('./AiBotSettings.vue'));
const ServicesManagement = defineAsyncComponent(() => import('./ServicesManagement.vue'));
const ImportTools = defineAsyncComponent(() => import('./ImportTools.vue'));
const TaskManager = defineAsyncComponent(() => import('./TaskManager.vue'));
const EmailMarketing = defineAsyncComponent(() => import('./EmailMarketing.vue'));
const LogsAndAnalysis = defineAsyncComponent(() => import('./LogsAndAnalysis.vue'));

// Zoos
const PersonalityZoo = defineAsyncComponent(() => import('./zoos/PersonalitiesManagement.vue'));
const PromptZoo = defineAsyncComponent(() => import('./zoos/PromptsManagement.vue'));
const McpZoo = defineAsyncComponent(() => import('./zoos/McpsManagement.vue'));
const AppZoo = defineAsyncComponent(() => import('./zoos/AppsManagement.vue'));

// Engine Bindings
const LLMBindingsSettings = defineAsyncComponent(() => import('./bindings/LLMBindingsSettings.vue'));
const TTIBindingsSettings = defineAsyncComponent(() => import('./bindings/TTIBindingsSettings.vue'));
const TTSBindingsSettings = defineAsyncComponent(() => import('./bindings/TTSBindingsSettings.vue'));
const STTBindingsSettings = defineAsyncComponent(() => import('./bindings/STTBindingsSettings.vue'));
const TTVBindingsSettings = defineAsyncComponent(() => import('./bindings/TTVBindingsSettings.vue'));
const TTMBindingsSettings = defineAsyncComponent(() => import('./bindings/TTMBindingsSettings.vue'));
const RAGBindingsSettings = defineAsyncComponent(() => import('./bindings/RAGBindingsSettings.vue'));

onMounted(() => {
    adminStore.fetchAllUsers();
});

function handleDashboardNavigation(payload) {
    emit('navigate', payload);
}
</script>

<template>
    <div class="h-full flex flex-col overflow-y-auto custom-scrollbar">
        <!-- 1. DASHBOARD -->
        <Dashboard 
            v-if="activeTab === 'dashboard'" 
            @navigate="handleDashboardNavigation" 
        />

        <!-- 2. SYSTEM MONITORING -->
        <SystemLoad v-else-if="activeTab === 'system_load'" />
        <GPULoad v-else-if="activeTab === 'gpu_load'" />
        <LogsAndAnalysis v-else-if="activeTab === 'logs_analysis' || activeTab === 'logs'" />
        <RequirementsManagement v-else-if="activeTab === 'requirements'" />

        <!-- 3. MAINTENANCE -->
        <Operations v-else-if="activeTab === 'operations'" />
        <SecurityTools v-else-if="activeTab === 'security'" />

        <!-- 4. USER MANAGEMENT -->
        <UserTable 
            v-else-if="activeTab === 'users' || activeTab === 'user-table'" 
            :users="allUsers" 
            :is-loading="isLoadingUsers" 
        />
        <ModerationQueue v-else-if="activeTab === 'moderation'" />
        <ServicesManagement v-else-if="activeTab === 'services_mgmt' || activeTab === 'services'" />
        <EmailMarketing v-else-if="activeTab === 'email_marketing'" />
        <TaskManager v-else-if="activeTab === 'tasks'" />

        <!-- 5. ZOOS -->
        <PersonalityZoo v-else-if="activeTab === 'personalities' || activeTab === 'personalities_zoo'" />
        <PromptZoo v-else-if="activeTab === 'prompts' || activeTab === 'prompts_zoo'" />
        <McpZoo v-else-if="activeTab === 'mcps' || activeTab === 'mcps_zoo'" />
        <AppZoo v-else-if="activeTab === 'apps' || activeTab === 'apps_zoo'" />

        <!-- 6. BINDINGS & ENGINES -->
        <LLMBindingsSettings v-else-if="activeTab === 'llm_bindings' || activeTab === 'llm'" />
        <TTIBindingsSettings v-else-if="activeTab === 'tti_bindings' || activeTab === 'tti'" />
        <TTVBindingsSettings v-else-if="activeTab === 'ttv_bindings' || activeTab === 'ttv'" />
        <TTMBindingsSettings v-else-if="activeTab === 'ttm_bindings' || activeTab === 'ttm'" />
        <TTSBindingsSettings v-else-if="activeTab === 'tts_bindings' || activeTab === 'tts'" />
        <STTBindingsSettings v-else-if="activeTab === 'stt_bindings' || activeTab === 'stt'" />
        <RAGBindingsSettings v-else-if="activeTab === 'rag_bindings' || activeTab === 'rag'" />
        <BuildersSettings v-else-if="activeTab === 'builders'" />
        <AiBotSettings v-else-if="activeTab === 'ai_bot'" />

        <!-- 7. GLOBAL SETTINGS -->
        <HttpsSettings v-else-if="activeTab === 'https_settings' || activeTab === 'https'" />
        <WelcomeSettings v-else-if="activeTab === 'welcome_settings' || activeTab === 'welcome'" />
        <EmailSettings v-else-if="activeTab === 'email' || activeTab === 'email_settings'" />
        <SSOClientSettings v-else-if="activeTab === 'sso_client_settings' || activeTab === 'sso_client'" />
        <SCIMSettings v-else-if="activeTab === 'scim_settings' || activeTab === 'scim'" />
        <ImportTools v-else-if="activeTab === 'import'" />
        <NewsFeedSettings v-else-if="activeTab === 'news_feed'" />
        <NewsManagement v-else-if="activeTab === 'news'" />
        <RssManagement v-else-if="activeTab === 'rss'" />

        <!-- FALLBACK -->
        <Dashboard 
            v-else 
            @navigate="handleDashboardNavigation" 
        />
    </div>
</template>

<style scoped>
@reference "tailwindcss";
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb { @apply bg-gray-300 dark:bg-gray-700 rounded-full; }
</style>