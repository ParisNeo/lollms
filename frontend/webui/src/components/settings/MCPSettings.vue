<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import McpCard from '../ui/McpCard.vue';

// --- Store Setup ---
const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();
const { userMcps } = storeToRefs(dataStore);
const { user } = storeToRefs(authStore);

// --- Component State ---
const getInitialFormState = () => ({
    name: '',
    url: '',
    icon: '',
    authentication_token: ''
});

const mcpForm = ref(getInitialFormState());
const editingMcp = ref(null);
const isLoading = ref(false);
const isReloading = ref(false);
const showToken = ref(false);
const fileInput = ref(null);
const formIconLoadFailed = ref(false);

// --- NEW: State to control form visibility ---
const isFormVisible = ref(false);

onMounted(() => {
    dataStore.fetchMcps();
});

watch(() => mcpForm.value.icon, () => {
    formIconLoadFailed.value = false;
});

// --- Computed Properties ---
const isEditMode = computed(() => editingMcp.value !== null);

const sortedUserMcps = computed(() => {
    if (!user.value) return [];
    return userMcps.value
        .filter(mcp => mcp.owner_username === user.value.username)
        .sort((a, b) => a.name.localeCompare(b.name));
});

const sortedSystemMcps = computed(() => {
    return userMcps.value
        .filter(mcp => mcp.owner_username === null)
        .sort((a, b) => a.name.localeCompare(b.name));
});

// --- Methods ---

// --- NEW: Function to show the form for adding a new MCP ---
function showAddForm() {
    // Ensure we are not in edit mode and the form is reset
    if(isEditMode.value) {
      cancelEditing();
    }
    mcpForm.value = getInitialFormState();
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- UPDATED: startEditing now also shows the form ---
function startEditing(mcp) {
    editingMcp.value = { ...mcp };
    mcpForm.value.name = mcp.name;
    mcpForm.value.url = mcp.url;
    mcpForm.value.icon = mcp.icon || '';
    mcpForm.value.authentication_token = mcp.authentication_token || '';
    isFormVisible.value = true; // Show the form
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- UPDATED: cancelEditing now also hides the form ---
function cancelEditing() {
    editingMcp.value = null;
    mcpForm.value = getInitialFormState();
    showToken.value = false;
    isFormVisible.value = false; // Hide the form
}

function handleFormIconError() {
    formIconLoadFailed.value = true;
}

async function handleReloadServers() {
    isReloading.value = true;
    try {
        await dataStore.triggerMcpReload();
    } catch (error) {
        // Handled globally
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
        const payload = {
            name: mcpForm.value.name,
            url: mcpForm.value.url,
            icon: mcpForm.value.icon || null,
            authentication_token: mcpForm.value.authentication_token || null,
        };
        if (isEditMode.value) {
            await dataStore.updateMcp(editingMcp.value.id, payload);
        } else {
            await dataStore.addMcp(payload);
        }
        cancelEditing(); // This will now reset the form AND hide it
    } catch (error) {
        // Handled globally
    } finally {
        isLoading.value = false;
    }
}

async function handleDeleteMcp(mcp) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete '${mcp.name}'?`,
        message: 'Are you sure you want to remove this MCP server? This cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        // If the form for the deleted item is open, close it.
        if (editingMcp.value && editingMcp.value.id === mcp.id) {
            cancelEditing();
        }
        await dataStore.deleteMcp(mcp.id);
    }
}

function triggerFileInput() {
    fileInput.value.click();
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'];
    if (!allowedTypes.includes(file.type)) {
        uiStore.addNotification('Invalid file type. Please select an image.', 'error');
        return;
    }
    if (file.size > 1 * 1024 * 1024) {
        uiStore.addNotification('File is too large. Maximum size is 1MB.', 'error');
        return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
        mcpForm.value.icon = e.target.result;
    };
    reader.onerror = () => {
        uiStore.addNotification('Failed to read the file.', 'error');
    };
    reader.readAsDataURL(file);
    event.target.value = '';
}
</script>

<style scoped>
/* Simple fade and slide-down transition for the form */
.form-fade-enter-active,
.form-fade-leave-active {
    transition: opacity 0.3s ease, transform 0.3s ease;
}
.form-fade-enter-from,
.form-fade-leave-to {
    opacity: 0;
    transform: translateY(-20px);
}
</style>

<template>
    <div class="space-y-10">
        <!-- Add/Edit MCP Server Section - NOW CONDITIONAL -->
        <transition name="form-fade">
            <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
                <div class="px-4 py-5 sm:p-6">
                    <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">
                        {{ isEditMode ? 'Edit Personal MCP Server' : 'Add Personal MCP Server' }}
                    </h2>
                    <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">
                        {{ isEditMode ? 'Update the details for your existing MCP server.' : 'Add a new server to access more models and services.' }}
                    </p>
                </div>
                <div class="border-t border-gray-200 dark:border-gray-700">
                    <form @submit.prevent="handleFormSubmit" class="p-4 sm:p-6 space-y-6">
                        <!-- Form content remains the same... -->
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
                            <div>
                                <label for="mcpName" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Name</label>
                                <input type="text" id="mcpName" v-model="mcpForm.name" class="input-field mt-1" placeholder="My Local Server" required>
                            </div>
                            <div>
                                <label for="mcpUrl" class="block text-sm font-medium text-gray-700 dark:text-gray-300">URL</label>
                                <input type="url" id="mcpUrl" v-model="mcpForm.url" class="input-field mt-1" placeholder="http://127.0.0.1:9602" required>
                            </div>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Icon (Optional)</label>
                            <div class="mt-2 flex items-center gap-x-4">
                                <div class="h-16 w-16 rounded-md bg-gray-200 dark:bg-gray-700 flex items-center justify-center overflow-hidden">
                                    <img v-if="mcpForm.icon && !formIconLoadFailed" :src="mcpForm.icon" @error="handleFormIconError" alt="Icon Preview" class="h-full w-full object-cover">
                                    <svg v-else-if="isEditMode" class="w-8 h-8 text-gray-500 dark:text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M21.75 17.25v-.228a4.5 4.5 0 0 0-.12-1.03l-2.268-9.64a3.375 3.375 0 0 0-3.285-2.602H7.923a3.375 3.375 0 0 0-3.285 2.602l-2.268 9.64a4.5 4.5 0 0 0-.12 1.03v.228m19.5 0a3 3 0 0 1-3 3H5.25a3 3 0 0 1-3-3m19.5 0a3 3 0 0 0-3-3H5.25a3 3 0 0 0-3 3m16.5 0h.008v.008h-.008v-.008Z" /></svg>
                                </div>
                                <div class="flex-grow space-y-2">
                                    <input type="text" v-model="mcpForm.icon" class="input-field" placeholder="Paste image URL or upload a file">
                                    <div class="flex items-center gap-x-3">
                                        <button @click="triggerFileInput" type="button" class="btn btn-secondary text-sm">Upload File</button>
                                        <button v-if="mcpForm.icon" @click="mcpForm.icon = ''" type="button" class="text-sm font-medium text-red-600 hover:text-red-500">Remove</button>
                                    </div>
                                </div>
                            </div>
                            <input type="file" ref="fileInput" @change="handleFileSelect" class="hidden" accept="image/png, image/jpeg, image/gif, image/webp, image/svg+xml">
                        </div>
                        <div>
                            <label for="mcpToken" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Authentication Token (Optional)</label>
                            <div class="mt-1 relative">
                                <input :type="showToken ? 'text' : 'password'" id="mcpToken" v-model="mcpForm.authentication_token" class="input-field pr-10" placeholder="Paste token here">
                                <button type="button" @click="showToken = !showToken" class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                                    <svg v-if="!showToken" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                                    <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.243 4.243L6.228 6.228" /></svg>
                                </button>
                            </div>
                        </div>
                        <div class="flex justify-end items-center gap-x-3 pt-2">
                            <button @click="cancelEditing" type="button" class="btn btn-secondary">Cancel</button>
                            <button type="submit" class="btn btn-primary" :disabled="isLoading">
                                {{ isLoading ? (isEditMode ? 'Saving...' : 'Adding...') : (isEditMode ? 'Save Changes' : 'Add MCP Server') }}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </transition>

        <!-- Your MCP Servers Section -->
        <section>
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Your MCP Servers</h3>
                <!-- UPDATED: Button group for actions -->
                <div class="flex items-center gap-x-3">
                    <button @click="showAddForm()" class="btn btn-primary text-sm">
                        + Add Server
                    </button>
                    <button @click="handleReloadServers()" class="btn btn-secondary text-sm" :disabled="isReloading">
                        {{ isReloading ? 'Reloading...' : 'Reload Servers' }}
                    </button>
                </div>
            </div>
            <div v-if="sortedUserMcps.length === 0" class="text-center py-10 px-4 rounded-lg bg-gray-50 dark:bg-gray-800/50">
                <p class="text-gray-500 dark:text-gray-400">You haven't added any personal MCP servers yet.</p>
                <p class="text-sm text-gray-400 dark:text-gray-500 mt-1">Use the "Add Server" button to get started.</p>
            </div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <McpCard v-for="mcp in sortedUserMcps" 
                         :key="mcp.id" 
                         :mcp="mcp" 
                         is-editable
                         @edit="startEditing"
                         @delete="handleDeleteMcp" />
            </div>
        </section>

        <!-- System MCP Servers Section -->
        <section>
            <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white mb-4">System MCP Servers</h3>
            <div v-if="sortedSystemMcps.length === 0" class="text-center py-10 px-4 rounded-lg bg-gray-50 dark:bg-gray-800/50">
                 <p class="text-gray-500 dark:text-gray-400">No system-wide MCP servers are available.</p>
            </div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <McpCard v-for="mcp in sortedSystemMcps" 
                         :key="mcp.id" 
                         :mcp="mcp" />
            </div>
        </section>
    </div>
</template>