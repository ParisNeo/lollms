<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useTasksStore } from '../../../stores/tasks';
import { useUiStore } from '../../../stores/ui';
import { useDataStore } from '../../../stores/data';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import IconArrowUp from '../../../assets/icons/IconArrowUp.vue';
import IconArrowDown from '../../../assets/icons/IconArrowDown.vue';
import IconPlus from '../../../assets/icons/IconPlus.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import AppCard from '../../ui/Cards/AppCard.vue';
import AppCardSkeleton from '../../ui/Cards/AppCardSkeleton.vue';

const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

const { personalityFilters } = adminStore;
const { 
    personalityZooRepositories, isLoadingPersonalityZooRepositories, 
    zooPersonalities, isLoadingZooPersonalities 
} = storeToRefs(adminStore);
const { publicPersonalities } = storeToRefs(dataStore);
const { tasks } = storeToRefs(tasksStore);

const activeSubTab = ref('zoo');
const newRepo = ref({ type: 'git', name: '', url: '', path: '' });
const isAddRepoFormVisible = ref(false);
const isLoadingAction = ref(null);
const isRefreshingCache = ref(false);

const searchQuery = computed({
  get: () => personalityFilters.searchQuery,
  set: (val) => { personalityFilters.searchQuery = val; }
});
const selectedCategory = computed({
  get: () => personalityFilters.selectedCategory,
  set: (val) => { personalityFilters.selectedCategory = val; }
});
const installationStatusFilter = computed({
  get: () => personalityFilters.installationStatusFilter,
  set: (val) => { personalityFilters.installationStatusFilter = val; }
});
const selectedRepository = computed({
  get: () => personalityFilters.selectedRepository,
  set: (val) => { personalityFilters.selectedRepository = val; }
});
const sortKey = computed({
  get: () => personalityFilters.sortKey,
  set: (val) => { personalityFilters.sortKey = val; }
});
const sortOrder = computed({
  get: () => personalityFilters.sortOrder,
  set: (val) => { personalityFilters.sortOrder = val; }
});
const currentPage = computed({
  get: () => personalityFilters.currentPage,
  set: (val) => { personalityFilters.currentPage = val; }
});
const pageSize = computed({
  get: () => personalityFilters.pageSize,
  set: (val) => { personalityFilters.pageSize = val; }
});

const starredItems = ref(JSON.parse(localStorage.getItem('starredPersonalities') || '[]'));
let debounceTimer = null;

const sortOptions = [
    { value: 'name', label: 'Name' }, 
    { value: 'author', label: 'Author' },
    { value: 'last_update_date', label: 'Last Updated' }, 
    { value: 'creation_date', label: 'Creation Date' },
];

const totalItems = computed(() => zooPersonalities.value.total || 0);
const totalPages = computed(() => zooPersonalities.value.pages || 1);
const pageInfo = computed(() => {
    if (totalItems.value === 0) return 'Showing 0-0 of 0';
    const start = (currentPage.value - 1) * pageSize.value + 1;
    const end = Math.min(currentPage.value * pageSize.value, totalItems.value);
    return `Showing ${start}-${end} of ${totalItems.value}`;
});

async function fetchZooItems() {
    await adminStore.fetchZooPersonalities();
}

const itemsWithTaskStatus = computed(() => {
    const taskMap = new Map();
    (tasks.value || []).forEach(task => { 
        if (task?.name?.startsWith('Installing personality: ') && (task.status === 'running' || task.status === 'pending')) { 
            const itemName = task.name.replace('Installing personality: ', ''); 
            taskMap.set(itemName, task); 
        } 
    });
    return (zooPersonalities.value.items || []).map(item => ({ 
        ...item, 
        task: taskMap.get(item.folder_name) || null 
    }));
});

function debouncedFetch() { 
    clearTimeout(debounceTimer); 
    debounceTimer = setTimeout(() => { 
        currentPage.value = 1; 
        fetchZooItems(); 
    }, 300); 
}

function clearSearch() {
    searchQuery.value = '';
    debouncedFetch();
}

function selectCategory(cat) {
    selectedCategory.value = cat;
    currentPage.value = 1;
    fetchZooItems();
}

watch([sortKey, sortOrder, selectedCategory, installationStatusFilter, selectedRepository], () => { 
    currentPage.value = 1; 
    fetchZooItems(); 
});
watch(searchQuery, debouncedFetch);
watch(currentPage, fetchZooItems);
watch(starredItems, (newStarred) => { 
    localStorage.setItem('starredPersonalities', JSON.stringify(newStarred)); 
    if (selectedCategory.value === 'Starred') { 
        currentPage.value = 1; 
        fetchZooItems(); 
    } 
}, { deep: true });

onMounted(() => {
    dataStore.fetchPersonalities();
    adminStore.fetchPersonalityZooRepositories();
    fetchZooItems();
});

const sortedRepositories = computed(() => [...(personalityZooRepositories.value || [])].sort((a, b) => (a.name || '').localeCompare(b.name || '')));
const categories = computed(() => ['All', 'Starred', ...(zooPersonalities.value.categories || [])]);

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
        await adminStore.addPersonalityZooRepository(payload); 
        newRepo.value = { type: 'git', name: '', url: '', path: '' }; 
        isAddRepoFormVisible.value = false; 
    }
    finally { isLoadingAction.value = null; }
}

async function handlePullRepository(repo) { 
    isLoadingAction.value = repo.id; 
    try { await adminStore.pullPersonalityZooRepository(repo.id); } 
    finally { isLoadingAction.value = null; } 
}

async function handleDeleteRepository(repo) {
    if (await uiStore.showConfirmation({ title: `Delete Repository '${repo.name}'?` })) {
        isLoadingAction.value = repo.id;
        try { await adminStore.deletePersonalityZooRepository(repo.id); } 
        finally { isLoadingAction.value = null; }
    }
}

async function handleInstallItem(item) { 
    await adminStore.installZooPersonality({ repository: item.repository, folder_name: item.folder_name }); 
}

async function handleUninstallItem(personality) {
    const installed = publicPersonalities.value.find(p => p.name === personality.name && p.owner_username === 'System');
    if (!installed) return;
    if (await uiStore.showConfirmation({ title: `Uninstall '${personality.name}'?` })) {
        await dataStore.deletePersonality(installed.id);
        await fetchZooItems();
    }
}

async function showItemHelp(item) { 
    const readme = await adminStore.fetchPersonalityReadme(item.repository, item.folder_name); 
    uiStore.openModal('sourceViewer', { title: `README: ${item.name}`, content: readme, language: 'markdown' }); 
}

function handleStarToggle(itemName) { 
    const i = starredItems.value.indexOf(itemName); 
    if (i > -1) starredItems.value.splice(i, 1); 
    else starredItems.value.push(itemName); 
}

function openEditor(personality = null) {
    uiStore.openModal('personalityEditor', { personality });
}

function openGeneratePersonalityModal() {
    uiStore.openModal('generatePersonality');
}

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
                    Personality Zoo Catalog
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

        <!-- TAB 1: PERSONALITY ZOO -->
        <section v-if="activeSubTab === 'zoo'" class="space-y-5">
            <!-- Action & Header -->
            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-white/60 dark:bg-gray-850/50 p-4 rounded-2xl border border-gray-200/80 dark:border-gray-700/60 backdrop-blur-md">
                <div>
                    <h3 class="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                        <span>Personalities Zoo</span>
                        <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300">
                            {{ totalItems }} Available
                        </span>
                    </h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Explore tailored AI personas with specialized conditionings, scripts, and capabilities.</p>
                </div>

                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <button @click="openGeneratePersonalityModal" class="btn btn-secondary btn-sm flex-1 sm:flex-none justify-center">
                        <IconSparkles class="w-3.5 h-3.5 mr-1" />Generate with AI
                    </button>
                    <button @click="openEditor()" class="btn btn-primary btn-sm flex-1 sm:flex-none justify-center">
                        <IconPlus class="w-3.5 h-3.5 mr-1"/>Create New
                    </button>
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
                            placeholder="Search personalities by title, author, or specialty..." 
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
                    <select v-model="installationStatusFilter" class="input-field text-xs py-2 rounded-xl">
                        <option value="All">All Statuses</option>
                        <option value="Installed">Installed Only</option>
                        <option value="Uninstalled">Uninstalled Only</option>
                    </select>

                    <!-- Repository Filter -->
                    <select v-model="selectedRepository" class="input-field text-xs py-2 rounded-xl">
                        <option value="All">All Sources</option>
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

            <!-- Personalities Grid -->
            <div v-if="isLoadingZooPersonalities" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-5">
                <AppCardSkeleton v-for="i in 8" :key="i" />
            </div>

            <div v-else-if="itemsWithTaskStatus.length === 0" class="text-center py-16 px-4 rounded-2xl bg-white/50 dark:bg-gray-800/40 border border-gray-200/80 dark:border-gray-700/60">
                <div class="w-12 h-12 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center mx-auto mb-3 text-gray-400">
                    <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                </div>
                <h4 class="font-bold text-sm text-gray-800 dark:text-gray-200">No Personalities Found</h4>
                <p class="text-xs text-gray-500 mt-1 max-w-sm mx-auto">No AI personalities match your active filters. Try searching for a different keyword or category.</p>
                <button 
                    v-if="searchQuery || selectedCategory !== 'All' || installationStatusFilter !== 'All'"
                    @click="searchQuery = ''; selectedCategory = 'All'; installationStatusFilter = 'All'; fetchZooItems();"
                    class="btn btn-secondary btn-sm mt-4"
                >
                    Reset Filters
                </button>
            </div>

            <div v-else class="space-y-6">
                <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-5">
                    <AppCard 
                        v-for="item in itemsWithTaskStatus" 
                        :key="`${item.repository}/${item.folder_name}`" 
                        :app="item" 
                        :task="item.task" 
                        :is-starred="starredItems.includes(item.name)" 
                        item-type-name="Personality" 
                        @star="handleStarToggle(item.name)" 
                        @install="handleInstallItem" 
                        @uninstall="handleUninstallItem" 
                        @help="showItemHelp" 
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
                    <h3 class="text-lg font-bold text-gray-900 dark:text-white">Personality Zoo Repositories</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Repositories hosting personality conditioning prompts and configurations.</p>
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
                        <input v-model="newRepo.name" type="text" class="input-field" placeholder="e.g. Official Personalities" required>
                    </div>

                    <div v-if="newRepo.type === 'git'">
                        <label class="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Git Clone URL</label>
                        <input v-model="newRepo.url" type="url" class="input-field" placeholder="https://github.com/user/personalities-zoo.git" :required="newRepo.type === 'git'">
                    </div>

                    <div v-if="newRepo.type === 'local'">
                        <label class="block text-xs font-semibold text-gray-700 dark:text-gray-300 mb-1">Local Directory Absolute Path</label>
                        <input v-model="newRepo.path" type="text" class="input-field" placeholder="/path/to/personalities" :required="newRepo.type === 'local'">
                    </div>

                    <div class="flex justify-end gap-2 pt-2 border-t dark:border-gray-700">
                        <button type="button" @click="isAddRepoFormVisible = false" class="btn btn-secondary btn-sm">Cancel</button>
                        <button type="submit" class="btn btn-primary btn-sm">Save Repository</button>
                    </div>
                </form>
            </div>

            <!-- Repositories List -->
            <div v-if="isLoadingPersonalityZooRepositories" class="text-center py-8 text-sm text-gray-500">Loading repositories...</div>
            <div v-else-if="sortedRepositories.length === 0" class="text-center py-12 rounded-2xl bg-gray-50 dark:bg-gray-800/50 text-gray-500">
                <p class="text-sm">No personality repositories added.</p>
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