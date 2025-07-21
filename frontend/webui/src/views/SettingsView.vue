<script setup>
import { ref, defineAsyncComponent, computed } from 'vue';
import { useAuthStore } from '../stores/auth';
import PageViewLayout from '../components/layout/PageViewLayout.vue';

import IconUserCircle from '../assets/icons/IconUserCircle.vue';
import IconSettings from '../assets/icons/IconSettings.vue';
import IconCog from '../assets/icons/IconCog.vue';
import IconSparkles from '../assets/icons/IconSparkles.vue';
import IconDatabase from '../assets/icons/IconDatabase.vue';
import IconWrenchScrewdriver from '../assets/icons/IconWrenchScrewdriver.vue';
import IconKey from '../assets/icons/IconKey.vue';

const AccountSettings = defineAsyncComponent(() => import('../components/settings/AccountSettings.vue'));
const GeneralSettings = defineAsyncComponent(() => import('../components/settings/GeneralSettings.vue'));
const LLMSettings = defineAsyncComponent(() => import('../components/settings/LLMSettings.vue'));
const PersonalitiesSettings = defineAsyncComponent(() => import('../components/settings/PersonalitiesSettings.vue'));
const RAGSettings = defineAsyncComponent(() => import('../components/settings/RAGSettings.vue'));
const ServicesSettings = defineAsyncComponent(() => import('../components/settings/ServicesSettings.vue'));
const ApiKeysSettings = defineAsyncComponent(() => import('../components/settings/ApiKeysSettings.vue'));

const authStore = useAuthStore();

const activeTab = ref('account');

const tabs = [
    { id: 'account', label: 'Account', icon: IconUserCircle, component: AccountSettings },
    { id: 'general', label: 'General', icon: IconSettings, component: GeneralSettings },
    { id: 'llmConfig', label: 'LLM Config', icon: IconCog, component: LLMSettings },
    { id: 'personalities', label: 'Personalities', icon: IconSparkles, component: PersonalitiesSettings },
    { id: 'rag', label: 'RAG', minLevel: 1, icon: IconDatabase, component: RAGSettings },
    { id: 'services', label: 'Services', minLevel: 3, icon: IconWrenchScrewdriver, component: ServicesSettings },
    { id: 'apiKeys', label: 'API Keys', minLevel: 2, icon: IconKey, component: ApiKeysSettings }
];

const user = computed(() => authStore.user);

const visibleTabs = computed(() => {
    if (!user.value) return [];
    return tabs.filter(tab => {
        if (tab.adminOnly && !user.value.is_admin) return false;
        if (tab.minLevel && user.value.user_ui_level < tab.minLevel) return false;
        return true;
    });
});

const activeComponent = computed(() => {
    const active = visibleTabs.value.find(t => t.id === activeTab.value);
    return active ? active.component : null;
});
</script>

<template>
  <PageViewLayout title="Settings" :title-icon="IconSettings">
    <template #sidebar>
      <button 
        v-for="tab in visibleTabs" 
        :key="tab.id"
        @click="activeTab = tab.id" 
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
              <component v-if="activeComponent" :is="activeComponent" />
              <div v-else class="text-center text-gray-500 dark:text-gray-400">
                  <p>Select a category to view settings.</p>
              </div>
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