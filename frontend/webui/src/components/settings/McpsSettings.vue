<script setup>
import { computed, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import McpCard from '../ui/McpCard.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const { userMcps, systemMcps } = storeToRefs(dataStore);
const { isAdmin } = storeToRefs(authStore);

onMounted(() => {
    dataStore.fetchMcps();
});

const sortedUserMcps = computed(() => userMcps.value.sort((a, b) => a.name.localeCompare(b.name)));
const sortedSystemMcps = computed(() => systemMcps.value.sort((a, b) => a.name.localeCompare(b.name)));

function showAddForm() {
    uiStore.openModal('serviceRegistration', { itemType: 'mcp', ownerType: 'user', onRegistered: dataStore.fetchMcps });
}

function showAddSystemForm() {
    uiStore.openModal('serviceRegistration', { itemType: 'mcp', ownerType: 'system', onRegistered: dataStore.fetchMcps });
}

function startEditing(item) {
    uiStore.openModal('serviceRegistration', { item, itemType: 'mcp', onRegistered: dataStore.fetchMcps });
}

async function handleDeleteItem(item) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete '${item.name}'?`,
        message: 'Are you sure you want to remove this registered MCP?',
        confirmText: 'Delete'
    });
    if (confirmed) {
        await dataStore.deleteMcp(item.id);
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
                <div class="ml-3"><p class="text-sm">This section is for registering personal, external MCPs by providing a URL. For locally installed services, please visit the <router-link to="/admin?section=mcps" class="font-medium underline hover:text-blue-600 dark:hover:text-blue-300">Admin Panel</router-link>.</p></div>
            </div>
        </div>

        <section>
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
                <h3 class="text-xl font-bold">Your Personal MCPs</h3>
                 <div class="flex items-center gap-x-2">
                    <button @click="showAddForm" class="btn btn-primary text-sm">+ Add Personal MCP</button>
                    <button v-if="isAdmin" @click="showAddSystemForm" class="btn btn-secondary text-sm">+ Add System MCP</button>
                </div>
            </div>
            <div v-if="sortedUserMcps.length === 0" class="empty-state-card"><p>You haven't added any personal MCPs.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"><McpCard v-for="mcp in sortedUserMcps" :key="mcp.id" :mcp="mcp" is-editable @edit="startEditing(mcp)" @delete="handleDeleteItem(mcp)" /></div>
        </section>
        
        <section>
            <h3 class="text-xl font-bold my-4">System MCPs</h3>
            <div v-if="sortedSystemMcps.length === 0" class="empty-state-card"><p>No system-wide MCPs available.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <McpCard v-for="mcp in sortedSystemMcps" :key="mcp.id" :mcp="mcp" :is-editable="isAdmin" @edit="startEditing(mcp)" @delete="handleDeleteItem(mcp)" />
            </div>
        </section>
    </div>
</template>