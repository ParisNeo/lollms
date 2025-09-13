<script setup>
import { computed, defineAsyncComponent, markRaw, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth'; // Import auth store
import PageViewLayout from '../components/layout/PageViewLayout.vue';

// Import Icons
import IconDashboard from '../assets/icons/IconDashboard.vue';
import IconUserGroup from '../assets/icons/IconUserGroup.vue';
import IconTasks from '../assets/icons/IconTasks.vue';
import IconSquares2x2 from '../assets/icons/IconSquares2x2.vue';
import IconMcp from '../assets/icons/IconMcp.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconUserCircle from '../assets/icons/IconUserCircle.vue';
import IconCpuChip from '../assets/icons/IconCpuChip.vue';
import IconCog from '../assets/icons/IconCog.vue';
import IconKey from '../assets/icons/IconKey.vue';
import IconMail from '../assets/icons/IconMail.vue';
import IconArrowDownTray from '../assets/icons/IconArrowDownTray.vue';
import IconSend from '../assets/icons/IconSend.vue';
import IconServer from '../assets/icons/IconServer.vue'; 
import IconPhoto from '../assets/icons/IconPhoto.vue';
import IconChevronRight from '../assets/icons/IconChevronRight.vue';
import IconLollms from '../assets/icons/IconLollms.vue';
import IconHome from '../assets/icons/IconHome.vue';
import IconBuild from '../assets/icons/IconBuild.vue';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore(); 

const wsConnected = computed(() => authStore.wsConnected); 
const openGroups = ref(['bindings']); // Keep the 'bindings' group open by default

// Define components for dynamic loading
const components = {
  dashboard: defineAsyncComponent(() => import('../components/admin/Dashboard.vue')),
  users: defineAsyncComponent(() => import('../components/admin/UserTable.vue')),
  tasks: defineAsyncComponent(() => import('../components/admin/TaskManager.vue')),
  broadcast: defineAsyncComponent(() => import('../components/admin/BroadcastMessage.vue')),
  llm_bindings: defineAsyncComponent(() => import('../components/admin/bindings/LLMBindingsSettings.vue')),
  tti_bindings: defineAsyncComponent(() => import('../components/admin/bindings/TTIBindingsSettings.vue')),
  builders: defineAsyncComponent(() => import('../components/admin/BuildersSettings.vue')),
  ai_bot: defineAsyncComponent(() => import('../components/admin/AiBotSettings.vue')),
  services: defineAsyncComponent(() => import('../components/settings/ServicesSettings.vue')),
  apps: defineAsyncComponent(() => import('../components/admin/zoos/AppsManagement.vue')),
  mcps: defineAsyncComponent(() => import('../components/admin/zoos/McpsManagement.vue')),
  personalities: defineAsyncComponent(() => import('../components/admin/zoos/PersonalitiesManagement.vue')),
  prompts: defineAsyncComponent(() => import('../components/admin/zoos/PromptsManagement.vue')),
  global_settings: defineAsyncComponent(() => import('../components/admin/GlobalSettings.vue')),
  https: defineAsyncComponent(() => import('../components/admin/HttpsSettings.vue')),
  email: defineAsyncComponent(() => import('../components/admin/EmailSettings.vue')),
  import: defineAsyncComponent(() => import('../components/admin/ImportTools.vue')),
  welcome_settings: defineAsyncComponent(() => import('../components/admin/WelcomeSettings.vue')),
};

const sections = [
  { type: 'link', id: 'dashboard', name: 'Dashboard', icon: markRaw(IconDashboard) },
  { type: 'divider', label: 'Management' },
  { type: 'link', id: 'users', name: 'Users', icon: markRaw(IconUserGroup) },
  { type: 'link', id: 'tasks', name: 'Tasks', icon: markRaw(IconTasks) },
  { type: 'link', id: 'broadcast', name: 'Broadcast', icon: markRaw(IconSend) },
  { type: 'divider', label: 'Zoos' },
  { type: 'link', id: 'personalities', name: 'Personalities', icon: markRaw(IconUserCircle) },
  { type: 'link', id: 'prompts', name: 'Prompts', icon: markRaw(IconSparkles) },
  { type: 'link', id: 'mcps', name: 'MCPs', icon: markRaw(IconMcp) },
  { type: 'link', id: 'apps', name: 'Apps', icon: markRaw(IconSquares2x2) },
  { type: 'divider', label: 'Bindings & Services' },
  { type: 'link', id: 'llm_bindings', name: 'LLM Bindings', icon: markRaw(IconCpuChip) },
  { type: 'link', id: 'tti_bindings', name: 'TTI Bindings', icon: markRaw(IconPhoto) },
  { type: 'link', id: 'builders', name: 'Code Builders', icon: markRaw(IconBuild) },
  { type: 'link', id: 'ai_bot', name: 'AI Bot', icon: markRaw(IconLollms) },
  { type: 'link', id: 'services', name: 'API Services', icon: markRaw(IconServer) },
  { type: 'divider', label: 'System & Tools' },
  { type: 'link', id: 'welcome_settings', name: 'Welcome Page', icon: markRaw(IconHome) },
  { type: 'link', id: 'global_settings', name: 'Global Settings', icon: markRaw(IconCog) },
  { type: 'link', id: 'https', name: 'HTTPS Settings', icon: markRaw(IconKey) },
  { type: 'link', id: 'email', name: 'Email Settings', icon: markRaw(IconMail) },
  { type: 'link', id: 'import', name: 'Import Tools', icon: markRaw(IconArrowDownTray) },
];

const activeSectionId = computed({
    get: () => route.query.section || 'dashboard',
    set: (sectionId) => {
        router.push({ query: { ...route.query, section: sectionId } });
    }
});

const activeComponent = computed(() => {
    return components[activeSectionId.value] || components.dashboard;
});

function toggleGroup(groupId) {
    const index = openGroups.value.indexOf(groupId);
    if (index > -1) {
        openGroups.value.splice(index, 1);
    } else {
        openGroups.value.push(groupId);
    }
}
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
                <div v-else-if="section.type === 'group'">
                    <button @click="toggleGroup(section.id)" class="w-full flex items-center justify-between gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50">
                        <div class="flex items-center gap-3">
                            <component :is="section.icon" class="w-5 h-5" />
                            <span>{{ section.name }}</span>
                        </div>
                        <IconChevronRight class="w-4 h-4 transition-transform" :class="{'rotate-90': openGroups.includes(section.id)}" />
                    </button>
                    <div v-if="openGroups.includes(section.id)" class="pl-4 mt-1 space-y-1">
                        <a v-for="item in section.sub_items" :key="item.id"
                           href="#"
                           @click.prevent="activeSectionId = item.id"
                           class="flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition-colors"
                           :class="activeSectionId === item.id ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'">
                            <component :is="item.icon" class="w-5 h-5" />
                            <span>{{ item.name }}</span>
                        </a>
                    </div>
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
            <div class="p-4 sm:p-6">
                <Suspense>
                    <template #default>
                        <component :is="activeComponent" :key="activeSectionId" />
                    </template>
                    <template #fallback>
                        <div class="text-center py-10">
                            <p class="text-gray-500 dark:text-gray-400">Loading component...</p>
                        </div>
                    </template>
                </Suspense>
            </div>
        </template>
    </PageViewLayout>
</template>