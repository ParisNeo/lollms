<script setup>
import { ref, computed, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import McpCard from '../ui/McpCard.vue';
import IconInfo from '../../assets/icons/IconInfo.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();

const { userMcps } = storeToRefs(dataStore);

const isReloading = ref(false);

onMounted(() => {
    dataStore.fetchMcps();
});

const sortedUserMcps = computed(() => userMcps.value.filter(m => m.type === 'user').sort((a, b) => a.name.localeCompare(b.name)));
const sortedSystemMcps = computed(() => userMcps.value.filter(m => m.type === 'system').sort((a, b) => a.name.localeCompare(b.name)));

function showAddForm() {
    uiStore.openModal('serviceRegistration', { itemType: 'mcp' });
}

function startEditing(item) {
    uiStore.openModal('serviceRegistration', { item, itemType: 'mcp' });
}

async function handleReloadServers() {
    isReloading.value = true;
    try { await dataStore.triggerMcpReload(); } 
    finally { isReloading.value = false; }
}

async function handleDeleteItem(item) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete '${item.name}'?`,
        message: 'Are you sure you want to remove this registered MCP server?',
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
                <div class="ml-3"><p class="text-sm">This section is for registering personal, external MCPs by providing a URL. For locally installed MCPs, please visit the <router-link to="/admin" class="font-medium underline hover:text-blue-600 dark:hover:text-blue-300">Admin Panel</router-link>.</p></div>
            </div>
        </div>

        <section>
            <div class="flex justify-between items-center mb-4"><h3 class="text-xl font-bold">Your Personal MCPs</h3><button @click="showAddForm" class="btn btn-primary text-sm">+ Add Personal Server</button></div>
            <div v-if="sortedUserMcps.length === 0" class="empty-state-card"><p>You haven't added any personal MCPs.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"><McpCard v-for="mcp in sortedUserMcps" :key="mcp.id" :mcp="mcp" is-editable @edit="startEditing(mcp)" @delete="handleDeleteItem(mcp)" /></div>
        </section>

        <section>
            <div class="flex justify-between items-center my-4"><h3 class="text-xl font-bold">System MCPs</h3><button @click="handleReloadServers()" class="btn btn-secondary text-sm" :disabled="isReloading">{{ isReloading ? 'Reloading...' : 'Reload All' }}</button></div>
            <div v-if="sortedSystemMcps.length === 0" class="empty-state-card"><p>No system-wide MCPs available.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"><McpCard v-for="mcp in sortedSystemMcps" :key="mcp.id" :mcp="mcp" /></div>
        </section>
    </div>
</template>