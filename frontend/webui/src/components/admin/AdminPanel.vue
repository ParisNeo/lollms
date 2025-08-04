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
const BindingsSettings = defineAsyncComponent(() => import('./BindingsSettings.vue'));
const EmailSettings = defineAsyncComponent(() => import('./EmailSettings.vue'));
const ImportTools = defineAsyncComponent(() => import('./ImportTools.vue'));
const HttpsSettings = defineAsyncComponent(() => import('./HttpsSettings.vue'));
const AppsManagement = defineAsyncComponent(() => import('./AppsManagement.vue'));
const TaskManager = defineAsyncComponent(() => import('./TaskManager.vue'));

const tabs = [
    { id: 'dashboard', component: Dashboard },
    { id: 'users', component: UserTable },
    { id: 'tasks', component: TaskManager },
    { id: 'https', component: HttpsSettings },
    { id: 'bindings', component: BindingsSettings },
    { id: 'apps', component: AppsManagement },
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