<!-- [UPDATE] frontend/webui/src/views/AdminView.vue -->
<script setup>
import { computed, defineAsyncComponent, markRaw } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import PageViewLayout from '../components/layout/PageViewLayout.vue';

// Import Icons
import IconDashboard from '../assets/icons/IconDashboard.vue';
import IconUserGroup from '../assets/icons/IconUserGroup.vue';
import IconCpuChip from '../assets/icons/IconCpuChip.vue';
import IconCog from '../assets/icons/IconCog.vue';
import IconMail from '../assets/icons/IconMail.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconSquares2x2 from '../assets/icons/IconSquares2x2.vue';
import IconMcp from '../assets/icons/IconMcp.vue';
import IconTasks from '../assets/icons/IconTasks.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconUserCircle from '../assets/icons/IconUserCircle.vue';
import IconSend from '../assets/icons/IconSend.vue';
import IconServer from '../assets/icons/IconServer.vue';
import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconLollms from '../assets/icons/IconLollms.vue';
import IconHome from '../assets/icons/IconHome.vue';
import IconBuild from '../assets/icons/IconBuild.vue';
import IconMicrophone from '../assets/icons/IconMicrophone.vue';
import IconDatabase from '../assets/icons/IconDatabase.vue';
import IconGlobeAlt from '../assets/icons/IconGlobeAlt.vue';
import IconFileText from '../assets/icons/IconFileText.vue';
import IconKey from '../assets/icons/IconKey.vue';
import IconEye from '../assets/icons/IconEye.vue'; // Icon for moderation

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore(); 

const wsConnected = computed(() => authStore.wsConnected); 

const AdminPanel = defineAsyncComponent(() => import('../components/admin/AdminPanel.vue'));

const sections = [
  { type: 'link', id: 'dashboard', name: 'Dashboard', icon: markRaw(IconDashboard) },
  { type: 'link', id: 'server_settings', name: 'Server Settings', icon: markRaw(IconServer) },
  { type: 'divider', label: 'Management' },
  { type: 'link', id: 'users', name: 'Users', icon: markRaw(IconUserGroup) },
  { type: 'link', id: 'moderation', name: 'Moderation Queue', icon: markRaw(IconEye) }, // New Entry
  { type: 'link', id: 'tasks', name: 'Tasks', icon: markRaw(IconTasks) },
  { type: 'link', id: 'broadcast', name: 'Broadcast', icon: markRaw(IconSend) },
  { type: 'divider', label: 'Content' },
  { type: 'link', id: 'news_management', name: 'News Articles', icon: markRaw(IconFileText) },
  { type: 'link', id: 'rss_feeds', name: 'RSS Feeds', icon: markRaw(IconGlobeAlt) },
  { type: 'link', id: 'news_feed_settings', name: 'News Feed Settings', icon: markRaw(IconCog) },
  { type: 'divider', label: 'Zoos' },
  { type: 'link', id: 'personalities', name: 'Personalities', icon: markRaw(IconUserCircle) },
  { type: 'link', id: 'prompts', name: 'Prompts', icon: markRaw(IconSparkles) },
  { type: 'link', id: 'mcps', name: 'MCPs', icon: markRaw(IconMcp) },
  { type: 'link', id: 'apps', name: 'Apps', icon: markRaw(IconSquares2x2) },
  { type: 'divider', label: 'Bindings & Services' },
  { type: 'link', id: 'llm_bindings', name: 'LLM Bindings', icon: markRaw(IconCpuChip) },
  { type: 'link', id: 'tti_bindings', name: 'TTI Bindings', icon: markRaw(IconPhoto) },
  { type: 'link', id: 'tts_bindings', name: 'TTS Bindings', icon: markRaw(IconMicrophone) },
  { type: 'link', id: 'stt_bindings', name: 'STT Bindings', icon: markRaw(IconMicrophone) },
  { type: 'link', id: 'rag_bindings', name: 'RAG Bindings', icon: markRaw(IconDatabase) },
  { type: 'link', id: 'builders', name: 'Code Builders', icon: markRaw(IconBuild) },
  { type: 'link', id: 'ai_bot', name: 'AI Bot', icon: markRaw(IconLollms) },
  { type: 'divider', label: 'System & Tools' },
  { type: 'link', id: 'welcome_settings', name: 'Welcome Page', icon: markRaw(IconHome) },
  { type: 'link', id: 'global_settings', name: 'Application Settings', icon: markRaw(IconCog) },
  { type: 'link', id: 'email', name: 'Email Settings', icon: markRaw(IconMail) },
  { type: 'link', id: 'sso_client_settings', name: 'SSO Client', icon: markRaw(IconKey) },
  { type: 'link', id: 'scim_settings', name: 'SCIM Provisioning', icon: markRaw(IconUserGroup) },
  { type: 'link', id: 'import', name: 'Import Tools', icon: markRaw(IconArrowDownTray) },
];

const activeSectionId = computed({
    get: () => route.query.section || 'dashboard',
    set: (sectionId) => {
        router.push({ query: { ...route.query, section: sectionId } });
    }
});
</script>

<template>
    <PageViewLayout title="Admin Panel" :title-icon="IconCog">
        <template #sidebar>
            <div class="p-3 mb-2 border-b dark:border-gray-700">
                <div class="flex items-center gap-2 text-xs" :class="wsConnected ? 'text-green-500' : 'text-red-500'">
                    <IconServer class="w-4 h-4" />
                    <span class="font-semibold">WebSocket: {{ wsConnected ? 'Connected' : 'Disconnected' }}</span>
                </div>
            </div>
            <template v-for="(section, index) in sections" :key="index">
                <div v-if="section.type === 'divider'" class="px-3 pt-4 pb-2 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
                    {{ section.label }}
                </div>
                <a v-else-if="section.type === 'link'"
                   href="#"
                   @click.prevent="activeSectionId = section.id"
                   class="flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors"
                   :class="activeSectionId === section.id ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'"
                >
                    <component :is="section.icon" class="w-5 h-5" />
                    <span>{{ section.name }}</span>
                </a>
            </template>
        </template>
        <template #main>
            <div class="p-4 sm:p-6 h-full">
                <AdminPanel :active-tab="activeSectionId" />
            </div>
        </template>
    </PageViewLayout>
</template>
