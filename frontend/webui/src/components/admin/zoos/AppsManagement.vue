<!-- frontend/webui/src/components/admin/zoos/AppsManagement.vue -->
<script setup>
import { onMounted, computed, watch, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useTasksStore } from '../../../stores/tasks';
import { useUiStore } from '../../../stores/ui';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconArrowUp from '../../../assets/icons/IconArrowUp.vue';
import IconArrowDown from '../../../assets/icons/IconArrowDown.vue';
import AppCard from '../../ui/Cards/AppCard.vue';
import AppCardSkeleton from '../../ui/Cards/AppCardSkeleton.vue';

const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();

// Use the store directly for reactive filter objects
const { appFilters } = adminStore;

// Use storeToRefs for refs and other reactive properties
const { 
    zooRepositories, isLoadingZooRepositories, zooApps, isLoadingZooApps
} = storeToRefs(adminStore);
const { tasks } = storeToRefs(tasksStore);

const activeSubTab = ref('zoo');
const newRepo = ref({ type: 'git', name: '', url: '', path: '' });
const isAddRepoFormVisible = ref(false);
const isLoadingAction = ref(null);
const starredItems = ref(JSON.parse(localStorage.getItem('starredApps') || '[]'));
let debounceTimer = null;

const currentPage = computed({
  get: () => appFilters.currentPage,
  set: (val) => { appFilters.currentPage = val; }
});

const sortOptions = [
    { value: 'last_update_date', label: 'Last Updated' }, { value: 'creation_date', label: 'Creation Date' },
    { value: 'name', label: 'Name' }, { value: 'author', label: 'Author' },
];

const totalItems = computed(() => zooApps.value.total || 0);
const totalPages = computed(() => zooApps.value.pages || 1);
const pageInfo = computed(() => {
    if (totalItems.value === 0) return 'Showing 0-0 of 0';
    const start = (appFilters.currentPage - 1) * appFilters.pageSize + 1;
    const end = Math.min(appFilters.currentPage * appFilters.pageSize, totalItems.value);
    return `Showing ${start}-${end} of ${totalItems.value}`;
});

function debouncedFetch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        if (appFilters.currentPage !== 1) appFilters.currentPage = 1;
        else adminStore.fetchZooApps();
    }, 300);
}

watch(
    () => [appFilters.sortKey, appFilters.sortOrder, appFilters.selectedCategory, appFilters.installationStatusFilter, appFilters.selectedRepository], 
    () => {
        if (appFilters.currentPage !== 1) appFilters.currentPage = 1;
        else adminStore.fetchZooApps();
    }
);
watch(() => appFilters.searchQuery, debouncedFetch);
watch(() => appFilters.currentPage, () => adminStore.fetchZooApps());
watch(starredItems, (newStarred) => { localStorage.setItem('starredApps', JSON.stringify(newStarred)); }, { deep: true });
watch(activeSubTab, (newTab) => {
    if (newTab === 'zoo') adminStore.fetchZooApps();
    if (newTab === 'source') adminStore.fetchZooRepositories();
})

onMounted(() => {
    if(activeSubTab.value === 'zoo') adminStore.fetchZooApps();
    if(activeSubTab.value === 'source') adminStore.fetchZooRepositories();
});

const itemsWithTaskStatus = computed(() => {
    const taskMap = new Map();
    const installPrefix = 'Installing app: ';
    const otherTaskRegex = /^(Updating app|Start app|Stop app|Fixing item|Purging item): .* \(([a-fA-F0-9-]+)\)$/;

    (tasks.value || []).forEach(task => {
        if (task?.name && (task.status === 'running' || task.status === 'pending')) {
            let key;
            if (task.name.startsWith(installPrefix)) {
                key = `folder:${task.name.replace(installPrefix, '')}`;
            } else {
                const match = task.name.match(otherTaskRegex);
                if (match) key = `id:${match[2]}`;
            }
            if (key && (!taskMap.has(key) || new Date(task.created_at) > new Date(taskMap.get(key).created_at))) {
                taskMap.set(key, task);
            }
        }
    });
    return (zooApps.value.items || []).map(item => ({...item, task: taskMap.get(`folder:${item.folder_name}`) || (item.id ? taskMap.get(`id:${item.id}`) : null)}));
});

const sortedRepositories = computed(() => Array.isArray(zooRepositories.value) ? [...zooRepositories.value].sort((a, b) => (a.name || '').localeCompare(b.name || '')) : []);
const categories = computed(() => ['All', 'Starred', ...(zooApps.value.categories || [])]);

function handleStarToggle(itemName) { const index = starredItems.value.indexOf(itemName); if (index > -1) starredItems.value.splice(index, 1); else starredItems.value.push(itemName); }
function formatDateTime(isoString) { if (!isoString) return 'Never'; return new Date(isoString).toLocaleString(); }
async function handleAddRepository() {
    if (!newRepo.value.name) { uiStore.addNotification('Repository name is required.', 'warning'); return; }
    const payload = { name: newRepo.value.name };
    if (newRepo.value.type === 'git') payload.url = newRepo.value.url; else payload.path = newRepo.value.path;
    isLoadingAction.value = 'add';
    try { await adminStore.addZooRepository(payload); newRepo.value = { type: 'git', name: '', url: '', path: '' }; isAddRepoFormVisible.value = false; }
    finally { isLoadingAction.value = null; }
}
async function handlePullRepository(repo) { isLoadingAction.value = repo.id; try { await adminStore.pullZooRepository(repo.id); } finally { isLoadingAction.value = null; } }
async function handleDeleteRepository(repo) {
    if (await uiStore.showConfirmation({ title: `Delete Repository '${repo.name}'?`})) {
        isLoadingAction.value = repo.id;
        try { await adminStore.deleteZooRepository(repo.id); } finally { isLoadingAction.value = null; }
    }
}
function handleInstallItem(item) { uiStore.openModal('appInstall', { app: item, type: 'apps' }); }
async function handleUpdateApp(app) { if (await uiStore.showConfirmation({ title: `Update '${app.name}'?`, confirmText: 'Update' })) { await adminStore.updateApp(app.id); }}
async function handleAppAction(appId, action) { isLoadingAction.value = `${action}-${appId}`; try { if (action === 'start') await adminStore.startApp(appId); if (action === 'stop') await adminStore.stopApp(appId); } finally { isLoadingAction.value = null; } }
async function handleRestartApp(app) {
    if (await uiStore.showConfirmation({ title: `Restart '${app.name}'?`, message: 'The application will be stopped and started again.', confirmText: 'Restart' })) {
        await adminStore.restartApp(app.id);
    }
}
async function handleUninstallApp(app) { if (await uiStore.showConfirmation({ title: `Uninstall '${app.name}'?`, confirmText: 'Uninstall' })) { isLoadingAction.value = `uninstall-${app.id}`; try { await adminStore.uninstallApp(app.id); } finally { isLoadingAction.value = null; } } }
function handleConfigureApp(app) {
    if (app.is_installed) {
        uiStore.openModal('appConfig', { app });
    } else if (app.repository === 'Registered') {
        uiStore.openModal('serviceRegistration', { 
            item: app, 
            itemType: 'app', 
            ownerType: app.type || 'system',
            onRegistered: adminStore.fetchZooApps
        });
    }
}
function handleEditEnv(app) {
    uiStore.openModal('appEnvConfig', { app });
}
async function handleDeleteRegisteredItem(app) {
    if (await uiStore.showConfirmation({ title: `Delete Registration for '${app.name}'?`, message: 'This will remove the manually registered entry but will not affect the service itself.', confirmText: 'Delete' })) {
        await adminStore.deleteRegisteredApp(app.id);
    }
}
function handleViewLogs(app) { uiStore.openModal('appLog', { app }); }
async function showItemHelp(item) { const readme = await adminStore.fetchAppReadme(item.repository, item.folder_name); uiStore.openModal('sourceViewer', { title: `README: ${item.name}`, content: readme, language: 'markdown' }); }
async function handleCancelTask(taskId) { await tasksStore.cancelTask(taskId); }
function viewTask(taskId) { uiStore.openModal('tasksManager', { initialTaskId: taskId }); }
async function handleSync() { await adminStore.syncInstallations(); }
async function handlePurgeItem(item) {
    if (await uiStore.showConfirmation({ title: `Purge '${item.name}'?`, message: 'This will permanently delete the installation folder.', confirmText: 'Purge'})) {
        await adminStore.purgeBrokenInstallation(item);
    }
}
async function handleFixItem(item) {
    if (await uiStore.showConfirmation({ title: `Fix '${item.name}'?`, message: 'This will attempt to re-create the database entry for this item.', confirmText: 'Fix'})) {
        await adminStore.fixBrokenInstallation(item);
    }
}
function handleShowDetails(app) { uiStore.openModal('appDetails', { app }); }
function handleRegisterApp() { uiStore.openModal('serviceRegistration', { itemType: 'app', ownerType: 'system', onRegistered: adminStore.fetchZooApps }); }

async function handleRefreshCache() {
    const task = await adminStore.refreshZooCache();
    if (task) {
        uiStore.openModal('tasksManager', { initialTaskId: task.id });
    }
}

const getTaskForApp = (app) => {
  if (!app.folder_name) return null;
  // This finds any task whose name includes the app's folder_name
  return tasksStore.tasks.find(task =>
    (task.name.toLowerCase().includes(app.folder_name.toLowerCase())) &&
    (task.status === 'running' || task.status === 'pending')
  );
};
</script>

<style scoped>
.tab-button { @apply px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors; }
.tab-button.active { @apply border-blue-500 text-blue-600 dark:text-blue-400; }
.tab-button.inactive { @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600; }
.empty-state-card { @apply text-center py-10 px-4 rounded-lg bg-gray-50 dark:bg-gray-800/50 text-gray-500 dark:text-gray-400; }
</style>

<template>
    <div class="space-y-6">
        <div class="border-b border-gray-200 dark:border-gray-700">
            <nav class="-mb-px flex space-x-6" aria-label="Sub Tabs">
                <button @click="activeSubTab = 'zoo'" class="tab-button" :class="activeSubTab === 'zoo' ? 'active' : 'inactive'">Zoo</button>
                <button @click="activeSubTab = 'source'" class="tab-button" :class="activeSubTab === 'source' ? 'active' : 'inactive'">Repositories</button>
            </nav>
        </div>

        <section v-if="activeSubTab === 'zoo'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
                <h3 class="text-xl font-semibold">App Zoo</h3>
                <div class="flex items-center gap-2">
                    <button @click="handleRefreshCache" class="btn btn-secondary" title="Refresh Zoo Cache from all sources">
                        <IconRefresh class="w-4 h-4" />
                    </button>
                    <button @click="handleRegisterApp" class="btn btn-secondary">Register External App</button>
                    <button @click="handleSync" class="btn btn-secondary-outline" title="Repair broken installations and remove orphaned DB entries.">Sync Installations</button>
                </div>
            </div>
             <div class="space-y-4">
                <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
                    <div class="relative lg:col-span-1"><input type="text" v-model="appFilters.searchQuery" placeholder="Search apps..." class="input-field w-full pl-10" /><div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"><svg class="h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg></div></div>
                    <div class="grid grid-cols-1 sm:grid-cols-3 lg:col-span-3 gap-4">
                        <select v-model="appFilters.installationStatusFilter" class="input-field"><option value="All">All Statuses</option><option value="Installed">Installed</option><option value="Uninstalled">Uninstalled</option><option value="Registered">Registered</option><option value="Broken">Broken</option></select>
                        <select v-model="appFilters.selectedCategory" class="input-field"><option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option></select>
                        <select v-model="appFilters.selectedRepository" class="input-field"><option value="All">All Sources</option><option value="Registered">Registered</option><option v-for="repo in sortedRepositories" :key="repo.id" :value="repo.name">{{ repo.name }}</option></select>
                    </div>
                </div>
                <div class="flex items-center gap-2"><select v-model="appFilters.sortKey" class="input-field w-48"><option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">Sort by {{ opt.label }}</option></select><button @click="appFilters.sortOrder = appFilters.sortOrder === 'asc' ? 'desc' : 'asc'" class="btn btn-secondary p-2"><IconArrowUp v-if="appFilters.sortOrder === 'asc'" class="w-5 h-5" /><IconArrowDown v-else class="w-5 h-5" /></button></div>
                
                <div v-if="isLoadingZooApps" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6"><AppCardSkeleton v-for="i in 8" :key="i" /></div>
                <div v-else-if="!itemsWithTaskStatus || itemsWithTaskStatus.length === 0" class="empty-state-card"><h4 class="font-semibold">No Apps Found</h4></div>
                <div v-else>
                    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
                        <AppCard v-for="item in itemsWithTaskStatus" :key="item.id || `${item.repository}/${item.folder_name}`" :app="item" :task="item.task" :is-starred="starredItems.includes(item.name)" @star="handleStarToggle(item.name)" @install="handleInstallItem(item)" @update="handleUpdateApp(item)" @uninstall="handleUninstallApp(item)" @delete="handleDeleteRegisteredItem(item)" @help="showItemHelp(item)" @view-task="viewTask" @cancel-install="handleCancelTask(item.task.id)" @start="handleAppAction(item.id, 'start')" @stop="handleAppAction(item.id, 'stop')" @configure="handleConfigureApp(item)" @fix="handleFixItem(item)" @purge="handlePurgeItem(item)" @details="handleShowDetails" @logs="handleViewLogs(item)" @edit-env="handleEditEnv(item)" @restart="handleRestartApp(item)" />
                    </div>
                    <div v-if="totalPages > 1" class="flex justify-between items-center mt-6"><button @click="currentPage--" :disabled="currentPage === 1" class="btn btn-secondary">Previous</button><span class="text-sm text-gray-600 dark:text-gray-400">{{ pageInfo }}</span><button @click="currentPage++" :disabled="currentPage >= totalPages" class="btn btn-secondary">Next</button></div>
                </div>
            </div>
        </section>
        
        <section v-if="activeSubTab === 'source'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2"><h3 class="text-xl font-semibold">App Zoo Repositories</h3><button @click="isAddRepoFormVisible = !isAddRepoFormVisible" class="btn btn-primary">{{ isAddRepoFormVisible ? 'Cancel' : 'Add Repository' }}</button></div>
            <div v-if="isAddRepoFormVisible" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm mb-6"><form @submit.prevent="handleAddRepository" class="space-y-4"><div class="flex items-center gap-x-4"><label><input type="radio" v-model="newRepo.type" value="git" class="radio-input"> Git</label><label><input type="radio" v-model="newRepo.type" value="local" class="radio-input"> Local</label></div><div><label>Name</label><input v-model="newRepo.name" type="text" class="input-field" required></div><div v-if="newRepo.type === 'git'"><label>URL</label><input v-model="newRepo.url" type="url" class="input-field" :required="newRepo.type==='git'"></div><div v-if="newRepo.type === 'local'"><label>Path</label><input v-model="newRepo.path" type="text" class="input-field" :required="newRepo.type==='local'"></div><div class="flex justify-end"><button type="submit" class="btn btn-primary">Add</button></div></form></div>
            <div v-if="isLoadingZooRepositories" class="text-center p-4">Loading...</div>
            <div v-else-if="!sortedRepositories || sortedRepositories.length === 0" class="empty-state-card"><p>No repositories added.</p></div>
            <div v-else class="space-y-4"><div v-for="repo in sortedRepositories" :key="repo.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex items-center justify-between"><div><p class="font-semibold">{{ repo.name }}</p><p class="text-sm text-gray-500">{{ repo.url }}</p><p class="text-xs text-gray-400">Pulled: {{ formatDateTime(repo.last_pulled_at) }}</p></div><div class="flex items-center gap-2"><button @click="handlePullRepository(repo)" class="btn btn-secondary btn-sm"><IconRefresh class="w-4 h-4 mr-1"/>{{ repo.type === 'git' ? 'Pull' : 'Rescan' }}</button><button v-if="repo.is_deletable" @click="handleDeleteRepository(repo)" class="btn btn-danger btn-sm"><IconTrash class="w-4 h-4"/></button></div></div></div>
        </section>
    </div>
</template>