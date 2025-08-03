<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import IconArrowUpCircle from '../../assets/icons/IconArrowUpCircle.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import IconArrowUp from '../../assets/icons/IconArrowUp.vue';
import IconArrowDown from '../../assets/icons/IconArrowDown.vue';
import TaskProgressIndicator from '../ui/TaskProgressIndicator.vue';
import AppCard from '../ui/AppCard.vue';
import AppCardSkeleton from '../ui/AppCardSkeleton.vue';

const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();

const { 
    zooRepositories, isLoadingZooRepositories, zooApps, isLoadingZooApps, 
    mcpZooRepositories, isLoadingMcpZooRepositories, zooMcps, isLoadingZooMcps,
    installedApps, isLoadingInstalledApps 
} = storeToRefs(adminStore);

const { tasks } = storeToRefs(tasksStore);

const mainTab = ref('apps'); // 'apps' or 'mcps'
const activeSubTab = ref('repositories');
const isAddFormVisible = ref(false);
const newRepo = ref({ name: '', url: '' });
const isLoadingAction = ref(null);
const searchQuery = ref('');
const selectedCategory = ref('All');
const installationStatusFilter = ref('All');
const isPullingAll = ref(false);
const sortKey = ref('last_update_date');
const sortOrder = ref('desc');
const starredItems = ref(JSON.parse(localStorage.getItem('starredItems') || '[]'));

const sortOptions = [
    { value: 'last_update_date', label: 'Last Updated' },
    { value: 'creation_date', label: 'Creation Date' },
    { value: 'name', label: 'Name' },
    { value: 'author', label: 'Author' },
];

onMounted(() => {
    adminStore.fetchZooRepositories();
    adminStore.fetchMcpZooRepositories();
    adminStore.fetchZooApps();
    adminStore.fetchZooMcps();
    adminStore.fetchInstalledApps();
});

watch(mainTab, () => {
    activeSubTab.value = 'repositories';
});

watch(activeSubTab, (newTab) => {
    if (newTab === 'available_items') {
        if (mainTab.value === 'apps') adminStore.fetchZooApps();
        else adminStore.fetchZooMcps();
        adminStore.fetchInstalledApps();
    }
    if (newTab === 'installed_apps') {
        adminStore.fetchInstalledApps();
    }
});

watch(starredItems, (newStarred) => {
    localStorage.setItem('starredItems', JSON.stringify(newStarred));
}, { deep: true });

const currentRepositories = computed(() => mainTab.value === 'apps' ? zooRepositories.value : mcpZooRepositories.value);
const isLoadingCurrentRepositories = computed(() => mainTab.value === 'apps' ? isLoadingZooRepositories.value : isLoadingMcpZooRepositories.value);
const currentZooItems = computed(() => mainTab.value === 'apps' ? zooApps.value : zooMcps.value);
const isLoadingCurrentZooItems = computed(() => mainTab.value === 'apps' ? isLoadingZooApps.value : isLoadingZooMcps.value);

const itemsWithTaskStatus = computed(() => {
    if (!Array.isArray(currentZooItems.value)) return [];

    const taskMap = new Map();
    const taskPrefix = 'Installing app: '; // Both MCPs and Apps are installed as 'apps'
    if (Array.isArray(tasks.value)) {
        tasks.value.forEach(task => {
            if (task && task.name && task.name.startsWith(taskPrefix)) {
                const itemName = task.name.replace(taskPrefix, '');
                if (!taskMap.has(itemName) || new Date(task.created_at) > new Date(taskMap.get(itemName).created_at)) {
                    taskMap.set(itemName, task);
                }
            }
        });
    }

    return currentZooItems.value.map(item => {
        const task = taskMap.get(item.folder_name); // Match by folder_name which is used in task name
        return {
            ...item,
            task: (task && (task.status === 'running' || task.status === 'pending')) ? task : null,
        };
    });
});

const sortedRepositories = computed(() => {
    if (!Array.isArray(currentRepositories.value)) return [];
    return [...currentRepositories.value].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
});

const categories = computed(() => {
    if (!Array.isArray(currentZooItems.value)) return ['All'];
    const allCats = new Set(currentZooItems.value.map(item => item.category || 'Uncategorized'));
    return ['All', ...Array.from(allCats).sort()];
});

const filteredAndSortedItems = computed(() => {
    let items = itemsWithTaskStatus.value.filter(item => {
        const matchesStatus = installationStatusFilter.value === 'All' ||
                              (installationStatusFilter.value === 'Installed' && item.is_installed) ||
                              (installationStatusFilter.value === 'Uninstalled' && !item.is_installed && !item.task);
        const matchesCategory = selectedCategory.value === 'All' || item.category === selectedCategory.value;
        const matchesSearch = !searchQuery.value || 
                              item.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
                              (item.description && item.description.toLowerCase().includes(searchQuery.value.toLowerCase())) ||
                              (item.author && item.author.toLowerCase().includes(searchQuery.value.toLowerCase()));
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

        if (typeof valA === 'string' && typeof valB === 'string') {
            return sortOrder.value === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
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

const sortedInstalledApps = computed(() => {
    if (!Array.isArray(installedApps.value)) return [];
    return [...installedApps.value].sort((a, b) => (a.name || '').localeCompare(b.name || ''));
});

const installedAppsWithTaskStatus = computed(() => {
    const taskMap = new Map();
    if (Array.isArray(tasks.value)) {
        tasks.value.forEach(task => {
            if (!task || !task.name) return;
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

    return sortedInstalledApps.value.map(app => ({
        ...app,
        task: taskMap.get(app.folder_name) || null,
    }));
});

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
        isAddFormVisible.value = false;
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
        if (mainTab.value === 'apps') {
            await adminStore.pullAllZooRepositories();
        } else {
            await adminStore.pullAllMcpZooRepositories();
        }
    } finally {
        isPullingAll.value = false;
    }
}

async function handleDeleteRepository(repo) {
    const confirmed = await uiStore.showConfirmation({ title: `Delete Repository '${repo.name}'?`, message: 'This will remove the repository and its cached files. This action cannot be undone.', confirmText: 'Delete' });
    if (confirmed) {
        isLoadingAction.value = repo.id;
        try {
            if (mainTab.value === 'apps') {
                await adminStore.deleteZooRepository(repo.id);
            } else {
                await adminStore.deleteMcpZooRepository(repo.id);
            }
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
        try {
            await adminStore.uninstallApp(app.id);
        } finally {
            isLoadingAction.value = null;
        }
    }
}

function showItemDetails(item) { uiStore.openModal('appDetails', { app: item }); }
function handleEditApp(app) { uiStore.openModal('appConfig', { app }); }

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
</script>

<style scoped>
.tab-button { @apply px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors; }
.tab-button.active { @apply border-blue-500 text-blue-600 dark:text-blue-400; }
.tab-button.inactive { @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600; }
.form-fade-enter-active, .form-fade-leave-active { transition: all 0.3s ease-in-out; max-height: 500px; opacity: 1; }
.form-fade-enter-from, .form-fade-leave-to { max-height: 0; opacity: 0; transform: translateY(-20px); margin-top: 0; margin-bottom: 0; padding-top: 0; padding-bottom: 0; border-width: 0; }
</style>

<template>
    <div class="space-y-8">
        <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Apps & MCPs Zoo</h2>
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">Install and manage LOLLMS Applications and MCPs from various sources (Zoos).</p>
        </div>

        <div class="border-b border-gray-200 dark:border-gray-700">
            <nav class="-mb-px flex space-x-6" aria-label="Main Tabs">
                <button @click="mainTab = 'apps'" class="tab-button" :class="mainTab === 'apps' ? 'active' : 'inactive'">Apps Zoo</button>
                <button @click="mainTab = 'mcps'" class="tab-button" :class="mainTab === 'mcps' ? 'active' : 'inactive'">MCPs Zoo</button>
            </nav>
        </div>
        
        <div class="border-b border-gray-200 dark:border-gray-700">
            <nav class="-mb-px flex space-x-6" aria-label="Sub Tabs">
                <button @click="activeSubTab = 'repositories'" class="tab-button" :class="activeSubTab === 'repositories' ? 'active' : 'inactive'">Repositories</button>
                <button @click="activeSubTab = 'available_items'" class="tab-button" :class="activeSubTab === 'available_items' ? 'active' : 'inactive'">Available {{ mainTab === 'apps' ? 'Apps' : 'MCPs' }}</button>
                <button @click="activeSubTab = 'installed_apps'" class="tab-button" :class="activeSubTab === 'installed_apps' ? 'active' : 'inactive'">Installed</button>
            </nav>
        </div>

        <section v-if="activeSubTab === 'repositories'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
                <h3 class="text-xl font-semibold">{{ mainTab === 'apps' ? 'App' : 'MCP' }} Zoo Repositories</h3>
                <div class="flex items-center gap-2">
                    <button @click="handlePullAll" class="btn btn-secondary" :disabled="isPullingAll"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isPullingAll}" /><span class="ml-2">Pull All</span></button>
                    <button @click="isAddFormVisible = !isAddFormVisible" class="btn btn-primary">{{ isAddFormVisible ? 'Cancel' : 'Add Repository' }}</button>
                </div>
            </div>
            <transition name="form-fade">
                <div v-if="isAddFormVisible" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm mb-6 overflow-hidden">
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
            <div v-else-if="!sortedRepositories || sortedRepositories.length === 0" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg"><p>No {{ mainTab === 'apps' ? 'App' : 'MCP' }} Zoo repositories have been added yet.</p></div>
            <div v-else class="space-y-4">
                <div v-for="repo in sortedRepositories" :key="repo.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div class="flex-grow truncate">
                        <p class="font-semibold text-gray-900 dark:text-white">{{ repo.name }}</p>
                        <p class="text-sm text-gray-500 dark:text-gray-400 font-mono truncate" :title="repo.url">{{ repo.url }}</p>
                        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">Last updated: {{ formatDateTime(repo.last_pulled_at) }}</p>
                    </div>
                    <div class="flex items-center gap-x-2 flex-shrink-0">
                        <button @click="handlePullRepository(repo)" class="btn btn-secondary btn-sm" :disabled="isLoadingAction === repo.id" title="Refresh (git pull)"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingAction === repo.id}" /><span class="ml-1">Pull</span></button>
                        <button v-if="repo.is_deletable" @click="handleDeleteRepository(repo)" class="btn btn-danger btn-sm" :disabled="isLoadingAction === repo.id" title="Delete"><IconTrash class="w-4 h-4" /></button>
                    </div>
                </div>
            </div>
        </section>

        <section v-if="activeSubTab === 'available_items'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
                <h3 class="text-xl font-semibold">Available {{ mainTab === 'apps' ? 'Apps' : 'MCPs' }}</h3>
                <button @click="mainTab === 'apps' ? adminStore.fetchZooApps() : adminStore.fetchZooMcps()" class="btn btn-secondary" :disabled="isLoadingCurrentZooItems"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingCurrentZooItems}" /><span class="ml-2">Rescan All Sources</span></button>
            </div>
            <div class="space-y-4">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <div class="relative lg:col-span-1"><input type="text" v-model="searchQuery" :placeholder="`Search ${mainTab}...`" class="input-field w-full pl-10" /><div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"><svg class="h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg></div></div>
                    <div class="grid grid-cols-2 lg:col-span-2 gap-4">
                        <select v-model="installationStatusFilter" class="input-field"><option value="All">All Statuses</option><option value="Installed">Installed</option><option value="Uninstalled">Uninstalled</option></select>
                        <select v-model="selectedCategory" class="input-field"><option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option></select>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <select v-model="sortKey" class="input-field w-48"><option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">Sort by {{ opt.label }}</option></select>
                    <button @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'" class="btn btn-secondary p-2"><IconArrowUp v-if="sortOrder === 'asc'" class="w-5 h-5" /><IconArrowDown v-else class="w-5 h-5" /></button>
                </div>
                <div v-if="isLoadingCurrentZooItems" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6"><AppCardSkeleton v-for="i in 8" :key="i" /></div>
                <div v-else-if="!currentZooItems || currentZooItems.length === 0" class="text-center p-10 bg-gray-50 dark:bg-gray-800/50 rounded-lg"><h4 class="font-semibold">No Items Found</h4><p class="text-sm text-gray-500">Please add and pull a repository to see available {{ mainTab }}.</p></div>
                <div v-else-if="filteredAndSortedItems.length === 0" class="text-center p-10 bg-gray-50 dark:bg-gray-800/50 rounded-lg"><h4 class="font-semibold">No Matching Items</h4><p class="text-sm text-gray-500">Try adjusting your search or filter.</p></div>
                <div v-else>
                    <div v-if="groupedItems" class="space-y-8">
                        <div v-for="(authorItems, author) in groupedItems" :key="author"><h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3 border-b pb-2 dark:border-gray-700">{{ author }}</h3><div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6"><AppCard v-for="item in authorItems" :key="`${item.repository}/${item.folder_name}`" :app="item" :task="item.task" :is-starred="starredItems.includes(item.name)" @star="handleStarToggle(item.name)" @install="handleInstallItem(item)" @details="showItemDetails(item)" @help="showItemHelp(item)" @view-task="viewTask" @cancel-install="handleCancelTask" /></div></div>
                    </div>
                    <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6"><AppCard v-for="item in filteredAndSortedItems" :key="`${item.repository}/${item.folder_name}`" :app="item" :task="item.task" :is-starred="starredItems.includes(item.name)" @star="handleStarToggle(item.name)" @install="handleInstallItem(item)" @update="handleUpdateApp(item)" @details="showItemDetails(item)" @help="showItemHelp(item)" @view-task="viewTask" @cancel-install="handleCancelTask" /></div>
                </div>
            </div>
        </section>
        
        <section v-if="activeSubTab === 'installed_apps'">
             <h3 class="text-xl font-semibold mb-4">Installed Items</h3>
            <div v-if="isLoadingInstalledApps" class="text-center p-10">Loading installed items...</div>
            <div v-else-if="!installedAppsWithTaskStatus || installedAppsWithTaskStatus.length === 0" class="text-center p-10 bg-gray-50 dark:bg-gray-800/50 rounded-lg"><h4 class="font-semibold">No Items Installed</h4><p class="text-sm text-gray-500">Go to the "Available" tab to install an application or MCP.</p></div>
            <div v-else class="space-y-4">
                <div v-for="app in installedAppsWithTaskStatus" :key="app.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div class="flex items-center gap-4 flex-grow truncate">
                        <img v-if="app.icon" :src="app.icon" class="h-10 w-10 rounded-md flex-shrink-0 object-cover" alt="App Icon">
                        <div class="flex-grow truncate"><p class="font-semibold text-gray-900 dark:text-white truncate" :title="app.name">{{ app.name }}</p><p class="text-xs text-gray-500 dark:text-gray-400 font-mono truncate" :title="`Port: ${app.port}`">Port: {{ app.port }}</p></div>
                    </div>
                    <div class="flex items-center gap-x-2 flex-shrink-0 flex-wrap justify-end">
                        <TaskProgressIndicator v-if="app.task" :task="app.task" @view="viewTask" @cancel="handleCancelTask"/>
                        <template v-else>
                            <button v-if="app.update_available" @click="handleUpdateApp(app)" class="btn btn-warning btn-sm p-2" title="Update App"><IconArrowUpCircle class="w-5 h-5" /></button>
                            <span class="px-2 py-1 text-xs font-semibold rounded-full" :class="{ 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300': app.status === 'running', 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300': app.status === 'stopped', 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300': app.status === 'error' }">{{ app.status }}</span>
                            <a v-if="app.status === 'running' && app.url" :href="app.url" target="_blank" class="btn btn-secondary btn-sm p-2" title="Open App"><IconGlobeAlt class="w-5 h-5" /></a>
                            <button @click="handleEditApp(app)" class="btn btn-secondary btn-sm p-2" title="Edit App Settings"><IconPencil class="w-5 h-5" /></button>
                            <button @click="handleShowLogs(app)" class="btn btn-secondary btn-sm p-2" title="View App Logs"><IconCode class="w-5 h-5" /></button>
                            <button v-if="app.status !== 'running'" @click="handleAppAction(app.id, 'start')" class="btn btn-success btn-sm p-2" :disabled="isLoadingAction === `start-${app.id}`" title="Start App"><IconPlayCircle class="w-5 h-5" /></button>
                            <button v-if="app.status === 'running' || (app.status === 'error' && app.pid)" @click="handleAppAction(app.id, 'stop')" class="btn btn-warning btn-sm p-2" :disabled="isLoadingAction === `stop-${app.id}`" title="Stop App"><IconStopCircle class="w-5 h-5" /></button>
                            <button @click="handleUninstallApp(app)" class="btn btn-danger btn-sm p-2" title="Uninstall App"><IconTrash class="w-5 h-5" /></button>
                        </template>
                    </div>
                </div>
            </div>
        </section>
    </div>
</template>