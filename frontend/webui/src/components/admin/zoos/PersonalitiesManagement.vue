<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useTasksStore } from '../../../stores/tasks';
import { useUiStore } from '../../../stores/ui';
import { useDataStore } from '../../../stores/data';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import AppCard from '../../ui/AppCard.vue';
import AppCardSkeleton from '../../ui/AppCardSkeleton.vue';

const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();
const dataStore = useDataStore();

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
const searchQuery = ref('');
const selectedCategory = ref('All');
const installationStatusFilter = ref('All');
const selectedRepository = ref('All');
const sortKey = ref('name');
const sortOrder = ref('asc');
const starredItems = ref(JSON.parse(localStorage.getItem('starredPersonalities') || '[]'));
const currentPage = ref(1);
const pageSize = ref(24);
let debounceTimer = null;

const sortOptions = [
    { value: 'name', label: 'Name' }, { value: 'author', label: 'Author' },
    { value: 'last_update_date', label: 'Last Updated' }, { value: 'creation_date', label: 'Creation Date' },
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
    const params = {
        page: currentPage.value, page_size: pageSize.value, sort_by: sortKey.value,
        sort_order: sortOrder.value, 
        category: selectedCategory.value !== 'All' && selectedCategory.value !== 'Starred' ? selectedCategory.value : undefined,
        repository: selectedRepository.value !== 'All' ? selectedRepository.value : undefined,
        search_query: searchQuery.value || undefined, 
        installation_status: installationStatusFilter.value !== 'All' ? installationStatusFilter.value : undefined,
    };
    if (selectedCategory.value === 'Starred') {
        params.starred_names = starredItems.value;
    }
    await adminStore.fetchZooPersonalities(params);
}

const itemsWithTaskStatus = computed(() => {
    const taskMap = new Map();
    (tasks.value || []).forEach(task => { 
        if (task?.name?.startsWith('Installing personality: ') && (task.status === 'running' || task.status === 'pending')) { 
            const itemName = task.name.replace('Installing personality: ', ''); 
            taskMap.set(itemName, task); 
        } 
    });
    return (zooPersonalities.value.items || []).map(item => ({ ...item, task: taskMap.get(item.folder_name) || null }));
});

function debouncedFetch() { clearTimeout(debounceTimer); debounceTimer = setTimeout(() => { currentPage.value = 1; fetchZooItems(); }, 300); }
watch([sortKey, sortOrder, selectedCategory, installationStatusFilter, selectedRepository], () => { currentPage.value = 1; fetchZooItems(); });
watch(searchQuery, debouncedFetch);
watch(currentPage, fetchZooItems);
watch(starredItems, (newStarred) => { localStorage.setItem('starredPersonalities', JSON.stringify(newStarred)); if (selectedCategory.value === 'Starred') { currentPage.value = 1; fetchZooItems(); } }, { deep: true });

onMounted(() => {
    dataStore.fetchPersonalities();
    adminStore.fetchPersonalityZooRepositories();
    fetchZooItems();
});

const sortedRepositories = computed(() => [...(personalityZooRepositories.value || [])].sort((a, b) => (a.name || '').localeCompare(b.name || '')));
const categories = computed(() => ['All', 'Starred', ...(zooPersonalities.value.categories || [])]);

function formatDateTime(isoString) { if (!isoString) return 'Never'; return new Date(isoString).toLocaleString(); }
async function handleAddRepository() {
    if (!newRepo.value.name) { uiStore.addNotification('Repository name is required.', 'warning'); return; }
    const payload = { name: newRepo.value.name };
    if (newRepo.value.type === 'git') payload.url = newRepo.value.url; else payload.path = newRepo.value.path;
    isLoadingAction.value = 'add';
    try { await adminStore.addPersonalityZooRepository(payload); newRepo.value = { type: 'git', name: '', url: '', path: '' }; isAddRepoFormVisible.value = false; }
    finally { isLoadingAction.value = null; }
}
async function handlePullRepository(repo) { isLoadingAction.value = repo.id; try { await adminStore.pullPersonalityZooRepository(repo.id); } finally { isLoadingAction.value = null; } }
async function handleDeleteRepository(repo) {
    if (await uiStore.showConfirmation({ title: `Delete Repository '${repo.name}'?` })) {
        isLoadingAction.value = repo.id;
        try { await adminStore.deletePersonalityZooRepository(repo.id); } finally { isLoadingAction.value = null; }
    }
}
async function handleInstallItem(item) { await adminStore.installZooPersonality({ repository: item.repository, folder_name: item.folder_name }); }
async function handleUninstallItem(personality) {
    const installed = publicPersonalities.value.find(p => p.name === personality.name && p.owner_username === 'System');
    if (!installed) return;
    if (await uiStore.showConfirmation({ title: `Uninstall '${personality.name}'?` })) {
        await dataStore.deletePersonality(installed.id);
        await fetchZooItems();
    }
}
async function showItemHelp(item) { const readme = await adminStore.fetchPersonalityReadme(item.repository, item.folder_name); uiStore.openModal('sourceViewer', { title: `README: ${item.name}`, content: readme, language: 'markdown' }); }
function handleStarToggle(itemName) { const i = starredItems.value.indexOf(itemName); if (i > -1) starredItems.value.splice(i, 1); else starredItems.value.push(itemName); }
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
            <nav class="-mb-px flex space-x-6">
                <button @click="activeSubTab = 'zoo'" :class="['tab-button', activeSubTab === 'zoo' ? 'active' : 'inactive']">Zoo</button>
                <button @click="activeSubTab = 'source'" :class="['tab-button', activeSubTab === 'source' ? 'active' : 'inactive']">Repositories</button>
            </nav>
        </div>

        <section v-if="activeSubTab === 'zoo'">
            <h3 class="text-xl font-semibold mb-4">Personality Zoo</h3>
            <div class="space-y-4">
                <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
                    <div class="relative lg:col-span-1"><input v-model="searchQuery" type="text" placeholder="Search Personalities..." class="input-field w-full pl-10" /><div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"><svg class="h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg></div></div>
                    <div class="grid grid-cols-1 sm:grid-cols-3 lg:col-span-3 gap-4">
                        <select v-model="installationStatusFilter" class="input-field"><option value="All">All Statuses</option><option value="Installed">Installed</option><option value="Uninstalled">Uninstalled</option></select>
                        <select v-model="selectedCategory" class="input-field"><option v-for="c in categories" :key="c" :value="c">{{ c }}</option></select>
                        <select v-model="selectedRepository" class="input-field"><option value="All">All Sources</option><option v-for="repo in sortedRepositories" :key="repo.id" :value="repo.name">{{ repo.name }}</option></select>
                    </div>
                </div>

                <div v-if="isLoadingZooPersonalities" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6"><AppCardSkeleton v-for="i in 8" :key="i"/></div>
                <div v-else-if="itemsWithTaskStatus.length === 0" class="empty-state-card"><p>No personalities found.</p></div>
                <div v-else>
                    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
                        <AppCard v-for="item in itemsWithTaskStatus" :key="`${item.repository}/${item.folder_name}`" :app="item" :task="item.task" :is-starred="starredItems.includes(item.name)" item-type-name="Personality" @star="handleStarToggle(item.name)" @install="handleInstallItem" @uninstall="handleUninstallItem" @help="showItemHelp" />
                    </div>
                    <div v-if="totalPages > 1" class="flex justify-between items-center mt-6">
                        <button @click="currentPage--" :disabled="currentPage === 1" class="btn btn-secondary">Previous</button>
                        <span class="text-sm text-gray-600 dark:text-gray-400">{{ pageInfo }}</span>
                        <button @click="currentPage++" :disabled="currentPage >= totalPages" class="btn btn-secondary">Next</button>
                    </div>
                </div>
            </div>
        </section>

        <section v-if="activeSubTab === 'source'">
             <div class="flex justify-between items-center mb-4"><h3 class="text-xl font-semibold">Personality Zoo Repositories</h3><button @click="isAddRepoFormVisible = !isAddRepoFormVisible" class="btn btn-primary">{{ isAddRepoFormVisible ? 'Cancel' : 'Add Repository' }}</button></div>
             <div v-if="isAddRepoFormVisible" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm mb-6"><form @submit.prevent="handleAddRepository" class="space-y-4"><div class="flex items-center gap-x-4"><label><input type="radio" v-model="newRepo.type" value="git" class="radio-input"> Git</label><label><input type="radio" v-model="newRepo.type" value="local" class="radio-input"> Local</label></div><div><label>Name</label><input v-model="newRepo.name" type="text" class="input-field" required></div><div v-if="newRepo.type === 'git'"><label>URL</label><input v-model="newRepo.url" type="url" class="input-field" :required="newRepo.type==='git'"></div><div v-if="newRepo.type === 'local'"><label>Path</label><input v-model="newRepo.path" type="text" class="input-field" :required="newRepo.type==='local'"></div><div class="flex justify-end"><button type="submit" class="btn btn-primary">Add</button></div></form></div>
             <div v-if="isLoadingPersonalityZooRepositories" class="text-center p-4">Loading...</div>
             <div v-else-if="sortedRepositories.length === 0" class="empty-state-card"><p>No repositories added.</p></div>
             <div v-else class="space-y-4"><div v-for="repo in sortedRepositories" :key="repo.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex items-center justify-between"><div><p class="font-semibold">{{ repo.name }}</p><p class="text-sm text-gray-500">{{ repo.url }}</p><p class="text-xs text-gray-400">Pulled: {{ formatDateTime(repo.last_pulled_at) }}</p></div><div class="flex items-center gap-2"><button @click="handlePullRepository(repo)" class="btn btn-secondary btn-sm"><IconRefresh class="w-4 h-4 mr-1"/>{{ repo.type === 'git' ? 'Pull' : 'Rescan' }}</button><button v-if="repo.is_deletable" @click="handleDeleteRepository(repo)" class="btn btn-danger btn-sm"><IconTrash class="w-4 h-4"/></button></div></div></div>
        </section>
    </div>
</template>
