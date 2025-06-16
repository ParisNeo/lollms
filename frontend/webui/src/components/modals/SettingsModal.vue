<script>
import { mapState, mapActions } from 'pinia';
import { defineAsyncComponent, watch } from 'vue';
import { useAuthStore } from '../../stores/auth';
import { useUiStore } from '../../stores/ui';
import GenericModal from '../ui/GenericModal.vue';

const AccountSettings = defineAsyncComponent(() => import('../settings/AccountSettings.vue'));
const LLMSettings = defineAsyncComponent(() => import('../settings/LLMSettings.vue'));
const PersonalitiesSettings = defineAsyncComponent(() => import('../settings/PersonalitiesSettings.vue'));
const RAGSettings = defineAsyncComponent(() => import('../settings/RAGSettings.vue'));
const MCPSettings = defineAsyncComponent(() => import('../settings/MCPSettings.vue'));
const AdminPanel = defineAsyncComponent(() => import('../admin/AdminPanel.vue'));

export default {
  name: 'SettingsModal',
  components: {
    GenericModal,
  },
  data() {
    return {
      activeTab: 'account',
      tabs: [
        { id: 'account', label: 'Account', icon: '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>', component: AccountSettings },
        { id: 'llmConfig', label: 'LLM Config', icon: '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>', component: LLMSettings },
        { id: 'personalities', label: 'Personalities', icon: '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0zm6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>', component: PersonalitiesSettings },
        { id: 'rag', label: 'RAG', icon: '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>', component: RAGSettings },
        { id: 'mcps', label: 'MCPs', icon: '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7" /></svg>', component: MCPSettings },
        { id: 'admin', label: 'Administration', icon: '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M15 21v-1.5a6.375 6.375 0 00-3.262-5.171M9 10a3 3 0 11-6 0 3 3 0 016 0zm3 2a3 3 0 11-6 0 3 3 0 016 0z" /></svg>', adminOnly: true, component: AdminPanel }
      ]
    };
  },
  computed: {
    ...mapState(useAuthStore, ['isAdmin']),
    ...mapState(useUiStore, {
        modalData: state => state.modalData('settings')
    }),
    visibleTabs() {
        return this.tabs.filter(tab => !tab.adminOnly || this.isAdmin);
    },
    activeComponent() {
        const active = this.visibleTabs.find(t => t.id === this.activeTab);
        return active ? active.component : null;
    }
  },
  watch: {
      modalData(newData) {
          if(newData?.initialTab && this.tabs.some(t => t.id === newData.initialTab)) {
              this.activeTab = newData.initialTab;
          }
      }
  },
  created() {
      // Set initial tab when modal is first created/opened
      if(this.modalData?.initialTab && this.tabs.some(t => t.id === this.modalData.initialTab)) {
          this.activeTab = this.modalData.initialTab;
      }
  },
  methods: {
    ...mapActions(useUiStore, ['closeModal']),
  }
};
</script>

<template>
  <GenericModal modalName="settings" title="Settings" maxWidthClass="max-w-7xl">
    <template #body>
      <div class="flex flex-row flex-grow overflow-hidden -m-6 h-[85vh]">
        <!-- Tabs Navigation -->
        <nav class="w-56 border-r dark:border-gray-700 p-4 space-y-1 flex-shrink-0 bg-gray-50 dark:bg-gray-800/50 overflow-y-auto">
          <button 
            v-for="tab in visibleTabs" 
            :key="tab.id"
            @click="activeTab = tab.id" 
            :class="{'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300': activeTab === tab.id}" 
            class="w-full flex items-center space-x-3 text-left px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            <span v-html="tab.icon"></span>
            <span>{{ tab.label }}</span>
          </button>
        </nav>

        <!-- Tab Content -->
        <div class="flex-grow overflow-y-auto p-6">
            <Suspense>
                <template #default>
                    <component :is="activeComponent" />
                </template>
                <template #fallback>
                    <div class="flex items-center justify-center h-full">
                        <p class="text-gray-500 italic">Loading settings...</p>
                    </div>
                </template>
            </Suspense>
        </div>
      </div>
    </template>
    
    <template #footer>
      <button @click="closeModal('settings')" class="btn btn-secondary">Close</button>
    </template>
  </GenericModal>
</template>