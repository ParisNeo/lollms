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

const tabs = [
  { id: 'account', label: 'Account', component: AccountSettings, icon: IconUserCircle },
  { id: 'general', label: 'General', component: GeneralSettings, icon: IconCog },
  { id: 'llm', label: 'LLM', component: LLMSettings, icon: IconCpuChip },
  { id: 'rag', label: 'RAG', component: RAGSettings, icon: IconDatabase },
  { id: 'personalities', label: 'Personalities', component: PersonalitiesSettings, icon: IconSparkles },
  { id: 'prompts', label: 'User Prompts', component: PromptsSettings, icon: IconTicket },
  { id: 'mcps', label: 'MCPs', component: McpsSettings, icon: IconMcp },
  { id: 'apps', label: 'Apps', component: AppsSettings, icon: IconSquares2x2 },
  { id: 'api-keys', label: 'API Keys', component: ApiKeysSettings, icon: IconKey },
];

const activeTab = ref(route.query.tab || 'account');

watch(() => route.query.tab, (newTab) => {
  if (newTab && tabs.some(t => t.id === newTab)) {
    activeTab.value = newTab;
  }
});

const activeComponent = computed(() => {
    return tabs.find(tab => tab.id === activeTab.value)?.component || null;
});

function selectTab(tabId) {
    activeTab.value = tabId;
    router.push({ query: { tab: tabId } });
}
</script>

<template>
  <PageViewLayout title="Settings" :title-icon="IconCog">
    <template #sidebar>
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        @click="selectTab(tab.id)" 
        :class="{ 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300': activeTab === tab.id }" 
        class="w-full flex items-center space-x-3 text-left px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
      >
        <component :is="tab.icon" class="w-5 h-5 flex-shrink-0" />
        <span>{{ tab.label }}</span>
      </button>
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