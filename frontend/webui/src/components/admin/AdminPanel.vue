<script setup>
import { ref, computed, defineAsyncComponent, onMounted } from 'vue';
import { useUiStore } from '../../stores/ui';
import { useAdminStore } from '../../stores/admin';
import { storeToRefs } from 'pinia';

// --- Components ---
const Dashboard = defineAsyncComponent(() => import('./Dashboard.vue'));
const UserTable = defineAsyncComponent(() => import('./UserTable.vue'));
const GlobalSettings = defineAsyncComponent(() => import('./GlobalSettings.vue'));
const BindingsSettings = defineAsyncComponent(() => import('./BindingsSettings.vue'));
const EmailSettings = defineAsyncComponent(() => import('./EmailSettings.vue'));
const ImportTools = defineAsyncComponent(() => import('./ImportTools.vue'));
const ServicesSettings = defineAsyncComponent(() => import('./ServicesSettings.vue'));
const HttpsSettings = defineAsyncComponent(() => import('./HttpsSettings.vue')); // Added

const uiStore = useUiStore();
const adminStore = useAdminStore();

const { globalSettings, allUsers } = storeToRefs(adminStore);

const activeTab = ref('dashboard');

const emailMode = computed(() => {
    const setting = globalSettings.value.find(s => s.key === 'password_recovery_mode');
    return setting ? setting.value : 'manual';
});

const tabs = [
    { id: 'dashboard', label: 'Dashboard', component: Dashboard },
    { id: 'users', label: 'User Management', component: UserTable },
    { id: 'https', label: 'Server/HTTPS', component: HttpsSettings }, // Added
    { id: 'bindings', label: 'LLM Bindings', component: BindingsSettings },
    { id: 'services', label: 'Services', component: ServicesSettings },
    { id: 'global_settings', label: 'Global Settings', component: GlobalSettings },
    { id: 'email', label: 'Email Settings', component: EmailSettings },
    { id: 'import', label: 'Import', component: ImportTools }
];

const activeComponent = computed(() => {
    return tabs.find(tab => tab.id === activeTab.value)?.component || null;
});

function handleEmailAllUsers() {
    const eligibleUsers = allUsers.value.filter(u => u.is_active && u.receive_notification_emails && u.email);

    if (emailMode.value === 'manual') {
        uiStore.openModal('emailList', { users: eligibleUsers });
    } else {
        uiStore.openModal('emailAllUsers');
    }
}

onMounted(() => {
    adminStore.fetchAllUsers();
    adminStore.fetchGlobalSettings();
});
</script>

<template>
    <div class="space-y-8">
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
                <h1 class="text-2xl font-bold text-gray-900 dark:text-white">Admin Dashboard</h1>
                <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Manage users, system settings, and application configurations.
                </p>
            </div>
            <div>
                <button
                    type="button"
                    class="btn btn-primary"
                    @click="handleEmailAllUsers"
                >
                    Email Users
                </button>
            </div>
        </div>

        <!-- Tab Navigation -->
        <div class="border-b border-gray-200 dark:border-gray-700">
            <nav class="-mb-px flex space-x-6 overflow-x-auto" aria-label="Tabs">
                <button
                    v-for="tab in tabs"
                    :key="tab.id"
                    @click="activeTab = tab.id"
                    :class="[
                        activeTab === tab.id
                            ? 'border-blue-500 text-blue-600 dark:border-blue-400 dark:text-blue-300'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-500',
                        'whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors'
                    ]"
                >
                    {{ tab.label }}
                </button>
            </nav>
        </div>

        <!-- Tab Content -->
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
    </div>
</template>