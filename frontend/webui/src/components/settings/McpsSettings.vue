<!-- [REWRITE] frontend/webui/src/components/settings/McpsSettings.vue -->
<script setup>
import { onMounted, computed } from 'vue';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { storeToRefs } from 'pinia';
import McpCard from '../ui/McpCard.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();

const { userMcps, systemMcps } = storeToRefs(dataStore);

onMounted(() => {
    dataStore.fetchMcps();
});

function handleAddMcp() {
    uiStore.openModal('serviceRegistration', { 
        itemType: 'mcp', 
        ownerType: 'user',
        onRegistered: dataStore.fetchMcps 
    });
}

function handleEditMcp(mcp) {
    uiStore.openModal('serviceRegistration', { 
        item: mcp, 
        itemType: 'mcp', 
        ownerType: 'user',
        onRegistered: dataStore.fetchMcps 
    });
}

async function handleDeleteMcp(mcp) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete MCP '${mcp.name}'?`,
        message: 'This will permanently remove your registered MCP. This action cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        await dataStore.deleteMcp(mcp.id);
    }
}
</script>

<template>
    <div class="space-y-10">
        <!-- Personal MCPs Section -->
        <div>
            <div class="flex justify-between items-center mb-4">
                <div>
                    <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                        My Personal MCPs
                    </h3>
                    <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        MCPs you have personally registered. They are only visible and usable by you.
                    </p>
                </div>
                <button @click="handleAddMcp" class="btn btn-primary">Register New MCP</button>
            </div>
            
            <div v-if="userMcps.length === 0" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <p class="text-gray-500">You have no personal MCPs registered.</p>
            </div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <McpCard 
                    v-for="mcp in userMcps" 
                    :key="mcp.id" 
                    :mcp="mcp" 
                    is-editable 
                    @edit="handleEditMcp" 
                    @delete="handleDeleteMcp" 
                />
            </div>
        </div>

        <!-- System MCPs Section -->
        <div>
            <div class="mb-4">
                <h3 class="text-xl font-semibold leading-6 text-gray-900 dark:text-white">
                    Available System MCPs
                </h3>
                <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    MCPs provided by the administrator for everyone to use.
                </p>
            </div>
            
            <div v-if="systemMcps.length === 0" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <p class="text-gray-500">No system-wide MCPs are currently available.</p>
            </div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <McpCard 
                    v-for="mcp in systemMcps" 
                    :key="mcp.id" 
                    :mcp="mcp" 
                    :is-editable="false" 
                />
            </div>
        </div>
    </div>
</template>