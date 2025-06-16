<script setup>
import { ref, computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';

// --- Store Setup ---
const dataStore = useDataStore();
const uiStore = useUiStore();
const { userMcps } = storeToRefs(dataStore);

// --- Component State ---
const newMcpForm = ref({
    alias: '',
    address: ''
});
const isAdding = ref(false);

// --- Computed Properties ---
const sortedMcps = computed(() => {
    // Spreading to avoid sorting the original store array
    return [...userMcps.value].sort((a, b) => a.alias.localeCompare(b.alias));
});

// --- Methods ---
async function handleAddMcp() {
    if (!newMcpForm.value.alias || !newMcpForm.value.address) {
        uiStore.addNotification('Alias and Address are required.', 'warning');
        return;
    }

    isAdding.value = true;
    try {
        await dataStore.addMcp(newMcpForm.value);
        // Reset form on success
        newMcpForm.value.alias = '';
        newMcpForm.value.address = '';
    } catch (error) {
        // Error notification is handled by the data store or global interceptor
        // The component does not need to crash or block
    } finally {
        isAdding.value = false;
    }
}

async function handleDeleteMcp(mcp) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete '${mcp.alias}'?`,
        message: `Are you sure you want to remove the MCP server at ${mcp.address}? This cannot be undone.`,
        confirmText: 'Delete'
    });
    if (confirmed) {
        await dataStore.deleteMcp(mcp.id);
    }
}
</script>

<template>
    <div class="space-y-8">
        <!-- Add MCP Server Section -->
        <section>
            <h4 class="text-lg font-semibold mb-4 border-b dark:border-gray-600 pb-2">Add MCP Server</h4>
            <form @submit.prevent="handleAddMcp" class="space-y-4 max-w-xl">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <label for="mcpAlias" class="block text-sm font-medium">Alias</label>
                        <input type="text" id="mcpAlias" v-model="newMcpForm.alias" class="input-field mt-1" placeholder="e.g., My Local Server" required>
                    </div>
                    <div>
                        <label for="mcpAddress" class="block text-sm font-medium">Address</label>
                        <input type="url" id="mcpAddress" v-model="newMcpForm.address" class="input-field mt-1" placeholder="http://127.0.0.1:9602" required>
                    </div>
                </div>
                <div class="text-right">
                    <button type="submit" class="btn btn-primary" :disabled="isAdding">
                        {{ isAdding ? 'Adding...' : 'Add MCP Server' }}
                    </button>
                </div>
            </form>
        </section>

        <!-- Manage MCP Servers Section -->
        <section>
            <h4 class="text-lg font-semibold mb-2">Configured MCP Servers</h4>
            <div class="max-h-80 overflow-y-auto border dark:border-gray-600 rounded p-2 space-y-1">
                <p v-if="!sortedMcps || sortedMcps.length === 0" class="italic text-sm text-gray-500 p-2">
                    No MCP servers configured. Add one using the form above.
                </p>
                <div v-for="mcp in sortedMcps" :key="mcp.id" class="flex justify-between items-center py-1.5 px-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-sm">
                    <div>
                        <strong class="font-medium text-gray-800 dark:text-gray-100">{{ mcp.alias }}</strong>
                        <p class="text-xs text-gray-500 dark:text-gray-400 font-mono">{{ mcp.address }}</p>
                    </div>
                    <div class="space-x-2">
                        <!-- Edit button can be added here in the future -->
                        <button @click="handleDeleteMcp(mcp)" class="text-red-500 hover:text-red-700" title="Delete MCP Server">Delete</button>
                    </div>
                </div>
            </div>
        </section>
    </div>
</template>