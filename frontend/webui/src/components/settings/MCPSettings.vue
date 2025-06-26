<script setup>
import { ref, computed, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';

// --- Store Setup ---
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const { userMcps } = storeToRefs(dataStore);
const { user } = storeToRefs(authStore);

// --- Component State ---
const mcpForm = ref({
    name: '',
    url: ''
});
const editingMcp = ref(null); // If not null, we are in edit mode
const isLoading = ref(false);

onMounted(() => {
    dataStore.fetchMcps();
});

// --- Computed Properties ---
const isEditMode = computed(() => editingMcp.value !== null);
const isReloading = ref(false);

const sortedUserMcps = computed(() => {
    return userMcps.value
        .filter(mcp => mcp.owner_username === user.value?.username)
        .sort((a, b) => a.name.localeCompare(b.name));
});

const sortedSystemMcps = computed(() => {
    return userMcps.value
        .filter(mcp => mcp.owner_username === null)
        .sort((a, b) => a.name.localeCompare(b.name));
});

// --- Methods ---
function startEditing(mcp) {
    editingMcp.value = { ...mcp }; // Create a copy for editing
    mcpForm.value.name = mcp.name;
    mcpForm.value.url = mcp.url;
}

function cancelEditing() {
    editingMcp.value = null;
    mcpForm.value = { name: '', url: '' }; // Clear the form
}
async function handleReloadServers() {
    isReloading.value = true;
    try {
        await dataStore.triggerMcpReload();
    } catch (error) {
        // Error notification is handled globally
    } finally {
        isReloading.value = false;
    }
}

async function handleFormSubmit() {
    if (!mcpForm.value.name || !mcpForm.value.url) {
        uiStore.addNotification('Name and URL are required.', 'warning');
        return;
    }

    isLoading.value = true;
    try {
        if (isEditMode.value) {
            // Update existing MCP
            await dataStore.updateMcp(editingMcp.value.id, { name: mcpForm.value.name, url: mcpForm.value.url });
        } else {
            // Add new MCP
            await dataStore.addMcp(mcpForm.value);
        }
        cancelEditing(); // Reset form and mode on success
    } catch (error) {
        // Error notification is handled globally
    } finally {
        isLoading.value = false;
    }
}

async function handleDeleteMcp(mcp) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete '${mcp.name}'?`,
        message: `Are you sure you want to remove the MCP server at ${mcp.url}? This cannot be undone.`,
        confirmText: 'Delete'
    });
    if (confirmed) {
        // If we are currently editing the one we're deleting, cancel edit mode
        if (editingMcp.value && editingMcp.value.id === mcp.id) {
            cancelEditing();
        }
        await dataStore.deleteMcp(mcp.id);
    }
}
</script>

<template>
    <div class="space-y-8">
        <!-- Add/Edit MCP Server Section -->
        <section>
            <h4 class="text-lg font-semibold mb-4 border-b dark:border-gray-600 pb-2">
                {{ isEditMode ? 'Edit Personal MCP Server' : 'Add Personal MCP Server' }}
            </h4>
            <form @submit.prevent="handleFormSubmit" class="space-y-4 max-w-xl">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <label for="mcpName" class="block text-sm font-medium">Name</label>
                        <input type="text" id="mcpName" v-model="mcpForm.name" class="input-field mt-1" placeholder="e.g., My Local Server" required>
                    </div>
                    <div>
                        <label for="mcpUrl" class="block text-sm font-medium">URL</label>
                        <input type="url" id="mcpUrl" v-model="mcpForm.url" class="input-field mt-1" placeholder="http://127.0.0.1:9602" required>
                    </div>
                </div>
                <div class="text-right flex justify-end items-center space-x-2">
                    <button v-if="isEditMode" @click="cancelEditing" type="button" class="btn btn-secondary">
                        Cancel
                    </button>
                    <button type="submit" class="btn btn-primary" :disabled="isLoading">
                        <span v-if="isLoading">{{ isEditMode ? 'Saving...' : 'Adding...' }}</span>
                        <span v-else>{{ isEditMode ? 'Save Changes' : 'Add MCP Server' }}</span>
                    </button>
                </div>
            </form>
            <button @click="handleReloadServers()" class="btn btn-primary" :disabled="isReloading">
                <span v-if="isReloading">Reloading...</span>
                <span v-else>Reload</span>
            </button>
        </section>

        <!-- Manage Your MCP Servers Section -->
        <section>
            <h4 class="text-lg font-semibold mb-2">Your MCP Servers</h4>
            <div class="max-h-60 overflow-y-auto border dark:border-gray-600 rounded p-2 space-y-1">
                <p v-if="sortedUserMcps.length === 0" class="italic text-sm text-gray-500 p-2">
                    No personal MCP servers configured.
                </p>
                <div v-for="mcp in sortedUserMcps" :key="mcp.id" class="flex justify-between items-center py-1.5 px-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-sm">
                    <div>
                        <strong class="font-medium text-gray-800 dark:text-gray-100">{{ mcp.name }}</strong>
                        <p class="text-xs text-gray-500 dark:text-gray-400 font-mono">{{ mcp.url }}</p>
                    </div>
                    <div class="space-x-4 flex-shrink-0">
                        <button @click="startEditing(mcp)" class="font-medium text-blue-500 hover:text-blue-700" title="Edit MCP Server">Edit</button>
                        <button @click="handleDeleteMcp(mcp)" class="font-medium text-red-500 hover:text-red-700" title="Delete MCP Server">Delete</button>
                    </div>
                </div>
            </div>
        </section>
        
        <!-- System MCP Servers Section -->
        <section>
            <h4 class="text-lg font-semibold mb-2">System MCP Servers</h4>
            <div class="max-h-60 overflow-y-auto border dark:border-gray-600 rounded p-2 space-y-1">
                <p v-if="sortedSystemMcps.length === 0" class="italic text-sm text-gray-500 p-2">
                    No system-wide MCP servers available.
                </p>
                <div v-for="mcp in sortedSystemMcps" :key="mcp.id" class="flex justify-between items-center py-1.5 px-2 text-sm">
                    <div>
                        <strong class="font-medium text-gray-800 dark:text-gray-100">{{ mcp.name }}</strong>
                        <p class="text-xs text-gray-500 dark:text-gray-400 font-mono">{{ mcp.url }}</p>
                    </div>
                </div>
            </div>
        </section>
    </div>
</template>
