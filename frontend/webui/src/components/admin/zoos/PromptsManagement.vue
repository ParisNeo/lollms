<script setup>
import { ref, onMounted, computed, watch, onUnmounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../../stores/admin';
import { useTasksStore } from '../../../stores/tasks';
import { useUiStore } from '../../../stores/ui';
import { usePromptsStore } from '../../../stores/prompts';
import useEventBus from '../../../services/eventBus';
import IconRefresh from '../../../assets/icons/IconRefresh.vue';
import IconTrash from '../../../assets/icons/IconTrash.vue';
import PromptCard from '../../ui/PromptCard.vue';
import AppCardSkeleton from '../../ui/AppCardSkeleton.vue';
import IconSparkles from '../../../assets/icons/IconSparkles.vue';
import IconArrowDown from '../../../assets/icons/IconArrowDown.vue';
import IconArrowUp from '../../../assets/icons/IconArrowUp.vue';

const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();
const promptsStore = usePromptsStore();
const { on, off } = useEventBus();

const { promptFilters } = adminStore;
const { promptZooRepositories, isLoadingPromptZooRepositories, zooPrompts, isLoadingZooPrompts } = storeToRefs(adminStore);
const { systemPrompts: installedPrompts, isLoading: isLoadingInstalled } = storeToRefs(promptsStore);
const { tasks } = storeToRefs(tasksStore);

const activeSubTab = ref('zoo');
const newRepo = ref({ type: 'git', name: '', url: '', path: '' });
const isAddRepoFormVisible = ref(false);
const isLoadingAction = ref(null);
const starredItems = ref(JSON.parse(localStorage.getItem('starredPrompts') || '[]'));
let debounceTimer = null;
const pendingGenerationTaskId = ref(null);

const currentPage = computed({
  get: () => promptFilters.currentPage,
  set: (val) => { promptFilters.currentPage = val; }
});

const totalItems = computed(() => zooPrompts.value.total || 0);
const totalPages = computed(() => zooPrompts.value.pages || 1);
const pageInfo = computed(() => {
    if (totalItems.value === 0) return 'Showing 0-0 of 0';
    const start = (promptFilters.currentPage - 1) * promptFilters.pageSize + 1;
    const end = Math.min(promptFilters.currentPage * promptFilters.pageSize, totalItems.value);
    return `Showing ${start}-${end} of ${totalItems.value}`;
});

async function fetchZooItems() {
    const params = {
        page: promptFilters.currentPage, page_size: promptFilters.pageSize, sort_by: promptFilters.sortKey,
        sort_order: promptFilters.sortOrder, 
        category: promptFilters.selectedCategory !== 'All' ? promptFilters.selectedCategory : undefined,
        repository: promptFilters.selectedRepository !== 'All' ? promptFilters.selectedRepository : undefined,
        search_query: promptFilters.searchQuery || undefined, 
        installation_status: promptFilters.installationStatusFilter !== 'All' ? promptFilters.installationStatusFilter : undefined,
    };
    await adminStore.fetchZooPrompts(params);
}

const itemsWithTaskStatus = computed(() => {
    const taskMap = new Map();
    (tasks.value || []).forEach(task => { 
        if (task?.name?.startsWith('Installing prompt: ') && (task.status === 'running' || task.status === 'pending')) { 
            const itemName = task.name.replace('Installing prompt: ', ''); 
            taskMap.set(itemName, task); 
        } 
    });
    return (zooPrompts.value.items || []).map(item => ({ ...item, task: taskMap.get(item.folder_name) || null }));
});

function debouncedFetch() { clearTimeout(debounceTimer); debounceTimer = setTimeout(() => { if (promptFilters.currentPage !== 1) promptFilters.currentPage = 1; else fetchZooItems(); }, 300); }
watch(() => [promptFilters.sortKey, promptFilters.sortOrder, promptFilters.selectedCategory, promptFilters.installationStatusFilter, promptFilters.selectedRepository], () => { if (promptFilters.currentPage !== 1) promptFilters.currentPage = 1; else fetchZooItems(); });
watch(() => promptFilters.searchQuery, debouncedFetch);
watch(() => promptFilters.currentPage, fetchZooItems);
watch(starredItems, (newStarred) => { localStorage.setItem('starredPrompts', JSON.stringify(newStarred)); }, { deep: true });

onMounted(() => {
    promptsStore.fetchPrompts();
    adminStore.fetchPromptZooRepositories();
    fetchZooItems();
    on('task:completed', handleTaskCompletion);
});

onUnmounted(() => {
    off('task:completed', handleTaskCompletion);
});


const sortedRepositories = computed(() => Array.isArray(promptZooRepositories.value) ? [...promptZooRepositories.value].sort((a, b) => (a.name || '').localeCompare(b.name || '')) : []);
const categories = computed(() => ['All', 'Starred', ...(zooPrompts.value.categories || [])]);

const sortOptions = [
    { value: 'name', label: 'Name' }, { value: 'author', label: 'Author' },
    { value: 'last_update_date', label: 'Last Updated' }, { value: 'creation_date', label: 'Creation Date' },
];

function formatDateTime(isoString) { if (!isoString) return 'Never'; return new Date(isoString).toLocaleString(); }
async function handleAddRepository() {
    if (!newRepo.value.name) { uiStore.addNotification('Repository name is required.', 'warning'); return; }
    const payload = { name: newRepo.value.name };
    if (newRepo.value.type === 'git') payload.url = newRepo.value.url; else payload.path = newRepo.value.path;
    isLoadingAction.value = 'add';
    try { await adminStore.addPromptZooRepository(payload); newRepo.value = { type: 'git', name: '', url: '', path: '' }; isAddRepoFormVisible.value = false; }
    finally { isLoadingAction.value = null; }
}
async function handlePullRepository(repo) { isLoadingAction.value = repo.id; try { await adminStore.pullPromptZooRepository(repo.id); } finally { isLoadingAction.value = null; } }
async function handleDeleteRepository(repo) {
    if (await uiStore.showConfirmation({ title: `Delete Repository '${repo.name}'?` })) {
        isLoadingAction.value = repo.id;
        try { await adminStore.deletePromptZooRepository(repo.id); } finally { isLoadingAction.value = null; }
    }
}
async function handleInstallItem(item) { await adminStore.installZooPrompt({ repository: item.repository, folder_name: item.folder_name }); }
async function handleUninstallItem(item) {
    const installed = installedPrompts.value.find(p => p.name === item.name);
    if (!installed) return;
    if (await uiStore.showConfirmation({ title: `Uninstall '${item.name}'?`, message: 'This will remove the prompt from the system.' })) {
        await adminStore.deleteSystemPrompt(installed.id);
        await fetchZooItems();
    }
}
async function showItemHelp(item) { const readme = await adminStore.fetchPromptReadme(item.repository, item.folder_name); uiStore.openModal('sourceViewer', { title: `README: ${item.name}`, content: readme, language: 'markdown' }); }
function handleStarToggle(itemName) { const i = starredItems.value.indexOf(itemName); if (i > -1) starredItems.value.splice(i, 1); else starredItems.value.push(itemName); }
function handleGeneratePrompt() { uiStore.openModal('generatePrompt', { isSystemPrompt: true, onTaskSubmitted: (taskId) => { pendingGenerationTaskId.value = taskId; } }); }
function handleTaskCompletion(task) { if (task && task.id === pendingGenerationTaskId.value) { pendingGenerationTaskId.value = null; if (uiStore.isModalOpen('tasksManager')) uiStore.closeModal('tasksManager'); if (task.status === 'completed' && task.result) { handleEditPrompt(task.result); } else { uiStore.addNotification('Prompt generation did not complete successfully.', 'warning'); } } }
async function handleUpdatePrompt(prompt) { 
    const installed = installedPrompts.value.find(p => p.name === prompt.name);
    if (installed) await adminStore.updateSystemPromptFromZoo(installed.id); 
}

function handleEditPrompt(prompt) {
    uiStore.openModal('editPrompt', { prompt: { ...prompt }, isSystemPrompt: true });
}

async function handleRefreshCache() {
    const task = await adminStore.refreshZooCache();
    if (task) {
        uiStore.openModal('tasksManager', { initialTaskId: task.id });
    }
}
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
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-xl font-semibold">Prompts Zoo</h3>
                <div class="flex gap-2">
                    <button @click="handleRefreshCache" class="btn btn-secondary" title="Refresh Zoo Cache from all sources">
                        <IconRefresh class="w-4 h-4" />
                    </button>
                    <button @click="handleGeneratePrompt" class="btn btn-secondary">
                        <IconSparkles class="w-4 h-4 mr-2" /> Generate with AI
                    </button>
                    <button @click="handleEditPrompt({})" class="btn btn-primary">Create New Prompt</button>
                </div>
            </div>
            <div class="space-y-4">
                <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
                    <div class="relative lg:col-span-1"><input v-model="promptFilters.searchQuery" type="text" placeholder="Search Prompts..." class="input-field w-full pl-10" /><div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"><svg class="h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg></div></div>
                    <div class="grid grid-cols-1 sm:grid-cols-3 lg:col-span-3 gap-4">
                        <select v-model="promptFilters.installationStatusFilter" class="input-field"><option value="All">All Statuses</option><option value="Installed">Installed</option><option value="Uninstalled">Uninstalled</option></select>
                        <select v-model="promptFilters.selectedCategory" class="input-field"><option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option></select>
                        <select v-model="promptFilters.selectedRepository" class="input-field"><option value="All">All Sources</option><option v-for="repo in sortedRepositories" :key="repo.id" :value="repo.name">{{ repo.name }}</option></select>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <select v-model="promptFilters.sortKey" class="input-field w-48">
                        <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">Sort by {{ opt.label }}</option>
                    </select>
                    <button @click="promptFilters.sortOrder = promptFilters.sortOrder === 'asc' ? 'desc' : 'asc'" class="btn btn-secondary p-2">
                        <IconArrowUp v-if="promptFilters.sortOrder === 'asc'" class="w-5 h-5" />
                        <IconArrowDown v-else class="w-5 h-5" />
                    </button>
                </div>
                
                <div v-if="isLoadingZooPrompts || isLoadingInstalled" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"><AppCardSkeleton v-for="i in 6" :key="i" /></div>
                <div v-else-if="itemsWithTaskStatus.length === 0" class="empty-state-card"><h4 class="font-semibold">No Prompts Found</h4></div>
                <div v-else>
                    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                        <PromptCard v-for="item in itemsWithTaskStatus" :key="item.id || `${item.repository}/${item.folder_name}`" :prompt="item" :task="item.task" :is-starred="starredItems.includes(item.name)" @star="handleStarToggle(item.name)" @install="handleInstallItem" @uninstall="handleUninstallItem" @help="showItemHelp" @update="handleUpdatePrompt(item)" @edit="handleEditPrompt(item)" />
                    </div>
                    <div v-if="totalPages > 1" class="flex justify-between items-center mt-6"><button @click="currentPage--" :disabled="currentPage === 1" class="btn btn-secondary">Previous</button><span class="text-sm text-gray-600 dark:text-gray-400">{{ pageInfo }}</span><button @click="currentPage++" :disabled="currentPage >= totalPages" class="btn btn-secondary">Next</button></div>
                </div>
            </div>
        </section>
        
        <section v-if="activeSubTab === 'source'">
             <div class="flex justify-between items-center mb-4"><h3 class="text-xl font-semibold">Prompt Zoo Repositories</h3><button @click="isAddRepoFormVisible = !isAddRepoFormVisible" class="btn btn-primary">{{ isAddRepoFormVisible ? 'Cancel' : 'Add' }}</button></div>
             <div v-if="isAddRepoFormVisible" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm mb-6"><form @submit.prevent="handleAddRepository" class="space-y-4"><div class="flex items-center gap-x-4"><label><input type="radio" v-model="newRepo.type" value="git" class="radio-input"> Git</label><label><input type="radio" v-model="newRepo.type" value="local" class="radio-input"> Local</label></div><div><label>Name</label><input v-model="newRepo.name" type="text" class="input-field" required></div><div v-if="newRepo.type === 'git'"><label>URL</label><input v-model="newRepo.url" type="url" class="input-field" :required="newRepo.type==='git'"></div><div v-if="newRepo.type === 'local'"><label>Path</label><input v-model="newRepo.path" type="text" class="input-field" :required="newRepo.type==='local'"></div><div class="flex justify-end"><button type="submit" class="btn btn-primary">Add</button></div></form></div>
             <div v-if="isLoadingPromptZooRepositories" class="text-center p-4">Loading...</div>
             <div v-else-if="!sortedRepositories || sortedRepositories.length === 0" class="empty-state-card"><p>No repositories added.</p></div>
             <div v-else class="space-y-4"><div v-for="repo in sortedRepositories" :key="repo.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex items-center justify-between"><div><p class="font-semibold">{{ repo.name }}</p><p class="text-sm text-gray-500">{{ repo.url }}</p><p class="text-xs text-gray-400">Pulled: {{ formatDateTime(repo.last_pulled_at) }}</p></div><div class="flex items-center gap-2"><button @click="handlePullRepository(repo)" class="btn btn-secondary btn-sm"><IconRefresh class="w-4 h-4 mr-1"/>{{ repo.type === 'git' ? 'Pull' : 'Rescan' }}</button><button v-if="repo.is_deletable" @click="handleDeleteRepository(repo)" class="btn btn-danger btn-sm"><IconTrash class="w-4 h-4"/></button></div></div></div>
        </section>
    </div>
</template>