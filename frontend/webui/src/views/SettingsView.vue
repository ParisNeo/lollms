<script setup>
import { computed, markRaw, defineAsyncComponent } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import PageViewLayout from '../components/layout/PageViewLayout.vue';

// Import Icons
import IconCog from '../assets/icons/IconCog.vue';
import IconCpuChip from '../assets/icons/IconCpuChip.vue';
import IconDatabase from '../assets/icons/IconDatabase.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconUserCircle from '../assets/icons/IconUserCircle.vue';
import IconSquares2x2 from '../assets/icons/IconSquares2x2.vue';
import IconMcp from '../assets/icons/IconMcp.vue';
import IconKey from '../assets/icons/IconKey.vue';
import IconLink from '../assets/icons/IconLink.vue';
import IconPhoto from '../assets/icons/IconPhoto.vue';

const route = useRoute();
const router = useRouter();

const components = {
  general: defineAsyncComponent(() => import('../components/settings/GeneralSettings.vue')),
  llm: defineAsyncComponent(() => import('../components/settings/LLMSettings.vue')),
  tti: defineAsyncComponent(() => import('../components/settings/TTISettings.vue')),
  rag: defineAsyncComponent(() => import('../components/settings/RAGSettings.vue')),
  personalities: defineAsyncComponent(() => import('../components/settings/PersonalitiesSettings.vue')),
  prompts: defineAsyncComponent(() => import('../components/settings/PromptsSettings.vue')),
  apps: defineAsyncComponent(() => import('../components/settings/AppsSettings.vue')),
  mcps: defineAsyncComponent(() => import('../components/settings/McpsSettings.vue')),
  api_keys: defineAsyncComponent(() => import('../components/settings/ApiKeysSettings.vue')),
  account: defineAsyncComponent(() => import('../components/settings/AccountSettings.vue')),
};

const sections = [
  { id: 'account', name: 'Account', icon: markRaw(IconUserCircle) },
  { id: 'general', name: 'General', icon: markRaw(IconCog) },
  { id: 'llm', name: 'LLM Parameters', icon: markRaw(IconCpuChip) },
  { id: 'tti', name: 'TTI Parameters', icon: markRaw(IconPhoto) },
  { id: 'rag', name: 'RAG Parameters', icon: markRaw(IconDatabase) },
  { type: 'divider', label: 'Customization' },
  { id: 'personalities', name: 'Personalities', icon: markRaw(IconUserCircle) },
  { id: 'prompts', name: 'Prompts', icon: markRaw(IconSparkles) },
  { id: 'apps', name: 'Apps', icon: markRaw(IconSquares2x2) },
  { id: 'mcps', name: 'MCPs', icon: markRaw(IconMcp) },
  { type: 'divider', label: 'Security' },
  { id: 'api_keys', name: 'API Keys', icon: markRaw(IconKey) },
];

const activeTab = computed({
    get: () => route.query.tab || 'account',
    set: (tab) => {
        router.push({ query: { ...route.query, tab: tab } });
    }
});

const activeComponent = computed(() => {
    return components[activeTab.value] || components.general;
});
</script>

<template>
    <PageViewLayout title="Settings" :title-icon="IconCog">
        <template #sidebar>
            <template v-for="(section, index) in sections" :key="index">
                <div v-if="section.type === 'divider'" class="px-3 pt-4 pb-2 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
                    {{ section.label }}
                </div>
                <a v-else
                   href="#"
                   @click.prevent="activeTab = section.id"
                   class="flex items-center gap-3 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors"
                   :class="activeTab === section.id ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700/50'"
                >
                    <component :is="section.icon" class="w-5 h-5" />
                    <span>{{ section.name }}</span>
                </a>
            </template>
        </template>
        <template #main>
            <div class="p-4 sm:p-6 lg:p-8">
                <div class="max-w-4xl mx-auto">
                    <Suspense>
                        <template #default>
                            <component :is="activeComponent" />
                        </template>
                        <template #fallback>
                            <div class="text-center py-10">
                                <p class="text-gray-500 dark:text-gray-400">Loading settings...</p>
                            </div>
                        </template>
                    </Suspense>
                </div>
            </div>
        </template>
    </PageViewLayout>
</template>