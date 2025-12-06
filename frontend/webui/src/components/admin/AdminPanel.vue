<!-- [UPDATE] frontend/webui/src/components/admin/AdminPanel.vue -->
<script setup>
import { computed, defineAsyncComponent } from 'vue';

const props = defineProps({
    activeTab: {
        type: String,
        required: true,
        default: 'dashboard'
    }
});

const Dashboard = defineAsyncComponent(() => import('./Dashboard.vue'));
const UserTable = defineAsyncComponent(() => import('./UserTable.vue'));
const ServerSettings = defineAsyncComponent(() => import('./ServerSettings.vue'));
const GlobalSettings = defineAsyncComponent(() => import('./GlobalSettings.vue'));
const LLMBindingsSettings = defineAsyncComponent(() => import('./bindings/LLMBindingsSettings.vue'));
const TTIBindingsSettings = defineAsyncComponent(() => import('./bindings/TTIBindingsSettings.vue'));
const TTSBindingsSettings = defineAsyncComponent(() => import('./bindings/TTSBindingsSettings.vue'));
const STTBindingsSettings = defineAsyncComponent(() => import('./bindings/STTBindingsSettings.vue'));
const RAGBindingsSettings = defineAsyncComponent(() => import('./bindings/RAGBindingsSettings.vue'));
const AiBotSettings = defineAsyncComponent(() => import('./AiBotSettings.vue'));
const EmailSettings = defineAsyncComponent(() => import('./EmailSettings.vue'));
const SSOClientSettings = defineAsyncComponent(() => import('./SSOClientSettings.vue'));
const SCIMSettings = defineAsyncComponent(() => import('./SCIMSettings.vue'));
const ImportTools = defineAsyncComponent(() => import('./ImportTools.vue'));
const AppsManagement = defineAsyncComponent(() => import('./zoos/AppsManagement.vue'));
const McpsManagement = defineAsyncComponent(() => import('./zoos/McpsManagement.vue'));
const PromptsManagement = defineAsyncComponent(() => import('./zoos/PromptsManagement.vue'));
const PersonalitiesManagement = defineAsyncComponent(() => import('./zoos/PersonalitiesManagement.vue'));
const TaskManager = defineAsyncComponent(() => import('./TaskManager.vue'));
const BroadcastMessage = defineAsyncComponent(() => import('./BroadcastMessage.vue'));
const BuildersSettings = defineAsyncComponent(() => import('./BuildersSettings.vue'));
const WelcomeSettings = defineAsyncComponent(() => import('./WelcomeSettings.vue'));
const RssManagement = defineAsyncComponent(() => import('./RssManagement.vue'));
const NewsFeedSettings = defineAsyncComponent(() => import('./NewsFeedSettings.vue'));
const NewsManagement = defineAsyncComponent(() => import('./NewsManagement.vue'));
const ModerationQueue = defineAsyncComponent(() => import('./ModerationQueue.vue')); // New Import

const tabs = [
    { id: 'dashboard', component: Dashboard },
    { id: 'server_settings', component: ServerSettings },
    { id: 'users', component: UserTable },
    { id: 'tasks', component: TaskManager },
    { id: 'broadcast', component: BroadcastMessage },
    { id: 'llm_bindings', component: LLMBindingsSettings },
    { id: 'tti_bindings', component: TTIBindingsSettings },
    { id: 'tts_bindings', component: TTSBindingsSettings },
    { id: 'stt_bindings', component: STTBindingsSettings },
    { id: 'rag_bindings', component: RAGBindingsSettings },
    { id: 'builders', component: BuildersSettings },
    { id: 'ai_bot', component: AiBotSettings },
    { id: 'apps', component: AppsManagement },
    { id: 'mcps', component: McpsManagement },
    { id: 'personalities', component: PersonalitiesManagement },
    { id: 'prompts', component: PromptsManagement },
    { id: 'global_settings', component: GlobalSettings },
    { id: 'email', component: EmailSettings },
    { id: 'sso_client_settings', component: SSOClientSettings },
    { id: 'scim_settings', component: SCIMSettings },
    { id: 'import', component: ImportTools },
    { id: 'welcome_settings', component: WelcomeSettings },
    { id: 'rss_feeds', component: RssManagement },
    { id: 'news_feed_settings', component: NewsFeedSettings },
    { id: 'news_management', component: NewsManagement },
    { id: 'moderation', component: ModerationQueue }, // New Tab
];

const activeComponent = computed(() => {
    return tabs.find(tab => tab.id === props.activeTab)?.component || null;
});
</script>

<template>
    <div>
        <Suspense>
            <template #default>
                <component :is="activeComponent" />
            </template>
            <template #fallback>
                <div class="text-center py-10">
                    <p class="text-gray-500 dark:text-gray-400">Loading component...</p>
                </div>
            </template>
        </Suspense>
    </div>
</template>
