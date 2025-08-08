<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconArrowUpCircle from '../../assets/icons/IconArrowUpCircle.vue';
import IconCog from '../../assets/icons/IconCog.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconArrowUp from '../../assets/icons/IconArrowUp.vue';
import IconArrowDown from '../../assets/icons/IconArrowDown.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import AppCard from '../ui/AppCard.vue';
import AppCardSkeleton from '../ui/AppCardSkeleton.vue';
import IconAnimateSpin from '../../assets/icons/IconAnimateSpin.vue';
import IconTicket from '../../assets/icons/IconTicket.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';

const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();

const { 
    zooRepositories, isLoadingZooRepositories, zooApps, isLoadingZooApps, 
    installedApps, isLoadingInstalledApps
} = storeToRefs(adminStore);
const { tasks } = storeToRefs(tasksStore);

const activeSubTab = ref('repositories');

const newRepo = ref({ type: 'git', name: '', url: '', path: '' });
const isAddRepoFormVisible = ref(false);
const isLoadingAction = ref(null);
const searchQuery = ref('');
const selectedCategory = ref('All');
const installationStatusFilter = ref('All');
const isPullingAll = ref(false);
const sortKey = ref('last_update_date');
const sortOrder = ref('desc');
const starredItems = ref(JSON.parse(localStorage.getItem('starredItems') || '[]'));
const currentPage = ref(1);
const pageSize = ref(24);
let debounceTimer = null;

const sortOptions = [
    { value: 'last_update_date', label: 'Last Updated' }, { value: 'creation_date', label: 'Creation Date' },
    { value: 'name', label: 'Name' }, { value: 'author', label: 'Author' },
];

const totalItems = computed(() => zooApps.value.total || 0);
const totalPages = computed(() => zooApps.value.pages || 1);
const pageInfo = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value + 1;
    const end = Math.min(currentPage.value * pageSize.value, totalItems.value);
    return `Showing ${start}-${end} of ${totalItems.value}`;
});

const repoAppCounts = computed(() => {
    if (!zooApps.value.items) return {};
    return zooApps.value.items.reduce((acc, app) => {
        acc[app.repository] = (acc[app.repository] || 0) + 1;
        return acc;
    }, {});
});

async function fetchZooItems() {
    if (selectedCategory.value === 'Starred') {
        // Client-side filtering for starred items
        return;
    }
    const params = {
        page: currentPage.value, page_size: pageSize.value, sort_by: sortKey.value,
        sort_order: sortOrder.value, category: selectedCategory.value !== 'All' ? selectedCategory.value : undefined,
        search_query: searchQuery.value || undefined, installation_status: installationStatusFilter.value !== 'All' ? installationStatusFilter.value : undefined,
    };
    await adminStore.fetchZooApps(params);
}

function debouncedFetch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        currentPage.value = 1;
        fetchZooItems();
    }, 300);
}

watch(() => newRepo.value.type, (newType) => {
    if (newType === 'git') newRepo.value.path = '';
    else newRepo.value.url = '';
});

watch([activeSubTab, sortKey, sortOrder, selectedCategory, installationStatusFilter], () => {
    currentPage.value = 1;
    if (activeSubTab.value === 'available_items') fetchZooItems();
});
watch(searchQuery, debouncedFetch);
watch(currentPage, fetchZooItems);
watch(starredItems, (newStarred) => { localStorage.setItem('starredItems', JSON.stringify(newStarred)); }, { deep: true });

onMounted(() => {
    adminStore.fetchZooRepositories();
    adminStore.fetchInstalledApps();
    fetchZooItems();
});

const itemsWithTaskStatus = computed(() => {
    if (!Array.isArray(zooApps.value.items)) return [];
    let items = zooApps.value.items;
    
    // Client-side filter for starred items
    if (selectedCategory.value === 'Starred') {
        items = items.filter(item => starredItems.value.includes(item.name));
    }

    const taskMap = new Map();
    const taskPrefixes = ['Installing app: ', 'Updating app: '];
    tasks.value.forEach(task => {
        if (task?.name) {
            for (const prefix of taskPrefixes) {
                if (task.name.startsWith(prefix) && (task.status === 'running' || task.status === 'pending')) {
                    const itemName = task.name.replace(prefix, '');
                    if (!taskMap.has(itemName) || new Date(task.created_at) > new Date(taskMap.get(itemName).created_at)) {
                        taskMap.set(itemName, task);
                    }
                    break; 
                }
            }
        }
    });
    return items.map(item => ({ ...item, task: taskMap.get(item.name) || taskMap.get(item.folder_name) || null }));
});

const sortedRepositories = computed(() => Array.isArray(zooRepositories.value) ? [...zooRepositories.value].sort((a, b) => (a.name || '').localeCompare(b.name || '')) : []);
const categories = computed(() => {
    return zooApps.value.categories || ['All', 'Starred'];
});

const installedItemsWithTaskStatus = computed(() => {
    const filtered = installedApps.value.filter(app => (app.item_type || 'app') === 'app');
    const sorted = [...filtered].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    
    const taskMap = new Map();
    tasks.value.forEach(task => {
        if (!task?.name) return;
        let appName = '';
        let activityType = null;
        if (task.name.startsWith('Start app: ')) {
            appName = task.name.replace('Start app: ', '');
            activityType = 'starting';
        }
        else if (task.name.startsWith('Stop app: ')) {
            appName = task.name.replace('Stop app: ', '');
            activityType = 'stopping';
        }
        else if (task.name.startsWith('Updating app: ')) {
            appName = task.name.replace('Updating app: ', '');
            activityType = 'updating';
        }
        
        if (appName && (task.status === 'running' || task.status === 'pending')) {
            if (!taskMap.has(appName) || new Date(task.created_at) > new Date(taskMap.get(appName).created_at)) {
                taskMap.set(appName, { task, activityType }); // Store both task and activity type
            }
        }
    });
    return sorted.map(app => {
        const taskInfo = taskMap.get(app.name);
        return { 
            ...app, 
            task: taskInfo ? taskInfo.task : null,
            activity_status: taskInfo ? taskInfo.activityType : null // Add activity status
        }
    });
});

function handleStarToggle(itemName) {
    const index = starredItems.value.indexOf(itemName);
    if (index > -1) starredItems.value.splice(index, 1);
    else starredItems.value.push(itemName);
}

function formatDateTime(isoString) { if (!isoString) return 'Never'; return new Date(isoString).toLocaleString(); }

async function handleAddRepository() {
    if (!newRepo.value.name) {
        uiStore.addNotification('Repository name is required.', 'warning');
        return;
    }
    const payload = { name: newRepo.value.name };
    if (newRepo.value.type === 'git') {
        if (!newRepo.value.url) {
            uiStore.addNotification('Git URL is required.', 'warning');
            return;
        }
        payload.url = newRepo.value.url;
    } else {
        if (!newRepo.value.path) {
            uiStore.addNotification('Local Folder Path is required.', 'warning');
            return;
        }
        payload.path = newRepo.value.path;
    }

    isLoadingAction.value = 'add';
    try {
        await adminStore.addZooRepository(payload);
        newRepo.value = { type: 'git', name: '', url: '', path: '' };
        isAddRepoFormVisible.value = false;
    } finally {
        isLoadingAction.value = null;
    }
}

async function handlePullRepository(repo) {
    isLoadingAction.value = repo.id;
    try { await adminStore.pullZooRepository(repo.id); } 
    finally { isLoadingAction.value = null; }
}

async function handlePullAll() {
    isPullingAll.value = true;
    try { await adminStore.pullAllZooRepositories(); } 
    finally { isPullingAll.value = false; }
}

async function handleDeleteRepository(repo) {
    const confirmed = await uiStore.showConfirmation({ title: `Delete Repository '${repo.name}'?`, message: 'This will remove the repository record. For Git repos, it also deletes cached files. This action cannot be undone.', confirmText: 'Delete' });
    if (confirmed) {
        isLoadingAction.value = repo.id;
        try { await adminStore.deleteZooRepository(repo.id); } 
        finally { isLoadingAction.value = null; }
    }
}

function handleInstallItem(item) { uiStore.openModal('appInstall', { app: item, type: 'apps' }); }

async function handleUpdateApp(app) {
    const confirmed = await uiStore.showConfirmation({ 
        title: `Update '${app.name}'?`, 
        message: 'This will update the app to the latest version while preserving your configuration. The app will be stopped during the update.',
        confirmText: 'Update'
    });
    if (confirmed) {
        await adminStore.updateApp(app.id);
    }
}

async function handleAppAction(appId, action) {
    isLoadingAction.value = `${action}-${appId}`;
    try {
        if (action === 'start') await adminStore.startApp(appId);
        if (action === 'stop') await adminStore.stopApp(appId);
    } finally { isLoadingAction.value = null; }
}

async function handleUninstallApp(app) {
    const confirmed = await uiStore.showConfirmation({ title: `Uninstall '${app.name}'?`, message: 'This will permanently delete all files. This cannot be undone.', confirmText: 'Uninstall' });
    if (confirmed) {
        isLoadingAction.value = `uninstall-${app.id}`;
        try { await adminStore.uninstallApp(app.id); } finally { isLoadingAction.value = null; }
    }
}

function showItemDetails(item) {
    uiStore.openModal('sourceViewer', {
        title: `Details: ${item.name}`,
        content: item.description || 'No description available.',
        language: 'text'
    });
}
function handleConfigureApp(app) { uiStore.openModal('appConfig', { app }); }
function handleEditRegistration(app) { uiStore.openModal('serviceRegistration', { item: app, itemType: 'app', isInstalled: true }); }
async function handleShowLogs(app) {
    const logContent = await adminStore.fetchAppLog(app.id);
    uiStore.openModal('sourceViewer', { title: `Logs: ${app.name}`, content: logContent || 'No log content found.', language: 'log' });
}
async function showItemHelp(item) {
    const readmeContent = await adminStore.fetchAppReadme(item.repository, item.folder_name);
    uiStore.openModal('sourceViewer', { title: `README: ${item.name}`, content: readmeContent, language: 'markdown' });
}
async function handleCancelTask(taskId) { await tasksStore.cancelTask(taskId); }
function viewTask(taskId) { uiStore.openModal('tasksManager', { initialTaskId: taskId }); }
</script>
<style scoped>
.tab-button { @apply px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors; }
.tab-button.active { @apply border-blue-500 text-blue-600 dark:text-blue-400; }
.tab-button.inactive { @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600; }
.form-fade-enter-active, .form-fade-leave-active { transition: all 0.3s ease-in-out; }
.form-fade-enter-from, .form-fade-leave-to { opacity: 0; transform: translateY(-10px); }
.empty-state-card { @apply text-center py-10 px-4 rounded-lg bg-gray-50 dark:bg-gray-800/50 text-gray-500 dark:text-gray-400; }
</style>

<template>
    <div class="space-y-6">
        <div class="border-b border-gray-200 dark:border-gray-700">
            <nav class="-mb-px flex space-x-6" aria-label="Sub Tabs">
                <button @click="activeSubTab = 'repositories'" class="tab-button" :class="activeSubTab === 'repositories' ? 'active' : 'inactive'">Repositories</button>
                <button @click="activeSubTab = 'available_items'" class="tab-button" :class="activeSubTab === 'available_items' ? 'active' : 'inactive'">Available</button>
                <button @click="activeSubTab = 'installed_apps'" class="tab-button" :class="activeSubTab === 'installed_apps' ? 'active' : 'inactive'">Installed</button>
            </nav>
        </div>

        <section v-if="activeSubTab === 'repositories'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
                <h3 class="text-xl font-semibold">App Zoo Repositories</h3>
                <div class="flex items-center gap-2">
                    <button @click="handlePullAll" class="btn btn-secondary" :disabled="isPullingAll"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isPullingAll}" /><span class="ml-2">Pull All</span></button>
                    <button @click="isAddRepoFormVisible = !isAddRepoFormVisible" class="btn btn-primary">{{ isAddRepoFormVisible ? 'Cancel' : 'Add Repository' }}</button>
                </div>
            </div>
            <transition name="form-fade">
                <div v-if="isAddRepoFormVisible" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm mb-6 overflow-hidden">
                    <form @submit.prevent="handleAddRepository" class="space-y-4">
                        <div class="flex items-center gap-x-4 border-b pb-4 dark:border-gray-700">
                            <label class="flex items-center gap-x-2 cursor-pointer text-sm font-medium"><input type="radio" v-model="newRepo.type" value="git" class="radio-input"> Git Repository</label>
                            <label class="flex items-center gap-x-2 cursor-pointer text-sm font-medium"><input type="radio" v-model="newRepo.type" value="local" class="radio-input"> Local Folder</label>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div><label for="repo-name-app" class="block text-sm font-medium mb-1">Name</label><input id="repo-name-app" v-model="newRepo.name" type="text" class="input-field" placeholder="e.g., Official Zoo" required></div>
                            <div class="md:col-span-2" v-if="newRepo.type === 'git'"><label for="repo-url-app" class="block text-sm font-medium mb-1">Git URL</label><input id="repo-url-app" v-model="newRepo.url" type="url" class="input-field" placeholder="https://github.com/ParisNeo/lollms_apps_zoo.git" :required="newRepo.type === 'git'"></div>
                            <div class="md:col-span-2" v-if="newRepo.type === 'local'"><label for="repo-path-app" class="block text-sm font-medium mb-1">Full Folder Path</label><input id="repo-path-app" v-model="newRepo.path" type="text" class="input-field" placeholder="e.g., C:\Users\YourUser\Documents\my-lollms-apps" :required="newRepo.type === 'local'"></div>
                        </div>
                        <div class="flex justify-end"><button type="submit" class="btn btn-primary" :disabled="isLoadingAction === 'add'">{{ isLoadingAction === 'add' ? 'Adding...' : 'Add Repository' }}</button></div>
                    </form>
                </div>
            </transition>
            <div v-if="isLoadingZooRepositories" class="text-center p-4">Loading repositories...</div>
            <div v-else-if="!sortedRepositories || sortedRepositories.length === 0" class="empty-state-card"><p>No App Zoo repositories added.</p></div>
            <div v-else class="space-y-4">
                <div v-for="repo in sortedRepositories" :key="repo.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div class="flex-grow truncate">
                        <div class="flex items-center gap-2">
                            <span class="px-2 py-0.5 text-xs font-semibold rounded-full" :class="repo.type === 'git' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300' : 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300'">{{ repo.type }}</span>
                            <p class="font-semibold">{{ repo.name }}</p>
                            <span class="text-sm text-gray-500">({{ repoAppCounts[repo.name] || 0 }} items)</span>
                        </div>
                        <p class="text-sm text-gray-500 font-mono truncate mt-1" :title="repo.url">{{ repo.url }}</p>
                        <p class="text-xs text-gray-400 mt-1">Last updated: {{ formatDateTime(repo.last_pulled_at) }}</p>
                    </div>
                    <div class="flex items-center gap-x-2 flex-shrink-0"><button @click="handlePullRepository(repo)" class="btn btn-secondary btn-sm" :disabled="isLoadingAction === repo.id"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingAction === repo.id}" /><span class="ml-1">{{ repo.type === 'git' ? 'Pull' : 'Rescan' }}</span></button><button v-if="repo.is_deletable" @click="handleDeleteRepository(repo)" class="btn btn-danger btn-sm" :disabled="isLoadingAction === repo.id"><IconTrash class="w-4 h-4" /></button></div>
                </div>
            </div>
        </section>

        <section v-if="activeSubTab === 'available_items'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2"><h3 class="text-xl font-semibold">Available Apps</h3><button @click="fetchZooItems" class="btn btn-secondary" :disabled="isLoadingZooApps"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingZooApps}" /><span class="ml-2">Rescan</span></button></div>
            <div class="space-y-4">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-4"><div class="relative lg:col-span-1"><input type="text" v-model="searchQuery" placeholder="Search apps..." class="input-field w-full pl-10" /><div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"><svg class="h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg></div></div><div class="grid grid-cols-2 lg:col-span-2 gap-4"><select v-model="installationStatusFilter" class="input-field"><option value="All">All Statuses</option><option value="Installed">Installed</option><option value="Uninstalled">Uninstalled</option></select><select v-model="selectedCategory" class="input-field"><option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option></select></div></div>
                <div class="flex items-center gap-2"><select v-model="sortKey" class="input-field w-48"><option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">Sort by {{ opt.label }}</option></select><button @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'" class="btn btn-secondary p-2"><IconArrowUp v-if="sortOrder === 'asc'" class="w-5 h-5" /><IconArrowDown v-else class="w-5 h-5" /></button></div>
                <div v-if="isLoadingZooApps" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6"><AppCardSkeleton v-for="i in 8" :key="i" /></div>
                <div v-else-if="!itemsWithTaskStatus || itemsWithTaskStatus.length === 0" class="empty-state-card"><h4 class="font-semibold">No Apps Found</h4><p class="text-sm">No apps match your criteria. Please add and pull a repository or adjust your filters.</p></div>
                <div v-else>
                    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
                        <AppCard v-for="item in itemsWithTaskStatus" :key="`${item.repository}/${item.folder_name}`" :app="item" :task="item.task" :is-starred="starredItems.includes(item.name)" @star="handleStarToggle(item.name)" @install="handleInstallItem(item)" @update="handleUpdateApp(item)" @uninstall="handleUninstallApp(item)" @details="showItemDetails(item)" @help="showItemHelp(item)" @view-task="viewTask" @cancel-install="handleCancelTask(item.task.id)" @start="handleAppAction(item.id, 'start')" @stop="handleAppAction(item.id, 'stop')" />
                    </div>
                    <div v-if="selectedCategory !== 'Starred'" class="mt-6 flex justify-between items-center">
                        <p class="text-sm text-gray-500">{{ pageInfo }}</p>
                        <div class="flex gap-2">
                            <button @click="currentPage--" :disabled="currentPage <= 1" class="btn btn-secondary">Previous</button>
                            <button @click="currentPage++" :disabled="currentPage >= totalPages" class="btn btn-secondary">Next</button>
                        </div>
                    </div>
                </div>
            </div>
        </section>
        
        <section v-if="activeSubTab === 'installed_apps'">
             <div class="flex justify-between items-center mb-4"><h3 class="text-xl font-semibold">Installed Apps</h3><button @click="adminStore.fetchInstalledApps" class="btn btn-secondary" :disabled="isLoadingInstalledApps"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingInstalledApps}" /><span class="ml-2">Refresh</span></button></div>
            <div v-if="isLoadingInstalledApps" class="text-center p-10">Loading...</div>
            <div v-else-if="!installedItemsWithTaskStatus || installedItemsWithTaskStatus.length === 0" class="empty-state-card"><h4 class="font-semibold">No Apps Installed</h4><p class="text-sm">Go to "Available" to install an app.</p></div>
            <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
                 <div v-for="app in installedItemsWithTaskStatus" :key="app.id" class="flex flex-col">
                    <AppCard :app="app" :task="app.task" @update="handleUpdateApp(app)" @uninstall="handleUninstallApp(app)" @start="handleAppAction(app.id, 'start')" @stop="handleAppAction(app.id, 'stop')" />
                    <div class="bg-white dark:bg-gray-800 rounded-b-lg p-2 flex justify-around items-center text-sm border-t border-gray-200 dark:border-gray-700">
                        <a v-if="app.status === 'running' && app.url" :href="app.url" target="_blank" class="btn-footer" title="Open"><IconGlobeAlt class="w-5 h-5" /></a>
                        <button @click="handleEditRegistration(app)" class="btn-footer" title="Edit Registration"><IconPencil class="w-5 h-5" /></button>
                        <button v-if="app.has_config_schema" @click="handleConfigureApp(app)" class="btn-footer" title="Configure"><IconCog class="w-5 h-5" /></button>
                        <button @click="handleShowLogs(app)" class="btn-footer" title="Logs"><IconCode class="w-5 h-5" /></button>
                    </div>
                </div>
            </div>
        </section>
    </div>
</template>