<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useDataStore } from '../../stores/data';
import { useUiStore } from '../../stores/ui';
import { useAuthStore } from '../../stores/auth';
import McpCard from '../ui/McpCard.vue';
import IconWrenchScrewdriver from '../../assets/icons/IconWrenchScrewdriver.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';

const dataStore = useDataStore();
const uiStore = useUiStore();
const authStore = useAuthStore();

const { userMcps, userApps } = storeToRefs(dataStore);
const { user } = storeToRefs(authStore);

const activeTab = ref('mcps');

const getInitialFormState = (type = 'mcps', ownerType = 'user') => ({
    name: '',
    url: '',
    icon: '',
    active: true,
    type: ownerType,
    authentication_type: 'none',
    authentication_key: ''
});

const form = ref(getInitialFormState());
const editingItem = ref(null);
const isLoading = ref(false);
const isReloading = ref(false);
const showKey = ref(false);
const fileInput = ref(null);
const formIconLoadFailed = ref(false);
const isFormVisible = ref(false);

onMounted(() => {
    dataStore.fetchMcps();
    dataStore.fetchApps();
});

watch(() => form.value.icon, () => {
    formIconLoadFailed.value = false;
});

const isEditMode = computed(() => editingItem.value !== null);

const sortedUserMcps = computed(() => userMcps.value.filter(m => m.type === 'user').sort((a, b) => a.name.localeCompare(b.name)));
const sortedSystemMcps = computed(() => userMcps.value.filter(m => m.type === 'system').sort((a, b) => a.name.localeCompare(b.name)));
const sortedUserApps = computed(() => userApps.value.filter(a => a.type === 'user').sort((a, b) => a.name.localeCompare(b.name)));
const sortedSystemApps = computed(() => userApps.value.filter(a => a.type === 'system').sort((a, b) => a.name.localeCompare(b.name)));

function showAddForm(type, ownerType = 'user') {
    if (isEditMode.value) {
        cancelEditing();
    }
    activeTab.value = type;
    form.value = getInitialFormState(type, ownerType);
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function startEditing(item, type) {
    activeTab.value = type;
    editingItem.value = { ...item, _type: type };
    form.value.name = item.name;
    form.value.url = item.url;
    form.value.icon = item.icon || '';
    form.value.active = typeof item.active === 'boolean' ? item.active : true;
    form.value.type = item.type || 'user';
    form.value.authentication_type = item.authentication_type || 'none';
    form.value.authentication_key = item.authentication_key || '';
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

async function handleReloadServers() {
    isReloading.value = true;
    try {
        await dataStore.triggerMcpReload();
    } finally {
        isReloading.value = false;
    }
}

async function handleFormSubmit() {
    if (!form.value.name || !form.value.url) {
        uiStore.addNotification('Name and URL are required.', 'warning');
        return;
    }
    isLoading.value = true;
    try {
        const payload = {
            name: form.value.name,
            url: form.value.url,
            icon: form.value.icon || null,
            active: form.value.active,
            type: form.value.type,
            authentication_type: form.value.authentication_type,
            authentication_key: form.value.authentication_key || "",
        };
        const isApp = activeTab.value === 'apps';
        if (isEditMode.value) {
            await (isApp ? dataStore.updateApp(editingItem.value.id, payload) : dataStore.updateMcp(editingItem.value.id, payload));
        } else {
            await (isApp ? dataStore.addApp(payload) : dataStore.addMcp(payload));
        }
        cancelEditing();
    } finally {
        isLoading.value = false;
    }
}

async function handleDeleteItem(item, type) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete '${item.name}'?`,
        message: `Are you sure you want to remove this ${type === 'mcps' ? 'MCP server' : 'Application'}? This cannot be undone.`,
        confirmText: 'Delete'
    });
    if (confirmed) {
        if (editingItem.value && editingItem.value.id === item.id) {
            cancelEditing();
        }
        await (type === 'apps' ? dataStore.deleteApp(item.id) : dataStore.deleteMcp(item.id));
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
    
    if (file.type === 'image/svg+xml') {
        const reader = new FileReader();
        reader.onload = (e) => { form.value.icon = e.target.result; };
        reader.onerror = () => { uiStore.addNotification('Failed to read the SVG file.', 'error'); };
        reader.readAsDataURL(file);
        event.target.value = '';
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
            const MAX_WIDTH = 128;
            const MAX_HEIGHT = 128;
            let width = img.width;
            let height = img.height;

            if (width > height) {
                if (width > MAX_WIDTH) {
                    height = Math.round(height * (MAX_WIDTH / width));
                    width = MAX_WIDTH;
                }
            } else {
                if (height > MAX_HEIGHT) {
                    width = Math.round(width * (MAX_HEIGHT / height));
                    height = MAX_HEIGHT;
                }
            }

            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, width, height);

            form.value.icon = canvas.toDataURL('image/png');
        };
        img.onerror = () => {
            uiStore.addNotification('Failed to load image for processing.', 'error');
        };
        img.src = e.target.result;
    };
    reader.onerror = () => {
        uiStore.addNotification('Failed to read the file.', 'error');
    };
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
                        {{ isEditMode ? 'Edit' : 'Add' }} {{ form.type }} {{ activeTab === 'mcps' ? 'MCP Server' : 'Application' }}
                    </h2>
                    <p class="mt-1 max-w-2xl text-sm text-gray-500 dark:text-gray-400">
                        {{ form.type === 'user' ? 'This is only available to you.' : 'This is available to all users.' }}
                    </p>
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
                                    <IconWrenchScrewdriver v-else class="w-8 h-8 text-gray-500 dark:text-gray-400" />
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
                                    <IconEyeOff v-if="showKey" class="w-5 h-5" />
                                    <IconEye v-else class="w-5 h-5" />
                                </button>
                            </div>
                        </fieldset>
                        
                        <div class="flex justify-end items-center gap-x-3 pt-2">
                            <button @click="cancelEditing" type="button" class="btn btn-secondary">Cancel</button>
                            <button type="submit" class="btn btn-primary" :disabled="isLoading">
                                {{ isLoading ? (isEditMode ? 'Saving...' : 'Adding...') : (isEditMode ? 'Save Changes' : `Add ${activeTab === 'mcps' ? 'MCP' : 'App'}`) }}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </transition>

        <!-- MCP Servers Section -->
        <section v-show="activeTab === 'mcps'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-4">
                <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Your Personal MCPs</h3>
                <div class="flex items-center gap-x-3">
                    <button @click="showAddForm('mcps', 'user')" class="btn btn-primary text-sm">+ Add Personal Server</button>
                    <button v-if="user.is_admin" @click="showAddForm('mcps', 'system')" class="btn btn-secondary text-sm">+ Add System Server</button>
                </div>
            </div>
            <div v-if="sortedUserMcps.length === 0" class="empty-state-card"><p>You haven't added any personal MCP servers yet.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <McpCard v-for="mcp in sortedUserMcps" :key="mcp.id" :mcp="mcp" is-editable @edit="startEditing(mcp, 'mcps')" @delete="handleDeleteItem(mcp, 'mcps')" />
            </div>
        </section>
        <section v-show="activeTab === 'mcps'">
            <div class="flex justify-between items-center my-4 flex-wrap gap-4">
                 <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">System MCPs</h3>
                 <button @click="handleReloadServers()" class="btn btn-secondary text-sm" :disabled="isReloading">{{ isReloading ? 'Reloading...' : 'Reload All Servers' }}</button>
            </div>
            <div v-if="sortedSystemMcps.length === 0" class="empty-state-card"><p>No system-wide MCP servers are available.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <McpCard v-for="mcp in sortedSystemMcps" :key="mcp.id" :mcp="mcp" :is-editable="user.is_admin" @edit="startEditing(mcp, 'mcps')" @delete="handleDeleteItem(mcp, 'mcps')" />
            </div>
        </section>

        <!-- Apps Section -->
        <section v-show="activeTab === 'apps'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-4">
                <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white">Your Personal Apps</h3>
                <div class="flex items-center gap-x-3">
                    <button @click="showAddForm('apps', 'user')" class="btn btn-primary text-sm">+ Add Personal App</button>
                    <button v-if="user.is_admin" @click="showAddForm('apps', 'system')" class="btn btn-secondary text-sm">+ Add System App</button>
                </div>
            </div>
            <div v-if="sortedUserApps.length === 0" class="empty-state-card"><p>You haven't added any personal Apps yet.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <McpCard v-for="app in sortedUserApps" :key="app.id" :mcp="app" is-editable @edit="startEditing(app, 'apps')" @delete="handleDeleteItem(app, 'apps')" />
            </div>
        </section>
        <section v-show="activeTab === 'apps'">
             <h3 class="text-xl font-bold leading-6 text-gray-900 dark:text-white my-4">System Apps</h3>
            <div v-if="sortedSystemApps.length === 0" class="empty-state-card"><p>No system-wide Apps are available.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <McpCard v-for="app in sortedSystemApps" :key="app.id" :mcp="app" :is-editable="user.is_admin" @edit="startEditing(app, 'apps')" @delete="handleDeleteItem(app, 'apps')" />
            </div>
        </section>
    </div>
</template>