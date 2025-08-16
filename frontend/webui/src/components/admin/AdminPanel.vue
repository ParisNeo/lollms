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
const GlobalSettings = defineAsyncComponent(() => import('./GlobalSettings.vue'));
const LLMBindingsSettings = defineAsyncComponent(() => import('./bindings/LLMBindingsSettings.vue'));
const TTIBindingsSettings = defineAsyncComponent(() => import('./bindings/TTIBindingsSettings.vue'));
const EmailSettings = defineAsyncComponent(() => import('./EmailSettings.vue'));
const ImportTools = defineAsyncComponent(() => import('./ImportTools.vue'));
const HttpsSettings = defineAsyncComponent(() => import('./HttpsSettings.vue'));
const AppsManagement = defineAsyncComponent(() => import('./zoos/AppsManagement.vue'));
const McpsManagement = defineAsyncComponent(() => import('./zoos/McpsManagement.vue'));
const PromptsManagement = defineAsyncComponent(() => import('./zoos/PromptsManagement.vue'));
const PersonalitiesManagement = defineAsyncComponent(() => import('./zoos/PersonalitiesManagement.vue'));
const TaskManager = defineAsyncComponent(() => import('./TaskManager.vue'));
const BroadcastMessage = defineAsyncComponent(() => import('./BroadcastMessage.vue'));

const tabs = [
    { id: 'dashboard', component: Dashboard },
    { id: 'users', component: UserTable },
    { id: 'tasks', component: TaskManager },
    { id: 'broadcast', component: BroadcastMessage },
    { id: 'https', component: HttpsSettings },
    { id: 'llm_bindings', component: LLMBindingsSettings },
    { id: 'tti_bindings', component: TTIBindingsSettings },
    { id: 'apps', component: AppsManagement },
    { id: 'mcps', component: McpsManagement },
    { id: 'personalities', component: PersonalitiesManagement },
    { id: 'prompts', component: PromptsManagement },
    { id: 'global_settings', component: GlobalSettings },
    { id: 'email', component: EmailSettings },
    { id: 'import', component: ImportTools }
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