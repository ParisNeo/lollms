<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import McpCard from '../ui/McpCard.vue';

const adminStore = useAdminStore();
const uiStore = useUiStore();

const { mcps, apps, isLoadingServices } = storeToRefs(adminStore);

const activeTab = ref('mcps');

const getInitialFormState = (type = 'mcps') => ({
    name: '',
    url: '',
    icon: '',
    active: true,
    type: 'system', // Admin form defaults to creating 'system' items
    authentication_type: 'none',
    authentication_key: ''
});

const form = ref(getInitialFormState());
const editingItem = ref(null);
const isLoading = ref(false);
const showKey = ref(false);
const fileInput = ref(null);
const formIconLoadFailed = ref(false);
const isFormVisible = ref(false);

onMounted(() => {
    adminStore.fetchMcps();
    adminStore.fetchApps();
});

watch(() => form.value.icon, () => {
    formIconLoadFailed.value = false;
});

const isEditMode = computed(() => editingItem.value !== null);

const sortedSystemMcps = computed(() => mcps.value.filter(m => m.type === 'system').sort((a, b) => a.name.localeCompare(b.name)));
const sortedUserMcps = computed(() => mcps.value.filter(m => m.type === 'user').sort((a, b) => a.name.localeCompare(b.name)));
const sortedSystemApps = computed(() => apps.value.filter(a => a.type === 'system').sort((a, b) => a.name.localeCompare(b.name)));
const sortedUserApps = computed(() => apps.value.filter(a => a.type === 'user').sort((a, b) => a.name.localeCompare(b.name)));

function showAddForm(type) {
    if (isEditMode.value) {
        cancelEditing();
    }
    activeTab.value = type;
    form.value = getInitialFormState(type);
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function startEditing(item, type) {
    activeTab.value = type;
    editingItem.value = { ...item, _type: type }; // Use a temporary property to track type
    form.value.name = item.name;
    form.value.url = item.url;
    form.value.icon = item.icon || '';
    form.value.active = typeof item.active === 'boolean' ? item.active : true;
    form.value.type = item.type; // Preserve the original type
    form.value.authentication_type = item.authentication_type || 'none';
    form.value.authentication_key = ''; // Never pre-fill the key
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function cancelEditing() {
    editingItem.value = null;
    form.value = getInitialFormState(activeTab.value);
    showKey.value = false;
    isFormVisible.value = false;
}

function handleFormIconError() {
    formIconLoadFailed.value = true;
}

async function handleFormSubmit() {
    if (!form.value.name || !form.value.url) {
        uiStore.addNotification('Name and URL are required.', 'warning');
        return;
    }
    isLoading.value = true;
    try {
        const payload = { ...form.value };
        const isApp = activeTab.value === 'apps';
        
        if (isEditMode.value) {
            await (isApp ? adminStore.updateApp(editingItem.value.id, payload) : adminStore.updateMcp(editingItem.value.id, payload));
        } else {
            await (isApp ? adminStore.addApp(payload) : adminStore.addMcp(payload));
        }
        cancelEditing();
    } finally {
        isLoading.value = false;
    }
}

async function handleDeleteItem(item, type) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete '${item.name}'?`,
        message: `This will permanently remove this ${type === 'mcps' ? 'MCP server' : 'Application'} for all users. This cannot be undone.`,
        confirmText: 'Delete'
    });
    if (confirmed) {
        if (editingItem.value && editingItem.value.id === item.id) {
            cancelEditing();
        }
        await (type === 'apps' ? adminStore.deleteApp(item.id) : adminStore.deleteMcp(item.id));
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
    if (file.size > 1 * 1024 * 1024) { // 1MB limit
        uiStore.addNotification('File is too large. Maximum size is 1MB.', 'error');
        return;
    }
    const reader = new FileReader();
    reader.onload = (e) => { form.value.icon = e.target.result; };
    reader.onerror = () => { uiStore.addNotification('Failed to read the file.', 'error'); };
    reader.readAsDataURL(file);
    event.target.value = '';
}
</script>

<style scoped>
.form-fade-enter-active,
.form-fade-leave-active {
    transition: opacity 0.3s ease, transform 0.3s ease;
}
.form-fade-enter-from,
.form-fade-leave-to {
    opacity: 0;
    transform: translateY(-20px);
}
.tab-button {
    @apply px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors;
}
.tab-button.active {
    @apply border-blue-500 text-blue-600 dark:text-blue-400;
}
.tab-button.inactive {
    @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600;
}
.empty-state-card {
    @apply text-center py-10 px-4 rounded-lg bg-gray-50 dark:bg-gray-800/50 text-gray-500 dark:text-gray-400;
}
</style>

<template>
    <div class="space-y-10">
        <!-- TABS for MCPs and Apps -->
        <div class="border-b border-gray-200 dark:border-gray-700">
            <nav class="-mb-px flex space-x-6" aria-label="Tabs">
                <button @click="activeTab = 'mcps'" class="tab-button" :class="activeTab === 'mcps' ? 'active' : 'inactive'">
                    MCP Servers
                </button>
                <button @click="activeTab = 'apps'" class="tab-button" :class="activeTab === 'apps' ? 'active' : 'inactive'">
                    Applications
                </button>
            </nav>
        </div>

        <!-- Add/Edit Form Section -->
        <transition name="form-fade">
            <div v-if="isFormVisible" class="bg-white dark:bg-gray-800 shadow-md rounded-lg">
                <div class="px-4 py-5 sm:p-6">
                    <h2 class="text-xl font-bold leading-6 text-gray-900 dark:text-white capitalize">
                        {{ isEditMode ? 'Edit' : 'Add New' }} {{ activeTab === 'mcps' ? 'MCP Server' : 'Application' }}
                    </h2>
                </div>
                <div class="border-t border-gray-200 dark:border-gray-700">
                     <form @submit.prevent="handleFormSubmit" class="p-4 sm:p-6 space-y-6">
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
                            <div>
                                <label for="formName" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Name</label>
                                <input type="text" id="formName" v-model="form.name" class="input-field mt-1" :placeholder="activeTab === 'mcps' ? 'My Local Server' : 'My Web App'" required>
                            </div>
                            <div>
                                <label for="formUrl" class="block text-sm font-medium text-gray-700 dark:text-gray-300">URL</label>
                                <input type="url" id="formUrl" v-model="form.url" class="input-field mt-1" :placeholder="activeTab === 'mcps' ? 'http://127.0.0.1:9602' : 'https://example.com'" required>
                            </div>
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">Icon (Optional)</label>
                            <div class="mt-2 flex items-center gap-x-4">
                                <div class="h-16 w-16 rounded-md bg-gray-200 dark:bg-gray-700 flex items-center justify-center overflow-hidden">
                                    <img v-if="form.icon && !formIconLoadFailed" :src="form.icon" @error="handleFormIconError" alt="Icon Preview" class="h-full w-full object-cover">
                                    <svg v-else class="w-8 h-8 text-gray-500 dark:text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M21.75 17.25v-.228a4.5 4.5 0 0 0-.12-1.03l-2.268-9.64a3.375 3.375 0 0 0-3.285-2.602H7.923a3.375 3.375 0 0 0-3.285 2.602l-2.268 9.64a4.5 4.5 0 0 0-.12 1.03v.228m19.5 0a3 3 0 0 1-3 3H5.25a3 3 0 0 1-3-3m19.5 0a3 3 0 0 0-3-3H5.25a3 3 0 0 0-3 3m16.5 0h.008v.008h-.008v-.008Z" /></svg>
                                </div>
                                <div class="flex-grow space-y-2">
                                    <input type="text" v-model="form.icon" class="input-field" placeholder="Paste image URL or upload a file">
                                    <div class="flex items-center gap-x-3">
                                        <button @click="triggerFileInput" type="button" class="btn btn-secondary text-sm">Upload File</button>
                                        <button v-if="form.icon" @click="form.icon = ''" type="button" class="text-sm font-medium text-red-600 hover:text-red-500">Remove</button>
                                    </div>
                                </div>
                            </div>
                            <input type="file" ref="fileInput" @change="handleFileSelect" class="hidden" accept="image/png, image/jpeg, image/gif, image/webp, image/svg+xml">
                        </div>

                        <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                            <span class="flex-grow flex flex-col">
                                <span class="text-sm font-medium text-gray-900 dark:text-gray-100">Active</span>
                                <span class="text-sm text-gray-500 dark:text-gray-400">Inactive items cannot be used.</span>
                            </span>
                            <button @click="form.active = !form.active" type="button" :class="[form.active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-gray-800']">
                                <span :class="[form.active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out']"></span>
                            </button>
                        </div>
                        
                        <fieldset class="space-y-4">
                            <legend class="text-sm font-medium text-gray-700 dark:text-gray-300">Authentication</legend>
                            <select id="formAuthType" v-model="form.authentication_type" class="input-field">
                                <option value="none">None</option>
                                <option value="lollms_chat_auth">LoLLMs Chat Auth</option>
                                <option value="bearer">Bearer Token</option>
                            </select>
                             <p v-if="form.authentication_type === 'lollms_chat_auth'" class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                A temporary token will be generated by LoLLMs for each session.
                            </p>
                            <div v-if="form.authentication_type === 'bearer'" class="relative">
                                <label for="formKey" class="sr-only">Authentication Key</label>
                                <input :type="showKey ? 'text' : 'password'" id="formKey" v-model="form.authentication_key" class="input-field pr-10" placeholder="Paste your Bearer token here">
                                <button type="button" @click="showKey = !showKey" class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                                    <svg v-if="!showKey" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
                                    <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-5 h-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.243 4.243L6.228 6.228" /></svg>
                                </button>
                            </div>
                        </fieldset>
                        
                        <div class="flex justify-end items-center gap-x-3 pt-2">
                            <button @click="cancelEditing" type="button" class="btn btn-secondary">Cancel</button>
                            <button type="submit" class="btn btn-primary" :disabled="isLoading">
                                {{ isLoading ? (isEditMode ? 'Saving...' : 'Adding...') : (isEditMode ? 'Save Changes' : `Add`) }}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </transition>

        <!-- MCP Servers Section -->
        <section v-show="activeTab === 'mcps'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-4">
                <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">System MCPs</h3>
                <div class="flex items-center gap-x-3">
                    <button @click="showAddForm('mcps')" class="btn btn-primary text-sm">+ Add System Server</button>
                </div>
            </div>
            <div v-if="sortedSystemMcps.length === 0" class="empty-state-card"><p>No system-wide MCP servers are defined.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <McpCard v-for="mcp in sortedSystemMcps" :key="mcp.id" :mcp="mcp" is-editable @edit="startEditing(mcp, 'mcps')" @delete="handleDeleteItem(mcp, 'mcps')" />
            </div>
            <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white mt-8 mb-4">User-defined MCPs</h3>
            <div v-if="sortedUserMcps.length === 0" class="empty-state-card"><p>No users have added personal MCP servers yet.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <McpCard v-for="mcp in sortedUserMcps" :key="mcp.id" :mcp="mcp" is-editable @edit="startEditing(mcp, 'mcps')" @delete="handleDeleteItem(mcp, 'mcps')" />
            </div>
        </section>

        <!-- Apps Section -->
        <section v-show="activeTab === 'apps'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-4">
                <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">System Apps</h3>
                 <div class="flex items-center gap-x-3">
                    <button @click="showAddForm('apps')" class="btn btn-primary text-sm">+ Add System App</button>
                </div>
            </div>
            <div v-if="sortedSystemApps.length === 0" class="empty-state-card"><p>No system-wide Apps are available.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <McpCard v-for="app in sortedSystemApps" :key="app.id" :mcp="app" is-editable @edit="startEditing(app, 'apps')" @delete="handleDeleteItem(app, 'apps')" />
            </div>
             <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white mt-8 mb-4">User-defined Apps</h3>
            <div v-if="sortedUserApps.length === 0" class="empty-state-card"><p>No users have added personal Apps yet.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <McpCard v-for="app in sortedUserApps" :key="app.id" :mcp="app" is-editable @edit="startEditing(app, 'apps')" @delete="handleDeleteItem(app, 'apps')" />
            </div>
        </section>
    </div>
</template>