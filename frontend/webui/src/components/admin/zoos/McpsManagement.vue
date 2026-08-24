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
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconGlobeAlt from '../../../assets/icons/IconGlobeAlt.vue';
import IconPlayCircle from '../../../assets/icons/IconPlayCircle.vue';
import IconStopCircle from '../../../assets/icons/IconStopCircle.vue';
import IconArrowPath from '../../../assets/icons/IconArrowPath.vue';
import AppCard from '../../ui/Cards/AppCard.vue';
import AppCardSkeleton from '../../ui/Cards/AppCardSkeleton.vue';

const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();

const { mcpFilters } = adminStore;
const { 
    mcpZooRepositories, isLoadingMcpZooRepositories, zooMcps, isLoadingZooMcps
} = storeToRefs(adminStore);
const { tasks } = storeToRefs(tasksStore);

const activeSubTab = ref('zoo');
const newRepo = ref({ type: 'git', name: '', url: '', path: '' });
const isAddRepoFormVisible = ref(false);
const isLoadingAction = ref(null);
const isRefreshingCache = ref(false);
const starredItems = ref(JSON.parse(localStorage.getItem('starredMcps') || '[]'));
let debounceTimer = null;

const searchQuery = computed({
  get: () => mcpFilters.searchQuery,
  set: (val) => { mcpFilters.searchQuery = val; }
});
const selectedCategory = computed({
  get: () => mcpFilters.selectedCategory,
  set: (val) => { mcpFilters.selectedCategory = val; }
});
const installationStatusFilter = computed({
  get: () => mcpFilters.installationStatusFilter,
  set: (val) => { mcpFilters.installationStatusFilter = val; }
});
const selectedRepository = computed({
  get: () => mcpFilters.selectedRepository,
  set: (val) => { mcpFilters.selectedRepository = val; }
});
const sortKey = computed({
  get: () => mcpFilters.sortKey,
  set: (val) => { mcpFilters.sortKey = val; }
});
const sortOrder = computed({
  get: () => mcpFilters.sortOrder,
  set: (val) => { mcpFilters.sortOrder = val; }
});
const currentPage = computed({
  get: () => mcpFilters.currentPage,
  set: (val) => { mcpFilters.currentPage = val; }
});
const pageSize = computed({
  get: () => mcpFilters.pageSize,
  set: (val) => { mcpFilters.pageSize = val; }
});

const sortOptions = [
    { value: 'last_update_date', label: 'Last Updated' }, 
    { value: 'creation_date', label: 'Creation Date' },
    { value: 'name', label: 'Name' }, 
    { value: 'author', label: 'Author' },
];

const totalItems = computed(() => zooMcps.value.total || 0);
const totalPages = computed(() => zooMcps.value.pages || 1);
const pageInfo = computed(() => {
    if (totalItems.value === 0) return 'Showing 0-0 of 0';
    const start = (currentPage.value - 1) * pageSize.value + 1;
    const end = Math.min(currentPage.value * pageSize.value, totalItems.value);
    return `Showing ${start}-${end} of ${totalItems.value}`;
});

function debouncedFetch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        if (currentPage.value !== 1) currentPage.value = 1;
        else adminStore.fetchZooMcps();
    }, 300);
}

function clearSearch() {
    searchQuery.value = '';
    debouncedFetch();
}

function selectCategory(cat) {
    selectedCategory.value = cat;
    currentPage.value = 1;
    adminStore.fetchZooMcps();
}

function filterByRunning() {
    if (installationStatusFilter.value === 'Running') {
        installationStatusFilter.value = 'All';
    } else {
        installationStatusFilter.value = 'Running';
    }
    currentPage.value = 1;
    adminStore.fetchZooMcps();
}

watch([sortKey, sortOrder, selectedCategory, installationStatusFilter, selectedRepository], () => {
    if (currentPage.value !== 1) currentPage.value = 1;
    else adminStore.fetchZooMcps();
});
watch(searchQuery, debouncedFetch);
watch(currentPage, () => adminStore.fetchZooMcps());
watch(starredItems, (newStarred) => { localStorage.setItem('starredMcps', JSON.stringify(newStarred)); }, { deep: true });
watch(activeSubTab, (newTab) => {
    if (newTab === 'zoo') adminStore.fetchZooMcps();
    if (newTab === 'source') adminStore.fetchMcpZooRepositories();
});

onMounted(() => {
    if (activeSubTab.value === 'zoo') adminStore.fetchZooMcps();
    if (activeSubTab.value === 'source') adminStore.fetchMcpZooRepositories();
});

const itemsWithTaskStatus = computed(() => {
    const taskMap = new Map();
    const installPrefix = 'Installing MCP: ';
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
    return (zooMcps.value.items || []).map(item => ({
        ...item, 
        task: taskMap.get(`folder:${item.folder_name}`) || (item.id ? taskMap.get(`id:${item.id}`) : null)
    }));
});

// Live Running MCPs Computer
const runningMcps = computed(() => {
    return (zooMcps.value.items || []).filter(item => item.is_installed && item.status === 'running');
});

const sortedRepositories = computed(() => Array.isArray(mcpZooRepositories.value) ? [...mcpZooRepositories.value].sort((a, b) => (a.name || '').localeCompare(b.name || '')) : []);
const categories = computed(() => ['All', 'Starred', ...(zooMcps.value.categories || [])]);

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
    if (!newRepo.value.name) { uiStore.addNotification('Repository name is required.', 'warning'); return; }
    const payload = { name: newRepo.value.name };
    if (newRepo.value.type === 'git') payload.url = newRepo.value.url; else payload.path = newRepo.value.path;
    isLoadingAction.value = 'add';
    try { 
        await adminStore.addMcpZooRepository(payload); 
        newRepo.value = { type: 'git', name: '', url: '', path: '' }; 
        isAddRepoFormVisible.value = false; 
    }
    finally { isLoadingAction.value = null; }
}

async function handlePullRepository(repo) { 
    isLoadingAction.value = repo.id; 
    try { await adminStore.pullMcpZooRepository(repo.id); } 
    finally { isLoadingAction.value = null; } 
}

async function handleDeleteRepository(repo) { 
    if (await uiStore.showConfirmation({ title: `Delete Repository '${repo.name}'?` })) { 
        isLoadingAction.value = repo.id; 
        try { await adminStore.deleteMcpZooRepository(repo.id); } 
        finally { isLoadingAction.value = null; } 
    } 
}

function handleInstallItem(item) { uiStore.openModal('appInstall', { app: item, type: 'mcps' }); }
async function handleUpdateApp(app) { 
    if (await uiStore.showConfirmation({ title: `Update '${app.name}'?`, confirmText: 'Update' })) { 
        await adminStore.updateApp(app.id); 
    }
}

async function handleAppAction(appId, action) { 
    isLoadingAction.value = `${action}-${appId}`; 
    try { 
        if (action === 'start') await adminStore.startApp(appId); 
        if (action === 'stop') await adminStore.stopApp(appId); 
    } 
    finally { isLoadingAction.value = null; } 
}

async function handleRestartApp(app) {
    if (await uiStore.showConfirmation({ title: `Restart '${app.name}'?`, message: 'The MCP service will be stopped and started again.', confirmText: 'Restart' })) {
        await adminStore.restartApp(app.id);
    }
}

async function handleUninstallApp(app) { 
    if (await uiStore.showConfirmation({ title: `Uninstall '${app.name}'?`, confirmText: 'Uninstall' })) { 
        isLoadingAction.value = `uninstall-${app.id}`; 
        try { await adminStore.uninstallApp(app.id); } 
        finally { isLoadingAction.value = null; } 
    } 
}

function handleConfigureApp(mcp) {
    if (mcp.is_installed) {
        uiStore.openModal('appConfig', { app: mcp });
    } else if (mcp.repository === 'Registered') {
        uiStore.openModal('serviceRegistration', { 
            item: mcp, 
            itemType: 'mcp', 
            ownerType: mcp.type || 'system',
            onRegistered: adminStore.fetchZooMcps
        });
    }
}

function handleEditEnv(mcp) {
    uiStore.openModal('appEnvConfig', { app: mcp });
}

async function handleDeleteRegisteredItem(mcp) {
    if (await uiStore.showConfirmation({ title: `Delete Registration for '${mcp.name}'?`, message: 'This will remove the manually registered entry but will not affect the service itself.', confirmText: 'Delete' })) {
        await adminStore.deleteRegisteredMcp(mcp.id);
    }
}

function handleViewLogs(app) { uiStore.openModal('appLog', { app }); }
async function showItemHelp(item) { 
    const readme = await adminStore.fetchMcpReadme(item.repository, item.folder_name); 
    uiStore.openModal('sourceViewer', { title: `README: ${item.name}`, content: readme, language: 'markdown' }); 
}

async function handleCancelTask(taskId) { await tasksStore.cancelTask(taskId); }
function viewTask(taskId) { uiStore.openModal('tasksManager', { initialTaskId: taskId }); }
async function handleSync() { await adminStore.syncInstallations(); }
async function handlePurgeItem(item) { 
    if (await uiStore.showConfirmation({ title: `Purge '${item.name}'?`, message: 'This will permanently delete the installation folder.', confirmText: 'Purge' })) { 
        await adminStore.purgeBrokenInstallation({...item, item_type: 'mcp'}); 
    }
}

async function handleFixItem(item) { 
    if (await uiStore.showConfirmation({ title: `Fix '${item.name}'?`, message: 'This will attempt to re-create the database entry for this item.', confirmText: 'Fix' })) { 
        await adminStore.fixBrokenInstallation({...item, item_type: 'mcp'}); 
    }
}

function handleShowDetails(app) { uiStore.openModal('appDetails', { app }); }
function handleRegisterMcp() { uiStore.openModal('serviceRegistration', { itemType: 'mcp', ownerType: 'system', onRegistered: adminStore.fetchZooMcps }); }

async function handleRefreshCache() {
    isRefreshingCache.value = true;
    try {
        const task = await adminStore.refreshZooCache();
        if (task) {
            uiStore.openModal('tasksManager', { initialTaskId: task.id });
        }
    } finally {
        setTimeout(() => { isRefreshingCache.value = false; }, 800);
    }
}
</script>

<template>
    <div class="space-y-6">
        <!-- Sub Tabs Navigation -->
        <div class="flex items-center justify-between border-b border-gray-200 dark:border-gray-700/80 pb-px">
            <nav class="flex space-x-2" aria-label="Sub Tabs">
                <button 
                    @click="activeSubTab = 'zoo'" 
                    class="px-4 py-2.5 text-sm font-bold rounded-xl transition-all flex items-center gap-2"
                    :class="activeSubTab === 'zoo' ? 'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400 shadow-xs' : 'text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200'"
                >
                    MCPs Zoo Catalog
                </button>
                <button 
                    @click="activeSubTab = 'source'" 
                    class="px-4 py-2.5 text-sm font-bold rounded-xl transition-all flex items-center gap-2"
                    :class="activeSubTab === 'source' ? 'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400 shadow-xs' : 'text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200'"
                >
                    Repositories ({{ sortedRepositories.length }})
                </button>
            </nav>

            <div class="flex items-center gap-2">
                <button 
                    @click="handleRefreshCache" 
                    class="btn btn-secondary btn-sm flex items-center gap-1.5" 
                    :disabled="isRefreshingCache"
                    title="Refresh and rescan Zoo cache"
                >
                    <IconRefresh class="w-3.5 h-3.5" :class="{ 'animate-spin': isRefreshingCache }" />
                    <span>Rescan Cache</span>
                </button>
            </div>
        </div>
        
        <!-- TAB 1: MCP ZOO CATALOG -->
        <section v-if="activeSubTab === 'zoo'" class="space-y-5">
            <!-- Action & Status Header -->
            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white/60 dark:bg-gray-850/50 p-4 rounded-2xl border border-gray-200/80 dark:border-gray-700/60 backdrop-blur-md">
                <div>
                    <h3 class="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                        <span>Model Context Protocol (MCP) Zoo</span>
                        <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300">
                            {{ totalItems }} Total
                        </span>
                        <button 
                            @click="filterByRunning"
                            class="text-xs font-semibold px-2.5 py-0.5 rounded-full transition-all flex items-center gap-1.5 cursor-pointer"
                            :class="installationStatusFilter === 'Running' ? 'bg-emerald-600 text-white shadow-xs' : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 hover:bg-emerald-200'"
                            title="Click to toggle filtering for running MCPs only"
                        >
                            <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                            <span>{{ runningMcps.length }} Running</span>
                        </button>
                    </h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Equip AI models with external tools, APIs, filesystems, and databases via MCP standard.</p>
                </div>

                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <button @click="handleRegisterMcp" class="btn btn-secondary btn-sm flex-1 sm:flex-none justify-center">
                        <IconPlus class="w-3.5 h-3.5 mr-1" />Register MCP
                    </button>
                    <button @click="handleSync" class="btn btn-secondary-outline btn-sm flex-1 sm:flex-none justify-center" title="Repair ghost installations and remove orphaned DB entries">
                        Sync Installs
                    </button>
                </div>
            </div>

            <!-- Running MCPs Quick Access Bar -->
            <div v-if="runningMcps.length > 0" class="p-3 bg-emerald-50/70 dark:bg-emerald-950/20 border border-emerald-200/80 dark:border-emerald-800/40 rounded-2xl">
                <div class="flex items-center justify-between gap-2 mb-2 px-1">
                    <div class="flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        <span class="text-xs font-bold text-emerald-900 dark:text-emerald-300 uppercase tracking-wider">Active MCP Endpoints & Ports</span>
                    </div>
                    <span class="text-[11px] font-medium text-emerald-700 dark:text-emerald-400 font-mono">
                        {{ runningMcps.length }} port{{ runningMcps.length > 1 ? 's' : '' }} assigned
                    </span>
                </div>

                <div class="flex items-center gap-2 overflow-x-auto py-1 custom-scrollbar">
                    <div 
                        v-for="mcp in runningMcps" 
                        :key="mcp.id" 
                        class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white dark:bg-gray-800 border border-emerald-200/80 dark:border-emerald-800/60 shadow-xs shrink-0"
                    >
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        <span class="text-xs font-bold text-gray-900 dark:text-white max-w-[120px] truncate" :title="mcp.name">{{ mcp.name }}</span>
                        <span class="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-emerald-600 dark:text-emerald-400">
                            :{{ mcp.port }}
                        </span>
                        
                        <div class="flex items-center gap-1 pl-1 border-l border-gray-200 dark:border-gray-700">
                            <a 
                                v-if="mcp.url" 
                                :href="mcp.url" 
                                target="_blank" 
                                class="p-1 text-gray-500 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-400 rounded-md transition-colors" 
                                title="Open Endpoint"
                            >
                                <IconGlobeAlt class="w-3.5 h-3.5" />
                            </a>
                            <button 
                                @click="handleRestartApp(mcp)" 
                                class="p-1 text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200 rounded-md transition-colors" 
                                title="Restart"
                            >
                                <IconArrowPath class="w-3.5 h-3.5" />
                            </button>
                            <button 
                                @click="handleAppAction(mcp.id, 'stop')" 
                                class="p-1 text-amber-600 hover:text-amber-800 dark:text-amber-400 rounded-md transition-colors" 
                                title="Stop"
                            >
                                <IconStopCircle class="w-3.5 h-3.5" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Search, Categories, & Filters -->
            <div class="space-y-3">
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                    <!-- Search Input -->
                    <div class="relative lg:col-span-2">
                        <input 
                            type="text" 
                            v-model="searchQuery" 
                            placeholder="Search MCP servers and tools..." 
                            class="input-field w-full pl-9 pr-8 text-xs py-2 rounded-xl" 
                        />
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <svg class="h-4 w-4 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        </div>
                        <button 
                            v-if="searchQuery" 
                            @click="clearSearch"
                            class="absolute inset-y-0 right-0 pr-2.5 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                        >
                            &times;
                        </button>
                    </div>

                    <!-- Status Filter -->
                    <select v-model="installationStatusFilter" class="input-field text-xs py-2 rounded-xl font-medium">
                        <option value="All">All Statuses</option>
                        <option value="Running">⚡ Running Only</option>
                        <option value="Stopped">⏹️ Stopped Only</option>
                        <option value="Installed">Installed Only</option>
                        <option value="Uninstalled">Uninstalled Only</option>
                        <option value="Registered">Registered</option>
                        <option value="Broken">Broken</option>
                    </select>

                    <!-- Repository Filter -->
                    <select v-model="selectedRepository" class="input-field text-xs py-2 rounded-xl">
                        <option value="All">All Sources</option>
                        <option value="Registered">Registered</option>
                        <option v-for="repo in sortedRepositories" :key="repo.id" :value="repo.name">{{ repo.name }}</option>
                    </select>

                    <!-- Sort Selector -->
                    <div class="flex items-center gap-1.5">
                        <select v-model="sortKey" class="input-field text-xs py-2 rounded-xl grow">
                            <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                        </select>
                        <button 
                            @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'" 
                            class="btn btn-secondary p-2 rounded-xl shrink-0"
                            :title="sortOrder === 'asc' ? 'Sort Ascending' : 'Sort Descending'"
                        >
                            <IconArrowUp v-if="sortOrder === 'asc'" class="w-4 h-4" />
                            <IconArrowDown v-else class="w-4 h-4" />
                        </button>
                    </div>
                </div>

                <!-- Horizontal Category Pills -->
                <div class="flex items-center gap-1.5 overflow-x-auto py-1 custom-scrollbar">
                    <button 
                        v-for="cat in categories" 
                        :key="cat" 
                        @click="selectCategory(cat)"
                        class="px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all duration-200"
                        :class="selectedCategory === cat ? 'bg-blue-600 text-white shadow-xs' : 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300'"
                    >
                        {{ cat === 'Starred' ? '★ Starred' : cat }}
                    </button>
                </div>
            </div>

            <!-- MCPs Grid -->
            <div v-if="isLoadingZooMcps" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-5">
                <AppCardSkeleton v-for="i in 8" :key="i" />
            </div>

            <div v-else-if="!itemsWithTaskStatus || itemsWithTaskStatus.length === 0" class="text-center py-16 px-4 rounded-2xl bg-white/50 dark:bg-gray-800/40 border border-gray-200/80 dark:border-gray-700/60">
                <div class="w-12 h-12 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center mx-auto mb-3 text-gray-400">
                    <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a3 3 0 016 0v2M7 7h10" />
                    </svg>
                </div>
                <h4 class="font-bold text-sm text-gray-800 dark:text-gray-200">No MCPs Found</h4>
                <p class="text-xs text-gray-500 mt-1 max-w-sm mx-auto">No Model Context Protocol servers match your active filters.</p>
                <button 
                    v-if="searchQuery || selectedCategory !== 'All' || installationStatusFilter !== 'All'"
                    @click="searchQuery = ''; selectedCategory = 'All'; installationStatusFilter = 'All'; adminStore.fetchZooMcps();"
                    class="btn btn-secondary btn-sm mt-4"
                >
                    Reset Filters
                </button>
            </div>

            <div v-else class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-5">
                    <AppCard 
                        v-for="item in itemsWithTaskStatus" 
                        :key="item.id || `${item.repository}/${item.folder_name}`" 
                        :app="item" 
                        :task="item.task" 
                        :is-starred="starredItems.includes(item.name)" 
                        item-type-name="MCP" 
                        @star="handleStarToggle(item.name)" 
                        @install="handleInstallItem(item)" 
                        @update="handleUpdateApp(item)" 
                        @uninstall="handleUninstallApp(item)" 
                        @delete="handleDeleteRegisteredItem(item)" 
                        @help="showItemHelp(item)" 
                        @view-task="viewTask" 
                        @cancel-install="handleCancelTask(item.task.id)" 
                        @start="handleAppAction(item.id, 'start')" 
                        @stop="handleAppAction(item.id, 'stop')" 
                        @configure="handleConfigureApp(item)" 
                        @fix="handleFixItem(item)" 
                        @purge="handlePurgeItem(item)" 
                        @details="handleShowDetails" 
                        @logs="handleViewLogs(item)" 
                        @edit-env="handleEditEnv(item)" 
                        @restart="handleRestartApp(item)"
                    />
                </div>

                <!-- Pagination -->
                <div v-if="totalPages > 1" class="flex justify-between items-center bg-white/60 dark:bg-gray-850/50 px-4 py-3 rounded-2xl border border-gray-200/80 dark:border-gray-700/60 backdrop-blur-md">
                    <button @click="currentPage--" :disabled="currentPage === 1" class="btn btn-secondary btn-sm">Previous</button>
                    <span class="text-xs font-medium text-gray-600 dark:text-gray-400">{{ pageInfo }}</span>
                    <button @click="currentPage++" :disabled="currentPage >= totalPages" class="btn btn-secondary btn-sm">Next</button>
                </div>
            </div>
        </section>

        <!-- TAB 2: REPOSITORIES -->
        <section v-if="activeSubTab === 'source'" class="space-y-5">
            <div class="flex justify-between items-center bg-white/60 dark:bg-gray-850/50 p-4 rounded-2xl border border-gray-200/80 dark:border-gray-700/60 backdrop-blur-md">
                <div>
                    <h3 class="text-lg font-bold text-gray-900 dark:text-white">MCP Zoo Repositories</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Repositories and sources providing tools and MCP servers.</p>
                </div>
                <button @click="isAddRepoFormVisible = !isAddRepoFormVisible" class="btn btn-primary btn-sm">
                    {{ isAddRepoFormVisible ? 'Cancel' : 'Add Repository' }}
                </button>
            </div>

            <!-- Add Repo Expandable Form -->
            <div v-if="isAddRepoFormVisible" class="bg-white dark:bg-gray-800 p-5 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-sm">
                <form @submit.prevent="handleAddRepository" class="space-y-4">
                    <div class="flex items-center gap-x-6 text-sm font-medium">
                        <label class="flex items-center gap-2 cursor-pointer">
                            <input type="radio" v-model="newRepo.type" value="git" class="radio-input"> 
                            <span>Git Repository</span>
                        </label>
                        <label class="flex items-center gap-2 cursor-pointer">
                            <input type="radio" v-model="newRepo.type" value="local" class="radio-input"> 
                            <span>Local Directory</span>
                        </label>
                    </div>

                    <div>
                        <label class="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Repository Name</label>
                        <input v-model="newRepo.name" type="text" class="input-field" placeholder="e.g. Community MCPs" required>
                    </div>

                    <div v-if="newRepo.type === 'git'">
                        <label class="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Git Clone URL</label>
                        <input v-model="newRepo.url" type="url" class="input-field" placeholder="https://github.com/user/mcp-zoo.git" :required="newRepo.type === 'git'">
                    </div>

                    <div v-if="newRepo.type === 'local'">
                        <label class="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Local Directory Absolute Path</label>
                        <input v-model="newRepo.path" type="text" class="input-field" placeholder="/path/to/mcps" :required="newRepo.type === 'local'">
                    </div>

                    <div class="flex justify-end gap-2 pt-2 border-t dark:border-gray-700">
                        <button type="button" @click="isAddRepoFormVisible = false" class="btn btn-secondary btn-sm">Cancel</button>
                        <button type="submit" class="btn btn-primary btn-sm">Save Repository</button>
                    </div>
                </form>
            </div>

            <!-- Repositories List -->
            <div v-if="isLoadingMcpZooRepositories" class="text-center py-8 text-sm text-gray-500">Loading repositories...</div>
            <div v-else-if="!sortedRepositories || sortedRepositories.length === 0" class="text-center py-12 rounded-2xl bg-gray-50 dark:bg-gray-800/50 text-gray-500">
                <p class="text-sm">No MCP repositories added.</p>
            </div>
            <div v-else class="space-y-3">
                <div 
                    v-for="repo in sortedRepositories" 
                    :key="repo.id" 
                    class="bg-white dark:bg-gray-800/90 p-4 rounded-2xl border border-gray-200/80 dark:border-gray-700/70 shadow-xs flex items-center justify-between gap-4"
                >
                    <div class="min-w-0">
                        <div class="flex items-center gap-2">
                            <p class="font-bold text-sm text-gray-900 dark:text-white truncate">{{ repo.name }}</p>
                            <span class="px-2 py-0.2 rounded text-[10px] font-mono uppercase bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                                {{ repo.type }}
                            </span>
                        </div>
                        <p class="text-xs text-gray-500 dark:text-gray-400 font-mono truncate mt-0.5">{{ repo.url }}</p>
                        <p class="text-[11px] text-gray-400 mt-1">Last synced: {{ formatDateTime(repo.last_pulled_at) }}</p>
                    </div>

                    <div class="flex items-center gap-2 shrink-0">
                        <button 
                            @click="handlePullRepository(repo)" 
                            class="btn btn-secondary btn-sm flex items-center gap-1.5"
                            :disabled="isLoadingAction === repo.id"
                        >
                            <IconRefresh class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoadingAction === repo.id }" />
                            <span>{{ repo.type === 'git' ? 'Pull Updates' : 'Rescan' }}</span>
                        </button>
                        <button 
                            v-if="repo.is_deletable" 
                            @click="handleDeleteRepository(repo)" 
                            class="p-2 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/40 text-gray-400 hover:text-rose-600 transition-colors"
                            title="Remove Repository"
                        >
                            <IconTrash class="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>
        </section>
    </div>
</template>

<style scoped>
@reference "tailwindcss";
</style>