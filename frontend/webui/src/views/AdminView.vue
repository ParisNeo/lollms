<script setup>
import { computed, defineAsyncComponent } from 'vue';
import { useRoute, useRouter } from 'vue-router';
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

const route = useRoute();
const router = useRouter();

// Define components for dynamic loading
const components = {
  dashboard: defineAsyncComponent(() => import('../components/admin/Dashboard.vue')),
  users: defineAsyncComponent(() => import('../components/admin/UserTable.vue')),
  tasks: defineAsyncComponent(() => import('../components/admin/TaskManager.vue')),
  bindings: defineAsyncComponent(() => import('../components/admin/BindingsSettings.vue')),
  apps: defineAsyncComponent(() => import('../components/admin/zoos/AppsManagement.vue')),
  mcps: defineAsyncComponent(() => import('../components/admin/zoos/McpsManagement.vue')),
  personalities: defineAsyncComponent(() => import('../components/admin/zoos/PersonalitiesManagement.vue')),
  prompts: defineAsyncComponent(() => import('../components/admin/zoos/PromptsManagement.vue')),
  global_settings: defineAsyncComponent(() => import('../components/admin/GlobalSettings.vue')),
  https: defineAsyncComponent(() => import('../components/admin/HttpsSettings.vue')),
  email: defineAsyncComponent(() => import('../components/admin/EmailSettings.vue')),
  import: defineAsyncComponent(() => import('../components/admin/ImportTools.vue')),
};

const sections = [
  { type: 'link', id: 'dashboard', name: 'Dashboard', icon: IconDashboard },
  { type: 'divider', label: 'Management' },
  { type: 'link', id: 'users', name: 'Users', icon: IconUserGroup },
  { type: 'link', id: 'tasks', name: 'Tasks', icon: IconTasks },
  { type: 'divider', label: 'Zoos' },
  { type: 'link', id: 'personalities', name: 'Personalities', icon: IconUserCircle },
  { type: 'link', id: 'prompts', name: 'Prompts', icon: IconSparkles },
  { type: 'link', id: 'mcps', name: 'MCPs', icon: IconMcp },
  { type: 'link', id: 'apps', name: 'Apps', icon: IconSquares2x2 },
  { type: 'divider', label: 'System & Tools' },
  { type: 'link', id: 'bindings', name: 'LLM Bindings', icon: IconCpuChip },
  { type: 'link', id: 'global_settings', name: 'Global Settings', icon: IconCog },
  { type: 'link', id: 'https', name: 'HTTPS Settings', icon: IconKey },
  { type: 'link', id: 'email', name: 'Email Settings', icon: IconMail },
  { type: 'link', id: 'import', name: 'Import Tools', icon: IconArrowDownTray },
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

</script>

<template>
    <PageViewLayout title="Admin Panel" :titleIcon="IconCog">
        <template #sidebar>
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
            <div class="p-4 sm:p-6">
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
    </PageViewLayout>
</template>