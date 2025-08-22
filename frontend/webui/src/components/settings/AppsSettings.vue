<!-- [REWRITE] frontend/webui/src/components/settings/AppsSettings.vue -->
<script setup>
import { onMounted, computed } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';
import McpCard from '../ui/McpCard.vue'; // Reusing for consistent look

const dataStore = useDataStore();
const uiStore = useUiStore();

const { userApps, systemApps } = storeToRefs(dataStore);

onMounted(() => {
    dataStore.fetchApps();
});

function handleAddApp() {
    uiStore.openModal('serviceRegistration', { 
        itemType: 'app', 
        ownerType: 'user',
        onRegistered: dataStore.fetchApps 
    });
}

function handleEditApp(app) {
    uiStore.openModal('serviceRegistration', { 
        item: app, 
        itemType: 'app', 
        ownerType: 'user',
        onRegistered: dataStore.fetchApps 
    });
}

async function handleDeleteApp(app) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete App '${app.name}'?`,
        message: 'This will permanently remove your registered app. This action cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        await dataStore.deleteApp(app.id);
    }
}
</script>

<template>
    <div class="space-y-10">
        <!-- Personal Apps Section -->
        <div>
            <div class="flex justify-between items-center mb-4">
                <div>
                    <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                        My Personal Apps
                    </h3>
                    <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        Apps you have personally registered. They are only visible and usable by you.
                    </p>
                </div>
                <button @click="handleAddApp" class="btn btn-primary">Register New App</button>
            </div>
            
            <div v-if="userApps.length === 0" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <p class="text-gray-500">You have no personal apps registered.</p>
            </div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <McpCard 
                    v-for="app in userApps" 
                    :key="app.id" 
                    :mcp="app" 
                    is-editable 
                    @edit="handleEditApp" 
                    @delete="handleDeleteApp" 
                />
            </div>
        </div>

        <!-- System Apps Section -->
        <div>
            <div class="mb-4">
                <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                    Available System Apps
                </h3>
                <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Apps provided by the administrator for everyone to use.
                </p>
            </div>
            
            <div v-if="systemApps.length === 0" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <p class="text-gray-500">No system-wide apps are currently available.</p>
            </div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <McpCard 
                    v-for="app in systemApps" 
                    :key="app.id" 
                    :mcp="app" 
                    :is-editable="false" 
                />
            </div>
        </div>
    </div>
</template>