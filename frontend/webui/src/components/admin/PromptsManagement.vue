<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import { usePromptsStore } from '../../stores/prompts';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import AppCard from '../ui/AppCard.vue';
import AppCardSkeleton from '../ui/AppCardSkeleton.vue';
import TaskProgressIndicator from '../ui/TaskProgressIndicator.vue';

const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();
const promptsStore = usePromptsStore();

const { 
    promptZooRepositories, isLoadingPromptZooRepositories, zooPrompts, isLoadingZooPrompts
} = storeToRefs(adminStore);
const { systemPrompts: installedPrompts, isLoading: isLoadingInstalled } = storeToRefs(promptsStore);
const { tasks } = storeToRefs(tasksStore);

const activeSubTab = ref('installed');

// --- Repositories Tab State ---
const newRepo = ref({ name: '', url: '' });
const isAddRepoFormVisible = ref(false);
const isLoadingAction = ref(null);
const isPullingAll = ref(false);

// --- Available Tab State ---
const searchQuery = ref('');
const selectedCategory = ref('All');
const installationStatusFilter = ref('All');
const sortKey = ref('last_update_date');
const sortOrder = ref('desc');
const starredItems = ref(JSON.parse(localStorage.getItem('starredPrompts') || '[]'));
const currentPage = ref(1);
const pageSize = ref(24);
let debounceTimer = null;

const sortOptions = [
    { value: 'last_update_date', label: 'Last Updated' }, { value: 'creation_date', label: 'Creation Date' },
    { value: 'name', label: 'Name' }, { value: 'author', label: 'Author' },
];

const totalItems = computed(() => zooPrompts.value.total || 0);
const totalPages = computed(() => zooPrompts.value.pages || 1);
const pageInfo = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value + 1;
    const end = Math.min(currentPage.value * pageSize.value, totalItems.value);
    return `Showing ${start}-${end} of ${totalItems.value}`;
});

async function fetchZooItems() {
    const params = {
        page: currentPage.value, page_size: pageSize.value, sort_by: sortKey.value,
        sort_order: sortOrder.value, category: selectedCategory.value !== 'All' ? selectedCategory.value : undefined,
        search_query: searchQuery.value || undefined, installation_status: installationStatusFilter.value !== 'All' ? installationStatusFilter.value : undefined,
    };
    await adminStore.fetchZooPrompts(params);
}

function debouncedFetch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => { currentPage.value = 1; fetchZooItems(); }, 300);
}

watch([sortKey, sortOrder, selectedCategory, installationStatusFilter], () => { currentPage.value = 1; fetchZooItems(); });
watch(searchQuery, debouncedFetch);
watch(currentPage, fetchZooItems);
watch(starredItems, (newStarred) => { localStorage.setItem('starredPrompts', JSON.stringify(newStarred)); }, { deep: true });

onMounted(() => {
    promptsStore.fetchPrompts(); // For installed prompts
    adminStore.fetchPromptZooRepositories();
    fetchZooItems();
});

const itemsWithTaskStatus = computed(() => {
    if (!Array.isArray(zooPrompts.value.items)) return [];
    let items = zooPrompts.value.items;
    
    const taskMap = new Map();
    // No tasks for prompts yet, but keep structure for future
    return items.map(item => ({ ...item, task: taskMap.get(item.folder_name) || null }));
});

const sortedRepositories = computed(() => Array.isArray(promptZooRepositories.value) ? [...promptZooRepositories.value].sort((a, b) => (a.name || '').localeCompare(b.name || '')) : []);
const categories = computed(() => ['All', ...adminStore.zooPrompts.categories]);

function handleStarToggle(itemName) {
    const index = starredItems.value.indexOf(itemName);
    if (index > -1) starredItems.value.splice(index, 1);
    else starredItems.value.push(itemName);
}

function formatDateTime(isoString) { if (!isoString) return 'Never'; return new Date(isoString).toLocaleString(); }

// --- Repository Actions ---
async function handleAddRepository() {
    if (!newRepo.value.name || !newRepo.value.url) { uiStore.addNotification('Repository name and URL are required.', 'warning'); return; }
    isLoadingAction.value = 'add';
    try {
        await adminStore.addPromptZooRepository(newRepo.value.name, newRepo.value.url);
        newRepo.value = { name: '', url: '' };
        isAddRepoFormVisible.value = false;
    } finally { isLoadingAction.value = null; }
}
async function handlePullRepository(repo) {
    isLoadingAction.value = repo.id;
    try { await adminStore.pullPromptZooRepository(repo.id); } 
    finally { isLoadingAction.value = null; }
}
async function handlePullAll() {
    isPullingAll.value = true;
    try { await adminStore.pullAllPromptZooRepositories(); } 
    finally { isPullingAll.value = false; }
}
async function handleDeleteRepository(repo) {
    const confirmed = await uiStore.showConfirmation({ title: `Delete Repository '${repo.name}'?`, message: 'This will remove the repository and its cached files.', confirmText: 'Delete' });
    if (confirmed) {
        isLoadingAction.value = repo.id;
        try { await adminStore.deletePromptZooRepository(repo.id); } 
        finally { isLoadingAction.value = null; }
    }
}

// --- Prompt Actions ---
async function handleInstallItem(item) {
    try {
        await adminStore.installZooPrompt({ repository: item.repository, folder_name: item.folder_name });
        await fetchZooItems(); // To update 'is_installed' status
        await promptsStore.fetchPrompts(); // To update the installed list
    } catch(e) {}
}
async function showItemHelp(item) {
    const readmeContent = await adminStore.fetchPromptReadme(item.repository, item.folder_name);
    uiStore.openModal('sourceViewer', { title: `README: ${item.name}`, content: readmeContent, language: 'markdown' });
}

// --- Installed Prompts Actions ---
const isEditModalVisible = ref(false);
const currentPrompt = ref(null);

function handleAddPrompt() {
  currentPrompt.value = { name: '', content: '' };
  isEditModalVisible.value = true;
}
function handleEditPrompt(prompt) {
  currentPrompt.value = { ...prompt };
  isEditModalVisible.value = true;
}
async function handleSavePrompt() {
  if (!currentPrompt.value) return;
  const { id, name, content } = currentPrompt.value;
  try {
    if (id) {
      await adminStore.updateSystemPrompt(id, { name, content });
    } else {
      await adminStore.createSystemPrompt({ name, content });
    }
    isEditModalVisible.value = false;
  } catch(e) {}
}
async function handleDeletePrompt(prompt) {
  const confirmed = await uiStore.showConfirmation({ title: `Delete '${prompt.name}'?` });
  if (confirmed) {
    await adminStore.deleteSystemPrompt(prompt.id);
  }
}
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
                <button @click="activeSubTab = 'installed'" class="tab-button" :class="activeSubTab === 'installed' ? 'active' : 'inactive'">Installed</button>
                <button @click="activeSubTab = 'available'" class="tab-button" :class="activeSubTab === 'available' ? 'active' : 'inactive'">Available from Zoo</button>
                <button @click="activeSubTab = 'repositories'" class="tab-button" :class="activeSubTab === 'repositories' ? 'active' : 'inactive'">Repositories</button>
            </nav>
        </div>

        <section v-if="activeSubTab === 'installed'">
            <!-- Content from old SystemPromptsManagement.vue -->
        </section>

        <section v-if="activeSubTab === 'available'">
             <div class="space-y-4">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-4"><div class="relative lg:col-span-1"><input type="text" v-model="searchQuery" placeholder="Search Prompts..." class="input-field w-full pl-10" /><div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"><svg class="h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg></div></div><div class="grid grid-cols-2 lg:col-span-2 gap-4"><select v-model="installationStatusFilter" class="input-field"><option value="All">All Statuses</option><option value="Installed">Installed</option><option value="Uninstalled">Uninstalled</option></select><select v-model="selectedCategory" class="input-field"><option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option></select></div></div>
                <div class="flex items-center gap-2"><select v-model="sortKey" class="input-field w-48"><option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">Sort by {{ opt.label }}</option></select><button @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'" class="btn btn-secondary p-2"><IconArrowUp v-if="sortOrder === 'asc'" class="w-5 h-5" /><IconArrowDown v-else class="w-5 h-5" /></button></div>
                <div v-if="isLoadingZooPrompts" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6"><AppCardSkeleton v-for="i in 8" :key="i" /></div>
                <div v-else-if="!itemsWithTaskStatus || itemsWithTaskStatus.length === 0" class="empty-state-card"><h4 class="font-semibold">No Prompts Found</h4><p class="text-sm">No prompts match your criteria. Add and pull a repository or adjust filters.</p></div>
                <div v-else>
                    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
                        <AppCard v-for="item in itemsWithTaskStatus" :key="`${item.repository}/${item.folder_name}`" :app="item" :task="item.task" :is-starred="starredItems.includes(item.name)" item-type-name="Prompt" @star="handleStarToggle(item.name)" @install="handleInstallItem(item)" @help="showItemHelp(item)" />
                    </div>
                    <div class="mt-6 flex justify-between items-center"><p class="text-sm text-gray-500">{{ pageInfo }}</p><div class="flex gap-2"><button @click="currentPage--" :disabled="currentPage <= 1" class="btn btn-secondary">Previous</button><button @click="currentPage++" :disabled="currentPage >= totalPages" class="btn btn-secondary">Next</button></div></div>
                </div>
            </div>
        </section>
        
        <section v-if="activeSubTab === 'repositories'">
            <div class="flex justify-between items-center mb-4 flex-wrap gap-2">
                <h3 class="text-xl font-semibold">Prompt Zoo Repositories</h3>
                <div class="flex items-center gap-2">
                    <button @click="handlePullAll" class="btn btn-secondary" :disabled="isPullingAll"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isPullingAll}" /><span class="ml-2">Pull All</span></button>
                    <button @click="isAddRepoFormVisible = !isAddRepoFormVisible" class="btn btn-primary">{{ isAddRepoFormVisible ? 'Cancel' : 'Add Repository' }}</button>
                </div>
            </div>
            <transition name="form-fade">
                <div v-if="isAddRepoFormVisible" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm mb-6 overflow-hidden">
                    <form @submit.prevent="handleAddRepository" class="space-y-4">
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div><label for="repo-name-prompt" class="block text-sm font-medium">Name</label><input id="repo-name-prompt" v-model="newRepo.name" type="text" class="input-field mt-1" required></div>
                            <div class="md:col-span-2"><label for="repo-url-prompt" class="block text-sm font-medium">Git URL</label><input id="repo-url-prompt" v-model="newRepo.url" type="url" class="input-field mt-1" required></div>
                        </div>
                        <div class="flex justify-end"><button type="submit" class="btn btn-primary" :disabled="isLoadingAction === 'add'">{{ isLoadingAction === 'add' ? 'Adding...' : 'Add' }}</button></div>
                    </form>
                </div>
            </transition>
            <div v-if="isLoadingPromptZooRepositories" class="text-center p-4">Loading...</div>
            <div v-else-if="!sortedRepositories || sortedRepositories.length === 0" class="empty-state-card"><p>No repositories added.</p></div>
            <div v-else class="space-y-4">
                <div v-for="repo in sortedRepositories" :key="repo.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div class="flex-grow truncate"><p class="font-semibold">{{ repo.name }}</p><p class="text-sm text-gray-500 font-mono truncate">{{ repo.url }}</p><p class="text-xs text-gray-400 mt-1">Last updated: {{ formatDateTime(repo.last_pulled_at) }}</p></div>
                    <div class="flex items-center gap-x-2 flex-shrink-0"><button @click="handlePullRepository(repo)" class="btn btn-secondary btn-sm" :disabled="isLoadingAction === repo.id"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingAction === repo.id}" /><span class="ml-1">Pull</span></button><button v-if="repo.is_deletable" @click="handleDeleteRepository(repo)" class="btn btn-danger btn-sm" :disabled="isLoadingAction === repo.id"><IconTrash class="w-4 h-4" /></button></div>
                </div>
            </div>
        </section>
    </div>

     <!-- Modal from old SystemPromptsManagement.vue -->
    <GenericModal :modalName="'editSystemPrompt'" :title="currentPrompt && currentPrompt.id ? 'Edit System Prompt' : 'Add System Prompt'" @close="isEditModalVisible = false">
        <template #body>
            <form v-if="currentPrompt" @submit.prevent="handleSavePrompt" class="space-y-4">
                <div><label for="prompt-name" class="block text-sm font-medium">Name</label><input id="prompt-name" v-model="currentPrompt.name" type="text" class="input-field mt-1" required></div>
                <div><label for="prompt-content" class="block text-sm font-medium">Content</label><textarea id="prompt-content" v-model="currentPrompt.content" rows="10" class="input-field mt-1"></textarea></div>
            </form>
        </template>
        <template #footer>
            <button @click="isEditModalVisible = false" class="btn btn-secondary">Cancel</button>
            <button @click="handleSavePrompt" class="btn btn-primary">Save</button>
        </template>
    </GenericModal>
</template>