<script setup>
import { computed, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import McpCard from '../ui/McpCard.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();

const { userApps } = storeToRefs(dataStore);

onMounted(() => {
    dataStore.fetchApps();
});

const sortedUserApps = computed(() => userApps.value.filter(a => a.type === 'user' && !a.is_installed).sort((a, b) => a.name.localeCompare(b.name)));
const sortedSystemApps = computed(() => userApps.value.filter(a => a.type === 'system' && !a.is_installed).sort((a, b) => a.name.localeCompare(b.name)));

function showAddForm() {
    uiStore.openModal('serviceRegistration', { itemType: 'app' });
}

function startEditing(item) {
    uiStore.openModal('serviceRegistration', { item, itemType: 'app' });
}

async function handleDeleteItem(item) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete '${item.name}'?`,
        message: 'Are you sure you want to remove this registered Application?',
        confirmText: 'Delete'
    });
    if (confirmed) {
        await dataStore.deleteApp(item.id);
    }
}
</script>

<style scoped>
.empty-state-card { @apply text-center py-10 px-4 rounded-lg bg-gray-50 dark:bg-gray-800/50 text-gray-500 dark:text-gray-400; }
</style>

<template>
    <div class="space-y-10">
        <div class="p-4 bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-400 text-blue-800 dark:text-blue-200">
            <div class="flex">
                <div class="flex-shrink-0"><IconInfo class="h-5 w-5 text-blue-400" aria-hidden="true" /></div>
                <div class="ml-3"><p class="text-sm">This section is for registering personal, external Apps by providing a URL. For locally installed services, please visit the <router-link to="/admin" class="font-medium underline hover:text-blue-600 dark:hover:text-blue-300">Admin Panel</router-link>.</p></div>
            </div>
        </div>

        <section>
            <div class="flex justify-between items-center mb-4"><h3 class="text-xl font-bold">Your Personal Apps</h3><button @click="showAddForm" class="btn btn-primary text-sm">+ Add App</button></div>
            <div v-if="sortedUserApps.length === 0" class="empty-state-card"><p>You haven't added any personal Apps.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"><McpCard v-for="app in sortedUserApps" :key="app.id" :mcp="app" is-editable @edit="startEditing(app)" @delete="handleDeleteItem(app)" /></div>
        </section>
        
        <section>
            <h3 class="text-xl font-bold my-4">System Apps</h3>
            <div v-if="sortedSystemApps.length === 0" class="empty-state-card"><p>No system-wide Apps available.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"><McpCard v-for="app in sortedSystemApps" :key="app.id" :mcp="app" /></div>
        </section>
    </div>
</template>