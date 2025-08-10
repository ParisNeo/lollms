<script setup>
import { ref, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import PageViewLayout from '../components/layout/PageViewLayout.vue';

import IconUserCircle from '../assets/icons/IconUserCircle.vue';
import IconCog from '../assets/icons/IconCog.vue';
import IconCpuChip from '../assets/icons/IconCpuChip.vue';
import IconDatabase from '../assets/icons/IconDatabase.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconMcp from '../assets/icons/IconMcp.vue';
import IconSquares2x2 from '../assets/icons/IconSquares2x2.vue';
import IconKey from '../assets/icons/IconKey.vue';
import IconTicket from '../assets/icons/IconTicket.vue';

import AccountSettings from '../components/settings/AccountSettings.vue';
import GeneralSettings from '../components/settings/GeneralSettings.vue';
import LLMSettings from '../components/settings/LLMSettings.vue';
import RAGSettings from '../components/settings/RAGSettings.vue';
import PersonalitiesSettings from '../components/settings/PersonalitiesSettings.vue';
import PromptsSettings from '../components/settings/PromptsSettings.vue';
import McpsSettings from '../components/settings/McpsSettings.vue';
import AppsSettings from '../components/settings/AppsSettings.vue';
import ApiKeysSettings from '../components/settings/ApiKeysSettings.vue';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const user = computed(() => authStore.user);

const sections = [
  { type: 'divider', label: 'User & Interface' },
  { type: 'link', id: 'account', name: 'Account', component: AccountSettings, icon: IconUserCircle },
  { type: 'link', id: 'general', name: 'General', component: GeneralSettings, icon: IconCog },
  
  { type: 'divider', label: 'AI Configuration' },
  { type: 'link', id: 'llm', name: 'LLM', component: LLMSettings, icon: IconCpuChip },
  { type: 'link', id: 'rag', name: 'RAG', component: RAGSettings, icon: IconDatabase },

  { type: 'divider', label: 'Content Management' },
  { type: 'link', id: 'personalities', name: 'Personalities', component: PersonalitiesSettings, icon: IconSparkles },
  { type: 'link', id: 'prompts', name: 'User Prompts', component: PromptsSettings, icon: IconTicket },

  { type: 'divider', label: 'Services & Integrations' },
  { type: 'link', id: 'mcps', name: 'MCPs', component: McpsSettings, icon: IconMcp },
  { type: 'link', id: 'apps', name: 'Apps', component: AppsSettings, icon: IconSquares2x2 },
  { type: 'link', id: 'api-keys', name: 'API Keys', component: ApiKeysSettings, icon: IconKey },
];

const activeTab = ref(route.query.tab || 'account');

watch(() => route.query.tab, (newTab) => {
  const allTabs = sections.filter(s => s.type === 'link').map(s => s.id);
  if (newTab && allTabs.includes(newTab)) {
    activeTab.value = newTab;
  }
});

const activeComponent = computed(() => {
    const linkItems = sections.filter(s => s.type === 'link');
    return linkItems.find(tab => tab.id === activeTab.value)?.component || null;
});

function selectTab(tabId) {
    activeTab.value = tabId;
    router.push({ query: { tab: tabId } });
}
</script>

<template>
  <PageViewLayout title="Settings" :title-icon="IconCog">
    <template #sidebar>
      <template v-for="(section, index) in sections" :key="index">
        <div v-if="section.type === 'divider'" class="px-3 pt-4 pb-2 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
            {{ section.label }}
        </div>
        <button 
          v-else-if="section.type === 'link'"
          @click="selectTab(section.id)" 
          :class="{ 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300': activeTab === section.id }" 
          class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        >
          <component :is="section.icon" class="w-5 h-5 flex-shrink-0" />
          <span>{{ section.name }}</span>
        </button>
      </template>
    </template>
    <template #main>
      <Suspense>
        <template #default>
            <component :is="activeComponent" />
        </template>
        <template #fallback>
            <div class="flex items-center justify-center h-full">
                <p class="text-lg text-gray-500 dark:text-gray-400 italic">Loading settings...</p>
            </div>
        </template>
      </Suspense>
    </template>
  </PageViewLayout>
</template>