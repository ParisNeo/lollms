<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import { useDataStore } from '../../stores/data';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import IconArrowUpCircle from '../../assets/icons/IconArrowUpCircle.vue';
import IconCog from '../../assets/icons/IconCog.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconArrowUp from '../../assets/icons/IconArrowUp.vue';
import IconArrowDown from '../../assets/icons/IconArrowDown.vue';
import IconEye from '../../assets/icons/IconEye.vue';
import IconEyeOff from '../../assets/icons/IconEyeOff.vue';
import IconWrenchScrewdriver from '../../assets/icons/IconWrenchScrewdriver.vue';
import TaskProgressIndicator from '../ui/TaskProgressIndicator.vue';
import AppCard from '../ui/AppCard.vue';
import AppCardSkeleton from '../ui/AppCardSkeleton.vue';
import McpCard from '../ui/McpCard.vue';

const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const { 
    zooRepositories, isLoadingZooRepositories, zooApps, isLoadingZooApps, 
    mcpZooRepositories, isLoadingMcpZooRepositories, zooMcps, isLoadingZooMcps,
    installedApps, isLoadingInstalledApps, mcps, apps
} = storeToRefs(adminStore);

const { tasks } = storeToRefs(tasksStore);

const mainTab = ref('apps');
const activeSubTab = ref('repositories');

// --- Form State ---
const isFormVisible = ref(false);
const editingItem = ref(null);
const isLoading = ref(false);
const showKey = ref(false);
const fileInput = ref(null);
const formIconLoadFailed = ref(false);
const getInitialFormState = (type = 'apps', ownerType = 'system') => ({
    name: '', client_id: '', url: '', icon: '', active: true, type: ownerType,
    authentication_type: 'none', authentication_key: '',
    sso_redirect_uri: '', sso_user_infos_to_share: [],
});
const form = ref(getInitialFormState());
const ssoInfoOptions = [
    { id: 'email', label: 'Email Address' }, { id: 'first_name', label: 'First Name' },
    { id: 'family_name', label: 'Family Name' }, { id: 'birth_date', label: 'Birth Date' },
];
const isReloading = ref(false);

// --- Repositories & Available Items State ---
const newRepo = ref({ name: '', url: '' });
const isAddRepoFormVisible = ref(false);
const isLoadingAction = ref(null);
const searchQuery = ref('');
const selectedCategory = ref('All');
const installationStatusFilter = ref('All');
const isPullingAll = ref(false);
const sortKey = ref('last_update_date');
const sortOrder = ref('desc');
const starredItems = ref(JSON.parse(localStorage.getItem('starredItems') || '[]'));

const sortOptions = [
    { value: 'last_update_date', label: 'Last Updated' }, { value: 'creation_date', label: 'Creation Date' },
    { value: 'name', label: 'Name' }, { value: 'author', label: 'Author' },
];

onMounted(() => {
    adminStore.fetchZooRepositories();
    adminStore.fetchMcpZooRepositories();
    adminStore.fetchZooApps();
    adminStore.fetchZooMcps();
    adminStore.fetchInstalledApps();
    adminStore.fetchApps();
    adminStore.fetchMcps();
});

watch(mainTab, () => { if(activeSubTab.value!=='installed_apps' && activeSubTab.value!=='registered') activeSubTab.value = 'repositories'; });
watch(activeSubTab, (newTab) => {
    if (newTab === 'available_items') {
        if (mainTab.value === 'apps') adminStore.fetchZooApps(); else adminStore.fetchZooMcps();
        adminStore.fetchInstalledApps();
    } else if (newTab === 'installed_apps') {
        adminStore.fetchInstalledApps();
    } else if (newTab === 'registered') {
        adminStore.fetchApps();
        adminStore.fetchMcps();
    }
});
watch(starredItems, (newStarred) => { localStorage.setItem('starredItems', JSON.stringify(newStarred)); }, { deep: true });
watch(() => form.value.icon, () => { formIconLoadFailed.value = false; });

const currentRepositories = computed(() => mainTab.value === 'apps' ? zooRepositories.value : mcpZooRepositories.value);
const isLoadingCurrentRepositories = computed(() => mainTab.value === 'apps' ? isLoadingZooRepositories.value : isLoadingMcpZooRepositories.value);
const currentZooItems = computed(() => mainTab.value === 'apps' ? zooApps.value : zooMcps.value);
const isLoadingCurrentZooItems = computed(() => mainTab.value === 'apps' ? isLoadingZooApps.value : isLoadingZooMcps.value);

const itemsWithTaskStatus = computed(() => {
    if (!Array.isArray(currentZooItems.value)) return [];
    const taskMap = new Map();
    const taskPrefix = 'Installing app: ';
    if (Array.isArray(tasks.value)) {
        tasks.value.forEach(task => {
            if (task?.name?.startsWith(taskPrefix)) {
                const itemName = task.name.replace(taskPrefix, '');
                if (!taskMap.has(itemName) || new Date(task.created_at) > new Date(taskMap.get(itemName).created_at)) {
                    taskMap.set(itemName, task);
                }
            }
        });
    }
    return currentZooItems.value.map(item => ({ ...item, task: taskMap.get(item.folder_name) || null }));
});

const sortedRepositories = computed(() => Array.isArray(currentRepositories.value) ? [...currentRepositories.value].sort((a, b) => (a.name || '').localeCompare(b.name || '')) : []);
const categories = computed(() => {
    if (!Array.isArray(currentZooItems.value)) return ['All'];
    const allCats = new Set(currentZooItems.value.map(item => item.category || 'Uncategorized'));
    return ['All', ...Array.from(allCats).sort()];
});

const filteredAndSortedItems = computed(() => {
    let items = itemsWithTaskStatus.value.filter(item => {
        const matchesStatus = installationStatusFilter.value === 'All' || (installationStatusFilter.value === 'Installed' && item.is_installed) || (installationStatusFilter.value === 'Uninstalled' && !item.is_installed && !item.task);
        const matchesCategory = selectedCategory.value === 'All' || item.category === selectedCategory.value;
        const matchesSearch = !searchQuery.value || item.name.toLowerCase().includes(searchQuery.value.toLowerCase()) || (item.description && item.description.toLowerCase().includes(searchQuery.value.toLowerCase())) || (item.author && item.author.toLowerCase().includes(searchQuery.value.toLowerCase()));
        return matchesStatus && matchesCategory && matchesSearch;
    });
    items.sort((a, b) => {
        const isAStarred = starredItems.value.includes(a.name);
        const isBStarred = starredItems.value.includes(b.name);
        if (isAStarred && !isBStarred) return -1;
        if (!isAStarred && isBStarred) return 1;
        if (a.is_installed && !b.is_installed) return -1;
        if (!a.is_installed && b.is_installed) return 1;
        let valA = a[sortKey.value] || '';
        let valB = b[sortKey.value] || '';
        if (sortKey.value.includes('date')) {
            valA = valA ? new Date(valA).getTime() : 0;
            valB = valB ? new Date(valB).getTime() : 0;
        }
        if (typeof valA === 'string' && typeof valB === 'string') return sortOrder.value === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
        return sortOrder.value === 'asc' ? valA - valB : valB - valA;
    });
    return items;
});

const groupedItems = computed(() => {
    if (sortKey.value !== 'author') return null;
    return filteredAndSortedItems.value.reduce((acc, item) => {
        const author = item.author || 'Unknown Author';
        if (!acc[author]) acc[author] = [];
        acc[author].push(item);
        return acc;
    }, {});
});

const installedItemsWithTaskStatus = computed(() => {
    const sorted = Array.isArray(installedApps.value) ? [...installedApps.value].sort((a, b) => (a.name || '').localeCompare(b.name || '')) : [];
    const taskMap = new Map();
    if (Array.isArray(tasks.value)) {
        tasks.value.forEach(task => {
            if (!task?.name) return;
            let appName = '';
            if (task.name.startsWith('Start app: ')) appName = task.name.replace('Start app: ', '');
            else if (task.name.startsWith('Stop app: ')) appName = task.name.replace('Stop app: ', '');
            else if (task.name.startsWith('Installing app: ')) appName = task.name.replace('Installing app: ', '');
            if (appName && (task.status === 'running' || task.status === 'pending')) {
                if (!taskMap.has(appName) || new Date(task.created_at) > new Date(taskMap.get(appName).created_at)) {
                    taskMap.set(appName, task);
                }
            }
        });
    }
    return sorted.map(app => ({ ...app, task: taskMap.get(app.folder_name) || null }));
});

const registeredUserApps = computed(() => apps.value.filter(a => !a.is_installed && a.type === 'user').sort((a, b) => a.name.localeCompare(b.name)));
const registeredSystemApps = computed(() => apps.value.filter(a => !a.is_installed && a.type === 'system').sort((a, b) => a.name.localeCompare(b.name)));
const registeredUserMcps = computed(() => mcps.value.filter(m => !m.is_installed && m.type === 'user').sort((a, b) => a.name.localeCompare(b.name)));
const registeredSystemMcps = computed(() => mcps.value.filter(m => !m.is_installed && m.type === 'system').sort((a, b) => a.name.localeCompare(b.name)));

const isEditMode = computed(() => editingItem.value !== null);
const isSsoAuth = computed(() => form.value.authentication_type === 'lollms_sso');

function handleStarToggle(itemName) {
    const index = starredItems.value.indexOf(itemName);
    if (index > -1) starredItems.value.splice(index, 1);
    else starredItems.value.push(itemName);
}

function formatDateTime(isoString) {
    if (!isoString) return 'Never';
    return new Date(isoString).toLocaleString();
}

async function handleAddRepository() {
    if (!newRepo.value.name || !newRepo.value.url) {
        uiStore.addNotification('Repository name and URL are required.', 'warning');
        return;
    }
    isLoadingAction.value = 'add';
    try {
        if (mainTab.value === 'apps') {
            await adminStore.addZooRepository(newRepo.value.name, newRepo.value.url);
        } else {
            await adminStore.addMcpZooRepository(newRepo.value.name, newRepo.value.url);
        }
        newRepo.value = { name: '', url: '' };
        isAddRepoFormVisible.value = false;
    } finally {
        isLoadingAction.value = null;
    }
}

async function handlePullRepository(repo) {
    isLoadingAction.value = repo.id;
    try {
        if (mainTab.value === 'apps') {
            await adminStore.pullZooRepository(repo.id);
        } else {
            await adminStore.pullMcpZooRepository(repo.id);
        }
    } finally {
        isLoadingAction.value = null;
    }
}

async function handlePullAll() {
    isPullingAll.value = true;
    try {
        if (mainTab.value === 'apps') await adminStore.pullAllZooRepositories();
        else await adminStore.pullAllMcpZooRepositories();
    } finally {
        isPullingAll.value = false;
    }
}

async function handleDeleteRepository(repo) {
    const confirmed = await uiStore.showConfirmation({ title: `Delete Repository '${repo.name}'?`, message: 'This will remove the repository and its cached files. This action cannot be undone.', confirmText: 'Delete' });
    if (confirmed) {
        isLoadingAction.value = repo.id;
        try {
            if (mainTab.value === 'apps') await adminStore.deleteZooRepository(repo.id);
            else await adminStore.deleteMcpZooRepository(repo.id);
        } finally {
            isLoadingAction.value = null;
        }
    }
}

function handleInstallItem(item) { 
    const installData = { app: item, type: mainTab.value };
    uiStore.openModal('appInstall', installData); 
}

function handleUpdateApp(app) {
    const zooItemDetails = currentZooItems.value.find(zooItem => zooItem.name === app.name);
    if (!zooItemDetails) {
        uiStore.addNotification(`Could not find details for '${app.name}' in the zoo. Try refreshing repositories.`, 'error');
        return;
    }
    uiStore.showConfirmation({ title: `Update '${app.name}'?`, message: 'This will reinstall it with the latest version. It will be stopped. Are you sure?', confirmText: 'Update' })
        .then(confirmed => { if (confirmed) handleInstallItem(zooItemDetails); });
}

async function handleAppAction(appId, action) {
    isLoadingAction.value = `${action}-${appId}`;
    try {
        if (action === 'start') await adminStore.startApp(appId);
        if (action === 'stop') await adminStore.stopApp(appId);
    } finally {
        isLoadingAction.value = null;
    }
}

async function handleUninstallApp(app) {
    const confirmed = await uiStore.showConfirmation({ title: `Uninstall '${app.name}'?`, message: 'This will permanently delete all files. This cannot be undone.', confirmText: 'Uninstall' });
    if (confirmed) {
        isLoadingAction.value = `uninstall-${app.id}`;
        try { await adminStore.uninstallApp(app.id); } finally { isLoadingAction.value = null; }
    }
}

function showItemDetails(item) { uiStore.openModal('appDetails', { app: item }); }
function handleConfigureApp(app) { uiStore.openModal('appConfig', { app }); }
async function handleShowLogs(app) {
    const logContent = await adminStore.fetchAppLog(app.id);
    uiStore.openModal('sourceViewer', { title: `Logs: ${app.name}`, content: logContent || 'No log content found.', language: 'log' });
}
async function showItemHelp(item) {
    const readmeContent = mainTab.value === 'apps' 
        ? await adminStore.fetchAppReadme(item.repository, item.folder_name)
        : await adminStore.fetchMcpReadme(item.repository, item.folder_name);
    uiStore.openModal('sourceViewer', { title: `README: ${item.name}`, content: readmeContent, language: 'markdown' });
}
async function handleCancelTask(taskId) { await tasksStore.cancelTask(taskId); }
function viewTask(taskId) { uiStore.openModal('tasksManager', { initialTaskId: taskId }); }

// --- Registered Services Form Logic ---
function showAddRegisteredForm(type) {
    if (isEditMode.value) cancelEditing();
    form.value = getInitialFormState(type, 'system');
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}
function startEditing(item, type) {
    editingItem.value = { ...item, _type: type };
    form.value.name = item.name;
    form.value.url = item.url;
    form.value.icon = item.icon || '';
    form.value.active = typeof item.active === 'boolean' ? item.active : true;
    form.value.type = item.type;
    form.value.authentication_type = item.authentication_type || 'none';
    form.value.authentication_key = '';
    form.value.sso_redirect_uri = item.sso_redirect_uri || '';
    form.value.sso_user_infos_to_share = item.sso_user_infos_to_share || [];
    isFormVisible.value = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}
function cancelEditing() {
    editingItem.value = null;
    isFormVisible.value = false;
    showKey.value = false;
}
function handleFormIconError() { formIconLoadFailed.value = true; }
async function handleFormSubmit() {
    if (!form.value.name || !form.value.url) { uiStore.addNotification('Name and URL are required.', 'warning'); return; }
    isLoading.value = true;
    try {
        const payload = { ...form.value };
        const isApp = isEditMode.value ? editingItem.value._type === 'apps' : mainTab.value === 'apps';
        
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
    const confirmed = await uiStore.showConfirmation({ title: `Delete '${item.name}'?`, message: `This will permanently remove this registered ${type === 'mcps' ? 'MCP server' : 'Application'}. This cannot be undone.`, confirmText: 'Delete' });
    if (confirmed) {
        if (editingItem.value && editingItem.value.id === item.id) cancelEditing();
        await (type === 'apps' ? adminStore.deleteApp(item.id) : adminStore.deleteMcp(item.id));
    }
}
function triggerFileInput() { fileInput.value.click(); }
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'];
    if (!allowedTypes.includes(file.type)) { uiStore.addNotification('Invalid file type. Please select an image.', 'error'); return; }
    if (file.type === 'image/svg+xml') {
        const reader = new FileReader();
        reader.onload = (e) => { form.value.icon = e.target.result; };
        reader.readAsDataURL(file);
    } else {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                const MAX_WIDTH = 128, MAX_HEIGHT = 128;
                let { width, height } = img;
                if (width > height) { if (width > MAX_WIDTH) { height *= MAX_WIDTH / width; width = MAX_WIDTH; } }
                else { if (height > MAX_HEIGHT) { width *= MAX_HEIGHT / height; height = MAX_HEIGHT; } }
                const canvas = document.createElement('canvas');
                canvas.width = width; canvas.height = height;
                canvas.getContext('2d').drawImage(img, 0, 0, width, height);
                form.value.icon = canvas.toDataURL('image/png');
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    }
    event.target.value = '';
}
async function handleReloadMcps() {
    isReloading.value = true;
    try {
        await dataStore.triggerMcpReload();
    } finally {
        isReloading.value = false;
    }
}
</script>

<style scoped>
.tab-button { @apply px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors; }
.tab-button.active { @apply border-blue-500 text-blue-600 dark:text-blue-400; }
.tab-button.inactive { @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600; }
.form-fade-enter-active, .form-fade-leave-active { transition: all 0.3s ease-in-out; max-height: 1000px; opacity: 1; overflow: hidden; }
.form-fade-enter-from, .form-fade-leave-to { max-height: 0; opacity: 0; transform: translateY(-20px); margin-top: 0; margin-bottom: 0; padding-top: 0; padding-bottom: 0; border-width: 0; }
.empty-state-card { @apply text-center py-10 px-4 rounded-lg bg-gray-50 dark:bg-gray-800/50 text-gray-500 dark:text-gray-400; }
</style>

<template>
    <div class="space-y-8">
        <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Apps, MCPs & Services</h2>
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">Manage all LOLLMS extensions: Install from Zoos or register external services.</p>
        </div>

        <div class="border-b border-gray-200 dark:border-gray-700">
            <nav class="-mb-px flex space-x-6" aria-label="Main Tabs">
                <button @click="mainTab = 'apps'" class="tab-button" :class="mainTab === 'apps' ? 'active' : 'inactive'">Apps</button>
                <button @click="mainTab = 'mcps'" class="tab-button" :class="mainTab === 'mcps' ? 'active' : 'inactive'">MCPs</button>
            </nav>
        </div>
        
        <div class="border-b border-gray-200 dark:border-gray-700">
            <nav class="-mb-px flex space-x-6" aria-label="Sub Tabs">
                <button @click="activeSubTab = 'repositories'" class="tab-button" :class="activeSubTab === 'repositories' ? 'active' : 'inactive'">Repositories</button>
                <button @click="activeSubTab = 'available_items'" class="tab-button" :class="activeSubTab === 'available_items' ? 'active' : 'inactive'">Available</button>
                <button @click="activeSubTab = 'installed_apps'" class="tab-button" :class="activeSubTab === 'installed_apps' ? 'active' : 'inactive'">Installed</button>
                <button @click="activeSubTab = 'registered'" class="tab-button" :class="activeSubTab === 'registered' ? 'active' : 'inactive'">Registered</button>
            </nav>
        </div>
        
        <transition name="form-fade">
            <div v-if="isFormVisible && activeSubTab === 'registered'" class="bg-white dark:bg-gray-800 shadow-md rounded-lg mb-8">
                <div class="px-4 py-5 sm:p-6"><h2 class="text-xl font-bold capitalize">{{ isEditMode ? 'Edit' : 'Add' }} Registered {{ mainTab === 'apps' ? 'App' : 'MCP' }}</h2></div>
                <div class="border-t border-gray-200 dark:border-gray-700">
                    <form @submit.prevent="handleFormSubmit" class="p-4 sm:p-6 space-y-6">
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
                            <div><label for="formName" class="label">Name</label><input type="text" id="formName" v-model="form.name" class="input-field mt-1" required></div>
                            <div><label for="formUrl" class="label">URL</label><input type="url" id="formUrl" v-model="form.url" class="input-field mt-1" required></div>
                        </div>
                        <div>
                            <label class="label">Icon (Optional)</label>
                            <div class="mt-2 flex items-center gap-x-4">
                                <div class="h-16 w-16 rounded-md bg-gray-200 dark:bg-gray-700 flex items-center justify-center overflow-hidden">
                                    <img v-if="form.icon && !formIconLoadFailed" :src="form.icon" @error="handleFormIconError" alt="Icon Preview" class="h-full w-full object-cover">
                                    <IconWrenchScrewdriver v-else class="w-8 h-8 text-gray-500 dark:text-gray-400" />
                                </div>
                                <div class="flex-grow space-y-2"><input type="text" v-model="form.icon" class="input-field" placeholder="Paste image URL or upload"><div class="flex items-center gap-x-3"><button @click="triggerFileInput" type="button" class="btn btn-secondary text-sm">Upload</button><button v-if="form.icon" @click="form.icon = ''" type="button" class="text-sm font-medium text-red-600 hover:text-red-500">Remove</button></div></div>
                            </div>
                            <input type="file" ref="fileInput" @change="handleFileSelect" class="hidden" accept="image/*">
                        </div>
                        <div class="flex items-center justify-between bg-gray-50 dark:bg-gray-700/50 p-3 rounded-md">
                            <span class="flex-grow flex flex-col"><span class="text-sm font-medium">Active</span><span class="text-sm text-gray-500">Inactive items cannot be used.</span></span>
                            <button @click="form.active = !form.active" type="button" :class="[form.active ? 'bg-blue-600' : 'bg-gray-200 dark:bg-gray-600', 'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors']"><span :class="[form.active ? 'translate-x-5' : 'translate-x-0', 'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition']"></span></button>
                        </div>
                        <fieldset class="space-y-4">
                            <legend class="label">Authentication</legend>
                            <select id="formAuthType" v-model="form.authentication_type" class="input-field"><option value="none">None</option><option value="lollms_sso">LoLLMs SSO</option><option value="bearer">Bearer Token</option></select>
                            <div v-if="form.authentication_type === 'bearer'" class="relative"><label for="formKey" class="sr-only">Auth Key</label><input :type="showKey ? 'text' : 'password'" id="formKey" v-model="form.authentication_key" class="input-field pr-10" placeholder="Paste Bearer token"><button type="button" @click="showKey = !showKey" class="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"><IconEyeOff v-if="showKey" class="w-5 h-5" /><IconEye v-else class="w-5 h-5" /></button></div>
                        </fieldset>
                        <div v-if="isSsoAuth" class="p-4 space-y-4 border rounded-md dark:border-gray-600">
                            <h4 class="font-medium">SSO Configuration</h4>
                            <div><label for="ssoClientId" class="label">Client ID</label><input type="text" id="ssoClientId" v-model="form.client_id" class="input-field mt-1" :class="{ 'bg-gray-100 dark:bg-gray-700': isEditMode && editingItem.client_id }" :readonly="isEditMode && editingItem.client_id" placeholder="Optional, will be generated"><p class="mt-1 text-xs text-gray-500">Unique ID. Cannot be changed after creation.</p></div>
                            <div><label for="ssoRedirectUri" class="label">Redirect URI</label><input type="url" id="ssoRedirectUri" v-model="form.sso_redirect_uri" class="input-field mt-1" required><p class="mt-1 text-xs text-gray-500">URL to redirect to after authentication.</p></div>
                            <div><label class="label">User Info to Share</label><div class="mt-2 space-y-2"><div v-for="option in ssoInfoOptions" :key="option.id" class="flex items-center"><input :id="`sso-info-${option.id}`" type="checkbox" :value="option.id" v-model="form.sso_user_infos_to_share" class="h-4 w-4 rounded border-gray-300 text-blue-600"><label :for="`sso-info-${option.id}`" class="ml-2 text-sm">{{ option.label }}</label></div></div></div>
                        </div>
                        <div class="flex justify-end gap-3"><button type="button" @click="cancelEditing" class="btn btn-secondary">Cancel</button><button type="submit" class="btn btn-primary" :disabled="isLoading">{{ isLoading ? 'Saving...' : 'Save' }}</button></div>
                    </form>
                </div>
            </div>
        </transition>

        <section v-if="activeSubTab === 'repositories'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
                <h3 class="text-xl font-semibold">{{ mainTab === 'apps' ? 'App' : 'MCP' }} Zoo Repositories</h3>
                <div class="flex items-center gap-2">
                    <button @click="handlePullAll" class="btn btn-secondary" :disabled="isPullingAll"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isPullingAll}" /><span class="ml-2">Pull All</span></button>
                    <button @click="isAddRepoFormVisible = !isAddRepoFormVisible" class="btn btn-primary">{{ isAddRepoFormVisible ? 'Cancel' : 'Add Repository' }}</button>
                </div>
            </div>
            <transition name="form-fade">
                <div v-if="isAddRepoFormVisible" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm mb-6 overflow-hidden">
                    <form @submit.prevent="handleAddRepository" class="space-y-4">
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div><label for="repo-name" class="block text-sm font-medium">Name</label><input id="repo-name" v-model="newRepo.name" type="text" class="input-field mt-1" placeholder="e.g., Official Zoo" required></div>
                            <div class="md:col-span-2"><label for="repo-url" class="block text-sm font-medium">Git URL</label><input id="repo-url" v-model="newRepo.url" type="url" class="input-field mt-1" placeholder="https://github.com/ParisNeo/lollms_apps_zoo.git" required></div>
                        </div>
                        <div class="flex justify-end"><button type="submit" class="btn btn-primary" :disabled="isLoadingAction === 'add'">{{ isLoadingAction === 'add' ? 'Adding...' : 'Add Repository' }}</button></div>
                    </form>
                </div>
            </transition>
            <div v-if="isLoadingCurrentRepositories" class="text-center p-4">Loading repositories...</div>
            <div v-else-if="!sortedRepositories || sortedRepositories.length === 0" class="empty-state-card"><p>No {{ mainTab }} Zoo repositories added.</p></div>
            <div v-else class="space-y-4">
                <div v-for="repo in sortedRepositories" :key="repo.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div class="flex-grow truncate"><p class="font-semibold">{{ repo.name }}</p><p class="text-sm text-gray-500 font-mono truncate">{{ repo.url }}</p><p class="text-xs text-gray-400 mt-1">Last updated: {{ formatDateTime(repo.last_pulled_at) }}</p></div>
                    <div class="flex items-center gap-x-2 flex-shrink-0"><button @click="handlePullRepository(repo)" class="btn btn-secondary btn-sm" :disabled="isLoadingAction === repo.id"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingAction === repo.id}" /><span class="ml-1">Pull</span></button><button v-if="repo.is_deletable" @click="handleDeleteRepository(repo)" class="btn btn-danger btn-sm" :disabled="isLoadingAction === repo.id"><IconTrash class="w-4 h-4" /></button></div>
                </div>
            </div>
        </section>

        <section v-if="activeSubTab === 'available_items'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2"><h3 class="text-xl font-semibold">Available {{ mainTab === 'apps' ? 'Apps' : 'MCPs' }}</h3><button @click="mainTab === 'apps' ? adminStore.fetchZooApps() : adminStore.fetchZooMcps()" class="btn btn-secondary" :disabled="isLoadingCurrentZooItems"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingCurrentZooItems}" /><span class="ml-2">Rescan</span></button></div>
            <div class="space-y-4">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-4"><div class="relative lg:col-span-1"><input type="text" v-model="searchQuery" :placeholder="`Search ${mainTab}...`" class="input-field w-full pl-10" /><div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"><svg class="h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg></div></div><div class="grid grid-cols-2 lg:col-span-2 gap-4"><select v-model="installationStatusFilter" class="input-field"><option value="All">All Statuses</option><option value="Installed">Installed</option><option value="Uninstalled">Uninstalled</option></select><select v-model="selectedCategory" class="input-field"><option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option></select></div></div>
                <div class="flex items-center gap-2"><select v-model="sortKey" class="input-field w-48"><option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">Sort by {{ opt.label }}</option></select><button @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'" class="btn btn-secondary p-2"><IconArrowUp v-if="sortOrder === 'asc'" class="w-5 h-5" /><IconArrowDown v-else class="w-5 h-5" /></button></div>
                <div v-if="isLoadingCurrentZooItems" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6"><AppCardSkeleton v-for="i in 8" :key="i" /></div>
                <div v-else-if="!currentZooItems || currentZooItems.length === 0" class="empty-state-card"><h4 class="font-semibold">No Items Found</h4><p class="text-sm">Add and pull a repository to see available {{ mainTab }}.</p></div>
                <div v-else-if="filteredAndSortedItems.length === 0" class="empty-state-card"><h4 class="font-semibold">No Matching Items</h4><p class="text-sm">Try adjusting your search or filter.</p></div>
                <div v-else><div v-if="groupedItems" class="space-y-8"><div v-for="(authorItems, author) in groupedItems" :key="author"><h3 class="text-lg font-semibold mb-3 border-b pb-2">{{ author }}</h3><div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6"><AppCard v-for="item in authorItems" :key="`${item.repository}/${item.folder_name}`" :app="item" :task="item.task" :is-starred="starredItems.includes(item.name)" @star="handleStarToggle(item.name)" @install="handleInstallItem(item)" @details="showItemDetails(item)" @help="showItemHelp(item)" @view-task="viewTask" @cancel-install="handleCancelTask" /></div></div></div><div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6"><AppCard v-for="item in filteredAndSortedItems" :key="`${item.repository}/${item.folder_name}`" :app="item" :task="item.task" :is-starred="starredItems.includes(item.name)" @star="handleStarToggle(item.name)" @install="handleInstallItem(item)" @update="handleUpdateApp(item)" @details="showItemDetails(item)" @help="showItemHelp(item)" @view-task="viewTask" @cancel-install="handleCancelTask" /></div></div>
            </div>
        </section>
        
        <section v-if="activeSubTab === 'installed_apps'">
             <div class="flex justify-between items-center mb-4"><h3 class="text-xl font-semibold">Installed Items</h3><button @click="adminStore.fetchInstalledApps" class="btn btn-secondary" :disabled="isLoadingInstalledApps"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingInstalledApps}" /><span class="ml-2">Refresh</span></button></div>
            <div v-if="isLoadingInstalledApps" class="text-center p-10">Loading...</div>
            <div v-else-if="!installedItemsWithTaskStatus || installedItemsWithTaskStatus.length === 0" class="empty-state-card"><h4 class="font-semibold">No Items Installed</h4><p class="text-sm">Go to "Available" to install an item.</p></div>
            <div v-else class="space-y-4">
                <div v-for="app in installedItemsWithTaskStatus" :key="app.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div class="flex items-center gap-4 flex-grow truncate"><img v-if="app.icon" :src="app.icon" class="h-10 w-10 rounded-md flex-shrink-0 object-cover" alt="Icon"><div class="flex-grow truncate"><div class="flex items-center gap-2"><p class="font-semibold truncate">{{ app.name }}</p><span class="text-xs font-semibold px-2 py-0.5 rounded-full" :class="app.item_type === 'mcp' ? 'bg-cyan-100 text-cyan-800' : 'bg-indigo-100 text-indigo-800'">{{ app.item_type === 'mcp' ? 'MCP' : 'App' }}</span></div><p class="text-xs text-gray-500 font-mono truncate">Port: {{ app.port }}</p></div></div>
                    <div class="flex items-center gap-x-2 flex-shrink-0 flex-wrap justify-end">
                        <TaskProgressIndicator v-if="app.task" :task="app.task" @view="viewTask" @cancel="handleCancelTask"/>
                        <template v-else>
                            <button v-if="app.update_available" @click="handleUpdateApp(app)" class="btn btn-warning btn-sm p-2" title="Update"><IconArrowUpCircle class="w-5 h-5" /></button>
                            <span class="px-2 py-1 text-xs font-semibold rounded-full" :class="{ 'bg-green-100 text-green-800': app.status === 'running', 'bg-gray-100 text-gray-800': app.status === 'stopped', 'bg-red-100 text-red-800': app.status === 'error' }">{{ app.status }}</span>
                            <a v-if="app.status === 'running' && app.url" :href="app.url" target="_blank" class="btn btn-secondary btn-sm p-2" title="Open"><IconGlobeAlt class="w-5 h-5" /></a>
                            <button v-if="app.has_config_schema" @click="handleConfigureApp(app)" class="btn btn-secondary btn-sm p-2" title="Configure"><IconCog class="w-5 h-5" /></button>
                            <button @click="handleShowLogs(app)" class="btn btn-secondary btn-sm p-2" title="Logs"><IconCode class="w-5 h-5" /></button>
                            <button v-if="app.status !== 'running'" @click="handleAppAction(app.id, 'start')" class="btn btn-success btn-sm p-2" :disabled="isLoadingAction === `start-${app.id}`" title="Start"><IconPlayCircle class="w-5 h-5" /></button>
                            <button v-if="app.status === 'running' || (app.status === 'error' && app.pid)" @click="handleAppAction(app.id, 'stop')" class="btn btn-warning btn-sm p-2" :disabled="isLoadingAction === `stop-${app.id}`" title="Stop"><IconStopCircle class="w-5 h-5" /></button>
                            <button @click="handleUninstallApp(app)" class="btn btn-danger btn-sm p-2" title="Uninstall"><IconTrash class="w-5 h-5" /></button>
                        </template>
                    </div>
                </div>
            </div>
        </section>

        <section v-if="activeSubTab === 'registered'">
            <div v-if="mainTab === 'apps'" class="space-y-8">
                <div class="flex justify-between items-center mb-4"><h3 class="text-xl font-semibold">Registered System Apps</h3><button @click="showAddRegisteredForm('apps')" class="btn btn-primary text-sm">+ Add System App</button></div>
                <div v-if="registeredSystemApps.length === 0" class="empty-state-card"><p>No system-wide Apps are registered.</p></div>
                <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"><McpCard v-for="app in registeredSystemApps" :key="app.id" :mcp="app" is-editable @edit="startEditing(app, 'apps')" @delete="handleDeleteItem(app, 'apps')" /></div>
            </div>
             <div v-if="mainTab === 'mcps'" class="space-y-8">
                <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
                    <h3 class="text-xl font-semibold">Registered System MCPs</h3>
                    <div class="flex items-center gap-2">
                        <button @click="handleReloadMcps" class="btn btn-secondary text-sm" :disabled="isReloading">
                             <IconRefresh class="w-4 h-4" :class="{'animate-spin': isReloading}" />
                            <span class="ml-2">{{ isReloading ? 'Reloading...' : 'Reload MCPs' }}</span>
                        </button>
                        <button @click="showAddRegisteredForm('mcps')" class="btn btn-primary text-sm">+ Add System MCP</button>
                    </div>
                </div>
                <div v-if="registeredSystemMcps.length === 0" class="empty-state-card"><p>No system-wide MCPs are registered.</p></div>
                <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5"><McpCard v-for="mcp in registeredSystemMcps" :key="mcp.id" :mcp="mcp" is-editable @edit="startEditing(mcp, 'mcps')" @delete="handleDeleteItem(mcp, 'mcps')" /></div>
            </div>
        </section>
    </div>
</template>