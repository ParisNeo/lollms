<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useUiStore } from '../../stores/ui';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPlayCircle from '../../assets/icons/IconPlayCircle.vue';
import IconStopCircle from '../../assets/icons/IconStopCircle.vue';
import IconGlobeAlt from '../../assets/icons/IconGlobeAlt.vue';
import IconArrowsUpDown from '../../assets/icons/IconArrowsUpDown.vue';
import IconArrowUp from '../../assets/icons/IconArrowUp.vue';
import IconArrowDown from '../../assets/icons/IconArrowDown.vue';
import IconArrowUpCircle from '../../assets/icons/IconArrowUpCircle.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconCode from '../../assets/icons/IconCode.vue';
import AppCard from '../ui/AppCard.vue';
import AppCardSkeleton from '../ui/AppCardSkeleton.vue';


const adminStore = useAdminStore();
const uiStore = useUiStore();

const { zooRepositories, isLoadingZooRepositories, zooApps, isLoadingZooApps, installedApps, isLoadingInstalledApps, tasks, activeTaskIds } = storeToRefs(adminStore);

const activeTab = ref('repositories');
const isAddFormVisible = ref(false);
const newRepo = ref({ name: '', url: '' });
const isLoadingAction = ref(null); 
const searchQuery = ref('');
const selectedCategory = ref('All');
const installationStatusFilter = ref('All');
const isPullingAll = ref(false);

// Sorting and Starring state
const sortKey = ref('last_update_date');
const sortOrder = ref('desc');
const starredApps = ref(JSON.parse(localStorage.getItem('starredApps') || '[]'));

const sortOptions = [
    { value: 'last_update_date', label: 'Last Updated' },
    { value: 'creation_date', label: 'Creation Date' },
    { value: 'name', label: 'Name' },
    { value: 'author', label: 'Author' },
];

onMounted(() => {
    adminStore.fetchZooRepositories();
    adminStore.fetchZooApps();
    adminStore.fetchInstalledApps();
    adminStore.fetchTasks();
});

watch(activeTab, (newTab) => {
    if (newTab === 'available_apps') {
        adminStore.fetchZooApps();
        adminStore.fetchInstalledApps();
        adminStore.fetchTasks();
    }
    if (newTab === 'installed_apps') {
        adminStore.fetchInstalledApps();
        adminStore.fetchTasks();
    }
});

watch(starredApps, (newStarred) => {
    localStorage.setItem('starredApps', JSON.stringify(newStarred));
}, { deep: true });

const appsWithTaskStatus = computed(() => {
    const taskMap = new Map();
    tasks.value.forEach(task => {
        if (task.name.startsWith('Installing app: ')) {
            const appName = task.name.replace('Installing app: ', '');
            if (!taskMap.has(appName) || new Date(task.created_at) > new Date(taskMap.get(appName).created_at)) {
                taskMap.set(appName, task);
            }
        }
    });

    return zooApps.value.map(app => {
        const task = taskMap.get(app.name);
        return {
            ...app,
            task: (task && (task.status === 'running' || task.status === 'pending')) ? task : null,
        };
    });
});

const sortedRepositories = computed(() => {
    if (!zooRepositories.value) return [];
    return [...zooRepositories.value].sort((a, b) => a.name.localeCompare(b.name));
});

const categories = computed(() => {
    const allCats = new Set(zooApps.value.map(app => app.category || 'Uncategorized'));
    return ['All', ...Array.from(allCats).sort()];
});

const filteredAndSortedApps = computed(() => {
    let apps = appsWithTaskStatus.value.filter(app => {
        const matchesStatus = installationStatusFilter.value === 'All' ||
                              (installationStatusFilter.value === 'Installed' && app.is_installed) ||
                              (installationStatusFilter.value === 'Uninstalled' && !app.is_installed && !app.task);
        const matchesCategory = selectedCategory.value === 'All' || app.category === selectedCategory.value;
        const matchesSearch = !searchQuery.value || 
                              app.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
                              (app.description && app.description.toLowerCase().includes(searchQuery.value.toLowerCase())) ||
                              (app.author && app.author.toLowerCase().includes(searchQuery.value.toLowerCase()));
        return matchesStatus && matchesCategory && matchesSearch;
    });

    apps.sort((a, b) => {
        const isAStarred = starredApps.value.includes(a.name);
        const isBStarred = starredApps.value.includes(b.name);
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

    return apps;
});

const groupedApps = computed(() => {
    if (sortKey.value !== 'author') return null;

    return filteredAndSortedApps.value.reduce((acc, app) => {
        const author = app.author || 'Unknown Author';
        if (!acc[author]) {
            acc[author] = [];
        }
        acc[author].push(app);
        return acc;
    }, {});
});

const sortedInstalledApps = computed(() => {
    if (!installedApps.value) return [];
    return [...installedApps.value].sort((a, b) => a.name.localeCompare(b.name));
});

const installedAppsWithTaskStatus = computed(() => {
    const taskMap = new Map();
    tasks.value.forEach(task => {
        let appName = '';
        if (task.name.startsWith('Start app: ')) {
            appName = task.name.replace('Start app: ', '');
        } else if (task.name.startsWith('Installing app: ')) {
            appName = task.name.replace('Installing app: ', '');
        }
        
        if (appName && (task.status === 'running' || task.status === 'pending')) {
            if (!taskMap.has(appName) || new Date(task.created_at) > new Date(taskMap.get(appName).created_at)) {
                taskMap.set(appName, task);
            }
        }
    });

    return sortedInstalledApps.value.map(app => ({
        ...app,
        task: taskMap.get(app.name) || null,
    }));
});

function handleStarToggle(appName) {
    const index = starredApps.value.indexOf(appName);
    if (index > -1) {
        starredApps.value.splice(index, 1);
    } else {
        starredApps.value.push(appName);
    }
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
        await adminStore.addZooRepository(newRepo.value.name, newRepo.value.url);
        newRepo.value = { name: '', url: '' };
        isAddFormVisible.value = false;
    } catch (error) {
    } finally {
        isLoadingAction.value = null;
    }
}

async function handlePullRepository(repo) {
    isLoadingAction.value = repo.id;
    try {
        await adminStore.pullZooRepository(repo.id);
    } catch (error) {
    } finally {
        isLoadingAction.value = null;
    }
}

async function handlePullAll() {
    isPullingAll.value = true;
    try {
        await adminStore.pullAllZooRepositories();
    } finally {
        isPullingAll.value = false;
    }
}

async function handleDeleteRepository(repo) {
    const confirmed = await uiStore.showConfirmation({
        title: `Delete Repository '${repo.name}'?`,
        message: 'This will remove the repository from the list and delete its cached files from the server. This action cannot be undone.',
        confirmText: 'Delete'
    });
    if (confirmed) {
        isLoadingAction.value = repo.id;
        try {
            await adminStore.deleteZooRepository(repo.id);
        } catch (error) {
        } finally {
            isLoadingAction.value = null;
        }
    }
}

function handleInstallApp(app) {
    uiStore.openModal('appInstall', { app });
}

function handleUpdateApp(app) {
    const zooAppDetails = zooApps.value.find(zooApp => zooApp.name === app.name);
    if (!zooAppDetails) {
        uiStore.addNotification(`Could not find app details for '${app.name}' in the zoo. Try refreshing repositories.`, 'error');
        return;
    }
    
    uiStore.showConfirmation({
        title: `Update '${app.name}'?`,
        message: 'This will reinstall the app with the latest version from the zoo. The app will be stopped during this process. Are you sure you want to continue?',
        confirmText: 'Update'
    }).then(confirmed => {
        if (confirmed) {
            handleInstallApp(zooAppDetails);
        }
    });
}


async function handleAppAction(appId, action) {
    isLoadingAction.value = `${action}-${appId}`;
    try {
        if (action === 'start') await adminStore.startApp(appId);
        if (action === 'stop') await adminStore.stopApp(appId);
    } catch (error) {
    } finally {
        isLoadingAction.value = null;
    }
}

async function handleUninstallApp(app) {
    const confirmed = await uiStore.showConfirmation({
        title: `Uninstall '${app.name}'?`,
        message: 'This will stop the app if it is running and permanently delete its files and virtual environment. This action cannot be undone.',
        confirmText: 'Uninstall'
    });
    if (confirmed) {
        isLoadingAction.value = `uninstall-${app.id}`;
        try {
            await adminStore.uninstallApp(app.id);
        } catch (error) {
        } finally {
            isLoadingAction.value = null;
        }
    }
}

function showAppDetails(app) {
    uiStore.openModal('appDetails', { app });
}

function handleEditApp(app) {
    uiStore.openModal('appConfig', { app });
}

async function handleShowLogs(app) {
    try {
        const logContent = await adminStore.fetchAppLog(app.id);
        uiStore.openModal('sourceViewer', {
            title: `Logs: ${app.name}`,
            content: logContent || 'No log content found.',
            language: 'log'
        });
    } catch (error) {
    }
}

async function showAppHelp(app) {
    try {
        const readmeContent = await adminStore.fetchAppReadme(app.repository, app.folder_name);
        uiStore.openModal('sourceViewer', {
            title: `README: ${app.name}`,
            content: readmeContent,
            language: 'markdown'
        });
    } catch (error) {
    }
}

async function handleCancelTask(taskId) {
    await adminStore.cancelTask(taskId);
}

</script>

<style scoped>
.tab-button {
    @apply px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors;
}
.tab-button.active {
    @apply border-blue-500 text-blue-600 dark:text-blue-400;
}
.tab-button.inactive {
    @apply border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600;
}
.form-fade-enter-active,
.form-fade-leave-active {
    transition: all 0.3s ease-in-out;
    max-height: 500px;
    opacity: 1;
}
.form-fade-enter-from,
.form-fade-leave-to {
    max-height: 0;
    opacity: 0;
    transform: translateY(-20px);
    margin-top: 0;
    margin-bottom: 0;
    padding-top: 0;
    padding-bottom: 0;
    border-width: 0;
}
</style>

<template>
    <div class="space-y-8">
        <div>
            <h2 class="text-2xl font-bold text-gray-900 dark:text-white">Apps Management</h2>
            <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Install and manage LOLLMS Applications from various sources (Zoos).
            </p>
        </div>

        <div class="border-b border-gray-200 dark:border-gray-700">
            <nav class="-mb-px flex space-x-6" aria-label="Tabs">
                <button @click="activeTab = 'repositories'" class="tab-button" :class="activeTab === 'repositories' ? 'active' : 'inactive'">
                    Repositories
                </button>
                <button @click="activeTab = 'available_apps'" class="tab-button" :class="activeTab === 'available_apps' ? 'active' : 'inactive'">
                    Available Apps
                </button>
                 <button @click="activeTab = 'installed_apps'" class="tab-button" :class="activeTab === 'installed_apps' ? 'active' : 'inactive'">
                    Installed Apps
                </button>
            </nav>
        </div>

        <!-- Repositories Section -->
        <section v-if="activeTab === 'repositories'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
                <h3 class="text-xl font-semibold">App Zoo Repositories</h3>
                <div class="flex items-center gap-2">
                    <button @click="handlePullAll" class="btn btn-secondary" :disabled="isPullingAll">
                        <IconRefresh class="w-4 h-4" :class="{'animate-spin': isPullingAll}" />
                        <span class="ml-2">Pull All</span>
                    </button>
                    <button @click="isAddFormVisible = !isAddFormVisible" class="btn btn-primary">
                        {{ isAddFormVisible ? 'Cancel' : 'Add Repository' }}
                    </button>
                </div>
            </div>

            <transition name="form-fade">
                <div v-if="isAddFormVisible" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm mb-6 overflow-hidden">
                    <form @submit.prevent="handleAddRepository" class="space-y-4">
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                             <div>
                                <label for="repo-name" class="block text-sm font-medium">Name</label>
                                <input id="repo-name" v-model="newRepo.name" type="text" class="input-field mt-1" placeholder="e.g., Official Zoo" required>
                            </div>
                            <div class="md:col-span-2">
                                <label for="repo-url" class="block text-sm font-medium">Git URL</label>
                                <input id="repo-url" v-model="newRepo.url" type="url" class="input-field mt-1" placeholder="https://github.com/ParisNeo/lollms_apps_zoo.git" required>
                            </div>
                        </div>
                        <div class="flex justify-end">
                            <button type="submit" class="btn btn-primary" :disabled="isLoadingAction === 'add'">
                                {{ isLoadingAction === 'add' ? 'Adding...' : 'Add Repository' }}
                            </button>
                        </div>
                    </form>
                </div>
            </transition>

            <div v-if="isLoadingZooRepositories" class="text-center p-4">Loading repositories...</div>
            <div v-else-if="sortedRepositories.length === 0" class="text-center p-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <p>No App Zoo repositories have been added yet.</p>
            </div>
            <div v-else class="space-y-4">
                <div v-for="repo in sortedRepositories" :key="repo.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div class="flex-grow truncate">
                        <p class="font-semibold text-gray-900 dark:text-white">{{ repo.name }}</p>
                        <p class="text-sm text-gray-500 dark:text-gray-400 font-mono truncate" :title="repo.url">{{ repo.url }}</p>
                        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">Last updated: {{ formatDateTime(repo.last_pulled_at) }}</p>
                    </div>
                    <div class="flex items-center gap-x-2 flex-shrink-0">
                        <button @click="handlePullRepository(repo)" class="btn btn-secondary btn-sm" :disabled="isLoadingAction === repo.id" title="Refresh (git pull)">
                            <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingAction === repo.id}" />
                            <span class="ml-1">Pull</span>
                        </button>
                        <button @click="handleDeleteRepository(repo)" class="btn btn-danger btn-sm" :disabled="isLoadingAction === repo.id" title="Delete">
                            <IconTrash class="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>
        </section>

        <!-- Available Apps Section -->
        <section v-if="activeTab === 'available_apps'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
                <h3 class="text-xl font-semibold">Available Apps</h3>
                <button @click="adminStore.fetchZooApps()" class="btn btn-secondary" :disabled="isLoadingZooApps">
                    <IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingZooApps}" />
                    <span class="ml-2">Rescan All Sources</span>
                </button>
            </div>
             <div class="space-y-4">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <div class="relative lg:col-span-1">
                        <input type="text" v-model="searchQuery" placeholder="Search apps..." class="input-field w-full pl-10" />
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <svg class="h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                        </div>
                    </div>
                    <div class="grid grid-cols-2 lg:col-span-2 gap-4">
                        <select v-model="installationStatusFilter" class="input-field">
                            <option value="All">All Statuses</option>
                            <option value="Installed">Installed</option>
                            <option value="Uninstalled">Uninstalled</option>
                        </select>
                        <select v-model="selectedCategory" class="input-field">
                            <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
                        </select>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <select v-model="sortKey" class="input-field w-48">
                        <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">Sort by {{ opt.label }}</option>
                    </select>
                    <button @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'" class="btn btn-secondary p-2">
                        <IconArrowUp v-if="sortOrder === 'asc'" class="w-5 h-5" />
                        <IconArrowDown v-else class="w-5 h-5" />
                    </button>
                </div>

                <div v-if="isLoadingZooApps" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
                    <AppCardSkeleton v-for="i in 8" :key="i" />
                </div>
                <div v-else-if="zooApps.length === 0" class="text-center p-10 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                    <h4 class="font-semibold">No Apps Found</h4>
                    <p class="text-sm text-gray-500">Please add and pull a repository to see available apps.</p>
                </div>
                <div v-else-if="filteredAndSortedApps.length === 0" class="text-center p-10 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                    <h4 class="font-semibold">No Matching Apps</h4>
                    <p class="text-sm text-gray-500">Try adjusting your search or filter.</p>
                </div>
                <div v-else>
                    <div v-if="groupedApps" class="space-y-8">
                        <div v-for="(authorApps, author) in groupedApps" :key="author">
                            <h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3 border-b pb-2 dark:border-gray-700">{{ author }}</h3>
                             <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
                                <AppCard v-for="app in authorApps" :key="`${app.repository}/${app.folder_name}`" :app="app" :task="app.task" :is-starred="starredApps.includes(app.name)" @star="handleStarToggle(app.name)" @install="handleInstallApp(app)" @details="showAppDetails(app)" @help="showAppHelp(app)" @cancel-install="handleCancelTask" />
                            </div>
                        </div>
                    </div>
                     <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
                        <AppCard v-for="app in filteredAndSortedApps" :key="`${app.repository}/${app.folder_name}`" :app="app" :task="app.task" :is-starred="starredApps.includes(app.name)" @star="handleStarToggle(app.name)" @install="handleInstallApp(app)" @update="handleUpdateApp(app)" @details="showAppDetails(app)" @help="showAppHelp(app)" @cancel-install="handleCancelTask" />
                    </div>
                </div>
             </div>
        </section>
        
        <!-- Installed Apps Section -->
        <section v-if="activeTab === 'installed_apps'">
             <div v-if="isLoadingInstalledApps" class="text-center p-10">Loading installed apps...</div>
             <div v-else-if="installedAppsWithTaskStatus.length === 0" class="text-center p-10 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <h4 class="font-semibold">No Apps Installed</h4>
                <p class="text-sm text-gray-500">Go to the "Available Apps" tab to install an application.</p>
            </div>
            <div v-else class="space-y-4">
                 <div v-for="app in installedAppsWithTaskStatus" :key="app.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div class="flex items-center gap-4 flex-grow truncate">
                        <img v-if="app.icon" :src="app.icon" class="h-10 w-10 rounded-md flex-shrink-0 object-cover" alt="App Icon">
                        <div class="flex-grow truncate">
                            <p class="font-semibold text-gray-900 dark:text-white truncate" :title="app.name">{{ app.name }}</p>
                            <p class="text-xs text-gray-500 dark:text-gray-400 font-mono truncate" :title="`Port: ${app.port}`">Port: {{ app.port }}</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-x-2 flex-shrink-0 flex-wrap justify-end">
                        <div v-if="app.task" class="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400">
                            <span class="capitalize">{{ app.task.name.split(':')[0] }}... ({{ app.task.progress }}%)</span>
                            <button @click="handleCancelTask(app.task.id)" class="btn btn-warning btn-sm !p-1" title="Cancel Task">
                                <IconStopCircle class="w-4 h-4" />
                            </button>
                        </div>
                        <template v-else>
                            <button v-if="app.update_available" @click="handleUpdateApp(app)" class="btn btn-warning btn-sm p-2" title="Update App">
                                <IconArrowUpCircle class="w-5 h-5" />
                            </button>
                            <span class="px-2 py-1 text-xs font-semibold rounded-full" :class="{
                                'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300': app.status === 'running',
                                'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300': app.status === 'stopped',
                                'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300': app.status === 'error',
                            }">
                               {{ app.status }}
                            </span>
                            <a v-if="app.status === 'running' && app.url" :href="app.url" target="_blank" class="btn btn-secondary btn-sm p-2" title="Open App">
                                <IconGlobeAlt class="w-5 h-5" />
                            </a>
                            <button @click="handleEditApp(app)" class="btn btn-secondary btn-sm p-2" title="Edit App Settings">
                                <IconPencil class="w-5 h-5" />
                            </button>
                            <button @click="handleShowLogs(app)" class="btn btn-secondary btn-sm p-2" title="View App Logs">
                                <IconCode class="w-5 h-5" />
                            </button>
                            <button v-if="app.status !== 'running'" @click="handleAppAction(app.id, 'start')" class="btn btn-success btn-sm p-2" title="Start App">
                                <IconPlayCircle class="w-5 h-5" />
                            </button>
                             <button v-if="app.status === 'running'" @click="handleAppAction(app.id, 'stop')" class="btn btn-warning btn-sm p-2" :disabled="isLoadingAction === `stop-${app.id}`" title="Stop App">
                                <IconStopCircle class="w-5 h-5" />
                            </button>
                            <button @click="handleUninstallApp(app)" class="btn btn-danger btn-sm p-2" title="Uninstall App">
                                <IconTrash class="w-5 h-5" />
                            </button>
                        </template>
                    </div>
                 </div>
            </div>
        </section>
    </div>
</template>