<script setup>
import { ref, onMounted, computed, watch, onUnmounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useAdminStore } from '../../stores/admin';
import { useTasksStore } from '../../stores/tasks';
import { useUiStore } from '../../stores/ui';
import { usePromptsStore } from '../../stores/prompts';
import useEventBus from '../../services/eventBus';
import IconRefresh from '../../assets/icons/IconRefresh.vue';
import IconTrash from '../../assets/icons/IconTrash.vue';
import IconPencil from '../../assets/icons/IconPencil.vue';
import IconArrowUpCircle from '../../assets/icons/IconArrowUpCircle.vue';
import AppCard from '../ui/AppCard.vue';
import AppCardSkeleton from '../ui/AppCardSkeleton.vue';
import GenericModal from '../ui/GenericModal.vue';
import IconSparkles from '../../assets/icons/IconSparkles.vue';

const adminStore = useAdminStore();
const tasksStore = useTasksStore();
const uiStore = useUiStore();
const promptsStore = usePromptsStore();
const { on, off } = useEventBus();

const { promptZooRepositories, isLoadingPromptZooRepositories, zooPrompts, isLoadingZooPrompts } = storeToRefs(adminStore);
const { systemPrompts: installedPrompts, isLoading: isLoadingInstalled } = storeToRefs(promptsStore);
const { tasks } = storeToRefs(tasksStore);

const activeSubTab = ref('installed');

const newRepo = ref({ name: '', url: '' });
const isAddRepoFormVisible = ref(false);
const isLoadingAction = ref(null);
const isPullingAll = ref(false);
const searchQuery = ref('');
const selectedCategory = ref('All');
const installationStatusFilter = ref('All');
const sortKey = ref('last_update_date');
const sortOrder = ref('desc');
const starredItems = ref(JSON.parse(localStorage.getItem('starredPrompts') || '[]'));
const currentPage = ref(1);
const pageSize = ref(24);
let debounceTimer = null;
const pendingGenerationTaskId = ref(null);

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

function debouncedFetch() { clearTimeout(debounceTimer); debounceTimer = setTimeout(() => { currentPage.value = 1; fetchZooItems(); }, 300); }

watch([sortKey, sortOrder, selectedCategory, installationStatusFilter, activeSubTab], () => { if (activeSubTab.value === 'available') { currentPage.value = 1; fetchZooItems(); } });
watch(searchQuery, debouncedFetch);
watch(currentPage, fetchZooItems);
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

const itemsWithTaskStatus = computed(() => {
    if (!Array.isArray(zooPrompts.value.items)) return [];
    const taskMap = new Map();
    tasks.value.forEach(task => { if (task?.name?.startsWith('Installing prompt: ')) { const itemName = task.name.replace('Installing prompt: ', ''); taskMap.set(itemName, task); } });
    return zooPrompts.value.items.map(item => ({ ...item, task: taskMap.get(item.folder_name) || null }));
});
const sortedRepositories = computed(() => Array.isArray(promptZooRepositories.value) ? [...promptZooRepositories.value].sort((a, b) => (a.name || '').localeCompare(b.name || '')) : []);
const categories = computed(() => {
    return zooPrompts.value.categories || ['All'];
});

function formatDateTime(isoString) { if (!isoString) return 'Never'; return new Date(isoString).toLocaleString(); }

async function handleAddRepository() {
    if (!newRepo.value.name || !newRepo.value.url) return;
    isLoadingAction.value = 'add';
    try { await adminStore.addPromptZooRepository(newRepo.value); newRepo.value = { name: '', url: '' }; isAddRepoFormVisible.value = false; }
    finally { isLoadingAction.value = null; }
}
async function handlePullRepository(repo) { isLoadingAction.value = repo.id; try { await adminStore.pullPromptZooRepository(repo.id); } finally { isLoadingAction.value = null; } }
async function handlePullAll() { isPullingAll.value = true; try { await adminStore.pullAllPromptZooRepositories(); } finally { isPullingAll.value = false; } }
async function handleDeleteRepository(repo) {
    if (await uiStore.showConfirmation({ title: `Delete Repository '${repo.name}'?` })) {
        isLoadingAction.value = repo.id;
        try { await adminStore.deletePromptZooRepository(repo.id); } finally { isLoadingAction.value = null; }
    }
}
async function handleInstallItem(item) { await adminStore.installZooPrompt({ repository: item.repository, folder_name: item.folder_name }); }
async function handleUninstallItem(item) {
    const installedPrompt = installedPrompts.value.find(p => p.name === item.name);
    if (!installedPrompt) {
        uiStore.addNotification(`Cannot find installed prompt '${item.name}' to uninstall. Please refresh.`, 'error');
        return;
    }
    if (await uiStore.showConfirmation({ title: `Uninstall '${item.name}'?`, message: 'This will remove the prompt from the system.' })) {
        await adminStore.deleteSystemPrompt(installedPrompt.id);
    }
}
async function showItemHelp(item) { const readme = await adminStore.fetchPromptReadme(item.repository, item.folder_name); uiStore.openModal('sourceViewer', { title: `README: ${item.name}`, content: readme, language: 'markdown' }); }
function showItemDetails(item) {
    uiStore.openModal('sourceViewer', { 
        title: `Details: ${item.name}`, 
        content: item.description || 'No description available.', 
        language: 'text' 
    });
}
function handleStarToggle(itemName) { const i = starredItems.value.indexOf(itemName); if (i > -1) starredItems.value.splice(i, 1); else starredItems.value.push(itemName); }

const currentPrompt = ref(null);
function handleAddPrompt() { currentPrompt.value = { name: '', content: '', category: '', author: '', description: '', icon: null }; uiStore.openModal('editSystemPrompt'); }

function handleGeneratePrompt() {
    uiStore.openModal('generatePrompt', { 
        isSystemPrompt: true,
        onTaskSubmitted: (taskId) => {
            pendingGenerationTaskId.value = taskId;
        }
    });
}

function handleTaskCompletion(task) {
    if (task && task.id === pendingGenerationTaskId.value) {
        pendingGenerationTaskId.value = null;
        
        if (uiStore.isModalOpen('tasksManager')) {
            uiStore.closeModal('tasksManager');
        }

        if (task.status === 'completed' && task.result) {
            handleEditPrompt(task.result);
        } else {
            uiStore.addNotification('System prompt generation did not complete successfully.', 'warning');
        }
    }
}

async function handleUpdatePrompt(prompt) {
    await adminStore.updateSystemPromptFromZoo(prompt.id);
}

function handleEditPrompt(prompt) { currentPrompt.value = { ...prompt }; uiStore.openModal('editSystemPrompt'); }
async function handleSavePrompt() {
    if (!currentPrompt.value) return;
    const { id, ...data } = currentPrompt.value;
    try {
        if (id) await adminStore.updateSystemPrompt(id, data);
        else await adminStore.createSystemPrompt(data);
        uiStore.closeModal('editSystemPrompt');
    } catch(e) {}
}
async function handleDeletePrompt(prompt) {
    if (await uiStore.showConfirmation({ title: `Delete '${prompt.name}'?` })) {
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
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-xl font-semibold">Installed System Prompts</h3>
                <div class="flex items-center gap-2">
                    <button @click="handleGeneratePrompt" class="btn btn-secondary">
                        <IconSparkles class="w-4 h-4 mr-2" />
                        Generate with AI
                    </button>
                    <button @click="handleAddPrompt" class="btn btn-primary">Add Prompt</button>
                </div>
            </div>
            <div v-if="isLoadingInstalled" class="text-center p-4">Loading...</div>
            <div v-else-if="!installedPrompts || installedPrompts.length === 0" class="empty-state-card"><p>No system prompts installed.</p></div>
            <div v-else class="space-y-3">
                <div v-for="prompt in installedPrompts" :key="prompt.id" class="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-sm flex items-center justify-between gap-4">
                    <div class="flex items-center gap-3 flex-grow truncate">
                        <img v-if="prompt.icon" :src="prompt.icon" class="h-8 w-8 rounded-md flex-shrink-0 object-cover" alt="Icon">
                        <div class="flex-grow truncate">
                            <p class="font-medium truncate">{{ prompt.name }}</p>
                            <div v-if="prompt.version" class="text-xs text-gray-500 flex items-center gap-2">
                                <span>v{{ prompt.version }}</span>
                                <span v-if="prompt.update_available" class="text-yellow-600 dark:text-yellow-400 font-semibold">(repo: v{{ prompt.repo_version }})</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center gap-x-2 flex-shrink-0">
                        <button v-if="prompt.update_available" @click="handleUpdatePrompt(prompt)" class="btn btn-warning btn-sm p-2" title="Update"><IconArrowUpCircle class="w-4 h-4" /></button>
                        <button @click="handleEditPrompt(prompt)" class="btn btn-secondary btn-sm p-2" title="Edit"><IconPencil class="w-4 h-4" /></button>
                        <button @click="handleDeletePrompt(prompt)" class="btn btn-danger btn-sm p-2" title="Delete"><IconTrash class="w-4 h-4" /></button>
                    </div>
                </div>
            </div>
        </section>

        <section v-if="activeSubTab === 'available'">
             <div class="space-y-4">
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-4"><input type="text" v-model="searchQuery" placeholder="Search Prompts..." class="input-field" /><select v-model="selectedCategory" class="input-field"><option value="All">All Categories</option><option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option></select></div>
                <div v-if="isLoadingZooPrompts" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6"><AppCardSkeleton v-for="i in 6" :key="i" /></div>
                <div v-else-if="!itemsWithTaskStatus || itemsWithTaskStatus.length === 0" class="empty-state-card"><h4 class="font-semibold">No Prompts Found</h4></div>
                <div v-else>
                    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                        <AppCard v-for="item in itemsWithTaskStatus" :key="`${item.repository}/${item.folder_name}`" :app="item" :task="item.task" :is-starred="starredItems.includes(item.name)" item-type-name="Prompt" @star="handleStarToggle(item.name)" @install="handleInstallItem" @uninstall="handleUninstallItem" @help="showItemHelp" @details="showItemDetails" />
                    </div>
                    <div class="mt-6 flex justify-between items-center"><p class="text-sm text-gray-500">{{ pageInfo }}</p><div class="flex gap-2"><button @click="currentPage--" :disabled="currentPage <= 1" class="btn btn-secondary">Prev</button><button @click="currentPage++" :disabled="currentPage >= totalPages" class="btn btn-secondary">Next</button></div></div>
                </div>
            </div>
        </section>
        
        <section v-if="activeSubTab === 'repositories'">
            <div class="flex justify-between items-center mb-4"><h3 class="text-xl font-semibold">Prompt Zoo Repositories</h3><div class="flex items-center gap-2"><button @click="handlePullAll" class="btn btn-secondary" :disabled="isPullingAll"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isPullingAll}" /><span class="ml-2">Pull All</span></button><button @click="isAddRepoFormVisible = !isAddRepoFormVisible" class="btn btn-primary">{{ isAddRepoFormVisible ? 'Cancel' : 'Add' }}</button></div></div>
            <transition name="form-fade"><div v-if="isAddRepoFormVisible" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm mb-6"><form @submit.prevent="handleAddRepository" class="flex gap-4"><input v-model="newRepo.name" type="text" placeholder="Name" class="input-field flex-1" required><input v-model="newRepo.url" type="url" placeholder="Git URL" class="input-field flex-grow-[2]" required><button type="submit" class="btn btn-primary" :disabled="isLoadingAction === 'add'">Add</button></form></div></transition>
            <div v-if="isLoadingPromptZooRepositories" class="text-center p-4">Loading...</div>
            <div v-else-if="!sortedRepositories || sortedRepositories.length === 0" class="empty-state-card"><p>No repositories added.</p></div>
            <div v-else class="space-y-4">
                <div v-for="repo in sortedRepositories" :key="repo.id" class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm flex items-center justify-between gap-4">
                    <div class="flex-grow truncate"><p class="font-semibold">{{ repo.name }}</p><p class="text-sm text-gray-500 font-mono truncate">{{ repo.url }}</p><p class="text-xs text-gray-400 mt-1">Updated: {{ formatDateTime(repo.last_pulled_at) }}</p></div>
                    <div class="flex items-center gap-x-2"><button @click="handlePullRepository(repo)" class="btn btn-secondary btn-sm" :disabled="isLoadingAction === repo.id"><IconRefresh class="w-4 h-4" :class="{'animate-spin': isLoadingAction === repo.id}" /> Pull</button><button v-if="repo.is_deletable" @click="handleDeleteRepository(repo)" class="btn btn-danger btn-sm" :disabled="isLoadingAction === repo.id"><IconTrash class="w-4 h-4" /></button></div>
                </div>
            </div>
        </section>
    </div>

    <GenericModal :modalName="'editSystemPrompt'" :title="currentPrompt && currentPrompt.id ? 'Edit System Prompt' : 'Add System Prompt'">
        <template #body>
            <form v-if="currentPrompt" @submit.prevent="handleSavePrompt" class="space-y-4">
                <div><label for="prompt-name" class="block text-sm font-medium">Name</label><input id="prompt-name" v-model="currentPrompt.name" type="text" class="input-field mt-1" required></div>
                <div><label for="prompt-content" class="block text-sm font-medium">Content</label><textarea id="prompt-content" v-model="currentPrompt.content" rows="10" class="input-field mt-1"></textarea></div>
            </form>
        </template>
        <template #footer>
            <button @click="uiStore.closeModal('editSystemPrompt')" class="btn btn-secondary">Cancel</button>
            <button @click="handleSavePrompt" class="btn btn-primary">Save</button>
        </template>
    </GenericModal>
</template>